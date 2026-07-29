"""Report Generator System for AELMA marine digital twin.

Comprehensive report generation for regulatory compliance, operational analysis,
and fleet management. Supports multiple report types, export formats, scheduling,
and delivery methods.

Report Types:
- Trip Reports: Complete fishing trip summary
- Daily Reports: 24-hour operational summary
- Catch Reports: Species breakdown and analysis
- Equipment Reports: Gear usage and maintenance
- Crew Reports: Hours, fatigue, actions
- Weather Reports: Conditions encountered
- Performance Reports: Efficiency metrics
- Compliance Reports: Regulatory requirements
- Maintenance Reports: Equipment status and alerts
- Fleet Reports: Multi-vessel analytics

Export Formats:
- PDF: Formatted reports with tables, charts, maps
- HTML: Interactive web reports
- JSON: Machine-readable structured data
- CSV: Spreadsheet-compatible data
- XML: Regulatory submission formats
- Markdown: Documentation and email reports
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
import smtplib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Callable
from xml.etree import ElementTree as ET
from xml.dom import minidom

import aiohttp

log = logging.getLogger("aelma.twin.report_generator")


def _utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


def _coerce_ts(ts: Any) -> datetime:
    """Coerce timestamp argument to datetime.

    Accepts None (now, UTC), datetime (naive assumed UTC),
    epoch-seconds number, or ISO string.
    """
    if ts is None:
        return _utc_now()
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts
    if isinstance(ts, (int, float)) and not isinstance(ts, bool):
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            raise ValueError(f"ReportGenerator: unparseable ts string: {ts!r}") from None
    raise TypeError(f"ReportGenerator: unsupported ts type {type(ts).__name__}")


@dataclass
class ReportSpec:
    """Specification for report generation.

    Attributes
    ----------
    report_type:
        Type of report to generate (trip, daily, catch, equipment, etc.)
    title:
        Report title for display
    start_time:
        Report time window start (datetime, epoch seconds, or ISO string)
    end_time:
        Report time window end (datetime, epoch seconds, or ISO string)
    format:
        Export format (pdf, html, json, csv, xml, md)
    vessel_id:
        Optional vessel identifier for multi-vessel systems
    crew_filter:
        Optional set of crew members to filter on
    include_charts:
        Include charts and visualizations (for HTML/PDF)
    include_maps:
        Include maps (for HTML/PDF)
    include_raw_data:
        Include raw data appendix
    recipient_emails:
        Optional list of email recipients for automatic delivery
    """
    report_type: str
    title: str
    start_time: Any
    end_time: Any
    format: str = "html"
    vessel_id: str | None = None
    crew_filter: set[str] | None = None
    include_charts: bool = True
    include_maps: bool = True
    include_raw_data: bool = False
    recipient_emails: list[str] | None = None

    def __post_init__(self):
        """Validate and normalize report specification."""
        valid_formats = {"pdf", "html", "json", "csv", "xml", "md"}
        if self.format not in valid_formats:
            raise ValueError(
                f"ReportSpec: format must be one of {valid_formats}, got {self.format!r}"
            )

        valid_types = {
            "trip", "daily", "catch", "equipment", "crew",
            "weather", "performance", "compliance", "maintenance", "fleet"
        }
        if self.report_type not in valid_types:
            raise ValueError(
                f"ReportSpec: report_type must be one of {valid_types}, got {self.report_type!r}"
            )

        # Normalize timestamps
        self._start_dt = _coerce_ts(self.start_time)
        self._end_dt = _coerce_ts(self.end_time)

        if self._end_dt < self._start_dt:
            raise ValueError("ReportSpec: end_time must be after start_time")

    @property
    def start_dt(self) -> datetime:
        """Start time as datetime object."""
        return self._start_dt

    @property
    def end_dt(self) -> datetime:
        """End time as datetime object."""
        return self._end_dt


@dataclass
class ReportResult:
    """Result of report generation.

    Attributes
    ----------
    report_id:
        Unique identifier for this report
    spec:
        Original report specification
    generated_at:
        When the report was generated
    file_path:
        Path to generated file (if saved to disk)
    content:
        Report content (if not saved to disk)
    status:
        Generation status (pending, generating, complete, failed)
    error_message:
        Error message if generation failed
    size_bytes:
        Size of generated report in bytes
    """
    report_id: str
    spec: ReportSpec
    generated_at: datetime
    file_path: str | None = None
    content: str | None = None
    status: str = "pending"
    error_message: str | None = None
    size_bytes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "report_id": self.report_id,
            "spec": {
                "report_type": self.spec.report_type,
                "title": self.spec.title,
                "start_time": self.spec.start_time,
                "end_time": self.spec.end_time,
                "format": self.spec.format,
                "vessel_id": self.spec.vessel_id,
            },
            "generated_at": self.generated_at.isoformat(),
            "file_path": self.file_path,
            "status": self.status,
            "error_message": self.error_message,
            "size_bytes": self.size_bytes,
        }


@dataclass
class ScheduleSpec:
    """Specification for scheduled report generation.

    Attributes
    ----------
    schedule_id:
        Unique identifier for this schedule
    spec:
        Report specification to generate on schedule
    cron_expression:
        Cron expression for scheduling (e.g., "0 6 * * *" for daily at 6am)
    enabled:
        Whether the schedule is currently active
    last_run:
        Last time the report was generated
    next_run:
        Next scheduled run time
    """
    schedule_id: str
    spec: ReportSpec
    cron_expression: str
    enabled: bool = True
    last_run: datetime | None = None
    next_run: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "schedule_id": self.schedule_id,
            "spec": {
                "report_type": self.spec.report_type,
                "title": self.spec.title,
                "format": self.spec.format,
            },
            "cron_expression": self.cron_expression,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
        }


class ReportGenerator:
    """Comprehensive report generation system for marine digital twin.

    Parameters
    ----------
    storage_path:
        Directory to store generated reports
    template_path:
        Directory containing report templates
    smtp_host:
        SMTP server for email delivery
    smtp_port:
        SMTP server port
    smtp_user:
        SMTP username
    smtp_password:
        SMTP password
    smtp_from:
        From address for report emails
    """

    def __init__(
        self,
        storage_path: str | Path = "reports",
        template_path: str | Path = "twin/templates",
        smtp_host: str | None = None,
        smtp_port: int = 587,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        smtp_from: str | None = None,
    ) -> None:
        """Initialize report generator."""
        self.storage_path = Path(storage_path)
        self.template_path = Path(template_path)
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.smtp_from = smtp_from

        # Create storage directories
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.template_path.mkdir(parents=True, exist_ok=True)

        # Report storage
        self._reports: dict[str, ReportResult] = {}
        self._schedules: dict[str, ScheduleSpec] = {}
        self._webhooks: dict[str, list[str]] = {}  # report_type -> [urls]

        # Data source callbacks (to be injected by TwinCore)
        self._telemetry_query_cb: Callable[..., Any] | None = None
        self._a2a_query_cb: Callable[..., Any] | None = None
        self._oplog_query_cb: Callable[..., Any] | None = None
        self._bathymetry_cb: Callable[..., Any] | None = None
        self._vessel_state_cb: Callable[..., Any] | None = None

        # Lock for concurrent report generation
        self._generation_lock = asyncio.Lock()

        log.info("ReportGenerator initialized: storage=%s", self.storage_path)

    # ------------------------------------------------------------------ #
    # Data source registration
    # ------------------------------------------------------------------ #
    def register_telemetry_query(self, callback: Callable[..., Any]) -> None:
        """Register telemetry query callback from TwinCore."""
        self._telemetry_query_cb = callback

    def register_a2a_query(self, callback: Callable[..., Any]) -> None:
        """Register A2A log query callback from TwinCore."""
        self._a2a_query_cb = callback

    def register_oplog_query(self, callback: Callable[..., Any]) -> None:
        """Register OpLog query callback from TwinCore."""
        self._oplog_query_cb = callback

    def register_bathymetry(self, callback: Callable[..., Any]) -> None:
        """Register bathymetry query callback from TwinCore."""
        self._bathymetry_cb = callback

    def register_vessel_state(self, callback: Callable[..., Any]) -> None:
        """Register vessel state callback from TwinCore."""
        self._vessel_state_cb = callback

    # ------------------------------------------------------------------ #
    # Report generation
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
        report_id = str(uuid.uuid4())
        result = ReportResult(
            report_id=report_id,
            spec=spec,
            generated_at=_utc_now(),
            status="generating",
        )

        self._reports[report_id] = result

        try:
            async with self._generation_lock:
                # Gather data
                data = await self._gather_report_data(spec)

                # Generate content based on format
                content = await self._render_report(spec, data)

                # Save to file or keep in memory
                file_ext = self._get_file_extension(spec.format)
                file_name = f"{spec.report_type}_{spec.start_dt.strftime('%Y%m%d')}_{spec.end_dt.strftime('%Y%m%d')}_{report_id[:8]}{file_ext}"
                file_path = self.storage_path / file_name

                # Save content to file for all formats
                saved_path = await self._save_report(file_path, content, spec.format)
                result.file_path = str(saved_path)
                result.size_bytes = saved_path.stat().st_size

                # Also keep content in memory for small formats
                if spec.format in {"json", "csv", "xml", "md"}:
                    result.content = content

                result.status = "complete"
                log.info("Report generated: %s (%s)", report_id, spec.format)

                # Trigger webhooks
                await self._trigger_webhooks(spec.report_type, result)

                # Send emails if recipients specified
                if spec.recipient_emails:
                    await self._send_report_email(result, spec.recipient_emails)

                return result

        except Exception as exc:
            result.status = "failed"
            result.error_message = str(exc)
            log.error("Report generation failed: %s - %s", report_id, exc)
            return result

    async def generate_trip_report(
        self,
        trip_id: str,
        start_time: Any,
        end_time: Any,
        format: str = "pdf"
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
            Export format

        Returns
        -------
        ReportResult
        """
        spec = ReportSpec(
            report_type="trip",
            title=f"Trip Report - {trip_id}",
            start_time=start_time,
            end_time=end_time,
            format=format,
        )
        return await self.generate_report(spec)

    async def generate_daily_report(
        self,
        date: datetime,
        format: str = "pdf"
    ) -> ReportResult:
        """Generate a daily report.

        Parameters
        ----------
        date:
            Date for report (datetime, will use day portion)
        format:
            Export format

        Returns
        -------
        ReportResult
        """
        dt = _coerce_ts(date)
        start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(hour=23, minute=59, second=59, microsecond=999999)

        spec = ReportSpec(
            report_type="daily",
            title=f"Daily Report - {start.strftime('%Y-%m-%d')}",
            start_time=start,
            end_time=end,
            format=format,
        )
        return await self.generate_report(spec)

    async def generate_catch_report(
        self,
        start_time: Any,
        end_time: Any,
        format: str = "pdf"
    ) -> ReportResult:
        """Generate a catch report.

        Parameters
        ----------
        start_time:
            Report start time
        end_time:
            Report end time
        format:
            Export format

        Returns
        -------
        ReportResult
        """
        spec = ReportSpec(
            report_type="catch",
            title="Catch Report",
            start_time=start_time,
            end_time=end_time,
            format=format,
        )
        return await self.generate_report(spec)

    # ------------------------------------------------------------------ #
    # Data gathering
    # ------------------------------------------------------------------ #
    async def _gather_report_data(self, spec: ReportSpec) -> dict[str, Any]:
        """Gather data for report generation.

        Parameters
        ----------
        spec:
            Report specification

        Returns
        -------
        dict
            Aggregated data for report
        """
        data = {
            "spec": {
                "report_type": spec.report_type,
                "title": spec.title,
                "start_time": spec.start_dt.isoformat(),
                "end_time": spec.end_dt.isoformat(),
                "vessel_id": spec.vessel_id,
            },
            "positions": [],
            "telemetry": {},
            "actions": [],
            "operations": [],
            "catch": [],
            "bathymetry": None,
            "vessel_state": None,
        }

        # Query position history
        if self._telemetry_query_cb:
            try:
                positions = await self._telemetry_query_cb(
                    channels={"position.lat", "position.lon"},
                    start_time=spec.start_dt,
                    end_time=spec.end_dt,
                )
                data["positions"] = positions
            except Exception as exc:
                log.warning("Failed to query positions: %s", exc)

        # Query relevant telemetry channels based on report type
        if self._telemetry_query_cb:
            channels = self._get_channels_for_report_type(spec.report_type)
            if channels:
                try:
                    telemetry = await self._telemetry_query_cb(
                        channels=channels,
                        start_time=spec.start_dt,
                        end_time=spec.end_dt,
                    )
                    data["telemetry"] = telemetry
                except Exception as exc:
                    log.warning("Failed to query telemetry: %s", exc)

        # Query A2A actions
        if self._a2a_query_cb:
            try:
                actions = await self._a2a_query_cb(
                    start_time=spec.start_dt,
                    end_time=spec.end_dt,
                )
                data["actions"] = actions
            except Exception as exc:
                log.warning("Failed to query A2A log: %s", exc)

        # Query operations log
        if self._oplog_query_cb:
            try:
                operations = await self._oplog_query_cb(
                    start_time=spec.start_dt,
                    end_time=spec.end_dt,
                )
                data["operations"] = operations

                # Extract catch data from operations
                if spec.report_type in {"catch", "trip", "daily"}:
                    data["catch"] = [
                        op for op in operations
                        if op.get("entry_type") == "catch_logged"
                    ]
            except Exception as exc:
                log.warning("Failed to query OpLog: %s", exc)

        # Query bathymetry for trip/daily reports
        if spec.report_type in {"trip", "daily"} and self._bathymetry_cb:
            try:
                bathymetry = await self._bathymetry_cb()
                data["bathymetry"] = bathymetry
            except Exception as exc:
                log.warning("Failed to query bathymetry: %s", exc)

        # Get current vessel state
        if self._vessel_state_cb:
            try:
                state = await self._vessel_state_cb()
                data["vessel_state"] = state
            except Exception as exc:
                log.warning("Failed to get vessel state: %s", exc)

        # Compute statistics
        data["statistics"] = self._compute_statistics(data, spec)

        return data

    def _get_channels_for_report_type(self, report_type: str) -> set[str] | None:
        """Get relevant telemetry channels for report type."""
        channel_map = {
            "trip": {"speed_kn", "heading_deg", "depth_m", "fuel_level", "engine_hours"},
            "daily": {"speed_kn", "heading_deg", "depth_m", "fuel_level", "engine_hours"},
            "catch": {"depth_m", "sea_surface_temp", "speed_kn"},
            "equipment": {"engine_hours", "hydraulic_pressure", "winch_speed"},
            "crew": {"speed_kn", "heading_deg"},
            "weather": {"wind_speed", "wind_dir", "air_temp", "sea_surface_temp", "barometer"},
            "performance": {"speed_kn", "fuel_rate", "engine_rpm", "depth_m"},
            "compliance": {"position.lat", "position.lon", "speed_kn"},
            "maintenance": {"engine_hours", "hydraulic_pressure", "temperature"},
            "fleet": {"speed_kn", "heading_deg", "fuel_level"},
        }
        return channel_map.get(report_type)

    def _compute_statistics(self, data: dict[str, Any], spec: ReportSpec) -> dict[str, Any]:
        """Compute statistical summaries for report data.

        Parameters
        ----------
        data:
            Gathered report data
        spec:
            Report specification

        Returns
        -------
        dict
            Statistical summaries
        """
        stats = {
            "record_count": {
                "positions": len(data.get("positions", [])),
                "actions": len(data.get("actions", [])),
                "operations": len(data.get("operations", [])),
                "catch": len(data.get("catch", [])),
            },
            "time_range": {
                "start": spec.start_dt.isoformat(),
                "end": spec.end_dt.isoformat(),
                "duration_hours": (spec.end_dt - spec.start_dt).total_seconds() / 3600,
            },
        }

        # Position statistics
        positions = data.get("positions", [])
        if positions:
            lats = [p.get("value", 0) for p in positions if p.get("channel") == "position.lat"]
            lons = [p.get("value", 0) for p in positions if p.get("channel") == "position.lon"]

            if lats and lons:
                stats["position"] = {
                    "lat_range": {"min": min(lats), "max": max(lats)},
                    "lon_range": {"min": min(lons), "max": max(lons)},
                }

        # Catch statistics
        catch_records = data.get("catch", [])
        if catch_records:
            total_weight = 0
            species_counts: dict[str, int] = {}

            for record in catch_records:
                metadata = record.get("metadata", {})
                weight = metadata.get("weight_kg", 0)
                species = metadata.get("species", "unknown")

                total_weight += weight
                species_counts[species] = species_counts.get(species, 0) + 1

            stats["catch"] = {
                "total_weight_kg": total_weight,
                "species_breakdown": species_counts,
                "total_records": len(catch_records),
            }

        # Telemetry statistics
        telemetry = data.get("telemetry", {})
        if telemetry and isinstance(telemetry, dict):
            stats["telemetry"] = {}

            for channel, readings in telemetry.items():
                if isinstance(readings, list) and readings:
                    values = [r.get("value", 0) for r in readings if isinstance(r.get("value"), (int, float))]
                    if values:
                        stats["telemetry"][channel] = {
                            "count": len(values),
                            "mean": sum(values) / len(values),
                            "min": min(values),
                            "max": max(values),
                        }

        # Action statistics
        actions = data.get("actions", [])
        if actions:
            action_counts: dict[str, int] = {}
            source_counts: dict[str, int] = {}

            for action in actions:
                action_type = action.get("action", "unknown")
                source = action.get("source", "unknown")

                action_counts[action_type] = action_counts.get(action_type, 0) + 1
                source_counts[source] = source_counts.get(source, 0) + 1

            stats["actions"] = {
                "total": len(actions),
                "by_type": action_counts,
                "by_source": source_counts,
            }

        # Operation statistics
        operations = data.get("operations", [])
        if operations:
            entry_type_counts: dict[str, int] = {}
            crew_counts: dict[str, int] = {}

            for op in operations:
                entry_type = op.get("entry_type", "unknown")
                crew = op.get("crew", "unknown")

                entry_type_counts[entry_type] = entry_type_counts.get(entry_type, 0) + 1
                crew_counts[crew] = crew_counts.get(crew, 0) + 1

            stats["operations"] = {
                "total": len(operations),
                "by_entry_type": entry_type_counts,
                "by_crew": crew_counts,
            }

        return stats

    # ------------------------------------------------------------------ #
    # Report rendering
    # ------------------------------------------------------------------ #
    async def _render_report(self, spec: ReportSpec, data: dict[str, Any]) -> str:
        """Render report content based on format.

        Parameters
        ----------
        spec:
            Report specification
        data:
            Gathered report data

        Returns
        -------
        str
            Rendered report content
        """
        renderer_map = {
            "html": self._render_html,
            "json": self._render_json,
            "csv": self._render_csv,
            "xml": self._render_xml,
            "md": self._render_markdown,
            "pdf": self._render_pdf,
        }

        renderer = renderer_map.get(spec.format)
        if renderer is None:
            raise ValueError(f"Unsupported format: {spec.format}")

        return await renderer(spec, data)

    async def _render_html(self, spec: ReportSpec, data: dict[str, Any]) -> str:
        """Render HTML report."""
        template = self._get_template(spec.report_type)
        if template:
            # Use template
            return template.format(**data)

        # Default HTML template
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{spec.title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #2c3e50; }}
        h2 {{ color: #34495e; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #3498db; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .summary {{ background-color: #ecf0f1; padding: 20px; border-radius: 5px; margin: 20px 0; }}
        .stat {{ display: inline-block; margin: 10px; padding: 10px; background-color: #3498db; color: white; border-radius: 3px; }}
        .timestamp {{ color: #7f8c8d; font-size: 0.9em; }}
    </style>
</head>
<body>
    <h1>{spec.title}</h1>
    <div class="summary">
        <p><strong>Vessel:</strong> {spec.vessel_id or 'N/A'}</p>
        <p><strong>Period:</strong> {spec.start_dt.strftime('%Y-%m-%d %H:%M')} to {spec.end_dt.strftime('%Y-%m-%d %H:%M')}</p>
        <p><strong>Generated:</strong> {_utc_now().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
    </div>

    {self._render_html_statistics(data)}

    {self._render_html_catch_table(data)}

    {self._render_html_operations_table(data)}

    {self._render_html_actions_table(data)}

</body>
</html>"""
        return html

    def _render_html_statistics(self, data: dict[str, Any]) -> str:
        """Render statistics section for HTML."""
        stats = data.get("statistics", {})
        if not stats:
            return ""

        html = "<h2>Statistics</h2>\n"
        html += '<div class="summary">\n'

        # Record counts
        record_count = stats.get("record_count", {})
        html += "<h3>Record Counts</h3>\n"
        html += "<p>"
        for key, count in record_count.items():
            html += f'<span class="stat">{key.title()}: {count}</span>\n'
        html += "</p>\n"

        # Time range
        time_range = stats.get("time_range", {})
        html += f"<h3>Time Range</h3>\n"
        html += f"<p>Duration: {time_range.get('duration_hours', 0):.1f} hours</p>\n"

        # Catch statistics
        catch_stats = stats.get("catch", {})
        if catch_stats:
            html += "<h3>Catch Summary</h3>\n"
            html += f"<p>Total Weight: {catch_stats.get('total_weight_kg', 0)} kg</p>\n"

            species_breakdown = catch_stats.get("species_breakdown", {})
            if species_breakdown:
                html += "<table>\n<tr><th>Species</th><th>Count</th></tr>\n"
                for species, count in species_breakdown.items():
                    html += f"<tr><td>{species}</td><td>{count}</td></tr>\n"
                html += "</table>\n"

        html += "</div>\n"
        return html

    def _render_html_catch_table(self, data: dict[str, Any]) -> str:
        """Render catch data table for HTML."""
        catch_records = data.get("catch", [])
        if not catch_records:
            return ""

        html = "<h2>Catch Records</h2>\n"
        html += "<table>\n"
        html += "<tr><th>Time</th><th>Crew</th><th>Species</th><th>Weight (kg)</th><th>Notes</th></tr>\n"

        for record in catch_records[:100]:  # Limit to 100 records
            ts = record.get("ts", "unknown")
            crew = record.get("crew", "unknown")
            metadata = record.get("metadata", {})
            species = metadata.get("species", "unknown")
            weight = metadata.get("weight_kg", "N/A")

            html += f"<tr><td>{ts}</td><td>{crew}</td><td>{species}</td><td>{weight}</td><td></td></tr>\n"

        html += "</table>\n"
        return html

    def _render_html_operations_table(self, data: dict[str, Any]) -> str:
        """Render operations table for HTML."""
        operations = data.get("operations", [])
        if not operations:
            return ""

        html = "<h2>Operations Log</h2>\n"
        html += "<table>\n"
        html += "<tr><th>Time</th><th>Type</th><th>Crew</th><th>Message</th></tr>\n"

        for op in operations[:50]:  # Limit to 50 records
            ts = op.get("ts", "unknown")
            entry_type = op.get("entry_type", "unknown")
            crew = op.get("crew", "unknown")
            message = op.get("message", "")

            html += f"<tr><td>{ts}</td><td>{entry_type}</td><td>{crew}</td><td>{message}</td></tr>\n"

        html += "</table>\n"
        return html

    def _render_html_actions_table(self, data: dict[str, Any]) -> str:
        """Render actions table for HTML."""
        actions = data.get("actions", [])
        if not actions:
            return ""

        html = "<h2>Actions Log</h2>\n"
        html += "<table>\n"
        html += "<tr><th>Time</th><th>Action</th><th>Source</th><th>Priority</th><th>Reason</th></tr>\n"

        for action in actions[:50]:  # Limit to 50 records
            ts = action.get("ts", "unknown")
            act = action.get("action", "unknown")
            source = action.get("source", "unknown")
            priority = action.get("priority", 0)
            reason = action.get("reason", "")

            html += f"<tr><td>{ts}</td><td>{act}</td><td>{source}</td><td>{priority:.2f}</td><td>{reason}</td></tr>\n"

        html += "</table>\n"
        return html

    async def _render_json(self, spec: ReportSpec, data: dict[str, Any]) -> str:
        """Render JSON report."""
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)

    async def _render_csv(self, spec: ReportSpec, data: dict[str, Any]) -> str:
        """Render CSV report."""
        output = io.StringIO()

        # Multi-sheet CSV: sections separated by headers
        writer = csv.writer(output)

        # Metadata section
        writer.writerow(["Report Metadata"])
        writer.writerow(["Report Type", spec.report_type])
        writer.writerow(["Title", spec.title])
        writer.writerow(["Start Time", spec.start_dt.isoformat()])
        writer.writerow(["End Time", spec.end_dt.isoformat()])
        writer.writerow(["Generated", _utc_now().isoformat()])
        writer.writerow([])

        # Statistics section
        stats = data.get("statistics", {})
        if stats:
            writer.writerow(["Statistics"])

            record_count = stats.get("record_count", {})
            if record_count:
                writer.writerow(["Record Counts"])
                writer.writerow(["Category", "Count"])
                for key, count in record_count.items():
                    writer.writerow([key, count])
                writer.writerow([])

            catch_stats = stats.get("catch", {})
            if catch_stats:
                writer.writerow(["Catch Statistics"])
                writer.writerow(["Total Weight (kg)", catch_stats.get("total_weight_kg", 0)])
                writer.writerow([])

        # Catch records section
        catch_records = data.get("catch", [])
        if catch_records:
            writer.writerow(["Catch Records"])
            writer.writerow(["Time", "Crew", "Species", "Weight (kg)", "Notes"])

            for record in catch_records:
                metadata = record.get("metadata", {})
                writer.writerow([
                    record.get("ts", ""),
                    record.get("crew", ""),
                    metadata.get("species", ""),
                    metadata.get("weight_kg", ""),
                    record.get("message", ""),
                ])
            writer.writerow([])

        # Operations section
        operations = data.get("operations", [])
        if operations:
            writer.writerow(["Operations Log"])
            writer.writerow(["Time", "Type", "Crew", "Message"])

            for op in operations:
                writer.writerow([
                    op.get("ts", ""),
                    op.get("entry_type", ""),
                    op.get("crew", ""),
                    op.get("message", ""),
                ])
            writer.writerow([])

        # Actions section
        actions = data.get("actions", [])
        if actions:
            writer.writerow(["Actions Log"])
            writer.writerow(["Time", "Action", "Source", "Priority", "Reason"])

            for action in actions:
                writer.writerow([
                    action.get("ts", ""),
                    action.get("action", ""),
                    action.get("source", ""),
                    action.get("priority", ""),
                    action.get("reason", ""),
                ])

        return output.getvalue()

    async def _render_xml(self, spec: ReportSpec, data: dict[str, Any]) -> str:
        """Render XML report (e-logbook format)."""
        root = ET.Element("Report")
        root.set("type", spec.report_type)
        root.set("generated", _utc_now().isoformat())

        # Metadata
        metadata = ET.SubElement(root, "Metadata")
        ET.SubElement(metadata, "Title").text = spec.title
        ET.SubElement(metadata, "StartTime").text = spec.start_dt.isoformat()
        ET.SubElement(metadata, "EndTime").text = spec.end_dt.isoformat()
        if spec.vessel_id:
            ET.SubElement(metadata, "VesselID").text = spec.vessel_id

        # Statistics
        stats = data.get("statistics", {})
        stats_elem = ET.SubElement(root, "Statistics")

        record_count = stats.get("record_count", {})
        counts_elem = ET.SubElement(stats_elem, "RecordCounts")
        for key, count in record_count.items():
            elem = ET.SubElement(counts_elem, "Count")
            elem.set("type", key)
            elem.text = str(count)

        catch_stats = stats.get("catch", {})
        if catch_stats:
            catch_elem = ET.SubElement(stats_elem, "Catch")
            ET.SubElement(catch_elem, "TotalWeightKg").text = str(catch_stats.get("total_weight_kg", 0))

            species_breakdown = catch_stats.get("species_breakdown", {})
            if species_breakdown:
                species_elem = ET.SubElement(catch_elem, "SpeciesBreakdown")
                for species, count in species_breakdown.items():
                    sp = ET.SubElement(species_elem, "Species")
                    sp.set("name", species)
                    sp.text = str(count)

        # Catch records
        catch_records = data.get("catch", [])
        if catch_records:
            catches_elem = ET.SubElement(root, "CatchRecords")
            for record in catch_records:
                catch_elem = ET.SubElement(catches_elem, "Catch")
                catch_elem.set("timestamp", record.get("ts", ""))
                catch_elem.set("crew", record.get("crew", ""))

                metadata = record.get("metadata", {})
                ET.SubElement(catch_elem, "Species").text = metadata.get("species", "")
                ET.SubElement(catch_elem, "WeightKg").text = str(metadata.get("weight_kg", 0))

        # Operations
        operations = data.get("operations", [])
        if operations:
            ops_elem = ET.SubElement(root, "Operations")
            for op in operations:
                op_elem = ET.SubElement(ops_elem, "Operation")
                op_elem.set("timestamp", op.get("ts", ""))
                ET.SubElement(op_elem, "Type").text = op.get("entry_type", "")
                ET.SubElement(op_elem, "Crew").text = op.get("crew", "")
                ET.SubElement(op_elem, "Message").text = op.get("message", "")

        # Actions
        actions = data.get("actions", [])
        if actions:
            actions_elem = ET.SubElement(root, "Actions")
            for action in actions:
                act_elem = ET.SubElement(actions_elem, "Action")
                act_elem.set("timestamp", action.get("ts", ""))
                ET.SubElement(act_elem, "Name").text = action.get("action", "")
                ET.SubElement(act_elem, "Source").text = action.get("source", "")
                ET.SubElement(act_elem, "Priority").text = str(action.get("priority", ""))
                ET.SubElement(act_elem, "Reason").text = action.get("reason", "")

        # Pretty print
        xml_str = ET.tostring(root, encoding="unicode")
        dom = minidom.parseString(xml_str)
        return dom.toprettyxml(indent="  ")

    async def _render_markdown(self, spec: ReportSpec, data: dict[str, Any]) -> str:
        """Render Markdown report."""
        md = f"# {spec.title}\n\n"
        md += f"**Vessel:** {spec.vessel_id or 'N/A'}\n"
        md += f"**Period:** {spec.start_dt.strftime('%Y-%m-%d %H:%M')} to {spec.end_dt.strftime('%Y-%m-%d %H:%M')}\n"
        md += f"**Generated:** {_utc_now().strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"

        # Statistics
        stats = data.get("statistics", {})
        if stats:
            md += "## Statistics\n\n"

            record_count = stats.get("record_count", {})
            if record_count:
                md += "### Record Counts\n\n"
                for key, count in record_count.items():
                    md += f"- **{key.title()}:** {count}\n"
                md += "\n"

            catch_stats = stats.get("catch", {})
            if catch_stats:
                md += "### Catch Summary\n\n"
                md += f"- **Total Weight:** {catch_stats.get('total_weight_kg', 0)} kg\n"
                md += f"- **Total Records:** {catch_stats.get('total_records', 0)}\n\n"

                species_breakdown = catch_stats.get("species_breakdown", {})
                if species_breakdown:
                    md += "#### Species Breakdown\n\n"
                    md += "| Species | Count |\n"
                    md += "|---------|-------|\n"
                    for species, count in species_breakdown.items():
                        md += f"| {species} | {count} |\n"
                    md += "\n"

        # Catch records
        catch_records = data.get("catch", [])
        if catch_records:
            md += "## Catch Records\n\n"
            md += "| Time | Crew | Species | Weight (kg) |\n"
            md += "|------|------|---------|-------------|\n"

            for record in catch_records[:100]:
                metadata = record.get("metadata", {})
                md += f"| {record.get('ts', '')} | {record.get('crew', '')} | {metadata.get('species', '')} | {metadata.get('weight_kg', '')} |\n"
            md += "\n"

        # Operations
        operations = data.get("operations", [])
        if operations:
            md += "## Operations Log\n\n"
            md += "| Time | Type | Crew | Message |\n"
            md += "|------|------|------|---------|\n"

            for op in operations[:50]:
                md += f"| {op.get('ts', '')} | {op.get('entry_type', '')} | {op.get('crew', '')} | {op.get('message', '')} |\n"
            md += "\n"

        # Actions
        actions = data.get("actions", [])
        if actions:
            md += "## Actions Log\n\n"
            md += "| Time | Action | Source | Priority | Reason |\n"
            md += "|------|--------|--------|----------|--------|\n"

            for action in actions[:50]:
                md += f"| {action.get('ts', '')} | {action.get('action', '')} | {action.get('source', '')} | {action.get('priority', '')} | {action.get('reason', '')} |\n"
            md += "\n"

        return md

    async def _render_pdf(self, spec: ReportSpec, data: dict[str, Any]) -> str:
        """Render PDF report (requires external library, falls back to HTML)."""
        # For now, return HTML which can be converted to PDF
        # In production, use weasyprint or reportlab
        log.warning("PDF generation not fully implemented, returning HTML")
        return await self._render_html(spec, data)

    def _get_template(self, report_type: str) -> str | None:
        """Load report template from file.

        Parameters
        ----------
        report_type:
            Type of report

        Returns
        -------
        str or None
            Template content or None if not found
        """
        template_file = self.template_path / f"{report_type}_report.html"
        if not template_file.exists():
            return None

        try:
            return template_file.read_text(encoding="utf-8")
        except OSError as exc:
            log.warning("Failed to load template %s: %s", template_file, exc)
            return None

    def _get_file_extension(self, format: str) -> str:
        """Get file extension for export format."""
        extensions = {
            "pdf": ".pdf",
            "html": ".html",
            "json": ".json",
            "csv": ".csv",
            "xml": ".xml",
            "md": ".md",
        }
        return extensions.get(format, ".txt")

    async def _save_report(self, file_path: Path, content: str, format: str) -> None:
        """Save report to file.

        Parameters
        ----------
        file_path:
            Destination file path
        content:
            Report content
        format:
            Export format
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "pdf":
            # For PDF, content is actually HTML that needs conversion
            # Save as HTML for now with .pdf extension warning
            log.warning("Saving HTML as .pdf - conversion needed")
            file_path = file_path.with_suffix(".html")

        with file_path.open("w", encoding="utf-8") as f:
            f.write(content)

        log.info("Report saved to %s", file_path)

        # Update the path to reflect actual saved file
        return file_path

    # ------------------------------------------------------------------ #
    # Scheduling
    # ------------------------------------------------------------------ #
    def schedule_report(self, spec: ReportSpec, cron_expression: str) -> str:
        """Schedule a report for automatic generation.

        Parameters
        ----------
        spec:
            Report specification
        cron_expression:
            Cron expression (e.g., "0 6 * * *" for daily at 6am)

        Returns
        -------
        str
            Schedule ID
        """
        schedule_id = str(uuid.uuid4())

        schedule = ScheduleSpec(
            schedule_id=schedule_id,
            spec=spec,
            cron_expression=cron_expression,
            enabled=True,
        )

        self._schedules[schedule_id] = schedule
        log.info("Report scheduled: %s - %s", schedule_id, cron_expression)

        return schedule_id

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
        if schedule_id in self._schedules:
            del self._schedules[schedule_id]
            log.info("Schedule cancelled: %s", schedule_id)
            return True
        return False

    def get_scheduled_reports(self) -> list[dict[str, Any]]:
        """Get all scheduled reports.

        Returns
        -------
        list[dict]
            List of schedule specifications
        """
        return [schedule.to_dict() for schedule in self._schedules.values()]

    # ------------------------------------------------------------------ #
    # Report management
    # ------------------------------------------------------------------ #
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
        return self._reports.get(report_id)

    def list_reports(
        self,
        report_type: str | None = None,
        limit: int = 100
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
        reports = list(self._reports.values())

        if report_type:
            reports = [r for r in reports if r.spec.report_type == report_type]

        # Sort by generated time, newest first
        reports.sort(key=lambda r: r.generated_at, reverse=True)

        return reports[:limit]

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
        if report_id not in self._reports:
            return False

        result = self._reports[report_id]

        # Delete file if exists
        if result.file_path:
            try:
                Path(result.file_path).unlink(missing_ok=True)
            except OSError as exc:
                log.warning("Failed to delete report file %s: %s", result.file_path, exc)

        del self._reports[report_id]
        log.info("Report deleted: %s", report_id)
        return True

    # ------------------------------------------------------------------ #
    # Delivery
    # ------------------------------------------------------------------ #
    async def _send_report_email(
        self,
        result: ReportResult,
        recipients: list[str]
    ) -> None:
        """Send report via email.

        Parameters
        ----------
        result:
            Report result
        recipients:
            List of recipient email addresses
        """
        if not self.smtp_host or not self.smtp_from:
            log.warning("Email delivery not configured")
            return

        try:
            msg = MIMEMultipart()
            msg["From"] = self.smtp_from
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = f"{result.spec.title} - {result.spec.report_type.upper()}"

            # Body
            body = f"""
Report: {result.spec.title}
Type: {result.spec.report_type}
Period: {result.spec.start_dt.strftime('%Y-%m-%d %H:%M')} to {result.spec.end_dt.strftime('%Y-%m-%d %H:%M')}
Generated: {result.generated_at.strftime('%Y-%m-%d %H:%M:%S')} UTC
Status: {result.status}
"""
            if result.error_message:
                body += f"Error: {result.error_message}\n"

            msg.attach(MIMEText(body, "plain"))

            # Attach file if available
            if result.file_path:
                try:
                    with open(result.file_path, "rb") as f:
                        attachment = MIMEApplication(f.read())
                        attachment.add_header(
                            "Content-Disposition",
                            "attachment",
                            filename=Path(result.file_path).name
                        )
                        msg.attach(attachment)
                except OSError as exc:
                    log.warning("Failed to attach report file: %s", exc)

            # Send via SMTP
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.smtp_user and self.smtp_password:
                    server.starttls()
                    server.login(self.smtp_user, self.smtp_password)

                server.send_message(msg)

            log.info("Report sent to %d recipients", len(recipients))

        except Exception as exc:
            log.error("Failed to send report email: %s", exc)

    def register_webhook(self, url: str, report_types: list[str]) -> None:
        """Register webhook for report notifications.

        Parameters
        ----------
        url:
            Webhook URL
        report_types:
            List of report types to trigger on
        """
        for report_type in report_types:
            if report_type not in self._webhooks:
                self._webhooks[report_type] = []
            self._webhooks[report_type].append(url)

        log.info("Webhook registered: %s for types %s", url, report_types)

    async def _trigger_webhooks(self, report_type: str, result: ReportResult) -> None:
        """Trigger registered webhooks.

        Parameters
        ----------
        report_type:
            Report type
        result:
            Report result
        """
        urls = self._webhooks.get(report_type, [])
        if not urls:
            return

        payload = result.to_dict()

        async with aiohttp.ClientSession() as session:
            for url in urls:
                try:
                    async with session.post(url, json=payload) as response:
                        if response.status >= 400:
                            log.warning("Webhook returned error: %s - %d", url, response.status)
                        else:
                            log.info("Webhook triggered: %s", url)
                except aiohttp.ClientError as exc:
                    log.warning("Webhook failed: %s - %s", url, exc)

    # ------------------------------------------------------------------ #
    # Template management
    # ------------------------------------------------------------------ #
    def register_template(self, template_name: str, template_path: str) -> None:
        """Register a report template.

        Parameters
        ----------
        template_name:
            Template identifier (e.g., "trip_report")
        template_path:
            Path to template file
        """
        src = Path(template_path)
        dst = self.template_path / f"{template_name}.html"

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            log.info("Template registered: %s from %s", template_name, template_path)
        except OSError as exc:
            log.error("Failed to register template: %s", exc)

    def get_template(self, template_name: str) -> str | None:
        """Get a template by name.

        Parameters
        ----------
        template_name:
            Template identifier

        Returns
        -------
        str or None
            Template content or None if not found
        """
        template_file = self.template_path / f"{template_name}.html"
        if not template_file.exists():
            return None

        try:
            return template_file.read_text(encoding="utf-8")
        except OSError as exc:
            log.warning("Failed to read template %s: %s", template_name, exc)
            return None

    # ------------------------------------------------------------------ #
    # Status
    # ------------------------------------------------------------------ #
    async def stats(self) -> dict[str, Any]:
        """Get system statistics.

        Returns
        -------
        dict
            System status and statistics
        """
        return {
            "storage_path": str(self.storage_path),
            "template_path": str(self.template_path),
            "total_reports": len(self._reports),
            "total_schedules": len(self._schedules),
            "total_webhooks": sum(len(urls) for urls in self._webhooks.values()),
            "email_configured": self.smtp_host is not None,
        }
