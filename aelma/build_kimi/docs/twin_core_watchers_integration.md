# TwinCore Watchers Integration

## Overview

The WatcherRegistry system has been integrated into AELMA's TwinCore to provide real-time vessel safety monitoring and alerting. Watchers are deterministic threshold rules that evaluate every telemetry packet and can trigger viewer-facing actions when conditions are met.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        TwinCore                             │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Telemetry Packet → handle_packet()                         │
│                      ↓                                        │
│                  VesselState.apply_packet()                  │
│                      ↓                                        │
│                  _build_frame()                              │
│                      ↓                                        │
│                  WatcherRegistry.evaluate()                  │
│                      ↓                                        │
│                  [fires matching rules]                      │
│                      ↓                                        │
│                  _on_watcher_fired()                         │
│                      ↓                                        │
│                  WebSocket broadcast to viewers               │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. WatcherRegistry

The `WatcherRegistry` manages the evaluation of watcher rules against telemetry frames.

**Location:** `C:\Users\casey\claudetz\aelma\build_kimi\twin\core.py`

**Key Features:**
- Rule validation and normalization
- Per-rule cooldown enforcement
- Event emission for fired/suppressed/error states
- Thread-safe evaluation

### 2. WatcherHistory

The `WatcherHistory` tracks rule firings and suppressions for cooldown enforcement.

**Features:**
- Per-rule cooldown tracking
- Fire/suppression statistics
- Configurable default cooldown

### 3. Default Vessel Safety Rules

Three default watcher rules are registered when `enable_watchers=True`:

#### Shallow Water Warning
```python
{
    "id": "shallow-water",
    "name": "Shallow water warning",
    "when": lambda f: 0 < f.get("depth_m", 999) < 2.0,
    "action": "raise_alert",
    "payload": {
        "severity": "warning",
        "code": "SHALLOW_WATER",
        "message": "Depth critical: {depth}m"
    },
    "priority": 0.85,
    "cooldown_s": 30.0
}
```

#### Grounding Risk Alert
```python
{
    "id": "grounding-risk",
    "name": "Grounding risk alert",
    "when": lambda f: 0 < f.get("depth_m", 999) < 1.0,
    "action": "raise_alert",
    "payload": {
        "severity": "critical",
        "code": "GROUNDING_RISK",
        "message": "GROUNDING RISK: depth={depth}m"
    },
    "priority": 0.95,
    "cooldown_s": 15.0
}
```

#### Engine Overheat Warning
```python
{
    "id": "engine-overheat",
    "name": "Engine overheating warning",
    "when": lambda f: f.get("engine_temp_c", 0) > 90.0,
    "action": "raise_alert",
    "payload": {
        "severity": "critical",
        "code": "ENGINE_OVERHEAT",
        "message": "Engine overheat: {temp}°C"
    },
    "priority": 0.92,
    "cooldown_s": 20.0
}
```

## Integration Points

### TwinCore.__init__()

Watcher system initialization:

```python
def __init__(
    self,
    # ... existing parameters ...
    enable_watchers: bool = True,
    default_cooldown_s: float = 30.0,
) -> None:
    # ... existing initialization ...

    # Initialize watcher system
    self._watcher_history = WatcherHistory(default_cooldown_s=default_cooldown_s)
    self._watchers = WatcherRegistry(
        verbose=False,
        history=self._watcher_history,
        now=time.monotonic,
    )

    # Set up watcher event listener for broadcasting fired actions
    self._watchers.on("fired", self._on_watcher_fired)

    # Register default vessel safety rules
    if enable_watchers:
        self._register_default_watchers()
```

### TwinCore.handle_packet()

Watcher evaluation on every packet:

```python
def handle_packet(self, packet: dict[str, Any]) -> None:
    # Log packet to telemetry file
    self._log_telemetry(packet)

    # Apply to vessel state
    self.state.apply_packet(packet)

    # Evaluate watcher rules on the updated state
    if self.enable_watchers:
        try:
            frame = self._build_frame()
            fired_actions = self._watchers.evaluate(frame)
            if fired_actions:
                log.debug(
                    "watchers evaluated: %d actions fired",
                    len(fired_actions)
                )
        except Exception as exc:
            log.warning("watcher evaluation failed: %s", exc)

    # Continue with depth fusion...
```

### TwinCore._build_frame()

Frame building for watcher evaluation:

```python
def _build_frame(self) -> dict[str, Any]:
    """Build a telemetry frame dict from current vessel state."""
    frame = {
        "timestamp_ns": time.time_ns(),
        "vessel_id": self.vessel_id,
    }

    # Add pose data
    if self.state.lat is not None:
        frame["lat"] = self.state.lat
    if self.state.lon is not None:
        frame["lon"] = self.state.lon
    if self.state.heading_deg is not None:
        frame["heading_deg"] = self.state.heading_deg
    if self.state.speed_kn is not None:
        frame["speed_kn"] = self.state.speed_kn

    # Add channel data
    for channel_name, channel_data in self.state.channels.items():
        if "value" in channel_data:
            frame[channel_name] = channel_data["value"]

    return frame
```

### TwinCore._on_watcher_fired()

Action broadcasting to viewers:

```python
def _on_watcher_fired(self, action: dict[str, Any]) -> None:
    """Handle a fired watcher action by broadcasting to viewers."""
    log.info(
        "[watcher fired] %s -> %s (priority=%.2f)",
        action.get("rule_id"),
        action.get("action"),
        action.get("priority", DEFAULT_PRIORITY),
    )

    # Broadcast the action to all connected viewers
    if self._viewers:
        msg = json.dumps({"type": "action", "data": action})
        asyncio.create_task(self._broadcast_action(msg))
```

## API

### Dynamic Rule Registration

```python
# Register a custom watcher rule
rule_id = core.register_watcher({
    "id": "high-speed-warning",
    "name": "High speed warning",
    "when": lambda f: f.get("speed_kn", 0) > 15.0,
    "action": {
        "name": "raise_alert",
        "payload": lambda f: {
            "severity": "warning",
            "code": "HIGH_SPEED",
            "message": f"Speed high: {f['speed_kn']:.1f}kn"
        },
        "reason": lambda f: f"speed={f['speed_kn']:.1f}kn",
        "priority": lambda f: 0.75,
    },
    "cooldown_s": 60.0,
})
```

### Rule Unregistration

```python
# Remove a watcher rule
removed = core.unregister_watcher("high-speed-warning")
```

### Statistics

```python
# Get watcher statistics
stats = core.get_watcher_stats()
print(f"Total fires: {stats['history']['total_fires']}")
print(f"Total suppressed: {stats['history']['total_suppressed']}")
```

## Action Format

Fired watcher actions are broadcast to viewers in this format:

```json
{
    "type": "action",
    "data": {
        "action": "raise_alert",
        "payload": {
            "severity": "warning",
            "code": "SHALLOW_WATER",
            "message": "Depth critical: 1.50m"
        },
        "reason": "depth=1.50m",
        "priority": 0.85,
        "rule_id": "shallow-water"
    }
}
```

## Supported Actions

The watcher system supports the following action types:

- `morph_to_hazard_mode` - Transition UI to hazard mode
- `morph_to_navigation_mode` - Transition UI to navigation mode
- `morph_to_engineering_mode` - Transition UI to engineering mode
- `highlight_waypoint` - Highlight a waypoint on the chart
- `raise_alert` - Raise an operator alert
- `clear_alerts` - Clear active alerts
- `set_panel_focus` - Focus a specific UI panel
- `announce` - Make a text announcement

## Configuration

### TwinCore Parameters

```python
core = TwinCore(
    bridge_url="ws://localhost:8000",
    viewer_port=8090,
    vessel_id="US-AK-FVEILEEN-51",
    bathymetry_path="bathymetry.json",
    telemetry_log_path="telemetry.jsonl",
    broadcast_interval=1.0,
    persist_interval=60.0,
    viewport_radius_m=500.0,
    enable_telemetry_log=True,
    enable_watchers=True,          # Enable watcher system
    default_cooldown_s=30.0,       # Default cooldown for all rules
)
```

## Testing

The integration includes comprehensive tests:

```bash
# Run watcher integration tests
pytest tests/test_twin.py::TestWatcherIntegration -xvs
```

### Test Coverage

- `test_watchers_initialized_on_core_creation` - Verifies watcher initialization
- `test_default_watchers_registered` - Checks default rules are registered
- `test_shallow_water_watcher_fires` - Tests shallow water detection
- `test_grounding_risk_watcher_fires` - Tests grounding risk detection
- `test_engine_overheat_watcher_fires` - Tests engine overheat detection
- `test_cooldown_enforcement` - Verifies cooldown suppression
- `test_cooldown_stats_tracked` - Tests statistics tracking
- `test_custom_watcher_registration` - Tests dynamic rule registration
- `test_watcher_unregistration` - Tests rule removal
- `test_watchers_disabled_with_flag` - Tests disable functionality
- `test_frame_building_includes_all_fields` - Tests frame construction
- `test_multiple_watchers_can_fire_simultaneously` - Tests concurrent firings

## Error Handling

Watcher evaluation is isolated from core twin functionality:

```python
try:
    frame = self._build_frame()
    fired_actions = self._watchers.evaluate(frame)
    if fired_actions:
        log.debug("watchers evaluated: %d actions fired", len(fired_actions))
except Exception as exc:
    log.warning("watcher evaluation failed: %s", exc)
    # Twin continues to operate normally
```

## Performance Considerations

- Watchers are evaluated on **every** telemetry packet
- Rule predicates must be **fast and deterministic** (no I/O, no network calls)
- Cooldown periods prevent alert spamming
- Evaluation failures are contained and logged

## Future Enhancements

Potential improvements to the watcher system:

1. **Payload Deduplication** - Detect identical alert payloads within cooldown windows
2. **Rule Groups** - Organize rules into logical groups for management
3. **Priority-based Routing** - Route high-priority actions to specific channels
4. **Action Chaining** - Allow one action to trigger another
5. **Time-based Rules** - Support time-windowed conditions (e.g., "night mode")
6. **Compound Conditions** - Support AND/OR logic in rule predicates

## Files Modified

1. **`C:\Users\casey\claudetz\aelma\build_kimi\twin\core.py`**
   - Added WatcherRegistry and WatcherHistory classes
   - Modified `__init__()` to initialize watcher system
   - Modified `handle_packet()` to evaluate watchers
   - Added `_build_frame()` method
   - Added `_on_watcher_fired()` method
   - Added `_register_default_watchers()` method
   - Added `register_watcher()` method
   - Added `unregister_watcher()` method
   - Added `get_watcher_stats()` method

2. **`C:\Users\casey\claudetz\aelma\build_kimi\tests\test_twin.py`**
   - Added `TestWatcherIntegration` test class with 12 comprehensive tests

## References

- **Watcher System Source:** `C:\Users\casey\claudetz\aelma\twin\watchers.py`
- **Action Schemas:** `C:\Users\casey\claudetz\aelma\schema\actions.py`
- **State Management:** `C:\Users\casey\claudetz\aelma\build_kimi\twin\state.py`

---

**Last Updated:** 2026-07-27
**Status:** Production - All tests passing (40/40)
