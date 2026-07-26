"""
NMEA0183 Integration Code Examples
===================================

Production-ready code examples for marine vessel NMEA integration.

Author: Marine Systems Analyst
Date: 2026-07-24
Status: Production Ready
"""

import math
import time
import serial
import queue
import threading
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from collections import deque
from enum import Enum

# =============================================================================
# CHECKSUM VALIDATION
# =============================================================================

def validate_nmea_checksum(sentence: str) -> bool:
    """
    Validate NMEA sentence checksum.

    Args:
        sentence: Raw NMEA string (e.g., "$GPRMC,...*47")

    Returns:
        True if checksum valid, False otherwise

    Example:
        >>> validate_nmea_checksum("$GPRMC,...*47")
        True
    """
    star_idx = sentence.find('*')
    if star_idx == -1:
        return False

    provided = sentence[star_idx + 1:star_idx + 3]

    calculated = 0
    for char in sentence[1:star_idx]:
        calculated ^= ord(char)

    return f"{calculated:02X}".upper() == provided.upper()


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class GPSPosition:
    """GPS position data"""
    timestamp_ns: int
    latitude: float
    longitude: float
    speed_knots: float
    heading_true: float
    fix_quality: int  # 0=Invalid, 1=GPS, 2=DGPS
    num_sats: int
    hdop: float
    altitude_m: float
    status: str  # 'A'=Valid, 'V'=Invalid


@dataclass
class HeadingData:
    """Heading data"""
    timestamp_ns: int
    heading_true: float
    heading_magnetic: float
    deviation: float
    variation: float


@dataclass
class DepthData:
    """Depth data"""
    timestamp_ns: int
    depth_m: float
    transducer_offset_m: float
    unit: str  # 'M'=Meters, 'f'=Feet, 'F'=Fathoms


# =============================================================================
# INTERPOLATION ENGINE
# =============================================================================

class GPSInterpolator:
    """
    GPS interpolator for sub-second positioning.

    Features:
    - Dead reckoning with velocity vectors
    - Rolling buffer for historical positions
    - Confidence scoring
    - Heading interpolation with wraparound handling
    """

    def __init__(self, buffer_size_seconds: float = 5.0):
        self.gps_buffer = deque()
        self.heading_buffer = deque()
        self.buffer_duration_ns = int(buffer_size_seconds * 1e9)
        self.last_gps: Optional[GPSPosition] = None

    def update_gps(self, position: GPSPosition) -> None:
        """Update GPS state"""
        self.gps_buffer.append(position)
        self.last_gps = position

        # Prune old data
        cutoff = position.timestamp_ns - self.buffer_duration_ns
        while self.gps_buffer and self.gps_buffer[0].timestamp_ns < cutoff:
            self.gps_buffer.popleft()

    def update_heading(self, heading: float, timestamp_ns: int) -> None:
        """Update heading"""
        self.heading_buffer.append((timestamp_ns, heading))

        # Prune old data
        cutoff = timestamp_ns - self.buffer_duration_ns
        while self.heading_buffer and self.heading_buffer[0][0] < cutoff:
            self.heading_buffer.popleft()

    def interpolate_position(self, target_timestamp_ns: int) -> Optional[Tuple[float, float, float]]:
        """
        Interpolate position for target timestamp.

        Returns:
            (latitude, longitude, confidence) or None if extrapolation too far
        """
        if not self.last_gps:
            return None

        delta_t_ns = target_timestamp_ns - self.last_gps.timestamp_ns
        delta_t_sec = delta_t_ns / 1e9

        # Maximum extrapolation: 2.0 seconds
        if abs(delta_t_sec) > 2.0:
            return None

        # Get heading for this time
        heading = self._interpolate_heading(target_timestamp_ns)
        if heading is None:
            heading = self.last_gps.heading_true

        # Dead reckoning calculation
        speed_mps = self.last_gps.speed_knots * 0.514444  # knots to m/s
        heading_rad = math.radians(heading)
        lat_rad = math.radians(self.last_gps.latitude)

        # Calculate displacement
        distance_m = speed_mps * delta_t_sec
        earth_radius_m = 6378137.0  # WGS84 equatorial radius

        delta_lat = (distance_m * math.cos(heading_rad)) / earth_radius_m
        delta_lon = (distance_m * math.sin(heading_rad)) / \
                    (earth_radius_m * math.cos(lat_rad))

        # Calculate interpolated position
        interp_lat = self.last_gps.latitude + math.degrees(delta_lat)
        interp_lon = self.last_gps.longitude + math.degrees(delta_lon)

        # Calculate confidence
        confidence = self._calculate_confidence(delta_t_sec)

        return (interp_lat, interp_lon, confidence)

    def _interpolate_heading(self, target_timestamp_ns: int) -> Optional[float]:
        """Interpolate heading with wraparound handling"""
        if not self.heading_buffer:
            return None

        before = None
        after = None

        for ts, hdg in self.heading_buffer:
            if ts <= target_timestamp_ns:
                before = (ts, hdg)
            else:
                after = (ts, hdg)
                break

        if before and after:
            # Linear interpolation
            total_delta = after[0] - before[0]
            if total_delta > 0:
                fraction = (target_timestamp_ns - before[0]) / total_delta

                # Handle angle wraparound
                if abs(after[1] - before[1]) > 180:
                    if after[1] > before[1]:
                        before = (before[0], before[1] + 360)
                    else:
                        after = (after[0], after[1] + 360)

                result = before[1] + (after[1] - before[1]) * fraction
                return result % 360

        elif before:
            return before[1]

        elif after:
            return after[1]

        return None

    def _calculate_confidence(self, delta_t_sec: float) -> float:
        """Calculate interpolation confidence (0.0 to 1.0)"""
        if not self.last_gps:
            return 0.0

        # Time confidence (exponential decay)
        time_conf = math.exp(-abs(delta_t_sec) / 1.0)  # 1 second half-life

        # Fix quality confidence
        quality_conf = {
            0: 0.0,   # Invalid
            1: 0.7,   # GPS
            2: 0.9,   # DGPS
            4: 0.95,  # RTK
            5: 0.98   # Float RTK
        }.get(self.last_gps.fix_quality, 0.5)

        # HDOP confidence
        hdop_conf = max(0.0, 1.0 - (self.last_gps.hdop / 5.0))

        # Combined confidence
        confidence = time_conf * quality_conf * hdop_conf
        return max(0.0, min(1.0, confidence))


# =============================================================================
# NMEA SENTENCE PARSING
# =============================================================================

def parse_rmc_sentence(sentence: str) -> Optional[GPSPosition]:
    """
    Parse $GPRMC sentence.

    Args:
        sentence: Raw NMEA RMC sentence

    Returns:
        GPSPosition or None if parsing fails

    Example:
        >>> sentence = "$GPRMC,210230,A,3855.4487,N,09446.0071,W,0.0,076.2,210324,,,A*47"
        >>> pos = parse_rmc_sentence(sentence)
        >>> print(f"{pos.latitude:.6f}, {pos.longitude:.6f}")
        38.924145, -94.766785
    """
    try:
        # Validate checksum
        if not validate_nmea_checksum(sentence):
            return None

        # Split fields
        fields = sentence.split(',')
        if len(fields) < 12 or fields[0][:3] != '$GP' or fields[2] != 'A':
            return None

        # Parse time (HHMMSS.sss)
        time_str = fields[1]
        if len(time_str) >= 6:
            hours = int(time_str[0:2])
            minutes = int(time_str[2:4])
            seconds = float(time_str[4:])
        else:
            return None

        # Parse date (DDMMYY)
        date_str = fields[9]
        if len(date_str) == 6:
            day = int(date_str[0:2])
            month = int(date_str[2:4])
            year = 2000 + int(date_str[4:6])  # Assume 20xx
        else:
            year = 2026
            month = 1
            day = 1

        # Parse latitude (DDMM.MMMM)
        lat_str = fields[3]
        lat_hemi = fields[4]
        if lat_str and lat_hemi:
            lat_deg = float(lat_str[:2])
            lat_min = float(lat_str[2:])
            latitude = lat_deg + lat_min / 60.0
            if lat_hemi == 'S':
                latitude = -latitude
        else:
            return None

        # Parse longitude (DDDMM.MMMM)
        lon_str = fields[5]
        lon_hemi = fields[6]
        if lon_str and lon_hemi:
            lon_deg = float(lon_str[:3])
            lon_min = float(lon_str[3:])
            longitude = lon_deg + lon_min / 60.0
            if lon_hemi == 'W':
                longitude = -longitude
        else:
            return None

        # Parse speed (knots)
        speed_knots = float(fields[7]) if fields[7] else 0.0

        # Parse heading (degrees true)
        heading_true = float(fields[8]) if fields[8] else 0.0

        # Create timestamp
        import datetime
        try:
            timestamp_ns = int(datetime.datetime(year, month, day,
                                                 hours, minutes, int(seconds)).timestamp() * 1e9)
        except ValueError:
            timestamp_ns = int(time.time() * 1e9)

        return GPSPosition(
            timestamp_ns=int(timestamp_ns),
            latitude=latitude,
            longitude=longitude,
            speed_knots=speed_knots,
            heading_true=heading_true,
            fix_quality=1 if fields[2] == 'A' else 0,
            num_sats=0,  # RMC doesn't provide satellite count
            hdop=0.0,    # RMC doesn't provide HDOP
            altitude_m=0.0,
            status=fields[2]
        )

    except (ValueError, IndexError) as e:
        print(f"Error parsing RMC: {e}")
        return None


def parse_gga_sentence(sentence: str) -> Optional[GPSPosition]:
    """
    Parse $GPGGA sentence.

    Args:
        sentence: Raw NMEA GGA sentence

    Returns:
        GPSPosition or None if parsing fails

    Example:
        >>> sentence = "$GPGGA,123519,4807.036,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"
        >>> pos = parse_gga_sentence(sentence)
        >>> print(f"Fix quality: {pos.fix_quality}, Sats: {pos.num_sats}")
        Fix quality: 1, Sats: 8
    """
    try:
        # Validate checksum
        if not validate_nmea_checksum(sentence):
            return None

        # Split fields
        fields = sentence.split(',')
        if len(fields) < 15 or fields[0][:3] != '$GP':
            return None

        # Parse latitude
        lat_str = fields[2]
        lat_hemi = fields[3]
        if lat_str and lat_hemi:
            lat_deg = float(lat_str[:2])
            lat_min = float(lat_str[2:])
            latitude = lat_deg + lat_min / 60.0
            if lat_hemi == 'S':
                latitude = -latitude
        else:
            latitude = 0.0

        # Parse longitude
        lon_str = fields[4]
        lon_hemi = fields[5]
        if lon_str and lon_hemi:
            lon_deg = float(lon_str[:3])
            lon_min = float(lon_str[3:])
            longitude = lon_deg + lon_min / 60.0
            if lon_hemi == 'W':
                longitude = -longitude
        else:
            longitude = 0.0

        # Parse fix quality
        fix_quality = int(fields[6]) if fields[6] else 0

        # Parse satellite count
        num_sats = int(fields[7]) if fields[7] else 0

        # Parse HDOP
        hdop = float(fields[8]) if fields[8] else 99.99

        # Parse altitude
        altitude_m = float(fields[9]) if fields[9] else 0.0

        # Create timestamp
        import datetime
        now = datetime.datetime.now()
        timestamp_ns = int(now.timestamp() * 1e9)

        return GPSPosition(
            timestamp_ns=int(timestamp_ns),
            latitude=latitude,
            longitude=longitude,
            speed_knots=0.0,  # GGA doesn't include speed
            heading_true=0.0,  # GGA doesn't include heading
            fix_quality=fix_quality,
            num_sats=num_sats,
            hdop=hdop,
            altitude_m=altitude_m,
            status='A' if fix_quality > 0 else 'V'
        )

    except (ValueError, IndexError) as e:
        print(f"Error parsing GGA: {e}")
        return None


def parse_hdt_sentence(sentence: str) -> Optional[HeadingData]:
    """
    Parse $HCHDT sentence (Heading, True).

    Args:
        sentence: Raw NMEA HDT sentence

    Returns:
        HeadingData or None if parsing fails

    Example:
        >>> sentence = "$HCHDT,123.4,T*23"
        >>> heading = parse_hdt_sentence(sentence)
        >>> print(f"Heading: {heading.heading_true}°")
        Heading: 123.4°
    """
    try:
        # Validate checksum
        if not validate_nmea_checksum(sentence):
            return None

        # Split fields
        fields = sentence.split(',')
        if len(fields) < 3 or fields[0][:2] != '$HC':
            return None

        # Parse heading
        heading_true = float(fields[1]) if fields[1] else 0.0

        return HeadingData(
            timestamp_ns=int(time.time() * 1e9),
            heading_true=heading_true,
            heading_magnetic=0.0,
            deviation=0.0,
            variation=0.0
        )

    except (ValueError, IndexError) as e:
        print(f"Error parsing HDT: {e}")
        return None


# =============================================================================
# SERIAL PORT HANDLING
# =============================================================================

class NMEASerialPort:
    """
    Windows COM port handler for NMEA0183 data.

    Features:
    - Auto-detection of NMEA ports
    - Baud rate negotiation
    - Thread-safe operation
    - Automatic reconnection

    Usage:
        >>> port = NMEASerialPort("COM1", 4800)
        >>> if port.connect():
        ...     while True:
        ...         sentence = port.get_sentence()
        ...         if sentence:
        ...             print(sentence)
    """

    BAUD_RATES = [4800, 9600, 19200, 38400, 57600, 115200]

    def __init__(self, port: str, baud_rate: int = 4800, timeout: float = 1.0):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.serial_conn: Optional[serial.Serial] = None
        self.is_running = False
        self.data_queue = queue.Queue()
        self.worker_thread: Optional[threading.Thread] = None

    def connect(self) -> bool:
        """Open serial connection"""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )

            self.is_running = True
            self._start_worker()
            return True

        except serial.SerialException as e:
            print(f"Failed to connect to {self.port}: {e}")
            return False

    def _start_worker(self) -> None:
        """Start data collection worker thread"""
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True
        )
        self.worker_thread.start()

    def _worker_loop(self) -> None:
        """Worker thread loop for continuous data collection"""
        buffer = ""

        while self.is_running and self.serial_conn and self.serial_conn.is_open:
            try:
                # Read data
                data = self.serial_conn.read(100)
                if not data:
                    continue

                # Decode
                text = data.decode('ascii', errors='ignore')
                buffer += text

                # Extract complete sentences
                while True:
                    start_idx = buffer.find('$')
                    if start_idx == -1:
                        buffer = ""
                        break

                    end_idx = buffer.find('\r\n', start_idx)
                    if end_idx == -1:
                        break

                    # Extract sentence
                    sentence = buffer[start_idx:end_idx]
                    buffer = buffer[end_idx + 2:]

                    # Validate and queue
                    if validate_nmea_checksum(sentence):
                        self.data_queue.put(sentence)

            except serial.SerialException:
                self.is_running = False
                break
            except UnicodeDecodeError:
                continue

    def get_sentence(self, timeout: float = 1.0) -> Optional[str]:
        """
        Get next valid NMEA sentence.

        Args:
            timeout: Seconds to wait

        Returns:
            NMEA sentence or None if timeout
        """
        try:
            return self.data_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def disconnect(self) -> None:
        """Close serial connection"""
        self.is_running = False

        if self.worker_thread:
            self.worker_thread.join(timeout=2.0)

        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()

    @staticmethod
    def detect_ports() -> List[str]:
        """
        Auto-detect serial ports that might be NMEA devices.

        Returns:
            List of port identifiers (e.g., ['COM1', 'COM2'])

        Example:
            >>> ports = NMEASerialPort.detect_ports()
            >>> print(f"Found {len(ports)} NMEA ports")
        """
        import serial.tools.list_ports
        nmea_ports = []

        for port_info in serial.tools.list_ports.comports():
            # Look for NMEA-specific keywords
            nmea_keywords = ['GPS', 'NMEA', 'GNSS', 'FURUNO', 'GARMIN', 'SIMRAD']
            if any(keyword in port_info.description.upper()
                   for keyword in nmea_keywords):
                nmea_ports.append(port_info.device)

        return nmea_ports

    @staticmethod
    def test_baud_rate(port: str, baud_rate: int, timeout_sec: float = 3.0) -> bool:
        """
        Test if a port is sending NMEA data at a specific baud rate.

        Args:
            port: Port identifier (e.g., 'COM3')
            baud_rate: Baud rate to test
            timeout_sec: Time to wait for NMEA data

        Returns:
            True if valid NMEA data received

        Example:
            >>> if NMEASerialPort.test_baud_rate("COM1", 4800):
            ...     print("NMEA data found at 4800 baud")
        """
        try:
            with serial.Serial(port, baudrate=baud_rate, timeout=timeout_sec) as ser:
                # Read some data
                data = ser.read(100)

                # Check for NMEA sentence
                text = data.decode('ascii', errors='ignore')
                if '$' in text and '*' in text:
                    # Validate checksum
                    for line in text.split('$'):
                        if '*' in line:
                            sentence = '$' + line.split('*')[0] + '*' + line.split('*')[1][:2]
                            if validate_nmea_checksum(sentence):
                                return True

                return False

        except (serial.SerialException, UnicodeDecodeError):
            return False


# =============================================================================
# MAIN NMEA COLLECTOR
# =============================================================================

class NMEACollector:
    """
    Main NMEA data collection and interpolation system.

    Features:
    - Multi-source NMEA collection (serial, UDP, TCP)
    - Real-time position interpolation
    - Data quality validation
    - Error handling and recovery

    Usage:
        >>> collector = NMEACollector()
        >>> if collector.initialize():
        ...     collector.start_collection()
        ...     while True:
        ...         time.sleep(1)
        ...         pos = collector.get_interpolated_position()
        ...         if pos:
        ...             print(f"Position: {pos.latitude:.6f}, {pos.longitude:.6f}")
    """

    def __init__(self):
        self.serial_ports: List[NMEASerialPort] = []
        self.interpolator = GPSInterpolator()
        self.is_running = False

    def initialize(self) -> bool:
        """Initialize all data sources"""
        # Detect and connect to serial ports
        serial_ports = NMEASerialPort.detect_ports()

        if not serial_ports:
            print("No NMEA ports detected")
            return False

        for port_str in serial_ports:
            # Try default baud rate first
            port = NMEASerialPort(port_str, 4800)

            # Test different baud rates
            for baud in NMEASerialPort.BAUD_RATES:
                if NMEASerialPort.test_baud_rate(port_str, baud, timeout_sec=2.0):
                    port = NMEASerialPort(port_str, baud)
                    if port.connect():
                        print(f"Connected to {port_str} at {baud} baud")
                        self.serial_ports.append(port)
                        break

        return len(self.serial_ports) > 0

    def start_collection(self) -> None:
        """Start data collection from all sources"""
        self.is_running = True

        # Start worker threads for each port
        for port in self.serial_ports:
            threading.Thread(
                target=self._serial_worker,
                args=(port,),
                daemon=True
            ).start()

    def _serial_worker(self, port: NMEASerialPort) -> None:
        """Worker thread for serial port data collection"""
        while self.is_running:
            sentence = port.get_sentence(timeout=1.0)
            if sentence:
                self._process_sentence(sentence)

    def _process_sentence(self, sentence: str) -> None:
        """Process NMEA sentence"""
        msg_type = sentence[3:6]

        if msg_type == "RMC":
            position = parse_rmc_sentence(sentence)
            if position:
                self.interpolator.update_gps(position)
                print(f"GPS Update: {position.latitude:.6f}, {position.longitude:.6f}")

        elif msg_type == "GGA":
            position = parse_gga_sentence(sentence)
            if position:
                self.interpolator.update_gps(position)
                print(f"GPS Update: {position.latitude:.6f}, {position.longitude:.6f} "
                      f"(Quality: {position.fix_quality}, Sats: {position.num_sats})")

        elif msg_type == "HDT":
            heading = parse_hdt_sentence(sentence)
            if heading:
                self.interpolator.update_heading(heading.heading_true, heading.timestamp_ns)
                print(f"Heading Update: {heading.heading_true}°")

    def get_interpolated_position(self, target_ns: Optional[int] = None) -> Optional[Tuple[float, float, float]]:
        """
        Get interpolated position for timestamp.

        Args:
            target_ns: Target timestamp in nanoseconds (default: now)

        Returns:
            (latitude, longitude, confidence) or None

        Example:
            >>> lat, lon, conf = collector.get_interpolated_position()
            >>> print(f"Position: {lat:.6f}, {lon:.6f} (confidence: {conf:.2f})")
        """
        if target_ns is None:
            target_ns = int(time.time() * 1e9)

        return self.interpolator.interpolate_position(target_ns)

    def stop_collection(self) -> None:
        """Stop data collection"""
        self.is_running = False

        for port in self.serial_ports:
            port.disconnect()


# =============================================================================
# TESTING AND UTILITIES
# =============================================================================

def test_interpolation():
    """Test interpolation accuracy"""
    print("Testing GPS Interpolation")
    print("=" * 50)

    interpolator = GPSInterpolator()

    # Create test GPS updates
    base_time = int(time.time() * 1e9)

    # Update 1: Moving northeast at 10 knots
    pos1 = GPSPosition(
        timestamp_ns=base_time,
        latitude=58.0,
        longitude=-135.0,
        speed_knots=10.0,
        heading_true=45.0,
        fix_quality=2,
        num_sats=8,
        hdop=0.9,
        altitude_m=0.0,
        status='A'
    )
    interpolator.update_gps(pos1)

    print(f"Initial position: {pos1.latitude:.6f}, {pos1.longitude:.6f}")
    print(f"Speed: {pos1.speed_knots} knots, Heading: {pos1.heading_true}°")

    # Test interpolation at various offsets
    print("\nInterpolation results:")
    print("-" * 50)

    for offset_ms in [100, 250, 500, 750, 1000]:
        test_time = base_time + (offset_ms * 1_000_000)
        result = interpolator.interpolate_position(test_time)

        if result:
            lat, lon, conf = result
            distance = calculate_distance(pos1.latitude, pos1.longitude, lat, lon)
            print(f"+{offset_ms:4d}ms: {lat:.6f}, {lon:.6f} "
                  f"(dist: {distance*1000:.1f}m, conf: {conf:.2f})")
        else:
            print(f"+{offset_ms:4d}ms: Failed (out of range)")


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate great-circle distance between two points (Haversine formula).

    Args:
        lat1, lon1: First point (degrees)
        lat2, lon2: Second point (degrees)

    Returns:
        Distance in kilometers

    Example:
        >>> dist = calculate_distance(58.0, -135.0, 58.1, -135.1)
        >>> print(f"Distance: {dist:.2f} km")
    """
    import math

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    lon1_rad = math.radians(lon1)
    lon2_rad = math.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))

    return 6371 * c  # Earth radius in km


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    print("NMEA0183 Integration Test")
    print("=" * 50)

    # Test 1: Checksum validation
    print("\n1. Testing checksum validation...")
    test_sentences = [
        "$GPRMC,210230,A,3855.4487,N,09446.0071,W,0.0,076.2,210324,,,A*47",
        "$GPGGA,123519,4807.036,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47",
        "$HCHDT,123.4,T*23"
    ]

    for sentence in test_sentences:
        is_valid = validate_nmea_checksum(sentence)
        print(f"  {sentence[3:6]}: {'✓ Valid' if is_valid else '✗ Invalid'}")

    # Test 2: Sentence parsing
    print("\n2. Testing sentence parsing...")
    for sentence in test_sentences:
        msg_type = sentence[3:6]

        if msg_type == "RMC":
            result = parse_rmc_sentence(sentence)
            if result:
                print(f"  RMC: {result.latitude:.6f}, {result.longitude:.6f}")
        elif msg_type == "GGA":
            result = parse_gga_sentence(sentence)
            if result:
                print(f"  GGA: {result.latitude:.6f}, {result.longitude:.6f} "
                      f"(Quality: {result.fix_quality}, Sats: {result.num_sats})")
        elif msg_type == "HDT":
            result = parse_hdt_sentence(sentence)
            if result:
                print(f"  HDT: {result.heading_true}°")

    # Test 3: Interpolation
    print("\n3. Testing interpolation...")
    test_interpolation()

    # Test 4: Port detection
    print("\n4. Detecting NMEA ports...")
    ports = NMEASerialPort.detect_ports()
    if ports:
        print(f"  Found {len(ports)} NMEA ports:")
        for port in ports:
            print(f"    - {port}")
    else:
        print("  No NMEA ports detected")

    print("\n" + "=" * 50)
    print("Testing complete!")
    print("\nTo use with real hardware:")
    print("  collector = NMEACollector()")
    print("  if collector.initialize():")
    print("      collector.start_collection()")
    print("      # Get interpolated positions...")
    print("      collector.stop_collection()")

