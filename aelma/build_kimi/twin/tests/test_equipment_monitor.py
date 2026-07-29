"""Comprehensive test suite for Equipment monitoring and maintenance system.

Tests cover:
- Equipment CRUD operations
- Status updates and validation
- Maintenance logging and history
- Failure logging and resolution
- Maintenance scheduling and due calculation
- Predictive maintenance analytics
- MTBF, MTTR, uptime calculations
- Alert generation
- Persistence and serialization
- Integration with WatcherRegistry
- Edge cases and error handling
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import pytest

from twin.equipment_monitor import (
    Equipment,
    EquipmentMonitor,
    EquipmentStatus,
    EquipmentType,
    FailureEvent,
    FailureType,
    MaintenanceLog,
    MaintenanceSchedule,
    MaintenanceType,
    Severity,
)


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def temp_data_dir():
    """Create temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def monitor(temp_data_dir):
    """Create EquipmentMonitor instance with persistence."""
    return EquipmentMonitor(data_dir=temp_data_dir, enable_persistence=True)


@pytest.fixture
def monitor_no_persist():
    """Create EquipmentMonitor instance without persistence."""
    return EquipmentMonitor(enable_persistence=False)


@pytest.fixture
def sample_equipment():
    """Sample equipment data."""
    return {
        "equipment_id": "ENG-001",
        "name": "Main Engine",
        "type": EquipmentType.ENGINE,
        "location": "Engine Room",
        "install_date_ns": 1704067200000000000,  # 2024-01-01
    }


@pytest.fixture
def populated_monitor(monitor):
    """Monitor populated with sample equipment and data."""
    # Add equipment
    monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")
    monitor.add_equipment("GEN-001", "Generator 1", EquipmentType.GENERATOR, "Engine Room")
    monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")
    monitor.add_equipment("WINCH-001", "Trawl Winch", EquipmentType.WINCH, "Deck")

    # Log some maintenance
    monitor.log_maintenance(
        "ENG-001",
        MaintenanceType.ROUTINE,
        "Oil change and filter replacement",
        "tech_john",
        4.5,
        350.00,
    )

    monitor.log_maintenance(
        "PUMP-001",
        MaintenanceType.PREVENTIVE,
        "Seal replacement and bearing check",
        "tech_jane",
        2.0,
        150.00,
    )

    # Schedule maintenance
    monitor.schedule_maintenance("ENG-001", MaintenanceType.ROUTINE, 500.0)
    monitor.schedule_maintenance("PUMP-001", MaintenanceType.PREVENTIVE, 100.0)

    return monitor


# --------------------------------------------------------------------- #
# Equipment CRUD Tests
# --------------------------------------------------------------------- #


class TestEquipmentCRUD:
    """Test equipment creation, retrieval, and updates."""

    def test_add_equipment_success(self, monitor):
        """Test successful equipment addition."""
        equipment = monitor.add_equipment(
            "ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room"
        )

        assert equipment.equipment_id == "ENG-001"
        assert equipment.name == "Main Engine"
        assert equipment.type == EquipmentType.ENGINE
        assert equipment.location == "Engine Room"
        assert equipment.status == EquipmentStatus.OPERATIONAL
        assert equipment.install_date_ns > 0

    def test_add_equipment_with_string_type(self, monitor):
        """Test equipment addition with string type conversion."""
        equipment = monitor.add_equipment(
            "GEN-001", "Generator", "GENERATOR", "Engine Room"
        )

        assert equipment.type == EquipmentType.GENERATOR

    def test_add_equipment_duplicate_id_raises_error(self, monitor):
        """Test that duplicate equipment IDs raise ValueError."""
        monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")

        with pytest.raises(ValueError, match="already exists"):
            monitor.add_equipment("ENG-001", "Duplicate", EquipmentType.ENGINE, "Elsewhere")

    def test_add_equipment_invalid_id_raises_error(self, monitor):
        """Test that invalid equipment IDs raise ValueError."""
        with pytest.raises(ValueError, match="equipment_id must be a non-empty string"):
            monitor.add_equipment("", "Engine", EquipmentType.ENGINE, "Engine Room")

    def test_add_equipment_invalid_type_raises_error(self, monitor):
        """Test that invalid equipment types raise ValueError."""
        # The EquipmentType enum conversion raises ValueError before our validation
        with pytest.raises(ValueError, match="is not a valid EquipmentType"):
            monitor.add_equipment("ENG-001", "Engine", "INVALID_TYPE", "Engine Room")

    def test_get_equipment_success(self, monitor):
        """Test successful equipment retrieval."""
        added = monitor.add_equipment(
            "ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room"
        )
        retrieved = monitor.get_equipment("ENG-001")

        assert retrieved is not None
        assert retrieved.equipment_id == added.equipment_id

    def test_get_equipment_not_found(self, monitor):
        """Test equipment retrieval when not found."""
        result = monitor.get_equipment("NONEXISTENT")
        assert result is None

    def test_get_all_equipment(self, monitor):
        """Test retrieving all equipment."""
        monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")
        monitor.add_equipment("GEN-001", "Generator", EquipmentType.GENERATOR, "Engine Room")

        all_eq = monitor.get_all_equipment()
        assert len(all_eq) == 2
        assert "ENG-001" in all_eq
        assert "GEN-001" in all_eq

    def test_get_equipment_by_type(self, monitor):
        """Test filtering equipment by type."""
        monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")
        monitor.add_equipment("ENG-002", "Aux Engine", EquipmentType.ENGINE, "Engine Room")
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")

        engines = monitor.get_equipment_by_type(EquipmentType.ENGINE)
        assert len(engines) == 2

        pumps = monitor.get_equipment_by_type("PUMP")
        assert len(pumps) == 1
        assert pumps[0].equipment_id == "PUMP-001"


# --------------------------------------------------------------------- #
# Status Update Tests
# --------------------------------------------------------------------- #


class TestStatusUpdates:
    """Test equipment status updates."""

    def test_update_status_to_degraded(self, monitor):
        """Test updating equipment status to DEGRADED."""
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")

        updated = monitor.update_equipment_status("PUMP-001", EquipmentStatus.DEGRADED)
        assert updated.status == EquipmentStatus.DEGRADED

    def test_update_status_with_string(self, monitor):
        """Test status update with string conversion."""
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")

        updated = monitor.update_equipment_status("PUMP-001", "FAILED")
        assert updated.status == EquipmentStatus.FAILED

    def test_update_nonexistent_equipment_raises_error(self, monitor):
        """Test updating status of nonexistent equipment raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            monitor.update_equipment_status("NONEXISTENT", EquipmentStatus.FAILED)

    def test_status_to_dict_serialization(self, monitor):
        """Test EquipmentStatus serializes correctly."""
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")
        equipment = monitor.get_equipment("PUMP-001")

        data = equipment.to_dict()
        assert "status" in data
        assert data["status"] == "OPERATIONAL"


# --------------------------------------------------------------------- #
# Maintenance Logging Tests
# --------------------------------------------------------------------- #


class TestMaintenanceLogging:
    """Test maintenance activity logging."""

    def test_log_maintenance_success(self, monitor):
        """Test successful maintenance logging."""
        monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")

        log_entry = monitor.log_maintenance(
            "ENG-001",
            MaintenanceType.ROUTINE,
            "Oil change and filter replacement",
            "tech_john",
            4.5,
            350.00,
        )

        assert log_entry.equipment_id == "ENG-001"
        assert log_entry.maintenance_type == MaintenanceType.ROUTINE
        assert log_entry.technician == "tech_john"
        assert log_entry.duration_hours == 4.5
        assert log_entry.cost == 350.00
        assert log_entry.timestamp_ns > 0

    def test_log_maintenance_with_string_type(self, monitor):
        """Test maintenance logging with string type conversion."""
        monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")

        log_entry = monitor.log_maintenance(
            "ENG-001",
            "PREVENTIVE",
            "Preventive maintenance",
            "tech_jane",
            2.0,
            150.00,
        )

        assert log_entry.maintenance_type == MaintenanceType.PREVENTIVE

    def test_log_maintenance_updates_equipment(self, monitor):
        """Test that logging maintenance updates equipment last_maintenance_ns."""
        monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")

        log_entry = monitor.log_maintenance(
            "ENG-001",
            MaintenanceType.ROUTINE,
            "Maintenance",
            "tech_john",
            1.0,
            100.00,
        )

        equipment = monitor.get_equipment("ENG-001")
        assert equipment.last_maintenance_ns == log_entry.timestamp_ns

    def test_log_maintenance_nonexistent_equipment_raises_error(self, monitor):
        """Test logging maintenance for nonexistent equipment raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            monitor.log_maintenance(
                "NONEXISTENT",
                MaintenanceType.ROUTINE,
                "Maintenance",
                "tech_john",
                1.0,
                100.00,
            )

    def test_get_maintenance_history(self, monitor):
        """Test retrieving maintenance history."""
        monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")

        monitor.log_maintenance("ENG-001", MaintenanceType.ROUTINE, "First", "tech1", 1.0, 100.0)
        time.sleep(0.01)  # Ensure different timestamps
        monitor.log_maintenance("ENG-001", MaintenanceType.PREVENTIVE, "Second", "tech2", 2.0, 200.0)

        history = monitor.get_maintenance_history("ENG-001")
        assert len(history) == 2
        assert history[0].maintenance_type == MaintenanceType.PREVENTIVE  # Most recent first

    def test_get_maintenance_cost_summary(self, monitor):
        """Test maintenance cost summary calculation."""
        monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")

        monitor.log_maintenance("ENG-001", MaintenanceType.ROUTINE, "First", "tech1", 1.0, 100.0)
        monitor.log_maintenance("ENG-001", MaintenanceType.PREVENTIVE, "Second", "tech2", 2.0, 250.0)

        summary = monitor.get_maintenance_cost_summary("ENG-001")
        assert summary["total_cost"] == 350.0
        assert summary["total_hours"] == 3.0
        assert summary["maintenance_count"] == 2
        assert "cost_by_type" in summary


# --------------------------------------------------------------------- #
# Failure Logging Tests
# --------------------------------------------------------------------- #


class TestFailureLogging:
    """Test failure event logging and resolution."""

    def test_log_failure_success(self, monitor):
        """Test successful failure logging."""
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")

        failure = monitor.log_failure(
            "PUMP-001",
            FailureType.MECHANICAL,
            Severity.HIGH,
            "Bearing failure detected",
        )

        assert failure.equipment_id == "PUMP-001"
        assert failure.failure_type == FailureType.MECHANICAL
        assert failure.severity == Severity.HIGH
        assert failure.description == "Bearing failure detected"
        assert failure.timestamp_ns > 0
        assert failure.resolved_ns is None

    def test_log_failure_with_string_types(self, monitor):
        """Test failure logging with string type conversion."""
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")

        failure = monitor.log_failure(
            "PUMP-001",
            "ELECTRICAL",
            "CRITICAL",
            "Electrical failure",
        )

        assert failure.failure_type == FailureType.ELECTRICAL
        assert failure.severity == Severity.CRITICAL

    def test_log_critical_failure_updates_status(self, monitor):
        """Test that logging critical failure updates equipment status to FAILED."""
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")

        monitor.log_failure(
            "PUMP-001",
            FailureType.MECHANICAL,
            Severity.CRITICAL,
            "Catastrophic failure",
        )

        equipment = monitor.get_equipment("PUMP-001")
        assert equipment.status == EquipmentStatus.FAILED

    def test_log_high_severity_failure_updates_status(self, monitor):
        """Test that HIGH severity failure updates equipment status to FAILED."""
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")

        monitor.log_failure("PUMP-001", FailureType.WEAR, Severity.HIGH, "Wear detected")

        equipment = monitor.get_equipment("PUMP-001")
        assert equipment.status == EquipmentStatus.FAILED

    def test_log_medium_severity_failure_no_status_change(self, monitor):
        """Test that MEDIUM severity failure does not change status to FAILED."""
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")

        monitor.log_failure("PUMP-001", FailureType.WEAR, Severity.MEDIUM, "Wear detected")

        equipment = monitor.get_equipment("PUMP-001")
        assert equipment.status == EquipmentStatus.OPERATIONAL

    def test_resolve_failure_success(self, monitor):
        """Test successful failure resolution."""
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")

        failure = monitor.log_failure(
            "PUMP-001",
            FailureType.MECHANICAL,
            Severity.HIGH,
            "Bearing failure",
        )

        resolved = monitor.resolve_failure("PUMP-001", "Replaced bearings")

        assert resolved is not None
        assert resolved.resolved_ns is not None
        assert resolved.resolved_ns > failure.timestamp_ns

    def test_resolve_failure_updates_equipment_status(self, monitor):
        """Test that resolving failure updates equipment status to OPERATIONAL."""
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")

        monitor.log_failure("PUMP-001", FailureType.MECHANICAL, Severity.HIGH, "Failure")
        assert monitor.get_equipment("PUMP-001").status == EquipmentStatus.FAILED

        monitor.resolve_failure("PUMP-001", "Fixed")
        assert monitor.get_equipment("PUMP-001").status == EquipmentStatus.OPERATIONAL

    def test_resolve_failure_no_unresolved_returns_none(self, monitor):
        """Test resolving failure when none are unresolved returns None."""
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")

        result = monitor.resolve_failure("PUMP-001", "No failure to resolve")
        assert result is None

    def test_get_failure_history(self, monitor):
        """Test retrieving failure history."""
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")

        monitor.log_failure("PUMP-001", FailureType.MECHANICAL, Severity.HIGH, "First")
        time.sleep(0.01)
        monitor.log_failure("PUMP-001", FailureType.ELECTRICAL, Severity.MEDIUM, "Second")

        history = monitor.get_failure_history("PUMP-001")
        assert len(history) == 2
        assert history[0].failure_type == FailureType.ELECTRICAL  # Most recent first


# --------------------------------------------------------------------- #
# Maintenance Scheduling Tests
# --------------------------------------------------------------------- #


class TestMaintenanceScheduling:
    """Test maintenance scheduling and due calculation."""

    def test_schedule_maintenance_success(self, monitor):
        """Test successful maintenance scheduling."""
        monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")

        schedule = monitor.schedule_maintenance("ENG-001", MaintenanceType.ROUTINE, 500.0)

        assert schedule.equipment_id == "ENG-001"
        assert schedule.maintenance_type == MaintenanceType.ROUTINE
        assert schedule.interval_hours == 500.0
        assert schedule.next_due_ns > schedule.last_performed_ns

    def test_schedule_maintenance_with_default_interval(self, monitor):
        """Test scheduling with default interval for equipment type."""
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")

        schedule = monitor.schedule_maintenance("PUMP-001", MaintenanceType.ROUTINE)

        assert schedule.interval_hours == EquipmentMonitor.DEFAULT_INTERVALS[EquipmentType.PUMP]

    def test_get_maintenance_schedule(self, monitor):
        """Test retrieving maintenance schedule."""
        monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")

        monitor.schedule_maintenance("ENG-001", MaintenanceType.ROUTINE, 500.0)
        schedule = monitor.get_maintenance_schedule("ENG-001")

        assert schedule is not None
        assert schedule.equipment_id == "ENG-001"

    def test_get_due_maintenance(self, monitor):
        """Test retrieving maintenance due within lookahead."""
        monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")

        # Schedule maintenance 10 hours from now
        monitor.schedule_maintenance("ENG-001", MaintenanceType.ROUTINE, 500.0)
        schedule = monitor.get_maintenance_schedule("ENG-001")
        schedule.next_due_ns = time.time_ns() + int(10 * 3600 * 1e9)

        due = monitor.get_due_maintenance(lookahead_hours=24)
        assert len(due) == 1
        assert due[0].equipment_id == "ENG-001"

    def test_get_due_maintenance_empty_when_no_due(self, monitor):
        """Test get_due_maintenance returns empty when nothing due."""
        monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")

        monitor.schedule_maintenance("ENG-001", MaintenanceType.ROUTINE, 500.0)

        due = monitor.get_due_maintenance(lookahead_hours=1)
        assert len(due) == 0

    def test_get_overdue_maintenance(self, monitor):
        """Test retrieving overdue maintenance."""
        monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")

        monitor.schedule_maintenance("ENG-001", MaintenanceType.ROUTINE, 500.0)
        schedule = monitor.get_maintenance_schedule("ENG-001")
        schedule.next_due_ns = time.time_ns() - 1000  # Already overdue

        overdue = monitor.get_overdue_maintenance()
        assert len(overdue) == 1
        assert overdue[0].equipment_id == "ENG-001"


# --------------------------------------------------------------------- #
# Predictive Maintenance Tests
# --------------------------------------------------------------------- #


class TestPredictiveMaintenance:
    """Test predictive maintenance analytics."""

    def test_predict_maintenance_needs_with_schedule(self, monitor):
        """Test prediction based on maintenance schedule."""
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")

        # Schedule maintenance 12 hours from now
        monitor.schedule_maintenance("PUMP-001", MaintenanceType.ROUTINE, 100.0)
        schedule = monitor.get_maintenance_schedule("PUMP-001")
        schedule.next_due_ns = time.time_ns() + int(12 * 3600 * 1e9)

        predictions = monitor.predict_maintenance_needs("PUMP-001", lookahead_hours=24)

        assert len(predictions) >= 1
        assert any(p["reason"] == "scheduled_maintenance" for p in predictions)

    def test_predict_maintenance_needs_with_failure_history(self, monitor):
        """Test prediction based on failure history (MTBF)."""
        monitor.add_equipment("BEAR-001", "Bearing", EquipmentType.PUMP, "Engine Room")

        # Create failure history
        now = time.time_ns()
        day_ns = 24 * 3600 * 1e9

        # First failure
        f1 = monitor.log_failure(
            "BEAR-001", FailureType.WEAR, Severity.HIGH, "First failure"
        )
        f1.timestamp_ns = now - 30 * day_ns
        f1.resolved_ns = now - 29 * day_ns

        # Second failure
        f2 = monitor.log_failure(
            "BEAR-001", FailureType.WEAR, Severity.HIGH, "Second failure"
        )
        f2.timestamp_ns = now - 15 * day_ns
        f2.resolved_ns = now - 14 * day_ns

        predictions = monitor.predict_maintenance_needs("BEAR-001", lookahead_hours=168)

        assert len(predictions) >= 1
        assert any(p["reason"] == "failure_pattern_prediction" for p in predictions)
        assert any("mtbf_hours" in p for p in predictions)

    def test_predict_maintenance_needs_with_degraded_status(self, monitor):
        """Test prediction based on DEGRADED status."""
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")
        monitor.update_equipment_status("PUMP-001", EquipmentStatus.DEGRADED)

        predictions = monitor.predict_maintenance_needs("PUMP-001")

        assert len(predictions) >= 1
        assert any(p["reason"] == "current_status" for p in predictions)
        assert any(p["priority"] == "critical" for p in predictions)


# --------------------------------------------------------------------- #
# Analytics Tests
# --------------------------------------------------------------------- #


class TestAnalytics:
    """Test MTBF, MTTR, uptime, and other analytics."""

    def test_calculate_mtbf(self, monitor):
        """Test Mean Time Between Failures calculation."""
        monitor.add_equipment("BEAR-001", "Bearing", EquipmentType.PUMP, "Engine Room")

        now = time.time_ns()
        day_ns = 24 * 3600 * 1e9

        # Create resolved failures with proper chronological order
        # First failure (older): 30 days ago, resolved 29 days ago
        f1_timestamp = now - 30 * day_ns
        f1_resolved = now - 29 * day_ns

        # Second failure (more recent): 15 days ago, resolved 14 days ago
        f2_timestamp = now - 15 * day_ns
        f2_resolved = now - 14 * day_ns

        # Manually create failure events with specific timestamps
        # Add them in chronological order (oldest first)
        f1 = FailureEvent(
            equipment_id="BEAR-001",
            failure_type=FailureType.WEAR,
            severity=Severity.HIGH,
            description="F1",
            timestamp_ns=f1_timestamp,
        )
        f1.resolved_ns = f1_resolved
        monitor._failure_events.append(f1)

        f2 = FailureEvent(
            equipment_id="BEAR-001",
            failure_type=FailureType.WEAR,
            severity=Severity.HIGH,
            description="F2",
            timestamp_ns=f2_timestamp,
        )
        f2.resolved_ns = f2_resolved
        monitor._failure_events.append(f2)

        mtbf = monitor.calculate_mtbf("BEAR-001")
        assert mtbf is not None
        assert mtbf > 0
        # MTBF should be approximately 14 days (336 hours)
        # Time between first resolution (29 days ago) and second failure (15 days ago) = 14 days
        expected_mtbf_hours = 14 * 24
        assert abs(mtbf - expected_mtbf_hours) < 1.0  # Within 1 hour tolerance

    def test_calculate_mtbf_insufficient_data(self, monitor):
        """Test MTBF returns None with insufficient data."""
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")

        # Only one failure - insufficient for MTBF
        monitor.log_failure("PUMP-001", FailureType.WEAR, Severity.HIGH, "Single failure")

        mtbf = monitor.calculate_mtbf("PUMP-001")
        assert mtbf is None

    def test_calculate_mttr(self, monitor):
        """Test Mean Time To Repair calculation."""
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")

        failure = monitor.log_failure("PUMP-001", FailureType.WEAR, Severity.HIGH, "Failure")
        time.sleep(0.1)  # Simulate repair time
        monitor.resolve_failure("PUMP-001", "Fixed")

        mttr = monitor.calculate_mttr("PUMP-001")
        assert mttr is not None
        assert mttr > 0

    def test_calculate_equipment_uptime(self, monitor):
        """Test equipment uptime calculation."""
        monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")

        # Simulate some downtime
        now = time.time_ns()
        failure = monitor.log_failure("ENG-001", FailureType.MECHANICAL, Severity.HIGH, "Failure")
        failure.timestamp_ns = now - 3600 * 1e9  # 1 hour ago
        failure.resolved_ns = now - 1800 * 1e9  # Resolved 30 minutes ago

        uptime = monitor.calculate_equipment_uptime("ENG-001")

        assert "uptime_percentage" in uptime
        assert "total_downtime_hours" in uptime
        assert "failure_count" in uptime
        assert uptime["failure_count"] == 1

    def test_calculate_equipment_uptime_with_unresolved_failure(self, monitor):
        """Test uptime with unresolved failure counts as downtime."""
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")

        # Unresolved failure
        monitor.log_failure("PUMP-001", FailureType.WEAR, Severity.HIGH, "Ongoing failure")

        uptime = monitor.calculate_equipment_uptime("PUMP-001")

        assert uptime["uptime_percentage"] < 100  # Should have downtime


# --------------------------------------------------------------------- #
# Alert Generation Tests
# --------------------------------------------------------------------- #


class TestAlertGeneration:
    """Test alert generation for equipment issues."""

    def test_alert_for_failed_equipment(self, monitor):
        """Test alert generation for failed equipment."""
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")
        monitor.update_equipment_status("PUMP-001", EquipmentStatus.FAILED)

        alerts = monitor.get_alerts()

        assert len(alerts) >= 1
        assert any(a["code"] == "EQUIPMENT_FAILED" for a in alerts)
        assert any(a["severity"] == "critical" for a in alerts)

    def test_alert_for_degraded_equipment(self, monitor):
        """Test alert generation for degraded equipment."""
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")
        monitor.update_equipment_status("PUMP-001", EquipmentStatus.DEGRADED)

        alerts = monitor.get_alerts()

        assert len(alerts) >= 1
        assert any(a["code"] == "EQUIPMENT_DEGRADED" for a in alerts)
        assert any(a["severity"] == "warning" for a in alerts)

    def test_alert_for_overdue_maintenance(self, monitor):
        """Test alert for overdue maintenance."""
        monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")

        monitor.schedule_maintenance("ENG-001", MaintenanceType.ROUTINE, 500.0)
        schedule = monitor.get_maintenance_schedule("ENG-001")
        schedule.next_due_ns = time.time_ns() - 1000  # Overdue

        alerts = monitor.get_alerts()

        assert any(a["code"] == "MAINTENANCE_OVERDUE" for a in alerts)

    def test_alert_for_unresolved_critical_failure(self, monitor):
        """Test alert for unresolved critical failure."""
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")

        monitor.log_failure(
            "PUMP-001",
            FailureType.MECHANICAL,
            Severity.CRITICAL,
            "Critical failure",
        )

        alerts = monitor.get_alerts()

        assert any(a["code"] == "CRITICAL_FAILURE_UNRESOLVED" for a in alerts)
        assert any(a["severity"] == "critical" for a in alerts)


# --------------------------------------------------------------------- #
# Integration Tests
# --------------------------------------------------------------------- #


class TestIntegration:
    """Test integration with WatcherRegistry and serialization."""

    def test_get_watcher_frame(self, populated_monitor):
        """Test watcher frame generation for rule evaluation."""
        frame = populated_monitor.get_watcher_frame()

        assert "timestamp_ns" in frame
        assert "equipment_count" in frame
        assert "equipment_status_counts" in frame
        assert "overdue_maintenance_count" in frame
        assert frame["equipment_count"] == 4

    def test_to_dict_comprehensive_snapshot(self, populated_monitor):
        """Test comprehensive snapshot creation."""
        snapshot = populated_monitor.to_dict()

        assert "equipment" in snapshot
        assert "maintenance_logs" in snapshot
        assert "failure_events" in snapshot
        assert "schedules" in snapshot
        assert "watcher_frame" in snapshot
        assert "alerts" in snapshot

    def test_persistence_to_disk(self, monitor, temp_data_dir):
        """Test data persists to JSONL files."""
        monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")
        monitor.log_maintenance(
            "ENG-001",
            MaintenanceType.ROUTINE,
            "Oil change",
            "tech_john",
            2.0,
            150.0,
        )

        # Verify files exist
        assert (temp_data_dir / "equipment.jsonl").exists()
        assert (temp_data_dir / "maintenance.jsonl").exists()

    def test_load_from_disk(self, temp_data_dir):
        """Test loading persisted data from disk."""
        # Create monitor, add data
        monitor1 = EquipmentMonitor(data_dir=temp_data_dir, enable_persistence=True)
        monitor1.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")
        monitor1.log_maintenance(
            "ENG-001",
            MaintenanceType.ROUTINE,
            "Oil change",
            "tech_john",
            2.0,
            150.0,
        )

        # Create new monitor and load
        monitor2 = EquipmentMonitor(data_dir=temp_data_dir, enable_persistence=True)
        monitor2.load_from_disk()

        assert monitor2.get_equipment("ENG-001") is not None
        assert len(monitor2.get_maintenance_history("ENG-001")) == 1

    def test_equipment_serialization_roundtrip(self, sample_equipment):
        """Test Equipment to_dict/from_dict roundtrip."""
        equipment = Equipment(**sample_equipment)

        data = equipment.to_dict()
        restored = Equipment.from_dict(data)

        assert restored.equipment_id == equipment.equipment_id
        assert restored.name == equipment.name
        assert restored.type == equipment.type
        assert restored.location == equipment.location

    def test_maintenance_log_serialization_roundtrip(self, monitor):
        """Test MaintenanceLog to_dict/from_dict roundtrip."""
        monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")

        log_entry = monitor.log_maintenance(
            "ENG-001",
            MaintenanceType.ROUTINE,
            "Oil change",
            "tech_john",
            2.0,
            150.0,
        )

        data = log_entry.to_dict()
        restored = MaintenanceLog.from_dict(data)

        assert restored.equipment_id == log_entry.equipment_id
        assert restored.maintenance_type == log_entry.maintenance_type
        assert restored.description == log_entry.description

    def test_failure_event_serialization_roundtrip(self, monitor):
        """Test FailureEvent to_dict/from_dict roundtrip."""
        monitor.add_equipment("PUMP-001", "Cooling Pump", EquipmentType.PUMP, "Engine Room")

        failure = monitor.log_failure(
            "PUMP-001",
            FailureType.MECHANICAL,
            Severity.HIGH,
            "Bearing failure",
        )

        data = failure.to_dict()
        restored = FailureEvent.from_dict(data)

        assert restored.equipment_id == failure.equipment_id
        assert restored.failure_type == failure.failure_type
        assert restored.severity == failure.severity

    def test_schedule_serialization_roundtrip(self, monitor):
        """Test MaintenanceSchedule to_dict/from_dict roundtrip."""
        monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")

        schedule = monitor.schedule_maintenance("ENG-001", MaintenanceType.ROUTINE, 500.0)

        data = schedule.to_dict()
        restored = MaintenanceSchedule.from_dict(data)

        assert restored.equipment_id == schedule.equipment_id
        assert restored.maintenance_type == schedule.maintenance_type
        assert restored.interval_hours == schedule.interval_hours


# --------------------------------------------------------------------- #
# Edge Cases and Error Handling
# --------------------------------------------------------------------- #


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_monitor_state(self, monitor):
        """Test monitor behavior with no equipment."""
        assert monitor.get_all_equipment() == {}
        assert monitor.get_alerts() == []
        assert monitor.get_due_maintenance() == []
        assert monitor.get_overdue_maintenance() == []

    def test_equipment_with_invalid_install_date(self, monitor):
        """Test validation rejects negative install_date_ns."""
        with pytest.raises(ValueError, match="install_date_ns must be >= 0"):
            monitor.add_equipment(
                "ENG-001",
                "Main Engine",
                EquipmentType.ENGINE,
                "Engine Room",
                install_date_ns=-1,
            )

    def test_maintenance_log_with_negative_duration(self, monitor):
        """Test validation rejects negative duration_hours."""
        monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")

        with pytest.raises(ValueError, match="duration_hours must be >= 0"):
            monitor.log_maintenance(
                "ENG-001",
                MaintenanceType.ROUTINE,
                "Maintenance",
                "tech_john",
                -1.0,
                100.0,
            )

    def test_maintenance_log_with_negative_cost(self, monitor):
        """Test validation rejects negative cost."""
        monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")

        with pytest.raises(ValueError, match="cost must be >= 0"):
            monitor.log_maintenance(
                "ENG-001",
                MaintenanceType.ROUTINE,
                "Maintenance",
                "tech_john",
                1.0,
                -100.0,
            )

    def test_schedule_with_negative_interval(self, monitor):
        """Test validation rejects zero or negative interval_hours."""
        monitor.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")

        with pytest.raises(ValueError, match="interval_hours must be > 0"):
            monitor.schedule_maintenance("ENG-001", MaintenanceType.ROUTINE, 0)

    def test_monitor_disabled_persistence(self, monitor_no_persist, temp_data_dir):
        """Test monitor with persistence disabled."""
        monitor_no_persist.add_equipment("ENG-001", "Main Engine", EquipmentType.ENGINE, "Engine Room")

        # No files should be created
        assert not (temp_data_dir / "equipment.jsonl").exists()


# --------------------------------------------------------------------- #
# Run tests
# --------------------------------------------------------------------- #


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
