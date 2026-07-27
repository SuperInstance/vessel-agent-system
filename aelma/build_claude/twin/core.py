"""TwinCore — the asyncio orchestrator for the AELMA digital twin.

Connects to the bridge as a WebSocket client, ingests TelemetryPackets,
maintains :class:`~twin.state.VesselState`, fuses depth soundings into a
:class:`~twin.bathymetry.BathymetryGrid`, and periodically broadcasts
``VesselStateSnapshot`` JSON to all connected viewer WebSocket clients.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from .state import VesselState
from .bathymetry import BathymetryGrid

logger = logging.getLogger("aelma.twin")

# Broadcast interval (seconds) for VesselStateSnapshot.
_DEFAULT_BROADCAST_INTERVAL = 1.0

# Bathymetry persistence interval (seconds).
_DEFAULT_PERSIST_INTERVAL = 60.0

# Reconnect delay (seconds) when the bridge link drops.
_RECONNECT_DELAY = 2.0


class TwinCore:
    """Async digital-twin core for the F/V EILEEN.

    Parameters
    ----------
    bridge_url
        WebSocket URL of the AELMA bridge (e.g. ``ws://localhost:8000``).
    viewer_port
        TCP port on which the twin serves VesselStateSnapshot to viewers.
    vessel_id
        ISO-style vessel identifier (e.g. ``"US-AK-FVEILEEN-51"``).
    bathymetry_path
        Filesystem path for bathymetry JSON persistence.
    broadcast_interval
        Seconds between snapshot broadcasts to viewers.
    """

    def __init__(
        self,
        bridge_url: str = "ws://localhost:8000",
        viewer_port: int = 8090,
        vessel_id: str = "US-AK-FVEILEEN-51",
        bathymetry_path: str = "bathymetry.json",
        broadcast_interval: float = _DEFAULT_BROADCAST_INTERVAL,
    ) -> None:
        """Initialise the twin core."""
        self.bridge_url = bridge_url
        self.viewer_port = viewer_port
        self.vessel_id = vessel_id
        self.bathymetry_path = bathymetry_path
        self.broadcast_interval = broadcast_interval

        self.state = VesselState()
        self.bathymetry = BathymetryGrid()

        # Connected viewer WebSocket clients (async set of ws connections).
        self._viewers: set = set()

        # Background tasks.
        self._tasks: list[asyncio.Task] = []

        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Start all twin background tasks and run until cancelled.

        This is the main entry point when the twin is launched as a
        long-running process.  It starts:

        * The bridge WebSocket client consumer.
        * The viewer WebSocket server.
        * The periodic broadcast loop.
        * The periodic bathymetry persistence loop.
        """
        self._running = True

        # Try to load existing bathymetry from disk.
        try:
            self.bathymetry.load(self.bathymetry_path)
            logger.info("Loaded bathymetry from %s", self.bathymetry_path)
        except FileNotFoundError:
            logger.info("No existing bathymetry file; starting fresh.")
        except Exception as exc:
            logger.warning("Failed to load bathymetry: %s", exc)

        # Start background tasks.
        self._tasks = [
            asyncio.create_task(self._bridge_consumer(), name="bridge-consumer"),
            asyncio.create_task(self._viewer_server(), name="viewer-server"),
            asyncio.create_task(self._broadcast_loop(), name="broadcast-loop"),
            asyncio.create_task(self._persist_loop(), name="persist-loop"),
        ]

        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False
            for t in self._tasks:
                t.cancel()
            await asyncio.gather(*self._tasks, return_exceptions=True)

    def stop(self) -> None:
        """Signal the core to shut down."""
        self._running = False
        for t in self._tasks:
            t.cancel()

    # ------------------------------------------------------------------
    # Packet handling
    # ------------------------------------------------------------------

    def handle_packet(self, packet: dict) -> None:
        """Process a single TelemetryPacket.

        Updates :attr:`state` and, for depth channels, fuses a sounding
        into :attr:`bathymetry` using the current vessel position.
        """
        self.state.apply_packet(packet)

        # Fuse depth soundings into the bathymetry grid.
        if packet["channel"] == "depth_m" and packet["value"] is not None:
            if self.state.lat is not None and self.state.lon is not None:
                self.bathymetry.fuse(
                    lat=self.state.lat,
                    lon=self.state.lon,
                    depth_m=float(packet["value"]),
                    timestamp_ns=packet["timestamp_ns"],
                    source="sounder",
                )

    # ------------------------------------------------------------------
    # Bridge consumer (WebSocket client)
    # ------------------------------------------------------------------

    async def _bridge_consumer(self) -> None:
        """Connect to the bridge and consume TelemetryPackets.

        Reconnects automatically on disconnection.
        """
        import websockets

        while self._running:
            try:
                logger.info("Connecting to bridge at %s", self.bridge_url)
                async with websockets.connect(self.bridge_url) as ws:
                    logger.info("Connected to bridge.")
                    async for raw in ws:
                        try:
                            packet = json.loads(raw)
                            self.handle_packet(packet)
                        except (json.JSONDecodeError, KeyError) as exc:
                            logger.warning("Bad packet from bridge: %s", exc)
            except Exception as exc:
                if self._running:
                    logger.warning("Bridge connection error: %s", exc)
                    await asyncio.sleep(_RECONNECT_DELAY)

    # ------------------------------------------------------------------
    # Viewer server (WebSocket server)
    # ------------------------------------------------------------------

    async def _viewer_server(self) -> None:
        """Run the WebSocket server for viewer clients."""
        import websockets

        async def handler(ws) -> None:
            """Register a new viewer and keep the connection open."""
            self._viewers.add(ws)
            logger.info("Viewer connected (%d total)", len(self._viewers))
            try:
                # Keep the connection alive; viewers don't send commands.
                async for _ in ws:
                    pass
            except websockets.exceptions.ConnectionClosed:
                pass
            finally:
                self._viewers.discard(ws)
                logger.info("Viewer disconnected (%d total)", len(self._viewers))

        logger.info("Starting viewer server on port %d", self.viewer_port)
        async with websockets.serve(handler, "0.0.0.0", self.viewer_port):
            while self._running:
                await asyncio.sleep(1.0)

    # ------------------------------------------------------------------
    # Broadcast loop
    # ------------------------------------------------------------------

    async def _broadcast_loop(self) -> None:
        """Periodically broadcast VesselStateSnapshot to all viewers."""
        while self._running:
            await asyncio.sleep(self.broadcast_interval)
            if not self._viewers:
                continue
            snapshot = self._make_snapshot()
            raw = json.dumps(snapshot)
            dead: list = []
            for ws in list(self._viewers):
                try:
                    await ws.send(raw)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._viewers.discard(ws)

    def _make_snapshot(self) -> dict:
        """Build the current VesselStateSnapshot dict."""
        viewport = None
        if self.state.lat is not None and self.state.lon is not None:
            viewport = [self.state.lat, self.state.lon, 500.0]
        return self.state.snapshot(
            vessel_id=self.vessel_id,
            viewport=viewport,
            bathymetry=self.bathymetry,
        )

    # ------------------------------------------------------------------
    # Persistence loop
    # ------------------------------------------------------------------

    async def _persist_loop(self) -> None:
        """Periodically persist the bathymetry grid to disk."""
        while self._running:
            await asyncio.sleep(_DEFAULT_PERSIST_INTERVAL)
            try:
                self.bathymetry.save(self.bathymetry_path)
                logger.info("Persisted bathymetry (%d voxels)", self.bathymetry.total_voxels())
            except Exception as exc:
                logger.warning("Failed to persist bathymetry: %s", exc)

        # Final save on shutdown.
        try:
            self.bathymetry.save(self.bathymetry_path)
        except Exception as exc:
            logger.warning("Final bathymetry save failed: %s", exc)
