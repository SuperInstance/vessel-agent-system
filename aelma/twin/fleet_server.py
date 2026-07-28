"""FleetServer: Production fleet management server with bridge integration.

This extends FleetManager to run as a complete server that:
- Connects to multiple vessel bridges as WebSocket clients
- Ingestes telemetry from all vessels
- Provides fleet-wide WebSocket viewer API
- Broadcasts fleet snapshots to dashboard viewers

Example usage:
    python -m twin.fleet_server --config fleet_config.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Any

import websockets

from .fleet_manager import FleetManager, VesselInstance

log = logging.getLogger("aelma.fleet_server")

# Default configuration
DEFAULT_FLEET_CONFIG_PATH = "fleet_config.json"
DEFAULT_FLEET_VIEWER_PORT = 8092


class FleetServer:
    """Production fleet server with bridge connections and viewer API."""

    def __init__(self, config_path: Path | str) -> None:
        """Initialize fleet server from configuration file.

        Parameters
        ----------
        config_path:
            Path to fleet configuration JSON file
        """
        self.config_path = Path(config_path)
        self.config = self._load_config()

        # Create fleet manager
        self.fleet = FleetManager(
            viewer_port=self.config.get("fleet_viewer_port", DEFAULT_FLEET_VIEWER_PORT),
            broadcast_interval=self.config.get("broadcast_interval", 1.0),
            data_dir=self.config.get("data_dir", "fleet_data"),
        )

        # Register all vessels
        self.bridge_connections: dict[str, Any] = {}
        for vessel_id, vessel_config in self.config.get("vessels", {}).items():
            self.fleet.register_vessel(vessel_id, vessel_config)

        # Background tasks
        self._tasks: set[Any] = set()
        self._running = False

    def _load_config(self) -> dict[str, Any]:
        """Load fleet configuration from JSON file.

        Expected format:
        {
            "data_dir": "fleet_data",
            "fleet_viewer_port": 8092,
            "broadcast_interval": 1.0,
            "vessels": {
                "US-AK-FVEILEEN-51": {
                    "bridge_url": "ws://localhost:8000",
                    "name": "F/V Pioneer",
                    "vessel_type": "fishing",
                    "viewer_port": 8090,
                    "bathymetry_path": "bathymetry.json",
                    "a2a_log_path": "a2a.jsonl",
                    "oplog_path": "oplog.jsonl"
                },
                ...
            }
        }
        """
        if not self.config_path.exists():
            log.error("Config file not found: %s", self.config_path)
            sys.exit(1)

        with open(self.config_path) as f:
            config = json.load(f)

        # Validate required fields
        if "vessels" not in config:
            log.error("Config missing 'vessels' key")
            sys.exit(1)

        return config

    async def _bridge_loop(self, vessel_id: str) -> None:
        """Connect to a vessel's bridge and ingest telemetry packets.

        Runs as a background task for each registered vessel.

        Parameters
        ----------
        vessel_id:
            Vessel to connect to
        """
        vessel = self.fleet.get_vessel(vessel_id)
        bridge_url = vessel.config.get("bridge_url")

        if not bridge_url:
            log.error("No bridge_url for vessel %s", vessel_id)
            return

        backoff = 1.0
        while self._running:
            try:
                log.info("Connecting to %s bridge at %s", vessel_id, bridge_url)
                async with websockets.connect(bridge_url) as ws:
                    log.info("Connected to %s bridge", vessel_id)
                    vessel.bridge_connected = True
                    backoff = 1.0

                    try:
                        async for raw in ws:
                            if not self._running:
                                break

                            try:
                                packet = json.loads(raw)
                                if isinstance(packet, list):
                                    for p in packet:
                                        self.fleet.handle_telemetry(vessel_id, p)
                                else:
                                    self.fleet.handle_telemetry(vessel_id, packet)
                            except json.JSONDecodeError as exc:
                                log.warning("Invalid JSON from %s: %s", vessel_id, exc)
                            except KeyError as exc:
                                log.warning("Malformed packet from %s: %s", vessel_id, exc)
                    finally:
                        vessel.bridge_connected = False

            except (OSError, websockets.WebSocketException) as exc:
                log.warning(
                    "%s bridge connection failed: %s; retrying in %.0fs",
                    vessel_id,
                    exc,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)

    async def start(self) -> None:
        """Start the fleet server.

        Launches:
        - Bridge connections for all vessels
        - Fleet viewer WebSocket server
        - Snapshot broadcast loop
        """
        self._running = True
        log.info("Starting fleet server with %d vessels", len(self.fleet.vessels))

        # Start bridge connections
        for vessel_id in self.fleet.list_vessels():
            task = asyncio.create_task(self._bridge_loop(vessel_id))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

        # Start fleet viewer server
        log.info(
            "Fleet viewer WebSocket server on port %d",
            self.fleet.viewer_port,
        )

        try:
            async with websockets.serve(
                self.fleet._fleet_viewer_handler,
                "0.0.0.0",
                self.fleet.viewer_port,
            ):
                # Start broadcast loop
                broadcast_task = asyncio.create_task(self.fleet._broadcast_loop())
                self._tasks.add(broadcast_task)
                broadcast_task.add_done_callback(self._tasks.discard)

                log.info("Fleet server running")
                await asyncio.gather(*self._tasks)
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop the fleet server and cleanup."""
        log.info("Stopping fleet server")
        self._running = False

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        self._tasks.clear()
        log.info("Fleet server stopped")

    def get_status(self) -> dict[str, Any]:
        """Get fleet server status.

        Returns
        -------
        dict
            Status summary including fleet status and server info
        """
        status = self.fleet.get_status()
        status["config_path"] = str(self.config_path)
        status["running"] = self._running
        return status


def main() -> int:
    """Run the fleet server."""
    parser = argparse.ArgumentParser(description="AELMA Fleet Server")
    parser.add_argument(
        "--config",
        type=str,
        default=DEFAULT_FLEET_CONFIG_PATH,
        help=f"Path to fleet config JSON (default: {DEFAULT_FLEET_CONFIG_PATH})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Override fleet viewer port",
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

    # Create server
    server = FleetServer(args.config)

    # Override port if specified
    if args.port:
        server.fleet.viewer_port = args.port

    # Setup signal handlers
    loop = asyncio.get_event_loop()

    def signal_handler():
        log.info("Received shutdown signal")
        loop.create_task(server.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    # Run server
    try:
        asyncio.run(server.start())
    except asyncio.CancelledError:
        log.info("Server cancelled")
    except KeyboardInterrupt:
        log.info("Keyboard interrupt")
    finally:
        log.info("Exiting")
        return 0


if __name__ == "__main__":
    sys.exit(main())
