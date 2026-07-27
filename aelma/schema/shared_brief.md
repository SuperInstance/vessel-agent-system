# AELMA Bridge Component — Build Brief (Parallel Competition)

You are building one component of AELMA (Agent-Engine Linked Marine Architecture) — a hardware-in-the-loop digital twin for a commercial fishing vessel. The F/V EILEEN is a 51-foot salmon troller home-ported in Sitka, Alaska. This is Phase 1 of a real implementation: build the bridge that turns NMEA 0183 wire bytes into structured telemetry.

## Working directory
All work goes in: C:\Users\casey\claudetz\aelma\build_<TAG>\bridge\
(TAG is kimi or claude — your launcher sets it.)

## Schemas (already exist, match exactly)
Read these first:
- C:\Users\casey\claudetz\aelma\schema\telemetry_packet.schema.json

## Deliverables
Create these files in your build dir:

1. `nmea.py` — NMEA 0183 parser, pure functions, no I/O. Handle:
   - $GPGGA, $GNGGA: position (convert ddmm.mmm to decimal degrees)
   - $GPRMC, $GNRMC: position, SOG, COG, timestamp
   - $SDDPT, $SDDBT: depth in meters
   - $WIMWV: wind (true/apparent)
   - $YXMTW: water temp C
   - $YXXDR: air temp, baro
   - Validate checksum (XOR of bytes between $ and *, exclusive). Raise ValueError on bad checksum.
   - Return: list[dict] where each dict has keys {source:"nmea0183", channel:str, value:any, sentence:str}. Caller assigns timestamp_ns and quality.

2. `quality.py` — check_quality(channel, value) -> "good"|"fair"|"poor"|"bad". Sane ranges per channel (lat [-90,90], lon [-180,180], depth_m [0,11000], wind_kts [0,200], sea_temp_c [-5,40], air_temp_c [-60,60], engine_rpm [0,4000]). Out of range = "bad", None = "bad", NaN/inf = "bad". For unknown channels, return "fair".

3. `bridge.py` — async server. Listens on plain TCP for NMEA text (port 8001, default) AND serves WebSocket clients on port 8000. For each NMEA line: parse, assign timestamp_ns = time.time_ns(), run quality check, build full telemetry_packet dict matching schema, broadcast JSON to all WS subscribers. Maintain last-seen per channel (send on new subscriber connect). Graceful on malformed sentences. Structured logging to stderr.

4. `__init__.py`, `__main__.py` (CLI: --tcp-port, --ws-port, --debug)

5. `README.md` in build dir — one page: what it is, protocol, how to run.

6. Tests: write `tests/test_bridge.py` covering:
   - GGA parsing (good and bad checksum)
   - RMC parsing
   - DPT parsing
   - MWV parsing (true and apparent)
   - MTW parsing
   - XDR air temp parsing
   - check_quality in-range and out-of-range for several channels
   - End-to-end: parse + quality + packet build

## Constraints
- Python 3.11+. stdlib + `websockets` (PyPI) only.
- Each file < 300 lines. Readable.
- Type hints everywhere. `from __future__ import annotations` at top of every .py.
- Module + function docstrings.
- Use pytest for tests.

## Quality bar
Run from your build dir parent (cd /c/Users/casey/claudetz/aelma):
    python -m pytest build_<TAG>/tests/test_bridge.py -v
All tests must pass.

## After completion
Write a short report to /tmp/build_<TAG>_bridge_report.md listing files, line counts, key design decisions, and test results.
