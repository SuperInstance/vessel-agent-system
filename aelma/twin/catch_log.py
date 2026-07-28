"""CatchLog: fishing catch tracking for AELMA.

Records individual catch events (species, weight, count, location, depth,
method, quality) to an append-only JSONL file, and optionally mirrors each
event into the crew operations log (:mod:`twin.oplog`) as a
``catch_logged`` entry so trip summaries see them.

Record shape (one JSON object per line)::

    {
      "kind":      "catch_log_entry",
      "species":   "salmon",
      "weight_lb": 12.5,
      "count":     2,
      "location":  {"lat": 59.5, "lon": -152.3},
      "depth":     40.0,
      "method":    "troll",
      "quality":   "premium",
      "ts":        "2026-07-28T10:30:00.000000+00:00",
      "_loggedAt": "2026-07-28T10:30:00.123456+00:00",
      "_seq":      0
    }

Contracts:
- Append-only. Records are never mutated or deleted through this class;
  corrections are new records.
- log_catch validates arguments and raises ValueError/TypeError on bad input.
- Writes are serialized behind an asyncio.Lock for unique, ordered _seq values.
- File is flushed after every record. Catch entries are low-frequency.
- JSONL storage with timestamps.
- When an OpLog is attached, each catch also produces a ``catch_logged``
  OpLog entry carrying the same fields in its metadata.

Supported species: salmon, halibut, cod, crab, shrimp.

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

from .oplog import OpLog, _coerce_ts

log = logging.getLogger("aelma.twin.catch_log")

#: Species this system knows how to track.
VALID_SPECIES = frozenset({"salmon", "halibut", "cod", "crab", "shrimp"})

#: Record kind identifier.
KIND_CATCH = "catch_log_entry"

#: Field order used by export_to_csv.
CSV_FIELDS = (
    "ts",
    "species",
    "weight_lb",
    "count",
    "location",
    "depth",
    "method",
    "quality",
    "_seq",
)


def _utc_now_iso() -> str:
    """Get current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_location(location: Any) -> Any:
    """Validate a location argument: None, a place string, or lat/lon mapping."""
    if location is None:
        return None
    if isinstance(location, str):
        if not location.strip():
            raise ValueError("CatchLog.log_catch: location string must be non-empty")
        return location.strip()
    if isinstance(location, Mapping):
        lat = location.get("lat")
        lon = location.get("lon")
        if not _is_number(lat) or not _is_number(lon):
            raise ValueError(
                "CatchLog.log_catch: location mapping must carry numeric "
                "'lat' and 'lon' keys"
            )
        if not -90.0 <= lat <= 90.0:
            raise ValueError(f"CatchLog.log_catch: lat out of range: {lat!r}")
        if not -180.0 <= lon <= 180.0:
            raise ValueError(f"CatchLog.log_catch: lon out of range: {lon!r}")
        return {"lat": float(lat), "lon": float(lon)}
    raise TypeError(
        "CatchLog.log_catch: location must be None, a string, or a "
        "{'lat', 'lon'} mapping"
    )


class CatchLog:
    """Asyncio-safe append-only JSONL log of fishing catch events.

    Parameters
    ----------
    path:
        Destination JSONL file. Parent directories created on first append.
        Existing file is appended to; _seq continues from line count.
    oplog:
        Optional :class:`~twin.oplog.OpLog` to mirror each catch into as a
        ``catch_logged`` entry.
    crew:
        Crew identifier stamped on mirrored OpLog entries. Default
        ``"system"``; may be overridden per call.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        oplog: OpLog | None = None,
        crew: str = "system",
    ) -> None:
        self._path = Path(path)
        self._oplog = oplog
        self._crew = crew
        self._lock = asyncio.Lock()
        self._closed = False
        self._seq = self._count_existing_lines()

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
            log.warning("CatchLog: could not scan %s for seq resume: %s", self._path, exc)
            return 0

    async def log_catch(
        self,
        species: str,
        weight_lb: float,
        count: int = 1,
        location: Any = None,
        depth: float | None = None,
        method: str | None = None,
        quality: str | None = None,
        *,
        crew: str | None = None,
        ts: Any = None,
    ) -> dict[str, Any]:
        """Validate and persist one catch record; return it as written.

        Parameters
        ----------
        species:
            One of :data:`VALID_SPECIES` (case-insensitive).
        weight_lb:
            Total landed weight in pounds. Must be a non-negative number.
        count:
            Number of individual animals. Must be a positive integer.
        location:
            Where the catch was made: a place string or
            ``{"lat": ..., "lon": ...}`` mapping. Optional.
        depth:
            Fishing depth in meters. Optional, non-negative when given.
        method:
            Fishing method (troll, pot, longline, trawl, ...). Optional.
        quality:
            Quality grade (premium, standard, damaged, ...). Optional.
        crew:
            Crew identifier for the mirrored OpLog entry; falls back to the
            constructor default.
        ts:
            Timestamp (None for now, datetime, epoch seconds, or ISO string).

        Returns
        -------
        dict
            The exact object serialized to disk, including augmented fields.
        """
        if self._closed:
            raise RuntimeError("CatchLog: log_catch after close()")

        # Validate species
        if not isinstance(species, str) or not species.strip():
            raise ValueError("CatchLog.log_catch: species must be a non-empty string")
        species = species.strip().lower()
        if species not in VALID_SPECIES:
            raise ValueError(
                f"CatchLog.log_catch: species must be one of "
                f"{sorted(VALID_SPECIES)}, got {species!r}"
            )

        # Validate weight
        if not _is_number(weight_lb):
            raise TypeError(
                f"CatchLog.log_catch: weight_lb must be a number, got "
                f"{type(weight_lb).__name__}"
            )
        if weight_lb < 0:
            raise ValueError(f"CatchLog.log_catch: weight_lb must be >= 0, got {weight_lb!r}")

        # Validate count
        if not isinstance(count, int) or isinstance(count, bool):
            raise TypeError(
                f"CatchLog.log_catch: count must be an int, got {type(count).__name__}"
            )
        if count < 1:
            raise ValueError(f"CatchLog.log_catch: count must be >= 1, got {count!r}")

        # Validate optional fields
        location = _validate_location(location)
        if depth is not None:
            if not _is_number(depth):
                raise TypeError(
                    f"CatchLog.log_catch: depth must be a number or None, got "
                    f"{type(depth).__name__}"
                )
            if depth < 0:
                raise ValueError(f"CatchLog.log_catch: depth must be >= 0, got {depth!r}")
            depth = float(depth)
        for name, value in (("method", method), ("quality", quality)):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(
                    f"CatchLog.log_catch: {name} must be a non-empty string or None"
                )
        method = method.strip() if method is not None else None
        quality = quality.strip() if quality is not None else None

        crew = self._crew if crew is None else crew
        if not isinstance(crew, str) or not crew.strip():
            raise ValueError("CatchLog.log_catch: crew must be a non-empty string")

        async with self._lock:
            if self._closed:
                raise RuntimeError("CatchLog: log_catch after close()")

            record = {
                "kind": KIND_CATCH,
                "species": species,
                "weight_lb": float(weight_lb),
                "count": count,
                "location": location,
                "depth": depth,
                "method": method,
                "quality": quality,
                "ts": _coerce_ts(ts),
                "_loggedAt": _utc_now_iso(),
                "_seq": self._seq,
            }
            self._write_line(record)
            self._seq += 1

        # Mirror into OpLog outside the lock — OpLog has its own.
        if self._oplog is not None:
            message = f"Catch: {count}x {species}, {weight_lb:g} lb"
            if method:
                message += f" ({method})"
            await self._oplog.log_entry(
                "catch_logged",
                crew.strip(),
                message,
                {
                    "species": species,
                    "weight_lb": float(weight_lb),
                    "count": count,
                    "location": location,
                    "depth": depth,
                    "method": method,
                    "quality": quality,
                },
                ts=record["ts"],
            )

        return record

    def _write_line(self, record: dict[str, Any]) -> None:
        """Write one record to the log file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, default=str)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def _read_records(self) -> list[dict[str, Any]]:
        """Read all well-formed catch records from the log file."""
        records: list[dict[str, Any]] = []
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        log.warning("CatchLog: skipping malformed line in %s", self._path)
                        continue
                    if record.get("kind") != KIND_CATCH:
                        continue
                    records.append(record)
        except FileNotFoundError:
            return []
        except OSError as exc:
            log.warning("CatchLog: could not read %s: %s", self._path, exc)
        return records

    def get_catch_summary(self) -> dict[str, Any]:
        """Aggregate all catch records into a summary dict.

        Returns
        -------
        dict
            ``entries``, ``total_count``, ``total_weight_lb``, and
            ``by_species`` (per-species entries/count/weight, sorted by name).
        """
        by_species: dict[str, dict[str, float]] = {}
        total_count = 0
        total_weight = 0.0
        entries = 0
        for record in self._read_records():
            entries += 1
            species = str(record.get("species") or "unknown")
            bucket = by_species.setdefault(
                species, {"entries": 0, "count": 0, "weight_lb": 0.0}
            )
            bucket["entries"] += 1
            count = record.get("count")
            weight = record.get("weight_lb")
            if _is_number(count):
                bucket["count"] += count
                total_count += int(count)
            if _is_number(weight):
                bucket["weight_lb"] += weight
                total_weight += weight
        return {
            "entries": entries,
            "total_count": total_count,
            "total_weight_lb": round(total_weight, 3),
            "by_species": {
                name: {
                    "entries": b["entries"],
                    "count": b["count"],
                    "weight_lb": round(b["weight_lb"], 3),
                }
                for name, b in sorted(by_species.items())
            },
        }

    def export_to_csv(self, path: str | Path | None = None) -> str:
        """Export all catch records to CSV.

        Parameters
        ----------
        path:
            Optional destination file. When given, the CSV is written there
            (parent directories created) in addition to being returned.

        Returns
        -------
        str
            The CSV content (header plus one row per record). Location
            mappings are rendered as ``lat,lon``; empty when no records.
        """
        records = self._read_records()
        if not records:
            return ""
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=list(CSV_FIELDS))
        writer.writeheader()
        for record in records:
            row = {field: record.get(field) for field in CSV_FIELDS}
            location = record.get("location")
            if isinstance(location, Mapping):
                row["location"] = f"{location.get('lat')},{location.get('lon')}"
            writer.writerow(row)
        content = output.getvalue()
        if path is not None:
            target = Path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            # newline="" so the csv module's \r\n terminators are preserved.
            with target.open("w", encoding="utf-8", newline="") as fh:
                fh.write(content)
        return content

    async def stats(self) -> dict[str, Any]:
        """Lightweight status snapshot."""
        try:
            size_bytes = self._path.stat().st_size
        except OSError:
            size_bytes = 0
        return {
            "path": str(self._path),
            "records": self._seq,
            "closed": self._closed,
            "size_bytes": size_bytes,
            "oplog_attached": self._oplog is not None,
        }

    async def close(self) -> None:
        """Mark the log closed. Later operations raise RuntimeError."""
        async with self._lock:
            self._closed = True

    async def __aenter__(self) -> "CatchLog":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()
