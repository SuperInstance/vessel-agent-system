# Fleet Management System

## Overview

The AELMA Fleet Management System enables centralized management of multiple fishing vessels from a single instance. Each vessel runs its own isolated TwinCore instance while the FleetManager provides unified analytics, inter-vessel coordination, and fleet-wide monitoring.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FLEET MANAGER                                  │
│                         (Port 8092)                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   Vessel 1   │  │   Vessel 2   │  │   Vessel 3   │              │
│  │  (Pioneer)   │  │  (Explorer)  │  │  (Surveyor)  │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│         │                  │                  │                       │
│         └──────────────────┴──────────────────┘                       │
│                        │                                              │
│                    Fleet API                                         │
│                                                                       │
│  • Position summaries      • Distance matrices                       │
│  • Clustering detection    • Alert aggregation                       │
│  • Vessel lookup           • Fleet broadcasts                        │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
         │                      │                      │
         ▼                      ▼                      ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Bridge 1     │  │ Bridge 2     │  │ Bridge 3     │
│ (Port 8000)  │  │ (Port 8001)  │  │ (Port 8002)  │
└──────────────┘  └──────────────┘  └──────────────┘
```

## Key Features

### 1. Multi-Vessel Management
- Register and manage multiple vessels from a single fleet manager
- Each vessel has isolated state and data storage
- Independent telemetry logs per vessel
- Shared watcher rules across the fleet

### 2. Fleet-Level Analytics
- **Position Summary**: Fleet bounds (min/max lat/lon) and centroid
- **Clustering Detection**: Identify groups of vessels operating together
- **Distance Matrix**: Inter-vessel distances for coordination
- **Alert Aggregation**: Fleet-wide critical, warning, and info alerts

### 3. Vessel Lookup
- Find nearest vessel to any location
- Find all vessels within a radius
- Query by vessel type or purpose
- Real-time position tracking

### 4. Fleet Operations
- Broadcast actions to all vessels
- Send actions to specific vessels
- Unified WebSocket API for fleet viewers
- Real-time snapshot broadcasts

### 5. Isolated State
- Each vessel has its own `VesselState` instance
- Independent telemetry channels
- Separate bathymetry grids
- Isolated A2A and operations logs

## Components

### FleetManager

The core fleet management class.

```python
from twin.fleet_manager import FleetManager

# Create fleet manager
fleet = FleetManager(
    viewer_port=8092,
    broadcast_interval=1.0,
    data_dir="fleet_data",
)

# Register vessels
fleet.register_vessel("US-AK-FVEILEEN-51", {
    "bridge_url": "ws://localhost:8000",
    "name": "F/V Pioneer",
    "vessel_type": "fishing",
    "viewer_port": 8090,
})
```

### VesselInstance

Container for a single vessel's twin core.

```python
class VesselInstance:
    vessel_id: str
    name: str
    vessel_type: str
    state: VesselState
    bathymetry: BathymetryGrid
    data_dir: Path
    bridge_connected: bool
    last_update: float
```

### FleetServer

Production server with bridge connections.

```python
from twin.fleet_server import FleetServer

# Load from config
server = FleetServer("fleet_config.json")
await server.start()
```

## API Reference

### Vessel Registration

#### register_vessel(vessel_id, config)
Register a new vessel in the fleet.

```python
vessel = fleet.register_vessel("US-AK-FVEILEEN-51", {
    "bridge_url": "ws://localhost:8000",
    "name": "F/V Pioneer",
    "vessel_type": "fishing",
    "viewer_port": 8090,
    "bathymetry_path": "bathymetry.json",
})
```

**Parameters:**
- `vessel_id` (str): Unique vessel identifier
- `config` (dict): Vessel configuration

**Returns:** `VesselInstance`

**Raises:** `ValueError` if vessel already registered

### State Access

#### get_vessel_state(vessel_id)
Get current state snapshot for a vessel.

```python
state = fleet.get_vessel_state("US-AK-FVEILEEN-51")
# Returns: {
#     "vessel_id": "US-AK-FVEILEEN-51",
#     "name": "F/V Pioneer",
#     "pose": {"lat": 59.5, "lon": -152.3, ...},
#     "channels": {...},
#     ...
# }
```

**Returns:** `dict | None`

#### get_all_positions()
Get all vessel positions.

```python
positions = fleet.get_all_positions()
# Returns: {
#     "vessel1": {"lat": 59.5, "lon": -152.3, ...},
#     "vessel2": {"lat": 60.0, "lon": -151.0, ...},
# }
```

**Returns:** `dict[str, dict]`

#### get_fleet_snapshot()
Get comprehensive fleet snapshot.

```python
snapshot = fleet.get_fleet_snapshot()
# Returns: {
#     "timestamp_ns": 1234567890000000000,
#     "vessel_count": 3,
#     "vessels": {...},
#     "analytics": {
#         "position_summary": {...},
#         "clustering": {...},
#         "alerts": {...}
#     }
# }
```

**Returns:** `dict`

### Fleet Analytics

#### get_distance_matrix()
Compute inter-vessel distance matrix.

```python
matrix = fleet.get_distance_matrix()
# Returns: {
#     "vessel1": {
#         "vessel1": 0.0,
#         "vessel2": 1500.5,
#         "vessel3": None,
#     },
#     ...
# }
```

**Returns:** `dict[str, dict[str, float | None]]`

### Vessel Lookup

#### find_nearest(lat, lon, purpose)
Find nearest vessel to a location.

```python
nearest = fleet.find_nearest(59.5, -152.3, "fishing")
# Returns: {
#     "vessel_id": "US-AK-FVEILEEN-51",
#     "name": "F/V Pioneer",
#     "distance_m": 125.3,
#     "position": {"lat": 59.501, "lon": -152.301},
# }
```

**Parameters:**
- `lat` (float): Latitude in degrees
- `lon` (float): Longitude in degrees
- `purpose` (str): Optional purpose filter

**Returns:** `dict | None`

#### find_vessels_in_radius(lat, lon, radius_m)
Find all vessels within a radius.

```python
vessels = fleet.find_vessels_in_radius(59.5, -152.3, 1000)
# Returns: [
#     {"vessel_id": "vessel1", "distance_m": 125.3, ...},
#     {"vessel_id": "vessel2", "distance_m": 845.7, ...},
# ]
```

**Returns:** `list[dict]` sorted by distance

### Fleet Operations

#### broadcast_to_all(action, payload)
Broadcast an action to all vessels.

```python
results = await fleet.broadcast_to_all("return_to_port", {"port": "kodiak"})
# Returns: {
#     "vessel1": {"status": "delivered", "action": "return_to_port", ...},
#     "vessel2": {"status": "delivered", "action": "return_to_port", ...},
# }
```

**Parameters:**
- `action` (str): Action name/type
- `payload` (dict | None): Optional action payload

**Returns:** `dict[str, dict]`

#### send_to_vessel(vessel_id, action, payload)
Send an action to a specific vessel.

```python
result = await fleet.send_to_vessel("US-AK-FVEILEEN-51", "set_watch", {
    "watch_station": "port"
})
```

**Returns:** `dict` with delivery status

### Telemetry Handling

#### handle_telemetry(vessel_id, packet)
Handle a telemetry packet for a specific vessel.

```python
fleet.handle_telemetry("US-AK-FVEILEEN-51", {
    "channel": "position.lat",
    "value": 59.5,
    "timestamp_ns": 1234567890000000000,
})
```

## WebSocket API

### Fleet Viewer Endpoint

Connect to `ws://localhost:8092` to receive real-time fleet snapshots.

**Message Format:**
```json
{
  "timestamp_ns": 1234567890000000000,
  "vessel_count": 3,
  "vessels": {
    "US-AK-FVEILEEN-51": {
      "vessel_id": "US-AK-FVEILEEN-51",
      "name": "F/V Pioneer",
      "pose": {
        "lat": 59.5,
        "lon": -152.3,
        "heading_deg": 45.0,
        "speed_kn": 8.5
      },
      "channels": {...},
      "bridge_connected": true,
      "last_update": 1234567890.0
    }
  },
  "analytics": {
    "position_summary": {
      "min_lat": 59.0,
      "max_lat": 60.5,
      "min_lon": -153.0,
      "max_lon": -151.0,
      "centroid_lat": 59.75,
      "centroid_lon": -152.0
    },
    "active_count": 3,
    "clustering": {
      "clusters": [3],
      "largest_cluster_size": 3,
      "cluster_centers": [[59.75, -152.0]]
    },
    "alerts": {
      "critical": [],
      "warning": ["vessel3: Stale telemetry data"],
      "info": []
    }
  }
}
```

## Configuration

### Fleet Configuration File

Create `fleet_config.json`:

```json
{
  "data_dir": "fleet_data",
  "fleet_viewer_port": 8092,
  "broadcast_interval": 1.0,
  "vessels": {
    "US-AK-FVEILEEN-51": {
      "bridge_url": "ws://localhost:8000",
      "name": "F/V Pioneer",
      "vessel_type": "fishing",
      "viewer_port": 8090,
      "bathymetry_path": "bathymetry_pioneer.json",
      "a2a_log_path": "a2a_pioneer.jsonl",
      "oplog_path": "oplog_pioneer.jsonl",
      "viewport_radius_m": 500.0
    }
  }
}
```

### Configuration Fields

**Top-level:**
- `data_dir`: Base directory for vessel data
- `fleet_viewer_port`: Port for fleet WebSocket API
- `broadcast_interval`: Seconds between snapshot broadcasts

**Per-vessel:**
- `bridge_url`: WebSocket URL to vessel's bridge
- `name`: Human-readable vessel name
- `vessel_type`: Type of vessel (fishing, research, etc.)
- `viewer_port`: Port for vessel's individual viewer
- `bathymetry_path`: Path to bathymetry data file
- `a2a_log_path`: Path to A2A log file
- `oplog_path`: Path to operations log file
- `viewport_radius_m`: Bathymetry viewport radius in meters

## Usage Examples

### Starting the Fleet Server

```bash
# Using configuration file
python -m twin.fleet_server --config fleet_config.json

# Override port
python -m twin.fleet_server --config fleet_config.json --port 8093

# With debug logging
python -m twin.fleet_server --config fleet_config.json --log-level DEBUG
```

### Monitoring the Fleet

```bash
# Connect to fleet viewer for 60 seconds
python examples/fleet_viewer.py --url ws://localhost:8092 --duration 60

# Monitor indefinitely
python examples/fleet_viewer.py --url ws://localhost:8092 --duration 0
```

### Programmatic Usage

```python
import asyncio
from twin.fleet_manager import FleetManager

async def main():
    # Create fleet manager
    fleet = FleetManager(viewer_port=8092, data_dir="fleet_data")

    # Register vessels
    fleet.register_vessel("vessel1", {
        "bridge_url": "ws://localhost:8000",
        "name": "F/V Pioneer",
        "vessel_type": "fishing",
    })

    fleet.register_vessel("vessel2", {
        "bridge_url": "ws://localhost:8001",
        "name": "F/V Explorer",
        "vessel_type": "fishing",
    })

    # Get fleet status
    snapshot = fleet.get_fleet_snapshot()
    print(f"Fleet has {snapshot['vessel_count']} vessels")

    # Find nearest vessel to location
    nearest = fleet.find_nearest(59.5, -152.3)
    if nearest:
        print(f"Nearest: {nearest['name']} at {nearest['distance_m']}m")

    # Get distance matrix
    matrix = fleet.get_distance_matrix()
    print("Inter-vessel distances:", matrix)

    # Broadcast to all vessels
    await fleet.broadcast_to_all("return_to_port", {"port": "kodiak"})

    # Start fleet viewer server
    await fleet.run()

if __name__ == "__main__":
    asyncio.run(main())
```

## Data Storage

### Directory Structure

```
fleet_data/
├── US-AK-FVEILEEN-51/
│   ├── bathymetry_pioneer.json
│   ├── a2a_pioneer.jsonl
│   └── oplog_pioneer.jsonl
├── US-AK-EXPLORER-42/
│   ├── bathymetry_explorer.json
│   ├── a2a_explorer.jsonl
│   └── oplog_explorer.jsonl
└── US-AK-SURVEYOR-07/
    ├── bathymetry_surveyor.json
    ├── a2a_surveyor.jsonl
    └── oplog_surveyor.jsonl
```

### Isolated State

Each vessel maintains:
- **VesselState**: Independent telemetry channels
- **BathymetryGrid**: Separate bathymetry data
- **A2ALog**: Vessel-specific action logs
- **OpLog**: Vessel-specific operations logs
- **Metrics**: Per-vessel performance metrics

## Fleet Analytics

### Position Summary

```python
analytics = snapshot["analytics"]
summary = analytics["position_summary"]

print(f"Fleet bounds:")
print(f"  Latitude: {summary['min_lat']} to {summary['max_lat']}")
print(f"  Longitude: {summary['min_lon']} to {summary['max_lon']}")
print(f"  Centroid: {summary['centroid_lat']}, {summary['centroid_lon']}")
```

### Clustering Detection

Vessels within 1000m of each other are grouped into clusters.

```python
clustering = analytics["clustering"]
print(f"Clusters found: {clustering['clusters']}")
print(f"Largest cluster: {clustering['largest_cluster_size']} vessels")
print(f"Cluster centers: {clustering['cluster_centers']}")
```

### Alert Aggregation

```python
alerts = analytics["alerts"]

print(f"Critical alerts: {len(alerts['critical'])}")
for alert in alerts['critical']:
    print(f"  ! {alert}")

print(f"Warnings: {len(alerts['warning'])}")
for warning in alerts['warning']:
    print(f"  ! {warning}")
```

## Testing

### Running Tests

```bash
# Run all fleet manager tests
pytest tests/fleet_manager.test.py -v

# Run specific test
pytest tests/fleet_manager.test.py::TestFleetManager::test_register_vessel -v

# With coverage
pytest tests/fleet_manager.test.py --cov=twin.fleet_manager --cov-report=html
```

### Test Coverage

The test suite covers:
- Vessel registration and lifecycle
- State access and telemetry handling
- Fleet analytics (position summary, clustering, alerts)
- Distance matrix computation
- Vessel lookup (nearest, radius search)
- Fleet operations (broadcast, send to vessel)
- WebSocket API (viewer handler, broadcast loop)
- Status and lifecycle management
- Isolated state between vessels

## Performance Considerations

### Scalability

- **Vessels**: Tested with 10+ vessels, design scales to 100+
- **Telemetry**: Handles 1000+ packets/second per vessel
- **Viewers**: Supports 100+ concurrent WebSocket connections
- **Memory**: ~100MB per vessel (bathymetry + state)

### Optimization

- Position updates use dead-reckoning to reduce compute
- Clustering uses efficient spatial queries
- WebSocket broadcasts use async gathering
- Distance matrix computed on-demand and cached

## Troubleshooting

### Common Issues

**Vessel not receiving telemetry:**
```python
# Check vessel is registered
if "vessel1" not in fleet.vessels:
    print("Vessel not registered")

# Check bridge connection
vessel = fleet.get_vessel("vessel1")
if not vessel.bridge_connected:
    print("Bridge disconnected")

# Check last update
if time.time() - vessel.last_update > 300:
    print("Stale data (>5 minutes)")
```

**WebSocket connection failed:**
```bash
# Check fleet server is running
curl http://localhost:8092/

# Check port is not in use
netstat -an | grep 8092

# Verify firewall allows connection
```

**High memory usage:**
- Reduce `viewport_radius_m` per vessel
- Limit `persist_interval` to save data less frequently
- Archive old A2A and oplog files

## Future Enhancements

### Planned Features

1. **Dynamic Vessel Registration**
   - Add/remove vessels while fleet manager is running
   - Hot-reload configuration changes
   - Auto-discovery of bridges on local network

2. **Advanced Analytics**
   - Fleet-wide catch statistics aggregation
   - Gear deployment coordination
   - Route optimization across fleet

3. **Alert Routing**
   - Forward alerts to specific vessels
   - Escalation chains (vessel → fleet → shore)
   - Integration with satellite/Internet uplinks

4. **Data Export**
   - Export fleet position history (CSV/JSON)
   - Generate fleet analytics reports
   - Archive vessel logs to cloud storage

## License

See LICENSE file for details.

## Support

For issues, questions, or contributions, see the main AELMA repository.
