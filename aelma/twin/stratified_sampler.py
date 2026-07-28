"""StratifiedSampler: balanced ML training dataset creation from telemetry.

Provides stratified sampling strategies for creating balanced training datasets
from AELMA telemetry and A2A action logs. Preserves rare events (alerts, anomalies)
while ensuring representation across value ranges, time periods, and event types.

Example::

    sampler = StratifiedSampler(
        telemetry_query=telemetry_query,
        a2a_query=a2a_query,
        seed=42  # reproducible sampling
    )

    # Sample depth readings balanced across depth ranges
    samples = await sampler.sample(
        channel="depth_m",
        n_per_bin=10,
        value_bins=[(0, 5), (5, 10), (10, 20), (20, float('inf'))]
    )

    # Sample evenly across time periods
    time_samples = await sampler.sample_time_periods(
        n=100,
        period_minutes=30
    )

    # Export to ML format (JSONL)
    await sampler.export_to_jsonl(
        output_path="training_dataset.jsonl",
        samples=combined_samples
    )
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Try to import A2AQuery if available
try:
    from .a2a_query import A2AQuery
except ImportError:
    A2AQuery = None  # type: ignore


@dataclass
class SampleBin:
    """A bin for stratified sampling.

    Attributes:
        label: Human-readable bin label
        min_val: Minimum value (exclusive)
        max_val: Maximum value (inclusive, use inf for unbounded)
    """
    label: str
    min_val: float
    max_val: float

    def contains(self, value: float) -> bool:
        """Check if a value falls within this bin."""
        if self.min_val == float('-inf'):
            return value <= self.max_val
        if self.max_val == float('inf'):
            return value > self.min_val
        return self.min_val < value <= self.max_val


@dataclass
class TrainingExample:
    """A single training example with features and label.

    Attributes:
        features: Dict of feature values (telemetry readings, context)
        label: Optional label for supervised learning (e.g., anomaly=True)
        metadata: Optional metadata (timestamp, source, etc.)
        weight: Optional sample weight for loss calculation
    """
    features: dict[str, Any]
    label: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "features": self.features,
            "label": self.label,
            "metadata": self.metadata,
            "weight": self.weight
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrainingExample":
        """Create from dictionary."""
        return cls(
            features=data["features"],
            label=data.get("label"),
            metadata=data.get("metadata", {}),
            weight=data.get("weight", 1.0)
        )


class StratifiedSampler:
    """Balanced sampling for ML training datasets from telemetry.

    Supports multiple stratification strategies:
    - Value-based: bin telemetry by value ranges
    - Time-based: sample evenly across time periods
    - Event-based: oversample rare events (alerts, anomalies)
    - Combined: multi-dimensional stratification

    All sampling is reproducible with a fixed random seed.
    """

    def __init__(
        self,
        seed: int = 42,
        telemetry_query: Any = None,
        a2a_query: A2AQuery | None = None
    ) -> None:
        """Initialize the sampler.

        Args:
            seed: Random seed for reproducible sampling
            telemetry_query: Optional telemetry query interface
            a2a_query: Optional A2A query interface for event sampling
        """
        self.seed = seed
        self._rng = random.Random(seed)
        self.telemetry_query = telemetry_query
        self.a2a_query = a2a_query

    # ------------------------------------------------------------------ #
    # Value-based stratification
    # ------------------------------------------------------------------ #

    async def sample(
        self,
        channel: str,
        n_per_bin: int,
        value_bins: list[tuple[float, float]] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[TrainingExample]:
        """Sample telemetry values balanced across bins.

        Args:
            channel: Telemetry channel to sample (e.g., "depth_m")
            n_per_bin: Number of samples to draw per bin
            value_bins: List of (min, max) tuples defining bins.
                        Defaults to sensible bins based on channel.
            filters: Optional filters for telemetry query

        Returns:
            List of TrainingExample instances balanced across bins

        Example::
            sampler.sample(
                channel="depth_m",
                n_per_bin=10,
                value_bins=[(0, 5), (5, 10), (10, 20), (20, float('inf'))]
            )
        """
        if value_bins is None:
            value_bins = self._default_bins_for_channel(channel)

        bins = [SampleBin(f"bin_{i}", min_v, max_v) for i, (min_v, max_v) in enumerate(value_bins)]

        if self.telemetry_query is None:
            raise ValueError("telemetry_query required for sample()")

        # Fetch all channel data
        all_data = await self._fetch_telemetry(channel, filters)

        # Bin the data
        binned_data: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in all_data:
            value = record.get("value")
            if isinstance(value, (int, float)):
                for bin_def in bins:
                    if bin_def.contains(float(value)):
                        binned_data[bin_def.label].append(record)
                        break

        # Sample from each bin
        examples: list[TrainingExample] = []
        for bin_def in bins:
            bin_records = binned_data.get(bin_def.label, [])
            sampled = self._sample_list(bin_records, n_per_bin)

            for record in sampled:
                examples.append(TrainingExample(
                    features={
                        "value": record.get("value"),
                        "channel": channel,
                        "timestamp_ns": record.get("timestamp_ns"),
                        "quality": record.get("quality", "good"),
                    },
                    metadata={
                        "source": record.get("source"),
                        "bin": bin_def.label,
                    }
                ))

        return examples

    def _default_bins_for_channel(self, channel: str) -> list[tuple[float, float]]:
        """Get default bins for common channels."""
        if channel == "depth_m":
            return [(0, 5), (5, 10), (10, 20), (20, float('inf'))]
        elif channel in ["speed_kn", "speed_over_ground_kn"]:
            return [(0, 2), (2, 5), (5, 10), (10, float('inf'))]
        elif channel in ["heading_deg", "heading_true_deg"]:
            return [(0, 90), (90, 180), (180, 270), (270, 360)]
        else:
            # Generic bins: percentiles
            return [(float('-inf'), 0), (0, 50), (50, 100), (100, float('inf'))]

    # ------------------------------------------------------------------ #
    # Time-based stratification
    # ------------------------------------------------------------------ #

    async def sample_time_periods(
        self,
        channel: str,
        n: int,
        period_minutes: int = 30,
        filters: dict[str, Any] | None = None,
    ) -> list[TrainingExample]:
        """Sample evenly across time periods.

        Ensures temporal diversity by dividing the time range into periods
        and sampling evenly from each.

        Args:
            channel: Telemetry channel to sample
            n: Total number of samples desired
            period_minutes: Length of each time period in minutes
            filters: Optional filters for telemetry query

        Returns:
            List of TrainingExample instances evenly distributed across time

        Example::
            sampler.sample_time_periods(
                channel="depth_m",
                n=100,
                period_minutes=30  # 30-minute periods
            )
        """
        if self.telemetry_query is None:
            raise ValueError("telemetry_query required for sample_time_periods()")

        # Fetch all data
        all_data = await self._fetch_telemetry(channel, filters)

        if not all_data:
            return []

        # Determine time range
        timestamps = [r.get("timestamp_ns") for r in all_data if r.get("timestamp_ns") is not None]
        if not timestamps:
            return []

        min_ts = min(timestamps)
        max_ts = max(timestamps)
        period_ns = period_minutes * 60 * 1_000_000_000

        # Create time periods
        num_periods = max(1, int((max_ts - min_ts) / period_ns) + 1)
        samples_per_period = max(1, n // num_periods)

        # Bin by time period
        period_data: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for record in all_data:
            ts = record.get("timestamp_ns")
            if ts is not None:
                period_idx = int((ts - min_ts) / period_ns)
                period_data[period_idx].append(record)

        # Sample from each period
        examples: list[TrainingExample] = []
        for period_idx in sorted(period_data.keys()):
            records = period_data[period_idx]
            sampled = self._sample_list(records, samples_per_period)

            for record in sampled:
                examples.append(TrainingExample(
                    features={
                        "value": record.get("value"),
                        "channel": channel,
                        "timestamp_ns": record.get("timestamp_ns"),
                        "quality": record.get("quality", "good"),
                    },
                    metadata={
                        "source": record.get("source"),
                        "time_period": period_idx,
                    }
                ))

        return examples

    # ------------------------------------------------------------------ #
    # Event-based stratification (rare event preservation)
    # ------------------------------------------------------------------ #

    async def sample_events(
        self,
        normal_ratio: float = 0.7,
        alert_action: str = "raise_alert",
        anomaly_action: str = "log_anomaly",
        limit: int = 1000,
    ) -> list[TrainingExample]:
        """Sample A2A events with oversampling of rare events.

        Ensures alerts and anomalies are well-represented in the training set.

        Args:
            normal_ratio: Target ratio of normal to alert/anomaly events (0.7 = 70% normal)
            alert_action: Action name for alerts (default: "raise_alert")
            anomaly_action: Action name for anomalies (default: "log_anomaly")
            limit: Maximum total samples

        Returns:
            List of TrainingExample instances with balanced event types

        Example::
            sampler.sample_events(
                normal_ratio=0.7,
                limit=1000  # 700 normal, 300 alerts/anomalies
            )
        """
        if self.a2a_query is None:
            raise ValueError("a2a_query required for sample_events()")

        # Fetch alerts and anomalies
        alerts = await self.a2a_query.query({"action": alert_action}, limit=limit)
        anomalies = await self.a2a_query.query({"action": anomaly_action}, limit=limit)

        rare_events = alerts + anomalies

        # Calculate desired counts
        rare_count = len(rare_events)
        if rare_count == 0:
            # No rare events, return empty
            return []

        normal_count = int(rare_count * (normal_ratio / (1 - normal_ratio)))
        normal_count = min(normal_count, limit - rare_count)

        # Fetch normal events (not alerts or anomalies)
        normal = await self.a2a_query.query(
            {"action": {"$ne": alert_action, "$ne": anomaly_action}},
            limit=normal_count
        )

        # Build training examples
        examples: list[TrainingExample] = []

        # Rare events with higher weight
        for record in rare_events:
            label = 1 if record.get("action") == alert_action else 2
            examples.append(TrainingExample(
                features={
                    "action": record.get("action"),
                    "source": record.get("source"),
                    "priority": record.get("priority", 0.5),
                    "reason": record.get("reason", ""),
                    "timestamp_ns": record.get("ts"),
                },
                label=label,
                metadata={
                    "event_type": "rare",
                    "source": record.get("source"),
                },
                weight=2.0  # Upweight rare events
            ))

        # Normal events
        for record in normal:
            examples.append(TrainingExample(
                features={
                    "action": record.get("action"),
                    "source": record.get("source"),
                    "priority": record.get("priority", 0.5),
                    "reason": record.get("reason", ""),
                    "timestamp_ns": record.get("ts"),
                },
                label=0,  # Normal = 0
                metadata={
                    "event_type": "normal",
                    "source": record.get("source"),
                },
                weight=1.0
            ))

        # Shuffle for randomness
        self._rng.shuffle(examples)

        return examples[:limit]

    # ------------------------------------------------------------------ #
    # Export to ML format
    # ------------------------------------------------------------------ #

    async def export_to_jsonl(
        self,
        output_path: str | Path,
        samples: list[TrainingExample] | list[dict[str, Any]],
        *,
        include_metadata: bool = True,
    ) -> int:
        """Export samples to JSONL format for ML training.

        Args:
            output_path: Path to output JSONL file
            samples: List of TrainingExample or dict objects
            include_metadata: Whether to include metadata field in output

        Returns:
            Number of records written

        Example::
            await sampler.export_to_jsonl(
                "training_dataset.jsonl",
                samples=depth_samples + alert_samples
            )
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        count = 0
        with output_path.open("w", encoding="utf-8") as f:
            for sample in samples:
                # Convert TrainingExample to dict if needed
                if isinstance(sample, TrainingExample):
                    data = sample.to_dict()
                else:
                    data = sample

                # Optionally strip metadata
                if not include_metadata and "metadata" in data:
                    data = {k: v for k, v in data.items() if k != "metadata"}

                f.write(json.dumps(data) + "\n")
                count += 1

        return count

    # ------------------------------------------------------------------ #
    # Combined strategies
    # ------------------------------------------------------------------ #

    async def sample_combined(
        self,
        channel: str,
        n_per_value_bin: int = 5,
        time_period_minutes: int = 30,
        n_time_samples: int = 50,
        n_events: int = 100,
        normal_ratio: float = 0.7,
        value_bins: list[tuple[float, float]] | None = None,
    ) -> list[TrainingExample]:
        """Sample using multiple strategies combined.

        Creates a diverse training dataset with:
        - Value-stratified telemetry samples
        - Time-stratified telemetry samples
        - Event-stratified A2A samples (alerts, anomalies)

        Args:
            channel: Telemetry channel for value/time sampling
            n_per_value_bin: Samples per value bin
            time_period_minutes: Time period length in minutes
            n_time_samples: Total time-stratified samples
            n_events: Total event samples
            normal_ratio: Ratio of normal to rare events
            value_bins: Optional custom value bins

        Returns:
            Combined list of TrainingExample instances

        Example::
            samples = await sampler.sample_combined(
                channel="depth_m",
                n_per_value_bin=10,
                n_events=500
            )
        """
        all_samples: list[TrainingExample] = []

        # Value-stratified samples
        if self.telemetry_query is not None:
            value_samples = await self.sample(
                channel=channel,
                n_per_bin=n_per_value_bin,
                value_bins=value_bins
            )
            all_samples.extend(value_samples)

            # Time-stratified samples
            time_samples = await self.sample_time_periods(
                channel=channel,
                n=n_time_samples,
                period_minutes=time_period_minutes
            )
            all_samples.extend(time_samples)

        # Event-stratified samples
        if self.a2a_query is not None:
            event_samples = await self.sample_events(
                normal_ratio=normal_ratio,
                limit=n_events
            )
            all_samples.extend(event_samples)

        # Shuffle to mix strategies
        self._rng.shuffle(all_samples)

        return all_samples

    # ------------------------------------------------------------------ #
    # Helper methods
    # ------------------------------------------------------------------ #

    async def _fetch_telemetry(
        self,
        channel: str,
        filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Fetch telemetry data for a channel.

        Must be implemented by the concrete telemetry query interface.
        This is a placeholder for the expected interface.
        """
        if self.telemetry_query is None:
            return []

        # Try to query if it has the right interface
        if hasattr(self.telemetry_query, 'query_channel'):
            return await self.telemetry_query.query_channel(channel, filters or {})
        elif hasattr(self.telemetry_query, 'iter_records'):
            records = []
            async for rec in self.telemetry_query.iter_records({"channel": channel, **(filters or {})}):
                records.append(rec)
            return records
        else:
            raise ValueError("telemetry_query must implement query_channel() or iter_records()")

    def _sample_list(self, items: list[Any], n: int) -> list[Any]:
        """Sample n items from a list without replacement.

        If n > len(items), returns all items (with replacement for remaining).
        """
        if not items:
            return []

        m = len(items)
        if n <= m:
            return self._rng.sample(items, n)
        else:
            # Return all items plus random samples to fill quota
            result = items.copy()
            remaining = n - m
            result.extend(self._rng.choices(items, k=remaining))
            return result

    def set_seed(self, seed: int) -> None:
        """Reset random seed for reproducibility."""
        self.seed = seed
        self._rng = random.Random(seed)
