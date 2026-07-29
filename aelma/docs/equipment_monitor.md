# EquipmentMonitor Component Documentation

## Table of Contents

1. [Component Overview](#component-overview)
2. [Architecture](#architecture)
3. [Data Structures](#data-structures)
4. [API Reference](#api-reference)
5. [Equipment Types](#equipment-types)
6. [Equipment Statuses](#equipment-statuses)
7. [Maintenance Types](#maintenance-types)
8. [Failure Types](#failure-types)
9. [Severity Levels](#severity-levels)
10. [Predictive Maintenance](#predictive-maintenance)
11. [Usage Examples](#usage-examples)
12. [Testing](#testing)

---

## Component Overview

### Purpose

The **EquipmentMonitor** is a comprehensive equipment monitoring and maintenance tracking system for the AELMA twin. It provides:

- **Equipment Lifecycle Management**: Track vessel equipment from installation through decommissioning
- **Status Monitoring**: Real-time operational status tracking (OPERATIONAL, DEGRADED, FAILED, etc.)
- **Maintenance Logging**: Complete maintenance history with costs, duration, and technician tracking
- **Failure Tracking**: Detailed failure event logging with severity classification
- **Maintenance Scheduling**: Recurring maintenance schedules with automatic due date calculation
- **Predictive Analytics**: MTBF, MTTR, uptime calculations, and failure pattern prediction
- **Alert Generation**: Automated alerts for equipment issues and maintenance needs
- **Data Persistence**: JSONL-based storage for all equipment data

### Use Cases

#### 1. Preventive Maintenance

Schedule routine maintenance based on equipment type and usage patterns to prevent failures before they occur.

```python
monitor.schedule_maintenance("ENG-001", MaintenanceType.ROUTINE, interval_hours=500)
```

#### 2. Regulatory Compliance

Maintain detailed maintenance records required by maritime regulations (SOLAS, MARPOL, class societies).

```python
monitor.log_maintenance(
    equipment_id="ENG-001",
    maintenance_type=MaintenanceType.INSPECTION,
    description="Annual safety inspection",
    technician="surveyor_smith",
    duration_hours=2.0,
    cost=500.00
)
```

#### 3. Fleet Management

Track equipment status across multiple vessels, identify recurring failures, and optimize maintenance schedules.

```python
for equipment_id in monitor.get_all_equipment():
    uptime = monitor.calculate_equipment_uptime(equipment_id)
    mtbf = monitor.calculate_mtbf(equipment_id)
    print(f"{equipment_id}: Uptime {uptime['uptime_percentage']}%, MTBF {mtbf} hours")
```

#### 4. Failure Analysis

Analyze failure patterns to identify equipment issues and predict future failures.

```python
predictions = monitor.predict_maintenance_needs("ENG-001", lookahead_hours=168)
for prediction in predictions:
    print(f"Maintenance needed: {prediction['reason']}")
    print(f"Priority: {prediction['priority']}")
```

### Integration

The EquipmentMonitor integrates with several AELMA components:

#### TwinCore Integration

- Provides equipment status as part of twin state
- Updates equipment status based on sensor data
- Receives commands for status changes

```python
frame = monitor.get_watcher_frame()
twin_state.update_equipment_status(frame)
```

#### WatcherRegistry Integration

- Supplies watcher frame data for rule evaluation
- Generates alerts for watcher actions
- Supports equipment-based monitoring rules

```python
# Watcher can evaluate equipment status
watcher.evaluate(frame=monitor.get_watcher_frame())
alerts = monitor.get_alerts()
```

#### Maintenance Systems

- Exports maintenance schedules for planning
- Receives maintenance completion confirmations
- Tracks technician assignments and costs

---

## Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    EquipmentMonitor                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  │
│  │   Equipment   │  │  Maintenance   │  │   Failure     │  │
│  │   Registry    │  │     Logs      │  │   Events      │  │
│  │               │  │               │  │               │  │
│  │ • CRUD ops    │  │ • History     │  │ • Logging     │  │
│  │ • Status      │  │ • Costs       │  │ • Resolution  │  │
│  │ • Tracking    │  │ • Technicians │  │ • Severity    │  │
│  └───────────────┘  └───────────────┘  └───────────────┘  │
│                                                               │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  │
│  │  Maintenance  │  │   Predictive  │  │    Alert      │  │
│  │  Schedules    │  │   Analytics   │  │  Generation   │  │
│  │               │  │               │  │               │  │
│  │ • Scheduling  │  │ • MTBF        │  │ • Equipment   │  │
│  │ • Due dates   │  │ • MTTR        │  │ • Overdue     │  │
│  │ • Recurring   │  │ • Uptime      │  │ • Critical    │  │
│  └───────────────┘  └───────────────┘  └───────────────┘  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    JSONL Persistence                         │
├─────────────────────────────────────────────────────────────┤
│  equipment.jsonl    |  All equipment records                │
│  maintenance.jsonl  |  Maintenance logs                      │
│  failures.jsonl     |  Failure events                        │
│  schedules.jsonl    |  Maintenance schedules                 │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Sensor Data → Status Update → Equipment Registry → Watcher Frame
     │              │                │                  │
     ▼              ▼                ▼                  ▼
  Monitor         Update          In-Memory         Alert
  Equipment       Status           Storage          Generation
     │              │                │                  │
     ▼              ▼                ▼                  ▼
  Log            Persist          JSONL            Trigger
  Failure         Files           Files            Actions
```

### Storage Architecture

The EquipmentMonitor uses JSONL (JSON Lines) format for data persistence:

- **equipment.jsonl**: One JSON object per line for each equipment record
- **maintenance.jsonl**: One JSON object per line for each maintenance log entry
- **failures.jsonl**: One JSON object per line for each failure event
- **schedules.jsonl**: One JSON object per line for each maintenance schedule

Each append operation writes a new line to the appropriate file, ensuring durability and enabling crash recovery.

### Lifecycle Management

```
INSTALLATION → OPERATIONAL → [DEGRADED → MAINTENANCE_REQUIRED] → FAILED → RESOLVED → OPERATIONAL
     │              │                    │                     │           │
     │              │                    ▼                     ▼           │
     │              │             Schedule Maintenance    Log Failure     │
     │              │                    │                     │           │
     │              └────────────────────┴─────────────────────┘           │
     │                                                                   │
     └───────────────── Maintenance History Tracking ────────────────────┘
```

---

## Data Structures

### Equipment

Represents a piece of vessel equipment.

```python
@dataclass
class Equipment:
    equipment_id: str              # Unique identifier (e.g., "ENG-001")
    name: str                      # Human-readable name (e.g., "Main Engine")
    type: EquipmentType           # Equipment type enum
    location: str                  # Physical location on vessel
    status: EquipmentStatus       # Current operational status
    install_date_ns: int          # Installation timestamp (nanoseconds)
    last_maintenance_ns: int      # Last maintenance timestamp (nanoseconds)
```

**Validation Rules:**
- `equipment_id`: Must be non-empty string, unique per equipment
- `name`: Must be non-empty string
- `type`: Must be valid EquipmentType enum value
- `location`: Required string
- `status`: Must be valid EquipmentStatus enum value
- `install_date_ns`: Must be >= 0 (0 = auto-set to current time)
- `last_maintenance_ns`: Must be >= 0 or None

**Methods:**
- `to_dict()`: Serialize to dictionary for JSON storage
- `from_dict(data)`: Deserialize from dictionary

### MaintenanceLog

Represents a maintenance activity performed on equipment.

```python
@dataclass
class MaintenanceLog:
    equipment_id: str              # Equipment identifier
    maintenance_type: MaintenanceType  # Type of maintenance performed
    description: str               # Description of work performed
    technician: str                # Name or ID of technician
    duration_hours: float         # Duration of maintenance in hours
    cost: float                   # Cost of maintenance (currency units)
    timestamp_ns: int             # Timestamp of maintenance (nanoseconds)
```

**Validation Rules:**
- `equipment_id`: Must be non-empty string, must exist in registry
- `maintenance_type`: Must be valid MaintenanceType enum value
- `description`: Required string
- `technician`: Required string
- `duration_hours`: Must be >= 0
- `cost`: Must be >= 0
- `timestamp_ns`: Must be >= 0 (0 = auto-set to current time)

### FailureEvent

Represents a equipment failure event.

```python
@dataclass
class FailureEvent:
    equipment_id: str              # Equipment identifier
    failure_type: FailureType      # Type of failure
    severity: Severity             # Failure severity level
    description: str               # Description of the failure
    timestamp_ns: int              # Timestamp of failure (nanoseconds)
    resolved_ns: int | None       # Resolution timestamp (None = unresolved)
```

**Validation Rules:**
- `equipment_id`: Must be non-empty string, must exist in registry
- `failure_type`: Must be valid FailureType enum value
- `severity`: Must be valid Severity enum value
- `description`: Required string
- `timestamp_ns`: Must be >= 0 (0 = auto-set to current time)
- `resolved_ns`: Must be >= 0 or None

**Automatic Status Changes:**
- HIGH or CRITICAL severity failures automatically set equipment status to FAILED
- Resolving failure automatically sets equipment status to OPERATIONAL

### MaintenanceSchedule

Represents a scheduled recurring maintenance for equipment.

```python
@dataclass
class MaintenanceSchedule:
    equipment_id: str              # Equipment identifier
    maintenance_type: MaintenanceType  # Type of maintenance
    interval_hours: float         # Recurrence interval in hours
    last_performed_ns: int        # Last performed timestamp (nanoseconds)
    next_due_ns: int             # Next due timestamp (nanoseconds)
```

**Validation Rules:**
- `equipment_id`: Must be non-empty string, must exist in registry
- `maintenance_type`: Must be valid MaintenanceType enum value
- `interval_hours`: Must be > 0
- `last_performed_ns`: Must be >= 0
- `next_due_ns`: Must be >= 0

**Default Intervals:**
The system provides default maintenance intervals by equipment type:

| Equipment Type | Default Interval |
|--------------|------------------|
| ENGINE | 500 hours |
| GENERATOR | 250 hours |
| PUMP | 100 hours |
| WINCH | 150 hours |
| CRANE | 200 hours |
| NET_SOUNDING | 100 hours |
| NAVIGATION | 50 hours |
| COMMUNICATION | 50 hours |
| SAFETY | 25 hours |
| FISHING_GEAR | 75 hours |

---

## API Reference

### Constructor

#### `EquipmentMonitor.__init__(data_dir, enable_persistence)`

Initialize the equipment monitor.

**Parameters:**
- `data_dir` (str | Path): Directory for JSONL persistence files (default: "equipment_data")
- `enable_persistence` (bool): Whether to persist data to JSONL files (default: True)

**Returns:**
- EquipmentMonitor instance

**Example:**
```python
# With persistence (default)
monitor = EquipmentMonitor(data_dir="vessel_equipment", enable_persistence=True)

# Without persistence (in-memory only)
monitor = EquipmentMonitor(enable_persistence=False)
```

---

### Equipment CRUD Operations

#### `add_equipment(equipment_id, name, type, location, install_date_ns)`

Add a new equipment record to the registry.

**Parameters:**
- `equipment_id` (str): Unique identifier for the equipment
- `name` (str): Human-readable name
- `type` (EquipmentType | str): Equipment type (enum or string value)
- `location` (str): Physical location on vessel
- `install_date_ns` (int): Installation timestamp in nanoseconds (0 = now, default)

**Returns:**
- Equipment: The created Equipment instance

**Raises:**
- ValueError: If equipment_id already exists or validation fails

**Example:**
```python
equipment = monitor.add_equipment(
    equipment_id="ENG-001",
    name="Main Engine",
    type=EquipmentType.ENGINE,
    location="Engine Room"
)
```

---

#### `update_equipment_status(equipment_id, status)`

Update equipment operational status.

**Parameters:**
- `equipment_id` (str): Equipment identifier
- `status` (EquipmentStatus | str): New status (enum or string value)

**Returns:**
- Equipment: The updated Equipment instance

**Raises:**
- ValueError: If equipment_id not found or validation fails

**Example:**
```python
# Update to degraded status
equipment = monitor.update_equipment_status("ENG-001", EquipmentStatus.DEGRADED)

# Update using string
equipment = monitor.update_equipment_status("ENG-001", "FAILED")
```

---

#### `get_equipment(equipment_id)`

Get equipment by ID.

**Parameters:**
- `equipment_id` (str): Equipment identifier

**Returns:**
- Equipment | None: Equipment instance or None if not found

**Example:**
```python
equipment = monitor.get_equipment("ENG-001")
if equipment:
    print(f"Status: {equipment.status.value}")
```

---

#### `get_all_equipment()`

Get all equipment records.

**Returns:**
- dict[str, Equipment]: Dict mapping equipment_id to Equipment

**Example:**
```python
all_equipment = monitor.get_all_equipment()
for eq_id, equipment in all_equipment.items():
    print(f"{eq_id}: {equipment.name} - {equipment.status.value}")
```

---

#### `get_equipment_by_type(equipment_type)`

Get all equipment of a specific type.

**Parameters:**
- `equipment_type` (EquipmentType | str): Equipment type filter (enum or string value)

**Returns:**
- list[Equipment]: List of Equipment instances matching the type

**Example:**
```python
# Get all pumps
pumps = monitor.get_equipment_by_type(EquipmentType.PUMP)

# Get using string
engines = monitor.get_equipment_by_type("ENGINE")
```

---

### Maintenance Operations

#### `log_maintenance(equipment_id, maintenance_type, description, technician, duration_hours, cost, timestamp_ns)`

Log a maintenance activity.

**Parameters:**
- `equipment_id` (str): Equipment identifier
- `maintenance_type` (MaintenanceType | str): Type of maintenance performed (enum or string)
- `description` (str): Description of work performed
- `technician` (str): Name or ID of technician
- `duration_hours` (float): Duration of maintenance in hours
- `cost` (float): Cost of maintenance (currency units)
- `timestamp_ns` (int): Timestamp of maintenance in nanoseconds (0 = now, default)

**Returns:**
- MaintenanceLog: The created MaintenanceLog instance

**Raises:**
- ValueError: If equipment_id not found or validation fails

**Example:**
```python
log_entry = monitor.log_maintenance(
    equipment_id="ENG-001",
    maintenance_type=MaintenanceType.ROUTINE,
    description="Oil change and filter replacement",
    technician="tech_john",
    duration_hours=4.5,
    cost=350.00
)
```

---

#### `get_maintenance_history(equipment_id)`

Get maintenance history for equipment.

**Parameters:**
- `equipment_id` (str): Equipment identifier

**Returns:**
- list[MaintenanceLog]: List of MaintenanceLog entries, most recent first

**Example:**
```python
history = monitor.get_maintenance_history("ENG-001")
for log in history:
    print(f"{log.timestamp_ns}: {log.maintenance_type.value} - {log.description}")
```

---

### Failure Operations

#### `log_failure(equipment_id, failure_type, severity, description, timestamp_ns)`

Log a equipment failure.

**Parameters:**
- `equipment_id` (str): Equipment identifier
- `failure_type` (FailureType | str): Type of failure (enum or string)
- `severity` (Severity | str): Failure severity (enum or string)
- `description` (str): Description of the failure
- `timestamp_ns` (int): Timestamp of failure in nanoseconds (0 = now, default)

**Returns:**
- FailureEvent: The created FailureEvent instance

**Raises:**
- ValueError: If equipment_id not found or validation fails

**Automatic Behavior:**
- If severity is HIGH or CRITICAL, equipment status automatically changes to FAILED

**Example:**
```python
failure = monitor.log_failure(
    equipment_id="PUMP-001",
    failure_type=FailureType.MECHANICAL,
    severity=Severity.HIGH,
    description="Bearing failure detected"
)
```

---

#### `resolve_failure(equipment_id, resolution_description, timestamp_ns)`

Resolve the most recent unresolved failure for equipment.

**Parameters:**
- `equipment_id` (str): Equipment identifier
- `resolution_description` (str): Description of resolution actions
- `timestamp_ns` (int): Resolution timestamp in nanoseconds (0 = now, default)

**Returns:**
- FailureEvent | None: The resolved FailureEvent, or None if no unresolved failure exists

**Raises:**
- ValueError: If equipment_id not found

**Automatic Behavior:**
- Equipment status automatically changes to OPERATIONAL

**Example:**
```python
resolved = monitor.resolve_failure(
    equipment_id="PUMP-001",
    resolution_description="Replaced bearings and seals"
)
```

---

#### `get_failure_history(equipment_id)`

Get failure history for equipment.

**Parameters:**
- `equipment_id` (str): Equipment identifier

**Returns:**
- list[FailureEvent]: List of FailureEvent entries, most recent first

**Example:**
```python
failures = monitor.get_failure_history("PUMP-001")
for failure in failures:
    status = "RESOLVED" if failure.resolved_ns else "UNRESOLVED"
    print(f"{failure.failure_type.value} ({failure.severity.value}): {status}")
```

---

### Maintenance Scheduling

#### `schedule_maintenance(equipment_id, maintenance_type, interval_hours)`

Schedule recurring maintenance for equipment.

**Parameters:**
- `equipment_id` (str): Equipment identifier
- `maintenance_type` (MaintenanceType | str): Type of maintenance (enum or string)
- `interval_hours` (float | None): Interval in hours (None = use default for type)

**Returns:**
- MaintenanceSchedule: The created/updated MaintenanceSchedule

**Raises:**
- ValueError: If equipment_id not found or validation fails

**Example:**
```python
# Use default interval for equipment type
schedule = monitor.schedule_maintenance("ENG-001", MaintenanceType.ROUTINE)

# Specify custom interval
schedule = monitor.schedule_maintenance(
    equipment_id="PUMP-001",
    maintenance_type=MaintenanceType.PREVENTIVE,
    interval_hours=100.0
)
```

---

#### `get_maintenance_schedule(equipment_id)`

Get maintenance schedule for equipment.

**Parameters:**
- `equipment_id` (str): Equipment identifier

**Returns:**
- MaintenanceSchedule | None: MaintenanceSchedule or None if not scheduled

**Example:**
```python
schedule = monitor.get_maintenance_schedule("ENG-001")
if schedule:
    due_hours = (schedule.next_due_ns - time.time_ns()) / 1e9 / 3600
    print(f"Maintenance due in {due_hours:.1f} hours")
```

---

#### `get_due_maintenance(lookahead_hours)`

Get maintenance schedules due within lookahead period.

**Parameters:**
- `lookahead_hours` (float): Hours to look ahead (default: 24.0)

**Returns:**
- list[MaintenanceSchedule]: List of MaintenanceSchedule due within lookahead, sorted by due time

**Example:**
```python
# Get maintenance due in next 7 days
due = monitor.get_due_maintenance(lookahead_hours=168)
for schedule in due:
    equipment = monitor.get_equipment(schedule.equipment_id)
    print(f"{equipment.name}: {schedule.maintenance_type.value} due")
```

---

#### `get_overdue_maintenance()`

Get maintenance schedules that are overdue.

**Returns:**
- list[MaintenanceSchedule]: List of overdue MaintenanceSchedule, sorted by overdue time

**Example:**
```python
overdue = monitor.get_overdue_maintenance()
for schedule in overdue:
    equipment = monitor.get_equipment(schedule.equipment_id)
    overdue_hours = (time.time_ns() - schedule.next_due_ns) / 1e9 / 3600
    print(f"{equipment.name}: Overdue by {overdue_hours:.1f} hours")
```

---

### Predictive Maintenance Analytics

#### `predict_maintenance_needs(equipment_id, lookahead_hours)`

Predict maintenance needs for equipment.

**Parameters:**
- `equipment_id` (str): Equipment identifier
- `lookahead_hours` (float): Prediction horizon in hours (default: 168 = 7 days)

**Returns:**
- list[dict]: List of predicted maintenance needs with metadata

**Analysis Methods:**
1. **Scheduled Maintenance**: Checks if scheduled maintenance is due within lookahead
2. **Failure Pattern Prediction**: Uses MTBF to predict next failure
3. **Current Status**: Alerts if equipment is in DEGRADED or MAINTENANCE_REQUIRED status

**Prediction Format:**
```python
{
    "equipment_id": str,
    "maintenance_type": str,
    "predicted_due_hours": float,
    "due_date": str (ISO format),
    "reason": str ("scheduled_maintenance" | "failure_pattern_prediction" | "current_status"),
    "priority": str ("critical" | "high" | "medium" | "low"),
    "mtbf_hours": float (optional, for failure_pattern_prediction),
    "status": str (optional, for current_status)
}
```

**Example:**
```python
predictions = monitor.predict_maintenance_needs("ENG-001", lookahead_hours=168)
for prediction in predictions:
    print(f"Reason: {prediction['reason']}")
    print(f"Priority: {prediction['priority']}")
    print(f"Due: {prediction['due_date']}")
```

---

#### `calculate_mtbf(equipment_id)`

Calculate Mean Time Between Failures for equipment.

**Parameters:**
- `equipment_id` (str): Equipment identifier

**Returns:**
- float | None: MTBF in hours, or None if insufficient data (< 2 resolved failures)

**Calculation:**
- MTBF = Average time between failure resolution and next failure
- Requires at least 2 resolved failures

**Example:**
```python
mtbf = monitor.calculate_mtbf("ENG-001")
if mtbf:
    print(f"Mean Time Between Failures: {mtbf:.1f} hours")
```

---

#### `calculate_mttr(equipment_id)`

Calculate Mean Time To Repair for equipment.

**Parameters:**
- `equipment_id` (str): Equipment identifier

**Returns:**
- float | None: MTTR in hours, or None if insufficient data (< 1 resolved failure)

**Calculation:**
- MTTR = Average time from failure to resolution
- Requires at least 1 resolved failure

**Example:**
```python
mttr = monitor.calculate_mttr("ENG-001")
if mttr:
    print(f"Mean Time To Repair: {mttr:.1f} hours")
```

---

#### `calculate_equipment_uptime(equipment_id)`

Calculate uptime statistics for equipment.

**Parameters:**
- `equipment_id` (str): Equipment identifier

**Returns:**
- dict: Uptime statistics with keys:
  - `equipment_id` (str): Equipment identifier
  - `uptime_percentage` (float): Percentage of time operational
  - `total_downtime_hours` (float): Total downtime in hours
  - `total_uptime_hours` (float): Total uptime in hours
  - `failure_count` (int): Number of failures
  - `current_status` (str): Current operational status

**Example:**
```python
uptime = monitor.calculate_equipment_uptime("ENG-001")
print(f"Uptime: {uptime['uptime_percentage']}%")
print(f"Downtime: {uptime['total_downtime_hours']} hours")
print(f"Failures: {uptime['failure_count']}")
```

---

#### `get_maintenance_cost_summary(equipment_id)`

Get maintenance cost summary.

**Parameters:**
- `equipment_id` (str | None): Optional equipment filter (None = all equipment)

**Returns:**
- dict: Cost summary with keys:
  - `equipment_id` (str | None): Equipment filter applied
  - `total_cost` (float): Total maintenance cost
  - `total_hours` (float): Total maintenance hours
  - `maintenance_count` (int): Number of maintenance activities
  - `cost_by_type` (dict): Cost grouped by maintenance type

**Example:**
```python
# Get summary for specific equipment
summary = monitor.get_maintenance_cost_summary("ENG-001")

# Get summary for all equipment
total_summary = monitor.get_maintenance_cost_summary()
print(f"Total maintenance cost: ${total_summary['total_cost']}")
```

---

### Alert Generation

#### `get_alerts()`

Generate alerts for equipment issues and maintenance needs.

**Returns:**
- list[dict]: List of alert dicts with:
  - `severity` (str): Alert severity ("critical" | "warning" | "high")
  - `code` (str): Alert code
  - `message` (str): Human-readable message
  - Additional metadata fields based on alert type

**Alert Types:**

1. **EQUIPMENT_FAILED** (critical)
   - Equipment has failed
   - Equipment is non-operational

2. **EQUIPMENT_DEGRADED** (warning)
   - Equipment is operating in degraded mode
   - Reduced capability

3. **MAINTENANCE_REQUIRED** (high)
   - Equipment requires maintenance
   - Status is MAINTENANCE_REQUIRED

4. **MAINTENANCE_OVERDUE** (warning)
   - Scheduled maintenance is overdue
   - Includes overdue_hours field

5. **CRITICAL_FAILURE_UNRESOLVED** (critical)
   - Critical failure remains unresolved
   - Safety impact

**Example:**
```python
alerts = monitor.get_alerts()
for alert in alerts:
    print(f"[{alert['severity'].upper()}] {alert['code']}: {alert['message']}")
```

---

### Integration Methods

#### `get_watcher_frame()`

Build a watcher frame for equipment monitoring.

**Returns:**
- dict: Watcher frame with:
  - `timestamp_ns` (int): Current timestamp
  - `equipment_count` (int): Total equipment count
  - `equipment_status_counts` (dict[str, int]): Count by status
  - `overdue_maintenance_count` (int): Number of overdue schedules
  - `unresolved_failure_counts` (dict[str, int]): Count by severity
  - `total_maintenance_logs` (int): Total maintenance activities
  - `total_failures` (int): Total failure events

**Example:**
```python
frame = monitor.get_watcher_frame()
print(f"Equipment: {frame['equipment_count']}")
print(f"Status breakdown: {frame['equipment_status_counts']}")
print(f"Overdue maintenance: {frame['overdue_maintenance_count']}")
```

---

#### `to_dict()`

Create a comprehensive snapshot of the equipment monitor state.

**Returns:**
- dict: Complete state with:
  - `equipment` (dict[str, dict]): All equipment records
  - `maintenance_logs` (list[dict]): All maintenance logs
  - `failure_events` (list[dict]): All failure events
  - `schedules` (dict[str, dict]): All maintenance schedules
  - `watcher_frame` (dict): Current watcher frame
  - `alerts` (list[dict]): Current alerts

**Example:**
```python
snapshot = monitor.to_dict()

# Save to file
import json
with open("equipment_snapshot.json", "w") as f:
    json.dump(snapshot, f, indent=2)
```

---

### Persistence Methods

#### `load_from_disk()`

Load all data from JSONL files.

**Returns:**
- None

**Behavior:**
- Reconstructs in-memory state from persisted files
- Logs number of records loaded
- Handles malformed JSON lines gracefully

**Example:**
```python
# Create monitor with persistence enabled
monitor = EquipmentMonitor(data_dir="equipment_data", enable_persistence=True)

# Load previously saved data
monitor.load_from_disk()

# Continue operations
equipment = monitor.get_equipment("ENG-001")
```

---

## Equipment Types

The EquipmentMonitor supports 10 equipment types:

| Type | Description | Default Maintenance Interval |
|------|-------------|------------------------------|
| ENGINE | Main and auxiliary propulsion engines | 500 hours |
| GENERATOR | Electrical generators and alternators | 250 hours |
| PUMP | Fluid transfer pumps (cooling, fuel, ballast) | 100 hours |
| WINCH | Trawl and anchor winches | 150 hours |
| CRANE | Cargo and handling cranes | 200 hours |
| NET_SOUNDING | Net sounding and fishing equipment | 100 hours |
| NAVIGATION | GPS, radar, AIS, compass systems | 50 hours |
| COMMUNICATION | Radio, satellite, internet systems | 50 hours |
| SAFETY | Life rafts, fire suppression, alarms | 25 hours |
| FISHING_GEAR | Nets, traps, fishing equipment | 75 hours |

### Usage

```python
from twin.equipment_monitor import EquipmentType

# Using enum
equipment = monitor.add_equipment(
    "ENG-001",
    "Main Engine",
    EquipmentType.ENGINE,
    "Engine Room"
)

# Using string (auto-converted)
equipment = monitor.add_equipment(
    "PUMP-001",
    "Cooling Pump",
    "PUMP",  # String automatically converted to EquipmentType.PUMP
    "Engine Room"
)
```

---

## Equipment Statuses

The EquipmentMonitor tracks 5 operational statuses:

| Status | Description | Automatic Transitions |
|--------|-------------|----------------------|
| OPERATIONAL | Running normally, full capability | Default status, set after failure resolution |
| DEGRADED | Reduced capability, operational with limits | Alert generated, maintenance recommended |
| FAILED | Non-operational, requires repair | Auto-set on HIGH/CRITICAL failure |
| MAINTENANCE_REQUIRED | Maintenance due, operational but urgent | Alert generated |
| OFFLINE | Intentionally off (maintenance, shutdown) | Manual status change only |

### Status Lifecycle

```
INSTALLATION → OPERATIONAL
     │
     ├─→ DEGRADED → MAINTENANCE_REQUIRED → FAILED → (Repair) → OPERATIONAL
     │
     └─→ OFFLINE → (Restart) → OPERATIONAL
```

### Usage

```python
from twin.equipment_monitor import EquipmentStatus

# Update status
monitor.update_equipment_status("ENG-001", EquipmentStatus.DEGRADED)

# Check status
equipment = monitor.get_equipment("ENG-001")
if equipment.status == EquipmentStatus.FAILED:
    print("Equipment has failed - immediate attention required")
```

---

## Maintenance Types

The EquipmentMonitor supports 6 maintenance activity types:

| Type | Description | Typical Use Case |
|------|-------------|------------------|
| ROUTINE | Regular scheduled maintenance | Oil changes, filter replacements |
| PREVENTIVE | Preventive maintenance before failure | Bearing checks, seal replacements |
| CORRECTIVE | Repair after failure | Fixing broken components |
| EMERGENCY | Urgent repair | Critical failures, safety issues |
| UPGRADE | Equipment upgrade or modernization | Installing new components |
| INSPECTION | Visual inspection and verification | Regulatory inspections, safety checks |

### Usage

```python
from twin.equipment_monitor import MaintenanceType

# Log routine maintenance
monitor.log_maintenance(
    "ENG-001",
    MaintenanceType.ROUTINE,
    "Oil change and filter replacement",
    "tech_john",
    4.5,
    350.00
)

# Schedule preventive maintenance
monitor.schedule_maintenance("PUMP-001", MaintenanceType.PREVENTIVE, 100.0)

# Log emergency repair
monitor.log_maintenance(
    "PUMP-001",
    MaintenanceType.EMERGENCY,
    "Emergency bearing replacement",
    "tech_jane",
    2.0,
    800.00
)
```

---

## Failure Types

The EquipmentMonitor tracks 7 failure types:

| Type | Description | Common Causes |
|------|-------------|----------------|
| MECHANICAL | Mechanical component failure | Bearing wear, shaft misalignment |
| ELECTRICAL | Electrical system failure | Short circuits, wiring issues |
| HYDRAULIC | Hydraulic system failure | Leaks, pump failures, valve issues |
| SOFTWARE | Software/firmware failure | Bugs, crashes, corrupted data |
| CORROSION | Corrosion-related failure | Saltwater exposure, oxidation |
| WEAR | Wear and tear failure | Age-related degradation |
| ACCIDENT | Accidental damage | Collision, impact, misuse |

### Usage

```python
from twin.equipment_monitor import FailureType, Severity

# Log mechanical failure
monitor.log_failure(
    "PUMP-001",
    FailureType.MECHANICAL,
    Severity.HIGH,
    "Bearing failure detected"
)

# Log corrosion issue
monitor.log_failure(
    "DECK-001",
    FailureType.CORROSION,
    Severity.MEDIUM,
    "Surface corrosion on mounting brackets"
)
```

---

## Severity Levels

The EquipmentMonitor uses 4 severity levels for failures and alerts:

| Severity | Description | Operational Impact | Automatic Actions |
|----------|-------------|-------------------|-------------------|
| LOW | Minor issue, no operational impact | None | Alert only |
| MEDIUM | Degraded operation | Reduced capability | Alert only |
| HIGH | Major issue, reduced capability | Significant impact | Status → FAILED, Alert |
| CRITICAL | Non-operational, safety impact | System down | Status → FAILED, Alert |

### Severity Guidelines

**Use CRITICAL for:**
- Life-safety equipment failures
- Propulsion system failures
- Fire suppression failures
- Critical navigation failures

**Use HIGH for:**
- Main equipment failures
- Significant capability reduction
- Safety equipment degradation

**Use MEDIUM for:**
- Minor equipment failures
- Reduced performance
- Non-critical system issues

**Use LOW for:**
- Cosmetic issues
- Minor anomalies
- Documentation discrepancies

### Usage

```python
from twin.equipment_monitor import Severity

# Critical failure
monitor.log_failure(
    "ENG-001",
    FailureType.MECHANICAL,
    Severity.CRITICAL,
    "Main engine seized - vessel dead in water"
)

# High severity
monitor.log_failure(
    "PUMP-001",
    FailureType.MECHANICAL,
    Severity.HIGH,
    "Cooling pump failure - temperature rising"
)

# Medium severity
monitor.log_failure(
    "NAV-001",
    FailureType.ELECTRICAL,
    Severity.MEDIUM,
    "Backup GPS malfunction - primary GPS operational"
)

# Low severity
monitor.log_failure(
    "DECK-001",
    FailureType.WEAR,
    Severity.LOW,
    "Surface wear on deck coating"
)
```

---

## Predictive Maintenance

The EquipmentMonitor provides predictive maintenance capabilities to anticipate failures and schedule maintenance proactively.

### Prediction Methods

#### 1. Schedule-Based Prediction

Analyzes upcoming maintenance schedules to identify due maintenance within the lookahead period.

```python
# Schedule maintenance 12 hours from now
monitor.schedule_maintenance("PUMP-001", MaintenanceType.ROUTINE, 100.0)

predictions = monitor.predict_maintenance_needs("PUMP-001", lookahead_hours=24)
# Returns: [{"reason": "scheduled_maintenance", "priority": "high", ...}]
```

#### 2. MTBF-Based Prediction

Uses Mean Time Between Failures to predict when the next failure is likely to occur.

**Requirements:**
- At least 2 resolved failures
- Consistent failure intervals

**Calculation:**
- MTBF = Average time between failure resolution and next failure
- Next predicted failure = Last failure resolution + MTBF

```python
# After multiple failures with consistent intervals
predictions = monitor.predict_maintenance_needs("ENG-001", lookahead_hours=168)
# Returns: [{"reason": "failure_pattern_prediction", "mtbf_hours": 336.5, ...}]
```

#### 3. Status-Based Prediction

Monitors current equipment status to identify immediate maintenance needs.

**Triggers:**
- Equipment in DEGRADED status
- Equipment in MAINTENANCE_REQUIRED status

```python
monitor.update_equipment_status("PUMP-001", EquipmentStatus.DEGRADED)

predictions = monitor.predict_maintenance_needs("PUMP-001")
# Returns: [{"reason": "current_status", "priority": "critical", "status": "DEGRADED"}]
```

### Analytics

#### Mean Time Between Failures (MTBF)

Measures reliability by calculating average time between failures.

```python
mtbf = monitor.calculate_mtbf("ENG-001")
print(f"Average time between failures: {mtbf} hours")

# Interpretation:
# - Higher MTBF = More reliable equipment
# - Lower MTBF = Frequent failures
# - None = Insufficient data (< 2 failures)
```

#### Mean Time To Repair (MTTR)

Measures maintainability by calculating average repair time.

```python
mttr = monitor.calculate_mttr("ENG-001")
print(f"Average repair time: {mttr} hours")

# Interpretation:
# - Lower MTTR = Faster repairs
# - Higher MTTR = Extended downtime
# - None = Insufficient data (< 1 resolved failure)
```

#### Equipment Uptime

Calculates overall equipment availability.

```python
uptime = monitor.calculate_equipment_uptime("ENG-001")
print(f"Uptime: {uptime['uptime_percentage']}%")
print(f"Downtime: {uptime['total_downtime_hours']} hours")
print(f"Failures: {uptime['failure_count']}")

# Interpretation:
# - High uptime % = Reliable equipment
# - Low uptime % = Frequent failures or extended repairs
```

### Maintenance Cost Analysis

Track maintenance costs and optimize budgets.

```python
# Get cost summary for specific equipment
summary = monitor.get_maintenance_cost_summary("ENG-001")
print(f"Total cost: ${summary['total_cost']}")
print(f"Total hours: {summary['total_hours']}")

# Analyze costs by type
for mtype, data in summary['cost_by_type'].items():
    print(f"{mtype}: {data['count']} activities, ${data['total_cost']}")

# Get fleet-wide costs
fleet_summary = monitor.get_maintenance_cost_summary()
print(f"Fleet maintenance cost: ${fleet_summary['total_cost']}")
```

---

## Usage Examples

### Example 1: Adding Equipment

```python
from twin.equipment_monitor import EquipmentMonitor, EquipmentType, EquipmentStatus

# Initialize monitor
monitor = EquipmentMonitor(data_dir="vessel_equipment")

# Add various equipment
monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")
monitor.add_equipment("GEN-001", "Generator 1", EquipmentType.GENERATOR, "Engine Room")
monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")
monitor.add_equipment("WINCH-001", "Trawl Winch", EquipmentType.WINCH, "Deck")
monitor.add_equipment("NAV-001", "GPS System", EquipmentType.NAVIGATION, "Bridge")

# Verify equipment
all_equipment = monitor.get_all_equipment()
print(f"Total equipment: {len(all_equipment)}")
```

### Example 2: Logging Maintenance

```python
from twin.equipment_monitor import MaintenanceType
import time

# Perform routine maintenance on main engine
log_entry = monitor.log_maintenance(
    equipment_id="ENG-001",
    maintenance_type=MaintenanceType.ROUTINE,
    description="Oil change and filter replacement",
    technician="tech_john",
    duration_hours=4.5,
    cost=350.00
)

# Perform preventive maintenance on cooling pump
monitor.log_maintenance(
    equipment_id="PUMP-001",
    maintenance_type=MaintenanceType.PREVENTIVE,
    description="Seal replacement and bearing check",
    technician="tech_jane",
    duration_hours=2.0,
    cost=150.00
)

# Review maintenance history
history = monitor.get_maintenance_history("ENG-001")
for log in history:
    print(f"{log.timestamp_ns}: {log.maintenance_type.value} by {log.technician}")
```

### Example 3: Tracking Failures

```python
from twin.equipment_monitor import FailureType, Severity

# Log a failure
failure = monitor.log_failure(
    equipment_id="PUMP-001",
    failure_type=FailureType.MECHANICAL,
    severity=Severity.HIGH,
    description="Bearing failure detected"
)

# Equipment status automatically changes to FAILED for HIGH/CRITICAL severity
equipment = monitor.get_equipment("PUMP-001")
print(f"Equipment status: {equipment.status.value}")  # FAILED

# Resolve the failure
resolved = monitor.resolve_failure(
    equipment_id="PUMP-001",
    resolution_description="Replaced bearings and seals"
)

# Equipment status automatically changes back to OPERATIONAL
equipment = monitor.get_equipment("PUMP-001")
print(f"Equipment status: {equipment.status.value}")  # OPERATIONAL

# Review failure history
failures = monitor.get_failure_history("PUMP-001")
for failure in failures:
    status = "RESOLVED" if failure.resolved_ns else "UNRESOLVED"
    print(f"{failure.failure_type.value} ({failure.severity.value}): {status}")
```

### Example 4: Scheduling Maintenance

```python
# Schedule maintenance with default interval
schedule = monitor.schedule_maintenance("ENG-001", MaintenanceType.ROUTINE)
print(f"Next maintenance due: {schedule.next_due_ns}")

# Schedule with custom interval
schedule = monitor.schedule_maintenance(
    equipment_id="PUMP-001",
    maintenance_type=MaintenanceType.PREVENTIVE,
    interval_hours=100.0
)

# Check for due maintenance
due = monitor.get_due_maintenance(lookahead_hours=24)
for schedule in due:
    equipment = monitor.get_equipment(schedule.equipment_id)
    hours_until_due = (schedule.next_due_ns - time.time_ns()) / 1e9 / 3600
    print(f"{equipment.name}: Maintenance due in {hours_until_due:.1f} hours")

# Check for overdue maintenance
overdue = monitor.get_overdue_maintenance()
for schedule in overdue:
    equipment = monitor.get_equipment(schedule.equipment_id)
    overdue_hours = (time.time_ns() - schedule.next_due_ns) / 1e9 / 3600
    print(f"{equipment.name}: Overdue by {overdue_hours:.1f} hours")
```

### Example 5: Predictive Analytics

```python
# Predict maintenance needs for the next week
predictions = monitor.predict_maintenance_needs("ENG-001", lookahead_hours=168)

for prediction in predictions:
    print(f"Reason: {prediction['reason']}")
    print(f"Priority: {prediction['priority']}")
    print(f"Due: {prediction['due_date']}")
    if 'mtbf_hours' in prediction:
        print(f"MTBF: {prediction['mtbf_hours']:.1f} hours")
    print()

# Calculate reliability metrics
mtbf = monitor.calculate_mtbf("ENG-001")
mttr = monitor.calculate_mttr("ENG-001")
uptime = monitor.calculate_equipment_uptime("ENG-001")

print(f"Reliability Analysis:")
print(f"  MTBF: {mtbf:.1f} hours" if mtbf else "  MTBF: Insufficient data")
print(f"  MTTR: {mttr:.1f} hours" if mttr else "  MTTR: Insufficient data")
print(f"  Uptime: {uptime['uptime_percentage']}%")
print(f"  Downtime: {uptime['total_downtime_hours']} hours")
print(f"  Failures: {uptime['failure_count']}")
```

### Example 6: Alert Generation

```python
# Get all current alerts
alerts = monitor.get_alerts()

# Sort by severity
severity_order = {"critical": 0, "high": 1, "warning": 2}
alerts.sort(key=lambda x: severity_order.get(x['severity'], 99))

# Display alerts
for alert in alerts:
    print(f"[{alert['severity'].upper()}] {alert['code']}")
    print(f"  {alert['message']}")

    # Add additional context based on alert type
    if 'equipment_id' in alert:
        equipment = monitor.get_equipment(alert['equipment_id'])
        print(f"  Location: {equipment.location}")
        print(f"  Type: {equipment.type.value}")

    if 'overdue_hours' in alert:
        print(f"  Overdue by: {alert['overdue_hours']} hours")

    print()
```

### Example 7: Watcher Integration

```python
# Get watcher frame for rule evaluation
frame = monitor.get_watcher_frame()

print(f"Equipment Monitor Snapshot:")
print(f"  Total equipment: {frame['equipment_count']}")
print(f"  Status breakdown: {frame['equipment_status_counts']}")
print(f"  Overdue maintenance: {frame['overdue_maintenance_count']}")
print(f"  Unresolved failures: {frame['unresolved_failure_counts']}")
print(f"  Total maintenance logs: {frame['total_maintenance_logs']}")
print(f"  Total failures: {frame['total_failures']}")

# Use frame in watcher rule evaluation
# watcher.evaluate(frame=frame)
```

### Example 8: Complete Workflow

```python
from twin.equipment_monitor import (
    EquipmentMonitor,
    EquipmentType,
    EquipmentStatus,
    MaintenanceType,
    FailureType,
    Severity
)
import time

# 1. Initialize monitor
monitor = EquipmentMonitor(data_dir="vessel_equipment")

# 2. Add equipment
monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")
monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")

# 3. Schedule maintenance
monitor.schedule_maintenance("ENG-001", MaintenanceType.ROUTINE, 500.0)
monitor.schedule_maintenance("PUMP-001", MaintenanceType.PREVENTIVE, 100.0)

# 4. Log initial maintenance
monitor.log_maintenance(
    "ENG-001",
    MaintenanceType.ROUTINE,
    "Initial oil change",
    "tech_john",
    4.5,
    350.00
)

# 5. Simulate failure
monitor.log_failure(
    "PUMP-001",
    FailureType.MECHANICAL,
    Severity.HIGH,
    "Bearing failure"
)

# 6. Check status
pump = monitor.get_equipment("PUMP-001")
print(f"Pump status: {pump.status.value}")  # FAILED

# 7. Get alerts
alerts = monitor.get_alerts()
for alert in alerts:
    print(f"Alert: {alert['code']} - {alert['message']}")

# 8. Resolve failure
monitor.resolve_failure("PUMP-001", "Replaced bearings")

# 9. Log repair maintenance
monitor.log_maintenance(
    "PUMP-001",
    MaintenanceType.CORRECTIVE,
    "Bearing replacement",
    "tech_jane",
    2.0,
    450.00
)

# 10. Calculate analytics
uptime = monitor.calculate_equipment_uptime("PUMP-001")
print(f"Pump uptime: {uptime['uptime_percentage']}%")

# 11. Predict future needs
predictions = monitor.predict_maintenance_needs("ENG-001", 168)
for prediction in predictions:
    print(f"Prediction: {prediction['reason']} - {prediction['priority']} priority")

# 12. Save snapshot
snapshot = monitor.to_dict()
import json
with open("equipment_snapshot.json", "w") as f:
    json.dump(snapshot, f, indent=2)
```

---

## Testing

The EquipmentMonitor has comprehensive test coverage with 60+ test cases organized into 8 test classes.

### Test Organization

#### TestEquipmentCRUD (8 tests)
- Equipment creation and retrieval
- String type conversion
- Duplicate ID detection
- Invalid input validation
- Equipment filtering by type

#### TestStatusUpdates (4 tests)
- Status updates
- String status conversion
- Nonexistent equipment handling
- Status serialization

#### TestMaintenanceLogging (6 tests)
- Maintenance logging
- String type conversion
- Equipment timestamp updates
- Nonexistent equipment handling
- Maintenance history retrieval
- Cost summary calculation

#### TestFailureLogging (9 tests)
- Failure logging
- String type conversion
- Automatic status updates (HIGH/CRITICAL)
- Status preservation (MEDIUM/LOW)
- Failure resolution
- Equipment status restoration
- Unresolved failure handling
- Failure history retrieval

#### TestMaintenanceScheduling (5 tests)
- Maintenance scheduling
- Default interval usage
- Schedule retrieval
- Due maintenance calculation
- Overdue maintenance calculation

#### TestPredictiveMaintenance (3 tests)
- Schedule-based prediction
- Failure history (MTBF) prediction
- Status-based prediction

#### TestAnalytics (4 tests)
- MTBF calculation with chronological data
- MTBF with insufficient data
- MTTR calculation
- Equipment uptime calculation
- Uptime with unresolved failures

#### TestAlertGeneration (4 tests)
- Failed equipment alerts
- Degraded equipment alerts
- Overdue maintenance alerts
- Unresolved critical failure alerts

#### TestIntegration (10 tests)
- Watcher frame generation
- Comprehensive snapshot creation
- JSONL persistence
- Disk loading
- Serialization roundtrips (all data structures)

#### TestEdgeCases (7 tests)
- Empty monitor state
- Invalid install dates
- Negative maintenance duration
- Negative maintenance cost
- Invalid scheduling intervals
- Disabled persistence

### Running Tests

```bash
# Run all tests
pytest twin/tests/test_equipment_monitor.py -v

# Run specific test class
pytest twin/tests/test_equipment_monitor.py::TestEquipmentCRUD -v

# Run specific test
pytest twin/tests/test_equipment_monitor.py::TestEquipmentCRUD::test_add_equipment_success -v

# Run with coverage
pytest twin/tests/test_equipment_monitor.py --cov=twin.equipment_monitor --cov-report=html
```

### Test Coverage

The test suite covers:

- **CRUD Operations**: Equipment creation, retrieval, updates, filtering
- **Status Management**: Status changes, automatic updates, serialization
- **Maintenance Logging**: Logging, history, cost tracking
- **Failure Tracking**: Logging, resolution, history, automatic status changes
- **Scheduling**: Schedule creation, due calculation, overdue detection
- **Predictive Analytics**: MTBF, MTTR, uptime, predictions
- **Alert Generation**: All alert types, severity levels
- **Integration**: Watcher frames, snapshots, persistence
- **Edge Cases**: Validation, error handling, empty states

### Test Data

Tests use temporary directories and sample data:

```python
@pytest.fixture
def populated_monitor(monitor):
    """Monitor populated with sample equipment and data."""
    monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")
    monitor.add_equipment("GEN-001", "Generator 1", EquipmentType.GENERATOR, "Engine Room")
    monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")
    monitor.add_equipment("WINCH-001", "Trawl Winch", EquipmentType.WINCH, "Deck")

    monitor.log_maintenance("ENG-001", MaintenanceType.ROUTINE, "Oil change", "tech_john", 4.5, 350.00)
    monitor.log_maintenance("PUMP-001", MaintenanceType.PREVENTIVE, "Seal replacement", "tech_jane", 2.0, 150.00)

    monitor.schedule_maintenance("ENG-001", MaintenanceType.ROUTINE, 500.0)
    monitor.schedule_maintenance("PUMP-001", MaintenanceType.PREVENTIVE, 100.0)

    return monitor
```

---

## Best Practices

### 1. Equipment Registration

Always add equipment before logging maintenance or failures:

```python
# Good
monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")
monitor.log_maintenance("ENG-001", MaintenanceType.ROUTINE, "Service", "tech", 1.0, 100.0)

# Bad - will raise ValueError
monitor.log_maintenance("ENG-001", MaintenanceType.ROUTINE, "Service", "tech", 1.0, 100.0)
```

### 2. Maintenance Scheduling

Schedule maintenance after logging the initial maintenance:

```python
# Log initial maintenance
monitor.log_maintenance("ENG-001", MaintenanceType.ROUTINE, "Initial service", "tech", 2.0, 200.0)

# Then schedule recurring maintenance
monitor.schedule_maintenance("ENG-001", MaintenanceType.ROUTINE, 500.0)
```

### 3. Failure Resolution

Always resolve failures after repair:

```python
# Log failure
monitor.log_failure("PUMP-001", FailureType.MECHANICAL, Severity.HIGH, "Bearing failure")

# Perform repair...

# Resolve failure
monitor.resolve_failure("PUMP-001", "Replaced bearings")

# Log repair maintenance
monitor.log_maintenance("PUMP-001", MaintenanceType.CORRECTIVE, "Bearing replacement", "tech", 2.0, 450.00)
```

### 4. Alert Monitoring

Check alerts regularly for proactive maintenance:

```python
alerts = monitor.get_alerts()
critical_alerts = [a for a in alerts if a['severity'] == 'critical']

if critical_alerts:
    # Take immediate action
    send_notification(critical_alerts)
```

### 5. Predictive Maintenance

Use predictive analytics to schedule maintenance proactively:

```python
# Check weekly predictions
predictions = monitor.predict_maintenance_needs("ENG-001", lookahead_hours=168)

high_priority = [p for p in predictions if p['priority'] in ('critical', 'high')]
if high_priority:
    # Schedule maintenance
    for prediction in high_priority:
        schedule_maintenance_for(prediction)
```

---

## Performance Considerations

### Persistence

- **JSONL Format**: Append-only writes ensure durability
- **In-Memory Storage**: Fast queries with in-memory indexes
- **Loading**: `load_from_disk()` can be slow for large datasets

### Scalability

- **Equipment Count**: Supports 1000+ equipment records
- **Maintenance Logs**: Scales to 10,000+ log entries
- **Failure Events**: Scales to 10,000+ events
- **Queries**: O(n) for filtered queries, O(1) for ID lookups

### Optimization Tips

1. **Use Specific Queries**: Use `get_equipment()` instead of `get_all_equipment()` when possible
2. **Filter Early**: Use `get_equipment_by_type()` to reduce working set
3. **Batch Operations**: Load all data at startup with `load_from_disk()`
4. **Monitor Alerts**: Check alerts periodically instead of on every update

---

## Troubleshooting

### Common Issues

#### Issue: "Equipment not found" error

**Cause**: Attempting to log maintenance/failure for non-existent equipment

**Solution**: Always add equipment first:

```python
monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")
monitor.log_maintenance("ENG-001", ...)  # Now works
```

#### Issue: Maintenance schedule not due

**Cause**: Scheduling with incorrect interval calculation

**Solution**: Check interval and last maintenance time:

```python
schedule = monitor.schedule_maintenance("ENG-001", MaintenanceType.ROUTINE, 500.0)
print(f"Next due: {schedule.next_due_ns}")
print(f"Hours from now: {(schedule.next_due_ns - time.time_ns()) / 1e9 / 3600}")
```

#### Issue: Alerts not generated

**Cause**: Equipment status or maintenance schedules not triggering alerts

**Solution**: Verify status and schedules:

```python
equipment = monitor.get_equipment("ENG-001")
print(f"Status: {equipment.status.value}")

schedule = monitor.get_maintenance_schedule("ENG-001")
if schedule:
    print(f"Next due: {schedule.next_due_ns}")
else:
    print("No schedule found")

alerts = monitor.get_alerts()
print(f"Total alerts: {len(alerts)}")
```

---

## Reference Implementation

### Complete Equipment Monitoring System

```python
from twin.equipment_monitor import (
    EquipmentMonitor,
    EquipmentType,
    EquipmentStatus,
    MaintenanceType,
    FailureType,
    Severity
)
import time
import json

class VesselEquipmentSystem:
    """Complete vessel equipment monitoring system."""

    def __init__(self, data_dir="vessel_equipment"):
        """Initialize equipment monitoring system."""
        self.monitor = EquipmentMonitor(data_dir=data_dir)
        self.monitor.load_from_disk()

    def add_equipment(self, equipment_id, name, type, location):
        """Add new equipment."""
        return self.monitor.add_equipment(equipment_id, name, type, location)

    def perform_maintenance(self, equipment_id, maintenance_type, description, technician, duration, cost):
        """Log maintenance activity."""
        return self.monitor.log_maintenance(
            equipment_id, maintenance_type, description, technician, duration, cost
        )

    def report_failure(self, equipment_id, failure_type, severity, description):
        """Log equipment failure."""
        return self.monitor.log_failure(equipment_id, failure_type, severity, description)

    def resolve_failure(self, equipment_id, resolution):
        """Resolve equipment failure."""
        return self.monitor.resolve_failure(equipment_id, resolution)

    def schedule_maintenance(self, equipment_id, maintenance_type, interval_hours=None):
        """Schedule recurring maintenance."""
        return self.monitor.schedule_maintenance(equipment_id, maintenance_type, interval_hours)

    def get_status_report(self):
        """Generate comprehensive status report."""
        frame = self.monitor.get_watcher_frame()
        alerts = self.monitor.get_alerts()

        return {
            "timestamp": time.time(),
            "equipment": {
                "total": frame["equipment_count"],
                "status_counts": frame["equipment_status_counts"]
            },
            "maintenance": {
                "overdue_count": frame["overdue_maintenance_count"],
                "total_logs": frame["total_maintenance_logs"]
            },
            "failures": {
                "unresolved_counts": frame["unresolved_failure_counts"],
                "total_events": frame["total_failures"]
            },
            "alerts": {
                "total": len(alerts),
                "critical": len([a for a in alerts if a['severity'] == 'critical']),
                "high": len([a for a in alerts if a['severity'] == 'high']),
                "warning": len([a for a in alerts if a['severity'] == 'warning'])
            }
        }

    def get_equipment_analytics(self, equipment_id):
        """Get analytics for specific equipment."""
        mtbf = self.monitor.calculate_mtbf(equipment_id)
        mttr = self.monitor.calculate_mttr(equipment_id)
        uptime = self.monitor.calculate_equipment_uptime(equipment_id)
        predictions = self.monitor.predict_maintenance_needs(equipment_id, lookahead_hours=168)

        return {
            "equipment_id": equipment_id,
            "mtbf_hours": mtbf,
            "mttr_hours": mttr,
            "uptime_percentage": uptime["uptime_percentage"],
            "total_downtime_hours": uptime["total_downtime_hours"],
            "failure_count": uptime["failure_count"],
            "predictions": predictions
        }

    def save_snapshot(self, filepath):
        """Save current state to file."""
        snapshot = self.monitor.to_dict()
        with open(filepath, 'w') as f:
            json.dump(snapshot, f, indent=2)

# Usage
system = VesselEquipmentSystem()

# Add equipment
system.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")
system.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")

# Schedule maintenance
system.schedule_maintenance("ENG-001", MaintenanceType.ROUTINE, 500.0)

# Get status report
report = system.get_status_report()
print(json.dumps(report, indent=2))

# Get equipment analytics
analytics = system.get_equipment_analytics("ENG-001")
print(json.dumps(analytics, indent=2))
```

---

## Appendix

### JSONL File Format

#### equipment.jsonl

```json
{"equipment_id": "ENG-001", "name": "Main Engine", "type": "ENGINE", "location": "Engine Room", "status": "OPERATIONAL", "install_date_ns": 1704067200000000000, "last_maintenance_ns": 1704153600000000000}
{"equipment_id": "PUMP-001", "name": "Cooling Pump", "type": "PUMP", "location": "Engine Room", "status": "OPERATIONAL", "install_date_ns": 1704067200000000000, "last_maintenance_ns": null}
```

#### maintenance.jsonl

```json
{"equipment_id": "ENG-001", "maintenance_type": "ROUTINE", "description": "Oil change and filter replacement", "technician": "tech_john", "duration_hours": 4.5, "cost": 350.0, "timestamp_ns": 1704153600000000000}
{"equipment_id": "PUMP-001", "maintenance_type": "PREVENTIVE", "description": "Seal replacement and bearing check", "technician": "tech_jane", "duration_hours": 2.0, "cost": 150.0, "timestamp_ns": 1704157200000000000}
```

#### failures.jsonl

```json
{"equipment_id": "PUMP-001", "failure_type": "MECHANICAL", "severity": "HIGH", "description": "Bearing failure detected", "timestamp_ns": 1704160800000000000, "resolved_ns": 1704164400000000000}
{"equipment_id": "ENG-001", "failure_type": "ELECTRICAL", "severity": "CRITICAL", "description": "Starter motor failure", "timestamp_ns": 1704168000000000000, "resolved_ns": null}
```

#### schedules.jsonl

```json
{"equipment_id": "ENG-001", "maintenance_type": "ROUTINE", "interval_hours": 500.0, "last_performed_ns": 1704153600000000000, "next_due_ns": 1705927200000000000}
{"equipment_id": "PUMP-001", "maintenance_type": "PREVENTIVE", "interval_hours": 100.0, "last_performed_ns": 1704157200000000000, "next_due_ns": 1704497600000000000}
```

### Timestamp Conversion

The system uses nanosecond timestamps (Unix epoch * 1e9):

```python
import time
from datetime import datetime, timezone

# Current time in nanoseconds
now_ns = time.time_ns()

# Convert to datetime
dt = datetime.fromtimestamp(now_ns / 1e9, tz=timezone.utc)

# Convert from datetime to nanoseconds
ns = int(dt.timestamp() * 1e9)

# Format as ISO string
iso_string = dt.isoformat()
```

---

## Changelog

### Version 1.0.0 (2026-07-28)

- Initial release
- Equipment CRUD operations
- Maintenance logging and scheduling
- Failure tracking and resolution
- Predictive maintenance analytics (MTBF, MTTR, uptime)
- Alert generation
- JSONL persistence
- 60+ comprehensive tests
- Full documentation

---

## Support

For questions, issues, or contributions:

1. Review the test suite for usage examples
2. Check the API reference for method signatures
3. Examine the JSONL file format for data structure
4. Review the integration examples for patterns

---

**Document Version:** 1.0.0
**Last Updated:** 2026-07-28
**Component:** EquipmentMonitor (twin/equipment_monitor.py)
