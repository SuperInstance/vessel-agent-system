"""Test suite for Signal K delta parsing in the AELMA bridge.

Covers delta parsing, path-to-channel mapping, array value handling,
and end-to-end packet building for Signal K messages.
"""

from __future__ import annotations

import json
import sys
import os

import pytest

# Add parent directory to path
_BUILD_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BUILD_DIR not in sys.path:
    sys.path.insert(0, _BUILD_DIR)

from bridge import signalk  # noqa: E402
from bridge.bridge import build_packet  # noqa: E402


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def _make_delta(updates: list) -> dict:
    """Build a minimal Signal K delta dict."""
    return {
        "context": "vessels.urn:mrn:imo:mmsi:123456789",
        "updates": updates
    }


# ---------------------------------------------------------------------------
# Path-to-channel mapping tests
# ---------------------------------------------------------------------------

class TestPathToChannel:
    """Tests for signalk.path_to_channel function."""

    def test_navigation_depth(self) -> None:
        """Test navigation.depth.* paths."""
        assert signalk.path_to_channel("navigation.depth.belowKeel") == "depth_m"
        assert signalk.path_to_channel("navigation.depth.belowSurface") == "depth_m"
        assert signalk.path_to_channel("navigation.depth.belowTransom") == "depth_m"
        assert signalk.path_to_channel("navigation.depth.transducerToKeel") == "depth_m"

    def test_navigation_position(self) -> None:
        """Test navigation.position.* paths."""
        assert signalk.path_to_channel("navigation.position.latitude") == "position.lat"
        assert signalk.path_to_channel("navigation.position.longitude") == "position.lon"

    def test_navigation_speed(self) -> None:
        """Test navigation.speedOverGround path."""
        assert signalk.path_to_channel("navigation.speedOverGround") == "sog_kn"

    def test_navigation_course(self) -> None:
        """Test navigation.courseOverGroundTrue path."""
        assert signalk.path_to_channel("navigation.courseOverGroundTrue") == "cog_deg"

    def test_wind_speed(self) -> None:
        """Test environment.wind.speed* paths."""
        assert signalk.path_to_channel("environment.wind.speedTrue") == "wind_kts_true"
        assert signalk.path_to_channel("environment.wind.speedApparent") == "wind_kts_apparent"

    def test_wind_direction(self) -> None:
        """Test environment.wind.angle* paths."""
        assert signalk.path_to_channel("environment.wind.angleTrue") == "wind_dir_deg_true"
        assert signalk.path_to_channel("environment.wind.angleApparent") == "wind_dir_deg_apparent"

    def test_water_temp(self) -> None:
        """Test environment.water.temperature path."""
        assert signalk.path_to_channel("environment.water.temperature") == "sea_temp_c"

    def test_air_temp(self) -> None:
        """Test environment.air.temperature path."""
        assert signalk.path_to_channel("environment.air.temperature") == "air_temp_c"

    def test_air_pressure(self) -> None:
        """Test environment.air.pressure path."""
        assert signalk.path_to_channel("environment.air.pressure") == "baro_mb"

    def test_unknown_path_returns_none(self) -> None:
        """Test unsupported path returns None."""
        assert signalk.path_to_channel("unknown.path.value") is None
        assert signalk.path_to_channel("navigation.heading") is None


# ---------------------------------------------------------------------------
# Delta parsing tests
# ---------------------------------------------------------------------------

class TestDeltaParsing:
    """Tests for SignalKDelta class and parse_delta function."""

    def test_simple_depth_delta(self) -> None:
        """Test parsing a simple depth delta."""
        delta = _make_delta([{
            "timestamp": "2025-01-15T12:34:56Z",
            "values": [
                {"path": "navigation.depth.belowKeel", "value": 73.2}
            ]
        }])

        readings = signalk.parse_delta(delta)
        assert len(readings) == 1
        assert readings[0]["channel"] == "depth_m"
        assert readings[0]["value"] == pytest.approx(73.2)
        assert readings[0]["source"] == "signalk"

    def test_position_delta(self) -> None:
        """Test parsing a position delta with lat/lon."""
        delta = _make_delta([{
            "timestamp": "2025-01-15T12:34:56Z",
            "values": [
                {"path": "navigation.position.latitude", "value": 56.8013},
                {"path": "navigation.position.longitude", "value": -135.3028}
            ]
        }])

        readings = signalk.parse_delta(delta)
        assert len(readings) == 2

        # Find lat and lon readings
        lat_readings = [r for r in readings if r["channel"] == "position.lat"]
        lon_readings = [r for r in readings if r["channel"] == "position.lon"]

        assert len(lat_readings) == 1
        assert len(lon_readings) == 1
        assert lat_readings[0]["value"] == pytest.approx(56.8013)
        assert lon_readings[0]["value"] == pytest.approx(-135.3028)

    def test_wind_delta(self) -> None:
        """Test parsing a wind delta."""
        delta = _make_delta([{
            "timestamp": "2025-01-15T12:34:56Z",
            "values": [
                {"path": "environment.wind.speedTrue", "value": 6.5},
                {"path": "environment.wind.angleTrue", "value": 45.0}
            ]
        }])

        readings = signalk.parse_delta(delta)
        assert len(readings) == 2

        # Check speed (converted from m/s to knots)
        speed_readings = [r for r in readings if r["channel"] == "wind_kts_true"]
        assert len(speed_readings) == 1
        assert speed_readings[0]["value"] == pytest.approx(6.5 * 1.94384, rel=1e-4)

        # Check direction
        dir_readings = [r for r in readings if r["channel"] == "wind_dir_deg_true"]
        assert len(dir_readings) == 1
        assert dir_readings[0]["value"] == pytest.approx(45.0)

    def test_water_temp_delta(self) -> None:
        """Test parsing water temperature (Kelvin -> Celsius)."""
        delta = _make_delta([{
            "timestamp": "2025-01-15T12:34:56Z",
            "values": [
                {"path": "environment.water.temperature", "value": 285.65}  # 12.5°C
            ]
        }])

        readings = signalk.parse_delta(delta)
        assert len(readings) == 1
        assert readings[0]["channel"] == "sea_temp_c"
        # Kelvin -> Celsius conversion
        assert readings[0]["value"] == pytest.approx(285.65 - 273.15)

    def test_air_temp_pressure_delta(self) -> None:
        """Test parsing air temperature and pressure."""
        delta = _make_delta([{
            "timestamp": "2025-01-15T12:34:56Z",
            "values": [
                {"path": "environment.air.temperature", "value": 288.15},  # 15°C
                {"path": "environment.air.pressure", "value": 101325}  # 1013.25 mb
            ]
        }])

        readings = signalk.parse_delta(delta)
        assert len(readings) == 2

        # Check temp (Kelvin -> Celsius)
        temp_readings = [r for r in readings if r["channel"] == "air_temp_c"]
        assert len(temp_readings) == 1
        assert temp_readings[0]["value"] == pytest.approx(288.15 - 273.15)

        # Check pressure (Pa -> mb)
        press_readings = [r for r in readings if r["channel"] == "baro_mb"]
        assert len(press_readings) == 1
        assert press_readings[0]["value"] == pytest.approx(101325 / 100.0)

    def test_speed_over_ground_delta(self) -> None:
        """Test speed over ground (m/s -> knots)."""
        delta = _make_delta([{
            "timestamp": "2025-01-15T12:34:56Z",
            "values": [
                {"path": "navigation.speedOverGround", "value": 2.68}  # ~5.2 knots
            ]
        }])

        readings = signalk.parse_delta(delta)
        assert len(readings) == 1
        assert readings[0]["channel"] == "sog_kn"
        # m/s -> knots conversion
        assert readings[0]["value"] == pytest.approx(2.68 * 1.94384, rel=1e-4)

    def test_course_over_ground_delta(self) -> None:
        """Test course over ground."""
        delta = _make_delta([{
            "timestamp": "2025-01-15T12:34:56Z",
            "values": [
                {"path": "navigation.courseOverGroundTrue", "value": 180.0}
            ]
        }])

        readings = signalk.parse_delta(delta)
        assert len(readings) == 1
        assert readings[0]["channel"] == "cog_deg"
        assert readings[0]["value"] == pytest.approx(180.0)

    def test_multiple_updates(self) -> None:
        """Test delta with multiple updates."""
        delta = _make_delta([
            {
                "timestamp": "2025-01-15T12:34:56Z",
                "values": [
                    {"path": "navigation.depth.belowKeel", "value": 73.2}
                ]
            },
            {
                "timestamp": "2025-01-15T12:34:57Z",
                "values": [
                    {"path": "navigation.speedOverGround", "value": 2.68}
                ]
            }
        ])

        readings = signalk.parse_delta(delta)
        assert len(readings) == 2

        # Check depth
        depth_readings = [r for r in readings if r["channel"] == "depth_m"]
        assert len(depth_readings) == 1

        # Check speed
        speed_readings = [r for r in readings if r["channel"] == "sog_kn"]
        assert len(speed_readings) == 1

    def test_unknown_paths_ignored(self) -> None:
        """Test that unsupported paths are ignored."""
        delta = _make_delta([{
            "timestamp": "2025-01-15T12:34:56Z",
            "values": [
                {"path": "navigation.depth.belowKeel", "value": 73.2},
                {"path": "unknown.path.value", "value": 42.0},
                {"path": "navigation.heading", "value": 180.0}
            ]
        }])

        readings = signalk.parse_delta(delta)
        assert len(readings) == 1  # Only depth
        assert readings[0]["channel"] == "depth_m"

    def test_empty_delta(self) -> None:
        """Test empty delta returns no readings."""
        delta = _make_delta([])
        readings = signalk.parse_delta(delta)
        assert len(readings) == 0

    def test_no_values_field(self) -> None:
        """Test update without values field."""
        delta = _make_delta([{
            "timestamp": "2025-01-15T12:34:56Z"
        }])
        readings = signalk.parse_delta(delta)
        assert len(readings) == 0

    def test_null_values_handled(self) -> None:
        """Test null values are handled gracefully."""
        delta = _make_delta([{
            "timestamp": "2025-01-15T12:34:56Z",
            "values": [
                {"path": "navigation.depth.belowKeel", "value": None}
            ]
        }])

        readings = signalk.parse_delta(delta)
        assert len(readings) == 0  # Null values shouldn't produce readings


# ---------------------------------------------------------------------------
# SignalKDelta class tests
# ---------------------------------------------------------------------------

class TestSignalKDeltaClass:
    """Tests for SignalKDelta class methods."""

    def test_from_dict(self) -> None:
        """Test creating SignalKDelta from dict."""
        delta_data = _make_delta([{
            "timestamp": "2025-01-15T12:34:56Z",
            "values": [
                {"path": "navigation.depth.belowKeel", "value": 73.2}
            ]
        }])

        delta = signalk.SignalKDelta(delta_data)
        readings = delta.to_readings()
        assert len(readings) == 1

    def test_from_json_string(self) -> None:
        """Test creating SignalKDelta from JSON string."""
        delta_data = _make_delta([{
            "timestamp": "2025-01-15T12:34:56Z",
            "values": [
                {"path": "navigation.depth.belowKeel", "value": 73.2}
            ]
        }])

        json_str = json.dumps(delta_data)
        delta = signalk.SignalKDelta(json_str)
        readings = delta.to_readings()
        assert len(readings) == 1

    def test_get_context(self) -> None:
        """Test get_context method."""
        delta_data = _make_delta([{
            "timestamp": "2025-01-15T12:34:56Z",
            "values": [
                {"path": "navigation.depth.belowKeel", "value": 73.2}
            ]
        }])

        delta = signalk.SignalKDelta(delta_data)
        context = delta.get_context()
        assert "urn:mrn:imo:mmsi:123456789" in context

    def test_get_timestamp(self) -> None:
        """Test get_timestamp method."""
        delta_data = _make_delta([{
            "timestamp": "2025-01-15T12:34:56Z",
            "values": [
                {"path": "navigation.depth.belowKeel", "value": 73.2}
            ]
        }])

        delta = signalk.SignalKDelta(delta_data)
        timestamp = delta.get_timestamp()
        assert timestamp == "2025-01-15T12:34:56Z"


# ---------------------------------------------------------------------------
# End-to-end tests
# ---------------------------------------------------------------------------

class TestEndToEnd:
    """End-to-end: parse -> build_packet -> verify fields."""

    def test_depth_packet(self) -> None:
        """Test building a complete depth packet."""
        delta = _make_delta([{
            "timestamp": "2025-01-15T12:34:56Z",
            "values": [
                {"path": "navigation.depth.belowKeel", "value": 73.2}
            ]
        }])

        readings = signalk.parse_delta(delta)
        assert len(readings) == 1

        pkt = build_packet(readings[0])
        assert pkt["source"] == "signalk"
        assert pkt["channel"] == "depth_m"
        assert pkt["value"] == pytest.approx(73.2)
        assert pkt["quality"] == "good"
        assert pkt["timestamp_ns"] > 0

    def test_position_packet(self) -> None:
        """Test building position packets."""
        delta = _make_delta([{
            "timestamp": "2025-01-15T12:34:56Z",
            "values": [
                {"path": "navigation.position.latitude", "value": 56.8013},
                {"path": "navigation.position.longitude", "value": -135.3028}
            ]
        }])

        readings = signalk.parse_delta(delta)
        assert len(readings) == 2

        for reading in readings:
            pkt = build_packet(reading)
            assert pkt["quality"] == "good"
            assert pkt["timestamp_ns"] > 0
            assert pkt["source"] == "signalk"
            assert pkt["channel"] in ["position.lat", "position.lon"]

    def test_wind_packet(self) -> None:
        """Test building wind packets."""
        delta = _make_delta([{
            "timestamp": "2025-01-15T12:34:56Z",
            "values": [
                {"path": "environment.wind.speedTrue", "value": 6.5},
                {"path": "environment.wind.angleTrue", "value": 45.0}
            ]
        }])

        readings = signalk.parse_delta(delta)
        for reading in readings:
            pkt = build_packet(reading)
            assert pkt["quality"] == "good"
            assert pkt["timestamp_ns"] > 0
            assert pkt["source"] == "signalk"
            assert pkt["channel"] in ["wind_kts_true", "wind_dir_deg_true"]

    def test_packet_json_serializable(self) -> None:
        """Test that packets can be serialized to JSON."""
        delta = _make_delta([{
            "timestamp": "2025-01-15T12:34:56Z",
            "values": [
                {"path": "navigation.depth.belowKeel", "value": 73.2}
            ]
        }])

        readings = signalk.parse_delta(delta)
        pkt = build_packet(readings[0])

        # Test JSON serialization
        json_str = json.dumps(pkt)
        restored = json.loads(json_str)
        assert restored["channel"] == "depth_m"
        assert restored["value"] == pytest.approx(73.2)


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------

class TestEndpoints:
    """Tests for endpoint utility functions."""

    def test_signalk_ws_endpoint(self) -> None:
        """Test WebSocket endpoint builder."""
        assert signalk.signalk_ws_endpoint("localhost", 3000) == "ws://localhost:3000/signalk/v1/stream"
        assert signalk.signalk_ws_endpoint("192.168.1.100", 4000) == "ws://192.168.1.100:4000/signalk/v1/stream"

    def test_signalk_tcp_endpoint(self) -> None:
        """Test TCP endpoint builder."""
        assert signalk.signalk_tcp_endpoint("localhost", 4000) == "localhost:4000"
        assert signalk.signalk_tcp_endpoint("192.168.1.100", 5000) == "192.168.1.100:5000"


# ---------------------------------------------------------------------------
# Quality tests
# ---------------------------------------------------------------------------

class TestQualityChecks:
    """Tests for quality checks on Signal K values."""

    def test_depth_quality_good(self) -> None:
        """Test depth quality is good for valid values."""
        delta = _make_delta([{
            "timestamp": "2025-01-15T12:34:56Z",
            "values": [
                {"path": "navigation.depth.belowKeel", "value": 73.2}
            ]
        }])

        readings = signalk.parse_delta(delta)
        pkt = build_packet(readings[0])
        assert pkt["quality"] == "good"

    def test_position_quality_good(self) -> None:
        """Test position quality is good for valid coordinates."""
        delta = _make_delta([{
            "timestamp": "2025-01-15T12:34:56Z",
            "values": [
                {"path": "navigation.position.latitude", "value": 56.8013}
            ]
        }])

        readings = signalk.parse_delta(delta)
        pkt = build_packet(readings[0])
        assert pkt["quality"] == "good"


# ---------------------------------------------------------------------------
# Multiplexing tests
# ---------------------------------------------------------------------------

class TestMultiplexing:
    """Tests for multiplexing NMEA and Signal K sources."""

    def test_signalk_source_identification(self) -> None:
        """Test that Signal K source is correctly identified."""
        delta = _make_delta([{
            "timestamp": "2025-01-15T12:34:56Z",
            "values": [
                {"path": "navigation.depth.belowKeel", "value": 73.2}
            ]
        }])

        readings = signalk.parse_delta(delta)
        assert readings[0]["source"] == "signalk"

        # Build packet and verify source
        pkt = build_packet(readings[0])
        assert pkt["source"] == "signalk"

    def test_nmea_vs_signalk_sources(self) -> None:
        """Test that NMEA and Signal K sources are distinguishable."""
        # Import NMEA parser
        from bridge import nmea

        # NMEA depth reading
        def _make(body: str) -> str:
            """Build a valid-checksum NMEA sentence."""
            c = 0
            for ch in body:
                c ^= ord(ch)
            return f"${body}*{c:02X}"

        nmea_sentence = _make("SDDPT,73.2,-1.5,")
        nmea_readings = nmea.parse_sentence(nmea_sentence)

        # Signal K depth reading
        delta = _make_delta([{
            "timestamp": "2025-01-15T12:34:56Z",
            "values": [
                {"path": "navigation.depth.belowKeel", "value": 73.2}
            ]
        }])
        sk_readings = signalk.parse_delta(delta)

        # Check sources
        assert nmea_readings[0]["source"] == "nmea0183"
        assert sk_readings[0]["source"] == "signalk"

        # Build packets
        nmea_pkt = build_packet(nmea_readings[0])
        sk_pkt = build_packet(sk_readings[0])

        # Both should have same channel and value, but different sources
        assert nmea_pkt["channel"] == sk_pkt["channel"]
        assert nmea_pkt["value"] == sk_pkt["value"]
        assert nmea_pkt["source"] == "nmea0183"
        assert sk_pkt["source"] == "signalk"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
