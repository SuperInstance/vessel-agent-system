"""AELMA Twin Core — digital twin for the F/V EILEEN.

A Python asyncio process that connects to the AELMA bridge via WebSocket,
maintains vessel state, runs a progressive bathymetry TSDF layer, and
broadcasts VesselStateSnapshot JSON to viewer clients.
"""

from __future__ import annotations

from .state import VesselState, haversine_m, bearing_deg
from .bathymetry import BathymetryGrid, quantise_cell, cell_center
from .core import TwinCore

__all__ = [
    "VesselState",
    "BathymetryGrid",
    "TwinCore",
    "haversine_m",
    "bearing_deg",
    "quantise_cell",
    "cell_center",
]
