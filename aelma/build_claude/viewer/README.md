# AELMA Viewer

Browser-based 3D viewer for the AELMA (Agent-Engine Linked Marine Architecture) digital twin of the F/V EILEEN.

## Quick Start

### Option 1: Python Server (recommended)

```bash
python serve.py
# or with a custom port:
python serve.py --port 9000
```

Then open `http://localhost:8080` in Chrome or Safari.

### Option 2: Any static file server

Serve the `viewer/` directory with any web server. The viewer is a static site that only needs Three.js from CDN.

## What It Does

- Connects via WebSocket to `ws://localhost:8090`
- Renders a live 3D vessel (cone hull + box cabin, orange #ff7700)
- Displays progressive bathymetry as a colored point cloud:
  - Shallow (< 30m): warm orange
  - Mid (30-80m): green
  - Deep (> 80m): blue
  - Opacity from confidence values
- Shows a semi-transparent water surface at y=0
- Tracks the last 500 vessel positions as an orange line
- Auto-rotates the camera after 5 seconds of no input
- Touch controls for iPad (pinch zoom, drag rotate via OrbitControls)

## Sidebar Readouts

- Vessel ID and connection status dot
- Large depth readout (color-coded by quality)
- Channel grid (sea temp, etc. -- auto-populated)
- Voxel count, speed, heading, session duration, position

## Requirements

- Modern browser with WebGL (Chrome, Safari)
- Internet connection (for Three.js CDN)
- AELMA twin core running on `ws://localhost:8090`

## Files

| File | Purpose |
|------|---------|
| `index.html` | Single-file entry point |
| `style.css` | Dark nautical theme, responsive layout |
| `app.js` | ES module: WebSocket, Three.js scene, DOM updates |
| `serve.py` | Python HTTP server with CORS headers |
| `README.md` | This file |

## Coordinate System

ENU (East-North-Up): 1 Three.js unit = 1 meter.

- x = (lon - lon0) * 111000 * cos(lat0_rad)
- z = (lat - lat0) * 111000
- y = -depth

## Testing Without the Twin Core

The viewer will show a "Connecting..." overlay and attempt reconnection with exponential backoff (capped at 5 seconds). To test rendering without the core, you can inject a test message via browser console:

```javascript
const testSnapshot = {
  timestamp_ns: Date.now() * 1e6,
  vessel_id: "US-AK-FVEILEEN-51",
  pose: { lat: 56.80134, lon: -135.30278, heading_deg: 215.0, speed_kn: 4.2 },
  channels: {
    depth_m: { value: 73.2, timestamp_ns: 0, quality: "good" },
    sea_temp_c: { value: 9.5, timestamp_ns: 0, quality: "good" }
  },
  bathymetry: {
    voxel_count: 2,
    viewport_center: { lat: 56.80134, lon: -135.30278 },
    viewport_radius_m: 500,
    cells: [[56.8013, -135.3028, 73.2, 0.85], [56.8015, -135.3031, 75.1, 0.78]]
  }
};
// Dispatch manually:
const ws = new WebSocket("ws://localhost:8090");
// Or call the handler directly if accessible
```
