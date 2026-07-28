"""GearTracker: fishing gear deployment tracking for AELMA.

Records gear deployment and retrieval events (type, line_length, depth,
start_time, end_time) to an append-only JSONL file. Deployments and
retrievals are separate records linked by ``deployment_id``; active gear
is the set of deployments with no matching retrieval.

Record shape (one JSON object per line)::

    {
      "kind":          "gear_deployment",
      "event":         "deploy",            # or "retrieve"
      "deployment_id": "9f2c1a4b7e3d",
      "gear_type":     "pots",              # deploy only
      "line_length":   150.0,               # deploy only, meters
      "depth":         40.0,                # deploy only, meters
      "start_time":    "2026-07-28T10:30:00+00:00",  # deploy only
      "end_time":      null,                # retrieve only
      "_loggedAt":     "2026-07-28T10:30:00.123456+00:00",
      "_seq":          0
    }

Contracts:
- Append-only. Records are never mutated or deleted through this class;
  a retrieval is a new record, not an edit of the deployment record.
- deploy_gear/retrieve_gear validate arguments and raise
  ValueError/TypeError on bad input.
- Writes are serialized behind an asyncio.Lock for unique, ordered _seq
  values and consistent active-gear state.
- File is flushed after every record. Gear events are low-frequency.
- JSONL storage with timestamps. Active gear state is rebuilt from the
  file on startup, so restarts resume correctly.
- When a mode manager is attached, deploy_gear auto-sets the
  ``GEAR_DEPLOYED`` fishing mode, and retrieve_gear returns the vessel to
  ``FISHING`` once the last active gear is hauled. Mode sync failures are
  logged, never raised — gear logging must not break on mode errors.

Supported gear types: troll_lines, pots, nets, dredges.

Mode manager integration is duck-typed: any object exposing
``set_mode(mode: str, reason: str)`` works, e.g. the FishingModeManager
from build_kimi/twin/fishing_modes.py (which accepts string modes).

Stdlib only.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .oplog import _coerce_ts

log = logging.getLogger("aelma.twin.gear_tracker")

#: Gear types this system knows how to track.
VALID_GEAR_TYPES = frozenset({"troll_lines", "pots", "nets", "dredges"})

#: Record kind identifier.
KIND_GEAR = "gear_deployment"

#: Event names within a gear_deployment record.
EVENT_DEPLOY = "deploy"
EVENT_RETRIEVE = "retrieve"

#: Mode set on the attached mode manager when gear goes in the water.
MODE_GEAR_DEPLOYED = "GEAR_DEPLOYED"

#: Mode set when the last active gear is retrieved.
MODE_FISHING = "FISHING"


def _utc_now_iso() -> str:
    """Get current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _parse_iso(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp; naive values are assumed UTC."""
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class GearTracker:
    """Asyncio-safe append-only JSONL log of gear deployment events.

    Parameters
    ----------
    path:
        Destination JSONL file. Parent directories created on first append.
        Existing file is appended to; _seq continues from line count and
        active gear state is rebuilt from deploy/retrieve records.
    mode_manager:
        Optional mode manager (e.g. FishingModeManager) to auto-sync the
        vessel's operational mode on deploy/retrieve. Duck-typed: must
        expose ``set_mode(mode: str, reason: str)``.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        mode_manager: Any = None,
    ) -> None:
        self._path = Path(path)
        self._mode_manager = mode_manager
        self._lock = asyncio.Lock()
        self._closed = False
        # deployment_id -> deploy record, for gear currently in the water.
        self._active: dict[str, dict[str, Any]] = {}
        self._known_ids: set[str] = set()
        self._seq = self._load_existing()

    @property
    def path(self) -> Path:
        """Path to the active log file."""
        return self._path

    @property
    def seq(self) -> int:
        """The _seq value the next appended record will receive."""
        return self._seq

    @property
    def closed(self) -> bool:
        """Whether the tracker is closed."""
        return self._closed

    def _load_existing(self) -> int:
        """Scan the log file to resume _seq and rebuild active gear state."""
        count = 0
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    count += 1
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        log.warning(
                            "GearTracker: skipping malformed line in %s", self._path
                        )
                        continue
                    if record.get("kind") != KIND_GEAR:
                        continue
                    deployment_id = record.get("deployment_id")
                    if isinstance(deployment_id, str) and deployment_id:
                        self._known_ids.add(deployment_id)
                    if record.get("event") == EVENT_DEPLOY:
                        self._active[deployment_id] = record
                    elif record.get("event") == EVENT_RETRIEVE:
                        self._active.pop(deployment_id, None)
        except FileNotFoundError:
            return 0
        except OSError as exc:
            log.warning(
                "GearTracker: could not scan %s for state resume: %s", self._path, exc
            )
        return count

    async def deploy_gear(
        self,
        gear_type: str,
        line_length: float,
        depth: float,
        *,
        deployment_id: str | None = None,
        ts: Any = None,
    ) -> dict[str, Any]:
        """Validate and persist one gear deployment; return it as written.

        Parameters
        ----------
        gear_type:
            One of :data:`VALID_GEAR_TYPES` (case-insensitive).
        line_length:
            Length of deployed line in meters. Must be a positive number.
        depth:
            Deployment depth in meters. Must be a non-negative number.
        deployment_id:
            Optional caller-assigned identifier; a unique one is generated
            when omitted. Must not collide with a previously used id.
        ts:
            Deployment start time (None for now, datetime, epoch seconds,
            or ISO string).

        Returns
        -------
        dict
            The exact object serialized to disk, including augmented fields.
        """
        if self._closed:
            raise RuntimeError("GearTracker: deploy_gear after close()")

        # Validate gear type
        if not isinstance(gear_type, str) or not gear_type.strip():
            raise ValueError(
                "GearTracker.deploy_gear: gear_type must be a non-empty string"
            )
        gear_type = gear_type.strip().lower()
        if gear_type not in VALID_GEAR_TYPES:
            raise ValueError(
                f"GearTracker.deploy_gear: gear_type must be one of "
                f"{sorted(VALID_GEAR_TYPES)}, got {gear_type!r}"
            )

        # Validate line_length
        if not _is_number(line_length):
            raise TypeError(
                f"GearTracker.deploy_gear: line_length must be a number, got "
                f"{type(line_length).__name__}"
            )
        if line_length <= 0:
            raise ValueError(
                f"GearTracker.deploy_gear: line_length must be > 0, got "
                f"{line_length!r}"
            )

        # Validate depth
        if not _is_number(depth):
            raise TypeError(
                f"GearTracker.deploy_gear: depth must be a number, got "
                f"{type(depth).__name__}"
            )
        if depth < 0:
            raise ValueError(
                f"GearTracker.deploy_gear: depth must be >= 0, got {depth!r}"
            )

        # Validate / generate deployment id
        if deployment_id is None:
            deployment_id = uuid.uuid4().hex[:12]
        else:
            if not isinstance(deployment_id, str) or not deployment_id.strip():
                raise ValueError(
                    "GearTracker.deploy_gear: deployment_id must be a non-empty "
                    "string or None"
                )
            deployment_id = deployment_id.strip()
            if deployment_id in self._known_ids:
                raise ValueError(
                    f"GearTracker.deploy_gear: deployment_id {deployment_id!r} "
                    f"already used"
                )

        async with self._lock:
            if self._closed:
                raise RuntimeError("GearTracker: deploy_gear after close()")

            record = {
                "kind": KIND_GEAR,
                "event": EVENT_DEPLOY,
                "deployment_id": deployment_id,
                "gear_type": gear_type,
                "line_length": float(line_length),
                "depth": float(depth),
                "start_time": _coerce_ts(ts),
                "end_time": None,
                "_loggedAt": _utc_now_iso(),
                "_seq": self._seq,
            }
            self._write_line(record)
            self._seq += 1
            self._active[deployment_id] = record
            self._known_ids.add(deployment_id)

        # Sync mode outside the lock — mode manager has its own.
        self._sync_mode(
            MODE_GEAR_DEPLOYED,
            f"Deployed {gear_type} (deployment {deployment_id})",
        )

        return record

    async def retrieve_gear(
        self,
        deployment_id: str,
        *,
        ts: Any = None,
    ) -> dict[str, Any]:
        """Validate and persist one gear retrieval; return it as written.

        Parameters
        ----------
        deployment_id:
            Identifier of an active (deployed, not yet retrieved) gear
            deployment.
        ts:
            Retrieval end time (None for now, datetime, epoch seconds, or
            ISO string). Must not precede the deployment's start_time.

        Returns
        -------
        dict
            The exact object serialized to disk, including augmented fields.
        """
        if self._closed:
            raise RuntimeError("GearTracker: retrieve_gear after close()")

        if not isinstance(deployment_id, str) or not deployment_id.strip():
            raise ValueError(
                "GearTracker.retrieve_gear: deployment_id must be a non-empty string"
            )
        deployment_id = deployment_id.strip()

        async with self._lock:
            if self._closed:
                raise RuntimeError("GearTracker: retrieve_gear after close()")

            deploy_record = self._active.get(deployment_id)
            if deploy_record is None:
                if deployment_id in self._known_ids:
                    raise ValueError(
                        f"GearTracker.retrieve_gear: deployment "
                        f"{deployment_id!r} already retrieved"
                    )
                raise ValueError(
                    f"GearTracker.retrieve_gear: unknown deployment "
                    f"{deployment_id!r}"
                )

            end_time = _coerce_ts(ts)
            start_time = deploy_record.get("start_time")
            if isinstance(start_time, str) and _parse_iso(end_time) < _parse_iso(
                start_time
            ):
                raise ValueError(
                    f"GearTracker.retrieve_gear: end_time {end_time!r} precedes "
                    f"start_time {start_time!r}"
                )

            record = {
                "kind": KIND_GEAR,
                "event": EVENT_RETRIEVE,
                "deployment_id": deployment_id,
                "end_time": end_time,
                "_loggedAt": _utc_now_iso(),
                "_seq": self._seq,
            }
            self._write_line(record)
            self._seq += 1
            del self._active[deployment_id]
            gear_type = deploy_record.get("gear_type", "gear")
            none_active = not self._active

        # Sync mode outside the lock — mode manager has its own.
        if none_active:
            self._sync_mode(
                MODE_FISHING,
                f"All gear retrieved (last: {gear_type}, deployment "
                f"{deployment_id})",
            )

        return record

    def _sync_mode(self, mode: str, reason: str) -> None:
        """Best-effort mode update on the attached mode manager."""
        if self._mode_manager is None:
            return
        try:
            self._mode_manager.set_mode(mode, reason)
        except Exception as exc:  # noqa: BLE001 - mode sync must never break logging
            log.warning("GearTracker: mode sync to %s failed: %s", mode, exc)

    def _write_line(self, record: dict[str, Any]) -> None:
        """Write one record to the log file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, default=str)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def _read_records(self) -> list[dict[str, Any]]:
        """Read all well-formed gear records from the log file."""
        records: list[dict[str, Any]] = []
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        log.warning(
                            "GearTracker: skipping malformed line in %s", self._path
                        )
                        continue
                    if record.get("kind") != KIND_GEAR:
                        continue
                    records.append(record)
        except FileNotFoundError:
            return []
        except OSError as exc:
            log.warning("GearTracker: could not read %s: %s", self._path, exc)
        return records

    def get_active_gear(self) -> list[dict[str, Any]]:
        """Return copies of all currently deployed (not retrieved) gear.

        Each entry carries deployment_id, gear_type, line_length, depth,
        start_time, and end_time (None while active). Ordered by _seq.
        """
        return [dict(record) for record in self._active.values()]

    def get_gear_history(self) -> list[dict[str, Any]]:
        """Return completed deployments (deployed and retrieved).

        Each entry merges the deploy and retrieve records:
        deployment_id, gear_type, line_length, depth, start_time,
        end_time, and duration_s. Ordered by start_time. Active
        deployments are excluded; use :meth:`get_active_gear` for those.
        """
        deploys: dict[str, dict[str, Any]] = {}
        retrieves: dict[str, dict[str, Any]] = {}
        for record in self._read_records():
            deployment_id = record.get("deployment_id")
            if not isinstance(deployment_id, str):
                continue
            if record.get("event") == EVENT_DEPLOY:
                deploys[deployment_id] = record
            elif record.get("event") == EVENT_RETRIEVE:
                retrieves[deployment_id] = record

        history: list[dict[str, Any]] = []
        for deployment_id, deploy in deploys.items():
            retrieve = retrieves.get(deployment_id)
            if retrieve is None:
                continue
            entry = {
                "deployment_id": deployment_id,
                "gear_type": deploy.get("gear_type"),
                "line_length": deploy.get("line_length"),
                "depth": deploy.get("depth"),
                "start_time": deploy.get("start_time"),
                "end_time": retrieve.get("end_time"),
            }
            start = deploy.get("start_time")
            end = retrieve.get("end_time")
            if isinstance(start, str) and isinstance(end, str):
                try:
                    entry["duration_s"] = round(
                        (_parse_iso(end) - _parse_iso(start)).total_seconds(), 3
                    )
                except ValueError:
                    entry["duration_s"] = None
            else:
                entry["duration_s"] = None
            history.append(entry)

        history.sort(key=lambda e: (e.get("start_time") or "", e["deployment_id"]))
        return history

    async def stats(self) -> dict[str, Any]:
        """Lightweight status snapshot."""
        try:
            size_bytes = self._path.stat().st_size
        except OSError:
            size_bytes = 0
        return {
            "path": str(self._path),
            "records": self._seq,
            "active_deployments": len(self._active),
            "closed": self._closed,
            "size_bytes": size_bytes,
            "mode_manager_attached": self._mode_manager is not None,
        }

    async def close(self) -> None:
        """Mark the tracker closed. Later operations raise RuntimeError."""
        async with self._lock:
            self._closed = True

    async def __aenter__(self) -> "GearTracker":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()
