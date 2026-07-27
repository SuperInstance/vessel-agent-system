"""AELMA Bridge — NMEA 0183 to telemetry-packet bridge.

Public API:
    from bridge import nmea, quality, bridge
    from bridge.bridge import NMEABridge, build_packet
"""

from __future__ import annotations

from . import nmea, quality, bridge  # noqa: F401

__version__ = "1.0.0"
__all__ = ["nmea", "quality", "bridge"]
