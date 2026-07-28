"""Fishing mode manager for AELMA twin.

Tracks vessel operational states (TRANSIT, FISHING, DRIFTING, ANCHORED, etc.)
with time-in-mode tracking, statistics, and mode-specific watcher rules.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("aelma.fishing_modes")


class FishingMode(Enum):
    """Vessel operational modes."""

    TRANSIT = "TRANSIT"
    FISHING = "FISHING"
    DRIFTING = "DRIFTING"
    ANCHORED = "ANCHORED"
    GEAR_DEPLOYED = "GEAR_DEPLOYED"
    HAULING = "HAULING"
    MAINTENANCE = "MAINTENANCE"


@dataclass
class ModeTransition:
    """Record of a mode change."""

    timestamp_ns: int
    from_mode: FishingMode | None
    to_mode: FishingMode
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp_ns": self.timestamp_ns,
            "from_mode": self.from_mode.value if self.from_mode else None,
            "to_mode": self.to_mode.value,
            "reason": self.reason,
        }


@dataclass
class ModeStatistics:
    """Statistics for time spent in a particular mode."""

    mode: FishingMode
    total_duration_ns: int = 0
    entry_count: int = 0
    last_entry_ns: int | None = None
    last_exit_ns: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "mode": self.mode.value,
            "total_duration_ns": self.total_duration_ns,
            "entry_count": self.entry_count,
            "last_entry_ns": self.last_entry_ns,
            "last_exit_ns": self.last_exit_ns,
        }


class FishingModeManager:
    """Manages vessel operational modes with history and statistics.

    Tracks mode changes, maintains history, and provides mode-specific
    context for watcher rules.
    """

    def __init__(self, initial_mode: FishingMode = FishingMode.TRANSIT) -> None:
        """Initialize the mode manager.

        Args:
            initial_mode: Starting operational mode.
        """
        self._current_mode = initial_mode
        self._mode_since_ns = time.time_ns()
        self._history: list[ModeTransition] = []
        self._statistics: dict[FishingMode, ModeStatistics] = {
            mode: ModeStatistics(mode=mode)
            for mode in FishingMode
        }

        # Record initial mode entry
        self._statistics[initial_mode].entry_count = 1
        self._statistics[initial_mode].last_entry_ns = self._mode_since_ns

        log.info("FishingModeManager initialized with mode: %s", initial_mode.value)

    def set_mode(self, mode: FishingMode | str, reason: str = "") -> None:
        """Change the current operational mode.

        Args:
            mode: New mode (FishingMode enum or string value).
            reason: Human-readable explanation for the mode change.
        """
        # Normalize mode to enum
        if isinstance(mode, str):
            try:
                mode = FishingMode(mode)
            except ValueError:
                raise ValueError(f"Invalid fishing mode: {mode!r}")

        if not isinstance(mode, FishingMode):
            raise TypeError(f"mode must be FishingMode or str, got {type(mode)}")

        # Skip if no change
        if mode == self._current_mode:
            log.debug("Mode unchanged: %s", mode.value)
            return

        now_ns = time.time_ns()
        duration_ns = now_ns - self._mode_since_ns

        # Update statistics for exiting mode
        self._statistics[self._current_mode].total_duration_ns += duration_ns
        self._statistics[self._current_mode].last_exit_ns = now_ns

        # Record transition
        transition = ModeTransition(
            timestamp_ns=now_ns,
            from_mode=self._current_mode,
            to_mode=mode,
            reason=reason or f"Transition from {self._current_mode.value} to {mode.value}",
        )
        self._history.append(transition)

        # Update statistics for entering mode
        self._statistics[mode].entry_count += 1
        self._statistics[mode].last_entry_ns = now_ns

        # Update current mode
        old_mode = self._current_mode
        self._current_mode = mode
        self._mode_since_ns = now_ns

        log.info(
            "Mode change: %s -> %s (reason: %s, duration in previous: %.2fs)",
            old_mode.value,
            mode.value,
            reason,
            duration_ns / 1e9,
        )

    def get_mode(self) -> dict[str, Any]:
        """Get current mode and duration information.

        Returns:
            Dict with current mode, time since mode change, and reason.
        """
        now_ns = time.time_ns()
        duration_ns = now_ns - self._mode_since_ns

        # Get the reason for entering current mode
        reason = ""
        for transition in reversed(self._history):
            if transition.to_mode == self._current_mode:
                reason = transition.reason
                break

        return {
            "current_mode": self._current_mode.value,
            "since_ns": self._mode_since_ns,
            "duration_ns": duration_ns,
            "duration_s": duration_ns / 1e9,
            "reason": reason,
        }

    def get_mode_history(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Get the full mode change history.

        Args:
            limit: Maximum number of transitions to return (most recent first).
                   If None, returns all history.

        Returns:
            List of mode transition records, most recent first.
        """
        history = [t.to_dict() for t in self._history]
        if limit is not None:
            history = history[-limit:]
        return list(reversed(history))

    def get_statistics(self) -> dict[str, Any]:
        """Get aggregate statistics for all modes.

        Returns:
            Dict with per-mode statistics and summary information.
        """
        stats = {
            "modes": {mode.value: stat.to_dict() for mode, stat in self._statistics.items()},
            "total_transitions": len(self._history),
            "current_mode_info": self.get_mode(),
        }
        return stats

    def get_time_in_mode(self, mode: FishingMode | str) -> dict[str, Any]:
        """Get detailed statistics for a specific mode.

        Args:
            mode: The mode to query (FishingMode enum or string value).

        Returns:
            Dict with mode statistics.
        """
        if isinstance(mode, str):
            try:
                mode = FishingMode(mode)
            except ValueError:
                raise ValueError(f"Invalid fishing mode: {mode!r}")

        if mode not in self._statistics:
            raise KeyError(f"No statistics for mode: {mode.value}")

        stat = self._statistics[mode]
        result = stat.to_dict()

        # Add current duration if this is the active mode
        if mode == self._current_mode:
            now_ns = time.time_ns()
            current_duration_ns = now_ns - self._mode_since_ns
            result["current_duration_ns"] = current_duration_ns
            result["current_duration_s"] = current_duration_ns / 1e9

        return result

    def should_apply_mode_rules(self, mode: FishingMode | str) -> bool:
        """Check if mode-specific rules should be applied.

        Args:
            mode: The mode to check (FishingMode enum or string value).

        Returns:
            True if the vessel is currently in the specified mode.
        """
        if isinstance(mode, str):
            try:
                mode = FishingMode(mode)
            except ValueError:
                return False

        return self._current_mode == mode

    def get_context_for_watchers(self) -> dict[str, Any]:
        """Get mode context for watcher rule evaluation.

        Returns a dict that can be merged into the watcher frame
        to provide mode-aware context.
        """
        now_ns = time.time_ns()
        duration_ns = now_ns - self._mode_since_ns

        return {
            "fishing_mode": self._current_mode.value,
            "fishing_mode_duration_ns": duration_ns,
            "fishing_mode_duration_s": duration_ns / 1e9,
            "fishing_mode_transitions": len(self._history),
        }


# --------------------------------------------------------------------- #
# Mode-specific watcher rule helpers
# --------------------------------------------------------------------- #

def transit_speed_exceeds(frame: dict[str, Any], max_kn: float = 15.0) -> bool:
    """Check if vessel speed exceeds transit mode threshold."""
    return (
        FishingModeManager._check_mode(frame, "TRANSIT")
        and frame.get("speed_kn", 0) > max_kn
    )


def transit_course_deviation(frame: dict[str, Any], max_deviation_deg: float = 15.0) -> bool:
    """Check if vessel deviates from expected course during transit.

    This is a placeholder - in practice, you'd compare current heading
    to an expected waypoint course.
    """
    return (
        FishingModeManager._check_mode(frame, "TRANSIT")
        and bool(frame.get("heading_deg"))
    )


def fishing_depth_critical(frame: dict[str, Any], min_depth_m: float = 5.0) -> bool:
    """Check if fishing depth is too shallow."""
    return (
        FishingModeManager._check_mode(frame, "FISHING")
        and 0 < frame.get("depth_m", 999) < min_depth_m
    )


def fishing_gear_failure(frame: dict[str, Any]) -> bool:
    """Check for fishing gear status indicators."""
    return (
        FishingModeManager._check_mode(frame, "FISHING")
        and frame.get("gear_status") == "FAILURE"
    )


def drifting_rate_excessive(frame: dict[str, Any], max_drift_kn: float = 2.0) -> bool:
    """Check if drift rate exceeds safe threshold."""
    return (
        FishingModeManager._check_mode(frame, "DRIFTING")
        and frame.get("speed_kn", 0) > max_drift_kn
    )


def drifting_position_warning(frame: dict[str, Any], max_drift_m: float = 500.0) -> bool:
    """Check if vessel has drifted too far from origin.

    This is a placeholder - in practice, you'd track drift origin
    and compute distance from it.
    """
    return (
        FishingModeManager._check_mode(frame, "DRIFTING")
        and bool(frame.get("lat", frame.get("lon")))
    )


def anchor_drag_detected(frame: dict[str, Any], drag_threshold_m: float = 50.0) -> bool:
    """Check if anchor is dragging.

    This is a placeholder - in practice, you'd track anchor set position
    and compute distance from it.
    """
    return (
        FishingModeManager._check_mode(frame, "ANCHORED")
        and frame.get("speed_kn", 0) > 0.5
    )


def gear_deployed_too_long(frame: dict[str, Any], max_hours: float = 12.0) -> bool:
    """Check if gear has been deployed too long."""
    return (
        FishingModeManager._check_mode(frame, "GEAR_DEPLOYED")
        and frame.get("fishing_mode_duration_s", 0) > (max_hours * 3600)
    )


def hauling_slow_progress(frame: dict[str, Any], min_haul_speed_kn: float = 1.0) -> bool:
    """Check if haul progress is too slow."""
    return (
        FishingModeManager._check_mode(frame, "HAULING")
        and frame.get("speed_kn", 0) < min_haul_speed_kn
        and frame.get("gear_tension", 0) > 50
    )


@staticmethod
def _check_mode(frame: dict[str, Any], mode: str) -> bool:
    """Helper to check if frame matches a fishing mode."""
    return frame.get("fishing_mode") == mode


# Add static method to FishingModeManager
FishingModeManager._check_mode = _check_mode
