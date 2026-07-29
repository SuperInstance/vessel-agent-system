# Crew Safety System for AELMA Twin

## Overview

The Crew Safety system provides comprehensive safety management for vessel operations, going beyond fatigue monitoring to cover all aspects of crew safety including:

- **Safety Incident Tracking** - Log, track, and analyze safety incidents
- **Emergency Response Protocols** - Standardized emergency procedures
- **Training & Certification Management** - Track crew training and certifications
- **Safety Drills** - Schedule, conduct, and score safety drills
- **Safety Equipment Management** - Track safety equipment status and inspections
- **PPE Management** - Monitor Personal Protective Equipment issuance

## Architecture

### Data Structures

#### SafetyIncident
```python
@dataclass
class SafetyIncident:
    incident_id: str
    incident_type: IncidentType
    severity: IncidentSeverity
    description: str
    location_lat: float | None
    location_lon: float | None
    timestamp_ns: int
    crew_involved: list[str]
    resolved_ns: int | None
    root_cause: str | None
    lessons_learned: str | None
    corrective_actions: list[str]
```

#### EmergencyProtocol
```python
@dataclass
class EmergencyProtocol:
    protocol_type: ProtocolType
    steps: list[str]
    contacts: list[dict[str, str]]
    equipment_required: list[EquipmentType]
    priority_contacts: list[dict[str, str]]
```

#### TrainingRecord
```python
@dataclass
class TrainingRecord:
    crew_id: str
    training_type: TrainingType
    completion_date_ns: int
    expiry_date_ns: int | None
    certification_id: str | None
    instructor: str | None
    training_provider: str | None
    score: float | None
    notes: str | None
```

#### SafetyDrill
```python
@dataclass
class SafetyDrill:
    drill_type: DrillType
    scheduled_date_ns: int
    completed_date_ns: int | None
    participants: list[str]
    score: float | None
    deficiencies: list[str]
    strengths: list[str]
    evaluator: str | None
    notes: str | None
    response_time_seconds: float | None
```

#### SafetyEquipment
```python
@dataclass
class SafetyEquipment:
    equipment_id: str
    equipment_type: EquipmentType
    location: str
    last_inspected_ns: int
    expiry_date_ns: int | None
    status: EquipmentStatus
    model: str | None
    serial_number: str | None
    inspection_notes: str | None
```

#### PPERecord
```python
@dataclass
class PPERecord:
    crew_id: str
    ppe_type: PPEType
    issue_date_ns: int
    condition: PPECondition
    size: str | None
    brand: str | None
    serial_number: str | None
    expiry_date_ns: int | None
    inspection_required_ns: int | None
```

## Incident Types

- `MOB` - Man Overboard
- `INJURY` - Crew injury
- `ILLNESS` - Medical emergency
- `FIRE` - Fire on board
- `FLOODING` - Flooding emergency
- `GEAR_ENTANGLEMENT` - Fishing gear incident
- `WEATHER_DAMAGE` - Weather-related incident
- `MACHINERY_FAILURE` - Equipment failure causing safety issue
- `NEAR_MISS` - Near miss incident
- `OTHER` - Other safety incidents

## Severity Levels

- `MINOR` - No injuries, minimal impact
- `MODERATE` - Minor injuries or equipment damage
- `MAJOR` - Serious injuries or significant damage
- `CRITICAL` - Life-threatening or vessel disabled

## Emergency Protocols

The system includes 5 default emergency protocols:

1. **MOB_RESPONSE** - Man overboard response procedures
2. **FIRE_RESPONSE** - Fire fighting procedures
3. **ABANDON_SHIP** - Abandon ship procedures
4. **MEDICAL_EMERGENCY** - Medical response procedures
5. **MAYDAY** - Distress call procedures

Each protocol includes:
- Step-by-step procedures
- Crew role assignments
- Required equipment lists
- Priority emergency contacts

## Training Types

- `BASIC_SAFETY` - Basic safety training
- `MOB_DRILL` - Man overboard drill
- `FIRE_DRILL` - Fire fighting drill
- `FIRST_AID` - First aid/CPR
- `SURVIVAL_CRAFT` - Lifeboat/liferaft operations
- `HELICOPTER_EVACUATION` - Helicopter operations
- `THERMAL_PROTECTORS` - Fire protection
- `CARGO_SAFETY` - Cargo handling safety

## Safety Equipment Types

- `LIFE_JACKET` - Personal flotation device
- `LIFE_RAFT` - Liferaft
- `EPIRB` - Emergency position indicating radio beacon
- `SAT_PHONE` - Satellite phone
- `FIRST_AID_KIT` - Medical kit
- `FIRE_EXTINGUISHER` - Fire suppression
- `IMMERSION_SUIT` - Exposure suit
- `MOB_DEVICE` - PLB/AIS MOB device
- `FLARES` - Visual distress signals

## PPE Types

- `HARD_HAT` - Head protection
- `SAFETY_BOOTS` - Foot protection
- `GLOVES` - Hand protection
- `HIGH_VISIBILITY` - High-visibility clothing
- `SAFETY_GLASSES` - Eye protection
- `HEARING_PROTECTION` - Ear protection
- `LIFE_JACKET` - PFD
- `IMMERSION_SUIT` - Exposure suit
- `RESPIRATOR` - Respiratory protection

## Usage Examples

### Initialize Safety System

```python
from safety import CrewSafety

safety = CrewSafety(
    vessel_id="US-AK-FVEILEEN-51",
    data_dir="crew_safety_data"
)
```

### Log Safety Incident

```python
incident = safety.log_safety_incident(
    incident_type=IncidentType.MOB,
    severity=IncidentSeverity.CRITICAL,
    description="Crew member fell overboard while hauling gear",
    location_lat=59.5,
    location_lon=-152.3,
    crew_involved=["crew_001"]
)
```

### Resolve Incident

```python
safety.resolve_incident(
    incident_id=incident.incident_id,
    root_cause="Slipped on wet deck during gear retrieval",
    lessons_learned="Need non-slip deck coating and better footwear",
    corrective_actions=[
        "Install non-slip deck coating",
        "Require slip-resistant safety boots",
        "Add hand lines near winch"
    ]
)
```

### Activate Emergency Protocol

```python
protocol = safety.activate_emergency_protocol(ProtocolType.MOB_RESPONSE)
for step in protocol.steps:
    print(step)
```

### Add Training Record

```python
now_ns = time.time_ns()
expiry_ns = now_ns + (365 * 24 * 3600 * 1e9)  # 1 year

safety.add_training_record(
    crew_id="crew_001",
    training_type=TrainingType.BASIC_SAFETY,
    completion_date_ns=now_ns,
    expiry_date_ns=expiry_ns,
    certification_id="BST-2024-001",
    instructor="John Smith",
    score=95.0
)
```

### Log Safety Drill

```python
safety.log_safety_drill(
    drill_type=DrillType.MOB_DRILL,
    scheduled_date_ns=time.time_ns(),
    participants=["crew_001", "crew_002", "crew_003"],
    score=88.0,
    deficiencies=["Some crew delayed in donning PFDs"],
    strengths=["Good communication", "Quick MOB notification"],
    evaluator="Captain",
    response_time_seconds=105.0
)
```

### Add Safety Equipment

```python
safety.add_safety_equipment(
    equipment_id="EPIRB-001",
    equipment_type=EquipmentType.EPIRB,
    location="Bridge",
    expiry_date_ns=time.time_ns() + (5 * 365 * 24 * 3600 * 1e9),
    model="McMurdo FastFind",
    serial_number="SN12345"
)
```

### Issue PPE

```python
safety.issue_ppe(
    crew_id="crew_001",
    ppe_type=PPEType.HARD_HAT,
    size="Large",
    brand="MSA",
    serial_number="HH12345"
)
```

### Get Alerts

```python
alerts = safety.get_alerts()
for alert in alerts:
    print(f"{alert['severity']}: {alert['message']}")
```

### Get Safety Summary

```python
summary = safety.get_safety_summary(days=30)
print(f"Incidents: {summary['incident_statistics']['total_incidents']}")
print(f"Equipment Issues: {summary['equipment']['unserviceable']}")
print(f"Overdue Drills: {summary['drills']['overdue_count']}")
```

## Integration with TwinCore

The safety system integrates with TwinCore through several mechanisms:

### 1. MOB Detection Integration

```python
# In TwinCore
if self.mob is not None and self.safety is not None:
    mob_event = self.mob.get_active_event()
    if mob_event:
        # Log MOB as safety incident
        self.safety.log_safety_incident(
            incident_type=IncidentType.MOB,
            severity=IncidentSeverity.CRITICAL,
            description=f"MOB detected: {mob_event.crew_member_id or 'Unknown'}",
            location_lat=mob_event.mob_lat,
            location_lon=mob_event.mob_lon,
            crew_involved=[mob_event.crew_member_id] if mob_event.crew_member_id else []
        )
```

### 2. WatcherRegistry Integration

```python
# Safety system provides watcher frame
watcher_frame = safety.get_watcher_frame()

# Includes:
# - Total incidents and severity counts
# - Unresolved incidents
# - Equipment issues
# - Training expirations
# - Active alerts
```

### 3. Snapshot Integration

```python
# In TwinCore snapshot
snap = {
    # ... other data
    "safety": self.safety.to_dict() if self.safety else None
}
```

## Alert Generation

The system generates alerts for:

### Training Alerts
- **Critical**: Training expired
- **High**: Training expires within 7 days
- **Warning**: Training expires within 30 days

### Equipment Alerts
- **Critical**: Equipment expired
- **High**: Equipment expires within 7 days
- **Warning**: Equipment expires within 30 days
- **High**: Equipment unserviceable

### Drill Alerts
- **High**: Drill overdue (90+ days since last drill)

### Incident Alerts
- **Critical**: Unresolved CRITICAL incident
- **High**: Unresolved MAJOR incident

## Persistence

All data is persisted using JSONL append-only files:

- `incidents.jsonl` - Safety incident records
- `protocols.jsonl` - Emergency protocols
- `training.jsonl` - Training records
- `drills.jsonl` - Safety drill records
- `equipment.jsonl` - Safety equipment records
- `ppe.jsonl` - PPE issuance records

Data is automatically loaded on initialization and persisted on updates.

## Safety Analytics

### Incident Statistics
```python
stats = safety.get_incident_statistics(days=30)
# Returns:
# - Total incidents
# - Breakdown by type and severity
# - Resolution rate
# - Average resolution time
```

### Training Status
```python
expiring = safety.check_training_expiry(days_ahead=30)
# Returns list of training expiring soon
```

### Equipment Status
```python
expiring = safety.check_equipment_expiry(days_ahead=30)
# Returns list of equipment expiring soon

issues = safety.get_safety_equipment(status="UNSERVICEABLE")
# Returns equipment needing attention
```

### Drill Performance
```python
overdue = safety.get_overdue_drills(days_threshold=90)
# Returns list of overdue drills

history = safety.get_drill_history(drill_type=DrillType.MOB_DRILL)
# Returns drill history with scores and performance
```

## Testing

The system includes 48 comprehensive tests covering:

- Incident logging and resolution
- Emergency protocol activation
- Training management
- Drill tracking
- Equipment management
- PPE tracking
- Alert generation
- Data persistence
- Integration scenarios
- Watcher frame generation
- Serialization

Run tests with:
```bash
pytest twin/safety/tests/test_crew_safety.py -v
```

## File Structure

```
twin/safety/
├── __init__.py                 # Package exports
├── crew_safety.py             # Main safety system implementation
├── README.md                  # This documentation
└── tests/
    ├── __init__.py
    └── test_crew_safety.py    # Comprehensive test suite
```

## Key Features

1. **Comprehensive Incident Tracking**
   - Multiple incident types
   - Severity classification
   - Root cause analysis
   - Lessons learned capture
   - Corrective action tracking

2. **Emergency Response Ready**
   - 5 standard protocols pre-configured
   - Step-by-step procedures
   - Role-based responsibilities
   - Equipment requirements
   - Emergency contact lists

3. **Training Management**
   - Certification tracking
   - Expiry monitoring
   - Scoring and performance
   - Instructor records
   - Automated alerts

4. **Safety Drills**
   - Multiple drill types
   - Performance scoring
   - Deficiency tracking
   - Response time measurement
   - Overdue monitoring

5. **Equipment Tracking**
   - Status monitoring
   - Expiry tracking
   - Inspection scheduling
   - Location tracking
   - Maintenance records

6. **PPE Management**
   - Issuance tracking
   - Condition monitoring
   - Size/brand management
   - Expiry tracking
   - Crew assignment

7. **Alert System**
   - Multi-severity alerts
   - Expiry warnings
   - Status notifications
   - Overdue reminders
   - Critical incident alerts

8. **Integration Ready**
   - WatcherRegistry frame
   - TwinCore snapshot
   - MOB detection integration
   - JSON persistence
   - Full serialization

## Safety Culture Promotion

The system promotes a strong safety culture through:

1. **Incident Tracking** - Learn from mistakes
2. **Root Cause Analysis** - Address underlying issues
3. **Lessons Learned** - Share knowledge
4. **Regular Drills** - Practice response procedures
5. **Training Monitoring** - Ensure crew competency
6. **Equipment Readiness** - Maintain safety gear
7. **Alert System** - Proactive issue identification

## Regulatory Compliance

The system supports regulatory compliance by:

- Recording all safety incidents
- Tracking required training certifications
- Documenting safety drill participation
- Maintaining equipment inspection records
- Providing audit trails through JSONL logs
- Generating comprehensive safety summaries

## Future Enhancements

Potential future additions:

1. **Safety KPIs** - Track safety performance indicators
2. **Risk Assessment** - Pre-sail safety planning
3. **JSA Integration** - Job Safety Analysis integration
4. **Safety Meetings** - Record safety meeting minutes
5. **Audit Trails** - Enhanced logging for compliance
6. **Reporting** - Generate safety reports
7. **Analytics** - Advanced safety analytics
8. **Mobile App** - Mobile access for crew

## Conclusion

The Crew Safety system provides a comprehensive foundation for vessel safety management, extending beyond fatigue monitoring to cover all aspects of crew safety. By tracking incidents, managing training, monitoring equipment, and maintaining emergency protocols, the system helps prevent accidents, ensures regulatory compliance, and promotes a strong safety culture on board.
