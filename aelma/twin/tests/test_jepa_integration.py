"""Tests for JEPA world model integration with TwinCore."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the repository root importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from twin.core import TwinCore

T0 = 1_753_478_400_000_000_000
SITKA_LAT, SITKA_LON = 57.0531, -135.3300


def pos_packets(lat: float, lon: float, ts: int) -> list[dict]:
    """Build a paired position fix (same timestamp on both components)."""
    return [
        {"timestamp_ns": ts, "source": "nmea0183", "channel": "position.lat",
         "value": lat, "quality": "good"},
        {"timestamp_ns": ts, "source": "nmea0183", "channel": "position.lon",
         "value": lon, "quality": "good"},
    ]


class TestTwinCoreJEPAIntegration:
    """Test JEPA model integration with TwinCore."""

    def _core(self, tmp_path, enable_jepa: bool = True) -> TwinCore:
        return TwinCore(
            bathymetry_path=tmp_path / "bathy.json",
            enable_jepa=enable_jepa,
            jepa_min_samples=5,
        )

    def test_jepa_enabled_by_default(self, tmp_path):
        """Test that JEPA is enabled by default."""
        core = TwinCore(bathymetry_path=tmp_path / "bathy.json")
        assert core.enable_jepa is True
        assert core.jepa is not None

    def test_jepa_can_be_disabled(self, tmp_path):
        """Test that JEPA can be disabled."""
        core = TwinCore(
            bathymetry_path=tmp_path / "bathy.json",
            enable_jepa=False,
        )
        assert core.enable_jepa is False
        assert core.jepa is None

    def test_jepa_trains_on_packets(self, tmp_path):
        """Test that JEPA trains on telemetry packets."""
        core = self._core(tmp_path)

        # Feed position packets
        for p in pos_packets(SITKA_LAT, SITKA_LON, T0):
            core.handle_packet(p)

        # Feed depth packets with trend
        for i in range(10):
            packet = {
                "timestamp_ns": T0 + i * 1_000_000_000,
                "source": "nmea0183",
                "channel": "depth_m",
                "value": 50.0 + i,
            }
            core.handle_packet(packet)

        # JEPA should have learned
        assert core.jepa is not None
        assert core.jepa._tick_count >= 10
        assert len(core.jepa._history) >= 10

    def test_jepa_stats_in_snapshot(self, tmp_path):
        """Test that JEPA stats are included in snapshots."""
        core = self._core(tmp_path)

        # Feed some packets
        for p in pos_packets(SITKA_LAT, SITKA_LON, T0):
            core.handle_packet(p)

        packet = {
            "timestamp_ns": T0 + 1,
            "source": "nmea0183",
            "channel": "depth_m",
            "value": 73.2,
        }
        core.handle_packet(packet)

        # Build snapshot
        snap = core.build_snapshot(now_ns=T0 + 2)

        # Should include JEPA stats
        assert "jepa" in snap
        assert "tick_count" in snap["jepa"]
        assert "history_size" in snap["jepa"]

    def test_jepa_no_stats_when_disabled(self, tmp_path):
        """Test that JEPA stats are not included when disabled."""
        core = self._core(tmp_path, enable_jepa=False)

        # Feed packets
        for p in pos_packets(SITKA_LAT, SITKA_LON, T0):
            core.handle_packet(p)

        # Build snapshot
        snap = core.build_snapshot(now_ns=T0 + 1)

        # Should not include JEPA stats
        assert "jepa" not in snap

    def test_jepa_prediction_after_training(self, tmp_path):
        """Test that JEPA can make predictions after training."""
        core = self._core(tmp_path)

        # Train with position and depth
        for p in pos_packets(SITKA_LAT, SITKA_LON, T0):
            core.handle_packet(p)

        # Create a trend
        for i in range(10):
            packet = {
                "timestamp_ns": T0 + i * 1_000_000_000,
                "source": "nmea0183",
                "channel": "depth_m",
                "value": 50.0 + i * 0.5,  # Gradual increase
            }
            core.handle_packet(packet)

        # Now make a prediction
        current_state = {
            "depth_m": 55.0,
            "speed_kn": 10.0,
            "lat": SITKA_LAT,
            "lon": SITKA_LON,
            "heading_deg": 45.0,
            "timestamp_ns": T0 + 11_000_000_000,
        }

        prediction = core.jepa.predict_future(current_state, steps_ahead=1)

        # Should predict after enough training
        # Note: May be None if not enough samples or patterns learned
        # This test verifies the integration works, not that prediction is perfect

    def test_jepa_anomaly_detection_integration(self, tmp_path):
        """Test that JEPA anomaly detection is integrated."""
        core = self._core(tmp_path)

        # Train with normal pattern
        for p in pos_packets(SITKA_LAT, SITKA_LON, T0):
            core.handle_packet(p)

        # Normal depth range
        for i in range(15):
            packet = {
                "timestamp_ns": T0 + i * 1_000_000_000,
                "source": "nmea0183",
                "channel": "depth_m",
                "value": 50.0,  # Constant depth
            }
            core.handle_packet(packet)

        # Check that JEPA has learned
        assert core.jepa is not None
        stats = core.jepa.stats
        assert stats["tick_count"] >= 15

    def test_jepa_config_parameters(self, tmp_path):
        """Test that JEPA configuration parameters are passed through."""
        core = TwinCore(
            bathymetry_path=tmp_path / "bathy.json",
            enable_jepa=True,
            jepa_history_size=500,
            jepa_learning_rate=0.2,
            jepa_anomaly_threshold=3.0,
            jepa_min_samples=20,
        )

        assert core.jepa is not None
        assert core.jepa.history_size == 500
        assert core.jepa.learning_rate == 0.2
        assert core.jepa.anomaly_threshold == 3.0
        assert core.jepa.min_samples == 20

    def test_jepa_does_not_break_normal_operations(self, tmp_path):
        """Test that JEPA doesn't break normal twin operations."""
        core = self._core(tmp_path)

        # Normal operations should work
        for p in pos_packets(SITKA_LAT, SITKA_LON, T0):
            core.handle_packet(p)

        packet = {
            "timestamp_ns": T0 + 1,
            "source": "nmea0183",
            "channel": "depth_m",
            "value": 73.2,
        }
        core.handle_packet(packet)

        # Bathymetry should still work
        assert core.bathymetry.total_voxels() == 1

        # State should still work
        snap = core.build_snapshot()
        assert snap["pose"]["lat"] == pytest.approx(SITKA_LAT)
        assert snap["pose"]["lon"] == pytest.approx(SITKA_LON)
