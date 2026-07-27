"""Test suite for the AELMA bridge.

Covers GGA, RMC, DPT/DBT, MWV, MTW, XDR parsing; checksum validation;
check_quality across multiple channels; and end-to-end packet building.
"""

from __future__ import annotations

import json
import sys
import os

import pytest

_BUILD_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BUILD_DIR not in sys.path:
    sys.path.insert(0, _BUILD_DIR)

from bridge import nmea, quality  # noqa: E402
from bridge.bridge import build_packet  # noqa: E402


def _make(body: str) -> str:
    """Build a valid-checksum NMEA sentence from *body* (no $ or *XX)."""
    c = 0
    for ch in body:
        c ^= ord(ch)
    return f"${body}*{c:02X}"


# ---------------------------------------------------------------------------
# Checksum tests
# ---------------------------------------------------------------------------

class TestChecksum:
    """Tests for nmea.verify_checksum."""

    def test_valid(self) -> None:
        nmea.verify_checksum(_make("GPGGA,1,2,3"))

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="Checksum mismatch"):
            nmea.verify_checksum("$GPGGA,1,2,3*FF")

    def test_missing_star_raises(self) -> None:
        with pytest.raises(ValueError, match="missing"):
            nmea.verify_checksum("$GPGGA,123456")

    def test_missing_dollar_raises(self) -> None:
        with pytest.raises(ValueError, match="must start"):
            nmea.verify_checksum("GPGGA,1,2,3*FF")


# ---------------------------------------------------------------------------
# GGA tests
# ---------------------------------------------------------------------------

class TestGGA:
    """Tests for $GPGGA / $GNGGA parsing."""

    def test_gga_valid(self) -> None:
        s = _make("GPGGA,123456,5648.080,N,13518.167,W,1,08,0.8,0.0,M,0.0,M,,")
        r = nmea.parse_sentence(s)
        assert len(r) == 2
        assert r[0]["channel"] == "position.lat"
        assert abs(r[0]["value"] - (56 + 48.080 / 60)) < 1e-6
        assert r[1]["channel"] == "position.lon"
        assert r[1]["value"] < 0  # west
        assert abs(abs(r[1]["value"]) - (135 + 18.167 / 60)) < 1e-6

    def test_gga_bad_checksum(self) -> None:
        with pytest.raises(ValueError):
            nmea.parse_sentence("$GPGGA,123456,5648.080,N,13518.167,W,*FF")

    def test_gngga(self) -> None:
        s = _make("GNGGA,123456,5648.080,N,13518.167,W,1,08,0.8,0.0,M,0.0,M,,")
        r = nmea.parse_sentence(s)
        assert len(r) == 2

    def test_gga_empty(self) -> None:
        s = _make("GPGGA,123456,,,,,0,00,99.9,,,,,,")
        assert nmea.parse_sentence(s) == []

    def test_gga_south_west(self) -> None:
        s = _make("GPGGA,123456,3400.000,S,11800.000,W,1,08,0.8,0.0,M,0.0,M,,")
        r = nmea.parse_sentence(s)
        assert r[0]["value"] < 0 and r[1]["value"] < 0
        assert abs(r[0]["value"] - (-34.0)) < 1e-6
        assert abs(r[1]["value"] - (-118.0)) < 1e-6


# ---------------------------------------------------------------------------
# RMC tests
# ---------------------------------------------------------------------------

class TestRMC:
    """Tests for $GPRMC / $GNRMC parsing."""

    def test_rmc_valid(self) -> None:
        s = _make("GPRMC,123456,A,5648.080,N,13518.167,W,5.2,180.0,010125,,,")
        r = nmea.parse_sentence(s)
        chs = [x["channel"] for x in r]
        assert "position.lat" in chs and "position.lon" in chs
        assert "sog_kn" in chs and "cog_deg" in chs
        sog = [x for x in r if x["channel"] == "sog_kn"][0]
        assert sog["value"] == pytest.approx(5.2)
        cog = [x for x in r if x["channel"] == "cog_deg"][0]
        assert cog["value"] == pytest.approx(180.0)

    def test_gnrmc(self) -> None:
        s = _make("GNRMC,123456,A,5648.080,N,13518.167,W,5.2,180.0,010125,,,")
        assert len(nmea.parse_sentence(s)) == 4


# ---------------------------------------------------------------------------
# DPT / DBT tests
# ---------------------------------------------------------------------------

class TestDPT:
    """Tests for $SDDPT and $SDDBT parsing."""

    def test_dpt(self) -> None:
        s = _make("SDDPT,73.2,-1.5,")
        r = nmea.parse_sentence(s)
        assert len(r) == 1
        assert r[0]["channel"] == "depth_m"
        assert r[0]["value"] == pytest.approx(73.2)

    def test_dbt(self) -> None:
        s = _make("SDDBT,240.0,F,73.2,M,40.0,F,")
        r = nmea.parse_sentence(s)
        assert r[0]["channel"] == "depth_m"
        assert r[0]["value"] == pytest.approx(73.2)

    def test_dpt_empty(self) -> None:
        assert nmea.parse_sentence(_make("SDDPT,,-1.5,")) == []


# ---------------------------------------------------------------------------
# MWV tests
# ---------------------------------------------------------------------------

class TestMWV:
    """Tests for $WIMWV wind parsing."""

    def test_true(self) -> None:
        s = _make("WIMWV,45.0,T,12.5,K,A")
        r = nmea.parse_sentence(s)
        chs = [x["channel"] for x in r]
        assert "wind_kts_true" in chs and "wind_dir_deg_true" in chs
        spd = [x for x in r if x["channel"] == "wind_kts_true"][0]
        assert spd["value"] == pytest.approx(12.5)

    def test_apparent_ms(self) -> None:
        s = _make("WIMWV,90.0,R,15.0,M,A")
        r = nmea.parse_sentence(s)
        chs = [x["channel"] for x in r]
        assert "wind_kts_apparent" in chs
        spd = [x for x in r if x["channel"] == "wind_kts_apparent"][0]
        assert spd["value"] == pytest.approx(15.0 * 1.943844, rel=1e-4)
        d = [x for x in r if x["channel"] == "wind_dir_deg_apparent"][0]
        assert d["value"] == pytest.approx(90.0)


# ---------------------------------------------------------------------------
# MTW tests
# ---------------------------------------------------------------------------

class TestMTW:
    """Tests for $YXMTW water temperature parsing."""

    def test_mtw_celsius(self) -> None:
        s = _make("YXMTW,12.5,C")
        r = nmea.parse_sentence(s)
        assert r[0]["channel"] == "sea_temp_c"
        assert r[0]["value"] == pytest.approx(12.5)


# ---------------------------------------------------------------------------
# XDR tests
# ---------------------------------------------------------------------------

class TestXDR:
    """Tests for $YXXDR transducer parsing."""

    def test_air_temp(self) -> None:
        s = _make("YXXDR,C,15.5,C,AIR")
        r = nmea.parse_sentence(s)
        assert r[0]["channel"] == "air_temp_c"
        assert r[0]["value"] == pytest.approx(15.5)

    def test_baro(self) -> None:
        s = _make("YXXDR,P,1013.2,B,BARO")
        r = nmea.parse_sentence(s)
        assert r[0]["channel"] == "baro_mb"
        assert r[0]["value"] == pytest.approx(1013.2 * 1000)

    def test_multi(self) -> None:
        s = _make("YXXDR,C,15.5,C,AIR,P,1013.2,B,BARO")
        chs = [x["channel"] for x in nmea.parse_sentence(s)]
        assert "air_temp_c" in chs and "baro_mb" in chs


# ---------------------------------------------------------------------------
# Quality tests (table-driven)
# ---------------------------------------------------------------------------

_GOOD = [
    ("position.lat", 56.8), ("position.lat", -89.9),
    ("position.lon", -135.3), ("position.lon", 180.0),
    ("depth_m", 73.2), ("depth_m", 0.0), ("depth_m", 11000.0),
    ("wind_kts", 12.5), ("wind_kts", 0.0),
    ("sea_temp_c", 12.5), ("sea_temp_c", -5.0), ("sea_temp_c", 40.0),
    ("air_temp_c", 5.0), ("air_temp_c", -60.0), ("air_temp_c", 60.0),
    ("engine_rpm", 1800), ("engine_rpm", 0), ("engine_rpm", 4000),
]

_BAD = [
    ("position.lat", 95.0), ("position.lon", 200.0),
    ("depth_m", -5.0), ("depth_m", 20000.0),
    ("wind_kts", 250.0), ("sea_temp_c", 50.0),
    ("air_temp_c", -70.0), ("engine_rpm", 5000),
]


@pytest.mark.parametrize("channel,value", _GOOD)
def test_quality_good(channel: str, value: float) -> None:
    assert quality.check_quality(channel, value) == "good"


@pytest.mark.parametrize("channel,value", _BAD)
def test_quality_bad(channel: str, value: float) -> None:
    assert quality.check_quality(channel, value) == "bad"


def test_quality_none_is_bad() -> None:
    assert quality.check_quality("depth_m", None) == "bad"


def test_quality_nan_inf_bad() -> None:
    assert quality.check_quality("depth_m", float("nan")) == "bad"
    assert quality.check_quality("depth_m", float("inf")) == "bad"
    assert quality.check_quality("depth_m", float("-inf")) == "bad"


def test_quality_unknown_fair() -> None:
    assert quality.check_quality("mystery", 42.0) == "fair"


# ---------------------------------------------------------------------------
# End-to-end tests
# ---------------------------------------------------------------------------

class TestEndToEnd:
    """End-to-end: parse -> build_packet -> verify fields."""

    def test_depth_packet(self) -> None:
        s = _make("SDDPT,73.2,-1.5,")
        pkt = build_packet(nmea.parse_sentence(s)[0])
        assert pkt["source"] == "nmea0183"
        assert pkt["channel"] == "depth_m"
        assert pkt["value"] == pytest.approx(73.2)
        assert pkt["quality"] == "good"
        assert pkt["timestamp_ns"] > 0
        assert "$SDDPT" in pkt["sentence"]

    def test_position_packet(self) -> None:
        s = _make("GPGGA,123456,5648.080,N,13518.167,W,1,08,0.8,0.0,M,0.0,M,,")
        for reading in nmea.parse_sentence(s):
            pkt = build_packet(reading)
            assert pkt["quality"] == "good"
            assert pkt["timestamp_ns"] > 0

    def test_bad_depth_quality(self) -> None:
        s = _make("SDDPT,15000.0,-1.5,")
        pkt = build_packet(nmea.parse_sentence(s)[0])
        assert pkt["quality"] == "bad"

    def test_wind_packet(self) -> None:
        s = _make("WIMWV,45.0,T,12.5,K,A")
        for reading in nmea.parse_sentence(s):
            assert build_packet(reading)["quality"] == "good"

    def test_packet_json_serializable(self) -> None:
        s = _make("SDDPT,73.2,-1.5,")
        pkt = build_packet(nmea.parse_sentence(s)[0])
        restored = json.loads(json.dumps(pkt))
        assert restored["channel"] == "depth_m"
        assert restored["value"] == pytest.approx(73.2)


def test_unknown_sentence_returns_empty() -> None:
    assert nmea.parse_sentence(_make("GPXYZ,1,2,3")) == []
