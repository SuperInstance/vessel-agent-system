"""Signal quality assessment for AELMA telemetry channels.

``check_quality`` applies per-channel plausibility ranges. Values
outside the range, ``None``, and NaN/inf are ``"bad"``. Channels with
no known range get ``"fair"`` (we have no basis to trust or distrust
them). In-range values are ``"good"``.
"""

from __future__ import annotations

import math

__all__ = ["check_quality", "RANGES"]

# Plausible physical ranges per channel: (min, max) inclusive.
RANGES: dict[str, tuple[float, float]] = {
    "position.lat": (-90.0, 90.0),
    "position.lon": (-180.0, 180.0),
    "depth_m": (0.0, 11000.0),
    "wind_kts": (0.0, 200.0),
    "apparent_wind_kts": (0.0, 200.0),
    "wind_dir_deg": (0.0, 360.0),
    "apparent_wind_dir_deg": (0.0, 360.0),
    "sog_kts": (0.0, 100.0),
    "cog_deg": (0.0, 360.0),
    "sea_temp_c": (-5.0, 40.0),
    "air_temp_c": (-60.0, 60.0),
    "engine_rpm": (0.0, 4000.0),
    "baro_hpa": (870.0, 1085.0),
}


def check_quality(channel: str, value: object) -> str:
    """Rate a telemetry reading as "good", "fair", "poor", or "bad".

    Args:
        channel: telemetry channel name, e.g. ``"depth_m"``.
        value: the reading; expected numeric for ranged channels.

    Returns:
        ``"bad"`` for None, NaN/inf, or out-of-range values;
        ``"good"`` for in-range values on known channels;
        ``"fair"`` for channels without a defined range.
    """
    if value is None:
        return "bad"
    limits = RANGES.get(channel)
    if limits is None:
        return "fair"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        # Non-numeric value on a numeric channel: cannot range-check it.
        return "fair"
    if math.isnan(value) or math.isinf(value):
        return "bad"
    low, high = limits
    if low <= value <= high:
        return "good"
    return "bad"
