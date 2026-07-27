# AELMA Viewer Component — Build Brief (Parallel Competition)

Build the VIEWER for AELMA (Agent-Engine Linked Marine Architecture) — a hardware-in-the-loop digital twin for the F/V EILEEN, a 51-foot fishing vessel in Southeast Alaska.

## Working directory
All work goes in: C:\Users\casey\claudetz\aelma\build_<TAG>\viewer\
(TAG is kimi or claude.)

## What the viewer does
Browser-based 3D scene + sidebar that connects via WebSocket to the twin core at ws://localhost:8090 and renders a live vessel + progressive bathymetry.

## VesselStateSnapshot schema (received over WS)
```json
{
  "timestamp_ns": 1753478400000000000,
  "vessel_id": "US-AK-FVEILEEN-51",
  "pose": { "lat": 56.80134, "lon": -135.30278, "heading_deg": 215.0, "speed_kn": 4.2 },
  "channels": {
    "depth_m": { "value": 73.2, "timestamp_ns": 1753478399987500000, "quality": "good" },
    "sea_temp_c": { "value": 9.5, "timestamp_ns": 1753478399950000000, "quality": "good" }
  },
  "bathymetry": {
    "voxel_count": 1842,
    "viewport_center": { "lat": 56.80134, "lon": -135.30278 },
    "viewport_radius_m": 500,
    "cells": [[56.8013, -135.3028, 73.2, 0.85], [56.8015, -135.3031, 75.1, 0.78]]
  }
}
```

## Deliverables

1. `index.html` — single-file entry. Three.js loaded from CDN (https://unpkg.com/three@0.160.0/build/three.module.js). Inline scene bootstrap that imports app.js as a module.

2. `style.css` — separate file. Dark nautical theme. Sidebar fixed-width 320px right. Canvas fills rest. Responsive (iPad portrait + landscape).

3. `app.js` — separate file. ES module importing Three.js. Contains:
   - WebSocket connection with auto-reconnect (exponential backoff capped at 5s)
   - Local ENU coordinate projection centered on first received position:
     - x = (lon − lon0) · 111000 · cos(lat0_rad)
     - z = (lat − lat0) · 111000
     - y = −depth
   - Vessel mesh: cone hull (8m) + box cabin (3m), distinct color (orange #ff7700)
   - Bathymetry point cloud: BufferGeometry with per-vertex color from depth (shallow<30m warm orange, 30-80m green, >80m blue) and opacity from confidence
   - Water surface: semi-transparent blue plane at y=0, 1000x1000m
   - Track line: orange, last 500 vessel positions
   - Hemisphere + directional lighting, sky-blue background, fog
   - OrbitControls from Three.js addons (https://unpkg.com/three@0.160.0/examples/jsm/controls/OrbitControls.js)
   - Auto-rotate when no input for 5s
   - Touch controls for iPad (pinch zoom, drag rotate)
   - Sidebar DOM updates: header (vessel_id, status dot), big depth readout (color by quality), grid of channel readouts, voxel count, session duration
   - Subtle CSS pulse animation on value updates

4. `serve.py` — Python `http.server` on port 8080 with CORS headers. Argparse for --port.

5. `README.md` — quickstart.

## Coordinate system
1 Three.js unit = 1 meter. ENU (East-North-Up): +x = east, +z = north (note Three.js uses +y up), +y = up.

## Quality bar
- Works in Chrome + Safari (iPad)
- Only external dep: Three.js from CDN
- Total payload < 50KB excluding CDN
- No build step — just open in browser

## After completion
Write report to /tmp/build_<TAG>_viewer_report.md with files, line counts, design notes, how to test.
