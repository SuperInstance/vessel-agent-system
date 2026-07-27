# AELMA Bridge

NMEA 0183 to telemetry-packet bridge for the F/V EILEEN digital twin.

## What It Is

A small async server that reads NMEA 0183 sentences from marine
instruments over TCP and republishes them as structured JSON telemetry
packets over WebSocket. It is the ingestion edge of the AELMA
(Agent-Engine Linked Marine Architecture) system.

## Architecture

```
  NMEA instruments                   Twin core / viewers
  (GPS, depth, wind, temp)           (any WS client)
        |                                    ^
        v                                    |
   TCP :8001 (text) ---> [ Bridge ] ---> WS :8000 (JSON)
                              |
                    +---------+---------+
                    |                   |
              nmea.py (parse)     quality.py (grade)
```

The bridge:

1. Accepts plain-TCP connections on port **8001**. Each line is one NMEA
   sentence (`$GPGGA,...*42`).
2. Parses each sentence with pure functions (`nmea.py`).
3. Assigns `timestamp_ns` from `time.time_ns()` and a quality grade
   (`quality.py`).
4. Builds a telemetry packet matching `telemetry_packet.schema.json`.
5. Broadcasts the packet as JSON to all WebSocket subscribers on port
   **8000**.
6. On new subscriber connect, immediately sends the last-known reading
   for every channel.

## Protocol

### TCP input (port 8001)

Newline-delimited ASCII NMEA 0183 sentences. Example:

```
$GPGGA,123456,5648.080,N,13518.167,W,1,08,0.8,0.0,M,0.0,M,,*59
$SDDPT,73.2,-1.5,*3A
$YXMTW,12.5,C*1F
```

### WebSocket output (port 8000)

Each message is one JSON telemetry packet:

```json
{
  "timestamp_ns": 1753478400000000000,
  "source": "nmea0183",
  "channel": "depth_m",
  "value": 73.2,
  "quality": "good",
  "sentence": "$SDDPT,73.2,-1.5,*3A"
}
```

Supported channels include: `position.lat`, `position.lon`, `depth_m`,
`sog_kn`, `cog_deg`, `wind_kts_true`, `wind_kts_apparent`,
`wind_dir_deg_true`, `wind_dir_deg_apparent`, `sea_temp_c`,
`air_temp_c`, `baro_mb`.

## Supported NMEA Sentences

| Sentence  | Data extracted |
|-----------|---------------|
| `$GPGGA` / `$GNGGA` | position.lat, position.lon |
| `$GPRMC` / `$GNRMC` | position.lat, position.lon, sog_kn, cog_deg |
| `$SDDPT` | depth_m |
| `$SDDBT` | depth_m |
| `$WIMWV` | wind speed (true/apparent), wind direction |
| `$YXMTW` | sea_temp_c |
| `$YXXDR` | air_temp_c, baro_mb (also sea_temp_c if labeled) |

## How to Run

```bash
# From the build directory:
python -m bridge --tcp-port 8001 --ws-port 8000 --debug

# Or with defaults (no debug):
python -m bridge
```

### Quick test with netcat and websocat

```bash
# Terminal 1: start the bridge
python -m bridge

# Terminal 2: feed an NMEA sentence
echo '$SDDPT,73.2,-1.5,*3A' | nc localhost 8001

# Terminal 3: listen on WebSocket
websocat ws://localhost:8000
```

## Quality Grading

| Grade | Meaning |
|-------|---------|
| `good` | Fresh reading, within plausible range |
| `fair` | Unknown channel (cannot assess) |
| `poor` | Stale or marginal (reserved for future use) |
| `bad`  | None, NaN, inf, or out of plausible range |

## Dependencies

- Python 3.11+
- `websockets` (PyPI)

## Files

| File | Purpose |
|------|---------|
| `bridge/nmea.py` | Pure NMEA 0183 sentence parser |
| `bridge/quality.py` | Channel quality grading |
| `bridge/bridge.py` | Async TCP+WS server |
| `bridge/__main__.py` | CLI entry point |
| `tests/test_bridge.py` | Test suite |
