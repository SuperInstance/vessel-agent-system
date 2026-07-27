# AELMA Simulator (build_claude)

A pure-stdlib Python simulator that emits realistic NMEA 0183 sentences for
the F/V EILEEN trolling near Sitka, Alaska. Used to develop the AELMA
**bridge** and **twin** without real hardware.

## What it does

- Opens a TCP connection to the bridge (default `localhost:8001`) and writes
  one NMEA 0183 sentence per line (`\r\n` terminated).
- Simulates a repeating 25-minute trip:
  1. Troll SW 5 min (215°, 4.2 kn)
  2. Turn W 10 min (270°, 4.2 kn)
  3. Turn NW 5 min (315°, 4.2 kn)
  4. Drift 5 min (270°, 0.5 kn)
- Models bathymetry as a baseline 70 m seafloor with a Gaussian reef bump
  (peak rises to ~25 m) and a submarine-canyon trough (drops to ~130 m).
- Adds realistic measurement noise: 2 m GPS jitter, 0.3 m depth jitter.

## NMEA sentences emitted

| Sentence  | Rate    | Contents                                              |
|-----------|---------|-------------------------------------------------------|
| `$GPGGA`  | 1 Hz    | Position (ddmm.mmmm), quality 1, 4–12 sats, HDOP 0.8–1.5 |
| `$GPRMC`  | 1 Hz    | Position, SOG, COG, HHMMSS UTC timestamp, date        |
| `$SDDPT`  | 2 Hz    | Depth metres, offset -1.5                              |
| `$WIMWV`  | 0.2 Hz  | Wind direction true, wind speed kn                    |
| `$YXMTW`  | 0.1 Hz  | Water temperature °C                                  |
| `$YXXDR`  | 0.1 Hz  | Air temperature (C, AIRTEMP) and barometric pressure (B, BARO) |

All sentences include a correct XOR checksum (`$body*HH`).

## CLI

```
python -m build_claude.simulator.simulate \
    --host localhost \
    --port 8001 \
    --duration-min 30 \
    --seed 42 \
    --speedup 1
```

| Flag             | Default | Purpose                                  |
|------------------|---------|------------------------------------------|
| `--host`         | localhost | Bridge TCP host                          |
| `--port`         | 8001    | Bridge TCP port                            |
| `--duration-min` | 30      | Simulated trip length in minutes           |
| `--seed`         | 42      | RNG seed for reproducible runs             |
| `--speedup`      | 1       | Time multiplier (`>1` = faster than realtime) |

`Ctrl+C` shuts down cleanly.

## Quick smoke test

Start a throwaway TCP listener in one terminal:

```
python -c "import socket as s; srv=s.socket(); srv.bind(('',8001)); srv.listen(); c,_=srv.accept(); [print(repr(c.recv(256))) for _ in iter(int,1)]"
```

In another terminal:

```
cd C:\Users\casey\claudetz\aelma
python -m build_claude.simulator.simulate --duration-min 0.1 --speedup 30
```

You should see a stream of NMEA 0183 sentences and one stderr log line per
simulated second.

## Tests

```
cd C:\Users\casey\claudetz\aelma
python -m pytest build_claude/tests/test_simulator.py -v
```

## Constraints honored

- Python stdlib only (`math`, `socket`, `time`, `argparse`, `random`,
  `datetime`, `sys`).
- `simulate.py` is under 300 lines.
- Every NMEA sentence ends with `\r\n` and carries a valid XOR checksum.
- One log line per simulated second to stderr (elapsed, position, depth).
