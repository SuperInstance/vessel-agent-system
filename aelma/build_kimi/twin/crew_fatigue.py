"""Crew Fatigue monitoring system for the AELMA twin.

Tracks crew work hours, watch schedules, and fatigue levels to prevent
fatigue-related incidents. Uses cumulative work hour tracking, rest
period monitoring, and watch rotation analysis to calculate fatigue
scores and generate alerts when thresholds are exceeded.

Fatigue calculation considers:
- Cumulative work hours (24h, 48h, 72h windows)
- Rest period quality and duration
- Break frequency and duration
- Watch rotation patterns (6-on/6-off, 4-on/8-off, 12-on/12-off)
- Activity type weighting (navigation, gear handling, rest)

Alert thresholds:
- HIGH: >12 hours continuous work
- CRITICAL: >16 hours continuous work
- DANGER: >24 hours without 8-hour rest
- MULTIPLE: >72 hours with <24-hour rest
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# Constants for fatigue thresholds
FATIGUE_THRESHOLD_HIGH = 12.0 * 3600e9  # 12 hours in nanoseconds
FATIGUE_THRESHOLD_CRITICAL = 16.0 * 3600e9  # 16 hours in nanoseconds
FATIGUE_THRESHOLD_DANGER = 24.0 * 3600e9  # 24 hours in nanoseconds
FATIGUE_REST_MINIMUM = 8.0 * 3600e9  # 8 hours minimum rest
FATIGUE_MULTIPLE_WINDOW = 72.0 * 3600e9  # 72 hours
FATIGUE_MULTIPLE_REST_MAX = 24.0 * 3600e9  # 24 hours max rest for multiple alert

# Fatigue score calculation weights
ACTIVITY_WEIGHTS = {
    "NAVIGATION": 1.5,  # High cognitive load
    "GEAR_HANDLING": 1.4,  # High physical load
    "DECK_WORK": 1.2,  # Medium physical load
    "MAINTENANCE": 1.1,  # Medium load
    "REST": 0.0,  # No fatigue contribution
    "STANDBY": 0.5,  # Low load
}

# Time windows for fatigue calculation (in nanoseconds)
WINDOW_24H = 24.0 * 3600e9
WINDOW_48H = 48.0 * 3600e9
WINDOW_72H = 72.0 * 3600e9


class CrewStatus(str, Enum):
    """Crew member status."""

    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    SICK = "sick"
    INJURED = "injured"
    UNAVAILABLE = "unavailable"


class WatchType(str, Enum):
    """Watch schedule rotation types."""

    SIX_ON_SIX_OFF = "six_on_six_off"  # 6 hours on, 6 hours off
    FOUR_ON_EIGHT_OFF = "four_on_eight_off"  # 4 hours on, 8 hours off
    TWELVE_ON_TWELVE_OFF = "twelve_on_twelve_off"  # 12 hours on, 12 hours off
    CUSTOM = "custom"  # User-defined rotation


class ActivityType(str, Enum):
    """Activity types for work period logging."""

    NAVIGATION = "NAVIGATION"
    GEAR_HANDLING = "GEAR_HANDLING"
    DECK_WORK = "DECK_WORK"
    MAINTENANCE = "MAINTENANCE"
    REST = "REST"
    STANDBY = "STANDBY"


class AlertSeverity(str, Enum):
    """Fatigue alert severity levels."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    DANGER = "danger"


class AlertType(str, Enum):
    """Fatigue alert types."""

    CONTINUOUS_WORK_HIGH = "continuous_work_high"  # >12h continuous
    CONTINUOUS_WORK_CRITICAL = "continuous_work_critical"  # >16h continuous
    INSUFFICIENT_REST_DANGER = "insufficient_rest_danger"  # >24h without 8h rest
    MULTIPLE_FATIGUE = "multiple_fatigue"  # >72h with <24h rest
    WATCH_SCHEDULE_DEVIATION = "watch_schedule_deviation"  # Deviation from schedule
    REST_PERIOD_SHORT = "rest_period_short"  # Rest period too short


@dataclass
class CrewMember:
    """A crew member with identification and status.

    Attributes:
        crew_id: Unique identifier for the crew member
        name: Full name of the crew member
        role: Role on the vessel (captain, mate, engineer, deckhand)
        vessel_id: Vessel identifier
        status: Current availability status
    """

    crew_id: str
    name: str
    role: str
    vessel_id: str
    status: CrewStatus = CrewStatus.ACTIVE

    def __post_init__(self):
        """Validate crew member data."""
        if not self.crew_id or not isinstance(self.crew_id, str):
            raise ValueError("crew_id must be a non-empty string")
        if not self.name or not isinstance(self.name, str):
            raise ValueError("name must be a non-empty string")
        if not self.role or not isinstance(self.role, str):
            raise ValueError("role must be a non-empty string")
        if not self.vessel_id or not isinstance(self.vessel_id, str):
            raise ValueError("vessel_id must be a non-empty string")
        if isinstance(self.status, str):
            self.status = CrewStatus(self.status)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "crew_id": self.crew_id,
            "name": self.name,
            "role": self.role,
            "vessel_id": self.vessel_id,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrewMember:
        """Create CrewMember from dictionary."""
        return cls(
            crew_id=data["crew_id"],
            name=data["name"],
            role=data["role"],
            vessel_id=data["vessel_id"],
            status=CrewStatus(data.get("status", "active")),
        )


@dataclass
class WorkHours:
    """A recorded work period for a crew member.

    Attributes:
        crew_id: Crew member identifier
        start_time_ns: Work period start timestamp (nanoseconds)
        end_time_ns: Work period end timestamp (nanoseconds)
        activity_type: Type of work performed
        watch_position: Watch position (if applicable)
    """

    crew_id: str
    start_time_ns: int
    end_time_ns: int
    activity_type: ActivityType
    watch_position: str | None = None

    def __post_init__(self):
        """Validate work hours data."""
        if not self.crew_id or not isinstance(self.crew_id, str):
            raise ValueError("crew_id must be a non-empty string")
        if not isinstance(self.start_time_ns, int):
            raise ValueError("start_time_ns must be an integer")
        if self.start_time_ns < 0:
            raise ValueError("start_time_ns must be a non-negative integer")
        if not isinstance(self.end_time_ns, int):
            raise ValueError("end_time_ns must be an integer")
        if self.end_time_ns < 0:
            raise ValueError("end_time_ns must be a non-negative integer")
        if self.start_time_ns >= self.end_time_ns:
            raise ValueError("start_time_ns must be before end_time_ns")
        if isinstance(self.activity_type, str):
            self.activity_type = ActivityType(self.activity_type)

    @property
    def duration_ns(self) -> int:
        """Duration of work period in nanoseconds."""
        return self.end_time_ns - self.start_time_ns

    @property
    def duration_hours(self) -> float:
        """Duration of work period in hours."""
        return self.duration_ns / (3600e9)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "crew_id": self.crew_id,
            "start_time_ns": self.start_time_ns,
            "end_time_ns": self.end_time_ns,
            "activity_type": self.activity_type.value,
            "watch_position": self.watch_position,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkHours:
        """Create WorkHours from dictionary."""
        return cls(
            crew_id=data["crew_id"],
            start_time_ns=int(data["start_time_ns"]),
            end_time_ns=int(data["end_time_ns"]),
            activity_type=ActivityType(data["activity_type"]),
            watch_position=data.get("watch_position"),
        )


@dataclass
class FatigueMetrics:
    """Fatigue metrics for a crew member.

    Attributes:
        crew_id: Crew member identifier
        fatigue_score: Overall fatigue score (0-100)
        hours_worked_24h: Hours worked in last 24 hours
        hours_worked_48h: Hours worked in last 48 hours
        hours_worked_72h: Hours worked in last 72 hours
        hours_rest_24h: Hours of rest in last 24 hours
        last_break_ns: Timestamp of last break period
        continuous_work_ns: Duration of current continuous work period
        watch_compliance: Whether work follows watch schedule (0-1 score)
    """

    crew_id: str
    fatigue_score: float
    hours_worked_24h: float
    hours_worked_48h: float
    hours_worked_72h: float
    hours_rest_24h: float
    last_break_ns: int | None
    continuous_work_ns: int
    watch_compliance: float

    def __post_init__(self):
        """Validate fatigue metrics."""
        if not 0 <= self.fatigue_score <= 100:
            raise ValueError("fatigue_score must be between 0 and 100")
        if self.hours_worked_24h < 0:
            raise ValueError("hours_worked_24h must be non-negative")
        if self.hours_worked_48h < 0:
            raise ValueError("hours_worked_48h must be non-negative")
        if self.hours_worked_72h < 0:
            raise ValueError("hours_worked_72h must be non-negative")
        if self.hours_rest_24h < 0:
            raise ValueError("hours_rest_24h must be non-negative")
        if self.continuous_work_ns < 0:
            raise ValueError("continuous_work_ns must be non-negative")
        if not 0 <= self.watch_compliance <= 1:
            raise ValueError("watch_compliance must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "crew_id": self.crew_id,
            "fatigue_score": round(self.fatigue_score, 2),
            "hours_worked_24h": round(self.hours_worked_24h, 2),
            "hours_worked_48h": round(self.hours_worked_48h, 2),
            "hours_worked_72h": round(self.hours_worked_72h, 2),
            "hours_rest_24h": round(self.hours_rest_24h, 2),
            "last_break_ns": self.last_break_ns,
            "continuous_work_hours": round(self.continuous_work_ns / (3600e9), 2),
            "watch_compliance": round(self.watch_compliance, 2),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FatigueMetrics:
        """Create FatigueMetrics from dictionary."""
        return cls(
            crew_id=data["crew_id"],
            fatigue_score=float(data["fatigue_score"]),
            hours_worked_24h=float(data["hours_worked_24h"]),
            hours_worked_48h=float(data["hours_worked_48h"]),
            hours_worked_72h=float(data["hours_worked_72h"]),
            hours_rest_24h=float(data["hours_rest_24h"]),
            last_break_ns=data.get("last_break_ns"),
            continuous_work_ns=int(data.get("continuous_work_hours", 0) * 3600e9),
            watch_compliance=float(data.get("watch_compliance", 1.0)),
        )


@dataclass
class WatchSchedule:
    """Watch schedule configuration for a crew member.

    Attributes:
        crew_id: Crew member identifier
        watch_type: Type of watch rotation
        start_time_ns: Watch start timestamp (nanoseconds)
        duration_ns: Watch duration in nanoseconds
        rotation_ns: Rotation period in nanoseconds
        custom_name: Name for custom watch types
    """

    crew_id: str
    watch_type: WatchType
    start_time_ns: int
    duration_ns: int
    rotation_ns: int
    custom_name: str | None = None

    def __post_init__(self):
        """Validate watch schedule."""
        if not self.crew_id or not isinstance(self.crew_id, str):
            raise ValueError("crew_id must be a non-empty string")
        if isinstance(self.watch_type, str):
            self.watch_type = WatchType(self.watch_type)
        if not isinstance(self.start_time_ns, int) or self.start_time_ns < 0:
            raise ValueError("start_time_ns must be a non-negative integer")

        # Set default durations for standard watch types (before validation)
        if self.duration_ns == 0 or self.rotation_ns == 0:
            if self.watch_type == WatchType.SIX_ON_SIX_OFF:
                if self.duration_ns == 0:
                    self.duration_ns = int(6 * 3600e9)
                if self.rotation_ns == 0:
                    self.rotation_ns = int(12 * 3600e9)  # 6h on, 6h off
            elif self.watch_type == WatchType.FOUR_ON_EIGHT_OFF:
                if self.duration_ns == 0:
                    self.duration_ns = int(4 * 3600e9)
                if self.rotation_ns == 0:
                    self.rotation_ns = int(12 * 3600e9)  # 4h on, 8h off
            elif self.watch_type == WatchType.TWELVE_ON_TWELVE_OFF:
                if self.duration_ns == 0:
                    self.duration_ns = int(12 * 3600e9)
                if self.rotation_ns == 0:
                    self.rotation_ns = int(24 * 3600e9)  # 12h on, 12h off

        # Now validate
        if not isinstance(self.duration_ns, int) or self.duration_ns <= 0:
            raise ValueError("duration_ns must be a positive integer")
        if not isinstance(self.rotation_ns, int) or self.rotation_ns <= 0:
            raise ValueError("rotation_ns must be a positive integer")

    @property
    def duration_hours(self) -> float:
        """Watch duration in hours."""
        return self.duration_ns / (3600e9)

    @property
    def rotation_hours(self) -> float:
        """Watch rotation period in hours."""
        return self.rotation_ns / (3600e9)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "crew_id": self.crew_id,
            "watch_type": self.watch_type.value,
            "start_time_ns": self.start_time_ns,
            "duration_hours": self.duration_hours,
            "rotation_hours": self.rotation_hours,
            "custom_name": self.custom_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WatchSchedule:
        """Create WatchSchedule from dictionary."""
        return cls(
            crew_id=data["crew_id"],
            watch_type=WatchType(data["watch_type"]),
            start_time_ns=int(data["start_time_ns"]),
            duration_ns=int(data.get("duration_hours", 0) * 3600e9),
            rotation_ns=int(data.get("rotation_hours", 0) * 3600e9),
            custom_name=data.get("custom_name"),
        )


@dataclass
class FatigueAlert:
    """Fatigue alert for a crew member.

    Attributes:
        crew_id: Crew member identifier
        alert_type: Type of fatigue alert
        severity: Alert severity level
        fatigue_score: Fatigue score at alert time
        timestamp_ns: Alert timestamp (nanoseconds)
        message: Human-readable alert message
        metrics: Fatigue metrics at alert time
    """

    crew_id: str
    alert_type: AlertType
    severity: AlertSeverity
    fatigue_score: float
    timestamp_ns: int
    message: str
    metrics: dict[str, Any]

    def __post_init__(self):
        """Validate alert data."""
        if not self.crew_id or not isinstance(self.crew_id, str):
            raise ValueError("crew_id must be a non-empty string")
        if isinstance(self.alert_type, str):
            self.alert_type = AlertType(self.alert_type)
        if isinstance(self.severity, str):
            self.severity = AlertSeverity(self.severity)
        if not 0 <= self.fatigue_score <= 100:
            raise ValueError("fatigue_score must be between 0 and 100")
        if not isinstance(self.timestamp_ns, int) or self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be a non-negative integer")
        if not self.message or not isinstance(self.message, str):
            raise ValueError("message must be a non-empty string")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "crew_id": self.crew_id,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "fatigue_score": round(self.fatigue_score, 2),
            "timestamp_ns": self.timestamp_ns,
            "message": self.message,
            "metrics": self.metrics,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FatigueAlert:
        """Create FatigueAlert from dictionary."""
        return cls(
            crew_id=data["crew_id"],
            alert_type=AlertType(data["alert_type"]),
            severity=AlertSeverity(data["severity"]),
            fatigue_score=float(data["fatigue_score"]),
            timestamp_ns=int(data["timestamp_ns"]),
            message=data["message"],
            metrics=data["metrics"],
        )


class CrewFatigueMonitor:
    """Monitor crew fatigue levels using work hours and watch schedules.

    Tracks work periods, rest periods, and watch schedules to calculate
    fatigue scores and generate alerts when thresholds are exceeded.

    Example:
        >>> monitor = CrewFatigueMonitor("vessel_001")
        >>> monitor.add_crew_member("crew_001", "John Smith", "captain")
        >>> monitor.log_work_period("crew_001", start_ns, end_ns, "NAVIGATION")
        >>> metrics = monitor.get_fatigue_metrics("crew_001")
        >>> alerts = monitor.get_fatigue_alerts()
    """

    def __init__(
        self,
        vessel_id: str,
        data_dir: str | Path = "crew_fatigue_data",
    ):
        """Initialize the crew fatigue monitor.

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
        self._crew: dict[str, CrewMember] = {}
        self._work_hours: list[WorkHours] = []
        self._watch_schedules: dict[str, list[WatchSchedule]] = {}
        self._alerts: list[FatigueAlert] = []

        # JSONL file paths
        self._crew_file = self.data_dir / "crew.jsonl"
        self._work_hours_file = self.data_dir / "work_hours.jsonl"
        self._alerts_file = self.data_dir / "fatigue_alerts.jsonl"

        # Load existing data
        self._load_data()

    def _load_data(self) -> None:
        """Load persisted data from JSONL files."""
        # Load crew members
        if self._crew_file.exists():
            with open(self._crew_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            crew = CrewMember.from_dict(data)
                            self._crew[crew.crew_id] = crew
                        except (json.JSONDecodeError, KeyError, ValueError) as e:
                            continue

        # Load work hours
        if self._work_hours_file.exists():
            with open(self._work_hours_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            work = WorkHours.from_dict(data)
                            self._work_hours.append(work)
                        except (json.JSONDecodeError, KeyError, ValueError) as e:
                            continue

        # Load alerts
        if self._alerts_file.exists():
            with open(self._alerts_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            alert = FatigueAlert.from_dict(data)
                            self._alerts.append(alert)
                        except (json.JSONDecodeError, KeyError, ValueError) as e:
                            continue

    def _persist_crew(self, crew: CrewMember) -> None:
        """Append crew member to JSONL file."""
        with open(self._crew_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(crew.to_dict()) + "\n")

    def _persist_work_hours(self, work: WorkHours) -> None:
        """Append work hours to JSONL file."""
        with open(self._work_hours_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(work.to_dict()) + "\n")

    def _persist_alert(self, alert: FatigueAlert) -> None:
        """Append alert to JSONL file."""
        with open(self._alerts_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(alert.to_dict()) + "\n")

    def add_crew_member(
        self,
        crew_id: str,
        name: str,
        role: str,
        status: CrewStatus | str = CrewStatus.ACTIVE,
    ) -> CrewMember:
        """Add a crew member to the monitor.

        Args:
            crew_id: Unique identifier for the crew member
            name: Full name of the crew member
            role: Role on the vessel
            status: Current availability status

        Returns:
            The created CrewMember object

        Raises:
            ValueError: If crew_id already exists
        """
        if crew_id in self._crew:
            raise ValueError(f"Crew member {crew_id} already exists")

        if isinstance(status, str):
            status = CrewStatus(status)

        crew = CrewMember(
            crew_id=crew_id,
            name=name,
            role=role,
            vessel_id=self.vessel_id,
            status=status,
        )
        self._crew[crew_id] = crew
        self._persist_crew(crew)
        return crew

    def get_crew_member(self, crew_id: str) -> CrewMember | None:
        """Get a crew member by ID.

        Args:
            crew_id: Crew member identifier

        Returns:
            CrewMember object or None if not found
        """
        return self._crew.get(crew_id)

    def list_crew_members(self) -> list[CrewMember]:
        """List all crew members.

        Returns:
            List of CrewMember objects
        """
        return list(self._crew.values())

    def update_crew_status(
        self,
        crew_id: str,
        status: CrewStatus | str,
    ) -> bool:
        """Update crew member status.

        Args:
            crew_id: Crew member identifier
            status: New status

        Returns:
            True if updated, False if crew member not found
        """
        crew = self._crew.get(crew_id)
        if not crew:
            return False

        if isinstance(status, str):
            status = CrewStatus(status)

        crew.status = status
        self._persist_crew(crew)
        return True

    def log_work_period(
        self,
        crew_id: str,
        start_time_ns: int,
        end_time_ns: int,
        activity_type: ActivityType | str,
        watch_position: str | None = None,
    ) -> WorkHours:
        """Log a work period for a crew member.

        Args:
            crew_id: Crew member identifier
            start_time_ns: Work period start timestamp (nanoseconds)
            end_time_ns: Work period end timestamp (nanoseconds)
            activity_type: Type of work performed
            watch_position: Watch position (if applicable)

        Returns:
            The created WorkHours object

        Raises:
            ValueError: If crew member not found or validation fails
        """
        if crew_id not in self._crew:
            raise ValueError(f"Crew member {crew_id} not found")

        if isinstance(activity_type, str):
            activity_type = ActivityType(activity_type)

        work = WorkHours(
            crew_id=crew_id,
            start_time_ns=start_time_ns,
            end_time_ns=end_time_ns,
            activity_type=activity_type,
            watch_position=watch_position,
        )
        self._work_hours.append(work)
        self._persist_work_hours(work)

        # Check for fatigue alerts
        self._check_fatigue_alerts(crew_id)

        return work

    def log_break(
        self,
        crew_id: str,
        start_time_ns: int,
        duration_ns: int,
    ) -> WorkHours:
        """Log a break period for a crew member.

        Args:
            crew_id: Crew member identifier
            start_time_ns: Break start timestamp (nanoseconds)
            duration_ns: Break duration in nanoseconds

        Returns:
            The created WorkHours object with REST activity type

        Raises:
            ValueError: If crew member not found or validation fails
        """
        if crew_id not in self._crew:
            raise ValueError(f"Crew member {crew_id} not found")

        return self.log_work_period(
            crew_id=crew_id,
            start_time_ns=start_time_ns,
            end_time_ns=start_time_ns + duration_ns,
            activity_type=ActivityType.REST,
            watch_position=None,
        )

    def get_work_hours(
        self,
        crew_id: str,
        since_ns: int | None = None,
        until_ns: int | None = None,
    ) -> list[WorkHours]:
        """Get work hours for a crew member.

        Args:
            crew_id: Crew member identifier
            since_ns: Filter by start time >= this timestamp (nanoseconds)
            until_ns: Filter by end time <= this timestamp (nanoseconds)

        Returns:
            List of WorkHours objects matching the filters
        """
        work_periods = [w for w in self._work_hours if w.crew_id == crew_id]

        if since_ns is not None:
            work_periods = [w for w in work_periods if w.start_time_ns >= since_ns]

        if until_ns is not None:
            work_periods = [w for w in work_periods if w.end_time_ns <= until_ns]

        return work_periods

    def _calculate_work_hours_in_window(
        self,
        crew_id: str,
        now_ns: int,
        window_ns: int,
    ) -> float:
        """Calculate total work hours in a time window (excluding REST).

        Args:
            crew_id: Crew member identifier
            now_ns: Current timestamp (nanoseconds)
            window_ns: Window duration in nanoseconds

        Returns:
            Total work hours in the window (excluding REST periods)
        """
        start_window = now_ns - window_ns
        work_periods = self.get_work_hours(crew_id, since_ns=start_window, until_ns=now_ns)

        total_hours = 0.0
        for work in work_periods:
            # Skip REST periods when calculating work hours
            if work.activity_type == ActivityType.REST:
                continue

            # Calculate overlap with window
            work_start = max(work.start_time_ns, start_window)
            work_end = min(work.end_time_ns, now_ns)
            if work_end > work_start:
                total_hours += (work_end - work_start) / (3600e9)

        return total_hours

    def _calculate_rest_hours_in_window(
        self,
        crew_id: str,
        now_ns: int,
        window_ns: int,
    ) -> float:
        """Calculate total rest hours in a time window.

        Args:
            crew_id: Crew member identifier
            now_ns: Current timestamp (nanoseconds)
            window_ns: Window duration in nanoseconds

        Returns:
            Total rest hours in the window
        """
        start_window = now_ns - window_ns
        work_periods = self.get_work_hours(crew_id, since_ns=start_window, until_ns=now_ns)

        rest_hours = 0.0
        for work in work_periods:
            if work.activity_type == ActivityType.REST:
                work_start = max(work.start_time_ns, start_window)
                work_end = min(work.end_time_ns, now_ns)
                if work_end > work_start:
                    rest_hours += (work_end - work_start) / (3600e9)

        return rest_hours

    def _get_continuous_work_hours(self, crew_id: str, now_ns: int) -> int:
        """Get duration of current continuous work period.

        Args:
            crew_id: Crew member identifier
            now_ns: Current timestamp (nanoseconds)

        Returns:
            Duration of continuous work in nanoseconds
        """
        work_periods = self.get_work_hours(crew_id, since_ns=0, until_ns=now_ns)
        if not work_periods:
            return 0

        # Find the most recent work period
        most_recent = max(work_periods, key=lambda w: w.end_time_ns)

        # If it's a REST period, no continuous work
        if most_recent.activity_type == ActivityType.REST:
            return 0

        # Look back to find the start of continuous work
        continuous_start = most_recent.start_time_ns
        for work in sorted(work_periods, key=lambda w: w.end_time_ns, reverse=True)[1:]:
            if work.activity_type == ActivityType.REST:
                break
            continuous_start = min(continuous_start, work.start_time_ns)

        return now_ns - continuous_start

    def _calculate_watch_compliance(
        self,
        crew_id: str,
        now_ns: int,
    ) -> float:
        """Calculate watch schedule compliance score (0-1).

        Args:
            crew_id: Crew member identifier
            now_ns: Current timestamp (nanoseconds)

        Returns:
            Compliance score between 0 and 1
        """
        schedules = self._watch_schedules.get(crew_id, [])
        if not schedules:
            return 1.0  # No schedule defined, assume compliant

        work_periods = self.get_work_hours(crew_id, since_ns=0, until_ns=now_ns)
        if not work_periods:
            return 1.0

        # Simple compliance: check if work periods match watch schedule
        # For now, return 1.0 if any schedule is defined
        # A full implementation would check work periods against scheduled times
        return 1.0

    def get_fatigue_score(self, crew_id: str, now_ns: int | None = None) -> float:
        """Calculate fatigue score for a crew member (0-100).

        Fatigue score is based on:
        - Cumulative work hours (24h, 48h, 72h windows)
        - Rest period quality and duration
        - Continuous work duration
        - Activity type weighting

        Args:
            crew_id: Crew member identifier
            now_ns: Current timestamp (nanoseconds), defaults to current time

        Returns:
            Fatigue score between 0 and 100

        Raises:
            ValueError: If crew member not found
        """
        if crew_id not in self._crew:
            raise ValueError(f"Crew member {crew_id} not found")

        if now_ns is None:
            now_ns = time.time_ns()

        # Calculate work hours in different windows
        hours_24h = self._calculate_work_hours_in_window(crew_id, now_ns, WINDOW_24H)
        hours_48h = self._calculate_work_hours_in_window(crew_id, now_ns, WINDOW_48H)
        hours_72h = self._calculate_work_hours_in_window(crew_id, now_ns, WINDOW_72H)

        # Calculate rest hours
        rest_24h = self._calculate_rest_hours_in_window(crew_id, now_ns, WINDOW_24H)

        # Continuous work duration
        continuous_work_ns = self._get_continuous_work_hours(crew_id, now_ns)
        continuous_hours = continuous_work_ns / (3600e9)

        # Calculate weighted work hours (considering activity types)
        work_periods = self.get_work_hours(crew_id, since_ns=now_ns - WINDOW_24H, until_ns=now_ns)
        weighted_hours = 0.0
        for work in work_periods:
            weight = ACTIVITY_WEIGHTS.get(work.activity_type.value, 1.0)
            weighted_hours += work.duration_hours * weight

        # Base fatigue from work hours
        work_fatigue = min(100, (weighted_hours / 24.0) * 50)

        # Fatigue from lack of rest
        rest_deficit = max(0, 8.0 - rest_24h)  # Need 8 hours rest
        rest_fatigue = min(100, (rest_deficit / 8.0) * 30)

        # Fatigue from continuous work
        continuous_fatigue = min(100, (continuous_hours / 16.0) * 20)

        # Total fatigue score
        fatigue_score = work_fatigue + rest_fatigue + continuous_fatigue

        return round(min(100, fatigue_score), 2)

    def get_fatigue_metrics(self, crew_id: str, now_ns: int | None = None) -> FatigueMetrics:
        """Get comprehensive fatigue metrics for a crew member.

        Args:
            crew_id: Crew member identifier
            now_ns: Current timestamp (nanoseconds), defaults to current time

        Returns:
            FatigueMetrics object

        Raises:
            ValueError: If crew member not found
        """
        if crew_id not in self._crew:
            raise ValueError(f"Crew member {crew_id} not found")

        if now_ns is None:
            now_ns = time.time_ns()

        fatigue_score = self.get_fatigue_score(crew_id, now_ns)
        hours_worked_24h = self._calculate_work_hours_in_window(crew_id, now_ns, WINDOW_24H)
        hours_worked_48h = self._calculate_work_hours_in_window(crew_id, now_ns, WINDOW_48H)
        hours_worked_72h = self._calculate_work_hours_in_window(crew_id, now_ns, WINDOW_72H)
        hours_rest_24h = self._calculate_rest_hours_in_window(crew_id, now_ns, WINDOW_24H)
        continuous_work_ns = self._get_continuous_work_hours(crew_id, now_ns)
        watch_compliance = self._calculate_watch_compliance(crew_id, now_ns)

        # Find last break
        work_periods = self.get_work_hours(crew_id, since_ns=0, until_ns=now_ns)
        last_break_ns = None
        for work in sorted(work_periods, key=lambda w: w.end_time_ns, reverse=True):
            if work.activity_type == ActivityType.REST:
                last_break_ns = work.end_time_ns
                break

        return FatigueMetrics(
            crew_id=crew_id,
            fatigue_score=fatigue_score,
            hours_worked_24h=hours_worked_24h,
            hours_worked_48h=hours_worked_48h,
            hours_worked_72h=hours_worked_72h,
            hours_rest_24h=hours_rest_24h,
            last_break_ns=last_break_ns,
            continuous_work_ns=continuous_work_ns,
            watch_compliance=watch_compliance,
        )

    def get_all_fatigue_metrics(self, now_ns: int | None = None) -> dict[str, FatigueMetrics]:
        """Get fatigue metrics for all crew members.

        Args:
            now_ns: Current timestamp (nanoseconds), defaults to current time

        Returns:
            Dictionary mapping crew_id to FatigueMetrics
        """
        metrics = {}
        for crew_id in self._crew:
            try:
                metrics[crew_id] = self.get_fatigue_metrics(crew_id, now_ns)
            except ValueError:
                continue  # Skip crew members with errors
        return metrics

    def _check_fatigue_alerts(self, crew_id: str, now_ns: int | None = None) -> list[FatigueAlert]:
        """Check for fatigue alerts and generate them if thresholds exceeded.

        Args:
            crew_id: Crew member identifier
            now_ns: Current timestamp (nanoseconds)

        Returns:
            List of generated FatigueAlert objects
        """
        if now_ns is None:
            now_ns = time.time_ns()

        metrics = self.get_fatigue_metrics(crew_id, now_ns)
        alerts = []

        # Check for HIGH continuous work (>12 hours)
        if metrics.continuous_work_ns > FATIGUE_THRESHOLD_HIGH:
            alert = FatigueAlert(
                crew_id=crew_id,
                alert_type=AlertType.CONTINUOUS_WORK_HIGH,
                severity=AlertSeverity.HIGH,
                fatigue_score=metrics.fatigue_score,
                timestamp_ns=now_ns,
                message=f"Continuous work exceeds 12 hours: {metrics.continuous_work_ns / (3600e9):.1f}h",
                metrics=metrics.to_dict(),
            )
            alerts.append(alert)
            self._alerts.append(alert)
            self._persist_alert(alert)

        # Check for CRITICAL continuous work (>16 hours)
        if metrics.continuous_work_ns > FATIGUE_THRESHOLD_CRITICAL:
            alert = FatigueAlert(
                crew_id=crew_id,
                alert_type=AlertType.CONTINUOUS_WORK_CRITICAL,
                severity=AlertSeverity.CRITICAL,
                fatigue_score=metrics.fatigue_score,
                timestamp_ns=now_ns,
                message=f"CRITICAL: Continuous work exceeds 16 hours: {metrics.continuous_work_ns / (3600e9):.1f}h",
                metrics=metrics.to_dict(),
            )
            alerts.append(alert)
            self._alerts.append(alert)
            self._persist_alert(alert)

        # Check for DANGER: >24 hours without 8-hour rest
        if metrics.last_break_ns is not None:
            time_since_break = now_ns - metrics.last_break_ns
            if time_since_break > FATIGUE_THRESHOLD_DANGER:
                # Check if had adequate rest in that period
                if metrics.hours_rest_24h < 8.0:
                    alert = FatigueAlert(
                        crew_id=crew_id,
                        alert_type=AlertType.INSUFFICIENT_REST_DANGER,
                        severity=AlertSeverity.DANGER,
                        fatigue_score=metrics.fatigue_score,
                        timestamp_ns=now_ns,
                        message=f"DANGER: >24h without adequate 8h rest (last rest: {time_since_break / (3600e9):.1f}h ago)",
                        metrics=metrics.to_dict(),
                    )
                    alerts.append(alert)
                    self._alerts.append(alert)
                    self._persist_alert(alert)

        # Check for MULTIPLE fatigue: >72 hours with <24-hour rest
        if metrics.hours_worked_72h > 72.0 and metrics.hours_rest_24h < 24.0:
            alert = FatigueAlert(
                crew_id=crew_id,
                alert_type=AlertType.MULTIPLE_FATIGUE,
                severity=AlertSeverity.CRITICAL,
                fatigue_score=metrics.fatigue_score,
                timestamp_ns=now_ns,
                message=f"CRITICAL: >72h work with <24h rest in last 24h",
                metrics=metrics.to_dict(),
            )
            alerts.append(alert)
            self._alerts.append(alert)
            self._persist_alert(alert)

        return alerts

    def get_fatigue_alerts(
        self,
        crew_id: str | None = None,
        since_ns: int | None = None,
        min_severity: AlertSeverity | None = None,
    ) -> list[FatigueAlert]:
        """Get fatigue alerts, optionally filtered.

        Args:
            crew_id: Filter by crew member (None for all)
            since_ns: Filter by timestamp >= this (nanoseconds)
            min_severity: Filter by minimum severity level

        Returns:
            List of FatigueAlert objects matching filters
        """
        alerts = self._alerts

        if crew_id is not None:
            alerts = [a for a in alerts if a.crew_id == crew_id]

        if since_ns is not None:
            alerts = [a for a in alerts if a.timestamp_ns >= since_ns]

        if min_severity is not None:
            severity_order = [
                AlertSeverity.INFO,
                AlertSeverity.LOW,
                AlertSeverity.MEDIUM,
                AlertSeverity.HIGH,
                AlertSeverity.CRITICAL,
                AlertSeverity.DANGER,
            ]
            try:
                min_idx = severity_order.index(min_severity)
                alerts = [a for a in alerts if severity_order.index(a.severity) >= min_idx]
            except ValueError:
                pass  # Invalid severity, return all

        return sorted(alerts, key=lambda a: a.timestamp_ns, reverse=True)

    def set_watch_schedule(
        self,
        crew_id: str,
        watch_type: WatchType | str,
        start_time_ns: int,
        duration_ns: int = 0,
        rotation_ns: int = 0,
        custom_name: str | None = None,
    ) -> WatchSchedule:
        """Set a watch schedule for a crew member.

        Args:
            crew_id: Crew member identifier
            watch_type: Type of watch rotation
            start_time_ns: Watch start timestamp (nanoseconds)
            duration_ns: Watch duration in nanoseconds (0 for default based on type)
            rotation_ns: Rotation period in nanoseconds (0 for default based on type)
            custom_name: Name for custom watch types

        Returns:
            The created WatchSchedule object

        Raises:
            ValueError: If crew member not found or validation fails
        """
        if crew_id not in self._crew:
            raise ValueError(f"Crew member {crew_id} not found")

        if isinstance(watch_type, str):
            watch_type = WatchType(watch_type)

        schedule = WatchSchedule(
            crew_id=crew_id,
            watch_type=watch_type,
            start_time_ns=start_time_ns,
            duration_ns=duration_ns,
            rotation_ns=rotation_ns,
            custom_name=custom_name,
        )

        if crew_id not in self._watch_schedules:
            self._watch_schedules[crew_id] = []

        self._watch_schedules[crew_id].append(schedule)
        return schedule

    def get_watch_schedules(self, crew_id: str) -> list[WatchSchedule]:
        """Get watch schedules for a crew member.

        Args:
            crew_id: Crew member identifier

        Returns:
            List of WatchSchedule objects

        Raises:
            ValueError: If crew member not found
        """
        if crew_id not in self._crew:
            raise ValueError(f"Crew member {crew_id} not found")

        return self._watch_schedules.get(crew_id, [])

    def predict_fatigue_risk(
        self,
        crew_id: str,
        future_work_hours: float,
        now_ns: int | None = None,
    ) -> float:
        """Predict fatigue risk for planned future work.

        Args:
            crew_id: Crew member identifier
            future_work_hours: Additional work hours being planned
            now_ns: Current timestamp (nanoseconds)

        Returns:
            Predicted fatigue score (0-100)

        Raises:
            ValueError: If crew member not found
        """
        if crew_id not in self._crew:
            raise ValueError(f"Crew member {crew_id} not found")

        if now_ns is None:
            now_ns = time.time_ns()

        # Get current metrics
        current_metrics = self.get_fatigue_metrics(crew_id, now_ns)

        # Predict future fatigue
        # Simple model: add future hours to current work hours
        future_work_24h = current_metrics.hours_worked_24h + future_work_hours

        # Calculate predicted fatigue
        predicted_rest = max(0, 24.0 - future_work_24h)
        rest_deficit = max(0, 8.0 - predicted_rest)
        predicted_fatigue = min(100, (future_work_24h / 24.0) * 50 + (rest_deficit / 8.0) * 30)

        return round(predicted_fatigue, 2)

    def to_dict(self, now_ns: int | None = None) -> dict[str, Any]:
        """Create a snapshot of the monitor state.

        Args:
            now_ns: Current timestamp (nanoseconds), defaults to current time

        Returns:
            Dictionary containing monitor state
        """
        if now_ns is None:
            now_ns = time.time_ns()

        return {
            "vessel_id": self.vessel_id,
            "timestamp_ns": now_ns,
            "crew_count": len(self._crew),
            "crew_members": [c.to_dict() for c in self._crew.values()],
            "fatigue_metrics": {
                crew_id: metrics.to_dict()
                for crew_id, metrics in self.get_all_fatigue_metrics(now_ns).items()
            },
            "recent_alerts": [a.to_dict() for a in self.get_fatigue_alerts(since_ns=now_ns - (24 * 3600e9))],
        }
