# NMEA0183 Implementation Guide - Quick Start

## Prerequisites

```bash
# Install required Python packages
pip install pynmea2 pyserial numpy pandas
```

## Quick Start Example

### 1. Basic NMEA Parsing (5 minutes)

```python
import pynmea2
from datetime import datetime

# Parse individual sentences
rmc_sentence = "$GPRMC,210230,A,3855.4487,N,09446.0071,W,0.0,076.2,210324,,,A*47"
gga_sentence = "$GPGGA,123519,4807.036,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"

# Parse RMC (Recommended Minimum)
rmc = pynmea2.parse(rmc_sentence)
print(f"Latitude: {rmc.latitude} {rmc.lat_dir}")
print(f"Longitude: {rmc.longitude} {rmc.lon_dir}")
print(f"Speed: {rmc.spd_over_grnd} knots")
print(f"Heading: {rmc.true_course}° True")

# Parse GGA (Fix Data)
gga = pynmea2.parse(gga_sentence)
print(f"Fix Quality: {gga.gps_qual} (1=GPS, 2=DGPS)")
print(f"Satellites: {gga.num_sats}")
print(f"Altitude: {gga.altitude} {gga.altitude_units}")
```

### 2. Checksum Validation (2 minutes)

```python
def validate_checksum(sentence: str) -> bool:
    """Validate NMEA checksum"""
    star_idx = sentence.find('*')
    if star_idx == -1:
        return False

    provided = sentence[star_idx + 1:star_idx + 3]
    calculated = 0

    for char in sentence[1:star_idx]:
        calculated ^= ord(char)

    return f"{calculated:02X}" == provided

# Test
test_sentence = "$GPRMC,210230,A,3855.4487,N,09446.0071,W,0.0,076.2,210324,,,A*47"
print(f"Checksum valid: {validate_checksum(test_sentence)}")
```

### 3. Serial Port Integration (5 minutes)

```python
import serial
import time

# Auto-detect NMEA ports
def find_nmea_ports():
    """Find serial ports that might have NMEA data"""
    import serial.tools.list_ports
    nmea_ports = []

    for port in serial.tools.list_ports.comports():
        if any(keyword in port.description.upper()
               for keyword in ['GPS', 'NMEA', 'FURUNO', 'GARMIN']):
            nmea_ports.append(port.device)

    return nmea_ports

# Connect to GPS
ports = find_nmea_ports()
if ports:
    ser = serial.Serial(ports[0], baudrate=4800, timeout=1)

    # Read NMEA data
    buffer = ""
    while True:
        data = ser.read(100).decode('ascii', errors='ignore')
        buffer += data

        # Extract complete sentences
        while '$' in buffer and '\r\n' in buffer:
            start = buffer.find('$')
            end = buffer.find('\r\n', start)

            if end > start:
                sentence = buffer[start:end]
                buffer = buffer[end + 2:]

                if validate_checksum(sentence):
                    print(sentence)
```

### 4. Basic Interpolation (10 minutes)

```python
import math
from dataclasses import dataclass
from typing import Optional

@dataclass
class GPSUpdate:
    """GPS position update"""
    timestamp_ns: int
    latitude: float
    longitude: float
    speed_knots: float
    heading_degrees: float

class SimpleInterpolator:
    """Basic GPS interpolator"""

    def __init__(self):
        self.last_update: Optional[GPSUpdate] = None

    def update(self, position: GPSUpdate):
        """Update with new GPS position"""
        self.last_update = position

    def interpolate(self, target_ns: int) -> Optional[tuple]:
        """Interpolate position for target time"""
        if not self.last_update:
            return None

        # Time difference
        delta_s = (target_ns - self.last_update.timestamp_ns) / 1e9

        # Only interpolate within 2 seconds
        if abs(delta_s) > 2.0:
            return None

        # Calculate displacement
        speed_mps = self.last_update.speed_knots * 0.514444
        heading_rad = math.radians(self.last_update.heading_degrees)
        lat_rad = math.radians(self.last_update.latitude)

        distance_m = speed_mps * delta_s

        # Earth radius
        earth_m = 6378137.0

        # Calculate delta
        delta_lat = (distance_m * math.cos(heading_rad)) / earth_m
        delta_lon = (distance_m * math.sin(heading_rad)) / \
                    (earth_m * math.cos(lat_rad))

        # New position
        new_lat = self.last_update.latitude + math.degrees(delta_lat)
        new_lon = self.last_update.longitude + math.degrees(delta_lon)

        return (new_lat, new_lon)

# Usage
interpolator = SimpleInterpolator()

# Update with GPS position
now = int(time.time() * 1e9)
interpolator.update(GPSUpdate(
    timestamp_ns=now,
    latitude=58.123,
    longitude=-134.456,
    speed_knots=8.5,
    heading_degrees=45.0
))

# Interpolate for sounder ping (500ms later)
ping_time = now + 500_000_000  # 500ms
result = interpolator.interpolate(ping_time)

if result:
    lat, lon = result
    print(f"Interpolated: {lat:.6f}, {lon:.6f}")
```

## Production Integration

### 5. Complete NMEA Collector (30 minutes)

```python
import serial
import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional

class NMEACollector:
    """Production NMEA data collector"""

    def __init__(self, port: str = "COM1", baud: int = 4800):
        self.port = port
        self.baud = baud
        self.serial_conn: Optional[serial.Serial] = None
        self.data_queue = queue.Queue()
        self.is_running = False
        self.worker_thread: Optional[threading.Thread] = None

        # Interpolator
        from nmea_integration_analysis import NMEAInterpolator
        self.interpolator = NMEAInterpolator()

    def connect(self) -> bool:
        """Connect to NMEA source"""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0
            )

            self.is_running = True
            self._start_worker()
            return True

        except serial.SerialException as e:
            print(f"Failed to connect: {e}")
            return False

    def _start_worker(self):
        """Start data collection thread"""
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True
        )
        self.worker_thread.start()

    def _worker_loop(self):
        """Data collection loop"""
        buffer = ""

        while self.is_running:
            try:
                # Read data
                data = self.serial_conn.read(100)
                if not data:
                    continue

                # Decode
                text = data.decode('ascii', errors='ignore')
                buffer += text

                # Extract sentences
                while True:
                    start = buffer.find('$')
                    if start == -1:
                        buffer = ""
                        break

                    end = buffer.find('\r\n', start)
                    if end == -1:
                        break

                    sentence = buffer[start:end]
                    buffer = buffer[end + 2:]

                    # Validate
                    if self._validate_sentence(sentence):
                        self.data_queue.put(sentence)

            except Exception as e:
                print(f"Error: {e}")
                break

    def _validate_sentence(self, sentence: str) -> bool:
        """Validate NMEA sentence"""
        if not sentence.startswith('$'):
            return False
        if '*' not in sentence:
            return False

        # Checksum validation
        return validate_checksum(sentence)

    def get_sentence(self, timeout: float = 1.0) -> Optional[str]:
        """Get next valid sentence"""
        try:
            return self.data_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_interpolated_position(self, target_ns: int) -> Optional[tuple]:
        """Get interpolated position for timestamp"""
        return self.interpolator.interpolate_position(target_ns)

    def disconnect(self):
        """Disconnect from NMEA source"""
        self.is_running = False

        if self.worker_thread:
            self.worker_thread.join(timeout=2.0)

        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()

# Usage
collector = NMEACollector(port="COM1", baud=4800)

if collector.connect():
    print("Connected to GPS")

    # Collect data
    while True:
        sentence = collector.get_sentence()
        if sentence:
            msg_type = sentence[3:6]

            if msg_type in ["RMC", "GGA"]:
                # Parse GPS position
                msg = pynmea2.parse(sentence)

                position = GPSUpdate(
                    timestamp_ns=int(time.time() * 1e9),
                    latitude=msg.latitude if msg.lat_dir == 'N' else -msg.latitude,
                    longitude=msg.longitude if msg.lon_dir == 'E' else -msg.longitude,
                    speed_knots=getattr(msg, 'spd_over_grnd', 0),
                    heading_degrees=getattr(msg, 'true_course', 0)
                )

                collector.interpolator.update_gps(position)
                print(f"Position: {position.latitude:.6f}, {position.longitude:.6f}")

                # Test interpolation
                test_time = int(time.time() * 1e9) + 500_000_000  # 500ms
                result = collector.get_interpolated_position(test_time)
                if result:
                    lat, lon, conf = result
                    print(f"  Interpolated (+500ms): {lat:.6f}, {lon:.6f} (conf: {conf:.2f})")
```

## Testing Your Setup

### 6. Test with Real Data

```python
# Test script to validate your NMEA setup
def test_nmea_setup():
    """Test NMEA integration"""

    print("Testing NMEA Setup")
    print("=" * 50)

    # 1. Test checksum validation
    print("\n1. Testing checksum validation...")
    test_sentences = [
        "$GPRMC,210230,A,3855.4487,N,09446.0071,W,0.0,076.2,210324,,,A*47",
        "$GPGGA,123519,4807.036,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47",
        "$HCHDT,123.4,T*23"
    ]

    for sentence in test_sentences:
        is_valid = validate_checksum(sentence)
        print(f"  {sentence[3:6]}: {'✓' if is_valid else '✗'}")

    # 2. Test parsing
    print("\n2. Testing sentence parsing...")
    for sentence in test_sentences:
        try:
            msg = pynmea2.parse(sentence)
            print(f"  {sentence[3:6]}: ✓ Parsed")
        except Exception as e:
            print(f"  {sentence[3:6]}: ✗ {e}")

    # 3. Test interpolation
    print("\n3. Testing interpolation...")
    interpolator = SimpleInterpolator()

    # Add GPS update
    now = int(time.time() * 1e9)
    interpolator.update(GPSUpdate(
        timestamp_ns=now,
        latitude=58.0,
        longitude=-135.0,
        speed_knots=10.0,
        heading_degrees=90.0
    ))

    # Test interpolation at various offsets
    for offset_ms in [100, 500, 1000, 1500]:
        test_time = now + (offset_ms * 1_000_000)
        result = interpolator.interpolate(test_time)
        if result:
            lat, lon = result
            print(f"  +{offset_ms}ms: {lat:.6f}, {lon:.6f}")
        else:
            print(f"  +{offset_ms}ms: Failed (out of range)")

    print("\n✓ All tests complete")

if __name__ == "__main__":
    test_nmea_setup()
```

## Common Issues and Solutions

### Issue 1: No Data from Serial Port

**Symptoms:** No NMEA sentences received

**Solutions:**
1. Check COM port number
2. Try different baud rates (4800, 38400, 115200)
3. Verify device is transmitting (use terminal program)
4. Check cable connections

```python
# Auto-detect correct baud rate
def find_correct_baud(port: str) -> int:
    """Try different baud rates"""
    for baud in [4800, 9600, 19200, 38400, 57600, 115200]:
        try:
            with serial.Serial(port, baudrate=baud, timeout=2) as ser:
                data = ser.read(100)
                if b'$' in data and b'*' in data:
                    return baud
        except:
            continue
    return None

correct_baud = find_correct_baud("COM1")
print(f"Correct baud rate: {correct_baud}")
```

### Issue 2: Checksum Failures

**Symptoms:** All sentences fail checksum validation

**Solutions:**
1. Verify ASCII encoding
2. Check for transmission errors
3. Disable checksum validation for testing

```python
# Less strict validation (for testing only)
def validate_checksum_lax(sentence: str) -> bool:
    """Lax checksum validation (ignores case)"""
    star_idx = sentence.find('*')
    if star_idx == -1:
        return False

    provided = sentence[star_idx + 1:star_idx + 3].upper()
    calculated = 0

    for char in sentence[1:star_idx]:
        calculated ^= ord(char)

    return f"{calculated:02X}" == provided
```

### Issue 3: Inaccurate Interpolation

**Symptoms:** Interpolated positions are far from actual track

**Solutions:**
1. Check GPS fix quality (use DGPS if available)
2. Verify heading data accuracy
3. Reduce extrapolation time window
4. Improve velocity estimation

```python
# Better interpolation with quality check
def interpolate_with_quality(interpolator, target_ns: int):
    """Interpolate with quality checks"""
    result = interpolator.interpolate_position(target_ns)

    if result:
        lat, lon, confidence = result

        # Only use high-confidence positions
        if confidence >= 0.7:
            return (lat, lon, confidence)
        else:
            print(f"Low confidence: {confidence:.2f}")
            return None

    return None
```

## Next Steps

1. **Install dependencies:**
   ```bash
   pip install pynmea2 pyserial numpy
   ```

2. **Test with your hardware:**
   ```bash
   python test_nmea_setup.py
   ```

3. **Integrate with your system:**
   - Copy the `NMEACollector` class
   - Configure for your COM port and baud rate
   - Add your custom data processing

4. **Production deployment:**
   - Add error handling and logging
   - Implement automatic failover
   - Add health monitoring
   - Create Windows service

## Full Documentation

For complete implementation details, see:
- `nmea_integration_analysis.md` - Comprehensive analysis and algorithms
- `nmea_implementation_guide.md` - This quick start guide

---

**Quick Start Version:** 1.0
**Last Updated:** 2026-07-24
**Status:** Ready for Testing
