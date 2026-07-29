# 🚢 AELMA Sensor Capture Setup Guide
## NMEA 0183 + UDP Depth Sounder Integration for F/V EILEEN

**Status:** System READY - 56 tests passing - All position formats supported

---

## 📡 **Your Sensor Setup Options**

### **Option 1: Real Sensors (Recommended for Operations)**
Connect your actual vessel sensors to AELMA

### **Option 2: Simulated Sensors (Testing/Development)**
Use the built-in simulator for virtual F/V EILEEN

---

## 🔧 **Sensor Configuration**

### **1. NMEA 0183 TCP Connection** ✅

**What it captures:**
- GPS position (lat/lon in 3 formats)
- Depth sounder data
- Speed over ground
- Heading/course
- Time & date
- GPS quality & satellite count

**Default Configuration:**
```python
# Built-in NMEA 0183 TCP listener
Host: 0.0.0.0 (all interfaces)
Port: 8001
Output: nmea_telemetry.jsonl
```

**How to Connect Your Sensors:**

**If you have NMEA sensors:**
```bash
# Method 1: TCP forwarding (recommended)
# Point your NMEA multiplexer to localhost:8001

# Method 2: Serial to TCP bridge
# Install serial-to- TCP bridge (e.g., ser2net)
# Configure to read from serial port and forward to localhost:8001

# Method 3: Signal K to NMEA
# If you have Signal K, add NMEA TCP output pointing to localhost:8001
```

**Typical NMEA 0183 Sources:**
- GPS/chartplotter (Garmin, Simrad, Raymarine)
- AIS transponder
- Autopilot
- Depth sounder (NMEA output)
- Weather station
- VHF radio with NMEA gateway

---

### **2. UDP Depth Sounder** ✅

**What it captures:**
- Depth below transducer
- Timestamp
- Sensor ID
- Raw packet data

**Default Configuration:**
```python
# Built-in UDP depth listener
Host: 0.0.0.0 (all interfaces)
Port: 50000
Output: depth_sounder.jsonl
```

**How to Connect Your Depth Sounder:**

**If your depth sounder supports UDP:**
```bash
# Configure depth sounder to send UDP packets to:
# Destination: 192.168.1.100 (your laptop IP)
# Port: 50000
# Protocol: UDP
# Format: Plain text depth value or "DEPTH=X.X" format
```

**If your depth sounder only has serial output:**
```bash
# Use serial-to-UDP bridge (e.g., ser2net)
# Configure to read from serial port and forward as UDP to localhost:50000
```

**Supported Depth Formats:**
- `DEPTH=12.3` - Named parameter format
- `12.3m` - Plain text with unit
- `12.3` - Plain number (assumes meters)
- Binary 4-byte float (IEEE 754)

---

### **3. Radar UDP (Future Expansion)** 🔮

**What it will capture:**
- Radar target data
- ARPA targets
- Tracking data
- Raw radar packets

**Configuration:**
```python
# Generic UDP radar listener (ready for when you have radar)
Host: 0.0.0.0
Port: 50001
Output: radar.jsonl
```

**When you add radar:**
```bash
# Configure radar to send UDP to:
# Destination: 192.168.1.100
# Port: 50001
# Protocol: Manufacturer-specific
```

---

## 📍 **Position Format Support (All 3 Formats)**

Your position is stored in **three formats simultaneously**:

### **Format 1: Decimal Degrees (Computational)**
```
Latitude: 57.053
Longitude: -135.330
```
**Used for:** Calculations, distance, mapping APIs

### **Format 2: Degrees-Minutes-Seconds (Human)**
```
Latitude: 57°03'10.8"N
Longitude: 135°19'48.0"W
```
**Used for:** Radio communications, paper charts, logbooks

### **Format 3: NMEA 0183 Format (Marine Standard)**
```
Latitude: 5703.180,N
Longitude: 13519.800,W
```
**Used for:** NMEA equipment compatibility, marine displays

**Conversion Example:**
```python
# All three formats stored for each position fix
record = NMEA0183Record(
    lat_dec=57.053,
    lon_dec=-135.330,
    lat_dms="57°03'10.8\"N",
    lon_dms="135°19'48.0\"W",
    lat_nmea="5703.180,N",
    lon_nmea="13519.800,W"
)
```

---

## 🚀 **Quick Start: Live Sensor Capture**

### **Step 1: Start the Sensor Capture System**

```python
# Option A: Use TwinCore integration (automatic)
cd aelma/twin
python -m twin.core --bridge-url ws://localhost:8000 \
    --nmea-port 8001 \
    --udp-depth-port 50000

# Option B: Standalone sensor coordinator
cd aelma/twin/sensors
python nmea_udp_capture.py
```

### **Step 2: Connect Your Sensors**

**NMEA 0183 Sources:**
```bash
# If you have a serial NMEA source:
# Install serial-to-TCP bridge and configure:
# Serial port: COM1 (Windows) or /dev/ttyUSB0 (Linux)
# Baud rate: 4800 (NMEA standard) or 38400 (NMEA 2000 high speed)
# TCP forward to: localhost:8001
```

**UDP Depth Sounder:**
```bash
# Configure your depth sounder to send UDP:
# IP: 192.168.1.100 (your computer's IP)
# Port: 50000
# Protocol: UDP
# Format: "DEPTH=X.X" or plain number
```

### **Step 3: Verify Data Flow**

```bash
# Check for incoming NMEA sentences
tail -f nmea_telemetry.jsonl

# Check for depth sounder data
tail -f depth_sounder.jsonl

# Check system log
tail -f sensor_capture.log
```

### **Step 4: View in Dashboard**

```
http://localhost:8081/dashboard.html
```

**What you should see:**
- **Position gauges updating** (if NMEA GPS active)
- **Depth gauge updating** (if depth sounder active)
- **Speed/heading gauges** (if NMEA data available)
- **Charts drawing live data**

---

## 📊 **Data Storage Structure**

```
aelma/
├── nmea_telemetry.jsonl      # All NMEA 0183 sentences
├── depth_sounder.jsonl         # UDP depth sounder data
├── radar.jsonl                  # Future radar data
└── sensor_capture.log          # System log
```

### **JSONL Format Examples**

**nmea_telemetry.jsonl:**
```json
{"kind": "nmea_0183", "sentence_type": "GPGGA", "raw_sentence": "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47", "timestamp_ns": 1722289012345678901, "lat_dec": 48.1173, "lon_dec": 11.5167, "lat_dms": "48°07'02.3\"N", "lon_dms": "11°31'00.0\"E", "lat_nmea": "4807.038,N", "lon_nmea": "01131.000,E", "utc_time": "12:35:19", "date": "2026-07-28", "quality": 1, "satellites": 8, "hdop": 0.9}
{"kind": "nmea_0183", "sentence_type": "DBT", "raw_sentence": "$DBT,,042.5,f*21", "timestamp_ns": 1722289012345678902, "depth_m": 12.95, "sensor_id": "depth_sounder"}
```

**depth_sounder.jsonl:**
```json
{"kind": "udp_depth", "sensor_id": "depth_sounder", "depth_m": 45.2, "depth_ft": 148.3, "depth_fathoms": 24.7, "timestamp_ns": 1722289012345678903, "raw_packet": "DEPTH=45.2"}
```

---

## 🎯 **Your Human-in-the-Loop Responsibilities**

### **Every Watch (4-6 hours):**
- [ ] Check sensor data is flowing (JSONL files growing)
- [ ] Verify position accuracy (compare to chart)
- [ ] Check depth sounder is recording
- [ ] Monitor for sensor errors in log file

### **Daily:**
- [ ] Backup JSONL log files
- [ ] Review data quality (missing sentences, gaps)
- [ ] Check sensor health indicators
- [ ] Verify GPS quality (HDOP, satellite count)

### **Weekly:**
- [ ] Archive old JSONL files to storage
- [ ] Check for sensor firmware updates
- [ ] Calibrate depth sounder against known depth
- [ ] Validate position against known waypoints

---

## ⚠️ **Troubleshooting**

### **No NMEA Data Arriving:**

**Check TCP listener:**
```bash
netstat -ano | grep 8001
# Should show LISTENING state
```

**Test NMEA source:**
```bash
# Use telnet to test connection
telnet localhost 8001
# Type: $GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47
# Press Enter
# Should appear in nmea_telemetry.jsonl
```

**Serial port configuration:**
```bash
# On Linux, check serial port exists
ls -l /dev/ttyUSB0
# On Windows, check COM ports
# Device Manager → Ports (COM & LPT)
```

### **No UDP Depth Data:**

**Check UDP listener:**
```bash
netstat -ano | grep 50000
# Should show LISTENING state
```

**Test UDP sender:**
```python
# Simple test script
import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.sendto(b"DEPTH=45.2", ("127.0.0.1", 50000))
print("Test packet sent")
# Check depth_sounder.jsonl for result
```

**Firewall check:**
```bash
# Windows: Allow port 50000 through Windows Firewall
# Linux: sudo ufw allow 50000/udp
```

### **Position Seems Wrong:**

**Check format conversions:**
```python
# Open Python REPL
from twin.sensors.nmea_udp_capture import dec_to_dms, dec_to_nmea

lat, lon = 57.053, -135.330
dms_lat, dms_lon = dec_to_dms(lat, lon)
nmea_lat, nmea_lon = dec_to_nmea(lat, lon)

print(f"Decimal: {lat}, {lon}")
print(f"DMS: {dms_lat}, {dms_lon}")
print(f"NMEA: {nmea_lat}, {nmea_lon}")
```

**Compare to known position:**
- Check against your GPS chartplotter display
- Verify against paper chart
- Confirm against handheld GPS

### **Data Gaps or Missing Sentences:**

**Check JSONL files:**
```bash
# Count NMEA records
wc -l nmea_telemetry.jsonl

# Check last entry time
tail -1 nmea_telemetry.jsonl | python -m json.tool
```

**Check error log:**
```bash
grep ERROR sensor_capture.log
```

---

## 🔮 **Future Sensor Additions**

### **When You Add Radar:**
```python
# Generic UDP radar handler already built
coordinator = SensorCaptureCoordinator()
coordinator.start_radar(port=50001)
# Configure radar to send UDP to port 50001
```

### **When You Add AIS:**
```python
# AIS often broadcasts on UDP port 10101
# Can be captured with generic UDP handler
```

### **When You Add Weather Station:**
```python
# Weather stations often send NMEA 0183 sentences
# $WIMDA, wind direction/speed, barometric pressure, etc.
# Will be captured by NMEA listener automatically
```

---

## 📈 **Sensor Data Quality Metrics**

### **Good Data Indicators:**
- ✅ Regular NMEA sentences (1-10 per second)
- ✅ Consistent GPS quality (quality 1-2, HDOP <2.0)
- ✅ 8+ satellites (typical for marine GPS)
- ✅ Depth sounder updates (1-5 per second)
- ✅ Position matches known location

### **Warning Indicators:**
- ⚠️ GPS quality indicator 0 (no fix)
- ⚠️ HDOP >5.0 (poor accuracy)
- ⚠️ <4 satellites (poor geometry)
- ⚠️ Large position jumps (multipath errors)
- ⚠️ Depth sounder gaps >30 seconds

### **Error Indicators:**
- ❌ No NMEA sentences for >30 seconds
- ❌ Malformed sentences (checksum failures)
- ❌ Position drift >100m from expected
- ❌ Depth sounder not reporting

---

## 🎓 **Understanding Your Position Formats**

### **When to Use Each Format:**

**Decimal Degrees (57.053, -135.330):**
- Computer calculations
- Distance between waypoints
- Chart plotting APIs
- Database queries

**DMS (57°03'10.8"N, 135°19'48.0"W):**
- Radio communications
- Paper chart plotting
- Logbook entries
- Crew coordination

**NMEA Format (5703.180,N, 13519.800,W):**
- Marine equipment compatibility
- Chartplotter input
- VHF radio DSC
- Electronic chart systems

### **Quick Reference:**
```
Decimal:    57.053° N, 135.330° W
DMS:        57°03'10.8"N, 135°19'48.0"W
NMEA:       5703.180,N, 13519.800,W
Chart:      57° 03.18' N, 135° 19.80' W (USGS format)
```

---

## 📞 **Quick Reference Commands**

```bash
# Start sensor capture
cd aelma/twin/sensors
python nmea_udp_capture.py

# Check NMEA data
tail -f nmea_telemetry.jsonl

# Check depth data
tail -f depth_sounder.jsonl

# Count records
wc -l nmea_telemetry.jsonl depth_sounder.jsonl

# Test NMEA connection
telnet localhost 8001

# Test UDP depth
python -c "import socket; sock.sendto(b'DEPTH=45.2', ('127.0.0.1', 50000))"

# Check ports
netstat -ano | grep -E "8001|50000|50001"

# View dashboard
# Open browser to http://localhost:8081/dashboard.html
```

---

## ✅ **System Status Checklist**

**Before departure:**
- [ ] NMEA listener started (port 8001)
- [ ] UDP depth listener started (port 50000)
- [ ] Dashboard accessible (port 8081)
- [ ] JSONL files being written
- [ ] Position accuracy verified
- [ ] Depth sounder calibrated

**During operations:**
- [ ] Sensor data flowing continuously
- [ ] Position matches expected location
- [ ] Depth readings reasonable
- [ ] No errors in sensor_capture.log
- [ ] GPS quality acceptable (1-2, HDOP <2.0)

**End of watch:**
- [ ] Backup JSONL log files
- [ ] Review sensor health
- [ ] Note any data gaps
- [ ] Archive to permanent storage

---

**Your AELMA system is ready to capture ALL your NMEA 0183 and UDP depth sounder data in THREE position formats!**

🚢 **Safe travels up the coast - your digital twin has eyes on everything!** ⚡