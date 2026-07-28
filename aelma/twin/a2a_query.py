"""A2AQuery: read-side query layer over A2ALog JSONL files.

Python/asyncio adaptation of the mini-agent ``backend/a2aQuery.js``
pattern: a streaming, pure-stdlib reader that filters, counts, and
summarizes the A2A action history written by :class:`twin.a2a_log.A2ALog`.
The query layer never writes — it can point at a live log file safely
(records are whole lines, so a partially-written tail line is simply
skipped as malformed).

Filter shape (all optional, AND-ed together)::

    {
      "kind":            "action",          # exact match on rec["kind"]
      "action":          "raise_alert",     # exact match on rec["action"]
      "source":          "watcher",         # exact match on rec["source"]
      "since":           ISO timestamp,     # rec["ts"] >= since
      "until":           ISO timestamp,     # rec["ts"] <= until
      "min_priority":    0.7,               # rec["priority"] >= min
      "max_priority":    0.9,               # rec["priority"] <= max
      "reason_contains": "depth",           # substring of rec["reason"]
    }

A record that is *missing* the field a filter inspects fails that filter
(the JS contract: "missing fields on a record cause that record to fail
the corresponding filter"). Malformed lines are skipped and counted in
:attr:`A2AQuery.last_bad_lines`.

Timestamps compare as parsed datetimes; ``since``/``until`` accept ISO
strings, :class:`~datetime.datetime`, or epoch seconds. Naive datetimes
and timestamps without offset are treated as UTC.

Stdlib only.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Iterable, Mapping

log = logging.getLogger("aelma.twin.a2a_query")

#: Filters recognized by :func:`record_matches`. Anything else in the
#: filter dict is ignored, so callers can pass richer dicts safely.
KNOWN_FILTERS = frozenset(
    {
        "kind",
        "action",
        "source",
        "since",
        "until",
        "min_priority",
        "max_priority",
        "reason_contains",
    }
)


def _parse_ts(value: Any) -> datetime | None:
    """Parse a timestamp into an aware datetime (UTC assumed when naive).

    Returns ``None`` for unparseable or missing values — callers treat
    that as "filter cannot match", never as an exception.
    """
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        dt = datetime.fromtimestamp(value, tz=timezone.utc)
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def record_matches(rec: Mapping[str, Any], filters: Mapping[str, Any]) -> bool:
    """Pure predicate: does one parsed record satisfy all filters?

    Every present filter must pass (logical AND). A record missing the
    field a filter inspects fails that filter. Unparseable ``since`` /
    ``until`` filter values match nothing (fail-closed).
    """
    if not filters:
        return True

    if "kind" in filters and rec.get("kind") != filters["kind"]:
        return False
    if "action" in filters and rec.get("action") != filters["action"]:
        return False
    if "source" in filters and rec.get("source") != filters["source"]:
        return False

    if "since" in filters or "until" in filters:
        rec_ts = _parse_ts(rec.get("ts"))
        if rec_ts is None:
            return False
        if "since" in filters:
            since = _parse_ts(filters["since"])
            if since is None or rec_ts < since:
                return False
        if "until" in filters:
            until = _parse_ts(filters["until"])
            if until is None or rec_ts > until:
                return False

    if "min_priority" in filters:
        pri = rec.get("priority")
        if not isinstance(pri, (int, float)) or pri < filters["min_priority"]:
            return False
    if "max_priority" in filters:
        pri = rec.get("priority")
        if not isinstance(pri, (int, float)) or pri > filters["max_priority"]:
            return False

    if "reason_contains" in filters:
        reason = rec.get("reason")
        if not isinstance(reason, str) or filters["reason_contains"] not in reason:
            return False

    return True


class A2AQuery:
    """Streaming read-only query layer over one A2A JSONL log file."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        #: Lines skipped as malformed during the most recent scan.
        self.last_bad_lines = 0

    @property
    def path(self) -> Path:
        return self._path

    # ------------------------------------------------------------------
    # Streaming core
    # ------------------------------------------------------------------

    def _iter_lines(self) -> Iterable[str]:
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                yield from fh
        except FileNotFoundError:
            return

    async def iter_records(
        self, filters: Mapping[str, Any] | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield matching records in file order, one line at a time.

        Malformed JSON lines and non-object lines are skipped (and counted
        in :attr:`last_bad_lines`). The scan itself is synchronous file
        I/O; control is yielded to the event loop between records so a
        large history cannot starve other tasks.
        """
        self.last_bad_lines = 0
        filters = filters or {}
        for line in self._iter_lines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                self.last_bad_lines += 1
                continue
            if not isinstance(rec, dict):
                self.last_bad_lines += 1
                continue
            if record_matches(rec, filters):
                yield rec
                await asyncio.sleep(0)

    async def query(
        self,
        filters: Mapping[str, Any] | None = None,
        *,
        limit: int = 0,
    ) -> list[dict[str, Any]]:
        """Collect matching records. ``limit <= 0`` means no limit."""
        out: list[dict[str, Any]] = []
        async for rec in self.iter_records(filters):
            out.append(rec)
            if limit > 0 and len(out) >= limit:
                break
        return out

    # ------------------------------------------------------------------
    # Aggregations
    # ------------------------------------------------------------------

    async def count_by(
        self, field: str, filters: Mapping[str, Any] | None = None
    ) -> dict[str, int]:
        """Group matching records by ``field`` and count each value.

        Records missing the field are skipped (not bucketed as "unknown"),
        matching the mini-agent behavior.
        """
        if not isinstance(field, str) or not field:
            raise ValueError("A2AQuery.count_by: field must be a non-empty string")
        counts: Counter[str] = Counter()
        async for rec in self.iter_records(filters):
            value = rec.get(field)
            if value is None:
                continue
            counts[str(value)] += 1
        return dict(counts)

    async def top_by(
        self,
        field: str,
        n: int = 5,
        filters: Mapping[str, Any] | None = None,
    ) -> list[tuple[str, int]]:
        """Top-N most frequent values of ``field`` — wrapper over count_by."""
        counts = await self.count_by(field, filters)
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]

    async def by_source(
        self,
        source: str,
        filters: Mapping[str, Any] | None = None,
        *,
        limit: int = 0,
    ) -> list[dict[str, Any]]:
        """Convenience: query with an additional exact ``source`` filter."""
        if not isinstance(source, str) or not source:
            raise ValueError("A2AQuery.by_source: source must be a non-empty string")
        merged = dict(filters or {})
        merged["source"] = source
        return await self.query(merged, limit=limit)

    async def summary(
        self, filters: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        """One-pass aggregate over matching records.

        Returns totals, per-action and per-source breakdowns, the time
        span covered, and mean priority (``None`` when no record carries
        a numeric priority).
        """
        total = 0
        by_action: Counter[str] = Counter()
        by_source: Counter[str] = Counter()
        first_ts: datetime | None = None
        last_ts: datetime | None = None
        pri_sum = 0.0
        pri_n = 0

        async for rec in self.iter_records(filters):
            total += 1
            if rec.get("action") is not None:
                by_action[str(rec["action"])] += 1
            if rec.get("source") is not None:
                by_source[str(rec["source"])] += 1
            ts = _parse_ts(rec.get("ts"))
            if ts is not None:
                if first_ts is None or ts < first_ts:
                    first_ts = ts
                if last_ts is None or ts > last_ts:
                    last_ts = ts
            pri = rec.get("priority")
            if isinstance(pri, (int, float)) and not isinstance(pri, bool):
                pri_sum += pri
                pri_n += 1

        return {
            "total": total,
            "by_action": dict(by_action),
            "by_source": dict(by_source),
            "first_ts": first_ts.isoformat() if first_ts else None,
            "last_ts": last_ts.isoformat() if last_ts else None,
            "avg_priority": (pri_sum / pri_n) if pri_n else None,
            "bad_lines": self.last_bad_lines,
        }

    async def bucket_by_time(
        self,
        bucket_s: float,
        filters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Group matching records into fixed-width time buckets.

        Buckets are aligned to the epoch (a bucket starts at a multiple of
        ``bucket_s``), so results are stable across calls. Records without
        a parseable ``ts`` are skipped. Returns a list of
        ``{"start": ISO, "count": int}`` sorted by start time; empty
        buckets between the first and last record are omitted.
        """
        if bucket_s <= 0:
            raise ValueError("A2AQuery.bucket_by_time: bucket_s must be > 0")
        buckets: dict[int, int] = {}
        async for rec in self.iter_records(filters):
            ts = _parse_ts(rec.get("ts"))
            if ts is None:
                continue
            bucket_start = (ts.timestamp() // bucket_s) * bucket_s
            buckets[bucket_start] = buckets.get(bucket_start, 0) + 1
        return [
            {
                "start": datetime.fromtimestamp(start, tz=timezone.utc).isoformat(),
                "count": buckets[start],
            }
            for start in sorted(buckets)
        ]

    async def recent(
        self,
        limit: int = 10,
        filters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return the most recent matching records in reverse chronological order.

        This is a convenience method that queries all matching records and
        returns the last N, sorted by ``ts`` descending. For large logs,
        consider using time-bounded filters instead.
        """
        if limit <= 0:
            return []
        all_records = await self.query(filters)
        # Sort by timestamp descending (most recent first)
        sorted_records = sorted(
            all_records,
            key=lambda r: r.get("ts", ""),
            reverse=True,
        )
        return sorted_records[:limit]
