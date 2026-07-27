"""Telemetry query analytics layer for AELMA.

Provides streaming analytics over JSONL telemetry logs, inspired by the
mini-agent's a2aQuery pattern. Supports filtering, time-bucketing, statistics,
and percentile calculations without loading entire logs into memory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Generator

try:
    from functools import cached_property
except ImportError:
    # Python < 3.8 fallback
    cached_property = property  # type: ignore


@dataclass
class TelemetryRecord:
    """A single telemetry packet record.

    Matches AELMA's TelemetryPacket schema:
    - timestamp_ns: nanosecond epoch timestamp
    - source: packet origin (nmea0183, nmea2000, simulator, manual, signal_k)
    - channel: telemetry channel name (e.g., depth_m, position.lat, engine_rpm)
    - value: numeric reading (int or float)
    - quality: reading quality (good, suspect, invalid)
    """

    timestamp_ns: int
    source: str
    channel: str
    value: float
    quality: str = "good"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TelemetryRecord:
        """Create a TelemetryRecord from a dictionary (e.g., parsed JSONL)."""
        return cls(
            timestamp_ns=int(data["timestamp_ns"]),
            source=str(data["source"]),
            channel=str(data["channel"]),
            value=float(data["value"]),
            quality=str(data.get("quality", "good")),
        )


@dataclass
class FilterOptions:
    """Filter options for telemetry queries."""

    channel: str | None = None
    value_range: tuple[float, float] | None = None
    since: int | None = None  # nanosecond timestamp
    until: int | None = None  # nanosecond timestamp
    source: str | None = None
    quality: str | None = None


@dataclass
class TimeBucket:
    """A time-bucketed aggregation result."""

    bucket_start_ns: int
    bucket_end_ns: int
    count: int
    values: list[float] = field(default_factory=list)

    @property
    def mean(self) -> float:
        """Arithmetic mean of values in this bucket."""
        if not self.values:
            return 0.0
        return sum(self.values) / len(self.values)

    @property
    def min(self) -> float:
        """Minimum value in this bucket."""
        return min(self.values) if self.values else 0.0

    @property
    def max(self) -> float:
        """Maximum value in this bucket."""
        return max(self.values) if self.values else 0.0


@dataclass
class StatsResult:
    """Statistical summary of a field."""

    count: int
    min: float
    max: float
    mean: float
    stddev: float = 0.0


class TelemetryQuery:
    """Streaming analytics over AELMA telemetry JSONL logs.

    Inspired by the mini-agent's a2aQuery pattern, this class provides:
    - Generator-based streaming (no loading entire logs into memory)
    - Filtering by channel, value range, time range, source, quality
    - Time-bucketing for grouping readings into windows
    - Statistics (min, max, mean, stddev)
    - Percentile calculations

    Example:
        >>> query = TelemetryQuery("/path/to/telemetry.jsonl")
        >>> # Filter depth readings between 70-80m
        >>> for record in query.filter(channel="depth_m", value_range=(70.0, 80.0)):
        ...     print(record.value)
        >>> # Get time-bucketed statistics (60-second buckets)
        >>> for bucket in query.time_bucket(60).filter(channel="depth_m"):
        ...     print(f"{bucket.bucket_start_ns}: mean={bucket.mean:.2f}")
        >>> # Calculate statistics
        >>> stats = query.stats("value").filter(channel="depth_m")
        >>> print(f"Mean depth: {stats.mean:.2f}m")
    """

    def __init__(self, log_path: str | Path) -> None:
        """Initialize a TelemetryQuery over a JSONL log file.

        Args:
            log_path: Path to the telemetry JSONL file.
        """
        self.log_path = Path(log_path)
        if not self.log_path.exists():
            raise FileNotFoundError(f"Telemetry log not found: {log_path}")

    def _stream(self, filters: FilterOptions | None = None) -> Generator[TelemetryRecord, None, None]:
        """Stream records from the log file with optional filtering.

        Args:
            filters: Optional FilterOptions to apply during streaming.

        Yields:
            TelemetryRecord objects that match the filters.
        """
        filters = filters or FilterOptions()

        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue  # Skip malformed lines

                try:
                    record = TelemetryRecord.from_dict(data)
                except (KeyError, TypeError, ValueError):
                    continue  # Skip invalid records

                # Apply filters
                if filters.channel is not None and record.channel != filters.channel:
                    continue
                if filters.value_range is not None:
                    lo, hi = filters.value_range
                    if not (lo <= record.value <= hi):
                        continue
                if filters.since is not None and record.timestamp_ns < filters.since:
                    continue
                if filters.until is not None and record.timestamp_ns > filters.until:
                    continue
                if filters.source is not None and record.source != filters.source:
                    continue
                if filters.quality is not None and record.quality != filters.quality:
                    continue

                yield record

    def filter(
        self,
        channel: str | None = None,
        value_range: tuple[float, float] | None = None,
        since: int | None = None,
        until: int | None = None,
        source: str | None = None,
        quality: str | None = None,
    ) -> Generator[TelemetryRecord, None, None]:
        """Filter telemetry records by various criteria.

        Args:
            channel: Filter by channel name (exact match).
            value_range: Filter by value range (inclusive): (min, max).
            since: Filter by minimum timestamp (nanosecond epoch).
            until: Filter by maximum timestamp (nanosecond epoch).
            source: Filter by source name (exact match).
            quality: Filter by quality (exact match).

        Yields:
            TelemetryRecord objects matching all filter criteria.

        Example:
            >>> for record in query.filter(channel="depth_m", since=start_ns):
            ...     print(f"{record.timestamp_ns}: {record.value}m")
        """
        filters = FilterOptions(
            channel=channel,
            value_range=value_range,
            since=since,
            until=until,
            source=source,
            quality=quality,
        )
        return self._stream(filters)

    def time_bucket(self, seconds: int = 60) -> TimeBucketer:
        """Group records into time buckets for aggregation.

        Args:
            seconds: Bucket size in seconds (default: 60).

        Returns:
            A TimeBucketer object that yields TimeBucket results.

        Example:
            >>> for bucket in query.time_bucket(30).filter(channel="depth_m"):
            ...     print(f"{bucket.count} readings, mean={bucket.mean:.2f}m")
        """
        return TimeBucketer(self, seconds)

    def stats(self, field: str = "value") -> StatsCalculator:
        """Calculate statistics (min, max, mean, stddev) for a field.

        Args:
            field: Field name to analyze (default: "value").

        Returns:
            A StatsCalculator object that computes statistics.

        Example:
            >>> stats = query.stats("value").filter(channel="depth_m")
            >>> print(f"Depth: {stats.min:.2f}-{stats.max:.2f}m, mean={stats.mean:.2f}m")
        """
        return StatsCalculator(self, field)

    def percentile(self, field: str = "value", p: float = 50.0) -> PercentileCalculator:
        """Calculate percentile for a field.

        Args:
            field: Field name to analyze (default: "value").
            p: Percentile to compute (0-100, default: 50 for median).

        Returns:
            A PercentileCalculator object that computes percentiles.

        Example:
            >>> median = query.percentile("value", 50).filter(channel="depth_m")
            >>> p95 = query.percentile("value", 95).filter(channel="depth_m")
            >>> print(f"Median depth: {median.value:.2f}m, p95: {p95.value:.2f}m")
        """
        return PercentileCalculator(self, field, p)


class TimeBucketer:
    """Time-bucketing helper for TelemetryQuery.

    Groups records into fixed-width time windows and aggregates values.
    """

    def __init__(self, query: TelemetryQuery, bucket_seconds: int) -> None:
        """Initialize a TimeBucketer.

        Args:
            query: The TelemetryQuery to bucket.
            bucket_seconds: Bucket size in seconds.
        """
        self.query = query
        self.bucket_seconds = bucket_seconds
        self._filters = FilterOptions()

    def filter(
        self,
        channel: str | None = None,
        value_range: tuple[float, float] | None = None,
        since: int | None = None,
        until: int | None = None,
        source: str | None = None,
        quality: str | None = None,
    ) -> TimeBucketer:
        """Set filter options for bucketing.

        Returns self for method chaining.
        """
        self._filters = FilterOptions(
            channel=channel,
            value_range=value_range,
            since=since,
            until=until,
            source=source,
            quality=quality,
        )
        return self

    def execute(self) -> Generator[TimeBucket, None, None]:
        """Execute the bucketed query.

        Yields:
            TimeBucket objects with aggregated statistics per time window.
        """
        bucket_ns = self.bucket_seconds * 1_000_000_000
        buckets: dict[int, TimeBucket] = {}

        for record in self.query._stream(self._filters):
            # Compute bucket key (floor to bucket boundary)
            bucket_key = (record.timestamp_ns // bucket_ns) * bucket_ns

            if bucket_key not in buckets:
                buckets[bucket_key] = TimeBucket(
                    bucket_start_ns=bucket_key,
                    bucket_end_ns=bucket_key + bucket_ns,
                    count=0,
                )

            bucket = buckets[bucket_key]
            bucket.count += 1
            bucket.values.append(record.value)

        # Yield buckets in chronological order
        for bucket_key in sorted(buckets.keys()):
            yield buckets[bucket_key]

    def __iter__(self) -> Generator[TimeBucket, None, None]:
        """Make TimeBucketer directly iterable."""
        return self.execute()


class StatsCalculator:
    """Statistics calculator for TelemetryQuery.

    Computes min, max, mean, and stddev for a field across records.
    """

    def __init__(self, query: TelemetryQuery, field: str = "value") -> None:
        """Initialize a StatsCalculator.

        Args:
            query: The TelemetryQuery to analyze.
            field: Field name to analyze (default: "value").
        """
        self.query = query
        self.field = field
        self._filters = FilterOptions()

    def filter(
        self,
        channel: str | None = None,
        value_range: tuple[float, float] | None = None,
        since: int | None = None,
        until: int | None = None,
        source: str | None = None,
        quality: str | None = None,
    ) -> StatsCalculator:
        """Set filter options for statistics.

        Returns self for method chaining.
        """
        self._filters = FilterOptions(
            channel=channel,
            value_range=value_range,
            since=since,
            until=until,
            source=source,
            quality=quality,
        )
        return self

    def execute(self) -> StatsResult:
        """Execute the statistics calculation.

        Returns:
            A StatsResult with count, min, max, mean, stddev.
        """
        values: list[float] = []

        for record in self.query._stream(self._filters):
            if self.field == "value":
                values.append(record.value)
            # Could extend to other numeric fields here

        if not values:
            return StatsResult(count=0, min=0.0, max=0.0, mean=0.0)

        count = len(values)
        min_val = min(values)
        max_val = max(values)
        mean = sum(values) / count

        # Calculate stddev
        if count > 1:
            variance = sum((v - mean) ** 2 for v in values) / count
            stddev = variance ** 0.5
        else:
            stddev = 0.0

        return StatsResult(count=count, min=min_val, max=max_val, mean=mean, stddev=stddev)

    @cached_property
    def result(self) -> StatsResult:
        """Lazy property that computes statistics on first access."""
        return self.execute()

    @property
    def count(self) -> int:
        """Number of records analyzed."""
        return self.result.count

    @property
    def min(self) -> float:
        """Minimum field value."""
        return self.result.min

    @property
    def max(self) -> float:
        """Maximum field value."""
        return self.result.max

    @property
    def mean(self) -> float:
        """Mean (average) field value."""
        return self.result.mean

    @property
    def stddev(self) -> float:
        """Standard deviation of field values."""
        return self.result.stddev


class PercentileCalculator:
    """Percentile calculator for TelemetryQuery.

    Computes percentiles (e.g., median, p95, p99) for a field.
    """

    def __init__(self, query: TelemetryQuery, field: str = "value", p: float = 50.0) -> None:
        """Initialize a PercentileCalculator.

        Args:
            query: The TelemetryQuery to analyze.
            field: Field name to analyze (default: "value").
            p: Percentile to compute (0-100, default: 50 for median).
        """
        if not 0 <= p <= 100:
            raise ValueError(f"Percentile must be 0-100, got {p}")

        self.query = query
        self.field = field
        self.p = p
        self._filters = FilterOptions()

    def filter(
        self,
        channel: str | None = None,
        value_range: tuple[float, float] | None = None,
        since: int | None = None,
        until: int | None = None,
        source: str | None = None,
        quality: str | None = None,
    ) -> PercentileCalculator:
        """Set filter options for percentile calculation.

        Returns self for method chaining.
        """
        self._filters = FilterOptions(
            channel=channel,
            value_range=value_range,
            since=since,
            until=until,
            source=source,
            quality=quality,
        )
        return self

    def execute(self) -> float:
        """Execute the percentile calculation.

        Returns:
            The percentile value.
        """
        values: list[float] = []

        for record in self.query._stream(self._filters):
            if self.field == "value":
                values.append(record.value)

        if not values:
            return 0.0

        # Sort for percentile calculation
        sorted_values = sorted(values)

        # Linear interpolation between closest ranks
        n = len(sorted_values)
        target_rank = (self.p / 100.0) * (n - 1)
        lower_idx = int(target_rank)
        upper_idx = min(lower_idx + 1, n - 1)

        if lower_idx == upper_idx:
            return sorted_values[lower_idx]

        # Linear interpolation
        fraction = target_rank - lower_idx
        lower_val = sorted_values[lower_idx]
        upper_val = sorted_values[upper_idx]

        return lower_val + fraction * (upper_val - lower_val)

    @cached_property
    def value(self) -> float:
        """Lazy property that computes percentile on first access."""
        return self.execute()
