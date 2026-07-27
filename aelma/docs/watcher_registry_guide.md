# AELMA WatcherRegistry System Guide

## Overview

The WatcherRegistry system is the fast-path decision layer for AELMA. It provides deterministic, rule-based monitoring of vessel telemetry that fires actions without involving any AI/ML models. This is critical for safety-critical alerts that must be:

- **Deterministic** - Same input always produces same output
- **Fast** - Evaluates in microseconds, not milliseconds
- **Reliable** - No LLM hallucinations or model failures
- **Contained** - Errors in one rule never affect other rules

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Vessel Telemetry Stream                  │
│  (depth, speed, position, fuel, engine status, etc.)       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   WatcherRegistry                            │
│  • Evaluate all rules against each frame                     │
│  • Return list of fired actions                              │
│  • Contain errors per rule                                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   WatcherHistory (optional)                  │
│  • Cooldown enforcement (prevent flooding)                   │
│  • Payload deduplication (same alert suppression)            │
│  • Statistics tracking (fires, suppressions)                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Action Dispatch                            │
│  • Send to viewer for display                                │
│  • Send to vessel control systems                            │
│  • Log to alert history                                      │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. WatcherRegistry (`twin/watchers.py`)

The main rule engine that evaluates conditions against telemetry frames.

**Key Features:**
- Rule registration with validation
- Pure function evaluation (no side effects)
- Error containment per rule
- Event emission for monitoring
- Async stream processing support

**Basic Usage:**
```python
from twin.watchers import WatcherRegistry

registry = WatcherRegistry(verbose=True)

# Add a shallow water warning rule
registry.add({
    "id": "shallow-water",
    "name": "Shallow water warning",
    "when": lambda f: 0 < f.get("depth_m", 999) < 2.0,
    "action": {
        "name": "raise_alert",
        "payload": lambda f: {
            "severity": "warning",
            "code": "SHALLOW_WATER",
            "message": f"Depth {f['depth_m']:.1f}m"
        },
        "reason": lambda f: f"depth={f['depth_m']:.2f}m",
        "priority": lambda f: 0.85,
    },
    "cooldown_s": 30.0,
})

# Evaluate against a telemetry frame
frame = {"depth_m": 1.2, "speed_kn": 5.4}
actions = registry.evaluate(frame)
```

### 2. WatcherHistory (`twin/watcher_history.py`)

Optional suppression layer that prevents alert flooding through:

- **Cooldown** - Time-based suppression (default: per-rule configurable)
- **Payload dedup** - Hash-based suppression of identical payloads
- **Statistics** - Track fires and suppressions per rule

**Key Methods:**
- `should_fire(rule_id, now, cooldown_s, payload)` - Decide if action allowed
- `record(rule_id, now, payload, priority)` - Track fired action
- `mark_suppressed(rule_id, reason)` - Track suppressed action
- `get_stats()` - Get aggregate statistics

**Suppression Reasons:**
- `REASON_DUPLICATE` - Same payload within cooldown window
- `REASON_COOLDOWN` - Different payload but still in cooldown

**Usage:**
```python
from twin.watcher_history import WatcherHistory, REASON_DUPLICATE, REASON_COOLDOWN

history = WatcherHistory(default_cooldown_s=30.0)
registry = WatcherRegistry(history=history)

# After evaluation:
stats = history.get_stats()
print(f"Fires: {stats['total_fires']}")
print(f"Suppressions: {stats['total_suppressed']}")
```

### 3. Vessel Actions (`schema/actions.py`)

Valid action schemas for vessel commands. Each action has:

- **Description** - Human-readable purpose
- **Required fields** - Mandatory parameters
- **Optional fields** - Additional parameters with validation
- **Types & constraints** - JSON Schema validation rules

**Available Actions:**
- `raise_alert` - Safety alerts to crew
- `clear_alerts` - Dismiss active alerts
- `haul_gear` - Fishing gear operations
- `anchor_drop` - Anchor deployment
- `set_throttle` - Engine power control
- `morph_to_navigation_mode` - Operating mode transitions

## Rule Structure

Every watcher rule has this structure:

```python
{
    "id": "unique-rule-id",           # Required: unique identifier
    "name": "Human-readable name",     # Required: description
    "when": lambda frame: bool,        # Required: predicate function
    "action": {
        "name": "action_name",         # Required: must be in ALLOWED_ACTIONS
        "payload": lambda frame: {},   # Optional: action parameters
        "reason": lambda frame: "",    # Optional: human reason
        "priority": lambda frame: 0.5  # Optional: 0.0-1.0 priority
    },
    "cooldown_s": 30.0                 # Optional: cooldown in seconds
}
```

### Allowed Actions

The watcher registry validates against these action names:

- `morph_to_hazard_mode` - Emergency mode
- `morph_to_navigation_mode` - Navigation mode
- `morph_to_engineering_mode` - Engineering mode
- `highlight_waypoint` - Navigation focus
- `raise_alert` - Safety alerts
- `clear_alerts` - Dismiss alerts
- `set_panel_focus` - UI focus
- `announce` - Informational messages

## Integration Patterns

### 1. Frame Stream Processing

```python
async def process_telemetry_stream():
    registry = WatcherRegistry(history=WatcherHistory())

    async def telemetry_generator():
        while True:
            frame = await get_latest_telemetry()
            yield frame
            await asyncio.sleep(0.1)  # 10 Hz update rate

    async def dispatch(action):
        await viewer.broadcast(action)

    await registry.run(telemetry_generator(), dispatch)
```

### 2. Event Monitoring

```python
registry = WatcherRegistry(history=WatcherHistory())

# Monitor fired actions
registry.on("fired", lambda action: log_action(action))

# Monitor suppressed actions
registry.on("suppressed", lambda rule_id, reason:
    log.info(f"Rule {rule_id} suppressed: {reason}"))

# Monitor errors
registry.on("error", lambda exc, ctx:
    log.error(f"Rule {ctx['rule_id']} error at {ctx['stage']}: {exc}"))
```

### 3. Statistics & Monitoring

```python
# Get registry statistics
stats = registry.stats
print(f"Rules: {stats['rule_count']}")
print(f"History stats: {stats['history']}")

# Get detailed per-rule stats
history_stats = registry.history.get_stats()
for rule_id, rule_stats in history_stats["rules"].items():
    print(f"{rule_id}: {rule_stats['total_fires']} fires, "
          f"{rule_stats['total_suppressed']} suppressed")
```

## Testing

The test suite covers:

1. **WatcherHistory unit tests** - State machine, cooldown, dedup
2. **Registry construction** - Validation, registration, lookup
3. **Evaluation** - Match/no-match, ordering, defaults
4. **Error isolation** - Containment per rule, error events
5. **History integration** - Cooldown, suppression, stats
6. **Async processing** - Stream processing, dispatch

**Run tests:**
```bash
cd /path/to/aelma
python -m pytest tests/test_watchers.py -v
```

**Run demo:**
```bash
python examples/watcher_demo.py
```

## Design Principles

### 1. Pure Functions
All rule callbacks must be pure (no I/O, no mutation, no awaiting). This ensures:
- Deterministic evaluation
- Easy testing
- No side effects during evaluation

### 2. Error Containment
Errors in one rule never affect other rules:
- `when` exceptions → emit error event, continue to next rule
- Action callback exceptions → emit error event, skip rule
- History exceptions → emit error event, skip rule
- Listener exceptions → log exception, continue evaluation

### 3. Time-Based Suppression
- Uses monotonic clock (not wall-clock time)
- Deterministic testing with fake clock injection
- Cooldown per rule (configurable)
- Default cooldown via history instance

### 4. Payload Deduplication
- Hash-based identity (SHA-256, first 16 hex chars)
- Canonical JSON serialization (sorted keys)
- Degrades gracefully for non-serializable payloads
- Distinguishes "same alert repeating" from "new alert too fast"

## Performance Characteristics

- **Evaluation speed:** ~1-10 microseconds per rule
- **Memory:** O(num_rules) for registry, O(num_rules) for history
- **Throughput:** 10,000+ evaluations/second typical
- **Latency:** Sub-millisecond for typical rule sets

## Best Practices

### 1. Rule Design
- Keep predicates simple and fast
- Use specific, meaningful rule IDs
- Provide clear human-readable names
- Set appropriate cooldowns (typically 10-60 seconds)

### 2. Action Design
- Use minimum required payload fields
- Provide clear, actionable reason strings
- Set meaningful priorities (0.0-1.0)
- Validate payloads against action schemas

### 3. History Configuration
- Set sensible default cooldown (30s typical)
- Override per-rule for special cases
- Monitor suppression statistics
- Reset history when appropriate

### 4. Testing
- Test predicates with edge cases
- Test cooldown expiration
- Test payload changes vs duplicates
- Test error scenarios
- Use fake clock for deterministic tests

## Reference Implementation

Based on the mini-agent WatcherRegistry pattern (Trinity Marine Station), adapted to Python asyncio with:

- Pure Python 3.12+ type hints
- Asyncio-native stream processing
- Deterministic fake clock for testing
- Comprehensive error containment
- Hash-based payload deduplication

## Files

- `twin/watchers.py` - WatcherRegistry implementation
- `twin/watcher_history.py` - WatcherHistory implementation
- `schema/actions.py` - Vessel action schemas
- `tests/test_watchers.py` - Comprehensive test suite
- `examples/watcher_demo.py` - Usage demonstration
