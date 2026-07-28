"""AELMA Bridge — NMEA 0183 and Signal K to telemetry-packet bridge.

Public API:
    from bridge import nmea, quality, bridge, signalk
    from bridge.bridge import NMEABridge, SignalKBridge, build_packet
    from bridge.signalk import parse_delta, path_to_channel
"""

from __future__ import annotations

from . import nmea, quality, bridge, signalk  # noqa: F401

__version__ = "1.0.0"
__all__ = ["nmea", "quality", "bridge", "signalk"]
