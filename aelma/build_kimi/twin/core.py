"""TwinCore: the AELMA twin runtime.

Composes :class:`VesselState` and :class:`BathymetryGrid` into an asyncio
process that:

1. connects as a WebSocket client to the bridge and ingests TelemetryPackets,
2. fuses depth soundings into the progressive bathymetry grid,
3. serves viewer WebSocket clients and broadcasts a VesselStateSnapshot
   every ``broadcast_interval`` seconds,
4. persists the bathymetry grid every ``persist_interval`` seconds,
5. logs all telemetry packets to a JSONL file for analytics.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

import websockets

from .bathymetry import BathymetryGrid
from .state import VesselState

log = logging.getLogger("aelma.twin")

# Telemetry channel carrying sounder depth; packet sources map onto the
# bathymetry voxel source enum.
DEPTH_CHANNEL = "depth_m"
_SOURCE_MAP = {
    "manual": "manual",
    "simulator": "sounder",
    "nmea0183": "sounder",
    "nmea2000": "sounder",
    "signal_k": "sounder",
}


class TwinCore:
    """Digital twin for one vessel: state + bathymetry + WS plumbing."""

    def __init__(
        self,
        bridge_url: str = "ws://localhost:8000",
        viewer_port: int = 8090,
        vessel_id: str = "US-AK-FVEILEEN-51",
        bathymetry_path: str | Path = "bathymetry.json",
        telemetry_log_path: str | Path = "telemetry.jsonl",
        broadcast_interval: float = 1.0,
        persist_interval: float = 60.0,
        viewport_radius_m: float = 500.0,
        enable_telemetry_log: bool = True,
    ) -> None:
        """Configure the twin; nothing connects until :meth:`run` is awaited.

        Args:
            bridge_url: WebSocket URL of the bridge server.
            viewer_port: Port for the viewer WebSocket server.
            vessel_id: Identifier for this vessel.
            bathymetry_path: Path to bathymetry persistence file.
            telemetry_log_path: Path to telemetry JSONL log file.
            broadcast_interval: Seconds between viewer snapshot broadcasts.
            persist_interval: Seconds between bathymetry persistence writes.
            viewport_radius_m: Radius of bathymetry viewport in meters.
            enable_telemetry_log: Whether to log telemetry packets to JSONL.
        """
        self.bridge_url = bridge_url
        self.viewer_port = viewer_port
        self.vessel_id = vessel_id
        self.bathymetry_path = Path(bathymetry_path)
        self.telemetry_log_path = Path(telemetry_log_path)
        self.broadcast_interval = broadcast_interval
        self.persist_interval = persist_interval
        self.viewport_radius_m = viewport_radius_m
        self.enable_telemetry_log = enable_telemetry_log

        self.state = VesselState()
        self.bathymetry = BathymetryGrid()
        self._viewers: set[Any] = set()
        self._telemetry_log_file: Any | None = None

    # ------------------------------------------------------------------ #
    # Telemetry logging
    # ------------------------------------------------------------------ #
    def _open_telemetry_log(self) -> None:
        """Open the telemetry log file for appending."""
        if not self.enable_telemetry_log:
            return

        try:
            # Create parent directory if it doesn't exist
            self.telemetry_log_path.parent.mkdir(parents=True, exist_ok=True)

            # Open file in append mode
            self._telemetry_log_file = open(
                self.telemetry_log_path,
                mode="a",
                encoding="utf-8",
                buffering=1,  # Line buffering
            )
            log.info("telemetry log opened: %s", self.telemetry_log_path)
        except OSError as exc:
            log.error("failed to open telemetry log: %s", exc)
            self._telemetry_log_file = None

    def _close_telemetry_log(self) -> None:
        """Close the telemetry log file."""
        if self._telemetry_log_file is not None:
            try:
                self._telemetry_log_file.close()
                log.info("telemetry log closed")
            except OSError as exc:
                log.error("error closing telemetry log: %s", exc)
            finally:
                self._telemetry_log_file = None

    def _log_telemetry(self, packet: dict[str, Any]) -> None:
        """Write a telemetry packet to the JSONL log.

        Args:
            packet: TelemetryPacket dict to log.
        """
        if not self.enable_telemetry_log or self._telemetry_log_file is None:
            return

        try:
            self._telemetry_log_file.write(json.dumps(packet) + "\n")
        except (OSError, TypeError) as exc:
            log.warning("failed to write telemetry packet: %s", exc)

    # ------------------------------------------------------------------ #
    # Packet handling
    # ------------------------------------------------------------------ #
    def handle_packet(self, packet: dict[str, Any]) -> None:
        """Apply one TelemetryPacket to state and, if a sounding, the grid.

        Logs the packet to the telemetry JSONL file if logging is enabled.

        Args:
            packet: TelemetryPacket dict with timestamp_ns, source, channel,
                    value, and optional quality fields.
        """
        # Log packet to telemetry file
        self._log_telemetry(packet)

        # Apply to vessel state
        self.state.apply_packet(packet)

        # Fuse depth soundings into bathymetry grid
        if packet.get("channel") != DEPTH_CHANNEL:
            return
        value = packet.get("value")
        if not isinstance(value, (int, float)) or value is None:
            return
        lat, lon = self.state.lat, self.state.lon
        if lat is None or lon is None:
            return  # no fix yet: nowhere to put the sounding
        self.bathymetry.fuse(
            lat,
            lon,
            float(value),
            int(packet["timestamp_ns"]),
            source=_SOURCE_MAP.get(str(packet.get("source")), "sounder"),
        )

    # ------------------------------------------------------------------ #
    # Snapshot assembly
    # ------------------------------------------------------------------ #
    def build_snapshot(self, now_ns: int | None = None) -> dict[str, Any]:
        """Assemble the full VesselStateSnapshot, including the bathymetry
        viewport block centered on the (dead-reckoned) vessel position."""
        if now_ns is None:
            now_ns = time.time_ns()
        snap = self.state.snapshot(self.vessel_id, [self.viewport_radius_m], now_ns)
        lat, lon = snap["pose"]["lat"], snap["pose"]["lon"]
        snap["bathymetry"] = {
            "voxel_count": self.bathymetry.total_voxels(),
            "viewport_center": {"lat": lat, "lon": lon},
            "viewport_radius_m": self.viewport_radius_m,
            "cells": self.bathymetry.cells_in_radius(
                lat, lon, self.viewport_radius_m, now_ns
            ),
        }
        return snap

    # ------------------------------------------------------------------ #
    # Bridge side (WebSocket client)
    # ------------------------------------------------------------------ #
    async def _bridge_loop(self) -> None:
        """Connect to the bridge and ingest packets, reconnecting forever."""
        backoff = 1.0
        while True:
            try:
                async with websockets.connect(self.bridge_url) as ws:
                    log.info("connected to bridge at %s", self.bridge_url)
                    backoff = 1.0
                    async for raw in ws:
                        try:
                            packet = json.loads(raw)
                            if isinstance(packet, list):
                                for p in packet:
                                    self.handle_packet(p)
                            else:
                                self.handle_packet(packet)
                        except (json.JSONDecodeError, KeyError, TypeError) as exc:
                            log.warning("dropping malformed packet: %s", exc)
            except (OSError, websockets.WebSocketException) as exc:
                log.warning("bridge connection failed (%s); retry in %.0fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)

    # ------------------------------------------------------------------ #
    # Viewer side (WebSocket server)
    # ------------------------------------------------------------------ #
    async def _viewer_handler(self, ws: Any) -> None:
        """Register a viewer, push an immediate snapshot, hold until close."""
        self._viewers.add(ws)
        log.info("viewer connected (%d total)", len(self._viewers))
        try:
            await ws.send(json.dumps(self.build_snapshot()))
            await ws.wait_closed()
        finally:
            self._viewers.discard(ws)
            log.info("viewer disconnected (%d total)", len(self._viewers))

    async def _broadcast_loop(self) -> None:
        """Send a fresh snapshot to every connected viewer on the interval."""
        while True:
            await asyncio.sleep(self.broadcast_interval)
            if not self._viewers:
                continue
            msg = json.dumps(self.build_snapshot())
            results = await asyncio.gather(
                *(ws.send(msg) for ws in list(self._viewers)),
                return_exceptions=True,
            )
            for ws, res in zip(list(self._viewers), results):
                if isinstance(res, Exception):
                    self._viewers.discard(ws)

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    async def _persist_loop(self) -> None:
        """Write the bathymetry grid to disk on the persist interval."""
        while True:
            await asyncio.sleep(self.persist_interval)
            try:
                self.bathymetry.save(self.bathymetry_path)
                log.info(
                    "persisted %d voxels to %s",
                    self.bathymetry.total_voxels(),
                    self.bathymetry_path,
                )
            except OSError as exc:
                log.error("bathymetry persist failed: %s", exc)

    # ------------------------------------------------------------------ #
    # Entry point
    # ------------------------------------------------------------------ #
    async def run(self) -> None:
        """Load persisted state, then run all loops until cancelled.

        Opens telemetry log file on startup and closes on shutdown.
        """
        self.bathymetry.load(self.bathymetry_path)
        self._open_telemetry_log()

        try:
            async with websockets.serve(
                self._viewer_handler, "localhost", self.viewer_port
            ):
                log.info("viewer WS server listening on port %d", self.viewer_port)
                await asyncio.gather(
                    self._bridge_loop(),
                    self._broadcast_loop(),
                    self._persist_loop(),
                )
        finally:
            self._close_telemetry_log()
