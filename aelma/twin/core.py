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
from .jepa_model import JEPAModel
from .metrics import (
    ACTIONS_FIRED,
    MEMORY_BYTES,
    PACKET_HANDLING_SECONDS,
    PACKETS_RECEIVED,
    WEBSOCKET_CONNECTIONS,
    MetricsCollector,
    serve_metrics,
)
from .mob_detector import MOBDetector
from .oplog import OpLog
from .quota_manager import QuotaManager
from .report_generator import ReportGenerator, ReportSpec, ReportResult
from .state import VesselState
from .crew_fatigue import CrewFatigueMonitor
from .equipment_monitor import EquipmentMonitor
from .sensors.nmea_udp_capture import SensorCaptureCoordinator

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
        oplog_path: str | Path = "oplog.jsonl",
        oplog_max_bytes: int | None = None,
        oplog_keep: int = 5,
        breaker_failure_threshold: int = 5,
        breaker_recovery_timeout: float = 30.0,
        health_port: int | None = 8091,
        metrics_port: int | None = 9090,
        enable_jepa: bool = True,
        jepa_history_size: int = 1000,
        jepa_learning_rate: float = 0.1,
        jepa_anomaly_threshold: float = 2.5,
        jepa_min_samples: int = 10,
        quota_path: str | Path = "quota",
        quota_enabled: bool = True,
        mob_events_path: str | Path = "mob_events.jsonl",
        enable_mob: bool = True,
        crew_fatigue_path: str | Path = "crew_fatigue",
        enable_crew_fatigue: bool = True,
        equipment_path: str | Path = "equipment",
        enable_equipment: bool = True,
        report_storage_path: str | Path = "reports",
        report_template_path: str | Path = "twin/templates",
        smtp_host: str | None = None,
        smtp_port: int = 587,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        smtp_from: str | None = None,
        enable_sensors: bool = True,
        nmea_port: int = 8001,
        udp_depth_port: int = 50000,
        sensor_output_dir: str | Path = "sensor_data",
    ) -> None:
        """Configure the twin; nothing connects until :meth:`run` is awaited."""
        self.bridge_url = bridge_url
        self.viewer_port = viewer_port
        self.vessel_id = vessel_id
        self.bathymetry_path = Path(bathymetry_path)
        self.crew_fatigue_path = Path(crew_fatigue_path)
        self.equipment_path = Path(equipment_path)
        self.broadcast_interval = broadcast_interval
        self.persist_interval = persist_interval
        self.viewport_radius_m = viewport_radius_m
        self.a2a_log_path = Path(a2a_log_path)
        self.oplog_path = Path(oplog_path)
        self.metrics_port = metrics_port
        self.quota_path = Path(quota_path)
        self.quota_enabled = quota_enabled
        self.mob_events_path = Path(mob_events_path)
        self.report_storage_path = Path(report_storage_path)
        self.report_template_path = Path(report_template_path)
        self.sensor_output_dir = Path(sensor_output_dir)

        self.state = VesselState()
        self.bathymetry = BathymetryGrid()
        self._viewers: set[Any] = set()
        # Flipped by _bridge_loop; read by the health endpoint.
        self.bridge_connected = False
        self.a2a_log = A2ALog(self.a2a_log_path, max_bytes=a2a_max_bytes, keep=a2a_keep)
        self.oplog = OpLog(self.oplog_path, max_bytes=oplog_max_bytes, keep=oplog_keep)
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
            PACKET_HANDLING_SECONDS, help="Time spent applying one telemetry packet."
        )

        # JEPA world model for predictive telemetry and anomaly detection
        self.enable_jepa = enable_jepa
        self.jepa = JEPAModel(
            history_size=jepa_history_size,
            learning_rate=jepa_learning_rate,
            anomaly_threshold=jepa_anomaly_threshold,
            min_samples=jepa_min_samples,
        ) if enable_jepa else None

        # Quota manager for commercial fishing quota tracking
        self.quota = QuotaManager(
            storage_path=self.quota_path if quota_enabled else None,
            vessel_id=vessel_id,
        ) if quota_enabled else None

        # Report generator for regulatory compliance and operational analysis
        self.reports = ReportGenerator(
            storage_path=self.report_storage_path,
            template_path=self.report_template_path,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_user=smtp_user,
            smtp_password=smtp_password,
            smtp_from=smtp_from,
        )

        # Register data source callbacks with report generator
        self.reports.register_vessel_state(self._get_vessel_state)
        self.reports.register_bathymetry(self._get_bathymetry_data)
        self.reports.register_a2a_query(self._query_a2a_log)
        self.reports.register_oplog_query(self.query_oplog)
        self.reports.register_telemetry_query(self._query_telemetry)

        # MOB detector for man over board safety system
        self.mob = MOBDetector(
            storage_path=self.mob_events_path
        ) if enable_mob else None

        # Crew fatigue monitoring system
        self.crew_fatigue = CrewFatigueMonitor(
            vessel_id=self.vessel_id,
            data_dir=self.crew_fatigue_path
        ) if enable_crew_fatigue else None

        # Equipment monitoring system
        self.equipment = EquipmentMonitor(
            data_dir=self.equipment_path,
            enable_persistence=True
        ) if enable_equipment else None

        # Sensor capture coordinator for NMEA/UDP sensors
        self.sensor_coordinator = SensorCaptureCoordinator(
            nmea_jsonl=self.sensor_output_dir / "nmea_telemetry.jsonl",
            depth_jsonl=self.sensor_output_dir / "depth_sounder.jsonl",
            radar_jsonl=self.sensor_output_dir / "radar.jsonl",
            log_path=self.sensor_output_dir / "sensor_capture.log",
        ) if enable_sensors else None
        self.nmea_port = nmea_port
        self.udp_depth_port = udp_depth_port

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

    async def log_crew_action(
        self,
        entry_type: str,
        crew: str,
        message: str,
        metadata: dict[str, Any] | None = None,
        *,
        ts: Any = None,
    ) -> dict[str, Any]:
        """Log a crew operations entry to the operations log.

        This is the main entry point for logging manual crew operations such as
        gear deployment/retrieval, haul operations, anchor handling, catch logging,
        manual alerts, and general crew notes.

        Parameters
        ----------
        entry_type:
            Type of operation (gear_deployed, gear_retrieved, haul_started,
            haul_complete, anchor_drop, anchor_raise, manual_alert, crew_note,
            catch_logged)
        crew:
            Crew member identifier (name, ID, or role)
        message:
            Human-readable description of the operation
        metadata:
            Optional structured data (gear type, location, quantities, etc.)
        ts:
            Timestamp (None for now, datetime, epoch seconds, or ISO string)

        Returns
        -------
        dict
            The logged record as written (including generated fields like _seq
            and _loggedAt).

        Example
        -------
        >>> await twin.log_crew_action(
        ...     "gear_deployed",
        ...     "captain",
        ...     "Deployed cod pot gear at 59.5N, -152.3W",
        ...     {"gear_type": "cod_pot", "count": 50, "lat": 59.5, "lon": -152.3}
        ... )
        """
        return await self.oplog.log_entry(
            entry_type,
            crew,
            message,
            metadata,
            ts=ts,
        )

    async def query_oplog(
        self,
        *,
        entry_type: str | set[str] | None = None,
        crew: str | set[str] | None = None,
        start_time: Any = None,
        end_time: Any = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Query the operations log with filters.

        Parameters
        ----------
        entry_type:
            Filter by entry type (string or set). None = all types.
        crew:
            Filter by crew member (string or set). None = all crew.
        start_time:
            Filter entries after this time. Accepts datetime, epoch seconds, or ISO string.
        end_time:
            Filter entries before this time. Accepts datetime, epoch seconds, or ISO string.
        limit:
            Maximum number of entries to return. Default 1000.
        offset:
            Number of entries to skip (for pagination). Default 0.

        Returns
        -------
        list[dict]
            List of matching records, ordered by timestamp (newest first).
        """
        return await self.oplog.query(
            entry_type=entry_type,
            crew=crew,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=offset,
        )

    async def export_oplog(
        self,
        format: str = "json",
        *,
        entry_type: str | set[str] | None = None,
        crew: str | set[str] | None = None,
        start_time: Any = None,
        end_time: Any = None,
        limit: int = 1000,
    ) -> str:
        """Export the operations log to specified format.

        Parameters
        ----------
        format:
            Export format: 'json', 'csv', or 'text'. Default 'json'.
        entry_type, crew, start_time, end_time, limit:
            Same filters as query_oplog().

        Returns
        -------
        str
            Exported data in requested format.
        """
        return await self.oplog.export(
            format=format,
            entry_type=entry_type,
            crew=crew,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )


    def handle_packet(self, packet: dict[str, Any]) -> None:
        """Apply one TelemetryPacket to state and, if a sounding, the grid."""
        started = time.perf_counter()
        try:
            self.state.apply_packet(packet)

            # Train JEPA model on every packet
            if self.jepa is not None:
                self.jepa.train_on_packet(packet)

            # Update MOB detector with position/heading/speed
            if self.mob is not None:
                channel = packet.get("channel")
                if channel in ["position.lat", "position.lon", "heading_deg", "speed_kn"]:
                    lat = self.state.lat
                    lon = self.state.lon
                    heading = self.state.heading_deg
                    speed = self.state.speed_kn
                    if lat is not None and lon is not None:
                        self.mob.update_vessel_position(lat, lon, heading, speed)

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

            # Run JEPA prediction and anomaly detection on depth packets
            if self.jepa is not None:
                self._run_jepa_prediction(packet)
        finally:
            self.metrics.increment(PACKETS_RECEIVED)
            self.metrics.observe(
                PACKET_HANDLING_SECONDS, time.perf_counter() - started
            )

    def _run_jepa_prediction(self, packet: dict[str, Any]) -> None:
        """Run JEPA prediction and emit anomaly events if needed."""
        if self.jepa is None:
            return

        # Build current state dict from packet and state
        current_state = {
            "depth_m": packet.get("value"),
            "speed_kn": self.state.speed_kn,
            "lat": self.state.lat,
            "lon": self.state.lon,
            "heading_deg": self.state.heading_deg,
            "timestamp_ns": packet.get("timestamp_ns"),
        }

        # Try to predict next state
        prediction = self.jepa.predict_future(current_state, steps_ahead=1)
        if prediction is None:
            return  # Not enough data yet

        # Check for anomalies
        # For now, we'll log anomalous predictions
        # In production, this would emit watcher events
        if prediction.anomaly_score > 0.5:
            log.warning(
                "JEPA detected anomaly: score=%.2f, confidence=%.2f, errors=%s",
                prediction.anomaly_score,
                prediction.confidence,
                prediction.errors,
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

        # Add JEPA world model stats if enabled
        if self.jepa is not None:
            snap["jepa"] = self.jepa.stats

        # Add quota status if enabled
        if self.quota is not None:
            snap["quota"] = self.quota.get_quota_status()

        # Add MOB status if enabled
        if self.mob is not None:
            snap["mob"] = self.mob.to_dict()

        # Add crew fatigue status if enabled
        if self.crew_fatigue is not None:
            snap["crew_fatigue"] = self.crew_fatigue.to_dict()

        # Add equipment status if enabled
        if self.equipment is not None:
            snap["equipment"] = self.equipment.to_dict()

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

        # Start sensor capture coordinator if enabled
        sensor_tasks = []
        if self.sensor_coordinator is not None:
            log.info("Starting NMEA/UDP sensor capture coordinator")
            self.sensor_coordinator.start_nmea_listener(port=self.nmea_port)
            self.sensor_coordinator.start_udp_depth(port=self.udp_depth_port)
            log.info("NMEA listener on port %d, UDP depth on port %d",
                     self.nmea_port, self.udp_depth_port)

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
            # Stop sensor coordinator if running
            if self.sensor_coordinator is not None:
                self.sensor_coordinator.stop_all()
                log.info("Sensor capture coordinator stopped")
            # Final save on shutdown to prevent data loss
            self.bathymetry.save(self.bathymetry_path)
            log.info("bathymetry saved on shutdown")

    # ------------------------------------------------------------------ #
    # Report generator data source callbacks
    # ------------------------------------------------------------------ #
    async def _get_vessel_state(self) -> dict[str, Any]:
        """Callback for report generator to get vessel state."""
        return self.state.snapshot(self.vessel_id, [self.viewport_radius_m])

    async def _get_bathymetry_data(self) -> dict[str, Any]:
        """Callback for report generator to get bathymetry data."""
        return {
            "voxel_count": self.bathymetry.total_voxels(),
            "cells": self.bathymetry.cells_in_radius(
                self.state.lat or 0.0,
                self.state.lon or 0.0,
                self.viewport_radius_m,
                time.time_ns(),
            ),
        }

    async def _query_a2a_log(
        self,
        *,
        action: str | set[str] | None = None,
        source: str | set[str] | None = None,
        start_time: Any = None,
        end_time: Any = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Callback for report generator to query A2A log."""
        # This would need to be implemented in A2ALog
        # For now, return empty list
        return []

    async def _query_telemetry(
        self,
        *,
        channels: set[str] | None = None,
        start_time: Any = None,
        end_time: Any = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Callback for report generator to query telemetry history."""
        # This would need a telemetry history system
        # For now, return current channel values
        if channels is None:
            channels = set(self.state.channels.keys())

        results = []
        for channel in channels:
            if channel in self.state.channels:
                entry = self.state.channels[channel]
                results.append({
                    "channel": channel,
                    "value": entry.get("value"),
                    "timestamp_ns": entry.get("timestamp_ns"),
                    "quality": entry.get("quality", "good"),
                })

        return results

    # ------------------------------------------------------------------ #
    # Report generation API
    # ------------------------------------------------------------------ #
    async def generate_report(self, spec: ReportSpec) -> ReportResult:
        """Generate a report from specification.

        Parameters
        ----------
        spec:
            Report specification

        Returns
        -------
        ReportResult
            Result of report generation
        """
        # Set vessel_id if not specified
        if spec.vessel_id is None:
            spec.vessel_id = self.vessel_id

        return await self.reports.generate_report(spec)

    async def generate_trip_report(
        self,
        trip_id: str,
        start_time: Any,
        end_time: Any,
        format: str = "pdf",
    ) -> ReportResult:
        """Generate a trip report.

        Parameters
        ----------
        trip_id:
            Trip identifier
        start_time:
            Trip start time
        end_time:
            Trip end time
        format:
            Export format (pdf, html, json, csv, xml, md)

        Returns
        -------
        ReportResult
        """
        return await self.reports.generate_trip_report(trip_id, start_time, end_time, format)

    async def generate_daily_report(
        self,
        date: Any,
        format: str = "pdf",
    ) -> ReportResult:
        """Generate a daily report.

        Parameters
        ----------
        date:
            Date for report
        format:
            Export format (pdf, html, json, csv, xml, md)

        Returns
        -------
        ReportResult
        """
        return await self.reports.generate_daily_report(date, format)

    async def generate_catch_report(
        self,
        start_time: Any,
        end_time: Any,
        format: str = "pdf",
    ) -> ReportResult:
        """Generate a catch report.

        Parameters
        ----------
        start_time:
            Report start time
        end_time:
            Report end time
        format:
            Export format (pdf, html, json, csv, xml, md)

        Returns
        -------
        ReportResult
        """
        return await self.reports.generate_catch_report(start_time, end_time, format)

    def schedule_report(
        self,
        report_type: str,
        title: str,
        start_time: Any,
        end_time: Any,
        cron_expression: str,
        format: str = "pdf",
        recipient_emails: list[str] | None = None,
    ) -> str:
        """Schedule a report for automatic generation.

        Parameters
        ----------
        report_type:
            Type of report (trip, daily, catch, etc.)
        title:
            Report title
        start_time:
            Report time window start
        end_time:
            Report time window end
        cron_expression:
            Cron expression for scheduling (e.g., "0 6 * * *" for daily at 6am)
        format:
            Export format
        recipient_emails:
            Optional email recipients

        Returns
        -------
        str
            Schedule ID
        """
        spec = ReportSpec(
            report_type=report_type,
            title=title,
            start_time=start_time,
            end_time=end_time,
            format=format,
            vessel_id=self.vessel_id,
            recipient_emails=recipient_emails,
        )

        return self.reports.schedule_report(spec, cron_expression)

    def cancel_schedule(self, schedule_id: str) -> bool:
        """Cancel a scheduled report.

        Parameters
        ----------
        schedule_id:
            Schedule ID to cancel

        Returns
        -------
        bool
            True if cancelled, False if not found
        """
        return self.reports.cancel_schedule(schedule_id)

    def get_scheduled_reports(self) -> list[dict[str, Any]]:
        """Get all scheduled reports.

        Returns
        -------
        list[dict]
            List of schedule specifications
        """
        return self.reports.get_scheduled_reports()

    def get_report(self, report_id: str) -> ReportResult | None:
        """Get a report by ID.

        Parameters
        ----------
        report_id:
            Report identifier

        Returns
        -------
        ReportResult or None
            Report result or None if not found
        """
        return self.reports.get_report(report_id)

    def list_reports(
        self,
        report_type: str | None = None,
        limit: int = 100,
    ) -> list[ReportResult]:
        """List reports with optional filter.

        Parameters
        ----------
        report_type:
            Filter by report type (None = all)
        limit:
            Maximum number of reports to return

        Returns
        -------
        list[ReportResult]
            List of reports, newest first
        """
        return self.reports.list_reports(report_type, limit)

    def delete_report(self, report_id: str) -> bool:
        """Delete a report.

        Parameters
        ----------
        report_id:
            Report identifier

        Returns
        -------
        bool
            True if deleted, False if not found
        """
        return self.reports.delete_report(report_id)

    def register_webhook(self, url: str, report_types: list[str]) -> None:
        """Register webhook for report notifications.

        Parameters
        ----------
        url:
            Webhook URL
        report_types:
            List of report types to trigger on
        """
        self.reports.register_webhook(url, report_types)
