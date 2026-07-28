# QuotaManager Component Documentation

## Component Overview

The `QuotaManager` component is a comprehensive commercial fishing quota tracking and management system for the AELMA marine digital twin. It provides real-time quota monitoring, catch logging, validation, analytics, and alert generation for regulatory compliance and operational efficiency.

### Purpose

The QuotaManager serves three primary purposes:

1. **Regulatory Compliance**: Ensure fishing operations remain within allocated quota limits for Alaska commercial fisheries
2. **Catch Optimization**: Provide real-time quota status to maximize fishing efficiency while avoiding violations
3. **Data Management**: Maintain comprehensive catch records for reporting, analysis, and audit trails

### Use Cases

- **Daily Operations**: Track catches against quota limits during fishing trips
- **Regulatory Reporting**: Generate catch reports for state and federal compliance
- **Fleet Management**: Monitor quota usage across multiple species and vessels
- **Bycatch Monitoring**: Track non-target species catch for regulatory compliance
- **Quota Planning**: Project exhaustion dates to optimize fishing schedules
- **Catch Validation**: Prevent over-catching with automatic quota validation

### Integration Points

- **TwinCore**: Quota status included in snapshots, accessible via `core.quota`
- **WatcherRegistry**: Quota metrics available for rule evaluation via `get_watcher_frame()`
- **OpLog**: Crew actions and quota events logged to operations log
- **A2A System**: Agent-to-agent communication for quota coordination

## Architecture

### Design Philosophy

The QuotaManager follows these design principles:

1. **Append-Only Storage**: All quota and catch events are immutable JSONL records
2. **In-Memory State**: Fast access with automatic persistence
3. **Validation First**: All operations validated before state changes
4. **Alert-Driven**: Automatic threshold-based alerting
5. **Synchronous I/O**: Low-frequency operations use simple file I/O

### Data Structures

#### SpeciesQuota

```python
@dataclass
class SpeciesQuota:
    """Quota allocation for a single species."""

    species: str                    # Species code (chinook, coho, etc.)
    total_limit_lb: float           # Total quota limit in pounds
    current_catch_lb: float = 0.0   # Current catch amount
    reserve_percent: float = 10.0  # Safety buffer percentage
    quota_source: str = "IFQ"      # Quota source
    expiry_date: str | None = None # ISO 8601 expiry date
```

**Methods:**
- `remaining_lb() -> float`: Total remaining quota (including reserve)
- `usable_lb() -> float`: Usable quota (excluding reserve buffer)
- `percent_used() -> float`: Percentage of total quota used
- `to_dict() -> dict`: Serialize to dictionary

**Validation:**
- Species must be in VALID_SPECIES set
- Total limit must be positive
- Current catch cannot exceed total limit
- Reserve percent must be 0-100
- Quota source must be valid

#### CatchEvent

```python
@dataclass
class CatchEvent:
    """A single catch event."""

    catch_id: str                   # Unique catch identifier
    species: str                    # Species code
    weight_lb: float               # Weight in pounds
    lat: float                     # Latitude
    lon: float                     # Longitude
    timestamp_ns: int              # Nanosecond timestamp
    gear_type: str                # Gear type (purse_seine, gillnet, etc.)
    vessel_id: str                 # Vessel identifier
    crew_member: str | None = None # Crew member
    released: bool = False         # Release status
    release_reason: str | None = None # Release reason
```

**Methods:**
- `to_dict() -> dict`: Serialize to dictionary

**Validation:**
- Species must be in VALID_SPECIES set
- Weight must be positive
- Latitude must be -90 to 90
- Longitude must be -180 to 180
- Timestamp must be positive integer
- Gear type and vessel ID must be non-empty strings
- Release requires reason

### Storage Architecture

#### JSONL Storage

**quota.jsonl** - Quota allocation records:
```json
{
  "kind": "species_quota",
  "species": "chinook",
  "total_limit_lb": 1000.0,
  "current_catch_lb": 50.0,
  "reserve_percent": 10.0,
  "quota_source": "IFQ",
  "expiry_date": "2026-12-31T23:59:59.000000+00:00",
  "_loggedAt": "2026-07-28T10:30:00.123456+00:00",
  "_seq": 0
}
```

**catch.jsonl** - Catch events, transfers, and alerts:
```json
{
  "kind": "catch_event",
  "catch_id": "20260728_103000_abc123",
  "species": "chinook",
  "weight_lb": 15.5,
  "lat": 57.0531,
  "lon": -135.3300,
  "timestamp_ns": 1753478400000000000,
  "gear_type": "purse_seine",
  "vessel_id": "US-AK-FVEILEEN-51",
  "crew_member": "captain",
  "released": false,
  "_loggedAt": "2026-07-28T10:30:00.123456+00:00",
  "_seq": 1
}
```

**Record Types:**
- `species_quota`: Quota allocation
- `catch_event`: Catch/release event
- `quota_transfer`: Quota transfer between vessels
- `quota_alert`: Threshold alert

#### Memory Management

- **Quota State**: `dict[str, SpeciesQuota]` - All current quotas
- **Catch History**: `deque[CatchEvent]` - Most recent 5000 events (configurable via MAX_CATCHES)
- **Alerts**: `list[dict[str, Any]]` - All generated alerts
- **Sequence Numbers**: `_quota_seq`, `_catch_seq` - For JSONL ordering

### Validation Architecture

#### Multi-Layer Validation

1. **Input Validation**: Dataclass `__post_init__` validation
2. **Business Logic Validation**: Quota availability checks
3. **State Validation**: Consistency checks before persistence
4. **Schema Validation**: JSON schema compliance (future)

#### Error Handling Strategy

```python
# Input validation (dataclass)
try:
    quota = SpeciesQuota(species="tuna", total_limit_lb=1000.0)
except ValueError as e:
    # "Invalid species: tuna. Must be one of [...]"
    pass

# Business logic validation
try:
    quota_manager.log_catch("chinook", 9999.0, lat, lon, "purse_seine")
except ValueError as e:
    # "Insufficient quota for chinook: requesting 9999.0 lb, usable 800.0 lb"
    pass
```

### Reserve Management System

#### Reserve Calculation

```python
usable_quota = total_limit - current_catch - (total_limit * reserve_percent / 100)
```

**Purpose**: Prevent accidental over-catching by maintaining a safety buffer

**Example:**
- Total limit: 1000 lb
- Current catch: 50 lb
- Reserve percent: 10%
- Remaining: 950 lb
- Usable: 850 lb (950 - 100)

**Validation**: Catch operations fail if weight exceeds usable quota

## API Reference

### QuotaManager.__init__()

Initialize the quota manager.

```python
QuotaManager(
    storage_path: str | Path | None = None,
    vessel_id: str = "US-AK-FVEILEEN-51",
    default_reserve_percent: float = 10.0,
) -> None
```

**Parameters:**
- `storage_path`: Base directory for JSONL files (None = no persistence)
- `vessel_id`: Vessel identifier for catch events
- `default_reserve_percent`: Default reserve percentage for new quotas

**Behavior:**
- Creates `quota.jsonl` and `catch.jsonl` in storage directory
- Loads existing quotas and catches on startup
- Initializes empty state if no storage

**Example:**
```python
# In-memory (no persistence)
qm = QuotaManager(storage_path=None)

# With persistence
qm = QuotaManager(
    storage_path="/var/lib/aelma/quota",
    vessel_id="US-AK-FVEILEEN-51",
    default_reserve_percent=15.0,
)
```

### Quota Management

#### set_species_quota()

Set or create quota for a species.

```python
QuotaManager.set_species_quota(
    species: str,
    total_limit_lb: float,
    current_catch_lb: float = 0.0,
    reserve_percent: float | None = None,
    quota_source: str = "IFQ",
    expiry_date: str | None = None,
) -> SpeciesQuota
```

**Parameters:**
- `species`: Species code (chinook, coho, halibut, etc.)
- `total_limit_lb`: Total quota limit in pounds
- `current_catch_lb`: Current catch amount (for existing quotas)
- `reserve_percent`: Safety buffer percentage (None uses default)
- `quota_source`: Quota source (IFQ, CDQ, community, state, federal)
- `expiry_date`: ISO 8601 expiry date or None

**Returns:** SpeciesQuota object

**Behavior:**
- Replaces existing quota for species
- Validates all parameters
- Appends record to quota.jsonl
- Creates new quota record in JSONL

**Example:**
```python
quota = qm.set_species_quota(
    species="chinook",
    total_limit_lb=1000.0,
    reserve_percent=10.0,
    quota_source="IFQ",
    expiry_date="2026-12-31T23:59:59.000000+00:00",
)
```

#### get_species_quota()

Get quota for a species.

```python
QuotaManager.get_species_quota(species: str) -> SpeciesQuota | None
```

**Returns:** SpeciesQuota or None if not set

**Example:**
```python
quota = qm.get_species_quota("chinook")
if quota:
    print(f"Remaining: {quota.remaining_lb()} lb")
```

#### update_species_quota()

Update existing quota allocation.

```python
QuotaManager.update_species_quota(
    species: str,
    total_limit_lb: float | None = None,
    current_catch_lb: float | None = None,
    reserve_percent: float | None = None,
    expiry_date: str | None = None,
) -> SpeciesQuota | None
```

**Parameters:** Only update fields that are not None

**Returns:** Updated SpeciesQuota or None if species not found

**Behavior:**
- Creates new quota record (append-only)
- Updates in-memory state
- Appends to quota.jsonl

**Example:**
```python
# Update only total limit
updated = qm.update_species_quota("chinook", total_limit_lb=1500.0)
```

#### remove_species_quota()

Remove quota for a species.

```python
QuotaManager.remove_species_quota(species: str) -> bool
```

**Returns:** True if existed, False otherwise

**Behavior:**
- Removes from in-memory state only
- Does not delete from JSONL (append-only)
- Use with caution

**Example:**
```python
existed = qm.remove_species_quota("chinook")
```

#### transfer_quota()

Record quota transfer between vessels.

```python
QuotaManager.transfer_quota(
    from_vessel: str,
    to_vessel: str,
    species: str,
    amount_lb: float,
) -> dict[str, Any]
```

**Returns:** Transfer record dictionary

**Behavior:**
- Creates log entry only (audit trail)
- Does not modify quotas (must be done separately)
- Appends to catch.jsonl

**Example:**
```python
# Record transfer
transfer = qm.transfer_quota(
    from_vessel="US-AK-VESSEL1",
    to_vessel="US-AK-VESSEL2",
    species="chinook",
    amount_lb=100.0,
)

# Actually update quotas
qm.update_species_quota("chinook", current_catch_lb=-100.0)
```

### Catch Logging

#### log_catch()

Log a catch event and deduct from quota.

```python
QuotaManager.log_catch(
    species: str,
    weight_lb: float,
    lat: float,
    lon: float,
    gear_type: str,
    timestamp_ns: int | None = None,
    crew_member: str | None = None,
) -> CatchEvent
```

**Parameters:**
- `species`: Species code
- `weight_lb`: Weight in pounds (must be positive)
- `lat`: Latitude (-90 to 90)
- `lon`: Longitude (-180 to 180)
- `gear_type`: Gear type (purse_seine, gillnet, pot, longline, etc.)
- `timestamp_ns`: Nanosecond timestamp (None = now)
- `crew_member`: Crew member identifier

**Returns:** CatchEvent object

**Raises:**
- `ValueError`: No quota set, insufficient quota, or invalid parameters

**Behavior:**
- Validates quota availability (including reserve)
- Generates unique catch ID
- Deducts from quota
- Checks for threshold alerts
- Appends to catch.jsonl

**Example:**
```python
catch = qm.log_catch(
    species="chinook",
    weight_lb=15.5,
    lat=57.0531,
    lon=-135.3300,
    gear_type="purse_seine",
    crew_member="captain",
)
```

#### log_release()

Mark a catch as released and restore quota.

```python
QuotaManager.log_release(
    catch_id: str,
    reason: str,
) -> CatchEvent | None
```

**Parameters:**
- `catch_id`: Catch event ID
- `reason`: Release reason (size_limit, bycatch, quality, etc.)

**Returns:** Updated CatchEvent or None if not found

**Behavior:**
- Marks catch as released
- Restores quota (deducts weight)
- Appends updated record to catch.jsonl

**Example:**
```python
qm.log_release(
    catch_id="20260728_103000_abc123",
    reason="size_limit",
)
```

#### get_catch_history()

Get catch history with optional filters.

```python
QuotaManager.get_catch_history(
    species: str | None = None,
    start_time: int | None = None,
    end_time: int | None = None,
    limit: int = 1000,
) -> list[CatchEvent]
```

**Parameters:**
- `species`: Filter by species (None = all)
- `start_time`: Start timestamp in nanoseconds (None = beginning)
- `end_time`: End timestamp in nanoseconds (None = now)
- `limit`: Maximum events to return

**Returns:** List of CatchEvent objects, most recent first

**Example:**
```python
# Get chinook catches from last 24 hours
now = time.time_ns()
yesterday = now - (24 * 3600 * 1_000_000_000)

history = qm.get_catch_history(
    species="chinook",
    start_time=yesterday,
    end_time=now,
    limit=100,
)
```

### Quota Queries

#### get_remaining_quota()

Get remaining quota for a species.

```python
QuotaManager.get_remaining_quota(species: str) -> float
```

**Returns:** Remaining quota in pounds (0.0 if not set)

**Example:**
```python
remaining = qm.get_remaining_quota("chinook")
print(f"Remaining chinook: {remaining} lb")
```

#### get_quota_percent_used()

Get percentage of quota used for a species.

```python
QuotaManager.get_quota_percent_used(species: str) -> float
```

**Returns:** Percentage used (0.0 if not set)

**Example:**
```python
percent = qm.get_quota_percent_used("chinook")
print(f"Chinook: {percent:.1f}% used")
```

#### get_quota_status()

Get comprehensive quota status for all species.

```python
QuotaManager.get_quota_status() -> dict[str, dict[str, Any]]
```

**Returns:** Dictionary with species status:
- `total_limit_lb`: Total quota limit
- `current_catch_lb`: Current catch
- `remaining_lb`: Remaining quota
- `usable_lb`: Usable quota (excluding reserve)
- `percent_used`: Percentage used
- `reserve_percent`: Reserve percentage
- `quota_source`: Quota source
- `expiry_date`: Expiry date

**Example:**
```python
status = qm.get_quota_status()
for species, info in status.items():
    print(f"{species}: {info['percent_used']:.1f}% used")
```

#### check_quota_available()

Check if sufficient quota is available for a catch.

```python
QuotaManager.check_quota_available(
    species: str,
    weight_lb: float,
) -> bool
```

**Returns:** True if sufficient quota, False otherwise

**Example:**
```python
if qm.check_quota_available("chinook", 50.0):
    # Safe to catch 50 lb
    qm.log_catch("chinook", 50.0, lat, lon, "purse_seine")
```

### Analytics Methods

#### calculate_catch_rate()

Calculate catch rate for a species over a time window.

```python
QuotaManager.calculate_catch_rate(
    species: str,
    window_hours: float = 24.0,
) -> float
```

**Parameters:**
- `species`: Species code
- `window_hours`: Time window in hours

**Returns:** Catch rate in pounds per hour

**Behavior:**
- Sum all non-released catches in time window
- Divide by window hours
- Ignores released catches

**Example:**
```python
rate = qm.calculate_catch_rate("chinook", window_hours=24.0)
print(f"Chinook catch rate: {rate:.2f} lb/hr")
```

#### project_exhaustion_date()

Project when quota will be exhausted based on recent catch rate.

```python
QuotaManager.project_exhaustion_date(
    species: str,
    window_hours: float = 24.0,
) -> str | None
```

**Parameters:**
- `species`: Species code
- `window_hours`: Time window for catch rate calculation

**Returns:** ISO 8601 projection date or None (if not calculable)

**Behavior:**
- Calculates catch rate over time window
- Projects exhaustion based on usable quota
- Returns None if no recent catches or already exhausted

**Example:**
```python
projection = qm.project_exhaustion_date("chinook")
if projection:
    print(f"Chinook projected exhaustion: {projection}")
```

#### get_bycatch_report()

Report bycatch ratios for a target species.

```python
QuotaManager.get_bycatch_report(
    target_species: str,
) -> dict[str, float]
```

**Parameters:**
- `target_species`: Primary species to analyze

**Returns:** Dictionary with non-target species as keys and pounds as values

**Behavior:**
- Sums all non-target species catches
- Ignores released catches
- Excludes target species from results

**Example:**
```python
bycatch = qm.get_bycatch_report("chinook")
for species, weight in bycatch.items():
    print(f"{species}: {weight} lb bycatch")
```

#### get_species_summary()

Get comprehensive summary for a single species.

```python
QuotaManager.get_species_summary(
    species: str,
) -> dict[str, Any]
```

**Returns:** Summary dictionary:
- `species`: Species code
- `quota_set`: Boolean
- `total_limit_lb`: Total limit (if set)
- `current_catch_lb`: Current catch
- `remaining_lb`: Remaining quota
- `usable_lb`: Usable quota
- `percent_used`: Percentage used
- `catch_count`: Number of catch events
- `catch_rate_lb_per_hour`: Recent catch rate
- `projected_exhaustion`: Exhaustion date
- `quota_source`: Quota source
- `expiry_date`: Expiry date

**Example:**
```python
summary = qm.get_species_summary("chinook")
print(f"Chinook: {summary['percent_used']:.1f}% used")
print(f"Rate: {summary['catch_rate_lb_per_hour']} lb/hr")
print(f"Projection: {summary['projected_exhaustion']}")
```

### Alert Generation

#### get_alerts()

Get recent quota threshold alerts.

```python
QuotaManager.get_alerts(
    species: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]
```

**Parameters:**
- `species`: Filter by species (None = all)
- `limit`: Maximum alerts to return

**Returns:** List of alert dictionaries

**Alert Thresholds:** 80%, 90%, 95%, 100%

**Alert Format:**
```python
{
    "kind": "quota_alert",
    "species": "chinook",
    "threshold": 80.0,
    "percent_used": 82.5,
    "remaining_lb": 175.0,
    "timestamp_ns": 1753478400000000000,
    "ts": "2026-07-28T10:30:00.000000+00:00",
}
```

**Behavior:**
- Each threshold triggers alert once (no duplicates)
- Alerts generated automatically on catch logging
- Stored in memory and catch.jsonl

**Example:**
```python
alerts = qm.get_alerts("chinook", limit=10)
for alert in alerts:
    print(f"Alert: {alert['species']} at {alert['threshold']}%")
```

### Integration Methods

#### to_dict()

Export quota manager state to dictionary.

```python
QuotaManager.to_dict() -> dict[str, Any]
```

**Returns:** Dictionary with:
- `vessel_id`: Vessel identifier
- `quotas`: Quota allocations (species -> quota dict)
- `catch_count`: Total catch events
- `alert_count`: Total alerts

**Use Case:** Snapshot generation for TwinCore

**Example:**
```python
snapshot = qm.to_dict()
# {
#     "vessel_id": "US-AK-FVEILEEN-51",
#     "quotas": {"chinook": {...}, "coho": {...}},
#     "catch_count": 150,
#     "alert_count": 3,
# }
```

#### get_watcher_frame()

Get frame data for WatcherRegistry evaluation.

```python
QuotaManager.get_watcher_frame() -> dict[str, Any]
```

**Returns:** Flat dictionary with quota metrics

**Frame Format:**
```python
{
    "quota_alert_count": 2,
    "quota_chinook_percent_used": 45.2,
    "quota_chinook_remaining_lb": 548.0,
    "quota_chinook_usable_lb": 498.0,
    "quota_chinook_total_limit_lb": 1000.0,
    "quota_chinook_current_catch_lb": 452.0,
    "quota_catch_rate_chinook_lb_per_hr": 12.5,
    ...
}
```

**Naming Convention:** `quota_{species}_{metric}`

**Use Case:** Rule evaluation in WatcherRegistry

**Example:**
```python
frame = qm.get_watcher_frame()
# Use in watcher rule
if frame.get("quota_chinook_percent_used", 0) >= 80.0:
    # Trigger alert
    pass
```

## Data Validation

### Input Validation

#### Species Validation

```python
VALID_SPECIES = frozenset({
    "chinook", "coho", "sockeye", "pink", "chum",
    "halibut", "cod", "black_cod",
    "crab", "king_crab", "snow_crab", "dungeness_crab",
})
```

**Validation:**
```python
if species not in VALID_SPECIES:
    raise ValueError(f"Invalid species: {species}")
```

#### Position Validation

**Latitude Range:** -90.0 to 90.0
**Longitude Range:** -180.0 to 180.0

```python
if not -90.0 <= lat <= 90.0:
    raise ValueError(f"lat out of range: {lat}")
if not -180.0 <= lon <= 180.0:
    raise ValueError(f"lon out of range: {lon}")
```

#### Weight Validation

**Rules:**
- Weight must be positive (> 0)
- No zero or negative weights
- No maximum limit (but quota validation applies)

```python
if weight_lb <= 0:
    raise ValueError("weight_lb must be positive")
```

#### Quota Source Validation

```python
QUOTA_SOURCES = frozenset({"IFQ", "CDQ", "community", "state", "federal"})
```

**Validation:**
```python
if quota_source not in QUOTA_SOURCES:
    raise ValueError(f"Invalid quota_source: {quota_source}")
```

### Business Logic Validation

#### Quota Availability Check

```python
def check_quota_available(species: str, weight_lb: float) -> bool:
    quota = self.quotas.get(species)
    if quota is None:
        return False
    return weight_lb <= quota.usable_lb()
```

**Logic:**
- Check quota exists
- Compare weight to usable quota (excluding reserve)
- Return boolean result

#### Catch Deduction Logic

```python
def log_catch(species, weight_lb, ...):
    quota = self.quotas.get(species)
    if quota is None:
        raise ValueError(f"No quota set for species: {species}")

    if weight_lb > quota.usable_lb():
        raise ValueError(
            f"Insufficient quota for {species}: "
            f"requesting {weight_lb} lb, "
            f"usable {quota.usable_lb():.2f} lb"
        )

    # Deduct from quota
    quota.current_catch_lb += weight_lb
```

**Validation Steps:**
1. Check quota exists
2. Check sufficient usable quota
3. Deduct weight from quota

#### Release Restoration Logic

```python
def log_release(catch_id: str, reason: str):
    catch = find_catch(catch_id)
    if catch is None:
        return None

    catch.released = True
    catch.release_reason = reason

    # Restore quota
    quota = self.quotas.get(catch.species)
    if quota is not None:
        quota.current_catch_lb = max(0.0, quota.current_catch_lb - catch.weight_lb)
```

**Logic:**
- Find catch event
- Mark as released
- Restore quota (deduct weight)
- Prevent negative quota

### Error Handling Patterns

#### ValueError Patterns

```python
# No quota set
raise ValueError(f"No quota set for species: {species}")

# Insufficient quota
raise ValueError(
    f"Insufficient quota for {species}: "
    f"requesting {weight_lb} lb, "
    f"usable {quota.usable_lb():.2f} lb "
    f"(remaining {quota.remaining_lb():.2f} lb)"
)

# Invalid species
raise ValueError(
    f"Invalid species: {species}. "
    f"Must be one of {sorted(VALID_SPECIES)}"
)

# Invalid position
raise ValueError(f"lat out of range: {lat}")
raise ValueError(f"lon out of range: {lon}")

# Invalid weight
raise ValueError("weight_lb must be positive")

# Missing required field
raise ValueError("release_reason required when released=True")
```

## Analytics & Projections

### Catch Rate Calculation

#### Algorithm

```python
def calculate_catch_rate(species: str, window_hours: float = 24.0) -> float:
    now = _now_ns()
    window_ns = int(window_hours * 3600_000_000_000)  # hours to nanoseconds
    start_ns = now - window_ns

    total_catch = 0.0
    for catch in self._catches:
        if catch.species == species and not catch.released:
            if catch.timestamp_ns >= start_ns:
                total_catch += catch.weight_lb

    return total_catch / window_hours if window_hours > 0 else 0.0
```

**Logic:**
1. Calculate time window in nanoseconds
2. Filter catches by species and time window
3. Sum non-released catches
4. Divide by window hours

**Example:**
```python
# 100 lb caught over 24 hours = 4.17 lb/hr
rate = qm.calculate_catch_rate("chinook", window_hours=24.0)
```

### Exhaustion Date Projection

#### Algorithm

```python
def project_exhaustion_date(species: str, window_hours: float = 24.0) -> str | None:
    quota = self.quotas.get(species)
    if quota is None:
        return None

    remaining = quota.usable_lb()
    if remaining <= 0:
        return _utc_now_iso()  # Already exhausted

    rate = self.calculate_catch_rate(species, window_hours)
    if rate <= 0:
        return None  # No recent catch, can't project

    hours_until_exhaustion = remaining / rate
    seconds = int(hours_until_exhaustion * 3600)

    projection = datetime.now(timezone.utc)
    projection = projection.fromtimestamp(
        projection.timestamp() + seconds,
        tz=timezone.utc,
    )

    return projection.isoformat()
```

**Logic:**
1. Get usable quota (excluding reserve)
2. Calculate recent catch rate
3. Project hours until exhaustion
4. Convert to ISO 8601 timestamp

**Edge Cases:**
- Already exhausted → Return current time
- No recent catches → Return None (can't project)
- Zero or negative rate → Return None

**Example:**
```python
projection = qm.project_exhaustion_date("chinook")
# Returns: "2026-08-15T14:30:00.000000+00:00"
```

### Bycatch Reporting

#### Algorithm

```python
def get_bycatch_report(target_species: str) -> dict[str, float]:
    bycatch = {}

    for catch in self._catches:
        if catch.released:
            continue
        if catch.species != target_species:
            bycatch[catch.species] = bycatch.get(catch.species, 0.0) + catch.weight_lb

    return bycatch
```

**Logic:**
1. Iterate all catches
2. Skip released catches
3. Skip target species catches
4. Sum non-target species by weight

**Use Cases:**
- Regulatory compliance reporting
- Gear type optimization
- Bycatch reduction strategies

**Example:**
```python
bycatch = qm.get_bycatch_report("chinook")
# {"coho": 30.0, "halibut": 20.0, "cod": 15.0}
```

### Percent Used Tracking

#### Calculation

```python
def percent_used(self) -> float:
    if self.total_limit_lb <= 0:
        return 0.0
    return (self.current_catch_lb / self.total_limit_lb) * 100.0
```

**Thresholds:**
- 80%: Warning level
- 90%: Critical level
- 95%: Near exhaustion
- 100%: Exhausted

**Alert Logic:**
```python
def _check_quota_alerts(species: str) -> list[dict[str, Any]]:
    quota = self.quotas.get(species)
    if quota is None:
        return []

    percent = quota.percent_used()
    last_level = self._last_alert_levels.get(species, 0.0)
    new_alerts = []

    for threshold in ALERT_THRESHOLDS:
        if percent >= threshold and last_level < threshold:
            alert = {
                "kind": "quota_alert",
                "species": species,
                "threshold": threshold,
                "percent_used": round(percent, 2),
                "remaining_lb": round(quota.remaining_lb(), 2),
                "timestamp_ns": _now_ns(),
                "ts": _utc_now_iso(),
            }
            new_alerts.append(alert)
            self._alerts.append(alert)

    # Update last alert level
    if percent > last_level:
        self._last_alert_levels[species] = percent

    return new_alerts
```

**Behavior:**
- Each threshold triggers alert once
- Tracked per species
- Automatic on catch logging

## Alert Generation

### Threshold System

#### Alert Levels

```python
ALERT_THRESHOLDS = [80.0, 90.0, 95.0, 100.0]
```

**Trigger Conditions:**
- 80%: Warning - Approaching quota limit
- 90%: Critical - Near quota exhaustion
- 95%: Severe - Quota nearly exhausted
- 100%: Exhausted - Quota fully used

#### Alert Payload

```python
{
    "kind": "quota_alert",
    "species": "chinook",
    "threshold": 80.0,
    "percent_used": 82.5,
    "remaining_lb": 175.0,
    "timestamp_ns": 1753478400000000000,
    "ts": "2026-07-28T10:30:00.000000+00:00",
}
```

**Fields:**
- `kind`: Record type identifier
- `species`: Species code
- `threshold`: Alert threshold (80, 90, 95, 100)
- `percent_used`: Current percentage
- `remaining_lb`: Remaining quota in pounds
- `timestamp_ns`: Nanosecond timestamp
- `ts`: ISO 8601 timestamp

### Alert Deduplication

#### State Tracking

```python
self._last_alert_levels: dict[str, float] = {}
```

**Logic:**
- Track last alert level per species
- Only trigger alert when crossing threshold
- Prevents duplicate alerts

**Example:**
```python
# First time crossing 80%
# Alert generated at 80.5%

# Continuing to catch
# No new 80% alert (already triggered)

# Crossing 90%
# New alert generated at 90.2%
```

### Integration with WatcherRegistry

#### Frame Data

```python
frame = qm.get_watcher_frame()
# {
#     "quota_alert_count": 3,
#     "quota_chinook_percent_used": 92.5,
#     ...
# }
```

#### Watcher Rule Example

```python
registry.add({
    "id": "quota-exhaustion-warning",
    "name": "Quota exhaustion warning",
    "when": lambda f: f.get("quota_alert_count", 0) > 0,
    "action": {
        "name": "raise_alert",
        "payload": lambda f: {
            "kind": "quota_alert",
            "alert_count": f["quota_alert_count"],
        },
        "reason": lambda f: f"Quota alerts: {f['quota_alert_count']}",
        "priority": lambda f: 0.8,
    },
    "cooldown_s": 300.0,
})
```

## Usage Examples

### Setting Up Species Quotas

```python
from twin.quota_manager import QuotaManager

# Initialize quota manager
qm = QuotaManager(storage_path="quota", vessel_id="US-AK-FVEILEEN-51")

# Set up multiple species quotas
quotas = [
    {"species": "chinook", "limit": 1000.0, "reserve": 10.0, "source": "IFQ"},
    {"species": "coho", "limit": 800.0, "reserve": 10.0, "source": "IFQ"},
    {"species": "halibut", "limit": 500.0, "reserve": 15.0, "source": "CDQ"},
    {"species": "cod", "limit": 2000.0, "reserve": 5.0, "source": "state"},
]

for q in quotas:
    qm.set_species_quota(
        species=q["species"],
        total_limit_lb=q["limit"],
        reserve_percent=q["reserve"],
        quota_source=q["source"],
        expiry_date="2026-12-31T23:59:59.000000+00:00",
    )
```

### Logging Catches with Quota Deduction

```python
import time

# Log a catch event
catch = qm.log_catch(
    species="chinook",
    weight_lb=15.5,
    lat=57.0531,
    lon=-135.3300,
    gear_type="purse_seine",
    timestamp_ns=time.time_ns(),
    crew_member="captain",
)

print(f"Catch ID: {catch.catch_id}")
print(f"Species: {catch.species}")
print(f"Weight: {catch.weight_lb} lb")

# Check remaining quota
remaining = qm.get_remaining_quota("chinook")
print(f"Remaining chinook quota: {remaining} lb")

# Check percentage
percent = qm.get_quota_percent_used("chinook")
print(f"Chinook quota: {percent:.1f}% used")
```

### Handling Catch Releases

```python
# Log a catch that's too small
catch = qm.log_catch(
    species="chinook",
    weight_lb=5.0,
    lat=57.0531,
    lon=-135.3300,
    gear_type="purse_seine",
    crew_member="deckhand",
)

print(f"Before release: {qm.get_quota_percent_used('chinook'):.1f}% used")

# Release the catch (restores quota)
qm.log_release(
    catch_id=catch.catch_id,
    reason="size_limit",
)

print(f"After release: {qm.get_quota_percent_used('chinook'):.1f}% used")
```

### Monitoring Quota Exhaustion

```python
# Set up quota
qm.set_species_quota("chinook", 1000.0, reserve_percent=10.0)

# Log some catches
for i in range(8):
    qm.log_catch("chinook", 100.0, 57.0531, -135.3300, "purse_seine")

# Check for alerts
alerts = qm.get_alerts("chinook")
for alert in alerts:
    print(f"Alert: {alert['threshold']}% - {alert['percent_used']:.1f}% used")

# Get comprehensive status
status = qm.get_species_summary("chinook")
print(f"Status: {status['percent_used']:.1f}% used")
print(f"Remaining: {status['remaining_lb']} lb")
print(f"Usable: {status['usable_lb']} lb")
print(f"Catch rate: {status['catch_rate_lb_per_hour']} lb/hr")

# Project exhaustion
projection = qm.project_exhaustion_date("chinook")
if projection:
    print(f"Projected exhaustion: {projection}")
```

### Integration with TwinCore

```python
from twin.core import TwinCore

# Initialize TwinCore with quota manager
core = TwinCore(
    vessel_id="US-AK-FVEILEEN-51",
    quota_path="quota",
    quota_enabled=True,
)

# Set up quotas
core.quota.set_species_quota("chinook", 1000.0)
core.quota.set_species_quota("coho", 800.0)

# Log catches during operations
core.quota.log_catch("chinook", 50.0, lat, lon, "purse_seine")
core.quota.log_catch("coho", 30.0, lat, lon, "gillnet")

# Check status in snapshot
snapshot = core.build_snapshot()
quota_status = snapshot.get("quota", {})

for species, info in quota_status.items():
    print(f"{species}: {info['percent_used']:.1f}% used")

# Use in WatcherRegistry
frame = core.quota.get_watcher_frame()
actions = core.watchers.evaluate(frame)
```

## Testing

### Test Organization

Test file: `twin/tests/test_quota_manager.py`

**Test Classes:**
- `TestSpeciesQuota`: Dataclass validation (8 tests)
- `TestCatchEvent`: Catch event validation (10 tests)
- `TestQuotaManagerInit`: Initialization (4 tests)
- `TestQuotaManagement`: Quota CRUD (11 tests)
- `TestCatchLogging`: Catch operations (11 tests)
- `TestQuotaQueries`: Quota queries (6 tests)
- `TestAnalytics`: Analytics and projections (7 tests)
- `TestAlerts`: Alert generation (6 tests)
- `TestIntegration`: TwinCore integration (4 tests)
- `TestPersistence`: JSONL persistence (4 tests)
- `TestEdgeCases`: Edge cases (11 tests)

**Total: 82 tests**

### Running Tests

```bash
# Run all quota manager tests
pytest twin/tests/test_quota_manager.py -v

# Run specific test class
pytest twin/tests/test_quota_manager.py::TestCatchLogging -v

# Run specific test
pytest twin/tests/test_quota_manager.py::TestCatchLogging::test_log_catch -v

# Run with coverage
pytest twin/tests/test_quota_manager.py --cov=twin/quota_manager --cov-report=html

# Run with verbose output
pytest twin/tests/test_quota_manager.py -vv
```

### Test Coverage

**Validation Tests:**
- Species validation (valid and invalid)
- Position validation (lat/lon ranges)
- Weight validation (positive, zero, negative)
- Quota source validation
- Reserve percent validation (0-100)
- Total limit validation (positive)
- Current catch validation (non-negative, not exceeding total)

**Business Logic Tests:**
- Quota availability checks
- Catch deduction logic
- Release restoration logic
- Alert threshold triggering
- Alert deduplication

**Analytics Tests:**
- Catch rate calculation
- Exhaustion projection
- Bycatch reporting
- Percent used calculation

**Integration Tests:**
- TwinCore initialization
- Watcher frame generation
- Snapshot inclusion
- Persistence roundtrip

### Test Data

**Constants:**
```python
T0 = 1_753_478_400_000_000_000  # Fixed epoch ns
SITKA_LAT, SITKA_LON = 57.0531, -135.3300
```

**Fixtures:**
- `tmp_path`: pytest temporary directory for persistence tests

### Test Patterns

```python
# Pattern 1: Validation testing
def test_invalid_species_raises():
    with pytest.raises(ValueError, match="Invalid species"):
        SpeciesQuota(species="tuna", total_limit_lb=1000.0)

# Pattern 2: Business logic testing
def test_log_catch_insufficient_quota_raises():
    qm = QuotaManager(storage_path=None)
    qm.set_species_quota("chinook", 100.0, reserve_percent=10.0)
    with pytest.raises(ValueError, match="Insufficient quota"):
        qm.log_catch("chinook", 95.0, lat, lon, "purse_seine")

# Pattern 3: Persistence testing
def test_quota_persistence_roundtrip(tmp_path):
    qm1 = QuotaManager(storage_path=tmp_path)
    qm1.set_species_quota("chinook", 1000.0)

    qm2 = QuotaManager(storage_path=tmp_path)
    assert qm2.quotas["chinook"].total_limit_lb == 1000.0
```

## Constants and Configuration

### Global Constants

```python
# Record kind identifiers
KIND_QUOTA = "species_quota"
KIND_CATCH = "catch_event"

# Valid species
VALID_SPECIES = frozenset({
    "chinook", "coho", "sockeye", "pink", "chum",
    "halibut", "cod", "black_cod",
    "crab", "king_crab", "snow_crab", "dungeness_crab",
})

# Quota sources
QUOTA_SOURCES = frozenset({"IFQ", "CDQ", "community", "state", "federal"})

# Alert thresholds
ALERT_THRESHOLDS = [80.0, 90.0, 95.0, 100.0]

# Maximum catch events in memory
MAX_CATCHES = 5000

# Default reserve percentage
DEFAULT_RESERVE_PERCENT = 10.0
```

### Configuration Guidelines

**Reserve Percentage:**
- 10%: Standard regulatory buffer
- 15%: Conservative approach
- 20%: High-risk species
- 5%: Low-risk species

**Catch History Limit:**
- Default: 5000 events
- Increase for: Long trips, many small catches
- Decrease for: Memory-constrained environments

**Alert Thresholds:**
- Default: [80, 90, 95, 100]
- Customizable: Modify ALERT_THRESHOLDS constant

## Performance Considerations

### Memory Usage

**Estimates:**
- SpeciesQuota: ~200 bytes per species
- CatchEvent: ~300 bytes per event
- Alert: ~200 bytes per alert
- Total for 10 species, 5000 catches: ~1.5 MB

**Optimization:**
- Catch history limited to MAX_CATCHES
- Deque provides O(1) append/pop
- Dictionary lookups are O(1)

### I/O Performance

**Write Operations:**
- Each catch: 1 file append (~200 bytes)
- Each quota update: 1 file append (~150 bytes)
- Synchronous I/O (safe but slower)
- Immediate flush to disk

**Read Operations:**
- Startup: Full JSONL scan
- In-memory queries: Fast
- No disk reads after startup

**Optimization:**
- Batch catches if possible
- Consider async I/O for high-frequency operations
- Implement file rotation for long-running deployments

### Query Performance

**Time Complexity:**
- `get_species_quota()`: O(1)
- `log_catch()`: O(1) average case
- `get_catch_history()`: O(n) where n = catch count
- `calculate_catch_rate()`: O(n) where n = catch count
- `get_bycatch_report()`: O(n) where n = catch count

**Best Practices:**
- Use `limit` parameter for history queries
- Filter by species when possible
- Cache analytics results for repeated queries

## Troubleshooting

### Common Issues

#### Issue: Quota Not Persisting

**Symptoms:**
- Quotas disappear on restart
- JSONL files not created

**Solution:**
```python
# Ensure storage_path is set
qm = QuotaManager(storage_path="quota")  # Not None

# Check directory permissions
import os
os.makedirs("quota", exist_ok=True)

# Verify files created
assert os.path.exists("quota/quota.jsonl")
```

#### Issue: Insufficient Quota Error

**Symptoms:**
- `ValueError: Insufficient quota for chinook`
- Catch operations fail unexpectedly

**Solution:**
```python
# Check usable quota (excluding reserve)
quota = qm.get_species_quota("chinook")
print(f"Usable: {quota.usable_lb()} lb")
print(f"Remaining: {quota.remaining_lb()} lb")

# Adjust reserve if needed
qm.update_species_quota("chinook", reserve_percent=5.0)
```

#### Issue: Missing Quota Status in Snapshots

**Symptoms:**
- `core.quota` is None
- Snapshot doesn't include quota data

**Solution:**
```python
# Ensure quota_enabled=True
core = TwinCore(quota_enabled=True)

# Check quota manager exists
assert core.quota is not None

# Verify quotas set
core.quota.set_species_quota("chinook", 1000.0)
```

#### Issue: Watcher Frame Empty

**Symptoms:**
- `get_watcher_frame()` returns empty dict
- Watcher rules not triggering

**Solution:**
```python
# Set quotas first
core.quota.set_species_quota("chinook", 1000.0)

# Log some catches
core.quota.log_catch("chinook", 50.0, lat, lon, "purse_seine")

# Get frame
frame = core.quota.get_watcher_frame()
assert "quota_chinook_percent_used" in frame
```

#### Issue: Duplicate Alerts

**Symptoms:**
- Multiple alerts at same threshold
- Alert spam in operations

**Solution:**
```python
# Check alert deduplication state
print(qm._last_alert_levels)

# Should track last alert level per species
# {"chinook": 82.5, "coho": 45.0}
```

## Dependencies

### Stdlib Only

```python
import json      # JSON serialization
import logging   # Logging
import time      # Timestamp generation
import uuid      # Catch ID generation
from collections import deque  # Catch history
from dataclasses import dataclass, field  # Data structures
from datetime import datetime, timezone  # Time handling
from pathlib import Path  # File paths
from typing import Any  # Type hints
```

### No External Dependencies

The QuotaManager uses only Python standard library for:
- Maximum compatibility
- Minimal dependencies
- Easy deployment
- Reliable operation

## Future Enhancements

### Planned Features

1. **Multi-Vessel Pooling**
   - Share quota across vessels
   - Transfer operations
   - Pool analytics

2. **Regulatory Reporting**
   - ADF&G report generation
   - NOAA eVES integration
   - Automatic compliance checks

3. **Economic Analysis**
   - Price per species tracking
   - Revenue optimization
   - Cost-benefit analysis

4. **Advanced Analytics**
   - Seasonal patterns
   - Historical performance
   - Predictive modeling

5. **Mobile Integration**
   - Mobile app API
   - Offline support
   - Sync capabilities

6. **Performance Optimization**
   - Async I/O support
   - Batch operations
   - Caching layer

7. **Data Validation**
   - JSON schema validation
   - Cross-record validation
   - Anomaly detection

## References

### Regulatory

- [ADF&G Commercial Fishing](https://www.adfg.alaska.gov/)
- [NOAA Fisheries Quota Management](https://www.fisheries.noaa.gov/)
- [Alaska IFQ Program](https://www.fisheries.noaa.gov/alaska/commercial-fishing/individual-fishing-quota)

### Technical

- [JSONL Specification](https://jsonlines.org/)
- [Python dataclasses](https://docs.python.org/3/library/dataclasses.html)
- [ISO 8601 Timestamps](https://en.wikipedia.org/wiki/ISO_8601)

### Related Documentation

- `quota_management.md`: User-facing quota system guide
- `twin/core.py`: TwinCore integration
- `twin/watchers.py`: WatcherRegistry integration
- `oplog.md`: Operations log integration

## Support

For questions or issues about the QuotaManager component:

1. Check this documentation
2. Review test examples in `twin/tests/test_quota_manager.py`
3. Examine source code in `twin/quota_manager.py`
4. Contact AELMA development team
