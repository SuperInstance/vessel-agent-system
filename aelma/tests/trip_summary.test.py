"""Tests for the AELMA trip summary generator (twin.trip_summary).

Coverage:

  1. Telemetry ingestion — position fixes, distance, depth extremes, window.
  2. OpLog ingestion — fishing time pairing, crew action grouping, catch stats.
  3. A2A ingestion — alert counting by kind, action/source breakdowns.
  4. generate_summary — aggregate structure and unit conversions.
  5. Exports — JSON round-trip, HTML escaping, text sections, file export.
  6. Error handling — malformed inputs rejected or ignored safely.

Run from the repo root: python -m pytest tests/trip_summary.test.py -v
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Make the repository root importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twin.state import haversine_m  # noqa: E402
from twin.trip_summary import TripSummary  # noqa: E402


# =============================================================================
# Helpers / fixtures
# =============================================================================

BASE = datetime(2026, 7, 28, 10, 0, 0, tzinfo=timezone.utc)


def ts_ns(seconds: float) -> int:
    """Epoch nanoseconds, ``seconds`` after BASE."""
    return int((BASE + timedelta(seconds=seconds)).timestamp() * 1e9)


def iso(seconds: float) -> str:
    """ISO timestamp, ``seconds`` after BASE."""
    return (BASE + timedelta(seconds=seconds)).isoformat()


def packet(channel: str, value, seconds: float) -> dict:
    return {
        "timestamp_ns": ts_ns(seconds),
        "source": "simulator",
        "channel": channel,
        "value": value,
        "quality": "good",
    }


def fix(summary: TripSummary, lat: float, lon: float, seconds: float) -> None:
    """Feed a lat/lon packet pair (same timestamp, as the bridge emits)."""
    summary.add_telemetry(packet("position.lat", lat, seconds))
    summary.add_telemetry(packet("position.lon", lon, seconds))


def oplog(entry_type: str, seconds: float, crew: str = "captain",
          message: str = "", metadata: dict | None = None) -> dict:
    return {
        "kind": "oplog_entry",
        "entry_type": entry_type,
        "crew": crew,
        "message": message,
        "metadata": metadata or {},
        "ts": iso(seconds),
    }


def a2a(action: str, seconds: float, payload: dict | None = None,
        source: str = "watcher", reason: str = "") -> dict:
    return {
        "kind": "action",
        "action": action,
        "payload": payload or {},
        "source": source,
        "reason": reason,
        "priority": 0.85,
        "ts": iso(seconds),
    }


@pytest.fixture
def summary() -> TripSummary:
    return TripSummary(vessel_id="TEST-VESSEL-1")


# =============================================================================
# 1. Telemetry ingestion
# =============================================================================

class TestTelemetry:
    def test_distance_accumulates_over_fixes(self, summary: TripSummary) -> None:
        fix(summary, 59.5, -152.3, 0)
        fix(summary, 59.51, -152.3, 60)
        fix(summary, 59.52, -152.3, 120)
        result = summary.generate_summary()
        expected_m = haversine_m(59.5, -152.3, 59.51, -152.3) + haversine_m(
            59.51, -152.3, 59.52, -152.3
        )
        assert result["distance"]["m"] == pytest.approx(expected_m, rel=1e-6)
        assert result["distance"]["nm"] == pytest.approx(expected_m / 1852.0, abs=1e-3)
        assert result["distance"]["km"] == pytest.approx(expected_m / 1000.0, abs=1e-3)
        assert result["distance"]["position_fixes"] == 3

    def test_single_fix_gives_zero_distance(self, summary: TripSummary) -> None:
        fix(summary, 59.5, -152.3, 0)
        assert summary.generate_summary()["distance"]["m"] == 0.0

    def test_unpaired_position_component_ignored(self, summary: TripSummary) -> None:
        summary.add_telemetry(packet("position.lat", 59.5, 0))
        summary.add_telemetry(packet("position.lon", -152.3, 5))  # different ts
        assert summary.generate_summary()["distance"]["position_fixes"] == 0

    def test_depth_extremes(self, summary: TripSummary) -> None:
        summary.add_telemetry(packet("depth_m", 42.0, 0))
        summary.add_telemetry(packet("depth_m", 87.5, 10))
        summary.add_telemetry(packet("depth_m", 12.25, 20))
        depth = summary.generate_summary()["depth"]
        assert depth["max_m"] == 87.5
        assert depth["min_m"] == 12.25
        assert depth["samples"] == 3

    def test_no_depth_gives_none(self, summary: TripSummary) -> None:
        depth = summary.generate_summary()["depth"]
        assert depth["max_m"] is None
        assert depth["min_m"] is None
        assert depth["samples"] == 0

    def test_non_numeric_values_ignored_but_extend_window(
        self, summary: TripSummary
    ) -> None:
        summary.add_telemetry(packet("depth_m", None, 0))
        summary.add_telemetry(packet("tide_state", "rising", 600))
        result = summary.generate_summary()
        assert result["depth"]["samples"] == 0
        assert result["trip_window"]["duration_s"] == pytest.approx(600.0)

    def test_unrelated_channels_do_not_affect_distance(self, summary: TripSummary) -> None:
        fix(summary, 59.5, -152.3, 0)
        fix(summary, 59.51, -152.3, 60)
        summary.add_telemetry(packet("wind_kts", 18.0, 30))
        result = summary.generate_summary()
        assert result["distance"]["position_fixes"] == 2


# =============================================================================
# 2. OpLog ingestion
# =============================================================================

class TestOpLog:
    def test_fishing_time_pairs_gear_events(self, summary: TripSummary) -> None:
        summary.add_oplog_entry(oplog("gear_deployed", 100))
        summary.add_oplog_entry(oplog("gear_retrieved", 400))
        summary.add_oplog_entry(oplog("gear_deployed", 600))
        summary.add_oplog_entry(oplog("gear_retrieved", 900))
        fishing = summary.generate_summary()["fishing"]
        assert fishing["time_s"] == pytest.approx(300.0 + 300.0)
        assert fishing["basis"] == "gear_in_water"
        assert fishing["gear_deployments"] == 2

    def test_unmatched_deployment_runs_to_trip_end(self, summary: TripSummary) -> None:
        summary.add_oplog_entry(oplog("gear_deployed", 100))
        summary.add_telemetry(packet("wind_kts", 10.0, 1100))  # trip end
        fishing = summary.generate_summary()["fishing"]
        assert fishing["time_s"] == pytest.approx(1000.0)

    def test_haul_fallback_when_no_gear_events(self, summary: TripSummary) -> None:
        summary.add_oplog_entry(oplog("haul_started", 200))
        summary.add_oplog_entry(oplog("haul_complete", 500))
        fishing = summary.generate_summary()["fishing"]
        assert fishing["time_s"] == pytest.approx(300.0)
        assert fishing["basis"] == "hauls"
        assert fishing["hauls_completed"] == 1

    def test_no_fishing_events(self, summary: TripSummary) -> None:
        fishing = summary.generate_summary()["fishing"]
        assert fishing["time_s"] == 0.0
        assert fishing["basis"] == "none"

    def test_crew_actions_grouped_by_type(self, summary: TripSummary) -> None:
        summary.add_oplog_entry(oplog("anchor_drop", 10))
        summary.add_oplog_entry(oplog("crew_note", 20, message="Seal on deck"))
        summary.add_oplog_entry(oplog("crew_note", 30, message="Seal left"))
        summary.add_oplog_entry(oplog("anchor_raise", 40))
        crew = summary.generate_summary()["crew_actions"]
        assert crew["total"] == 4
        assert crew["by_type"] == {"anchor_drop": 1, "anchor_raise": 1, "crew_note": 2}
        assert crew["entries"][1]["message"] == "Seal on deck"

    def test_catch_statistics_by_species(self, summary: TripSummary) -> None:
        summary.add_oplog_entry(oplog(
            "catch_logged", 100,
            metadata={"species": "pacific_cod", "count": 12, "weight_kg": 34.5},
        ))
        summary.add_oplog_entry(oplog(
            "catch_logged", 200,
            metadata={"species": "pacific_cod", "count": 8, "weight_kg": 21.0},
        ))
        summary.add_oplog_entry(oplog(
            "catch_logged", 300,
            metadata={"species": "halibut", "count": 2, "weight_kg": 40.25},
        ))
        catch = summary.generate_summary()["catch"]
        assert catch["entries"] == 3
        assert catch["total_count"] == 22
        assert catch["total_weight_kg"] == pytest.approx(95.75)
        assert catch["by_species"]["pacific_cod"] == {"count": 20, "weight_kg": 55.5}
        assert catch["by_species"]["halibut"]["weight_kg"] == 40.25

    def test_catch_with_missing_metadata_fields(self, summary: TripSummary) -> None:
        summary.add_oplog_entry(oplog("catch_logged", 100, metadata={}))
        catch = summary.generate_summary()["catch"]
        assert catch["entries"] == 1
        assert catch["total_count"] == 0
        assert "unknown" in catch["by_species"]


# =============================================================================
# 3. A2A ingestion
# =============================================================================

class TestA2A:
    def test_alerts_counted_by_kind(self, summary: TripSummary) -> None:
        summary.add_a2a_action(a2a("raise_alert", 10, {"kind": "shallow_water"},
                                   reason="depth=1.40m"))
        summary.add_a2a_action(a2a("raise_alert", 20, {"kind": "shallow_water"},
                                   reason="depth=1.10m"))
        summary.add_a2a_action(a2a("raise_alert", 30, {"kind": "traffic"},
                                   source="llm", reason="AIS contact"))
        alerts = summary.generate_summary()["alerts"]
        assert alerts["total"] == 3
        assert alerts["by_kind"] == {"shallow_water": 2, "traffic": 1}
        assert alerts["entries"][0]["reason"] == "depth=1.40m"
        assert alerts["entries"][2]["source"] == "llm"

    def test_non_alert_actions_not_counted_as_alerts(self, summary: TripSummary) -> None:
        summary.add_a2a_action(a2a("morph_mode", 10, {"mode": "transit"}))
        summary.add_a2a_action(a2a("announce", 20, source="crew"))
        result = summary.generate_summary()
        assert result["alerts"]["total"] == 0
        assert result["a2a_actions"]["total"] == 2
        assert result["a2a_actions"]["by_action"] == {"announce": 1, "morph_mode": 1}
        assert result["a2a_actions"]["by_source"] == {"crew": 1, "watcher": 1}

    def test_empty_logs(self, summary: TripSummary) -> None:
        result = summary.generate_summary()
        assert result["alerts"]["total"] == 0
        assert result["a2a_actions"]["total"] == 0
        assert result["crew_actions"]["total"] == 0


# =============================================================================
# 4. generate_summary aggregate
# =============================================================================

class TestGenerateSummary:
    def test_full_structure_and_window(self, summary: TripSummary) -> None:
        fix(summary, 59.5, -152.3, 0)
        fix(summary, 59.6, -152.4, 3600)
        summary.add_telemetry(packet("depth_m", 55.0, 1800))
        summary.add_oplog_entry(oplog("gear_deployed", 100))
        summary.add_oplog_entry(oplog("gear_retrieved", 3400))
        summary.add_a2a_action(a2a("raise_alert", 2000, {"kind": "shallow_water"}))
        result = summary.generate_summary()

        assert result["vessel_id"] == "TEST-VESSEL-1"
        assert set(result) == {
            "vessel_id", "generated_at", "trip_window", "distance", "depth",
            "fishing", "alerts", "a2a_actions", "crew_actions", "catch",
        }
        window = result["trip_window"]
        assert window["start"] == BASE.isoformat()
        assert window["end"] == (BASE + timedelta(seconds=3600)).isoformat()
        assert window["duration_s"] == pytest.approx(3600.0)
        assert result["fishing"]["time_s"] == pytest.approx(3300.0)

    def test_empty_summary_is_safe(self, summary: TripSummary) -> None:
        result = summary.generate_summary()
        assert result["trip_window"]["start"] is None
        assert result["trip_window"]["duration_s"] == 0.0
        assert result["distance"]["nm"] == 0.0

    def test_summary_is_json_serializable(self, summary: TripSummary) -> None:
        fix(summary, 59.5, -152.3, 0)
        summary.add_oplog_entry(oplog("crew_note", 10))
        json.dumps(summary.generate_summary())


# =============================================================================
# 5. Exports
# =============================================================================

@pytest.fixture
def populated(summary: TripSummary) -> TripSummary:
    fix(summary, 59.5, -152.3, 0)
    fix(summary, 59.51, -152.31, 1800)
    summary.add_telemetry(packet("depth_m", 73.2, 900))
    summary.add_oplog_entry(oplog("gear_deployed", 100, message="Pots in"))
    summary.add_oplog_entry(oplog(
        "catch_logged", 1500, crew="deckhand",
        metadata={"species": "cod", "count": 5, "weight_kg": 12.0},
    ))
    summary.add_oplog_entry(oplog("gear_retrieved", 1700, message="Pots out"))
    summary.add_a2a_action(a2a("raise_alert", 800, {"kind": "shallow_water"},
                               reason="depth=2.10m"))
    return summary


class TestExports:
    def test_export_json_round_trip(self, populated: TripSummary) -> None:
        data = json.loads(populated.export_json())
        assert data["vessel_id"] == "TEST-VESSEL-1"
        assert data["alerts"]["total"] == 1
        assert data["catch"]["by_species"]["cod"]["count"] == 5

    def test_export_text_sections(self, populated: TripSummary) -> None:
        text = populated.export_text()
        for section in (
            "AELMA TRIP SUMMARY REPORT", "NAVIGATION", "FISHING",
            "CATCH", "ALERTS", "CREW ACTIONS", "A2A ACTIONS",
        ):
            assert section in text
        assert "TEST-VESSEL-1" in text
        assert "shallow_water" in text
        assert "cod: 5 fish, 12 kg" in text

    def test_export_html_structure_and_escaping(self, summary: TripSummary) -> None:
        summary.add_oplog_entry(oplog(
            "crew_note", 10, message="Saw <b>whale</b> & calf"))
        page = summary.export_html()
        assert page.startswith("<!DOCTYPE html>")
        assert "<table>" in page
        assert "Saw &lt;b&gt;whale&lt;/b&gt; &amp; calf" in page
        assert "<b>whale</b>" not in page

    def test_export_writes_files_and_infers_format(
        self, populated: TripSummary, tmp_path: Path
    ) -> None:
        for name, marker in (
            ("report.json", '"vessel_id"'),
            ("report.html", "<!DOCTYPE html>"),
            ("report.txt", "AELMA TRIP SUMMARY REPORT"),
        ):
            target = tmp_path / name
            content = populated.export(str(target))
            assert target.read_text(encoding="utf-8") == content
            assert marker in content

    def test_export_explicit_format_and_bad_format(
        self, populated: TripSummary, tmp_path: Path
    ) -> None:
        target = tmp_path / "report.dat"
        populated.export(str(target), fmt="text")
        assert "TRIP SUMMARY" in target.read_text(encoding="utf-8")
        with pytest.raises(ValueError, match="unknown format"):
            populated.export(str(target), fmt="pdf")


# =============================================================================
# 6. Error handling
# =============================================================================

class TestErrors:
    def test_non_mapping_inputs_rejected(self, summary: TripSummary) -> None:
        with pytest.raises(TypeError):
            summary.add_telemetry("not a packet")
        with pytest.raises(TypeError):
            summary.add_oplog_entry(42)
        with pytest.raises(TypeError):
            summary.add_a2a_action(["raise_alert"])

    def test_malformed_timestamps_ignored(self, summary: TripSummary) -> None:
        summary.add_telemetry({
            "timestamp_ns": "garbage", "source": "simulator",
            "channel": "depth_m", "value": 10.0,
        })
        summary.add_oplog_entry({"entry_type": "crew_note", "ts": "not-a-date"})
        summary.add_a2a_action({"action": "raise_alert", "ts": object()})
        result = summary.generate_summary()
        assert result["depth"]["samples"] == 0
        assert result["trip_window"]["start"] is None
        # Records still counted; only their timestamps are unusable.
        assert result["crew_actions"]["total"] == 1
        assert result["alerts"]["total"] == 1

    def test_default_vessel_id(self) -> None:
        assert TripSummary().generate_summary()["vessel_id"] == "US-AK-FVEILEEN-51"
