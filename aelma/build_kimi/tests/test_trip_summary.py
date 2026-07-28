"""Tests for TripSummary trip analytics and reporting."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make the repository root importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from build_kimi.twin.trip_summary import (
    AlertSummary,
    CatchStatistics,
    FuelStatistics,
    ModeTimeSummary,
    PositionHistory,
    TripSummary,
    WeatherSummary,
    haversine_m,
)

T0 = 1_753_478_400_000_000_000  # Fixed epoch ns for deterministic tests


# --------------------------------------------------------------------- #
# Utility functions
# --------------------------------------------------------------------- #


class TestHaversine:
    """Test haversine distance calculation."""

    def test_zero_distance_same_point(self):
        """Distance should be zero for same point."""
        dist = haversine_m(47.6, -122.4, 47.6, -122.4)
        assert dist == 0.0

    def test_short_distance(self):
        """Test short distance calculation."""
        # ~1 km apart
        dist = haversine_m(47.6, -122.4, 47.605, -122.41)
        assert 500 < dist < 1500  # Approximately 1km

    def test_long_distance(self):
        """Test long distance calculation."""
        # Seattle to San Francisco (~1100 km)
        dist = haversine_m(47.6, -122.4, 37.7, -122.4)
        assert 1100_000 < dist < 1200_000  # ~1100 km


# --------------------------------------------------------------------- #
# AlertSummary
# --------------------------------------------------------------------- #


class TestAlertSummary:
    """Alert tracking and summarization."""

    def test_initial_state(self):
        """AlertSummary should start empty."""
        summary = AlertSummary()
        assert summary.total_count == 0
        assert summary.by_severity == {}
        assert summary.by_code == {}
        assert summary.highest_priority == 0.0
        assert summary.critical_count == 0
        assert summary.warning_count == 0
        assert summary.info_count == 0

    def test_add_critical_alert(self):
        """Adding critical alert should increment counters."""
        summary = AlertSummary()
        summary.add_alert({
            "action": "raise_alert",
            "payload": {"severity": "critical", "code": "GROUNDING_RISK"},
            "priority": 0.95,
        })
        assert summary.total_count == 1
        assert summary.critical_count == 1
        assert summary.by_severity["critical"] == 1
        assert summary.by_code["GROUNDING_RISK"] == 1
        assert summary.highest_priority == 0.95

    def test_add_multiple_alerts(self):
        """Multiple alerts should aggregate correctly."""
        summary = AlertSummary()
        summary.add_alert({
            "action": "raise_alert",
            "payload": {"severity": "warning", "code": "SHALLOW_WATER"},
            "priority": 0.7,
        })
        summary.add_alert({
            "action": "raise_alert",
            "payload": {"severity": "critical", "code": "GROUNDING_RISK"},
            "priority": 0.95,
        })
        summary.add_alert({
            "action": "raise_alert",
            "payload": {"severity": "warning", "code": "SHALLOW_WATER"},
            "priority": 0.75,
        })

        assert summary.total_count == 3
        assert summary.critical_count == 1
        assert summary.warning_count == 2
        assert summary.by_severity["warning"] == 2
        assert summary.by_code["SHALLOW_WATER"] == 2

    def test_highest_priority_tracking(self):
        """Should track highest priority alert."""
        summary = AlertSummary()
        summary.add_alert({"action": "raise_alert", "payload": {}, "priority": 0.5})
        summary.add_alert({"action": "raise_alert", "payload": {}, "priority": 0.8})
        summary.add_alert({"action": "raise_alert", "payload": {}, "priority": 0.6})

        assert summary.highest_priority == 0.8

    def test_to_dict(self):
        """Should convert to dictionary for JSON serialization."""
        summary = AlertSummary()
        summary.add_alert({
            "action": "raise_alert",
            "payload": {"severity": "critical", "code": "GROUNDING_RISK"},
            "priority": 0.95,
        })

        data = summary.to_dict()
        assert data["total_count"] == 1
        assert data["critical_count"] == 1
        assert data["by_severity"]["critical"] == 1


# --------------------------------------------------------------------- #
# ModeTimeSummary
# --------------------------------------------------------------------- #


class TestModeTimeSummary:
    """Fishing mode time tracking."""

    def test_initial_state(self):
        """ModeTimeSummary should start empty."""
        summary = ModeTimeSummary()
        assert summary.total_duration_ns == 0
        assert summary.mode_durations_ns == {}
        assert summary.mode_entries == {}

    def test_add_mode_duration(self):
        """Should accumulate mode duration."""
        summary = ModeTimeSummary()
        summary.add_mode_duration("TRANSIT", 3_600_000_000_000, 1)  # 1 hour
        summary.add_mode_duration("FISHING", 7_200_000_000_000, 2)  # 2 hours

        assert summary.total_duration_ns == 10_800_000_000_000
        assert summary.mode_durations_ns["TRANSIT"] == 3_600_000_000_000
        assert summary.mode_durations_ns["FISHING"] == 7_200_000_000_000
        assert summary.mode_entries["TRANSIT"] == 1
        assert summary.mode_entries["FISHING"] == 2

    def test_to_dict_conversions(self):
        """Should convert nanoseconds to human-readable units."""
        summary = ModeTimeSummary()
        summary.add_mode_duration("TRANSIT", 3_600_000_000_000, 1)  # 1 hour

        data = summary.to_dict()
        assert data["total_duration_ns"] == 3_600_000_000_000
        assert data["total_duration_s"] == 3600.0
        assert data["total_duration_h"] == 1.0
        assert data["mode_durations_s"]["TRANSIT"] == 3600.0
        assert data["mode_durations_h"]["TRANSIT"] == 1.0

    def test_percentage_calculation(self):
        """Should calculate percentage time in each mode."""
        summary = ModeTimeSummary()
        summary.add_mode_duration("TRANSIT", 3_600_000_000_000, 1)  # 1 hour
        summary.add_mode_duration("FISHING", 3_600_000_000_000, 1)  # 1 hour

        data = summary.to_dict()
        assert data["mode_durations_pct"]["TRANSIT"] == 50.0
        assert data["mode_durations_pct"]["FISHING"] == 50.0


# --------------------------------------------------------------------- #
# CatchStatistics
# --------------------------------------------------------------------- #


class TestCatchStatistics:
    """Catch data tracking."""

    def test_initial_state(self):
        """CatchStatistics should start empty."""
        stats = CatchStatistics()
        assert stats.total_catch_kg == 0.0
        assert stats.species_counts == {}
        assert stats.haul_count == 0

    def test_add_haul(self):
        """Should accumulate catch data."""
        stats = CatchStatistics()
        stats.add_haul("Salmon", 150.0)
        stats.add_haul("Cod", 200.0)
        stats.add_haul("Salmon", 175.0)

        assert stats.haul_count == 3
        assert stats.total_catch_kg == 525.0
        assert stats.species_counts["Salmon"] == 2
        assert stats.species_counts["Cod"] == 1
        assert stats.best_haul_kg == 200.0
        assert stats.avg_haul_kg == 175.0

    def test_to_dict(self):
        """Should convert to dictionary for JSON serialization."""
        stats = CatchStatistics()
        stats.add_haul("Salmon", 150.0)

        data = stats.to_dict()
        assert data["total_catch_kg"] == 150.0
        assert data["haul_count"] == 1
        assert data["species_counts"]["Salmon"] == 1


# --------------------------------------------------------------------- #
# FuelStatistics
# --------------------------------------------------------------------- #


class TestFuelStatistics:
    """Fuel consumption tracking."""

    def test_initial_state(self):
        """FuelStatistics should start empty."""
        stats = FuelStatistics()
        assert stats.total_fuel_l == 0.0
        assert stats.avg_consumption_lh == 0.0
        assert stats.engine_hours == 0.0

    def test_add_fuel_reading(self):
        """Should accumulate fuel consumption."""
        stats = FuelStatistics()
        stats.add_fuel_reading(10.0, 3600)  # 10 L/h for 1 hour
        stats.add_fuel_reading(12.0, 1800)  # 12 L/h for 30 min

        # Fuel calculation: rate * (duration_s / 3600) = rate * hours
        # First: 10.0 * (3600/3600) = 10.0 L
        # Second: 12.0 * (1800/3600) = 6.0 L
        # Total: 16.0 L (not 160.0 as test originally expected)
        assert stats.total_fuel_l == 16.0
        assert stats.engine_hours == 1.5
        assert stats.avg_consumption_lh == pytest.approx(10.67, 0.1)
        assert stats.max_consumption_lh == 12.0

    def test_to_dict(self):
        """Should convert to dictionary for JSON serialization."""
        stats = FuelStatistics()
        stats.add_fuel_reading(10.0, 3600)

        data = stats.to_dict()
        assert data["total_fuel_l"] == 10.0
        assert data["engine_hours"] == 1.0


# --------------------------------------------------------------------- #
# WeatherSummary
# --------------------------------------------------------------------- #


class TestWeatherSummary:
    """Weather condition tracking."""

    def test_initial_state(self):
        """WeatherSummary should start empty."""
        summary = WeatherSummary()
        assert summary.min_wind_speed_kn is None
        assert summary.max_wind_speed_kn is None
        assert summary.wind_readings == 0

    def test_add_wind_reading(self):
        """Should track wind statistics."""
        summary = WeatherSummary()
        summary.add_wind_reading(10.0)
        summary.add_wind_reading(15.0)
        summary.add_wind_reading(12.0)

        assert summary.wind_readings == 3
        assert summary.min_wind_speed_kn == 10.0
        assert summary.max_wind_speed_kn == 15.0
        assert summary.avg_wind_speed_kn == pytest.approx(12.33, 0.1)

    def test_add_wave_reading(self):
        """Should track wave statistics."""
        summary = WeatherSummary()
        summary.add_wave_reading(1.5)
        summary.add_wave_reading(2.0)
        summary.add_wave_reading(1.8)

        assert summary.wave_readings == 3
        assert summary.min_wave_height_m == 1.5
        assert summary.max_wave_height_m == 2.0
        assert summary.avg_wave_height_m == pytest.approx(1.77, 0.1)

    def test_to_dict(self):
        """Should convert to dictionary for JSON serialization."""
        summary = WeatherSummary()
        summary.add_wind_reading(15.0)
        summary.add_wave_reading(2.0)

        data = summary.to_dict()
        assert data["wind_speed_kn"]["avg"] == 15.0
        assert data["wave_height_m"]["avg"] == 2.0


# --------------------------------------------------------------------- #
# PositionHistory
# --------------------------------------------------------------------- #


class TestPositionHistory:
    """Position tracking and distance calculation."""

    def test_initial_state(self):
        """PositionHistory should start empty."""
        history = PositionHistory()
        assert history.total_distance_m == 0.0
        assert history.position_count == 0

    def test_add_first_position(self):
        """First position should initialize without distance."""
        history = PositionHistory()
        history.add_position(T0, 47.6, -122.4)

        assert history.total_distance_m == 0.0
        assert len(history.positions) == 1

    def test_add_second_position(self):
        """Second position should calculate distance."""
        history = PositionHistory()
        history.add_position(T0, 47.6, -122.4)
        history.add_position(T0 + 60_000_000_000, 47.605, -122.405)  # 1 min later

        assert history.total_distance_m > 0
        assert len(history.positions) == 2

    def test_distance_accumulation(self):
        """Distance should accumulate across multiple fixes."""
        history = PositionHistory()
        history.add_position(T0, 47.6, -122.4)
        history.add_position(T0 + 60_000_000_000, 47.605, -122.405)
        history.add_position(T0 + 120_000_000_000, 47.61, -122.41)

        assert history.total_distance_m > 0
        assert len(history.positions) == 3

    def test_duplicate_position_handling(self):
        """Should handle duplicate positions/timestamps."""
        history = PositionHistory()
        history.add_position(T0, 47.6, -122.4)
        history.add_position(T0, 47.6, -122.4)  # Duplicate

        assert len(history.positions) == 1
        assert history.total_distance_m == 0.0

    def test_to_dict(self):
        """Should convert to dictionary with unit conversions."""
        history = PositionHistory()
        history.add_position(T0, 47.6, -122.4)
        history.add_position(T0 + 60_000_000_000, 47.7, -122.5)  # ~15 km

        data = history.to_dict()
        assert data["total_distance_m"] > 0
        assert data["total_distance_km"] > 0
        assert data["total_distance_nm"] > 0
        assert data["position_count"] == 2


# --------------------------------------------------------------------- #
# TripSummary main class
# --------------------------------------------------------------------- #


class TestTripSummaryInit:
    """TripSummary initialization and basic state."""

    def test_init_with_vessel_id(self):
        """Should initialize with vessel ID."""
        summary = TripSummary(vessel_id="US-AK-FVEILEEN-51")
        assert summary.vessel_id == "US-AK-FVEILEEN-51"
        assert not summary.has_data

    def test_init_default_vessel_id(self):
        """Should use 'unknown' as default vessel ID."""
        summary = TripSummary()
        assert summary.vessel_id == "unknown"


class TestTripSummaryTelemetry:
    """Telemetry data accumulation."""

    def test_add_depth_reading(self):
        """Should accumulate depth readings."""
        summary = TripSummary()
        summary.add_telemetry({
            "timestamp_ns": T0,
            "channel": "depth_m",
            "value": 73.2,
        })

        assert len(summary.depth_readings) == 1
        assert summary.depth_readings[0] == 73.2
        assert summary.has_data

    def test_ignore_invalid_depth(self):
        """Should ignore None or non-positive depths."""
        summary = TripSummary()
        summary.add_telemetry({
            "timestamp_ns": T0,
            "channel": "depth_m",
            "value": None,
        })
        summary.add_telemetry({
            "timestamp_ns": T0 + 1,
            "channel": "depth_m",
            "value": -5.0,
        })

        assert len(summary.depth_readings) == 0

    def test_track_timestamps(self):
        """Should track start and end timestamps."""
        summary = TripSummary()
        summary.add_telemetry({"timestamp_ns": T0, "channel": "depth_m", "value": 10.0})
        summary.add_telemetry({"timestamp_ns": T0 + 100, "channel": "depth_m", "value": 20.0})
        summary.add_telemetry({"timestamp_ns": T0 - 50, "channel": "depth_m", "value": 15.0})

        assert summary.start_timestamp_ns == T0 - 50
        assert summary.end_timestamp_ns == T0 + 100

    def test_position_pairing(self):
        """Should pair lat/lon with same timestamp."""
        summary = TripSummary()
        summary.add_telemetry({"timestamp_ns": T0, "channel": "position.lat", "value": 47.6})
        summary.add_telemetry({"timestamp_ns": T0, "channel": "position.lon", "value": -122.4})

        assert len(summary.position_history.positions) == 1
        assert summary.position_history.positions[0] == (T0, 47.6, -122.4)

    def test_split_position_fix(self):
        """Should not pair lat/lon with different timestamps."""
        summary = TripSummary()
        summary.add_telemetry({"timestamp_ns": T0, "channel": "position.lat", "value": 47.6})
        summary.add_telemetry({"timestamp_ns": T0 + 10, "channel": "position.lon", "value": -122.4})

        assert len(summary.position_history.positions) == 0

    def test_weather_telemetry(self):
        """Should accumulate weather data."""
        summary = TripSummary()
        summary.add_telemetry({"timestamp_ns": T0, "channel": "wind_speed_kn", "value": 15.0})
        summary.add_telemetry({"timestamp_ns": T0, "channel": "wave_height_m", "value": 2.0})

        assert summary.weather.wind_readings == 1
        assert summary.weather.wave_readings == 1
        assert summary.weather.max_wind_speed_kn == 15.0

    def test_fuel_telemetry(self):
        """Should accumulate fuel data."""
        summary = TripSummary()
        summary.add_telemetry({"timestamp_ns": T0, "channel": "engine_fuel_rate_lh", "value": 10.0})

        assert summary.fuel.total_fuel_l > 0
        assert summary.fuel.engine_hours > 0

    def test_telemetry_record_object(self):
        """Should accept TelemetryRecord-like objects."""
        from build_kimi.twin.telemetry_query import TelemetryRecord

        summary = TripSummary()
        record = TelemetryRecord(
            timestamp_ns=T0,
            source="nmea0183",
            channel="depth_m",
            value=73.2,
        )
        summary.add_telemetry(record)

        assert len(summary.depth_readings) == 1
        assert summary.depth_readings[0] == 73.2


class TestTripSummaryOpLog:
    """Crew operation log tracking."""

    def test_add_oplog_entry(self):
        """Should add oplog entry."""
        summary = TripSummary()
        entry = {
            "action": "start_fishing",
            "timestamp_ns": T0,
            "crew_member": "captain",
        }
        summary.add_oplog_entry(entry)

        assert len(summary.oplog_entries) == 1
        assert summary.oplog_entries[0] == entry
        assert summary.has_data

    def test_extract_catch_data(self):
        """Should extract catch data from log_catch entries."""
        summary = TripSummary()
        summary.add_oplog_entry({
            "action": "log_catch",
            "timestamp_ns": T0,
            "species": "Salmon",
            "weight_kg": 150.0,
        })
        summary.add_oplog_entry({
            "action": "log_catch",
            "timestamp_ns": T0 + 1,
            "species": "Cod",
            "weight_kg": 200.0,
        })

        assert summary.catch.haul_count == 2
        assert summary.catch.total_catch_kg == 350.0
        assert summary.catch.species_counts["Salmon"] == 1


class TestTripSummaryA2A:
    """Automated A2A action tracking."""

    def test_add_a2a_action(self):
        """Should add A2A action."""
        summary = TripSummary()
        action = {
            "action": "raise_alert",
            "priority": 0.8,
            "payload": {"severity": "warning"},
        }
        summary.add_a2a_action(action)

        assert len(summary.a2a_actions) == 1
        assert summary.a2a_actions[0] == action
        assert summary.has_data

    def test_track_alerts_from_a2a(self):
        """Should track alerts from A2A actions."""
        summary = TripSummary()
        summary.add_a2a_action({
            "action": "raise_alert",
            "priority": 0.95,
            "payload": {
                "severity": "critical",
                "code": "GROUNDING_RISK",
            },
        })

        assert summary.alerts.total_count == 1
        assert summary.alerts.critical_count == 1
        assert summary.alerts.by_code["GROUNDING_RISK"] == 1


class TestTripSummaryModeTime:
    """Fishing mode time tracking."""

    def test_add_mode_duration(self):
        """Should add mode duration."""
        summary = TripSummary()
        summary.add_mode_duration("TRANSIT", 3_600_000_000_000)  # 1 hour
        summary.add_mode_duration("FISHING", 7_200_000_000_000)  # 2 hours

        assert summary.mode_time.total_duration_ns == 10_800_000_000_000
        assert summary.mode_time.mode_durations_ns["TRANSIT"] == 3_600_000_000_000
        assert summary.has_data

    def test_multiple_mode_entries(self):
        """Should track number of entries into each mode."""
        summary = TripSummary()
        summary.add_mode_duration("TRANSIT", 3_600_000_000_000, 3)

        assert summary.mode_time.mode_entries["TRANSIT"] == 3


class TestTripSummaryGeneration:
    """Summary generation and formatting."""

    def test_generate_summary_structure(self):
        """Should generate summary with all sections."""
        summary = TripSummary(vessel_id="TEST-VESSEL")
        summary.add_telemetry({"timestamp_ns": T0, "channel": "depth_m", "value": 73.2})
        summary.add_telemetry({"timestamp_ns": T0, "channel": "position.lat", "value": 47.6})
        summary.add_telemetry({"timestamp_ns": T0, "channel": "position.lon", "value": -122.4})

        result = summary.generate_summary()

        assert result["vessel_id"] == "TEST-VESSEL"
        assert "trip" in result
        assert "distance" in result
        assert "depth" in result
        assert "fishing_modes" in result
        assert "alerts" in result
        assert "catch" in result
        assert "fuel" in result
        assert "weather" in result
        assert "crew_actions" in result
        assert "automated_actions" in result
        assert "data_quality" in result

    def test_trip_duration_calculation(self):
        """Should calculate trip duration."""
        summary = TripSummary()
        summary.add_telemetry({"timestamp_ns": T0, "channel": "depth_m", "value": 10.0})
        summary.add_telemetry({"timestamp_ns": T0 + 3_600_000_000_000, "channel": "depth_m", "value": 20.0})

        result = summary.generate_summary()
        assert result["trip"]["duration_ns"] == 3_600_000_000_000
        assert result["trip"]["duration_s"] == 3600.0
        assert result["trip"]["duration_h"] == 1.0

    def test_depth_statistics(self):
        """Should calculate depth statistics."""
        summary = TripSummary()
        summary.add_telemetry({"timestamp_ns": T0, "channel": "depth_m", "value": 70.0})
        summary.add_telemetry({"timestamp_ns": T0 + 1, "channel": "depth_m", "value": 75.0})
        summary.add_telemetry({"timestamp_ns": T0 + 2, "channel": "depth_m", "value": 72.0})

        result = summary.generate_summary()
        depth = result["depth"]
        assert depth["min_m"] == 70.0
        assert depth["max_m"] == 75.0
        assert depth["avg_m"] == pytest.approx(72.33, 0.1)
        assert depth["reading_count"] == 3

    def test_empty_summary(self):
        """Should handle summary with no data."""
        summary = TripSummary()
        result = summary.generate_summary()

        assert result["trip"]["duration_ns"] == 0
        assert result["depth"]["reading_count"] == 0
        assert result["distance"]["total_distance_m"] == 0.0


class TestTripSummaryExport:
    """Export functionality."""

    def test_export_json(self, tmp_path):
        """Should export summary as JSON."""
        summary = TripSummary(vessel_id="TEST-VESSEL")
        summary.add_telemetry({"timestamp_ns": T0, "channel": "depth_m", "value": 73.2})

        output_path = tmp_path / "summary.json"
        summary.export_json(output_path)

        assert output_path.exists()

        with open(output_path) as f:
            data = json.load(f)

        assert data["vessel_id"] == "TEST-VESSEL"
        assert data["depth"]["reading_count"] == 1

    def test_export_html(self, tmp_path):
        """Should export summary as HTML."""
        summary = TripSummary(vessel_id="TEST-VESSEL")
        summary.add_telemetry({"timestamp_ns": T0, "channel": "depth_m", "value": 73.2})

        output_path = tmp_path / "summary.html"
        summary.export_html(output_path)

        assert output_path.exists()

        with open(output_path) as f:
            html = f.read()

        assert "<html>" in html
        assert "TEST-VESSEL" in html
        assert "73.2" in html

    def test_export_text(self, tmp_path):
        """Should export summary as plain text."""
        summary = TripSummary(vessel_id="TEST-VESSEL")
        summary.add_telemetry({"timestamp_ns": T0, "channel": "depth_m", "value": 73.2})

        output_path = tmp_path / "summary.txt"
        summary.export_text(output_path)

        assert output_path.exists()

        with open(output_path) as f:
            text = f.read()

        assert "TEST-VESSEL" in text
        assert "73.2" in text

    def test_export_creates_directories(self, tmp_path):
        """Should create parent directories if needed."""
        summary = TripSummary()
        output_path = tmp_path / "subdir" / "summary.json"
        summary.export_json(output_path)

        assert output_path.exists()


# --------------------------------------------------------------------- #
# Integration tests
# --------------------------------------------------------------------- #


class TestTripSummaryIntegration:
    """Integration tests with realistic data."""

    def test_complete_fishing_trip(self):
        """Simulate a complete fishing trip with all data types."""
        summary = TripSummary(vessel_id="FV-EXAMPLE-01")

        # Transit phase (1 hour in nanoseconds)
        hour_ns = 3_600_000_000_000
        summary.add_mode_duration("TRANSIT", hour_ns, 1)
        summary.add_telemetry({"timestamp_ns": T0, "channel": "position.lat", "value": 47.6})
        summary.add_telemetry({"timestamp_ns": T0, "channel": "position.lon", "value": -122.4})
        summary.add_telemetry({"timestamp_ns": T0 + 600_000_000_000, "channel": "depth_m", "value": 100.0})

        # Fishing phase (4 hours in nanoseconds)
        four_hours_ns = 14_400_000_000_000
        summary.add_mode_duration("FISHING", four_hours_ns, 1)
        # Add telemetry at the end of the fishing phase
        fishing_end = T0 + hour_ns + four_hours_ns
        summary.add_telemetry({"timestamp_ns": fishing_end, "channel": "position.lat", "value": 47.7})
        summary.add_telemetry({"timestamp_ns": fishing_end, "channel": "position.lon", "value": -122.5})
        summary.add_telemetry({"timestamp_ns": T0 + 4_000_000_000_000, "channel": "depth_m", "value": 73.2})
        summary.add_telemetry({"timestamp_ns": T0 + 5_000_000_000_000, "channel": "depth_m", "value": 75.0})

        # Catch logging
        summary.add_oplog_entry({
            "action": "log_catch",
            "timestamp_ns": T0 + 5_000_000_000_000,
            "species": "Salmon",
            "weight_kg": 150.0,
        })
        summary.add_oplog_entry({
            "action": "log_catch",
            "timestamp_ns": T0 + 10_000_000_000_000,
            "species": "Cod",
            "weight_kg": 200.0,
        })

        # Alerts
        summary.add_a2a_action({
            "action": "raise_alert",
            "priority": 0.7,
            "payload": {"severity": "warning", "code": "SHALLOW_WATER"},
        })

        # Weather
        summary.add_telemetry({"timestamp_ns": T0 + 3_600_000_000_000, "channel": "wind_speed_kn", "value": 15.0})
        summary.add_telemetry({"timestamp_ns": T0 + 3_600_000_000_000, "channel": "wave_height_m", "value": 2.0})

        # Fuel
        summary.add_telemetry({"timestamp_ns": T0 + 3_600_000_000_000, "channel": "engine_fuel_rate_lh", "value": 10.0})

        # Generate summary
        result = summary.generate_summary()

        # Verify all data accumulated
        assert result["vessel_id"] == "FV-EXAMPLE-01"
        # Trip duration is from first to last telemetry timestamp
        # First: T0, Last: fishing_end = T0 + hour_ns + four_hours_ns = T0 + 5 hours
        expected_duration_h = 5.0
        assert result["trip"]["duration_h"] == pytest.approx(expected_duration_h, 0.1)
        assert result["distance"]["total_distance_m"] > 0
        assert result["depth"]["reading_count"] == 3
        assert result["catch"]["haul_count"] == 2
        assert result["catch"]["total_catch_kg"] == 350.0
        assert result["alerts"]["total_count"] == 1
        assert result["weather"]["wind_speed_kn"]["max"] == 15.0
        assert result["fuel"]["engine_hours"] > 0
        # Verify mode durations are accumulated correctly
        assert result["fishing_modes"]["mode_durations_h"]["TRANSIT"] == pytest.approx(1.0, 0.1)
        assert result["fishing_modes"]["mode_durations_h"]["FISHING"] == pytest.approx(4.0, 0.1)

    def test_export_all_formats(self, tmp_path):
        """Should export to all formats successfully."""
        summary = TripSummary(vessel_id="FV-EXPORT-TEST")
        summary.add_telemetry({"timestamp_ns": T0, "channel": "depth_m", "value": 73.2})

        summary.export_json(tmp_path / "summary.json")
        summary.export_html(tmp_path / "summary.html")
        summary.export_text(tmp_path / "summary.txt")

        assert (tmp_path / "summary.json").exists()
        assert (tmp_path / "summary.html").exists()
        assert (tmp_path / "summary.txt").exists()
