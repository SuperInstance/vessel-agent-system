"""Comprehensive Crew Safety system for the AELMA twin.

Enhances crew safety beyond fatigue monitoring with:
- MOB incident detection and integration
- Emergency response protocols
- Safety incident tracking and analysis
- Training and certification management
- Safety drill scheduling and scoring
- Safety equipment tracking
- PPE (Personal Protective Equipment) management
- Alert generation for safety issues

This system provides a holistic approach to vessel safety management,
tracking everything from minor incidents to major emergencies, ensuring
regulatory compliance, and promoting a culture of safety.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

log = logging.getLogger("aelma.safety.crew_safety")


# --------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------- #


class IncidentType(str, Enum):
    """Types of safety incidents."""

    MOB = "MOB"  # Man Overboard
    INJURY = "INJURY"  # Crew injury
    ILLNESS = "ILLNESS"  # Medical emergency
    FIRE = "FIRE"  # Fire on board
    FLOODING = "FLOODING"  # Flooding emergency
    GEAR_ENTANGLEMENT = "GEAR_ENTANGLEMENT"  # Fishing gear incident
    WEATHER_DAMAGE = "WEATHER_DAMAGE"  # Weather-related incident
    MACHINERY_FAILURE = "MACHINERY_FAILURE"  # Equipment failure causing safety issue
    NEAR_MISS = "NEAR_MISS"  # Near miss incident
    OTHER = "OTHER"  # Other safety incidents


class IncidentSeverity(str, Enum):
    """Severity levels for safety incidents."""

    MINOR = "MINOR"  # No injuries, minimal impact
    MODERATE = "MODERATE"  # Minor injuries or equipment damage
    MAJOR = "MAJOR"  # Serious injuries or significant damage
    CRITICAL = "CRITICAL"  # Life-threatening or vessel disabled


class ProtocolType(str, Enum):
    """Emergency protocol types."""

    MOB_RESPONSE = "MOB_RESPONSE"  # Man overboard response
    FIRE_RESPONSE = "FIRE_RESPONSE"  # Fire fighting
    ABANDON_SHIP = "ABANDON_SHIP"  # Abandon ship procedures
    MEDICAL_EMERGENCY = "MEDICAL_EMERGENCY"  # Medical response
    MAYDAY = "MAYDAY"  # Distress call procedures


class TrainingType(str, Enum):
    """Types of safety training."""

    BASIC_SAFETY = "BASIC_SAFETY"  # Basic safety training
    MOB_DRILL = "MOB_DRILL"  # Man overboard drill
    FIRE_DRILL = "FIRE_DRILL"  # Fire fighting drill
    FIRST_AID = "FIRST_AID"  # First aid/CPR
    SURVIVAL_CRAFT = "SURVIVAL_CRAFT"  # Lifeboat/liferaft
    HELICOPTER_EVACUATION = "HELICOPTER_EVACUATION"  # Helicopter operations
    THERMAL_PROTECTORS = "THERMAL_PROTECTORS"  # Fire protection
    CARGO_SAFETY = "CARGO_SAFETY"  # Cargo handling safety


class DrillType(str, Enum):
    """Types of safety drills."""

    MOB_DRILL = "MOB_DRILL"  # Man overboard drill
    FIRE_DRILL = "FIRE_DRILL"  # Fire drill
    ABANDON_SHIP_DRILL = "ABANDON_SHIP_DRILL"  # Abandon ship drill
    MEDICAL_EMERGENCY_DRILL = "MEDICAL_EMERGENCY_DRILL"  # Medical drill
    MAYDAY_DRILL = "MAYDAY_DRILL"  # Distress call drill


class EquipmentType(str, Enum):
    """Types of safety equipment."""

    LIFE_JACKET = "LIFE_JACKET"  # PFD
    LIFE_RAFT = "LIFE_RAFT"  # Liferaft
    EPIRB = "EPIRB"  # Emergency beacon
    SAT_PHONE = "SAT_PHONE"  # Satellite phone
    FIRST_AID_KIT = "FIRST_AID_KIT"  # Medical kit
    FIRE_EXTINGUISHER = "FIRE_EXTINGUISHER"  # Fire suppression
    IMMERSION_SUIT = "IMMERSION_SUIT"  # Exposure suit
    MOB_DEVICE = "MOB_DEVICE"  # PLB/AIS MOB
    FLARES = "FLARES"  # Visual distress signals


class EquipmentStatus(str, Enum):
    """Safety equipment status."""

    SERVICEABLE = "SERVICEABLE"  # Ready for use
    NEEDS_INSPECTION = "NEEDS_INSPECTION"  # Due for inspection
    UNSERVICEABLE = "UNSERVICEABLE"  # Not functional
    EXPIRED = "EXPIRED"  # Expired consumables


class PPEType(str, Enum):
    """Types of Personal Protective Equipment."""

    HARD_HAT = "HARD_HAT"  # Head protection
    SAFETY_BOOTS = "SAFETY_BOOTS"  # Foot protection
    GLOVES = "GLOVES"  # Hand protection
    HIGH_VISIBILITY = "HIGH_VISIBILITY"  # High-visibility clothing
    SAFETY_GLASSES = "SAFETY_GLASSES"  # Eye protection
    HEARING_PROTECTION = "HEARING_PROTECTION"  # Ear protection
    LIFE_JACKET = "LIFE_JACKET"  # PFD
    IMMERSION_SUIT = "IMMERSION_SUIT"  # Exposure suit
    RESPIRATOR = "RESPIRATOR"  # Respiratory protection
    OTHER = "OTHER"  # Other PPE


class PPECondition(str, Enum):
    """PPE condition status."""

    NEW = "NEW"  # New condition
    GOOD = "GOOD"  # Good condition
    FAIR = "FAIR"  # Fair condition, needs monitoring
    POOR = "POOR"  # Poor condition, needs replacement
    DAMAGED = "DAMAGED"  # Damaged, not usable


# --------------------------------------------------------------------- #
# Dataclasses
# --------------------------------------------------------------------- #


@dataclass
class SafetyIncident:
    """Record of a safety incident."""

    incident_id: str
    incident_type: IncidentType
    severity: IncidentSeverity
    description: str
    location_lat: float | None = None
    location_lon: float | None = None
    timestamp_ns: int = 0
    crew_involved: list[str] = field(default_factory=list)
    resolved_ns: int | None = None
    root_cause: str | None = None
    lessons_learned: str | None = None
    corrective_actions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate incident data."""
        if not self.incident_id or not isinstance(self.incident_id, str):
            raise ValueError("incident_id must be a non-empty string")
        if isinstance(self.incident_type, str):
            self.incident_type = IncidentType(self.incident_type)
        if isinstance(self.severity, str):
            self.severity = IncidentSeverity(self.severity)
        if not isinstance(self.description, str):
            raise ValueError("description must be a string")
        if not isinstance(self.crew_involved, list):
            raise ValueError("crew_involved must be a list")
        if not isinstance(self.corrective_actions, list):
            raise ValueError("corrective_actions must be a list")
        if self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be >= 0")
        if self.resolved_ns is not None and self.resolved_ns < 0:
            raise ValueError("resolved_ns must be >= 0 or None")

        # Set timestamp to now if not provided
        if self.timestamp_ns == 0:
            self.timestamp_ns = time.time_ns()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "incident_id": self.incident_id,
            "incident_type": self.incident_type.value,
            "severity": self.severity.value,
            "description": self.description,
            "location_lat": self.location_lat,
            "location_lon": self.location_lon,
            "timestamp_ns": self.timestamp_ns,
            "crew_involved": self.crew_involved,
            "resolved_ns": self.resolved_ns,
            "root_cause": self.root_cause,
            "lessons_learned": self.lessons_learned,
            "corrective_actions": self.corrective_actions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SafetyIncident":
        """Create SafetyIncident from dictionary."""
        return cls(
            incident_id=data["incident_id"],
            incident_type=IncidentType(data["incident_type"]),
            severity=IncidentSeverity(data["severity"]),
            description=data["description"],
            location_lat=data.get("location_lat"),
            location_lon=data.get("location_lon"),
            timestamp_ns=data.get("timestamp_ns", 0),
            crew_involved=data.get("crew_involved", []),
            resolved_ns=data.get("resolved_ns"),
            root_cause=data.get("root_cause"),
            lessons_learned=data.get("lessons_learned"),
            corrective_actions=data.get("corrective_actions", []),
        )


@dataclass
class EmergencyProtocol:
    """Emergency response protocol."""

    protocol_type: ProtocolType
    steps: list[str]
    contacts: list[dict[str, str]]  # [{"role": "Captain", "name": "John"}]
    equipment_required: list[EquipmentType | str] = field(default_factory=list)
    priority_contacts: list[dict[str, str]] = field(default_factory=list)  # Emergency contacts

    def __post_init__(self) -> None:
        """Validate protocol data."""
        if isinstance(self.protocol_type, str):
            self.protocol_type = ProtocolType(self.protocol_type)
        if not isinstance(self.steps, list):
            raise ValueError("steps must be a list")
        if not isinstance(self.contacts, list):
            raise ValueError("contacts must be a list")
        if not isinstance(self.priority_contacts, list):
            raise ValueError("priority_contacts must be a list")

        # Convert equipment strings to enums
        normalized_equipment = []
        for eq in self.equipment_required:
            if isinstance(eq, str):
                normalized_equipment.append(EquipmentType(eq))
            else:
                normalized_equipment.append(eq)
        self.equipment_required = normalized_equipment

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "protocol_type": self.protocol_type.value,
            "steps": self.steps,
            "contacts": self.contacts,
            "equipment_required": [eq.value if isinstance(eq, EquipmentType) else eq for eq in self.equipment_required],
            "priority_contacts": self.priority_contacts,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EmergencyProtocol":
        """Create EmergencyProtocol from dictionary."""
        return cls(
            protocol_type=ProtocolType(data["protocol_type"]),
            steps=data["steps"],
            contacts=data["contacts"],
            equipment_required=data.get("equipment_required", []),
            priority_contacts=data.get("priority_contacts", []),
        )


@dataclass
class TrainingRecord:
    """Training and certification record."""

    crew_id: str
    training_type: TrainingType
    completion_date_ns: int
    expiry_date_ns: int | None = None
    certification_id: str | None = None
    instructor: str | None = None
    training_provider: str | None = None
    score: float | None = None  # Training score if applicable
    notes: str | None = None

    def __post_init__(self) -> None:
        """Validate training data."""
        if not self.crew_id or not isinstance(self.crew_id, str):
            raise ValueError("crew_id must be a non-empty string")
        if isinstance(self.training_type, str):
            self.training_type = TrainingType(self.training_type)
        if self.completion_date_ns < 0:
            raise ValueError("completion_date_ns must be >= 0")
        if self.expiry_date_ns is not None and self.expiry_date_ns < 0:
            raise ValueError("expiry_date_ns must be >= 0 or None")
        if self.score is not None and not 0 <= self.score <= 100:
            raise ValueError("score must be between 0 and 100 or None")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "crew_id": self.crew_id,
            "training_type": self.training_type.value,
            "completion_date_ns": self.completion_date_ns,
            "expiry_date_ns": self.expiry_date_ns,
            "certification_id": self.certification_id,
            "instructor": self.instructor,
            "training_provider": self.training_provider,
            "score": self.score,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrainingRecord":
        """Create TrainingRecord from dictionary."""
        return cls(
            crew_id=data["crew_id"],
            training_type=TrainingType(data["training_type"]),
            completion_date_ns=data["completion_date_ns"],
            expiry_date_ns=data.get("expiry_date_ns"),
            certification_id=data.get("certification_id"),
            instructor=data.get("instructor"),
            training_provider=data.get("training_provider"),
            score=data.get("score"),
            notes=data.get("notes"),
        )


@dataclass
class SafetyDrill:
    """Safety drill record."""

    drill_type: DrillType
    scheduled_date_ns: int
    completed_date_ns: int | None = None
    participants: list[str] = field(default_factory=list)
    score: float | None = None  # Overall score 0-100
    deficiencies: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    evaluator: str | None = None
    notes: str | None = None
    response_time_seconds: float | None = None  # Time to complete drill

    def __post_init__(self) -> None:
        """Validate drill data."""
        if isinstance(self.drill_type, str):
            self.drill_type = DrillType(self.drill_type)
        if self.scheduled_date_ns < 0:
            raise ValueError("scheduled_date_ns must be >= 0")
        if self.completed_date_ns is not None and self.completed_date_ns < 0:
            raise ValueError("completed_date_ns must be >= 0 or None")
        if not isinstance(self.participants, list):
            raise ValueError("participants must be a list")
        if self.score is not None and not 0 <= self.score <= 100:
            raise ValueError("score must be between 0 and 100 or None")
        if not isinstance(self.deficiencies, list):
            raise ValueError("deficiencies must be a list")
        if not isinstance(self.strengths, list):
            raise ValueError("strengths must be a list")
        if self.response_time_seconds is not None and self.response_time_seconds < 0:
            raise ValueError("response_time_seconds must be >= 0 or None")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "drill_type": self.drill_type.value,
            "scheduled_date_ns": self.scheduled_date_ns,
            "completed_date_ns": self.completed_date_ns,
            "participants": self.participants,
            "score": self.score,
            "deficiencies": self.deficiencies,
            "strengths": self.strengths,
            "evaluator": self.evaluator,
            "notes": self.notes,
            "response_time_seconds": self.response_time_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SafetyDrill":
        """Create SafetyDrill from dictionary."""
        return cls(
            drill_type=DrillType(data["drill_type"]),
            scheduled_date_ns=data["scheduled_date_ns"],
            completed_date_ns=data.get("completed_date_ns"),
            participants=data.get("participants", []),
            score=data.get("score"),
            deficiencies=data.get("deficiencies", []),
            strengths=data.get("strengths", []),
            evaluator=data.get("evaluator"),
            notes=data.get("notes"),
            response_time_seconds=data.get("response_time_seconds"),
        )


@dataclass
class SafetyEquipment:
    """Safety equipment record."""

    equipment_id: str
    equipment_type: EquipmentType
    location: str
    last_inspected_ns: int = 0
    expiry_date_ns: int | None = None
    status: EquipmentStatus = EquipmentStatus.SERVICEABLE
    model: str | None = None
    serial_number: str | None = None
    inspection_notes: str | None = None

    def __post_init__(self) -> None:
        """Validate equipment data."""
        if not self.equipment_id or not isinstance(self.equipment_id, str):
            raise ValueError("equipment_id must be a non-empty string")
        if isinstance(self.equipment_type, str):
            self.equipment_type = EquipmentType(self.equipment_type)
        if not isinstance(self.location, str):
            raise ValueError("location must be a string")
        if self.last_inspected_ns < 0:
            raise ValueError("last_inspected_ns must be >= 0")
        if self.expiry_date_ns is not None and self.expiry_date_ns < 0:
            raise ValueError("expiry_date_ns must be >= 0 or None")
        if isinstance(self.status, str):
            self.status = EquipmentStatus(self.status)

        # Set inspection date to now if not provided
        if self.last_inspected_ns == 0:
            self.last_inspected_ns = time.time_ns()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "equipment_id": self.equipment_id,
            "equipment_type": self.equipment_type.value,
            "location": self.location,
            "last_inspected_ns": self.last_inspected_ns,
            "expiry_date_ns": self.expiry_date_ns,
            "status": self.status.value,
            "model": self.model,
            "serial_number": self.serial_number,
            "inspection_notes": self.inspection_notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SafetyEquipment":
        """Create SafetyEquipment from dictionary."""
        return cls(
            equipment_id=data["equipment_id"],
            equipment_type=EquipmentType(data["equipment_type"]),
            location=data["location"],
            last_inspected_ns=data.get("last_inspected_ns", 0),
            expiry_date_ns=data.get("expiry_date_ns"),
            status=EquipmentStatus(data.get("status", "SERVICEABLE")),
            model=data.get("model"),
            serial_number=data.get("serial_number"),
            inspection_notes=data.get("inspection_notes"),
        )


@dataclass
class PPERecord:
    """PPE (Personal Protective Equipment) issue record."""

    crew_id: str
    ppe_type: PPEType
    issue_date_ns: int = 0
    condition: PPECondition = PPECondition.GOOD
    size: str | None = None
    brand: str | None = None
    serial_number: str | None = None
    expiry_date_ns: int | None = None  # For items with finite lifespan
    inspection_required_ns: int | None = None  # Next inspection date

    def __post_init__(self) -> None:
        """Validate PPE data."""
        if not self.crew_id or not isinstance(self.crew_id, str):
            raise ValueError("crew_id must be a non-empty string")
        if isinstance(self.ppe_type, str):
            self.ppe_type = PPEType(self.ppe_type)
        if self.issue_date_ns < 0:
            raise ValueError("issue_date_ns must be >= 0")
        if isinstance(self.condition, str):
            self.condition = PPECondition(self.condition)
        if self.expiry_date_ns is not None and self.expiry_date_ns < 0:
            raise ValueError("expiry_date_ns must be >= 0 or None")
        if self.inspection_required_ns is not None and self.inspection_required_ns < 0:
            raise ValueError("inspection_required_ns must be >= 0 or None")

        # Set issue date to now if not provided
        if self.issue_date_ns == 0:
            self.issue_date_ns = time.time_ns()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "crew_id": self.crew_id,
            "ppe_type": self.ppe_type.value,
            "issue_date_ns": self.issue_date_ns,
            "condition": self.condition.value,
            "size": self.size,
            "brand": self.brand,
            "serial_number": self.serial_number,
            "expiry_date_ns": self.expiry_date_ns,
            "inspection_required_ns": self.inspection_required_ns,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PPERecord":
        """Create PPERecord from dictionary."""
        return cls(
            crew_id=data["crew_id"],
            ppe_type=PPEType(data["ppe_type"]),
            issue_date_ns=data.get("issue_date_ns", 0),
            condition=PPECondition(data.get("condition", "GOOD")),
            size=data.get("size"),
            brand=data.get("brand"),
            serial_number=data.get("serial_number"),
            expiry_date_ns=data.get("expiry_date_ns"),
            inspection_required_ns=data.get("inspection_required_ns"),
        )


# --------------------------------------------------------------------- #
# Crew Safety System
# --------------------------------------------------------------------- #


class CrewSafety:
    """Comprehensive crew safety management system.

    Tracks safety incidents, manages emergency protocols, monitors training
    certifications, schedules safety drills, tracks safety equipment, and
    manages PPE issuance.

    Example:
        >>> safety = CrewSafety("vessel_001")
        >>> safety.log_safety_incident("MOB", "CRITICAL", "Crew fell overboard", 59.5, -152.3)
        >>> safety.add_training_record("crew_001", "BASIC_SAFETY", completion_ns, expiry_ns)
        >>> alerts = safety.get_alerts()
    """

    def __init__(
        self,
        vessel_id: str,
        data_dir: str | Path = "crew_safety_data",
    ) -> None:
        """Initialize the crew safety system.

        Args:
            vessel_id: Vessel identifier
            data_dir: Directory for JSONL persistence files
        """
        if not vessel_id or not isinstance(vessel_id, str):
            raise ValueError("vessel_id must be a non-empty string")

        self.vessel_id = vessel_id
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # In-memory storage
        self._incidents: dict[str, SafetyIncident] = {}
        self._protocols: dict[str, EmergencyProtocol] = {}
        self._training: list[TrainingRecord] = []
        self._drills: list[SafetyDrill] = []
        self._equipment: dict[str, SafetyEquipment] = {}
        self._ppe: list[PPERecord] = []

        # Load existing data and set up default protocols
        self._load_data()
        self._setup_default_protocols()

        log.info("CrewSafety initialized for vessel %s", vessel_id)

    # ------------------------------------------------------------------ #
    # Incident Management
    # ------------------------------------------------------------------ #

    def log_safety_incident(
        self,
        incident_type: IncidentType | str,
        severity: IncidentSeverity | str,
        description: str,
        location_lat: float | None = None,
        location_lon: float | None = None,
        crew_involved: list[str] | None = None,
        timestamp_ns: int = 0,
        incident_id: str | None = None,
    ) -> SafetyIncident:
        """Log a safety incident.

        Args:
            incident_type: Type of incident
            severity: Incident severity level
            description: Human-readable description
            location_lat: Incident latitude
            location_lon: Incident longitude
            crew_involved: List of crew member IDs involved
            timestamp_ns: Incident timestamp (nanoseconds, 0 = now)
            incident_id: Optional incident ID (generated if not provided)

        Returns:
            The created SafetyIncident

        Raises:
            ValueError: If validation fails
        """
        if isinstance(incident_type, str):
            incident_type = IncidentType(incident_type)
        if isinstance(severity, str):
            severity = IncidentSeverity(severity)

        if incident_id is None:
            incident_id = str(uuid.uuid4())[:8]

        incident = SafetyIncident(
            incident_id=incident_id,
            incident_type=incident_type,
            severity=severity,
            description=description,
            location_lat=location_lat,
            location_lon=location_lon,
            timestamp_ns=timestamp_ns,
            crew_involved=crew_involved or [],
        )

        self._incidents[incident_id] = incident
        self._persist_incident(incident)

        # Log based on severity
        if severity == IncidentSeverity.CRITICAL:
            log.critical("CRITICAL safety incident %s: %s", incident_id, description)
        elif severity == IncidentSeverity.MAJOR:
            log.error("MAJOR safety incident %s: %s", incident_id, description)
        elif severity == IncidentSeverity.MODERATE:
            log.warning("MODERATE safety incident %s: %s", incident_id, description)
        else:
            log.info("MINOR safety incident %s: %s", incident_id, description)

        return incident

    def get_safety_incidents(
        self,
        incident_type: IncidentType | str | None = None,
        severity: IncidentSeverity | str | None = None,
        crew_id: str | None = None,
        start_time_ns: int | None = None,
        end_time_ns: int | None = None,
        resolved: bool | None = None,
    ) -> list[SafetyIncident]:
        """Get safety incidents with optional filters.

        Args:
            incident_type: Filter by incident type
            severity: Filter by severity
            crew_id: Filter by crew member involvement
            start_time_ns: Filter by timestamp >= this
            end_time_ns: Filter by timestamp <= this
            resolved: Filter by resolution status

        Returns:
            List of matching incidents
        """
        incidents = list(self._incidents.values())

        # Apply filters
        if incident_type is not None:
            if isinstance(incident_type, str):
                incident_type = IncidentType(incident_type)
            incidents = [i for i in incidents if i.incident_type == incident_type]

        if severity is not None:
            if isinstance(severity, str):
                severity = IncidentSeverity(severity)
            incidents = [i for i in incidents if i.severity == severity]

        if crew_id is not None:
            incidents = [i for i in incidents if crew_id in i.crew_involved]

        if start_time_ns is not None:
            incidents = [i for i in incidents if i.timestamp_ns >= start_time_ns]

        if end_time_ns is not None:
            incidents = [i for i in incidents if i.timestamp_ns <= end_time_ns]

        if resolved is not None:
            if resolved:
                incidents = [i for i in incidents if i.resolved_ns is not None]
            else:
                incidents = [i for i in incidents if i.resolved_ns is None]

        # Sort by timestamp (newest first)
        incidents.sort(key=lambda x: x.timestamp_ns, reverse=True)
        return incidents

    def resolve_incident(
        self,
        incident_id: str,
        root_cause: str | None = None,
        lessons_learned: str | None = None,
        corrective_actions: list[str] | None = None,
    ) -> SafetyIncident | None:
        """Resolve a safety incident.

        Args:
            incident_id: Incident ID to resolve
            root_cause: Root cause analysis
            lessons_learned: Lessons learned from incident
            corrective_actions: List of corrective actions

        Returns:
            The resolved incident, or None if not found
        """
        incident = self._incidents.get(incident_id)
        if not incident:
            log.warning("Attempted to resolve unknown incident: %s", incident_id)
            return None

        incident.resolved_ns = time.time_ns()
        incident.root_cause = root_cause
        incident.lessons_learned = lessons_learned
        incident.corrective_actions = corrective_actions or []

        self._persist_incident(incident)

        log.info("Resolved safety incident %s", incident_id)
        return incident

    def get_incident_statistics(self, days: int = 30) -> dict[str, Any]:
        """Get safety incident statistics.

        Args:
            days: Number of days to analyze (default 30)

        Returns:
            Dictionary with incident statistics
        """
        now_ns = time.time_ns()
        start_ns = now_ns - (days * 24 * 3600 * 1e9)

        recent_incidents = [i for i in self._incidents.values() if i.timestamp_ns >= start_ns]

        # Count by type
        type_counts: dict[str, int] = {}
        for incident in recent_incidents:
            itype = incident.incident_type.value
            type_counts[itype] = type_counts.get(itype, 0) + 1

        # Count by severity
        severity_counts: dict[str, int] = {}
        for incident in recent_incidents:
            sev = incident.severity.value
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        # Resolution rate
        resolved_count = sum(1 for i in recent_incidents if i.resolved_ns is not None)
        resolution_rate = resolved_count / len(recent_incidents) if recent_incidents else 0.0

        # Average resolution time
        resolution_times = []
        for incident in recent_incidents:
            if incident.resolved_ns is not None:
                resolution_hours = (incident.resolved_ns - incident.timestamp_ns) / 1e9 / 3600
                resolution_times.append(resolution_hours)

        avg_resolution_hours = sum(resolution_times) / len(resolution_times) if resolution_times else None

        return {
            "period_days": days,
            "total_incidents": len(recent_incidents),
            "incident_type_counts": type_counts,
            "incident_severity_counts": severity_counts,
            "resolved_count": resolved_count,
            "unresolved_count": len(recent_incidents) - resolved_count,
            "resolution_rate": round(resolution_rate, 3),
            "average_resolution_hours": round(avg_resolution_hours, 2) if avg_resolution_hours else None,
        }

    # ------------------------------------------------------------------ #
    # Emergency Protocols
    # ------------------------------------------------------------------ #

    def _setup_default_protocols(self) -> None:
        """Set up default emergency protocols if none exist."""
        if self._protocols:
            return  # Already have protocols

        # MOB Response Protocol
        mob_protocol = EmergencyProtocol(
            protocol_type=ProtocolType.MOB_RESPONSE,
            steps=[
                "1. Immediately mark MOB position on GPS/chart plotter",
                "2. Press MOB button on navigation equipment",
                "3. Sound alarm: 'MAN OVERBOARD - PORT/STARBOARD SIDE'",
                "4. Throw life ring, danbuoy, and MOB marker",
                "5. Assign visual spotter (keep MOB in sight)",
                "6. Initiate recovery maneuver (Williamson turn or Anderson turn)",
                "7. Call Mayday if situation warrants",
                "8. Prepare recovery equipment (life sling, rescue basket)",
                "9. Retrieve person from water",
                "10. Provide first aid and treat for hypothermia",
                "11. Report incident to vessel owner and authorities",
            ],
            contacts=[
                {"role": "Captain", "responsibility": "Overall coordination"},
                {"role": "Mate", "responsibility": "Visual spotting and navigation"},
                {"role": "Deckhand", "responsibility": "Equipment deployment"},
            ],
            equipment_required=[
                EquipmentType.LIFE_JACKET,
                EquipmentType.MOB_DEVICE,
                EquipmentType.LIFE_RAFT,
            ],
            priority_contacts=[
                {"type": "USCG", "contact": "VHF-FM Channel 16"},
                {"type": "Rescue Coordination Center", "contact": "+1 (907) 463-2000"},
            ],
        )

        # Fire Response Protocol
        fire_protocol = EmergencyProtocol(
            protocol_type=ProtocolType.FIRE_RESPONSE,
            steps=[
                "1. Sound general alarm and announce fire location",
                "2. Shut off fuel and ventilation to affected area",
                "3. Deploy fire boundaries (close doors, hatches)",
                "4. Attack fire with appropriate extinguishers",
                "5. If fire spreads or intensifies - prepare to abandon ship",
                "6. Call Mayday if vessel is endangered",
                "7. Continuously monitor fire boundaries",
                "8. Maintain firefighting until fire is extinguished",
                "9. Ventilate area after fire is out",
                "10. Assess damage and repair if safe to do so",
            ],
            contacts=[
                {"role": "Captain", "responsibility": "Coordination and communications"},
                {"role": "Engineer", "responsibility": "Fuel and power systems"},
                {"role": "Deckhand", "responsibility": "Firefighting equipment"},
            ],
            equipment_required=[
                EquipmentType.FIRE_EXTINGUISHER,
                EquipmentType.FIRST_AID_KIT,
            ],
            priority_contacts=[
                {"type": "USCG", "contact": "VHF-FM Channel 16"},
                {"type": "Fire Department", "contact": "911 (if in range)"},
            ],
        )

        # Abandon Ship Protocol
        abandon_protocol = EmergencyProtocol(
            protocol_type=ProtocolType.ABANDON_SHIP,
            steps=[
                "1. Sound abandon ship alarm (6 short blasts + 1 long)",
                "2. Activate EPIRB",
                "3. Broadcast Mayday on VHF-FM Channel 16",
                "4. Don immersion suits and PFDs",
                "5. Grab survival kit and EPIRB backup",
                "6. Launch liferafts leeward of vessel",
                "7. Board liferafts and tether together",
                "8. Deploy sea anchor and maintain visual contact",
                "9. Activate secondary EPIRB if primary fails",
                "10. Use signaling devices to attract attention",
                "11. Ration water and food",
                "12. Maintain morale and survival procedures",
            ],
            contacts=[
                {"role": "Captain", "responsibility": "Order abandon ship and coordinate"},
                {"role": "All Crew", "responsibility": "Follow survival procedures"},
            ],
            equipment_required=[
                EquipmentType.IMMERSION_SUIT,
                EquipmentType.LIFE_JACKET,
                EquipmentType.LIFE_RAFT,
                EquipmentType.EPIRB,
            ],
            priority_contacts=[
                {"type": "USCG", "contact": "VHF-FM Channel 16"},
                {"type": "RCC", "contact": "+1 (907) 463-2000"},
            ],
        )

        # Medical Emergency Protocol
        medical_protocol = EmergencyProtocol(
            protocol_type=ProtocolType.MEDICAL_EMERGENCY,
            steps=[
                "1. Assess scene safety for responders",
                "2. Assess patient condition (ABC: Airway, Breathing, Circulation)",
                "3. Call for medical advice (if available)",
                "4. Administer first aid as trained",
                "5. Use vessel medical kit supplies",
                "6. Monitor patient condition continuously",
                "7. Consider medevac if condition is serious",
                "8. Contact rescue coordination center for assistance",
                "9. Prepare landing area for helicopter if medevac",
                "10. Document all medical interventions provided",
            ],
            contacts=[
                {"role": "Captain", "responsibility": "Coordination and communications"},
                {"role": "Crew with First Aid", "responsibility": "Patient care"},
            ],
            equipment_required=[
                EquipmentType.FIRST_AID_KIT,
                EquipmentType.SAT_PHONE,
            ],
            priority_contacts=[
                {"type": "USCG", "contact": "VHF-FM Channel 16"},
                {"type": "Medical Advice", "contact": "Telemedical service"},
                {"type": "Medevac", "contact": "Request through USCG"},
            ],
        )

        # Mayday Protocol
        mayday_protocol = EmergencyProtocol(
            protocol_type=ProtocolType.MAYDAY,
            steps=[
                "1. Assess situation - is immediate assistance required?",
                "2. Select VHF-FM Channel 16",
                "3. Press distress button on DSC radio",
                "4. Make voice Mayday call:",
                "   - MAYDAY-MAYDAY-MAYDAY",
                "   - Vessel name and call sign",
                "   - Position (lat/lon or bearing/distance from landmark)",
                "   - Nature of distress",
                "   - Assistance required",
                "   - Number of persons on board",
                "   - Other relevant information",
                "5. Repeat Mayday call at intervals until acknowledged",
                "6. Switch to designated working channel when directed",
                "7. Provide updates as situation evolves",
                "8. Cancel Mayday when no longer needed",
            ],
            contacts=[
                {"role": "Captain", "responsibility": "Make Mayday call"},
                {"role": "All Crew", "responsibility": "Prepare for emergency response"},
            ],
            equipment_required=[
                EquipmentType.EPIRB,
                EquipmentType.SAT_PHONE,
            ],
            priority_contacts=[
                {"type": "USCG", "contact": "VHF-FM Channel 16"},
                {"type": "RCC", "contact": "Rescue Coordination Center"},
            ],
        )

        # Store protocols
        self._protocols["MOB_RESPONSE"] = mob_protocol
        self._protocols["FIRE_RESPONSE"] = fire_protocol
        self._protocols["ABANDON_SHIP"] = abandon_protocol
        self._protocols["MEDICAL_EMERGENCY"] = medical_protocol
        self._protocols["MAYDAY"] = mayday_protocol

        # Persist default protocols
        self._persist_protocols()

    def activate_emergency_protocol(
        self, protocol_type: ProtocolType | str
    ) -> EmergencyProtocol:
        """Activate an emergency protocol.

        Args:
            protocol_type: Type of protocol to activate

        Returns:
            The activated protocol

        Raises:
            ValueError: If protocol type not found
        """
        if isinstance(protocol_type, str):
            protocol_type = ProtocolType(protocol_type)

        protocol_key = protocol_type.value
        protocol = self._protocols.get(protocol_key)

        if not protocol:
            raise ValueError(f"Protocol not found: {protocol_type}")

        log.critical("EMERGENCY PROTOCOL ACTIVATED: %s", protocol_type.value)
        return protocol

    def get_emergency_protocol(
        self, protocol_type: ProtocolType | str
    ) -> EmergencyProtocol | None:
        """Get an emergency protocol by type.

        Args:
            protocol_type: Type of protocol

        Returns:
            The protocol, or None if not found
        """
        if isinstance(protocol_type, str):
            protocol_type = ProtocolType(protocol_type)

        return self._protocols.get(protocol_type.value)

    # ------------------------------------------------------------------ #
    # Training Management
    # ------------------------------------------------------------------ #

    def add_training_record(
        self,
        crew_id: str,
        training_type: TrainingType | str,
        completion_date_ns: int,
        expiry_date_ns: int | None = None,
        certification_id: str | None = None,
        instructor: str | None = None,
        training_provider: str | None = None,
        score: float | None = None,
        notes: str | None = None,
    ) -> TrainingRecord:
        """Add a training record.

        Args:
            crew_id: Crew member ID
            training_type: Type of training
            completion_date_ns: Completion timestamp (nanoseconds)
            expiry_date_ns: Expiry timestamp (nanoseconds)
            certification_id: Certification identifier
            instructor: Instructor name
            training_provider: Training provider name
            score: Training score (0-100)
            notes: Additional notes

        Returns:
            The created TrainingRecord
        """
        if isinstance(training_type, str):
            training_type = TrainingType(training_type)

        record = TrainingRecord(
            crew_id=crew_id,
            training_type=training_type,
            completion_date_ns=completion_date_ns,
            expiry_date_ns=expiry_date_ns,
            certification_id=certification_id,
            instructor=instructor,
            training_provider=training_provider,
            score=score,
            notes=notes,
        )

        self._training.append(record)
        self._persist_training(record)

        log.info("Added training record for crew %s: %s", crew_id, training_type.value)
        return record

    def get_crew_training(
        self,
        crew_id: str,
        training_type: TrainingType | str | None = None,
        include_expired: bool = False,
    ) -> list[TrainingRecord]:
        """Get training records for a crew member.

        Args:
            crew_id: Crew member ID
            training_type: Filter by training type
            include_expired: Include expired certifications

        Returns:
            List of training records
        """
        records = [r for r in self._training if r.crew_id == crew_id]

        if training_type is not None:
            if isinstance(training_type, str):
                training_type = TrainingType(training_type)
            records = [r for r in records if r.training_type == training_type]

        if not include_expired:
            now_ns = time.time_ns()
            records = [r for r in records if r.expiry_date_ns is None or r.expiry_date_ns > now_ns]

        # Sort by completion date (newest first)
        records.sort(key=lambda x: x.completion_date_ns, reverse=True)
        return records

    def check_training_expiry(self, days_ahead: int = 30) -> list[dict[str, Any]]:
        """Check for training expiring soon.

        Args:
            days_ahead: Number of days to look ahead (default 30)

        Returns:
            List of expiring training records with crew info
        """
        now_ns = time.time_ns()
        threshold_ns = now_ns + (days_ahead * 24 * 3600 * 1e9)

        expiring = []
        for record in self._training:
            if record.expiry_date_ns and record.expiry_date_ns <= threshold_ns:
                days_until_expiry = (record.expiry_date_ns - now_ns) / 1e9 / 24 / 3600
                expiring.append({
                    "crew_id": record.crew_id,
                    "training_type": record.training_type.value,
                    "certification_id": record.certification_id,
                    "expiry_date_ns": record.expiry_date_ns,
                    "days_until_expiry": round(days_until_expiry, 1),
                    "is_expired": record.expiry_date_ns < now_ns,
                })

        # Sort by days until expiry (soonest first)
        expiring.sort(key=lambda x: x["days_until_expiry"])
        return expiring

    # ------------------------------------------------------------------ #
    # Drill Management
    # ------------------------------------------------------------------ #

    def log_safety_drill(
        self,
        drill_type: DrillType | str,
        scheduled_date_ns: int,
        participants: list[str],
        score: float | None = None,
        deficiencies: list[str] | None = None,
        strengths: list[str] | None = None,
        evaluator: str | None = None,
        notes: str | None = None,
        response_time_seconds: float | None = None,
    ) -> SafetyDrill:
        """Log a safety drill.

        Args:
            drill_type: Type of drill
            scheduled_date_ns: Scheduled date (nanoseconds)
            participants: List of participant crew IDs
            score: Overall score (0-100)
            deficiencies: List of deficiencies found
            strengths: List of strengths observed
            evaluator: Evaluator name
            notes: Additional notes
            response_time_seconds: Time to complete drill

        Returns:
            The created SafetyDrill
        """
        if isinstance(drill_type, str):
            drill_type = DrillType(drill_type)

        drill = SafetyDrill(
            drill_type=drill_type,
            scheduled_date_ns=scheduled_date_ns,
            completed_date_ns=time.time_ns(),
            participants=participants,
            score=score,
            deficiencies=deficiencies or [],
            strengths=strengths or [],
            evaluator=evaluator,
            notes=notes,
            response_time_seconds=response_time_seconds,
        )

        self._drills.append(drill)
        self._persist_drill(drill)

        log.info("Logged safety drill: %s with score %.1f", drill_type.value, score or 0)
        return drill

    def get_drill_history(
        self,
        drill_type: DrillType | str | None = None,
        start_time_ns: int | None = None,
        end_time_ns: int | None = None,
        limit: int = 100,
    ) -> list[SafetyDrill]:
        """Get safety drill history.

        Args:
            drill_type: Filter by drill type
            start_time_ns: Filter by scheduled date >= this
            end_time_ns: Filter by scheduled date <= this
            limit: Maximum number of records

        Returns:
            List of drill records
        """
        drills = self._drills

        if drill_type is not None:
            if isinstance(drill_type, str):
                drill_type = DrillType(drill_type)
            drills = [d for d in drills if d.drill_type == drill_type]

        if start_time_ns is not None:
            drills = [d for d in drills if d.scheduled_date_ns >= start_time_ns]

        if end_time_ns is not None:
            drills = [d for d in drills if d.scheduled_date_ns <= end_time_ns]

        # Sort by scheduled date (newest first) and limit
        drills.sort(key=lambda x: x.scheduled_date_ns, reverse=True)
        return drills[:limit]

    def get_overdue_drills(self, days_threshold: int = 90) -> list[dict[str, Any]]:
        """Get drills that haven't been conducted recently.

        Args:
            days_threshold: Days without drill to consider overdue (default 90)

        Returns:
            List of overdue drill types with days since last drill
        """
        now_ns = time.time_ns()
        threshold_ns = now_ns - (days_threshold * 24 * 3600 * 1e9)

        last_drill_by_type: dict[str, int] = {}
        for drill in self._drills:
            dtype = drill.drill_type.value
            if drill.completed_date_ns:
                if dtype not in last_drill_by_type or drill.completed_date_ns > last_drill_by_type[dtype]:
                    last_drill_by_type[dtype] = drill.completed_date_ns

        overdue = []
        for drill_type in DrillType:
            dtype = drill_type.value
            last_drill_ns = last_drill_by_type.get(dtype)

            if last_drill_ns is None:
                # Never conducted
                days_since = 999  # Considered overdue
            else:
                days_since = (now_ns - last_drill_ns) / 1e9 / 24 / 3600

            if last_drill_ns is None or last_drill_ns < threshold_ns:
                overdue.append({
                    "drill_type": dtype,
                    "last_conducted_ns": last_drill_ns,
                    "days_since_last_drill": round(days_since, 1),
                    "threshold_days": days_threshold,
                    "is_overdue": True,
                })

        overdue.sort(key=lambda x: x["days_since_last_drill"], reverse=True)
        return overdue

    # ------------------------------------------------------------------ #
    # Equipment Management
    # ------------------------------------------------------------------ #

    def add_safety_equipment(
        self,
        equipment_id: str,
        equipment_type: EquipmentType | str,
        location: str,
        expiry_date_ns: int | None = None,
        model: str | None = None,
        serial_number: str | None = None,
    ) -> SafetyEquipment:
        """Add safety equipment.

        Args:
            equipment_id: Equipment identifier
            equipment_type: Type of equipment
            location: Equipment location on vessel
            expiry_date_ns: Expiry timestamp (nanoseconds)
            model: Equipment model
            serial_number: Serial number

        Returns:
            The created SafetyEquipment
        """
        if isinstance(equipment_type, str):
            equipment_type = EquipmentType(equipment_type)

        equipment = SafetyEquipment(
            equipment_id=equipment_id,
            equipment_type=equipment_type,
            location=location,
            expiry_date_ns=expiry_date_ns,
            model=model,
            serial_number=serial_number,
        )

        self._equipment[equipment_id] = equipment
        self._persist_equipment(equipment)

        log.info("Added safety equipment: %s (%s)", equipment_id, equipment_type.value)
        return equipment

    def get_safety_equipment(
        self,
        equipment_type: EquipmentType | str | None = None,
        status: EquipmentStatus | str | None = None,
    ) -> list[SafetyEquipment]:
        """Get safety equipment with optional filters.

        Args:
            equipment_type: Filter by equipment type
            status: Filter by status

        Returns:
            List of matching equipment
        """
        equipment = list(self._equipment.values())

        if equipment_type is not None:
            if isinstance(equipment_type, str):
                equipment_type = EquipmentType(equipment_type)
            equipment = [e for e in equipment if e.equipment_type == equipment_type]

        if status is not None:
            if isinstance(status, str):
                status = EquipmentStatus(status)
            equipment = [e for e in equipment if e.status == status]

        return equipment

    def inspect_equipment(
        self,
        equipment_id: str,
        status: EquipmentStatus | str,
        notes: str | None = None,
    ) -> SafetyEquipment | None:
        """Inspect and update safety equipment status.

        Args:
            equipment_id: Equipment ID
            status: New status
            notes: Inspection notes

        Returns:
            The updated equipment, or None if not found
        """
        equipment = self._equipment.get(equipment_id)
        if not equipment:
            log.warning("Equipment not found: %s", equipment_id)
            return None

        if isinstance(status, str):
            status = EquipmentStatus(status)

        equipment.status = status
        equipment.last_inspected_ns = time.time_ns()
        equipment.inspection_notes = notes

        self._persist_equipment(equipment)

        log.info("Inspected equipment %s: status=%s", equipment_id, status.value)
        return equipment

    def check_equipment_expiry(self, days_ahead: int = 30) -> list[dict[str, Any]]:
        """Check for equipment expiring soon.

        Args:
            days_ahead: Number of days to look ahead (default 30)

        Returns:
            List of expiring equipment
        """
        now_ns = time.time_ns()
        threshold_ns = now_ns + (days_ahead * 24 * 3600 * 1e9)

        expiring = []
        for equipment in self._equipment.values():
            if equipment.expiry_date_ns and equipment.expiry_date_ns <= threshold_ns:
                days_until_expiry = (equipment.expiry_date_ns - now_ns) / 1e9 / 24 / 3600
                expiring.append({
                    "equipment_id": equipment.equipment_id,
                    "equipment_type": equipment.equipment_type.value,
                    "location": equipment.location,
                    "expiry_date_ns": equipment.expiry_date_ns,
                    "days_until_expiry": round(days_until_expiry, 1),
                    "is_expired": equipment.expiry_date_ns < now_ns,
                    "status": equipment.status.value,
                })

        # Sort by days until expiry (soonest first)
        expiring.sort(key=lambda x: x["days_until_expiry"])
        return expiring

    # ------------------------------------------------------------------ #
    # PPE Management
    # ------------------------------------------------------------------ #

    def issue_ppe(
        self,
        crew_id: str,
        ppe_type: PPEType | str,
        size: str | None = None,
        brand: str | None = None,
        serial_number: str | None = None,
        expiry_date_ns: int | None = None,
        inspection_required_ns: int | None = None,
    ) -> PPERecord:
        """Issue PPE to a crew member.

        Args:
            crew_id: Crew member ID
            ppe_type: Type of PPE
            size: PPE size
            brand: PPE brand
            serial_number: Serial number
            expiry_date_ns: Expiry timestamp (nanoseconds)
            inspection_required_ns: Next inspection timestamp (nanoseconds)

        Returns:
            The created PPERecord
        """
        if isinstance(ppe_type, str):
            ppe_type = PPEType(ppe_type)

        record = PPERecord(
            crew_id=crew_id,
            ppe_type=ppe_type,
            size=size,
            brand=brand,
            serial_number=serial_number,
            expiry_date_ns=expiry_date_ns,
            inspection_required_ns=inspection_required_ns,
        )

        self._ppe.append(record)
        self._persist_ppe(record)

        log.info("Issued PPE to crew %s: %s", crew_id, ppe_type.value)
        return record

    def get_crew_ppe(
        self,
        crew_id: str,
        ppe_type: PPEType | str | None = None,
    ) -> list[PPERecord]:
        """Get PPE records for a crew member.

        Args:
            crew_id: Crew member ID
            ppe_type: Filter by PPE type

        Returns:
            List of PPE records
        """
        records = [r for r in self._ppe if r.crew_id == crew_id]

        if ppe_type is not None:
            if isinstance(ppe_type, str):
                ppe_type = PPEType(ppe_type)
            records = [r for r in records if r.ppe_type == ppe_type]

        # Sort by issue date (newest first)
        records.sort(key=lambda x: x.issue_date_ns, reverse=True)
        return records

    # ------------------------------------------------------------------ #
    # Summary and Alerts
    # ------------------------------------------------------------------ #

    def get_safety_summary(self, days: int = 30) -> dict[str, Any]:
        """Get comprehensive safety summary.

        Args:
            days: Number of days to analyze (default 30)

        Returns:
            Dictionary with safety summary data
        """
        incident_stats = self.get_incident_statistics(days)

        # Training status
        now_ns = time.time_ns()
        training_expiry = self.check_training_expiry(30)
        valid_training = [t for t in self._training if t.expiry_date_ns is None or t.expiry_date_ns > now_ns]

        # Equipment status
        equipment_by_status: dict[str, int] = {}
        for equipment in self._equipment.values():
            status = equipment.status.value
            equipment_by_status[status] = equipment_by_status.get(status, 0) + 1

        # Drill status
        overdue_drills = self.get_overdue_drills(90)
        recent_drills = [d for d in self._drills if d.completed_date_ns and d.completed_date_ns >= now_ns - (days * 24 * 3600 * 1e9)]

        return {
            "period_days": days,
            "incident_statistics": incident_stats,
            "training": {
                "total_records": len(self._training),
                "valid_certifications": len(valid_training),
                "expiring_soon": len(training_expiry),
                "expiring_details": training_expiry[:10],  # Top 10
            },
            "equipment": {
                "total_items": len(self._equipment),
                "by_status": equipment_by_status,
                "needs_inspection": equipment_by_status.get("NEEDS_INSPECTION", 0),
                "unserviceable": equipment_by_status.get("UNSERVICEABLE", 0),
                "expired": equipment_by_status.get("EXPIRED", 0),
            },
            "drills": {
                "total_conducted": len(recent_drills),
                "overdue_count": len(overdue_drills),
                "overdue_details": overdue_drills,
                "average_score": round(sum(d.score or 0 for d in recent_drills) / len(recent_drills), 2) if recent_drills else None,
            },
            "ppe": {
                "total_issued": len(self._ppe),
            },
        }

    def get_alerts(self) -> list[dict[str, Any]]:
        """Generate safety alerts.

        Returns:
            List of alert dictionaries
        """
        alerts = []
        now_ns = time.time_ns()

        # Training expiry alerts
        expiring_training = self.check_training_expiry(30)
        for record in expiring_training:
            if record["is_expired"]:
                alerts.append({
                    "severity": "critical",
                    "code": "TRAINING_EXPIRED",
                    "message": f"Training expired for crew {record['crew_id']}: {record['training_type']}",
                    "data": record,
                })
            elif record["days_until_expiry"] <= 7:
                alerts.append({
                    "severity": "high",
                    "code": "TRAINING_EXPIRING_SOON",
                    "message": f"Training expires in {record['days_until_expiry']:.0f} days for crew {record['crew_id']}: {record['training_type']}",
                    "data": record,
                })
            else:
                alerts.append({
                    "severity": "warning",
                    "code": "TRAINING_EXPIRING",
                    "message": f"Training expires in {record['days_until_expiry']:.0f} days for crew {record['crew_id']}: {record['training_type']}",
                    "data": record,
                })

        # Equipment expiry alerts
        expiring_equipment = self.check_equipment_expiry(30)
        for record in expiring_equipment:
            if record["is_expired"]:
                alerts.append({
                    "severity": "critical",
                    "code": "EQUIPMENT_EXPIRED",
                    "message": f"Equipment expired: {record['equipment_id']} ({record['equipment_type']})",
                    "data": record,
                })
            elif record["days_until_expiry"] <= 7:
                alerts.append({
                    "severity": "high",
                    "code": "EQUIPMENT_EXPIRING_SOON",
                    "message": f"Equipment expires in {record['days_until_expiry']:.0f} days: {record['equipment_id']}",
                    "data": record,
                })
            else:
                alerts.append({
                    "severity": "warning",
                    "code": "EQUIPMENT_EXPIRING",
                    "message": f"Equipment expires in {record['days_until_expiry']:.0f} days: {record['equipment_id']}",
                    "data": record,
                })

        # Overdue drill alerts
        overdue_drills = self.get_overdue_drills(90)
        for drill in overdue_drills:
            alerts.append({
                "severity": "high",
                "code": "DRILL_OVERDUE",
                "message": f"Drill overdue: {drill['drill_type']} (last done {drill['days_since_last_drill']:.0f} days ago)",
                "data": drill,
            })

        # Unresolved incident alerts
        unresolved_incidents = [i for i in self._incidents.values() if i.resolved_ns is None]
        for incident in unresolved_incidents:
            if incident.severity == IncidentSeverity.CRITICAL:
                alerts.append({
                    "severity": "critical",
                    "code": "INCIDENT_UNRESOLVED_CRITICAL",
                    "message": f"Critical incident unresolved: {incident.incident_id} - {incident.description}",
                    "data": {"incident_id": incident.incident_id, "type": incident.incident_type.value},
                })
            elif incident.severity == IncidentSeverity.MAJOR:
                alerts.append({
                    "severity": "high",
                    "code": "INCIDENT_UNRESOLVED_MAJOR",
                    "message": f"Major incident unresolved: {incident.incident_id} - {incident.description}",
                    "data": {"incident_id": incident.incident_id, "type": incident.incident_type.value},
                })

        # Equipment status alerts
        equipment_issues = self.get_safety_equipment(status="UNSERVICEABLE")
        for equipment in equipment_issues:
            alerts.append({
                "severity": "high",
                "code": "EQUIPMENT_UNSERVICEABLE",
                "message": f"Equipment unserviceable: {equipment.equipment_id} ({equipment.equipment_type.value})",
                "data": {"equipment_id": equipment.equipment_id, "type": equipment.equipment_type.value, "location": equipment.location},
            })

        return alerts

    def get_watcher_frame(self) -> dict[str, Any]:
        """Build a watcher frame for safety monitoring.

        Returns a dict with safety status, alerts, and metrics for
        watcher rule evaluation.
        """
        now_ns = time.time_ns()

        # Count incidents by severity
        incident_counts: dict[str, int] = {}
        for incident in self._incidents.values():
            sev = incident.severity.value
            incident_counts[sev] = incident_counts.get(sev, 0) + 1

        # Count equipment issues
        equipment_issues = len(self.get_safety_equipment(status="UNSERVICEABLE"))

        # Get alert count
        alerts = self.get_alerts()

        return {
            "timestamp_ns": now_ns,
            "total_incidents": len(self._incidents),
            "incident_severity_counts": incident_counts,
            "unresolved_incidents": len([i for i in self._incidents.values() if i.resolved_ns is None]),
            "equipment_issues": equipment_issues,
            "total_equipment": len(self._equipment),
            "total_training_records": len(self._training),
            "total_drills": len(self._drills),
            "total_ppe_issued": len(self._ppe),
            "active_alerts": len(alerts),
            "critical_alerts": len([a for a in alerts if a["severity"] == "critical"]),
        }

    def to_dict(self) -> dict[str, Any]:
        """Create a comprehensive snapshot of the safety system state.

        Returns:
            Dict with all safety data
        """
        return {
            "vessel_id": self.vessel_id,
            "timestamp_ns": time.time_ns(),
            "incidents": {iid: inc.to_dict() for iid, inc in self._incidents.items()},
            "protocols": {ptype: proto.to_dict() for ptype, proto in self._protocols.items()},
            "training": [t.to_dict() for t in self._training],
            "drills": [d.to_dict() for d in self._drills],
            "equipment": {eid: eq.to_dict() for eid, eq in self._equipment.items()},
            "ppe": [p.to_dict() for p in self._ppe],
            "watcher_frame": self.get_watcher_frame(),
            "alerts": self.get_alerts(),
        }

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _persist_incident(self, incident: SafetyIncident) -> None:
        """Append incident to JSONL file."""
        try:
            path = self.data_dir / "incidents.jsonl"
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(incident.to_dict()) + "\n")
        except (OSError, TypeError) as exc:
            log.warning("Failed to persist incident record: %s", exc)

    def _persist_protocols(self) -> None:
        """Write all protocols to JSONL file."""
        try:
            path = self.data_dir / "protocols.jsonl"
            with open(path, "w", encoding="utf-8") as f:
                for protocol in self._protocols.values():
                    f.write(json.dumps(protocol.to_dict()) + "\n")
        except (OSError, TypeError) as exc:
            log.warning("Failed to persist protocols: %s", exc)

    def _persist_training(self, record: TrainingRecord) -> None:
        """Append training record to JSONL file."""
        try:
            path = self.data_dir / "training.jsonl"
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict()) + "\n")
        except (OSError, TypeError) as exc:
            log.warning("Failed to persist training record: %s", exc)

    def _persist_drill(self, drill: SafetyDrill) -> None:
        """Append drill record to JSONL file."""
        try:
            path = self.data_dir / "drills.jsonl"
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(drill.to_dict()) + "\n")
        except (OSError, TypeError) as exc:
            log.warning("Failed to persist drill record: %s", exc)

    def _persist_equipment(self, equipment: SafetyEquipment) -> None:
        """Append equipment to JSONL file."""
        try:
            path = self.data_dir / "equipment.jsonl"
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(equipment.to_dict()) + "\n")
        except (OSError, TypeError) as exc:
            log.warning("Failed to persist equipment record: %s", exc)

    def _persist_ppe(self, record: PPERecord) -> None:
        """Append PPE record to JSONL file."""
        try:
            path = self.data_dir / "ppe.jsonl"
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict()) + "\n")
        except (OSError, TypeError) as exc:
            log.warning("Failed to persist PPE record: %s", exc)

    def _load_data(self) -> None:
        """Load all data from JSONL files."""
        # Load incidents
        incidents_path = self.data_dir / "incidents.jsonl"
        if incidents_path.exists():
            with open(incidents_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            incident = SafetyIncident.from_dict(data)
                            self._incidents[incident.incident_id] = incident
                        except (json.JSONDecodeError, KeyError, ValueError) as exc:
                            log.warning("Failed to load incident record: %s", exc)

        # Load protocols
        protocols_path = self.data_dir / "protocols.jsonl"
        if protocols_path.exists():
            with open(protocols_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            protocol = EmergencyProtocol.from_dict(data)
                            self._protocols[protocol.protocol_type.value] = protocol
                        except (json.JSONDecodeError, KeyError, ValueError) as exc:
                            log.warning("Failed to load protocol: %s", exc)

        # Load training
        training_path = self.data_dir / "training.jsonl"
        if training_path.exists():
            with open(training_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            record = TrainingRecord.from_dict(data)
                            self._training.append(record)
                        except (json.JSONDecodeError, KeyError, ValueError) as exc:
                            log.warning("Failed to load training record: %s", exc)

        # Load drills
        drills_path = self.data_dir / "drills.jsonl"
        if drills_path.exists():
            with open(drills_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            drill = SafetyDrill.from_dict(data)
                            self._drills.append(drill)
                        except (json.JSONDecodeError, KeyError, ValueError) as exc:
                            log.warning("Failed to load drill record: %s", exc)

        # Load equipment
        equipment_path = self.data_dir / "equipment.jsonl"
        if equipment_path.exists():
            with open(equipment_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            equipment = SafetyEquipment.from_dict(data)
                            self._equipment[equipment.equipment_id] = equipment
                        except (json.JSONDecodeError, KeyError, ValueError) as exc:
                            log.warning("Failed to load equipment record: %s", exc)

        # Load PPE
        ppe_path = self.data_dir / "ppe.jsonl"
        if ppe_path.exists():
            with open(ppe_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            record = PPERecord.from_dict(data)
                            self._ppe.append(record)
                        except (json.JSONDecodeError, KeyError, ValueError) as exc:
                            log.warning("Failed to load PPE record: %s", exc)

        log.info(
            "Loaded safety data: %d incidents, %d protocols, %d training records, %d drills, %d equipment, %d PPE records",
            len(self._incidents),
            len(self._protocols),
            len(self._training),
            len(self._drills),
            len(self._equipment),
            len(self._ppe),
        )


# Exports
__all__ = [
    "CrewSafety",
    "SafetyIncident",
    "EmergencyProtocol",
    "TrainingRecord",
    "SafetyDrill",
    "SafetyEquipment",
    "PPERecord",
    "IncidentType",
    "IncidentSeverity",
    "ProtocolType",
    "TrainingType",
    "DrillType",
    "EquipmentType",
    "EquipmentStatus",
    "PPEType",
    "PPECondition",
]
