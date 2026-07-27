"""AELMA bridge package: NMEA 0183 -> telemetry packets over WebSocket."""

from __future__ import annotations

from .bridge import Bridge, build_packet
from .nmea import parse_sentence, validate_checksum
from .quality import check_quality

__all__ = [
    "Bridge",
    "build_packet",
    "parse_sentence",
    "validate_checksum",
    "check_quality",
]
