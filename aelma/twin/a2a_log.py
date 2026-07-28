"""A2ALog: append-only JSONL action log for agent-to-agent actions.

Python/asyncio adaptation of the mini-agent ``backend/a2aLog.js`` pattern:
a single-writer, append-only log where every A2A action (watcher-fired,
LLM-issued, or crew-entered) is persisted as one JSON object per line.
The log is the source of truth for "who told the viewer to do what, and
when" — :mod:`twin.a2a_query` is the read side.

Record shape (one JSON object per line)::

    {
      "kind":      "action",              # record kind, reserved for acks
      "action":    "raise_alert",         # action name (non-empty string)
      "payload":   {"kind": "shallow_water", "depth": 1.4},
      "source":    "watcher",             # watcher | llm | crew | system
      "reason":    "depth=1.40m",         # human-readable why (may be "")
      "priority":  0.85,                  # 0.0 .. 1.0
      "ts":        "2026-07-27T15:04:23.181000+00:00",  # action time (ISO)
      "_loggedAt": "2026-07-27T15:04:23.204112+00:00",  # write time (ISO)
      "_seq":      42                     # monotonic per log file
    }

Contracts (carried over from the mini-agent review):

* Append-only. Records are never mutated or deleted through this class;
  corrections are new records.
* ``append`` validates its arguments and raises ``ValueError`` /
  ``TypeError`` on bad input — a malformed action must never reach disk,
  because downstream consumers (viewer, query layer) trust the file.
* ``append`` after :meth:`close` raises ``RuntimeError`` (the JS version
  threw on append-after-destroy; same idea).
* Writes are serialized behind an :class:`asyncio.Lock`, so concurrent
  tasks get unique, ordered ``_seq`` values. File I/O itself is
  synchronous — records are one line each, so the blocking window is
  negligible and the stdlib-only constraint rules out aiofiles.
* The file is flushed after every record. A2A actions are low-frequency
  (alerts, mode morphs, announcements), so durability beats throughput.

Stdlib only.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

log = logging.getLogger("aelma.twin.a2a_log")

#: Priority used when the caller does not declare one. Matches
#: ``twin.watchers.DEFAULT_PRIORITY`` — deliberately duplicated so the log
#: layer does not depend on the watcher layer.
DEFAULT_PRIORITY = 0.5

#: Recognized action origins. ``watcher``/``llm``/``crew`` are the three
#: A2A producers in AELMA; ``system`` is the fallback for internally
#: generated records (mirrors the mini-agent narrator default).
VALID_SOURCES = frozenset({"watcher", "llm", "crew", "system"})

#: Record kind for normal actions. Reserved so future record kinds
#: (e.g. viewer acknowledgements) can share the file.
KIND_ACTION = "action"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_ts(ts: Any) -> str:
    """Coerce a timestamp argument to an ISO-8601 string.

    Accepts ``None`` (now, UTC), a :class:`~datetime.datetime` (naive is
    assumed UTC), an epoch-seconds number, or an ISO string (validated by
    round-tripping through ``fromisoformat``).
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
            raise ValueError(f"A2ALog.append: unparseable ts string: {ts!r}") from None
        return ts
    raise TypeError(f"A2ALog.append: unsupported ts type {type(ts).__name__}")


class A2ALog:
    """Asyncio-safe append-only JSONL log of A2A actions.

    Parameters
    ----------
    path:
        Destination JSONL file. Parent directories are created on first
        append. An existing file is appended to; ``_seq`` continues from
        the line count of the existing file so sequences stay monotonic
        across restarts.
    max_bytes:
        Rotate log files after they reach this size. Disabled (``None``) by
        default. When enabled, the current file is renamed to ``.1`` and a
        new file is started. Older rotations are numbered ``.2``, ``.3``,
        etc. Only the most recent ``keep`` files are kept.
    keep:
        Number of rotated files to keep when ``max_bytes`` is set. Default 5.
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
            raise ValueError("A2ALog: max_bytes must be positive or None")
        if keep < 1:
            raise ValueError("A2ALog: keep must be at least 1")
        self._path = Path(path)
        self._max_bytes = max_bytes
        self._keep = keep
        self._lock = asyncio.Lock()
        self._closed = False
        self._seq = self._count_existing_lines()
        self._current_size = self._measure_file_size()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def seq(self) -> int:
        """The ``_seq`` value the next appended record will receive."""
        return self._seq

    @property
    def closed(self) -> bool:
        return self._closed

    def _count_existing_lines(self) -> int:
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                return sum(1 for line in fh if line.strip())
        except FileNotFoundError:
            return 0
        except OSError as exc:  # unreadable file: start fresh, don't crash
            log.warning("A2ALog: could not scan %s for seq resume: %s", self._path, exc)
            return 0

    def _measure_file_size(self) -> int:
        """Return current file size in bytes, or 0 if missing."""
        try:
            return self._path.stat().st_size
        except FileNotFoundError:
            return 0
        except OSError as exc:
            log.warning("A2ALog: could not stat %s: %s", self._path, exc)
            return 0

    def _maybe_rotate(self, next_line_bytes: int = 0) -> None:
        """Rotate the log file if it has exceeded (or will exceed) max_bytes.

        Parameters
        ----------
        next_line_bytes:
            Size of the line about to be written. Used to check if the line
            itself will cause the file to exceed max_bytes.
        """
        if self._max_bytes is None:
            return
        # Rotate if we're already at/over the limit, or if adding the next line will exceed it
        if self._current_size >= self._max_bytes or (next_line_bytes > 0 and self._current_size + next_line_bytes > self._max_bytes):
            pass  # Proceed with rotation
        else:
            return

        log.debug("A2ALog: rotation triggered: size=%d, next=%d, max=%d",
                 self._current_size, next_line_bytes, self._max_bytes)

        # Perform rotation: .N files shift up, oldest is deleted
        # Existing: current.jsonl -> current.jsonl.1
        #           current.jsonl.1 -> current.jsonl.2
        #           ...
        #           current.jsonl.(keep-1) -> current.jsonl.keep
        #           current.jsonl.keep -> deleted
        try:
            # Delete the oldest file if it exists
            oldest = self._path.parent / f"{self._path.name}.{self._keep}"
            oldest.unlink(missing_ok=True)

            # Shift existing rotated files (only if they exist)
            for i in range(self._keep - 1, 0, -1):
                old_rotated = self._path.parent / f"{self._path.name}.{i}"
                if old_rotated.exists():
                    new_rotated = self._path.parent / f"{self._path.name}.{i + 1}"
                    old_rotated.rename(new_rotated)

            # Rotate current file to .1 (only if it exists)
            if self._path.exists():
                rotated = self._path.parent / f"{self._path.name}.1"
                self._path.rename(rotated)
                self._current_size = 0
                log.info("A2ALog: rotated %s to %s", self._path, rotated)
            else:
                log.warning("A2ALog: rotation requested but current file doesn't exist")
        except OSError as exc:
            log.error("A2ALog: rotation failed: %s", exc)
            # Continue with current file on rotation failure

    async def append(
        self,
        action: str,
        payload: Mapping[str, Any] | None = None,
        *,
        source: str = "system",
        reason: str = "",
        priority: float = DEFAULT_PRIORITY,
        ts: Any = None,
    ) -> dict[str, Any]:
        """Validate and persist one action record; return it as written.

        The returned dict is the exact object serialized to disk, including
        the augmented ``_loggedAt`` / ``_seq`` fields.
        """
        if self._closed:
            raise RuntimeError("A2ALog: append after close()")
        if not isinstance(action, str) or not action:
            raise ValueError("A2ALog.append: action must be a non-empty string")
        if payload is None:
            payload = {}
        if not isinstance(payload, Mapping):
            raise TypeError("A2ALog.append: payload must be a mapping or None")
        if source not in VALID_SOURCES:
            raise ValueError(
                f"A2ALog.append: source must be one of {sorted(VALID_SOURCES)}, "
                f"got {source!r}"
            )
        if not isinstance(reason, str):
            raise TypeError("A2ALog.append: reason must be a string")
        try:
            priority = float(priority)
        except (TypeError, ValueError):
            raise ValueError(
                f"A2ALog.append: priority must be a number, got {priority!r}"
            ) from None
        if not 0.0 <= priority <= 1.0:
            raise ValueError(
                f"A2ALog.append: priority {priority} out of range [0.0, 1.0]"
            )

        async with self._lock:
            if self._closed:
                raise RuntimeError("A2ALog: append after close()")
            record = {
                "kind": KIND_ACTION,
                "action": action,
                "payload": dict(payload),
                "source": source,
                "reason": reason,
                "priority": priority,
                "ts": _coerce_ts(ts),
                "_loggedAt": _utc_now_iso(),
                "_seq": self._seq,
            }
            self._write_line(record)
            self._seq += 1
            return record

    def _write_line(self, record: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, default=str)
        line_bytes = (len(line) + 1)  # +1 for newline

        # Check if we need to rotate before writing
        rotated = False
        if self._max_bytes is not None:
            should_rotate = self._current_size >= self._max_bytes or self._current_size + line_bytes > self._max_bytes
            if should_rotate:
                self._maybe_rotate(line_bytes)
                rotated = True

        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

        # Only add to size if we didn't just rotate (rotation resets to 0)
        if not rotated:
            self._current_size += line_bytes
        else:
            # After rotation, track the size of the new line
            self._current_size = line_bytes

    async def close(self) -> None:
        """Mark the log closed. Later appends raise ``RuntimeError``."""
        async with self._lock:
            self._closed = True

    async def stats(self) -> dict[str, Any]:
        """Lightweight status snapshot (mirrors the JS ``/status`` field)."""
        return {
            "path": str(self._path),
            "records": self._seq,
            "closed": self._closed,
            "size_bytes": self._current_size,
            "max_bytes": self._max_bytes,
            "keep": self._keep,
        }

    async def __aenter__(self) -> "A2ALog":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()
