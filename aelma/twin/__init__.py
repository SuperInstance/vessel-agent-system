"""AELMA twin core: digital-twin state, bathymetry TSDF, and asyncio runtime."""

from __future__ import annotations

from .a2a_log import A2ALog, DEFAULT_PRIORITY, KIND_ACTION, VALID_SOURCES
from .a2a_query import A2AQuery, KNOWN_FILTERS
from .bathymetry import BathymetryGrid
from .core import TwinCore
from .llm_narrator import Narrator
from .state import VesselState, bearing_deg, haversine_m
from .watcher_history import WatcherHistory
from .watchers import WatcherRegistry, WatcherRule

__all__ = [
    # A2A System
    "A2ALog",
    "A2AQuery",
    "DEFAULT_PRIORITY",
    "KIND_ACTION",
    "VALID_SOURCES",
    "KNOWN_FILTERS",
    # Core
    "BathymetryGrid",
    "Narrator",
    "TwinCore",
    "VesselState",
    "WatcherHistory",
    "WatcherRegistry",
    "WatcherRule",
    # Utilities
    "bearing_deg",
    "haversine_m",
]
