# Tide Prediction System for AELMA

## Overview

The AELMA tide prediction system provides real-time water level calculations for fishing vessels using harmonic constituent analysis. The system automatically calculates tide levels on position updates and includes them in the vessel state snapshot, enabling tide-aware navigation and safety checks.

## Features

- **Harmonic Tide Prediction**: Uses 6 major tidal constituents (M2, S2, O1, K1, N2, P1) for accurate semi-diurnal tide patterns
- **Automatic Calculation**: Tide levels are calculated automatically on position updates
- **Depth Clearance Checking**: Real-time under-keel clearance verification with configurable safety margins
- **Safe Passage Planning**: Identify safe transit windows based on tide predictions
- **High/Low Tide Events**: Automatic detection and prediction of next high and low tides
- **Low Water Alerts**: Watcher rules that alert when approaching low water conditions
- **Location-Aware**: Tidal amplitude scales with latitude (higher ranges at higher latitudes)

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    TWIN CORE                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              TidePredictor                                   │ │
│  │  • predict_tide(lat, lon, timestamp)                        │ │
│  │  • get_tide_range(start, end)                               │ │
│  │  • check_depth_clearance(draft, depth)                      │ │
│  │  • get_safe_passage_window(...)                              │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌──────────────────┐      ┌─────────────────────────────────┐ │
│  │  Watcher Rules   │      │  VesselStateSnapshot             │ │
│  │                  │      │                                 │ │
│  │ • Low water      │◄─────┤ • tide.current_level_m          │ │
│  │   alert          │      │ • tide.next_high_tide            │ │
│  │ • Depth          │      │ • tide.next_low_tide             │ │
│  │   clearance      │      │ • tide.confidence                │ │
│  └──────────────────┘      └─────────────────────────────────┘ │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Integration Points

1. **TwinCore Initialization**: Tide predictor is initialized on startup
2. **Position Updates**: Tide is calculated when vessel position is known
3. **Snapshot Assembly**: Tide data is included in every VesselStateSnapshot
4. **Watcher Evaluation**: Low water and depth clearance watcher rules
5. **Viewer Broadcast**: Tide information is broadcast to all connected viewers

## Harmonic Constituents

The system uses 6 major tidal constituents based on NOAA methodology:

| Constituent | Description | Period (hours) | Amplitude (relative) |
|-------------|-------------|----------------|---------------------|
| **M2** | Principal lunar semidiurnal | 12.42 | 1.0 (dominant) |
| **S2** | Principal solar semidiurnal | 12.00 | 0.3 |
| **O1** | Lunar diurnal | 25.82 | 0.2 |
| **K1** | Lunar diurnal | 23.93 | 0.15 |
| **N2** | Larger lunar elliptic semidiurnal | 12.66 | 0.2 |
| **P1** | Principal solar diurnal | 24.07 | 0.1 |

### Water Level Calculation

```
water_level = datum + Σ(amplitude_i × sin(phase_i))
```

Where:
- `datum` = MLLW (Mean Lower Low Water) reference
- `amplitude_i` = scaled by location and spring/neap cycle
- `phase_i` = function of constituent frequency and lunar time

### Location Scaling

- **Latitude Factor**: Higher latitudes have larger tidal ranges
  - `factor = 1.0 + 0.003 × |latitude|`
- **Spring/Neap Cycle**: Varies with lunar phase
  - `factor = 0.8 + 0.4 × cos(lunar_phase)`

## Usage

### Basic Tide Prediction

```python
from twin.tide_predictor import TidePredictor
from datetime import datetime, timezone

# Initialize predictor
predictor = TidePredictor(base_amplitude=2.0, datum_mllw_m=0.0)

# Predict tide at location and time
lat, lon = 59.5, -152.3  # Kodiak Island, Alaska
now = datetime.now(timezone.utc)

tide = predictor.predict_tide(lat, lon, now)
print(f"Water level: {tide.water_level_m:.2f}m MLLW")
print(f"Confidence: {tide.confidence:.2f}")
```

### Get Tide Range (High/Low Tides)

```python
# Get tide events for next 24 hours
events = predictor.get_tide_range(
    lat, lon,
    start_time=now,
    duration_hours=24
)

for event in events:
    print(f"{event.event_type.upper()} tide: {event.level_m:.2f}m at {event.timestamp}")
```

### Check Depth Clearance

```python
# Check if vessel can safely transit
vessel_draft = 2.5  # meters
chart_depth = 5.0  # meters (MLLW)

clearance = predictor.check_depth_clearance(
    vessel_draft_m=vessel_draft,
    chart_depth_m=chart_depth,
    lat=lat,
    lon=lon,
    timestamp=now,
    safety_margin_m=1.0  # 1m under-keel clearance required
)

if clearance["clearance_ok"]:
    print(f"Safe: {clearance['under_keel_clearance_m']:.2f}m clearance")
else:
    print(f"DANGER: Only {clearance['under_keel_clearance_m']:.2f}m clearance!")
```

### Safe Passage Planning

```python
# Find safe transit windows
analysis = predictor.get_safe_passage_window(
    vessel_draft_m=2.5,
    chart_depth_m=5.0,
    lat=lat,
    lon=lon,
    start_time=now,
    window_hours=12,
    safety_margin_m=1.0
)

print(f"Total safe time: {analysis['total_safe_minutes']} minutes")
print(f"Safe windows: {len(analysis['safe_windows'])}")

for window in analysis["safe_windows"]:
    print(f"  {window['start']} to {window['end']} ({window['duration_minutes']} min)")
```

### Next High/Low Tides

```python
# Get next high and low tides
next_tides = predictor.get_next_high_low_tides(lat, lon, now)

if next_tides["next_high_tide"]:
    high = next_tides["next_high_tide"]
    print(f"Next HIGH: {high['level_m']:.2f}m in {high['hours_from_now']:.1f}h")

if next_tides["next_low_tide"]:
    low = next_tides["next_low_tide"]
    print(f"Next LOW: {low['level_m']:.2f}m in {low['hours_from_now']:.1f}h")
```

## TwinCore Integration

### Configuration

The tide predictor is configured in TwinCore initialization:

```python
from twin.core import TwinCore

twin = TwinCore(
    # ... other parameters ...
    enable_tide_prediction=True,
    tide_amplitude_m=2.0,      # Base tidal amplitude for region
    tide_datum_mllw_m=0.0,    # MLLW datum offset
)
```

### VesselStateSnapshot

Tide information is automatically included in snapshots:

```json
{
  "timestamp_ns": 1234567890000000000,
  "vessel_id": "US-AK-FVEILEEN-51",
  "pose": {
    "lat": 59.5,
    "lon": -152.3,
    "heading_deg": 180.0,
    "speed_kn": 5.5
  },
  "tide": {
    "current_level_m": 1.23,
    "timestamp": "2026-07-28T10:30:00Z",
    "confidence": 0.85,
    "next_high_tide": {
      "timestamp": "2026-07-28T16:45:00Z",
      "level_m": 2.34,
      "hours_from_now": 6.25
    },
    "next_low_tide": {
      "timestamp": "2026-07-28T22:30:00Z",
      "level_m": -0.87,
      "hours_from_now": 12.0
    }
  }
}
```

### Watcher Rules

#### Low Water Alert

```python
{
    "id": "low-water-alert",
    "name": "Low water alert",
    "when": lambda f: f.get("tide_level_m", 0) < -0.5,
    "action": {
        "name": "raise_alert",
        "payload": {
            "severity": "warning",
            "code": "LOW_WATER",
            "message": "Low water approaching"
        }
    },
    "cooldown_s": 300.0
}
```

#### Depth Clearance Warning

```python
{
    "id": "tide-depth-clearance",
    "name": "Tide-aware depth clearance",
    "when": lambda f: f.get("water_depth_m", 999) < 3.0,
    "action": {
        "name": "raise_alert",
        "payload": {
            "severity": "warning",
            "code": "TIDE_DEPTH_CLEARANCE",
            "message": "Reduced clearance at low tide"
        }
    },
    "cooldown_s": 180.0
}
```

## Regional Configuration

### Pacific Northwest (Alaska)

```python
# High tidal ranges (3-5m)
predictor = TidePredictor(
    base_amplitude=3.5,
    datum_mllw_m=0.0
)
```

### Atlantic Coast (Maine)

```python
# Moderate tidal ranges (2-3m)
predictor = TidePredictor(
    base_amplitude=2.5,
    datum_mllw_m=0.0
)
```

### Gulf Coast

```python
# Lower tidal ranges (0.5-1m)
predictor = TidePredictor(
    base_amplitude=0.75,
    datum_mllw_m=0.0
)
```

## Accuracy and Limitations

### Confidence Levels

The system provides confidence estimates for predictions:

- **0.85+**: High confidence - Standard coastal locations
- **0.70-0.85**: Moderate confidence - Offshore or complex areas
- **< 0.70**: Lower confidence - Very high latitudes or unusual locations

### Limitations

1. **No Storm Surge**: Predictions don't include weather-induced water level changes
2. **No River Flow**: Doesn't account for freshwater discharge in estuaries
3. **Simplified Bathymetry**: Doesn't model local bathymetric effects
4. **No Sea Level Rise**: Uses fixed datum (MLLW)
5. **Approximate Phasing**: Lunar phase calculation is simplified

### Best Practices

1. **Always use chart depth (MLLW)** as the basis for calculations
2. **Add safety margin** (typically 1.0-1.5m for fishing vessels)
3. **Verify with local observations** when first using in new area
4. **Cross-reference with official tide tables** when critical
5. **Monitor weather conditions** for storm surge effects

## API Reference

### TidePredictor Class

#### `__init__(base_amplitude=2.0, datum_mllw_m=0.0)`

Initialize tide predictor.

**Parameters:**
- `base_amplitude` (float): Base tidal amplitude in meters (default: 2.0m)
- `datum_mllw_m` (float): MLLW datum offset in meters (default: 0.0)

#### `predict_tide(lat, lon, timestamp)`

Predict water level at location and time.

**Parameters:**
- `lat` (float): Latitude in decimal degrees
- `lon` (float): Longitude in decimal degrees
- `timestamp` (datetime): Prediction time (None for current time)

**Returns:**
- `TidePrediction`: Prediction object with water_level_m, confidence, etc.

#### `get_tide_range(lat, lon, start_time, duration_hours=24)`

Get high/low tide events for a period.

**Parameters:**
- `lat, lon` (float): Location coordinates
- `start_time` (datetime): Start of prediction period
- `duration_hours` (float): Length of period in hours (default: 24)

**Returns:**
- `list[TideEvent]`: List of high/low tide events in chronological order

#### `check_depth_clearance(vessel_draft_m, chart_depth_m, lat, lon, timestamp, safety_margin_m=1.0)`

Check if vessel has adequate depth clearance.

**Parameters:**
- `vessel_draft_m` (float): Vessel draft in meters
- `chart_depth_m` (float): Chart datum depth (MLLW) in meters
- `lat, lon` (float): Location coordinates
- `timestamp` (datetime): Time to check clearance (None for current time)
- `safety_margin_m` (float): Required under-keel clearance (default: 1.0m)

**Returns:**
- `dict`: Clearance check result with status, water depth, and clearance

#### `get_safe_passage_window(vessel_draft_m, chart_depth_m, lat, lon, start_time, window_hours=12, safety_margin_m=1.0)`

Find safe passage windows based on tide predictions.

**Parameters:**
- `vessel_draft_m` (float): Vessel draft in meters
- `chart_depth_m` (float): Chart datum depth in meters
- `lat, lon` (float): Location coordinates
- `start_time` (datetime): Start time for analysis
- `window_hours` (float): Analysis period in hours (default: 12)
- `safety_margin_m` (float): Required safety margin (default: 1.0m)

**Returns:**
- `dict`: Safe passage analysis with windows, tide events, and statistics

#### `get_next_high_low_tides(lat, lon, from_time)`

Get next high and low tide events after specified time.

**Parameters:**
- `lat, lon` (float): Location coordinates
- `from_time` (datetime): Search start time (None for current time)

**Returns:**
- `dict`: Next high and low tide predictions with timestamps and levels

## Testing

Run the comprehensive test suite:

```bash
# Run all tide predictor tests
python -m pytest tests/tide_predictor.test.py -v

# Run specific test class
python -m pytest tests/tide_predictor.test.py::TestTidePredictorBasics -v

# Run with coverage
python -m pytest tests/tide_predictor.test.py --cov=twin.tide_predictor --cov-report=html
```

## References

- **NOAA Tide Predictions**: https://tidesandcurrents.noaa.gov/
- **Harmonic Constituent Analysis**: https://tidesandcurrents.noaa.gov/harmonic_constitutions.html
- **NOAA Tide Prediction Methodology**: https://opendap.co-ops.nos.noaa.gov/algorithms/
- **MLLW Datum**: https://tidesandcurrents.noaa.gov/datum_options.html
- **Tidal Constituents**: https://en.wikipedia.org/wiki/Theory_of_tides#Tidal_constituents

## Changelog

### Version 1.0 (2026-07-28)

- Initial tide prediction system
- Harmonic constituent analysis with 6 major constituents
- Integration with TwinCore and VesselStateSnapshot
- Depth clearance checking
- Safe passage window analysis
- Watcher rules for low water alerts
- Comprehensive test suite
