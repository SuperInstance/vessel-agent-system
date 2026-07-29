"""Crew Safety System Demonstration

This script demonstrates all key features of the Crew Safety system.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tempfile
import time
from crew_safety import (
    CrewSafety,
    IncidentType,
    IncidentSeverity,
    ProtocolType,
    TrainingType,
    DrillType,
    EquipmentType,
    EquipmentStatus,
    PPEType,
)


def main():
    """Demonstrate crew safety system features."""

    print("=" * 70)
    print("CREW SAFETY SYSTEM DEMONSTRATION")
    print("=" * 70)

    # Create temporary directory for demo
    temp_dir = tempfile.mkdtemp()
    safety = CrewSafety("demo_vessel", data_dir=temp_dir)

    print("\n[1] SAFETY INCIDENT MANAGEMENT")
    print("-" * 70)

    # Log various incidents
    mob_incident = safety.log_safety_incident(
        IncidentType.MOB,
        IncidentSeverity.CRITICAL,
        "Crew member fell overboard during gear retrieval",
        location_lat=59.5,
        location_lon=-152.3,
        crew_involved=["crew_001"]
    )
    print(f"  Logged MOB incident: {mob_incident.incident_id}")

    injury_incident = safety.log_safety_incident(
        IncidentType.INJURY,
        IncidentSeverity.MODERATE,
        "Minor cut on finger while cutting bait",
        crew_involved=["crew_002"]
    )
    print(f"  Logged injury incident: {injury_incident.incident_id}")

    near_miss = safety.log_safety_incident(
        IncidentType.NEAR_MISS,
        IncidentSeverity.MINOR,
        "Near miss with swinging gear",
        crew_involved=["crew_003"]
    )
    print(f"  Logged near miss: {near_miss.incident_id}")

    # Resolve an incident
    safety.resolve_incident(
        injury_incident.incident_id,
        root_cause="Knife slipped on fish slime",
        lessons_learned="Need better cleaning procedures and cut-resistant gloves",
        corrective_actions=["Implement regular cleaning schedule", "Issue cut-resistant gloves"]
    )
    print(f"  Resolved injury incident")

    print("\n[2] EMERGENCY PROTOCOLS")
    print("-" * 70)

    # Activate MOB protocol
    mob_protocol = safety.activate_emergency_protocol(ProtocolType.MOB_RESPONSE)
    print(f"  Activated MOB protocol")
    print(f"  Steps: {len(mob_protocol.steps)} procedures")
    print(f"  Required equipment: {len(mob_protocol.equipment_required)} items")
    print(f"  Emergency contacts: {len(mob_protocol.priority_contacts)} contacts")

    # Show first few steps
    print("  First steps:")
    for i, step in enumerate(mob_protocol.steps[:3], 1):
        print(f"    {i}. {step}")

    print("\n[3] TRAINING MANAGEMENT")
    print("-" * 70)

    now_ns = time.time_ns()
    one_year_ns = 365 * 24 * 3600 * 1e9

    # Add training records
    safety.add_training_record(
        "crew_001",
        TrainingType.BASIC_SAFETY,
        now_ns,
        expiry_date_ns=now_ns + one_year_ns,
        certification_id="BST-2024-001",
        score=95.0
    )
    print("  Added Basic Safety training for crew_001 (score: 95.0)")

    safety.add_training_record(
        "crew_002",
        TrainingType.FIRST_AID,
        now_ns,
        expiry_date_ns=now_ns + one_year_ns,
        certification_id="FA-2024-002",
        score=88.0
    )
    print("  Added First Aid training for crew_002 (score: 88.0)")

    # Check training status
    crew_001_training = safety.get_crew_training("crew_001")
    print(f"  crew_001 has {len(crew_001_training)} valid certifications")

    print("\n[4] SAFETY DRILLS")
    print("-" * 70)

    # Log safety drills
    safety.log_safety_drill(
        DrillType.MOB_DRILL,
        now_ns,
        ["crew_001", "crew_002", "crew_003"],
        score=92.0,
        deficiencies=["Some crew delayed in donning PFDs"],
        strengths=["Excellent communication", "Quick MOB notification"],
        evaluator="Captain",
        response_time_seconds=98.0
    )
    print("  Logged MOB drill (score: 92.0, response: 98s)")

    safety.log_safety_drill(
        DrillType.FIRE_DRILL,
        now_ns,
        ["crew_001", "crew_002", "crew_003"],
        score=85.0,
        deficiencies=["Fire extinguisher placement unclear"],
        strengths=["Good evacuation procedures"],
        evaluator="Captain",
        response_time_seconds=75.0
    )
    print("  Logged Fire drill (score: 85.0, response: 75s)")

    print("\n[5] SAFETY EQUIPMENT")
    print("-" * 70)

    # Add safety equipment
    safety.add_safety_equipment(
        "EPIRB-001",
        EquipmentType.EPIRB,
        "Bridge",
        expiry_date_ns=now_ns + (5 * 365 * 24 * 3600 * 1e9),
        model="McMurdo FastFind"
    )
    print("  Added EPIRB-001 on Bridge")

    safety.add_safety_equipment(
        "LJ-001",
        EquipmentType.LIFE_JACKET,
        "Port locker",
        expiry_date_ns=now_ns + (3 * 365 * 24 * 3600 * 1e9)
    )
    print("  Added LJ-001 in Port locker")

    safety.add_safety_equipment(
        "LJ-002",
        EquipmentType.LIFE_JACKET,
        "Starboard locker",
        expiry_date_ns=now_ns + (3 * 365 * 24 * 3600 * 1e9)
    )
    print("  Added LJ-002 in Starboard locker")

    # Inspect equipment
    safety.inspect_equipment("LJ-001", EquipmentStatus.SERVICEABLE, "Good condition")
    print("  Inspected LJ-001: SERVICEABLE")

    print("\n[6] PPE MANAGEMENT")
    print("-" * 70)

    # Issue PPE
    safety.issue_ppe(
        "crew_001",
        PPEType.HARD_HAT,
        size="Large",
        brand="MSA"
    )
    print("  Issued hard hat to crew_001")

    safety.issue_ppe(
        "crew_001",
        PPEType.SAFETY_BOOTS,
        size="10",
        brand="Carolina"
    )
    print("  Issued safety boots to crew_001")

    safety.issue_ppe(
        "crew_002",
        PPEType.HARD_HAT,
        size="Medium",
        brand="MSA"
    )
    print("  Issued hard hat to crew_002")

    # Check PPE
    crew_001_ppe = safety.get_crew_ppe("crew_001")
    print(f"  crew_001 has {len(crew_001_ppe)} PPE items")

    print("\n[7] ALERTS GENERATION")
    print("-" * 70)

    # Get alerts
    alerts = safety.get_alerts()
    print(f"  Generated {len(alerts)} alerts:")

    # Show alerts by severity
    critical = [a for a in alerts if a["severity"] == "critical"]
    high = [a for a in alerts if a["severity"] == "high"]
    warning = [a for a in alerts if a["severity"] == "warning"]

    print(f"    - Critical: {len(critical)}")
    print(f"    - High: {len(high)}")
    print(f"    - Warning: {len(warning)}")

    # Show a few critical alerts
    if critical:
        print("\n  Sample critical alerts:")
        for alert in critical[:3]:
            print(f"    - {alert['code']}: {alert['message'][:60]}...")

    print("\n[8] SAFETY SUMMARY")
    print("-" * 70)

    # Get comprehensive summary
    summary = safety.get_safety_summary(days=30)

    print("  Incident Statistics:")
    print(f"    - Total incidents: {summary['incident_statistics']['total_incidents']}")
    print(f"    - Resolved: {summary['incident_statistics']['resolved_count']}")
    print(f"    - Unresolved: {summary['incident_statistics']['unresolved_count']}")

    print("\n  Training:")
    print(f"    - Valid certifications: {summary['training']['valid_certifications']}")
    print(f"    - Expiring soon: {summary['training']['expiring_soon']}")

    print("\n  Equipment:")
    print(f"    - Total items: {summary['equipment']['total_items']}")
    print(f"    - Serviceable: {summary['equipment']['by_status'].get('SERVICEABLE', 0)}")

    print("\n  Drills:")
    print(f"    - Conducted: {summary['drills']['total_conducted']}")
    print(f"    - Average score: {summary['drills']['average_score']}")

    print("\n  PPE:")
    print(f"    - Total issued: {summary['ppe']['total_issued']}")

    print("\n[9] WATCHER FRAME")
    print("-" * 70)

    # Get watcher frame for integration
    frame = safety.get_watcher_frame()
    print("  Watcher frame data:")
    print(f"    - Total incidents: {frame['total_incidents']}")
    print(f"    - Unresolved incidents: {frame['unresolved_incidents']}")
    print(f"    - Equipment issues: {frame['equipment_issues']}")
    print(f"    - Total equipment: {frame['total_equipment']}")
    print(f"    - Training records: {frame['total_training_records']}")
    print(f"    - Drills conducted: {frame['total_drills']}")
    print(f"    - PPE issued: {frame['total_ppe_issued']}")
    print(f"    - Active alerts: {frame['active_alerts']}")
    print(f"    - Critical alerts: {frame['critical_alerts']}")

    print("\n[10] INCIDENT STATISTICS")
    print("-" * 70)

    # Get incident statistics
    stats = safety.get_incident_statistics(days=30)
    print("  Incident statistics (30 days):")
    print(f"    - Total: {stats['total_incidents']}")
    print(f"    - Resolution rate: {stats['resolution_rate']:.1%}")

    print("\n  By type:")
    for itype, count in stats['incident_type_counts'].items():
        print(f"    - {itype}: {count}")

    print("\n  By severity:")
    for sev, count in stats['incident_severity_counts'].items():
        print(f"    - {sev}: {count}")

    print("\n" + "=" * 70)
    print("DEMONSTRATION COMPLETE")
    print("=" * 70)

    print("\nAll features demonstrated successfully!")
    print(f"Data saved to: {temp_dir}")


if __name__ == "__main__":
    main()
