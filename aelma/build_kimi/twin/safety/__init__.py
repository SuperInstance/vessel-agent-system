"""Crew safety system for the AELMA twin.

This module provides comprehensive crew safety management including:
- Safety incident tracking and analysis
- Emergency response protocols
- Training and certification management
- Safety drill scheduling and scoring
- Safety equipment tracking
- PPE (Personal Protective Equipment) management
"""

from .crew_safety import (
    CrewSafety,
    SafetyIncident,
    EmergencyProtocol,
    TrainingRecord,
    SafetyDrill,
    SafetyEquipment,
    PPERecord,
    IncidentType,
    IncidentSeverity,
    ProtocolType,
    TrainingType,
    DrillType,
    EquipmentType,
    EquipmentStatus,
    PPEType,
    PPECondition,
)

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
