#!/usr/bin/env python3
"""Demo script showing TelemetryQuery analytics capabilities.

This script demonstrates how to use the AELMA telemetry query analytics layer
to analyze JSONL telemetry logs with filtering, time-bucketing, statistics,
and percentiles.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from build_kimi.twin.telemetry_query import TelemetryQuery


def create_sample_telemetry_log(output_path: Path) -> None:
    """Create a sample telemetry log for demonstration."""
    T0 = 1_753_478_400_000_000_000  # Fixed epoch

    records = [
        # Depth readings over a 60-second period
        {
            "timestamp_ns": T0,
            "source": "nmea0183",
            "channel": "depth_m",
            "value": 73.2,
            "quality": "good",
        },
        {
            "timestamp_ns": T0 + 10_000_000_000,
            "source": "nmea0183",
            "channel": "depth_m",
            "value": 74.5,
            "quality": "good",
        },
        {
            "timestamp_ns": T0 + 20_000_000_000,
            "source": "nmea0183",
            "channel": "depth_m",
            "value": 71.8,
            "quality": "good",
        },
        {
            "timestamp_ns": T0 + 30_000_000_000,
            "source": "nmea0183",
            "channel": "depth_m",
            "value": 75.0,
            "quality": "suspect",
        },
        {
            "timestamp_ns": T0 + 40_000_000_000,
            "source": "nmea0183",
            "channel": "depth_m",
            "value": 72.3,
            "quality": "good",
        },
        {
            "timestamp_ns": T0 + 50_000_000_000,
            "source": "nmea0183",
            "channel": "depth_m",
            "value": 73.8,
            "quality": "good",
        },
        # Engine RPM readings
        {
            "timestamp_ns": T0 + 5_000_000_000,
            "source": "simulator",
            "channel": "engine_rpm",
            "value": 2200.0,
            "quality": "good",
        },
        {
            "timestamp_ns": T0 + 15_000_000_000,
            "source": "simulator",
            "channel": "engine_rpm",
            "value": 2300.0,
            "quality": "good",
        },
        {
            "timestamp_ns": T0 + 25_000_000_000,
            "source": "simulator",
            "channel": "engine_rpm",
            "value": 2400.0,
            "quality": "good",
        },
        # Position readings
        {
            "timestamp_ns": T0,
            "source": "nmea0183",
            "channel": "position.lat",
            "value": 57.0531,
            "quality": "good",
        },
        {
            "timestamp_ns": T0,
            "source": "nmea0183",
            "channel": "position.lon",
            "value": -135.3300,
            "quality": "good",
        },
    ]

    with open(output_path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    print(f"Created sample telemetry log: {output_path}")
    print(f"  Total records: {len(records)}")


def demo_basic_filtering(query: TelemetryQuery) -> None:
    """Demonstrate basic filtering capabilities."""
    print("\n" + "=" * 60)
    print("DEMO 1: Basic Filtering")
    print("=" * 60)

    # Filter by channel
    print("\n1. Filter depth_m channel:")
    for record in query.filter(channel="depth_m"):
        print(f"   {record.timestamp_ns}: {record.value}m ({record.quality})")

    # Filter by value range
    print("\n2. Filter depth_m between 72.0m and 74.0m:")
    for record in query.filter(channel="depth_m", value_range=(72.0, 74.0)):
        print(f"   {record.timestamp_ns}: {record.value}m")

    # Filter by quality
    print("\n3. Filter only 'good' quality depth readings:")
    for record in query.filter(channel="depth_m", quality="good"):
        print(f"   {record.timestamp_ns}: {record.value}m")

    # Filter by source
    print("\n4. Filter simulator source:")
    for record in query.filter(source="simulator"):
        print(f"   {record.timestamp_ns}: {record.channel} = {record.value}")


def demo_time_bucketing(query: TelemetryQuery) -> None:
    """Demonstrate time-bucketing for temporal analysis."""
    print("\n" + "=" * 60)
    print("DEMO 2: Time Bucketing")
    print("=" * 60)

    print("\n1. 30-second buckets for depth_m:")
    for bucket in query.time_bucket(30).filter(channel="depth_m"):
        print(f"   Bucket {bucket.bucket_start_ns} - {bucket.bucket_end_ns}:")
        print(f"     Count: {bucket.count}")
        print(f"     Mean: {bucket.mean:.2f}m")
        print(f"     Range: {bucket.min:.2f}m - {bucket.max:.2f}m")

    print("\n2. 60-second buckets for engine_rpm:")
    for bucket in query.time_bucket(60).filter(channel="engine_rpm"):
        print(f"   Bucket {bucket.bucket_start_ns} - {bucket.bucket_end_ns}:")
        print(f"     Count: {bucket.count}")
        print(f"     Mean RPM: {bucket.mean:.0f}")


def demo_statistics(query: TelemetryQuery) -> None:
    """Demonstrate statistical analysis."""
    print("\n" + "=" * 60)
    print("DEMO 3: Statistical Analysis")
    print("=" * 60)

    print("\n1. Depth statistics (all readings):")
    stats = query.stats("value").filter(channel="depth_m")
    print(f"   Count: {stats.count}")
    print(f"   Mean: {stats.mean:.2f}m")
    print(f"   StdDev: {stats.stddev:.2f}m")
    print(f"   Range: {stats.min:.2f}m - {stats.max:.2f}m")

    print("\n2. Depth statistics (good quality only):")
    stats_good = query.stats("value").filter(channel="depth_m", quality="good")
    print(f"   Count: {stats_good.count}")
    print(f"   Mean: {stats_good.mean:.2f}m")
    print(f"   Range: {stats_good.min:.2f}m - {stats_good.max:.2f}m")

    print("\n3. Engine RPM statistics:")
    stats_rpm = query.stats("value").filter(channel="engine_rpm")
    print(f"   Count: {stats_rpm.count}")
    print(f"   Mean: {stats_rpm.mean:.0f} RPM")
    print(f"   Range: {stats_rpm.min:.0f} - {stats_rpm.max:.0f} RPM")


def demo_percentiles(query: TelemetryQuery) -> None:
    """Demonstrate percentile calculations."""
    print("\n" + "=" * 60)
    print("DEMO 4: Percentiles")
    print("=" * 60)

    print("\n1. Depth percentiles:")
    for p in [0, 25, 50, 75, 95, 100]:
        value = query.percentile("value", p).filter(channel="depth_m").value
        print(f"   p{p}: {value:.2f}m")

    print("\n2. Engine RPM percentiles:")
    p50 = query.percentile("value", 50).filter(channel="engine_rpm").value
    p95 = query.percentile("value", 95).filter(channel="engine_rpm").value
    print(f"   Median (p50): {p50:.0f} RPM")
    print(f"   p95: {p95:.0f} RPM")


def demo_combined_filters(query: TelemetryQuery) -> None:
    """Demonstrate combining multiple filters."""
    print("\n" + "=" * 60)
    print("DEMO 5: Combined Filters")
    print("=" * 60)

    print("\n1. Depth between 72m-74m, good quality, NMEA0183 source:")
    count = 0
    for record in query.filter(
        channel="depth_m",
        value_range=(72.0, 74.0),
        quality="good",
        source="nmea0183",
    ):
        count += 1
        print(f"   {record.timestamp_ns}: {record.value}m")
    print(f"   Total: {count} records")

    print("\n2. Statistics for same filter:")
    stats = query.stats("value").filter(
        channel="depth_m",
        value_range=(72.0, 74.0),
        quality="good",
        source="nmea0183",
    )
    print(f"   Mean: {stats.mean:.2f}m")
    print(f"   Count: {stats.count}")


def demo_streaming_efficiency(query: TelemetryQuery) -> None:
    """Demonstrate streaming efficiency for large datasets."""
    print("\n" + "=" * 60)
    print("DEMO 6: Streaming Efficiency")
    print("=" * 60)

    print("\nCounting records without loading into memory:")
    count = sum(1 for _ in query.filter())
    print(f"  Total records: {count}")

    count_depth = sum(1 for _ in query.filter(channel="depth_m"))
    print(f"  Depth records: {count_depth}")

    count_engine = sum(1 for _ in query.filter(channel="engine_rpm"))
    print(f"  Engine RPM records: {count_engine}")


def main():
    """Run all telemetry query demos."""
    print("AELMA Telemetry Query Analytics Demo")
    print("=" * 60)

    # Create sample data
    log_path = Path("sample_telemetry.jsonl")
    create_sample_telemetry_log(log_path)

    # Initialize query
    query = TelemetryQuery(log_path)

    # Run demos
    demo_basic_filtering(query)
    demo_time_bucketing(query)
    demo_statistics(query)
    demo_percentiles(query)
    demo_combined_filters(query)
    demo_streaming_efficiency(query)

    print("\n" + "=" * 60)
    print("Demo complete!")
    print(f"Sample log file: {log_path.absolute()}")
    print("=" * 60)

    # Cleanup提示
    print(f"\nTo cleanup, run: rm {log_path}")


if __name__ == "__main__":
    main()
