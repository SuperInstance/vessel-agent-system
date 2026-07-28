"""Tests for the fishing mode manager."""

import time

import pytest

from build_kimi.twin.fishing_modes import (
    FishingMode,
    FishingModeManager,
    ModeStatistics,
    ModeTransition,
)


class TestFishingMode:
    """Tests for FishingMode enum."""

    def test_all_modes_defined(self):
        """Verify all expected fishing modes are defined."""
        expected_modes = {
            "TRANSIT",
            "FISHING",
            "DRIFTING",
            "ANCHORED",
            "GEAR_DEPLOYED",
            "HAULING",
            "MAINTENANCE",
        }
        actual_modes = {mode.value for mode in FishingMode}
        assert actual_modes == expected_modes

    def test_mode_from_string(self):
        """Test creating FishingMode from string."""
        assert FishingMode("FISHING") == FishingMode.FISHING
        assert FishingMode("TRANSIT") == FishingMode.TRANSIT

    def test_mode_from_invalid_string(self):
        """Test that invalid strings raise ValueError."""
        with pytest.raises(ValueError):
            FishingMode("INVALID_MODE")


class TestModeTransition:
    """Tests for ModeTransition dataclass."""

    def test_transition_creation(self):
        """Test creating a mode transition."""
        transition = ModeTransition(
            timestamp_ns=1234567890000000000,
            from_mode=None,
            to_mode=FishingMode.FISHING,
            reason="Starting fishing operation",
        )
        assert transition.timestamp_ns == 1234567890000000000
        assert transition.from_mode is None
        assert transition.to_mode == FishingMode.FISHING
        assert transition.reason == "Starting fishing operation"

    def test_transition_to_dict(self):
        """Test converting transition to dictionary."""
        transition = ModeTransition(
            timestamp_ns=1234567890000000000,
            from_mode=FishingMode.TRANSIT,
            to_mode=FishingMode.FISHING,
            reason="Arrived at fishing grounds",
        )
        data = transition.to_dict()
        assert data["timestamp_ns"] == 1234567890000000000
        assert data["from_mode"] == "TRANSIT"
        assert data["to_mode"] == "FISHING"
        assert data["reason"] == "Arrived at fishing grounds"


class TestModeStatistics:
    """Tests for ModeStatistics dataclass."""

    def test_statistics_creation(self):
        """Test creating mode statistics."""
        stats = ModeStatistics(
            mode=FishingMode.FISHING,
            total_duration_ns=3600000000000,  # 1 hour
            entry_count=5,
            last_entry_ns=1234567890000000000,
            last_exit_ns=1234571490000000000,
        )
        assert stats.mode == FishingMode.FISHING
        assert stats.total_duration_ns == 3600000000000
        assert stats.entry_count == 5
        assert stats.last_entry_ns == 1234567890000000000
        assert stats.last_exit_ns == 1234571490000000000

    def test_statistics_to_dict(self):
        """Test converting statistics to dictionary."""
        stats = ModeStatistics(
            mode=FishingMode.TRANSIT,
            total_duration_ns=7200000000000,  # 2 hours
            entry_count=3,
        )
        data = stats.to_dict()
        assert data["mode"] == "TRANSIT"
        assert data["total_duration_ns"] == 7200000000000
        assert data["entry_count"] == 3
        assert data["last_entry_ns"] is None
        assert data["last_exit_ns"] is None


class TestFishingModeManager:
    """Tests for FishingModeManager."""

    def test_initial_mode(self):
        """Test manager initialization with default mode."""
        manager = FishingModeManager()
        assert manager._current_mode == FishingMode.TRANSIT
        assert len(manager._history) == 0

    def test_initial_mode_custom(self):
        """Test manager initialization with custom mode."""
        manager = FishingModeManager(initial_mode=FishingMode.FISHING)
        assert manager._current_mode == FishingMode.FISHING

    def test_set_mode_enum(self):
        """Test setting mode with enum."""
        manager = FishingModeManager()
        manager.set_mode(FishingMode.FISHING, "Arrived at grounds")
        assert manager._current_mode == FishingMode.FISHING
        assert len(manager._history) == 1

    def test_set_mode_string(self):
        """Test setting mode with string."""
        manager = FishingModeManager()
        manager.set_mode("FISHING", "Arrived at grounds")
        assert manager._current_mode == FishingMode.FISHING

    def test_set_mode_invalid_string(self):
        """Test that invalid mode string raises ValueError."""
        manager = FishingModeManager()
        with pytest.raises(ValueError, match="Invalid fishing mode"):
            manager.set_mode("INVALID_MODE")

    def test_set_mode_invalid_type(self):
        """Test that invalid type raises TypeError."""
        manager = FishingModeManager()
        with pytest.raises(TypeError):
            manager.set_mode(123)  # type: ignore

    def test_set_same_mode_no_change(self):
        """Test that setting same mode doesn't create transition."""
        manager = FishingModeManager(initial_mode=FishingMode.TRANSIT)
        manager.set_mode(FishingMode.TRANSIT, "No change")
        assert len(manager._history) == 0

    def test_get_mode(self):
        """Test getting current mode information."""
        manager = FishingModeManager(initial_mode=FishingMode.TRANSIT)
        time.sleep(0.1)  # Small delay
        mode_info = manager.get_mode()

        assert mode_info["current_mode"] == "TRANSIT"
        assert mode_info["duration_s"] > 0.09  # At least 100ms
        assert mode_info["duration_ns"] > 90000000
        assert "reason" in mode_info

    def test_get_mode_after_change(self):
        """Test getting mode information after change."""
        manager = FishingModeManager()
        manager.set_mode(FishingMode.FISHING, "Starting to fish")
        mode_info = manager.get_mode()

        assert mode_info["current_mode"] == "FISHING"
        assert mode_info["reason"] == "Starting to fish"
        assert mode_info["duration_s"] < 1.0  # Just changed

    def test_mode_sequence(self):
        """Test sequence of mode changes."""
        manager = FishingModeManager()

        manager.set_mode(FishingMode.FISHING, "Arrived")
        assert manager._current_mode == FishingMode.FISHING

        manager.set_mode(FishingMode.GEAR_DEPLOYED, "Gear in water")
        assert manager._current_mode == FishingMode.GEAR_DEPLOYED

        manager.set_mode(FishingMode.HAULING, "Hauling gear")
        assert manager._current_mode == FishingMode.HAULING

        manager.set_mode(FishingMode.TRANSIT, "Heading home")
        assert manager._current_mode == FishingMode.TRANSIT

        assert len(manager._history) == 4

    def test_get_mode_history_all(self):
        """Test getting full mode history."""
        manager = FishingModeManager()

        manager.set_mode(FishingMode.FISHING, "Start fishing")
        manager.set_mode(FishingMode.DRIFTING, "Drifting")
        manager.set_mode(FishingMode.HAULING, "Hauling")

        history = manager.get_mode_history()
        assert len(history) == 3

        # Most recent first
        assert history[0]["to_mode"] == "HAULING"
        assert history[1]["to_mode"] == "DRIFTING"
        assert history[2]["to_mode"] == "FISHING"

    def test_get_mode_history_limited(self):
        """Test getting limited mode history."""
        manager = FishingModeManager()

        manager.set_mode(FishingMode.FISHING, "Start")
        manager.set_mode(FishingMode.DRIFTING, "Drift")
        manager.set_mode(FishingMode.HAULING, "Haul")
        manager.set_mode(FishingMode.TRANSIT, "Home")

        history = manager.get_mode_history(limit=2)
        assert len(history) == 2
        assert history[0]["to_mode"] == "TRANSIT"
        assert history[1]["to_mode"] == "HAULING"

    def test_get_statistics(self):
        """Test getting aggregate statistics."""
        manager = FishingModeManager()

        stats = manager.get_statistics()
        assert "modes" in stats
        assert "total_transitions" in stats
        assert "current_mode_info" in stats

        # Check all modes are present
        for mode in FishingMode:
            assert mode.value in stats["modes"]

    def test_get_time_in_mode(self):
        """Test getting statistics for specific mode."""
        manager = FishingModeManager()
        manager.set_mode(FishingMode.FISHING, "Fishing")

        transit_stats = manager.get_time_in_mode(FishingMode.TRANSIT)
        assert transit_stats["mode"] == "TRANSIT"
        assert transit_stats["entry_count"] == 1
        assert transit_stats["total_duration_ns"] > 0

    def test_get_time_in_mode_string(self):
        """Test getting time in mode using string."""
        manager = FishingModeManager()
        stats = manager.get_time_in_mode("TRANSIT")
        assert stats["mode"] == "TRANSIT"

    def test_get_time_in_mode_invalid_string(self):
        """Test that invalid mode string raises ValueError."""
        manager = FishingModeManager()
        with pytest.raises(ValueError):
            manager.get_time_in_mode("INVALID")

    def test_should_apply_mode_rules_true(self):
        """Test mode rule check when mode matches."""
        manager = FishingModeManager(initial_mode=FishingMode.FISHING)
        assert manager.should_apply_mode_rules(FishingMode.FISHING)
        assert manager.should_apply_mode_rules("FISHING")

    def test_should_apply_mode_rules_false(self):
        """Test mode rule check when mode doesn't match."""
        manager = FishingModeManager(initial_mode=FishingMode.TRANSIT)
        assert not manager.should_apply_mode_rules(FishingMode.FISHING)
        assert not manager.should_apply_mode_rules("FISHING")

    def test_statistics_accumulate_duration(self):
        """Test that statistics accumulate time correctly."""
        manager = FishingModeManager()

        # Start in TRANSIT
        start_stats = manager.get_time_in_mode(FishingMode.TRANSIT)
        assert start_stats["entry_count"] == 1

        time.sleep(0.1)

        # Switch to FISHING
        manager.set_mode(FishingMode.FISHING, "Switch")

        # Check TRANSIT stats
        transit_stats = manager.get_time_in_mode(FishingMode.TRANSIT)
        assert transit_stats["entry_count"] == 1
        assert transit_stats["total_duration_ns"] > 100000000  # > 100ms

        # Check FISHING stats
        fishing_stats = manager.get_time_in_mode(FishingMode.FISHING)
        assert fishing_stats["entry_count"] == 1
        assert fishing_stats["total_duration_ns"] == 0  # Haven't left yet

    def test_statistics_multiple_entries(self):
        """Test that statistics track multiple entries to same mode."""
        manager = FishingModeManager()

        # TRANSIT -> FISHING -> TRANSIT -> FISHING
        manager.set_mode(FishingMode.FISHING, "Fish 1")
        manager.set_mode(FishingMode.TRANSIT, "Transit 1")
        manager.set_mode(FishingMode.FISHING, "Fish 2")

        transit_stats = manager.get_time_in_mode(FishingMode.TRANSIT)
        assert transit_stats["entry_count"] == 2  # Initial + return

        fishing_stats = manager.get_time_in_mode(FishingMode.FISHING)
        assert fishing_stats["entry_count"] == 2

    def test_get_context_for_watchers(self):
        """Test getting context for watcher evaluation."""
        manager = FishingModeManager()
        manager.set_mode(FishingMode.FISHING, "Fishing")

        context = manager.get_context_for_watchers()
        assert context["fishing_mode"] == "FISHING"
        assert context["fishing_mode_duration_ns"] > 0
        assert context["fishing_mode_duration_s"] > 0
        assert context["fishing_mode_transitions"] == 1

    def test_current_duration_in_stats(self):
        """Test that current duration is included for active mode."""
        manager = FishingModeManager()
        time.sleep(0.1)

        stats = manager.get_time_in_mode(FishingMode.TRANSIT)
        assert "current_duration_ns" in stats
        assert "current_duration_s" in stats
        assert stats["current_duration_s"] > 0.09

    def test_no_current_duration_for_inactive_mode(self):
        """Test that inactive modes don't have current duration."""
        manager = FishingModeManager()
        manager.set_mode(FishingMode.FISHING, "Switch")

        stats = manager.get_time_in_mode(FishingMode.TRANSIT)
        assert "current_duration_ns" not in stats
        assert "current_duration_s" not in stats


class TestFishingModeIntegration:
    """Integration tests for fishing mode system with TwinCore."""

    def test_twincore_has_fishing_mode_manager(self):
        """Test that TwinCore has fishing mode manager."""
        from build_kimi.twin.core import TwinCore

        core = TwinCore(enable_watchers=False)
        assert hasattr(core, "fishing_modes")
        assert isinstance(core.fishing_modes, FishingModeManager)

    def test_twincore_set_fishing_mode(self):
        """Test setting fishing mode via TwinCore."""
        from build_kimi.twin.core import TwinCore

        core = TwinCore(enable_watchers=False)
        core.set_fishing_mode(FishingMode.FISHING, "Test fishing")

        mode = core.get_fishing_mode()
        assert mode["current_mode"] == "FISHING"
        assert mode["reason"] == "Test fishing"

    def test_twincore_get_fishing_mode_history(self):
        """Test getting fishing mode history via TwinCore."""
        from build_kimi.twin.core import TwinCore

        core = TwinCore(enable_watchers=False)
        core.set_fishing_mode(FishingMode.FISHING, "Fish")
        core.set_fishing_mode(FishingMode.TRANSIT, "Home")

        history = core.get_fishing_mode_history()
        assert len(history) == 2

    def test_twincore_get_fishing_mode_statistics(self):
        """Test getting fishing mode statistics via TwinCore."""
        from build_kimi.twin.core import TwinCore

        core = TwinCore(enable_watchers=False)
        stats = core.get_fishing_mode_statistics()

        assert "modes" in stats
        assert "total_transitions" in stats
        assert "current_mode_info" in stats

    def test_twincore_snapshot_includes_fishing_mode(self):
        """Test that snapshot includes fishing mode."""
        from build_kimi.twin.core import TwinCore

        core = TwinCore(enable_watchers=False)
        core.set_fishing_mode(FishingMode.FISHING, "Fishing")

        snapshot = core.build_snapshot()
        assert "fishing_mode" in snapshot
        assert snapshot["fishing_mode"]["current_mode"] == "FISHING"

    def test_watcher_frame_includes_fishing_mode(self):
        """Test that watcher frame includes fishing mode context."""
        from build_kimi.twin.core import TwinCore

        core = TwinCore(enable_watchers=False)
        core.set_fishing_mode(FishingMode.FISHING, "Fishing")

        # Access internal _build_frame for testing
        frame = core._build_frame()
        assert "fishing_mode" in frame
        assert frame["fishing_mode"] == "FISHING"
        assert "fishing_mode_duration_s" in frame
        assert "fishing_mode_duration_ns" in frame
        assert "fishing_mode_transitions" in frame


class TestModeSpecificWatchers:
    """Tests for mode-specific watcher rule helpers."""

    def test_transit_speed_check(self):
        """Test transit speed watcher condition."""
        from build_kimi.twin.fishing_modes import transit_speed_exceeds

        frame = {"fishing_mode": "TRANSIT", "speed_kn": 20.0}
        assert transit_speed_exceeds(frame, max_kn=15.0)

        frame = {"fishing_mode": "TRANSIT", "speed_kn": 10.0}
        assert not transit_speed_exceeds(frame, max_kn=15.0)

        frame = {"fishing_mode": "FISHING", "speed_kn": 20.0}
        assert not transit_speed_exceeds(frame, max_kn=15.0)

    def test_fishing_depth_check(self):
        """Test fishing depth watcher condition."""
        from build_kimi.twin.fishing_modes import fishing_depth_critical

        frame = {"fishing_mode": "FISHING", "depth_m": 3.0}
        assert fishing_depth_critical(frame, min_depth_m=5.0)

        frame = {"fishing_mode": "FISHING", "depth_m": 10.0}
        assert not fishing_depth_critical(frame, min_depth_m=5.0)

        frame = {"fishing_mode": "TRANSIT", "depth_m": 3.0}
        assert not fishing_depth_critical(frame, min_depth_m=5.0)

    def test_drifting_rate_check(self):
        """Test drift rate watcher condition."""
        from build_kimi.twin.fishing_modes import drifting_rate_excessive

        frame = {"fishing_mode": "DRIFTING", "speed_kn": 3.0}
        assert drifting_rate_excessive(frame, max_drift_kn=2.0)

        frame = {"fishing_mode": "DRIFTING", "speed_kn": 1.0}
        assert not drifting_rate_excessive(frame, max_drift_kn=2.0)

    def test_anchor_drag_check(self):
        """Test anchor drag watcher condition."""
        from build_kimi.twin.fishing_modes import anchor_drag_detected

        frame = {"fishing_mode": "ANCHORED", "speed_kn": 1.0}
        assert anchor_drag_detected(frame, drag_threshold_m=50.0)

        frame = {"fishing_mode": "ANCHORED", "speed_kn": 0.2}
        assert not anchor_drag_detected(frame, drag_threshold_m=50.0)

    def test_gear_deployed_duration_check(self):
        """Test gear deployed duration watcher condition."""
        from build_kimi.twin.fishing_modes import gear_deployed_too_long

        frame = {"fishing_mode": "GEAR_DEPLOYED", "fishing_mode_duration_s": 50000}
        assert gear_deployed_too_long(frame, max_hours=12.0)

        frame = {"fishing_mode": "GEAR_DEPLOYED", "fishing_mode_duration_s": 20000}
        assert not gear_deployed_too_long(frame, max_hours=12.0)

    def test_hauling_slow_progress_check(self):
        """Test hauling slow progress watcher condition."""
        from build_kimi.twin.fishing_modes import hauling_slow_progress

        frame = {
            "fishing_mode": "HAULING",
            "speed_kn": 0.5,
            "gear_tension": 75,
        }
        assert hauling_slow_progress(frame, min_haul_speed_kn=1.0)

        frame = {
            "fishing_mode": "HAULING",
            "speed_kn": 1.5,
            "gear_tension": 75,
        }
        assert not hauling_slow_progress(frame, min_haul_speed_kn=1.0)

        frame = {
            "fishing_mode": "HAULING",
            "speed_kn": 0.5,
            "gear_tension": 25,
        }
        assert not hauling_slow_progress(frame, min_haul_speed_kn=1.0)
