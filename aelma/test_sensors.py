#!/usr/bin/env python
"""Test script for NMEA/UDP sensor capture."""

import socket
import time
import json
from pathlib import Path


def test_nMEA_tcp():
    """Test NMEA TCP listener with sample sentences."""
    print("Testing NMEA TCP listener on localhost:8001...")

    # Sample NMEA sentences
    sentences = [
        "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47",
        "$GPGLL,4807.038,N,01131.000,E,123519,A*3C",
        "$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,,,A*1D",
        "$GPZDA,123519,28,06,2024,00,00*00",
        "$DBT,,042.5,f*21",
        "$DBS,,042.5,f*21"
    ]

    try:
        # Connect to NMEA listener
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("localhost", 8001))

        for sentence in sentences:
            sock.sendall((sentence + "\r\n").encode())
            print(f"  Sent: {sentence[:30]}...")
            time.sleep(0.1)

        sock.close()
        print("✓ NMEA test sentences sent successfully")

    except Exception as e:
        print(f"✗ NMEA test failed: {e}")


def test_udp_depth():
    """Test UDP depth listener."""
    print("Testing UDP Depth listener on localhost:50000...")

    # Sample depth data
    depth_samples = [
        "DEPTH=45.2",
        "DEPTH=52.8",
        "DEPTH=38.1",
        "48.5m",
        "42.3"
    ]

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        for sample in depth_samples:
            sock.sendto(sample.encode(), ("localhost", 50000))
            print(f"  Sent: {sample}")
            time.sleep(0.1)

        sock.close()
        print("✓ UDP depth test data sent successfully")

    except Exception as e:
        print(f"✗ UDP depth test failed: {e}")


def check_sensor_data():
    """Check if sensor data files are being created."""
    print("\nChecking sensor data files...")

    sensor_dir = Path("sensor_data")
    if not sensor_dir.exists():
        print("✗ sensor_data directory not found")
        return

    # Check NMEA telemetry
    nmea_file = sensor_dir / "nmea_telemetry.jsonl"
    if nmea_file.exists():
        lines = nmea_file.read_text().strip().split('\n') if nmea_file.stat().st_size > 0 else []
        print(f"✓ NMEA telemetry: {len(lines)} records")
        if lines and lines[0]:
            try:
                record = json.loads(lines[0])
                print(f"  Sample: {record.get('sentence_type', 'unknown')} - {record.get('timestamp_ns', 'no timestamp')}")
            except:
                pass
    else:
        print("  NMEA telemetry: file not created yet")

    # Check depth sounder
    depth_file = sensor_dir / "depth_sounder.jsonl"
    if depth_file.exists():
        lines = depth_file.read_text().strip().split('\n') if depth_file.stat().st_size > 0 else []
        print(f"✓ Depth sounder: {len(lines)} records")
    else:
        print("  Depth sounder: file not created yet")

    # Check log
    log_file = sensor_dir / "sensor_capture.log"
    if log_file.exists():
        log_lines = log_file.read_text().strip().split('\n')
        print(f"✓ Sensor log: {len(log_lines)} entries")


if __name__ == "__main__":
    print("AELMA Sensor Capture Test")
    print("=" * 50)

    test_nMEA_tcp()
    time.sleep(1)
    test_udp_depth()
    time.sleep(2)
    check_sensor_data()

    print("\nTest complete!")
