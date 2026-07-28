"""Tests for the AELMA catch logging system (CatchLog).

Mirrors the OpLog test structure adapted for catch tracking.
Coverage:

  1. CatchLog — log_catch validation, serialization, seq monotonicity.
  2. CatchLog — JSONL storage, resume across instances.
  3. CatchLog — get_catch_summary aggregation.
  4. CatchLog — export_to_csv (string and file output).
  5. OpLog integration — catch_logged entries mirrored with metadata.
  6. Error handling — bad species/weight/count/location, log after close.

Run from the repo root: python -m pytest tests/catch_log.test.py -v
"""

from __future__ import annotations

import csv
import json
import sys
from io import StringIO
from pathlib import Path

import pytest
import pytest_asyncio

# Make the repository root importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twin.catch_log import (  # noqa: E402
    KIND_CATCH,
    VALID_SPECIES,
    CatchLog,
)
from twin.oplog import OpLog  # noqa: E402


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_catch_path(tmp_path: Path) -> Path:
    """Temporary path for catch log files."""
    return tmp_path / "catch_log.jsonl"


@pytest.fixture
def temp_catch_log(temp_catch_path: Path) -> CatchLog:
    """Fresh CatchLog instance for each test."""
    return CatchLog(temp_catch_path)


@pytest_asyncio.fixture
async def populated_log(temp_catch_path: Path) -> CatchLog:
    """CatchLog with pre-populated catch records."""
    log = CatchLog(temp_catch_path)
    await log.log_catch(
        "salmon", 24.5, count=2,
        location={"lat": 59.5, "lon": -152.3}, depth=40.0,
        method="troll", quality="premium",
    )
    await log.log_catch("halibut", 85.0, count=1, location="Kachemak Bay",
                        method="longline", quality="standard")
    await log.log_catch("cod", 45.25, count=12, depth=120.0, method="pot")
    await log.log_catch("crab", 30.0, count=15, method="pot", quality="premium")
    await log.log_catch("shrimp", 10.5, count=200)
    await log.log_catch("salmon", 11.0, count=1, method="troll", quality="standard")
    return log


# =============================================================================
# CatchLog: Basic operations
# =============================================================================

class TestCatchLogBasic:
    """Test core CatchLog functionality: log_catch, validation, stats."""

    @pytest.mark.asyncio
    async def test_init_creates_dir_on_append(self, temp_catch_path: Path) -> None:
        """Log creates parent directory on first append."""
        nested = temp_catch_path.parent / "nested" / "catch.jsonl"
        log = CatchLog(nested)
        await log.log_catch("cod", 5.0)
        assert nested.exists()
        assert nested.parent.is_dir()

    @pytest.mark.asyncio
    async def test_log_catch_returns_record_with_seq(self, temp_catch_log: CatchLog) -> None:
        """log_catch returns complete record including _seq and _loggedAt."""
        rec = await temp_catch_log.log_catch(
            "salmon", 12.5, count=2,
            location={"lat": 59.5, "lon": -152.3},
            depth=40.0, method="troll", quality="premium",
        )
        assert rec["kind"] == KIND_CATCH
        assert rec["species"] == "salmon"
        assert rec["weight_lb"] == 12.5
        assert rec["count"] == 2
        assert rec["location"] == {"lat": 59.5, "lon": -152.3}
        assert rec["depth"] == 40.0
        assert rec["method"] == "troll"
        assert rec["quality"] == "premium"
        assert "_seq" in rec
        assert "_loggedAt" in rec
        assert "ts" in rec
        assert rec["_seq"] == 0

    @pytest.mark.asyncio
    async def test_species_normalized_to_lowercase(self, temp_catch_log: CatchLog) -> None:
        """Species input is case-insensitive and stored lowercase."""
        rec = await temp_catch_log.log_catch("  Salmon ", 5.0)
        assert rec["species"] == "salmon"

    @pytest.mark.asyncio
    async def test_all_supported_species(self, temp_catch_log: CatchLog) -> None:
        """Every supported species logs successfully."""
        assert VALID_SPECIES == {"salmon", "halibut", "cod", "crab", "shrimp"}
        for species in sorted(VALID_SPECIES):
            rec = await temp_catch_log.log_catch(species, 1.0)
            assert rec["species"] == species

    @pytest.mark.asyncio
    async def test_seq_monotonic(self, temp_catch_log: CatchLog) -> None:
        """Sequence numbers increment monotonically."""
        rec1 = await temp_catch_log.log_catch("cod", 1.0)
        rec2 = await temp_catch_log.log_catch("cod", 2.0)
        rec3 = await temp_catch_log.log_catch("cod", 3.0)
        assert rec1["_seq"] == 0
        assert rec2["_seq"] == 1
        assert rec3["_seq"] == 2
        assert temp_catch_log.seq == 3

    @pytest.mark.asyncio
    async def test_seq_resumes_across_instances(self, temp_catch_path: Path) -> None:
        """A new CatchLog on an existing file continues the sequence."""
        log1 = CatchLog(temp_catch_path)
        await log1.log_catch("cod", 1.0)
        await log1.log_catch("cod", 2.0)
        log2 = CatchLog(temp_catch_path)
        assert log2.seq == 2
        rec = await log2.log_catch("cod", 3.0)
        assert rec["_seq"] == 2

    @pytest.mark.asyncio
    async def test_optional_fields_default_none(self, temp_catch_log: CatchLog) -> None:
        """Omitted optional fields are stored as None."""
        rec = await temp_catch_log.log_catch("shrimp", 3.0)
        assert rec["location"] is None
        assert rec["depth"] is None
        assert rec["method"] is None
        assert rec["quality"] is None
        assert rec["count"] == 1

    @pytest.mark.asyncio
    async def test_string_location_accepted(self, temp_catch_log: CatchLog) -> None:
        """Location may be a free-form place string."""
        rec = await temp_catch_log.log_catch("halibut", 50.0, location="Kachemak Bay")
        assert rec["location"] == "Kachemak Bay"

    @pytest.mark.asyncio
    async def test_stats(self, temp_catch_log: CatchLog) -> None:
        """stats() reflects records written and file state."""
        await temp_catch_log.log_catch("cod", 5.0)
        stats = await temp_catch_log.stats()
        assert stats["records"] == 1
        assert stats["closed"] is False
        assert stats["size_bytes"] > 0
        assert stats["oplog_attached"] is False


# =============================================================================
# CatchLog: JSONL storage
# =============================================================================

class TestCatchLogStorage:
    """Test on-disk JSONL storage format."""

    @pytest.mark.asyncio
    async def test_file_is_jsonl(self, temp_catch_log: CatchLog, temp_catch_path: Path) -> None:
        """Each record lands as one JSON object per line."""
        await temp_catch_log.log_catch("salmon", 10.0, count=1)
        await temp_catch_log.log_catch("cod", 20.0, count=3)
        lines = temp_catch_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first["kind"] == KIND_CATCH
        assert first["species"] == "salmon"
        second = json.loads(lines[1])
        assert second["species"] == "cod"

    @pytest.mark.asyncio
    async def test_malformed_lines_skipped(
        self, temp_catch_log: CatchLog, temp_catch_path: Path
    ) -> None:
        """Malformed lines do not break summary/export."""
        await temp_catch_log.log_catch("cod", 5.0)
        with temp_catch_path.open("a", encoding="utf-8") as fh:
            fh.write("not json\n")
            fh.write('{"kind": "other_kind", "species": "cod"}\n')
        summary = temp_catch_log.get_catch_summary()
        assert summary["entries"] == 1
        assert summary["total_weight_lb"] == 5.0


# =============================================================================
# CatchLog: Summary aggregation
# =============================================================================

class TestCatchSummary:
    """Test get_catch_summary aggregation."""

    @pytest.mark.asyncio
    async def test_summary_totals(self, populated_log: CatchLog) -> None:
        """Summary aggregates entries, count, and weight across species."""
        summary = populated_log.get_catch_summary()
        assert summary["entries"] == 6
        assert summary["total_count"] == 2 + 1 + 12 + 15 + 200 + 1
        assert summary["total_weight_lb"] == round(
            24.5 + 85.0 + 45.25 + 30.0 + 10.5 + 11.0, 3
        )

    @pytest.mark.asyncio
    async def test_summary_by_species(self, populated_log: CatchLog) -> None:
        """Per-species buckets carry entries, count, and weight."""
        summary = populated_log.get_catch_summary()
        by_species = summary["by_species"]
        assert set(by_species) == {"salmon", "halibut", "cod", "crab", "shrimp"}
        assert by_species["salmon"] == {
            "entries": 2, "count": 3, "weight_lb": 35.5
        }
        assert by_species["halibut"] == {
            "entries": 1, "count": 1, "weight_lb": 85.0
        }
        assert by_species["shrimp"] == {
            "entries": 1, "count": 200, "weight_lb": 10.5
        }

    @pytest.mark.asyncio
    async def test_summary_empty_log(self, temp_catch_log: CatchLog) -> None:
        """Empty log yields a zeroed summary."""
        summary = temp_catch_log.get_catch_summary()
        assert summary == {
            "entries": 0,
            "total_count": 0,
            "total_weight_lb": 0.0,
            "by_species": {},
        }


# =============================================================================
# CatchLog: CSV export
# =============================================================================

class TestCatchCsvExport:
    """Test export_to_csv."""

    @pytest.mark.asyncio
    async def test_csv_header_and_rows(self, populated_log: CatchLog) -> None:
        """CSV has a header and one row per record."""
        content = populated_log.export_to_csv()
        reader = list(csv.DictReader(StringIO(content)))
        assert len(reader) == 6
        assert set(reader[0].keys()) == {
            "ts", "species", "weight_lb", "count",
            "location", "depth", "method", "quality", "_seq",
        }
        first = reader[0]
        assert first["species"] == "salmon"
        assert first["weight_lb"] == "24.5"
        assert first["count"] == "2"
        assert first["location"] == "59.5,-152.3"
        assert first["depth"] == "40.0"
        assert first["method"] == "troll"
        assert first["quality"] == "premium"

    @pytest.mark.asyncio
    async def test_csv_string_location(self, populated_log: CatchLog) -> None:
        """String locations pass through verbatim."""
        content = populated_log.export_to_csv()
        rows = list(csv.DictReader(StringIO(content)))
        assert rows[1]["location"] == "Kachemak Bay"

    @pytest.mark.asyncio
    async def test_csv_writes_file(self, populated_log: CatchLog, tmp_path: Path) -> None:
        """export_to_csv writes the file when a path is given."""
        out = tmp_path / "exports" / "catch.csv"
        content = populated_log.export_to_csv(out)
        assert out.exists()
        with out.open("r", encoding="utf-8", newline="") as fh:
            assert fh.read() == content

    @pytest.mark.asyncio
    async def test_csv_empty_log(self, temp_catch_log: CatchLog) -> None:
        """Empty log exports an empty string."""
        assert temp_catch_log.export_to_csv() == ""


# =============================================================================
# OpLog integration
# =============================================================================

class TestOpLogIntegration:
    """Test mirroring of catch records into the OpLog."""

    @pytest.mark.asyncio
    async def test_catch_mirrored_as_catch_logged(self, tmp_path: Path) -> None:
        """Each catch produces a catch_logged OpLog entry with full metadata."""
        oplog = OpLog(tmp_path / "oplog.jsonl")
        log = CatchLog(tmp_path / "catch.jsonl", oplog=oplog, crew="captain")
        await log.log_catch(
            "halibut", 85.0, count=1,
            location={"lat": 59.5, "lon": -152.3}, depth=60.0,
            method="longline", quality="premium",
        )
        entries = await oplog.query(entry_type="catch_logged")
        assert len(entries) == 1
        entry = entries[0]
        assert entry["crew"] == "captain"
        assert "halibut" in entry["message"]
        assert "85" in entry["message"]
        meta = entry["metadata"]
        assert meta["species"] == "halibut"
        assert meta["weight_lb"] == 85.0
        assert meta["count"] == 1
        assert meta["location"] == {"lat": 59.5, "lon": -152.3}
        assert meta["depth"] == 60.0
        assert meta["method"] == "longline"
        assert meta["quality"] == "premium"

    @pytest.mark.asyncio
    async def test_crew_override_per_call(self, tmp_path: Path) -> None:
        """Per-call crew argument overrides the constructor default."""
        oplog = OpLog(tmp_path / "oplog.jsonl")
        log = CatchLog(tmp_path / "catch.jsonl", oplog=oplog, crew="captain")
        await log.log_catch("cod", 10.0, crew="deckhand")
        entries = await oplog.query(entry_type="catch_logged")
        assert entries[0]["crew"] == "deckhand"

    @pytest.mark.asyncio
    async def test_no_oplog_no_mirror(self, temp_catch_log: CatchLog) -> None:
        """Without an OpLog attached, logging still works standalone."""
        rec = await temp_catch_log.log_catch("crab", 5.0, count=3)
        assert rec["species"] == "crab"
        stats = await temp_catch_log.stats()
        assert stats["oplog_attached"] is False

    @pytest.mark.asyncio
    async def test_oplog_ts_matches_catch_ts(self, tmp_path: Path) -> None:
        """Mirrored OpLog entry carries the same timestamp as the catch."""
        oplog = OpLog(tmp_path / "oplog.jsonl")
        log = CatchLog(tmp_path / "catch.jsonl", oplog=oplog)
        rec = await log.log_catch("shrimp", 2.0, ts=1753700000)
        entries = await oplog.query(entry_type="catch_logged")
        assert entries[0]["ts"] == rec["ts"]


# =============================================================================
# Error handling
# =============================================================================

class TestCatchLogErrors:
    """Test validation and lifecycle errors."""

    @pytest.mark.asyncio
    async def test_invalid_species_rejected(self, temp_catch_log: CatchLog) -> None:
        """Unsupported species raise ValueError."""
        with pytest.raises(ValueError, match="species"):
            await temp_catch_log.log_catch("tuna", 10.0)

    @pytest.mark.asyncio
    async def test_empty_species_rejected(self, temp_catch_log: CatchLog) -> None:
        """Empty species string raises ValueError."""
        with pytest.raises(ValueError, match="species"):
            await temp_catch_log.log_catch("  ", 10.0)

    @pytest.mark.asyncio
    async def test_negative_weight_rejected(self, temp_catch_log: CatchLog) -> None:
        """Negative weight raises ValueError."""
        with pytest.raises(ValueError, match="weight_lb"):
            await temp_catch_log.log_catch("cod", -1.0)

    @pytest.mark.asyncio
    async def test_non_numeric_weight_rejected(self, temp_catch_log: CatchLog) -> None:
        """Non-numeric weight raises TypeError."""
        with pytest.raises(TypeError, match="weight_lb"):
            await temp_catch_log.log_catch("cod", "heavy")

    @pytest.mark.asyncio
    async def test_bool_weight_rejected(self, temp_catch_log: CatchLog) -> None:
        """Boolean weight raises TypeError (bool is not a number here)."""
        with pytest.raises(TypeError, match="weight_lb"):
            await temp_catch_log.log_catch("cod", True)

    @pytest.mark.asyncio
    async def test_zero_count_rejected(self, temp_catch_log: CatchLog) -> None:
        """Count below 1 raises ValueError."""
        with pytest.raises(ValueError, match="count"):
            await temp_catch_log.log_catch("cod", 5.0, count=0)

    @pytest.mark.asyncio
    async def test_non_int_count_rejected(self, temp_catch_log: CatchLog) -> None:
        """Non-integer count raises TypeError."""
        with pytest.raises(TypeError, match="count"):
            await temp_catch_log.log_catch("cod", 5.0, count=2.5)

    @pytest.mark.asyncio
    async def test_bad_location_mapping_rejected(self, temp_catch_log: CatchLog) -> None:
        """Location mapping without numeric lat/lon raises ValueError."""
        with pytest.raises(ValueError, match="location"):
            await temp_catch_log.log_catch("cod", 5.0, location={"lat": "x", "lon": 1.0})

    @pytest.mark.asyncio
    async def test_out_of_range_lat_rejected(self, temp_catch_log: CatchLog) -> None:
        """Latitude outside [-90, 90] raises ValueError."""
        with pytest.raises(ValueError, match="lat"):
            await temp_catch_log.log_catch(
                "cod", 5.0, location={"lat": 91.0, "lon": 0.0}
            )

    @pytest.mark.asyncio
    async def test_bad_location_type_rejected(self, temp_catch_log: CatchLog) -> None:
        """Non-string/non-mapping location raises TypeError."""
        with pytest.raises(TypeError, match="location"):
            await temp_catch_log.log_catch("cod", 5.0, location=12345)

    @pytest.mark.asyncio
    async def test_negative_depth_rejected(self, temp_catch_log: CatchLog) -> None:
        """Negative depth raises ValueError."""
        with pytest.raises(ValueError, match="depth"):
            await temp_catch_log.log_catch("cod", 5.0, depth=-10.0)

    @pytest.mark.asyncio
    async def test_empty_method_rejected(self, temp_catch_log: CatchLog) -> None:
        """Empty method string raises ValueError."""
        with pytest.raises(ValueError, match="method"):
            await temp_catch_log.log_catch("cod", 5.0, method="  ")

    @pytest.mark.asyncio
    async def test_log_after_close_raises(self, temp_catch_log: CatchLog) -> None:
        """log_catch after close() raises RuntimeError."""
        await temp_catch_log.close()
        assert temp_catch_log.closed is True
        with pytest.raises(RuntimeError, match="close"):
            await temp_catch_log.log_catch("cod", 5.0)

    @pytest.mark.asyncio
    async def test_failed_validation_writes_nothing(
        self, temp_catch_log: CatchLog, temp_catch_path: Path
    ) -> None:
        """A rejected log_catch does not append to the file."""
        with pytest.raises(ValueError):
            await temp_catch_log.log_catch("tuna", 10.0)
        assert not temp_catch_path.exists()
        assert temp_catch_log.seq == 0


# =============================================================================
# Integration: complete workflow
# =============================================================================

class TestCatchLogWorkflow:
    """End-to-end: log catches, mirror to OpLog, summarize, export."""

    @pytest.mark.asyncio
    async def test_full_workflow(self, tmp_path: Path) -> None:
        """Log a mixed day of fishing, then summarize and export."""
        oplog = OpLog(tmp_path / "oplog.jsonl")
        async with CatchLog(
            tmp_path / "catch.jsonl", oplog=oplog, crew="captain"
        ) as log:
            await log.log_catch("salmon", 18.0, count=2, method="troll",
                                quality="premium",
                                location={"lat": 58.3, "lon": -136.1})
            await log.log_catch("salmon", 9.5, count=1, method="troll")
            await log.log_catch("crab", 42.0, count=21, method="pot",
                                location="Lynn Canal", depth=55.0)

            summary = log.get_catch_summary()
            assert summary["entries"] == 3
            assert summary["total_count"] == 24
            assert summary["total_weight_lb"] == 69.5
            assert summary["by_species"]["salmon"]["weight_lb"] == 27.5
            assert summary["by_species"]["crab"]["count"] == 21

            csv_content = log.export_to_csv(tmp_path / "catch.csv")
            assert len(list(csv.DictReader(StringIO(csv_content)))) == 3

        oplog_entries = await oplog.query(entry_type="catch_logged")
        assert len(oplog_entries) == 3
        assert all(e["crew"] == "captain" for e in oplog_entries)
