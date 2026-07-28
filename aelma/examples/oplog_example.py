#!/usr/bin/env python3
"""OpLog usage example demonstrating vessel operations logging.

This example shows how to:
1. Create a TwinCore with OpLog enabled
2. Log crew operations (gear deployment, hauls, catch logging)
3. Query operations by filters
4. Export to different formats

Run from the aelma directory: python -m examples.oplog_example
"""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twin.core import TwinCore


async def main():
    """Demonstrate OpLog functionality."""
    print("=== AELMA OpLog Example ===\n")

    # Create a TwinCore with OpLog enabled
    twin = TwinCore(
        oplog_path="example_oplog.jsonl",
        oplog_max_bytes=10000,  # Rotate at 10KB
        oplog_keep=3,  # Keep 3 rotated files
    )

    print("1. Logging fishing operations...")
    print("-" * 50)

    # Simulate a fishing operation
    base_time = datetime(2026, 7, 28, 6, 0, 0, tzinfo=timezone.utc)

    # Deploy gear
    await twin.log_crew_action(
        "gear_deployed",
        "captain",
        "Deployed cod pot gear at 59.5N, -152.3W",
        {
            "gear_type": "cod_pot",
            "count": 50,
            "lat": 59.5,
            "lon": -152.3,
            "depth_m": 45
        },
        ts=base_time,
    )
    print(f"[{base_time.strftime('%H:%M')}] Deployed cod pot gear")

    # Start hauling
    haul_start = base_time + timedelta(hours=4)
    await twin.log_crew_action(
        "haul_started",
        "crewman",
        "Started hauling pot string 1",
        {"string_number": 1, "pot_count": 25},
        ts=haul_start,
    )
    print(f"[{haul_start.strftime('%H:%M')}] Started hauling")

    # Complete haul
    haul_end = haul_start + timedelta(minutes=30)
    await twin.log_crew_action(
        "haul_complete",
        "captain",
        "Completed haul of string 1, good catch",
        {
            "string_number": 1,
            "total_pots": 25,
            "duration_minutes": 30,
            "estimated_catch_lb": 1200
        },
        ts=haul_end,
    )
    print(f"[{haul_end.strftime('%H:%M')}] Completed haul")

    # Log catch
    await twin.log_crew_action(
        "catch_logged",
        "captain",
        "Logged catch: cod, 1200lb, grade A",
        {"species": "cod", "weight_lb": 1200, "grade": "A"},
        ts=haul_end + timedelta(minutes=5),
    )
    print(f"[{(haul_end + timedelta(minutes=5)).strftime('%H:%M')}] Logged catch")

    # Crew note
    await twin.log_crew_action(
        "crew_note",
        "captain",
        "Weather worsening, heading to port",
        {"wind_kts": 25, "sea_state": "4"},
        ts=base_time + timedelta(hours=6),
    )
    print(f"[{(base_time + timedelta(hours=6)).strftime('%H:%M')}] Weather note logged")

    # Manual alert
    await twin.log_crew_action(
        "manual_alert",
        "crewman",
        "Noticed debris in water, avoided",
        {"alert_type": "debris", "severity": "medium"},
        ts=base_time + timedelta(hours=2),
    )
    print(f"[{(base_time + timedelta(hours=2)).strftime('%H:%M')}] Debris alert logged")

    print(f"\nTotal operations logged: {twin.oplog.seq}")

    print("\n2. Querying operations...")
    print("-" * 50)

    # Query all gear operations
    gear_ops = await twin.query_oplog(entry_type="gear_deployed")
    print(f"Gear deployments: {len(gear_ops)}")

    # Query captain's operations
    captain_ops = await twin.query_oplog(crew="captain")
    print(f"Captain's operations: {len(captain_ops)}")

    # Query today's hauls
    today_hauls = await twin.query_oplog(
        entry_type={"haul_started", "haul_complete"},
        start_time=base_time,
    )
    print(f"Today's haul operations: {len(today_hauls)}")

    # Query manual alerts
    alerts = await twin.query_oplog(entry_type="manual_alert")
    print(f"Manual alerts: {len(alerts)}")

    print("\n3. Recent operations (newest first):")
    print("-" * 50)

    recent = await twin.query_oplog(limit=5)
    for i, op in enumerate(recent, 1):
        ts = datetime.fromisoformat(op["ts"]).strftime("%H:%M")
        print(f"{i}. [{ts}] {op['entry_type']} - {op['crew']}: {op['message']}")

    print("\n4. Export formats...")
    print("-" * 50)

    # JSON export
    json_export = await twin.export_oplog(format="json", limit=3)
    print(f"JSON export ({len(json_export)} chars):")
    print(json_export[:200] + "..." if len(json_export) > 200 else json_export)

    # CSV export
    csv_export = await twin.export_oplog(
        format="csv",
        entry_type="catch_logged",
        limit=1
    )
    print(f"\nCSV export ({len(csv_export)} chars):")
    print(csv_export)

    # Text export
    text_export = await twin.export_oplog(
        format="text",
        crew="captain",
        limit=2
    )
    print(f"\nText export ({len(text_export)} chars):")
    print(text_export[:300] + "..." if len(text_export) > 300 else text_export)

    print("\n5. Log statistics...")
    print("-" * 50)

    stats = await twin.oplog.stats()
    print(f"Path: {stats['path']}")
    print(f"Total records: {stats['records']}")
    print(f"File size: {stats['size_bytes']} bytes")
    print(f"Max bytes: {stats['max_bytes']}")
    print(f"Keep files: {stats['keep']}")

    print("\n=== Example complete ===")
    print(f"\nOpLog file created: {twin.oplog_path}")
    print("You can examine the file or delete it when done.")


if __name__ == "__main__":
    asyncio.run(main())
