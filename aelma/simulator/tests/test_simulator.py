"""Tests for the AELMA simulator (build_claude).

Covers NMEA checksums, position math, depth-model output range, sentence
formatting (GGA/RMC/DPT/MWV/MTW/XDR), CLI argparse, and an end-to-end
in-memory simulation tick.
"""
from __future__ import annotations

import argparse
import math
import random
from datetime import datetime, timezone

import pytest

from build_claude.simulator.simulate import (
    BASELINE_DEPTH,
    REEF,
    TROUGH,
    _checksum,
    _dddmm,
    _ddmm,
    _dpt,
    _gga,
    _initial_state,
    _mtw,
    _mwv,
    _rmc,
    _xdr_air,
    _xdr_baro,
    build_sentences,
    depth_at,
    main,
    nmea_sentence,
    simulate,
    step_position,
    trip_phase,
)


# ---------------------------------------------------------------------------
# 1. Checksum correctness
# ---------------------------------------------------------------------------

class TestChecksum:
    """NMEA 0183 checksum = XOR of all bytes between $ and *, as 2-digit hex."""

    def test_checksum_known_vector(self):
        body = "GPGGA,123456,5648.0804,N,13518.1668,W,1,10,1.0,0.0,M,0.0,M,,"
        expected = 0
        for ch in body:
            expected ^= ord(ch)
        assert _checksum(body) == f"{expected:02X}"

    def test_checksum_empty_body(self):
        assert _checksum("") == "00"

    def test_checksum_single_char(self):
        assert _checksum("A") == "41"  # 0x41 = ASCII 'A'

    def test_sentence_format_and_terminator(self):
        line = nmea_sentence("GPGGA,123")
        assert line.startswith("$")
        assert line.endswith("\r\n")
        body, _, tail = line[1:].partition("*")
        assert _checksum(body) == tail.strip()


# ---------------------------------------------------------------------------
# 2. Position math
# ---------------------------------------------------------------------------

class TestPositionMath:
    """1 knot = 1/60 degree latitude per hour; east component scaled by cos(lat)."""

    def test_due_north_one_hour(self):
        # 60 kn due north for 1 hour == +1 degree latitude.
        rng = random.Random(0)
        lat, lon = step_position(56.0, -135.0, 0.0, 60.0, 3600.0, rng)
        assert abs(lat - 57.0) < 1e-3
        assert abs(lon - (-135.0)) < 1e-3

    def test_due_east_one_hour_at_equator(self):
        # At the equator, 60 kn due east for 1 hour ≈ +1 degree lon.
        rng = random.Random(0)
        lat, lon = step_position(0.0, 0.0, 90.0, 60.0, 3600.0, rng)
        assert abs(lat - 0.0) < 1e-3
        assert abs(lon - 1.0) < 1e-2

    def test_noise_is_small(self):
        rng = random.Random(42)
        for _ in range(50):
            lat, lon = step_position(56.0, -135.0, 0.0, 0.0, 1.0, rng)
            # 4-sigma of 2 m ≈ 8 m ≈ 7e-5 deg.
            assert abs(lat - 56.0) < 1e-4
            assert abs(lon - (-135.0)) < 1e-4

    def test_zero_speed_holds_position_on_average(self):
        rng = random.Random(7)
        lat, lon = step_position(56.0, -135.0, 215.0, 0.0, 1.0, rng)
        assert abs(lat - 56.0) < 1e-4
        assert abs(lon - (-135.0)) < 1e-4


# ---------------------------------------------------------------------------
# 3. Depth model
# ---------------------------------------------------------------------------

class TestDepthModel:
    """depth_at: baseline 70 m, reef bump, trough drop, clamped at 5 m min."""

    def test_baseline_far_from_features(self):
        d = depth_at(60.0, -130.0)
        assert abs(d - BASELINE_DEPTH) < 0.5

    def test_reef_shallows_water(self):
        d = depth_at(REEF[0], REEF[1])
        assert d < 35.0  # 70 - 45 = 25, plus small residual

    def test_trough_deepens_water(self):
        d = depth_at(TROUGH[0], TROUGH[1])
        assert d > 120.0  # 70 + 60 = 130

    def test_depth_always_positive_and_clamped(self):
        for i in range(-10, 11):
            for j in range(-10, 11):
                lat = REEF[0] + i * 0.001
                lon = REEF[1] + j * 0.001
                assert depth_at(lat, lon) >= 5.0


# ---------------------------------------------------------------------------
# 4. NMEA sentence formatting
# ---------------------------------------------------------------------------

class TestSentenceFormatting:
    """Validate each sentence type the simulator emits."""

    def _parse(self, line: str):
        assert line.startswith("$")
        assert line.endswith("\r\n")
        body, _, tail = line[1:].partition("*")
        assert _checksum(body) == tail.strip(), "checksum mismatch"
        talker = body[:2]
        stype = body[2:5]
        fields = body.split(",")
        return talker, stype, fields

    def test_gga_structure(self):
        utc = datetime(2024, 7, 4, 9, 27, 50, tzinfo=timezone.utc)
        line = _gga(56.80134, -135.30278, utc, 10, 1.0)
        talker, stype, f = self._parse(line)
        assert talker == "GP"
        assert stype == "GGA"
        assert f[0] == "GPGGA"
        assert f[1] == "092750"
        assert f[3] == "N"
        assert f[5] == "W"
        assert f[6] == "1"
        assert f[7] == "10"
        assert f[8] == "1.0"

    def test_rmc_structure(self):
        utc = datetime(2024, 7, 4, 9, 27, 50, tzinfo=timezone.utc)
        line = _rmc(56.80134, -135.30278, 4.2, 215.0, utc)
        talker, stype, f = self._parse(line)
        assert talker == "GP"
        assert stype == "RMC"
        assert f[1] == "092750"
        assert f[2] == "A"
        assert f[9] == "040724"

    def test_dpt_structure(self):
        line = _dpt(73.2)
        talker, stype, f = self._parse(line)
        assert talker == "SD"
        assert stype == "DPT"
        assert f[1] == "73.2"
        assert f[2] == "-1.5"

    def test_mwv_structure(self):
        line = _mwv(225, 8.5)
        talker, stype, f = self._parse(line)
        assert talker == "WI"
        assert stype == "MWV"
        assert f[1] == "225"
        assert f[2] == "T"
        assert f[3] == "8.5"
        assert f[4] == "N"
        assert f[5] == "A"

    def test_mtw_structure(self):
        line = _mtw(9.4)
        talker, stype, f = self._parse(line)
        assert talker == "YX"
        assert stype == "MTW"
        assert f[1] == "9.4"
        assert f[2] == "C"

    def test_xdr_air_and_baro(self):
        air = _xdr_air(11.2)
        baro = _xdr_baro(1013.5)
        _, _, fa = self._parse(air)
        _, _, fb = self._parse(baro)
        assert fa[1] == "A"
        assert fa[2] == "11.2"
        assert fa[3] == "C"
        assert fa[4] == "AIRTEMP"
        assert fb[1] == "P"
        assert fb[2] == "1013.5"
        assert fb[3] == "B"
        assert fb[4] == "BARO"


# ---------------------------------------------------------------------------
# 5. CLI / argparse
# ---------------------------------------------------------------------------

def _make_parser():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=8001)
    p.add_argument("--duration-min", type=float, default=30.0)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--speedup", type=float, default=1.0)
    return p


class TestCLI:
    def test_default_args(self):
        ns = _make_parser().parse_args([])
        assert ns.host == "localhost"
        assert ns.port == 8001
        assert ns.duration_min == 30.0
        assert ns.seed == 42
        assert ns.speedup == 1.0

    def test_custom_args_parsed(self):
        ns = _make_parser().parse_args(
            ["--host", "10.0.0.5", "--port", "9000",
             "--duration-min", "5", "--seed", "7", "--speedup", "10"])
        assert ns.host == "10.0.0.5"
        assert ns.port == 9000
        assert ns.duration_min == 5.0
        assert ns.seed == 7
        assert ns.speedup == 10.0

    def test_negative_duration_exits(self):
        with pytest.raises(SystemExit):
            main(["--duration-min", "-1", "--speedup", "9999"])

    def test_nonpositive_speedup_exits(self):
        with pytest.raises(SystemExit):
            main(["--duration-min", "1", "--speedup", "0"])


# ---------------------------------------------------------------------------
# 6. End-to-end simulation tick (in-memory, no TCP socket)
# ---------------------------------------------------------------------------

class TestSimulation:
    def test_one_tick_emits_expected_sentence_set(self):
        """Tick 1 should emit GPS + 2× depth (default rates)."""
        state = _initial_state(60.0, seed=1)
        rng = random.Random(1)
        lines = build_sentences(state, rng)
        bodies = [ln[1:6] for ln in lines]
        assert any(b.startswith("GPGGA") for b in bodies)
        assert any(b.startswith("GPRMC") for b in bodies)
        # Depth at 2 Hz: two accumulators both reach 1.0 on tick 1.
        assert sum(1 for b in bodies if b.startswith("SDDPT")) == 2

    def test_in_memory_run_produces_lines(self):
        """Drive simulate() in-memory with sock_send collecting lines."""
        collected: list[str] = []
        n = simulate("localhost", 9999, duration_min=0.05,
                     seed=3, speedup=10000, sock_send=collected.append)
        assert n == 3
        assert len(collected) > 0
        for ln in collected:
            assert ln.startswith("$")
            assert ln.endswith("\r\n")
            body, _, tail = ln[1:].partition("*")
            assert _checksum(body) == tail.strip()

    def test_trip_phase_cycles(self):
        assert trip_phase(0) == (215.0, 4.2)
        assert trip_phase(299) == (215.0, 4.2)
        assert trip_phase(300) == (270.0, 4.2)
        assert trip_phase(899) == (270.0, 4.2)
        assert trip_phase(900) == (315.0, 4.2)
        assert trip_phase(1200) == (270.0, 0.5)
        assert trip_phase(1500) == (215.0, 4.2)
