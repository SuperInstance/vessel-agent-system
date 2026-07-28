"""TwinCore: the AELMA twin runtime.

Composes :class:`VesselState` and :class:`BathymetryGrid` into an asyncio
process that:

1. connects as a WebSocket client to the bridge and ingests TelemetryPackets,
2. fuses depth soundings into the progressive bathymetry grid,
3. serves viewer WebSocket clients and broadcasts a VesselStateSnapshot
   every ``broadcast_interval`` seconds,
4. persists the bathymetry grid every ``persist_interval`` seconds.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

import websockets

from .a2a_log import A2ALog
from .bathymetry import BathymetryGrid
from .circuit_breaker import CircuitBreaker
from .health import HealthChecker
from .metrics import (
    ACTIONS_FIRED,
    MEMORY_BYTES,
    PACKET_HANDLING_SECONDS,
    PACKETS_RECEIVED,
    WEBSOCKET_CONNECTIONS,
    MetricsCollector,
    serve_metrics,
)
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
        broadcast_interval: float = 1.0,
        persist_interval: float = 60.0,
        viewport_radius_m: float = 500.0,
        a2a_log_path: str | Path = "a2a.jsonl",
        a2a_max_bytes: int | None = None,
        a2a_keep: int = 5,
        breaker_failure_threshold: int = 5,
        breaker_recovery_timeout: float = 30.0,
        health_port: int | None = 8091,
        metrics_port: int | None = 9090,
    ) -> None:
        """Configure the twin; nothing connects until :meth:`run` is awaited."""
        self.bridge_url = bridge_url
        self.viewer_port = viewer_port
        self.vessel_id = vessel_id
        self.bathymetry_path = Path(bathymetry_path)
        self.broadcast_interval = broadcast_interval
        self.persist_interval = persist_interval
        self.viewport_radius_m = viewport_radius_m
        self.a2a_log_path = Path(a2a_log_path)
        self.metrics_port = metrics_port

        self.state = VesselState()
        self.bathymetry = BathymetryGrid()
        self._viewers: set[Any] = set()
        # Flipped by _bridge_loop; read by the health endpoint.
        self.bridge_connected = False
        self.a2a_log = A2ALog(self.a2a_log_path, max_bytes=a2a_max_bytes, keep=a2a_keep)
        # Protects the bridge WebSocket client from hammering a dead bridge:
        # consecutive connect failures trip it OPEN for the recovery timeout.
        self.bridge_breaker = CircuitBreaker(
            name="bridge",
            failure_threshold=breaker_failure_threshold,
            recovery_timeout=breaker_recovery_timeout,
        )
        self.health = (
            HealthChecker(self, port=health_port) if health_port is not None else None
        )
        # Observability: counters/gauges/histograms scraped via /metrics.
        self.metrics = MetricsCollector()
        self.metrics.register_counter(
            PACKETS_RECEIVED, "Telemetry packets ingested from the bridge."
        )
        self.metrics.register_counter(
            ACTIONS_FIRED, "A2A actions logged."
        )
        self.metrics.register_gauge(
            WEBSOCKET_CONNECTIONS, "Currently connected viewer WebSocket clients."
        )
        self.metrics.register_gauge(MEMORY_BYTES, "Process resident memory in bytes.")
        self.metrics.register_histogram(
            PACKET_HANDLING_SECONDS, "Time spent applying one telemetry packet."
        )

    # ------------------------------------------------------------------ #
    # Packet handling
    # ------------------------------------------------------------------ #
    async def log_action(
        self,
        action: str,
        payload: dict[str, Any] | None = None,
        *,
        source: str = "system",
        reason: str = "",
        priority: float = 0.5,
    ) -> dict[str, Any]:
        """Log an A2A action to the action log.

        This is the main entry point for logging watcher-fired actions,
        LLM-issued actions, or crew-entered actions. Returns the logged
        record as written (including generated fields like _seq and _loggedAt).
        """
        self.metrics.increment(ACTIONS_FIRED, labels={"action": action})
        return await self.a2a_log.append(
            action,
            payload,
            source=source,
            reason=reason,
            priority=priority,
        )

    def handle_packet(self, packet: dict[str, Any]) -> None:
        """Apply one TelemetryPacket to state and, if a sounding, the grid."""
        started = time.perf_counter()
        try:
            self.state.apply_packet(packet)
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
        finally:
            self.metrics.increment(PACKETS_RECEIVED)
            self.metrics.observe(
                PACKET_HANDLING_SECONDS, time.perf_counter() - started
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
        """Connect to the bridge and ingest packets, reconnecting forever.

        Each connect attempt is admitted through ``self.bridge_breaker``;
        consecutive failures trip it OPEN so a dead bridge is retried on
        the breaker's recovery timeout rather than the raw backoff alone.
        """
        backoff = 1.0
        while True:
            await self.bridge_breaker.acquire()
            try:
                async with websockets.connect(self.bridge_url) as ws:
                    log.info("connected to bridge at %s", self.bridge_url)
                    self.bridge_connected = True
                    await self.bridge_breaker.record_success()
                    backoff = 1.0
                    try:
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
                    finally:
                        self.bridge_connected = False
            except (OSError, websockets.WebSocketException) as exc:
                await self.bridge_breaker.record_failure()
                log.warning(
                    "bridge connection failed (%s); breaker=%s; retry in %.0fs",
                    exc,
                    self.bridge_breaker.state.value,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)

    # ------------------------------------------------------------------ #
    # Viewer side (WebSocket server)
    # ------------------------------------------------------------------ #
    async def _viewer_handler(self, ws: Any) -> None:
        """Register a viewer, push an immediate snapshot, hold until close."""
        self._viewers.add(ws)
        self.metrics.set_gauge(WEBSOCKET_CONNECTIONS, len(self._viewers))
        log.info("viewer connected (%d total)", len(self._viewers))
        try:
            await ws.send(json.dumps(self.build_snapshot()))
            await ws.wait_closed()
        finally:
            self._viewers.discard(ws)
            self.metrics.set_gauge(WEBSOCKET_CONNECTIONS, len(self._viewers))
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
        """Load persisted state, then run all loops until cancelled."""
        self.bathymetry.load(self.bathymetry_path)
        if self.health is not None:
            await self.health.start()
        metrics_server = (
            await serve_metrics(self.metrics, port=self.metrics_port)
            if self.metrics_port is not None
            else None
        )
        try:
            async with websockets.serve(self._viewer_handler, "0.0.0.0", self.viewer_port):
                log.info("viewer WS server listening on port %d", self.viewer_port)
                await asyncio.gather(
                    self._bridge_loop(),
                    self._broadcast_loop(),
                    self._persist_loop(),
                )
        finally:
            if metrics_server is not None:
                metrics_server.close()
                await metrics_server.wait_closed()
            if self.health is not None:
                await self.health.stop()
            # Final save on shutdown to prevent data loss
            self.bathymetry.save(self.bathymetry_path)
            log.info("bathymetry saved on shutdown")
