# Fishing Mode Manager

Track vessel operational states with time-in-mode tracking, statistics, and mode-specific watcher rules.

## Overview

The `FishingModeManager` enables context-aware alerting based on what the vessel is actually doing. Instead of applying all rules to all telemetry, you can define mode-specific thresholds and watchers that only activate when the vessel is in a particular operational state.

## Operational Modes

| Mode | Description | Typical Use |
|------|-------------|-------------|
| `TRANSIT` | Vessel underway to destination | Travel to fishing grounds, returning to port |
| `FISHING` | Active fishing operations | Gear deployment, setting lines, net operation |
| `DRIFTING` | Intentional drift fishing | Drifting with current while fishing |
| `ANCHORED` | Vessel at anchor | Holding position, overnight anchorage |
| `GEAR_DEPLOYED` | Fishing gear in water | Waiting on gear, soak time |
| `HAULING` | Retrieving fishing gear | Hauling nets, lines, pots |
| `MAINTENANCE` | Maintenance operations | Repair, servicing, not fishing |

## Quick Start

### Basic Usage

```python
from build_kimi.twin.core import TwinCore
from build_kimi.twin.fishing_modes import FishingMode

# Initialize twin core (includes fishing mode manager)
twin = TwinCore()

# Set the operational mode
twin.set_fishing_mode(FishingMode.FISHING, "Arrived at fishing grounds")

# Get current mode and duration
mode_info = twin.get_fishing_mode()
print(f"Mode: {mode_info['current_mode']}")
print(f"Duration: {mode_info['duration_s']:.1f}s")
print(f"Reason: {mode_info['reason']}")

# Change mode when operation changes
twin.set_fishing_mode(FishingMode.GEAR_DEPLOYED, "Gear in water")
twin.set_fishing_mode(FishingMode.HAULING, "Hauling gear")
twin.set_fishing_mode(FishingMode.TRANSIT, "Heading home")
```

### Using String Mode Names

```python
# Can use strings instead of enums
twin.set_fishing_mode("FISHING", "Start fishing")
twin.set_fishing_mode("TRANSIT", "Heading to grounds")
```

## API Reference

### TwinCore Methods

#### `set_fishing_mode(mode, reason="")`

Set the current fishing mode.

**Parameters:**
- `mode` (`FishingMode` | `str`): New mode (enum or string value)
- `reason` (`str`): Human-readable explanation for the mode change

**Example:**
```python
twin.set_fishing_mode(FishingMode.FISHING, "Arrived at grounds")
twin.set_fishing_mode("TRANSIT", "Heading home")
```

#### `get_fishing_mode()`

Get current mode and duration information.

**Returns:** `dict`
- `current_mode` (`str`): Current mode name
- `since_ns` (`int`): Timestamp when mode was entered
- `duration_ns` (`int`): Nanoseconds since mode change
- `duration_s` (`float`): Seconds since mode change
- `reason` (`str`): Reason for entering current mode

**Example:**
```python
mode = twin.get_fishing_mode()
print(f"{mode['current_mode']}: {mode['duration_s']:.1f}s")
```

#### `get_fishing_mode_history(limit=None)`

Get mode change history.

**Parameters:**
- `limit` (`int` | `None`): Maximum transitions to return (most recent first)

**Returns:** `list[dict]` - Mode transition records

**Example:**
```python
# Get last 5 mode changes
history = twin.get_fishing_mode_history(limit=5)
for transition in history:
    print(f"{transition['from_mode']} -> {transition['to_mode']}: {transition['reason']}")
```

#### `get_fishing_mode_statistics()`

Get aggregate statistics for all modes.

**Returns:** `dict`
- `modes` (`dict`): Per-mode statistics
- `total_transitions` (`int`): Total number of mode changes
- `current_mode_info` (`dict`): Current mode information

**Example:**
```python
stats = twin.get_fishing_mode_statistics()
for mode_name, mode_stats in stats['modes'].items():
    total_hours = mode_stats['total_duration_ns'] / 1e9 / 3600
    print(f"{mode_name}: {mode_stats['entry_count']} entries, {total_hours:.1f}h total")
```

### FishingModeManager (Direct Access)

You can also access the mode manager directly:

```python
manager = twin.fishing_modes

# Check if mode-specific rules should apply
if manager.should_apply_mode_rules(FishingMode.FISHING):
    print("Apply fishing-specific rules")

# Get context for watcher evaluation
context = manager.get_context_for_watchers()
# Returns: {
#   'fishing_mode': 'FISHING',
#   'fishing_mode_duration_ns': 1234567890,
#   'fishing_mode_duration_s': 1.23456789,
#   'fishing_mode_transitions': 3
# }
```

## Mode-Specific Watcher Rules

The fishing mode manager integrates with the watcher system to enable context-aware alerting. Watcher rules can check the current mode and only trigger when the vessel is in a specific operational state.

### Built-in Mode-Specific Rules

When `enable_watchers=True` in TwinCore, these mode-specific rules are automatically registered:

#### TRANSIT Mode Rules

**Speed Excessive**
- ID: `transit-speed-excessive`
- Triggers: Speed > 15kn while in TRANSIT mode
- Priority: 0.70
- Cooldown: 60s

```python
# Manual registration
twin.register_watcher({
    "id": "transit-speed-warning",
    "name": "Transit speed warning",
    "when": lambda f: f.get("fishing_mode") == "TRANSIT" and f.get("speed_kn", 0) > 15.0,
    "action": {
        "name": "raise_alert",
        "payload": {
            "severity": "warning",
            "code": "TRANSIT_SPEED_HIGH",
            "message": "Transit speed excessive"
        }
    },
    "cooldown_s": 60.0,
})
```

#### FISHING Mode Rules

**Depth Critical**
- ID: `fishing-depth-critical`
- Triggers: Depth < 5m while in FISHING mode
- Priority: 0.80
- Cooldown: 30s

**Gear Failure**
- ID: `fishing-gear-failure`
- Triggers: `gear_status` channel == "FAILURE" while in FISHING
- Priority: 0.95
- Cooldown: 10s

#### DRIFTING Mode Rules

**Drift Rate Excessive**
- ID: `drifting-rate-excessive`
- Triggers: Speed > 2kn while in DRIFTING mode
- Priority: 0.65
- Cooldown: 45s

#### ANCHORED Mode Rules

**Anchor Drag Detected**
- ID: `anchor-drag-detected`
- Triggers: Speed > 0.5kn while in ANCHORED mode
- Priority: 0.88
- Cooldown: 20s

#### GEAR_DEPLOYED Mode Rules

**Deployed Too Long**
- ID: `gear-deployed-too-long`
- Triggers: Duration > 12 hours while in GEAR_DEPLOYED
- Priority: 0.50
- Cooldown: 300s

#### HAULING Mode Rules

**Slow Progress**
- ID: `hauling-slow-progress`
- Triggers: Speed < 1kn AND gear_tension > 50 while in HAULING
- Priority: 0.72
- Cooldown: 60s

### Creating Custom Mode-Specific Rules

Watchers automatically receive fishing mode context in their evaluation frame:

```python
# Custom watcher that only triggers during FISHING mode
twin.register_watcher({
    "id": "fishing-engine-load-high",
    "name": "High engine load while fishing",
    "when": lambda f: (
        f.get("fishing_mode") == "FISHING" and
        f.get("engine_load_percent", 0) > 90
    ),
    "action": {
        "name": "raise_alert",
        "payload": {
            "severity": "warning",
            "code": "ENGINE_LOAD_HIGH",
            "message": "Engine load critical while fishing"
        }
    },
    "cooldown_s": 30.0,
})

# Watcher using time-in-mode
twin.register_watcher({
    "id": "long-fishing-session",
    "name": "Extended fishing session",
    "when": lambda f: (
        f.get("fishing_mode") == "FISHING" and
        f.get("fishing_mode_duration_s", 0) > 36000  # > 10 hours
    ),
    "action": {
        "name": "raise_alert",
        "payload": {
            "severity": "info",
            "code": "LONG_SESSION",
            "message": f"Fishing for {f['fishing_mode_duration_s']/3600:.1f}h"
        }
    },
    "cooldown_s": 600.0,
})
```

## Integration with TwinCore

### In Telemetry Frame

The fishing mode context is automatically added to watcher evaluation frames:

```python
{
    "timestamp_ns": 1234567890000000000,
    "vessel_id": "US-AK-FVEILEEN-51",
    "speed_kn": 8.5,
    "heading_deg": 180.0,
    "depth_m": 45.2,
    # ... other telemetry channels
    "fishing_mode": "FISHING",
    "fishing_mode_duration_ns": 3600000000000,
    "fishing_mode_duration_s": 3600.0,
    "fishing_mode_transitions": 3,
}
```

### In VesselStateSnapshot

Snapshots include current mode information:

```python
snapshot = twin.build_snapshot()
print(snapshot["fishing_mode"])
# {
#   "current_mode": "FISHING",
#   "since_ns": 1234567890000000000,
#   "duration_ns": 3600000000000,
#   "duration_s": 3600.0,
#   "reason": "Arrived at fishing grounds"
# }
```

## Example Workflow

### Complete Fishing Operation

```python
from build_kimi.twin.core import TwinCore
from build_kimi.twin.fishing_modes import FishingMode
import time

# Initialize
twin = TwinCore(enable_watchers=True)

# Departure
twin.set_fishing_mode(FishingMode.TRANSIT, "Departing port")
time.sleep(60)  # Transit to grounds

# Arrive at fishing grounds
twin.set_fishing_mode(FishingMode.FISHING, "Arrived at fishing grounds")

# Deploy gear
twin.set_fishing_mode(FishingMode.GEAR_DEPLOYED, "Gear in water")
time.sleep(3600)  # Soak for 1 hour

# Haul gear
twin.set_fishing_mode(FishingMode.HAULING, "Hauling gear")
time.sleep(900)  # 15 minute haul

# Check statistics
stats = twin.get_fishing_mode_statistics()
print(f"Total transitions: {stats['total_transitions']}")

# Review history
for transition in twin.get_fishing_mode_history():
    from_mode = transition['from_mode'] or 'START'
    to_mode = transition['to_mode']
    print(f"{from_mode} -> {to_mode}: {transition['reason']}")

# Head home
twin.set_fishing_mode(FishingMode.TRANSIT, "Heading to port")
```

### Mode-Aware Analytics

```python
# Analyze time spent in each mode
stats = twin.get_fishing_mode_statistics()

for mode_name, mode_stats in stats['modes'].items():
    duration_s = mode_stats['total_duration_ns'] / 1e9
    duration_h = duration_s / 3600
    entry_count = mode_stats['entry_count']

    if entry_count > 0:
        avg_duration = duration_s / entry_count
        print(f"{mode_name}:")
        print(f"  Entries: {entry_count}")
        print(f"  Total time: {duration_h:.2f}h")
        print(f"  Avg per entry: {avg_duration/60:.1f}min")
```

## Best Practices

### 1. Mode Changes at Operation Boundaries

Change modes when the fundamental operation changes:

```python
# Good - Clear operation boundaries
twin.set_fishing_mode(FishingMode.TRANSIT, "Leaving port")
# ... transit ...
twin.set_fishing_mode(FishingMode.FISHING, "Starting fishing")
# ... fishing ...
twin.set_fishing_mode(FishingMode.TRANSIT, "Returning to port")

# Avoid - Too granular
twin.set_fishing_mode(FishingMode.FISHING, "Gear starboard going out")
# ... 30 seconds later ...
twin.set_fishing_mode(FishingMode.FISHING, "Gear port going out")
```

### 2. Descriptive Reasons

Use clear, searchable reasons:

```python
# Good - Specific and searchable
twin.set_fishing_mode(FishingMode.FISHING, "Arrived at cod grounds - 58.5N 148.3W")
twin.set_fishing_mode(FishingMode.TRANSIT, "Heading to halibut grounds - 59.0N 149.0W")

# Avoid - Vague
twin.set_fishing_mode(FishingMode.FISHING, "Fishing")
twin.set_fishing_mode(FishingMode.TRANSIT, "Moving")
```

### 3. Mode-Specific Thresholds

Set appropriate thresholds for each mode:

```python
# TRANSIT: Higher speed OK
twin.register_watcher({
    "id": "transit-speed",
    "when": lambda f: f.get("fishing_mode") == "TRANSIT" and f.get("speed_kn", 0) > 18.0,
    # ...
})

# FISHING: Lower speed threshold
twin.register_watcher({
    "id": "fishing-speed",
    "when": lambda f: f.get("fishing_mode") == "FISHING" and f.get("speed_kn", 0) > 6.0,
    # ...
})

# DRIFTING: Very low speed expected
twin.register_watcher({
    "id": "drifting-speed",
    "when": lambda f: f.get("fishing_mode") == "DRIFTING" and f.get("speed_kn", 0) > 2.0,
    # ...
})
```

### 4. Use Duration in Rules

Leverage time-in-mode for context-aware alerts:

```python
# Alert on long sessions
twin.register_watcher({
    "id": "long-fishing",
    "when": lambda f: (
        f.get("fishing_mode") == "FISHING" and
        f.get("fishing_mode_duration_s", 0) > 43200  # > 12 hours
    ),
    "action": {
        "name": "raise_alert",
        "payload": {
            "severity": "info",
            "code": "LONG_FISHING_SESSION",
            "message": f"Fishing for {f['fishing_mode_duration_s']/3600:.1f} hours"
        }
    },
    "cooldown_s": 600.0,
})
```

## Error Handling

### Invalid Mode Names

```python
try:
    twin.set_fishing_mode("INVALID_MODE", "Test")
except ValueError as e:
    print(f"Invalid mode: {e}")
```

### Getting Statistics for Non-Existent Mode

```python
try:
    stats = twin.get_time_in_mode("INVALID")
except ValueError as e:
    print(f"Invalid mode: {e}")
```

## Performance Considerations

### Mode Change Frequency

- Mode changes are lightweight (nanosecond timestamp updates)
- History grows linearly with transitions
- Statistics are computed on-demand (not maintained continuously)

### Watcher Evaluation

- Mode context adds 4 fields to watcher frames
- Mode checks are simple string comparisons
- No performance impact for typical use (<100 mode changes per hour)

### Statistics Queries

- `get_mode()`: O(1) - returns current state
- `get_mode_history(limit)`: O(limit) - returns last N transitions
- `get_statistics()`: O(n) - computes stats for all modes (n=7)
- `get_time_in_mode()`: O(1) - returns single mode stats

## Testing

Run the fishing mode tests:

```bash
# Run all fishing mode tests
pytest tests/test_fishing_modes.py -v

# Run specific test
pytest tests/test_fishing_modes.py::TestFishingModeManager::test_set_mode -v

# Run integration tests
pytest tests/test_fishing_modes.py::TestFishingModeIntegration -v
```

## See Also

- **TwinCore**: Main twin system documentation
- **Watcher System**: Watcher rules and evaluation
- **Telemetry System**: Packet handling and state updates
