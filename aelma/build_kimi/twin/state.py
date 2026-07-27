"""Vessel state tracking for the AELMA twin core.

Maintains the latest reading per telemetry channel and the vessel pose
(lat, lon, heading, speed). Heading and speed are derived from successive
position fixes using great-circle bearing and a simplified haversine
distance. Between fixes, :meth:`VesselState.snapshot` dead-reckons the
pose forward along the last known heading and speed.
"""

from __future__ import annotations

import math
import time
from typing import Any

# Meters per degree of latitude (spherical-earth approximation).
M_PER_DEG_LAT = 111000.0
# One knot in meters per second (1852 m / 3600 s).
KN_TO_MPS = 1852.0 / 3600.0


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle initial bearing from point 1 to point 2, in [0, 360).

    theta = atan2(sin(dlon) * cos(lat2),
                  cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon))
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    y = math.sin(dlam) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    return math.degrees(math.atan2(y, x)) % 360.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Simplified haversine (equirectangular) distance in meters.

    d = sqrt(dlat^2 + (dlon * cos(lat_mean))^2) * 111000, angles in degrees.
    Accurate to well under a meter for the short legs between position fixes.
    """
    dlat = lat2 - lat1
    dlon = (lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2.0))
    return math.sqrt(dlat * dlat + dlon * dlon) * M_PER_DEG_LAT


class VesselState:
    """Latest-reading cache plus derived pose for one vessel.

    Position arrives as separate ``position.lat`` / ``position.lon`` packets.
    A *fix* is complete when both components carry the same ``timestamp_ns``;
    only complete fixes update heading and speed, so a split fix never
    produces a bogus vector.
    """

    def __init__(self) -> None:
        """Initialize an empty state: no channels, no fix, no pose."""
        self.channels: dict[str, dict[str, Any]] = {}
        self.lat: float | None = None
        self.lon: float | None = None
        self.heading_deg: float | None = None
        self.speed_kn: float | None = None
        # Component timestamps used to pair split lat/lon packets.
        self._lat_ts: int | None = None
        self._lon_ts: int | None = None
        # Last complete fix (lat, lon, timestamp_ns) used for derivation.
        self._last_fix: tuple[float, float, int] | None = None

    def apply_packet(self, packet: dict[str, Any]) -> None:
        """Fold one TelemetryPacket into the state.

        Every packet refreshes its channel entry. ``position.lat`` /
        ``position.lon`` packets additionally update the pose and, when they
        complete a fix, derive heading (great-circle bearing) and speed
        (distance / dt) from the previous fix.
        """
        channel = str(packet["channel"])
        value = packet["value"]
        ts = int(packet["timestamp_ns"])
        self.channels[channel] = {
            "value": value,
            "timestamp_ns": ts,
            "quality": packet.get("quality", "good"),
        }

        if channel == "position.lat" and isinstance(value, (int, float)):
            self.lat = float(value)
            self._lat_ts = ts
            self._maybe_complete_fix(ts)
        elif channel == "position.lon" and isinstance(value, (int, float)):
            self.lon = float(value)
            self._lon_ts = ts
            self._maybe_complete_fix(ts)

    def _maybe_complete_fix(self, ts: int) -> None:
        """Derive heading/speed when lat and lon share a fresh timestamp."""
        if self.lat is None or self.lon is None:
            return
        if self._lat_ts != self._lon_ts or self._lat_ts != ts:
            return  # split fix: wait for the paired component
        if self._last_fix is not None and ts <= self._last_fix[2]:
            return  # stale or duplicate fix
        if self._last_fix is not None:
            prev_lat, prev_lon, prev_ts = self._last_fix
            dt_s = (ts - prev_ts) / 1e9
            dist_m = haversine_m(prev_lat, prev_lon, self.lat, self.lon)
            if dt_s > 0 and dist_m > 0:
                self.heading_deg = bearing_deg(prev_lat, prev_lon, self.lat, self.lon)
                self.speed_kn = (dist_m / dt_s) / KN_TO_MPS
        self._last_fix = (self.lat, self.lon, ts)

    def dead_reckon(self, now_ns: int) -> tuple[float | None, float | None]:
        """Extrapolate (lat, lon) to ``now_ns`` along last heading and speed.

        Returns the raw fix coordinates when heading/speed are unknown.
        """
        if self.lat is None or self.lon is None:
            return None, None
        if (
            self._last_fix is None
            or self.heading_deg is None
            or self.speed_kn is None
            or now_ns <= self._last_fix[2]
        ):
            return self.lat, self.lon
        fix_lat, fix_lon, fix_ts = self._last_fix
        dt_s = (now_ns - fix_ts) / 1e9
        dist_m = self.speed_kn * KN_TO_MPS * dt_s
        theta = math.radians(self.heading_deg)
        lat = fix_lat + (dist_m * math.cos(theta)) / M_PER_DEG_LAT
        lon = fix_lon + (dist_m * math.sin(theta)) / (
            M_PER_DEG_LAT * math.cos(math.radians(fix_lat))
        )
        return lat, lon

    def snapshot(
        self,
        vessel_id: str,
        viewport: list[float] | None = None,
        now_ns: int | None = None,
    ) -> dict[str, Any]:
        """Build a VesselStateSnapshot dict matching vessel_state.schema.json.

        The pose is dead-reckoned to ``now_ns``. ``viewport`` (radius spec for
        the bathymetry block, e.g. ``[500]`` or ``[lat, lon, radius_m]``) is
        accepted here so callers use one signature; the bathymetry block
        itself is assembled by :class:`~build_kimi.twin.core.TwinCore`, which
        owns the grid.
        """
        del viewport  # consumed by TwinCore when attaching bathymetry
        if now_ns is None:
            now_ns = time.time_ns()
        lat, lon = self.dead_reckon(now_ns)
        return {
            "timestamp_ns": now_ns,
            "vessel_id": vessel_id,
            "pose": {
                "lat": lat if lat is not None else 0.0,
                "lon": lon if lon is not None else 0.0,
                "heading_deg": self.heading_deg,
                "speed_kn": self.speed_kn,
            },
            "channels": {name: dict(entry) for name, entry in self.channels.items()},
        }
