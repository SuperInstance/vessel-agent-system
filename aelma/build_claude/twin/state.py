"""Vessel state management for the AELMA digital twin.

Maintains the latest per-channel telemetry reading and computes a smoothed
pose (position, heading, speed) from successive position fixes using
great-circle bearing and haversine distance.
"""

from __future__ import annotations

import math
import time
from typing import Any


# ---------------------------------------------------------------------------
# Geodesy helpers
# ---------------------------------------------------------------------------

_EARTH_RADIUS_M = 6_371_000.0  # mean Earth radius in meters
_M_PER_DEG_LAT = 111_000.0  # approximate meters per degree latitude


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance between two WGS84 points in meters.

    Uses the simplified equirectangular approximation as specified in the
    build brief:

        d = sqrt(dlat^2 + (dlon*cos(lat_mean))^2) * 111_000

    This is accurate to within ~0.5% for distances under 100 km at latitudes
    below 70 degrees, which covers all AELMA operating areas.
    """
    lat_mean = math.radians((lat1 + lat2) / 2.0)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    return math.sqrt(dlat * dlat + (dlon * math.cos(lat_mean)) ** 2) * _M_PER_DEG_LAT


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the initial great-circle bearing from point 1 to point 2.

    Uses the standard forward azimuth formula:

        theta = atan2(
            sin(dlon)*cos(lat2),
            cos(lat1)*sin(lat2) - sin(lat1)*cos(lat2)*cos(dlon)
        )

    Result is normalised to [0, 360).
    """
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlon = math.radians(lon2 - lon1)

    x = math.sin(dlon) * math.cos(lat2_r)
    y = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(dlon)

    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360.0) % 360.0


def mps_to_knots(mps: float) -> float:
    """Convert meters/second to knots."""
    return mps / 0.514444


# ---------------------------------------------------------------------------
# VesselState
# ---------------------------------------------------------------------------

class VesselState:
    """Holds the latest per-channel telemetry reading and current vessel pose.

    The twin calls :meth:`apply_packet` for every incoming ``TelemetryPacket``.
    Position fixes (``position.lat`` and ``position.lon`` channels) are paired
    to compute heading and speed via great-circle bearing and haversine
    distance divided by the time delta between fixes.

    :meth:`snapshot` produces a ``VesselStateSnapshot`` dict matching the
    JSON schema, including a viewport-filtered bathymetry summary.
    """

    def __init__(self) -> None:
        """Initialise an empty vessel state."""
        # Latest per-channel readings: channel -> {value, timestamp_ns, quality}
        self.channels: dict[str, dict[str, Any]] = {}

        # Pose
        self.lat: float | None = None
        self.lon: float | None = None
        self.heading_deg: float | None = None
        self.speed_kn: float | None = None

        # Previous *complete* position fix (used for bearing/speed delta)
        self._prev_lat: float | None = None
        self._prev_lon: float | None = None
        self._prev_pos_ts_ns: int | None = None

        # Buffered lat/lon waiting for their counterpart within the same
        # timestamp window.  The bridge often emits position.lat and
        # position.lon as separate packets with the same (or very close)
        # timestamp; we pair them here.
        self._pending_lat: float | None = None
        self._pending_lat_ts: int | None = None
        self._pending_lon: float | None = None
        self._pending_lon_ts: int | None = None

    # ------------------------------------------------------------------
    # Packet ingestion
    # ------------------------------------------------------------------

    def apply_packet(self, packet: dict) -> None:
        """Update internal state from a single TelemetryPacket.

        Parameters
        ----------
        packet
            A dict matching the ``TelemetryPacket`` JSON schema.  Must
            contain ``timestamp_ns``, ``source``, ``channel``, and
            ``value`` keys.

        Notes
        -----
        * Non-position channels are stored verbatim in ``self.channels``.
        * ``position.lat`` and ``position.lon`` are buffered and paired.
          When both are available we compute heading (great-circle bearing)
          and speed (haversine distance / dt in knots).
        """
        channel: str = packet["channel"]
        value = packet["value"]
        ts: int = packet["timestamp_ns"]
        quality: str = packet.get("quality", "good")

        # Store generic channel reading
        self.channels[channel] = {
            "value": value,
            "timestamp_ns": ts,
            "quality": quality,
        }

        # Handle position channels specially
        if channel == "position.lat":
            self._pending_lat = float(value)
            self._pending_lat_ts = ts
            self._try_pair_position()
        elif channel == "position.lon":
            self._pending_lon = float(value)
            self._pending_lon_ts = ts
            self._try_pair_position()

    def _try_pair_position(self) -> None:
        """Attempt to merge pending lat/lon into a full position fix.

        Both pending values must be present and their timestamps must be
        within 2 seconds of each other to be considered the same fix.
        """
        if (
            self._pending_lat is None
            or self._pending_lon is None
            or self._pending_lat_ts is None
            or self._pending_lon_ts is None
        ):
            return

        # Timestamps must be within 2 seconds (2_000_000_000 ns)
        if abs(self._pending_lat_ts - self._pending_lon_ts) > 2_000_000_000:
            return

        new_lat = self._pending_lat
        new_lon = self._pending_lon
        new_ts = max(self._pending_lat_ts, self._pending_lon_ts)

        # Update current pose position
        self.lat = new_lat
        self.lon = new_lon

        # Compute heading and speed if we have a previous fix
        if (
            self._prev_lat is not None
            and self._prev_lon is not None
            and self._prev_pos_ts_ns is not None
            and new_ts > self._prev_pos_ts_ns
        ):
            dt_s = (new_ts - self._prev_pos_ts_ns) / 1e9
            if dt_s > 0:
                dist_m = haversine_m(self._prev_lat, self._prev_lon, new_lat, new_lon)
                self.heading_deg = bearing_deg(self._prev_lat, self._prev_lon, new_lat, new_lon)
                self.speed_kn = mps_to_knots(dist_m / dt_s)

        # Store for next delta
        self._prev_lat = new_lat
        self._prev_lon = new_lon
        self._prev_pos_ts_ns = new_ts

        # Clear pending
        self._pending_lat = None
        self._pending_lat_ts = None
        self._pending_lon = None
        self._pending_lon_ts = None

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def snapshot(
        self,
        vessel_id: str,
        viewport: list | None = None,
        bathymetry=None,
    ) -> dict:
        """Return a ``VesselStateSnapshot`` dict matching the JSON schema.

        Parameters
        ----------
        vessel_id
            Vessel identifier string (e.g. ``"US-AK-FVEILEEN-51"``).
        viewport
            Optional ``[lat, lon, radius_m]`` viewport specification.  When
            provided along with *bathymetry*, the snapshot includes a
            bathymetry summary with cells within the radius.
        bathymetry
            Optional :class:`~twin.bathymetry.BathymetryGrid` to draw
            viewport cells from.

        Returns
        -------
        dict
            A dict conforming to ``vessel_state.schema.json``.
        """
        ts_ns = int(time.time() * 1e9)

        pose: dict[str, Any] = {
            "lat": self.lat if self.lat is not None else 0.0,
            "lon": self.lon if self.lon is not None else 0.0,
            "heading_deg": self.heading_deg,
            "speed_kn": self.speed_kn,
        }

        snap: dict[str, Any] = {
            "timestamp_ns": ts_ns,
            "vessel_id": vessel_id,
            "pose": pose,
            "channels": dict(self.channels),
        }

        if viewport is not None and bathymetry is not None:
            vlat, vlon, vradius_m = viewport[0], viewport[1], viewport[2]
            cells = bathymetry.cells_in_radius(vlat, vlon, vradius_m)
            snap["bathymetry"] = {
                "voxel_count": bathymetry.total_voxels(),
                "viewport_center": {"lat": vlat, "lon": vlon},
                "viewport_radius_m": vradius_m,
                "cells": cells,
            }

        return snap
