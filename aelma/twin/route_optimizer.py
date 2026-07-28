"""Route optimization for efficient fishing paths (AELMA twin).

Pure-Python route planner: keeps a waypoint list, orders an open or
closed route with a nearest-neighbor TSP approximation, measures legs
with great-circle haversine distances, estimates fuel cost from a simple
speed-dependent consumption model, and exports the result as GPX.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Sequence
from xml.sax.saxutils import escape

# Mean Earth radius in meters (spherical-earth model).
EARTH_RADIUS_M = 6371000.0
# Meters per nautical mile.
M_PER_NM = 1852.0
# One knot in meters per second (1852 m / 3600 s).
KN_TO_MPS = 1852.0 / 3600.0

# Simple fuel model: a vessel burns BASE_L_PER_NM liters per nautical mile
# at REFERENCE_SPEED_KN, and consumption scales with the square of speed.
BASE_L_PER_NM = 2.0
REFERENCE_SPEED_KN = 8.0
DEFAULT_FUEL_PRICE_PER_L = 1.50


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle haversine distance between two fixes, in meters.

    a = sin^2(dphi/2) + cos(phi1) * cos(phi2) * sin^2(dlam/2)
    d = 2 * R * atan2(sqrt(a), sqrt(1 - a))
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def _as_point(wp: Any) -> tuple[float, float, str]:
    """Normalize a waypoint to (lat, lon, name).

    Accepts a dict with ``lat``/``lon``/optional ``name`` keys, or a
    ``(lat, lon)`` / ``(lat, lon, name)`` tuple/list.
    """
    if isinstance(wp, dict):
        return float(wp["lat"]), float(wp["lon"]), str(wp.get("name", ""))
    if isinstance(wp, (tuple, list)):
        if len(wp) == 2:
            return float(wp[0]), float(wp[1]), ""
        if len(wp) == 3:
            return float(wp[0]), float(wp[1]), str(wp[2])
    raise ValueError(f"Unsupported waypoint format: {wp!r}")


class RouteOptimizer:
    """Waypoint store plus nearest-neighbor route planner for one vessel.

    Waypoints are added with :meth:`add_waypoint` and ordered into an
    efficient path with :meth:`optimize_route`. Distances are great-circle
    haversine meters; fuel estimates use a speed-squared consumption model.
    """

    def __init__(self, fuel_price_per_l: float = DEFAULT_FUEL_PRICE_PER_L) -> None:
        """Initialize an empty waypoint list and the fuel price used for costs."""
        self.waypoints: list[dict[str, Any]] = []
        self.fuel_price_per_l = float(fuel_price_per_l)

    # ------------------------------------------------------------------
    # Waypoints
    # ------------------------------------------------------------------

    def add_waypoint(self, lat: float, lon: float, name: str = "") -> dict[str, Any]:
        """Add a named waypoint and return it as ``{"lat", "lon", "name"}``."""
        lat, lon = float(lat), float(lon)
        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            raise ValueError(f"Invalid waypoint coordinates: ({lat}, {lon})")
        wp = {"lat": lat, "lon": lon, "name": name}
        self.waypoints.append(wp)
        return wp

    def clear_waypoints(self) -> None:
        """Remove all stored waypoints."""
        self.waypoints.clear()

    # ------------------------------------------------------------------
    # Distance / fuel
    # ------------------------------------------------------------------

    def calculate_distance(self, points: Sequence[Any]) -> float:
        """Total haversine distance in meters along a sequence of points."""
        if len(points) < 2:
            return 0.0
        pts = [_as_point(p) for p in points]
        return sum(
            haversine_m(a[0], a[1], b[0], b[1])
            for a, b in zip(pts, pts[1:])
        )

    def calculate_fuel_cost(
        self,
        distance_m: float,
        speed_kn: float,
        fuel_price_per_l: float | None = None,
    ) -> dict[str, float]:
        """Estimate fuel usage and cost for a leg.

        Consumption is ``BASE_L_PER_NM`` liters per nautical mile at
        ``REFERENCE_SPEED_KN``, scaled by ``(speed / reference)^2`` — a
        common first-order model for displacement hulls. Returns a dict with
        ``distance_nm``, ``duration_h``, ``fuel_liters`` and ``fuel_cost``.
        """
        if distance_m < 0:
            raise ValueError("distance_m must be non-negative")
        if speed_kn <= 0:
            raise ValueError("speed_kn must be positive")
        price = self.fuel_price_per_l if fuel_price_per_l is None else float(fuel_price_per_l)
        distance_nm = distance_m / M_PER_NM
        duration_h = distance_m / (speed_kn * KN_TO_MPS) / 3600.0
        fuel_liters = distance_nm * BASE_L_PER_NM * (speed_kn / REFERENCE_SPEED_KN) ** 2
        return {
            "distance_nm": distance_nm,
            "duration_h": duration_h,
            "fuel_liters": fuel_liters,
            "fuel_cost": fuel_liters * price,
        }

    # ------------------------------------------------------------------
    # Optimization (nearest-neighbor TSP approximation)
    # ------------------------------------------------------------------

    def optimize_route(
        self,
        start: Any,
        waypoints: Sequence[Any] | None = None,
        end: Any | None = None,
    ) -> dict[str, Any]:
        """Order waypoints into a near-shortest route from ``start``.

        Uses the nearest-neighbor TSP approximation: repeatedly visit the
        closest unvisited waypoint, then finish at ``end`` if given (open
        route otherwise). ``waypoints`` defaults to the stored list.

        Returns ``{"route", "legs", "total_distance_m"}`` where ``route``
        is the ordered waypoint list (start, waypoints..., end) and each
        leg carries its haversine distance in meters.
        """
        start_pt = _as_point(start)
        pool = [_as_point(wp) for wp in (self.waypoints if waypoints is None else waypoints)]
        end_pt = _as_point(end) if end is not None else None

        ordered: list[tuple[float, float, str]] = [start_pt]
        current = start_pt
        remaining = list(pool)
        legs: list[dict[str, Any]] = []
        total_m = 0.0

        while remaining:
            nearest = min(
                remaining,
                key=lambda wp: haversine_m(current[0], current[1], wp[0], wp[1]),
            )
            leg_m = haversine_m(current[0], current[1], nearest[0], nearest[1])
            legs.append({"from": current[2], "to": nearest[2], "distance_m": leg_m})
            total_m += leg_m
            ordered.append(nearest)
            remaining.remove(nearest)
            current = nearest

        if end_pt is not None:
            leg_m = haversine_m(current[0], current[1], end_pt[0], end_pt[1])
            legs.append({"from": current[2], "to": end_pt[2], "distance_m": leg_m})
            total_m += leg_m
            ordered.append(end_pt)

        route = [{"lat": lat, "lon": lon, "name": name} for lat, lon, name in ordered]
        return {"route": route, "legs": legs, "total_distance_m": total_m}

    # ------------------------------------------------------------------
    # GPX export
    # ------------------------------------------------------------------

    def export_gpx(
        self,
        route: Sequence[Any],
        name: str = "AELMA Optimized Route",
        filepath: str | Path | None = None,
    ) -> str:
        """Export an ordered route as GPX 1.1 XML.

        ``route`` is a sequence of waypoints (dicts or tuples, typically the
        ``route`` list from :meth:`optimize_route`). Returns the GPX string;
        when ``filepath`` is given the XML is also written to that file.
        """
        pts = [_as_point(p) for p in route]
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<gpx version="1.1" creator="AELMA RouteOptimizer"'
            ' xmlns="http://www.topografix.com/GPX/1/1">',
            f"  <name>{escape(name)}</name>",
            "  <rte>",
            f"    <name>{escape(name)}</name>",
        ]
        for lat, lon, wp_name in pts:
            lines.append(f'    <rtept lat="{lat:.6f}" lon="{lon:.6f}">')
            if wp_name:
                lines.append(f"      <name>{escape(wp_name)}</name>")
            lines.append("    </rtept>")
        lines.append("  </rte>")
        lines.append("</gpx>")
        gpx = "\n".join(lines) + "\n"
        if filepath is not None:
            Path(filepath).write_text(gpx, encoding="utf-8")
        return gpx
