"""Tests for the AELMA crew scheduling system (CrewScheduler).

Mirrors the CatchLog/OpLog test structure adapted for crew scheduling.
Coverage:

  1. add_crew_member — validation, roles, duplicates, persistence.
  2. assign_watch — validation, watch records, closing prior watches.
  3. get_on_watch_crew — active watch lookup at a point in time.
  4. check_fatigue — windowed watch-hour totals and fatigue flags.
  5. rotate_watch — rotation order, fatigue skipping, exhaustion.
  6. OpLog integration — crew_note entries linked via watch_id metadata.
  7. JSON storage — state resume across instances, atomic rewrite.

Run from the repo root: python -m pytest tests/crew_schedule.test.py -v
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio

# Make the repository root importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twin.crew_schedule import (  # noqa: E402
    KIND_SCHEDULE,
    VALID_ROLES,
    CrewScheduler,
)
from twin.oplog import OpLog  # noqa: E402

T0 = datetime(2026, 7, 28, 8, 0, 0, tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_sched_path(tmp_path: Path) -> Path:
    """Temporary path for crew schedule state files."""
    return tmp_path / "crew_schedule.json"


@pytest.fixture
def scheduler(temp_sched_path: Path) -> CrewScheduler:
    """Fresh CrewScheduler instance for each test."""
    return CrewScheduler(temp_sched_path)


@pytest_asyncio.fixture
async def crewed(scheduler: CrewScheduler) -> CrewScheduler:
    """Scheduler with one member per role."""
    await scheduler.add_crew_member("alice", "captain")
    await scheduler.add_crew_member("bob", "engineer")
    await scheduler.add_crew_member("carol", "deckhand")
    await scheduler.add_crew_member("dave", "cook")
    return scheduler


# =============================================================================
# Crew roster
# =============================================================================

class TestAddCrewMember:
    """add_crew_member: validation, roles, duplicates."""

    @pytest.mark.asyncio
    async def test_add_returns_record(self, scheduler: CrewScheduler) -> None:
        rec = await scheduler.add_crew_member("alice", "captain", max_watch_hours=8)
        assert rec["name"] == "alice"
        assert rec["role"] == "captain"
        assert rec["max_watch_hours"] == 8.0
        assert "added_at" in rec

    @pytest.mark.asyncio
    async def test_all_roles_accepted(self, scheduler: CrewScheduler) -> None:
        assert VALID_ROLES == {"captain", "engineer", "deckhand", "cook"}
        for i, role in enumerate(sorted(VALID_ROLES)):
            rec = await scheduler.add_crew_member(f"member{i}", role)
            assert rec["role"] == role

    @pytest.mark.asyncio
    async def test_rejects_bad_role(self, scheduler: CrewScheduler) -> None:
        with pytest.raises(ValueError, match="role"):
            await scheduler.add_crew_member("alice", "pilot")

    @pytest.mark.asyncio
    async def test_rejects_empty_name(self, scheduler: CrewScheduler) -> None:
        with pytest.raises(ValueError, match="name"):
            await scheduler.add_crew_member("  ", "captain")

    @pytest.mark.asyncio
    async def test_rejects_duplicate(self, scheduler: CrewScheduler) -> None:
        await scheduler.add_crew_member("alice", "captain")
        with pytest.raises(ValueError, match="duplicate"):
            await scheduler.add_crew_member("alice", "cook")

    @pytest.mark.asyncio
    async def test_rejects_bad_max_watch_hours(self, scheduler: CrewScheduler) -> None:
        with pytest.raises(ValueError, match="positive"):
            await scheduler.add_crew_member("alice", "captain", max_watch_hours=0)
        with pytest.raises(TypeError):
            await scheduler.add_crew_member("alice", "captain", max_watch_hours="6")

    @pytest.mark.asyncio
    async def test_list_crew_sorted(self, crewed: CrewScheduler) -> None:
        names = [m["name"] for m in crewed.list_crew()]
        assert names == ["alice", "bob", "carol", "dave"]

    @pytest.mark.asyncio
    async def test_remove_crew_member(self, crewed: CrewScheduler) -> None:
        removed = await crewed.remove_crew_member("dave")
        assert removed["role"] == "cook"
        assert [m["name"] for m in crewed.list_crew()] == ["alice", "bob", "carol"]

    @pytest.mark.asyncio
    async def test_remove_unknown_or_on_watch(self, crewed: CrewScheduler) -> None:
        with pytest.raises(ValueError, match="unknown"):
            await crewed.remove_crew_member("nobody")
        await crewed.assign_watch("nav", "alice", start=T0)
        with pytest.raises(ValueError, match="on watch"):
            await crewed.remove_crew_member("alice")


# =============================================================================
# Watch assignment
# =============================================================================

class TestAssignWatch:
    """assign_watch: validation, records, prior-watch closure."""

    @pytest.mark.asyncio
    async def test_assign_returns_watch_record(self, crewed: CrewScheduler) -> None:
        watch = await crewed.assign_watch(
            "nav", "alice", start=T0, duration_hours=4,
        )
        assert watch["watch_id"] == 1
        assert watch["name"] == "nav"
        assert watch["crew"] == ["alice"]
        assert watch["start"] == _iso(T0)
        assert watch["end"] == _iso(T0 + timedelta(hours=4))

    @pytest.mark.asyncio
    async def test_assign_multiple_crew(self, crewed: CrewScheduler) -> None:
        watch = await crewed.assign_watch(
            "deck", ["carol", "dave"], start=T0, end=_iso(T0 + timedelta(hours=6)),
        )
        assert watch["crew"] == ["carol", "dave"]

    @pytest.mark.asyncio
    async def test_ongoing_watch_has_no_end(self, crewed: CrewScheduler) -> None:
        watch = await crewed.assign_watch("nav", "alice", start=T0)
        assert watch["end"] is None

    @pytest.mark.asyncio
    async def test_new_watch_closes_previous(self, crewed: CrewScheduler) -> None:
        first = await crewed.assign_watch("nav", "alice", start=T0)
        second = await crewed.assign_watch("nav", "bob", start=T0 + timedelta(hours=4))
        assert second["watch_id"] == 2
        watches = crewed.list_watches(name="nav")
        assert watches[0]["end"] == second["start"]
        assert watches[1]["end"] is None
        assert watches[0]["watch_id"] == first["watch_id"]

    @pytest.mark.asyncio
    async def test_rejects_unknown_crew(self, crewed: CrewScheduler) -> None:
        with pytest.raises(ValueError, match="unknown crew"):
            await crewed.assign_watch("nav", ["alice", "ghost"], start=T0)

    @pytest.mark.asyncio
    async def test_rejects_bad_times(self, crewed: CrewScheduler) -> None:
        with pytest.raises(ValueError, match="after start"):
            await crewed.assign_watch(
                "nav", "alice", start=T0, end=_iso(T0 - timedelta(hours=1))
            )
        with pytest.raises(ValueError, match="not both"):
            await crewed.assign_watch(
                "nav", "alice", start=T0,
                end=_iso(T0 + timedelta(hours=4)), duration_hours=4,
            )
        with pytest.raises(ValueError, match="duration"):
            await crewed.assign_watch("nav", "alice", start=T0, duration_hours=-1)
        with pytest.raises(ValueError, match="unparseable"):
            await crewed.assign_watch("nav", "alice", start="not-a-time")


# =============================================================================
# On-watch lookup
# =============================================================================

class TestGetOnWatchCrew:
    """get_on_watch_crew: point-in-time active watch lookup."""

    @pytest.mark.asyncio
    async def test_returns_crew_during_watch(self, crewed: CrewScheduler) -> None:
        await crewed.assign_watch("nav", "alice", start=T0, duration_hours=4)
        mid = T0 + timedelta(hours=2)
        on_watch = crewed.get_on_watch_crew(mid)
        assert len(on_watch) == 1
        assert on_watch[0]["name"] == "alice"
        assert on_watch[0]["role"] == "captain"
        assert on_watch[0]["watch_name"] == "nav"
        assert on_watch[0]["watch_id"] == 1

    @pytest.mark.asyncio
    async def test_empty_outside_watch(self, crewed: CrewScheduler) -> None:
        await crewed.assign_watch("nav", "alice", start=T0, duration_hours=4)
        assert crewed.get_on_watch_crew(T0 - timedelta(hours=1)) == []
        assert crewed.get_on_watch_crew(T0 + timedelta(hours=5)) == []

    @pytest.mark.asyncio
    async def test_multiple_watches(self, crewed: CrewScheduler) -> None:
        await crewed.assign_watch("nav", "alice", start=T0, duration_hours=4)
        await crewed.assign_watch("engine", ["bob", "carol"], start=T0, duration_hours=4)
        names = [m["name"] for m in crewed.get_on_watch_crew(T0 + timedelta(hours=1))]
        assert names == ["alice", "bob", "carol"]

    @pytest.mark.asyncio
    async def test_ongoing_watch_is_active(self, crewed: CrewScheduler) -> None:
        await crewed.assign_watch("nav", "alice", start=T0)
        on_watch = crewed.get_on_watch_crew(T0 + timedelta(hours=100))
        assert [m["name"] for m in on_watch] == ["alice"]


# =============================================================================
# Fatigue
# =============================================================================

class TestCheckFatigue:
    """check_fatigue: windowed watch hours and fatigue flags."""

    @pytest.mark.asyncio
    async def test_fresh_crew_not_fatigued(self, crewed: CrewScheduler) -> None:
        result = crewed.check_fatigue(ts=T0)
        assert set(result) == {"alice", "bob", "carol", "dave"}
        for entry in result.values():
            assert entry["hours_on_watch"] == 0.0
            assert entry["fatigued"] is False

    @pytest.mark.asyncio
    async def test_hours_accumulate_within_window(self, crewed: CrewScheduler) -> None:
        await crewed.assign_watch("nav", "alice", start=T0, duration_hours=4)
        await crewed.assign_watch("nav", "alice", start=T0 + timedelta(hours=6),
                                  duration_hours=3)
        result = crewed.check_fatigue("alice", ts=T0 + timedelta(hours=12))
        assert result["alice"]["hours_on_watch"] == 7.0
        assert result["alice"]["fatigued"] is True  # 7 > default 6

    @pytest.mark.asyncio
    async def test_old_watches_fall_out_of_window(self, crewed: CrewScheduler) -> None:
        await crewed.assign_watch("nav", "alice", start=T0, duration_hours=5)
        later = T0 + timedelta(hours=48)
        result = crewed.check_fatigue("alice", ts=later)
        assert result["alice"]["hours_on_watch"] == 0.0
        assert result["alice"]["fatigued"] is False

    @pytest.mark.asyncio
    async def test_respects_custom_limit(self, scheduler: CrewScheduler) -> None:
        await scheduler.add_crew_member("alice", "captain", max_watch_hours=10)
        await scheduler.assign_watch("nav", "alice", start=T0, duration_hours=8)
        result = scheduler.check_fatigue("alice", ts=T0 + timedelta(hours=12))
        assert result["alice"]["max_watch_hours"] == 10.0
        assert result["alice"]["fatigued"] is False

    @pytest.mark.asyncio
    async def test_ongoing_watch_counts_until_now(self, crewed: CrewScheduler) -> None:
        await crewed.assign_watch("nav", "alice", start=T0)
        result = crewed.check_fatigue("alice", ts=T0 + timedelta(hours=5))
        assert result["alice"]["hours_on_watch"] == 5.0

    @pytest.mark.asyncio
    async def test_rejects_unknown_member(self, crewed: CrewScheduler) -> None:
        with pytest.raises(ValueError, match="unknown"):
            crewed.check_fatigue("ghost", ts=T0)


# =============================================================================
# Rotation
# =============================================================================

class TestRotateWatch:
    """rotate_watch: rotation order, fatigue skipping, exhaustion."""

    @pytest.mark.asyncio
    async def test_rotation_cycles_roster(self, crewed: CrewScheduler) -> None:
        assigned = []
        for i in range(5):
            watch = await crewed.rotate_watch("nav", ts=T0 + timedelta(hours=i * 4))
            assigned.append(watch["crew"][0])
        # Wraps around in roster order.
        assert assigned == ["alice", "bob", "carol", "dave", "alice"]

    @pytest.mark.asyncio
    async def test_rotation_closes_previous_watch(self, crewed: CrewScheduler) -> None:
        await crewed.rotate_watch("nav", ts=T0)
        await crewed.rotate_watch("nav", ts=T0 + timedelta(hours=4))
        watches = crewed.list_watches(name="nav")
        assert len(watches) == 2
        assert watches[0]["end"] == watches[1]["start"]

    @pytest.mark.asyncio
    async def test_rotation_skips_fatigued(self, crewed: CrewScheduler) -> None:
        # Bob racks up 7 hours on another watch: over the default 6h limit.
        await crewed.assign_watch("engine", "bob", start=T0 - timedelta(hours=7),
                                  duration_hours=7)
        watch = await crewed.rotate_watch("nav", ts=T0)
        assert watch["crew"] == ["alice"]
        watch = await crewed.rotate_watch("nav", ts=T0 + timedelta(hours=4))
        assert watch["crew"][0] == "carol"  # bob skipped

    @pytest.mark.asyncio
    async def test_rotation_exhausted_raises(self, scheduler: CrewScheduler) -> None:
        with pytest.raises(ValueError, match="roster is empty"):
            await scheduler.rotate_watch("nav", ts=T0)

    @pytest.mark.asyncio
    async def test_all_fatigued_raises(self, scheduler: CrewScheduler) -> None:
        await scheduler.add_crew_member("alice", "captain", max_watch_hours=1)
        await scheduler.assign_watch("nav", "alice", start=T0 - timedelta(hours=2),
                                     duration_hours=2)
        with pytest.raises(ValueError, match="fatigued"):
            await scheduler.rotate_watch("nav", ts=T0)


# =============================================================================
# OpLog integration
# =============================================================================

class TestOpLogIntegration:
    """Crew actions mirrored into OpLog, linked via watch_id metadata."""

    @pytest.mark.asyncio
    async def test_assign_watch_logged(self, temp_sched_path: Path, tmp_path: Path) -> None:
        oplog = OpLog(tmp_path / "oplog.jsonl")
        sched = CrewScheduler(temp_sched_path, oplog=oplog)
        await sched.add_crew_member("alice", "captain")
        watch = await sched.assign_watch("nav", "alice", start=T0, duration_hours=4)

        entries = await oplog.query(entry_type="crew_note")
        assert len(entries) == 1
        entry = entries[0]
        assert entry["crew"] == "alice"
        assert entry["metadata"]["action"] == "watch_assigned"
        assert entry["metadata"]["watch_id"] == watch["watch_id"]
        assert entry["metadata"]["watch_name"] == "nav"

    @pytest.mark.asyncio
    async def test_rotate_logged_with_watch_link(
        self, temp_sched_path: Path, tmp_path: Path
    ) -> None:
        oplog = OpLog(tmp_path / "oplog.jsonl")
        sched = CrewScheduler(temp_sched_path, oplog=oplog)
        await sched.add_crew_member("alice", "captain")
        await sched.add_crew_member("bob", "engineer")
        first = await sched.rotate_watch("nav", ts=T0)
        second = await sched.rotate_watch("nav", ts=T0 + timedelta(hours=4))

        entries = await oplog.query(entry_type="crew_note")
        # Each rotate logs watch_assigned + watch_rotated.
        assert len(entries) == 4
        actions = [e["metadata"]["action"] for e in entries]
        assert actions.count("watch_assigned") == 2
        assert actions.count("watch_rotated") == 2
        rotated = [e for e in entries if e["metadata"]["action"] == "watch_rotated"]
        assert {e["metadata"]["watch_id"] for e in rotated} == {
            first["watch_id"], second["watch_id"],
        }

    @pytest.mark.asyncio
    async def test_no_oplog_no_error(self, crewed: CrewScheduler) -> None:
        # Scheduler without OpLog works standalone.
        watch = await crewed.assign_watch("nav", "alice", start=T0)
        assert watch["watch_id"] == 1


# =============================================================================
# JSON storage
# =============================================================================

class TestStorage:
    """JSON state persistence and resume across instances."""

    @pytest.mark.asyncio
    async def test_state_file_written(self, temp_sched_path: Path) -> None:
        sched = CrewScheduler(temp_sched_path)
        await sched.add_crew_member("alice", "captain")
        await sched.assign_watch("nav", "alice", start=T0, duration_hours=4)

        with temp_sched_path.open("r", encoding="utf-8") as fh:
            state = json.load(fh)
        assert state["kind"] == KIND_SCHEDULE
        assert "alice" in state["crew"]
        assert len(state["watches"]) == 1

    @pytest.mark.asyncio
    async def test_resume_across_instances(self, temp_sched_path: Path) -> None:
        sched = CrewScheduler(temp_sched_path)
        await sched.add_crew_member("alice", "captain")
        await sched.add_crew_member("bob", "engineer")
        first = await sched.assign_watch("nav", "alice", start=T0, duration_hours=4)
        await sched.rotate_watch("nav", ts=T0 + timedelta(hours=4))
        await sched.close()

        resumed = CrewScheduler(temp_sched_path)
        assert [m["name"] for m in resumed.list_crew()] == ["alice", "bob"]
        watches = resumed.list_watches(name="nav")
        assert len(watches) == 2
        assert watches[0]["watch_id"] == first["watch_id"]

        # Watch ids and rotation continue where the last instance left off.
        watch = await resumed.assign_watch("nav", "alice", start=T0 + timedelta(hours=8))
        assert watch["watch_id"] == 3
        rotated = await resumed.rotate_watch("nav", ts=T0 + timedelta(hours=12))
        assert rotated["crew"] == ["bob"]

    @pytest.mark.asyncio
    async def test_no_temp_file_left_behind(self, temp_sched_path: Path) -> None:
        sched = CrewScheduler(temp_sched_path)
        await sched.add_crew_member("alice", "captain")
        leftovers = list(temp_sched_path.parent.glob("*.tmp"))
        assert leftovers == []

    @pytest.mark.asyncio
    async def test_ignores_malformed_state(self, temp_sched_path: Path) -> None:
        temp_sched_path.write_text("{not json", encoding="utf-8")
        sched = CrewScheduler(temp_sched_path)  # starts empty, no crash
        assert sched.list_crew() == []

    @pytest.mark.asyncio
    async def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "nested" / "sched.json"
        sched = CrewScheduler(nested)
        await sched.add_crew_member("alice", "captain")
        assert nested.exists()


# =============================================================================
# Lifecycle
# =============================================================================

class TestLifecycle:
    """close() semantics and stats."""

    @pytest.mark.asyncio
    async def test_mutation_after_close_raises(self, crewed: CrewScheduler) -> None:
        await crewed.close()
        with pytest.raises(RuntimeError, match="close"):
            await crewed.add_crew_member("erin", "deckhand")
        with pytest.raises(RuntimeError, match="close"):
            await crewed.assign_watch("nav", "alice", start=T0)
        with pytest.raises(RuntimeError, match="close"):
            await crewed.rotate_watch("nav", ts=T0)

    @pytest.mark.asyncio
    async def test_stats(self, crewed: CrewScheduler) -> None:
        await crewed.assign_watch("nav", "alice", start=T0)
        stats = await crewed.stats()
        assert stats["crew"] == 4
        assert stats["watches"] == 1
        assert stats["on_watch"] == 1
        assert stats["closed"] is False

    @pytest.mark.asyncio
    async def test_context_manager(self, temp_sched_path: Path) -> None:
        async with CrewScheduler(temp_sched_path) as sched:
            await sched.add_crew_member("alice", "captain")
        with pytest.raises(RuntimeError):
            await sched.add_crew_member("bob", "cook")
