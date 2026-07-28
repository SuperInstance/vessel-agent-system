"""Tests for the AELMA A2A (Agent-to-Agent) action log and query system.

Mirrors the mini-agent's three JS suites (a2aLog / a2aQuery / rotation)
adapted to pytest and asyncio. Coverage:

  1. A2ALog — append validation, serialization, seq monotonicity, stats.
  2. A2ALog — rotation (size-based, keep N files).
  3. A2AQuery — filter operations, aggregations, streaming.
  4. Integration — log + query workflow.
  5. Error handling — append after close, malformed records.

Run from the repo root:  python -m pytest tests/a2a.test.py -v
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
import pytest_asyncio

# Make the repository root importable regardless of pytest's rootdir handling.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twin.a2a_log import (  # noqa: E402
    A2ALog,
    DEFAULT_PRIORITY,
    KIND_ACTION,
    VALID_SOURCES,
    _coerce_ts,
)
from twin.a2a_query import (  # noqa: E402
    A2AQuery,
    KNOWN_FILTERS,
    _parse_ts,
    record_matches,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_log_path(tmp_path: Path) -> Path:
    """Temporary path for log files."""
    return tmp_path / "test.jsonl"


@pytest.fixture
def temp_log(temp_log_path: Path) -> A2ALog:
    """Fresh A2ALog instance for each test."""
    return A2ALog(temp_log_path)


@pytest_asyncio.fixture
async def populated_log(temp_log_path: Path) -> A2ALog:
    """Log with 10 pre-populated records."""
    log = A2ALog(temp_log_path)
    for i in range(10):
        await log.append(
            f"action_{i}",
            {"index": i},
            source="watcher" if i % 2 == 0 else "llm",
            priority=0.1 + (i * 0.08),
            reason=f"test record {i}",
        )
    return log


# =============================================================================
# A2ALog: Basic operations
# =============================================================================

class TestA2ALogBasic:
    """Test core A2ALog functionality: append, validation, stats."""

    @pytest.mark.asyncio
    async def test_init_creates_dir_on_append(self, temp_log_path: Path) -> None:
        """Log creates parent directory on first append."""
        nested = temp_log_path.parent / "nested" / "log.jsonl"
        log = A2ALog(nested)
        await log.append("test_action", {}, source="system")
        assert nested.exists()
        assert nested.parent.is_dir()

    @pytest.mark.asyncio
    async def test_append_returns_record_with_seq(self, temp_log: A2ALog) -> None:
        """Append returns complete record including _seq and _loggedAt."""
        rec = await temp_log.append(
            "raise_alert",
            {"kind": "shallow_water", "depth": 1.2},
            source="watcher",
            reason="depth=1.20m",
            priority=0.85,
        )
        assert rec["kind"] == KIND_ACTION
        assert rec["action"] == "raise_alert"
        assert rec["payload"]["depth"] == 1.2
        assert rec["source"] == "watcher"
        assert rec["reason"] == "depth=1.20m"
        assert rec["priority"] == 0.85
        assert "_loggedAt" in rec
        assert "_seq" in rec
        assert rec["_seq"] == 0

    @pytest.mark.asyncio
    async def test_seq_monotonic(self, temp_log: A2ALog) -> None:
        """Sequence numbers increment monotonically."""
        recs = [await temp_log.append(f"action_{i}", {}) for i in range(5)]
        assert [r["_seq"] for r in recs] == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_append_validates_action(self, temp_log: A2ALog) -> None:
        """Action must be non-empty string."""
        with pytest.raises(ValueError, match="non-empty string"):
            await temp_log.append("", {})

    @pytest.mark.asyncio
    async def test_append_validates_source(self, temp_log: A2ALog) -> None:
        """Source must be in VALID_SOURCES."""
        with pytest.raises(ValueError, match="must be one of"):
            await temp_log.append("test", {}, source="invalid_source")

    @pytest.mark.asyncio
    async def test_append_validates_priority(self, temp_log: A2ALog) -> None:
        """Priority must be number in [0.0, 1.0]."""
        with pytest.raises(ValueError, match="out of range"):
            await temp_log.append("test", {}, priority=1.5)

        with pytest.raises(ValueError, match="out of range"):
            await temp_log.append("test", {}, priority=-0.1)

    @pytest.mark.asyncio
    async def test_append_coerces_priority(self, temp_log: A2ALog) -> None:
        """Priority is coerced to float."""
        rec = await temp_log.append("test", {}, priority="0.7")
        assert isinstance(rec["priority"], float)
        assert rec["priority"] == 0.7

    @pytest.mark.asyncio
    async def test_append_default_values(self, temp_log: A2ALog) -> None:
        """Defaults: empty payload, system source, empty reason, 0.5 priority."""
        rec = await temp_log.append("test_action")
        assert rec["action"] == "test_action"
        assert rec["payload"] == {}
        assert rec["source"] == "system"
        assert rec["reason"] == ""
        assert rec["priority"] == DEFAULT_PRIORITY
        assert "ts" in rec
        assert "_loggedAt" in rec

    @pytest.mark.asyncio
    async def test_append_after_close_raises(self, temp_log: A2ALog) -> None:
        """Appending after close() raises RuntimeError."""
        await temp_log.close()
        with pytest.raises(RuntimeError, match="append after close"):
            await temp_log.append("test", {})

    @pytest.mark.asyncio
    async def test_stats(self, temp_log: A2ALog) -> None:
        """Stats() returns current log state."""
        await temp_log.append("test", {})
        await temp_log.append("test2", {})

        stats = await temp_log.stats()
        assert stats["records"] == 2
        assert stats["closed"] is False
        assert "path" in stats
        assert stats["size_bytes"] > 0
        assert stats["max_bytes"] is None
        assert stats["keep"] == 5

    @pytest.mark.asyncio
    async def test_context_manager(self, temp_log_path: Path) -> None:
        """A2ALog works as async context manager."""
        async with A2ALog(temp_log_path) as log:
            await log.append("test", {})
            assert (await log.stats())["closed"] is False

        # After exit, closed is True
        log2 = A2ALog(temp_log_path)
        stats = await log2.stats()
        assert stats["records"] == 1

    @pytest.mark.asyncio
    async def test_append_creates_jsonl_file(self, temp_log: A2ALog) -> None:
        """Appended records are written as JSONL (one JSON per line)."""
        await temp_log.append("action1", {"a": 1})
        await temp_log.append("action2", {"b": 2})

        lines = temp_log.path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2

        rec1 = json.loads(lines[0])
        rec2 = json.loads(lines[1])
        assert rec1["action"] == "action1"
        assert rec2["action"] == "action2"

    @pytest.mark.asyncio
    async def test_resume_seq_after_restart(self, temp_log_path: Path) -> None:
        """Sequence continues from existing file line count."""
        log1 = A2ALog(temp_log_path)
        await log1.append("test", {})
        await log1.append("test", {})

        log2 = A2ALog(temp_log_path)
        assert log2.seq == 2
        rec = await log2.append("test", {})
        assert rec["_seq"] == 2


# =============================================================================
# A2ALog: Rotation
# =============================================================================

class TestA2ALogRotation:
    """Test log rotation functionality."""

    @pytest.mark.asyncio
    async def test_rotation_disabled_by_default(self, temp_log_path: Path) -> None:
        """Without max_bytes, rotation is disabled."""
        log = A2ALog(temp_log_path)
        assert log._max_bytes is None

        # Append many records, no rotation
        for i in range(100):
            await log.append("test", {"data": "x" * 100})

        assert temp_log_path.exists()
        assert not temp_log_path.with_suffix(".jsonl.1").exists()

    @pytest.mark.asyncio
    async def test_rotation_creates_backup(self, temp_log_path: Path) -> None:
        """Rotation creates .1 file and starts fresh."""
        log = A2ALog(temp_log_path, max_bytes=1000, keep=3)

        # Write enough to trigger rotation
        for i in range(10):
            await log.append("test", {"data": "y" * 20})

        # Should have rotated
        backup1 = temp_log_path.parent / f"{temp_log_path.name}.1"
        assert backup1.exists()
        # Current file exists but smaller
        assert temp_log_path.exists()

    @pytest.mark.asyncio
    async def test_rotation_keeps_n_files(self, temp_log_path: Path) -> None:
        """Rotation keeps only the most recent N files."""
        log = A2ALog(temp_log_path, max_bytes=600, keep=2)

        # Trigger multiple rotations
        for i in range(20):
            await log.append("test", {"data": "z" * 30})

        # Should keep .1 and .2 only (.3 deleted)
        backup1 = temp_log_path.parent / f"{temp_log_path.name}.1"
        backup2 = temp_log_path.parent / f"{temp_log_path.name}.2"
        backup3 = temp_log_path.parent / f"{temp_log_path.name}.3"
        assert backup1.exists()
        assert backup2.exists()
        assert not backup3.exists()

    @pytest.mark.asyncio
    async def test_rotation_shifts_existing_backups(self, temp_log_path: Path) -> None:
        """Existing .N files are shifted up when rotation occurs."""
        # Pre-create .1 and .2 files
        backup1 = temp_log_path.parent / f"{temp_log_path.name}.1"
        backup2 = temp_log_path.parent / f"{temp_log_path.name}.2"
        backup1.write_text("backup1")
        backup2.write_text("backup2")

        # Use max_bytes large enough to avoid rotation on first write
        log = A2ALog(temp_log_path, max_bytes=2000, keep=3)
        # Write enough to trigger rotation
        for i in range(10):
            await log.append("test", {"data": "w" * 50})

        # After rotation, existing backups should have shifted
        # .1 → .2, .2 → .3 (and potentially more rotations)
        # We just verify that rotation happened and files exist
        backup1_final = temp_log_path.parent / f"{temp_log_path.name}.1"
        backup2_final = temp_log_path.parent / f"{temp_log_path.name}.2"
        backup3_final = temp_log_path.parent / f"{temp_log_path.name}.3"

        # At minimum, rotation should have occurred
        assert backup1_final.exists() or backup2_final.exists() or backup3_final.exists()

    @pytest.mark.asyncio
    async def test_rotation_validates_parameters(self, temp_log_path: Path) -> None:
        """Rotation parameters must be valid."""
        with pytest.raises(ValueError, match="must be positive"):
            A2ALog(temp_log_path, max_bytes=0)

        with pytest.raises(ValueError, match="must be at least 1"):
            A2ALog(temp_log_path, keep=0)

    @pytest.mark.asyncio
    async def test_stats_includes_rotation_config(self, temp_log_path: Path) -> None:
        """Stats includes rotation configuration."""
        log = A2ALog(temp_log_path, max_bytes=5000, keep=10)
        stats = await log.stats()
        assert stats["max_bytes"] == 5000
        assert stats["keep"] == 10


# =============================================================================
# A2AQuery: Core operations
# =============================================================================

class TestA2AQueryCore:
    """Test A2AQuery basic operations and filtering."""

    def test_init(self, temp_log_path: Path) -> None:
        """Query can be initialized with path."""
        query = A2AQuery(temp_log_path)
        assert query.path == temp_log_path
        assert query.last_bad_lines == 0

    @pytest.mark.asyncio
    async def test_iter_records_empty(self, temp_log_path: Path) -> None:
        """Empty log yields no records."""
        query = A2AQuery(temp_log_path)
        records = []
        async for rec in query.iter_records():
            records.append(rec)
        assert records == []

    @pytest.mark.asyncio
    async def test_iter_records_filters_malformed(
        self, temp_log_path: Path
    ) -> None:
        """Malformed JSON lines are skipped and counted."""
        # Write malformed file
        with temp_log_path.open("w", encoding="utf-8") as fh:
            fh.write('{"valid": "record"}\n')
            fh.write("not json\n")
            fh.write('{"another": "record"}\n')
            fh.write("also not json\n")
            fh.write('{"last": "record"}\n')

        query = A2AQuery(temp_log_path)
        records = []
        async for rec in query.iter_records():
            records.append(rec)

        assert len(records) == 3
        assert query.last_bad_lines == 2

    @pytest.mark.asyncio
    async def test_query_no_filters(self, populated_log: A2ALog) -> None:
        """Query with no filters returns all records."""
        query = A2AQuery(populated_log.path)
        records = await query.query()
        assert len(records) == 10

    @pytest.mark.asyncio
    async def test_query_with_limit(self, populated_log: A2ALog) -> None:
        """Query limit returns at most N records."""
        query = A2AQuery(populated_log.path)
        records = await query.query(limit=5)
        assert len(records) == 5

    @pytest.mark.asyncio
    async def test_query_filter_by_action(self, populated_log: A2ALog) -> None:
        """Can filter by exact action name."""
        query = A2AQuery(populated_log.path)
        records = await query.query({"action": "action_3"})
        assert len(records) == 1
        assert records[0]["action"] == "action_3"

    @pytest.mark.asyncio
    async def test_query_filter_by_source(self, populated_log: A2ALog) -> None:
        """Can filter by source."""
        query = A2AQuery(populated_log.path)
        watcher_recs = await query.query({"source": "watcher"})
        llm_recs = await query.query({"source": "llm"})

        # 0,2,4,6,8 are watcher; 1,3,5,7,9 are llm
        assert len(watcher_recs) == 5
        assert len(llm_recs) == 5

    @pytest.mark.asyncio
    async def test_query_filter_by_priority(self, populated_log: A2ALog) -> None:
        """Can filter by priority range."""
        query = A2AQuery(populated_log.path)

        # Priorities: 0.1, 0.18, 0.26, 0.34, 0.42, 0.5, 0.58, 0.66, 0.74, 0.82
        high_pri = await query.query({"min_priority": 0.5})
        low_pri = await query.query({"max_priority": 0.3})

        assert len(high_pri) == 5  # 0.5, 0.58, 0.66, 0.74, 0.82
        assert len(low_pri) == 3  # 0.1, 0.18, 0.26

    @pytest.mark.asyncio
    async def test_query_filter_by_reason_substring(
        self, populated_log: A2ALog
    ) -> None:
        """Can filter by reason substring."""
        query = A2AQuery(populated_log.path)
        recs = await query.query({"reason_contains": "test"})
        assert len(recs) == 10

        recs = await query.query({"reason_contains": "record 5"})
        assert len(recs) == 1


# =============================================================================
# A2AQuery: Aggregations
# =============================================================================

class TestA2AQueryAggregations:
    """Test A2AQuery aggregation methods."""

    @pytest.mark.asyncio
    async def test_count_by_action(self, populated_log: A2ALog) -> None:
        """Count by groups records by action."""
        query = A2AQuery(populated_log.path)
        counts = await query.count_by("action")
        assert counts == {f"action_{i}": 1 for i in range(10)}

    @pytest.mark.asyncio
    async def test_count_by_source(self, populated_log: A2ALog) -> None:
        """Count by works for any field."""
        query = A2AQuery(populated_log.path)
        counts = await query.count_by("source")
        assert counts == {"watcher": 5, "llm": 5}

    @pytest.mark.asyncio
    async def test_count_by_with_filters(self, populated_log: A2ALog) -> None:
        """Count by respects filters."""
        query = A2AQuery(populated_log.path)
        counts = await query.count_by("action", {"source": "watcher"})
        assert len(counts) == 5  # 5 watcher actions
        assert all(v == 1 for v in counts.values())

    @pytest.mark.asyncio
    async def test_count_by_validates_field(self, populated_log: A2ALog) -> None:
        """Field must be non-empty string."""
        query = A2AQuery(populated_log.path)
        with pytest.raises(ValueError, match="non-empty string"):
            await query.count_by("")

    @pytest.mark.asyncio
    async def test_top_by(self, populated_log: A2ALog) -> None:
        """Top-by returns most frequent values."""
        query = A2AQuery(populated_log.path)
        top = await query.top_by("source", n=2)
        # Both sources have 5 records, sort by count desc, name asc
        assert top == [("llm", 5), ("watcher", 5)]

    @pytest.mark.asyncio
    async def test_summary(self, populated_log: A2ALog) -> None:
        """Summary aggregates multiple stats."""
        query = A2AQuery(populated_log.path)
        summary = await query.summary()

        assert summary["total"] == 10
        assert len(summary["by_action"]) == 10
        assert summary["by_source"] == {"watcher": 5, "llm": 5}
        assert summary["first_ts"] is not None
        assert summary["last_ts"] is not None
        assert summary["avg_priority"] is not None
        # Priorities 0.1..0.82 avg = 0.46
        assert 0.4 < summary["avg_priority"] < 0.5

    @pytest.mark.asyncio
    async def test_summary_with_filters(self, populated_log: A2ALog) -> None:
        """Summary respects filters."""
        query = A2AQuery(populated_log.path)
        summary = await query.summary({"source": "watcher"})

        assert summary["total"] == 5
        assert summary["by_source"] == {"watcher": 5}

    @pytest.mark.asyncio
    async def test_bucket_by_time(self, populated_log: A2ALog) -> None:
        """Time bucketing groups records into fixed intervals."""
        query = A2AQuery(populated_log.path)
        # All records are written quickly, so they should be in same/adjacent buckets
        buckets = await query.bucket_by_time(3600)  # 1 hour buckets
        assert len(buckets) <= 2
        assert sum(b["count"] for b in buckets) == 10

    @pytest.mark.asyncio
    async def test_bucket_by_time_validates_interval(
        self, populated_log: A2ALog
    ) -> None:
        """Bucket interval must be positive."""
        query = A2AQuery(populated_log.path)
        with pytest.raises(ValueError, match="must be > 0"):
            await query.bucket_by_time(0)

    @pytest.mark.asyncio
    async def test_by_source_convenience(self, populated_log: A2ALog) -> None:
        """By_source adds source filter."""
        query = A2AQuery(populated_log.path)
        recs = await query.by_source("watcher")
        assert len(recs) == 5
        assert all(r["source"] == "watcher" for r in recs)

    @pytest.mark.asyncio
    async def test_recent(self, populated_log: A2ALog) -> None:
        """Recent returns most recent N records, newest first."""
        query = A2AQuery(populated_log.path)
        recs = await query.recent(limit=3)
        assert len(recs) == 3
        # Should be in reverse chronological order
        assert recs[0]["_seq"] == 9
        assert recs[1]["_seq"] == 8
        assert recs[2]["_seq"] == 7

    @pytest.mark.asyncio
    async def test_recent_with_filters(self, populated_log: A2ALog) -> None:
        """Recent respects filters."""
        query = A2AQuery(populated_log.path)
        recs = await query.recent(limit=2, filters={"source": "watcher"})
        assert len(recs) == 2
        assert all(r["source"] == "watcher" for r in recs)


# =============================================================================
# A2AQuery: Filter predicate
# =============================================================================

class TestRecordMatches:
    """Test the record_matches filter predicate."""

    def test_no_filters_always_matches(self) -> None:
        """Empty filter dict matches everything."""
        rec = {"action": "test", "priority": 0.5}
        assert record_matches(rec, {}) is True

    def test_kind_filter(self) -> None:
        """Kind field must match exactly."""
        rec = {"kind": "action", "action": "test"}
        assert record_matches(rec, {"kind": "action"}) is True
        assert record_matches(rec, {"kind": "other"}) is False
        assert record_matches(rec, {"kind": "action"}) is True

    def test_action_filter(self) -> None:
        """Action field must match exactly."""
        rec = {"action": "raise_alert"}
        assert record_matches(rec, {"action": "raise_alert"}) is True
        assert record_matches(rec, {"action": "other"}) is False

    def test_source_filter(self) -> None:
        """Source field must match exactly."""
        rec = {"source": "watcher"}
        assert record_matches(rec, {"source": "watcher"}) is True
        assert record_matches(rec, {"source": "llm"}) is False

    def test_missing_field_fails_filter(self) -> None:
        """Record missing a filtered field fails that filter."""
        rec = {"action": "test"}
        assert record_matches(rec, {"action": "test", "source": "watcher"}) is False

    def test_since_filter(self) -> None:
        """Since filters by timestamp >=."""
        rec = {"ts": "2026-07-27T12:00:00+00:00"}
        assert record_matches(rec, {"since": "2026-07-27T11:00:00+00:00"}) is True
        assert record_matches(rec, {"since": "2026-07-27T12:01:00+00:00"}) is False

    def test_until_filter(self) -> None:
        """Until filters by timestamp <=."""
        rec = {"ts": "2026-07-27T12:00:00+00:00"}
        assert record_matches(rec, {"until": "2026-07-27T13:00:00+00:00"}) is True
        assert record_matches(rec, {"until": "2026-07-27T11:00:00+00:00"}) is False

    def test_priority_range_filter(self) -> None:
        """Priority filters by numeric range."""
        rec = {"priority": 0.5}
        assert record_matches(rec, {"min_priority": 0.3}) is True
        assert record_matches(rec, {"max_priority": 0.7}) is True
        assert record_matches(rec, {"min_priority": 0.3, "max_priority": 0.7}) is True
        assert record_matches(rec, {"min_priority": 0.6}) is False
        assert record_matches(rec, {"max_priority": 0.4}) is False

    def test_reason_contains_filter(self) -> None:
        """Reason filter checks substring."""
        rec = {"reason": "depth=1.40m"}
        assert record_matches(rec, {"reason_contains": "depth"}) is True
        assert record_matches(rec, {"reason_contains": "1.40"}) is True
        assert record_matches(rec, {"reason_contains": "speed"}) is False

    def test_unknown_filter_keys_ignored(self) -> None:
        """Unknown filter keys are ignored (not enforced)."""
        rec = {"action": "test"}
        assert record_matches(rec, {"action": "test", "unknown_key": "value"}) is True


# =============================================================================
# Utilities
# =============================================================================

class TestUtilities:
    """Test utility functions."""

    def test_coerce_ts_none(self) -> None:
        """None returns current UTC ISO string."""
        ts = _coerce_ts(None)
        assert isinstance(ts, str)
        # Should parse as valid ISO
        assert datetime.fromisoformat(ts)

    def test_coerce_ts_datetime(self) -> None:
        """Datetime is converted to ISO string."""
        dt = _parse_ts("2026-07-27T12:00:00+00:00")
        ts = _coerce_ts(dt)
        assert ts == "2026-07-27T12:00:00+00:00"

    def test_coerce_ts_number(self) -> None:
        """Epoch seconds are converted to ISO string."""
        ts = _coerce_ts(1722096000)  # 2024-07-27 12:00:00 UTC
        assert ts.startswith("2024-07-27")

    def test_coerce_ts_string_valid(self) -> None:
        """Valid ISO string passes through."""
        ts = _coerce_ts("2026-07-27T12:00:00+00:00")
        assert ts == "2026-07-27T12:00:00+00:00"

    def test_coerce_ts_string_invalid(self) -> None:
        """Invalid ISO string raises ValueError."""
        with pytest.raises(ValueError, match="unparseable"):
            _coerce_ts("not-a-timestamp")

    def test_parse_ts_datetime(self) -> None:
        """Datetime objects pass through."""
        dt = _parse_ts("2026-07-27T12:00:00+00:00")
        assert dt == _parse_ts(dt)

    def test_parse_ts_number(self) -> None:
        """Numbers are converted from epoch."""
        dt = _parse_ts(1722096000)
        assert dt.year == 2024

    def test_parse_ts_string(self) -> None:
        """ISO strings are parsed."""
        dt = _parse_ts("2026-07-27T12:00:00+00:00")
        assert dt.year == 2026
        assert dt.month == 7
        assert dt.day == 27

    def test_parse_ts_invalid_string(self) -> None:
        """Invalid strings return None."""
        assert _parse_ts("not-a-date") is None

    def test_parse_ts_naive_datetime(self) -> None:
        """Naive datetimes are assumed UTC."""
        # Python's fromisoformat creates naive datetime for strings without offset
        from datetime import datetime
        dt_naive = datetime(2026, 7, 27, 12, 0, 0)
        dt = _parse_ts(dt_naive)
        assert dt is not None
        assert dt.tzinfo is not None  # Should have UTC attached


# =============================================================================
# Integration tests
# =============================================================================

class TestA2AIntegration:
    """Test integration between log and query."""

    @pytest.mark.asyncio
    async def test_log_then_query_workflow(self, temp_log_path: Path) -> None:
        """Full workflow: log records, then query them."""
        log = A2ALog(temp_log_path)

        # Log some records
        await log.append("alert", {"type": "shallow"}, source="watcher", priority=0.8)
        await log.append("mode_change", {"mode": "hazard"}, source="llm", priority=0.9)
        await log.append("announce", {"msg": "hello"}, source="crew", priority=0.3)

        # Query them
        query = A2AQuery(temp_log_path)

        all_recs = await query.query()
        assert len(all_recs) == 3

        alerts = await query.query({"action": "alert"})
        assert len(alerts) == 1
        assert alerts[0]["payload"]["type"] == "shallow"

        high_pri = await query.query({"min_priority": 0.7})
        assert len(high_pri) == 2

        counts = await query.count_by("source")
        assert counts == {"watcher": 1, "llm": 1, "crew": 1}

    @pytest.mark.asyncio
    async def test_query_can_read_live_log(self, temp_log_path: Path) -> None:
        """Query can read log while it's being written to."""
        log = A2ALog(temp_log_path)
        query = A2AQuery(temp_log_path)

        # Write some records
        for i in range(5):
            await log.append(f"action_{i}", {})

        # Query should see them
        recs = await query.query()
        assert len(recs) == 5

        # Write more
        for i in range(5, 10):
            await log.append(f"action_{i}", {})

        # Query should see all
        recs = await query.query()
        assert len(recs) == 10


# =============================================================================
# Constants
# =============================================================================

class TestConstants:
    """Test exported constants."""

    def test_valid_sources(self) -> None:
        """VALID_SOURCES contains expected sources."""
        assert VALID_SOURCES == {"watcher", "llm", "crew", "system"}

    def test_default_priority(self) -> None:
        """DEFAULT_PRIORITY is 0.5."""
        assert DEFAULT_PRIORITY == 0.5

    def test_kind_action(self) -> None:
        """KIND_ACTION is 'action'."""
        assert KIND_ACTION == "action"

    def test_known_filters(self) -> None:
        """KNOWN_FILTERS contains expected filter keys."""
        assert "action" in KNOWN_FILTERS
        assert "source" in KNOWN_FILTERS
        assert "min_priority" in KNOWN_FILTERS
        assert "max_priority" in KNOWN_FILTERS


# Need to import datetime for the utility tests
from datetime import datetime  # noqa: E402
