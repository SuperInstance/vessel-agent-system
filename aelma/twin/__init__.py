"""AELMA twin core: digital-twin state, bathymetry TSDF, and asyncio runtime."""

from __future__ import annotations

from .a2a_log import A2ALog, DEFAULT_PRIORITY, KIND_ACTION, VALID_SOURCES
from .a2a_query import A2AQuery, KNOWN_FILTERS
from .anomaly_detector import AnomalyDetector, ChannelStats
from .bathymetry import BathymetryGrid
from .circuit_breaker import CircuitBreaker, CircuitBreakerOpen, State
from .core import TwinCore
from .llm_narrator import Narrator
from .plugins import Plugin, PluginContext, PluginManager
from .state import VesselState, bearing_deg, haversine_m
from .stratified_sampler import SampleBin, StratifiedSampler, TrainingExample
from .trip_summary import TripSummary
from .watcher_history import WatcherHistory
from .watchers import WatcherRegistry, WatcherRule

__all__ = [
    # A2A System
    "A2ALog",
    "A2AQuery",
    "AnomalyDetector",
    "ChannelStats",
    "DEFAULT_PRIORITY",
    "KIND_ACTION",
    "VALID_SOURCES",
    "KNOWN_FILTERS",
    # Core
    "BathymetryGrid",
    "CircuitBreaker",
    "CircuitBreakerOpen",
    "Narrator",
    "Plugin",
    "PluginContext",
    "PluginManager",
    "SampleBin",
    "State",
    "StratifiedSampler",
    "TrainingExample",
    "TripSummary",
    "TwinCore",
    "VesselState",
    "WatcherHistory",
    "WatcherRegistry",
    "WatcherRule",
    # Utilities
    "bearing_deg",
    "haversine_m",
]
