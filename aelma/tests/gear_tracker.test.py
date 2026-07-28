"""Tests for the AELMA gear tracking system (GearTracker).

Mirrors the CatchLog test structure adapted for gear deployment tracking.
Coverage:

  1. GearTracker — deploy_gear validation, serialization, seq monotonicity.
  2. GearTracker — retrieve_gear validation and end_time checks.
  3. GearTracker — get_active_gear / get_gear_history.
  4. GearTracker — JSONL storage, state resume across instances.
  5. FishingModeManager integration — auto GEAR_DEPLOYED / FISHING modes.
  6. Error handling — bad types/values, unknown ids, ops after close.

Run from the repo root: python -m pytest tests/gear_tracker.test.py -v
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# Make the repository root importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twin.gear_tracker import (  # noqa: E402
    EVENT_DEPLOY,
    EVENT_RETRIEVE,
    KIND_GEAR,
    VALID_GEAR_TYPES,
    GearTracker,
)

# Load the real FishingModeManager directly from its file, avoiding the
# build_kimi package __init__ side effects.
_FISHING_MODES_PATH = (
    Path(__file__).resolve().parents[1] / "build_kimi" / "twin" / "fishing_modes.py"
)
_spec = importlib.util.spec_from_file_location("fishing_modes", _FISHING_MODES_PATH)
_fishing_modes = importlib.util.module_from_spec(_spec)
sys.modules["fishing_modes"] = _fishing_modes  # needed by @dataclass introspection
_spec.loader.exec_module(_fishing_modes)
FishingMode = _fishing_modes.FishingMode
FishingModeManager = _fishing_modes.FishingModeManager


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_gear_path(tmp_path: Path) -> Path:
    """Temporary path for gear tracker files."""
    return tmp_path / "gear_tracker.jsonl"


@pytest.fixture
def temp_tracker(temp_gear_path: Path) -> GearTracker:
    """Fresh GearTracker instance for each test."""
    return GearTracker(temp_gear_path)


@pytest.fixture
def mode_manager() -> FishingModeManager:
    """Fresh FishingModeManager (starts in TRANSIT)."""
    return FishingModeManager()


# =============================================================================
# GearTracker: deploy_gear
# =============================================================================

class TestDeployGear:
    """Test deploy_gear: validation, record shape, seq monotonicity."""

    @pytest.mark.asyncio
    async def test_deploy_returns_complete_record(self, temp_tracker: GearTracker) -> None:
        """deploy_gear returns the full record including augmented fields."""
        rec = await temp_tracker.deploy_gear("pots", 150.0, 40.0)
        assert rec["kind"] == KIND_GEAR
        assert rec["event"] == EVENT_DEPLOY
        assert rec["gear_type"] == "pots"
        assert rec["line_length"] == 150.0
        assert rec["depth"] == 40.0
        assert isinstance(rec["deployment_id"], str)
        assert rec["deployment_id"]
        assert isinstance(rec["start_time"], str)
        assert rec["end_time"] is None
        assert "_seq" in rec
        assert "_loggedAt" in rec
        assert rec["_seq"] == 0

    @pytest.mark.asyncio
    async def test_all_supported_gear_types(self, temp_tracker: GearTracker) -> None:
        """Every supported gear type deploys successfully."""
        assert VALID_GEAR_TYPES == {"troll_lines", "pots", "nets", "dredges"}
        for gear_type in sorted(VALID_GEAR_TYPES):
            rec = await temp_tracker.deploy_gear(gear_type, 100.0, 25.0)
            assert rec["gear_type"] == gear_type

    @pytest.mark.asyncio
    async def test_gear_type_normalized_to_lowercase(
        self, temp_tracker: GearTracker
    ) -> None:
        """Gear type input is case-insensitive and stored lowercase."""
        rec = await temp_tracker.deploy_gear("  Troll_Lines ", 100.0, 10.0)
        assert rec["gear_type"] == "troll_lines"

    @pytest.mark.asyncio
    async def test_seq_monotonic(self, temp_tracker: GearTracker) -> None:
        """_seq increments across deploy and retrieve records."""
        r0 = await temp_tracker.deploy_gear("pots", 100.0, 20.0)
        r1 = await temp_tracker.deploy_gear("nets", 200.0, 30.0)
        r2 = await temp_tracker.retrieve_gear(r0["deployment_id"])
        assert (r0["_seq"], r1["_seq"], r2["_seq"]) == (0, 1, 2)

    @pytest.mark.asyncio
    async def test_explicit_deployment_id(self, temp_tracker: GearTracker) -> None:
        """Caller-provided deployment_id is used and stripped."""
        rec = await temp_tracker.deploy_gear(
            "dredges", 50.0, 15.0, deployment_id=" dredge-1 "
        )
        assert rec["deployment_id"] == "dredge-1"

    @pytest.mark.asyncio
    async def test_duplicate_deployment_id_rejected(
        self, temp_tracker: GearTracker
    ) -> None:
        """Reusing a deployment_id raises ValueError, even after retrieval."""
        rec = await temp_tracker.deploy_gear("pots", 100.0, 20.0, deployment_id="p1")
        await temp_tracker.retrieve_gear(rec["deployment_id"])
        with pytest.raises(ValueError, match="already used"):
            await temp_tracker.deploy_gear("pots", 100.0, 20.0, deployment_id="p1")

    @pytest.mark.asyncio
    async def test_explicit_timestamps(self, temp_tracker: GearTracker) -> None:
        """start_time and end_time honor explicit ts values."""
        rec = await temp_tracker.deploy_gear(
            "nets", 300.0, 50.0, ts="2026-07-28T08:00:00+00:00"
        )
        assert rec["start_time"] == "2026-07-28T08:00:00+00:00"
        assert rec["start_time"].endswith("+00:00")

    @pytest.mark.asyncio
    async def test_epoch_timestamp_accepted(self, temp_tracker: GearTracker) -> None:
        """Epoch-seconds ts is coerced to an ISO string."""
        rec = await temp_tracker.deploy_gear("pots", 100.0, 20.0, ts=1_800_000_000)
        assert "T" in rec["start_time"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_type", ["", "   ", "longline", "trawl", "POT"])
    async def test_invalid_gear_type_rejected(
        self, temp_tracker: GearTracker, bad_type: str
    ) -> None:
        """Unknown or empty gear types raise ValueError."""
        with pytest.raises(ValueError, match="gear_type"):
            await temp_tracker.deploy_gear(bad_type, 100.0, 20.0)

    @pytest.mark.asyncio
    async def test_non_string_gear_type_rejected(self, temp_tracker: GearTracker) -> None:
        """Non-string gear_type raises ValueError."""
        with pytest.raises(ValueError, match="gear_type"):
            await temp_tracker.deploy_gear(42, 100.0, 20.0)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_length", [0, -1, -0.5])
    async def test_non_positive_line_length_rejected(
        self, temp_tracker: GearTracker, bad_length: float
    ) -> None:
        """Zero or negative line_length raises ValueError."""
        with pytest.raises(ValueError, match="line_length"):
            await temp_tracker.deploy_gear("pots", bad_length, 20.0)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_length", ["100", None, True])
    async def test_non_numeric_line_length_rejected(
        self, temp_tracker: GearTracker, bad_length: object
    ) -> None:
        """Non-numeric line_length raises TypeError."""
        with pytest.raises(TypeError, match="line_length"):
            await temp_tracker.deploy_gear("pots", bad_length, 20.0)

    @pytest.mark.asyncio
    async def test_negative_depth_rejected(self, temp_tracker: GearTracker) -> None:
        """Negative depth raises ValueError; zero depth is allowed."""
        with pytest.raises(ValueError, match="depth"):
            await temp_tracker.deploy_gear("pots", 100.0, -5.0)
        rec = await temp_tracker.deploy_gear("pots", 100.0, 0)
        assert rec["depth"] == 0.0

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_depth", ["40", None, False])
    async def test_non_numeric_depth_rejected(
        self, temp_tracker: GearTracker, bad_depth: object
    ) -> None:
        """Non-numeric depth raises TypeError."""
        with pytest.raises(TypeError, match="depth"):
            await temp_tracker.deploy_gear("pots", 100.0, bad_depth)

    @pytest.mark.asyncio
    async def test_creates_parent_dirs_on_append(self, temp_gear_path: Path) -> None:
        """Tracker creates parent directory on first append."""
        nested = temp_gear_path.parent / "nested" / "gear.jsonl"
        tracker = GearTracker(nested)
        await tracker.deploy_gear("pots", 100.0, 20.0)
        assert nested.exists()


# =============================================================================
# GearTracker: retrieve_gear
# =============================================================================

class TestRetrieveGear:
    """Test retrieve_gear: validation and record shape."""

    @pytest.mark.asyncio
    async def test_retrieve_returns_record(self, temp_tracker: GearTracker) -> None:
        """retrieve_gear returns a retrieve-event record with end_time."""
        deploy = await temp_tracker.deploy_gear("pots", 100.0, 20.0)
        rec = await temp_tracker.retrieve_gear(deploy["deployment_id"])
        assert rec["kind"] == KIND_GEAR
        assert rec["event"] == EVENT_RETRIEVE
        assert rec["deployment_id"] == deploy["deployment_id"]
        assert isinstance(rec["end_time"], str)
        assert rec["_seq"] == 1

    @pytest.mark.asyncio
    async def test_retrieve_unknown_id_rejected(self, temp_tracker: GearTracker) -> None:
        """Retrieving an unknown deployment raises ValueError."""
        with pytest.raises(ValueError, match="unknown deployment"):
            await temp_tracker.retrieve_gear("no-such-id")

    @pytest.mark.asyncio
    async def test_double_retrieve_rejected(self, temp_tracker: GearTracker) -> None:
        """Retrieving the same deployment twice raises ValueError."""
        deploy = await temp_tracker.deploy_gear("nets", 100.0, 20.0)
        await temp_tracker.retrieve_gear(deploy["deployment_id"])
        with pytest.raises(ValueError, match="already retrieved"):
            await temp_tracker.retrieve_gear(deploy["deployment_id"])

    @pytest.mark.asyncio
    async def test_retrieve_blank_id_rejected(self, temp_tracker: GearTracker) -> None:
        """Blank deployment_id raises ValueError."""
        with pytest.raises(ValueError, match="deployment_id"):
            await temp_tracker.retrieve_gear("   ")

    @pytest.mark.asyncio
    async def test_end_time_before_start_rejected(
        self, temp_tracker: GearTracker
    ) -> None:
        """end_time earlier than start_time raises ValueError."""
        deploy = await temp_tracker.deploy_gear(
            "pots", 100.0, 20.0, ts="2026-07-28T10:00:00+00:00"
        )
        with pytest.raises(ValueError, match="precedes"):
            await temp_tracker.retrieve_gear(
                deploy["deployment_id"], ts="2026-07-28T09:00:00+00:00"
            )
        # Deployment is still active after the failed retrieve.
        assert len(temp_tracker.get_active_gear()) == 1


# =============================================================================
# GearTracker: get_active_gear / get_gear_history
# =============================================================================

class TestQueries:
    """Test active-gear and history queries."""

    @pytest.mark.asyncio
    async def test_active_gear_tracks_deployments(
        self, temp_tracker: GearTracker
    ) -> None:
        """Active gear lists deployed-not-retrieved gear only."""
        d1 = await temp_tracker.deploy_gear("pots", 100.0, 20.0)
        d2 = await temp_tracker.deploy_gear("troll_lines", 250.0, 15.0)
        d3 = await temp_tracker.deploy_gear("nets", 300.0, 45.0)
        await temp_tracker.retrieve_gear(d2["deployment_id"])

        active = temp_tracker.get_active_gear()
        ids = {g["deployment_id"] for g in active}
        assert ids == {d1["deployment_id"], d3["deployment_id"]}
        assert all(g["end_time"] is None for g in active)
        assert {g["gear_type"] for g in active} == {"pots", "nets"}

    @pytest.mark.asyncio
    async def test_active_gear_returns_copies(self, temp_tracker: GearTracker) -> None:
        """Mutating returned dicts does not corrupt tracker state."""
        deploy = await temp_tracker.deploy_gear("pots", 100.0, 20.0)
        active = temp_tracker.get_active_gear()
        active[0]["gear_type"] = "corrupted"
        assert (
            temp_tracker.get_active_gear()[0]["gear_type"]
            == deploy["gear_type"]
        )

    @pytest.mark.asyncio
    async def test_empty_active_gear(self, temp_tracker: GearTracker) -> None:
        """No deployments means empty active list."""
        assert temp_tracker.get_active_gear() == []

    @pytest.mark.asyncio
    async def test_history_completed_only(self, temp_tracker: GearTracker) -> None:
        """History contains only retrieved deployments, with duration."""
        d1 = await temp_tracker.deploy_gear(
            "pots", 100.0, 20.0, ts="2026-07-28T06:00:00+00:00"
        )
        await temp_tracker.deploy_gear("nets", 200.0, 30.0)  # stays active
        await temp_tracker.retrieve_gear(
            d1["deployment_id"], ts="2026-07-28T10:30:00+00:00"
        )

        history = temp_tracker.get_gear_history()
        assert len(history) == 1
        entry = history[0]
        assert entry["deployment_id"] == d1["deployment_id"]
        assert entry["gear_type"] == "pots"
        assert entry["line_length"] == 100.0
        assert entry["depth"] == 20.0
        assert entry["start_time"] == "2026-07-28T06:00:00+00:00"
        assert entry["end_time"] == "2026-07-28T10:30:00+00:00"
        assert entry["duration_s"] == pytest.approx(4.5 * 3600)

    @pytest.mark.asyncio
    async def test_history_sorted_by_start_time(
        self, temp_tracker: GearTracker
    ) -> None:
        """History is ordered by start_time regardless of event order."""
        d1 = await temp_tracker.deploy_gear(
            "pots", 100.0, 20.0, ts="2026-07-28T06:00:00+00:00"
        )
        d2 = await temp_tracker.deploy_gear(
            "nets", 200.0, 30.0, ts="2026-07-28T04:00:00+00:00"
        )
        await temp_tracker.retrieve_gear(
            d1["deployment_id"], ts="2026-07-28T08:00:00+00:00"
        )
        await temp_tracker.retrieve_gear(
            d2["deployment_id"], ts="2026-07-28T09:00:00+00:00"
        )
        history = temp_tracker.get_gear_history()
        assert [h["deployment_id"] for h in history] == [
            d2["deployment_id"],
            d1["deployment_id"],
        ]

    @pytest.mark.asyncio
    async def test_empty_history(self, temp_tracker: GearTracker) -> None:
        """No completed deployments means empty history."""
        await temp_tracker.deploy_gear("pots", 100.0, 20.0)
        assert temp_tracker.get_gear_history() == []


# =============================================================================
# GearTracker: persistence
# =============================================================================

class TestPersistence:
    """Test JSONL storage and state resume across instances."""

    @pytest.mark.asyncio
    async def test_records_written_as_jsonl(
        self, temp_tracker: GearTracker, temp_gear_path: Path
    ) -> None:
        """Each event is one JSON object per line on disk."""
        deploy = await temp_tracker.deploy_gear("dredges", 80.0, 12.0)
        await temp_tracker.retrieve_gear(deploy["deployment_id"])

        lines = temp_gear_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        rec0, rec1 = (json.loads(line) for line in lines)
        assert rec0["event"] == EVENT_DEPLOY
        assert rec0["gear_type"] == "dredges"
        assert rec1["event"] == EVENT_RETRIEVE
        assert rec1["deployment_id"] == rec0["deployment_id"]

    @pytest.mark.asyncio
    async def test_state_resumes_across_instances(
        self, temp_gear_path: Path
    ) -> None:
        """A new instance rebuilds active gear and continues _seq."""
        tracker = GearTracker(temp_gear_path)
        d1 = await tracker.deploy_gear("pots", 100.0, 20.0)
        d2 = await tracker.deploy_gear("nets", 200.0, 30.0)
        await tracker.retrieve_gear(d1["deployment_id"])

        resumed = GearTracker(temp_gear_path)
        active = resumed.get_active_gear()
        assert [g["deployment_id"] for g in active] == [d2["deployment_id"]]
        assert resumed.seq == 3
        assert len(resumed.get_gear_history()) == 1

        # Retrieval of the still-active gear works on the resumed instance.
        rec = await resumed.retrieve_gear(d2["deployment_id"])
        assert rec["_seq"] == 3
        # And its id cannot be reused.
        with pytest.raises(ValueError, match="already used"):
            await resumed.deploy_gear(
                "pots", 100.0, 20.0, deployment_id=d1["deployment_id"]
            )

    @pytest.mark.asyncio
    async def test_malformed_lines_skipped(self, temp_gear_path: Path) -> None:
        """Malformed JSON lines are skipped with a warning, not fatal."""
        temp_gear_path.write_text(
            '{"kind": "gear_deployment", "event": "deploy",'
            ' "deployment_id": "x1", "gear_type": "pots"}\n'
            "not json at all\n"
            '{"kind": "other_thing"}\n',
            encoding="utf-8",
        )
        tracker = GearTracker(temp_gear_path)
        assert len(tracker.get_active_gear()) == 1
        assert tracker.seq == 3


# =============================================================================
# FishingModeManager integration
# =============================================================================

class TestModeManagerIntegration:
    """Test auto mode sync with a real FishingModeManager."""

    @pytest.mark.asyncio
    async def test_deploy_sets_gear_deployed_mode(
        self, temp_gear_path: Path, mode_manager: FishingModeManager
    ) -> None:
        """deploy_gear auto-sets GEAR_DEPLOYED mode with a reason."""
        tracker = GearTracker(temp_gear_path, mode_manager=mode_manager)
        assert mode_manager.get_mode()["current_mode"] == "TRANSIT"
        await tracker.deploy_gear("pots", 100.0, 20.0, deployment_id="p1")
        mode = mode_manager.get_mode()
        assert mode["current_mode"] == "GEAR_DEPLOYED"
        assert "pots" in mode["reason"]
        assert "p1" in mode["reason"]

    @pytest.mark.asyncio
    async def test_retrieve_last_gear_returns_to_fishing(
        self, temp_gear_path: Path, mode_manager: FishingModeManager
    ) -> None:
        """Retrieving the final active gear sets FISHING mode."""
        tracker = GearTracker(temp_gear_path, mode_manager=mode_manager)
        d = await tracker.deploy_gear("nets", 200.0, 30.0)
        await tracker.retrieve_gear(d["deployment_id"])
        assert mode_manager.get_mode()["current_mode"] == "FISHING"

    @pytest.mark.asyncio
    async def test_mode_stays_while_gear_active(
        self, temp_gear_path: Path, mode_manager: FishingModeManager
    ) -> None:
        """Partial retrieval leaves the vessel in GEAR_DEPLOYED."""
        tracker = GearTracker(temp_gear_path, mode_manager=mode_manager)
        d1 = await tracker.deploy_gear("pots", 100.0, 20.0)
        await tracker.deploy_gear("pots", 120.0, 25.0)
        await tracker.retrieve_gear(d1["deployment_id"])
        assert mode_manager.get_mode()["current_mode"] == "GEAR_DEPLOYED"

    @pytest.mark.asyncio
    async def test_works_without_mode_manager(self, temp_tracker: GearTracker) -> None:
        """Tracker works fine with no mode manager attached."""
        deploy = await temp_tracker.deploy_gear("pots", 100.0, 20.0)
        await temp_tracker.retrieve_gear(deploy["deployment_id"])
        assert temp_tracker.get_active_gear() == []
        assert len(temp_tracker.get_gear_history()) == 1

    @pytest.mark.asyncio
    async def test_mode_sync_failure_does_not_break_logging(
        self, temp_gear_path: Path
    ) -> None:
        """A failing mode manager is logged, not raised."""

        class BrokenManager:
            def set_mode(self, mode: str, reason: str = "") -> None:
                raise RuntimeError("mode manager exploded")

        tracker = GearTracker(temp_gear_path, mode_manager=BrokenManager())
        deploy = await tracker.deploy_gear("pots", 100.0, 20.0)
        rec = await tracker.retrieve_gear(deploy["deployment_id"])
        assert rec["event"] == EVENT_RETRIEVE
        assert temp_gear_path.exists()


# =============================================================================
# Lifecycle and stats
# =============================================================================

class TestLifecycle:
    """Test close() semantics and stats."""

    @pytest.mark.asyncio
    async def test_ops_after_close_raise(self, temp_tracker: GearTracker) -> None:
        """deploy/retrieve after close raise RuntimeError."""
        deploy = await temp_tracker.deploy_gear("pots", 100.0, 20.0)
        await temp_tracker.close()
        assert temp_tracker.closed
        with pytest.raises(RuntimeError, match="after close"):
            await temp_tracker.deploy_gear("nets", 100.0, 20.0)
        with pytest.raises(RuntimeError, match="after close"):
            await temp_tracker.retrieve_gear(deploy["deployment_id"])

    @pytest.mark.asyncio
    async def test_context_manager(self, temp_gear_path: Path) -> None:
        """Async context manager closes the tracker on exit."""
        async with GearTracker(temp_gear_path) as tracker:
            await tracker.deploy_gear("pots", 100.0, 20.0)
            assert not tracker.closed
        assert tracker.closed

    @pytest.mark.asyncio
    async def test_stats(self, temp_gear_path: Path) -> None:
        """stats reports path, records, active count, and attachments."""
        manager = FishingModeManager()
        tracker = GearTracker(temp_gear_path, mode_manager=manager)
        deploy = await tracker.deploy_gear("pots", 100.0, 20.0)
        await tracker.retrieve_gear(deploy["deployment_id"])
        await tracker.deploy_gear("nets", 200.0, 30.0)
        stats = await tracker.stats()
        assert stats["path"] == str(temp_gear_path)
        assert stats["records"] == 3
        assert stats["active_deployments"] == 1
        assert stats["closed"] is False
        assert stats["mode_manager_attached"] is True
        assert stats["size_bytes"] > 0
