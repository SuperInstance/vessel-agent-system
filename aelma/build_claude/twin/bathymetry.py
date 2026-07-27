"""Progressive bathymetry TSDF layer for the AELMA digital twin.

Each depth+position sample is fused into a quantised cell (~10 m at the
current latitude).  Cells accumulate a running average depth and a sample
count; confidence is derived from sample count and recency.
"""

from __future__ import annotations

import json
import math
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_M_PER_DEG_LAT = 111_000.0  # meters per degree of latitude
_CELL_SIZE_M = 10.0  # target cell size in meters
_WEEK_NS = 7 * 24 * 3600 * 1_000_000_000  # one week in nanoseconds


# ---------------------------------------------------------------------------
# Cell quantisation
# ---------------------------------------------------------------------------

def quantise_cell(lat: float, lon: float) -> tuple[int, int]:
    """Quantise a lat/lon position to a ~10 m grid cell.

    Returns a ``(lat_cell, lon_cell)`` integer tuple.  The cell size is
    approximately 10 m in both directions, adjusted for longitude
    convergence at high latitudes.

    Parameters
    ----------
    lat, lon
        Position in decimal degrees.

    Returns
    -------
    tuple[int, int]
        Integer cell coordinates.
    """
    lat_cell = round(lat / (_CELL_SIZE_M / _M_PER_DEG_LAT))

    lat_rad = math.radians(lat)
    cos_lat = math.cos(lat_rad)
    # Avoid division by zero at poles
    if abs(cos_lat) < 1e-12:
        cos_lat = 1e-12
    lon_cell = round(lon / (_CELL_SIZE_M / (_M_PER_DEG_LAT * cos_lat)))

    return (lat_cell, lon_cell)


def cell_center_from_key(
    lat_cell: int,
    lon_cell: int,
    ref_lat: float,
) -> tuple[float, float]:
    """Return the centre coordinates (lat, lon) of a quantised cell.

    Parameters
    ----------
    lat_cell, lon_cell
        Integer cell coordinates from :func:`quantise_cell`.
    ref_lat
        Reference latitude used to compute longitude convergence.

    Returns
    -------
    tuple[float, float]
        ``(lat, lon)`` in decimal degrees.
    """
    lat = lat_cell * (_CELL_SIZE_M / _M_PER_DEG_LAT)

    lat_rad = math.radians(ref_lat)
    cos_lat = math.cos(lat_rad)
    if abs(cos_lat) < 1e-12:
        cos_lat = 1e-12
    lon = lon_cell * (_CELL_SIZE_M / (_M_PER_DEG_LAT * cos_lat))

    return (lat, lon)


# Kept for backwards compatibility / external callers.
def cell_center(lat_cell: int, lon_cell: int, ref_lat: float = 0.0) -> tuple[float, float]:
    """Backwards-compatible wrapper for :func:`cell_center_from_key`."""
    return cell_center_from_key(lat_cell, lon_cell, ref_lat)


# ---------------------------------------------------------------------------
# BathymetryGrid
# ---------------------------------------------------------------------------

class BathymetryGrid:
    """Progressive TSDF bathymetry grid.

    Stores depth soundings in quantised ~10 m cells.  Each cell maintains
    a running-average depth, sample count, last-sample timestamp, source,
    and the geographic coordinates of the cell centre (recorded at first
    fusion time, so subsequent position queries are stable regardless of
    latitude shifts in later samples).
    """

    def __init__(self) -> None:
        """Initialise an empty grid."""
        # (lat_cell, lon_cell) -> cell dict
        self._cells: dict[tuple[int, int], dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Fusion
    # ------------------------------------------------------------------

    def fuse(
        self,
        lat: float,
        lon: float,
        depth_m: float,
        timestamp_ns: int,
        source: str = "sounder",
    ) -> None:
        """Fuse a single depth sounding into the grid.

        If the cell already exists, the depth is updated as a running
        average and the sample count is incremented.  The source is
        upgraded to ``"merged"`` when a cell receives samples from
        different sources.

        Parameters
        ----------
        lat, lon
            Position of the sounding in decimal degrees.
        depth_m
            Water depth in meters (positive downward).
        timestamp_ns
            UTC nanoseconds since Unix epoch.
        source
            Data source identifier (``"sounder"``, ``"chart"``, etc.).
        """
        key = quantise_cell(lat, lon)

        # Compute and store the cell centre coordinates at first fusion.
        # This ensures distance queries are stable even if later samples
        # at different latitudes shift the global reference latitude.
        center_lat, center_lon = cell_center_from_key(key[0], key[1], lat)

        cell = self._cells.get(key)
        if cell is None:
            self._cells[key] = {
                "depth_m": float(depth_m),
                "sample_count": 1,
                "last_sample_ns": timestamp_ns,
                "source": source,
                "center_lat": center_lat,
                "center_lon": center_lon,
            }
        else:
            count = cell["sample_count"]
            # Running average: new_avg = old_avg + (new - old_avg) / (count+1)
            cell["depth_m"] = cell["depth_m"] + (float(depth_m) - cell["depth_m"]) / (count + 1)
            cell["sample_count"] = count + 1
            cell["last_sample_ns"] = timestamp_ns
            if cell["source"] != source:
                cell["source"] = "merged"

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def confidence(self, cell: dict[str, Any], now_ns: int | None = None) -> float:
        """Compute confidence for a cell from sample count and recency.

        Formula (matching the voxel schema description):

        * Base confidence: ``min(0.1 * sample_count, 0.9)``
          (1 sample -> 0.1, 5 -> 0.5, 9+ -> 0.9)
        * Recency decay: 10% per week of age, floored at 0.

        Parameters
        ----------
        cell
            Internal cell dict with ``sample_count`` and
            ``last_sample_ns``.
        now_ns
            Current time in nanoseconds.  If ``None``, no recency decay
            is applied (useful for testing).

        Returns
        -------
        float
            Confidence in [0, 0.9].
        """
        base = min(0.1 * cell["sample_count"], 0.9)

        if now_ns is None:
            return base

        age_ns = now_ns - cell["last_sample_ns"]
        if age_ns <= 0:
            return base

        weeks_old = age_ns / _WEEK_NS
        # 10% decay per week, floored at 0
        decay = max(0.0, 1.0 - 0.1 * weeks_old)
        return base * decay

    def cells_in_radius(
        self,
        lat: float,
        lon: float,
        radius_m: float,
        now_ns: int | None = None,
    ) -> list[list[float]]:
        """Return all cells within *radius_m* of the given position.

        Each cell is returned as ``[lat, lon, depth_m, confidence]``.

        Parameters
        ----------
        lat, lon
            Centre of the search circle in decimal degrees.
        radius_m
            Search radius in meters.
        now_ns
            Optional current time for confidence recency decay.

        Returns
        -------
        list[list[float]]
            List of ``[lat, lon, depth_m, confidence]`` tuples.
        """
        from .state import haversine_m  # local import to avoid cycle at module load

        results: list[list[float]] = []
        for cell in self._cells.values():
            clat = cell["center_lat"]
            clon = cell["center_lon"]
            dist = haversine_m(lat, lon, clat, clon)
            if dist <= radius_m:
                conf = self.confidence(cell, now_ns)
                results.append([clat, clon, cell["depth_m"], conf])
        return results

    def total_voxels(self) -> int:
        """Return the total number of cells stored in the grid."""
        return len(self._cells)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """Persist the grid to a JSON file.

        Parameters
        ----------
        path
            Filesystem path to write.
        """
        data: dict[str, Any] = {"cells": []}
        for key, cell in self._cells.items():
            data["cells"].append({
                "lat": cell["center_lat"],
                "lon": cell["center_lon"],
                "lat_cell": key[0],
                "lon_cell": key[1],
                "depth_m": cell["depth_m"],
                "sample_count": cell["sample_count"],
                "last_sample_ns": cell["last_sample_ns"],
                "source": cell["source"],
            })

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self, path: str) -> None:
        """Load the grid from a JSON file written by :meth:`save`.

        Parameters
        ----------
        path
            Filesystem path to read.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._cells.clear()

        for entry in data.get("cells", []):
            # Prefer stored integer cell keys; fall back to re-quantising
            # from lat/lon for forward compatibility.
            lat_cell = entry.get("lat_cell")
            lon_cell = entry.get("lon_cell")
            if lat_cell is None or lon_cell is None:
                lat_cell, lon_cell = quantise_cell(entry["lat"], entry["lon"])

            self._cells[(lat_cell, lon_cell)] = {
                "depth_m": entry["depth_m"],
                "sample_count": entry["sample_count"],
                "last_sample_ns": entry["last_sample_ns"],
                "source": entry["source"],
                "center_lat": entry["lat"],
                "center_lon": entry["lon"],
            }
