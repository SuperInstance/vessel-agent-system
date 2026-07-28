# AELMA Trip Summary System

Comprehensive trip analytics and reporting system for the AELMA digital twin.

## Overview

The TripSummary system accumulates telemetry, operational, and alert data throughout a vessel's journey to generate comprehensive trip reports. It supports multiple export formats and integrates seamlessly with the TwinCore runtime.

## Features

- **Automatic Data Accumulation**: Continuously aggregates telemetry data without manual intervention
- **Multi-Format Export**: JSON, HTML, and plain text report generation
- **Comprehensive Statistics**: Distance, depth, fishing modes, alerts, catch, fuel, and weather
- **TwinCore Integration**: Fully integrated with the digital twin runtime
- **Flexible API**: Programmatic access to all summary data

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        TwinCore                              │
│  ┌───────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ VesselState   │  │ FishingModes │  │ TripSummary     │  │
│  │               │  │              │  │                 │  │
│  │ • position    │→ │ • mode       │→ │ • telemetry     │  │
│  │ • depth       │  │   changes    │  │ • positions     │  │
│  │ • speed       │  │              │  │ • alerts       │  │
│  └───────────────┘  └──────────────┘  │ • catch        │  │
│                                       │ • fuel         │  │
│                                       │ • weather      │  │
│                                       └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                                   │
         ↓                                   ↓
    Telemetry Query                    Export Methods
    • Streaming analytics               • JSON
    • Statistics                        • HTML
    • Percentiles                        • Text
```

## Components

### TripSummary Class

Main accumulator class that aggregates data from multiple sources.

```python
from build_kimi.twin.trip_summary import TripSummary

summary = TripSummary(vessel_id="US-AK-FVEILEEN-51")
summary.add_telemetry({...})
summary.add_oplog_entry({...})
summary.add_a2a_action({...})
result = summary.generate_summary()
```

### Data Accumulators

- **AlertSummary**: Tracks alerts by severity, code, and priority
- **ModeTimeSummary**: Accumulates time spent in each fishing mode
- **CatchStatistics**: Records catch data by species and weight
- **FuelStatistics**: Monitors fuel consumption and engine hours
- **WeatherSummary**: Tracks wind and wave conditions
- **PositionHistory**: Calculates distance traveled from position fixes

## Usage

### Basic Usage

```python
from build_kimi.twin.core import TwinCore

# Initialize TwinCore (includes TripSummary)
twin = TwinCore(
    vessel_id="US-AK-FVEILEEN-51",
    telemetry_log_path="telemetry.jsonl",
)

# Run the twin (automatically accumulates data)
await twin.run()

# Get trip summary
summary = twin.get_trip_summary()
print(f"Distance: {summary['distance']['total_distance_nm']:.2f} nm")
print(f"Duration: {summary['trip']['duration_h']:.2f} hours")
```

### Manual Accumulation

```python
from build_kimi.twin.trip_summary import TripSummary

summary = TripSummary(vessel_id="FV-EXAMPLE-01")

# Add telemetry data
summary.add_telemetry({
    "timestamp_ns": 1_753_478_400_000_000_000,
    "channel": "depth_m",
    "value": 73.2,
})

# Add crew operations
summary.add_oplog_entry({
    "action": "log_catch",
    "timestamp_ns": 1_753_478_500_000_000_000,
    "species": "Salmon",
    "weight_kg": 150.0,
})

# Add automated actions
summary.add_a2a_action({
    "action": "raise_alert",
    "priority": 0.9,
    "payload": {
        "severity": "critical",
        "code": "GROUNDING_RISK",
    },
})

# Generate summary
result = summary.generate_summary()
```

### Export Formats

#### JSON Export

```python
# Export as JSON (default)
twin.export_trip_summary("json", "trip_report.json")

# Or directly from TripSummary
summary.export_json("trip_report.json")
```

Output structure:
```json
{
  "vessel_id": "US-AK-FVEILEEN-51",
  "trip": {
    "start_timestamp_ns": 1753478400000000000,
    "end_timestamp_ns": 1753492000000000000,
    "duration_h": 3.75
  },
  "distance": {
    "total_distance_nm": 45.2,
    "total_distance_km": 83.7,
    "position_count": 234
  },
  "depth": {
    "min_m": 12.5,
    "max_m": 185.3,
    "avg_m": 78.4,
    "reading_count": 1523
  },
  "fishing_modes": {
    "mode_durations_h": {
      "TRANSIT": 1.5,
      "FISHING": 2.0,
      "HAULING": 0.25
    },
    "mode_durations_pct": {
      "TRANSIT": 40.0,
      "FISHING": 53.3,
      "HAULING": 6.7
    }
  },
  "alerts": {
    "total_count": 12,
    "critical_count": 2,
    "warning_count": 8,
    "info_count": 2
  },
  "catch": {
    "total_catch_kg": 1250.0,
    "haul_count": 15,
    "avg_haul_kg": 83.3,
    "species_counts": {
      "Salmon": 8,
      "Cod": 7
    }
  }
}
```

#### HTML Export

```python
# Export as HTML report
twin.export_trip_summary("html", "trip_report.html")

# Or directly from TripSummary
summary.export_html("trip_report.html")
```

Generates a formatted HTML report with:
- Trip overview table
- Depth statistics
- Fishing mode breakdown
- Alert summary
- Catch statistics
- Data quality metrics

#### Text Export

```python
# Export as plain text
twin.export_trip_summary("text", "trip_report.txt")

# Or directly from TripSummary
summary.export_text("trip_report.txt")
```

Generates a human-readable text report with all statistics.

## TwinCore API Methods

### get_trip_summary()

Generate comprehensive trip summary.

```python
summary = twin.get_trip_summary()
```

Returns dict with:
- `trip`: Duration, timestamps
- `distance`: Total distance traveled
- `depth`: Min/max/avg depth
- `fishing_modes`: Time in each mode
- `alerts`: Alert counts by severity
- `catch`: Catch statistics
- `fuel`: Fuel consumption
- `weather`: Wind and wave data
- `crew_actions`: Crew operation log
- `automated_actions`: A2A action log
- `data_quality`: Data completeness metrics

### export_trip_summary(format, path)

Export trip summary to file.

```python
# With default path
twin.export_trip_summary("json")

# With custom path
twin.export_trip_summary("html", "/path/to/report.html")

# Supported formats: "json", "html", "text"
```

### log_catch(species, weight_kg)

Log catch data into trip summary.

```python
twin.log_catch("Salmon", 150.0)
twin.log_catch("Cod", 200.0)

# Automatically accumulates into trip summary
summary = twin.get_trip_summary()
print(summary["catch"]["total_catch_kg"])  # 350.0
```

## Telemetry Channels Used

The TripSummary system automatically processes these telemetry channels:

### Position & Navigation
- `position.lat` - Latitude (decimal degrees)
- `position.lon` - Longitude (decimal degrees)

### Depth
- `depth_m` - Depth below surface (meters)

### Weather
- `wind_speed_kn` - Wind speed (knots)
- `wave_height_m` - Significant wave height (meters)

### Engine
- `engine_fuel_rate_lh` - Fuel consumption rate (liters/hour)

## Data Flow

```
Telemetry Packets
        │
        ↓
TwinCore.handle_packet()
        │
        ├─→ VesselState (current state)
        ├─→ BathymetryGrid (depth grid)
        ├─→ WatcherRegistry (alert rules)
        └─→ TripSummary (accumulation)
                    │
                    ├─→ add_telemetry()
                    ├─→ add_a2a_action() [from fired rules]
                    └─→ add_mode_duration() [from mode changes]
```

## Statistics Calculated

### Trip Duration
- Start timestamp (first telemetry packet)
- End timestamp (last telemetry packet)
- Total duration in seconds, minutes, hours

### Distance Traveled
- Great-circle distance between position fixes
- Accumulated for all position pairs
- Reported in meters, kilometers, nautical miles

### Depth Statistics
- Minimum depth
- Maximum depth
- Average depth
- Reading count

### Fishing Mode Time
- Total duration in each mode
- Percentage of trip per mode
- Number of entries into each mode

### Alerts
- Total count
- Count by severity (critical, warning, info)
- Count by alert code
- Highest priority alert

### Catch Statistics (if logged)
- Total catch weight
- Number of hauls
- Average haul weight
- Best haul weight
- Species breakdown

### Fuel Consumption (if engine data available)
- Total fuel consumed (liters)
- Engine hours
- Average consumption rate (L/h)
- Maximum consumption rate (L/h)

### Weather Conditions (if available)
- Wind speed: min, max, avg
- Wave height: min, max, avg

### Data Quality
- Telemetry record count
- Position fix count
- Depth reading count
- Weather reading counts

## Integration with TelemetryQuery

The TripSummary can work with historical telemetry data:

```python
from build_kimi.twin.telemetry_query import TelemetryQuery
from build_kimi.twin.trip_summary import TripSummary

# Query historical telemetry
query = TelemetryQuery("telemetry.jsonl")

# Accumulate into summary
summary = TripSummary(vessel_id="US-AK-FVEILEEN-51")

for record in query.filter():
    summary.add_telemetry({
        "timestamp_ns": record.timestamp_ns,
        "channel": record.channel,
        "value": record.value,
    })

# Generate historical trip summary
result = summary.generate_summary()
```

## Best Practices

### 1. Automatic Accumulation

Let TwinCore handle automatic accumulation:

```python
# Good - automatic
twin = TwinCore(vessel_id="FV-01")
await twin.run()
summary = twin.get_trip_summary()

# Manual - only for special cases
summary = TripSummary()
for packet in packets:
    summary.add_telemetry(packet)
```

### 2. Export During Operation

Export summaries periodically during long trips:

```python
import asyncio

async def run_with_periodic_exports(twin, interval_hours=6):
    """Run twin with periodic summary exports."""
    task = asyncio.create_task(twin.run())

    while True:
        await asyncio.sleep(interval_hours * 3600)
        timestamp = time.time_ns()
        twin.export_trip_summary("json", f"summary_{timestamp}.json")

    await task
```

### 3. Data Quality Monitoring

Check data quality before relying on summary:

```python
summary = twin.get_trip_summary()

# Verify sufficient data
quality = summary["data_quality"]
if quality["position_fixes"] < 10:
    print("Warning: Limited position data")
if quality["depth_readings"] == 0:
    print("Warning: No depth data available")
```

### 4. Catch Logging

Log catches promptly for accurate records:

```python
# In crew interface or automation
def on_catch_logged(species, weight_kg):
    twin.log_catch(species, weight_kg)

# Example automation
if haul_complete:
    estimated_weight = estimate_catch_weight()
    twin.log_catch("Salmon", estimated_weight)
```

## Performance Considerations

- **Memory**: TripSummary stores aggregated data, not raw telemetry. Memory usage is O(1) for most channels.
- **Position History**: Stores position fix tuples. For multi-day trips with high-frequency updates, this may grow large.
- **Distance Calculation**: Uses haversine formula. Accurate to <0.5% for typical fishing trip distances.
- **Export**: JSON export is fastest. HTML/text export involves additional formatting.

## Error Handling

```python
try:
    summary = twin.get_trip_summary()
except Exception as e:
    log.error(f"Failed to generate summary: {e}")

# Export with validation
try:
    twin.export_trip_summary("json", "/path/to/report.json")
except OSError as e:
    log.error(f"Failed to write summary: {e}")
except ValueError as e:
    log.error(f"Invalid export format: {e}")
```

## Testing

Comprehensive test suite in `tests/test_trip_summary.py`:

```bash
# Run all trip summary tests
pytest tests/test_trip_summary.py -v

# Run specific test class
pytest tests/test_trip_summary.py::TestTripSummaryGeneration -v

# Run with coverage
pytest tests/test_trip_summary.py --cov=build_kimi.twin.trip_summary
```

## Files

- `build_kimi/twin/trip_summary.py` - Main implementation
- `build_kimi/twin/core.py` - TwinCore integration
- `build_kimi/tests/test_trip_summary.py` - Test suite
- `build_kimi/docs/trip_summary.md` - This documentation

## Dependencies

- Python 3.8+
- Standard library only (no external dependencies)
- Integrated with TwinCore, FishingModeManager, TelemetryQuery

## Future Enhancements

Potential improvements for future versions:

1. **Custom Metrics**: User-defined accumulator functions
2. **Comparison Mode**: Compare multiple trips side-by-side
3. **Trend Analysis**: Track patterns across multiple trips
4. **Visualization Integration**: Direct plotting with matplotlib/plotly
5. **Database Backend**: Persistent storage for large fleets
6. **Real-time Dashboards**: WebSocket streaming of live summary updates

## Example: Complete Trip Workflow

```python
import asyncio
from build_kimi.twin.core import TwinCore

async def fishing_trip_example():
    """Complete fishing trip with trip summary."""

    # Initialize twin
    twin = TwinCore(
        vessel_id="FV-SALMON-QUEEN",
        telemetry_log_path="logs/telemetry.jsonl",
    )

    # Start twin in background
    task = asyncio.create_task(twin.run())

    try:
        # Simulate trip operations
        await asyncio.sleep(60)  # 1 minute of operation

        # Change to fishing mode
        twin.set_fishing_mode("FISHING", "Arrived at fishing grounds")

        # Log catches
        twin.log_catch("Salmon", 125.0)
        twin.log_catch("Salmon", 140.0)

        await asyncio.sleep(60)  # Continue fishing

        # Change to hauling mode
        twin.set_fishing_mode("HAULING", "Gear retrieval complete")

        await asyncio.sleep(30)  # Transit back

    finally:
        # Cancel twin task
        task.cancel()

        # Export final summary
        summary = twin.get_trip_summary()

        print(f"Trip Duration: {summary['trip']['duration_h']:.2f} hours")
        print(f"Distance: {summary['distance']['total_distance_nm']:.2f} nm")
        print(f"Total Catch: {summary['catch']['total_catch_kg']:.2f} kg")
        print(f"Alerts: {summary['alerts']['total_count']}")

        # Export in all formats
        twin.export_trip_summary("json", "trip_report.json")
        twin.export_trip_summary("html", "trip_report.html")
        twin.export_trip_summary("text", "trip_report.txt")

# Run the example
asyncio.run(fishing_trip_example())
```

## Conclusion

The TripSummary system provides comprehensive trip analytics for AELMA digital twins. It automatically accumulates data from telemetry, operations, and automated actions to generate detailed reports in multiple formats. Fully integrated with TwinCore, it offers both automatic and manual data collection modes to suit various operational workflows.
