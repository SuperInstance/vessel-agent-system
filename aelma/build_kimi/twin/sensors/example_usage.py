#!/usr/bin/env python3
"""Example usage of the NMEA 0183 and UDP capture system.

This script demonstrates how to use the sensor capture system
for the AELMA vessel digital twin.
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from nmea_udp_capture import (
    SensorCaptureCoordinator,
    NMEA0183Listener,
    UDPDepthListener,
    dec_to_dms,
    dec_to_nmea,
    nmea_to_dec,
    dms_to_dec,
    nmea_record_to_telemetry,
    depth_record_to_telemetry,
)
import time


def example_position_conversions():
    """Demonstrate position format conversions."""
    print("=== Position Format Conversions ===\n")

    # Original position in decimal degrees
    lat, lon = 57.053, -135.330
    print(f"Original (Decimal Degrees): {lat}, {lon}\n")

    # Convert to DMS format
    dms_lat, dms_lon = dec_to_dms(lat, lon)
    print(f"DMS Format: {dms_lat}, {dms_lon}\n")

    # Convert to NMEA format
    nmea_lat, nmea_lon = dec_to_nmea(lat, lon)
    print(f"NMEA Format: {nmea_lat}, {nmea_lon}\n")

    # Round-trip conversion
    lat_back, lon_back = nmea_to_dec(nmea_lat, nmea_lon)
    print(f"Round-trip: {lat_back:.6f}, {lon_back:.6f}")
    print(f"Error: {abs(lat - lat_back):.9f} degrees\n")


def example_coordinator():
    """Demonstrate sensor coordinator usage."""
    print("=== Sensor Coordinator Example ===\n")

    # Create coordinator with custom paths
    coordinator = SensorCaptureCoordinator(
        nmea_jsonl="nmea_telemetry.jsonl",
        depth_jsonl="depth_sounder.jsonl",
        radar_jsonl="radar.jsonl",
        log_path="sensor_capture.log",
    )

    print("Starting sensor capture system...")
    coordinator.start_nmea_listener(host="0.0.0.0", port=8001)
    coordinator.start_udp_depth(host="0.0.0.0", port=50000)
    coordinator.start_radar(host="0.0.0.0", port=50001)

    print("Sensors started. Monitoring for 10 seconds...")
    for i in range(10):
        time.sleep(1)
        status = coordinator.get_status()
        nmea_count = status["nmea"]["packet_count"] if status["nmea"] else 0
        depth_count = status["depth"]["packet_count"] if status["depth"] else 0
        radar_count = status["radar"]["packet_count"] if status["radar"] else 0

        print(f"\rPackets: NMEA={nmea_count}, Depth={depth_count}, Radar={radar_count}", end='')

    print("\n\nStopping sensor capture system...")
    coordinator.stop_all()
    print("Sensor capture stopped.")


def example_standalone_nmea():
    """Demonstrate standalone NMEA listener."""
    print("=== Standalone NMEA Listener Example ===\n")

    listener = NMEA0183Listener(
        host="0.0.0.0",
        port=8001,
        jsonl_path="nmea_telemetry.jsonl"
    )

    print("Starting NMEA listener on port 8001...")
    listener.start()

    print("Listening for 5 seconds...")
    time.sleep(5)

    status = listener.get_status()
    print(f"Received {status['packet_count']} packets")
    print(f"Errors: {status['error_count']}")

    listener.stop()
    print("NMEA listener stopped.")


def example_standalone_depth():
    """Demonstrate standalone depth listener."""
    print("=== Standalone Depth Listener Example ===\n")

    listener = UDPDepthListener(
        host="0.0.0.0",
        port=50000,
        jsonl_path="depth_sounder.jsonl",
        sensor_id="depth_sounder_1"
    )

    print("Starting depth listener on port 50000...")
    listener.start()

    print("Listening for 5 seconds...")
    time.sleep(5)

    status = listener.get_status()
    print(f"Received {status['packet_count']} packets")
    print(f"Errors: {status['error_count']}")

    listener.stop()
    print("Depth listener stopped.")


def example_telemetry_integration():
    """Demonstrate TwinCore telemetry integration."""
    print("=== TwinCore Integration Example ===\n")

    # Simulate an NMEA record
    from nmea_udp_capture import NMEA0183Record

    record = NMEA0183Record(
        sentence_type="GPGGA",
        raw_sentence="$GPGGA,123519,4807.036,N,01131.324,E,1,08,0.9,545.4,M,46.9,M,*,47",
        timestamp_ns=int(time.time_ns()),
        lat_dec=48.117,
        lon_dec=11.522,
        lat_dms="48°07'02.16\"N",
        lon_dms="11°31'19.44\"E",
        lat_nmea="4807.036,N",
        lon_nmea="01131.324,E",
        quality=1,
        satellites=8,
        hdop=0.9,
    )

    # Convert to telemetry packets
    packets = nmea_record_to_telemetry(record, vessel_id="aelma")

    print(f"Generated {len(packets)} telemetry packets:")
    for packet in packets:
        print(f"  - {packet['channel']}: {packet['value']}")

    print("\nThese packets can be fed directly into TwinCore.")


def example_depth_telemetry():
    """Demonstrate depth telemetry integration."""
    print("=== Depth Telemetry Example ===\n")

    # Simulate a depth record
    from nmea_udp_capture import UDPDepthRecord

    record = UDPDepthRecord(
        sensor_id="depth_sounder_1",
        depth_m=25.5,
        timestamp_ns=int(time.time_ns()),
        raw_packet=b"25.5",
    )

    # Convert to telemetry packet
    packet = depth_record_to_telemetry(record, vessel_id="aelma")

    print(f"Depth telemetry packet:")
    print(f"  - Channel: {packet['channel']}")
    print(f"  - Value: {packet['value']} {packet['channel'].split('.')[-1]}")
    print(f"  - Source: {packet['source']}")
    print(f"  - Vessel: {packet['vessel_id']}")


def main():
    """Run all examples."""
    print("=" * 60)
    print("AELMA Sensor Capture System - Usage Examples")
    print("=" * 60)
    print()

    # Static examples (don't require actual sensors)
    example_position_conversions()
    print("\n" + "=" * 60 + "\n")

    example_telemetry_integration()
    print("\n" + "=" * 60 + "\n")

    example_depth_telemetry()
    print("\n" + "=" * 60 + "\n")

    # Uncomment to run network examples (require actual sensors)
    # print("Note: The following examples require actual sensor connections.")
    # print("Uncomment in the script to run.\n")
    #
    # example_standalone_nmea()
    # print("\n" + "=" * 60 + "\n")
    #
    # example_standalone_depth()
    # print("\n" + "=" * 60 + "\n")
    #
    # example_coordinator()

    print("\nExamples completed!")
    print("\nTo test with actual sensors:")
    print("1. Connect GPS/multiplexer to TCP port 8001")
    print("2. Connect depth sounder to UDP port 50000")
    print("3. Uncomment the network examples above")
    print("4. Run this script again")


if __name__ == "__main__":
    main()
