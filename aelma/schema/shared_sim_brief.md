# AELMA Simulator Component — Build Brief (Parallel Competition)

You are building the SIMULATOR for AELMA (Agent-Engine Linked Marine Architecture). It emits realistic NMEA 0183 sentences simulating F/V EILEEN trolling in Southeast Alaska, so bridge and twin can be developed without real hardware.

## Working directory
All work goes in: C:\Users\casey\claudetz\aelma\build_<TAG>\simulator\
(TAG is kimi or claude — launcher sets it.)

## Deliverables
1. `simulate.py` — Python script that opens TCP to bridge (default localhost:8001) and writes NMEA 0183 sentences in real-time. Pure stdlib only.
2. `__init__.py`
3. `__main__.py` — calls simulate.py main
4. `README.md`
5. `tests/test_simulator.py` — at least 6 tests covering checksums, position math, depth model output range, CLI argparse

## Trip to simulate
F/V EILEEN (US-AK-FVEILEEN-51) trolling near Sitka, AK.
- Start: 56.80134 N, -135.30278 W, heading 215°, speed 4.2 kn (trolling)
- Duration: configurable (--duration-min, default 30)
- 1 Hz GPS, 2 Hz depth, 0.2 Hz wind, 0.1 Hz water temp
- Path: troll SW 5min → turn W 10min → turn NW 5min → drift 5min (speed 0.5 kn) → repeat
- Depth varies: 70-80m trolling, shoals to 30-40m during drift over reef, deepens to 120m over submarine canyon
- Wind: 8 kts SW building to 14 kts W over trip, gusts
- Sea temp: 9.5 → 9.2 C slowly
- Air temp: 11.0 C with jitter

## NMEA sentences to emit (with correct checksums)
- $GPGGA — position (ddmm.mmm format, quality 1, 8-12 sats, HDOP 0.8-1.5)
- $GPRMC — position, SOG, COG, HHMMSS timestamp, date
- $SDDPT — depth meters, offset -1.5
- $WIMWV — wind dir (deg true), wind speed kn, reference T
- $YXMTW — water temp C
- $YXXDR — air temp (A, C), baro (P, B)

## Position math
- 1 knot = 1/3600 nautical miles/sec = 1/(3600·60) degrees lat/sec
- new_lat = old_lat + (speed_kn · sin(heading_rad)) / 3600 / 60 per second (north component — wait, conventional: north = cos, east = sin, fix this)
- Use: north_component = speed_kn · cos(heading_rad), east_component = speed_kn · sin(heading_rad) (heading 0=N, 90=E)
- new_lat += north_component / 3600 / 60 per second
- new_lon += east_component / 3600 / 60 / cos(lat_rad) per second
- Add Gaussian noise σ=2m to position (use random.gauss)

## Depth model
Hidden "true seafloor" function of (lat, lon):
- Reef at (56.79, -135.31): peak rises to 25m, σ=200m (Gaussian bump subtracted from baseline)
- Trough at (56.78, -135.33): bottom drops to 130m, σ=300m (added to baseline)
- Baseline 70m
- depth_at(lat, lon) = max(5, baseline − reef_amp·exp(−d²/(2·σ_reef²)) + trough_amp·(1 − exp(−d²/(2·σ_trough²))))
- Add 0.3m measurement noise on top.

## CLI
- --host (default localhost)
- --port (default 8001)
- --duration-min (default 30)
- --seed (default 42)
- --speedup (default 1, >1 = faster than realtime)

## Constraints
- stdlib only (math, socket, time, argparse, random, datetime, sys).
- File < 300 lines.
- NMEA checksums MUST be correct (XOR of bytes between $ and *).
- One sentence per line, \r\n terminated (NMEA 0183 standard).
- Clean shutdown on Ctrl+C.
- Log one line per simulated second to stderr (elapsed, position, depth).

## Quality bar
cd /c/Users/casey/claudetz/aelma && python -m pytest build_<TAG>/tests/test_simulator.py -v
Run smoke test:
    python -m build_<TAG>.simulator.simulate --duration-min 0.1 --speedup 30

## After completion
Write report to /tmp/build_<TAG>_sim_report.md.
