"""Tests for TelemetryQuery analytics layer."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make the repository root importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from build_kimi.twin.telemetry_query import (
    FilterOptions,
    PercentileCalculator,
    StatsCalculator,
    StatsResult,
    TelemetryQuery,
    TelemetryRecord,
    TimeBucket,
    TimeBucketer,
)

T0 = 1_753_478_400_000_000_000  # Fixed epoch ns for deterministic tests


def write_test_log(tmp_path: Path, records: list[dict]) -> Path:
    """Write a synthetic telemetry log for testing."""
    log_path = tmp_path / "telemetry.jsonl"
    with open(log_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    return log_path


def sample_records() -> list[dict]:
    """Generate sample telemetry records for testing."""
    return [
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
    ]


# --------------------------------------------------------------------- #
# TelemetryRecord
# --------------------------------------------------------------------- #


class TestTelemetryRecord:
    """TelemetryRecord creation and validation."""

    def test_from_dict(self):
        data = {
            "timestamp_ns": T0,
            "source": "nmea0183",
            "channel": "depth_m",
            "value": 73.2,
            "quality": "good",
        }
        rec = TelemetryRecord.from_dict(data)
        assert rec.timestamp_ns == T0
        assert rec.source == "nmea0183"
        assert rec.channel == "depth_m"
        assert rec.value == 73.2
        assert rec.quality == "good"

    def test_default_quality(self):
        data = {
            "timestamp_ns": T0,
            "source": "nmea0183",
            "channel": "depth_m",
            "value": 73.2,
        }
        rec = TelemetryRecord.from_dict(data)
        assert rec.quality == "good"

    def test_type_conversions(self):
        data = {
            "timestamp_ns": str(T0),  # String input
            "source": "nmea0183",
            "channel": "depth_m",
            "value": "73.2",  # String input
        }
        rec = TelemetryRecord.from_dict(data)
        assert isinstance(rec.timestamp_ns, int)
        assert isinstance(rec.value, float)
        assert rec.value == 73.2


# --------------------------------------------------------------------- #
# TelemetryQuery initialization
# --------------------------------------------------------------------- #


class TestTelemetryQueryInit:
    """TelemetryQuery initialization and error handling."""

    def test_init_with_valid_path(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        assert query.log_path == log_path

    def test_init_with_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            TelemetryQuery(tmp_path / "nonexistent.jsonl")

    def test_init_with_string_path(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(str(log_path))
        assert query.log_path == Path(log_path)


# --------------------------------------------------------------------- #
# Filtering
# --------------------------------------------------------------------- #


class TestFiltering:
    """Filter functionality."""

    def test_no_filter_returns_all(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        results = list(query.filter())
        assert len(results) == 7

    def test_filter_by_channel(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        results = list(query.filter(channel="depth_m"))
        assert len(results) == 5
        assert all(r.channel == "depth_m" for r in results)

    def test_filter_by_value_range(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        results = list(query.filter(channel="depth_m", value_range=(72.0, 74.0)))
        # Depth values: [73.2, 74.5, 71.8, 75.0, 72.3]
        # In range [72.0, 74.0]: 73.2 and 72.3 only (2 values)
        assert len(results) == 2
        assert all(72.0 <= r.value <= 74.0 for r in results)

    def test_filter_by_source(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        results = list(query.filter(source="simulator"))
        assert len(results) == 2
        assert all(r.source == "simulator" for r in results)

    def test_filter_by_quality(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        results = list(query.filter(channel="depth_m", quality="suspect"))
        assert len(results) == 1
        assert results[0].quality == "suspect"

    def test_filter_by_time_range(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        since = T0 + 5_000_000_000
        until = T0 + 25_000_000_000
        results = list(query.filter(since=since, until=until))
        assert len(results) == 4
        assert all(since <= r.timestamp_ns <= until for r in results)

    def test_combined_filters(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        results = list(
            query.filter(
                channel="depth_m",
                value_range=(72.0, 75.0),
                source="nmea0183",
                quality="good",
            )
        )
        assert len(results) == 3

    def test_filter_with_no_matches(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        results = list(query.filter(channel="nonexistent"))
        assert len(results) == 0

    def test_filter_handles_malformed_lines(self, tmp_path):
        log_path = tmp_path / "malformed.jsonl"
        with open(log_path, "w") as f:
            f.write('{"timestamp_ns": ' + str(T0) + ', "source": "nmea0183", "channel": "depth_m", "value": 73.2}\n')
            f.write('invalid json line\n')
            f.write('{"timestamp_ns": ' + str(T0 + 1) + ', "source": "nmea0183", "channel": "depth_m", "value": 74.5}\n')

        query = TelemetryQuery(log_path)
        results = list(query.filter())
        assert len(results) == 2

    def test_filter_handles_invalid_records(self, tmp_path):
        log_path = tmp_path / "invalid.jsonl"
        with open(log_path, "w") as f:
            f.write('{"timestamp_ns": ' + str(T0) + ', "source": "nmea0183", "channel": "depth_m", "value": 73.2}\n')
            f.write('{"source": "nmea0183"}\n')  # Missing required fields
            f.write('{"timestamp_ns": ' + str(T0 + 1) + ', "source": "nmea0183", "channel": "depth_m", "value": 74.5}\n')

        query = TelemetryQuery(log_path)
        results = list(query.filter())
        assert len(results) == 2


# --------------------------------------------------------------------- #
# Time bucketing
# --------------------------------------------------------------------- #


class TestTimeBucketing:
    """Time-bucketing functionality."""

    def test_time_bucket_basic(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        buckets = list(query.time_bucket(60).filter(channel="depth_m"))

        # All depth_m readings are within 40 seconds, so should be in one bucket
        assert len(buckets) == 1
        assert buckets[0].count == 5
        assert buckets[0].bucket_start_ns == T0

    def test_time_bucket_multiple_buckets(self, tmp_path):
        # Create records spanning multiple 30-second buckets
        records = [
            {"timestamp_ns": T0, "source": "test", "channel": "ch", "value": 1.0},
            {"timestamp_ns": T0 + 35_000_000_000, "source": "test", "channel": "ch", "value": 2.0},
            {"timestamp_ns": T0 + 65_000_000_000, "source": "test", "channel": "ch", "value": 3.0},
        ]
        log_path = write_test_log(tmp_path, records)

        query = TelemetryQuery(log_path)
        buckets = list(query.time_bucket(30).filter(channel="ch"))

        assert len(buckets) == 3
        assert buckets[0].count == 1
        assert buckets[1].count == 1
        assert buckets[2].count == 1

    def test_time_bucket_aggregations(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        buckets = list(query.time_bucket(60).filter(channel="depth_m"))

        bucket = buckets[0]
        assert bucket.count == 5
        assert bucket.min == 71.8
        assert bucket.max == 75.0
        assert pytest.approx(bucket.mean, 0.1) == 73.36

    def test_time_bucket_empty_filter(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        buckets = list(query.time_bucket(60).filter(channel="nonexistent"))
        assert len(buckets) == 0

    def test_time_bucket_with_time_filter(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        since = T0 + 15_000_000_000
        buckets = list(query.time_bucket(60).filter(channel="depth_m", since=since))

        assert len(buckets) == 1
        assert buckets[0].count == 3


# --------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------- #


class TestStatistics:
    """Statistics calculation functionality."""

    def test_stats_basic(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        stats = query.stats("value").filter(channel="depth_m")

        assert stats.count == 5
        assert stats.min == 71.8
        assert stats.max == 75.0
        assert pytest.approx(stats.mean, 0.1) == 73.36

    def test_stats_stddev(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        stats = query.stats("value").filter(channel="depth_m")

        # Expected stddev for [73.2, 74.5, 71.8, 75.0, 72.3]
        # mean = 73.36
        # variance = ((73.2-73.36)^2 + (74.5-73.36)^2 + (71.8-73.36)^2 + (75.0-73.36)^2 + (72.3-73.36)^2) / 5
        # stddev = sqrt(variance) ≈ 1.18
        assert pytest.approx(stats.stddev, 0.1) == 1.18

    def test_stats_single_value(self, tmp_path):
        records = [
            {"timestamp_ns": T0, "source": "test", "channel": "ch", "value": 42.0},
        ]
        log_path = write_test_log(tmp_path, records)
        query = TelemetryQuery(log_path)
        stats = query.stats("value").filter(channel="ch")

        assert stats.count == 1
        assert stats.min == 42.0
        assert stats.max == 42.0
        assert stats.mean == 42.0
        assert stats.stddev == 0.0

    def test_stats_empty_filter(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        stats = query.stats("value").filter(channel="nonexistent")

        assert stats.count == 0
        assert stats.min == 0.0
        assert stats.max == 0.0
        assert stats.mean == 0.0
        assert stats.stddev == 0.0

    def test_stats_execute_returns_result_object(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        calc = query.stats("value").filter(channel="depth_m")
        result = calc.execute()

        assert isinstance(result, StatsResult)
        assert result.count == 5

    def test_stats_result_object(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        result = query.stats("value").filter(channel="depth_m").result

        assert isinstance(result, StatsResult)
        assert result.count == 5


# --------------------------------------------------------------------- #
# Percentiles
# --------------------------------------------------------------------- #


class TestPercentiles:
    """Percentile calculation functionality."""

    def test_median(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        median = query.percentile("value", 50).filter(channel="depth_m")

        # Sorted depth values: [71.8, 72.3, 73.2, 74.5, 75.0]
        # Median (p50) of 5 values is the 3rd value: 73.2
        assert pytest.approx(median.value, 0.1) == 73.2

    def test_percentile_95(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        p95 = query.percentile("value", 95).filter(channel="depth_m")

        # p95 of 5 values: target_rank = 0.95 * 4 = 3.8
        # Interpolate between index 3 and 4: 74.5 and 75.0
        # 74.5 + 0.8 * (75.0 - 74.5) = 74.9
        assert pytest.approx(p95.value, 0.1) == 74.9

    def test_percentile_25(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        p25 = query.percentile("value", 25).filter(channel="depth_m")

        # p25 of 5 values: target_rank = 0.25 * 4 = 1.0
        # Exactly at index 1: 72.3
        assert pytest.approx(p25.value, 0.1) == 72.3

    def test_percentile_0_is_min(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        p0 = query.percentile("value", 0).filter(channel="depth_m")

        assert p0.value == 71.8  # Minimum value

    def test_percentile_100_is_max(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        p100 = query.percentile("value", 100).filter(channel="depth_m")

        assert p100.value == 75.0  # Maximum value

    def test_percentile_empty_filter(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)
        p50 = query.percentile("value", 50).filter(channel="nonexistent")

        assert p50.value == 0.0

    def test_invalid_percentile_raises(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)

        with pytest.raises(ValueError):
            query.percentile("value", -1)

        with pytest.raises(ValueError):
            query.percentile("value", 101)

    def test_percentile_single_value(self, tmp_path):
        records = [
            {"timestamp_ns": T0, "source": "test", "channel": "ch", "value": 42.0},
        ]
        log_path = write_test_log(tmp_path, records)
        query = TelemetryQuery(log_path)
        p50 = query.percentile("value", 50).filter(channel="ch")

        assert p50.value == 42.0

    def test_percentile_even_count(self, tmp_path):
        records = [
            {"timestamp_ns": T0, "source": "test", "channel": "ch", "value": 1.0},
            {"timestamp_ns": T0 + 1, "source": "test", "channel": "ch", "value": 2.0},
            {"timestamp_ns": T0 + 2, "source": "test", "channel": "ch", "value": 3.0},
            {"timestamp_ns": T0 + 3, "source": "test", "channel": "ch", "value": 4.0},
        ]
        log_path = write_test_log(tmp_path, records)
        query = TelemetryQuery(log_path)
        p50 = query.percentile("value", 50).filter(channel="ch")

        # Median of [1, 2, 3, 4]: target_rank = 0.5 * 3 = 1.5
        # Interpolate between index 1 and 2: 2.0 and 3.0
        # 2.0 + 0.5 * (3.0 - 2.0) = 2.5
        assert p50.value == 2.5


# --------------------------------------------------------------------- #
# Integration tests
# --------------------------------------------------------------------- #


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_filter_then_stats(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)

        # Filter good quality depth readings, then calculate stats
        stats = query.stats("value").filter(channel="depth_m", quality="good")

        assert stats.count == 4  # Only good quality
        assert stats.min == 71.8
        assert stats.max == 74.5

    def test_filter_then_percentile(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)

        # Filter by source and channel, then get median
        median = query.percentile("value", 50).filter(source="nmea0183", channel="depth_m")

        assert pytest.approx(median.value, 0.1) == 73.2

    def test_time_filter_then_bucket(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)

        # Filter time range, then bucket
        since = T0 + 5_000_000_000
        buckets = list(query.time_bucket(30).filter(channel="depth_m", since=since))

        # After filtering: depth readings at T0+10s, T0+20s, T0+30s, T0+40s
        # 30-second buckets: [T0+0s to T0+30s] and [T0+30s to T0+60s]
        # First bucket: readings at T0+10s (74.5) and T0+20s (71.8) = 2 readings
        # Second bucket: readings at T0+30s (75.0) and T0+40s (72.3) = 2 readings
        assert len(buckets) == 2
        assert buckets[0].count == 2
        assert buckets[1].count == 2

    def test_combined_filter_and_stats(self, tmp_path):
        log_path = write_test_log(tmp_path, sample_records())
        query = TelemetryQuery(log_path)

        stats = query.stats("value").filter(
            channel="depth_m",
            value_range=(72.0, 74.5),
            quality="good",
        )

        # Depth values in range [72.0, 74.5] with quality "good": 73.2, 74.5, 72.3 (3 values)
        assert stats.count == 3
        assert stats.min == 72.3
        assert stats.max == 74.5

    def test_large_dataset_streaming(self, tmp_path):
        """Test that streaming works without loading entire dataset into memory."""
        # Create 1000 records
        records = []
        for i in range(1000):
            records.append({
                "timestamp_ns": T0 + i * 1_000_000_000,
                "source": "test",
                "channel": "ch",
                "value": float(i),
            })

        log_path = write_test_log(tmp_path, records)
        query = TelemetryQuery(log_path)

        # Verify we can iterate without memory issues
        count = 0
        for record in query.filter():
            count += 1
            assert record.value == float(count - 1)

        assert count == 1000


# --------------------------------------------------------------------- #
# Edge cases
# --------------------------------------------------------------------- #


class TestEdgeCases:
    """Edge case handling."""

    def test_empty_log_file(self, tmp_path):
        log_path = tmp_path / "empty.jsonl"
        log_path.write_text("")
        query = TelemetryQuery(log_path)

        results = list(query.filter())
        assert len(results) == 0

    def test_log_with_only_blank_lines(self, tmp_path):
        log_path = tmp_path / "blank.jsonl"
        log_path.write_text("\n\n\n")
        query = TelemetryQuery(log_path)

        results = list(query.filter())
        assert len(results) == 0

    def test_negative_values(self, tmp_path):
        records = [
            {"timestamp_ns": T0, "source": "test", "channel": "ch", "value": -5.0},
            {"timestamp_ns": T0 + 1, "source": "test", "channel": "ch", "value": 10.0},
        ]
        log_path = write_test_log(tmp_path, records)
        query = TelemetryQuery(log_path)

        stats = query.stats("value").filter(channel="ch")
        assert stats.min == -5.0
        assert stats.max == 10.0

    def test_zero_values(self, tmp_path):
        records = [
            {"timestamp_ns": T0, "source": "test", "channel": "ch", "value": 0.0},
            {"timestamp_ns": T0 + 1, "source": "test", "channel": "ch", "value": 10.0},
        ]
        log_path = write_test_log(tmp_path, records)
        query = TelemetryQuery(log_path)

        stats = query.stats("value").filter(channel="ch")
        assert stats.min == 0.0
        assert stats.mean == 5.0
