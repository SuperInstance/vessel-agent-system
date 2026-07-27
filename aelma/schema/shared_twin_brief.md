# AELMA Twin Component — Build Brief (Parallel Competition)

You are building the TWIN CORE of AELMA (Agent-Engine Linked Marine Architecture) — a digital twin for the F/V EILEEN, a 51-foot commercial fishing vessel home-ported in Sitka, Alaska.

## Working directory
All work goes in: C:\Users\casey\claudetz\aelma\build_<TAG>\twin\
(TAG is kimi or claude — launcher sets it.)

## What the twin does
A Python asyncio process that:
1. Connects as WebSocket CLIENT to the bridge at ws://localhost:8000
2. Receives TelemetryPacket JSON objects
3. Maintains VesselState (latest reading per channel, smoothed pose via dead reckoning between fixes)
4. Runs the progressive bathymetry TSDF layer: every depth+position becomes a voxel, accumulates evidence
5. Broadcasts VesselStateSnapshot JSON to viewer WebSocket clients (twin is a WS SERVER on port 8090)

## Schemas (already exist — match exactly)
- C:\Users\casey\claudetz\aelma\schema\telemetry_packet.schema.json (consumes)
- C:\Users\casey\claudetz\aelma\schema\vessel_state.schema.json (produces)
- C:\Users\casey\claudetz\aelma\schema\bathymetry_voxel.schema.json (internal storage)

## Deliverables (in your build dir)

1. `state.py` — VesselState class. Holds latest per-channel reading, current pose {lat, lon, heading_deg, speed_kn}. Methods:
   - `apply_packet(packet: dict) -> None` — updates state. For position packets, compute heading from previous position (great-circle bearing) and speed (haversine distance / dt).
   - `snapshot(vessel_id: str, viewport: list) -> dict` — returns VesselStateSnapshot matching schema.

2. `bathymetry.py` — BathymetryGrid class. Progressive TSDF. Internally dict keyed by (lat_cell, lon_cell) quantized to ~10m at current latitude. Each cell: depth_m (running average), sample_count, last_sample_ns, source. Methods:
   - `fuse(lat, lon, depth_m, timestamp_ns, source="sounder")` — running average + sample_count++
   - `confidence(cell) -> float` — 0.1 * min(sample_count, 20)/20 with recency decay (10% per week)
   - `cells_in_radius(lat, lon, radius_m) -> list[[lat, lon, depth, confidence]]`
   - `total_voxels() -> int`
   - `save(path)` / `load(path)` — JSON persistence

3. `core.py` — TwinCore class. Composes VesselState + BathymetryGrid. Asyncio. Connects to bridge WS, listens for TelemetryPackets. On each packet: state.apply_packet(); if depth packet, also bathymetry.fuse() with current position. Periodic broadcast (every 1s) of VesselStateSnapshot to all viewer WS clients. Persists bathymetry every 60s.

4. `__init__.py`, `__main__.py` (CLI: --bridge-url ws://localhost:8000, --viewer-port 8090, --vessel-id US-AK-FVEILEEN-51, --bathymetry-path bathymetry.json, --broadcast-interval 1.0)

5. `README.md` — quickstart.

6. Tests: `tests/test_twin.py` covering:
   - state apply+snapshot
   - bearing computation (known vectors)
   - bathymetry fuse (single + multiple samples same cell, running average correct)
   - cell quantization (nearby points map to same cell)
   - viewport radius filtering
   - confidence formula (sample count + recency)
   - persistence save/load roundtrip
   - haversine distance vs known formula

## Math
- Bearing: θ = atan2(sin(Δlon)·cos(lat2), cos(lat1)·sin(lat2) − sin(lat1)·cos(lat2)·cos(Δlon)) → degrees → [0, 360)
- Distance (haversine simplified): d ≈ sqrt(Δlat² + (Δlon·cos(lat_mean))²) · 111000 m
- Cell quantization: lat_cell = round(lat / (10/111000)); lon_cell = round(lon / (10/(111000·cos(lat_rad))))

## Constraints
- Python 3.11+. asyncio + `websockets` (PyPI) + stdlib. numpy only if needed.
- Each file < 350 lines.
- Type hints. `from __future__ import annotations`.
- Docstrings throughout.
- pytest for tests.

## Quality bar
cd /c/Users/casey/claudetz/aelma && python -m pytest build_<TAG>/tests/test_twin.py -v
All tests must pass.

## After completion
Write report to /tmp/build_<TAG>_twin_report.md with files, line counts, design decisions, test results.
