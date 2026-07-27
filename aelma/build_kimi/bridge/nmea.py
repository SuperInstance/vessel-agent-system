"""NMEA 0183 sentence parser for the AELMA bridge.

Pure functions, no I/O. Each public entry point takes one raw sentence
line and returns a list of reading dicts with keys::

    {"source": "nmea0183", "channel": str, "value": any, "sentence": str}

The caller (bridge) assigns ``timestamp_ns`` and ``quality``.

Checksums are validated: XOR of all bytes between ``$`` and ``*``
(exclusive) must equal the two hex digits after ``*``. A bad checksum
raises ``ValueError``.
"""

from __future__ import annotations

__all__ = ["parse_sentence", "validate_checksum"]

KMH_TO_KNOTS = 0.539957
MS_TO_KNOTS = 1.94384
BAR_TO_HPA = 1000.0


def validate_checksum(sentence: str) -> None:
    """Validate the NMEA checksum of *sentence*.

    Raises:
        ValueError: if the framing is wrong or the checksum mismatches.
    """
    s = sentence.strip()
    if not s.startswith("$"):
        raise ValueError(f"sentence does not start with '$': {sentence!r}")
    if "*" not in s:
        raise ValueError(f"sentence has no checksum: {sentence!r}")
    body, _, check = s[1:].rpartition("*")
    if len(check) < 2:
        raise ValueError(f"truncated checksum: {sentence!r}")
    expected = 0
    for ch in body:
        expected ^= ord(ch)
    try:
        actual = int(check[:2], 16)
    except ValueError:
        raise ValueError(f"non-hex checksum: {sentence!r}") from None
    if expected != actual:
        raise ValueError(
            f"checksum mismatch in {sentence!r}: "
            f"computed {expected:02X}, sentence says {actual:02X}"
        )


def _split(sentence: str) -> tuple[str, list[str]]:
    """Return (sentence_type, fields) after checksum validation."""
    validate_checksum(sentence)
    body = sentence.strip()[1:].rpartition("*")[0]
    parts = body.split(",")
    return parts[0], parts[1:]


def _float(field: str) -> float | None:
    """Parse a field as float; empty field -> None."""
    field = field.strip()
    if not field:
        return None
    return float(field)


def _lat_lon(raw: str, hemi: str) -> float | None:
    """Convert NMEA ddmm.mmm / dddmm.mmm to signed decimal degrees."""
    if not raw or not hemi:
        return None
    deg_len = 2 if hemi in ("N", "S") else 3
    deg = int(raw[:deg_len])
    minutes = float(raw[deg_len:])
    value = deg + minutes / 60.0
    if hemi in ("S", "W"):
        value = -value
    return value


def _reading(channel: str, value: object, sentence: str) -> dict:
    """Build one reading dict in the bridge's intermediate form."""
    return {
        "source": "nmea0183",
        "channel": channel,
        "value": value,
        "sentence": sentence.strip(),
    }


def _parse_gga(fields: list[str], sentence: str) -> list[dict]:
    """Parse GxGGA: time, lat, N/S, lon, E/W, fix quality, ..."""
    if len(fields) < 5:
        raise ValueError(f"GGA too short: {sentence!r}")
    lat = _lat_lon(fields[1], fields[2])
    lon = _lat_lon(fields[3], fields[4])
    out = []
    if lat is not None:
        out.append(_reading("position.lat", lat, sentence))
    if lon is not None:
        out.append(_reading("position.lon", lon, sentence))
    return out


def _parse_rmc(fields: list[str], sentence: str) -> list[dict]:
    """Parse GxRMC: time, status, lat, N/S, lon, E/W, SOG, COG, date."""
    if len(fields) < 9:
        raise ValueError(f"RMC too short: {sentence!r}")
    if fields[1] == "V":  # status field: receiver warning, no fix
        return []
    out = []
    lat = _lat_lon(fields[3], fields[4])
    lon = _lat_lon(fields[5], fields[6])
    if lat is not None:
        out.append(_reading("position.lat", lat, sentence))
    if lon is not None:
        out.append(_reading("position.lon", lon, sentence))
    sog = _float(fields[7])
    if sog is not None:
        out.append(_reading("sog_kts", sog, sentence))
    cog = _float(fields[8])
    if cog is not None:
        out.append(_reading("cog_deg", cog, sentence))
    # GPS time as ISO-8601-ish string; value type allows strings.
    if fields[1] and len(fields) > 9 and fields[9]:
        t, d = fields[1], fields[9]
        if len(t) >= 6 and len(d) == 6:
            year = 2000 + int(d[4:6])
            iso = (
                f"{year:04d}-{d[2:4]}-{d[0:2]}T"
                f"{t[0:2]}:{t[2:4]}:{t[4:]}Z"
            )
            out.append(_reading("gps_time", iso, sentence))
    return out


def _parse_dpt(fields: list[str], sentence: str) -> list[dict]:
    """Parse SDDPT: depth in meters below transducer (+offset ignored)."""
    if len(fields) < 1:
        raise ValueError(f"DPT too short: {sentence!r}")
    depth = _float(fields[0])
    if depth is None:
        return []
    return [_reading("depth_m", depth, sentence)]


def _parse_dbt(fields: list[str], sentence: str) -> list[dict]:
    """Parse SDDBT: depth in feet, fathoms, meters — take the meters."""
    if len(fields) < 6:
        raise ValueError(f"DBT too short: {sentence!r}")
    depth = _float(fields[5])
    if depth is None:
        return []
    return [_reading("depth_m", depth, sentence)]


def _parse_mwv(fields: list[str], sentence: str) -> list[dict]:
    """Parse WIMWV: angle, R(elative)/T(rue), speed, units, status."""
    if len(fields) < 5:
        raise ValueError(f"MWV too short: {sentence!r}")
    if fields[4] != "A":  # data not valid
        return []
    angle = _float(fields[0])
    speed = _float(fields[2])
    units = fields[3].upper()
    if speed is not None:
        if units == "K":
            speed *= KMH_TO_KNOTS
        elif units == "M":
            speed *= MS_TO_KNOTS
        # "N" is already knots
    ref = fields[1].upper()
    if ref == "T":
        dir_ch, spd_ch = "wind_dir_deg", "wind_kts"
    else:
        dir_ch, spd_ch = "apparent_wind_dir_deg", "apparent_wind_kts"
    out = []
    if angle is not None:
        out.append(_reading(dir_ch, angle, sentence))
    if speed is not None:
        out.append(_reading(spd_ch, speed, sentence))
    return out


def _parse_mtw(fields: list[str], sentence: str) -> list[dict]:
    """Parse YXMTW: water temperature in Celsius."""
    if len(fields) < 2 or fields[1].upper() != "C":
        raise ValueError(f"MTW not in Celsius: {sentence!r}")
    temp = _float(fields[0])
    if temp is None:
        return []
    return [_reading("sea_temp_c", temp, sentence)]


def _parse_xdr(fields: list[str], sentence: str) -> list[dict]:
    """Parse YXXDR transducer groups: type, value, units, name.

    Handles air temperature (type C) and barometric pressure (type P,
    reported in Bar, converted to hPa).
    """
    out = []
    for i in range(0, len(fields) - 3, 4):
        xtype, raw, units, name = fields[i : i + 4]
        value = _float(raw)
        if value is None:
            continue
        if xtype == "C" and units.upper() == "C":
            if "AIR" in name.upper():
                out.append(_reading("air_temp_c", value, sentence))
        elif xtype == "P" and units.upper() == "B":
            out.append(_reading("baro_hpa", value * BAR_TO_HPA, sentence))
    return out


_PARSERS = {
    "GGA": _parse_gga,
    "RMC": _parse_rmc,
    "DPT": _parse_dpt,
    "DBT": _parse_dbt,
    "MWV": _parse_mwv,
    "MTW": _parse_mtw,
    "XDR": _parse_xdr,
}


def parse_sentence(sentence: str) -> list[dict]:
    """Parse one NMEA 0183 sentence into zero or more readings.

    Args:
        sentence: raw sentence, e.g. ``"$GPGGA,...,*59\\r\\n"``.

    Returns:
        List of reading dicts. Empty for valid-but-uninformative
        sentences (void fixes, invalid data flags, unknown types).

    Raises:
        ValueError: on bad checksum or structurally malformed input.
    """
    stype, fields = _split(sentence)
    # Sentence type is the last 3 chars: $GPGGA -> GGA, $SDDPT -> DPT.
    key = stype[-3:] if len(stype) >= 3 else stype
    parser = _PARSERS.get(key)
    if parser is None:
        return []  # valid checksum, sentence type we don't handle
    try:
        return parser(fields, sentence)
    except (IndexError, ValueError) as exc:
        raise ValueError(f"malformed {key} sentence {sentence!r}: {exc}") from exc
