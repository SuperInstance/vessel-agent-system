"""Equipment monitoring and maintenance system for the AELMA twin.

Tracks vessel equipment status, maintenance schedules, failure events,
and provides predictive maintenance analytics.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

log = logging.getLogger("aelma.equipment")


# --------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------- #


class EquipmentType(Enum):
    """Types of vessel equipment."""

    ENGINE = "ENGINE"
    GENERATOR = "GENERATOR"
    PUMP = "PUMP"
    WINCH = "WINCH"
    CRANE = "CRANE"
    NET_SOUNDING = "NET_SOUNDING"
    NAVIGATION = "NAVIGATION"
    COMMUNICATION = "COMMUNICATION"
    SAFETY = "SAFETY"
    FISHING_GEAR = "FISHING_GEAR"


class EquipmentStatus(Enum):
    """Operational status of equipment."""

    OPERATIONAL = "OPERATIONAL"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    MAINTENANCE_REQUIRED = "MAINTENANCE_REQUIRED"
    OFFLINE = "OFFLINE"


class MaintenanceType(Enum):
    """Types of maintenance activities."""

    ROUTINE = "ROUTINE"
    PREVENTIVE = "PREVENTIVE"
    CORRECTIVE = "CORRECTIVE"
    EMERGENCY = "EMERGENCY"
    UPGRADE = "UPGRADE"
    INSPECTION = "INSPECTION"


class FailureType(Enum):
    """Types of equipment failures."""

    MECHANICAL = "MECHANICAL"
    ELECTRICAL = "ELECTRICAL"
    HYDRAULIC = "HYDRAULIC"
    SOFTWARE = "SOFTWARE"
    CORROSION = "CORROSION"
    WEAR = "WEAR"
    ACCIDENT = "ACCIDENT"


class Severity(Enum):
    """Severity levels for failures and alerts."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# --------------------------------------------------------------------- #
# Dataclasses
# --------------------------------------------------------------------- #


@dataclass
class Equipment:
    """Vessel equipment record."""

    equipment_id: str
    name: str
    type: EquipmentType
    location: str
    status: EquipmentStatus = EquipmentStatus.OPERATIONAL
    install_date_ns: int = 0
    last_maintenance_ns: int | None = None

    def __post_init__(self) -> None:
        """Validate equipment data."""
        if not self.equipment_id or not isinstance(self.equipment_id, str):
            raise ValueError("equipment_id must be a non-empty string")
        if not self.name or not isinstance(self.name, str):
            raise ValueError("name must be a non-empty string")
        if not isinstance(self.location, str):
            raise ValueError("location must be a string")
        if not isinstance(self.type, EquipmentType):
            raise ValueError(f"type must be EquipmentType, got {type(self.type)}")
        if not isinstance(self.status, EquipmentStatus):
            raise ValueError(f"status must be EquipmentStatus, got {type(self.status)}")
        if self.install_date_ns < 0:
            raise ValueError("install_date_ns must be >= 0")
        if self.last_maintenance_ns is not None and self.last_maintenance_ns < 0:
            raise ValueError("last_maintenance_ns must be >= 0 or None")

        # Set install date to now if not provided
        if self.install_date_ns == 0:
            self.install_date_ns = time.time_ns()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "equipment_id": self.equipment_id,
            "name": self.name,
            "type": self.type.value,
            "location": self.location,
            "status": self.status.value,
            "install_date_ns": self.install_date_ns,
            "last_maintenance_ns": self.last_maintenance_ns,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Equipment":
        """Create Equipment from dictionary."""
        return cls(
            equipment_id=data["equipment_id"],
            name=data["name"],
            type=EquipmentType(data["type"]),
            location=data["location"],
            status=EquipmentStatus(data["status"]),
            install_date_ns=data["install_date_ns"],
            last_maintenance_ns=data.get("last_maintenance_ns"),
        )


@dataclass
class MaintenanceLog:
    """Record of a maintenance activity."""

    equipment_id: str
    maintenance_type: MaintenanceType
    description: str
    technician: str
    duration_hours: float
    cost: float
    timestamp_ns: int

    def __post_init__(self) -> None:
        """Validate maintenance log data."""
        if not self.equipment_id or not isinstance(self.equipment_id, str):
            raise ValueError("equipment_id must be a non-empty string")
        if not isinstance(self.maintenance_type, MaintenanceType):
            raise ValueError(
                f"maintenance_type must be MaintenanceType, got {type(self.maintenance_type)}"
            )
        if not isinstance(self.description, str):
            raise ValueError("description must be a string")
        if not isinstance(self.technician, str):
            raise ValueError("technician must be a string")
        if self.duration_hours < 0:
            raise ValueError("duration_hours must be >= 0")
        if self.cost < 0:
            raise ValueError("cost must be >= 0")
        if self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be >= 0")

        # Set timestamp to now if not provided
        if self.timestamp_ns == 0:
            self.timestamp_ns = time.time_ns()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "equipment_id": self.equipment_id,
            "maintenance_type": self.maintenance_type.value,
            "description": self.description,
            "technician": self.technician,
            "duration_hours": self.duration_hours,
            "cost": self.cost,
            "timestamp_ns": self.timestamp_ns,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MaintenanceLog":
        """Create MaintenanceLog from dictionary."""
        return cls(
            equipment_id=data["equipment_id"],
            maintenance_type=MaintenanceType(data["maintenance_type"]),
            description=data["description"],
            technician=data["technician"],
            duration_hours=data["duration_hours"],
            cost=data["cost"],
            timestamp_ns=data["timestamp_ns"],
        )


@dataclass
class FailureEvent:
    """Record of a equipment failure."""

    equipment_id: str
    failure_type: FailureType
    severity: Severity
    description: str
    timestamp_ns: int
    resolved_ns: int | None = None

    def __post_init__(self) -> None:
        """Validate failure event data."""
        if not self.equipment_id or not isinstance(self.equipment_id, str):
            raise ValueError("equipment_id must be a non-empty string")
        if not isinstance(self.failure_type, FailureType):
            raise ValueError(
                f"failure_type must be FailureType, got {type(self.failure_type)}"
            )
        if not isinstance(self.severity, Severity):
            raise ValueError(f"severity must be Severity, got {type(self.severity)}")
        if not isinstance(self.description, str):
            raise ValueError("description must be a string")
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
            "equipment_id": self.equipment_id,
            "failure_type": self.failure_type.value,
            "severity": self.severity.value,
            "description": self.description,
            "timestamp_ns": self.timestamp_ns,
            "resolved_ns": self.resolved_ns,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FailureEvent":
        """Create FailureEvent from dictionary."""
        return cls(
            equipment_id=data["equipment_id"],
            failure_type=FailureType(data["failure_type"]),
            severity=Severity(data["severity"]),
            description=data["description"],
            timestamp_ns=data["timestamp_ns"],
            resolved_ns=data.get("resolved_ns"),
        )


@dataclass
class MaintenanceSchedule:
    """Scheduled maintenance for equipment."""

    equipment_id: str
    maintenance_type: MaintenanceType
    interval_hours: float
    last_performed_ns: int
    next_due_ns: int

    def __post_init__(self) -> None:
        """Validate maintenance schedule data."""
        if not self.equipment_id or not isinstance(self.equipment_id, str):
            raise ValueError("equipment_id must be a non-empty string")
        if not isinstance(self.maintenance_type, MaintenanceType):
            raise ValueError(
                f"maintenance_type must be MaintenanceType, got {type(self.maintenance_type)}"
            )
        if self.interval_hours <= 0:
            raise ValueError("interval_hours must be > 0")
        if self.last_performed_ns < 0:
            raise ValueError("last_performed_ns must be >= 0")
        if self.next_due_ns < 0:
            raise ValueError("next_due_ns must be >= 0")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "equipment_id": self.equipment_id,
            "maintenance_type": self.maintenance_type.value,
            "interval_hours": self.interval_hours,
            "last_performed_ns": self.last_performed_ns,
            "next_due_ns": self.next_due_ns,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MaintenanceSchedule":
        """Create MaintenanceSchedule from dictionary."""
        return cls(
            equipment_id=data["equipment_id"],
            maintenance_type=MaintenanceType(data["maintenance_type"]),
            interval_hours=data["interval_hours"],
            last_performed_ns=data["last_performed_ns"],
            next_due_ns=data["next_due_ns"],
        )


# --------------------------------------------------------------------- #
# Equipment Monitor
# --------------------------------------------------------------------- #


class EquipmentMonitor:
    """Equipment monitoring and maintenance tracking system.

    Provides comprehensive equipment lifecycle management including:
    - Equipment registration and status tracking
    - Maintenance logging and scheduling
    - Failure tracking and resolution
    - Predictive maintenance analytics
    - Alert generation for maintenance needs
    """

    # Default maintenance intervals (in hours)
    DEFAULT_INTERVALS = {
        EquipmentType.ENGINE: 500.0,  # Engine maintenance every 500 hours
        EquipmentType.GENERATOR: 250.0,
        EquipmentType.PUMP: 100.0,
        EquipmentType.WINCH: 150.0,
        EquipmentType.CRANE: 200.0,
        EquipmentType.NET_SOUNDING: 100.0,
        EquipmentType.NAVIGATION: 50.0,  # Navigation equipment checks
        EquipmentType.COMMUNICATION: 50.0,
        EquipmentType.SAFETY: 25.0,  # Frequent safety equipment checks
        EquipmentType.FISHING_GEAR: 75.0,
    }

    def __init__(
        self,
        data_dir: str | Path = "equipment_data",
        enable_persistence: bool = True,
    ) -> None:
        """Initialize the equipment monitor.

        Args:
            data_dir: Directory for JSONL persistence files.
            enable_persistence: Whether to persist data to JSONL files.
        """
        self.data_dir = Path(data_dir)
        self.enable_persistence = enable_persistence

        # In-memory storage
        self._equipment: dict[str, Equipment] = {}
        self._maintenance_logs: list[MaintenanceLog] = []
        self._failure_events: list[FailureEvent] = []
        self._schedules: dict[str, MaintenanceSchedule] = {}

        # Create data directory if persistence is enabled
        if self.enable_persistence:
            self.data_dir.mkdir(parents=True, exist_ok=True)

        log.info("EquipmentMonitor initialized with data_dir=%s", self.data_dir)

    # ------------------------------------------------------------------ #
    # Equipment CRUD operations
    # ------------------------------------------------------------------ #

    def add_equipment(
        self,
        equipment_id: str,
        name: str,
        type: EquipmentType | str,
        location: str,
        install_date_ns: int = 0,
    ) -> Equipment:
        """Add a new equipment record.

        Args:
            equipment_id: Unique identifier for the equipment.
            name: Human-readable name.
            type: Equipment type (enum or string value).
            location: Physical location on vessel.
            install_date_ns: Installation timestamp (nanoseconds, 0 = now).

        Returns:
            The created Equipment instance.

        Raises:
            ValueError: If equipment_id already exists or validation fails.
        """
        if equipment_id in self._equipment:
            raise ValueError(f"Equipment {equipment_id} already exists")

        # Convert string type to enum if needed
        if isinstance(type, str):
            type = EquipmentType(type)

        equipment = Equipment(
            equipment_id=equipment_id,
            name=name,
            type=type,
            location=location,
            install_date_ns=install_date_ns,
        )

        self._equipment[equipment_id] = equipment
        self._persist_equipment(equipment)

        log.info("Added equipment: %s (%s)", equipment_id, name)
        return equipment

    def update_equipment_status(
        self,
        equipment_id: str,
        status: EquipmentStatus | str,
    ) -> Equipment:
        """Update equipment operational status.

        Args:
            equipment_id: Equipment identifier.
            status: New status (enum or string value).

        Returns:
            The updated Equipment instance.

        Raises:
            ValueError: If equipment_id not found or validation fails.
        """
        equipment = self._equipment.get(equipment_id)
        if not equipment:
            raise ValueError(f"Equipment {equipment_id} not found")

        # Convert string status to enum if needed
        if isinstance(status, str):
            status = EquipmentStatus(status)

        old_status = equipment.status
        equipment.status = status

        self._persist_equipment(equipment)

        log.info(
            "Updated status for %s: %s -> %s",
            equipment_id,
            old_status.value,
            status.value,
        )
        return equipment

    def get_equipment(self, equipment_id: str) -> Equipment | None:
        """Get equipment by ID.

        Args:
            equipment_id: Equipment identifier.

        Returns:
            Equipment instance or None if not found.
        """
        return self._equipment.get(equipment_id)

    def get_all_equipment(self) -> dict[str, Equipment]:
        """Get all equipment records.

        Returns:
            Dict mapping equipment_id to Equipment.
        """
        return dict(self._equipment)

    def get_equipment_by_type(
        self, equipment_type: EquipmentType | str
    ) -> list[Equipment]:
        """Get all equipment of a specific type.

        Args:
            equipment_type: Equipment type filter (enum or string value).

        Returns:
            List of Equipment instances matching the type.
        """
        # Convert string type to enum if needed
        if isinstance(equipment_type, str):
            equipment_type = EquipmentType(equipment_type)

        return [
            eq for eq in self._equipment.values() if eq.type == equipment_type
        ]

    # ------------------------------------------------------------------ #
    # Maintenance operations
    # ------------------------------------------------------------------ #

    def log_maintenance(
        self,
        equipment_id: str,
        maintenance_type: MaintenanceType | str,
        description: str,
        technician: str,
        duration_hours: float,
        cost: float,
        timestamp_ns: int = 0,
    ) -> MaintenanceLog:
        """Log a maintenance activity.

        Args:
            equipment_id: Equipment identifier.
            maintenance_type: Type of maintenance performed (enum or string).
            description: Description of work performed.
            technician: Name or ID of technician.
            duration_hours: Duration of maintenance in hours.
            cost: Cost of maintenance (currency units).
            timestamp_ns: Timestamp of maintenance (nanoseconds, 0 = now).

        Returns:
            The created MaintenanceLog instance.

        Raises:
            ValueError: If equipment_id not found or validation fails.
        """
        if equipment_id not in self._equipment:
            raise ValueError(f"Equipment {equipment_id} not found")

        # Convert string type to enum if needed
        if isinstance(maintenance_type, str):
            maintenance_type = MaintenanceType(maintenance_type)

        log_entry = MaintenanceLog(
            equipment_id=equipment_id,
            maintenance_type=maintenance_type,
            description=description,
            technician=technician,
            duration_hours=duration_hours,
            cost=cost,
            timestamp_ns=timestamp_ns,
        )

        self._maintenance_logs.append(log_entry)

        # Update equipment's last maintenance timestamp
        equipment = self._equipment[equipment_id]
        equipment.last_maintenance_ns = log_entry.timestamp_ns
        self._persist_equipment(equipment)

        self._persist_maintenance_log(log_entry)

        log.info(
            "Logged maintenance for %s: %s by %s (%.1f hours, %.2f)",
            equipment_id,
            maintenance_type.value,
            technician,
            duration_hours,
            cost,
        )
        return log_entry

    def get_maintenance_history(self, equipment_id: str) -> list[MaintenanceLog]:
        """Get maintenance history for equipment.

        Args:
            equipment_id: Equipment identifier.

        Returns:
            List of MaintenanceLog entries, most recent first.
        """
        logs = [log for log in self._maintenance_logs if log.equipment_id == equipment_id]
        logs.sort(key=lambda x: x.timestamp_ns, reverse=True)
        return logs

    # ------------------------------------------------------------------ #
    # Failure operations
    # ------------------------------------------------------------------ #

    def log_failure(
        self,
        equipment_id: str,
        failure_type: FailureType | str,
        severity: Severity | str,
        description: str,
        timestamp_ns: int = 0,
    ) -> FailureEvent:
        """Log a equipment failure.

        Args:
            equipment_id: Equipment identifier.
            failure_type: Type of failure (enum or string).
            severity: Failure severity (enum or string).
            description: Description of the failure.
            timestamp_ns: Timestamp of failure (nanoseconds, 0 = now).

        Returns:
            The created FailureEvent instance.

        Raises:
            ValueError: If equipment_id not found or validation fails.
        """
        if equipment_id not in self._equipment:
            raise ValueError(f"Equipment {equipment_id} not found")

        # Convert strings to enums if needed
        if isinstance(failure_type, str):
            failure_type = FailureType(failure_type)
        if isinstance(severity, str):
            severity = Severity(severity)

        failure = FailureEvent(
            equipment_id=equipment_id,
            failure_type=failure_type,
            severity=severity,
            description=description,
            timestamp_ns=timestamp_ns,
        )

        self._failure_events.append(failure)

        # Update equipment status to FAILED if severity is HIGH or CRITICAL
        if severity in (Severity.HIGH, Severity.CRITICAL):
            self.update_equipment_status(equipment_id, EquipmentStatus.FAILED)

        self._persist_failure_event(failure)

        log.warning(
            "Logged failure for %s: %s (%s) - %s",
            equipment_id,
            failure_type.value,
            severity.value,
            description,
        )
        return failure

    def resolve_failure(
        self, equipment_id: str, resolution_description: str, timestamp_ns: int = 0
    ) -> FailureEvent | None:
        """Resolve the most recent unresolved failure for equipment.

        Args:
            equipment_id: Equipment identifier.
            resolution_description: Description of resolution actions.
            timestamp_ns: Resolution timestamp (nanoseconds, 0 = now).

        Returns:
            The resolved FailureEvent, or None if no unresolved failure exists.

        Raises:
            ValueError: If equipment_id not found.
        """
        if equipment_id not in self._equipment:
            raise ValueError(f"Equipment {equipment_id} not found")

        if timestamp_ns == 0:
            timestamp_ns = time.time_ns()

        # Find most recent unresolved failure
        unresolved = [
            f
            for f in self._failure_events
            if f.equipment_id == equipment_id and f.resolved_ns is None
        ]
        unresolved.sort(key=lambda x: x.timestamp_ns, reverse=True)

        if not unresolved:
            return None

        failure = unresolved[0]
        failure.resolved_ns = timestamp_ns

        self._persist_failure_event(failure)

        # Update equipment status back to OPERATIONAL
        self.update_equipment_status(equipment_id, EquipmentStatus.OPERATIONAL)

        log.info(
            "Resolved failure for %s at %s: %s",
            equipment_id,
            timestamp_ns,
            resolution_description,
        )
        return failure

    def get_failure_history(self, equipment_id: str) -> list[FailureEvent]:
        """Get failure history for equipment.

        Args:
            equipment_id: Equipment identifier.

        Returns:
            List of FailureEvent entries, most recent first.
        """
        failures = [
            f for f in self._failure_events if f.equipment_id == equipment_id
        ]
        failures.sort(key=lambda x: x.timestamp_ns, reverse=True)
        return failures

    # ------------------------------------------------------------------ #
    # Maintenance scheduling
    # ------------------------------------------------------------------ #

    def schedule_maintenance(
        self,
        equipment_id: str,
        maintenance_type: MaintenanceType | str,
        interval_hours: float | None = None,
    ) -> MaintenanceSchedule:
        """Schedule recurring maintenance for equipment.

        Args:
            equipment_id: Equipment identifier.
            maintenance_type: Type of maintenance (enum or string).
            interval_hours: Interval in hours (None = use default for type).

        Returns:
            The created/updated MaintenanceSchedule.

        Raises:
            ValueError: If equipment_id not found or validation fails.
        """
        equipment = self._equipment.get(equipment_id)
        if not equipment:
            raise ValueError(f"Equipment {equipment_id} not found")

        # Convert string type to enum if needed
        if isinstance(maintenance_type, str):
            maintenance_type = MaintenanceType(maintenance_type)

        # Use default interval if not specified
        if interval_hours is None:
            interval_hours = self.DEFAULT_INTERVALS.get(equipment.type, 100.0)

        # Use last maintenance time or install date
        last_performed = equipment.last_maintenance_ns or equipment.install_date_ns

        # Calculate next due time
        interval_ns = int(interval_hours * 3600 * 1e9)
        next_due_ns = last_performed + interval_ns

        schedule = MaintenanceSchedule(
            equipment_id=equipment_id,
            maintenance_type=maintenance_type,
            interval_hours=interval_hours,
            last_performed_ns=last_performed,
            next_due_ns=next_due_ns,
        )

        self._schedules[equipment_id] = schedule
        self._persist_schedule(schedule)

        log.info(
            "Scheduled %s maintenance for %s every %.1f hours (next due: %s)",
            maintenance_type.value,
            equipment_id,
            interval_hours,
            datetime.fromtimestamp(next_due_ns / 1e9, tz=timezone.utc).isoformat(),
        )
        return schedule

    def get_maintenance_schedule(self, equipment_id: str) -> MaintenanceSchedule | None:
        """Get maintenance schedule for equipment.

        Args:
            equipment_id: Equipment identifier.

        Returns:
            MaintenanceSchedule or None if not scheduled.
        """
        return self._schedules.get(equipment_id)

    def get_due_maintenance(self, lookahead_hours: float = 24.0) -> list[MaintenanceSchedule]:
        """Get maintenance schedules due within lookahead period.

        Args:
            lookahead_hours: Hours to look ahead (default 24h).

        Returns:
            List of MaintenanceSchedule due within lookahead, sorted by due time.
        """
        now_ns = time.time_ns()
        lookahead_ns = int(lookahead_hours * 3600 * 1e9)

        due = [
            s
            for s in self._schedules.values()
            if now_ns <= s.next_due_ns <= now_ns + lookahead_ns
        ]
        due.sort(key=lambda x: x.next_due_ns)

        return due

    def get_overdue_maintenance(self) -> list[MaintenanceSchedule]:
        """Get maintenance schedules that are overdue.

        Returns:
            List of overdue MaintenanceSchedule, sorted by overdue time.
        """
        now_ns = time.time_ns()
        overdue = [
            s for s in self._schedules.values() if s.next_due_ns < now_ns
        ]
        overdue.sort(key=lambda x: x.next_due_ns)
        return overdue

    # ------------------------------------------------------------------ #
    # Predictive maintenance analytics
    # ------------------------------------------------------------------ #

    def predict_maintenance_needs(
        self, equipment_id: str, lookahead_hours: float = 168.0
    ) -> list[dict[str, Any]]:
        """Predict maintenance needs for equipment.

        Analyzes:
        - Scheduled maintenance due dates
        - Failure history (MTBF)
        - Time since last maintenance
        - Equipment age and type

        Args:
            equipment_id: Equipment identifier.
            lookahead_hours: Prediction horizon in hours (default 7 days).

        Returns:
            List of predicted maintenance needs with metadata.
        """
        equipment = self._equipment.get(equipment_id)
        if not equipment:
            raise ValueError(f"Equipment {equipment_id} not found")

        predictions = []
        now_ns = time.time_ns()
        lookahead_ns = int(lookahead_hours * 3600 * 1e9)

        # Check scheduled maintenance
        schedule = self._schedules.get(equipment_id)
        if schedule and schedule.next_due_ns <= now_ns + lookahead_ns:
            time_until_due = (schedule.next_due_ns - now_ns) / 1e9 / 3600
            predictions.append({
                "equipment_id": equipment_id,
                "maintenance_type": schedule.maintenance_type.value,
                "predicted_due_hours": time_until_due,
                "due_date": datetime.fromtimestamp(
                    schedule.next_due_ns / 1e9, tz=timezone.utc
                ).isoformat(),
                "reason": "scheduled_maintenance",
                "priority": "high" if time_until_due < 24 else "medium",
            })

        # Analyze failure history for predictive insights
        failures = self.get_failure_history(equipment_id)
        if len(failures) >= 2:
            # Calculate MTBF
            resolved_failures = [f for f in failures if f.resolved_ns]
            if len(resolved_failures) >= 2:
                intervals = []
                for i in range(1, len(resolved_failures)):
                    interval_hours = (
                        resolved_failures[i].timestamp_ns
                        - resolved_failures[i - 1].resolved_ns
                    ) / 1e9 / 3600
                    intervals.append(interval_hours)

                if intervals:
                    mtbf = sum(intervals) / len(intervals)
                    # Predict next failure based on MTBF
                    last_failure_ns = resolved_failures[0].resolved_ns
                    next_predicted_failure = last_failure_ns + int(mtbf * 3600 * 1e9)

                    if next_predicted_failure <= now_ns + lookahead_ns:
                        predictions.append({
                            "equipment_id": equipment_id,
                            "maintenance_type": "PREVENTIVE",
                            "predicted_due_hours": (next_predicted_failure - now_ns)
                            / 1e9
                            / 3600,
                            "due_date": datetime.fromtimestamp(
                                next_predicted_failure / 1e9, tz=timezone.utc
                            ).isoformat(),
                            "reason": "failure_pattern_prediction",
                            "mtbf_hours": mtbf,
                            "priority": "high",
                        })

        # Check if equipment is in DEGRADED or MAINTENANCE_REQUIRED status
        if equipment.status in (
            EquipmentStatus.DEGRADED,
            EquipmentStatus.MAINTENANCE_REQUIRED,
        ):
            predictions.append({
                "equipment_id": equipment_id,
                "maintenance_type": "CORRECTIVE",
                "predicted_due_hours": 0,
                "due_date": datetime.now(timezone.utc).isoformat(),
                "reason": "current_status",
                "status": equipment.status.value,
                "priority": "critical",
            })

        # Sort by priority and due date
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        predictions.sort(
            key=lambda x: (priority_order.get(x["priority"], 99), x["predicted_due_hours"])
        )

        return predictions

    def calculate_mtbf(self, equipment_id: str) -> float | None:
        """Calculate Mean Time Between Failures for equipment.

        Args:
            equipment_id: Equipment identifier.

        Returns:
            MTBF in hours, or None if insufficient data.
        """
        failures = self.get_failure_history(equipment_id)
        resolved_failures = [f for f in failures if f.resolved_ns]

        if len(resolved_failures) < 2:
            return None

        # Sort chronologically (oldest first) for MTBF calculation
        resolved_failures.sort(key=lambda x: x.timestamp_ns)

        intervals = []
        for i in range(1, len(resolved_failures)):
            interval_hours = (
                resolved_failures[i].timestamp_ns - resolved_failures[i - 1].resolved_ns
            ) / 1e9 / 3600
            intervals.append(interval_hours)

        if not intervals:
            return None

        return sum(intervals) / len(intervals)

    def calculate_mttr(self, equipment_id: str) -> float | None:
        """Calculate Mean Time To Repair for equipment.

        Args:
            equipment_id: Equipment identifier.

        Returns:
            MTTR in hours, or None if insufficient data.
        """
        failures = self.get_failure_history(equipment_id)
        resolved_failures = [f for f in failures if f.resolved_ns]

        if not resolved_failures:
            return None

        repair_times = []
        for failure in resolved_failures:
            repair_hours = (failure.resolved_ns - failure.timestamp_ns) / 1e9 / 3600
            repair_times.append(repair_hours)

        return sum(repair_times) / len(repair_times)

    def calculate_equipment_uptime(self, equipment_id: str) -> dict[str, Any]:
        """Calculate uptime statistics for equipment.

        Args:
            equipment_id: Equipment identifier.

        Returns:
            Dict with uptime percentage, downtime hours, and operational status.
        """
        equipment = self._equipment.get(equipment_id)
        if not equipment:
            raise ValueError(f"Equipment {equipment_id} not found")

        now_ns = time.time_ns()
        total_age_ns = now_ns - equipment.install_date_ns

        # Calculate downtime from failure events
        failures = self.get_failure_history(equipment_id)
        downtime_ns = 0
        failure_count = len([f for f in failures if f.resolved_ns])

        for failure in failures:
            if failure.resolved_ns:
                downtime_ns += failure.resolved_ns - failure.timestamp_ns
            else:
                # Unresolved failure - count until now
                downtime_ns += now_ns - failure.timestamp_ns

        uptime_ns = total_age_ns - downtime_ns
        uptime_percentage = (uptime_ns / total_age_ns * 100) if total_age_ns > 0 else 0

        return {
            "equipment_id": equipment_id,
            "uptime_percentage": round(uptime_percentage, 2),
            "total_downtime_hours": round(downtime_ns / 1e9 / 3600, 2),
            "total_uptime_hours": round(uptime_ns / 1e9 / 3600, 2),
            "failure_count": failure_count,
            "current_status": equipment.status.value,
        }

    def get_maintenance_cost_summary(
        self, equipment_id: str | None = None
    ) -> dict[str, Any]:
        """Get maintenance cost summary.

        Args:
            equipment_id: Optional equipment filter (None = all equipment).

        Returns:
            Dict with total cost, cost by type, and maintenance count.
        """
        if equipment_id:
            logs = [log for log in self._maintenance_logs if log.equipment_id == equipment_id]
        else:
            logs = self._maintenance_logs

        total_cost = sum(log.cost for log in logs)
        total_hours = sum(log.duration_hours for log in logs)

        # Group by maintenance type
        cost_by_type: dict[str, dict[str, Any]] = {}
        for log in logs:
            mtype = log.maintenance_type.value
            if mtype not in cost_by_type:
                cost_by_type[mtype] = {"count": 0, "total_cost": 0.0, "total_hours": 0.0}
            cost_by_type[mtype]["count"] += 1
            cost_by_type[mtype]["total_cost"] += log.cost
            cost_by_type[mtype]["total_hours"] += log.duration_hours

        return {
            "equipment_id": equipment_id,
            "total_cost": round(total_cost, 2),
            "total_hours": round(total_hours, 2),
            "maintenance_count": len(logs),
            "cost_by_type": cost_by_type,
        }

    # ------------------------------------------------------------------ #
    # Alert generation
    # ------------------------------------------------------------------ #

    def get_alerts(self) -> list[dict[str, Any]]:
        """Generate alerts for equipment issues and maintenance needs.

        Returns:
            List of alert dicts with severity, message, and metadata.
        """
        alerts = []
        now_ns = time.time_ns()

        # Check for failed equipment
        for eq in self._equipment.values():
            if eq.status == EquipmentStatus.FAILED:
                alerts.append({
                    "severity": "critical",
                    "code": "EQUIPMENT_FAILED",
                    "message": f"Equipment {eq.name} ({eq.equipment_id}) has failed",
                    "equipment_id": eq.equipment_id,
                    "equipment_name": eq.name,
                    "equipment_type": eq.type.value,
                })
            elif eq.status == EquipmentStatus.DEGRADED:
                alerts.append({
                    "severity": "warning",
                    "code": "EQUIPMENT_DEGRADED",
                    "message": f"Equipment {eq.name} ({eq.equipment_id}) is degraded",
                    "equipment_id": eq.equipment_id,
                    "equipment_name": eq.name,
                    "equipment_type": eq.type.value,
                })
            elif eq.status == EquipmentStatus.MAINTENANCE_REQUIRED:
                alerts.append({
                    "severity": "high",
                    "code": "MAINTENANCE_REQUIRED",
                    "message": f"Equipment {eq.name} ({eq.equipment_id}) requires maintenance",
                    "equipment_id": eq.equipment_id,
                    "equipment_name": eq.name,
                    "equipment_type": eq.type.value,
                })

        # Check for overdue maintenance
        overdue = self.get_overdue_maintenance()
        for schedule in overdue:
            equipment = self._equipment.get(schedule.equipment_id)
            if equipment:
                overdue_hours = (now_ns - schedule.next_due_ns) / 1e9 / 3600
                alerts.append({
                    "severity": "warning",
                    "code": "MAINTENANCE_OVERDUE",
                    "message": f"Maintenance overdue by {overdue_hours:.1f}h for {equipment.name}",
                    "equipment_id": schedule.equipment_id,
                    "equipment_name": equipment.name,
                    "maintenance_type": schedule.maintenance_type.value,
                    "overdue_hours": round(overdue_hours, 1),
                })

        # Check for unresolved critical failures
        for failure in self._failure_events:
            if failure.resolved_ns is None and failure.severity == Severity.CRITICAL:
                equipment = self._equipment.get(failure.equipment_id)
                if equipment:
                    alerts.append({
                        "severity": "critical",
                        "code": "CRITICAL_FAILURE_UNRESOLVED",
                        "message": f"Critical failure unresolved: {failure.description}",
                        "equipment_id": failure.equipment_id,
                        "equipment_name": equipment.name,
                        "failure_type": failure.failure_type.value,
                        "description": failure.description,
                    })

        return alerts

    # ------------------------------------------------------------------ #
    # Integration methods
    # ------------------------------------------------------------------ #

    def get_watcher_frame(self) -> dict[str, Any]:
        """Build a watcher frame for equipment monitoring.

        Returns a dict with equipment status, maintenance alerts, and
        failure information for watcher rule evaluation.
        """
        now_ns = time.time_ns()

        # Count equipment by status
        status_counts: dict[str, int] = {}
        for eq in self._equipment.values():
            status = eq.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        # Count overdue maintenance
        overdue_count = len(self.get_overdue_maintenance())

        # Count unresolved failures by severity
        unresolved_failures = [f for f in self._failure_events if f.resolved_ns is None]
        failure_counts: dict[str, int] = {}
        for failure in unresolved_failures:
            severity = failure.severity.value
            failure_counts[severity] = failure_counts.get(severity, 0) + 1

        return {
            "timestamp_ns": now_ns,
            "equipment_count": len(self._equipment),
            "equipment_status_counts": status_counts,
            "overdue_maintenance_count": overdue_count,
            "unresolved_failure_counts": failure_counts,
            "total_maintenance_logs": len(self._maintenance_logs),
            "total_failures": len(self._failure_events),
        }

    def to_dict(self) -> dict[str, Any]:
        """Create a comprehensive snapshot of the equipment monitor state.

        Returns:
            Dict with all equipment, maintenance logs, failures, and schedules.
        """
        return {
            "equipment": {
                eq_id: eq.to_dict() for eq_id, eq in self._equipment.items()
            },
            "maintenance_logs": [log.to_dict() for log in self._maintenance_logs],
            "failure_events": [failure.to_dict() for failure in self._failure_events],
            "schedules": {
                eq_id: schedule.to_dict()
                for eq_id, schedule in self._schedules.items()
            },
            "watcher_frame": self.get_watcher_frame(),
            "alerts": self.get_alerts(),
        }

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _persist_equipment(self, equipment: Equipment) -> None:
        """Append equipment record to JSONL file."""
        if not self.enable_persistence:
            return

        try:
            path = self.data_dir / "equipment.jsonl"
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(equipment.to_dict()) + "\n")
        except (OSError, TypeError) as exc:
            log.warning("Failed to persist equipment record: %s", exc)

    def _persist_maintenance_log(self, log_entry: MaintenanceLog) -> None:
        """Append maintenance log to JSONL file."""
        if not self.enable_persistence:
            return

        try:
            path = self.data_dir / "maintenance.jsonl"
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry.to_dict()) + "\n")
        except (OSError, TypeError) as exc:
            log.warning("Failed to persist maintenance log: %s", exc)

    def _persist_failure_event(self, failure: FailureEvent) -> None:
        """Append failure event to JSONL file."""
        if not self.enable_persistence:
            return

        try:
            path = self.data_dir / "failures.jsonl"
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(failure.to_dict()) + "\n")
        except (OSError, TypeError) as exc:
            log.warning("Failed to persist failure event: %s", exc)

    def _persist_schedule(self, schedule: MaintenanceSchedule) -> None:
        """Append maintenance schedule to JSONL file."""
        if not self.enable_persistence:
            return

        try:
            path = self.data_dir / "schedules.jsonl"
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(schedule.to_dict()) + "\n")
        except (OSError, TypeError) as exc:
            log.warning("Failed to persist maintenance schedule: %s", exc)

    def load_from_disk(self) -> None:
        """Load all data from JSONL files.

        Reconstructs in-memory state from persisted files.
        """
        if not self.enable_persistence:
            return

        # Load equipment
        equipment_path = self.data_dir / "equipment.jsonl"
        if equipment_path.exists():
            with open(equipment_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            equipment = Equipment.from_dict(json.loads(line))
                            self._equipment[equipment.equipment_id] = equipment
                        except (json.JSONDecodeError, KeyError, ValueError) as exc:
                            log.warning("Failed to load equipment record: %s", exc)

        # Load maintenance logs
        maintenance_path = self.data_dir / "maintenance.jsonl"
        if maintenance_path.exists():
            with open(maintenance_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            log_entry = MaintenanceLog.from_dict(json.loads(line))
                            self._maintenance_logs.append(log_entry)
                        except (json.JSONDecodeError, KeyError, ValueError) as exc:
                            log.warning("Failed to load maintenance log: %s", exc)

        # Load failure events
        failures_path = self.data_dir / "failures.jsonl"
        if failures_path.exists():
            with open(failures_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            failure = FailureEvent.from_dict(json.loads(line))
                            self._failure_events.append(failure)
                        except (json.JSONDecodeError, KeyError, ValueError) as exc:
                            log.warning("Failed to load failure event: %s", exc)

        # Load schedules (keep only latest per equipment)
        schedules_path = self.data_dir / "schedules.jsonl"
        if schedules_path.exists():
            temp_schedules: dict[str, MaintenanceSchedule] = {}
            with open(schedules_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            schedule = MaintenanceSchedule.from_dict(json.loads(line))
                            temp_schedules[schedule.equipment_id] = schedule
                        except (json.JSONDecodeError, KeyError, ValueError) as exc:
                            log.warning("Failed to load schedule: %s", exc)
            self._schedules = temp_schedules

        log.info(
            "Loaded from disk: %d equipment, %d maintenance logs, %d failures, %d schedules",
            len(self._equipment),
            len(self._maintenance_logs),
            len(self._failure_events),
            len(self._schedules),
        )
