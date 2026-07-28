"""Signal K delta parser for the AELMA bridge.

Pure functions only -- no I/O, no side effects.  Each public function
takes a Signal K delta message and returns a list of telemetry reading
dicts.  The caller (bridge) is responsible for assigning the timestamp
and quality fields.

Signal K is a modern marine data format that uses self-describing JSON
deltas.  This module parses the "updates" field and converts Signal K
paths (e.g., "navigation.depth.belowTransom") to AELMA channels.

Reference: https://signalk.org/specification/1.0.0/doc/views/delta_updates.html

Supported paths (examples):
    navigation.position.*         -> position.lat, position.lon
    navigation.speedOverGround    -> sog_kn
    navigation.courseOverGround*  -> cog_deg
    navigation.depth.*            -> depth_m
    environment.wind.*            -> wind_kts_true/apparent, wind_dir_deg_true/apparent
    environment.water.temperature -> sea_temp_c
    environment.air.*             -> air_temp_c, baro_mb
"""

from __future__ import annotations

from typing import Any
import json

Reading = dict[str, Any]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any) -> float | None:
    """Parse *value* as float, returning None on empty or failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _reading(channel: str, value: Any, source: str = "signalk") -> Reading:
    """Build a single reading dict."""
    return {"source": source, "channel": channel, "value": value, "path": source}


# ---------------------------------------------------------------------------
# Path-to-channel mapping
# ---------------------------------------------------------------------------

def _navigation_position_to_readings(path: str, value: Any) -> list[Reading]:
    """Convert navigation.position.latitude/longitude to readings."""
    if "latitude" in path:
        return [_reading("position.lat", _safe_float(value), "signalk")]
    elif "longitude" in path:
        return [_reading("position.lon", _safe_float(value), "signalk")]
    return []


def _navigation_speed_to_readings(path: str, value: Any) -> list[Reading]:
    """Convert navigation.speedOverGround to reading (m/s -> knots)."""
    speed_ms = _safe_float(value)
    if speed_ms is None:
        return []
    # Convert m/s to knots (1 m/s = 1.94384 knots)
    speed_kn = speed_ms * 1.94384
    return [_reading("sog_kn", speed_kn, "signalk")]


def _navigation_course_to_readings(path: str, value: Any) -> list[Reading]:
    """Convert navigation.courseOverGroundTrue to reading."""
    cog = _safe_float(value)
    if cog is None:
        return []
    return [_reading("cog_deg", cog, "signalk")]


def _navigation_depth_to_readings(path: str, value: Any) -> list[Reading]:
    """Convert navigation.depth.* to reading."""
    depth = _safe_float(value)
    if depth is None:
        return []
    return [_reading("depth_m", depth, "signalk")]


def _wind_speed_to_readings(path: str, value: Any) -> list[Reading]:
    """Convert environment.wind.speedTrue/Apparent to reading (m/s -> knots)."""
    speed_ms = _safe_float(value)
    if speed_ms is None:
        return []
    # Convert m/s to knots
    speed_kn = speed_ms * 1.94384

    if "True" in path:
        return [_reading("wind_kts_true", speed_kn, "signalk")]
    elif "Apparent" in path:
        return [_reading("wind_kts_apparent", speed_kn, "signalk")]
    return []


def _wind_direction_to_readings(path: str, value: Any) -> list[Reading]:
    """Convert environment.wind.angleTrue/Apparent to reading."""
    angle = _safe_float(value)
    if angle is None:
        return []

    if "True" in path:
        return [_reading("wind_dir_deg_true", angle, "signalk")]
    elif "Apparent" in path:
        return [_reading("wind_dir_deg_apparent", angle, "signalk")]
    return []


def _water_temp_to_readings(path: str, value: Any) -> list[Reading]:
    """Convert environment.water.temperature to reading (Kelvin -> Celsius)."""
    temp_k = _safe_float(value)
    if temp_k is None:
        return []
    # Convert Kelvin to Celsius
    temp_c = temp_k - 273.15
    return [_reading("sea_temp_c", temp_c, "signalk")]


def _air_temp_to_readings(path: str, value: Any) -> list[Reading]:
    """Convert environment.air.temperature to reading (Kelvin -> Celsius)."""
    temp_k = _safe_float(value)
    if temp_k is None:
        return []
    # Convert Kelvin to Celsius
    temp_c = temp_k - 273.15
    return [_reading("air_temp_c", temp_c, "signalk")]


def _air_pressure_to_readings(path: str, value: Any) -> list[Reading]:
    """Convert environment.air.pressure to reading (Pa -> mb)."""
    pressure_pa = _safe_float(value)
    if pressure_pa is None:
        return []
    # Convert Pa to mb (1 Pa = 0.01 mb)
    pressure_mb = pressure_pa / 100.0
    return [_reading("baro_mb", pressure_mb, "signalk")]


# Path handler registry
_PATH_HANDLERS: dict[str, Any] = {
    # Navigation
    "navigation.position.latitude": _navigation_position_to_readings,
    "navigation.position.longitude": _navigation_position_to_readings,
    "navigation.speedOverGround": _navigation_speed_to_readings,
    "navigation.courseOverGroundTrue": _navigation_course_to_readings,
    "navigation.depth.belowKeel": _navigation_depth_to_readings,
    "navigation.depth.belowSurface": _navigation_depth_to_readings,
    "navigation.depth.belowTransom": _navigation_depth_to_readings,
    "navigation.depth.transducerToKeel": _navigation_depth_to_readings,

    # Environment wind
    "environment.wind.speedTrue": _wind_speed_to_readings,
    "environment.wind.speedApparent": _wind_speed_to_readings,
    "environment.wind.angleTrue": _wind_direction_to_readings,
    "environment.wind.angleApparent": _wind_direction_to_readings,

    # Environment water
    "environment.water.temperature": _water_temp_to_readings,

    # Environment air
    "environment.air.temperature": _air_temp_to_readings,
    "environment.air.pressure": _air_pressure_to_readings,
}


def _find_handler(path: str) -> Any:
    """Find a handler for the given path, supporting partial matches."""
    # Try exact match first
    if path in _PATH_HANDLERS:
        return _PATH_HANDLERS[path]

    # Try prefix match for more specific paths
    for registered_path, handler in _PATH_HANDLERS.items():
        if path.startswith(registered_path):
            return handler

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class SignalKDelta:
    """Parser for Signal K delta messages.

    A Signal K delta message contains one or more "updates" with values
    at specific paths.  This parser extracts all supported paths and
    converts them to AELMA channel readings.

    Example delta:
    {
        "context": "vessals.urn:mrn:imo:mmsi:123456789",
        "updates": [
            {
                "source": {
                    "type": "NMEA0183",
                    "sentence": "GPGGA"
                },
                "timestamp": "2025-01-15T12:34:56Z",
                "values": [
                    {
                        "path": "navigation.position.latitude",
                        "value": 56.8013
                    },
                    {
                        "path": "navigation.position.longitude",
                        "value": -135.3028
                    }
                ]
            }
        ]
    }
    """

    def __init__(self, delta_data: dict[str, Any] | str):
        """Initialize a Signal K delta parser.

        Args:
            delta_data: Either a parsed dict or JSON string of a Signal K delta.
        """
        if isinstance(delta_data, str):
            self._data = json.loads(delta_data)
        else:
            self._data = delta_data

    def to_readings(self) -> list[Reading]:
        """Convert all supported paths in the delta to readings.

        Returns:
            List of reading dicts with keys ``source``, ``channel``,
            ``value``, and ``path``.  Empty if no supported paths found.
        """
        readings: list[Reading] = []

        # Get updates array
        updates = self._data.get("updates", [])
        if not updates:
            return readings

        for update in updates:
            # Get values array from this update
            values = update.get("values", [])
            if not values:
                continue

            for value_entry in values:
                path = value_entry.get("path", "")
                value = value_entry.get("value")

                if not path:
                    continue

                # Find handler for this path
                handler = _find_handler(path)
                if handler is None:
                    continue

                # Convert to readings
                new_readings = handler(path, value)
                readings.extend(new_readings)

        return readings

    def get_context(self) -> str:
        """Get the context (vessel ID) from the delta."""
        return self._data.get("context", "")

    def get_timestamp(self) -> str:
        """Get the timestamp from the delta."""
        updates = self._data.get("updates", [])
        if updates:
            return updates[0].get("timestamp", "")
        return ""


def parse_delta(delta_data: dict[str, Any] | str) -> list[Reading]:
    """Parse a Signal K delta message into telemetry readings.

    This is a convenience function that creates a SignalKDelta instance
    and returns its readings.

    Args:
        delta_data: Either a parsed dict or JSON string of a Signal K delta.

    Returns:
        List of reading dicts with keys ``source``, ``channel``,
        ``value``, and ``path``.  Empty if no supported paths found.

    Example:
        >>> delta = {
        ...     "updates": [{
        ...         "values": [
        ...             {"path": "navigation.depth.belowKeel", "value": 73.2}
        ...         ]
        ...     }]
        ... }
        >>> readings = parse_delta(delta)
        >>> assert len(readings) == 1
        >>> assert readings[0]["channel"] == "depth_m"
        >>> assert readings[0]["value"] == 73.2
    """
    delta = SignalKDelta(delta_data)
    return delta.to_readings()


def path_to_channel(path: str) -> str | None:
    """Convert a Signal K path to an AELMA channel name.

    Args:
        path: Signal K path (e.g., "navigation.depth.belowKeel")

    Returns:
        AELMA channel name (e.g., "depth_m") or None if unsupported.

    Example:
        >>> path_to_channel("navigation.depth.belowKeel")
        'depth_m'
        >>> path_to_channel("navigation.speedOverGround")
        'sog_kn'
    """
    handler = _find_handler(path)
    if handler is None:
        return None

    # Call the handler and extract the channel name from the result
    readings = handler(path, 42.0)  # Use dummy value
    if readings:
        return readings[0]["channel"]
    return None


# ---------------------------------------------------------------------------
# WebSocket/Network utilities (pure functions for connection handling)
# ---------------------------------------------------------------------------

def signalk_ws_endpoint(host: str = "localhost", port: int = 3000) -> str:
    """Build a Signal K WebSocket endpoint URL.

    Args:
        host: Signal K server hostname or IP.
        port: Signal K server WebSocket port.

    Returns:
        WebSocket URL (e.g., "ws://localhost:3000/signalk/v1/stream")
    """
    return f"ws://{host}:{port}/signalk/v1/stream"


def signalk_tcp_endpoint(host: str = "localhost", port: int = 4000) -> str:
    """Build a Signal K TCP endpoint string.

    Args:
        host: Signal K server hostname or IP.
        port: Signal K server TCP port.

    Returns:
        TCP endpoint string (e.g., "localhost:4000")
    """
    return f"{host}:{port}"
