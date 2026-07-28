# AELMA Dashboard — Quick Reference Card

## 🚀 Quick Start

```bash
# Option 1: Test Environment
cd C:\Users\casey\claudetz\aelma
python test_twin_server.py                    # Terminal 1
cd viewer && python serve.py                  # Terminal 2
# Open: http://localhost:8080/dashboard.html

# Option 2: Full Stack
python -m build_claude.simulator.simulate    # Terminal 1
python -m twin --bridge-url ws://localhost:8001  # Terminal 2
cd viewer && python serve.py                 # Terminal 3
# Open: http://localhost:8080/dashboard.html

# Option 3: Quick Launch
start_dashboard_test.bat                     # Windows
```

## 📍 Dashboard Location

**File:** `C:\Users\casey\claudetz\aelma\viewer\dashboard.html`
**URL:** `http://localhost:8080/dashboard.html`
**WebSocket:** `ws://localhost:8090`

## 🎯 Features Overview

| Panel | Features | Update Rate |
|-------|----------|-------------|
| **Gauges** | Depth, Speed, Heading, Temp, Wind, RPM | 1 Hz |
| **Charts** | Depth & Speed time-series, 5/15/60m windows | 60 FPS |
| **Alerts** | Color-coded priority, 5-min retention | Real-time |
| **Bathymetry** | Heatmap, vessel position, statistics | 1 Hz |
| **Watchers** | Active rules, fire counts, cooldowns | Real-time |
| **Position** | Lat/Lon, course, vessel ID | 1 Hz |
| **Log** | Activity log, 50-entry retention | Event-driven |

## 🎨 Color Codes

### Quality Indicators
- 🟢 **Good**: Green - Reliable data
- 🟡 **Fair**: Yellow - Marginal quality
- 🟠 **Poor**: Orange - Low quality
- 🔴 **Bad**: Red - Unreliable

### Alert Priorities
- 🔴 **High**: Critical - Immediate attention
- 🟡 **Medium**: Warning - Monitor closely
- 🟢 **Low**: Informational - For awareness

### Bathymetry Depths
- 🟠 **Orange**: Shallow (< 30m)
- 🟢 **Green**: Medium (30-80m)
- 🔵 **Blue**: Deep (> 80m)

### Connection Status
- 🟢 **Connected**: Live data feed
- 🔵 **Connecting**: Establishing connection
- 🔴 **Disconnected**: Connection lost

## 🎛️ Control Buttons

### Export Data
- **Action:** Downloads JSON export
- **Content:** All telemetry, alerts, bathymetry
- **File:** `aelma-telemetry-[timestamp].json`

### Test Alert
- **Action:** Triggers manual test alert
- **Purpose:** Validate alert system
- **Type:** Low priority informational

## 📊 Chart Time Windows

| Button | Window | Data Points |
|--------|--------|-------------|
| **5m** | 5 minutes | ~300 points |
| **15m** | 15 minutes | ~900 points |
| **60m** | 60 minutes | ~3600 points |

## 🔧 Troubleshooting

### No Connection
```bash
# Check services
netstat -an | grep 8090    # TwinCore
netstat -an | grep 8080    # Viewer

# Restart services
python test_twin_server.py
cd viewer && python serve.py
```

### No Data
```bash
# Verify TwinCore output
curl -s http://localhost:8080/dashboard.html

# Check browser console
# F12 → Console tab → Look for errors
```

### Charts Not Rendering
```bash
# Verify browser supports Canvas
# Check JavaScript is enabled
# Try refresh (Ctrl+R)
```

## 📱 Browser Support

✅ Chrome 90+
✅ Firefox 88+
✅ Safari 14+
✅ Edge 90+

## 📐 Layout Breakpoints

| Size | Layout | Columns |
|------|--------|---------|
| > 1400px | Desktop | 3 columns |
| 1000-1400px | Medium | Adjusted 3-col |
| < 1200px | Tablet | 2 columns |
| < 768px | Mobile | 1 column |

## 🔍 Key Classes

### LineChart
```javascript
const chart = new LineChart(canvas, {
  color: '#00ff88',           // Line color
  fillColor: 'rgba(0,255,136,0.1)',  // Area fill
  threshold: 2.0,            // Threshold value
  thresholdColor: '#ff4444'   // Threshold line color
});
```

### BathymetryHeatmap
```javascript
const heatmap = new BathymetryHeatmap(canvas);
heatmap.updateCells(cells);   // Update depth data
heatmap.render();             // Render visualization
```

## 📡 WebSocket Protocol

### Connection
```javascript
ws = new WebSocket('ws://localhost:8090');
```

### Message Format
```json
{
  "timestamp_ns": 1753478400000000000,
  "vessel_id": "US-AK-FVEILEEN-51",
  "pose": {
    "lat": 56.80134,
    "lon": -135.30278,
    "heading_deg": 215.0,
    "speed_kn": 4.2
  },
  "channels": {
    "depth_m": {"value": 73.2, "quality": "good"},
    "sea_temp_c": {"value": 9.5, "quality": "good"}
  },
  "bathymetry": {
    "voxel_count": 1842,
    "cells": [[lat, lon, depth, confidence]]
  }
}
```

## 🎓 Quick Tips

1. **First Time**: Use test server for quick verification
2. **Development**: Check browser console for errors
3. **Testing**: Use "Test Alert" button to verify alerts
4. **Export**: Regular exports for data backup
5. **Performance**: Close unused tabs for better performance

## 📚 Documentation Files

- **DASHBOARD_README.md** - Comprehensive documentation
- **DASHBOARD_DELIVERY_SUMMARY.md** - Complete delivery summary
- **test_twin_server.py** - Test data generator
- **start_dashboard_test.bat** - Quick start script

## 🆘 Support

For issues:
1. Check this reference
2. Review DASHBOARD_README.md
3. Check browser console
4. Verify services are running
5. Test with test_twin_server.py

---

**Version:** 1.0 | **Date:** 2026-07-27 | **Status:** Production Ready
