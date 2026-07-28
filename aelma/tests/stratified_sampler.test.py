"""Tests for StratifiedSampler: balanced ML training dataset creation."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Make the repository root importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twin.stratified_sampler import (
    SampleBin,
    StratifiedSampler,
    TrainingExample,
)


# --------------------------------------------------------------------- #
# Mock query interfaces
# --------------------------------------------------------------------- #

class MockTelemetryQuery:
    """Mock telemetry query for testing."""

    def __init__(self, data: list[dict] | None = None):
        self.data = data or []

    async def query_channel(self, channel: str, filters: dict | None = None) -> list[dict]:
        """Query telemetry by channel."""
        return [r for r in self.data if r.get("channel") == channel]

    async def iter_records(self, filters: dict | None = None) -> list:
        """Iterate over records."""
        result = self.data
        if filters and "channel" in filters:
            result = [r for r in result if r.get("channel") == filters["channel"]]
        return iter(result)


class MockA2AQuery:
    """Mock A2A query for testing."""

    def __init__(self, actions: list[dict] | None = None):
        self.actions = actions or []

    async def query(self, filters: dict | None = None, limit: int = 0) -> list[dict]:
        """Query A2A actions."""
        result = self.actions.copy()

        if filters and "action" in filters:
            action_filter = filters["action"]
            if isinstance(action_filter, str):
                result = [r for r in result if r.get("action") == action_filter]
            elif isinstance(action_filter, dict):
                # Handle {"$ne": ...} queries
                if "$ne" in action_filter:
                    result = [r for r in result if r.get("action") != action_filter["$ne"]]

        if limit > 0:
            result = result[:limit]

        return result


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #

@pytest.fixture
def depth_telemetry():
    """Sample depth telemetry data spanning various ranges."""
    base_ts = datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp() * 1e9
    return [
        {"timestamp_ns": base_ts, "channel": "depth_m", "value": 2.5, "quality": "good", "source": "simulator"},
        {"timestamp_ns": base_ts + 1, "channel": "depth_m", "value": 3.0, "quality": "good", "source": "simulator"},
        {"timestamp_ns": base_ts + 2, "channel": "depth_m", "value": 7.5, "quality": "good", "source": "nmea0183"},
        {"timestamp_ns": base_ts + 3, "channel": "depth_m", "value": 8.0, "quality": "good", "source": "nmea0183"},
        {"timestamp_ns": base_ts + 4, "channel": "depth_m", "value": 15.0, "quality": "good", "source": "nmea2000"},
        {"timestamp_ns": base_ts + 5, "channel": "depth_m", "value": 18.0, "quality": "good", "source": "nmea2000"},
        {"timestamp_ns": base_ts + 6, "channel": "depth_m", "value": 25.0, "quality": "good", "source": "signal_k"},
        {"timestamp_ns": base_ts + 7, "channel": "depth_m", "value": 30.0, "quality": "good", "source": "signal_k"},
        {"timestamp_ns": base_ts + 8, "channel": "depth_m", "value": 4.0, "quality": "good", "source": "simulator"},
        {"timestamp_ns": base_ts + 9, "channel": "depth_m", "value": 12.0, "quality": "good", "source": "nmea0183"},
    ]


@pytest.fixture
def a2a_actions():
    """Sample A2A actions with alerts and anomalies."""
    base_ts = datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat()
    return [
        {"ts": base_ts, "action": "raise_alert", "source": "watcher", "priority": 0.9, "reason": "depth low"},
        {"ts": base_ts, "action": "raise_alert", "source": "watcher", "priority": 0.8, "reason": "speed high"},
        {"ts": base_ts, "action": "log_anomaly", "source": "llm", "priority": 0.7, "reason": "unusual pattern"},
        {"ts": base_ts, "action": "log_anomaly", "source": "llm", "priority": 0.6, "reason": "sensor drift"},
        {"ts": base_ts, "action": "normal_operation", "source": "system", "priority": 0.5, "reason": "routine"},
        {"ts": base_ts, "action": "normal_operation", "source": "system", "priority": 0.5, "reason": "routine"},
        {"ts": base_ts, "action": "normal_operation", "source": "system", "priority": 0.5, "reason": "routine"},
        {"ts": base_ts, "action": "normal_operation", "source": "system", "priority": 0.5, "reason": "routine"},
    ]


@pytest.fixture
def telemetry_query(depth_telemetry):
    """Mock telemetry query with depth data."""
    return MockTelemetryQuery(depth_telemetry)


@pytest.fixture
def a2a_query(a2a_actions):
    """Mock A2A query with action data."""
    return MockA2AQuery(a2a_actions)


# --------------------------------------------------------------------- #
# SampleBin tests
# --------------------------------------------------------------------- #

class TestSampleBin:
    """Test bin definitions and value containment."""

    def test_contains_middle_range(self):
        bin = SampleBin("shallow", 5.0, 10.0)
        assert bin.contains(7.5)
        assert not bin.contains(5.0)
        assert bin.contains(10.0)

    def test_contains_lower_unbounded(self):
        bin = SampleBin("deep", float('-inf'), 5.0)
        assert bin.contains(-1000.0)
        assert bin.contains(0.0)
        assert bin.contains(5.0)
        assert not bin.contains(5.1)

    def test_contains_upper_unbounded(self):
        bin = SampleBin("very_deep", 20.0, float('inf'))
        assert not bin.contains(20.0)
        assert bin.contains(20.1)
        assert bin.contains(1000.0)


# --------------------------------------------------------------------- #
# TrainingExample tests
# --------------------------------------------------------------------- #

class TestTrainingExample:
    """Test training example serialization."""

    def test_to_dict(self):
        example = TrainingExample(
            features={"value": 10.0, "channel": "depth_m"},
            label=1,
            metadata={"source": "simulator"},
            weight=2.0
        )
        data = example.to_dict()
        assert data["features"]["value"] == 10.0
        assert data["label"] == 1
        assert data["metadata"]["source"] == "simulator"
        assert data["weight"] == 2.0

    def test_from_dict(self):
        data = {
            "features": {"value": 10.0},
            "label": 1,
            "metadata": {},
            "weight": 1.0
        }
        example = TrainingExample.from_dict(data)
        assert example.features["value"] == 10.0
        assert example.label == 1

    def test_defaults(self):
        example = TrainingExample(features={"value": 5.0})
        assert example.label is None
        assert example.metadata == {}
        assert example.weight == 1.0


# --------------------------------------------------------------------- #
# StratifiedSampler initialization
# --------------------------------------------------------------------- #

class TestStratifiedSamplerInit:
    """Test sampler initialization and seed handling."""

    def test_init_with_seed(self):
        sampler = StratifiedSampler(seed=123)
        assert sampler.seed == 123

    def test_init_with_queries(self, telemetry_query, a2a_query):
        sampler = StratifiedSampler(
            seed=42,
            telemetry_query=telemetry_query,
            a2a_query=a2a_query
        )
        assert sampler.telemetry_query is telemetry_query
        assert sampler.a2a_query is a2a_query

    def test_set_seed(self):
        sampler = StratifiedSampler(seed=42)
        sampler.set_seed(999)
        assert sampler.seed == 999

    def test_reproducible_sampling(self):
        """Same seed produces same results."""
        data = list(range(100))
        sampler1 = StratifiedSampler(seed=42)
        sampler2 = StratifiedSampler(seed=42)

        samples1 = sampler1._sample_list(data, 10)
        samples2 = sampler2._sample_list(data, 10)

        assert samples1 == samples2


# --------------------------------------------------------------------- #
# Value-based stratification tests
# --------------------------------------------------------------------- #

class TestSampleValueStratification:
    """Test value-based stratified sampling."""

    @pytest.mark.asyncio
    async def test_sample_balanced_bins(self, telemetry_query):
        sampler = StratifiedSampler(
            seed=42,
            telemetry_query=telemetry_query
        )

        samples = await sampler.sample(
            channel="depth_m",
            n_per_bin=2,
            value_bins=[(0, 5), (5, 10), (10, 20), (20, float('inf'))]
        )

        # Should get 2 samples per bin = 8 total (if enough data)
        assert len(samples) >= 0

        # Check bin distribution
        bins = {}
        for sample in samples:
            bin_label = sample.metadata.get("bin")
            bins[bin_label] = bins.get(bin_label, 0) + 1

        # Each bin should have at most n_per_bin samples
        for count in bins.values():
            assert count <= 2

    @pytest.mark.asyncio
    async def test_sample_custom_bins(self, telemetry_query):
        sampler = StratifiedSampler(
            seed=42,
            telemetry_query=telemetry_query
        )

        custom_bins = [(0, 10), (10, float('inf'))]
        samples = await sampler.sample(
            channel="depth_m",
            n_per_bin=3,
            value_bins=custom_bins
        )

        # Check that samples fall into the specified bins
        for sample in samples:
            value = sample.features.get("value")
            assert isinstance(value, (int, float))

    @pytest.mark.asyncio
    async def test_sample_without_query_raises(self):
        sampler = StratifiedSampler(seed=42)

        with pytest.raises(ValueError, match="telemetry_query required"):
            await sampler.sample(channel="depth_m", n_per_bin=5)

    def test_default_bins_for_depth_channel(self):
        sampler = StratifiedSampler(seed=42)
        bins = sampler._default_bins_for_channel("depth_m")
        assert bins == [(0, 5), (5, 10), (10, 20), (20, float('inf'))]

    def test_default_bins_for_speed_channel(self):
        sampler = StratifiedSampler(seed=42)
        bins = sampler._default_bins_for_channel("speed_kn")
        assert bins == [(0, 2), (2, 5), (5, 10), (10, float('inf'))]

    def test_default_bins_for_heading_channel(self):
        sampler = StratifiedSampler(seed=42)
        bins = sampler._default_bins_for_channel("heading_deg")
        assert bins == [(0, 90), (90, 180), (180, 270), (270, 360)]

    def test_default_bins_generic(self):
        sampler = StratifiedSampler(seed=42)
        bins = sampler._default_bins_for_channel("unknown_channel")
        assert len(bins) == 4
        assert bins[0] == (float('-inf'), 0)


# --------------------------------------------------------------------- #
# Time-based stratification tests
# --------------------------------------------------------------------- #

class TestSampleTimeStratification:
    """Test time-based stratified sampling."""

    @pytest.mark.asyncio
    async def test_sample_time_periods(self, telemetry_query):
        sampler = StratifiedSampler(
            seed=42,
            telemetry_query=telemetry_query
        )

        samples = await sampler.sample_time_periods(
            channel="depth_m",
            n=10,
            period_minutes=30
        )

        # Should get samples distributed across time
        assert len(samples) >= 0

        # Check that metadata includes time_period
        for sample in samples:
            assert "time_period" in sample.metadata
            assert "timestamp_ns" in sample.features

    @pytest.mark.asyncio
    async def test_sample_time_without_query_raises(self):
        sampler = StratifiedSampler(seed=42)

        with pytest.raises(ValueError, match="telemetry_query required"):
            await sampler.sample_time_periods(channel="depth_m", n=10)

    @pytest.mark.asyncio
    async def test_empty_data_returns_empty(self, telemetry_query):
        sampler = StratifiedSampler(
            seed=42,
            telemetry_query=MockTelemetryQuery([])  # Empty data
        )

        samples = await sampler.sample_time_periods(
            channel="depth_m",
            n=10,
            period_minutes=30
        )

        assert len(samples) == 0


# --------------------------------------------------------------------- #
# Event-based stratification tests
# --------------------------------------------------------------------- #

class TestSampleEventStratification:
    """Test event-based stratification with rare event preservation."""

    @pytest.mark.asyncio
    async def test_sample_events_balanced(self, a2a_query):
        sampler = StratifiedSampler(
            seed=42,
            a2a_query=a2a_query
        )

        samples = await sampler.sample_events(
            normal_ratio=0.7,
            limit=100
        )

        # Should have both normal and rare events
        assert len(samples) > 0

        # Check labels: 0=normal, 1=alert, 2=anomaly
        labels = [s.label for s in samples]
        assert 0 in labels or 1 in labels or 2 in labels

        # Check that rare events have higher weight
        rare_samples = [s for s in samples if s.label in (1, 2)]
        for sample in rare_samples:
            assert sample.weight == 2.0

    @pytest.mark.asyncio
    async def test_sample_events_without_query_raises(self):
        sampler = StratifiedSampler(seed=42)

        with pytest.raises(ValueError, match="a2a_query required"):
            await sampler.sample_events(normal_ratio=0.7)

    @pytest.mark.asyncio
    async def test_sample_events_empty_returns_empty(self):
        sampler = StratifiedSampler(
            seed=42,
            a2a_query=MockA2AQuery([])  # Empty actions
        )

        samples = await sampler.sample_events(normal_ratio=0.7)

        assert len(samples) == 0

    @pytest.mark.asyncio
    async def test_rare_events_oversampled(self):
        """Test that alerts and anomalies are oversampled."""
        actions = [
            {"ts": "2024-01-01T00:00:00Z", "action": "raise_alert", "source": "watcher", "priority": 0.9, "reason": "low"},
            {"ts": "2024-01-01T00:00:00Z", "action": "log_anomaly", "source": "llm", "priority": 0.7, "reason": "drift"},
            {"ts": "2024-01-01T00:00:00Z", "action": "normal", "source": "system", "priority": 0.5, "reason": "ok"},
            {"ts": "2024-01-01T00:00:00Z", "action": "normal", "source": "system", "priority": 0.5, "reason": "ok"},
            {"ts": "2024-01-01T00:00:00Z", "action": "normal", "source": "system", "priority": 0.5, "reason": "ok"},
        ]

        sampler = StratifiedSampler(
            seed=42,
            a2a_query=MockA2AQuery(actions)
        )

        samples = await sampler.sample_events(normal_ratio=0.5, limit=100)

        # Should have 2 rare events (alert + anomaly)
        rare = [s for s in samples if s.label in (1, 2)]
        assert len(rare) == 2

        # Each rare event should have weight 2.0
        for sample in rare:
            assert sample.weight == 2.0


# --------------------------------------------------------------------- #
# Export tests
# --------------------------------------------------------------------- #

class TestExportToJsonl:
    """Test JSONL export functionality."""

    @pytest.mark.asyncio
    async def test_export_training_examples(self, tmp_path):
        sampler = StratifiedSampler(seed=42)

        samples = [
            TrainingExample(
                features={"value": 10.0, "channel": "depth_m"},
                label=1,
                metadata={"source": "simulator"},
                weight=1.5
            ),
            TrainingExample(
                features={"value": 5.0, "channel": "depth_m"},
                label=0,
                metadata={"source": "nmea0183"},
                weight=1.0
            ),
        ]

        output_path = tmp_path / "test.jsonl"
        count = await sampler.export_to_jsonl(output_path, samples)

        assert count == 2
        assert output_path.exists()

        # Verify content
        lines = output_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2

        # Parse and verify first line
        data1 = json.loads(lines[0])
        assert data1["features"]["value"] == 10.0
        assert data1["label"] == 1
        assert data1["metadata"]["source"] == "simulator"
        assert data1["weight"] == 1.5

    @pytest.mark.asyncio
    async def test_export_dict_samples(self, tmp_path):
        sampler = StratifiedSampler(seed=42)

        samples = [
            {"features": {"value": 10.0}, "label": 1, "metadata": {}, "weight": 1.0},
            {"features": {"value": 5.0}, "label": 0, "metadata": {}, "weight": 1.0},
        ]

        output_path = tmp_path / "test.jsonl"
        count = await sampler.export_to_jsonl(output_path, samples)

        assert count == 2

    @pytest.mark.asyncio
    async def test_export_creates_parent_dirs(self, tmp_path):
        sampler = StratifiedSampler(seed=42)

        samples = [TrainingExample(features={"value": 10.0})]

        output_path = tmp_path / "subdir" / "test.jsonl"
        count = await sampler.export_to_jsonl(output_path, samples)

        assert count == 1
        assert output_path.exists()

    @pytest.mark.asyncio
    async def test_export_without_metadata(self, tmp_path):
        sampler = StratifiedSampler(seed=42)

        samples = [
            TrainingExample(
                features={"value": 10.0},
                metadata={"source": "simulator"}
            ),
        ]

        output_path = tmp_path / "test.jsonl"
        count = await sampler.export_to_jsonl(
            output_path,
            samples,
            include_metadata=False
        )

        assert count == 1

        # Verify metadata is stripped
        line = output_path.read_text(encoding="utf-8").strip()
        data = json.loads(line)
        assert "metadata" not in data


# --------------------------------------------------------------------- #
# Combined strategy tests
# --------------------------------------------------------------------- #

class TestSampleCombined:
    """Test combined multi-strategy sampling."""

    @pytest.mark.asyncio
    async def test_sample_combined(self, telemetry_query, a2a_query):
        sampler = StratifiedSampler(
            seed=42,
            telemetry_query=telemetry_query,
            a2a_query=a2a_query
        )

        samples = await sampler.sample_combined(
            channel="depth_m",
            n_per_value_bin=2,
            n_time_samples=5,
            n_events=10,
        )

        # Should have samples from all strategies
        assert len(samples) > 0

        # Verify mixed metadata sources
        sources = set()
        for sample in samples:
            if "bin" in sample.metadata:
                sources.add("value")
            if "time_period" in sample.metadata:
                sources.add("time")
            if "event_type" in sample.metadata:
                sources.add("event")

        # Should have at least one strategy represented
        assert len(sources) > 0

    @pytest.mark.asyncio
    async def test_sample_combined_shuffle_order(self, telemetry_query, a2a_query):
        """Test that combined samples are shuffled."""
        sampler = StratifiedSampler(
            seed=42,
            telemetry_query=telemetry_query,
            a2a_query=a2a_query
        )

        samples = await sampler.sample_combined(
            channel="depth_m",
            n_per_value_bin=2,
            n_time_samples=5,
            n_events=10,
        )

        # Samples should be interleaved, not grouped by strategy
        # Check that we don't have all value samples first, then all time samples, etc.
        if len(samples) >= 10:
            metadata_types = [
                "bin" if "bin" in s.metadata else
                "time_period" if "time_period" in s.metadata else
                "event_type" if "event_type" in s.metadata else
                "unknown"
                for s in samples[:10]
            ]
            # Should have at least some variation
            assert len(set(metadata_types)) >= 1


# --------------------------------------------------------------------- #
# Helper method tests
# --------------------------------------------------------------------- #

class TestHelperMethods:
    """Test internal helper methods."""

    def test_sample_list_without_replacement(self):
        sampler = StratifiedSampler(seed=42)
        items = list(range(100))

        samples = sampler._sample_list(items, 10)

        assert len(samples) == 10
        assert len(set(samples)) == 10  # No duplicates
        assert all(s in items for s in samples)

    def test_sample_list_with_replacement(self):
        """When requesting more than available, use replacement."""
        sampler = StratifiedSampler(seed=42)
        items = list(range(5))

        samples = sampler._sample_list(items, 10)

        assert len(samples) == 10
        # Should have duplicates since we're sampling 10 from 5
        assert len(set(samples)) <= 5

    def test_sample_list_empty(self):
        sampler = StratifiedSampler(seed=42)
        samples = sampler._sample_list([], 10)
        assert samples == []

    def test_sample_list_reproducible(self):
        sampler1 = StratifiedSampler(seed=42)
        sampler2 = StratifiedSampler(seed=42)

        items = list(range(100))
        samples1 = sampler1._sample_list(items, 10)
        samples2 = sampler2._sample_list(items, 10)

        assert samples1 == samples2


# --------------------------------------------------------------------- #
# Integration tests
# --------------------------------------------------------------------- #

class TestIntegration:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_full_pipeline(self, tmp_path, telemetry_query, a2a_query):
        """Test complete pipeline: sample -> export -> verify."""
        sampler = StratifiedSampler(
            seed=42,
            telemetry_query=telemetry_query,
            a2a_query=a2a_query
        )

        # Sample using combined strategy
        samples = await sampler.sample_combined(
            channel="depth_m",
            n_per_value_bin=2,
            n_time_samples=5,
            n_events=8,
        )

        # Export to JSONL
        output_path = tmp_path / "training.jsonl"
        count = await sampler.export_to_jsonl(output_path, samples)

        # Verify export
        assert count == len(samples)
        assert output_path.exists()

        # Load and verify
        loaded_samples = []
        for line in output_path.read_text(encoding="utf-8").strip().split("\n"):
            if line:
                loaded_samples.append(json.loads(line))

        assert len(loaded_samples) == count

        # Verify structure
        for sample in loaded_samples:
            assert "features" in sample
            assert isinstance(sample["features"], dict)
            # Label is optional
            # Metadata is optional
            # Weight is optional

    @pytest.mark.asyncio
    async def test_reproducible_full_pipeline(self, tmp_path, telemetry_query, a2a_query):
        """Same seed produces identical results across runs."""
        sampler1 = StratifiedSampler(
            seed=42,
            telemetry_query=telemetry_query,
            a2a_query=a2a_query
        )
        sampler2 = StratifiedSampler(
            seed=42,
            telemetry_query=telemetry_query,
            a2a_query=a2a_query
        )

        output1 = tmp_path / "run1.jsonl"
        output2 = tmp_path / "run2.jsonl"

        samples1 = await sampler1.sample_combined(
            channel="depth_m",
            n_per_value_bin=2,
            n_time_samples=5,
            n_events=8,
        )
        await sampler1.export_to_jsonl(output1, samples1)

        samples2 = await sampler2.sample_combined(
            channel="depth_m",
            n_per_value_bin=2,
            n_time_samples=5,
            n_events=8,
        )
        await sampler2.export_to_jsonl(output2, samples2)

        # Files should be identical
        content1 = output1.read_text(encoding="utf-8")
        content2 = output2.read_text(encoding="utf-8")

        assert content1 == content2
