"""Fleet viewer client example.

Demonstrates how to connect to the fleet manager WebSocket API
and receive real-time fleet snapshots.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import websockets

log = logging.getLogger("aelma.fleet_viewer")


class FleetViewerClient:
    """Client for connecting to the fleet manager WebSocket API."""

    def __init__(
        self,
        url: str = "ws://localhost:8092",
    ) -> None:
        """Initialize the fleet viewer client.

        Parameters
        ----------
        url:
            WebSocket URL to fleet manager
        """
        self.url = url
        self._ws: Any | None = None
        self._connected = False

    async def connect(self) -> None:
        """Connect to the fleet manager."""
        log.info("Connecting to fleet manager at %s", self.url)
        self._ws = await websockets.connect(self.url)
        self._connected = True
        log.info("Connected to fleet manager")

    async def disconnect(self) -> None:
        """Disconnect from the fleet manager."""
        if self._ws:
            await self._ws.close()
            self._connected = False
            log.info("Disconnected from fleet manager")

    async def receive_snapshots(self, callback: callable[[dict], None]) -> None:
        """Receive and process fleet snapshots.

        Parameters
        ----------
        callback:
            Async function called with each snapshot dict
        """
        if not self._connected:
            raise RuntimeError("Not connected to fleet manager")

        log.info("Listening for fleet snapshots...")
        async for message in self._ws:
            try:
                snapshot = json.loads(message)
                await callback(snapshot)
            except json.JSONDecodeError as exc:
                log.error("Invalid JSON: %s", exc)
            except Exception as exc:
                log.error("Error processing snapshot: %s", exc)

    async def get_fleet_status(self) -> dict:
        """Get current fleet status (single snapshot)."""
        if not self._connected:
            raise RuntimeError("Not connected to fleet manager")

        message = await self._ws.recv()
        return json.loads(message)


async def print_snapshot(snapshot: dict) -> None:
    """Print a formatted fleet snapshot.

    Parameters
    ----------
    snapshot:
        Fleet snapshot dict
    """
    timestamp = snapshot.get("timestamp_ns", 0) / 1e9
    vessel_count = snapshot.get("vessel_count", 0)
    vessels = snapshot.get("vessels", {})
    analytics = snapshot.get("analytics", {})

    print("\n" + "=" * 60)
    print(f"FLEET SNAPSHOT - {timestamp:.2f}")
    print("=" * 60)
    print(f"Vessels: {vessel_count}")

    # Print vessel positions
    print("\nVESSEL POSITIONS:")
    for vessel_id, vessel_state in vessels.items():
        name = vessel_state.get("name", vessel_id)
        pose = vessel_state.get("pose", {})
        lat = pose.get("lat")
        lon = pose.get("lon")
        heading = pose.get("heading_deg")
        speed = pose.get("speed_kn")

        position_str = f"  {name} ({vessel_id})"
        if lat is not None and lon is not None:
            position_str += f"\n    Position: {lat:.4f}, {lon:.4f}"
            if heading is not None:
                position_str += f" | Heading: {heading:.0f}°"
            if speed is not None:
                position_str += f" | Speed: {speed:.1f} kn"
        else:
            position_str += "\n    No position fix"

        print(position_str)

    # Print analytics
    print("\nFLEET ANALYTICS:")
    position_summary = analytics.get("position_summary", {})
    if position_summary.get("min_lat") is not None:
        print(f"  Bounds:")
        print(f"    Latitude: {position_summary['min_lat']:.4f} to {position_summary['max_lat']:.4f}")
        print(f"    Longitude: {position_summary['min_lon']:.4f} to {position_summary['max_lon']:.4f}")
        print(f"    Centroid: {position_summary['centroid_lat']:.4f}, {position_summary['centroid_lon']:.4f}")

    clustering = analytics.get("clustering", {})
    if clustering.get("clusters"):
        print(f"  Clusters: {clustering['clusters']}")
        print(f"    Largest cluster: {clustering['largest_cluster_size']} vessels")

    alerts = analytics.get("alerts", {})
    critical = alerts.get("critical", [])
    warning = alerts.get("warning", [])

    if critical:
        print(f"\n  CRITICAL ALERTS ({len(critical)}):")
        for alert in critical[:5]:  # Show first 5
            print(f"    ! {alert}")

    if warning:
        print(f"\n  WARNINGS ({len(warning)}):")
        for alert in warning[:5]:  # Show first 5
            print(f"    ! {alert}")


async def monitor_fleet(url: str = "ws://localhost:8092", duration: int = 60) -> None:
    """Monitor the fleet for a specified duration.

    Parameters
    ----------
    url:
        Fleet manager WebSocket URL
    duration:
        Monitor duration in seconds (0 for infinite)
    """
    client = FleetViewerClient(url)

    try:
        await client.connect()

        # Monitor for specified duration
        if duration > 0:
            print(f"Monitoring fleet for {duration} seconds...")
            await asyncio.sleep_for(
                asyncio.create_task(client.receive_snapshots(print_snapshot)),
                duration,
            )
        else:
            print("Monitoring fleet (press Ctrl+C to stop)...")
            await client.receive_snapshots(print_snapshot)

    except asyncio.TimeoutError:
        print("\nMonitoring complete")
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
    finally:
        await client.disconnect()


def main() -> None:
    """Run the fleet viewer."""
    import argparse

    parser = argparse.ArgumentParser(description="AELMA Fleet Viewer")
    parser.add_argument(
        "--url",
        type=str,
        default="ws://localhost:8092",
        help="Fleet manager WebSocket URL (default: ws://localhost:8092)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Monitor duration in seconds, 0 for infinite (default: 60)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: INFO)",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Run monitor
    asyncio.run(monitor_fleet(args.url, args.duration))


if __name__ == "__main__":
    main()
