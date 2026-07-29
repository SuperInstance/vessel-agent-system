# CrewFatigueMonitor Component Documentation

## Component Overview

The **CrewFatigueMonitor** is a safety-critical component within the AELMA twin system that monitors crew fatigue levels to prevent fatigue-related incidents at sea. It tracks work hours, rest periods, and watch schedules to calculate comprehensive fatigue metrics and generate alerts when thresholds are exceeded.

### Purpose

- **Safety Compliance**: Enforce maritime work-hour regulations (STCW, USCG, IMO)
- **Fatigue Risk Assessment**: Calculate real-time fatigue scores based on cumulative work hours
- **Watch Scheduling**: Manage watch rotation patterns (6-on/6-off, 4-on/8-off, etc.)
- **Incident Prevention**: Generate alerts when fatigue levels become dangerous
- **Operational Planning**: Predict fatigue risk for planned future work

### Use Cases

1. **Real-time Monitoring**: Track crew fatigue levels during active operations
2. **Watch Schedule Compliance**: Ensure work follows defined watch rotations
3. **Rest Period Tracking**: Monitor rest quality and duration
4. **Fatigue Alerts**: Generate warnings when thresholds are exceeded
5. **Planning Support**: Predict fatigue impact of planned work hours
6. **Safety Reporting**: Generate compliance reports for regulatory bodies

### Integration

The CrewFatigueMonitor integrates with:

- **TwinCore**: Part of the digital twin's safety infrastructure
- **WatcherRegistry**: Monitors fatigue as a vessel safety metric
- **Safety Systems**: Alerts propagate to bridge and safety dashboards
- **Report Generation**: Data used for safety compliance reports

## Architecture

### Data Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Crew Member   │────▶│ Work Period Log  │────▶│ Fatigue Metrics │
│   (crew_id)     │     │ (start, end)     │     │ (score, hours)  │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                                │
                                                                ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Watch Schedule │────▶│ Rest Period Log  │────▶│  Fatigue Alerts │
│ (rotation)     │     │ (duration)       │     │ (thresholds)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

### Data Structures

#### CrewMember
Basic crew identification and status:
- `crew_id`: Unique identifier
- `name`: Full name
- `role`: Position on vessel (captain, mate, engineer, deckhand)
- `vessel_id`: Vessel identifier
- `status`: Availability status (active, on_leave, sick, injured, unavailable)

#### WorkHours
Recorded work/rest periods:
- `crew_id`: Crew member identifier
- `start_time_ns`: Period start timestamp (nanoseconds)
- `end_time_ns`: Period end timestamp (nanoseconds)
- `activity_type`: Type of work (NAVIGATION, GEAR_HANDLING, DECK_WORK, etc.)
- `watch_position`: Watch position (optional)

#### FatigueMetrics
Comprehensive fatigue assessment:
- `crew_id`: Crew member identifier
- `fatigue_score`: Overall fatigue score (0-100)
- `hours_worked_24h`: Hours worked in last 24 hours
- `hours_worked_48h`: Hours worked in last 48 hours
- `hours_worked_72h`: Hours worked in last 72 hours
- `hours_rest_24h`: Hours of rest in last 24 hours
- `last_break_ns`: Timestamp of last break
- `continuous_work_ns`: Duration of current continuous work period
- `watch_compliance`: Schedule adherence score (0-1)

#### WatchSchedule
Watch rotation configuration:
- `crew_id`: Crew member identifier
- `watch_type`: Rotation type (6-on/6-off, 4-on/8-off, etc.)
- `start_time_ns`: Watch start timestamp
- `duration_ns`: Watch duration
- `rotation_ns`: Rotation period
- `custom_name`: Custom watch name (for CUSTOM type)

#### FatigueAlert
Fatigue threshold warning:
- `crew_id`: Crew member identifier
- `alert_type`: Type of alert (continuous_work, insufficient_rest, etc.)
- `severity`: Severity level (info, low, medium, high, critical, danger)
- `fatigue_score`: Fatigue score at alert time
- `timestamp_ns`: Alert timestamp
- `message`: Human-readable alert message
- `metrics`: Full fatigue metrics at alert time

### Storage Architecture

The component uses JSONL (JSON Lines) format for persistent storage:

**File Structure**:
```
crew_fatigue_data/
├── crew.jsonl              # Crew member records
├── work_hours.jsonl        # Work/rest period logs
└── fatigue_alerts.jsonl    # Generated fatigue alerts
```

**JSONL Format**: One JSON object per line, append-only writes for durability

## API Reference

### CrewFatigueMonitor

#### Constructor

```python
CrewFatigueMonitor(vessel_id: str, data_dir: str | Path = "crew_fatigue_data")
```

Initialize the crew fatigue monitor.

**Parameters**:
- `vessel_id`: Vessel identifier (required)
- `data_dir`: Directory for JSONL persistence files (default: "crew_fatigue_data")

**Returns**: CrewFatigueMonitor instance

**Raises**: `ValueError` if vessel_id is empty

**Example**:
```python
monitor = CrewFatigueMonitor(
    vessel_id="fv_eileen",
    data_dir="/data/crew_fatigue"
)
```

### Crew Management

#### add_crew_member

```python
add_crew_member(
    crew_id: str,
    name: str,
    role: str,
    status: CrewStatus | str = CrewStatus.ACTIVE
) -> CrewMember
```

Add a crew member to the monitor.

**Parameters**:
- `crew_id`: Unique identifier for the crew member
- `name`: Full name of the crew member
- `role`: Role on the vessel (captain, mate, engineer, deckhand)
- `status`: Current availability status (default: ACTIVE)

**Returns**: Created CrewMember object

**Raises**: `ValueError` if crew_id already exists

**Example**:
```python
crew = monitor.add_crew_member(
    crew_id="crew_001",
    name="John Smith",
    role="captain",
    status=CrewStatus.ACTIVE
)
```

#### get_crew_member

```python
get_crew_member(crew_id: str) -> CrewMember | None
```

Get a crew member by ID.

**Parameters**:
- `crew_id`: Crew member identifier

**Returns**: CrewMember object or None if not found

#### list_crew_members

```python
list_crew_members() -> list[CrewMember]
```

List all crew members.

**Returns**: List of all CrewMember objects

#### update_crew_status

```python
update_crew_status(crew_id: str, status: CrewStatus | str) -> bool
```

Update crew member status.

**Parameters**:
- `crew_id`: Crew member identifier
- `status`: New status (ACTIVE, ON_LEAVE, SICK, INJURED, UNAVAILABLE)

**Returns**: True if updated, False if crew member not found

### Work Period Logging

#### log_work_period

```python
log_work_period(
    crew_id: str,
    start_time_ns: int,
    end_time_ns: int,
    activity_type: ActivityType | str,
    watch_position: str | None = None
) -> WorkHours
```

Log a work period for a crew member.

**Parameters**:
- `crew_id`: Crew member identifier
- `start_time_ns`: Work period start timestamp (nanoseconds)
- `end_time_ns`: Work period end timestamp (nanoseconds)
- `activity_type`: Type of work performed (NAVIGATION, GEAR_HANDLING, etc.)
- `watch_position`: Watch position (optional)

**Returns**: Created WorkHours object

**Raises**: `ValueError` if crew member not found or validation fails

**Example**:
```python
import time

# Log a 6-hour navigation watch
start_ns = time.time_ns()
end_ns = start_ns + (6 * 3600 * 1_000_000_000)

work = monitor.log_work_period(
    crew_id="crew_001",
    start_time_ns=start_ns,
    end_time_ns=end_ns,
    activity_type=ActivityType.NAVIGATION,
    watch_position="bridge"
)
```

#### log_break

```python
log_break(
    crew_id: str,
    start_time_ns: int,
    duration_ns: int
) -> WorkHours
```

Log a break period for a crew member.

**Parameters**:
- `crew_id`: Crew member identifier
- `start_time_ns`: Break start timestamp (nanoseconds)
- `duration_ns`: Break duration in nanoseconds

**Returns**: Created WorkHours object with REST activity type

**Example**:
```python
# Log an 8-hour rest period
break_period = monitor.log_break(
    crew_id="crew_001",
    start_time_ns=start_ns,
    duration_ns=8 * 3600 * 1_000_000_000
)
```

#### get_work_hours

```python
get_work_hours(
    crew_id: str,
    since_ns: int | None = None,
    until_ns: int | None = None
) -> list[WorkHours]
```

Get work hours for a crew member, optionally filtered by time.

**Parameters**:
- `crew_id`: Crew member identifier
- `since_ns`: Filter by start time >= this timestamp (optional)
- `until_ns`: Filter by end time <= this timestamp (optional)

**Returns**: List of WorkHours objects matching filters

### Fatigue Metrics

#### get_fatigue_score

```python
get_fatigue_score(crew_id: str, now_ns: int | None = None) -> float
```

Calculate fatigue score for a crew member (0-100).

**Parameters**:
- `crew_id`: Crew member identifier
- `now_ns`: Current timestamp in nanoseconds (default: current time)

**Returns**: Fatigue score between 0 and 100

**Raises**: `ValueError` if crew member not found

**Example**:
```python
score = monitor.get_fatigue_score("crew_001")
if score > 70:
    print(f"High fatigue alert: {score}")
```

#### get_fatigue_metrics

```python
get_fatigue_metrics(crew_id: str, now_ns: int | None = None) -> FatigueMetrics
```

Get comprehensive fatigue metrics for a crew member.

**Parameters**:
- `crew_id`: Crew member identifier
- `now_ns`: Current timestamp in nanoseconds (default: current time)

**Returns**: FatigueMetrics object with full metrics

**Raises**: `ValueError` if crew member not found

**Example**:
```python
metrics = monitor.get_fatigue_metrics("crew_001")
print(f"Fatigue Score: {metrics.fatigue_score}")
print(f"Hours worked (24h): {metrics.hours_worked_24h}")
print(f"Hours rest (24h): {metrics.hours_rest_24h}")
print(f"Continuous work: {metrics.continuous_work_ns / (3600e9)} hours")
```

#### get_all_fatigue_metrics

```python
get_all_fatigue_metrics(now_ns: int | None = None) -> dict[str, FatigueMetrics]
```

Get fatigue metrics for all crew members.

**Parameters**:
- `now_ns`: Current timestamp in nanoseconds (default: current time)

**Returns**: Dictionary mapping crew_id to FatigueMetrics

#### get_fatigue_alerts

```python
get_fatigue_alerts(
    crew_id: str | None = None,
    since_ns: int | None = None,
    min_severity: AlertSeverity | None = None
) -> list[FatigueAlert]
```

Get fatigue alerts, optionally filtered.

**Parameters**:
- `crew_id`: Filter by crew member (optional, default: all)
- `since_ns`: Filter by timestamp >= this (optional)
- `min_severity`: Filter by minimum severity level (optional)

**Returns**: List of FatigueAlert objects matching filters, sorted by timestamp (newest first)

**Example**:
```python
# Get all high-severity alerts for a crew member
alerts = monitor.get_fatigue_alerts(
    crew_id="crew_001",
    min_severity=AlertSeverity.HIGH
)

# Get all alerts in the last 24 hours
import time
day_ago = time.time_ns() - (24 * 3600 * 1_000_000_000)
recent_alerts = monitor.get_fatigue_alerts(since_ns=day_ago)
```

### Watch Schedules

#### set_watch_schedule

```python
set_watch_schedule(
    crew_id: str,
    watch_type: WatchType | str,
    start_time_ns: int,
    duration_ns: int = 0,
    rotation_ns: int = 0,
    custom_name: str | None = None
) -> WatchSchedule
```

Set a watch schedule for a crew member.

**Parameters**:
- `crew_id`: Crew member identifier
- `watch_type`: Type of watch rotation (SIX_ON_SIX_OFF, FOUR_ON_EIGHT_OFF, etc.)
- `start_time_ns`: Watch start timestamp (nanoseconds)
- `duration_ns`: Watch duration in nanoseconds (0 for default based on type)
- `rotation_ns`: Rotation period in nanoseconds (0 for default based on type)
- `custom_name`: Name for custom watch types (optional)

**Returns**: Created WatchSchedule object

**Raises**: `ValueError` if crew member not found or validation fails

**Example**:
```python
# Set a 6-on/6-off watch schedule
schedule = monitor.set_watch_schedule(
    crew_id="crew_001",
    watch_type=WatchType.SIX_ON_SIX_OFF,
    start_time_ns=time.time_ns()
)
```

#### get_watch_schedules

```python
get_watch_schedules(crew_id: str) -> list[WatchSchedule]
```

Get watch schedules for a crew member.

**Parameters**:
- `crew_id`: Crew member identifier

**Returns**: List of WatchSchedule objects

**Raises**: `ValueError` if crew member not found

### Fatigue Prediction

#### predict_fatigue_risk

```python
predict_fatigue_risk(
    crew_id: str,
    future_work_hours: float,
    now_ns: int | None = None
) -> float
```

Predict fatigue risk for planned future work.

**Parameters**:
- `crew_id`: Crew member identifier
- `future_work_hours`: Additional work hours being planned
- `now_ns`: Current timestamp in nanoseconds (default: current time)

**Returns**: Predicted fatigue score (0-100)

**Raises**: `ValueError` if crew member not found

**Example**:
```python
# Predict fatigue if we add 4 more hours of work
predicted_score = monitor.predict_fatigue_risk(
    crew_id="crew_001",
    future_work_hours=4.0
)

if predicted_score > 80:
    print("WARNING: Planned work will cause critical fatigue")
```

### Monitoring State

#### to_dict

```python
to_dict(now_ns: int | None = None) -> dict[str, Any]
```

Create a snapshot of the monitor state.

**Parameters**:
- `now_ns`: Current timestamp in nanoseconds (default: current time)

**Returns**: Dictionary containing monitor state

**Example**:
```python
snapshot = monitor.to_dict()
print(f"Crew count: {snapshot['crew_count']}")
print(f"Fatigue metrics: {snapshot['fatigue_metrics']}")
print(f"Recent alerts: {snapshot['recent_alerts']}")
```

## Fatigue Calculation

### Calculation Model

The fatigue score (0-100) is calculated from three components:

```python
fatigue_score = work_fatigue + rest_fatigue + continuous_fatigue
```

### Component Breakdown

#### 1. Work Fatigue (50% weight)

```python
work_fatigue = min(100, (weighted_hours / 24.0) * 50)
```

- Calculates weighted work hours in 24-hour window
- Weighted by activity type (see Activity Weights)
- Capped at 24 hours for full score contribution

#### 2. Rest Fatigue (30% weight)

```python
rest_deficit = max(0, 8.0 - rest_24h)
rest_fatigue = min(100, (rest_deficit / 8.0) * 30)
```

- Calculates deficit from 8-hour minimum rest requirement
- Assumes 8 hours rest is optimal in 24-hour period
- Increases as rest falls below 8 hours

#### 3. Continuous Work Fatigue (20% weight)

```python
continuous_fatigue = min(100, (continuous_hours / 16.0) * 20)
```

- Tracks current continuous work period duration
- Assumes 16 hours continuous work is maximum safe duration
- Increases linearly with continuous work time

### Time Windows

Fatigue calculation uses multiple time windows:

- **24-hour window**: Primary fatigue assessment period
- **48-hour window**: Extended fatigue tracking
- **72-hour window**: Long-term fatigue accumulation

### Activity Weights

Different activities contribute differently to fatigue:

| Activity Type | Weight | Description |
|--------------|--------|-------------|
| NAVIGATION | 1.5x | High cognitive load |
| GEAR_HANDLING | 1.4x | High physical load |
| DECK_WORK | 1.2x | Medium physical load |
| MAINTENANCE | 1.1x | Medium load |
| REST | 0.0x | No fatigue contribution |
| STANDBY | 0.5x | Low load |

**Example**: 1 hour of navigation counts as 1.5 hours toward work fatigue.

## Alert Thresholds

### Alert Levels

The system generates alerts at multiple severity levels:

#### HIGH Alert
**Condition**: Continuous work > 12 hours
**Severity**: HIGH
**Message**: "Continuous work exceeds 12 hours"

#### CRITICAL Alert
**Condition**: Continuous work > 16 hours
**Severity**: CRITICAL
**Message**: "CRITICAL: Continuous work exceeds 16 hours"

#### DANGER Alert
**Condition**: >24 hours without 8-hour rest
**Severity**: DANGER
**Message**: "DANGER: >24h without adequate 8h rest"

#### MULTIPLE Fatigue Alert
**Condition**: >72 hours work with <24-hour rest in last 24h
**Severity**: CRITICAL
**Message**: "CRITICAL: >72h work with <24h rest in last 24h"

### Severity Hierarchy

Alert severities are ordered from lowest to highest:

```
INFO < LOW < MEDIUM < HIGH < CRITICAL < DANGER
```

When filtering alerts by `min_severity`, all alerts at or above that level are returned.

### Alert Generation

Alerts are automatically generated when:
1. A work period is logged via `log_work_period()`
2. Fatigue metrics are calculated via `get_fatigue_metrics()`
3. Alert checks are triggered internally

Alerts are persisted immediately to `fatigue_alerts.jsonl` for durability.

## Watch Types

### Standard Watch Rotations

#### SIX_ON_SIX_OFF
**Pattern**: 6 hours on, 6 hours off
**Duration**: 6 hours
**Rotation**: 12 hours
**Typical Use**: Standard bridge watch rotation

```
Work: [06:00-12:00] Rest: [12:00-18:00] Work: [18:00-00:00] ...
```

#### FOUR_ON_EIGHT_OFF
**Pattern**: 4 hours on, 8 hours off
**Duration**: 4 hours
**Rotation**: 12 hours
**Typical Use**: High-intensity work periods

```
Work: [06:00-10:00] Rest: [10:00-18:00] Work: [18:00-22:00] ...
```

#### TWELVE_ON_TWELVE_OFF
**Pattern**: 12 hours on, 12 hours off
**Duration**: 12 hours
**Rotation**: 24 hours
**Typical Use**: Two-crew rotations

```
Work: [06:00-18:00] Rest: [18:00-06:00] Work: [06:00-18:00] ...
```

#### CUSTOM
**Pattern**: User-defined rotation
**Duration**: User-specified
**Rotation**: User-specified
**Typical Use**: Special operations, non-standard schedules

```python
schedule = monitor.set_watch_schedule(
    crew_id="crew_001",
    watch_type=WatchType.CUSTOM,
    start_time_ns=time.time_ns(),
    duration_ns=8 * 3600 * 1_000_000_000,  # 8 hours
    rotation_ns=16 * 3600 * 1_000_000_000,  # 16 hours total
    custom_name="Extended Watch"
)
```

### Watch Schedule Compliance

The system tracks watch compliance through the `watch_compliance` metric (0-1 score):

- **1.0**: Full compliance with schedule
- **0.5**: Partial deviation
- **0.0**: No compliance

Compliance is calculated by comparing actual work periods to scheduled watch times.

## Activity Types

### Activity Classification

#### NAVIGATION
**Weight**: 1.5x (high cognitive load)
**Description**: Bridge operations, navigation watch, route planning
**Examples**: Conning the vessel, radar watch, chart work

#### GEAR_HANDLING
**Weight**: 1.4x (high physical load)
**Description**: Fishing gear deployment and retrieval
**Examples**: Setting gear, hauling gear, gear maintenance

#### DECK_WORK
**Weight**: 1.2x (medium physical load)
**Description**: General deck operations
**Examples**: Cargo handling, line handling, deck maintenance

#### MAINTENANCE
**Weight**: 1.1x (medium load)
**Description**: Equipment maintenance and repairs
**Examples**: Engine room work, electrical repairs, plumbing

#### REST
**Weight**: 0.0x (no fatigue contribution)
**Description**: Sleep, rest periods, off-duty time
**Examples**: Sleeping, meal breaks, off-watch rest

#### STANDBY
**Weight**: 0.5x (low load)
**Description**: On-call but not actively working
**Examples**: On-call standby, alert but resting

### Activity Type Impact

**Example Calculation**:
```
Work periods in 24h:
- 4 hours NAVIGATION (1.5x) = 6.0 weighted hours
- 4 hours GEAR_HANDLING (1.4x) = 5.6 weighted hours
- 4 hours DECK_WORK (1.2x) = 4.8 weighted hours
- 8 hours REST (0.0x) = 0.0 weighted hours

Total weighted hours: 16.4 hours
Work fatigue: (16.4 / 24.0) * 50 = 34.2
```

## Usage Examples

### Basic Setup

```python
from twin.crew_fatigue import CrewFatigueMonitor, ActivityType, WatchType
import time

# Initialize monitor
monitor = CrewFatigueMonitor(
    vessel_id="fv_eileen",
    data_dir="/data/crew_fatigue"
)
```

### Adding Crew Members

```python
# Add captain
captain = monitor.add_crew_member(
    crew_id="crew_001",
    name="John Smith",
    role="captain",
    status="active"
)

# Add mate
mate = monitor.add_crew_member(
    crew_id="crew_002",
    name="Jane Doe",
    role="mate"
)

# Add engineer
engineer = monitor.add_crew_member(
    crew_id="crew_003",
    name="Bob Johnson",
    role="engineer"
)
```

### Logging Work Periods

```python
import time

# Get current time
now_ns = time.time_ns()
one_hour_ns = 3600 * 1_000_000_000

# Log 6-hour navigation watch
monitor.log_work_period(
    crew_id="crew_001",
    start_time_ns=now_ns,
    end_time_ns=now_ns + (6 * one_hour_ns),
    activity_type=ActivityType.NAVIGATION,
    watch_position="bridge"
)

# Log 4-hour gear handling
monitor.log_work_period(
    crew_id="crew_002",
    start_time_ns=now_ns,
    end_time_ns=now_ns + (4 * one_hour_ns),
    activity_type=ActivityType.GEAR_HANDLING,
    watch_position="deck"
)
```

### Logging Rest Periods

```python
# Log 8-hour rest period
monitor.log_break(
    crew_id="crew_001",
    start_time_ns=now_ns + (6 * one_hour_ns),
    duration_ns=8 * one_hour_ns
)
```

### Setting Watch Schedules

```python
# Set 6-on/6-off watch for captain
monitor.set_watch_schedule(
    crew_id="crew_001",
    watch_type=WatchType.SIX_ON_SIX_OFF,
    start_time_ns=now_ns
)

# Set 4-on/8-off watch for mate
monitor.set_watch_schedule(
    crew_id="crew_002",
    watch_type=WatchType.FOUR_ON_EIGHT_OFF,
    start_time_ns=now_ns
)
```

### Monitoring Fatigue

```python
# Get current fatigue score
score = monitor.get_fatigue_score("crew_001")
print(f"Captain fatigue score: {score}")

# Get comprehensive metrics
metrics = monitor.get_fatigue_metrics("crew_001")
print(f"Hours worked (24h): {metrics.hours_worked_24h}")
print(f"Hours worked (48h): {metrics.hours_worked_48h}")
print(f"Hours worked (72h): {metrics.hours_worked_72h}")
print(f"Hours rest (24h): {metrics.hours_rest_24h}")
print(f"Continuous work: {metrics.continuous_work_ns / (3600e9)} hours")
print(f"Watch compliance: {metrics.watch_compliance}")
```

### Getting All Crew Metrics

```python
# Get metrics for all crew
all_metrics = monitor.get_all_fatigue_metrics()

for crew_id, metrics in all_metrics.items():
    print(f"{crew_id}: Score {metrics.fatigue_score:.1f}, "
          f"Worked {metrics.hours_worked_24h:.1f}h, "
          f"Rested {metrics.hours_rest_24h:.1f}h")
```

### Checking Alerts

```python
# Get recent alerts for a crew member
alerts = monitor.get_fatigue_alerts(
    crew_id="crew_001",
    min_severity=AlertSeverity.HIGH
)

for alert in alerts:
    print(f"[{alert.severity}] {alert.message}")
    print(f"  Fatigue score: {alert.fatigue_score}")
    print(f"  Time: {alert.timestamp_ns}")
```

### Predicting Fatigue Risk

```python
# Check if adding 4 hours of work is safe
current_score = monitor.get_fatigue_score("crew_001")
predicted_score = monitor.predict_fatigue_risk(
    crew_id="crew_001",
    future_work_hours=4.0
)

print(f"Current fatigue: {current_score}")
print(f"Predicted fatigue after 4h work: {predicted_score}")

if predicted_score > 80:
    print("WARNING: Planned work exceeds safe fatigue levels")
elif predicted_score > current_score + 20:
    print("CAUTION: Significant fatigue increase expected")
```

### Complete Watch Cycle Example

```python
from twin.crew_fatigue import (
    CrewFatigueMonitor, ActivityType, WatchType, AlertSeverity
)
import time

# Initialize
monitor = CrewFatigueMonitor("fv_eileen")

# Add crew
monitor.add_crew_member("crew_001", "John Smith", "captain")

# Set watch schedule
monitor.set_watch_schedule(
    "crew_001", WatchType.SIX_ON_SIX_OFF, time.time_ns()
)

# Simulate a watch cycle
now_ns = time.time_ns()
six_hours = 6 * 3600 * 1_000_000_000

# First watch (6 hours navigation)
monitor.log_work_period(
    "crew_001", now_ns, now_ns + six_hours,
    ActivityType.NAVIGATION, "bridge"
)

# Check fatigue after work
metrics = monitor.get_fatigue_metrics("crew_001", now_ns + six_hours)
print(f"After 6h work: Score {metrics.fatigue_score:.1f}")

# Rest period (6 hours)
monitor.log_break("crew_001", now_ns + six_hours, six_hours)

# Check fatigue after rest
metrics = monitor.get_fatigue_metrics("crew_001", now_ns + (2 * six_hours))
print(f"After 6h rest: Score {metrics.fatigue_score:.1f}")

# Second watch (6 hours navigation)
monitor.log_work_period(
    "crew_001", now_ns + (2 * six_hours), now_ns + (3 * six_hours),
    ActivityType.NAVIGATION, "bridge"
)

# Check final fatigue
metrics = monitor.get_fatigue_metrics("crew_001", now_ns + (3 * six_hours))
print(f"After second 6h work: Score {metrics.fatigue_score:.1f}")

# Check for alerts
alerts = monitor.get_fatigue_alerts("crew_001")
if alerts:
    print(f"Generated {len(alerts)} alerts")
    for alert in alerts:
        print(f"  [{alert.severity}] {alert.message}")
```

## Testing

### Test Coverage

The component has comprehensive test coverage with 71+ test cases across multiple categories:

### Test Organization

#### 1. Crew Member Tests (8 tests)
- Create valid crew member
- Validation tests (empty id, name, role, vessel_id)
- Status conversion
- Serialization (to_dict, from_dict)

#### 2. Work Hours Tests (9 tests)
- Create valid work hours
- Validation (start after end, equal times, negative time)
- Activity type conversion
- Duration calculation
- Serialization

#### 3. Fatigue Metrics Tests (7 tests)
- Create valid fatigue metrics
- Validation (score range, negative hours, compliance range)
- Serialization

#### 4. Watch Schedule Tests (10 tests)
- Create standard watch types (6-on/6-off, 4-on/8-off, 12-on/12-off)
- Validation (negative duration, negative rotation)
- Type conversion
- Serialization

#### 5. Fatigue Alert Tests (7 tests)
- Create valid fatigue alert
- Validation (score range, empty message)
- Type conversion
- Serialization

#### 6. Crew Fatigue Monitor Tests (19 tests)
- Monitor creation and validation
- Crew management (add, get, list, update)
- Work period logging
- Break logging
- Work hours retrieval with filters
- Fatigue score calculation
- Fatigue metrics retrieval
- All crew metrics
- Watch schedule management
- Fatigue risk prediction
- Monitor snapshot

#### 7. Fatigue Alert Generation Tests (6 tests)
- Continuous work HIGH alert (>12 hours)
- Continuous work CRITICAL alert (>16 hours)
- Insufficient rest DANGER alert (>24h without 8h rest)
- Multiple fatigue alert (>72h with <24h rest)
- Alert filtering (by crew, severity, time)

#### 8. Persistence Tests (3 tests)
- Crew member persistence
- Work hours persistence
- Alerts persistence

#### 9. Integration Tests (3 tests)
- Complete watch cycle workflow
- Multiple crew members monitoring
- Fatigue trend over time

### Running Tests

```bash
# Run all tests
pytest twin/tests/test_crew_fatigue.py

# Run specific test class
pytest twin/tests/test_crew_fatigue.py::TestCrewFatigueMonitor

# Run specific test
pytest twin/tests/test_crew_fatigue.py::TestCrewFatigueMonitor::test_add_crew_member

# Run with coverage
pytest --cov=twin.crew_fatigue twin/tests/test_crew_fatigue.py
```

### Test Constants

Tests use deterministic timestamps for reproducibility:

```python
T0 = 1_753_478_400_000_000_000  # Fixed epoch ns
ONE_HOUR_NS = int(3600 * 1e9)   # 1 hour in nanoseconds
SIX_HOURS_NS = 6 * ONE_HOUR_NS
TWELVE_HOURS_NS = 12 * ONE_HOUR_NS
TWENTY_FOUR_HOURS_NS = 24 * ONE_HOUR_NS
```

### Test Patterns

#### Deterministic Testing
All tests use fixed timestamps (`T0`) to ensure reproducibility:

```python
def test_log_work_period(self):
    monitor.log_work_period(
        "crew_001",
        start_time_ns=T0,
        end_time_ns=T0 + SIX_HOURS_NS,
        activity_type=ActivityType.NAVIGATION
    )
    assert work.duration_hours == 6.0
```

#### Temporary Directories
Tests use temporary directories for file system operations:

```python
from tempfile import TemporaryDirectory

def test_crew_persistence(self):
    with TemporaryDirectory() as tmpdir:
        monitor1 = CrewFatigueMonitor("vessel_001", tmpdir)
        monitor1.add_crew_member("crew_001", "John Smith", "captain")

        # Create new monitor - should load persisted data
        monitor2 = CrewFatigueMonitor("vessel_001", tmpdir)
        crew = monitor2.get_crew_member("crew_001")
        assert crew is not None
```

## Data Formats

### JSONL Format

All persistence uses JSONL (JSON Lines) format - one JSON object per line:

**crew.jsonl**:
```json
{"crew_id": "crew_001", "name": "John Smith", "role": "captain", "vessel_id": "fv_eileen", "status": "active"}
{"crew_id": "crew_002", "name": "Jane Doe", "role": "mate", "vessel_id": "fv_eileen", "status": "active"}
```

**work_hours.jsonl**:
```json
{"crew_id": "crew_001", "start_time_ns": 1753478400000000000, "end_time_ns": 1753478760000000000, "activity_type": "NAVIGATION", "watch_position": "bridge"}
{"crew_id": "crew_001", "start_time_ns": 1753478760000000000, "end_time_ns": 1753479480000000000, "activity_type": "REST", "watch_position": null}
```

**fatigue_alerts.jsonl**:
```json
{"crew_id": "crew_001", "alert_type": "continuous_work_high", "severity": "high", "fatigue_score": 65.5, "timestamp_ns": 1753479120000000000, "message": "Continuous work exceeds 12 hours: 13.0h", "metrics": {...}}
```

### Serialization Methods

All data classes support bidirectional serialization:

```python
# To dictionary
crew_dict = crew.to_dict()
work_dict = work.to_dict()
metrics_dict = metrics.to_dict()
alert_dict = alert.to_dict()
schedule_dict = schedule.to_dict()

# From dictionary
crew = CrewMember.from_dict(crew_dict)
work = WorkHours.from_dict(work_dict)
metrics = FatigueMetrics.from_dict(metrics_dict)
alert = FatigueAlert.from_dict(alert_dict)
schedule = WatchSchedule.from_dict(schedule_dict)
```

## Best Practices

### 1. Timestamp Management

Always use nanoseconds for timestamps:

```python
import time

# Get current time in nanoseconds
now_ns = time.time_ns()

# Calculate duration in nanoseconds
one_hour_ns = 3600 * 1_000_000_000
six_hours_ns = 6 * one_hour_ns

# Log work period
monitor.log_work_period(
    crew_id="crew_001",
    start_time_ns=now_ns,
    end_time_ns=now_ns + six_hours_ns,
    activity_type=ActivityType.NAVIGATION
)
```

### 2. Activity Type Selection

Choose appropriate activity types for accurate fatigue calculation:

```python
# High cognitive load
ActivityType.NAVIGATION  # Bridge watch, navigation

# High physical load
ActivityType.GEAR_HANDLING  # Gear deployment/retrieval

# Medium physical load
ActivityType.DECK_WORK  # General deck operations

# No fatigue contribution
ActivityType.REST  # Sleep, rest periods
```

### 3. Alert Monitoring

Regularly check for alerts in production:

```python
# Check for high-severity alerts
alerts = monitor.get_fatigue_alerts(min_severity=AlertSeverity.HIGH)

for alert in alerts:
    # Log to safety system
    safety_system.log_alert(alert.to_dict())

    # Notify bridge if critical/danger
    if alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.DANGER]:
        bridge_system.notify_captain(alert)
```

### 4. Fatigue Prediction

Use fatigue prediction for operational planning:

```python
# Before assigning additional work
predicted_score = monitor.predict_fatigue_risk(
    crew_id="crew_001",
    future_work_hours=4.0
)

if predicted_score > 70:
    # Consider alternative crew assignment
    pass
elif predicted_score > 50:
    # Plan for additional rest period
    pass
```

### 5. Watch Schedule Management

Set watch schedules for compliance tracking:

```python
# Standard watch rotation
monitor.set_watch_schedule(
    crew_id="crew_001",
    watch_type=WatchType.SIX_ON_SIX_OFF,
    start_time_ns=time.time_ns()
)

# Check compliance
metrics = monitor.get_fatigue_metrics("crew_001")
if metrics.watch_compliance < 0.8:
    print("WARNING: Low watch schedule compliance")
```

### 6. Regular State Snapshots

Create regular snapshots for monitoring and reporting:

```python
# Hourly snapshot
import time

def hourly_snapshot():
    snapshot = monitor.to_dict()

    # Log to monitoring system
    monitoring_system.log(snapshot)

    # Check for concerning patterns
    for crew_id, metrics in snapshot["fatigue_metrics"].items():
        if metrics["fatigue_score"] > 70:
            alert_safety_team(crew_id, metrics)
```

## Safety Considerations

### 1. Regulatory Compliance

The system aligns with maritime work-hour regulations:

- **STCW Convention**: Standards of Training, Certification and Watchkeeping
- **USCG Regulations**: United States Coast Guard work-hour limits
- **ILO Convention**: International Labour Organization work-hour standards

### 2. Threshold Configuration

Alert thresholds are based on maritime safety research:

- **12 hours**: High fatigue threshold (STCW watch limit)
- **16 hours**: Critical fatigue threshold (USCG daily limit)
- **24 hours**: Danger threshold (extended operations limit)
- **72 hours**: Multiple fatigue threshold (cumulative fatigue)

### 3. Fatigue Score Interpretation

**0-30**: Low fatigue - Safe for continued operations
**30-50**: Moderate fatigue - Monitor closely
**50-70**: High fatigue - Consider rest
**70-85**: Very high fatigue - Rest recommended
**85-100**: Critical fatigue - Rest required

### 4. Alert Response

Recommended responses to alerts:

- **HIGH**: Increase monitoring, plan relief
- **CRITICAL**: Immediate relief required, consider crew substitution
- **DANGER**: Immediate action required, mandatory rest period

### 5. Data Integrity

The system ensures data integrity through:

- **Atomic writes**: Each record is written as a complete JSON line
- **Append-only storage**: Data is never overwritten
- **Validation**: All inputs are validated before storage
- **Error handling**: Corrupt data lines are skipped during load

## Performance Considerations

### Scalability

The system is designed for:

- **Crew size**: 1-50 crew members
- **Work periods**: Thousands of records per crew member
- **Alerts**: Continuous generation during active operations

### Optimization

For optimal performance:

1. **Use time filters**: Limit queries to relevant time windows
2. **Batch operations**: Log multiple work periods before checking metrics
3. **Regular cleanup**: Archive old data to maintain performance
4. **Index crew_id**: Ensure crew_id is always specified for queries

### Memory Usage

Typical memory footprint:

- **Per crew member**: ~500 bytes
- **Per work period**: ~300 bytes
- **Per alert**: ~800 bytes
- **Monitor overhead**: ~10KB base

## Integration Examples

### With WatcherRegistry

```python
from twin.watcher_registry import WatcherRegistry

# Register fatigue monitor as watcher
registry = WatcherRegistry()
registry.register("crew_fatigue", monitor)

# Update watchers on work period log
registry.notify_watchers("crew_fatigue", {
    "event": "work_period_logged",
    "crew_id": "crew_001",
    "activity": "NAVIGATION"
})
```

### With Report Generator

```python
from twin.reporting import ReportGenerator

# Generate fatigue compliance report
reporter = ReportGenerator()

snapshot = monitor.to_dict()
reporter.add_section("Crew Fatigue Status", {
    "total_crew": snapshot["crew_count"],
    "high_fatigue_count": sum(
        1 for m in snapshot["fatigue_metrics"].values()
        if m["fatigue_score"] > 70
    ),
    "recent_alerts": len(snapshot["recent_alerts"])
})
```

### With Safety Systems

```python
class SafetySystem:
    def __init__(self, fatigue_monitor):
        self.monitor = fatigue_monitor

    def check_crew_safety(self):
        """Check if any crew member is in unsafe fatigue state."""
        metrics = self.monitor.get_all_fatigue_metrics()

        unsafe = [
            crew_id for crew_id, m in metrics.items()
            if m.fatigue_score > 80
        ]

        if unsafe:
            self.trigger_safety_alert(unsafe)
            return False

        return True

    def trigger_safety_alert(self, crew_ids):
        """Trigger safety alert for fatigued crew."""
        # Notify captain, bridge, etc.
        pass
```

## Troubleshooting

### Common Issues

#### 1. Crew Member Not Found

**Problem**: `ValueError: Crew member {crew_id} not found`

**Solution**: Ensure crew member is added before operations:

```python
monitor.add_crew_member("crew_001", "John Smith", "captain")
# Now operations will work
monitor.log_work_period("crew_001", ...)
```

#### 2. No Alerts Generated

**Problem**: Expected alerts not appearing

**Solution**: Ensure work periods exceed thresholds:

```python
# Must log >12 hours continuous work for HIGH alert
monitor.log_work_period("crew_001", start_ns, end_ns + 13_hours_ns, ...)
# Now check alerts
alerts = monitor.get_fatigue_alerts("crew_001")
```

#### 3. High Fatigue Score Unexpectedly

**Problem**: Fatigue score higher than expected

**Solution**: Check activity weights and work periods:

```python
# NAVIGATION has 1.5x weight
# GEAR_HANDLING has 1.4x weight
# Use REST periods to reduce score

# Log appropriate rest periods
monitor.log_break("crew_001", start_ns, 8_hours_ns)
```

#### 4. Persistence Issues

**Problem**: Data not persisting across restarts

**Solution**: Ensure data directory is writable:

```python
import os

data_dir = "/data/crew_fatigue"
os.makedirs(data_dir, exist_ok=True)

monitor = CrewFatigueMonitor("vessel_001", data_dir)
```

## Future Enhancements

### Planned Features

1. **Machine Learning Integration**: ML-based fatigue prediction
2. **Biometric Monitoring**: Integration with wearable sensors
3. **Environmental Factors**: Sea state, weather impact on fatigue
4. **Task Complexity**: Cognitive load assessment
5. **Multi-vessel Tracking**: Fleet-wide fatigue monitoring
6. **Mobile App**: Real-time crew fatigue dashboard
7. **Regulatory Reporting**: Automated compliance report generation

### Extension Points

The system can be extended through:

1. **Custom Activity Types**: Add vessel-specific activities
2. **Custom Watch Types**: Define specialized watch rotations
3. **Custom Alert Types**: Add vessel-specific alert rules
4. **Custom Fatigue Models**: Implement specialized calculation algorithms

## References

### Maritime Regulations

- **STCW Convention**: International Convention on Standards of Training, Certification and Watchkeeping for Seafarers
- **USCG 46 CFR**: Title 46 Code of Federal Regulations (USCG)
- **ILO C180**: Seafarers' Hours of Work and the Manning of Ships Convention

### Fatigue Research

- **MTSA/ABP Research**: Maritime fatigue studies
- **NRC Reports**: Fatigue and transportation safety research
- **IMO Guidelines**: International Maritime Organization fatigue guidelines

### Related Standards

- **ISO 18087**: Ship and marine technology - Fatigue risk management
- **ILO MLCC**: Maritime Labour Convention, 2006
