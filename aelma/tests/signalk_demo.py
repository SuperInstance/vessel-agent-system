#!/usr/bin/env python3
"""Signal K Integration Demo for AELMA

This script demonstrates the Signal K integration by parsing example deltas
and converting them to telemetry packets.

Usage:
    python tests/signalk_demo.py
"""

import json
import sys
import os

# Add parent directory to path
_BUILD_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BUILD_DIR not in sys.path:
    sys.path.insert(0, _BUILD_DIR)

from bridge import signalk
from bridge.bridge import build_packet


def print_section(title: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def demo_basic_parsing():
    """Demonstrate basic Signal K delta parsing."""
    print_section("Basic Signal K Delta Parsing")

    # Example Signal K delta
    delta = {
        "context": "vessels.urn:mrn:imo:mmsi:123456789",
        "updates": [
            {
                "timestamp": "2025-01-15T12:34:56Z",
                "source": {
                    "type": "NMEA0183",
                    "sentence": "GPGGA"
                },
                "values": [
                    {"path": "navigation.position.latitude", "value": 56.8013},
                    {"path": "navigation.position.longitude", "value": -135.3028}
                ]
            }
        ]
    }

    print("Input Delta:")
    print(json.dumps(delta, indent=2))

    readings = signalk.parse_delta(delta)

    print(f"\nParsed {len(readings)} readings:")
    for reading in readings:
        print(f"  - {reading['channel']}: {reading['value']}")
        pkt = build_packet(reading)
        print(f"    -> TelemetryPacket: {pkt['source']}, quality={pkt['quality']}")


def demo_complex_delta():
    """Demonstrate complex delta with multiple updates."""
    print_section("Complex Delta (Multiple Updates)")

    delta = {
        "context": "vessels.urn:mrn:imo:mmsi:123456789",
        "updates": [
            {
                "timestamp": "2025-01-15T12:34:56Z",
                "values": [
                    {"path": "navigation.depth.belowKeel", "value": 73.2},
                    {"path": "navigation.speedOverGround", "value": 2.68},
                    {"path": "navigation.courseOverGroundTrue", "value": 180.0}
                ]
            },
            {
                "timestamp": "2025-01-15T12:34:57Z",
                "values": [
                    {"path": "environment.wind.speedTrue", "value": 6.5},
                    {"path": "environment.wind.angleTrue", "value": 45.0}
                ]
            }
        ]
    }

    print("Input Delta:")
    print(json.dumps(delta, indent=2))

    readings = signalk.parse_delta(delta)

    print(f"\nParsed {len(readings)} readings:")
    for reading in readings:
        print(f"  - {reading['channel']}: {reading['value']}")


def demo_unit_conversions():
    """Demonstrate unit conversions."""
    print_section("Unit Conversions")

    conversions = [
        ("navigation.speedOverGround", 2.68, "m/s", "knots", "sog_kn"),
        ("environment.wind.speedTrue", 6.5, "m/s", "knots", "wind_kts_true"),
        ("environment.water.temperature", 285.65, "K", "°C", "sea_temp_c"),
        ("environment.air.temperature", 288.15, "K", "°C", "air_temp_c"),
        ("environment.air.pressure", 101325, "Pa", "mb", "baro_mb"),
    ]

    for path, input_val, input_unit, output_unit, expected_channel in conversions:
        delta = {
            "updates": [{
                "values": [{"path": path, "value": input_val}]
            }]
        }

        readings = signalk.parse_delta(delta)
        if readings:
            reading = readings[0]
            print(f"{path}")
            print(f"  Input: {input_val} {input_unit}")
            print(f"  Output: {reading['value']:.2f} {output_unit}")
            print(f"  Channel: {reading['channel']}")

            # Verify channel
            assert reading['channel'] == expected_channel, f"Expected {expected_channel}, got {reading['channel']}"


def demo_path_mapping():
    """Demonstrate path-to-channel mapping."""
    print_section("Path-to-Channel Mapping")

    paths = [
        "navigation.depth.belowKeel",
        "navigation.position.latitude",
        "navigation.speedOverGround",
        "environment.wind.speedTrue",
        "environment.water.temperature",
        "environment.air.temperature",
        "environment.air.pressure",
        "unknown.path.value",
    ]

    for path in paths:
        channel = signalk.path_to_channel(path)
        if channel:
            print(f"{path:45} -> {channel}")
        else:
            print(f"{path:45} -> (unsupported)")


def demo_error_handling():
    """Demonstrate error handling."""
    print_section("Error Handling")

    # Invalid JSON
    print("1. Invalid JSON:")
    try:
        signalk.parse_delta("not valid json")
    except Exception as e:
        print(f"   Error caught: {type(e).__name__}")

    # Empty delta
    print("\n2. Empty Delta:")
    readings = signalk.parse_delta({"updates": []})
    print(f"   Readings: {readings}")

    # Null values
    print("\n3. Null Values:")
    readings = signalk.parse_delta({
        "updates": [{
            "values": [{"path": "navigation.depth.belowKeel", "value": None}]
        }]
    })
    print(f"   Readings: {readings}")

    # Unknown paths
    print("\n4. Unknown Paths:")
    readings = signalk.parse_delta({
        "updates": [{
            "values": [{"path": "unknown.path", "value": 42.0}]
        }]
    })
    print(f"   Readings: {readings}")


def demo_multiplexing():
    """Demonstrate NMEA and Signal K multiplexing."""
    print_section("NMEA + Signal K Multiplexing")

    # NMEA reading
    def _make(body: str) -> str:
        """Build a valid-checksum NMEA sentence."""
        c = 0
        for ch in body:
            c ^= ord(ch)
        return f"${body}*{c:02X}"

    nmea_sentence = _make("SDDPT,73.2,-1.5,")
    from bridge import nmea
    nmea_readings = nmea.parse_sentence(nmea_sentence)

    # Signal K reading
    delta = {
        "updates": [{
            "values": [{"path": "navigation.depth.belowKeel", "value": 73.2}]
        }]
    }
    sk_readings = signalk.parse_delta(delta)

    print("NMEA Source:")
    for reading in nmea_readings:
        pkt = build_packet(reading)
        print(f"  {pkt['source']:10} | {pkt['channel']:15} | {pkt['value']:.1f}")

    print("\nSignal K Source:")
    for reading in sk_readings:
        pkt = build_packet(reading)
        print(f"  {pkt['source']:10} | {pkt['channel']:15} | {pkt['value']:.1f}")

    print("\nBoth sources produce the same telemetry packet format!")


def main():
    """Run all demonstrations."""
    print("Signal K Integration Demo for AELMA")
    print("=" * 60)

    demo_basic_parsing()
    demo_complex_delta()
    demo_unit_conversions()
    demo_path_mapping()
    demo_error_handling()
    demo_multiplexing()

    print_section("Demo Complete")
    print("Signal K integration is working correctly!")
    print("\nNext Steps:")
    print("  1. Connect to a Signal K server:")
    print("     python -m bridge.bridge --signalk-host localhost --signalk-port 3000")
    print("  2. Run tests:")
    print("     python -m pytest tests/signalk.test.py -v")
    print("  3. Read documentation:")
    print("     docs/signalk_integration.md")


if __name__ == "__main__":
    main()
