"""Quality assessment for AELMA telemetry channels.

Provides :func:`check_quality` which maps a channel name and value to a
quality grade: ``"good"``, ``"fair"``, ``"poor"``, or ``"bad"``.

The grading logic is intentionally simple:

* ``None`` or non-finite values (NaN / inf) are always ``"bad"``.
* Values outside the plausible range for a known channel are ``"bad"``.
* Values within range are ``"good"``.
* Unknown channel names return ``"fair"`` (we cannot vouch for them
  but they are not necessarily wrong).
"""

from __future__ import annotations

import math
from typing import Any

# Plausible ranges (min, max) for known channels.
# Any value inside the inclusive range is "good".
_RANGES: dict[str, tuple[float, float]] = {
    "position.lat": (-90.0, 90.0),
    "position.lon": (-180.0, 180.0),
    "depth_m": (0.0, 11000.0),
    "wind_kts": (0.0, 200.0),
    "wind_kts_true": (0.0, 200.0),
    "wind_kts_apparent": (0.0, 200.0),
    "wind_dir_deg": (0.0, 360.0),
    "wind_dir_deg_true": (0.0, 360.0),
    "wind_dir_deg_apparent": (0.0, 360.0),
    "sea_temp_c": (-5.0, 40.0),
    "air_temp_c": (-60.0, 60.0),
    "engine_rpm": (0.0, 4000.0),
    "sog_kn": (0.0, 60.0),
    "cog_deg": (0.0, 360.0),
    "baro_mb": (800.0, 1100.0),
}


def _is_bad_value(value: Any) -> bool:
    """Return ``True`` if *value* is None, NaN, or infinite."""
    if value is None:
        return True
    if isinstance(value, bool):
        # bool is a subclass of int; treat as a valid discrete value.
        return False
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return True
        if isinstance(value, float) and math.isinf(value):
            return True
        return False
    # Strings and booleans are acceptable as-is.
    return False


def check_quality(channel: str, value: Any) -> str:
    """Grade a telemetry reading.

    Args:
        channel: Channel name, e.g. ``"depth_m"`` or ``"position.lat"``.
        value:   The reading value (number, string, bool, or None).

    Returns:
        One of ``"good"``, ``"fair"``, ``"poor"``, ``"bad"``.
    """
    if _is_bad_value(value):
        return "bad"

    rng = _RANGES.get(channel)
    if rng is None:
        # Unknown channel -- we cannot assess range, so call it fair.
        return "fair"

    # Only range-check numeric values.
    if isinstance(value, bool):
        return "fair"
    if not isinstance(value, (int, float)):
        return "fair"

    lo, hi = rng
    if lo <= float(value) <= hi:
        return "good"
    return "bad"
