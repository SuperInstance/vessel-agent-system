"""CrewScheduler: crew scheduling and watch management for AELMA.

Tracks crew members, their roles, shift/watch assignments, and fatigue.
State is persisted as a single JSON document (crew roster, watch history,
and rotation indices) that is rewritten atomically after every mutation.

Watch rotation: each named watch (e.g. "nav", "engine") keeps an index
into the crew roster. :meth:`CrewScheduler.rotate_watch` advances the
index and reassigns the watch to the next crew member, skipping members
that are currently fatigued.

State document shape::

    {
      "kind": "crew_schedule_state",
      "crew": {
        "alice": {
          "name": "alice",
          "role": "captain",
          "max_watch_hours": 6.0,
          "added_at": "2026-07-28T10:30:00.000000+00:00"
        }
      },
      "watches": [
        {
          "watch_id": 1,
          "name": "nav",
          "crew": ["alice"],
          "start": "2026-07-28T08:00:00+00:00",
          "end": null
        }
      ],
      "rotation_index": {"nav": 1}
    }

A watch with ``end: null`` is ongoing; assigning a new crew to a watch
name closes the previous watch of that name at the new watch's start.

OpLog integration: when an :class:`~twin.oplog.OpLog` is attached, watch
assignments and rotations are mirrored as ``crew_note`` entries whose
metadata carries ``action`` and ``watch_id`` so crew actions stay linked
to the watches they affected.

Contracts:
- add_crew_member / assign_watch validate arguments and raise
  ValueError/TypeError on bad input.
- Mutations are serialized behind an asyncio.Lock and persisted (atomic
  JSON rewrite) before returning.
- Fatigue is computed from watch history over a trailing window.

Supported roles: captain, engineer, deckhand, cook.

Stdlib only.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .oplog import OpLog, _coerce_ts

log = logging.getLogger("aelma.twin.crew_schedule")

#: Crew roles this system knows how to schedule.
VALID_ROLES = frozenset({"captain", "engineer", "deckhand", "cook"})

#: State document kind identifier.
KIND_SCHEDULE = "crew_schedule_state"

#: Default watch duration when neither end nor duration is given.
DEFAULT_WATCH_HOURS = 4.0

#: Default per-crew-member watch limit used by check_fatigue().
DEFAULT_MAX_WATCH_HOURS = 6.0

#: Default trailing window (hours) over which fatigue is measured.
DEFAULT_FATIGUE_WINDOW_HOURS = 24.0


def _utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    """Get current UTC time as ISO 8601 string."""
    return _utc_now().isoformat()


def _parse_dt(ts: Any) -> datetime:
    """Coerce a timestamp argument to an aware datetime (UTC if naive)."""
    if ts is None:
        return _utc_now()
    iso = _coerce_ts(ts)  # validates type and raises on bad input
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class CrewScheduler:
    """Asyncio-safe crew roster, watch assignments, and fatigue tracking.

    Parameters
    ----------
    path:
        Destination JSON state file. Parent directories created on first
        save. An existing well-formed state file is loaded on init.
    oplog:
        Optional :class:`~twin.oplog.OpLog` to mirror watch assignments
        and rotations into as ``crew_note`` entries.
    """

    def __init__(self, path: str | Path, *, oplog: OpLog | None = None) -> None:
        self._path = Path(path)
        self._oplog = oplog
        self._lock = asyncio.Lock()
        self._closed = False
        self._crew: dict[str, dict[str, Any]] = {}
        self._watches: list[dict[str, Any]] = []
        self._rotation_index: dict[str, int] = {}
        self._next_watch_id = 1
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load existing state from disk, if present."""
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                state = json.load(fh)
        except FileNotFoundError:
            return
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("CrewScheduler: could not load %s: %s", self._path, exc)
            return

        if not isinstance(state, dict) or state.get("kind") != KIND_SCHEDULE:
            log.warning("CrewScheduler: ignoring unrecognized state in %s", self._path)
            return

        crew = state.get("crew", {})
        if isinstance(crew, dict):
            self._crew = {str(k): dict(v) for k, v in crew.items()}

        watches = state.get("watches", [])
        if isinstance(watches, list):
            self._watches = [dict(w) for w in watches if isinstance(w, dict)]

        rotation = state.get("rotation_index", {})
        if isinstance(rotation, dict):
            self._rotation_index = {str(k): int(v) for k, v in rotation.items()}

        ids = [w.get("watch_id", 0) for w in self._watches]
        self._next_watch_id = (max(ids) + 1) if ids else 1

    def _save(self) -> None:
        """Persist state atomically (temp file + replace)."""
        state = {
            "kind": KIND_SCHEDULE,
            "crew": self._crew,
            "watches": self._watches,
            "rotation_index": self._rotation_index,
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2, ensure_ascii=False, default=str)
        os.replace(tmp, self._path)

    # ------------------------------------------------------------------
    # Crew roster
    # ------------------------------------------------------------------

    async def add_crew_member(
        self,
        name: str,
        role: str,
        *,
        max_watch_hours: float = DEFAULT_MAX_WATCH_HOURS,
    ) -> dict[str, Any]:
        """Add a crew member to the roster; return the stored record.

        Parameters
        ----------
        name:
            Unique crew member identifier.
        role:
            One of: captain, engineer, deckhand, cook.
        max_watch_hours:
            Watch-hour limit within the fatigue window. Default 6.
        """
        if not isinstance(name, str) or not name.strip():
            raise ValueError("CrewScheduler.add_crew_member: name must be a non-empty string")
        if role not in VALID_ROLES:
            raise ValueError(
                f"CrewScheduler.add_crew_member: role must be one of "
                f"{sorted(VALID_ROLES)}, got {role!r}"
            )
        if not isinstance(max_watch_hours, (int, float)) or isinstance(max_watch_hours, bool):
            raise TypeError("CrewScheduler.add_crew_member: max_watch_hours must be a number")
        if max_watch_hours <= 0:
            raise ValueError("CrewScheduler.add_crew_member: max_watch_hours must be positive")

        name = name.strip()
        async with self._lock:
            self._ensure_open()
            if name in self._crew:
                raise ValueError(f"CrewScheduler.add_crew_member: duplicate crew member {name!r}")
            member = {
                "name": name,
                "role": role,
                "max_watch_hours": float(max_watch_hours),
                "added_at": _utc_now_iso(),
            }
            self._crew[name] = member
            self._save()
            return dict(member)

    async def remove_crew_member(self, name: str) -> dict[str, Any]:
        """Remove a crew member from the roster; return the removed record.

        Raises ValueError if the member is unknown or currently on watch.
        """
        async with self._lock:
            self._ensure_open()
            if name not in self._crew:
                raise ValueError(f"CrewScheduler.remove_crew_member: unknown crew member {name!r}")
            for watch in self._active_watches(_utc_now()):
                if name in watch["crew"]:
                    raise ValueError(
                        f"CrewScheduler.remove_crew_member: {name!r} is on watch "
                        f"{watch['name']!r}"
                    )
            member = self._crew.pop(name)
            self._save()
            return member

    def list_crew(self) -> list[dict[str, Any]]:
        """Return the crew roster, sorted by name."""
        return [dict(self._crew[n]) for n in sorted(self._crew)]

    # ------------------------------------------------------------------
    # Watch assignment
    # ------------------------------------------------------------------

    async def assign_watch(
        self,
        watch_name: str,
        crew: str | Iterable[str],
        *,
        start: Any = None,
        end: Any = None,
        duration_hours: float | None = None,
        ts: Any = None,
    ) -> dict[str, Any]:
        """Assign crew to a named watch; return the watch record.

        Any previously ongoing watch of the same name is closed at the
        new watch's start. Exactly one of ``end`` / ``duration_hours``
        may be given; with neither, the watch is ongoing (``end=None``).

        Parameters
        ----------
        watch_name:
            Name of the watch (e.g. "nav", "engine", "galley").
        crew:
            Crew member name or iterable of names; all must be on the roster.
        start:
            Watch start (None for now, datetime, epoch seconds, ISO string).
        end:
            Watch end; must be after start.
        duration_hours:
            Alternative to ``end``: positive watch length in hours.
        ts:
            Timestamp used for the mirrored OpLog entry (default: now).
        """
        if not isinstance(watch_name, str) or not watch_name.strip():
            raise ValueError("CrewScheduler.assign_watch: watch_name must be a non-empty string")
        watch_name = watch_name.strip()

        if isinstance(crew, str):
            crew_names = [crew.strip()]
        elif isinstance(crew, Iterable):
            crew_names = [c.strip() if isinstance(c, str) else c for c in crew]
        else:
            raise TypeError("CrewScheduler.assign_watch: crew must be a name or iterable of names")
        if not crew_names or not all(isinstance(c, str) and c for c in crew_names):
            raise ValueError("CrewScheduler.assign_watch: crew must contain non-empty names")

        start_dt = _parse_dt(start)

        if end is not None and duration_hours is not None:
            raise ValueError("CrewScheduler.assign_watch: give end or duration_hours, not both")
        if duration_hours is not None:
            if not isinstance(duration_hours, (int, float)) or isinstance(duration_hours, bool):
                raise TypeError("CrewScheduler.assign_watch: duration_hours must be a number")
            if duration_hours <= 0:
                raise ValueError("CrewScheduler.assign_watch: duration_hours must be positive")
            end_dt = start_dt + timedelta(hours=duration_hours)
        elif end is not None:
            end_dt = _parse_dt(end)
        else:
            end_dt = None
        if end_dt is not None and end_dt <= start_dt:
            raise ValueError("CrewScheduler.assign_watch: end must be after start")

        async with self._lock:
            self._ensure_open()
            unknown = [c for c in crew_names if c not in self._crew]
            if unknown:
                raise ValueError(
                    f"CrewScheduler.assign_watch: unknown crew members: {unknown!r}"
                )

            # Close any ongoing watch of the same name at the new start.
            for watch in self._watches:
                if watch["name"] == watch_name and watch["end"] is None:
                    watch["end"] = start_dt.isoformat()

            watch = {
                "watch_id": self._next_watch_id,
                "name": watch_name,
                "crew": crew_names,
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat() if end_dt is not None else None,
            }
            self._next_watch_id += 1
            self._watches.append(watch)
            self._save()

        await self._log_watch_action(
            "watch_assigned",
            watch,
            f"Assigned {', '.join(crew_names)} to watch {watch_name!r}",
            ts=ts,
        )
        return dict(watch)

    async def rotate_watch(
        self,
        watch_name: str,
        *,
        duration_hours: float = DEFAULT_WATCH_HOURS,
        ts: Any = None,
    ) -> dict[str, Any]:
        """Advance a watch's rotation and assign the next crew member.

        The rotation order is the roster in the order members were added,
        restarting from the beginning when exhausted. Members currently
        fatigued (over their watch-hour limit) are skipped. Raises
        ValueError if no eligible crew member remains.
        """
        if not isinstance(watch_name, str) or not watch_name.strip():
            raise ValueError("CrewScheduler.rotate_watch: watch_name must be a non-empty string")
        watch_name = watch_name.strip()

        async with self._lock:
            self._ensure_open()
            if not self._crew:
                raise ValueError("CrewScheduler.rotate_watch: roster is empty")

            roster = list(self._crew)  # insertion order = order added
            fatigue = self._compute_fatigue(_utc_now(), DEFAULT_FATIGUE_WINDOW_HOURS)
            eligible = [n for n in roster if not fatigue[n]["fatigued"]]
            if not eligible:
                raise ValueError(
                    "CrewScheduler.rotate_watch: all crew members are fatigued"
                )

            idx = self._rotation_index.get(watch_name, 0) % len(roster)
            chosen = None
            for step in range(len(roster)):
                candidate = roster[(idx + step) % len(roster)]
                if candidate in eligible:
                    chosen = candidate
                    self._rotation_index[watch_name] = (idx + step + 1) % len(roster)
                    break
            assert chosen is not None  # eligible is non-empty

        watch = await self.assign_watch(
            watch_name, chosen, start=ts, duration_hours=duration_hours, ts=ts
        )
        await self._log_watch_action(
            "watch_rotated",
            watch,
            f"Rotated watch {watch_name!r} to {chosen}",
            ts=ts,
        )
        return watch

    def get_on_watch_crew(self, ts: Any = None) -> list[dict[str, Any]]:
        """Return crew members on watch at ``ts`` (default: now).

        Each entry is the crew record augmented with the ``watch_name``
        and ``watch_id`` of the watch they are standing.
        """
        now = _parse_dt(ts)
        on_watch: list[dict[str, Any]] = []
        for watch in self._active_watches(now):
            for name in watch["crew"]:
                member = self._crew.get(name)
                if member is None:
                    continue
                entry = dict(member)
                entry["watch_name"] = watch["name"]
                entry["watch_id"] = watch["watch_id"]
                on_watch.append(entry)
        on_watch.sort(key=lambda m: m["name"])
        return on_watch

    def list_watches(self, *, name: str | None = None) -> list[dict[str, Any]]:
        """Return watch records, oldest first; optionally filter by watch name."""
        watches = [dict(w) for w in self._watches if name is None or w["name"] == name]
        watches.sort(key=lambda w: w["watch_id"])
        return watches

    def _active_watches(self, now: datetime) -> list[dict[str, Any]]:
        """Return watches covering ``now``."""
        active = []
        for watch in self._watches:
            start = datetime.fromisoformat(watch["start"])
            end = datetime.fromisoformat(watch["end"]) if watch["end"] else None
            if start <= now and (end is None or now < end):
                active.append(watch)
        return active

    # ------------------------------------------------------------------
    # Fatigue
    # ------------------------------------------------------------------

    def check_fatigue(
        self,
        name: str | None = None,
        *,
        window_hours: float = DEFAULT_FATIGUE_WINDOW_HOURS,
        ts: Any = None,
    ) -> dict[str, dict[str, Any]]:
        """Check watch-hour totals against per-member limits.

        Parameters
        ----------
        name:
            Check a single crew member (None = entire roster).
        window_hours:
            Trailing window in hours over which watch time is summed.
        ts:
            Reference time for the window end (default: now).

        Returns
        -------
        dict
            ``{name: {"hours_on_watch", "max_watch_hours", "fatigued"}}``.
        """
        if not isinstance(window_hours, (int, float)) or isinstance(window_hours, bool):
            raise TypeError("CrewScheduler.check_fatigue: window_hours must be a number")
        if window_hours <= 0:
            raise ValueError("CrewScheduler.check_fatigue: window_hours must be positive")

        now = _parse_dt(ts)
        if name is not None:
            if name not in self._crew:
                raise ValueError(f"CrewScheduler.check_fatigue: unknown crew member {name!r}")
            names = [name]
        else:
            names = list(self._crew)

        fatigue = self._compute_fatigue(now, float(window_hours))
        return {n: fatigue[n] for n in names}

    def _compute_fatigue(self, now: datetime, window_hours: float) -> dict[str, dict[str, Any]]:
        """Sum each member's watch hours inside the trailing window."""
        window_start = now - timedelta(hours=window_hours)
        hours: dict[str, float] = {n: 0.0 for n in self._crew}

        for watch in self._watches:
            start = datetime.fromisoformat(watch["start"])
            end = datetime.fromisoformat(watch["end"]) if watch["end"] else now
            overlap_start = max(start, window_start)
            overlap_end = min(end, now)
            if overlap_end <= overlap_start:
                continue
            watch_hours = (overlap_end - overlap_start).total_seconds() / 3600.0
            for name in watch["crew"]:
                if name in hours:
                    hours[name] += watch_hours

        return {
            name: {
                "hours_on_watch": round(hours[name], 4),
                "max_watch_hours": self._crew[name]["max_watch_hours"],
                "fatigued": hours[name] > self._crew[name]["max_watch_hours"],
            }
            for name in self._crew
        }

    # ------------------------------------------------------------------
    # OpLog integration / lifecycle
    # ------------------------------------------------------------------

    async def _log_watch_action(
        self,
        action: str,
        watch: dict[str, Any],
        message: str,
        *,
        ts: Any = None,
    ) -> None:
        """Mirror a crew scheduling action into the attached OpLog."""
        if self._oplog is None:
            return
        await self._oplog.log_entry(
            "crew_note",
            ",".join(watch["crew"]),
            message,
            metadata={
                "action": action,
                "watch_id": watch["watch_id"],
                "watch_name": watch["name"],
                "start": watch["start"],
                "end": watch["end"],
            },
            ts=ts,
        )

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("CrewScheduler: operation after close()")

    async def stats(self) -> dict[str, Any]:
        """Lightweight status snapshot."""
        return {
            "path": str(self._path),
            "crew": len(self._crew),
            "watches": len(self._watches),
            "on_watch": len(self.get_on_watch_crew()),
            "closed": self._closed,
        }

    async def close(self) -> None:
        """Mark the scheduler closed. Later mutations raise RuntimeError."""
        async with self._lock:
            self._closed = True

    async def __aenter__(self) -> "CrewScheduler":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()
