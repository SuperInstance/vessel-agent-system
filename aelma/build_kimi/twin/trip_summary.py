"""Trip summary generator for AELMA twin.

Accumulates and aggregates telemetry, operational, and alert data
to generate comprehensive trip summaries. Supports multiple export formats.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from functools import cached_property
except ImportError:
    cached_property = property  # type: ignore


@dataclass
class AlertSummary:
    """Summary of alerts fired during the trip."""

    total_count: int = 0
    by_severity: dict[str, int] = field(default_factory=dict)
    by_code: dict[str, int] = field(default_factory=dict)
    highest_priority: float = 0.0
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0

    def add_alert(self, action: dict[str, Any]) -> None:
        """Record an alert action."""
        self.total_count += 1

        payload = action.get("payload", {})
        severity = payload.get("severity", "unknown")
        code = payload.get("code", "UNKNOWN")
        priority = action.get("priority", 0.5)

        self.by_severity[severity] = self.by_severity.get(severity, 0) + 1
        self.by_code[code] = self.by_code.get(code, 0) + 1
        self.highest_priority = max(self.highest_priority, priority)

        if severity == "critical":
            self.critical_count += 1
        elif severity == "warning":
            self.warning_count += 1
        elif severity == "info":
            self.info_count += 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_count": self.total_count,
            "by_severity": self.by_severity,
            "by_code": self.by_code,
            "highest_priority": self.highest_priority,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
        }


@dataclass
class ModeTimeSummary:
    """Summary of time spent in each fishing mode."""

    total_duration_ns: int = 0
    mode_durations_ns: dict[str, int] = field(default_factory=dict)
    mode_entries: dict[str, int] = field(default_factory=dict)

    def add_mode_duration(self, mode: str, duration_ns: int, entries: int) -> None:
        """Add time spent in a mode."""
        self.total_duration_ns += duration_ns
        self.mode_durations_ns[mode] = self.mode_durations_ns.get(mode, 0) + duration_ns
        self.mode_entries[mode] = self.mode_entries.get(mode, 0) + entries

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_duration_ns": self.total_duration_ns,
            "total_duration_s": self.total_duration_ns / 1e9,
            "total_duration_h": self.total_duration_ns / 1e9 / 3600,
            "mode_durations_ns": self.mode_durations_ns,
            "mode_durations_s": {k: v / 1e9 for k, v in self.mode_durations_ns.items()},
            "mode_durations_h": {k: v / 1e9 / 3600 for k, v in self.mode_durations_ns.items()},
            "mode_durations_pct": {
                k: (v / self.total_duration_ns * 100) if self.total_duration_ns > 0 else 0
                for k, v in self.mode_durations_ns.items()
            },
            "mode_entries": self.mode_entries,
        }


@dataclass
class CatchStatistics:
    """Summary of catch data (if available)."""

    total_catch_kg: float = 0.0
    species_counts: dict[str, int] = field(default_factory=dict)
    haul_count: int = 0
    best_haul_kg: float = 0.0
    avg_haul_kg: float = 0.0

    def add_haul(self, species: str, weight_kg: float) -> None:
        """Record a haul."""
        self.haul_count += 1
        self.total_catch_kg += weight_kg
        self.species_counts[species] = self.species_counts.get(species, 0) + 1
        self.best_haul_kg = max(self.best_haul_kg, weight_kg)
        self.avg_haul_kg = self.total_catch_kg / self.haul_count if self.haul_count > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_catch_kg": self.total_catch_kg,
            "species_counts": self.species_counts,
            "haul_count": self.haul_count,
            "best_haul_kg": self.best_haul_kg,
            "avg_haul_kg": self.avg_haul_kg,
        }


@dataclass
class FuelStatistics:
    """Summary of fuel consumption (if engine data available)."""

    total_fuel_l: float = 0.0
    avg_consumption_lh: float = 0.0
    max_consumption_lh: float = 0.0
    engine_hours: float = 0.0

    def __post_init__(self) -> None:
        # Initialize numeric fields to 0.0 to avoid None issues
        if self.total_fuel_l is None:
            self.total_fuel_l = 0.0
        if self.avg_consumption_lh is None:
            self.avg_consumption_lh = 0.0
        if self.max_consumption_lh is None:
            self.max_consumption_lh = 0.0
        if self.engine_hours is None:
            self.engine_hours = 0.0

    def add_fuel_reading(self, fuel_rate_lh: float, duration_s: float) -> None:
        """Add fuel consumption reading."""
        self.total_fuel_l += fuel_rate_lh * (duration_s / 3600)
        self.max_consumption_lh = max(self.max_consumption_lh, fuel_rate_lh)
        self.engine_hours += duration_s / 3600
        self.avg_consumption_lh = self.total_fuel_l / self.engine_hours if self.engine_hours > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_fuel_l": self.total_fuel_l,
            "avg_consumption_lh": self.avg_consumption_lh,
            "max_consumption_lh": self.max_consumption_lh,
            "engine_hours": self.engine_hours,
        }


@dataclass
class WeatherSummary:
    """Summary of weather conditions encountered."""

    min_wind_speed_kn: float | None = None
    max_wind_speed_kn: float | None = None
    avg_wind_speed_kn: float = 0.0
    min_wave_height_m: float | None = None
    max_wave_height_m: float | None = None
    avg_wave_height_m: float = 0.0
    wind_readings: int = 0
    wave_readings: int = 0

    def __post_init__(self) -> None:
        # Initialize avg fields to 0.0 to avoid None issues
        if self.avg_wind_speed_kn is None:
            self.avg_wind_speed_kn = 0.0
        if self.avg_wave_height_m is None:
            self.avg_wave_height_m = 0.0

    def add_wind_reading(self, wind_speed_kn: float) -> None:
        """Add wind speed reading."""
        self.wind_readings += 1
        if self.min_wind_speed_kn is None or wind_speed_kn < self.min_wind_speed_kn:
            self.min_wind_speed_kn = wind_speed_kn
        if self.max_wind_speed_kn is None or wind_speed_kn > self.max_wind_speed_kn:
            self.max_wind_speed_kn = wind_speed_kn
        self.avg_wind_speed_kn = (
            (self.avg_wind_speed_kn * (self.wind_readings - 1) + wind_speed_kn) / self.wind_readings
        )

    def add_wave_reading(self, wave_height_m: float) -> None:
        """Add wave height reading."""
        self.wave_readings += 1
        if self.min_wave_height_m is None or wave_height_m < self.min_wave_height_m:
            self.min_wave_height_m = wave_height_m
        if self.max_wave_height_m is None or wave_height_m > self.max_wave_height_m:
            self.max_wave_height_m = wave_height_m
        self.avg_wave_height_m = (
            (self.avg_wave_height_m * (self.wave_readings - 1) + wave_height_m) / self.wave_readings
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "wind_speed_kn": {
                "min": self.min_wind_speed_kn,
                "max": self.max_wind_speed_kn,
                "avg": self.avg_wind_speed_kn,
                "readings": self.wind_readings,
            },
            "wave_height_m": {
                "min": self.min_wave_height_m,
                "max": self.max_wave_height_m,
                "avg": self.avg_wave_height_m,
                "readings": self.wave_readings,
            },
        }


@dataclass
class PositionHistory:
    """Track position history for distance calculation."""

    positions: list[tuple[int, float, float]] = field(default_factory=list)  # (ts, lat, lon)
    total_distance_m: float = 0.0

    def add_position(self, timestamp_ns: int, lat: float, lon: float) -> None:
        """Add a position fix and calculate distance from previous."""
        if self.positions:
            prev_ts, prev_lat, prev_lon = self.positions[-1]
            # Only add if this is a new fix (different timestamp or position)
            if timestamp_ns != prev_ts or lat != prev_lat or lon != prev_lon:
                distance_m = haversine_m(prev_lat, prev_lon, lat, lon)
                self.total_distance_m += distance_m
                self.positions.append((timestamp_ns, lat, lon))
        else:
            self.positions.append((timestamp_ns, lat, lon))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_distance_m": self.total_distance_m,
            "total_distance_km": self.total_distance_m / 1000,
            "total_distance_nm": self.total_distance_m / 1852,
            "position_count": len(self.positions),
        }

    @property
    def position_count(self) -> int:
        """Get number of position fixes."""
        return len(self.positions)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in meters using haversine formula."""
    if lat1 == lat2 and lon1 == lon2:
        return 0.0

    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


class TripSummary:
    """Accumulates and aggregates trip data for summary generation.

    The TripSummary collector provides comprehensive trip analytics by
    accumulating telemetry, operational, and alert data throughout a
    vessel's journey. It supports multiple export formats and integrates
    with the TwinCore system.

    Example:
        >>> summary = TripSummary(vessel_id="US-AK-FVEILEEN-51")
        >>> summary.add_telemetry({"timestamp_ns": T0, "channel": "depth_m", "value": 73.2})
        >>> summary.add_oplog_entry({"action": "start_fishing", "timestamp_ns": T0})
        >>> summary.add_a2a_action({"action": "raise_alert", "priority": 0.9})
        >>> result = summary.generate_summary()
        >>> print(result["total_distance_km"])
    """

    def __init__(self, vessel_id: str = "unknown") -> None:
        """Initialize a TripSummary collector.

        Args:
            vessel_id: Vessel identifier for this trip.
        """
        self.vessel_id = vessel_id
        self.start_timestamp_ns: int | None = None
        self.end_timestamp_ns: int | None = None

        # Data accumulators
        self.depth_readings: list[float] = []
        self.position_history = PositionHistory()
        self.alerts = AlertSummary()
        self.mode_time = ModeTimeSummary()
        self.catch = CatchStatistics()
        self.fuel = FuelStatistics()
        self.weather = WeatherSummary()

        # OpLog entries (crew operations)
        self.oplog_entries: list[dict[str, Any]] = []

        # A2A actions (automated actions)
        self.a2a_actions: list[dict[str, Any]] = []

        # Track if we've accumulated data
        self._has_data = False

    def add_telemetry(self, record: dict[str, Any] | TelemetryRecord) -> None:
        """Accumulate telemetry data into the summary.

        Args:
            record: Telemetry packet dict or TelemetryRecord with timestamp_ns,
                    channel, value, and optional quality fields.
        """
        if isinstance(record, dict):
            timestamp_ns = int(record.get("timestamp_ns", 0))
            channel = str(record.get("channel", ""))
            value = record.get("value")
        else:
            timestamp_ns = record.timestamp_ns
            channel = record.channel
            value = record.value

        if value is None:
            return

        # Set timestamps
        if self.start_timestamp_ns is None or timestamp_ns < self.start_timestamp_ns:
            self.start_timestamp_ns = timestamp_ns
        if self.end_timestamp_ns is None or timestamp_ns > self.end_timestamp_ns:
            self.end_timestamp_ns = timestamp_ns

        self._has_data = True

        # Accumulate by channel
        if channel == "depth_m":
            if isinstance(value, (int, float)) and value > 0:
                self.depth_readings.append(float(value))

        elif channel == "position.lat":
            if isinstance(value, (int, float)):
                self._last_lat = float(value)
                self._last_lat_ts = timestamp_ns
                self._try_update_position(timestamp_ns)

        elif channel == "position.lon":
            if isinstance(value, (int, float)):
                self._last_lon = float(value)
                self._last_lon_ts = timestamp_ns
                self._try_update_position(timestamp_ns)

        elif channel == "wind_speed_kn":
            if isinstance(value, (int, float)) and value >= 0:
                self.weather.add_wind_reading(float(value))

        elif channel == "wave_height_m":
            if isinstance(value, (int, float)) and value >= 0:
                self.weather.add_wave_reading(float(value))

        elif channel == "engine_fuel_rate_lh":
            if isinstance(value, (int, float)) and value >= 0:
                # Estimate duration since last reading (1 second default)
                self.fuel.add_fuel_reading(float(value), 1.0)

    def _try_update_position(self, timestamp_ns: int) -> None:
        """Update position history when both lat and lon available."""
        if hasattr(self, "_last_lat") and hasattr(self, "_last_lon"):
            if hasattr(self, "_last_lat_ts") and hasattr(self, "_last_lon_ts"):
                if self._last_lat_ts == self._last_lon_ts == timestamp_ns:
                    self.position_history.add_position(
                        timestamp_ns, self._last_lat, self._last_lon
                    )

    def add_oplog_entry(self, entry: dict[str, Any]) -> None:
        """Add a crew operation log entry.

        Args:
            entry: OpLog entry dict with action, timestamp_ns, and optional fields.
        """
        self.oplog_entries.append(entry)
        self._has_data = True

        # Extract catch data if present
        if entry.get("action") == "log_catch":
            species = entry.get("species", "unknown")
            weight_kg = entry.get("weight_kg", 0.0)
            if isinstance(weight_kg, (int, float)) and weight_kg > 0:
                self.catch.add_haul(species, float(weight_kg))

    def add_a2a_action(self, action: dict[str, Any]) -> None:
        """Add an automated A2A action.

        Args:
            action: A2A action dict with action, payload, priority, etc.
        """
        self.a2a_actions.append(action)
        self._has_data = True

        # Track alerts
        if action.get("action") == "raise_alert":
            self.alerts.add_alert(action)

    def add_mode_duration(self, mode: str, duration_ns: int, entries: int = 1) -> None:
        """Add time spent in a fishing mode.

        Args:
            mode: Fishing mode name (TRANSIT, FISHING, etc.)
            duration_ns: Time spent in this mode in nanoseconds
            entries: Number of times this mode was entered
        """
        self.mode_time.add_mode_duration(mode, duration_ns, entries)
        self._has_data = True

    def generate_summary(self) -> dict[str, Any]:
        """Generate complete trip summary.

        Returns:
            Dict with all accumulated statistics and metadata.
        """
        # Calculate trip duration
        if self.start_timestamp_ns is not None and self.end_timestamp_ns is not None:
            duration_ns = self.end_timestamp_ns - self.start_timestamp_ns
        else:
            duration_ns = 0

        # Calculate depth statistics
        depth_stats = self._calculate_depth_stats()

        return {
            "vessel_id": self.vessel_id,
            "trip": {
                "start_timestamp_ns": self.start_timestamp_ns,
                "end_timestamp_ns": self.end_timestamp_ns,
                "start_iso": self._ns_to_iso(self.start_timestamp_ns) if self.start_timestamp_ns else None,
                "end_iso": self._ns_to_iso(self.end_timestamp_ns) if self.end_timestamp_ns else None,
                "duration_ns": duration_ns,
                "duration_s": duration_ns / 1e9,
                "duration_h": duration_ns / 1e9 / 3600,
            },
            "distance": self.position_history.to_dict(),
            "depth": depth_stats,
            "fishing_modes": self.mode_time.to_dict(),
            "alerts": self.alerts.to_dict(),
            "catch": self.catch.to_dict(),
            "fuel": self.fuel.to_dict(),
            "weather": self.weather.to_dict(),
            "crew_actions": {
                "total_count": len(self.oplog_entries),
                "actions": self.oplog_entries,
            },
            "automated_actions": {
                "total_count": len(self.a2a_actions),
                "actions": self.a2a_actions,
            },
            "data_quality": {
                "telemetry_records": len(self.depth_readings) + self.position_history.position_count,
                "position_fixes": self.position_history.position_count,
                "depth_readings": len(self.depth_readings),
                "wind_readings": self.weather.wind_readings,
                "wave_readings": self.weather.wave_readings,
            },
        }

    def _calculate_depth_stats(self) -> dict[str, Any]:
        """Calculate depth statistics."""
        if not self.depth_readings:
            return {
                "min_m": None,
                "max_m": None,
                "avg_m": None,
                "reading_count": 0,
            }

        depths = self.depth_readings
        return {
            "min_m": min(depths),
            "max_m": max(depths),
            "avg_m": sum(depths) / len(depths),
            "reading_count": len(depths),
        }

    def _ns_to_iso(self, timestamp_ns: int) -> str:
        """Convert nanosecond timestamp to ISO 8601 string."""
        dt = datetime.fromtimestamp(timestamp_ns / 1e9, tz=timezone.utc)
        return dt.isoformat()

    def export_json(self, path: str | Path) -> None:
        """Export summary as JSON file.

        Args:
            path: Output file path.
        """
        summary = self.generate_summary()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, default=str)

    def export_html(self, path: str | Path) -> None:
        """Export summary as HTML report.

        Args:
            path: Output file path.
        """
        summary = self.generate_summary()
        html = self._format_html(summary)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

    def export_text(self, path: str | Path) -> None:
        """Export summary as plain text report.

        Args:
            path: Output file path.
        """
        summary = self.generate_summary()
        text = self._format_text(summary)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def _format_html(self, summary: dict[str, Any]) -> str:
        """Format summary as HTML."""
        trip = summary["trip"]
        distance = summary["distance"]
        depth = summary["depth"]
        modes = summary["fishing_modes"]
        alerts = summary["alerts"]

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Trip Summary - {self.vessel_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #2c3e50; }}
        h2 {{ color: #34495e; border-bottom: 2px solid #3498db; }}
        table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #3498db; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .summary {{ background-color: #ecf0f1; padding: 15px; border-radius: 5px; }}
        .alert-critical {{ color: #e74c3c; font-weight: bold; }}
        .alert-warning {{ color: #f39c12; }}
        .alert-info {{ color: #3498db; }}
    </style>
</head>
<body>
    <h1>Trip Summary: {self.vessel_id}</h1>

    <div class="summary">
        <h2>Trip Overview</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Start Time</td><td>{trip.get('start_iso', 'N/A')}</td></tr>
            <tr><td>End Time</td><td>{trip.get('end_iso', 'N/A')}</td></tr>
            <tr><td>Duration</td><td>{trip.get('duration_h', 0):.2f} hours</td></tr>
            <tr><td>Total Distance</td><td>{distance.get('total_distance_nm', 0):.2f} nm</td></tr>
            <tr><td>Position Fixes</td><td>{distance.get('position_count', 0)}</td></tr>
        </table>
    </div>

    <div class="summary">
        <h2>Depth Statistics</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Minimum Depth</td><td>{depth.get('min_m', 'N/A')} m</td></tr>
            <tr><td>Maximum Depth</td><td>{depth.get('max_m', 'N/A')} m</td></tr>
            <tr><td>Average Depth</td><td>{depth.get('avg_m', 'N/A')} m</td></tr>
            <tr><td>Readings</td><td>{depth.get('reading_count', 0)}</td></tr>
        </table>
    </div>

    <div class="summary">
        <h2>Fishing Modes</h2>
        <table>
            <tr><th>Mode</th><th>Duration (h)</th><th>Percentage</th><th>Entries</th></tr>
"""

        for mode, duration_h in modes.get('mode_durations_h', {}).items():
            pct = modes.get('mode_durations_pct', {}).get(mode, 0)
            entries = modes.get('mode_entries', {}).get(mode, 0)
            html += f"            <tr><td>{mode}</td><td>{duration_h:.2f}</td><td>{pct:.1f}%</td><td>{entries}</td></tr>\n"

        html += """        </table>
    </div>

    <div class="summary">
        <h2>Alerts Summary</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Total Alerts</td><td>{}</td></tr>
            <tr><td>Critical</td><td class="alert-critical">{}</td></tr>
            <tr><td>Warnings</td><td class="alert-warning">{}</td></tr>
            <tr><td>Info</td><td class="alert-info">{}</td></tr>
        </table>
    </div>

</body>
</html>""".format(
            alerts.get('total_count', 0),
            alerts.get('critical_count', 0),
            alerts.get('warning_count', 0),
            alerts.get('info_count', 0),
        )

        return html

    def _format_text(self, summary: dict[str, Any]) -> str:
        """Format summary as plain text."""
        trip = summary["trip"]
        distance = summary["distance"]
        depth = summary["depth"]
        modes = summary["fishing_modes"]
        alerts = summary["alerts"]
        catch = summary["catch"]
        fuel = summary["fuel"]

        text = f"""
TRIP SUMMARY - {self.vessel_id}
{'=' * 60}

TRIP OVERVIEW
-------------
Start Time:    {trip.get('start_iso', 'N/A')}
End Time:      {trip.get('end_iso', 'N/A')}
Duration:      {trip.get('duration_h', 0):.2f} hours ({trip.get('duration_s', 0):.0f} seconds)

DISTANCE TRAVELED
-----------------
Total:         {distance.get('total_distance_nm', 0):.2f} nautical miles
               {distance.get('total_distance_km', 0):.2f} km
Position Fixes: {distance.get('position_count', 0)}

DEPTH STATISTICS
----------------
Minimum:       {depth.get('min_m', 'N/A')} m
Maximum:       {depth.get('max_m', 'N/A')} m
Average:       {depth.get('avg_m', 'N/A')} m
Readings:      {depth.get('reading_count', 0)}

FISHING MODES
-------------
"""

        for mode, duration_h in modes.get('mode_durations_h', {}).items():
            pct = modes.get('mode_durations_pct', {}).get(mode, 0)
            entries = modes.get('mode_entries', {}).get(mode, 0)
            text += f"{mode:15s} {duration_h:8.2f}h ({pct:5.1f}%) - {entries} entries\n"

        text += f"""
ALERTS
------
Total:         {alerts.get('total_count', 0)}
Critical:      {alerts.get('critical_count', 0)}
Warning:       {alerts.get('warning_count', 0)}
Info:          {alerts.get('info_count', 0)}
Highest Priority: {alerts.get('highest_priority', 0):.2f}

"""

        if catch.get('haul_count', 0) > 0:
            text += f"""CATCH STATISTICS
----------------
Total Catch:   {catch.get('total_catch_kg', 0):.2f} kg
Hauls:         {catch.get('haul_count', 0)}
Best Haul:     {catch.get('best_haul_kg', 0):.2f} kg
Average Haul:  {catch.get('avg_haul_kg', 0):.2f} kg

Species:
"""
            for species, count in catch.get('species_counts', {}).items():
                text += f"  {species}: {count}\n"

        if fuel.get('engine_hours', 0) > 0:
            text += f"""FUEL CONSUMPTION
----------------
Total Fuel:    {fuel.get('total_fuel_l', 0):.2f} L
Engine Hours:  {fuel.get('engine_hours', 0):.2f} h
Avg Rate:      {fuel.get('avg_consumption_lh', 0):.2f} L/h
Max Rate:      {fuel.get('max_consumption_lh', 0):.2f} L/h

"""

        text += f"""
DATA QUALITY
------------
Telemetry Records: {summary['data_quality']['telemetry_records']}
Position Fixes:     {summary['data_quality']['position_fixes']}
Depth Readings:     {summary['data_quality']['depth_readings']}
Wind Readings:      {summary['data_quality']['wind_readings']}
Wave Readings:      {summary['data_quality']['wave_readings']}

{'=' * 60}
Generated by AELMA TripSummary
"""

        return text

    @property
    def has_data(self) -> bool:
        """Check if any data has been accumulated."""
        return self._has_data
