"""OpLog: vessel operations log for crew activity tracking.

Complements the automated A2A log with manual crew operations tracking.
Records fishing gear deployment, retrieval, haul operations, anchor handling,
catch logging, manual alerts, and crew notes.

Record shape (one JSON object per line)::

    {
      "kind":              "oplog_entry",
      "entry_type":        "gear_deployed",
      "crew":              "captain",
      "message":           "Deployed cod pot gear at 59.5N, -152.3W",
      "metadata":         {"lat": 59.5, "lon": -152.3, "gear_type": "cod_pot"},
      "ts":                "2026-07-28T10:30:00.000000+00:00",
      "_loggedAt":        "2026-07-28T10:30:00.123456+00:00",
      "_seq":             42
    }

Entry types:
- gear_deployed: Fishing gear deployed (trawl, pot, longline, etc.)
- gear_retrieved: Fishing gear retrieved from water
- haul_started: Fishing haul/commencement of gear retrieval
- haul_complete: Fishing haul completed/gear fully retrieved
- anchor_drop: Vessel anchor deployed
- anchor_raise: Vessel anchor retrieved
- manual_alert: Crew-initiated alert/observation
- crew_note: General crew observation/note
- catch_logged: Species/catch data recorded

Contracts:
- Append-only. Records are never mutated or deleted through this class;
  corrections are new records.
- log_entry validates arguments and raises ValueError/TypeError on bad input.
- Writes are serialized behind an asyncio.Lock for unique, ordered _seq values.
- File is flushed after every record. OpLog entries are low-frequency.
- JSONL storage with timestamps.

Stdlib only.
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Mapping

log = logging.getLogger("aelma.twin.oplog")

#: Recognized entry types for vessel operations
VALID_ENTRY_TYPES = frozenset({
    "gear_deployed",
    "gear_retrieved",
    "haul_started",
    "haul_complete",
    "anchor_drop",
    "anchor_raise",
    "manual_alert",
    "crew_note",
    "catch_logged",
})

#: Record kind identifier
KIND_OPLOG = "oplog_entry"


def _utc_now_iso() -> str:
    """Get current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _coerce_ts(ts: Any) -> str:
    """Coerce timestamp argument to ISO-8601 string.

    Accepts None (now, UTC), datetime (naive assumed UTC),
    epoch-seconds number, or ISO string (validated by round-trip).
    """
    if ts is None:
        return _utc_now_iso()
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.isoformat()
    if isinstance(ts, (int, float)) and not isinstance(ts, bool):
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    if isinstance(ts, str):
        try:
            datetime.fromisoformat(ts)
        except ValueError:
            raise ValueError(f"OpLog: unparseable ts string: {ts!r}") from None
        return ts
    raise TypeError(f"OpLog: unsupported ts type {type(ts).__name__}")


class OpLog:
    """Asyncio-safe append-only JSONL log of vessel crew operations.

    Parameters
    ----------
    path:
        Destination JSONL file. Parent directories created on first append.
        Existing file is appended to; _seq continues from line count.
    max_bytes:
        Rotate log files after this size. Disabled (None) by default.
        When enabled, current file renamed to .1, older rotations .2, .3, etc.
    keep:
        Number of rotated files to keep when max_bytes set. Default 5.
        Must be at least 1.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        max_bytes: int | None = None,
        keep: int = 5,
    ) -> None:
        if max_bytes is not None and max_bytes <= 0:
            raise ValueError("OpLog: max_bytes must be positive or None")
        if keep < 1:
            raise ValueError("OpLog: keep must be at least 1")
        self._path = Path(path)
        self._max_bytes = max_bytes
        self._keep = keep
        self._lock = asyncio.Lock()
        self._closed = False
        self._seq = self._count_existing_lines()
        self._current_size = self._measure_file_size()

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
        """Whether the log is closed."""
        return self._closed

    def _count_existing_lines(self) -> int:
        """Count existing lines in the log file to resume sequence."""
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                return sum(1 for line in fh if line.strip())
        except FileNotFoundError:
            return 0
        except OSError as exc:
            log.warning("OpLog: could not scan %s for seq resume: %s", self._path, exc)
            return 0

    def _measure_file_size(self) -> int:
        """Return current file size in bytes, or 0 if missing."""
        try:
            return self._path.stat().st_size
        except FileNotFoundError:
            return 0
        except OSError as exc:
            log.warning("OpLog: could not stat %s: %s", self._path, exc)
            return 0

    def _maybe_rotate(self, next_line_bytes: int = 0) -> None:
        """Rotate log file if it has exceeded (or will exceed) max_bytes.

        Parameters
        ----------
        next_line_bytes:
            Size of line about to be written. Used to check if the line
            itself will cause file to exceed max_bytes.
        """
        if self._max_bytes is None:
            return

        # Rotate if we're already at/over limit, or if next line will exceed it
        if self._current_size >= self._max_bytes or (
            next_line_bytes > 0 and self._current_size + next_line_bytes > self._max_bytes
        ):
            pass  # Proceed with rotation
        else:
            return

        log.debug(
            "OpLog: rotation triggered: size=%d, next=%d, max=%d",
            self._current_size,
            next_line_bytes,
            self._max_bytes,
        )

        try:
            # Delete oldest file if exists
            oldest = self._path.parent / f"{self._path.name}.{self._keep}"
            oldest.unlink(missing_ok=True)

            # Shift existing rotated files
            for i in range(self._keep - 1, 0, -1):
                old_rotated = self._path.parent / f"{self._path.name}.{i}"
                if old_rotated.exists():
                    new_rotated = self._path.parent / f"{self._path.name}.{i + 1}"
                    old_rotated.rename(new_rotated)

            # Rotate current file to .1
            if self._path.exists():
                rotated = self._path.parent / f"{self._path.name}.1"
                self._path.rename(rotated)
                self._current_size = 0
                log.info("OpLog: rotated %s to %s", self._path, rotated)
        except OSError as exc:
            log.error("OpLog: rotation failed: %s", exc)

    async def log_entry(
        self,
        entry_type: str,
        crew: str,
        message: str,
        metadata: Mapping[str, Any] | None = None,
        *,
        ts: Any = None,
    ) -> dict[str, Any]:
        """Validate and persist one operations log entry; return it as written.

        Parameters
        ----------
        entry_type:
            Type of operation (gear_deployed, haul_started, etc.)
        crew:
            Crew member identifier (name, ID, role)
        message:
            Human-readable description of the operation
        metadata:
            Optional structured data (gear type, location, quantities, etc.)
        ts:
            Timestamp (None for now, datetime, epoch seconds, or ISO string)

        Returns
        -------
        dict
            The exact object serialized to disk, including augmented fields.
        """
        if self._closed:
            raise RuntimeError("OpLog: log_entry after close()")

        # Validate entry_type
        if entry_type not in VALID_ENTRY_TYPES:
            raise ValueError(
                f"OpLog.log_entry: entry_type must be one of "
                f"{sorted(VALID_ENTRY_TYPES)}, got {entry_type!r}"
            )

        # Validate crew
        if not isinstance(crew, str) or not crew.strip():
            raise ValueError("OpLog.log_entry: crew must be a non-empty string")

        # Validate message
        if not isinstance(message, str) or not message.strip():
            raise ValueError("OpLog.log_entry: message must be a non-empty string")

        # Validate metadata
        if metadata is None:
            metadata = {}
        elif not isinstance(metadata, Mapping):
            raise TypeError("OpLog.log_entry: metadata must be a mapping or None")

        async with self._lock:
            if self._closed:
                raise RuntimeError("OpLog: log_entry after close()")

            record = {
                "kind": KIND_OPLOG,
                "entry_type": entry_type,
                "crew": crew.strip(),
                "message": message.strip(),
                "metadata": dict(metadata),
                "ts": _coerce_ts(ts),
                "_loggedAt": _utc_now_iso(),
                "_seq": self._seq,
            }
            self._write_line(record)
            self._seq += 1
            return record

    def _write_line(self, record: dict[str, Any]) -> None:
        """Write one record to the log file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, default=str)
        line_bytes = len(line) + 1  # +1 for newline

        # Check rotation before writing
        rotated = False
        if self._max_bytes is not None:
            should_rotate = (
                self._current_size >= self._max_bytes or
                self._current_size + line_bytes > self._max_bytes
            )
            if should_rotate:
                self._maybe_rotate(line_bytes)
                rotated = True

        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

        # Update size tracking
        if not rotated:
            self._current_size += line_bytes
        else:
            self._current_size = line_bytes

    async def query(
        self,
        *,
        entry_type: str | set[str] | None = None,
        crew: str | set[str] | None = None,
        start_time: Any = None,
        end_time: Any = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Query operations log with filters.

        Parameters
        ----------
        entry_type:
            Filter by entry type (string or set of strings). None = all types.
        crew:
            Filter by crew member (string or set of strings). None = all crew.
        start_time:
            Filter entries after this time (None = beginning of log).
            Accepts datetime, epoch seconds, or ISO string.
        end_time:
            Filter entries before this time (None = end of log).
            Accepts datetime, epoch seconds, or ISO string.
        limit:
            Maximum number of entries to return. Default 1000.
        offset:
            Number of entries to skip (for pagination). Default 0.

        Returns
        -------
        list[dict]
            List of matching records, ordered by timestamp (newest first).
        """
        # Normalize filters
        if isinstance(entry_type, str):
            entry_types = {entry_type}
        elif entry_type is None:
            entry_types = None
        else:
            entry_types = set(entry_type)

        if isinstance(crew, str):
            crews = {crew}
        elif crew is None:
            crews = None
        else:
            crews = set(crew)

        # Parse time bounds
        start_ts = None
        if start_time is not None:
            start_ts = _coerce_ts(start_time)

        end_ts = None
        if end_time is not None:
            end_ts = _coerce_ts(end_time)

        # Collect all rotated files
        results = []
        files_to_search = [self._path]

        # Add rotated files in reverse order (oldest first)
        for i in range(self._keep, 0, -1):
            rotated_path = self._path.parent / f"{self._path.name}.{i}"
            if rotated_path.exists():
                files_to_search.append(rotated_path)

        # Read and filter records
        for file_path in files_to_search:
            try:
                with file_path.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        if not line.strip():
                            continue
                        try:
                            record = json.loads(line)

                            # Skip non-oplog records (shouldn't happen, but defensive)
                            if record.get("kind") != KIND_OPLOG:
                                continue

                            # Apply filters
                            if entry_types is not None:
                                if record.get("entry_type") not in entry_types:
                                    continue

                            if crews is not None:
                                if record.get("crew") not in crews:
                                    continue

                            if start_ts is not None:
                                if record.get("ts") < start_ts:
                                    continue

                            if end_ts is not None:
                                if record.get("ts") > end_ts:
                                    continue

                            results.append(record)

                        except (json.JSONDecodeError, KeyError, TypeError):
                            log.warning("OpLog: skipping malformed line in %s", file_path)
                            continue
            except OSError as exc:
                log.warning("OpLog: could not read %s: %s", file_path, exc)
                continue

        # Sort by timestamp (newest first)
        results.sort(key=lambda r: r.get("ts", ""), reverse=True)

        # Apply pagination
        return results[offset:offset + limit]

    async def export(
        self,
        format: str = "json",
        *,
        entry_type: str | set[str] | None = None,
        crew: str | set[str] | None = None,
        start_time: Any = None,
        end_time: Any = None,
        limit: int = 1000,
    ) -> str:
        """Export operations log to specified format.

        Parameters
        ----------
        format:
            Export format: 'json', 'csv', or 'text'. Default 'json'.
        entry_type, crew, start_time, end_time, limit:
            Same filters as query() method.

        Returns
        -------
        str
            Exported data in requested format.
        """
        records = await self.query(
            entry_type=entry_type,
            crew=crew,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

        if format == "json":
            return json.dumps(records, indent=2, ensure_ascii=False, default=str)

        elif format == "csv":
            output = StringIO()
            if not records:
                return ""

            # Get all unique fields across all records
            fieldnames = {"kind", "entry_type", "crew", "message", "ts", "_loggedAt", "_seq"}
            for record in records:
                if "metadata" in record and isinstance(record["metadata"], dict):
                    for key in record["metadata"].keys():
                        fieldnames.add(f"metadata_{key}")

            writer = csv.DictWriter(output, fieldnames=sorted(fieldnames))
            writer.writeheader()

            for record in records:
                flat = {}
                for key, value in record.items():
                    if key == "metadata" and isinstance(value, dict):
                        for mk, mv in value.items():
                            flat[f"metadata_{mk}"] = mv
                    else:
                        flat[key] = value
                writer.writerow(flat)

            return output.getvalue()

        elif format == "text":
            lines = []
            for record in records:
                ts = record.get("ts", "unknown")
                entry = record.get("entry_type", "unknown")
                crew_member = record.get("crew", "unknown")
                msg = record.get("message", "")

                lines.append(f"[{ts}] {entry} - {crew_member}")
                lines.append(f"  {msg}")

                metadata = record.get("metadata", {})
                if metadata:
                    for key, value in metadata.items():
                        lines.append(f"  {key}: {value}")
                lines.append("")  # blank line between entries

            return "\n".join(lines)

        else:
            raise ValueError(f"OpLog.export: unsupported format {format!r}")

    async def close(self) -> None:
        """Mark the log closed. Later operations raise RuntimeError."""
        async with self._lock:
            self._closed = True

    async def stats(self) -> dict[str, Any]:
        """Lightweight status snapshot."""
        return {
            "path": str(self._path),
            "records": self._seq,
            "closed": self._closed,
            "size_bytes": self._current_size,
            "max_bytes": self._max_bytes,
            "keep": self._keep,
        }

    async def __aenter__(self) -> "OpLog":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()
