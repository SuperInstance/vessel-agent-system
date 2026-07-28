"""H3 geospatial index for fast fleet and bathymetry queries.

Vessels are bucketed into H3 hexagonal cells (default resolution 9,
~1 km across) so radius queries only scan the handful of cells that
cover the search disk instead of every tracked vessel. When a
:class:`~twin.bathymetry.BathymetryGrid` is attached, per-cell depth
statistics (mean/min/max) are derived from the soundings whose centers
fall inside each H3 cell.
"""

from __future__ import annotations

import math
from typing import Any

import h3

from .bathymetry import BathymetryGrid
from .state import haversine_m

DEFAULT_RESOLUTION = 9

# Approximate hexagon edge length (m) per H3 resolution; used to size the
# k-ring that covers a query radius. Only resolutions we plausibly use.
_EDGE_LENGTH_M = {
    7: 1206.0,
    8: 460.0,
    9: 174.0,
    10: 66.0,
    11: 25.0,
}


class H3Index:
    """Spatial index mapping H3 cells to the vessels inside them.

    Keeps three structures in sync: ``cell -> {vessel_ids}``,
    ``vessel_id -> cell``, and ``vessel_id -> (lat, lon)`` so radius
    queries can be refined with exact distances after the coarse
    k-ring candidate scan.
    """

    def __init__(
        self,
        resolution: int = DEFAULT_RESOLUTION,
        bathymetry: BathymetryGrid | None = None,
    ) -> None:
        """Create an empty index at the given H3 resolution.

        ``bathymetry`` is optional; when supplied, :meth:`get_cell_stats`
        includes depth statistics for the cell.
        """
        self.resolution = int(resolution)
        self._cell_vessels: dict[str, set[str]] = {}
        self._vessel_cell: dict[str, str] = {}
        self._vessel_pos: dict[str, tuple[float, float]] = {}
        self._bathymetry = bathymetry

    def insert_vessel(self, vessel_id: str, lat: float, lon: float) -> str:
        """Insert or move a vessel at (``lat``, ``lon``); returns its cell.

        Re-inserting an existing vessel updates its position and moves it
        between cells when it has crossed a boundary.
        """
        cell = h3.latlng_to_cell(lat, lon, self.resolution)
        old = self._vessel_cell.get(vessel_id)
        if old is not None and old != cell:
            bucket = self._cell_vessels.get(old)
            if bucket is not None:
                bucket.discard(vessel_id)
                if not bucket:
                    del self._cell_vessels[old]
        self._cell_vessels.setdefault(cell, set()).add(vessel_id)
        self._vessel_cell[vessel_id] = cell
        self._vessel_pos[vessel_id] = (float(lat), float(lon))
        return cell

    def remove_vessel(self, vessel_id: str) -> bool:
        """Remove a vessel from the index. Returns True if it was present."""
        cell = self._vessel_cell.pop(vessel_id, None)
        self._vessel_pos.pop(vessel_id, None)
        if cell is None:
            return False
        bucket = self._cell_vessels.get(cell)
        if bucket is not None:
            bucket.discard(vessel_id)
            if not bucket:
                del self._cell_vessels[cell]
        return True

    def cell_of(self, vessel_id: str) -> str | None:
        """Current H3 cell of a vessel, or None if not indexed."""
        return self._vessel_cell.get(vessel_id)

    def _k_ring_for_radius(self, radius_m: float) -> int:
        """k such that grid_disk(k) from the center covers ``radius_m``."""
        edge = _EDGE_LENGTH_M.get(self.resolution)
        if edge is None:
            # Hexagon edge length scales by ~sqrt(1/7) per resolution step.
            edge = _EDGE_LENGTH_M[9] * (7 ** ((9 - self.resolution) / 2))
        # A k-ring spans ~1.5 * k * edge from the center; add one ring of
        # slack for cells whose center is outside but vessels inside range.
        return max(1, math.ceil(radius_m / (1.5 * edge)) + 1)

    def query_radius(self, lat: float, lon: float, radius_m: float) -> list[str]:
        """Vessel IDs within ``radius_m`` of (``lat``, ``lon``).

        Candidates come from the k-ring of cells covering the disk, then
        each candidate's exact haversine distance decides membership, so
        results are precise rather than cell-quantized.
        """
        center = h3.latlng_to_cell(lat, lon, self.resolution)
        cells = h3.grid_disk(center, self._k_ring_for_radius(radius_m))
        out: list[str] = []
        for cell in cells:
            for vessel_id in self._cell_vessels.get(cell, ()):
                vlat, vlon = self._vessel_pos[vessel_id]
                if haversine_m(lat, lon, vlat, vlon) <= radius_m:
                    out.append(vessel_id)
        return sorted(out)

    def get_cell_stats(self, cell: str) -> dict[str, Any]:
        """Statistics for one H3 cell.

        Always includes vessel count and IDs. When a bathymetry grid is
        attached, also includes ``depth_mean_m`` / ``depth_min_m`` /
        ``depth_max_m`` / ``voxel_count`` over the grid voxels whose
        centers fall inside this cell (empty stats when no soundings).
        """
        vessels = sorted(self._cell_vessels.get(cell, ()))
        clat, clon = h3.cell_to_latlng(cell)
        stats: dict[str, Any] = {
            "cell": cell,
            "resolution": h3.get_resolution(cell),
            "center_lat": clat,
            "center_lon": clon,
            "vessel_count": len(vessels),
            "vessels": vessels,
            "voxel_count": 0,
            "depth_mean_m": None,
            "depth_min_m": None,
            "depth_max_m": None,
        }
        if self._bathymetry is not None:
            # Scan voxels near the cell center (public API), then keep only
            # those actually assigned to this cell.
            edge = _EDGE_LENGTH_M.get(self.resolution, _EDGE_LENGTH_M[9])
            voxels = self._bathymetry.cells_in_radius(clat, clon, 2.0 * edge)
            depths = [
                v[2]
                for v in voxels
                if h3.latlng_to_cell(v[0], v[1], self.resolution) == cell
            ]
            if depths:
                stats["voxel_count"] = len(depths)
                stats["depth_mean_m"] = round(sum(depths) / len(depths), 3)
                stats["depth_min_m"] = round(min(depths), 3)
                stats["depth_max_m"] = round(max(depths), 3)
        return stats

    def vessel_count(self) -> int:
        """Number of vessels currently indexed."""
        return len(self._vessel_cell)

    def populated_cells(self) -> list[str]:
        """Cells containing at least one vessel."""
        return sorted(self._cell_vessels)
