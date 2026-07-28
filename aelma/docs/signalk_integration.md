# Signal K Integration for AELMA

## Overview

Signal K is a modern, JSON-based marine data format designed for boating applications. AELMA now supports Signal K as a first-class data source alongside NMEA 0183, enabling integration with modern marine instrument networks and software like:
- **Freeboard-SignalK** - Chart plotter and instrument display
- **Signal K Server** - Open-source marine data server
- **OpenCPN** - Chart plotter with Signal K plugin
- **K marine instruments** - Modern sensors with native Signal K support

## Architecture

The Signal K integration consists of three main components:

### 1. Signal K Parser (`bridge/signalk.py`)

**Pure functions** for parsing Signal K delta messages and converting them to AELMA telemetry packets.

```python
from bridge.signalk import parse_delta, SignalKDelta, path_to_channel

# Parse a Signal K delta
delta = {
    "context": "vessels.urn:mrn:imo:mmsi:123456789",
    "updates": [{
        "timestamp": "2025-01-15T12:34:56Z",
        "values": [
            {"path": "navigation.depth.belowKeel", "value": 73.2}
        ]
    }]
}

readings = parse_delta(delta)
# [{'source': 'signalk', 'channel': 'depth_m', 'value': 73.2, 'path': 'signalk'}]
```

**Key Functions:**
- `parse_delta(delta_data)` - Parse delta to readings
- `SignalKDelta(delta_data)` - Delta parser class
- `path_to_channel(path)` - Convert Signal K path to AELMA channel

### 2. Signal K Bridge (`bridge/bridge.py`)

**Async bridge** that connects to Signal K servers and broadcasts telemetry packets.

```python
from bridge.bridge import SignalKBridge

bridge = SignalKBridge(
    signalk_host="localhost",
    signalk_port=3000,
    signalk_tcp_port=8002,
    telemetry_ws_port=8000
)

await bridge.start()  # Starts WebSocket client + TCP server + telemetry WS
```

**Components:**
- **WebSocket Client** - Connects to Signal K server, receives delta updates
- **TCP Server** - Listens for direct Signal K JSON connections (port 8002)
- **Telemetry WebSocket Server** - Broadcasts telemetry packets to subscribers (port 8000)

### 3. Path Mapping

Signal K paths are automatically converted to AELMA channels:

| Signal K Path | AELMA Channel | Unit Conversion |
|--------------|---------------|-----------------|
| `navigation.position.latitude` | `position.lat` | None |
| `navigation.position.longitude` | `position.lon` | None |
| `navigation.speedOverGround` | `sog_kn` | m/s → knots |
| `navigation.courseOverGroundTrue` | `cog_deg` | None |
| `navigation.depth.belowKeel` | `depth_m` | None |
| `navigation.depth.belowSurface` | `depth_m` | None |
| `navigation.depth.belowTransom` | `depth_m` | None |
| `environment.wind.speedTrue` | `wind_kts_true` | m/s → knots |
| `environment.wind.speedApparent` | `wind_kts_apparent` | m/s → knots |
| `environment.wind.angleTrue` | `wind_dir_deg_true` | None |
| `environment.wind.angleApparent` | `wind_dir_deg_apparent` | None |
| `environment.water.temperature` | `sea_temp_c` | Kelvin → Celsius |
| `environment.air.temperature` | `air_temp_c` | Kelvin → Celsius |
| `environment.air.pressure` | `baro_mb` | Pa → mb |

## Signal K Delta Format

Signal K uses delta updates - compact JSON messages containing only changed values.

**Example Delta:**
```json
{
  "context": "vessels.urn:mrn:imo:mmsi:123456789",
  "updates": [
    {
      "source": {
        "type": "NMEA0183",
        "sentence": "GPGGA"
      },
      "timestamp": "2025-01-15T12:34:56Z",
      "values": [
        {
          "path": "navigation.position.latitude",
          "value": 56.8013
        },
        {
          "path": "navigation.position.longitude",
          "value": -135.3028
        },
        {
          "path": "navigation.depth.belowKeel",
          "value": 73.2
        }
      ]
    }
  ]
}
```

## Running the Signal K Bridge

### Method 1: Connect to Existing Signal K Server

```bash
# Connect to Signal K server at localhost:3000
python -m bridge.bridge --signalk-host localhost --signalk-port 3000
```

### Method 2: Receive TCP Signal K Connections

Point your Signal K server or instrument to send data to the bridge's TCP port:

```bash
# Bridge listens for Signal K JSON on port 8002
# Configure your Signal K server to forward to: localhost:8002
python -m bridge.bridge --signalk-tcp-port 8002
```

### Method 3: Direct Python API

```python
import asyncio
from bridge.bridge import SignalKBridge

async def main():
    bridge = SignalKBridge(
        signalk_host="192.168.1.100",  # Signal K server IP
        signalk_port=3000,
        telemetry_ws_port=8000
    )
    await bridge.serve_forever()

asyncio.run(main())
```

## Multiplexing NMEA and Signal K

The bridge can simultaneously process both NMEA 0183 and Signal K data sources:

```python
# NMEA Bridge (port 8001)
nmea_bridge = NMEABridge(tcp_port=8001, ws_port=8000)

# Signal K Bridge (port 8002, different telemetry port)
signalk_bridge = SignalKBridge(
    signalk_tcp_port=8002,
    telemetry_ws_port=8001  # Different port to avoid conflict
)

# Or use a unified telemetry port with source identification
# All packets include a 'source' field: 'nmea0183' or 'signalk'
```

## Telemetry Packet Format

Both NMEA and Signal K produce the same telemetry packet format:

```json
{
  "timestamp_ns": 1705320896123456789,
  "source": "signalk",
  "channel": "depth_m",
  "value": 73.2,
  "quality": "good",
  "sentence": null
}
```

**Fields:**
- `timestamp_ns` - Nanosecond timestamp (assigned by bridge)
- `source` - "nmea0183" or "signalk"
- `channel` - AELMA channel name
- `value` - Reading value (converted to standard units)
- `quality` - "good", "fair", or "bad"
- `sentence` - Original NMEA sentence (null for Signal K)

## Testing

Comprehensive test suite covers all aspects of Signal K integration:

```bash
# Run Signal K tests
python -m pytest tests/signalk.test.py -v

# Run with coverage
python -m pytest tests/signalk.test.py --cov=bridge/signalk --cov-report=html
```

**Test Coverage:**
- Path-to-channel mapping
- Delta parsing (simple, complex, nested)
- Unit conversions (m/s→knots, K→°C, Pa→mb)
- Array value handling
- Multiplexing with NMEA
- End-to-end packet building
- Error handling

## Signal K Server Setup

### Freeboard-SignalK

1. **Install Freeboard-SignalK:**
   ```bash
   docker run -p 3000:3000 --name signalk signalk/freeboard-signal-k
   ```

2. **Configure AELMA Bridge:**
   ```bash
   python -m bridge.bridge --signalk-host localhost --signalk-port 3000
   ```

3. **Verify Connection:**
   - Open http://localhost:3000
   - Check "Connected Instruments"
   - View real-time delta stream

### Signal K Node Server

1. **Install Node Server:**
   ```bash
   npm install -g signalk-server
   signalk-server
   ```

2. **Configure Settings:**
   ```json
   {
     "pipes": [
       {
         "id": "aelma-bridge",
         "type": "clients",
         "enabled": true,
         "options": {
           "port": 8002,
           "host": "localhost",
           "protocol": "tcp"
         }
       }
     ]
   }
   ```

## Troubleshooting

### Connection Issues

**Problem:** "Signal K connection closed, reconnecting..."
- **Solution:** Check Signal K server is running and accessible
- **Test:** `curl http://localhost:3000/signalk/v1/api/vessels/self`

**Problem:** "Invalid JSON from Signal K"
- **Solution:** Verify Signal K server is sending valid deltas
- **Test:** Use WebSocket client to inspect raw messages

### Data Not Appearing

**Problem:** No telemetry packets received
- **Check 1:** Verify Signal K paths are supported
- **Check 2:** Enable debug logging: `python -m bridge.bridge --debug`
- **Check 3:** Test with known-good delta: `python -c "from bridge.signalk import parse_delta; print(parse_delta(...))"`

### Unit Conversion Issues

**Problem:** Values seem incorrect
- **Check:** Verify expected units match AELMA conversions
- **Example:** Signal K wind speed is m/s, AELMA converts to knots
- **Test:** `print(path_to_channel("environment.wind.speedTrue"))` → "wind_kts_true"

## API Reference

### `signalk.parse_delta(delta_data)`

Parse a Signal K delta message into telemetry readings.

**Parameters:**
- `delta_data` (dict | str) - Signal K delta dict or JSON string

**Returns:**
- `list[Reading]` - List of reading dicts

**Example:**
```python
readings = parse_delta({
    "updates": [{
        "values": [
            {"path": "navigation.depth.belowKeel", "value": 73.2}
        ]
    }]
})
```

### `signalk.SignalKDelta(delta_data)`

Delta parser class with additional methods.

**Methods:**
- `to_readings()` - Convert to readings list
- `get_context()` - Get vessel context
- `get_timestamp()` - Get delta timestamp

**Example:**
```python
delta = SignalKDelta(delta_data)
readings = delta.to_readings()
context = delta.get_context()
```

### `signalk.path_to_channel(path)`

Convert a Signal K path to an AELMA channel name.

**Parameters:**
- `path` (str) - Signal K path

**Returns:**
- `str | None` - AELMA channel or None if unsupported

**Example:**
```python
channel = path_to_channel("navigation.depth.belowKeel")
# Returns: "depth_m"
```

### `bridge.SignalKBridge`

Async bridge for Signal K integration.

**Parameters:**
- `signalk_host` (str) - Signal K server hostname (default: "localhost")
- `signalk_port` (int) - Signal K WebSocket port (default: 3000)
- `signalk_tcp_port` (int) - TCP listener port (default: 8002)
- `telemetry_ws_port` (int) - Telemetry WebSocket port (default: 8000)

**Methods:**
- `start()` - Start all servers and connections
- `serve_forever()` - Run until stopped
- `stop()` - Graceful shutdown
- `ingest_delta(delta_data)` - Parse and broadcast delta

## Performance Considerations

### Message Rate

Signal K delta updates can be high-frequency (10-100 Hz). The bridge is designed to handle:

- **10 Hz** - Typical navigation data (position, speed, course)
- **50 Hz** - High-frequency sensors (depth, wind)
- **100 Hz** - Raw sensor data

**Optimization:**
- Use WebSocket client for real-time streaming (preferred)
- Use TCP server for batched data or testing
- Enable debug logging only during development

### Memory Usage

The bridge maintains a last-seen cache for each channel:

- **Per-channel overhead:** ~200 bytes
- **100 channels:** ~20 KB
- **1000 channels:** ~200 KB

**Memory management:**
- Cache is automatically pruned on channel updates
- No memory leaks from stale connections
- Graceful handling of connection drops

### Network Bandwidth

Typical bandwidth usage:

- **Per delta:** ~200-500 bytes (JSON)
- **10 Hz updates:** ~2-5 KB/s
- **50 Hz updates:** ~10-25 KB/s

**Optimization:**
- Use WebSocket compression (handled by websockets library)
- Filter unsupported paths at source
- Batch updates when possible

## Advanced Usage

### Custom Path Handlers

Add support for additional Signal K paths:

```python
# In bridge/signalk.py
def _custom_path_handler(path: str, value: Any) -> list[Reading]:
    """Handle custom Signal K path."""
    # Convert path to reading
    return [_reading("custom_channel", value, "signalk")]

# Register in _PATH_HANDLERS
_PATH_HANDLERS["custom.path.name"] = _custom_path_handler
```

### Custom Bridge Configuration

Create a custom bridge with specific behavior:

```python
class CustomSignalKBridge(SignalKBridge):
    async def ingest_delta(self, delta_data):
        packets = await super().ingest_delta(delta_data)
        # Add custom processing
        for pkt in packets:
            self.log_to_database(pkt)
        return packets
```

### Integration with Twin and Viewer

The Signal K bridge seamlessly integrates with the AELMA twin:

```
Signal K Server → SignalKBridge → TelemetryPackets → Twin → Viewer
                (WebSocket)      (WebSocket)        (State)  (Visualization)
```

**Setup:**
1. Start SignalKBridge on port 8000
2. Configure Twin to connect to `ws://localhost:8000`
3. Twin receives both NMEA and Signal K data
4. Viewer displays unified vessel state

## Reference

- [Signal K Specification](https://signalk.org/specification/1.0.0/doc/index.html)
- [Signal K Delta Updates](https://signalk.org/specification/1.0.0/doc/views/delta_updates.html)
- [Freeboard-SignalK](https://github.com/SignalK/freeboard-signalk)
- [AELMA Architecture](../docs/ARCHITECTURE.md)

## License

This integration is part of AELMA and follows the same license terms.
