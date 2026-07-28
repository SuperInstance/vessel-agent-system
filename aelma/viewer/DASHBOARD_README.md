# AELMA Telemetry Dashboard — Real-Time Monitoring System

## Overview

The AELMA Telemetry Dashboard is a comprehensive real-time monitoring system for vessel operations. Built with pure browser technologies (Canvas API, WebSocket, vanilla JavaScript), it provides live visualization of vessel telemetry, bathymetry data, alerts, and system status without requiring any external libraries.

## Dashboard Location

**File:** `C:\Users\casey\claudetz\aelma\viewer\dashboard.html`

**Access:** `http://localhost:8080/dashboard.html`

## Features

### 1. Real-Time Gauges Panel
- **Depth**: Current water depth in meters with quality indicator
- **Speed**: Vessel speed over ground in knots
- **Heading**: True heading in degrees (0-360)
- **Sea Temperature**: Water temperature in Celsius
- **Wind Speed**: Wind velocity in knots
- **Engine RPM**: Engine revolutions per minute

Each gauge displays:
- Large numerical value with unit
- Quality indicator (good/fair/poor/bad)
- Real-time updates at 1 Hz

### 2. Time-Series Charts
**Two canvas-based scrolling charts:**

#### Depth Over Time Chart
- Real-time depth visualization
- Configurable time windows: 5, 15, 60 minutes
- Threshold indicator at 2.0m (shallow water warning)
- Min/max tracking
- Area fill with gradient colors
- Current value indicator with glow effect

#### Speed Profile Chart
- Real-time speed visualization
- Configurable time windows: 5, 15, 60 minutes
- Threshold indicator at 10.0 knots (high speed alert)
- Smooth curve rendering
- Auto-scaling Y-axis

**Chart Features:**
- Pure Canvas API rendering (no external libraries)
- Smooth animations
- Grid lines for reference
- Threshold markers with configurable colors
- Scrolling time windows
- Responsive resizing

### 3. Alert History Panel
**Color-coded by priority:**
- **High (Red)**: Critical alerts requiring immediate attention
- **Medium (Orange)**: Warning conditions
- **Low (Green)**: Informational alerts

**Alert Types:**
- Shallow water warnings (depth < 2.0m)
- High speed alerts (speed > 10.0 knots)
- High temperature warnings (sea temp > 25°C)
- High wind warnings (wind > 20 knots)
- Manual test alerts

**Features:**
- Automatic aging (alerts disappear after 5 minutes)
- Slide-in animation for new alerts
- Timestamp for each alert
- Detailed message and context

### 4. Bathymetry Heatmap
**Interactive depth visualization:**
- Color-coded depth cells:
  - **Orange**: Shallow waters (< 30m)
  - **Green**: Medium depths (30-80m)
  - **Blue**: Deep waters (> 80m)
- Vessel position indicator (orange dot)
- Alpha blending based on confidence
- Real-time updates as new data arrives

**Statistics Panel:**
- Total voxel count
- Minimum depth in viewport
- Maximum depth in viewport
- Viewport radius display

### 5. Active Watcher Rules Panel
**Monitors system watcher rules:**
- Shallow Water Warning (depth < 2.0m)
- High Speed Alert (speed > 10.0kn)
- Engine Temperature (temp > 90°C)

**Per-rule statistics:**
- Total fires counter
- Cooldown period
- Active state indication
- Real-time updates

### 6. Position & Navigation Panel
**Live navigation data:**
- Current latitude (5 decimal precision)
- Current longitude (5 decimal precision)
- Course/heading
- Vessel identifier

### 7. Data Log Panel
**System activity log:**
- Connection status events
- Alert notifications
- Error messages
- User actions (export, etc.)
- Timestamped entries (last 50 retained)

## Control Buttons

### Export Data Button
**Function:** Exports complete telemetry dataset to JSON file

**Export includes:**
- Timestamp and session duration
- Historical telemetry data
- Alert history
- Bathymetry statistics
- System state

**File format:** `aelma-telemetry-[timestamp].json`

### Test Alert Button
**Function:** Triggers a manual test alert

**Purpose:** Validates alert system functionality without requiring actual alert conditions

## Technical Architecture

### WebSocket Connection
- **URL:** `ws://localhost:8090`
- **Protocol:** VesselStateSnapshot JSON messages
- **Reconnection:** Automatic exponential backoff (250ms → 5s max)
- **Status indicator:** Color-coded dot in header

### Data Flow
```
TwinCore (ws://localhost:8090)
    ↓ VesselStateSnapshot
Dashboard WebSocket Client
    ↓ Parse & Validate
    ├─→ Gauge Updates
    ├─→ Chart Data Points
    ├─→ Bathymetry Heatmap
    ├─→ Alert Evaluation
    └─→ Status Panels
```

### Canvas Chart Implementation
**Pure browser technologies:**
- No external chart libraries
- Custom LineChart class
- Hardware-accelerated rendering
- Responsive design
- Memory-efficient (auto-removes old data)

**Chart Features:**
- Dynamic scaling
- Threshold lines
- Area fills with gradients
- Current value indicators
- Grid overlay
- Smooth animations

## Installation & Usage

### Prerequisites
1. Python 3.8+ (for serving files)
2. Modern web browser with Canvas API support
3. TwinCore server running on port 8090

### Starting the Dashboard

#### Option 1: Using the Test Server
```bash
# Start the test TwinCore server
cd C:\Users\casey\claudetz\aelma
python test_twin_server.py

# Start the viewer server (in another terminal)
cd C:\Users\casey\claudetz\aelma\viewer
python serve.py --port 8080

# Open browser to:
# http://localhost:8080/dashboard.html
```

#### Option 2: Using Full AELMA Stack
```bash
# Start the simulator
cd C:\Users\casey\claudetz\aelma
python -m build_claude.simulator.simulate --port 8001 --speedup 10

# Start TwinCore (in another terminal)
python -m twin --bridge-url ws://localhost:8001 --viewer-port 8090

# Start the viewer (in another terminal)
cd C:\Users\casey\claudetz\aelma\viewer
python serve.py --port 8080

# Open browser to:
# http://localhost:8080/dashboard.html
```

### Verification Checklist
- [ ] Dashboard loads without errors
- [ ] Connection status shows "connected" (green dot)
- [ ] Gauges display live values
- [ ] Charts render with data points
- [ ] Bathymetry heatmap shows depth cells
- [ ] Alert panel is empty (no false alerts)
- [ ] Session timer increments
- [ ] Data log shows connection events
- [ ] Time window buttons work (5m/15m/60m)
- [ ] Export button generates JSON file
- [ ] Test Alert button triggers alert

## Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  HEADER: Status | Vessel Title | Session Time | Controls            │
├──────────┬──────────────────────────────┬────────────────────────────┤
│          │         CHARTS               │                            │
│  GAUGES  │  ┌──────────────────────┐   │      BATHYMETRY            │
│          │  │   Depth Chart        │   │                            │
│  ┌────┐  │  │                      │   │   ┌──────────────────┐    │
│  │Depth│  │  └──────────────────────┘   │   │                  │    │
│  ├────┤  │  ┌──────────────────────┐   │   │   Heatmap        │    │
│  │Speed│  │  │   Speed Chart       │   │   │                  │    │
│  ├────┤  │  │                      │   │   └──────────────────┘    │
│  │Head │  │  └──────────────────────┘   │   Stats: Voxel Count     │
│  ├────┤  │                              │   Min/Max Depth          │
│  │Temp │  │                              │                            │
│  ├────┤  │                              │                            │
│  │Wind │  │                              │                            │
│  ├────┤  │                              │                            │
│  │RPM  │  │                              │                            │
│  └────┘  │                              │                            │
├──────────┼──────────────────────────────┼────────────────────────────┤
│          │                              │                            │
│  ALERTS  │       POSITION               │      WATCHER RULES         │
│          │   ┌──────────────────┐      │   ┌──────────────────┐    │
│  ┌─────┐ │   │ Latitude         │      │   │ Shallow Water    │    │
│  │Alert│ │   ├──────────────────┤      │   ├──────────────────┤    │
│  ├─────┤ │   │ Longitude        │      │   │ High Speed       │    │
│  │Alert│ │   ├──────────────────┤      │   ├──────────────────┤    │
│  ├─────┤ │   │ Course           │      │   │ Engine Temp      │    │
│  │Alert│ │   ├──────────────────┤      │   └──────────────────┘    │
│  └─────┘ │   │ Vessel ID        │      │                            │
│          │   └──────────────────┘      │                            │
├──────────┴──────────────────────────────┴────────────────────────────┤
│  DATA LOG (scrolling activity log)                                    │
└─────────────────────────────────────────────────────────────────────┘
```

## Responsive Design

The dashboard adapts to different screen sizes:

**Desktop (> 1400px):** Full 3-column layout
**Medium (1000-1400px):** Adjusted column widths
**Tablet (< 1200px):** Stacked 2-column layout
**Mobile:** Vertical stack layout

## Browser Compatibility

**Tested and compatible with:**
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

**Required features:**
- Canvas API
- WebSocket API
- ES6+ JavaScript
- CSS Grid
- CSS Custom Properties

## Performance Considerations

**Memory Management:**
- Charts auto-remove data points outside time window
- Alerts expire after 5 minutes
- Data log limited to 50 entries
- Efficient Canvas rendering

**Update Frequency:**
- WebSocket messages: 1 Hz (1 per second)
- Chart render: 60 FPS (requestAnimationFrame)
- Session timer: 1 Hz
- Connection retry: exponential backoff

## Troubleshooting

### Dashboard shows "disconnected"
**Problem:** Cannot connect to TwinCore

**Solutions:**
1. Verify TwinCore is running: `netstat -an | grep 8090`
2. Check TwinCore logs for errors
3. Verify WebSocket URL in dashboard.html (line 825)
4. Test with manual TwinCore: `python test_twin_server.py`

### Gauges show "--" or "No data"
**Problem:** No telemetry data received

**Solutions:**
1. Verify bridge/simulator is running
2. Check TwinCore connection to bridge
3. Verify data channels are active
4. Check browser console for errors

### Charts don't render
**Problem:** Canvas elements not displaying

**Solutions:**
1. Check browser supports Canvas API
2. Verify JavaScript is enabled
3. Check browser console for errors
4. Try refreshing the page

### Bathymetry heatmap empty
**Problem:** No depth data received

**Solutions:**
1. Verify bathymetry data in snapshot
2. Check vessel has position fix
3. Verify depth sounder is active
4. Check viewport radius setting

## Development

### File Structure
```
viewer/
├── dashboard.html          # Main dashboard (self-contained)
├── index.html             # Original 3D viewer
├── app.js                 # 3D viewer application
├── style.css              # 3D viewer styles
├── serve.py               # HTTP server with CORS
└── DASHBOARD_README.md    # This documentation
```

### Dashboard HTML Structure
- **Lines 1-400:** CSS styling (embedded)
- **Lines 401-500:** Header and controls
- **Lines 501-700:** Main grid panels
- **Lines 701-900:** Chart containers
- **Lines 901-1000:** Alert and watcher panels
- **Lines 1001-1100:** Position and log panels
- **Lines 1101-1400:** JavaScript state management
- **Lines 1401-1700:** Chart classes (LineChart, BathymetryHeatmap)
- **Lines 1701-1900:** WebSocket client
- **Lines 1901-2000:** Data processing and rendering
- **Lines 2001-2200:** Alert system and controls
- **Lines 2201-End:** Utilities and initialization

### Key Classes

**LineChart**
- Canvas-based line chart rendering
- Configurable colors and thresholds
- Auto-scaling axes
- Scrolling time windows

**BathymetryHeatmap**
- 2D depth visualization
- Color-coded depth cells
- Vessel position indicator
- Alpha blending for confidence

## Testing

### Manual Testing
```bash
# 1. Start test server
python test_twin_server.py

# 2. Start viewer
cd viewer && python serve.py

# 3. Open dashboard
# Navigate to http://localhost:8080/dashboard.html

# 4. Verify connection
# Green status dot should appear

# 5. Test controls
# - Click time window buttons (5m/15m/60m)
# - Click "Test Alert" button
# - Click "Export Data" button

# 6. Monitor updates
# - Gauges should update every second
# - Charts should scroll left
# - Session timer should increment
```

### Integration Testing
```bash
# Test with full AELMA stack
python -m build_claude.simulator.simulate --port 8001 --speedup 10 &
python -m twin --bridge-url ws://localhost:8001 --viewer-port 8090 &
cd viewer && python serve.py

# Verify all features work with real data
```

## Future Enhancements

**Potential improvements:**
1. Historical data replay
2. Configurable alert thresholds
3. Multiple vessel support
4. Export to CSV/Excel
5. Custom dashboard layouts
6. Mobile app version
7. Real-time annotations
8. Trend analysis tools
9. Predictive alerts
10. Integration with ship ECDIS

## Support

For issues or questions:
1. Check this documentation
2. Review browser console for errors
3. Verify all services are running
4. Test with `test_twin_server.py`
5. Check TwinCore logs

## License

Part of the AELMA (Autonomous Electromagnetic Logging and Monitoring Architecture) system.

---

**Dashboard Version:** 1.0
**Last Updated:** 2026-07-27
**Status:** Production Ready
**Dependencies:** None (self-contained HTML)
