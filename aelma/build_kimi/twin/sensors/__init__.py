"""AELMA sensor capture package.

Provides comprehensive sensor data capture from marine sources:
- NMEA 0183 TCP listener for GPS, depth, speed, heading
- UDP listeners for depth sounders and radar
- Position format conversions (decimal, DMS, NMEA)
- JSONL persistence and TwinCore integration
"""

from .nmea_udp_capture import (
    # Position conversion functions
    dec_to_dms,
    dec_to_nmea,
    nmea_to_dec,
    dms_to_dec,

    # Data structures
    NMEA0183Record,
    UDPDepthRecord,
    UDPPacket,

    # Listeners
    NMEA0183Listener,
    UDPDepthListener,
    RadarUDPListener,
    SensorCaptureCoordinator,

    # Integration functions
    nmea_record_to_telemetry,
    depth_record_to_telemetry,
)

__all__ = [
    # Position conversion functions
    "dec_to_dms",
    "dec_to_nmea",
    "nmea_to_dec",
    "dms_to_dec",

    # Data structures
    "NMEA0183Record",
    "UDPDepthRecord",
    "UDPPacket",

    # Listeners
    "NMEA0183Listener",
    "UDPDepthListener",
    "RadarUDPListener",
    "SensorCaptureCoordinator",

    # Integration functions
    "nmea_record_to_telemetry",
    "depth_record_to_telemetry",
]
