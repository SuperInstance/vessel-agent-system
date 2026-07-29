"""NMEA 0183 and UDP sensor capture system for AELMA vessel digital twin.

This module provides comprehensive sensor data capture from marine sources:
- NMEA 0183 TCP listener for GPS, depth, speed, heading data
- UDP listener for depth sounder data
- Generic UDP packet handler for radar and future sensors
- Position format conversions (decimal, DMS, NMEA)
- JSONL persistence for all captured data

Example:
    >>> coordinator = SensorCaptureCoordinator()
    >>> coordinator.start_nmea_listener(host="0.0.0.0", port=8001)
    >>> coordinator.start_udp_depth(port=50000)
    >>> # Capture runs in background threads
    >>> coordinator.stop_all()
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import socket
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("aelma.sensors")

# --------------------------------------------------------------------- #
# Position Conversion Utilities
# --------------------------------------------------------------------- #

def dec_to_dms(lat: float, lon: float) -> tuple[str, str]:
    """Convert decimal degrees to Degrees-Minutes-Seconds (DMS) format.

    Args:
        lat: Latitude in decimal degrees (e.g., 57.053)
        lon: Longitude in decimal degrees (e.g., -135.330)

    Returns:
        Tuple of (lat_dms, lon_dms) strings formatted as:
        "57°03'11.0\"N", "135°19'48.0\"W"

    Example:
        >>> dec_to_dms(57.053, -135.330)
        ("57°03'10.8\"N", "135°19'48.0\"W")
    """
    def _dec_to_dms_component(dec: float, is_lat: bool) -> str:
        if dec < 0:
            dec = abs(dec)
            direction = 'S' if is_lat else 'W'
        else:
            direction = 'N' if is_lat else 'E'

        degrees = int(dec)
        minutes_decimal = (dec - degrees) * 60
        minutes = int(minutes_decimal)
        seconds = (minutes_decimal - minutes) * 60

        return f"{degrees}°{minutes:02d}'{seconds:05.2f}\"{direction}"

    return (_dec_to_dms_component(lat, True), _dec_to_dms_component(lon, False))


def dec_to_nmea(lat: float, lon: float) -> tuple[str, str]:
    """Convert decimal degrees to NMEA 0183 format.

    NMEA format: DDMM.MMM,N/S for latitude, DDDMM.MMM,E/W for longitude

    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees

    Returns:
        Tuple of (lat_nmea, lon_nmea) strings formatted as:
        "5703.110,N", "13519.480,W"

    Example:
        >>> dec_to_nmea(57.053, -135.330)
        ("5703.180,N", "13519.800,W")
    """
    def _dec_to_nmea_component(dec: float, is_lat: bool) -> tuple[str, str]:
        if dec < 0:
            dec = abs(dec)
            direction = 'S' if is_lat else 'W'
        else:
            direction = 'N' if is_lat else 'E'

        degrees = int(dec)
        minutes_decimal = (dec - degrees) * 60
        nmea_degrees = 2 if is_lat else 3  # Latitude uses 2 digits, longitude uses 3

        # Format: degrees (with leading zeros) + minutes (with leading zero if needed)
        # For latitude: DDMM.MMM (e.g., 5703.180)
        # For longitude: DDDMM.MMM (e.g., 13519.800)
        minutes_str = f"{minutes_decimal:06.3f}"  # Always 6 chars: XX.XXX or XXX.XXX
        nmea_str = f"{degrees:0{nmea_degrees}d}{minutes_str}"

        return (nmea_str, direction)

    lat_str, lat_dir = _dec_to_nmea_component(lat, True)
    lon_str, lon_dir = _dec_to_nmea_component(lon, False)

    return (f"{lat_str},{lat_dir}", f"{lon_str},{lon_dir}")


def nmea_to_dec(nmea_lat: str, nmea_lon: str) -> tuple[float, float]:
    """Convert NMEA 0183 format to decimal degrees.

    Args:
        nmea_lat: NMEA latitude string (e.g., "5703.110,N")
        nmea_lon: NMEA longitude string (e.g., "13519.480,W")

    Returns:
        Tuple of (lat_dec, lon_dec) as floats

    Example:
        >>> nmea_to_dec("5703.110,N", "13519.480,W")
        (57.051833, -135.3300)
    """
    def _nmea_to_dec_component(nmea: str) -> float:
        parts = nmea.split(',')
        if len(parts) != 2:
            raise ValueError(f"Invalid NMEA format: {nmea}")

        coord_str, direction = parts
        coord_str = coord_str.strip()
        direction = direction.strip().upper()

        # Determine degrees/minutes split point
        # NMEA latitude: DDMM.MMM (2 digits for degrees, always < 100 degrees)
        # NMEA longitude: DDDMM.MMM (3 digits for degrees, can be > 100 degrees)
        # We need to check if it could be longitude (3-digit degrees) or latitude (2-digit degrees)

        # Try 2-digit degrees first (latitude format)
        degrees_2 = int(coord_str[:2])
        minutes_2 = float(coord_str[2:])

        # Try 3-digit degrees (longitude format)
        if len(coord_str) >= 9:  # Could be DDDMM.MMM
            degrees_3 = int(coord_str[:3])
            minutes_3 = float(coord_str[3:])

            # Use 3-digit if minutes make sense (0-60 range)
            if 0 <= minutes_3 < 60:
                degrees, minutes = degrees_3, minutes_3
            else:
                degrees, minutes = degrees_2, minutes_2
        else:
            degrees, minutes = degrees_2, minutes_2

        dec = degrees + (minutes / 60.0)

        if direction in ('S', 'W'):
            dec = -dec

        return dec

    return (_nmea_to_dec_component(nmea_lat), _nmea_to_dec_component(nmea_lon))


def dms_to_dec(dms_lat: str, dms_lon: str) -> tuple[float, float]:
    """Convert DMS string to decimal degrees.

    Args:
        dms_lat: DMS latitude string (e.g., "57°03'11.0\"N")
        dms_lon: DMS longitude string (e.g., "135°19'48.0\"W")

    Returns:
        Tuple of (lat_dec, lon_dec) as floats

    Example:
        >>> dms_to_dec("57°03'11.0\"N", "135°19'48.0\"W")
        (57.05306, -135.3300)
    """
    def _dms_to_dec_component(dms: str) -> float:
        dms = dms.strip()

        # Extract direction
        direction = dms[-1]
        if direction not in ('N', 'S', 'E', 'W'):
            raise ValueError(f"Invalid direction in DMS: {dms}")

        # Parse degrees, minutes, seconds
        dms_body = dms[:-1]

        degrees_str = ""
        minutes_str = ""
        seconds_str = ""

        # Split by degrees symbol
        if '°' in dms_body:
            parts = dms_body.split('°')
            degrees_str = parts[0]
            remaining = parts[1] if len(parts) > 1 else ""
        else:
            remaining = dms_body

        # Split by minutes symbol
        if "'" in remaining:
            min_parts = remaining.split("'")
            minutes_str = min_parts[0]
            seconds_str = min_parts[1] if len(min_parts) > 1 else ""
        else:
            seconds_str = remaining

        degrees = float(degrees_str) if degrees_str else 0.0
        minutes = float(minutes_str) if minutes_str else 0.0
        seconds = float(seconds_str.replace('"', '')) if seconds_str else 0.0

        dec = degrees + (minutes / 60.0) + (seconds / 3600.0)

        if direction in ('S', 'W'):
            dec = -dec

        return dec

    return (_dms_to_dec_component(dms_lat), _dms_to_dec_component(dms_lon))


# --------------------------------------------------------------------- #
# Data Structures
# --------------------------------------------------------------------- #

@dataclass
class NMEA0183Record:
    """Record for a parsed NMEA 0183 sentence.

    Stores all position data in three formats:
    - Decimal degrees (57.053, -135.330)
    - DMS format (57°03'11"N, 135°19'48"W)
    - NMEA format (5703.110,N, 13519.480,W)
    """
    sentence_type: str  # GPGGA, GPGLL, GPRMC, GPZDA, DBT, DBS
    raw_sentence: str
    timestamp_ns: int

    # Position (decimal degrees)
    lat_dec: float | None = None
    lon_dec: float | None = None

    # Position (DMS format)
    lat_dms: str | None = None  # "57°03'11.0\"N"
    lon_dms: str | None = None  # "135°19'48.0\"W"

    # Position (NMEA format)
    lat_nmea: str | None = None  # "5703.110,N"
    lon_nmea: str | None = None  # "13519.480,W"

    # Other sensor data
    depth_m: float | None = None
    speed_kn: float | None = None
    heading_deg: float | None = None
    utc_time: str | None = None  # "HHMMSS"
    date: str | None = None  # "DDMMYY"
    quality: int | None = None  # GPS quality indicator (0-8)
    satellites: int | None = None
    hdop: float | None = None  # Horizontal dilution of precision

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "sentence_type": self.sentence_type,
            "raw_sentence": self.raw_sentence,
            "timestamp_ns": self.timestamp_ns,
            "lat_dec": self.lat_dec,
            "lon_dec": self.lon_dec,
            "lat_dms": self.lat_dms,
            "lon_dms": self.lon_dms,
            "lat_nmea": self.lat_nmea,
            "lon_nmea": self.lon_nmea,
            "depth_m": self.depth_m,
            "speed_kn": self.speed_kn,
            "heading_deg": self.heading_deg,
            "utc_time": self.utc_time,
            "date": self.date,
            "quality": self.quality,
            "satellites": self.satellites,
            "hdop": self.hdop,
        }


@dataclass
class UDPDepthRecord:
    """Record for a parsed depth sounder UDP packet."""
    sensor_id: str
    depth_m: float
    timestamp_ns: int
    raw_packet: bytes

    # Depth in multiple formats
    depth_ft: float = field(init=False)
    depth_fathoms: float = field(init=False)

    def __post_init__(self) -> None:
        """Calculate derived depth units."""
        self.depth_ft = self.depth_m * 3.28084
        self.depth_fathoms = self.depth_m * 0.546807

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "sensor_id": self.sensor_id,
            "depth_m": self.depth_m,
            "depth_ft": self.depth_ft,
            "depth_fathoms": self.depth_fathoms,
            "timestamp_ns": self.timestamp_ns,
            "raw_packet_hex": self.raw_packet.hex(),
        }


@dataclass
class UDPPacket:
    """Generic UDP packet record for unknown formats."""
    source: str  # "192.168.1.100:50000"
    protocol: str  # "UDP", "TCP"
    raw_bytes: bytes
    timestamp_ns: int
    parsed_as: str  # "depth_sounder", "radar", "unknown"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "source": self.source,
            "protocol": self.protocol,
            "timestamp_ns": self.timestamp_ns,
            "parsed_as": self.parsed_as,
            "raw_bytes_hex": self.raw_bytes.hex(),
            "length": len(self.raw_bytes),
        }


# --------------------------------------------------------------------- #
# NMEA 0183 TCP Listener
# --------------------------------------------------------------------- #

class NMEA0183Listener:
    """TCP listener for NMEA 0183 sentences from marine sensors.

    Connects to a TCP source (typically a GPS or multiplexer) and parses
    NMEA 0183 sentences in real-time. Stores parsed data to JSONL.

    Common sentence types supported:
    - $GPGGA: Global Positioning System Fix Data
    - $GPGLL: Geographic Position, Latitude/Longitude
    - $GPRMC: Recommended Minimum sentence C
    - $GPZDA: Time and Date
    - $DBT: Depth Below Transducer
    - $DBS: Depth Below Surface

    Example:
        >>> listener = NMEA0183Listener(host="0.0.0.0", port=8001)
        >>> listener.start()
        >>> # Runs in background thread
        >>> listener.stop()
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8001,
        jsonl_path: str | Path = "nmea_telemetry.jsonl",
    ) -> None:
        """Initialize NMEA listener.

        Args:
            host: Host to bind to (default: "0.0.0.0" for all interfaces)
            port: TCP port to listen on (default: 8001, standard NMEA port)
            jsonl_path: Path to JSONL output file
        """
        self.host = host
        self.port = port
        self.jsonl_path = Path(jsonl_path)
        self._running = False
        self._thread: threading.Thread | None = None
        self._server_socket: socket.socket | None = None
        self._lock = threading.Lock()
        self._packet_count = 0
        self._error_count = 0

    def start(self) -> None:
        """Start the NMEA listener in a background thread."""
        if self._running:
            log.warning("NMEA listener already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()
        log.info(f"NMEA listener started on {self.host}:{self.port}")

    def stop(self) -> None:
        """Stop the NMEA listener."""
        self._running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception as e:
                log.warning(f"Error closing server socket: {e}")

        if self._thread:
            self._thread.join(timeout=5.0)

        log.info(f"NMEA listener stopped. Packets: {self._packet_count}, Errors: {self._error_count}")

    def _run_server(self) -> None:
        """Run the TCP server (runs in background thread)."""
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen(5)
        self._server_socket.settimeout(1.0)  # Allow periodic stop checks

        log.info(f"NMEA TCP server listening on {self.host}:{self.port}")

        while self._running:
            try:
                client_socket, address = self._server_socket.accept()
                log.info(f"NMEA client connected from {address}")
                self._handle_client(client_socket, address)
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    log.error(f"NMEA server error: {e}")
                    self._error_count += 1

    def _handle_client(self, client_socket: socket.socket, address: tuple) -> None:
        """Handle a connected NMEA client.

        Args:
            client_socket: Connected socket
            address: Client address (host, port)
        """
        buffer = ""

        try:
            while self._running:
                data = client_socket.recv(1024)
                if not data:
                    break

                buffer += data.decode('ascii', errors='replace')

                # Process complete sentences
                while '\r\n' in buffer:
                    line, buffer = buffer.split('\r\n', 1)
                    line = line.strip()

                    if line:
                        record = self._parse_sentence(line)
                        if record:
                            self._write_record(record)
                            self._packet_count += 1

        except Exception as e:
            log.warning(f"Error handling NMEA client {address}: {e}")
            self._error_count += 1
        finally:
            client_socket.close()
            log.info(f"NMEA client {address} disconnected")

    def _parse_sentence(self, sentence: str) -> NMEA0183Record | None:
        """Parse a single NMEA 0183 sentence.

        Args:
            sentence: Raw NMEA sentence (e.g., "$GPGGA,...")

        Returns:
            NMEA0183Record if parsed successfully, None otherwise
        """
        if not sentence.startswith('$'):
            return None

        try:
            # Extract sentence type and checksum
            if '*' in sentence:
                data_part, checksum_part = sentence[1:].split('*', 1)
            else:
                data_part = sentence[1:]
                checksum_part = ""

            fields = data_part.split(',')
            sentence_type = fields[0]

            timestamp_ns = time.time_ns()

            # Parse based on sentence type
            if sentence_type == "GPGGA":
                return self._parse_gpgga(fields, sentence, timestamp_ns)
            elif sentence_type == "GPGLL":
                return self._parse_gpgll(fields, sentence, timestamp_ns)
            elif sentence_type == "GPRMC":
                return self._parse_gprmc(fields, sentence, timestamp_ns)
            elif sentence_type == "GPZDA":
                return self._parse_gpzda(fields, sentence, timestamp_ns)
            elif sentence_type in ("DBT", "DBS"):
                return self._parse_depth_sentence(fields, sentence, sentence_type, timestamp_ns)
            else:
                # Unknown sentence type, log and continue
                log.debug(f"Unknown NMEA sentence type: {sentence_type}")
                return None

        except Exception as e:
            log.warning(f"Error parsing NMEA sentence: {e}")
            self._error_count += 1
            return None

    def _parse_gpgga(self, fields: list[str], raw: str, timestamp_ns: int) -> NMEA0183Record:
        """Parse GPGGA (Global Positioning System Fix Data) sentence.

        Format: $GPGGA,HHMMSS,llll.ll,a,yyyyy.yy,a,x,xx,x.x,x.x,M,x.x,M,x.x,xxxx*hh

        Fields:
        0: GPGGA
        1: UTC time (HHMMSS)
        2: Latitude (DDMM.MMMM)
        3: N/S indicator
        4: Longitude (DDDMM.MMMM)
        5: E/W indicator
        6: Quality indicator (0=no fix, 1=GPS, 2=DGPS, etc.)
        7: Number of satellites
        8: Horizontal dilution of precision (HDOP)
        9: Altitude above MSL (meters)
        10: Units of altitude (M)
        11: Geoid separation (meters)
        12: Units of geoid separation (M)
        13: Age of differential GPS data
        14: Differential reference station ID
        """
        record = NMEA0183Record(
            sentence_type="GPGGA",
            raw_sentence=raw,
            timestamp_ns=timestamp_ns,
            utc_time=fields[1] if len(fields) > 1 else None,
            quality=int(fields[6]) if len(fields) > 6 and fields[6] else None,
            satellites=int(fields[7]) if len(fields) > 7 and fields[7] else None,
            hdop=float(fields[8]) if len(fields) > 8 and fields[8] else None,
        )

        if len(fields) > 4:
            nmea_lat = f"{fields[2]},{fields[3]}"
            nmea_lon = f"{fields[4]},{fields[5]}"

            if fields[2] and fields[4]:
                record.lat_nmea = nmea_lat
                record.lon_nmea = nmea_lon
                record.lat_dec, record.lon_dec = nmea_to_dec(nmea_lat, nmea_lon)
                record.lat_dms, record.lon_dms = dec_to_dms(record.lat_dec, record.lon_dec)

        return record

    def _parse_gpgll(self, fields: list[str], raw: str, timestamp_ns: int) -> NMEA0183Record:
        """Parse GPGLL (Geographic Position) sentence.

        Format: $GPGLL,llll.ll,a,yyyyy.yy,a,HHMMSS.ss,A*hh

        Fields:
        0: GPGLL
        1: Latitude (DDMM.MMMM)
        2: N/S indicator
        3: Longitude (DDDMM.MMMM)
        4: E/W indicator
        5: UTC time
        6: Status (A=active, V=void)
        """
        record = NMEA0183Record(
            sentence_type="GPGLL",
            raw_sentence=raw,
            timestamp_ns=timestamp_ns,
            utc_time=fields[5] if len(fields) > 5 else None,
        )

        if len(fields) > 4:
            nmea_lat = f"{fields[1]},{fields[2]}"
            nmea_lon = f"{fields[3]},{fields[4]}"

            if fields[1] and fields[3]:
                record.lat_nmea = nmea_lat
                record.lon_nmea = nmea_lon
                record.lat_dec, record.lon_dec = nmea_to_dec(nmea_lat, nmea_lon)
                record.lat_dms, record.lon_dms = dec_to_dms(record.lat_dec, record.lon_dec)

        return record

    def _parse_gprmc(self, fields: list[str], raw: str, timestamp_ns: int) -> NMEA0183Record:
        """Parse GPRMC (Recommended Minimum) sentence.

        Format: $GPRMC,HHMMSS.ss,A,llll.ll,a,yyyyy.yy,a,x.x,x.x,DDMMYY,x.x,a*hh

        Fields:
        0: GPRMC
        1: UTC time
        2: Status (A=active, V=void)
        3: Latitude (DDMM.MMMM)
        4: N/S indicator
        5: Longitude (DDDMM.MMMM)
        6: E/W indicator
        7: Speed over ground (knots)
        8: Track made good (degrees)
        9: Date (DDMMYY)
        10: Magnetic variation
        11: E/W indicator for variation
        """
        record = NMEA0183Record(
            sentence_type="GPRMC",
            raw_sentence=raw,
            timestamp_ns=timestamp_ns,
            utc_time=fields[1] if len(fields) > 1 else None,
            speed_kn=float(fields[7]) if len(fields) > 7 and fields[7] else None,
            heading_deg=float(fields[8]) if len(fields) > 8 and fields[8] else None,
            date=fields[9] if len(fields) > 9 else None,
        )

        if len(fields) > 6:
            nmea_lat = f"{fields[3]},{fields[4]}"
            nmea_lon = f"{fields[5]},{fields[6]}"

            if fields[3] and fields[5]:
                record.lat_nmea = nmea_lat
                record.lon_nmea = nmea_lon
                record.lat_dec, record.lon_dec = nmea_to_dec(nmea_lat, nmea_lon)
                record.lat_dms, record.lon_dms = dec_to_dms(record.lat_dec, record.lon_dec)

        return record

    def _parse_gpzda(self, fields: list[str], raw: str, timestamp_ns: int) -> NMEA0183Record:
        """Parse GPZDA (Time and Date) sentence.

        Format: $GPZDA,HHMMSS.ss,DD,MM,YYYY,TH,TH*hh

        Fields:
        0: GPZDA
        1: UTC time
        2: Day
        3: Month
        4: Year
        5: Local time zone hours
        6: Local time zone minutes
        """
        return NMEA0183Record(
            sentence_type="GPZDA",
            raw_sentence=raw,
            timestamp_ns=timestamp_ns,
            utc_time=fields[1] if len(fields) > 1 else None,
            date=f"{fields[4]}{fields[3]}{fields[2]}" if len(fields) > 4 else None,  # YYYYMMDD
        )

    def _parse_depth_sentence(
        self, fields: list[str], raw: str, sentence_type: str, timestamp_ns: int
    ) -> NMEA0183Record:
        """Parse depth sentences (DBT, DBS).

        DBT Format: $--DBT,x,f,x,M,x,F*hh
        - Depth below transducer in feet, meters, fathoms

        DBS Format: $--DBS,x,f,x,M,x,F*hh
        - Depth below surface in feet, meters, fathoms

        Field order: [sentence_type, depth_feet, f, depth_meters, M, depth_fathoms, F, checksum]
        """
        # Parse depth from meters field (field index 3 in standard format)
        depth_m = None

        # Try to find meters field (index 3: value after 'M')
        if len(fields) > 4:
            # Format: $DBT,12.5,f,3.8,M,2.1,F*hh
            # Index 0: DBT, 1: 12.5, 2: f, 3: 3.8, 4: M, 5: 2.1, 6: F
            if fields[3] and fields[3].replace('.', '').isdigit():
                depth_m = float(fields[3])

        # Fallback: look for any numeric field in reasonable range
        if depth_m is None:
            for i, field in enumerate(fields):
                if i > 0 and field and field.replace('.', '').replace('-', '').isdigit():
                    depth_val = float(field)
                    # Assume meters if less than 100 (marine depths)
                    if 0 < depth_val < 100:
                        depth_m = depth_val
                        break

        return NMEA0183Record(
            sentence_type=sentence_type,
            raw_sentence=raw,
            timestamp_ns=timestamp_ns,
            depth_m=depth_m,
        )

    def _write_record(self, record: NMEA0183Record) -> None:
        """Write a parsed record to JSONL file.

        Args:
            record: NMEA0183Record to write
        """
        try:
            with self._lock:
                with open(self.jsonl_path, 'a') as f:
                    f.write(json.dumps(record.to_dict()) + '\n')
        except Exception as e:
            log.error(f"Error writing NMEA record: {e}")
            self._error_count += 1

    def get_status(self) -> dict[str, Any]:
        """Get listener status."""
        return {
            "type": "NMEA0183",
            "host": self.host,
            "port": self.port,
            "running": self._running,
            "packet_count": self._packet_count,
            "error_count": self._error_count,
            "jsonl_path": str(self.jsonl_path),
        }


# --------------------------------------------------------------------- #
# UDP Depth Sounder Listener
# --------------------------------------------------------------------- #

class UDPDepthListener:
    """UDP listener for depth sounder data.

    Binds to a UDP port and receives depth data packets from marine depth
    sounders. Parses the data and stores to JSONL.

    Example:
        >>> listener = UDPDepthListener(port=50000)
        >>> listener.start()
        >>> # Runs in background thread
        >>> listener.stop()
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 50000,
        jsonl_path: str | Path = "depth_sounder.jsonl",
        sensor_id: str = "depth_sounder_1",
    ) -> None:
        """Initialize UDP depth listener.

        Args:
            host: Host to bind to
            port: UDP port to listen on
            jsonl_path: Path to JSONL output file
            sensor_id: Sensor identifier for records
        """
        self.host = host
        self.port = port
        self.jsonl_path = Path(jsonl_path)
        self.sensor_id = sensor_id
        self._running = False
        self._thread: threading.Thread | None = None
        self._socket: socket.socket | None = None
        self._lock = threading.Lock()
        self._packet_count = 0
        self._error_count = 0

    def start(self) -> None:
        """Start the UDP depth listener in a background thread."""
        if self._running:
            log.warning("UDP depth listener already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_listener, daemon=True)
        self._thread.start()
        log.info(f"UDP depth listener started on {self.host}:{self.port}")

    def stop(self) -> None:
        """Stop the UDP depth listener."""
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except Exception as e:
                log.warning(f"Error closing UDP socket: {e}")

        if self._thread:
            self._thread.join(timeout=5.0)

        log.info(f"UDP depth listener stopped. Packets: {self._packet_count}, Errors: {self._error_count}")

    def _run_listener(self) -> None:
        """Run the UDP listener (runs in background thread)."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self.host, self.port))
        self._socket.settimeout(1.0)  # Allow periodic stop checks

        log.info(f"UDP depth listener bound to {self.host}:{self.port}")

        while self._running:
            try:
                data, address = self._socket.recvfrom(1024)
                record = self._parse_depth_packet(data, address)
                if record:
                    self._write_record(record)
                    self._packet_count += 1

            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    log.error(f"UDP depth listener error: {e}")
                    self._error_count += 1

    def _parse_depth_packet(self, data: bytes, address: tuple) -> UDPDepthRecord | None:
        """Parse depth sounder UDP packet.

        Args:
            data: Raw packet bytes
            address: Source address (host, port)

        Returns:
            UDPDepthRecord if parsed successfully, None otherwise
        """
        if not data:
            return None

        try:
            # Try to parse as ASCII string (common format)
            try:
                message = data.decode('ascii').strip()

                if not message:
                    return None

                # Try various depth formats
                # Format 1: "DEPTH=12.3"
                if message.startswith('DEPTH='):
                    depth_m = float(message.split('=')[1].strip())
                    if 0 < depth_m < 500:
                        return UDPDepthRecord(
                            sensor_id=self.sensor_id,
                            depth_m=depth_m,
                            timestamp_ns=time.time_ns(),
                            raw_packet=data,
                        )

                # Format 2: "12.3m"
                elif message.endswith('m'):
                    depth_m = float(message[:-1].strip())
                    if 0 < depth_m < 500:
                        return UDPDepthRecord(
                            sensor_id=self.sensor_id,
                            depth_m=depth_m,
                            timestamp_ns=time.time_ns(),
                            raw_packet=data,
                        )

                # Format 3: Plain number
                else:
                    depth_m = float(message)
                    if 0 < depth_m < 500:  # Reasonable marine depth
                        return UDPDepthRecord(
                            sensor_id=self.sensor_id,
                            depth_m=depth_m,
                            timestamp_ns=time.time_ns(),
                            raw_packet=data,
                        )

            except (UnicodeDecodeError, ValueError):
                pass

            # Try binary format (4-byte float) only for pure binary packets
            # Don't try to parse ASCII-looking data as binary
            if len(data) == 4:  # Only exact 4-byte packets
                try:
                    import struct
                    depth_m = struct.unpack('f', data)[0]
                    # Validate the binary float result is reasonable and non-zero
                    if 0.5 < depth_m < 200:  # Reasonable marine depth range
                        return UDPDepthRecord(
                            sensor_id=self.sensor_id,
                            depth_m=depth_m,
                            timestamp_ns=time.time_ns(),
                            raw_packet=data,
                        )
                except struct.error:
                    pass

            # Unable to parse
            log.debug(f"Unable to parse depth packet: {data[:20]}")
            return None

        except Exception as e:
            log.warning(f"Error parsing depth packet: {e}")
            self._error_count += 1
            return None

    def _write_record(self, record: UDPDepthRecord) -> None:
        """Write a parsed record to JSONL file."""
        try:
            with self._lock:
                with open(self.jsonl_path, 'a') as f:
                    f.write(json.dumps(record.to_dict()) + '\n')
        except Exception as e:
            log.error(f"Error writing depth record: {e}")
            self._error_count += 1

    def get_status(self) -> dict[str, Any]:
        """Get listener status."""
        return {
            "type": "UDP_DEPTH",
            "host": self.host,
            "port": self.port,
            "sensor_id": self.sensor_id,
            "running": self._running,
            "packet_count": self._packet_count,
            "error_count": self._error_count,
            "jsonl_path": str(self.jsonl_path),
        }


# --------------------------------------------------------------------- #
# Generic UDP Listener (Radar/Future)
# --------------------------------------------------------------------- #

class RadarUDPListener:
    """UDP listener for radar data (future expansion).

    Generic UDP packet handler for unknown or radar formats.
    Stores raw packets with source tracking for later analysis.

    Example:
        >>> listener = RadarUDPListener(port=50001)
        >>> listener.start()
        >>> # Runs in background thread
        >>> listener.stop()
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 50001,
        jsonl_path: str | Path = "radar.jsonl",
    ) -> None:
        """Initialize radar UDP listener.

        Args:
            host: Host to bind to
            port: UDP port to listen on
            jsonl_path: Path to JSONL output file
        """
        self.host = host
        self.port = port
        self.jsonl_path = Path(jsonl_path)
        self._running = False
        self._thread: threading.Thread | None = None
        self._socket: socket.socket | None = None
        self._lock = threading.Lock()
        self._packet_count = 0

    def start(self) -> None:
        """Start the radar UDP listener in a background thread."""
        if self._running:
            log.warning("Radar UDP listener already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_listener, daemon=True)
        self._thread.start()
        log.info(f"Radar UDP listener started on {self.host}:{self.port}")

    def stop(self) -> None:
        """Stop the radar UDP listener."""
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except Exception as e:
                log.warning(f"Error closing UDP socket: {e}")

        if self._thread:
            self._thread.join(timeout=5.0)

        log.info(f"Radar UDP listener stopped. Packets: {self._packet_count}")

    def _run_listener(self) -> None:
        """Run the UDP listener (runs in background thread)."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self.host, self.port))
        self._socket.settimeout(1.0)  # Allow periodic stop checks

        log.info(f"Radar UDP listener bound to {self.host}:{self.port}")

        while self._running:
            try:
                data, address = self._socket.recvfrom(4096)  # Larger buffer for radar
                packet = UDPPacket(
                    source=f"{address[0]}:{address[1]}",
                    protocol="UDP",
                    raw_bytes=data,
                    timestamp_ns=time.time_ns(),
                    parsed_as="radar",
                )
                self._write_packet(packet)
                self._packet_count += 1

            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    log.error(f"Radar UDP listener error: {e}")

    def _write_packet(self, packet: UDPPacket) -> None:
        """Write a packet record to JSONL file."""
        try:
            with self._lock:
                with open(self.jsonl_path, 'a') as f:
                    f.write(json.dumps(packet.to_dict()) + '\n')
        except Exception as e:
            log.error(f"Error writing radar packet: {e}")

    def get_status(self) -> dict[str, Any]:
        """Get listener status."""
        return {
            "type": "RADAR_UDP",
            "host": self.host,
            "port": self.port,
            "running": self._running,
            "packet_count": self._packet_count,
            "jsonl_path": str(self.jsonl_path),
        }


# --------------------------------------------------------------------- #
# Sensor Capture Coordinator
# --------------------------------------------------------------------- #

class SensorCaptureCoordinator:
    """Coordinate all sensor capture operations.

    Manages NMEA TCP listener, UDP depth listener, and radar UDP listener.
    Provides unified start/stop interface and status reporting.

    Example:
        >>> coordinator = SensorCaptureCoordinator()
        >>> coordinator.start_nmea_listener(port=8001)
        >>> coordinator.start_udp_depth(port=50000)
        >>> coordinator.start_radar(port=50001)
        >>> status = coordinator.get_status()
        >>> coordinator.stop_all()
    """

    def __init__(
        self,
        nmea_jsonl: str | Path = "nmea_telemetry.jsonl",
        depth_jsonl: str | Path = "depth_sounder.jsonl",
        radar_jsonl: str | Path = "radar.jsonl",
        log_path: str | Path = "sensor_capture.log",
    ) -> None:
        """Initialize sensor capture coordinator.

        Args:
            nmea_jsonl: Path for NMEA telemetry JSONL
            depth_jsonl: Path for depth sounder JSONL
            radar_jsonl: Path for radar JSONL
            log_path: Path for system log
        """
        self.nmea_jsonl = Path(nmea_jsonl)
        self.depth_jsonl = Path(depth_jsonl)
        self.radar_jsonl = Path(radar_jsonl)
        self.log_path = Path(log_path)

        self.nmea_listener: NMEA0183Listener | None = None
        self.depth_listener: UDPDepthListener | None = None
        self.radar_listener: RadarUDPListener | None = None

        # Create parent directories for log and JSONL files
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.nmea_jsonl.parent.mkdir(parents=True, exist_ok=True)
        self.depth_jsonl.parent.mkdir(parents=True, exist_ok=True)
        self.radar_jsonl.parent.mkdir(parents=True, exist_ok=True)

        self._setup_logging()

    def _setup_logging(self) -> None:
        """Configure logging for sensor capture."""
        handler = logging.FileHandler(self.log_path, mode='a')
        handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        # Only add handler if not already present
        if not any(isinstance(h, logging.FileHandler) and h.baseFilename == str(self.log_path) for h in log.handlers):
            log.addHandler(handler)

    def start_nmea_listener(self, host: str = "0.0.0.0", port: int = 8001) -> None:
        """Start NMEA 0183 TCP listener.

        Args:
            host: Host to bind to (default: "0.0.0.0")
            port: TCP port (default: 8001)
        """
        if self.nmea_listener and self.nmea_listener._running:
            log.warning("NMEA listener already running")
            return

        self.nmea_listener = NMEA0183Listener(
            host=host,
            port=port,
            jsonl_path=self.nmea_jsonl,
        )
        self.nmea_listener.start()

    def start_udp_depth(
        self,
        host: str = "0.0.0.0",
        port: int = 50000,
        sensor_id: str = "depth_sounder_1",
    ) -> None:
        """Start UDP depth sounder listener.

        Args:
            host: Host to bind to
            port: UDP port (default: 50000)
            sensor_id: Sensor identifier
        """
        if self.depth_listener and self.depth_listener._running:
            log.warning("UDP depth listener already running")
            return

        self.depth_listener = UDPDepthListener(
            host=host,
            port=port,
            jsonl_path=self.depth_jsonl,
            sensor_id=sensor_id,
        )
        self.depth_listener.start()

    def start_radar(self, host: str = "0.0.0.0", port: int = 50001) -> None:
        """Start radar UDP listener.

        Args:
            host: Host to bind to
            port: UDP port (default: 50001)
        """
        if self.radar_listener and self.radar_listener._running:
            log.warning("Radar listener already running")
            return

        self.radar_listener = RadarUDPListener(
            host=host,
            port=port,
            jsonl_path=self.radar_jsonl,
        )
        self.radar_listener.start()

    def stop_all(self) -> None:
        """Stop all active listeners."""
        if self.nmea_listener:
            self.nmea_listener.stop()
        if self.depth_listener:
            self.depth_listener.stop()
        if self.radar_listener:
            self.radar_listener.stop()

        log.info("All sensor capture listeners stopped")

    def get_status(self) -> dict[str, Any]:
        """Get status of all listeners.

        Returns:
            Dictionary with status of all listeners
        """
        return {
            "nmea": self.nmea_listener.get_status() if self.nmea_listener else None,
            "depth": self.depth_listener.get_status() if self.depth_listener else None,
            "radar": self.radar_listener.get_status() if self.radar_listener else None,
            "timestamp_ns": time.time_ns(),
        }

    def start_all(self) -> None:
        """Start all sensor capture listeners with default ports."""
        self.start_nmea_listener()
        self.start_udp_depth()
        self.start_radar()
        log.info("All sensor capture listeners started")


# --------------------------------------------------------------------- #
# Integration with TwinCore
# --------------------------------------------------------------------- #

def nmea_record_to_telemetry(record: NMEA0183Record, vessel_id: str = "aelma") -> dict[str, Any]:
    """Convert an NMEA0183Record to TelemetryPacket format for TwinCore.

    Args:
        record: NMEA0183Record from listener
        vessel_id: Vessel identifier

    Returns:
        TelemetryPacket dictionary
    """
    packets = []

    # Position packets
    if record.lat_dec is not None:
        packets.append({
            "channel": "position.lat",
            "value": record.lat_dec,
            "timestamp_ns": record.timestamp_ns,
            "vessel_id": vessel_id,
            "source": f"nmea.{record.sentence_type}",
        })

    if record.lon_dec is not None:
        packets.append({
            "channel": "position.lon",
            "value": record.lon_dec,
            "timestamp_ns": record.timestamp_ns,
            "vessel_id": vessel_id,
            "source": f"nmea.{record.sentence_type}",
        })

    # Depth packet
    if record.depth_m is not None:
        packets.append({
            "channel": "depth.m",
            "value": record.depth_m,
            "timestamp_ns": record.timestamp_ns,
            "vessel_id": vessel_id,
            "source": f"nmea.{record.sentence_type}",
        })

    # Speed packet
    if record.speed_kn is not None:
        packets.append({
            "channel": "speed.kn",
            "value": record.speed_kn,
            "timestamp_ns": record.timestamp_ns,
            "vessel_id": vessel_id,
            "source": f"nmea.{record.sentence_type}",
        })

    # Heading packet
    if record.heading_deg is not None:
        packets.append({
            "channel": "heading.deg",
            "value": record.heading_deg,
            "timestamp_ns": record.timestamp_ns,
            "vessel_id": vessel_id,
            "source": f"nmea.{record.sentence_type}",
        })

    # GPS quality
    if record.quality is not None:
        packets.append({
            "channel": "gps.quality",
            "value": record.quality,
            "timestamp_ns": record.timestamp_ns,
            "vessel_id": vessel_id,
            "source": f"nmea.{record.sentence_type}",
        })

    # Satellite count
    if record.satellites is not None:
        packets.append({
            "channel": "gps.satellites",
            "value": record.satellites,
            "timestamp_ns": record.timestamp_ns,
            "vessel_id": vessel_id,
            "source": f"nmea.{record.sentence_type}",
        })

    return packets


def depth_record_to_telemetry(record: UDPDepthRecord, vessel_id: str = "aelma") -> dict[str, Any]:
    """Convert a UDPDepthRecord to TelemetryPacket format for TwinCore.

    Args:
        record: UDPDepthRecord from listener
        vessel_id: Vessel identifier

    Returns:
        TelemetryPacket dictionary
    """
    return {
        "channel": "depth.m",
        "value": record.depth_m,
        "timestamp_ns": record.timestamp_ns,
        "vessel_id": vessel_id,
        "source": record.sensor_id,
    }


# --------------------------------------------------------------------- #
# Main Entry Point
# --------------------------------------------------------------------- #

def main() -> None:
    """Main entry point for sensor capture system."""
    import argparse

    parser = argparse.ArgumentParser(description="AELMA Sensor Capture System")
    parser.add_argument("--nmea-port", type=int, default=8001, help="NMEA TCP port")
    parser.add_argument("--depth-port", type=int, default=50000, help="Depth UDP port")
    parser.add_argument("--radar-port", type=int, default=50001, help="Radar UDP port")
    parser.add_argument("--nmea-only", action="store_true", help="Only start NMEA listener")
    parser.add_argument("--depth-only", action="store_true", help="Only start depth listener")
    parser.add_argument("--radar-only", action="store_true", help="Only start radar listener")

    args = parser.parse_args()

    coordinator = SensorCaptureCoordinator()

    if args.nmea_only:
        coordinator.start_nmea_listener(port=args.nmea_port)
    elif args.depth_only:
        coordinator.start_udp_depth(port=args.depth_port)
    elif args.radar_only:
        coordinator.start_radar(port=args.radar_port)
    else:
        coordinator.start_all()

    try:
        # Run until interrupted
        while True:
            time.sleep(1)
            status = coordinator.get_status()
            print(f"\rPackets: NMEA={status['nmea']['packet_count'] if status['nmea'] else 0}, "
                  f"Depth={status['depth']['packet_count'] if status['depth'] else 0}, "
                  f"Radar={status['radar']['packet_count'] if status['radar'] else 0}", end='')
    except KeyboardInterrupt:
        print("\nShutting down...")
        coordinator.stop_all()


if __name__ == "__main__":
    main()
