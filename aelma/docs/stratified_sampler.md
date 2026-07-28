# StratifiedSampler - Balanced ML Training Datasets from Telemetry

The `StratifiedSampler` creates balanced training datasets from AELMA telemetry and A2A action logs. It implements multiple stratification strategies to ensure ML models receive representative training data while preserving rare events like alerts and anomalies.

## Overview

Training ML models on marine telemetry presents unique challenges:

- **Temporal skew**: Vessels spend most time in normal conditions, creating class imbalance
- **Value clustering**: Depth readings cluster in common ranges (e.g., 10-20m) with rare extremes
- **Event rarity**: Alerts and anomalies are critical but infrequent (<1% of data)
- **Concept drift**: Sensor characteristics change over time

`StratifiedSampler` addresses these challenges with three complementary strategies:

1. **Value stratification**: Bin telemetry values and sample evenly across ranges
2. **Time stratification**: Sample evenly across time periods to capture concept drift
3. **Event stratification**: Oversample rare events (alerts, anomalies) with class weighting

## Installation

The sampler is part of the `twin` module:

```python
from twin.stratified_sampler import StratifiedSampler, TrainingExample
from twin.a2a_query import A2AQuery
```

## Quick Start

### Basic Value Stratification

Sample depth readings balanced across depth ranges:

```python
from twin.stratified_sampler import StratifiedSampler

sampler = StratifiedSampler(
    seed=42,  # For reproducible results
    telemetry_query=my_telemetry_query
)

# Define depth bins in meters
depth_bins = [
    (0, 5),      # Shallow: 0-5m
    (5, 10),     # Medium: 5-10m
    (10, 20),    # Deep: 10-20m
    (20, float('inf'))  # Very deep: >20m
]

# Sample 10 readings per bin
samples = await sampler.sample(
    channel="depth_m",
    n_per_bin=10,
    value_bins=depth_bins
)

print(f"Sampled {len(samples)} depth readings")
# Output: Sampled 40 depth readings
```

### Time Stratification

Sample evenly across a voyage to capture temporal variation:

```python
# Sample 100 readings evenly across 30-minute periods
time_samples = await sampler.sample_time_periods(
    channel="depth_m",
    n=100,
    period_minutes=30
)

print(f"Sampled {len(time_samples)} time-stratified readings")
```

### Event Stratification

Preserve rare events (alerts, anomalies) in training data:

```python
from twin.a2a_query import A2AQuery

sampler = StratifiedSampler(
    seed=42,
    a2a_query=A2AQuery("a2a.jsonl")
)

# Sample with 70% normal, 30% alerts/anomalies
event_samples = await sampler.sample_events(
    normal_ratio=0.7,
    limit=1000  # Total samples
)

# Labels: 0=normal, 1=alert, 2=anomaly
alerts = [s for s in event_samples if s.label == 1]
anomalies = [s for s in event_samples if s.label == 2]

print(f"Alerts: {len(alerts)}, Anomalies: {len(anomalies)}")
```

### Combined Strategy

Use all three strategies for maximum diversity:

```python
combined_samples = await sampler.sample_combined(
    channel="depth_m",
    n_per_value_bin=10,      # Value stratification
    time_period_minutes=30,  # Time stratification
    n_time_samples=100,
    n_events=500,            # Event stratification
    normal_ratio=0.7
)

print(f"Total samples: {len(combined_samples)}")
```

### Export to JSONL

Export samples for ML training:

```python
await sampler.export_to_jsonl(
    output_path="training_dataset.jsonl",
    samples=combined_samples,
    include_metadata=True
)
```

Output format (JSONL):

```json
{"features": {"value": 15.2, "channel": "depth_m", "timestamp_ns": 1704067200000000000, "quality": "good"}, "label": null, "metadata": {"source": "nmea0183", "bin": "bin_2"}, "weight": 1.0}
{"features": {"action": "raise_alert", "source": "watcher", "priority": 0.9, "reason": "depth low"}, "label": 1, "metadata": {"event_type": "rare", "source": "watcher"}, "weight": 2.0}
```

## Stratification Strategies

### Value-Based Stratification

Bins telemetry values and samples evenly from each range:

```python
samples = await sampler.sample(
    channel="depth_m",
    n_per_bin=10,
    value_bins=[
        (0, 5),      # Bin 0
        (5, 10),     # Bin 1
        (10, 20),    # Bin 2
        (20, float('inf'))  # Bin 3 (unbounded)
    ]
)
```

**Default bins** for common channels:

- `depth_m`: [(0, 5), (5, 10), (10, 20), (20, inf)]
- `speed_kn`, `speed_over_ground_kn`: [(0, 2), (2, 5), (5, 10), (10, inf)]
- `heading_deg`, `heading_true_deg`: [(0, 90), (90, 180), (180, 270), (270, 360)]
- Other channels: Generic percentiles [(-inf, 0), (0, 50), (50, 100), (100, inf)]

**Use cases**:
- Depth-based classification (shallow/medium/deep water)
- Speed regime detection (idle/transit/full speed)
- Heading-based navigation pattern learning

### Time-Based Stratification

Divides time range into periods and samples evenly:

```python
samples = await sampler.sample_time_periods(
    channel="depth_m",
    n=100,
    period_minutes=30,  # 30-minute periods
    filters={"source": "nmea0183"}  # Optional filter
)
```

**How it works**:
1. Determines time range from telemetry (min to max timestamp)
2. Divides into fixed-width periods (e.g., 30 minutes)
3. Samples evenly from each period

**Use cases**:
- Capture concept drift over long voyages
- Ensure model sees all operational phases
- Balance day vs night, calm vs rough conditions

### Event-Based Stratification

Oversamples rare events with class weighting:

```python
event_samples = await sampler.sample_events(
    normal_ratio=0.7,      # 70% normal, 30% rare
    alert_action="raise_alert",
    anomaly_action="log_anomaly",
    limit=1000
)
```

**Label encoding**:
- `0`: Normal operation
- `1`: Alert events
- `2`: Anomaly events

**Sample weighting**:
- Normal events: `weight = 1.0`
- Rare events: `weight = 2.0` (for loss function)

**Use cases**:
- Anomaly detection (alerts = positive class)
- Failure prediction (anomalies = positive class)
- Condition monitoring (normal vs abnormal states)

## Training Example Structure

Each sample is a `TrainingExample` with:

```python
from twin.stratified_sampler import TrainingExample

example = TrainingExample(
    features={
        "value": 15.2,
        "channel": "depth_m",
        "timestamp_ns": 1704067200000000000,
        "quality": "good",
    },
    label=None,  # Optional: 0=normal, 1=alert, 2=anomaly
    metadata={
        "source": "nmea0183",
        "bin": "bin_2",  # Value bin identifier
        "time_period": 5,  # Time period index
        "event_type": "normal"  # Or "rare"
    },
    weight=1.0  # Sample weight for loss calculation
)
```

## Integration with AELMA

### With Telemetry Query

```python
from twin.telemetry_query import TelemetryQuery
from twin.stratified_sampler import StratifiedSampler

# Connect to telemetry storage
telemetry_query = TelemetryQuery("telemetry.db")

# Create sampler
sampler = StratifiedSampler(
    seed=42,
    telemetry_query=telemetry_query
)

# Sample depth readings
samples = await sampler.sample(
    channel="depth_m",
    n_per_bin=10
)
```

### With A2A Query

```python
from twin.a2a_query import A2AQuery
from twin.stratified_sampler import StratifiedSampler

# Connect to A2A log
a2a_query = A2AQuery("a2a.jsonl")

# Create sampler
sampler = StratifiedSampler(
    seed=42,
    a2a_query=a2a_query
)

# Sample events
samples = await sampler.sample_events(
    normal_ratio=0.7,
    limit=1000
)
```

### Combined Pipeline

```python
from twin.telemetry_query import TelemetryQuery
from twin.a2a_query import A2AQuery
from twin.stratified_sampler import StratifiedSampler

# Setup
telemetry_query = TelemetryQuery("telemetry.db")
a2a_query = A2AQuery("a2a.jsonl")

sampler = StratifiedSampler(
    seed=42,
    telemetry_query=telemetry_query,
    a2a_query=a2a_query
)

# Sample with combined strategy
samples = await sampler.sample_combined(
    channel="depth_m",
    n_per_value_bin=10,
    time_period_minutes=30,
    n_time_samples=100,
    n_events=500,
    normal_ratio=0.7
)

# Export to JSONL
await sampler.export_to_jsonl(
    output_path="training/vessel_depth_classifier.jsonl",
    samples=samples
)

print(f"Created training dataset with {len(samples)} examples")
```

## ML Training Integration

### For Anomaly Detection

```python
import pandas as pd
from sklearn.ensemble import IsolationForest

# Load samples
samples = []
with open("training/vessel_depth_classifier.jsonl") as f:
    for line in f:
        samples.append(TrainingExample.from_dict(json.loads(line)))

# Extract features
X = pd.DataFrame([s.features for s in samples])
y = [s.label for s in samples]  # 0=normal, 1/2=anomaly

# Train with sample weights
model = IsolationForest(contamination=0.1)
sample_weights = [s.weight for s in samples]
model.fit(X, sample_weight=sample_weights)
```

### For Classification

```python
from sklearn.linear_model import LogisticRegression

# Binary classification: normal vs alert
X = pd.DataFrame([s.features for s in samples])
y_binary = [1 if s.label == 1 else 0 for s in samples]

# Train with weights
clf = LogisticRegression(class_weight="balanced")
clf.fit(X, y_binary, sample_weight=[s.weight for s in samples])
```

### For Neural Networks

```python
import torch
from torch.utils.data import Dataset, DataLoader

class TelemetryDataset(Dataset):
    def __init__(self, jsonl_path):
        self.samples = []
        with open(jsonl_path) as f:
            for line in f:
                self.samples.append(TrainingExample.from_dict(json.loads(line)))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        sample = self.samples[idx]
        return (
            torch.tensor(list(sample.features.values()), dtype=torch.float32),
            torch.tensor(sample.label or 0, dtype=torch.long),
            torch.tensor(sample.weight, dtype=torch.float32)
        )

dataset = TelemetryDataset("training/vessel_depth_classifier.jsonl")
loader = DataLoader(dataset, batch_size=32, shuffle=True)

# Training loop with weighted loss
criterion = torch.nn.CrossEntropyLoss(reduction='none')
for features, labels, weights in loader:
    loss = criterion(features, labels)
    weighted_loss = (loss * weights).mean()
    weighted_loss.backward()
```

## Reproducibility

All sampling is deterministic with a fixed seed:

```python
# Run 1: Generate dataset
sampler1 = StratifiedSampler(seed=42, telemetry_query=query)
samples1 = await sampler1.sample(channel="depth_m", n_per_bin=10)

# Run 2: Identical results
sampler2 = StratifiedSampler(seed=42, telemetry_query=query)
samples2 = await sampler2.sample(channel="depth_m", n_per_bin=10)

assert samples1 == samples2  # True
```

## Best Practices

### 1. Choose Appropriate Bins

Customize bins for your domain:

```python
# For shallow-water operations
shallow_bins = [(0, 3), (3, 6), (6, 10), (10, float('inf'))]

# For deep-water operations
deep_bins = [(0, 20), (20, 50), (50, 100), (100, 200), (200, float('inf'))]
```

### 2. Balance Strategies

Adjust ratios based on your use case:

```python
# For anomaly detection: prioritize event sampling
samples = await sampler.sample_combined(
    channel="depth_m",
    n_per_value_bin=5,      # Fewer value samples
    n_events=2000,          # More event samples
    normal_ratio=0.5        # Balanced normal/rare
)

# For regression: prioritize value/time sampling
samples = await sampler.sample_combined(
    channel="depth_m",
    n_per_value_bin=20,     # More value samples
    n_events=100,           # Fewer event samples
    normal_ratio=0.9         # Mostly normal
)
```

### 3. Validate Datasets

Always inspect stratification results:

```python
samples = await sampler.sample(channel="depth_m", n_per_bin=10)

# Check bin distribution
from collections import Counter
bins = [s.metadata.get("bin") for s in samples]
print(Counter(bins))
# Output: Counter({'bin_0': 10, 'bin_1': 10, 'bin_2': 10, 'bin_3': 10})

# Check label distribution (event sampling)
event_samples = await sampler.sample_events(normal_ratio=0.7)
labels = [s.label for s in event_samples]
print(Counter(labels))
# Output: Counter({0: 140, 1: 10, 2: 10})  # ~70% normal
```

### 4. Export with Metadata

Keep metadata for debugging:

```python
await sampler.export_to_jsonl(
    "training.jsonl",
    samples,
    include_metadata=True  # Keep bin, time_period, event_type
)
```

### 5. Version Control Datasets

Track dataset generation parameters:

```python
# Save dataset metadata
metadata = {
    "created": datetime.now().isoformat(),
    "seed": 42,
    "strategies": {
        "value_bins": [(0, 5), (5, 10), (10, 20), (20, float('inf'))],
        "time_period_minutes": 30,
        "normal_ratio": 0.7,
        "n_per_bin": 10,
        "n_events": 500
    },
    "source_files": ["telemetry.db", "a2a.jsonl"]
}

with open("training/metadata.json", "w") as f:
    json.dump(metadata, f, indent=2)
```

## API Reference

### StratifiedSampler

```python
class StratifiedSampler:
    def __init__(
        self,
        seed: int = 42,
        telemetry_query: Any = None,
        a2a_query: A2AQuery | None = None
    ) -> None:
        """Initialize sampler with random seed and query interfaces."""
```

#### Methods

**sample()**
```python
async def sample(
    self,
    channel: str,
    n_per_bin: int,
    value_bins: list[tuple[float, float]] | None = None,
    filters: dict[str, Any] | None = None,
) -> list[TrainingExample]:
    """Sample telemetry balanced across value bins."""
```

**sample_time_periods()**
```python
async def sample_time_periods(
    self,
    channel: str,
    n: int,
    period_minutes: int = 30,
    filters: dict[str, Any] | None = None,
) -> list[TrainingExample]:
    """Sample telemetry evenly across time periods."""
```

**sample_events()**
```python
async def sample_events(
    self,
    normal_ratio: float = 0.7,
    alert_action: str = "raise_alert",
    anomaly_action: str = "log_anomaly",
    limit: int = 1000,
) -> list[TrainingExample]:
    """Sample A2A events with rare event oversampling."""
```

**export_to_jsonl()**
```python
async def export_to_jsonl(
    self,
    output_path: str | Path,
    samples: list[TrainingExample] | list[dict[str, Any]],
    *,
    include_metadata: bool = True,
) -> int:
    """Export samples to JSONL format. Returns record count."""
```

**sample_combined()**
```python
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
    """Sample using multiple strategies combined."""
```

### TrainingExample

```python
@dataclass
class TrainingExample:
    features: dict[str, Any]      # Feature values
    label: Any = None             # Optional label
    metadata: dict[str, Any]       # Optional metadata
    weight: float = 1.0           # Sample weight

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrainingExample:
        """Create from dictionary."""
```

## Troubleshooting

### Empty Sample Sets

**Problem**: `await sampler.sample(...)` returns empty list.

**Solution**: Verify telemetry query interface:

```python
# Check if data exists
data = await telemetry_query.query_channel("depth_m", {})
print(f"Found {len(data)} records")

# Check sampler configuration
sampler = StratifiedSampler(seed=42, telemetry_query=telemetry_query)
```

### Skewed Bin Distribution

**Problem**: Some bins have fewer samples than requested.

**Solution**: Adjust bin boundaries to match data distribution:

```python
# Analyze data distribution first
values = [r["value"] for r in telemetry_data]
min_val, max_val = min(values), max(values)

# Create custom bins
custom_bins = [
    (min_val, min_val + 5),
    (min_val + 5, min_val + 10),
    (min_val + 10, max_val)
]
```

### Import Errors

**Problem**: `ImportError: cannot import name 'A2AQuery'`

**Solution**: Ensure imports are correct:

```python
# Correct import
from twin.stratified_sampler import StratifiedSampler
from twin.a2a_query import A2AQuery

# Sampler will handle missing A2AQuery gracefully
sampler = StratifiedSampler(seed=42)  # OK without a2a_query
```

## Performance Considerations

### Memory Usage

For large telemetry datasets, use streaming:

```python
# Process in chunks
for chunk in range(0, total_records, chunk_size):
    chunk_samples = await sampler.sample(
        channel="depth_m",
        n_per_bin=10,
        filters={"limit": (chunk, chunk + chunk_size)}
    )
    await sampler.export_to_jsonl(f"training/chunk_{chunk}.jsonl", chunk_samples)
```

### Sampling Speed

Pre-filter data to reduce processing:

```python
# Faster: filter before sampling
filters = {
    "since": "2024-01-01T00:00:00Z",
    "until": "2024-12-31T23:59:59Z",
    "source": "nmea0183"
}

samples = await sampler.sample(
    channel="depth_m",
    n_per_bin=10,
    filters=filters
)
```

## Examples

### Example 1: Depth-Based Classification

Train a classifier to predict shallow vs deep water:

```python
# Create balanced depth dataset
sampler = StratifiedSampler(
    seed=42,
    telemetry_query=telemetry_query
)

samples = await sampler.sample(
    channel="depth_m",
    n_per_bin=25,
    value_bins=[(0, 10), (10, float('inf'))]
)

# Add labels
for sample in samples:
    if sample.features["value"] < 10:
        sample.label = 0  # Shallow
    else:
        sample.label = 1  # Deep

# Export
await sampler.export_to_jsonl("depth_classifier.jsonl", samples)
```

### Example 2: Anomaly Detection

Train an anomaly detector on A2A events:

```python
sampler = StratifiedSampler(
    seed=42,
    a2a_query=a2a_query
)

# Get balanced event dataset
samples = await sampler.sample_events(
    normal_ratio=0.8,
    limit=5000
)

# Export with labels (0=normal, 1=alert, 2=anomaly)
await sampler.export_to_jsonl("anomaly_detector.jsonl", samples)
```

### Example 3: Time-Series Forecasting

Create time-stratified dataset for forecasting:

```python
sampler = StratifiedSampler(
    seed=42,
    telemetry_query=telemetry_query
)

# Sample across entire voyage
samples = await sampler.sample_time_periods(
    channel="depth_m",
    n=1000,
    period_minutes=15  # 15-minute periods
)

# Export
await sampler.export_to_jsonl("time_series.jsonl", samples)
```

## References

- Related: [A2A Query System](./a2a_system.md)
- Related: [Watcher Registry](./watcher_registry_guide.md)
- Mini-agent reference: `C:\Users\casey\Downloads\mini-agent-freeze.txt` (stratified sampler implementation)
