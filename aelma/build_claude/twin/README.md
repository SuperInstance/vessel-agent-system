# AELMA Twin Core

Digital twin for the **F/V EILEEN**, a 51-foot commercial fishing vessel
home-ported in Sitka, Alaska.

## What it does

The twin is a Python `asyncio` process that:

1. Connects as a **WebSocket client** to the AELMA bridge
   (`ws://localhost:8000`).
2. Receives `TelemetryPacket` JSON objects.
3. Maintains `VesselState` -- latest reading per channel, smoothed pose
   (heading/speed computed from successive position fixes via great-circle
   bearing and haversine distance).
4. Runs a **progressive bathymetry TSDF layer**: every depth + position
   sample becomes a voxel in a ~10 m quantised grid, accumulating a
   running-average depth and confidence.
5. Broadcasts `VesselStateSnapshot` JSON to **viewer WebSocket clients**
   (the twin acts as a WS server on port 8090).

## Quick start

```bash
# Install dependencies (Python 3.11+)
pip install websockets pytest

# Run the twin
python -m twin \
    --bridge-url ws://localhost:8000 \
    --viewer-port 8090 \
    --vessel-id US-AK-FVEILEEN-51 \
    --bathymetry-path bathymetry.json \
    --broadcast-interval 1.0
```

## CLI options

| Flag | Default | Description |
|------|---------|-------------|
| `--bridge-url` | `ws://localhost:8000` | WebSocket URL of the AELMA bridge |
| `--viewer-port` | `8090` | TCP port for viewer WS server |
| `--vessel-id` | `US-AK-FVEILEEN-51` | ISO-style vessel identifier |
| `--bathymetry-path` | `bathymetry.json` | Path for bathymetry JSON persistence |
| `--broadcast-interval` | `1.0` | Seconds between snapshot broadcasts |
| `--log-level` | `INFO` | Logging level |

## Architecture

```
Bridge (ws://localhost:8000)
    |
    | TelemetryPacket JSON
    v
+------------------+
|    TwinCore      |
|                  |
|  VesselState     |  -- pose, channels, heading/speed
|  BathymetryGrid  |  -- progressive TSDF (~10 m cells)
+------------------+
    |
    | VesselStateSnapshot JSON (every 1 s)
    v
Viewers (ws://localhost:8090)
```

### Modules

| File | Description |
|------|-------------|
| `state.py` | `VesselState` -- per-channel state, pose, bearing/speed computation |
| `bathymetry.py` | `BathymetryGrid` -- progressive TSDF, cell quantisation, confidence |
| `core.py` | `TwinCore` -- asyncio orchestrator (bridge client + viewer server) |
| `__main__.py` | CLI entry point |

## Math reference

**Bearing** (initial great-circle azimuth):

    theta = atan2(sin(dlon)*cos(lat2),
                  cos(lat1)*sin(lat2) - sin(lat1)*cos(lat2)*cos(dlon))

Result normalised to [0, 360).

**Distance** (equirectangular approximation):

    d = sqrt(dlat^2 + (dlon*cos(lat_mean))^2) * 111_000  [meters]

**Cell quantisation** (~10 m grid):

    lat_cell = round(lat / (10 / 111_000))
    lon_cell = round(lon / (10 / (111_000 * cos(lat_rad))))

**Confidence**:

    base = min(0.1 * sample_count, 0.9)
    decay = max(0, 1 - 0.1 * weeks_old)
    confidence = base * decay

## Tests

```bash
cd C:\Users\casey\claudetz\aelma
python -m pytest build_claude/tests/test_twin.py -v
```

## Schemas

The twin consumes and produces JSON matching these schemas (in `schema/`):

- `telemetry_packet.schema.json` -- consumed from bridge
- `vessel_state.schema.json` -- produced for viewers
- `bathymetry_voxel.schema.json` -- internal storage format
