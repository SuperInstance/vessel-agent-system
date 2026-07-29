"""Comprehensive tests for the Crew Safety system."""

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from safety.crew_safety import (
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


class TestSafetyIncidents(unittest.TestCase):
    """Test safety incident logging and management."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.safety = CrewSafety("test_vessel", data_dir=self.temp_dir)

    def test_log_minor_incident(self):
        """Test logging a minor safety incident."""
        incident = self.safety.log_safety_incident(
            incident_type=IncidentType.NEAR_MISS,
            severity=IncidentSeverity.MINOR,
            description="Near miss with fishing gear",
        )

        self.assertEqual(incident.incident_type, IncidentType.NEAR_MISS)
        self.assertEqual(incident.severity, IncidentSeverity.MINOR)
        self.assertEqual(incident.description, "Near miss with fishing gear")
        self.assertIsNotNone(incident.incident_id)
        self.assertGreater(incident.timestamp_ns, 0)

    def test_log_critical_incident(self):
        """Test logging a critical safety incident."""
        incident = self.safety.log_safety_incident(
            incident_type=IncidentType.MOB,
            severity=IncidentSeverity.CRITICAL,
            description="Crew member fell overboard",
            location_lat=59.5,
            location_lon=-152.3,
            crew_involved=["crew_001"],
        )

        self.assertEqual(incident.incident_type, IncidentType.MOB)
        self.assertEqual(incident.severity, IncidentSeverity.CRITICAL)
        self.assertEqual(incident.location_lat, 59.5)
        self.assertEqual(incident.location_lon, -152.3)
        self.assertIn("crew_001", incident.crew_involved)

    def test_log_incident_with_string_types(self):
        """Test logging incident with string enum values."""
        incident = self.safety.log_safety_incident(
            incident_type="INJURY",
            severity="MODERATE",
            description="Minor cut on finger",
        )

        self.assertEqual(incident.incident_type, IncidentType.INJURY)
        self.assertEqual(incident.severity, IncidentSeverity.MODERATE)

    def test_resolve_incident(self):
        """Test resolving a safety incident."""
        incident = self.safety.log_safety_incident(
            incident_type=IncidentType.FIRE,
            severity=IncidentSeverity.MAJOR,
            description="Small fire in engine room",
        )

        resolved = self.safety.resolve_incident(
            incident_id=incident.incident_id,
            root_cause="Fuel leak",
            lessons_learned="Need better inspection routine",
            corrective_actions=["Implement weekly fuel line inspections"],
        )

        self.assertIsNotNone(resolved)
        self.assertIsNotNone(resolved.resolved_ns)
        self.assertEqual(resolved.root_cause, "Fuel leak")
        self.assertEqual(len(resolved.corrective_actions), 1)

    def test_resolve_nonexistent_incident(self):
        """Test resolving a non-existent incident."""
        resolved = self.safety.resolve_incident("nonexistent_id")
        self.assertIsNone(resolved)

    def test_get_incidents_by_type(self):
        """Test filtering incidents by type."""
        self.safety.log_safety_incident(IncidentType.MOB, IncidentSeverity.CRITICAL, "MOB 1")
        self.safety.log_safety_incident(IncidentType.INJURY, IncidentSeverity.MINOR, "Injury 1")
        self.safety.log_safety_incident(IncidentType.MOB, IncidentSeverity.CRITICAL, "MOB 2")

        mob_incidents = self.safety.get_safety_incidents(incident_type=IncidentType.MOB)
        self.assertEqual(len(mob_incidents), 2)
        for incident in mob_incidents:
            self.assertEqual(incident.incident_type, IncidentType.MOB)

    def test_get_incidents_by_severity(self):
        """Test filtering incidents by severity."""
        self.safety.log_safety_incident(IncidentType.MOB, IncidentSeverity.CRITICAL, "Critical")
        self.safety.log_safety_incident(IncidentType.NEAR_MISS, IncidentSeverity.MINOR, "Minor")
        self.safety.log_safety_incident(IncidentType.INJURY, IncidentSeverity.CRITICAL, "Critical 2")

        critical_incidents = self.safety.get_safety_incidents(severity=IncidentSeverity.CRITICAL)
        self.assertEqual(len(critical_incidents), 2)

    def test_get_incidents_by_crew(self):
        """Test filtering incidents by crew involvement."""
        self.safety.log_safety_incident(
            IncidentType.INJURY,
            IncidentSeverity.MINOR,
            "Injury 1",
            crew_involved=["crew_001", "crew_002"],
        )
        self.safety.log_safety_incident(
            IncidentType.INJURY,
            IncidentSeverity.MINOR,
            "Injury 2",
            crew_involved=["crew_003"],
        )

        crew_001_incidents = self.safety.get_safety_incidents(crew_id="crew_001")
        self.assertEqual(len(crew_001_incidents), 1)
        self.assertIn("crew_001", crew_001_incidents[0].crew_involved)

    def test_get_resolved_vs_unresolved(self):
        """Test filtering by resolution status."""
        incident1 = self.safety.log_safety_incident(IncidentType.NEAR_MISS, IncidentSeverity.MINOR, "Near miss")
        incident2 = self.safety.log_safety_incident(IncidentType.INJURY, IncidentSeverity.MINOR, "Injury")

        self.safety.resolve_incident(incident1.incident_id)

        resolved = self.safety.get_safety_incidents(resolved=True)
        unresolved = self.safety.get_safety_incidents(resolved=False)

        self.assertEqual(len(resolved), 1)
        self.assertEqual(len(unresolved), 1)

    def test_incident_statistics(self):
        """Test incident statistics calculation."""
        # Log various incidents
        self.safety.log_safety_incident(IncidentType.MOB, IncidentSeverity.CRITICAL, "MOB 1")
        self.safety.log_safety_incident(IncidentType.INJURY, IncidentSeverity.MINOR, "Injury 1")
        self.safety.log_safety_incident(IncidentType.NEAR_MISS, IncidentSeverity.MINOR, "Near miss 1")
        self.safety.log_safety_incident(IncidentType.INJURY, IncidentSeverity.MODERATE, "Injury 2")

        # Resolve one
        incident = self.safety.log_safety_incident(IncidentType.FIRE, IncidentSeverity.MAJOR, "Fire")
        self.safety.resolve_incident(incident.incident_id)

        stats = self.safety.get_incident_statistics(days=30)

        self.assertEqual(stats["total_incidents"], 5)
        self.assertIn("MOB", stats["incident_type_counts"])
        self.assertIn("CRITICAL", stats["incident_severity_counts"])
        self.assertEqual(stats["resolved_count"], 1)
        self.assertEqual(stats["unresolved_count"], 4)


class TestEmergencyProtocols(unittest.TestCase):
    """Test emergency protocol management."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.safety = CrewSafety("test_vessel", data_dir=self.temp_dir)

    def test_default_protocols_exist(self):
        """Test that default protocols are created."""
        mob_protocol = self.safety.get_emergency_protocol(ProtocolType.MOB_RESPONSE)
        self.assertIsNotNone(mob_protocol)
        self.assertEqual(mob_protocol.protocol_type, ProtocolType.MOB_RESPONSE)
        self.assertGreater(len(mob_protocol.steps), 0)
        self.assertGreater(len(mob_protocol.contacts), 0)

    def test_activate_mob_protocol(self):
        """Test activating MOB protocol."""
        protocol = self.safety.activate_emergency_protocol(ProtocolType.MOB_RESPONSE)

        self.assertEqual(protocol.protocol_type, ProtocolType.MOB_RESPONSE)
        self.assertIn("MOB", str(protocol.steps[0]))

    def test_activate_fire_protocol(self):
        """Test activating fire response protocol."""
        protocol = self.safety.activate_emergency_protocol(ProtocolType.FIRE_RESPONSE)

        self.assertEqual(protocol.protocol_type, ProtocolType.FIRE_RESPONSE)
        self.assertIn("fire", str(protocol.steps[0]).lower())

    def test_get_all_protocol_types(self):
        """Test that all standard protocols exist."""
        protocol_types = [
            ProtocolType.MOB_RESPONSE,
            ProtocolType.FIRE_RESPONSE,
            ProtocolType.ABANDON_SHIP,
            ProtocolType.MEDICAL_EMERGENCY,
            ProtocolType.MAYDAY,
        ]

        for ptype in protocol_types:
            protocol = self.safety.get_emergency_protocol(ptype)
            self.assertIsNotNone(protocol, f"Protocol {ptype} should exist")

    def test_protocol_equipment_requirements(self):
        """Test that protocols have required equipment listed."""
        mob_protocol = self.safety.get_emergency_protocol(ProtocolType.MOB_RESPONSE)
        self.assertGreater(len(mob_protocol.equipment_required), 0)
        self.assertIn(EquipmentType.LIFE_JACKET, mob_protocol.equipment_required)


class TestTrainingManagement(unittest.TestCase):
    """Test training and certification management."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.safety = CrewSafety("test_vessel", data_dir=self.temp_dir)
        self.now_ns = time.time_ns()

    def test_add_training_record(self):
        """Test adding a training record."""
        expiry_ns = self.now_ns + (365 * 24 * 3600 * 1e9)  # 1 year

        record = self.safety.add_training_record(
            crew_id="crew_001",
            training_type=TrainingType.BASIC_SAFETY,
            completion_date_ns=self.now_ns,
            expiry_date_ns=expiry_ns,
            certification_id="CERT-001",
            instructor="John Smith",
            score=95.0,
        )

        self.assertEqual(record.crew_id, "crew_001")
        self.assertEqual(record.training_type, TrainingType.BASIC_SAFETY)
        self.assertEqual(record.certification_id, "CERT-001")
        self.assertEqual(record.score, 95.0)

    def test_add_training_with_string_type(self):
        """Test adding training with string type."""
        record = self.safety.add_training_record(
            crew_id="crew_001",
            training_type="FIRST_AID",
            completion_date_ns=self.now_ns,
        )

        self.assertEqual(record.training_type, TrainingType.FIRST_AID)

    def test_get_crew_training(self):
        """Test retrieving crew training records."""
        expiry_ns = self.now_ns + (365 * 24 * 3600 * 1e9)

        self.safety.add_training_record(
            crew_id="crew_001",
            training_type=TrainingType.BASIC_SAFETY,
            completion_date_ns=self.now_ns,
            expiry_date_ns=expiry_ns,
        )
        self.safety.add_training_record(
            crew_id="crew_001",
            training_type=TrainingType.FIRE_DRILL,
            completion_date_ns=self.now_ns,
            expiry_date_ns=expiry_ns,
        )
        self.safety.add_training_record(
            crew_id="crew_002",
            training_type=TrainingType.MOB_DRILL,
            completion_date_ns=self.now_ns,
        )

        crew_001_training = self.safety.get_crew_training("crew_001")
        self.assertEqual(len(crew_001_training), 2)

        crew_002_training = self.safety.get_crew_training("crew_002")
        self.assertEqual(len(crew_002_training), 1)

    def test_get_training_by_type(self):
        """Test filtering training by type."""
        expiry_ns = self.now_ns + (365 * 24 * 3600 * 1e9)

        self.safety.add_training_record(
            crew_id="crew_001",
            training_type=TrainingType.BASIC_SAFETY,
            completion_date_ns=self.now_ns,
            expiry_date_ns=expiry_ns,
        )
        self.safety.add_training_record(
            crew_id="crew_001",
            training_type=TrainingType.FIRE_DRILL,
            completion_date_ns=self.now_ns,
            expiry_date_ns=expiry_ns,
        )

        basic_safety_training = self.safety.get_crew_training("crew_001", training_type=TrainingType.BASIC_SAFETY)
        self.assertEqual(len(basic_safety_training), 1)
        self.assertEqual(basic_safety_training[0].training_type, TrainingType.BASIC_SAFETY)

    def test_check_training_expiry(self):
        """Test checking for expiring training."""
        # Training expiring in 7 days
        expiring_soon = self.now_ns + (7 * 24 * 3600 * 1e9)
        # Training expiring in 60 days
        expiring_later = self.now_ns + (60 * 24 * 3600 * 1e9)
        # Expired training
        expired = self.now_ns - (10 * 24 * 3600 * 1e9)

        self.safety.add_training_record(
            crew_id="crew_001",
            training_type=TrainingType.FIRST_AID,
            completion_date_ns=self.now_ns - (30 * 24 * 3600 * 1e9),
            expiry_date_ns=expiring_soon,
        )
        self.safety.add_training_record(
            crew_id="crew_002",
            training_type=TrainingType.MOB_DRILL,
            completion_date_ns=self.now_ns - (30 * 24 * 3600 * 1e9),
            expiry_date_ns=expiring_later,
        )
        self.safety.add_training_record(
            crew_id="crew_003",
            training_type=TrainingType.BASIC_SAFETY,
            completion_date_ns=self.now_ns - (400 * 24 * 3600 * 1e9),
            expiry_date_ns=expired,
        )

        expiring = self.safety.check_training_expiry(days_ahead=30)
        self.assertEqual(len(expiring), 2)

        # Check that expired is flagged
        expired_records = [e for e in expiring if e["is_expired"]]
        self.assertEqual(len(expired_records), 1)
        self.assertEqual(expired_records[0]["crew_id"], "crew_003")


class TestDrillManagement(unittest.TestCase):
    """Test safety drill management."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.safety = CrewSafety("test_vessel", data_dir=self.temp_dir)
        self.now_ns = time.time_ns()

    def test_log_safety_drill(self):
        """Test logging a safety drill."""
        scheduled_ns = self.now_ns

        drill = self.safety.log_safety_drill(
            drill_type=DrillType.MOB_DRILL,
            scheduled_date_ns=scheduled_ns,
            participants=["crew_001", "crew_002", "crew_003"],
            score=85.0,
            deficiencies=["Some crew didn't don PFDs quickly"],
            strengths=["Good communication", "Quick response"],
            evaluator="Captain",
            response_time_seconds=120.0,
        )

        self.assertEqual(drill.drill_type, DrillType.MOB_DRILL)
        self.assertEqual(len(drill.participants), 3)
        self.assertEqual(drill.score, 85.0)
        self.assertEqual(len(drill.deficiencies), 1)
        self.assertEqual(len(drill.strengths), 2)
        self.assertEqual(drill.response_time_seconds, 120.0)

    def test_log_drill_with_string_type(self):
        """Test logging drill with string type."""
        drill = self.safety.log_safety_drill(
            drill_type="FIRE_DRILL",
            scheduled_date_ns=self.now_ns,
            participants=["crew_001"],
        )

        self.assertEqual(drill.drill_type, DrillType.FIRE_DRILL)

    def test_get_drill_history(self):
        """Test retrieving drill history."""
        self.safety.log_safety_drill(
            DrillType.MOB_DRILL,
            self.now_ns,
            ["crew_001"],
            score=90.0,
        )
        self.safety.log_safety_drill(
            DrillType.FIRE_DRILL,
            self.now_ns,
            ["crew_001"],
            score=85.0,
        )

        all_drills = self.safety.get_drill_history()
        self.assertEqual(len(all_drills), 2)

        mob_drills = self.safety.get_drill_history(drill_type=DrillType.MOB_DRILL)
        self.assertEqual(len(mob_drills), 1)
        self.assertEqual(mob_drills[0].drill_type, DrillType.MOB_DRILL)

    def test_get_overdue_drills(self):
        """Test identifying overdue drills."""
        # Drill done 100 days ago
        old_drill_ns = self.now_ns - (100 * 24 * 3600 * 1e9)

        # Simulate drill done in past
        drill = SafetyDrill(
            drill_type=DrillType.MOB_DRILL,
            scheduled_date_ns=old_drill_ns,
            completed_date_ns=old_drill_ns,
            participants=["crew_001"],
        )
        self.safety._drills.append(drill)

        overdue = self.safety.get_overdue_drills(days_threshold=90)
        self.assertGreater(len(overdue), 0)

        mob_overdue = [d for d in overdue if d["drill_type"] == "MOB_DRILL"]
        self.assertEqual(len(mob_overdue), 1)
        self.assertGreater(mob_overdue[0]["days_since_last_drill"], 90)


class TestEquipmentManagement(unittest.TestCase):
    """Test safety equipment management."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.safety = CrewSafety("test_vessel", data_dir=self.temp_dir)
        self.now_ns = time.time_ns()

    def test_add_safety_equipment(self):
        """Test adding safety equipment."""
        expiry_ns = self.now_ns + (365 * 24 * 3600 * 1e9)

        equipment = self.safety.add_safety_equipment(
            equipment_id="EPIRB_001",
            equipment_type=EquipmentType.EPIRB,
            location="Bridge",
            expiry_date_ns=expiry_ns,
            model="McMurdo FastFind",
            serial_number="SN12345",
        )

        self.assertEqual(equipment.equipment_id, "EPIRB_001")
        self.assertEqual(equipment.equipment_type, EquipmentType.EPIRB)
        self.assertEqual(equipment.location, "Bridge")
        self.assertEqual(equipment.model, "McMurdo FastFind")

    def test_add_equipment_with_string_type(self):
        """Test adding equipment with string type."""
        equipment = self.safety.add_safety_equipment(
            equipment_id="LJ_001",
            equipment_type="LIFE_JACKET",
            location="Port locker",
        )

        self.assertEqual(equipment.equipment_type, EquipmentType.LIFE_JACKET)

    def test_get_equipment_by_type(self):
        """Test filtering equipment by type."""
        self.safety.add_safety_equipment("LJ_001", EquipmentType.LIFE_JACKET, "Port")
        self.safety.add_safety_equipment("LJ_002", EquipmentType.LIFE_JACKET, "Starboard")
        self.safety.add_safety_equipment("EPIRB_001", EquipmentType.EPIRB, "Bridge")

        life_jackets = self.safety.get_safety_equipment(equipment_type=EquipmentType.LIFE_JACKET)
        self.assertEqual(len(life_jackets), 2)

        epirbs = self.safety.get_safety_equipment(equipment_type=EquipmentType.EPIRB)
        self.assertEqual(len(epirbs), 1)

    def test_get_equipment_by_status(self):
        """Test filtering equipment by status."""
        self.safety.add_safety_equipment("LJ_001", EquipmentType.LIFE_JACKET, "Port")
        self.safety.add_safety_equipment("EPIRB_001", EquipmentType.EPIRB, "Bridge")

        # Mark one as unserviceable
        self.safety.inspect_equipment("LJ_001", EquipmentStatus.UNSERVICEABLE)

        serviceable = self.safety.get_safety_equipment(status=EquipmentStatus.SERVICEABLE)
        unserviceable = self.safety.get_safety_equipment(status=EquipmentStatus.UNSERVICEABLE)

        self.assertEqual(len(serviceable), 1)
        self.assertEqual(len(unserviceable), 1)

    def test_inspect_equipment(self):
        """Test equipment inspection."""
        equipment = self.safety.add_safety_equipment(
            "LJ_001",
            EquipmentType.LIFE_JACKET,
            "Port",
        )

        # Mark as needs inspection
        inspected = self.safety.inspect_equipment(
            "LJ_001",
            EquipmentStatus.NEEDS_INSPECTION,
            notes="Strap showing wear",
        )

        self.assertEqual(inspected.status, EquipmentStatus.NEEDS_INSPECTION)
        self.assertEqual(inspected.inspection_notes, "Strap showing wear")
        self.assertGreater(inspected.last_inspected_ns, 0)

    def test_check_equipment_expiry(self):
        """Test checking for expiring equipment."""
        # Expiring in 7 days
        expiring_soon = self.now_ns + (7 * 24 * 3600 * 1e9)
        # Expiring in 60 days
        expiring_later = self.now_ns + (60 * 24 * 3600 * 1e9)
        # Already expired
        expired = self.now_ns - (10 * 24 * 3600 * 1e9)

        self.safety.add_safety_equipment("EPIRB_001", EquipmentType.EPIRB, "Bridge", expiry_date_ns=expiring_soon)
        self.safety.add_safety_equipment("RAFT_001", EquipmentType.LIFE_RAFT, "Deck", expiry_date_ns=expiring_later)
        self.safety.add_safety_equipment("FLARE_001", EquipmentType.FLARES, "Locker", expiry_date_ns=expired)

        expiring = self.safety.check_equipment_expiry(days_ahead=30)
        self.assertEqual(len(expiring), 2)

        # Check that expired is flagged
        expired_items = [e for e in expiring if e["is_expired"]]
        self.assertEqual(len(expired_items), 1)
        self.assertEqual(expired_items[0]["equipment_id"], "FLARE_001")


class TestPPEManagement(unittest.TestCase):
    """Test PPE management."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.safety = CrewSafety("test_vessel", data_dir=self.temp_dir)
        self.now_ns = time.time_ns()

    def test_issue_ppe(self):
        """Test issuing PPE to crew member."""
        expiry_ns = self.now_ns + (365 * 24 * 3600 * 1e9)

        ppe = self.safety.issue_ppe(
            crew_id="crew_001",
            ppe_type=PPEType.HARD_HAT,
            size="Large",
            brand="MSA",
            serial_number="HH12345",
            expiry_date_ns=expiry_ns,
        )

        self.assertEqual(ppe.crew_id, "crew_001")
        self.assertEqual(ppe.ppe_type, PPEType.HARD_HAT)
        self.assertEqual(ppe.size, "Large")
        self.assertEqual(ppe.brand, "MSA")

    def test_issue_ppe_with_string_type(self):
        """Test issuing PPE with string type."""
        ppe = self.safety.issue_ppe(
            crew_id="crew_001",
            ppe_type="SAFETY_BOOTS",
            size="10",
        )

        self.assertEqual(ppe.ppe_type, PPEType.SAFETY_BOOTS)

    def test_get_crew_ppe(self):
        """Test retrieving PPE for crew member."""
        self.safety.issue_ppe("crew_001", PPEType.HARD_HAT, "Large")
        self.safety.issue_ppe("crew_001", PPEType.SAFETY_BOOTS, "10")
        self.safety.issue_ppe("crew_001", PPEType.GLOVES, "Large")
        self.safety.issue_ppe("crew_002", PPEType.HARD_HAT, "Medium")

        crew_001_ppe = self.safety.get_crew_ppe("crew_001")
        self.assertEqual(len(crew_001_ppe), 3)

        crew_002_ppe = self.safety.get_crew_ppe("crew_002")
        self.assertEqual(len(crew_002_ppe), 1)

    def test_get_ppe_by_type(self):
        """Test filtering PPE by type."""
        self.safety.issue_ppe("crew_001", PPEType.HARD_HAT, "Large")
        self.safety.issue_ppe("crew_001", PPEType.SAFETY_GLASSES, "Universal")
        self.safety.issue_ppe("crew_001", PPEType.HARD_HAT, "Medium")

        hats = self.safety.get_crew_ppe("crew_001", ppe_type=PPEType.HARD_HAT)
        self.assertEqual(len(hats), 2)


class TestSafetySummary(unittest.TestCase):
    """Test safety summary generation."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.safety = CrewSafety("test_vessel", data_dir=self.temp_dir)
        self.now_ns = time.time_ns()

    def test_get_safety_summary(self):
        """Test generating safety summary."""
        # Add some data
        self.safety.log_safety_incident(IncidentType.NEAR_MISS, IncidentSeverity.MINOR, "Near miss")
        self.safety.add_safety_equipment("LJ_001", EquipmentType.LIFE_JACKET, "Port")
        self.safety.log_safety_drill(DrillType.MOB_DRILL, self.now_ns, ["crew_001"], score=85.0)

        summary = self.safety.get_safety_summary(days=30)

        self.assertIn("incident_statistics", summary)
        self.assertIn("training", summary)
        self.assertIn("equipment", summary)
        self.assertIn("drills", summary)
        self.assertIn("ppe", summary)

        self.assertEqual(summary["incident_statistics"]["total_incidents"], 1)
        self.assertEqual(summary["equipment"]["total_items"], 1)
        self.assertEqual(summary["drills"]["total_conducted"], 1)


class TestAlertGeneration(unittest.TestCase):
    """Test alert generation."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.safety = CrewSafety("test_vessel", data_dir=self.temp_dir)
        self.now_ns = time.time_ns()

    def test_training_expiry_alerts(self):
        """Test training expiry alerts."""
        expiring_soon = self.now_ns + (7 * 24 * 3600 * 1e9)
        expired = self.now_ns - (10 * 24 * 3600 * 1e9)

        self.safety.add_training_record(
            crew_id="crew_001",
            training_type=TrainingType.FIRST_AID,
            completion_date_ns=self.now_ns - (30 * 24 * 3600 * 1e9),
            expiry_date_ns=expiring_soon,
        )
        self.safety.add_training_record(
            crew_id="crew_002",
            training_type=TrainingType.MOB_DRILL,
            completion_date_ns=self.now_ns - (400 * 24 * 3600 * 1e9),
            expiry_date_ns=expired,
        )

        alerts = self.safety.get_alerts()

        # Should have alerts for both expiring and expired
        training_alerts = [a for a in alerts if a["code"].startswith("TRAINING")]
        self.assertGreater(len(training_alerts), 0)

        # Check severity levels
        high_alerts = [a for a in training_alerts if a["severity"] == "high"]
        critical_alerts = [a for a in training_alerts if a["severity"] == "critical"]
        self.assertGreater(len(high_alerts), 0)
        self.assertGreater(len(critical_alerts), 0)

    def test_equipment_expiry_alerts(self):
        """Test equipment expiry alerts."""
        expiring_soon = self.now_ns + (7 * 24 * 3600 * 1e9)
        expired = self.now_ns - (10 * 24 * 3600 * 1e9)

        self.safety.add_safety_equipment("EPIRB_001", EquipmentType.EPIRB, "Bridge", expiry_date_ns=expiring_soon)
        self.safety.add_safety_equipment("FLARE_001", EquipmentType.FLARES, "Locker", expiry_date_ns=expired)

        alerts = self.safety.get_alerts()

        equipment_alerts = [a for a in alerts if a["code"].startswith("EQUIPMENT")]
        self.assertGreater(len(equipment_alerts), 0)

    def test_unresolved_incident_alerts(self):
        """Test unresolved incident alerts."""
        self.safety.log_safety_incident(IncidentType.MOB, IncidentSeverity.CRITICAL, "MOB incident")
        self.safety.log_safety_incident(IncidentType.INJURY, IncidentSeverity.MAJOR, "Major injury")

        alerts = self.safety.get_alerts()

        incident_alerts = [a for a in alerts if a["code"].startswith("INCIDENT")]
        self.assertEqual(len(incident_alerts), 2)

        # Check for critical alert
        critical_alerts = [a for a in incident_alerts if a["severity"] == "critical"]
        self.assertEqual(len(critical_alerts), 1)

    def test_equipment_status_alerts(self):
        """Test equipment status alerts."""
        self.safety.add_safety_equipment("LJ_001", EquipmentType.LIFE_JACKET, "Port")
        self.safety.inspect_equipment("LJ_001", EquipmentStatus.UNSERVICEABLE)

        alerts = self.safety.get_alerts()

        unserviceable_alerts = [a for a in alerts if a["code"] == "EQUIPMENT_UNSERVICEABLE"]
        self.assertEqual(len(unserviceable_alerts), 1)


class TestPersistence(unittest.TestCase):
    """Test data persistence and loading."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def test_incident_persistence(self):
        """Test that incidents are persisted and loaded."""
        # Create system and add data
        safety1 = CrewSafety("test_vessel", data_dir=self.temp_dir)
        incident = safety1.log_safety_incident(
            IncidentType.MOB,
            IncidentSeverity.CRITICAL,
            "Test incident",
        )

        # Create new system instance (should load data)
        safety2 = CrewSafety("test_vessel", data_dir=self.temp_dir)
        loaded_incidents = safety2.get_safety_incidents()

        self.assertEqual(len(loaded_incidents), 1)
        self.assertEqual(loaded_incidents[0].incident_id, incident.incident_id)
        self.assertEqual(loaded_incidents[0].description, "Test incident")

    def test_equipment_persistence(self):
        """Test that equipment is persisted and loaded."""
        safety1 = CrewSafety("test_vessel", data_dir=self.temp_dir)
        equipment = safety1.add_safety_equipment(
            "EPIRB_001",
            EquipmentType.EPIRB,
            "Bridge",
        )

        safety2 = CrewSafety("test_vessel", data_dir=self.temp_dir)
        loaded_equipment = safety2.get_safety_equipment()

        self.assertEqual(len(loaded_equipment), 1)
        self.assertEqual(loaded_equipment[0].equipment_id, "EPIRB_001")

    def test_training_persistence(self):
        """Test that training records are persisted and loaded."""
        safety1 = CrewSafety("test_vessel", data_dir=self.temp_dir)
        safety1.add_training_record(
            "crew_001",
            TrainingType.BASIC_SAFETY,
            time.time_ns(),
        )

        safety2 = CrewSafety("test_vessel", data_dir=self.temp_dir)
        loaded_training = safety2.get_crew_training("crew_001")

        self.assertEqual(len(loaded_training), 1)
        self.assertEqual(loaded_training[0].crew_id, "crew_001")


class TestIntegration(unittest.TestCase):
    """Integration tests for crew safety system."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.safety = CrewSafety("test_vessel", data_dir=self.temp_dir)
        self.now_ns = time.time_ns()

    def test_complete_safety_workflow(self):
        """Test complete safety workflow from incident to resolution."""
        # Log an incident (MAJOR severity will generate alerts)
        incident = self.safety.log_safety_incident(
            IncidentType.INJURY,
            IncidentSeverity.MAJOR,
            "Crew member seriously injured while handling gear",
            location_lat=59.5,
            location_lon=-152.3,
            crew_involved=["crew_001"],
        )

        # Check it appears in alerts
        alerts = self.safety.get_alerts()
        incident_alerts = [a for a in alerts if a["code"].startswith("INCIDENT")]
        self.assertEqual(len(incident_alerts), 1)

        # Resolve the incident
        self.safety.resolve_incident(
            incident.incident_id,
            root_cause="Improper lifting technique",
            lessons_learned="Need training on proper gear handling",
            corrective_actions=["Conduct gear handling safety training"],
        )

        # Check that alert is cleared
        alerts_after = self.safety.get_alerts()
        incident_alerts_after = [a for a in alerts_after if a["code"].startswith("INCIDENT")]
        self.assertEqual(len(incident_alerts_after), 0)

    def test_mob_incident_with_protocol(self):
        """Test MOB incident with protocol activation."""
        # Log MOB incident
        incident = self.safety.log_safety_incident(
            IncidentType.MOB,
            IncidentSeverity.CRITICAL,
            "Crew member fell overboard",
            location_lat=59.5,
            location_lon=-152.3,
            crew_involved=["crew_001"],
        )

        # Activate MOB protocol
        protocol = self.safety.activate_emergency_protocol(ProtocolType.MOB_RESPONSE)

        # Verify protocol has steps
        self.assertGreater(len(protocol.steps), 0)
        self.assertIn("MOB", str(protocol.steps).upper())

        # Verify protocol has required equipment
        self.assertIn(EquipmentType.LIFE_JACKET, protocol.equipment_required)

    def test_training_drill_equipment_integration(self):
        """Test integration between training, drills, and equipment."""
        # Add training
        expiry_ns = self.now_ns + (365 * 24 * 3600 * 1e9)
        self.safety.add_training_record(
            "crew_001",
            TrainingType.MOB_DRILL,
            self.now_ns,
            expiry_date_ns=expiry_ns,
            score=95.0,
        )

        # Add equipment
        self.safety.add_safety_equipment("LJ_001", EquipmentType.LIFE_JACKET, "Port")
        self.safety.add_safety_equipment("MOB_001", EquipmentType.MOB_DEVICE, "Bridge")

        # Log drill
        drill = self.safety.log_safety_drill(
            DrillType.MOB_DRILL,
            self.now_ns,
            ["crew_001"],
            score=88.0,
            response_time_seconds=105.0,
        )

        # Get safety summary
        summary = self.safety.get_safety_summary()

        self.assertEqual(summary["training"]["valid_certifications"], 1)
        self.assertEqual(summary["equipment"]["total_items"], 2)
        self.assertEqual(summary["drills"]["total_conducted"], 1)
        self.assertEqual(summary["drills"]["average_score"], 88.0)


class TestWatcherFrame(unittest.TestCase):
    """Test watcher frame integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.safety = CrewSafety("test_vessel", data_dir=self.temp_dir)

    def test_get_watcher_frame(self):
        """Test generating watcher frame."""
        frame = self.safety.get_watcher_frame()

        self.assertIn("timestamp_ns", frame)
        self.assertIn("total_incidents", frame)
        self.assertIn("incident_severity_counts", frame)
        self.assertIn("equipment_issues", frame)
        self.assertIn("total_equipment", frame)
        self.assertIn("active_alerts", frame)

    def test_watcher_frame_with_data(self):
        """Test watcher frame with actual data."""
        # Add some incidents
        self.safety.log_safety_incident(IncidentType.MOB, IncidentSeverity.CRITICAL, "MOB")
        self.safety.log_safety_incident(IncidentType.NEAR_MISS, IncidentSeverity.MINOR, "Near miss")

        # Add equipment issues
        self.safety.add_safety_equipment("LJ_001", EquipmentType.LIFE_JACKET, "Port")
        self.safety.inspect_equipment("LJ_001", EquipmentStatus.UNSERVICEABLE)

        frame = self.safety.get_watcher_frame()

        self.assertEqual(frame["total_incidents"], 2)
        self.assertEqual(frame["equipment_issues"], 1)


class TestToDict(unittest.TestCase):
    """Test to_dict serialization."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.safety = CrewSafety("test_vessel", data_dir=self.temp_dir)

    def test_to_dict(self):
        """Test complete to_dict serialization."""
        # Add some data
        self.safety.log_safety_incident(IncidentType.MOB, IncidentSeverity.CRITICAL, "MOB")
        self.safety.add_training_record("crew_001", TrainingType.BASIC_SAFETY, time.time_ns())
        self.safety.log_safety_drill(DrillType.MOB_DRILL, time.time_ns(), ["crew_001"])
        self.safety.add_safety_equipment("LJ_001", EquipmentType.LIFE_JACKET, "Port")
        self.safety.issue_ppe("crew_001", PPEType.HARD_HAT, "Large")

        data = self.safety.to_dict()

        self.assertIn("vessel_id", data)
        self.assertIn("incidents", data)
        self.assertIn("protocols", data)
        self.assertIn("training", data)
        self.assertIn("drills", data)
        self.assertIn("equipment", data)
        self.assertIn("ppe", data)
        self.assertIn("watcher_frame", data)
        self.assertIn("alerts", data)

        self.assertEqual(data["vessel_id"], "test_vessel")
        self.assertEqual(len(data["incidents"]), 1)
        self.assertEqual(len(data["training"]), 1)


if __name__ == "__main__":
    unittest.main()
