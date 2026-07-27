"""Progressive bathymetry TSDF layer for the AELMA twin core.

Every depth sounding that arrives with a known vessel position is fused
into a voxel grid. Cells are ~10 m square, quantized in degrees so the
longitude cell width shrinks with cos(latitude). Each cell keeps a running
average depth, a sample count, the last sample timestamp, and a source;
confidence is derived from sample count with a weekly recency decay.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

from .state import M_PER_DEG_LAT, haversine_m

CELL_SIZE_M = 10.0
# Confidence model (per bathymetry_voxel.schema.json):
#   1 sample -> 0.1, 5 samples -> 0.5, 20+ samples -> 0.9 (capped),
#   then decays 10% per week since the last sample.
CONF_PER_SAMPLE = 0.1
CONF_MAX = 0.9
WEEK_NS = 7 * 24 * 3600 * 1_000_000_000
DECAY_PER_WEEK = 0.1

_VALID_SOURCES = {"sounder", "chart", "drone", "rov", "manual", "merged"}


def lat_cell_of(lat: float) -> int:
    """Quantize a latitude to its ~10 m cell index."""
    return round(lat / (CELL_SIZE_M / M_PER_DEG_LAT))


def lon_cell_of(lon: float, lat: float) -> int:
    """Quantize a longitude to its ~10 m cell index at the given latitude."""
    width_deg = CELL_SIZE_M / (M_PER_DEG_LAT * math.cos(math.radians(lat)))
    return round(lon / width_deg)


class BathymetryGrid:
    """Sparse voxel grid of fused depth soundings.

    Internally a dict keyed by ``(lat_cell, lon_cell)`` integer indices.
    Each value is a voxel dict matching bathymetry_voxel.schema.json
    (``lat``/``lon`` hold the cell center in decimal degrees).
    """

    def __init__(self) -> None:
        """Initialize an empty grid."""
        self._cells: dict[tuple[int, int], dict[str, Any]] = {}

    def fuse(
        self,
        lat: float,
        lon: float,
        depth_m: float,
        timestamp_ns: int,
        source: str = "sounder",
    ) -> dict[str, Any]:
        """Fuse one sounding into its cell: running average, count, timestamp.

        Returns the updated voxel. When a different source contributes to an
        existing cell the source is promoted to ``"merged"``.
        """
        if source not in _VALID_SOURCES:
            source = "sounder"
        key = (lat_cell_of(lat), lon_cell_of(lon, lat))
        cell = self._cells.get(key)
        if cell is None:
            center_lat = key[0] * (CELL_SIZE_M / M_PER_DEG_LAT)
            lon_width = CELL_SIZE_M / (M_PER_DEG_LAT * math.cos(math.radians(center_lat)))
            cell = {
                "lat": center_lat,
                "lon": key[1] * lon_width,
                "depth_m": float(depth_m),
                "sample_count": 1,
                "last_sample_ns": int(timestamp_ns),
                "source": source,
            }
            self._cells[key] = cell
        else:
            n = cell["sample_count"]
            cell["depth_m"] = (cell["depth_m"] * n + float(depth_m)) / (n + 1)
            cell["sample_count"] = n + 1
            cell["last_sample_ns"] = max(cell["last_sample_ns"], int(timestamp_ns))
            if cell["source"] != source:
                cell["source"] = "merged"
        return cell

    def confidence(self, cell: dict[str, Any], now_ns: int | None = None) -> float:
        """Confidence in a cell's depth: sample count with recency decay.

        Base confidence is ``min(0.1 * sample_count, 0.9)``; the result is
        multiplied by ``0.9 ** weeks_since_last_sample``.
        """
        if now_ns is None:
            now_ns = time.time_ns()
        base = min(CONF_PER_SAMPLE * cell["sample_count"], CONF_MAX)
        weeks = max(0, now_ns - cell["last_sample_ns"]) / WEEK_NS
        return base * (1.0 - DECAY_PER_WEEK) ** weeks

    def cells_in_radius(
        self,
        lat: float,
        lon: float,
        radius_m: float,
        now_ns: int | None = None,
    ) -> list[list[float]]:
        """Viewport query: cells whose center lies within ``radius_m``.

        Returns ``[[lat, lon, depth_m, confidence], ...]`` as the
        vessel_state schema's bathymetry block expects.
        """
        out: list[list[float]] = []
        for cell in self._cells.values():
            if haversine_m(lat, lon, cell["lat"], cell["lon"]) <= radius_m:
                out.append(
                    [
                        cell["lat"],
                        cell["lon"],
                        round(cell["depth_m"], 3),
                        round(self.confidence(cell, now_ns), 4),
                    ]
                )
        return out

    def total_voxels(self) -> int:
        """Number of populated cells in the grid."""
        return len(self._cells)

    def save(self, path: str | Path) -> None:
        """Persist the grid to JSON (list of schema-shaped voxels)."""
        payload = {"cells": [dict(cell) for cell in self._cells.values()]}
        Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load(self, path: str | Path) -> None:
        """Load a grid previously written by :meth:`save`.

        Missing files are tolerated (grid stays empty); confidence is not
        stored because it is derived from count and recency at query time.
        """
        p = Path(path)
        if not p.exists():
            return
        payload = json.loads(p.read_text(encoding="utf-8"))
        for cell in payload.get("cells", []):
            key = (lat_cell_of(cell["lat"]), lon_cell_of(cell["lon"], cell["lat"]))
            self._cells[key] = {
                "lat": float(cell["lat"]),
                "lon": float(cell["lon"]),
                "depth_m": float(cell["depth_m"]),
                "sample_count": int(cell["sample_count"]),
                "last_sample_ns": int(cell.get("last_sample_ns", 0)),
                "source": cell.get("source", "sounder"),
            }
