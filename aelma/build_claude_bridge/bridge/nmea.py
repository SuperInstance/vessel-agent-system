"""NMEA 0183 sentence parser for the AELMA bridge.

Pure functions only -- no I/O, no side effects.  Each public function
takes a raw NMEA 0183 sentence string and returns a list of telemetry
reading dicts.  The caller (bridge) is responsible for assigning the
timestamp and quality fields.

Supported sentences:
    $GPGGA / $GNGGA  -- GPS fix (lat, lon)
    $GPRMC / $GNRMC  -- recommended minimum (lat, lon, SOG, COG)
    $SDDPT / $SDDBT  -- depth (meters)
    $WIMWV           -- wind speed and direction (true/apparent)
    $YXMTW           -- water temperature (Celsius)
    $YXXDR           -- transducer measurements (air temp, baro)
"""

from __future__ import annotations

from typing import Any

Reading = dict[str, Any]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_float(text: str | None) -> float | None:
    """Parse *text* as float, returning None on empty or failure."""
    if not text:
        return None
    try:
        return float(text)
    except (ValueError, TypeError):
        return None


def _reading(channel: str, value: Any, sentence: str) -> Reading:
    """Build a single reading dict."""
    return {"source": "nmea0183", "channel": channel, "value": value,
            "sentence": sentence.strip()}


def _convert_coord(value_str: str, hemi: str, positive_hemi: str) -> float | None:
    """Convert an NMEA ddmm.mmmm coordinate string to decimal degrees."""
    raw = _safe_float(value_str)
    if raw is None:
        return None
    int_part = value_str.split(".")[0] if "." in value_str else value_str
    if len(int_part) <= 2:
        degrees, minutes = 0.0, raw
    else:
        degrees = float(int_part[:-2])
        minutes = raw - degrees * 100.0
    decimal = degrees + minutes / 60.0
    if hemi and hemi.upper() != positive_hemi:
        decimal = -decimal
    return decimal


def _f_to_c(value: float) -> float:
    """Convert Fahrenheit to Celsius."""
    return (value - 32.0) * 5.0 / 9.0


# ---------------------------------------------------------------------------
# Per-sentence parsers (each returns list[Reading])
# ---------------------------------------------------------------------------

def _parse_gga(f: list[str], s: str) -> list[Reading]:
    """$GPGGA / $GNGGA: position fix."""
    out: list[Reading] = []
    lat = _convert_coord(f[2], f[3], "N") if len(f) > 3 else None
    lon = _convert_coord(f[4], f[5], "E") if len(f) > 5 else None
    if lat is not None:
        out.append(_reading("position.lat", lat, s))
    if lon is not None:
        out.append(_reading("position.lon", lon, s))
    return out


def _parse_rmc(f: list[str], s: str) -> list[Reading]:
    """$GPRMC / $GNRMC: position, SOG, COG."""
    out: list[Reading] = []
    lat = _convert_coord(f[3], f[4], "N") if len(f) > 4 else None
    lon = _convert_coord(f[5], f[6], "E") if len(f) > 6 else None
    sog = _safe_float(f[7]) if len(f) > 7 else None
    cog = _safe_float(f[8]) if len(f) > 8 else None
    for ch, val in [("position.lat", lat), ("position.lon", lon),
                     ("sog_kn", sog), ("cog_deg", cog)]:
        if val is not None:
            out.append(_reading(ch, val, s))
    return out


def _parse_dpt(f: list[str], s: str) -> list[Reading]:
    """$SDDPT: depth below transducer (field 1, meters)."""
    depth = _safe_float(f[1]) if len(f) > 1 else None
    return [_reading("depth_m", depth, s)] if depth is not None else []


def _parse_dbt(f: list[str], s: str) -> list[Reading]:
    """$SDDBT: depth below keel (field 3, meters)."""
    depth_m = _safe_float(f[3]) if len(f) > 3 else None
    return [_reading("depth_m", depth_m, s)] if depth_m is not None else []


def _parse_mwv(f: list[str], s: str) -> list[Reading]:
    """$WIMWV: wind speed (knots) and direction (degrees).

    Reference field f[2]: T=true, R=relative(apparent).
    Units field f[4]: K=knots, M=m/s, N=km/h.
    """
    out: list[Reading] = []
    wind_dir = _safe_float(f[1]) if len(f) > 1 else None
    ref = f[2].upper() if len(f) > 2 else ""
    wind_speed = _safe_float(f[3]) if len(f) > 3 else None
    units = f[4].upper() if len(f) > 4 else "K"
    if wind_speed is not None:
        if units == "M":       # m/s -> knots
            wind_speed *= 1.943844
        elif units == "N":     # km/h -> knots
            wind_speed *= 0.539957
    suffix = "true" if ref == "T" else "apparent"
    if wind_speed is not None:
        out.append(_reading(f"wind_kts_{suffix}", wind_speed, s))
    if wind_dir is not None:
        out.append(_reading(f"wind_dir_deg_{suffix}", wind_dir, s))
    return out


def _parse_mtw(f: list[str], s: str) -> list[Reading]:
    """$YXMTW: water temperature.  Field 2 unit C or F."""
    temp = _safe_float(f[1]) if len(f) > 1 else None
    unit = f[2].upper() if len(f) > 2 else "C"
    if temp is not None and unit == "F":
        temp = _f_to_c(temp)
    return [_reading("sea_temp_c", temp, s)] if temp is not None else []


def _parse_xdr(f: list[str], s: str) -> list[Reading]:
    """$YXXDR: transducer measurements (type, value, unit, name quartets).

    Handles air temp (C+AIR), baro (P), water temp (C+WATER).
    """
    out: list[Reading] = []
    i = 1
    while i + 2 < len(f):
        xdr_type = f[i].upper()
        value = _safe_float(f[i + 1])
        unit = f[i + 2].upper()
        name = f[i + 3].upper() if i + 3 < len(f) else ""
        if value is not None:
            if xdr_type == "C" and "AIR" in name:
                v = _f_to_c(value) if unit == "F" else value
                out.append(_reading("air_temp_c", v, s))
            elif xdr_type == "P":
                v = value * 1000.0 if unit == "B" else value
                out.append(_reading("baro_mb", v, s))
            elif xdr_type == "C" and "WATER" in name:
                v = _f_to_c(value) if unit == "F" else value
                out.append(_reading("sea_temp_c", v, s))
        i += 4
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_PARSERS: dict[str, Any] = {}


def _register(types: list[str]) -> Any:
    """Decorator to register a parser for multiple sentence types."""
    def decorator(func: Any) -> Any:
        for t in types:
            _PARSERS[t] = func
        return func
    return decorator


_register(["GPGGA", "GNGGA"])(_parse_gga)
_register(["GPRMC", "GNRMC"])(_parse_rmc)
_register(["SDDPT"])(_parse_dpt)
_register(["SDDBT"])(_parse_dbt)
_register(["WIMWV"])(_parse_mwv)
_register(["YXMTW"])(_parse_mtw)
_register(["YXXDR"])(_parse_xdr)


def verify_checksum(sentence: str) -> None:
    """Validate the XOR checksum of an NMEA 0183 sentence.

    The checksum is the XOR of all characters between ``$`` and ``*``
    (exclusive).  The hex pair after ``*`` must match.

    Raises:
        ValueError: If the sentence is malformed or checksum mismatches.
    """
    stripped = sentence.strip()
    if not stripped.startswith("$"):
        raise ValueError(f"Sentence must start with '$': {stripped!r}")
    star_idx = stripped.rfind("*")
    if star_idx == -1:
        raise ValueError(f"Sentence missing '*': {stripped!r}")
    body = stripped[1:star_idx]
    provided = stripped[star_idx + 1:].split(",")[0].strip()
    if len(provided) < 2:
        raise ValueError(f"Checksum too short: {stripped!r}")
    computed = 0
    for ch in body:
        computed ^= ord(ch)
    computed_hex = f"{computed:02X}"
    if computed_hex != provided.upper():
        raise ValueError(
            f"Checksum mismatch: computed {computed_hex}, "
            f"got {provided.upper()} in {stripped!r}"
        )


def _split_fields(sentence: str) -> list[str]:
    """Return the comma-separated fields of a sentence body."""
    stripped = sentence.strip()
    star_idx = stripped.rfind("*")
    return stripped[1:star_idx].split(",")


def parse_sentence(sentence: str) -> list[Reading]:
    """Parse a single NMEA 0183 sentence into telemetry readings.

    Args:
        sentence: One complete NMEA sentence (``$...*XX``).

    Returns:
        List of reading dicts with keys ``source``, ``channel``,
        ``value``, and ``sentence``.  Empty if unknown type or no data.

    Raises:
        ValueError: If the checksum is invalid or sentence malformed.
    """
    stripped = sentence.strip()
    if not stripped:
        return []
    verify_checksum(stripped)
    fields = _split_fields(stripped)
    if not fields or not fields[0]:
        return []
    parser = _PARSERS.get(fields[0].upper())
    if parser is None:
        return []
    return parser(fields, stripped)
