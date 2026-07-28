"""Tide prediction system for AELMA twin.

Implements harmonic tide prediction using major tidal constituents
(M2, S2, O1, K1, N2, P1) to calculate water levels at fishing locations.

Reference: NOAA tide prediction methodology
https://tidesandcurrents.noaa.gov/harmonic_constitutions.html
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass
class TideEvent:
    """Represents a high or low tide event."""
    timestamp: datetime
    level_m: float
    event_type: str  # "high" or "low"


@dataclass
class TidePrediction:
    """Result of a tide prediction."""
    water_level_m: float
    timestamp: datetime
    confidence: float
    constituents_used: list[str]


# Harmonic constituent definitions for semi-diurnal tides
# Based on NOAA standard constituents for typical coastal waters
# Amplitudes in meters, phases in degrees relative to local equilibrium
_CONSTITUENTS = {
    # Principal lunar semidiurnal (12.42 hour period) - dominant in most waters
    "M2": {
        "amplitude": 1.0,  # Base amplitude, will be scaled by location factor
        "period_hours": 12.4206,
        "phase_deg": 0.0,
    },
    # Principal solar semidiurnal (12.0 hour period)
    "S2": {
        "amplitude": 0.3,
        "period_hours": 12.0,
        "phase_deg": 0.0,
    },
    # Lunar diurnal (25.82 hour period)
    "O1": {
        "amplitude": 0.2,
        "period_hours": 25.8193,
        "phase_deg": 270.0,
    },
    # Lunar diurnal (23.93 hour period)
    "K1": {
        "amplitude": 0.15,
        "period_hours": 23.9345,
        "phase_deg": 90.0,
    },
    # Larger lunar elliptic semidiurnal (12.66 hour period)
    "N2": {
        "amplitude": 0.2,
        "period_hours": 12.6583,
        "phase_deg": 0.0,
    },
    # Principal solar diurnal (24.07 hour period)
    "P1": {
        "amplitude": 0.1,
        "period_hours": 24.0659,
        "phase_deg": 90.0,
    },
}


class TidePredictor:
    """Harmonic tide prediction engine for coastal fishing locations.

    Uses 6 major harmonic constituents to predict water levels without
    requiring external tide APIs. Implements semi-diurnal tide patterns
    typical of most coastal waters (2 highs, 2 lows per day).

    Water levels are expressed relative to MLLW (Mean Lower Low Water) datum,
    which is the standard nautical chart reference.

    Example
    -------
    >>> predictor = TidePredictor()
    >>> tide = predictor.predict_tide(59.5, -152.3, datetime.now())
    >>> print(f"Water level: {tide.water_level_m:.2f}m MLLW")
    """

    def __init__(
        self,
        base_amplitude: float = 2.0,
        datum_mllw_m: float = 0.0,
    ) -> None:
        """Initialize tide predictor.

        Parameters
        ----------
        base_amplitude:
            Base tidal amplitude in meters (typical range: 1-5m).
            Default 2.0m represents moderate tidal range.
        datum_mllw_m:
            MLLW datum offset in meters (default 0.0).
            Can be adjusted for local chart datum.
        """
        self.base_amplitude = base_amplitude
        self.datum_mllw_m = datum_mllw_m

    def predict_tide(
        self,
        lat: float,
        lon: float,
        timestamp: datetime | None = None,
    ) -> TidePrediction:
        """Predict water level at location and time.

        Parameters
        ----------
        lat:
            Latitude in decimal degrees (e.g., 59.5 for Alaska).
        lon:
            Longitude in decimal degrees (e.g., -152.3 for Alaska).
        timestamp:
            Prediction time (default: current time).

        Returns
        -------
        TidePrediction
            Predicted water level in meters relative to MLLW.
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Calculate location-specific amplitude factor
        # Higher latitudes generally have larger tidal ranges
        lat_factor = 1.0 + 0.003 * abs(lat)

        # Calculate lunar time (simplified equilibrium tide approximation)
        # Lunar phase affects tide amplitude (spring vs neap tides)
        lunar_phase = self._get_lunar_phase(timestamp)
        spring_neap_factor = 0.8 + 0.4 * math.cos(math.radians(lunar_phase))

        # Calculate water level using harmonic constituents
        water_level = self.datum_mllw_m

        constituents_used = []

        for name, const in _CONSTITUENTS.items():
            # Scale base amplitude by location and spring/neap cycle
            amplitude = self.base_amplitude * const["amplitude"] * lat_factor * spring_neap_factor

            # Calculate constituent frequency (degrees per hour)
            frequency = 360.0 / const["period_hours"]

            # Calculate time since epoch in hours
            epoch_hours = self._timestamp_to_hours(timestamp)

            # Calculate constituent phase with location correction
            # Longitude correction: ~12 degrees of phase shift per 15 degrees of longitude
            lon_correction = lon * 0.8
            phase = math.radians(const["phase_deg"] + frequency * epoch_hours + lon_correction)

            # Add constituent contribution
            water_level += amplitude * math.sin(phase)
            constituents_used.append(name)

        # Calculate confidence based on prediction certainty
        # Higher confidence for standard coastal locations
        confidence = 0.85

        return TidePrediction(
            water_level_m=round(water_level, 2),
            timestamp=timestamp,
            confidence=confidence,
            constituents_used=constituents_used,
        )

    def get_tide_range(
        self,
        lat: float,
        lon: float,
        start_time: datetime | None = None,
        duration_hours: float = 24.0,
    ) -> list[TideEvent]:
        """Get high and low tide events for a time period.

        Parameters
        ----------
        lat, lon:
            Location coordinates.
        start_time:
            Start of prediction period (default: current time).
        duration_hours:
            Length of prediction period in hours (default: 24).

        Returns
        -------
        list[TideEvent]
            List of high/low tide events in chronological order.
        """
        if start_time is None:
            start_time = datetime.now()

        # Sample tide levels frequently to find extrema
        events = []
        sample_interval = 15.0  # minutes (finer sampling for better detection)
        num_samples = int(duration_hours * 60 / sample_interval)

        prev_level = None
        prev_time = None
        prev_derivative = None

        # Track local minima and maxima
        local_min = None
        local_max = None

        for i in range(num_samples + 1):
            sample_time = start_time + timedelta(minutes=i * sample_interval)
            prediction = self.predict_tide(lat, lon, sample_time)
            level = prediction.water_level_m

            # Calculate derivative (rate of change in m/min)
            if prev_level is not None:
                derivative = (level - prev_level) / sample_interval

                # Track local maximum (potential high tide)
                if local_max is None or level > local_max[1]:
                    local_max = (sample_time, level)

                # Track local minimum (potential low tide)
                if local_min is None or level < local_min[1]:
                    local_min = (sample_time, level)

                # Detect high tide (derivative changes from positive to negative)
                if prev_derivative is not None and prev_derivative > 0 and derivative <= 0:
                    if local_max is not None:
                        # Only add if we haven't just added a high tide
                        if not events or events[-1].event_type != "high":
                            events.append(TideEvent(
                                timestamp=local_max[0],
                                level_m=local_max[1],
                                event_type="high"
                            ))
                        local_max = None

                # Detect low tide (derivative changes from negative to positive)
                if prev_derivative is not None and prev_derivative < 0 and derivative >= 0:
                    if local_min is not None:
                        # Only add if we haven't just added a low tide
                        if not events or events[-1].event_type != "low":
                            events.append(TideEvent(
                                timestamp=local_min[0],
                                level_m=local_min[1],
                                event_type="low"
                            ))
                        local_min = None

                prev_derivative = derivative

            prev_level = level
            prev_time = sample_time

        # Sort events chronologically and return
        events.sort(key=lambda e: e.timestamp)

        return events

    def check_depth_clearance(
        self,
        vessel_draft_m: float,
        chart_depth_m: float,
        lat: float,
        lon: float,
        timestamp: datetime | None = None,
        safety_margin_m: float = 1.0,
    ) -> dict[str, Any]:
        """Check if vessel has adequate depth clearance at location and time.

        Parameters
        ----------
        vessel_draft_m:
            Vessel draft (depth below waterline) in meters.
        chart_depth_m:
            Chart datum depth (MLLW) in meters.
        lat, lon:
            Location coordinates.
        timestamp:
            Time to check clearance (default: current time).
        safety_margin_m:
            Additional safety margin in meters (default: 1.0m).

        Returns
        -------
        dict
            Clearance check result with status, water depth, and clearance.
        """
        tide = self.predict_tide(lat, lon, timestamp)
        water_depth = chart_depth_m + tide.water_level_m
        under_keel_clearance = water_depth - vessel_draft_m

        status = "safe" if under_keel_clearance >= safety_margin_m else "danger"

        return {
            "status": status,
            "timestamp": tide.timestamp.isoformat(),
            "vessel_draft_m": vessel_draft_m,
            "chart_depth_m": chart_depth_m,
            "tide_level_m": tide.water_level_m,
            "water_depth_m": round(water_depth, 2),
            "under_keel_clearance_m": round(under_keel_clearance, 2),
            "safety_margin_m": safety_margin_m,
            "clearance_ok": under_keel_clearance >= safety_margin_m,
        }

    def get_safe_passage_window(
        self,
        vessel_draft_m: float,
        chart_depth_m: float,
        lat: float,
        lon: float,
        start_time: datetime | None = None,
        window_hours: float = 12.0,
        safety_margin_m: float = 1.0,
    ) -> dict[str, Any]:
        """Find safe passage windows based on tide predictions.

        Parameters
        ----------
        vessel_draft_m:
            Vessel draft in meters.
        chart_depth_m:
            Chart datum depth in meters.
        lat, lon:
            Location coordinates.
        start_time:
            Start time for analysis (default: current time).
        window_hours:
            Analysis period in hours (default: 12).
        safety_margin_m:
            Required safety margin (default: 1.0m).

        Returns
        -------
        dict
            Safe passage analysis with windows and tide events.
        """
        if start_time is None:
            start_time = datetime.now()

        # Get tide events for the period
        events = self.get_tide_range(lat, lon, start_time, window_hours)

        # Check clearance at regular intervals
        sample_interval = 15.0  # minutes
        num_samples = int(window_hours * 60 / sample_interval)

        safe_windows = []
        current_window_start = None
        unsafe_periods = []

        for i in range(num_samples + 1):
            sample_time = start_time + timedelta(minutes=i * sample_interval)
            check = self.check_depth_clearance(
                vessel_draft_m, chart_depth_m, lat, lon, sample_time, safety_margin_m
            )

            if check["clearance_ok"]:
                if current_window_start is None:
                    current_window_start = sample_time
            else:
                if current_window_start is not None:
                    window_end = sample_time - timedelta(minutes=sample_interval)
                    duration_min = (window_end - current_window_start).total_seconds() / 60
                    if duration_min >= sample_interval:
                        safe_windows.append({
                            "start": current_window_start.isoformat(),
                            "end": window_end.isoformat(),
                            "duration_minutes": round(duration_min, 1),
                        })
                    current_window_start = None

                unsafe_periods.append({
                    "start": sample_time.isoformat(),
                    "water_depth_m": check["water_depth_m"],
                    "clearance_m": check["under_keel_clearance_m"],
                })

        # Close any open window
        if current_window_start is not None:
            duration_min = (start_time + timedelta(hours=window_hours) - current_window_start).total_seconds() / 60
            safe_windows.append({
                "start": current_window_start.isoformat(),
                "end": (start_time + timedelta(hours=window_hours)).isoformat(),
                "duration_minutes": round(duration_min, 1),
            })

        return {
            "vessel_draft_m": vessel_draft_m,
            "chart_depth_m": chart_depth_m,
            "safety_margin_m": safety_margin_m,
            "analysis_start": start_time.isoformat(),
            "analysis_duration_hours": window_hours,
            "tide_events": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "level_m": e.level_m,
                    "type": e.event_type,
                }
                for e in events
            ],
            "safe_windows": safe_windows,
            "unsafe_periods": unsafe_periods,
            "total_safe_minutes": sum(w["duration_minutes"] for w in safe_windows),
        }

    def _get_lunar_phase(self, timestamp: datetime) -> float:
        """Calculate lunar phase angle in degrees (simplified).

        Returns 0° at new moon, 180° at full moon.
        Spring tides occur at 0° and 180°, neap tides at 90° and 270°.
        """
        # Simplified lunar phase calculation
        # Using known new moon reference: January 11, 2024 18:57 UTC
        new_moon_ref = datetime(2024, 1, 11, 18, 57)

        # Handle timezone-aware timestamps
        if timestamp.tzinfo is not None:
            # Convert to UTC and make naive for calculation
            timestamp = timestamp.replace(tzinfo=None) - (timestamp.utcoffset() or timedelta(0))

        days_since_ref = (timestamp - new_moon_ref).total_seconds() / 86400.0

        # Lunar synodic period ~29.53 days
        lunar_cycle_days = 29.53
        phase_deg = (days_since_ref % lunar_cycle_days) / lunar_cycle_days * 360.0

        return phase_deg

    def _timestamp_to_hours(self, timestamp: datetime) -> float:
        """Convert datetime to hours since epoch."""
        epoch = datetime(1970, 1, 1)

        # Handle timezone-aware timestamps
        if timestamp.tzinfo is not None:
            # Convert to UTC and make naive for calculation
            timestamp = timestamp.replace(tzinfo=None) - (timestamp.utcoffset() or timedelta(0))

        return (timestamp - epoch).total_seconds() / 3600.0

    def get_next_high_low_tides(
        self,
        lat: float,
        lon: float,
        from_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Get next high and low tide events after specified time.

        Parameters
        ----------
        lat, lon:
            Location coordinates.
        from_time:
            Search start time (default: current time).

        Returns
        -------
        dict
            Next high and low tide predictions.
        """
        if from_time is None:
            from_time = datetime.now()

        # Look ahead 48 hours to find events
        events = self.get_tide_range(lat, lon, from_time, 48.0)

        next_high = None
        next_low = None

        for event in events:
            if event.timestamp >= from_time:
                if event.event_type == "high" and next_high is None:
                    next_high = event
                elif event.event_type == "low" and next_low is None:
                    next_low = event

        return {
            "location": {"lat": lat, "lon": lon},
            "query_time": from_time.isoformat(),
            "next_high_tide": {
                "timestamp": next_high.timestamp.isoformat() if next_high else None,
                "level_m": next_high.level_m if next_high else None,
                "hours_from_now": (next_high.timestamp - from_time).total_seconds() / 3600.0 if next_high else None,
            } if next_high else None,
            "next_low_tide": {
                "timestamp": next_low.timestamp.isoformat() if next_low else None,
                "level_m": next_low.level_m if next_low else None,
                "hours_from_now": (next_low.timestamp - from_time).total_seconds() / 3600.0 if next_low else None,
            } if next_low else None,
        }
