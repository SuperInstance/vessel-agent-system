# Equipment Monitoring and Maintenance System - Summary

## Overview

A comprehensive Equipment monitoring and maintenance system has been successfully implemented for the AELMA twin at `twin/equipment_monitor.py`. The system provides vessel equipment lifecycle management, maintenance tracking, failure monitoring, and predictive maintenance analytics.

## Implementation Details

### File Location
- **Main Module**: `C:\Users\casey\claudetz\aelma\build_kimi\twin\equipment_monitor.py`
- **Tests**: `C:\Users\casey\claudetz\aelma\build_kimi\twin\tests\test_equipment_monitor.py`
- **Test Results**: **60/60 tests passing** (100% success rate)

### Core Components

#### 1. Data Structures (Dataclasses)

**Equipment**
- `equipment_id`: Unique identifier
- `name`: Human-readable name
- `type`: EquipmentType enum (10 types)
- `location`: Physical location on vessel
- `status`: EquipmentStatus enum (5 states)
- `install_date_ns`: Installation timestamp (nanoseconds)
- `last_maintenance_ns`: Last maintenance timestamp

**MaintenanceLog**
- `equipment_id`: Associated equipment
- `maintenance_type`: MaintenanceType enum (6 types)
- `description`: Work performed
- `technician`: Who performed work
- `duration_hours`: Time spent
- `cost`: Maintenance cost
- `timestamp_ns`: When performed

**FailureEvent**
- `equipment_id`: Associated equipment
- `failure_type`: FailureType enum (7 types)
- `severity`: Severity enum (4 levels)
- `description`: Failure description
- `timestamp_ns`: When occurred
- `resolved_ns`: When resolved (optional)

**MaintenanceSchedule**
- `equipment_id`: Associated equipment
- `maintenance_type`: Type of maintenance
- `interval_hours`: Recurrence interval
- `last_performed_ns`: Last performance timestamp
- `next_due_ns`: Next due timestamp

#### 2. Enums

**EquipmentType** (10 types)
- ENGINE, GENERATOR, PUMP, WINCH, CRANE
- NET_SOUNDING, NAVIGATION, COMMUNICATION, SAFETY, FISHING_GEAR

**EquipmentStatus** (5 states)
- OPERATIONAL, DEGRADED, FAILED, MAINTENANCE_REQUIRED, OFFLINE

**MaintenanceType** (6 types)
- ROUTINE, PREVENTIVE, CORRECTIVE, EMERGENCY, UPGRADE, INSPECTION

**FailureType** (7 types)
- MECHANICAL, ELECTRICAL, HYDRAULIC, SOFTWARE, CORROSION, WEAR, ACCIDENT

**Severity** (4 levels)
- LOW, MEDIUM, HIGH, CRITICAL

#### 3. EquipmentMonitor Class

**Core Methods**

Equipment CRUD:
- `add_equipment()` - Register new equipment
- `update_equipment_status()` - Change operational status
- `get_equipment()` - Retrieve single equipment
- `get_all_equipment()` - Get all equipment
- `get_equipment_by_type()` - Filter by type

Maintenance Operations:
- `log_maintenance()` - Record maintenance activity
- `get_maintenance_history()` - Get maintenance log
- `get_maintenance_cost_summary()` - Cost analysis

Failure Operations:
- `log_failure()` - Record failure event
- `resolve_failure()` - Mark failure as resolved
- `get_failure_history()` - Get failure log

Maintenance Scheduling:
- `schedule_maintenance()` - Set recurring maintenance
- `get_maintenance_schedule()` - Get schedule for equipment
- `get_due_maintenance()` - Get upcoming maintenance (with lookahead)
- `get_overdue_maintenance()` - Get overdue items

Predictive Analytics:
- `predict_maintenance_needs()` - AI-powered predictions
- `calculate_mtbf()` - Mean Time Between Failures
- `calculate_mttr()` - Mean Time To Repair
- `calculate_equipment_uptime()` - Uptime percentage
- `get_maintenance_cost_summary()` - Cost analysis

Integration:
- `get_watcher_frame()` - WatcherRegistry integration
- `get_alerts()` - Generate alerts for issues
- `to_dict()` - Comprehensive snapshot
- `load_from_disk()` - Load persisted data

### Key Features

#### 1. Comprehensive Validation
- All dataclasses include `__post_init__` validation
- Type checking with helpful error messages
- Timestamp validation (must be >= 0)
- Numerical validation (durations, costs >= 0)

#### 2. JSONL Persistence
- Append-only persistence for reliability
- Four separate files:
  - `equipment.jsonl` - Equipment records
  - `maintenance.jsonl` - Maintenance logs
  - `failures.jsonl` - Failure events
  - `schedules.jsonl` - Maintenance schedules
- Automatic directory creation
- Graceful handling of I/O errors

#### 3. Predictive Maintenance
Multiple prediction strategies:
- **Scheduled maintenance**: Due date calculation
- **Failure history (MTBF)**: Pattern-based predictions
- **Current status**: DEGRADED/MAINTENANCE_REQUIRED detection
- **Priority ranking**: critical > high > medium > low

#### 4. Analytics

**MTBF (Mean Time Between Failures)**
- Calculates average time between consecutive failures
- Requires 2+ resolved failures
- Sorted chronologically for accuracy

**MTTR (Mean Time To Repair)**
- Average repair duration
- Based on resolved failures

**Equipment Uptime**
- Uptime percentage calculation
- Accounts for both resolved and unresolved failures
- Includes failure count

**Maintenance Cost Summary**
- Total cost and hours
- Breakdown by maintenance type
- Per-equipment or fleet-wide

#### 5. Alert Generation

Alerts generated for:
- **FAILED equipment** (critical severity)
- **DEGRADED equipment** (warning severity)
- **MAINTENANCE_REQUIRED** (high severity)
- **Overdue maintenance** (warning severity)
- **Unresolved CRITICAL failures** (critical severity)

#### 6. WatcherRegistry Integration

The `get_watcher_frame()` method provides real-time data for watcher rule evaluation:
- Equipment count and status breakdown
- Overdue maintenance count
- Unresolved failure counts by severity
- Total maintenance logs and failures

### Testing

#### Test Coverage: 60 comprehensive tests

**Equipment CRUD (9 tests)**
- Add equipment with various inputs
- Duplicate ID handling
- Invalid input validation
- String type conversion
- Equipment retrieval and filtering

**Status Updates (4 tests)**
- Status changes (string and enum)
- Nonexistent equipment handling
- Serialization verification

**Maintenance Logging (6 tests)**
- Maintenance logging with validation
- Equipment timestamp updates
- Maintenance history retrieval
- Cost summary calculation

**Failure Logging (8 tests)**
- Failure logging with validation
- Critical/high severity status changes
- Medium/low severity handling
- Failure resolution
- History retrieval

**Maintenance Scheduling (6 tests)**
- Schedule creation
- Default interval usage
- Due maintenance calculation
- Overdue detection

**Predictive Maintenance (3 tests)**
- Schedule-based predictions
- Failure pattern (MTBF) predictions
- Status-based predictions

**Analytics (4 tests)**
- MTBF calculation
- MTTR calculation
- Equipment uptime with resolved failures
- Equipment uptime with unresolved failures

**Alert Generation (4 tests)**
- Failed equipment alerts
- Degraded equipment alerts
- Overdue maintenance alerts
- Unresolved critical failure alerts

**Integration (8 tests)**
- Watcher frame generation
- Comprehensive snapshot creation
- JSONL persistence
- Load from disk
- Serialization roundtrips (Equipment, MaintenanceLog, FailureEvent, MaintenanceSchedule)

**Edge Cases (8 tests)**
- Empty monitor state
- Invalid install dates
- Negative durations/costs
- Invalid intervals
- Disabled persistence

### Default Maintenance Intervals

Equipment-specific intervals (in hours):
- ENGINE: 500h
- GENERATOR: 250h
- PUMP: 100h
- WINCH: 150h
- CRANE: 200h
- NET_SOUNDING: 100h
- NAVIGATION: 50h
- COMMUNICATION: 50h
- SAFETY: 25h
- FISHING_GEAR: 75h

## Usage Examples

### Basic Equipment Registration

```python
from twin.equipment_monitor import EquipmentMonitor, EquipmentType, EquipmentStatus

# Create monitor
monitor = EquipmentMonitor(data_dir="equipment_data", enable_persistence=True)

# Add equipment
engine = monitor.add_equipment(
    "ENG-001",
    "Main Engine",
    EquipmentType.ENGINE,
    "Engine Room"
)

# Update status
monitor.update_equipment_status("ENG-001", EquipmentStatus.OPERATIONAL)
```

### Maintenance Logging

```python
from twin.equipment_monitor import MaintenanceType

# Log maintenance
log_entry = monitor.log_maintenance(
    "ENG-001",
    MaintenanceType.ROUTINE,
    "Oil change and filter replacement",
    "tech_john",
    4.5,  # hours
    350.00  # cost
)

# Get maintenance history
history = monitor.get_maintenance_history("ENG-001")

# Get cost summary
summary = monitor.get_maintenance_cost_summary("ENG-001")
```

### Failure Management

```python
from twin.equipment_monitor import FailureType, Severity

# Log failure
failure = monitor.log_failure(
    "PUMP-001",
    FailureType.MECHANICAL,
    Severity.HIGH,
    "Bearing failure detected"
)

# Resolve failure
resolved = monitor.resolve_failure(
    "PUMP-001",
    "Replaced bearings",
    timestamp_ns=time.time_ns()
)
```

### Maintenance Scheduling

```python
from twin.equipment_monitor import MaintenanceType

# Schedule maintenance
schedule = monitor.schedule_maintenance(
    "ENG-001",
    MaintenanceType.ROUTINE,
    interval_hours=500.0
)

# Get due maintenance (next 24 hours)
due = monitor.get_due_maintenance(lookahead_hours=24)

# Get overdue
overdue = monitor.get_overdue_maintenance()
```

### Predictive Analytics

```python
# Predict maintenance needs (7-day lookahead)
predictions = monitor.predict_maintenance_needs(
    "ENG-001",
    lookahead_hours=168
)

# Calculate reliability metrics
mtbf = monitor.calculate_mtbf("ENG-001")  # Mean Time Between Failures
mttr = monitor.calculate_mttr("ENG-001")  # Mean Time To Repair
uptime = monitor.calculate_equipment_uptime("ENG-001")
```

### Alert Generation

```python
# Get all alerts
alerts = monitor.get_alerts()

for alert in alerts:
    print(f"[{alert['severity']}] {alert['code']}: {alert['message']}")
```

### Integration with TwinCore

```python
# In TwinCore, add equipment monitoring
from twin.equipment_monitor import EquipmentMonitor

class TwinCore:
    def __init__(self, ...):
        # ... existing initialization ...
        self.equipment_monitor = EquipmentMonitor(
            data_dir="equipment_data",
            enable_persistence=True
        )

    def handle_packet(self, packet: dict[str, Any]) -> None:
        # ... existing packet handling ...

        # Update equipment frame for watchers
        equipment_frame = self.equipment_monitor.get_watcher_frame()
        self.state.channels["equipment"] = equipment_frame

    def get_alerts(self) -> list[dict[str, Any]]:
        """Combine all system alerts."""
        alerts = []
        # ... existing alerts ...
        alerts.extend(self.equipment_monitor.get_alerts())
        return alerts
```

## Architecture Benefits

### 1. Modularity
- Self-contained equipment monitoring system
- No external dependencies beyond standard library
- Clean interfaces for integration

### 2. Scalability
- Handles unlimited equipment records
- Efficient JSONL append-only storage
- In-memory operations for speed

### 3. Reliability
- Comprehensive validation prevents invalid data
- Append-only persistence prevents data loss
- Graceful error handling

### 4. Observability
- Real-time alert generation
- WatcherRegistry integration
- Comprehensive analytics

### 5. Predictive Capability
- Multiple prediction strategies
- MTBF-based forecasting
- Status-based prioritization

## Testing Strategy

### Test Organization
- **9 test classes** covering major functionality areas
- **60 total tests** with clear documentation
- **Fixtures** for common test scenarios
- **Edge case coverage** for error handling

### Test Types
- **Unit tests**: Individual method testing
- **Integration tests**: Cross-component testing
- **Persistence tests**: I/O and serialization
- **Validation tests**: Error handling
- **Analytics tests**: Calculation accuracy

### Test Results
```
============================= 60 passed in 0.49s ==============================
```

## Performance Considerations

### In-Memory Operations
- All queries operate on in-memory data
- Fast retrieval and calculations
- No disk I/O during normal operations

### Persistence Strategy
- Append-only JSONL for reliability
- Minimal write overhead
- Easy data recovery and inspection

### Analytics Efficiency
- O(n) complexity for most queries
- Chronological sorting only when needed
- Efficient interval calculations

## Future Enhancements

### Potential Additions
1. **Equipment hierarchy**: Parent-child relationships
2. **Parts inventory**: Spare parts tracking
3. **Technician scheduling**: Resource allocation
4. **Vendor management**: Supplier information
5. **Warranty tracking**: Equipment warranty data
6. **Compliance reporting**: Regulatory requirements
7. **Advanced ML models**: More sophisticated predictions
8. **Mobile alerts**: SMS/email notifications
9. **Dashboard integration**: Real-time UI
10. **API endpoints**: REST/WebSocket access

## Conclusion

The Equipment monitoring and maintenance system provides a comprehensive, production-ready solution for vessel equipment lifecycle management. With 60 passing tests, robust validation, JSONL persistence, and predictive analytics, it offers a solid foundation for:

- **Equipment operators**: Real-time monitoring and alerts
- **Maintenance teams**: Scheduling and history tracking
- **Fleet managers**: Analytics and cost control
- **Safety officers**: Compliance and failure tracking

The system follows established AELMA twin patterns and integrates seamlessly with the existing TwinCore infrastructure through WatcherRegistry and alert generation.
