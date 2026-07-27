"""AELMA F/V EILEEN NMEA 0183 simulator.

Emits realistic NMEA 0183 sentences over TCP so the AELMA bridge and twin
can be developed without real hardware. Pure Python stdlib only.

Trip (repeats): troll SW 5min → turn W 10min → turn NW 5min → drift 5min.
Depth: baseline 70m with reef bump and submarine-canyon trough.

Usage:
    python -m build_claude.simulator.simulate --duration-min 0.1 --speedup 30
"""
from __future__ import annotations

import argparse
import math
import random
import socket
import sys
import time
from datetime import datetime, timezone

# --- Trip geometry ---------------------------------------------------------

START_LAT, START_LON = 56.80134, -135.30278
TRIP_PHASES = [(215.0, 4.2, 300), (270.0, 4.2, 600),
               (315.0, 4.2, 300), (270.0, 0.5, 300)]
TRIP_PERIOD = sum(p[2] for p in TRIP_PHASES)

# --- Bathymetry ------------------------------------------------------------

REEF = (56.79, -135.31, 45.0, 200.0)   # lat, lon, amp, sigma_m
TROUGH = (56.78, -135.33, 60.0, 300.0)
BASELINE_DEPTH = 70.0
M_PER_DEG_LAT = 111_320.0


def trip_phase(elapsed: float) -> tuple[float, float]:
    """(heading_deg, speed_kn) at elapsed seconds — cycles through TRIP_PHASES."""
    t = elapsed % TRIP_PERIOD
    for hdg, spd, dur in TRIP_PHASES:
        if t < dur:
            return hdg, spd
        t -= dur
    return TRIP_PHASES[-1][0], TRIP_PHASES[-1][1]


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Euclidean distance in metres between two lat/lon (small-area approx)."""
    dy = (lat2 - lat1) * M_PER_DEG_LAT
    dx = (lon2 - lon1) * M_PER_DEG_LAT * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def depth_at(lat: float, lon: float) -> float:
    """True seafloor depth in metres at (lat, lon).

    baseline − reef_bump + trough_drop, clamped to >= 5 m.

    Note: the brief specifies ``trough_amp*(1 - exp(-d²/2σ²))`` for the
    trough, but that form contributes its full amplitude everywhere far
    from the trough centre and zero at the centre — the opposite of the
    intended "bottom drops to 130 m" behaviour. Both reef and trough are
    therefore modelled as localised Gaussian anomalies (``exp`` form),
    which matches the documented peak depths: ~25 m over the reef and
    ~130 m over the canyon. See the completion report for details.
    """
    d_reef = _haversine_m(lat, lon, REEF[0], REEF[1])
    d_trough = _haversine_m(lat, lon, TROUGH[0], TROUGH[1])
    reef = REEF[2] * math.exp(-(d_reef ** 2) / (2 * REEF[3] ** 2))
    trough = TROUGH[2] * math.exp(-(d_trough ** 2) / (2 * TROUGH[3] ** 2))
    return max(5.0, BASELINE_DEPTH - reef + trough)


def step_position(lat, lon, heading_deg, speed_kn, dt_sec, rng):
    """Advance (lat, lon) by (heading, speed) for dt seconds with 2 m Gaussian jitter."""
    h = math.radians(heading_deg)
    north_kn = speed_kn * math.cos(h)
    east_kn = speed_kn * math.sin(h)
    lat = lat + (north_kn * dt_sec) / 3600.0 / 60.0
    lon = lon + (east_kn * dt_sec) / 3600.0 / 60.0 / math.cos(math.radians(lat))
    cos_lat = abs(math.cos(math.radians(lat))) or 1e-6
    lat += rng.gauss(0.0, 2.0) / M_PER_DEG_LAT
    lon += rng.gauss(0.0, 2.0) / (M_PER_DEG_LAT * cos_lat)
    return lat, lon


# --- NMEA formatting -------------------------------------------------------

def _checksum(body: str) -> str:
    """XOR every byte of body, return 2-digit uppercase hex."""
    cs = 0
    for ch in body:
        cs ^= ord(ch)
    return f"{cs:02X}"


def nmea_sentence(body: str) -> str:
    """Build ``$body*CS\\r\\n`` with correct XOR checksum."""
    return f"${body}*{_checksum(body)}\r\n"


def _ddmm(lat: float) -> str:
    hemi = "N" if lat >= 0 else "S"
    a = abs(lat)
    return f"{int(a):02d}{(a - int(a)) * 60:07.4f},{hemi}"


def _dddmm(lon: float) -> str:
    hemi = "E" if lon >= 0 else "W"
    a = abs(lon)
    return f"{int(a):03d}{(a - int(a)) * 60:07.4f},{hemi}"


def _gga(lat, lon, utc, sats, hdop):
    return nmea_sentence(
        f"GPGGA,{utc.strftime('%H%M%S')},{_ddmm(lat)},{_dddmm(lon)},"
        f"1,{sats:02d},{hdop:.1f},0.0,M,0.0,M,,")


def _rmc(lat, lon, sog, cog, utc):
    return nmea_sentence(
        f"GPRMC,{utc.strftime('%H%M%S')},A,{_ddmm(lat)},{_dddmm(lon)},"
        f"{sog:.1f},{cog:.1f},{utc.strftime('%d%m%y')},,,A")


def _dpt(depth_m, offset=-1.5):
    return nmea_sentence(f"SDDPT,{depth_m:.1f},{offset:.1f},")


def _mwv(wdir, wspd):
    return nmea_sentence(f"WIMWV,{wdir:.0f},T,{wspd:.1f},N,A")


def _mtw(t):
    return nmea_sentence(f"YXMTW,{t:.1f},C")


def _xdr_air(t):
    return nmea_sentence(f"YXXDR,A,{t:.1f},C,AIRTEMP")


def _xdr_baro(p):
    return nmea_sentence(f"YXXDR,P,{p:.1f},B,BARO")


# --- Tick ------------------------------------------------------------------

RATES = {"gga": 1.0, "rmc": 1.0, "dpt": 2.0, "mwv": 0.2, "mtw": 0.1, "xdr_air": 0.1}


def build_sentences(state: dict, rng: random.Random) -> list[str]:
    """Advance state by 1 s and return the NMEA sentences due this tick."""
    state["lat"], state["lon"] = step_position(
        state["lat"], state["lon"], state["heading"], state["speed"], 1.0, rng)

    p = min(1.0, state["elapsed"] / max(1.0, state["duration_sec"]))
    state["wind_dir"] = 225.0 + (270.0 - 225.0) * p + rng.gauss(0.0, 5.0)
    state["wind_speed"] = max(0.0, 8.0 + (14.0 - 8.0) * p + rng.gauss(0.0, 1.5))
    state["water_temp"] = 9.5 - 0.3 * p + rng.gauss(0.0, 0.05)
    state["air_temp"] = 11.0 + rng.gauss(0.0, 0.3)
    state["baro"] = 1013.0 + rng.gauss(0.0, 1.0)
    state["depth"] = max(0.1, depth_at(state["lat"], state["lon"]) + rng.gauss(0.0, 0.3))

    if int(state["elapsed"]) % 5 == 0:
        state["sats"] = max(4, min(12, int(round(state["sats"] + rng.gauss(0.0, 1.0)))))
        state["hdop"] = max(0.8, min(1.5, state["hdop"] + rng.gauss(0.0, 0.05)))

    out = []
    for ch, rate in RATES.items():
        state["acc"][ch] += rate
        while state["acc"][ch] >= 1.0:
            state["acc"][ch] -= 1.0
            if ch == "gga":
                out.append(_gga(state["lat"], state["lon"], state["utc"],
                                state["sats"], state["hdop"]))
            elif ch == "rmc":
                cog = (state["heading"] + rng.gauss(0.0, 2.0)) % 360.0
                out.append(_rmc(state["lat"], state["lon"], state["speed"], cog,
                                state["utc"]))
            elif ch == "dpt":
                out.append(_dpt(state["depth"]))
            elif ch == "mwv":
                out.append(_mwv(state["wind_dir"], state["wind_speed"]))
            elif ch == "mtw":
                out.append(_mtw(state["water_temp"]))
            elif ch == "xdr_air":
                out.append(_xdr_air(state["air_temp"]))
                out.append(_xdr_baro(state["baro"]))

    state["elapsed"] += 1.0
    state["utc"] = datetime.fromtimestamp(state["utc"].timestamp() + 1.0, tz=timezone.utc)
    state["heading"], state["speed"] = trip_phase(state["elapsed"])
    return out


def _initial_state(duration_sec: float, seed: int) -> dict:
    return {
        "lat": START_LAT, "lon": START_LON, "heading": 215.0, "speed": 4.2,
        "depth": depth_at(START_LAT, START_LON), "water_temp": 9.5,
        "air_temp": 11.0, "baro": 1013.0, "wind_dir": 225.0, "wind_speed": 8.0,
        "sats": 10, "hdop": 1.0, "elapsed": 0.0,
        "utc": datetime.now(tz=timezone.utc).replace(microsecond=0),
        "duration_sec": duration_sec, "acc": {k: 0.0 for k in RATES}, "seed": seed,
    }


# --- Main loop -------------------------------------------------------------

def simulate(host, port, duration_min, seed, speedup, sock_send=None) -> int:
    """Run the simulator. ``sock_send`` bypasses TCP (used by tests)."""
    duration_sec = max(0.0, duration_min * 60.0)
    state = _initial_state(duration_sec, seed)
    rng = random.Random(seed)

    own_sock = None
    if sock_send is None:
        own_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        own_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        try:
            own_sock.connect((host, port))
        except OSError as e:
            print(f"[sim] cannot connect to {host}:{port}: {e}", file=sys.stderr)
            return 0

    def emit(line):
        if sock_send is not None:
            sock_send(line)
        else:
            own_sock.sendall(line.encode("ascii", errors="replace"))

    wall_per_sim = 1.0 / max(1e-6, speedup)
    try:
        while state["elapsed"] < duration_sec:
            t0 = time.monotonic()
            for ln in build_sentences(state, rng):
                emit(ln)
            print(f"[sim] t={state['elapsed']:6.1f}s lat={state['lat']:.5f} "
                  f"lon={state['lon']:.5f} depth={state['depth']:5.1f}m "
                  f"spd={state['speed']:.1f}kn hdg={state['heading']:.0f}",
                  file=sys.stderr)
            slack = wall_per_sim - (time.monotonic() - t0)
            if slack > 0:
                time.sleep(slack)
    except KeyboardInterrupt:
        print("\n[sim] Ctrl+C — shutting down.", file=sys.stderr)
    finally:
        if own_sock is not None:
            try:
                own_sock.close()
            except OSError:
                pass
    print(f"[sim] done: {state['elapsed']:.1f}s simulated.", file=sys.stderr)
    return int(state["elapsed"])


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    p = argparse.ArgumentParser(
        prog="build_claude.simulator.simulate",
        description="AELMA F/V EILEEN NMEA 0183 simulator (pure stdlib).")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=8001)
    p.add_argument("--duration-min", type=float, default=30.0)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--speedup", type=float, default=1.0)
    args = p.parse_args(argv)
    if args.duration_min < 0:
        p.error("--duration-min must be >= 0")
    if args.speedup <= 0:
        p.error("--speedup must be > 0")
    simulate(args.host, args.port, args.duration_min, args.seed, args.speedup)
    return 0


if __name__ == "__main__":
    sys.exit(main())
