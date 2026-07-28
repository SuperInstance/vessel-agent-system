# Fishing Quota Management System

## Overview

The Fishing Quota Management System is a comprehensive quota tracking and catch management system for Alaska commercial fishing vessels in the AELMA marine digital twin. It provides real-time quota monitoring, catch logging, validation, analytics, and alert generation for regulatory compliance and operational efficiency.

## Features

- **Species-Based Quota Tracking**: Support for key Alaska species (salmon, halibut, cod, crab)
- **Catch Logging**: Automatic quota deduction with location, gear, and crew tracking
- **Quota Validation**: Prevents over-catching with reserve buffer support
- **Analytics & Projections**: Catch rates, exhaustion dates, bycatch reporting
- **Alert System**: Threshold-based alerts at 80%, 90%, 95%, and 100% quota usage
- **Persistence**: JSONL storage for quotas and catch events
- **Integration**: TwinCore, WatcherRegistry, and OpLog integration

## Supported Species

| Category | Species Code | Common Name |
|----------|-------------|-------------|
| Salmon | `chinook` | King salmon |
| Salmon | `coho` | Silver salmon |
| Salmon | `sockeye` | Red salmon |
| Salmon | `pink` | Humpy salmon |
| Salmon | `chum` | Dog salmon |
| Groundfish | `halibut` | Pacific halibut |
| Groundfish | `cod` | Pacific cod |
| Groundfish | `black_cod` | Sablefish |
| Shellfish | `crab` | General crab |
| Shellfish | `king_crab` | King crab |
| Shellfish | `snow_crab` | Snow crab |
| Shellfish | `dungeness_crab` | Dungeness crab |

## Quota Sources

- **IFQ**: Individual Fishing Quota
- **CDQ**: Community Development Quota
- **community**: Community quota share
- **state**: State-allocated quota
- **federal**: Federally-managed quota

## Installation

The quota manager is integrated into `twin/core.py` and enabled by default:

```python
from twin.core import TwinCore

# Quota manager enabled by default
core = TwinCore(
    vessel_id="US-AK-FVEILEEN-51",
    quota_path="quota",  # Directory for JSONL files
    quota_enabled=True,
)

# Access quota manager
quota_manager = core.quota
```

## Quick Start

### 1. Set Species Quotas

```python
# Set quota for chinook salmon
quota_manager.set_species_quota(
    species="chinook",
    total_limit_lb=1000.0,
    reserve_percent=10.0,  # Safety buffer
    quota_source="IFQ",
    expiry_date="2026-12-31T23:59:59.000000+00:00",
)

# Set quota for halibut
quota_manager.set_species_quota(
    species="halibut",
    total_limit_lb=500.0,
    reserve_percent=15.0,
    quota_source="CDQ",
)
```

### 2. Log Catch Events

```python
# Log a catch event
catch = quota_manager.log_catch(
    species="chinook",
    weight_lb=15.5,
    lat=57.0531,
    lon=-135.3300,
    gear_type="purse_seine",
    crew_member="captain",
)

print(f"Catch ID: {catch.catch_id}")
print(f"Remaining chinook quota: {quota_manager.get_remaining_quota('chinook')} lb")
```

### 3. Check Quota Status

```python
# Get comprehensive quota status
status = quota_manager.get_quota_status()

for species, info in status.items():
    print(f"{species}:")
    print(f"  Total: {info['total_limit_lb']} lb")
    print(f"  Caught: {info['current_catch_lb']} lb")
    print(f"  Remaining: {info['remaining_lb']} lb")
    print(f"  Usable: {info['usable_lb']} lb")
    print(f"  Percent Used: {info['percent_used']:.1f}%")
```

### 4. Handle Releases

```python
# Release a catch (restores quota)
quota_manager.log_release(
    catch_id="20260728_103000_abc123",
    reason="size_limit",
)
```

## API Reference

### QuotaManager Class

#### Initialization

```python
QuotaManager(
    storage_path: str | Path | None = None,
    vessel_id: str = "US-AK-FVEILEEN-51",
    default_reserve_percent: float = 10.0,
)
```

**Parameters:**
- `storage_path`: Directory for JSONL files (quota.jsonl, catch.jsonl)
- `vessel_id`: Vessel identifier for catch events
- `default_reserve_percent`: Default safety buffer for new quotas

#### Quota Management

##### `set_species_quota()`

Set or create quota for a species.

```python
quota_manager.set_species_quota(
    species: str,
    total_limit_lb: float,
    current_catch_lb: float = 0.0,
    reserve_percent: float | None = None,
    quota_source: str = "IFQ",
    expiry_date: str | None = None,
) -> SpeciesQuota
```

**Example:**
```python
quota_manager.set_species_quota(
    species="coho",
    total_limit_lb=800.0,
    reserve_percent=12.0,
    quota_source="CDQ",
)
```

##### `get_species_quota()`

Get quota for a species.

```python
quota = quota_manager.get_species_quota(species: str) -> SpeciesQuota | None
```

##### `update_species_quota()`

Update existing quota.

```python
quota_manager.update_species_quota(
    species: str,
    total_limit_lb: float | None = None,
    current_catch_lb: float | None = None,
    reserve_percent: float | None = None,
    expiry_date: str | None = None,
) -> SpeciesQuota | None
```

##### `remove_species_quota()`

Remove quota for a species.

```python
quota_manager.remove_species_quota(species: str) -> bool
```

##### `transfer_quota()`

Record quota transfer between vessels.

```python
quota_manager.transfer_quota(
    from_vessel: str,
    to_vessel: str,
    species: str,
    amount_lb: float,
) -> dict[str, Any]
```

#### Catch Logging

##### `log_catch()`

Log a catch event and deduct from quota.

```python
quota_manager.log_catch(
    species: str,
    weight_lb: float,
    lat: float,
    lon: float,
    gear_type: str,
    timestamp_ns: int | None = None,
    crew_member: str | None = None,
) -> CatchEvent
```

**Raises:**
- `ValueError`: No quota set for species or insufficient quota

**Example:**
```python
catch = quota_manager.log_catch(
    species="halibut",
    weight_lb=30.0,
    lat=57.0531,
    lon=-135.3300,
    gear_type="longline",
    crew_member="captain",
)
```

##### `log_release()`

Mark a catch as released and restore quota.

```python
quota_manager.log_release(
    catch_id: str,
    reason: str,  # "size_limit", "bycatch", "quality", etc.
) -> CatchEvent | None
```

##### `get_catch_history()`

Get catch history with filters.

```python
quota_manager.get_catch_history(
    species: str | None = None,
    start_time: int | None = None,  # nanoseconds
    end_time: int | None = None,
    limit: int = 1000,
) -> list[CatchEvent]
```

#### Quota Queries

##### `get_remaining_quota()`

Get remaining quota for a species.

```python
remaining = quota_manager.get_remaining_quota(species: str) -> float
```

##### `get_quota_percent_used()`

Get percentage of quota used.

```python
percent = quota_manager.get_quota_percent_used(species: str) -> float
```

##### `get_quota_status()`

Get comprehensive status for all species.

```python
status = quota_manager.get_quota_status() -> dict[str, dict[str, Any]]
```

**Returns:**
```python
{
    "chinook": {
        "total_limit_lb": 1000.0,
        "current_catch_lb": 200.0,
        "remaining_lb": 800.0,
        "usable_lb": 700.0,  # Excluding reserve
        "percent_used": 20.0,
        "reserve_percent": 10.0,
        "quota_source": "IFQ",
        "expiry_date": "2026-12-31T23:59:59.000000+00:00",
    },
    ...
}
```

##### `check_quota_available()`

Check if sufficient quota is available.

```python
available = quota_manager.check_quota_available(
    species: str,
    weight_lb: float,
) -> bool
```

#### Analytics

##### `calculate_catch_rate()`

Calculate catch rate over a time window.

```python
rate = quota_manager.calculate_catch_rate(
    species: str,
    window_hours: float = 24.0,
) -> float  # pounds per hour
```

##### `project_exhaustion_date()`

Project when quota will be exhausted.

```python
projection = quota_manager.project_exhaustion_date(
    species: str,
    window_hours: float = 24.0,
) -> str | None  # ISO 8601 date or None
```

##### `get_bycatch_report()`

Report bycatch for a target species.

```python
bycatch = quota_manager.get_bycatch_report(
    target_species: str,
) -> dict[str, float]  # species -> pounds
```

##### `get_species_summary()`

Get comprehensive summary for a species.

```python
summary = quota_manager.get_species_summary(
    species: str,
) -> dict[str, Any]
```

#### Alerts

##### `get_alerts()`

Get recent quota alerts.

```python
alerts = quota_manager.get_alerts(
    species: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]
```

**Alert thresholds:** 80%, 90%, 95%, 100%

#### Integration

##### `to_dict()`

Export quota manager state.

```python
state = quota_manager.to_dict() -> dict[str, Any]
```

##### `get_watcher_frame()`

Get frame data for WatcherRegistry evaluation.

```python
frame = quota_manager.get_watcher_frame() -> dict[str, Any]
```

**Frame format:**
```python
{
    "quota_alert_count": 2,
    "quota_chinook_percent_used": 45.2,
    "quota_chinook_remaining_lb": 548.0,
    "quota_chinook_usable_lb": 498.0,
    "quota_catch_rate_chinook_lb_per_hr": 12.5,
    ...
}
```

## Data Models

### SpeciesQuota

```python
@dataclass
class SpeciesQuota:
    species: str
    total_limit_lb: float
    current_catch_lb: float = 0.0
    reserve_percent: float = 10.0
    quota_source: str = "IFQ"
    expiry_date: str | None = None
```

**Methods:**
- `remaining_lb() -> float`: Remaining quota including reserve
- `usable_lb() -> float`: Usable quota (excluding reserve)
- `percent_used() -> float`: Percentage of quota used
- `to_dict() -> dict`: Convert to dictionary

### CatchEvent

```python
@dataclass
class CatchEvent:
    catch_id: str
    species: str
    weight_lb: float
    lat: float
    lon: float
    timestamp_ns: int
    gear_type: str
    vessel_id: str
    crew_member: str | None = None
    released: bool = False
    release_reason: str | None = None
```

## TwinCore Integration

### Initialization

```python
from twin.core import TwinCore

core = TwinCore(
    vessel_id="US-AK-FVEILEEN-51",
    quota_path="quota",  # Directory for JSONL files
    quota_enabled=True,  # Enable quota manager
)
```

### Access Quota Manager

```python
# Set quotas
core.quota.set_species_quota("chinook", 1000.0)

# Log catches
core.quota.log_catch("chinook", 50.0, lat, lon, "purse_seine")

# Check status
status = core.quota.get_quota_status()
```

### Snapshot Integration

Quota status is automatically included in TwinCore snapshots:

```python
snapshot = core.build_snapshot()

# Access quota status
quota_status = snapshot.get("quota", {})
for species, info in quota_status.items():
    print(f"{species}: {info['percent_used']:.1f}% used")
```

## WatcherRegistry Integration

Use quota data in watcher rules:

```python
from twin.watchers import WatcherRegistry

registry = WatcherRegistry()

# Alert when chinook quota exceeds 80%
registry.add({
    "id": "chinook-quota-warning",
    "name": "Chinook quota warning",
    "when": lambda f: f.get("quota_chinook_percent_used", 0) >= 80.0,
    "action": {
        "name": "raise_alert",
        "payload": lambda f: {
            "kind": "quota_warning",
            "species": "chinook",
            "percent_used": f["quota_chinook_percent_used"],
        },
        "reason": lambda f: f"Chinook quota {f['quota_chinook_percent_used']:.1f}% used",
        "priority": lambda f: 0.7,
    },
    "cooldown_s": 300.0,  # 5 minutes
})

# Evaluate with quota frame
frame = core.quota.get_watcher_frame()
actions = registry.evaluate(frame)
```

## OpLog Integration

Log quota-related actions to operations log:

```python
# Quota set event
await core.log_crew_action(
    entry_type="quota_set",
    crew="captain",
    message="Set chinook quota to 1000 lb IFQ",
    metadata={"species": "chinook", "limit_lb": 1000, "source": "IFQ"},
)

# Catch logged event
await core.log_crew_action(
    entry_type="catch_logged",
    crew="captain",
    message="Logged 15.5 lb chinook catch",
    metadata={
        "catch_id": catch.catch_id,
        "species": "chinook",
        "weight_lb": 15.5,
        "lat": catch.lat,
        "lon": catch.lon,
    },
)

# Quota exhausted alert
await core.log_crew_action(
    entry_type="manual_alert",
    crew="system",
    message="Chinook quota exhausted at 100%",
    metadata={"species": "chinook", "alert_type": "quota_exhausted"},
)
```

## Usage Examples

### Example 1: Daily Fishing Operations

```python
# Morning setup
core.quota.set_species_quota("chinook", 1000.0, reserve_percent=10.0)
core.quota.set_species_quota("coho", 800.0, reserve_percent=10.0)

# During fishing - log catches as they're brought aboard
catch1 = core.quota.log_catch(
    "chinook", 25.0, 57.0531, -135.3300, "purse_seine",
    crew_member="captain",
)
catch2 = core.quota.log_catch(
    "coho", 15.0, 57.0531, -135.3300, "purse_seine",
    crew_member="deckhand",
)

# Check status
for species in ["chinook", "coho"]:
    status = core.quota.get_species_summary(species)
    print(f"{species}: {status['percent_used']:.1f}% used")

# Monitor for alerts
alerts = core.quota.get_alerts()
for alert in alerts:
    print(f"Alert: {alert['species']} at {alert['percent_used']:.1f}%")
```

### Example 2: Bycatch Management

```python
# Primary target: chinook
core.quota.set_species_quota("chinook", 1000.0)

# Log catch mix
core.quota.log_catch("chinook", 100.0, lat, lon, "purse_seine")
core.quota.log_catch("coho", 15.0, lat, lon, "purse_seine")  # Bycatch
core.quota.log_catch("halibut", 5.0, lat, lon, "purse_seine")  # Bycatch

# Get bycatch report
bycatch = core.quota.get_bycatch_report("chinook")
print(f"Coho bycatch: {bycatch['coho']} lb")
print(f"Halibut bycatch: {bycatch['halibut']} lb")
```

### Example 3: Catch Release

```python
# Log a catch that's too small
catch = core.quota.log_catch("chinook", 5.0, lat, lon, "purse_seine")

# Release it (restores quota)
core.quota.log_release(catch.catch_id, "size_limit")

# Verify quota restored
print(f"Chinook used: {core.quota.get_quota_percent_used('chinook'):.1f}%")
```

### Example 4: Exhaustion Projection

```python
# Check when quota will be exhausted
projection = core.quota.project_exhaustion_date("chinook", window_hours=24.0)
if projection:
    print(f"Chinook quota projected exhaustion: {projection}")
else:
    print("Cannot project - insufficient catch data")

# Get catch rate
rate = core.quota.calculate_catch_rate("chinook", window_hours=24.0)
print(f"Current catch rate: {rate:.2f} lb/hr")
```

## Storage Format

### quota.jsonl

```json
{"kind":"species_quota","species":"chinook","total_limit_lb":1000.0,"current_catch_lb":50.0,"reserve_percent":10.0,"quota_source":"IFQ","expiry_date":"2026-12-31T23:59:59.000000+00:00","_loggedAt":"2026-07-28T10:30:00.123456+00:00","_seq":0}
```

### catch.jsonl

```json
{"kind":"catch_event","catch_id":"20260728_103000_abc123","species":"chinook","weight_lb":15.5,"lat":57.0531,"lon":-135.3300,"timestamp_ns":1753478400000000000,"gear_type":"purse_seine","vessel_id":"US-AK-FVEILEEN-51","crew_member":"captain","released":false,"_loggedAt":"2026-07-28T10:30:00.123456+00:00","_seq":1}
{"kind":"quota_transfer","from_vessel":"US-AK-VESSEL1","to_vessel":"US-AK-VESSEL2","species":"chinook","amount_lb":100.0,"timestamp_ns":1753478400000000000,"ts":"2026-07-28T10:30:00.000000+00:00"}
{"kind":"quota_alert","species":"chinook","threshold":80.0,"percent_used":82.5,"remaining_lb":175.0,"timestamp_ns":1753478400000000000,"ts":"2026-07-28T11:30:00.000000+00:00","_seq":2}
```

## Error Handling

### No Quota Set

```python
try:
    core.quota.log_catch("chinook", 50.0, lat, lon, "purse_seine")
except ValueError as e:
    print(f"Error: {e}")  # "No quota set for species: chinook"
```

### Insufficient Quota

```python
core.quota.set_species_quota("chinook", 100.0, reserve_percent=10.0)

try:
    core.quota.log_catch("chinook", 95.0, lat, lon, "purse_seine")
except ValueError as e:
    print(f"Error: {e}")  # "Insufficient quota for chinook: requesting 95.0 lb, usable 90.0 lb"
```

### Invalid Parameters

```python
# Invalid species
try:
    core.quota.set_species_quota("tuna", 1000.0)
except ValueError as e:
    print(f"Error: {e}")  # "Invalid species: tuna"

# Negative weight
try:
    core.quota.log_catch("chinook", -10.0, lat, lon, "purse_seine")
except ValueError as e:
    print(f"Error: {e}")  # "weight_lb must be positive"
```

## Best Practices

### 1. Set Appropriate Reserve Buffers

```python
# 10-20% reserve is typical for regulatory compliance
core.quota.set_species_quota("chinook", 1000.0, reserve_percent=15.0)
```

### 2. Log Catches Immediately

```python
# Log as soon as catch is brought aboard
catch = core.quota.log_catch("chinook", weight, lat, lon, gear, crew="captain")
```

### 3. Monitor Alerts Proactively

```python
# Check for new alerts after each catch
alerts = core.quota.get_alerts(limit=10)
for alert in alerts:
    if alert["threshold"] >= 90.0:
        # Take action - consider shifting effort
        notify_captain(alert)
```

### 4. Use Catch Rate for Planning

```python
# Calculate recent catch rate
rate = core.quota.calculate_catch_rate("chinook", window_hours=6.0)
remaining = core.quota.get_remaining_quota("chinook")

if rate > 0:
    hours_left = remaining / rate
    print(f"At current rate, chinook quota lasts {hours_left:.1f} hours")
```

### 5. Track Bycatch for Compliance

```python
# Regular bycatch reporting
for target_species in ["chinook", "coho"]:
    bycatch = core.quota.get_bycatch_report(target_species)
    if bycatch:
        log_bycatch(target_species, bycatch)
```

## Testing

Run the comprehensive test suite:

```bash
# Run all quota manager tests
pytest twin/tests/test_quota_manager.py -v

# Run specific test class
pytest twin/tests/test_quota_manager.py::TestCatchLogging -v

# Run with coverage
pytest twin/tests/test_quota_manager.py --cov=twin/quota_manager --cov-report=html
```

## Performance Considerations

- **Memory**: Default MAX_CATCHES = 5000 (adjust if needed)
- **Storage**: JSONL append-only, automatic rotation not implemented
- **Query Speed**: In-memory queries are fast; large histories may need filtering
- **Persistence**: Every catch logged immediately to disk (safe but slower)

## Troubleshooting

### Quota Not Persisting

```python
# Ensure storage_path is set
qm = QuotaManager(storage_path="quota")  # Not None
```

### Missing Quota Status in Snapshots

```python
# Ensure quota_enabled=True in TwinCore
core = TwinCore(quota_enabled=True)

# Check quota manager exists
assert core.quota is not None
```

### Watcher Frame Empty

```python
# Set quotas first
core.quota.set_species_quota("chinook", 1000.0)

# Then get frame
frame = core.quota.get_watcher_frame()
assert "quota_chinook_percent_used" in frame
```

## Future Enhancements

- Multi-vessel quota pooling
- Regulatory reporting integration (ADF&G, NOAA)
- Economic analysis (price per species)
- Automated catch reporting
- Mobile app integration
- Historical quota performance analysis
- Seasonal quota optimization

## References

- [ADF&G Commercial Fishing](https://www.adfg.alaska.gov/)
- [NOAA Fisheries Quota Management](https://www.fisheries.noaa.gov/)
- [Alaska IFQ Program](https://www.fisheries.noaa.gov/alaska/commercial-fishing/individual-fishing-quota)

## Support

For issues or questions about the Fishing Quota Management System, contact the AELMA development team or consult the API documentation above.
