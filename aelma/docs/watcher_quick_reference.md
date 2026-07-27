# WatcherRegistry Quick Reference Card

## Basic Setup

```python
from twin.watchers import WatcherRegistry
from twin.watcher_history import WatcherHistory

# Create registry with history
history = WatcherHistory(default_cooldown_s=30.0)
registry = WatcherRegistry(history=history, verbose=True)
```

## Rule Template

```python
registry.add({
    "id": "unique-rule-id",
    "name": "Human-readable name",
    "when": lambda f: <condition on frame>,
    "action": {
        "name": "action_name",  # Must be in ALLOWED_ACTIONS
        "payload": lambda f: <action parameters>,
        "reason": lambda f: <human reason>,
        "priority": lambda f: <0.0-1.0 priority>,
    },
    "cooldown_s": <seconds>,
})
```

## Evaluation

```python
# Synchronous evaluation
actions = registry.evaluate(frame)

# Async stream processing
await registry.run(frame_stream(), dispatch_callback)
```

## Frame Structure

```python
frame = {
    "depth_m": 1.2,
    "speed_kn": 5.4,
    "heading_deg": 214.5,
    "lat": 57.0531,
    "lon": -135.33,
    # ... any telemetry fields
}
```

## Action Structure

```python
action = {
    "action": "raise_alert",
    "payload": {"severity": "warning", "code": "SHALLOW_WATER"},
    "reason": "depth=1.20m",
    "priority": 0.85,
    "rule_id": "shallow-water",
}
```

## Allowed Actions

| Action | Purpose | Required Fields |
|--------|---------|-----------------|
| `raise_alert` | Safety alerts | severity, code |
| `clear_alerts` | Dismiss alerts | (none) |
| `announce` | Informational | (none) |
| `morph_to_hazard_mode` | Emergency mode | (none) |
| `morph_to_navigation_mode` | Navigation mode | mode |
| `morph_to_engineering_mode` | Engineering mode | (none) |
| `highlight_waypoint` | Navigation focus | (none) |
| `set_panel_focus` | UI focus | (none) |

## Vessel Actions (schemas)

| Action | Purpose | Required Fields |
|--------|---------|-----------------|
| `raise_alert` | Safety alerts | severity, code |
| `clear_alerts` | Dismiss alerts | (none) |
| `haul_gear` | Gear operations | gear_id |
| `anchor_drop` | Anchor deployment | (none) |
| `set_throttle` | Engine control | throttle_percent |
| `morph_to_navigation_mode` | Mode changes | mode |

## History Events

```python
# Monitor fired actions
registry.on("fired", lambda action: print(action))

# Monitor suppressed actions
registry.on("suppressed", lambda rid, reason: print(rid, reason))

# Monitor errors
registry.on("error", lambda exc, ctx: print(exc, ctx))
```

## Statistics

```python
# Registry stats
stats = registry.stats
# stats["rule_count"] - number of rules
# stats["rules"] - list of rule definitions
# stats["history"] - history stats or None

# History stats
hist = registry.history.get_stats()
# hist["total_fires"] - total actions fired
# hist["total_suppressed"] - total actions suppressed
# hist["rules"][rule_id] - per-rule stats
```

## Cooldown Behavior

| Time Since Last Fire | Same Payload | Different Payload |
|----------------------|--------------|-------------------|
| < cooldown_s | Suppressed (duplicate) | Suppressed (cooldown) |
| >= cooldown_s | Allowed | Allowed |

## Testing Pattern

```python
import time

# Fake clock for deterministic tests
clock = [1000.0]
def now():
    return clock[0]

registry = WatcherRegistry(history=WatcherHistory(), now=now)

# Advance time manually
clock[0] += 10.0
```

## Common Patterns

### Depth-based alert
```python
"when": lambda f: 0 < f.get("depth_m", 999) < 2.0,
"payload": lambda f: {"depth": f["depth_m"]},
```

### Speed-based alert
```python
"when": lambda f: f.get("speed_kn", 0) > 10.0,
"payload": lambda f: {"speed": f["speed_kn"]},
```

### Threshold monitoring
```python
"when": lambda f: f.get("fuel_percent", 100) < 20,
"payload": lambda f: {"level": f["fuel_percent"]},
```

## Files

| File | Purpose |
|------|---------|
| `twin/watchers.py` | Registry implementation |
| `twin/watcher_history.py` | History implementation |
| `schema/actions.py` | Action schemas |
| `tests/test_watchers.py` | Test suite |
| `examples/watcher_demo.py` | Usage examples |

## Commands

```bash
# Run tests
python -m pytest tests/test_watchers.py -v

# Run demo
python examples/watcher_demo.py

# Check stats
python -c "from twin.watchers import ALLOWED_ACTIONS; print(ALLOWED_ACTIONS)"
```

## Priority Guidelines

| Priority | Use Case |
|----------|----------|
| 0.9-1.0 | Critical safety hazards |
| 0.7-0.9 | Important warnings |
| 0.5-0.7 | Normal alerts |
| 0.3-0.5 | Informational |
| 0.0-0.3 | Background notifications |

## Cooldown Guidelines

| Use Case | Recommended Cooldown |
|----------|---------------------|
| Critical hazards | 5-10 seconds |
| Important warnings | 20-30 seconds |
| Normal alerts | 30-60 seconds |
| Informational | 60-120 seconds |
