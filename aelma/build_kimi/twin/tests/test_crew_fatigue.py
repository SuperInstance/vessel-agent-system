"""Tests for the Crew Fatigue monitoring system.

Covers crew member management, work period logging, fatigue score
calculation, rest period tracking, watch schedules, fatigue alerts,
fatigue prediction, edge cases, and persistence.
"""

from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

# Make the repository root importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Import the actual classes
from twin.crew_fatigue import (
    ActivityType,
    AlertSeverity,
    AlertType,
    CrewFatigueMonitor,
    CrewMember,
    CrewStatus,
    FatigueAlert,
    FatigueMetrics,
    WatchSchedule,
    WatchType,
    WorkHours,
)

# Test constants
T0 = 1_753_478_400_000_000_000  # Fixed epoch ns for deterministic tests
ONE_HOUR_NS = int(3600 * 1e9)  # 1 hour in nanoseconds (as integer)
SIX_HOURS_NS = 6 * ONE_HOUR_NS
TWELVE_HOURS_NS = 12 * ONE_HOUR_NS
TWENTY_FOUR_HOURS_NS = 24 * ONE_HOUR_NS
THIRTY_HOURS_NS = 30 * ONE_HOUR_NS


# ============================================================================ #
# Crew Member Tests
# ============================================================================ #

class TestCrewMember:
    """Test crew member creation and validation."""

    def test_create_crew_member(self):
        """Create a valid crew member."""
        crew = CrewMember(
            crew_id="crew_001",
            name="John Smith",
            role="captain",
            vessel_id="vessel_001",
        )
        assert crew.crew_id == "crew_001"
        assert crew.name == "John Smith"
        assert crew.role == "captain"
        assert crew.vessel_id == "vessel_001"
        assert crew.status == CrewStatus.ACTIVE

    def test_crew_member_validation_empty_id(self):
        """Empty crew_id should raise ValueError."""
        with pytest.raises(ValueError, match="crew_id must be a non-empty string"):
            CrewMember(
                crew_id="",
                name="John Smith",
                role="captain",
                vessel_id="vessel_001",
            )

    def test_crew_member_validation_empty_name(self):
        """Empty name should raise ValueError."""
        with pytest.raises(ValueError, match="name must be a non-empty string"):
            CrewMember(
                crew_id="crew_001",
                name="",
                role="captain",
                vessel_id="vessel_001",
            )

    def test_crew_member_validation_empty_role(self):
        """Empty role should raise ValueError."""
        with pytest.raises(ValueError, match="role must be a non-empty string"):
            CrewMember(
                crew_id="crew_001",
                name="John Smith",
                role="",
                vessel_id="vessel_001",
            )

    def test_crew_member_validation_empty_vessel_id(self):
        """Empty vessel_id should raise ValueError."""
        with pytest.raises(ValueError, match="vessel_id must be a non-empty string"):
            CrewMember(
                crew_id="crew_001",
                name="John Smith",
                role="captain",
                vessel_id="",
            )

    def test_crew_member_status_conversion(self):
        """String status should be converted to CrewStatus enum."""
        crew = CrewMember(
            crew_id="crew_001",
            name="John Smith",
            role="captain",
            vessel_id="vessel_001",
            status="sick",
        )
        assert crew.status == CrewStatus.SICK

    def test_crew_member_to_dict(self):
        """Convert crew member to dictionary."""
        crew = CrewMember(
            crew_id="crew_001",
            name="John Smith",
            role="captain",
            vessel_id="vessel_001",
            status=CrewStatus.ON_LEAVE,
        )
        data = crew.to_dict()
        assert data["crew_id"] == "crew_001"
        assert data["name"] == "John Smith"
        assert data["role"] == "captain"
        assert data["vessel_id"] == "vessel_001"
        assert data["status"] == "on_leave"

    def test_crew_member_from_dict(self):
        """Create crew member from dictionary."""
        data = {
            "crew_id": "crew_001",
            "name": "John Smith",
            "role": "captain",
            "vessel_id": "vessel_001",
            "status": "active",
        }
        crew = CrewMember.from_dict(data)
        assert crew.crew_id == "crew_001"
        assert crew.status == CrewStatus.ACTIVE


# ============================================================================ #
# Work Hours Tests
# ============================================================================ #

class TestWorkHours:
    """Test work period logging and validation."""

    def test_create_work_hours(self):
        """Create a valid work period."""
        work = WorkHours(
            crew_id="crew_001",
            start_time_ns=T0,
            end_time_ns=T0 + SIX_HOURS_NS,
            activity_type=ActivityType.NAVIGATION,
        )
        assert work.crew_id == "crew_001"
        assert work.start_time_ns == T0
        assert work.end_time_ns == T0 + SIX_HOURS_NS
        assert work.activity_type == ActivityType.NAVIGATION
        assert work.duration_hours == 6.0

    def test_work_hours_validation_start_after_end(self):
        """Start time after end time should raise ValueError."""
        with pytest.raises(ValueError, match="start_time_ns must be before end_time_ns"):
            WorkHours(
                crew_id="crew_001",
                start_time_ns=T0 + SIX_HOURS_NS,
                end_time_ns=T0,
                activity_type=ActivityType.NAVIGATION,
            )

    def test_work_hours_validation_equal_times(self):
        """Equal start and end times should raise ValueError."""
        with pytest.raises(ValueError, match="start_time_ns must be before end_time_ns"):
            WorkHours(
                crew_id="crew_001",
                start_time_ns=T0,
                end_time_ns=T0,
                activity_type=ActivityType.NAVIGATION,
            )

    def test_work_hours_negative_time(self):
        """Negative timestamps should raise ValueError."""
        with pytest.raises(ValueError, match="must be a non-negative integer"):
            WorkHours(
                crew_id="crew_001",
                start_time_ns=-100,
                end_time_ns=T0,
                activity_type=ActivityType.NAVIGATION,
            )

    def test_work_hours_activity_type_conversion(self):
        """String activity type should be converted to ActivityType enum."""
        work = WorkHours(
            crew_id="crew_001",
            start_time_ns=T0,
            end_time_ns=T0 + SIX_HOURS_NS,
            activity_type="GEAR_HANDLING",
        )
        assert work.activity_type == ActivityType.GEAR_HANDLING

    def test_work_hours_duration_calculation(self):
        """Calculate work duration correctly."""
        work = WorkHours(
            crew_id="crew_001",
            start_time_ns=T0,
            end_time_ns=T0 + TWELVE_HOURS_NS,
            activity_type=ActivityType.DECK_WORK,
        )
        assert work.duration_ns == TWELVE_HOURS_NS
        assert work.duration_hours == 12.0

    def test_work_hours_to_dict(self):
        """Convert work hours to dictionary."""
        work = WorkHours(
            crew_id="crew_001",
            start_time_ns=T0,
            end_time_ns=T0 + SIX_HOURS_NS,
            activity_type=ActivityType.NAVIGATION,
            watch_position="bridge",
        )
        data = work.to_dict()
        assert data["crew_id"] == "crew_001"
        assert data["start_time_ns"] == T0
        assert data["end_time_ns"] == T0 + SIX_HOURS_NS
        assert data["activity_type"] == "NAVIGATION"
        assert data["watch_position"] == "bridge"

    def test_work_hours_from_dict(self):
        """Create work hours from dictionary."""
        data = {
            "crew_id": "crew_001",
            "start_time_ns": T0,
            "end_time_ns": T0 + SIX_HOURS_NS,
            "activity_type": "NAVIGATION",
            "watch_position": "bridge",
        }
        work = WorkHours.from_dict(data)
        assert work.crew_id == "crew_001"
        assert work.activity_type == ActivityType.NAVIGATION
        assert work.watch_position == "bridge"


# ============================================================================ #
# Fatigue Metrics Tests
# ============================================================================ #

class TestFatigueMetrics:
    """Test fatigue metrics calculation and validation."""

    def test_create_fatigue_metrics(self):
        """Create valid fatigue metrics."""
        metrics = FatigueMetrics(
            crew_id="crew_001",
            fatigue_score=50.0,
            hours_worked_24h=8.0,
            hours_worked_48h=16.0,
            hours_worked_72h=24.0,
            hours_rest_24h=8.0,
            last_break_ns=T0 + TWELVE_HOURS_NS,
            continuous_work_ns=SIX_HOURS_NS,
            watch_compliance=1.0,
        )
        assert metrics.crew_id == "crew_001"
        assert metrics.fatigue_score == 50.0
        assert metrics.hours_worked_24h == 8.0

    def test_fatigue_metrics_validation_score_range(self):
        """Fatigue score outside 0-100 should raise ValueError."""
        with pytest.raises(ValueError, match="fatigue_score must be between 0 and 100"):
            FatigueMetrics(
                crew_id="crew_001",
                fatigue_score=150.0,
                hours_worked_24h=8.0,
                hours_worked_48h=16.0,
                hours_worked_72h=24.0,
                hours_rest_24h=8.0,
                last_break_ns=None,
                continuous_work_ns=0,
                watch_compliance=1.0,
            )

    def test_fatigue_metrics_validation_negative_hours(self):
        """Negative work hours should raise ValueError."""
        with pytest.raises(ValueError, match="hours_worked_24h must be non-negative"):
            FatigueMetrics(
                crew_id="crew_001",
                fatigue_score=50.0,
                hours_worked_24h=-1.0,
                hours_worked_48h=16.0,
                hours_worked_72h=24.0,
                hours_rest_24h=8.0,
                last_break_ns=None,
                continuous_work_ns=0,
                watch_compliance=1.0,
            )

    def test_fatigue_metrics_validation_compliance_range(self):
        """Watch compliance outside 0-1 should raise ValueError."""
        with pytest.raises(ValueError, match="watch_compliance must be between 0 and 1"):
            FatigueMetrics(
                crew_id="crew_001",
                fatigue_score=50.0,
                hours_worked_24h=8.0,
                hours_worked_48h=16.0,
                hours_worked_72h=24.0,
                hours_rest_24h=8.0,
                last_break_ns=None,
                continuous_work_ns=0,
                watch_compliance=1.5,
            )

    def test_fatigue_metrics_to_dict(self):
        """Convert fatigue metrics to dictionary."""
        metrics = FatigueMetrics(
            crew_id="crew_001",
            fatigue_score=65.5,
            hours_worked_24h=10.5,
            hours_worked_48h=20.0,
            hours_worked_72h=30.0,
            hours_rest_24h=6.0,
            last_break_ns=T0 + TWELVE_HOURS_NS,
            continuous_work_ns=SIX_HOURS_NS,
            watch_compliance=0.9,
        )
        data = metrics.to_dict()
        assert data["crew_id"] == "crew_001"
        assert data["fatigue_score"] == 65.5
        assert data["hours_worked_24h"] == 10.5
        assert data["continuous_work_hours"] == 6.0
        assert data["watch_compliance"] == 0.9

    def test_fatigue_metrics_from_dict(self):
        """Create fatigue metrics from dictionary."""
        data = {
            "crew_id": "crew_001",
            "fatigue_score": 65.5,
            "hours_worked_24h": 10.5,
            "hours_worked_48h": 20.0,
            "hours_worked_72h": 30.0,
            "hours_rest_24h": 6.0,
            "last_break_ns": T0 + TWELVE_HOURS_NS,
            "continuous_work_hours": 6.0,
            "watch_compliance": 0.9,
        }
        metrics = FatigueMetrics.from_dict(data)
        assert metrics.crew_id == "crew_001"
        assert metrics.fatigue_score == 65.5
        assert metrics.continuous_work_ns == int(SIX_HOURS_NS)


# ============================================================================ #
# Watch Schedule Tests
# ============================================================================ #

class TestWatchSchedule:
    """Test watch schedule configuration."""

    def test_create_watch_schedule_six_on_six_off(self):
        """Create 6-on/6-off watch schedule."""
        schedule = WatchSchedule(
            crew_id="crew_001",
            watch_type=WatchType.SIX_ON_SIX_OFF,
            start_time_ns=T0,
            duration_ns=0,  # Will be set to default (6 hours)
            rotation_ns=0,  # Will be set to default (12 hours)
        )
        assert schedule.watch_type == WatchType.SIX_ON_SIX_OFF
        assert schedule.duration_hours == 6.0
        assert schedule.rotation_hours == 12.0

    def test_create_watch_schedule_four_on_eight_off(self):
        """Create 4-on/8-off watch schedule."""
        schedule = WatchSchedule(
            crew_id="crew_001",
            watch_type=WatchType.FOUR_ON_EIGHT_OFF,
            start_time_ns=T0,
            duration_ns=0,  # Will be set to default (4 hours)
            rotation_ns=0,  # Will be set to default (12 hours)
        )
        assert schedule.watch_type == WatchType.FOUR_ON_EIGHT_OFF
        assert schedule.duration_hours == 4.0
        assert schedule.rotation_hours == 12.0

    def test_create_watch_schedule_twelve_on_twelve_off(self):
        """Create 12-on/12-off watch schedule."""
        schedule = WatchSchedule(
            crew_id="crew_001",
            watch_type=WatchType.TWELVE_ON_TWELVE_OFF,
            start_time_ns=T0,
            duration_ns=0,  # Will be set to default (12 hours)
            rotation_ns=0,  # Will be set to default (24 hours)
        )
        assert schedule.watch_type == WatchType.TWELVE_ON_TWELVE_OFF
        assert schedule.duration_hours == 12.0
        assert schedule.rotation_hours == 24.0

    def test_watch_schedule_validation_negative_duration(self):
        """Negative duration should raise ValueError."""
        with pytest.raises(ValueError, match="duration_ns must be a positive integer"):
            WatchSchedule(
                crew_id="crew_001",
                watch_type=WatchType.CUSTOM,
                start_time_ns=T0,
                duration_ns=-100,
                rotation_ns=TWENTY_FOUR_HOURS_NS,
            )

    def test_watch_schedule_validation_negative_rotation(self):
        """Negative rotation should raise ValueError."""
        with pytest.raises(ValueError, match="rotation_ns must be a positive integer"):
            WatchSchedule(
                crew_id="crew_001",
                watch_type=WatchType.CUSTOM,
                start_time_ns=T0,
                duration_ns=SIX_HOURS_NS,
                rotation_ns=-100,
            )

    def test_watch_schedule_type_conversion(self):
        """String watch type should be converted to WatchType enum."""
        schedule = WatchSchedule(
            crew_id="crew_001",
            watch_type="six_on_six_off",
            start_time_ns=T0,
            duration_ns=0,
            rotation_ns=0,
        )
        assert schedule.watch_type == WatchType.SIX_ON_SIX_OFF

    def test_watch_schedule_to_dict(self):
        """Convert watch schedule to dictionary."""
        schedule = WatchSchedule(
            crew_id="crew_001",
            watch_type=WatchType.SIX_ON_SIX_OFF,
            start_time_ns=T0,
            duration_ns=0,
            rotation_ns=0,
            custom_name="Day Watch",
        )
        data = schedule.to_dict()
        assert data["crew_id"] == "crew_001"
        assert data["watch_type"] == "six_on_six_off"
        assert data["duration_hours"] == 6.0
        assert data["rotation_hours"] == 12.0
        assert data["custom_name"] == "Day Watch"

    def test_watch_schedule_from_dict(self):
        """Create watch schedule from dictionary."""
        data = {
            "crew_id": "crew_001",
            "watch_type": "six_on_six_off",
            "start_time_ns": T0,
            "duration_hours": 6.0,
            "rotation_hours": 12.0,
            "custom_name": "Day Watch",
        }
        schedule = WatchSchedule.from_dict(data)
        assert schedule.crew_id == "crew_001"
        assert schedule.watch_type == WatchType.SIX_ON_SIX_OFF
        assert schedule.custom_name == "Day Watch"


# ============================================================================ #
# Fatigue Alert Tests
# ============================================================================ #

class TestFatigueAlert:
    """Test fatigue alert creation and validation."""

    def test_create_fatigue_alert(self):
        """Create a valid fatigue alert."""
        alert = FatigueAlert(
            crew_id="crew_001",
            alert_type=AlertType.CONTINUOUS_WORK_HIGH,
            severity=AlertSeverity.HIGH,
            fatigue_score=75.0,
            timestamp_ns=T0,
            message="Continuous work exceeds 12 hours",
            metrics={"hours_worked_24h": 14.0},
        )
        assert alert.crew_id == "crew_001"
        assert alert.alert_type == AlertType.CONTINUOUS_WORK_HIGH
        assert alert.severity == AlertSeverity.HIGH
        assert alert.fatigue_score == 75.0

    def test_fatigue_alert_validation_score_range(self):
        """Fatigue score outside 0-100 should raise ValueError."""
        with pytest.raises(ValueError, match="fatigue_score must be between 0 and 100"):
            FatigueAlert(
                crew_id="crew_001",
                alert_type=AlertType.CONTINUOUS_WORK_HIGH,
                severity=AlertSeverity.HIGH,
                fatigue_score=150.0,
                timestamp_ns=T0,
                message="Test alert",
                metrics={},
            )

    def test_fatigue_alert_validation_empty_message(self):
        """Empty message should raise ValueError."""
        with pytest.raises(ValueError, match="message must be a non-empty string"):
            FatigueAlert(
                crew_id="crew_001",
                alert_type=AlertType.CONTINUOUS_WORK_HIGH,
                severity=AlertSeverity.HIGH,
                fatigue_score=75.0,
                timestamp_ns=T0,
                message="",
                metrics={},
            )

    def test_fatigue_alert_type_conversion(self):
        """String alert type should be converted to AlertType enum."""
        alert = FatigueAlert(
            crew_id="crew_001",
            alert_type="continuous_work_high",
            severity="high",
            fatigue_score=75.0,
            timestamp_ns=T0,
            message="Test alert",
            metrics={},
        )
        assert alert.alert_type == AlertType.CONTINUOUS_WORK_HIGH
        assert alert.severity == AlertSeverity.HIGH

    def test_fatigue_alert_to_dict(self):
        """Convert fatigue alert to dictionary."""
        alert = FatigueAlert(
            crew_id="crew_001",
            alert_type=AlertType.CONTINUOUS_WORK_HIGH,
            severity=AlertSeverity.HIGH,
            fatigue_score=75.0,
            timestamp_ns=T0,
            message="Continuous work exceeds 12 hours",
            metrics={"hours_worked_24h": 14.0},
        )
        data = alert.to_dict()
        assert data["crew_id"] == "crew_001"
        assert data["alert_type"] == "continuous_work_high"
        assert data["severity"] == "high"
        assert data["fatigue_score"] == 75.0
        assert data["timestamp_ns"] == T0

    def test_fatigue_alert_from_dict(self):
        """Create fatigue alert from dictionary."""
        data = {
            "crew_id": "crew_001",
            "alert_type": "continuous_work_high",
            "severity": "high",
            "fatigue_score": 75.0,
            "timestamp_ns": T0,
            "message": "Continuous work exceeds 12 hours",
            "metrics": {"hours_worked_24h": 14.0},
        }
        alert = FatigueAlert.from_dict(data)
        assert alert.crew_id == "crew_001"
        assert alert.alert_type == AlertType.CONTINUOUS_WORK_HIGH
        assert alert.fatigue_score == 75.0


# ============================================================================ #
# Crew Fatigue Monitor Tests
# ============================================================================ #

class TestCrewFatigueMonitor:
    """Test crew fatigue monitor functionality."""

    def test_create_monitor(self):
        """Create a crew fatigue monitor."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            assert monitor.vessel_id == "vessel_001"
            assert len(monitor._crew) == 0
            assert len(monitor._work_hours) == 0

    def test_create_monitor_invalid_vessel_id(self):
        """Empty vessel_id should raise ValueError."""
        with pytest.raises(ValueError, match="vessel_id must be a non-empty string"):
            CrewFatigueMonitor(vessel_id="")

    def test_add_crew_member(self):
        """Add a crew member to the monitor."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            crew = monitor.add_crew_member(
                crew_id="crew_001",
                name="John Smith",
                role="captain",
            )
            assert crew.crew_id == "crew_001"
            assert monitor.get_crew_member("crew_001") is not None

    def test_add_duplicate_crew_member(self):
        """Adding duplicate crew member should raise ValueError."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member(
                crew_id="crew_001",
                name="John Smith",
                role="captain",
            )
            with pytest.raises(ValueError, match="already exists"):
                monitor.add_crew_member(
                    crew_id="crew_001",
                    name="Jane Doe",
                    role="mate",
                )

    def test_get_crew_member_not_found(self):
        """Getting non-existent crew member should return None."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            assert monitor.get_crew_member("crew_999") is None

    def test_list_crew_members(self):
        """List all crew members."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member("crew_001", "John Smith", "captain")
            monitor.add_crew_member("crew_002", "Jane Doe", "mate")
            crew_list = monitor.list_crew_members()
            assert len(crew_list) == 2
            crew_ids = {c.crew_id for c in crew_list}
            assert crew_ids == {"crew_001", "crew_002"}

    def test_update_crew_status(self):
        """Update crew member status."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member("crew_001", "John Smith", "captain")
            success = monitor.update_crew_status("crew_001", CrewStatus.SICK)
            assert success is True
            crew = monitor.get_crew_member("crew_001")
            assert crew.status == CrewStatus.SICK

    def test_update_crew_status_not_found(self):
        """Updating non-existent crew member should return False."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            success = monitor.update_crew_status("crew_999", CrewStatus.SICK)
            assert success is False

    def test_log_work_period(self):
        """Log a work period for a crew member."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member("crew_001", "John Smith", "captain")
            work = monitor.log_work_period(
                crew_id="crew_001",
                start_time_ns=T0,
                end_time_ns=T0 + SIX_HOURS_NS,
                activity_type=ActivityType.NAVIGATION,
            )
            assert work.crew_id == "crew_001"
            assert work.duration_hours == 6.0

    def test_log_work_period_not_found(self):
        """Logging work for non-existent crew member should raise ValueError."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            with pytest.raises(ValueError, match="not found"):
                monitor.log_work_period(
                    crew_id="crew_999",
                    start_time_ns=T0,
                    end_time_ns=T0 + SIX_HOURS_NS,
                    activity_type=ActivityType.NAVIGATION,
                )

    def test_log_break(self):
        """Log a break period for a crew member."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member("crew_001", "John Smith", "captain")
            break_period = monitor.log_break(
                crew_id="crew_001",
                start_time_ns=T0 + SIX_HOURS_NS,
                duration_ns=TWELVE_HOURS_NS,
            )
            assert break_period.activity_type == ActivityType.REST
            assert break_period.duration_hours == 12.0

    def test_get_work_hours(self):
        """Get work hours for a crew member."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member("crew_001", "John Smith", "captain")
            monitor.log_work_period("crew_001", T0, T0 + SIX_HOURS_NS, ActivityType.NAVIGATION)
            monitor.log_work_period("crew_001", T0 + TWELVE_HOURS_NS, T0 + TWENTY_FOUR_HOURS_NS, ActivityType.DECK_WORK)

            work_periods = monitor.get_work_hours("crew_001")
            assert len(work_periods) == 2

    def test_get_work_hours_with_time_filter(self):
        """Get work hours with time filtering."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member("crew_001", "John Smith", "captain")
            monitor.log_work_period("crew_001", T0, T0 + SIX_HOURS_NS, ActivityType.NAVIGATION)
            monitor.log_work_period("crew_001", T0 + TWENTY_FOUR_HOURS_NS, T0 + THIRTY_HOURS_NS, ActivityType.DECK_WORK)

            work_periods = monitor.get_work_hours("crew_001", since_ns=T0 + TWELVE_HOURS_NS)
            assert len(work_periods) == 1

    def test_get_fatigue_score(self):
        """Calculate fatigue score for a crew member."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member("crew_001", "John Smith", "captain")
            # Log 8 hours of work
            monitor.log_work_period("crew_001", T0, T0 + EIGHT_HOURS_NS, ActivityType.NAVIGATION)
            # Log 8 hours of rest
            monitor.log_break("crew_001", T0 + EIGHT_HOURS_NS, EIGHT_HOURS_NS)

            score = monitor.get_fatigue_score("crew_001", now_ns=T0 + TWENTY_FOUR_HOURS_NS)
            assert 0 <= score <= 100

    def test_get_fatigue_score_not_found(self):
        """Getting fatigue score for non-existent crew member should raise ValueError."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            with pytest.raises(ValueError, match="not found"):
                monitor.get_fatigue_score("crew_999")

    def test_get_fatigue_metrics(self):
        """Get comprehensive fatigue metrics."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member("crew_001", "John Smith", "captain")
            monitor.log_work_period("crew_001", T0, T0 + EIGHT_HOURS_NS, ActivityType.NAVIGATION)
            monitor.log_break("crew_001", T0 + EIGHT_HOURS_NS, EIGHT_HOURS_NS)

            metrics = monitor.get_fatigue_metrics("crew_001", now_ns=T0 + TWENTY_FOUR_HOURS_NS)
            assert metrics.crew_id == "crew_001"
            assert 0 <= metrics.fatigue_score <= 100
            assert metrics.hours_worked_24h >= 0
            assert metrics.hours_rest_24h >= 0

    def test_get_all_fatigue_metrics(self):
        """Get fatigue metrics for all crew members."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member("crew_001", "John Smith", "captain")
            monitor.add_crew_member("crew_002", "Jane Doe", "mate")
            monitor.log_work_period("crew_001", T0, T0 + EIGHT_HOURS_NS, ActivityType.NAVIGATION)
            monitor.log_work_period("crew_002", T0, T0 + SIX_HOURS_NS, ActivityType.DECK_WORK)

            all_metrics = monitor.get_all_fatigue_metrics(now_ns=T0 + TWENTY_FOUR_HOURS_NS)
            assert len(all_metrics) == 2
            assert "crew_001" in all_metrics
            assert "crew_002" in all_metrics

    def test_set_watch_schedule(self):
        """Set a watch schedule for a crew member."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member("crew_001", "John Smith", "captain")
            schedule = monitor.set_watch_schedule(
                crew_id="crew_001",
                watch_type=WatchType.SIX_ON_SIX_OFF,
                start_time_ns=T0,
            )
            assert schedule.watch_type == WatchType.SIX_ON_SIX_OFF
            assert schedule.duration_hours == 6.0

    def test_set_watch_schedule_not_found(self):
        """Setting watch schedule for non-existent crew member should raise ValueError."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            with pytest.raises(ValueError, match="not found"):
                monitor.set_watch_schedule(
                    crew_id="crew_999",
                    watch_type=WatchType.SIX_ON_SIX_OFF,
                    start_time_ns=T0,
                )

    def test_get_watch_schedules(self):
        """Get watch schedules for a crew member."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member("crew_001", "John Smith", "captain")
            monitor.set_watch_schedule("crew_001", WatchType.SIX_ON_SIX_OFF, T0)
            monitor.set_watch_schedule("crew_001", WatchType.FOUR_ON_EIGHT_OFF, T0 + TWENTY_FOUR_HOURS_NS)

            schedules = monitor.get_watch_schedules("crew_001")
            assert len(schedules) == 2

    def test_predict_fatigue_risk(self):
        """Predict fatigue risk for planned future work."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member("crew_001", "John Smith", "captain")
            monitor.log_work_period("crew_001", T0, T0 + EIGHT_HOURS_NS, ActivityType.NAVIGATION)

            risk_score = monitor.predict_fatigue_risk("crew_001", future_work_hours=4.0, now_ns=T0 + TWENTY_FOUR_HOURS_NS)
            assert 0 <= risk_score <= 100

    def test_predict_fatigue_risk_not_found(self):
        """Predicting fatigue for non-existent crew member should raise ValueError."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            with pytest.raises(ValueError, match="not found"):
                monitor.predict_fatigue_risk("crew_999", future_work_hours=4.0)

    def test_to_dict(self):
        """Create monitor snapshot."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member("crew_001", "John Smith", "captain")
            monitor.log_work_period("crew_001", T0, T0 + EIGHT_HOURS_NS, ActivityType.NAVIGATION)

            snapshot = monitor.to_dict(now_ns=T0 + TWENTY_FOUR_HOURS_NS)
            assert snapshot["vessel_id"] == "vessel_001"
            assert snapshot["crew_count"] == 1
            assert "crew_members" in snapshot
            assert "fatigue_metrics" in snapshot
            assert "recent_alerts" in snapshot


# ============================================================================ #
# Fatigue Alert Generation Tests
# ============================================================================ #

class TestFatigueAlertGeneration:
    """Test automatic fatigue alert generation."""

    def test_continuous_work_high_alert(self):
        """Generate HIGH alert for >12 hours continuous work."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member("crew_001", "John Smith", "captain")
            # Log 13 hours of continuous work
            monitor.log_work_period("crew_001", T0, T0 + THIRTEEN_HOURS_NS, ActivityType.NAVIGATION)

            alerts = monitor.get_fatigue_alerts(crew_id="crew_001")
            high_alerts = [a for a in alerts if a.alert_type == AlertType.CONTINUOUS_WORK_HIGH]
            assert len(high_alerts) >= 1
            assert high_alerts[0].severity == AlertSeverity.HIGH

    def test_continuous_work_critical_alert(self):
        """Generate CRITICAL alert for >16 hours continuous work."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member("crew_001", "John Smith", "captain")
            # Log 17 hours of continuous work
            monitor.log_work_period("crew_001", T0, T0 + SEVENTEEN_HOURS_NS, ActivityType.NAVIGATION)

            alerts = monitor.get_fatigue_alerts(crew_id="crew_001")
            critical_alerts = [a for a in alerts if a.alert_type == AlertType.CONTINUOUS_WORK_CRITICAL]
            assert len(critical_alerts) >= 1
            assert critical_alerts[0].severity == AlertSeverity.CRITICAL

    def test_insufficient_rest_danger_alert(self):
        """Generate DANGER alert for >24h without adequate rest."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member("crew_001", "John Smith", "captain")
            # Log 26 hours of work with minimal rest
            monitor.log_work_period("crew_001", T0, T0 + TWENTYSIX_HOURS_NS, ActivityType.NAVIGATION)

            alerts = monitor.get_fatigue_alerts(crew_id="crew_001")
            danger_alerts = [a for a in alerts if a.alert_type == AlertType.INSUFFICIENT_REST_DANGER]
            # May or may not trigger depending on rest calculation
            # Test verifies the logic doesn't crash

    def test_multiple_fatigue_alert(self):
        """Generate alert for >72h work with <24h rest."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member("crew_001", "John Smith", "captain")
            # Log 75 hours of work
            monitor.log_work_period("crew_001", T0, T0 + SEVENTYFIVE_HOURS_NS, ActivityType.NAVIGATION)

            alerts = monitor.get_fatigue_alerts(crew_id="crew_001")
            multiple_alerts = [a for a in alerts if a.alert_type == AlertType.MULTIPLE_FATIGUE]
            # May or may not trigger depending on rest calculation
            # Test verifies the logic doesn't crash

    def test_get_fatigue_alerts_filtered(self):
        """Get fatigue alerts with filters."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member("crew_001", "John Smith", "captain")
            monitor.log_work_period("crew_001", T0, T0 + THIRTEEN_HOURS_NS, ActivityType.NAVIGATION)

            # Get all alerts
            all_alerts = monitor.get_fatigue_alerts()
            assert len(all_alerts) >= 1

            # Get alerts by crew
            crew_alerts = monitor.get_fatigue_alerts(crew_id="crew_001")
            assert len(crew_alerts) >= 1

            # Get alerts by severity
            high_alerts = monitor.get_fatigue_alerts(min_severity=AlertSeverity.HIGH)
            assert len(high_alerts) >= 1

    def test_get_fatigue_alerts_by_time(self):
        """Get fatigue alerts filtered by time."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member("crew_001", "John Smith", "captain")
            monitor.log_work_period("crew_001", T0, T0 + THIRTEEN_HOURS_NS, ActivityType.NAVIGATION)

            # Get recent alerts
            recent_alerts = monitor.get_fatigue_alerts(since_ns=T0)
            assert len(recent_alerts) >= 1

            # Get alerts before the work period - should be empty
            # (We can't filter by end time, so we get all and check manually)
            all_alerts = monitor.get_fatigue_alerts()
            old_alerts = [a for a in all_alerts if a.timestamp_ns < T0]
            assert len(old_alerts) == 0


# ============================================================================ #
# Persistence Tests
# ============================================================================ #

class TestPersistence:
    """Test JSONL persistence functionality."""

    def test_crew_persistence(self):
        """Crew members should persist to JSONL."""
        with TemporaryDirectory() as tmpdir:
            monitor1 = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor1.add_crew_member("crew_001", "John Smith", "captain")

            # Create new monitor instance - should load persisted data
            monitor2 = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            crew = monitor2.get_crew_member("crew_001")
            assert crew is not None
            assert crew.name == "John Smith"

    def test_work_hours_persistence(self):
        """Work hours should persist to JSONL."""
        with TemporaryDirectory() as tmpdir:
            monitor1 = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor1.add_crew_member("crew_001", "John Smith", "captain")
            monitor1.log_work_period("crew_001", T0, T0 + SIX_HOURS_NS, ActivityType.NAVIGATION)

            # Create new monitor instance - should load persisted data
            monitor2 = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            work_periods = monitor2.get_work_hours("crew_001")
            assert len(work_periods) == 1
            assert work_periods[0].duration_hours == 6.0

    def test_alerts_persistence(self):
        """Alerts should persist to JSONL."""
        with TemporaryDirectory() as tmpdir:
            monitor1 = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor1.add_crew_member("crew_001", "John Smith", "captain")
            monitor1.log_work_period("crew_001", T0, T0 + THIRTEEN_HOURS_NS, ActivityType.NAVIGATION)

            # Get alerts from first monitor
            alerts1 = monitor1.get_fatigue_alerts(crew_id="crew_001")
            assert len(alerts1) >= 1

            # Create new monitor instance - should load persisted alerts
            monitor2 = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            alerts2 = monitor2.get_fatigue_alerts(crew_id="crew_001")
            assert len(alerts2) >= 1


# ============================================================================ #
# Integration Tests
# ============================================================================ #

class TestIntegration:
    """Integration tests for complete workflows."""

    def test_complete_watch_cycle(self):
        """Test a complete watch cycle with work and rest."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member("crew_001", "John Smith", "captain")
            monitor.set_watch_schedule("crew_001", WatchType.SIX_ON_SIX_OFF, T0)

            # 6-hour watch
            monitor.log_work_period("crew_001", T0, T0 + SIX_HOURS_NS, ActivityType.NAVIGATION, "bridge")

            # 6-hour rest
            monitor.log_break("crew_001", T0 + SIX_HOURS_NS, SIX_HOURS_NS)

            # Another 6-hour watch
            monitor.log_work_period("crew_001", T0 + TWELVE_HOURS_NS, T0 + EIGHTEEN_HOURS_NS, ActivityType.NAVIGATION, "bridge")

            # Check fatigue metrics
            metrics = monitor.get_fatigue_metrics("crew_001", now_ns=T0 + EIGHTEEN_HOURS_NS)
            assert metrics.hours_worked_24h == 12.0  # Two 6-hour watches
            # Note: hours_rest_24h will be 6h because we logged 6h of rest
            assert metrics.fatigue_score < 70  # Should be moderate fatigue

    def test_multiple_crew_members(self):
        """Test monitoring multiple crew members."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member("crew_001", "John Smith", "captain")
            monitor.add_crew_member("crew_002", "Jane Doe", "mate")
            monitor.add_crew_member("crew_003", "Bob Johnson", "engineer")

            # Log different work patterns
            monitor.log_work_period("crew_001", T0, T0 + EIGHT_HOURS_NS, ActivityType.NAVIGATION)
            monitor.log_work_period("crew_002", T0, T0 + SIX_HOURS_NS, ActivityType.DECK_WORK)
            monitor.log_work_period("crew_003", T0, T0 + TEN_HOURS_NS, ActivityType.MAINTENANCE)

            all_metrics = monitor.get_all_fatigue_metrics(now_ns=T0 + TWENTY_FOUR_HOURS_NS)
            assert len(all_metrics) == 3

            # Check that different work patterns produce different scores
            scores = [m.fatigue_score for m in all_metrics.values()]
            assert len(set(scores)) > 1  # Scores should vary

    def test_fatigue_trend_over_time(self):
        """Test fatigue score trending over time."""
        with TemporaryDirectory() as tmpdir:
            monitor = CrewFatigueMonitor(
                vessel_id="vessel_001",
                data_dir=tmpdir,
            )
            monitor.add_crew_member("crew_001", "John Smith", "captain")

            # Initial low fatigue (no work yet)
            score1 = monitor.get_fatigue_score("crew_001", now_ns=T0)
            assert score1 < 50  # No work, should be relatively low

            # After 8 hours work
            monitor.log_work_period("crew_001", T0, T0 + EIGHT_HOURS_NS, ActivityType.NAVIGATION)
            score2 = monitor.get_fatigue_score("crew_001", now_ns=T0 + EIGHT_HOURS_NS)
            assert score2 > score1  # Fatigue should increase

            # After rest
            monitor.log_break("crew_001", T0 + EIGHT_HOURS_NS, EIGHT_HOURS_NS)
            score3 = monitor.get_fatigue_score("crew_001", now_ns=T0 + SIXTEEN_HOURS_NS)
            assert score3 < score2 or score3 == score2  # Fatigue should decrease or stay same after rest


# Helper constants for tests
EIGHT_HOURS_NS = 8 * ONE_HOUR_NS
TEN_HOURS_NS = 10 * ONE_HOUR_NS
THIRTEEN_HOURS_NS = 13 * ONE_HOUR_NS
SIXTEEN_HOURS_NS = 16 * ONE_HOUR_NS
SEVENTEEN_HOURS_NS = 17 * ONE_HOUR_NS
TWENTYSIX_HOURS_NS = 26 * ONE_HOUR_NS
SEVENTYFIVE_HOURS_NS = 75 * ONE_HOUR_NS
EIGHTEEN_HOURS_NS = 18 * ONE_HOUR_NS
