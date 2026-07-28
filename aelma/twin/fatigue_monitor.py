"""FatigueMonitor: crew fatigue tracking and compliance for AELMA.

Prevents fatigue-related accidents by tracking per-crew watch/work
history and scoring fatigue against maritime rest rules:

- **10 hr max shift** — a single continuous watch may not exceed 10 hours.
- **8 hr min rest** — at least 8 hours of rest between shifts.
- **24 hr weekly limit** — no more than 24 hours worked in any trailing
  7-day window.

Tracked per crew member:

- ``hours_on_watch`` — length of the current ongoing watch (0 when off
  watch).
- ``hours_worked_last_24h`` — watch hours inside the trailing 24 hours.
- ``hours_rested`` — hours since the most recent watch ended (0 while
  on watch).
- ``consecutive_shifts`` — shifts in a row separated by less than the
  minimum rest.

State is persisted as a single JSON document (watch sessions per crew
member plus the set of CrewScheduler watch ids already imported) that is
rewritten atomically after every mutation.

State document shape::

    {
      "kind": "fatigue_monitor_state",
      "crew": {
        "alice": {
          "sessions": [
            {"start": "2026-07-28T08:00:00+00:00",
             "end": "2026-07-28T12:00:00+00:00"}
          ]
        }
      },
      "synced_watch_ids": [1, 2]
    }

A session with ``end: null`` is an ongoing watch.

CrewScheduler integration: when a :class:`~twin.crew_schedule.CrewScheduler`
is attached, :meth:`FatigueMonitor.log_watch_start` validates the crew
member against the roster, and :meth:`FatigueMonitor.sync_from_scheduler`
imports the scheduler's watch history (idempotent per watch id).

WatcherRegistry integration: :meth:`FatigueMonitor.register_watchers`
installs a ``crew-fatigue-risk`` rule that fires a ``raise_alert``
action whenever any crew member's fatigue score crosses the alert
threshold or a compliance rule is violated. Feed it frames from
:meth:`FatigueMonitor.build_frame`.

Contracts:
- log_watch_start / log_watch_end validate arguments and raise
  ValueError/TypeError on bad input.
- Mutations are serialized behind an asyncio.Lock and persisted (atomic
  JSON rewrite) before returning.
- get_fatigue_score / check_compliance are pure reads over the tracked
  history at a reference time (default: now).

Stdlib only.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .oplog import _coerce_ts

log = logging.getLogger("aelma.twin.fatigue_monitor")

#: State document kind identifier.
KIND_FATIGUE = "fatigue_monitor_state"

#: Maximum length of a single continuous watch, in hours.
MAX_SHIFT_HOURS = 10.0

#: Minimum rest required between shifts, in hours.
MIN_REST_HOURS = 8.0

#: Maximum hours worked inside a trailing 7-day window, in hours.
MAX_WEEKLY_HOURS = 24.0

#: Trailing window for hours_worked_last_24h, in hours.
DAY_WINDOW_HOURS = 24.0

#: Trailing window for the weekly limit, in hours.
WEEK_WINDOW_HOURS = 168.0

#: Default fatigue score (0..1) at or above which the watcher rule fires.
DEFAULT_ALERT_THRESHOLD = 0.7

#: Consecutive-shift count treated as "fully fatigued" for scoring.
CONSECUTIVE_SHIFTS_CAP = 3


def _utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


def _parse_dt(ts: Any) -> datetime:
    """Coerce a timestamp argument to an aware datetime (UTC if naive)."""
    if ts is None:
        return _utc_now()
    iso = _coerce_ts(ts)  # validates type and raises on bad input
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class FatigueMonitor:
    """Asyncio-safe crew fatigue tracker with compliance checks.

    Parameters
    ----------
    path:
        Destination JSON state file. Parent directories created on first
        save. An existing well-formed state file is loaded on init.
    scheduler:
        Optional :class:`~twin.crew_schedule.CrewScheduler`. When given,
        ``log_watch_start`` validates crew against the roster and
        ``sync_from_scheduler`` can import its watch history.
    max_shift_hours:
        Maximum length of one continuous watch (default 10).
    min_rest_hours:
        Minimum rest between shifts (default 8).
    max_weekly_hours:
        Maximum hours worked in a trailing 7-day window (default 24).
    """

    def __init__(
        self,
        path: str | Path,
        *,
        scheduler: Any = None,
        max_shift_hours: float = MAX_SHIFT_HOURS,
        min_rest_hours: float = MIN_REST_HOURS,
        max_weekly_hours: float = MAX_WEEKLY_HOURS,
    ) -> None:
        for label, value in (
            ("max_shift_hours", max_shift_hours),
            ("min_rest_hours", min_rest_hours),
            ("max_weekly_hours", max_weekly_hours),
        ):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise TypeError(f"FatigueMonitor: {label} must be a number")
            if value <= 0:
                raise ValueError(f"FatigueMonitor: {label} must be positive")

        self._path = Path(path)
        self._scheduler = scheduler
        self._max_shift_hours = float(max_shift_hours)
        self._min_rest_hours = float(min_rest_hours)
        self._max_weekly_hours = float(max_weekly_hours)
        self._lock = asyncio.Lock()
        self._closed = False
        # crew_id -> {"sessions": [{"start": iso, "end": iso|None}]}
        self._crew: dict[str, dict[str, Any]] = {}
        self._synced_watch_ids: set[int] = set()
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
            log.warning("FatigueMonitor: could not load %s: %s", self._path, exc)
            return

        if not isinstance(state, dict) or state.get("kind") != KIND_FATIGUE:
            log.warning("FatigueMonitor: ignoring unrecognized state in %s", self._path)
            return

        crew = state.get("crew", {})
        if isinstance(crew, dict):
            for cid, rec in crew.items():
                if not isinstance(rec, dict):
                    continue
                sessions = [
                    {"start": s["start"], "end": s.get("end")}
                    for s in rec.get("sessions", [])
                    if isinstance(s, dict) and "start" in s
                ]
                self._crew[str(cid)] = {"sessions": sessions}

        synced = state.get("synced_watch_ids", [])
        if isinstance(synced, list):
            self._synced_watch_ids = {int(i) for i in synced}

    def _save(self) -> None:
        """Persist state atomically (temp file + replace)."""
        state = {
            "kind": KIND_FATIGUE,
            "crew": self._crew,
            "synced_watch_ids": sorted(self._synced_watch_ids),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2, ensure_ascii=False, default=str)
        os.replace(tmp, self._path)

    # ------------------------------------------------------------------
    # Watch logging
    # ------------------------------------------------------------------

    async def log_watch_start(self, crew_id: str, *, ts: Any = None) -> dict[str, Any]:
        """Start a watch for ``crew_id``; return the session record.

        Raises ValueError if the crew member is already on watch, or (when
        a scheduler is attached) is not on the roster.
        """
        crew_id = self._validate_crew_id(crew_id, "log_watch_start")
        start_dt = _parse_dt(ts)

        async with self._lock:
            self._ensure_open()
            self._check_roster(crew_id, "log_watch_start")
            record = self._crew.setdefault(crew_id, {"sessions": []})
            if record["sessions"] and record["sessions"][-1]["end"] is None:
                raise ValueError(
                    f"FatigueMonitor.log_watch_start: {crew_id!r} is already on watch"
                )
            session = {"start": start_dt.isoformat(), "end": None}
            record["sessions"].append(session)
            self._save()
            return dict(session)

    async def log_watch_end(self, crew_id: str, *, ts: Any = None) -> dict[str, Any]:
        """End the ongoing watch for ``crew_id``; return the session record.

        Raises ValueError if the crew member is not currently on watch.
        """
        crew_id = self._validate_crew_id(crew_id, "log_watch_end")
        end_dt = _parse_dt(ts)

        async with self._lock:
            self._ensure_open()
            record = self._crew.get(crew_id)
            if record is None or not record["sessions"] or record["sessions"][-1]["end"] is not None:
                raise ValueError(
                    f"FatigueMonitor.log_watch_end: {crew_id!r} is not on watch"
                )
            session = record["sessions"][-1]
            start_dt = datetime.fromisoformat(session["start"])
            if end_dt <= start_dt:
                raise ValueError(
                    "FatigueMonitor.log_watch_end: end must be after the watch start"
                )
            session["end"] = end_dt.isoformat()
            self._save()
            return dict(session)

    # ------------------------------------------------------------------
    # Metrics and scoring
    # ------------------------------------------------------------------

    def get_metrics(self, crew_id: str, *, ts: Any = None) -> dict[str, Any]:
        """Return the tracked fatigue metrics for ``crew_id`` at ``ts``.

        Keys: ``hours_on_watch``, ``hours_worked_last_24h``,
        ``hours_rested``, ``consecutive_shifts``, ``on_watch``,
        ``hours_worked_last_7d``.
        """
        crew_id = self._validate_crew_id(crew_id, "get_metrics")
        now = _parse_dt(ts)
        sessions = self._sessions(crew_id)

        hours_on_watch = 0.0
        on_watch = False
        if sessions and sessions[-1]["end"] is None:
            start = datetime.fromisoformat(sessions[-1]["start"])
            hours_on_watch = max(0.0, (now - start).total_seconds() / 3600.0)
            on_watch = True

        hours_24h = self._sum_hours(sessions, now, DAY_WINDOW_HOURS)
        hours_7d = self._sum_hours(sessions, now, WEEK_WINDOW_HOURS)

        hours_rested = 0.0
        if not on_watch and sessions:
            last_end = datetime.fromisoformat(sessions[-1]["end"])
            hours_rested = max(0.0, (now - last_end).total_seconds() / 3600.0)

        return {
            "crew_id": crew_id,
            "on_watch": on_watch,
            "hours_on_watch": round(hours_on_watch, 4),
            "hours_worked_last_24h": round(hours_24h, 4),
            "hours_rested": round(hours_rested, 4),
            "consecutive_shifts": self._consecutive_shifts(sessions, now),
            "hours_worked_last_7d": round(hours_7d, 4),
        }

    def get_fatigue_score(self, crew_id: str, *, ts: Any = None) -> float:
        """Return a 0..1 fatigue score for ``crew_id`` at ``ts``.

        Weighted blend of the tracked metrics, each normalized against its
        rule limit and capped at 1.5x:

        - 45% current shift length vs. the max shift limit
        - 30% hours worked in the last 24h vs. the max shift limit
        - 15% hours worked in the last 7d vs. the weekly limit
        - 10% consecutive shifts vs. a 3-shift cap

        A score of 1.0 means fully fatigued; >= 0.7 is the default alert
        threshold used by :meth:`register_watchers`.
        """
        m = self.get_metrics(crew_id, ts=ts)
        score = (
            0.45 * min(m["hours_on_watch"] / self._max_shift_hours, 1.5)
            + 0.30 * min(m["hours_worked_last_24h"] / self._max_shift_hours, 1.5)
            + 0.15 * min(m["hours_worked_last_7d"] / self._max_weekly_hours, 1.5)
            + 0.10 * min(m["consecutive_shifts"] / CONSECUTIVE_SHIFTS_CAP, 1.5)
        )
        return round(min(1.0, max(0.0, score)), 4)

    def check_compliance(self, *, ts: Any = None) -> dict[str, dict[str, Any]]:
        """Check all tracked crew against the fatigue rules at ``ts``.

        Returns ``{crew_id: {"compliant": bool, "violations": [...]}}``
        where each violation is ``{"rule", "value", "limit", "detail"}``.
        Rules checked:

        - ``shift_exceeded`` — ongoing watch longer than max shift hours.
        - ``rest_violation`` — a gap between shifts below min rest hours.
        - ``weekly_exceeded`` — hours in the trailing 7 days over the
          weekly limit.
        """
        now = _parse_dt(ts)
        report: dict[str, dict[str, Any]] = {}
        for crew_id in sorted(self._crew):
            violations: list[dict[str, Any]] = []
            m = self.get_metrics(crew_id, ts=now)

            if m["hours_on_watch"] > self._max_shift_hours:
                violations.append({
                    "rule": "shift_exceeded",
                    "value": m["hours_on_watch"],
                    "limit": self._max_shift_hours,
                    "detail": (
                        f"ongoing watch of {m['hours_on_watch']:.1f}h exceeds "
                        f"the {self._max_shift_hours:.0f}h max shift"
                    ),
                })

            if m["hours_worked_last_7d"] > self._max_weekly_hours:
                violations.append({
                    "rule": "weekly_exceeded",
                    "value": m["hours_worked_last_7d"],
                    "limit": self._max_weekly_hours,
                    "detail": (
                        f"{m['hours_worked_last_7d']:.1f}h worked in the last 7d "
                        f"exceeds the {self._max_weekly_hours:.0f}h weekly limit"
                    ),
                })

            gaps = self._short_rest_gaps(self._sessions(crew_id))
            if gaps:
                worst = min(gaps)
                violations.append({
                    "rule": "rest_violation",
                    "value": round(worst, 4),
                    "limit": self._min_rest_hours,
                    "detail": (
                        f"rest gap of {worst:.1f}h is below the "
                        f"{self._min_rest_hours:.0f}h minimum rest"
                    ),
                })

            report[crew_id] = {
                "compliant": not violations,
                "violations": violations,
            }
        return report

    # ------------------------------------------------------------------
    # CrewScheduler integration
    # ------------------------------------------------------------------

    async def sync_from_scheduler(self) -> int:
        """Import watch history from the attached CrewScheduler.

        Each scheduler watch becomes a session for every crew member on
        it. Already-imported watch ids are skipped, so the call is
        idempotent. Returns the number of newly imported watches. Raises
        RuntimeError when no scheduler is attached.
        """
        if self._scheduler is None:
            raise RuntimeError("FatigueMonitor: no CrewScheduler attached")

        imported = 0
        async with self._lock:
            self._ensure_open()
            for watch in self._scheduler.list_watches():
                watch_id = watch.get("watch_id")
                if watch_id in self._synced_watch_ids:
                    continue
                for name in watch.get("crew", []):
                    record = self._crew.setdefault(name, {"sessions": []})
                    record["sessions"].append(
                        {"start": watch["start"], "end": watch["end"]}
                    )
                self._synced_watch_ids.add(watch_id)
                imported += 1
            for record in self._crew.values():
                record["sessions"].sort(key=lambda s: s["start"])
            if imported:
                self._save()
        return imported

    # ------------------------------------------------------------------
    # WatcherRegistry integration
    # ------------------------------------------------------------------

    def build_frame(self, *, ts: Any = None) -> dict[str, Any]:
        """Build a watcher frame with the current crew fatigue picture.

        Keys: ``fatigue_scores`` ({crew_id: score}), ``max_fatigue_score``,
        ``at_risk_crew`` (crew at or above the alert threshold),
        ``violations`` (compliance report from :meth:`check_compliance`).
        """
        now = _parse_dt(ts)
        scores = {
            crew_id: self.get_fatigue_score(crew_id, ts=now)
            for crew_id in sorted(self._crew)
        }
        return {
            "fatigue_scores": scores,
            "max_fatigue_score": max(scores.values(), default=0.0),
            "at_risk_crew": [
                cid for cid, s in scores.items() if s >= DEFAULT_ALERT_THRESHOLD
            ],
            "violations": self.check_compliance(ts=now),
        }

    def register_watchers(
        self,
        registry: Any,
        *,
        alert_threshold: float = DEFAULT_ALERT_THRESHOLD,
        cooldown_s: float = 300.0,
    ) -> str:
        """Register a ``crew-fatigue-risk`` rule on a WatcherRegistry.

        The rule fires a ``raise_alert`` action when a frame (as built by
        :meth:`build_frame`) shows any crew member at or above
        ``alert_threshold`` or with a compliance violation. Returns the
        rule id.
        """
        if not isinstance(alert_threshold, (int, float)) or isinstance(alert_threshold, bool):
            raise TypeError("FatigueMonitor.register_watchers: alert_threshold must be a number")
        if not 0.0 < alert_threshold <= 1.0:
            raise ValueError("FatigueMonitor.register_watchers: alert_threshold must be in (0, 1]")

        def _at_risk(frame: Any) -> list[str]:
            scores = frame.get("fatigue_scores", {})
            risk = {cid for cid, s in scores.items() if s >= alert_threshold}
            for cid, rep in frame.get("violations", {}).items():
                if not rep.get("compliant", True):
                    risk.add(cid)
            return sorted(risk)

        def _when(frame: Any) -> bool:
            return bool(_at_risk(frame))

        def _payload(frame: Any) -> dict[str, Any]:
            risk = _at_risk(frame)
            return {
                "kind": "crew_fatigue",
                "crew": risk,
                "fatigue_scores": {
                    cid: frame.get("fatigue_scores", {}).get(cid) for cid in risk
                },
                "violations": {
                    cid: frame.get("violations", {}).get(cid, {}).get("violations", [])
                    for cid in risk
                },
            }

        def _reason(frame: Any) -> str:
            risk = _at_risk(frame)
            top = frame.get("max_fatigue_score", 0.0)
            return f"crew fatigue risk: {', '.join(risk)} (max score {top:.2f})"

        def _priority(frame: Any) -> float:
            return min(1.0, 0.6 + 0.4 * float(frame.get("max_fatigue_score", 0.0)))

        return registry.add({
            "id": "crew-fatigue-risk",
            "name": "Crew fatigue risk",
            "when": _when,
            "action": {
                "name": "raise_alert",
                "payload": _payload,
                "reason": _reason,
                "priority": _priority,
            },
            "cooldown_s": cooldown_s,
        })

    # ------------------------------------------------------------------
    # Internals / lifecycle
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_crew_id(crew_id: Any, op: str) -> str:
        if not isinstance(crew_id, str) or not crew_id.strip():
            raise ValueError(
                f"FatigueMonitor.{op}: crew_id must be a non-empty string"
            )
        return crew_id.strip()

    def _check_roster(self, crew_id: str, op: str) -> None:
        if self._scheduler is None:
            return
        roster = {m["name"] for m in self._scheduler.list_crew()}
        if crew_id not in roster:
            raise ValueError(
                f"FatigueMonitor.{op}: unknown crew member {crew_id!r}"
            )

    def _sessions(self, crew_id: str) -> list[dict[str, Any]]:
        record = self._crew.get(crew_id)
        if record is None:
            return []
        return sorted(record["sessions"], key=lambda s: s["start"])

    @staticmethod
    def _sum_hours(
        sessions: list[dict[str, Any]], now: datetime, window_hours: float
    ) -> float:
        """Sum session hours overlapping the trailing window ending at now."""
        window_start = now - timedelta(hours=window_hours)
        total = 0.0
        for session in sessions:
            start = datetime.fromisoformat(session["start"])
            end = datetime.fromisoformat(session["end"]) if session["end"] else now
            overlap_start = max(start, window_start)
            overlap_end = min(end, now)
            if overlap_end > overlap_start:
                total += (overlap_end - overlap_start).total_seconds() / 3600.0
        return total

    def _consecutive_shifts(
        self, sessions: list[dict[str, Any]], now: datetime
    ) -> int:
        """Count trailing shifts separated by less than the min rest."""
        count = 0
        prev_end: datetime | None = None
        for session in reversed(sessions):
            start = datetime.fromisoformat(session["start"])
            end = datetime.fromisoformat(session["end"]) if session["end"] else now
            if end > now:
                continue  # session starts in the future; ignore
            if prev_end is None and session["end"] is not None:
                # Rest since the last shift ended counts too: a crew member
                # who has rested the minimum starts a fresh streak.
                if (now - end).total_seconds() / 3600.0 >= self._min_rest_hours:
                    break
            if prev_end is not None:
                gap = (prev_end - end).total_seconds() / 3600.0
                if gap >= self._min_rest_hours:
                    break
            count += 1
            prev_end = start
        return count

    def _short_rest_gaps(self, sessions: list[dict[str, Any]]) -> list[float]:
        """Return rest gaps (hours) between completed shifts below min rest."""
        gaps: list[float] = []
        prev_end: datetime | None = None
        for session in sessions:
            start = datetime.fromisoformat(session["start"])
            if prev_end is not None:
                gap = (start - prev_end).total_seconds() / 3600.0
                if gap < self._min_rest_hours:
                    gaps.append(gap)
            if session["end"] is not None:
                prev_end = datetime.fromisoformat(session["end"])
        return gaps

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("FatigueMonitor: operation after close()")

    async def stats(self) -> dict[str, Any]:
        """Lightweight status snapshot."""
        return {
            "path": str(self._path),
            "crew": len(self._crew),
            "on_watch": sum(
                1
                for rec in self._crew.values()
                if rec["sessions"] and rec["sessions"][-1]["end"] is None
            ),
            "synced_watches": len(self._synced_watch_ids),
            "limits": {
                "max_shift_hours": self._max_shift_hours,
                "min_rest_hours": self._min_rest_hours,
                "max_weekly_hours": self._max_weekly_hours,
            },
            "closed": self._closed,
        }

    async def close(self) -> None:
        """Mark the monitor closed. Later mutations raise RuntimeError."""
        async with self._lock:
            self._closed = True

    async def __aenter__(self) -> "FatigueMonitor":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()
