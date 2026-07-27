# AELMA Viewer - Alerts UI Documentation

## Overview

The Alerts UI provides real-time visualization of WatcherRegistry actions from the AELMA twin core, displaying color-coded alerts with priority levels, 3D visual indicators, and quick action buttons for safety-critical vessel operations.

## Features

### 1. Alerts Panel (Left Sidebar)

**Location**: Fixed panel at top-left of screen (320px wide)

**Components**:
- **Header**: "ALERTS" title with "Clear All" button
- **Active Alerts List**: Real-time display of current alerts
- **History Section**: Timestamped log of past alerts (max 20)

**Alert Display**:
```
┌─────────────────────────────────────┐
│ [CODE]         [TIME]        [✕]   │
│ Alert message text                 │
│ Reason: additional context         │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │  ← Priority bar
└─────────────────────────────────────┘
```

**Priority Levels**:
- **Critical** (≥0.9): Red border, pulsing animation, 3D sphere marker
- **High** (0.7-0.9): Yellow border, 3D ring marker
- **Medium** (0.4-0.7): Green border
- **Low** (<0.4): Blue border

### 2. 3D Visual Indicators

**Critical Alerts** (≥0.9 priority):
- Glowing red sphere floating above vessel
- Pulsing animation (scales 1.0-1.3x)
- Floating text label with alert code
- Follows vessel position in real-time

**Other Alerts**:
- Horizontal ring marker at vessel position
- Color-coded by priority level
- Positioned 5m above vessel

### 3. Quick Actions Panel

**Location**: Fixed panel at bottom-left of screen

**Buttons**:
- **▲ Haul Gear**: Retrieve deployed gear (with confirmation)
- **⚓ Drop Anchor**: Stop vessel (with confirmation)
- **✕ Clear Alerts**: Dismiss all active alerts

### 4. Action Confirmation Dialog

**Safety-critical actions require confirmation**:
- Modal dialog with backdrop blur
- Shows action name and description
- Displays payload data (if any)
- Confirm/Cancel buttons

## Integration with Twin Core

### WebSocket Message Schema

**Action Event**:
```json
{
  "type": "action",
  "data": {
    "action": "raise_alert",
    "payload": {
      "severity": "critical",
      "code": "GROUNDING_RISK",
      "message": "GROUNDING RISK: depth=0.8m"
    },
    "reason": "depth=0.80m",
    "priority": 0.95,
    "rule_id": "grounding-risk",
    "timestamp_ns": 1690000000000000
  }
}
```

**Action Request** (viewer → twin):
```json
{
  "type": "action_request",
  "data": {
    "action": "haul_gear",
    "payload": {},
    "timestamp_ns": 1690000000000000
  }
}
```

### Supported Actions

**raise_alert**:
- Displays alert in panel
- Creates 3D indicator
- Adds to history

**clear_alerts**:
- Dismisses all active alerts
- Removes 3D indicators
- Keeps history intact

**haul_gear, anchor_drop**:
- Shows confirmation dialog
- Sends action_request to twin
- Awaiting twin implementation

## Usage

### 1. Start the System

```bash
# Terminal 1: Start bridge
cd /c/Users/casey/claudetz/aelma/build_kimi
python -m bridge

# Terminal 2: Start twin core
python -m twin --verbose

# Terminal 3: Start simulator
cd /c/Users/casey/claudetz/aelma
python -m simulator.simulate --duration-min 10 --speedup 10

# Terminal 4: Start viewer HTTP server
cd /c/Users/casey/claudetz/aelma/build_kimi_viewer
python -m http.server 8080
```

### 2. Access the Viewer

Open browser to: `http://127.0.0.1:8080/`

### 3. Test the Alerts UI

**Demo Page** (standalone, no twin required):
`http://127.0.0.1:8080/demo.html`

**Test Page** (requires twin connection):
`http://127.0.0.1:8080/test_alerts.html`

### 4. Browser Console Testing

Load the test script in the viewer:
```javascript
// Load test functions
const script = document.createElement('script');
script.src = 'test_alerts.js';
document.head.appendChild(script);

// Run tests
testAlerts.runAll();      // All alert levels
testAlerts.critical();    // Critical alert only
testAlerts.high();        // High priority only
testAlerts.medium();      // Medium priority only
testAlerts.low();         // Low priority only
testAlerts.clear();       // Clear all alerts
```

## Technical Implementation

### File Structure

```
build_kimi_viewer/
├── index.html          # Main viewer with alerts panel
├── style.css           # Alerts UI styles
├── app.js              # Alert system logic
├── demo.html           # Standalone demo
├── test_alerts.html   # WebSocket test page
├── test_alerts.js      # Browser console tests
└── ALERTS_UI_DOCUMENTATION.md
```

### Key Functions

**Alert Management**:
- `addAlert(action)`: Add new alert from watcher
- `renderAlert(alert)`: Render alert in DOM
- `dismissAlert(alertId)`: Remove single alert
- `clearAllAlerts()`: Remove all alerts
- `addToHistory(alert)`: Add to history log
- `renderHistory()`: Update history display

**3D Indicators**:
- `add3DAlertIndicator(alert)`: Create 3D marker
- `remove3DAlertIndicator(alertId)`: Remove marker
- `updateAlertIndicators()`: Update positions in animation loop

**Action Handling**:
- `handleActionEvent(action)`: Process action from twin
- `showActionDialog(name, message, payload)`: Show confirmation
- `executeAction(action, payload)`: Send action to twin

### Animation Loop

The `updateAlertIndicators()` function runs every frame to:
1. Move markers with vessel position
2. Update pulsing animation for critical alerts
3. Project 3D positions to 2D screen for labels
4. Hide labels when behind camera

## Customization

### Add New Alert Types

Edit `build_kimi/twin/core.py`:
```python
self._watchers.add({
    "id": "my-custom-alert",
    "name": "My Custom Alert",
    "when": lambda f: f.get("my_channel", 0) > 100,
    "action": {
        "name": "raise_alert",
        "payload": lambda f: {
            "severity": "warning",
            "code": "MY_ALERT",
            "message": f"My channel is {f['my_channel']}"
        },
        "reason": lambda f: f"my_channel={f['my_channel']}",
        "priority": lambda f: 0.7,
    },
    "cooldown_s": 30.0,
})
```

### Modify Visual Styles

Edit `style.css`:
```css
/* Change critical alert color */
.alert-item.priority-critical {
  border-color: #ff0000;  /* Custom color */
  background: rgba(255, 0, 0, 0.15);
}

/* Adjust pulse animation */
@keyframes alert-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(255, 0, 0, 0.4); }
  50% { box-shadow: 0 0 0 16px rgba(255, 0, 0, 0); }
}
```

### Add Quick Actions

Edit `index.html`:
```html
<button class="action-btn" data-action="my_action" title="My Action">
  🎯 My Action
</button>
```

Edit `app.js`:
```javascript
// Add to messages object
const messages = {
  'my_action': 'Execute my custom action?',
  // ... existing messages
};
```

## Troubleshooting

### Alerts Not Appearing

1. **Check twin connection**:
   - Open browser console
   - Look for "Connected to twin core" message
   - Verify WebSocket connection to `ws://localhost:8090`

2. **Check watcher rules**:
   - Look for `[watcher fired]` messages in twin logs
   - Verify `enable_watchers=true` in twin config

3. **Check action format**:
   ```javascript
   console.log('[action] Received:', action);
   ```

### 3D Indicators Not Showing

1. **Check Three.js scene**:
   - Verify vessel is visible
   - Check camera position

2. **Check marker creation**:
   ```javascript
   console.log('Active markers:', alertMarkers.size);
   ```

3. **Verify animation loop**:
   ```javascript
   console.log('Frame rendered');
   ```

### Action Buttons Not Working

1. **Check dialog elements**:
   ```javascript
   console.log('Dialog:', document.getElementById('action-dialog'));
   ```

2. **Verify WebSocket**:
   ```javascript
   console.log('WebSocket:', ws?.readyState);
   ```

## Performance

**Memory Management**:
- Active alerts: No limit (expected < 10 active)
- Alert history: Max 20 items
- 3D markers: One per active alert

**Animation Cost**:
- Alert indicator updates: ~1ms per frame
- DOM updates only on new alerts
- Label projection: ~0.5ms per label

**Optimization Tips**:
- Use cooldown periods to prevent alert spam
- Dismiss alerts manually to free memory
- Limit history size for low-memory devices

## Future Enhancements

**Planned Features**:
1. Audio alerts for critical priorities
2. Alert grouping and filtering
3. Export alert history to CSV
4. Custom alert thresholds via UI
5. Alert acknowledgment workflow
6. Integration with vessel notification system

**Contributing**:
To add new features:
1. Update this documentation
2. Add browser console tests
3. Test with simulator
4. Verify with real NMEA data

## License

Part of the AELMA (Autonomous Electronic Logging & Monitoring Assistant) project.
