"""Quick demonstration of the fleet management system."""

import asyncio
import time
from twin.fleet_manager import FleetManager


async def demo_fleet_manager():
    """Demonstrate basic fleet manager usage."""
    print("=" * 60)
    print("AELMA Fleet Management System Demo")
    print("=" * 60)

    # Create fleet manager
    fleet = FleetManager(
        viewer_port=8092,
        broadcast_interval=1.0,
        data_dir="demo_fleet_data",
    )
    print("\nCreated fleet manager")

    # Register vessels
    print("\n--- Registering Vessels ---")
    fleet.register_vessel("US-AK-FVEILEEN-51", {
        "bridge_url": "ws://localhost:8000",
        "name": "F/V Pioneer",
        "vessel_type": "fishing",
        "viewer_port": 8090,
    })
    print("Registered: F/V Pioneer")

    fleet.register_vessel("US-AK-EXPLORER-42", {
        "bridge_url": "ws://localhost:8001",
        "name": "F/V Explorer",
        "vessel_type": "fishing",
        "viewer_port": 8091,
    })
    print("Registered: F/V Explorer")

    fleet.register_vessel("US-AK-SURVEYOR-07", {
        "bridge_url": "ws://localhost:8002",
        "name": "R/V Surveyor",
        "vessel_type": "research",
        "viewer_port": 8093,
    })
    print("Registered: R/V Surveyor")

    # Simulate telemetry updates
    print("\n--- Simulating Telemetry Updates ---")

    # Update Pioneer position
    fleet.handle_telemetry("US-AK-FVEILEEN-51", {
        "channel": "position.lat",
        "value": 59.5,
        "timestamp_ns": int(time.time() * 1e9),
    })
    fleet.handle_telemetry("US-AK-FVEILEEN-51", {
        "channel": "position.lon",
        "value": -152.3,
        "timestamp_ns": int(time.time() * 1e9),
    })
    print("Updated F/V Pioneer position: 59.5N, -152.3W")

    # Update Explorer position
    fleet.handle_telemetry("US-AK-EXPLORER-42", {
        "channel": "position.lat",
        "value": 59.8,
        "timestamp_ns": int(time.time() * 1e9),
    })
    fleet.handle_telemetry("US-AK-EXPLORER-42", {
        "channel": "position.lon",
        "value": -151.8,
        "timestamp_ns": int(time.time() * 1e9),
    })
    print("Updated F/V Explorer position: 59.8N, -151.8W")

    # Update Surveyor position
    fleet.handle_telemetry("US-AK-SURVEYOR-07", {
        "channel": "position.lat",
        "value": 60.2,
        "timestamp_ns": int(time.time() * 1e9),
    })
    fleet.handle_telemetry("US-AK-SURVEYOR-07", {
        "channel": "position.lon",
        "value": -151.2,
        "timestamp_ns": int(time.time() * 1e9),
    })
    print("Updated R/V Surveyor position: 60.2N, -151.2W")

    # Get all positions
    print("\n--- All Vessel Positions ---")
    positions = fleet.get_all_positions()
    for vessel_id, pos in positions.items():
        if pos["lat"] is not None and pos["lon"] is not None:
            print(f"{pos['name']}: {pos['lat']:.4f}N, {pos['lon']:.4f}W")
        else:
            print(f"{pos['name']}: No position fix")

    # Get fleet snapshot
    print("\n--- Fleet Snapshot ---")
    snapshot = fleet.get_fleet_snapshot()
    analytics = snapshot["analytics"]

    print(f"Vessel count: {snapshot['vessel_count']}")
    print(f"Active vessels: {analytics['active_count']}")

    summary = analytics["position_summary"]
    if summary["min_lat"] is not None:
        print(f"Fleet bounds:")
        print(f"  Latitude: {summary['min_lat']:.4f} to {summary['max_lat']:.4f}")
        print(f"  Longitude: {summary['min_lon']:.4f} to {summary['max_lon']:.4f}")
        print(f"  Centroid: {summary['centroid_lat']:.4f}, {summary['centroid_lon']:.4f}")

    # Distance matrix
    print("\n--- Inter-Vessel Distances ---")
    matrix = fleet.get_distance_matrix()
    for vid1 in matrix:
        for vid2 in matrix[vid1]:
            if vid1 < vid2:  # Only print each pair once
                dist = matrix[vid1][vid2]
                if dist is not None:
                    v1_name = fleet.get_vessel(vid1).name
                    v2_name = fleet.get_vessel(vid2).name
                    print(f"{v1_name} <-> {v2_name}: {dist:.1f}m")

    # Find nearest vessel
    print("\n--- Find Nearest Vessel ---")
    nearest = fleet.find_nearest(59.6, -152.0)
    if nearest:
        print(f"Nearest to (59.6N, -152.0W): {nearest['name']}")
        print(f"  Distance: {nearest['distance_m']:.1f}m")

    # Find vessels in radius
    print("\n--- Find Vessels in Radius ---")
    vessels_in_radius = fleet.find_vessels_in_radius(59.5, -152.3, 50000)
    print(f"Vessels within 50km of (59.5N, -152.3W):")
    for v in vessels_in_radius:
        print(f"  {v['name']}: {v['distance_m']:.1f}m")

    # Fleet operations
    print("\n--- Fleet Operations ---")
    results = await fleet.broadcast_to_all("test_action", {"message": "Hello fleet!"})
    print(f"Broadcast results: {len(results)} vessels reached")

    result = await fleet.send_to_vessel("US-AK-FVEILEEN-51", "specific_action", {"key": "value"})
    print(f"Send to vessel result: {result['status']}")

    # Get status
    print("\n--- Fleet Manager Status ---")
    status = fleet.get_status()
    print(f"Running: {status['running']}")
    print(f"Viewer port: {status['viewer_port']}")
    print(f"Vessel count: {status['vessel_count']}")
    print(f"Fleet viewers: {status['fleet_viewers']}")

    print("\n--- Demo Complete ---")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(demo_fleet_manager())
