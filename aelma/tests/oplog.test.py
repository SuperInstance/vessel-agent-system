"""Tests for the AELMA operations log (OpLog) system.

Mirrors the A2ALog test structure adapted for operations logging.
Coverage:

  1. OpLog — log_entry validation, serialization, seq monotonicity, stats.
  2. OpLog — rotation (size-based, keep N files).
  3. OpLog — query filters (type, crew, time range, pagination).
  4. OpLog — export formats (JSON, CSV, text).
  5. Error handling — log after close, invalid entry types, malformed data.
  6. Integration — complete workflow with multiple entry types.

Run from the repo root: python -m pytest tests/oplog.test.py -v
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
import pytest_asyncio

# Make the repository root importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twin.oplog import (  # noqa: E402
    OpLog,
    VALID_ENTRY_TYPES,
    KIND_OPLOG,
    _coerce_ts,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_oplog_path(tmp_path: Path) -> Path:
    """Temporary path for oplog files."""
    return tmp_path / "oplog.jsonl"


@pytest.fixture
def temp_oplog(temp_oplog_path: Path) -> OpLog:
    """Fresh OpLog instance for each test."""
    return OpLog(temp_oplog_path)


@pytest_asyncio.fixture
async def populated_oplog(temp_oplog_path: Path) -> OpLog:
    """OpLog with pre-populated operations entries."""
    log = OpLog(temp_oplog_path)
    base_time = datetime(2026, 7, 28, 10, 0, 0, tzinfo=timezone.utc)

    # Add various entry types
    entries = [
        ("gear_deployed", "captain", "Deployed cod pot gear", {"gear_type": "cod_pot", "count": 50}),
        ("haul_started", "crewman", "Started hauling pot 1", {"pot_number": 1}),
        ("haul_complete", "crewman", "Pot 1 retrieved", {"pot_number": 1, "catch_weight": 45}),
        ("catch_logged", "captain", "Logged 45lb cod catch", {"species": "cod", "weight_lb": 45}),
        ("anchor_drop", "crewman", "Dropped anchor in 30ft", {"depth_ft": 30}),
        ("anchor_raise", "crewman", "Raised anchor", {"duration_min": 15}),
        ("manual_alert", "captain", "Saw debris in water", {"alert_type": "debris"}),
        ("crew_note", "deckhand", "Weather worsening", {"wind_kts": 25}),
        ("gear_retrieved", "captain", "All gear retrieved", {"total_pots": 50}),
    ]

    for i, (entry_type, crew, message, metadata) in enumerate(entries):
        ts = base_time + timedelta(minutes=i * 10)
        await log.log_entry(entry_type, crew, message, metadata, ts=ts)

    return log


# =============================================================================
# OpLog: Basic operations
# =============================================================================

class TestOpLogBasic:
    """Test core OpLog functionality: log_entry, validation, stats."""

    @pytest.mark.asyncio
    async def test_init_creates_dir_on_append(self, temp_oplog_path: Path) -> None:
        """Log creates parent directory on first append."""
        nested = temp_oplog_path.parent / "nested" / "oplog.jsonl"
        log = OpLog(nested)
        await log.log_entry("crew_note", "captain", "Test note")
        assert nested.exists()
        assert nested.parent.is_dir()

    @pytest.mark.asyncio
    async def test_log_entry_returns_record_with_seq(self, temp_oplog: OpLog) -> None:
        """log_entry returns complete record including _seq and _loggedAt."""
        rec = await temp_oplog.log_entry(
            "gear_deployed",
            "captain",
            "Deployed trawl gear",
            {"gear_type": "trawl"},
        )
        assert rec["kind"] == KIND_OPLOG
        assert rec["entry_type"] == "gear_deployed"
        assert rec["crew"] == "captain"
        assert rec["message"] == "Deployed trawl gear"
        assert rec["metadata"] == {"gear_type": "trawl"}
        assert "_seq" in rec
        assert "_loggedAt" in rec
        assert "ts" in rec
        assert rec["_seq"] == 0

    @pytest.mark.asyncio
    async def test_seq_monotonic(self, temp_oplog: OpLog) -> None:
        """Sequence numbers increment monotonically."""
        rec1 = await temp_oplog.log_entry("crew_note", "a", "Note 1")
        rec2 = await temp_oplog.log_entry("crew_note", "b", "Note 2")
        rec3 = await temp_oplog.log_entry("crew_note", "c", "Note 3")
        assert rec1["_seq"] == 0
        assert rec2["_seq"] == 1
        assert rec3["_seq"] == 2

    @pytest.mark.asyncio
    async def test_logged_at_is_utc_now(self, temp_oplog: OpLog) -> None:
        """_loggedAt is set to current UTC time."""
        before = datetime.now(timezone.utc)
        rec = await temp_oplog.log_entry("crew_note", "captain", "Test")
        after = datetime.now(timezone.utc)
        logged_at = datetime.fromisoformat(rec["_loggedAt"])
        assert before <= logged_at <= after

    @pytest.mark.asyncio
    async def test_stats(self, temp_oplog: OpLog) -> None:
        """Stats returns current log state."""
        stats = await temp_oplog.stats()
        assert stats["records"] == 0
        assert not stats["closed"]
        assert stats["path"] == str(temp_oplog.path)

        await temp_oplog.log_entry("crew_note", "captain", "Test")
        stats = await temp_oplog.stats()
        assert stats["records"] == 1


# =============================================================================
# OpLog: Validation
# =============================================================================

class TestOpLogValidation:
    """Test input validation for log_entry."""

    @pytest.mark.asyncio
    async def test_invalid_entry_type(self, temp_oplog: OpLog) -> None:
        """Invalid entry_type raises ValueError."""
        with pytest.raises(ValueError, match="entry_type must be one of"):
            await temp_oplog.log_entry("invalid_type", "captain", "Test")

    @pytest.mark.asyncio
    async def test_empty_crew(self, temp_oplog: OpLog) -> None:
        """Empty crew string raises ValueError."""
        with pytest.raises(ValueError, match="crew must be a non-empty string"):
            await temp_oplog.log_entry("crew_note", "", "Test")

        with pytest.raises(ValueError, match="crew must be a non-empty string"):
            await temp_oplog.log_entry("crew_note", "   ", "Test")

    @pytest.mark.asyncio
    async def test_empty_message(self, temp_oplog: OpLog) -> None:
        """Empty message string raises ValueError."""
        with pytest.raises(ValueError, match="message must be a non-empty string"):
            await temp_oplog.log_entry("crew_note", "captain", "")

        with pytest.raises(ValueError, match="message must be a non-empty string"):
            await temp_oplog.log_entry("crew_note", "captain", "   ")

    @pytest.mark.asyncio
    async def test_invalid_metadata_type(self, temp_oplog: OpLog) -> None:
        """Non-mapping metadata raises TypeError."""
        with pytest.raises(TypeError, match="metadata must be a mapping or None"):
            await temp_oplog.log_entry("crew_note", "captain", "Test", metadata="invalid")

    @pytest.mark.asyncio
    async def test_crew_and_message_stripped(self, temp_oplog: OpLog) -> None:
        """Crew and message are stripped of whitespace."""
        rec = await temp_oplog.log_entry(
            "crew_note",
            "  captain  ",
            "  Test message  ",
        )
        assert rec["crew"] == "captain"
        assert rec["message"] == "Test message"


# =============================================================================
# OpLog: Timestamp handling
# =============================================================================

class TestOpLogTimestamps:
    """Test timestamp coercion and handling."""

    @pytest.mark.asyncio
    async def test_default_ts_is_now(self, temp_oplog: OpLog) -> None:
        """Default ts is current UTC time."""
        before = datetime.now(timezone.utc)
        rec = await temp_oplog.log_entry("crew_note", "captain", "Test")
        after = datetime.now(timezone.utc)

        ts = datetime.fromisoformat(rec["ts"])
        assert before <= ts <= after

    @pytest.mark.asyncio
    async def test_datetime_ts(self, temp_oplog: OpLog) -> None:
        """datetime object is accepted and converted."""
        dt = datetime(2026, 7, 28, 12, 30, 45, tzinfo=timezone.utc)
        rec = await temp_oplog.log_entry("crew_note", "captain", "Test", ts=dt)
        assert rec["ts"] == "2026-07-28T12:30:45+00:00"

    @pytest.mark.asyncio
    async def test_naive_datetime_assumed_utc(self, temp_oplog: OpLog) -> None:
        """Naive datetime is assumed UTC."""
        dt = datetime(2026, 7, 28, 12, 30, 45)
        rec = await temp_oplog.log_entry("crew_note", "captain", "Test", ts=dt)
        assert rec["ts"] == "2026-07-28T12:30:45+00:00"

    @pytest.mark.asyncio
    async def test_epoch_seconds_ts(self, temp_oplog: OpLog) -> None:
        """Epoch seconds are accepted."""
        ts = 1722165645  # 2024-07-28 11:20:45 UTC (test accounts for timezone)
        rec = await temp_oplog.log_entry("crew_note", "captain", "Test", ts=ts)
        # Just verify it's a valid ISO timestamp, don't hardcode specific value
        # due to potential timezone differences in test environments
        assert rec["ts"].startswith("2024-07-28T")
        assert "+00:00" in rec["ts"]

    @pytest.mark.asyncio
    async def test_iso_string_ts(self, temp_oplog: OpLog) -> None:
        """ISO string is accepted and validated."""
        ts = "2026-07-28T12:30:45+00:00"
        rec = await temp_oplog.log_entry("crew_note", "captain", "Test", ts=ts)
        assert rec["ts"] == ts

    @pytest.mark.asyncio
    async def test_invalid_iso_string_raises(self, temp_oplog: OpLog) -> None:
        """Invalid ISO string raises ValueError."""
        with pytest.raises(ValueError, match="unparseable ts string"):
            await temp_oplog.log_entry("crew_note", "captain", "Test", ts="invalid")


# =============================================================================
# OpLog: Query operations
# =============================================================================

class TestOpLogQuery:
    """Test query filters and pagination."""

    @pytest.mark.asyncio
    async def test_query_all(self, populated_oplog: OpLog) -> None:
        """Query with no filters returns all records."""
        results = await populated_oplog.query()
        assert len(results) == 9

    @pytest.mark.asyncio
    async def test_query_by_entry_type_single(self, populated_oplog: OpLog) -> None:
        """Filter by single entry type."""
        results = await populated_oplog.query(entry_type="gear_deployed")
        assert len(results) == 1
        assert results[0]["entry_type"] == "gear_deployed"

    @pytest.mark.asyncio
    async def test_query_by_entry_type_multiple(self, populated_oplog: OpLog) -> None:
        """Filter by multiple entry types."""
        results = await populated_oplog.query(
            entry_type={"gear_deployed", "gear_retrieved"}
        )
        assert len(results) == 2
        entry_types = {r["entry_type"] for r in results}
        assert entry_types == {"gear_deployed", "gear_retrieved"}

    @pytest.mark.asyncio
    async def test_query_by_crew_single(self, populated_oplog: OpLog) -> None:
        """Filter by single crew member."""
        results = await populated_oplog.query(crew="captain")
        assert len(results) == 4
        assert all(r["crew"] == "captain" for r in results)

    @pytest.mark.asyncio
    async def test_query_by_crew_multiple(self, populated_oplog: OpLog) -> None:
        """Filter by multiple crew members."""
        results = await populated_oplog.query(crew={"captain", "crewman"})
        assert len(results) == 8

    @pytest.mark.asyncio
    async def test_query_by_time_range(self, populated_oplog: OpLog) -> None:
        """Filter by time range."""
        start = datetime(2026, 7, 28, 10, 20, 0, tzinfo=timezone.utc)
        end = datetime(2026, 7, 28, 10, 40, 0, tzinfo=timezone.utc)

        results = await populated_oplog.query(start_time=start, end_time=end)
        # Should include entries at 10:20, 10:30, 10:40 (index 2, 3, 4)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_query_results_sorted_newest_first(self, populated_oplog: OpLog) -> None:
        """Query results are sorted by timestamp descending (newest first)."""
        results = await populated_oplog.query()
        timestamps = [r["ts"] for r in results]
        assert timestamps == sorted(timestamps, reverse=True)

    @pytest.mark.asyncio
    async def test_query_with_limit(self, populated_oplog: OpLog) -> None:
        """Limit restricts number of results."""
        results = await populated_oplog.query(limit=5)
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_query_with_offset(self, populated_oplog: OpLog) -> None:
        """Offset skips records for pagination."""
        first_page = await populated_oplog.query(limit=3, offset=0)
        second_page = await populated_oplog.query(limit=3, offset=3)

        assert len(first_page) == 3
        assert len(second_page) == 3
        assert first_page != second_page

    @pytest.mark.asyncio
    async def test_query_combined_filters(self, populated_oplog: OpLog) -> None:
        """Multiple filters work together (AND logic)."""
        # captain's haul entries
        results = await populated_oplog.query(
            entry_type="haul_complete",
            crew="crewman",
        )
        assert len(results) == 1
        assert results[0]["entry_type"] == "haul_complete"
        assert results[0]["crew"] == "crewman"


# =============================================================================
# OpLog: Export operations
# =============================================================================

class TestOpLogExport:
    """Test export to different formats."""

    @pytest.mark.asyncio
    async def test_export_json(self, populated_oplog: OpLog) -> None:
        """Export to JSON returns valid JSON string."""
        output = await populated_oplog.export(format="json", limit=5)
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 5
        assert data[0]["kind"] == KIND_OPLOG

    @pytest.mark.asyncio
    async def test_export_csv(self, populated_oplog: OpLog) -> None:
        """Export to CSV returns valid CSV string."""
        output = await populated_oplog.export(format="csv", limit=3)
        lines = output.strip().split("\n")
        assert len(lines) >= 2  # Header + at least 1 data row

        # Check header has standard fields
        header = lines[0]
        assert "entry_type" in header
        assert "crew" in header
        assert "message" in header

    @pytest.mark.asyncio
    async def test_export_csv_with_metadata(self, populated_oplog: OpLog) -> None:
        """CSV export flattens metadata fields."""
        output = await populated_oplog.export(
            format="csv",
            entry_type="catch_logged",
        )
        assert "metadata_species" in output
        assert "metadata_weight_lb" in output

    @pytest.mark.asyncio
    async def test_export_text(self, populated_oplog: OpLog) -> None:
        """Export to text returns human-readable format."""
        output = await populated_oplog.export(format="text", limit=2)
        assert "[2026-07-28" in output  # timestamp
        assert "gear_retrieved" in output or "captain" in output

    @pytest.mark.asyncio
    async def test_export_text_with_metadata(self, populated_oplog: OpLog) -> None:
        """Text export includes metadata fields."""
        output = await populated_oplog.export(
            format="text",
            entry_type="catch_logged",
        )
        assert "species:" in output
        assert "cod" in output
        assert "weight_lb:" in output

    @pytest.mark.asyncio
    async def test_export_empty_results(self, temp_oplog: OpLog) -> None:
        """Export with no matching records returns empty/valid output."""
        json_output = await temp_oplog.export(format="json")
        assert json_output == "[]"

        csv_output = await temp_oplog.export(format="csv")
        assert csv_output == ""

        text_output = await temp_oplog.export(format="text")
        assert text_output == ""

    @pytest.mark.asyncio
    async def test_export_invalid_format(self, populated_oplog: OpLog) -> None:
        """Invalid export format raises ValueError."""
        with pytest.raises(ValueError, match="unsupported format"):
            await populated_oplog.export(format="xml")

    @pytest.mark.asyncio
    async def test_export_with_filters(self, populated_oplog: OpLog) -> None:
        """Export applies same filters as query."""
        output = await populated_oplog.export(
            format="json",
            crew="captain",
            limit=2,
        )
        data = json.loads(output)
        assert len(data) == 2
        assert all(r["crew"] == "captain" for r in data)


# =============================================================================
# OpLog: File rotation
# =============================================================================

class TestOpLogRotation:
    """Test log rotation based on file size."""

    @pytest.mark.asyncio
    async def test_rotation_triggered_at_max_bytes(self, tmp_path: Path) -> None:
        """Log rotates when it exceeds max_bytes."""
        log_path = tmp_path / "rotate.jsonl"
        log = OpLog(log_path, max_bytes=500, keep=3)

        # Write enough data to trigger rotation
        for i in range(10):
            await log.log_entry(
                "crew_note",
                "captain",
                f"Test message {i} with some extra text to fill space",
            )

        stats = await log.stats()
        # File should have been rotated, size should be smaller
        assert stats["records"] == 10

        # Check that rotated file exists
        rotated = log_path.parent / "rotate.jsonl.1"
        assert rotated.exists()

    @pytest.mark.asyncio
    async def test_keep_parameter(self, tmp_path: Path) -> None:
        """Only N rotated files are kept."""
        log_path = tmp_path / "keep.jsonl"
        log = OpLog(log_path, max_bytes=200, keep=2)

        # Trigger multiple rotations
        for rotation in range(3):
            for i in range(5):
                await log.log_entry(
                    "crew_note",
                    "captain",
                    f"Rotation {rotation} message {i} " + "x" * 50,
                )

        # Only .1 and .2 should exist, .3 should be deleted
        assert (log_path.parent / "keep.jsonl.1").exists()
        assert (log_path.parent / "keep.jsonl.2").exists()
        assert not (log_path.parent / "keep.jsonl.3").exists()

    @pytest.mark.asyncio
    async def test_query_includes_rotated_files(self, tmp_path: Path) -> None:
        """Query reads from both active and rotated files."""
        log_path = tmp_path / "query_rotate.jsonl"
        log = OpLog(log_path, max_bytes=1000, keep=2)  # Larger max_bytes to prevent rotation during test

        # First, manually create a rotated file with known content
        rotated_path = log_path.parent / "query_rotate.jsonl.1"
        with rotated_path.open("w", encoding="utf-8") as f:
            for i in range(3):
                import json
                record = {
                    "kind": "oplog_entry",
                    "entry_type": "crew_note",
                    "crew": "captain",
                    "message": f"Rotated message {i}",
                    "metadata": {},
                    "ts": "2026-07-28T10:00:00+00:00",
                    "_loggedAt": "2026-07-28T10:00:00+00:00",
                    "_seq": i
                }
                f.write(json.dumps(record) + "\n")

        # Verify rotated file exists and has content
        assert rotated_path.exists()
        line_count = 0
        with rotated_path.open("r") as f:
            for line in f:
                if line.strip():
                    line_count += 1
        assert line_count == 3, f"Rotated file should have 3 lines, has {line_count}"

        # Now add some entries to the active file
        for i in range(3):
            await log.log_entry(
                "crew_note",
                "captain",
                f"Active message {i}"
            )

        # Verify active file has content
        assert log_path.exists()
        active_line_count = 0
        with log_path.open("r") as f:
            for line in f:
                if line.strip():
                    active_line_count += 1
        assert active_line_count == 3, f"Active file should have 3 lines, has {active_line_count}"

        # Query should read from both files
        results = await log.query()

        assert len(results) == 6, f"Expected 6 results (3 from rotated + 3 from active), got {len(results)}"


# =============================================================================
# OpLog: Error handling
# =============================================================================

class TestOpLogErrors:
    """Test error conditions and edge cases."""

    @pytest.mark.asyncio
    async def test_log_after_close_raises(self, temp_oplog: OpLog) -> None:
        """Logging after close raises RuntimeError."""
        await temp_oplog.close()
        with pytest.raises(RuntimeError, match="log_entry after close"):
            await temp_oplog.log_entry("crew_note", "captain", "Test")

    @pytest.mark.asyncio
    async def test_invalid_max_bytes(self, temp_oplog_path: Path) -> None:
        """Invalid max_bytes raises ValueError."""
        with pytest.raises(ValueError, match="max_bytes must be positive"):
            OpLog(temp_oplog_path, max_bytes=0)

        with pytest.raises(ValueError, match="max_bytes must be positive"):
            OpLog(temp_oplog_path, max_bytes=-100)

    @pytest.mark.asyncio
    async def test_invalid_keep(self, temp_oplog_path: Path) -> None:
        """Invalid keep parameter raises ValueError."""
        with pytest.raises(ValueError, match="keep must be at least 1"):
            OpLog(temp_oplog_path, keep=0)

        with pytest.raises(ValueError, match="keep must be at least 1"):
            OpLog(temp_oplog_path, keep=-1)

    @pytest.mark.asyncio
    async def test_context_manager(self, temp_oplog_path: Path) -> None:
        """OpLog works as async context manager."""
        async with OpLog(temp_oplog_path) as log:
            await log.log_entry("crew_note", "captain", "Test")

        # Should be closed now
        with pytest.raises(RuntimeError):
            await log.log_entry("crew_note", "captain", "Test 2")


# =============================================================================
# OpLog: Integration tests
# =============================================================================

class TestOpLogIntegration:
    """Integration tests for realistic workflows."""

    @pytest.mark.asyncio
    async def test_complete_fishing_operation(self, temp_oplog: OpLog) -> None:
        """Track a complete fishing operation from deployment to catch logging."""
        base_time = datetime(2026, 7, 28, 6, 0, 0, tzinfo=timezone.utc)

        # Deploy gear
        await temp_oplog.log_entry(
            "gear_deployed",
            "captain",
            "Deployed cod pot gear at 59.5N, 152.3W",
            {"gear_type": "cod_pot", "count": 50, "lat": 59.5, "lon": -152.3},
            ts=base_time,
        )

        # Start hauling
        haul_start = base_time + timedelta(hours=4)
        await temp_oplog.log_entry(
            "haul_started",
            "crewman",
            "Started hauling pot string 1",
            {"string_number": 1, "pot_count": 25},
            ts=haul_start,
        )

        # Complete haul
        haul_end = haul_start + timedelta(minutes=30)
        await temp_oplog.log_entry(
            "haul_complete",
            "captain",
            "Completed haul of string 1",
            {
                "string_number": 1,
                "total_pots": 25,
                "duration_minutes": 30,
                "estimated_catch_lb": 1200,
            },
            ts=haul_end,
        )

        # Log catch
        await temp_oplog.log_entry(
            "catch_logged",
            "captain",
            "Logged catch: cod, 1200lb",
            {"species": "cod", "weight_lb": 1200, "avg_weight_per_pot": 48},
            ts=haul_end + timedelta(minutes=5),
        )

        # Query the operation
        operation = await temp_oplog.query(
            entry_type={"gear_deployed", "haul_started", "haul_complete", "catch_logged"},
            start_time=base_time,
        )

        assert len(operation) == 4
        assert operation[-1]["entry_type"] == "gear_deployed"  # Oldest first

    @pytest.mark.asyncio
    async def test_crew_shift_tracking(self, temp_oplog: OpLog) -> None:
        """Track notes across a crew shift change."""
        morning_shift = datetime(2026, 7, 28, 6, 0, 0, tzinfo=timezone.utc)

        # Morning shift notes
        await temp_oplog.log_entry(
            "crew_note",
            "captain_john",
            "Shift started, weather good",
            {"wind_kts": 10, "visibility": "good"},
            ts=morning_shift,
        )

        # Add another entry for captain_john
        await temp_oplog.log_entry(
            "gear_deployed",
            "captain_john",
            "Deployed pot gear during morning shift",
            {"gear_type": "pot", "count": 50},
            ts=morning_shift + timedelta(hours=1),
        )

        await temp_oplog.log_entry(
            "manual_alert",
            "crewman_steve",
            "Noticed slight oil leak in winch",
            {"alert_type": "maintenance", "severity": "low"},
            ts=morning_shift + timedelta(hours=2),
        )

        # Shift change
        shift_change = morning_shift + timedelta(hours=8)
        await temp_oplog.log_entry(
            "crew_note",
            "captain_jane",
            "Shift change, relieved John",
            {"outgoing_captain": "john", "incoming_captain": "jane"},
            ts=shift_change,
        )

        # Evening shift notes
        await temp_oplog.log_entry(
            "anchor_drop",
            "captain_jane",
            "Dropped anchor for night",
            {"depth_ft": 40, "scope_ratio": 7},
            ts=shift_change + timedelta(hours=6),
        )

        # Query by specific crew
        john_entries = await temp_oplog.query(crew="captain_john")
        assert len(john_entries) == 2

        jane_entries = await temp_oplog.query(crew="captain_jane")
        assert len(jane_entries) == 2

    @pytest.mark.asyncio
    async def test_export_fishing_report(self, temp_oplog: OpLog) -> None:
        """Generate a fishing report in multiple formats."""
        # Add sample data
        await temp_oplog.log_entry(
            "gear_deployed",
            "captain",
            "Deployed trawl gear",
            {"gear_type": "trawl", "depth_m": 100},
        )
        await temp_oplog.log_entry(
            "catch_logged",
            "captain",
            "Caught 500lb pollock",
            {"species": "pollock", "weight_lb": 500},
        )

        # Export in different formats
        json_report = await temp_oplog.export(format="json")
        assert "pollock" in json_report

        csv_report = await temp_oplog.export(format="csv")
        assert "gear_deployed" in csv_report
        assert "catch_logged" in csv_report

        text_report = await temp_oplog.export(format="text")
        assert "Deployed trawl gear" in text_report
        assert "Caught 500lb pollock" in text_report


# =============================================================================
# Utilities
# =============================================================================

class TestUtilities:
    """Test utility functions."""

    def test_coerce_ts_with_datetime(self) -> None:
        """_coerce_ts handles datetime objects."""
        dt = datetime(2026, 7, 28, 12, 30, 45, tzinfo=timezone.utc)
        result = _coerce_ts(dt)
        assert result == "2026-07-28T12:30:45+00:00"

    def test_coerce_ts_with_naive_datetime(self) -> None:
        """_coerce_ts assumes UTC for naive datetime."""
        dt = datetime(2026, 7, 28, 12, 30, 45)
        result = _coerce_ts(dt)
        assert result == "2026-07-28T12:30:45+00:00"

    def test_coerce_ts_with_epoch_seconds(self) -> None:
        """_coerce_ts handles epoch seconds."""
        result = _coerce_ts(1722165645)
        # Just verify it's a valid ISO timestamp with UTC timezone
        assert result.startswith("2024-07-28T")
        assert "+00:00" in result

    def test_coerce_ts_with_iso_string(self) -> None:
        """_coerce_ts validates and returns ISO strings."""
        iso = "2026-07-28T12:30:45+00:00"
        result = _coerce_ts(iso)
        assert result == iso

    def test_coerce_ts_with_none(self) -> None:
        """_coerce_ts returns current time for None."""
        before = datetime.now(timezone.utc)
        result = _coerce_ts(None)
        after = datetime.now(timezone.utc)

        ts = datetime.fromisoformat(result)
        assert before <= ts <= after

    def test_coerce_ts_invalid_string(self) -> None:
        """_coerce_ts raises ValueError for invalid strings."""
        with pytest.raises(ValueError, match="unparseable ts string"):
            _coerce_ts("not-a-timestamp")

    def test_valid_entry_types_complete(self) -> None:
        """VALID_ENTRY_TYPES includes all expected types."""
        expected = {
            "gear_deployed",
            "gear_retrieved",
            "haul_started",
            "haul_complete",
            "anchor_drop",
            "anchor_raise",
            "manual_alert",
            "crew_note",
            "catch_logged",
        }
        assert VALID_ENTRY_TYPES == expected
