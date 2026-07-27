"""Tests for the AELMA bridge: parser, quality, and packet build."""

from __future__ import annotations

import asyncio

import pytest

from build_kimi.bridge import bridge as bridge_mod
from build_kimi.bridge.nmea import parse_sentence, validate_checksum
from build_kimi.bridge.quality import check_quality


def nmea(body: str) -> str:
    """Wrap a sentence body with $...* and a correct checksum."""
    checksum = 0
    for ch in body:
        checksum ^= ord(ch)
    return f"${body}*{checksum:02X}"


def by_channel(readings: list[dict]) -> dict[str, object]:
    """Index a list of readings by channel name."""
    return {r["channel"]: r["value"] for r in readings}


# --- GGA -------------------------------------------------------------------

# Classic known-good sentence (checksum 47 is published NMEA lore).
GGA = "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"


def test_gga_parses_position() -> None:
    readings = parse_sentence(GGA)
    vals = by_channel(readings)
    assert vals["position.lat"] == pytest.approx(48.1173, abs=1e-4)
    assert vals["position.lon"] == pytest.approx(11.5166667, abs=1e-4)
    for r in readings:
        assert r["source"] == "nmea0183"
        assert r["sentence"] == GGA


def test_gga_gn_talker_and_southern_hemisphere() -> None:
    s = nmea("GNGGA,001500,3350.000,S,15112.000,E,1,10,1.0,5.0,M,,,,")
    vals = by_channel(parse_sentence(s))
    assert vals["position.lat"] == pytest.approx(-33.8333333, abs=1e-4)
    assert vals["position.lon"] == pytest.approx(151.2, abs=1e-4)


def test_gga_bad_checksum_raises() -> None:
    with pytest.raises(ValueError, match="checksum"):
        parse_sentence(GGA[:-2] + "00")
    with pytest.raises(ValueError):
        validate_checksum(GGA[:-2] + "00")


# --- RMC -------------------------------------------------------------------

RMC = "$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A"


def test_rmc_parses_position_sog_cog_time() -> None:
    vals = by_channel(parse_sentence(RMC))
    assert vals["position.lat"] == pytest.approx(48.1173, abs=1e-4)
    assert vals["position.lon"] == pytest.approx(11.5166667, abs=1e-4)
    assert vals["sog_kts"] == pytest.approx(22.4)
    assert vals["cog_deg"] == pytest.approx(84.4)
    assert vals["gps_time"] == "1994-03-23T12:35:19Z"


def test_rmc_void_status_yields_nothing() -> None:
    s = nmea("GNRMC,001500,V,,,,,,,230394,,")
    assert parse_sentence(s) == []


# --- DPT / DBT -------------------------------------------------------------

def test_dpt_depth() -> None:
    vals = by_channel(parse_sentence("$SDDPT,73.2,-1.5,*3A"))
    assert vals["depth_m"] == pytest.approx(73.2)


def test_dbt_uses_meters_field() -> None:
    vals = by_channel(parse_sentence(nmea("SDDBT,10.0,f,3.0,M,1.6,F")))
    assert vals["depth_m"] == pytest.approx(3.0)


# --- MWV -------------------------------------------------------------------

def test_mwv_true_wind() -> None:
    vals = by_channel(parse_sentence(nmea("WIMWV,045.0,T,12.5,N,A")))
    assert vals["wind_dir_deg"] == pytest.approx(45.0)
    assert vals["wind_kts"] == pytest.approx(12.5)


def test_mwv_apparent_wind() -> None:
    vals = by_channel(parse_sentence(nmea("WIMWV,030.0,R,10.0,N,A")))
    assert vals["apparent_wind_dir_deg"] == pytest.approx(30.0)
    assert vals["apparent_wind_kts"] == pytest.approx(10.0)


def test_mwv_ms_converted_to_knots() -> None:
    vals = by_channel(parse_sentence(nmea("WIMWV,090.0,T,5.0,M,A")))
    assert vals["wind_kts"] == pytest.approx(5.0 * 1.94384)


def test_mwv_invalid_status_yields_nothing() -> None:
    assert parse_sentence(nmea("WIMWV,045.0,T,12.5,N,V")) == []


# --- MTW / XDR -------------------------------------------------------------

def test_mtw_water_temp() -> None:
    vals = by_channel(parse_sentence(nmea("YXMTW,8.5,C")))
    assert vals["sea_temp_c"] == pytest.approx(8.5)


def test_xdr_air_temp_and_baro() -> None:
    s = nmea("YXXDR,C,22.4,C,AIR,P,1.0132,B,Baro")
    vals = by_channel(parse_sentence(s))
    assert vals["air_temp_c"] == pytest.approx(22.4)
    assert vals["baro_hpa"] == pytest.approx(1013.2)


# --- Unknown / malformed ----------------------------------------------------

def test_unknown_sentence_type_returns_empty() -> None:
    assert parse_sentence(nmea("GPVTG,084.4,T,081.3,M,022.4,N,41.5,K")) == []


def test_garbage_raises_valueerror() -> None:
    with pytest.raises(ValueError):
        parse_sentence("not a sentence at all")


# --- Quality ----------------------------------------------------------------

@pytest.mark.parametrize(
    "channel,value,expected",
    [
        ("position.lat", 57.05, "good"),
        ("position.lat", 91.0, "bad"),
        ("position.lat", -90.0, "good"),
        ("position.lon", -135.3, "good"),
        ("position.lon", 181.0, "bad"),
        ("depth_m", 73.2, "good"),
        ("depth_m", -1.0, "bad"),
        ("depth_m", 11000.0, "good"),
        ("wind_kts", 45.0, "good"),
        ("wind_kts", 201.0, "bad"),
        ("sea_temp_c", 8.5, "good"),
        ("sea_temp_c", 41.0, "bad"),
        ("air_temp_c", -40.0, "good"),
        ("air_temp_c", 61.0, "bad"),
        ("engine_rpm", 1800, "good"),
        ("engine_rpm", 4001, "bad"),
        ("engine_rpm", None, "bad"),
        ("depth_m", float("nan"), "bad"),
        ("depth_m", float("inf"), "bad"),
        ("gps_time", "1994-03-23T12:35:19Z", "fair"),
        ("some_future_channel", 42.0, "fair"),
    ],
)
def test_check_quality(channel: str, value: object, expected: str) -> None:
    assert check_quality(channel, value) == expected


# --- End to end -------------------------------------------------------------

def test_end_to_end_packet_build() -> None:
    """Parse a GGA, build packets, verify schema shape and quality."""
    ts = 1_753_478_400_000_000_000
    packets = [
        bridge_mod.build_packet(r, ts) for r in parse_sentence(GGA)
    ]
    assert {p["channel"] for p in packets} == {"position.lat", "position.lon"}
    for pkt in packets:
        assert set(pkt) == {
            "timestamp_ns", "source", "channel", "value", "quality", "sentence",
        }
        assert pkt["timestamp_ns"] == ts
        assert pkt["source"] == "nmea0183"
        assert pkt["quality"] == "good"
        assert pkt["sentence"] == GGA
        assert isinstance(pkt["value"], float)


def test_end_to_end_bridge_line_handling() -> None:
    """Feed lines through Bridge.handle_nmea_line with no subscribers."""
    b = bridge_mod.Bridge()
    packets = asyncio.run(b.handle_nmea_line("$SDDPT,73.2,-1.5,*3A\n"))
    assert len(packets) == 1
    assert packets[0]["channel"] == "depth_m"
    assert packets[0]["quality"] == "good"
    assert b.last_seen["depth_m"] is packets[0]
    # Malformed input is dropped, not fatal.
    assert asyncio.run(b.handle_nmea_line("garbage\n")) == []
    assert asyncio.run(b.handle_nmea_line("\n")) == []
