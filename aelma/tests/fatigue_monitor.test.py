"""Tests for the AELMA crew fatigue monitoring system (FatigueMonitor).

Mirrors the CrewScheduler test structure adapted for fatigue tracking.
Coverage:

  1. log_watch_start / log_watch_end — validation, session records,
     double-start / missing-start errors, roster checks.
  2. get_metrics — hours_on_watch, hours_worked_last_24h, hours_rested,
     consecutive_shifts.
  3. get_fatigue_score — 0..1 range, rises with work, decays with rest.
  4. check_compliance — 10h max shift, 8h min rest, 24h weekly limit.
  5. CrewScheduler integration — roster validation, sync_from_scheduler
     idempotency.
  6. WatcherRegistry integration — crew-fatigue-risk rule fires on
     fatigue frames.
  7. JSON storage — state resume across instances, atomic rewrite.

Run from the repo root: python -m pytest tests/fatigue_monitor.test.py -v
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

from twin.crew_schedule import CrewScheduler  # noqa: E402
from twin.fatigue_monitor import (  # noqa: E402
    KIND_FATIGUE,
    MAX_SHIFT_HOURS,
    MIN_REST_HOURS,
    MAX_WEEKLY_HOURS,
    FatigueMonitor,
)
from twin.watcher_history import WatcherHistory  # noqa: E402
from twin.watchers import WatcherRegistry  # noqa: E402

T0 = datetime(2026, 7, 28, 8, 0, 0, tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_monitor_path(tmp_path: Path) -> Path:
    """Temporary path for fatigue monitor state files."""
    return tmp_path / "fatigue_monitor.json"


@pytest.fixture
def monitor(temp_monitor_path: Path) -> FatigueMonitor:
    """Fresh FatigueMonitor instance for each test."""
    return FatigueMonitor(temp_monitor_path)


@pytest_asyncio.fixture
async def scheduler(tmp_path: Path) -> CrewScheduler:
    """CrewScheduler with a small roster."""
    sched = CrewScheduler(tmp_path / "crew_schedule.json")
    await sched.add_crew_member("alice", "captain")
    await sched.add_crew_member("bob", "engineer")
    return sched


@pytest_asyncio.fixture
async def linked(temp_monitor_path: Path, scheduler: CrewScheduler) -> FatigueMonitor:
    """FatigueMonitor linked to the scheduler."""
    return FatigueMonitor(temp_monitor_path, scheduler=scheduler)


async def _shift(
    monitor: FatigueMonitor,
    crew_id: str,
    start: datetime,
    hours: float,
) -> None:
    """Log a completed shift of ``hours`` starting at ``start``."""
    await monitor.log_watch_start(crew_id, ts=start)
    await monitor.log_watch_end(crew_id, ts=start + timedelta(hours=hours))


# =============================================================================
# Watch logging
# =============================================================================

class TestWatchLogging:
    """log_watch_start / log_watch_end: validation and session records."""

    @pytest.mark.asyncio
    async def test_start_returns_session(self, monitor: FatigueMonitor) -> None:
        session = await monitor.log_watch_start("alice", ts=T0)
        assert session["start"] == _iso(T0)
        assert session["end"] is None

    @pytest.mark.asyncio
    async def test_end_closes_session(self, monitor: FatigueMonitor) -> None:
        await monitor.log_watch_start("alice", ts=T0)
        session = await monitor.log_watch_end("alice", ts=T0 + timedelta(hours=4))
        assert session["end"] == _iso(T0 + timedelta(hours=4))

    @pytest.mark.asyncio
    async def test_double_start_rejected(self, monitor: FatigueMonitor) -> None:
        await monitor.log_watch_start("alice", ts=T0)
        with pytest.raises(ValueError, match="already on watch"):
            await monitor.log_watch_start("alice", ts=T0 + timedelta(hours=1))

    @pytest.mark.asyncio
    async def test_end_without_start_rejected(self, monitor: FatigueMonitor) -> None:
        with pytest.raises(ValueError, match="not on watch"):
            await monitor.log_watch_end("alice", ts=T0)

    @pytest.mark.asyncio
    async def test_end_before_start_rejected(self, monitor: FatigueMonitor) -> None:
        await monitor.log_watch_start("alice", ts=T0)
        with pytest.raises(ValueError, match="after the watch start"):
            await monitor.log_watch_end("alice", ts=T0 - timedelta(hours=1))

    @pytest.mark.asyncio
    async def test_invalid_crew_id(self, monitor: FatigueMonitor) -> None:
        with pytest.raises(ValueError, match="non-empty string"):
            await monitor.log_watch_start("")
        with pytest.raises(ValueError, match="non-empty string"):
            await monitor.log_watch_end("   ")

    @pytest.mark.asyncio
    async def test_invalid_ts_type(self, monitor: FatigueMonitor) -> None:
        with pytest.raises(TypeError):
            await monitor.log_watch_start("alice", ts=object())

    @pytest.mark.asyncio
    async def test_restart_after_end(self, monitor: FatigueMonitor) -> None:
        await _shift(monitor, "alice", T0, 4)
        session = await monitor.log_watch_start("alice", ts=T0 + timedelta(hours=12))
        assert session["end"] is None


# =============================================================================
# Metrics
# =============================================================================

class TestMetrics:
    """get_metrics: the four tracked fatigue metrics."""

    @pytest.mark.asyncio
    async def test_unknown_crew_is_zeroed(self, monitor: FatigueMonitor) -> None:
        m = monitor.get_metrics("ghost", ts=T0)
        assert m["hours_on_watch"] == 0.0
        assert m["hours_worked_last_24h"] == 0.0
        assert m["hours_rested"] == 0.0
        assert m["consecutive_shifts"] == 0
        assert m["on_watch"] is False

    @pytest.mark.asyncio
    async def test_hours_on_watch(self, monitor: FatigueMonitor) -> None:
        await monitor.log_watch_start("alice", ts=T0)
        m = monitor.get_metrics("alice", ts=T0 + timedelta(hours=6))
        assert m["on_watch"] is True
        assert m["hours_on_watch"] == pytest.approx(6.0)
        assert m["hours_rested"] == 0.0

    @pytest.mark.asyncio
    async def test_hours_worked_last_24h(self, monitor: FatigueMonitor) -> None:
        await _shift(monitor, "alice", T0, 4)
        await _shift(monitor, "alice", T0 + timedelta(hours=12), 4)
        m = monitor.get_metrics("alice", ts=T0 + timedelta(hours=16))
        assert m["hours_worked_last_24h"] == pytest.approx(8.0)

    @pytest.mark.asyncio
    async def test_hours_worked_last_24h_window_slide(
        self, monitor: FatigueMonitor
    ) -> None:
        await _shift(monitor, "alice", T0, 4)
        # 30 hours later the shift is fully outside the trailing window.
        m = monitor.get_metrics("alice", ts=T0 + timedelta(hours=30))
        assert m["hours_worked_last_24h"] == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_hours_rested(self, monitor: FatigueMonitor) -> None:
        await _shift(monitor, "alice", T0, 4)
        m = monitor.get_metrics("alice", ts=T0 + timedelta(hours=14))
        assert m["hours_rested"] == pytest.approx(10.0)

    @pytest.mark.asyncio
    async def test_consecutive_shifts_short_gaps(
        self, monitor: FatigueMonitor
    ) -> None:
        # Three shifts with 4h rest gaps (< 8h min rest).
        await _shift(monitor, "alice", T0, 4)
        await _shift(monitor, "alice", T0 + timedelta(hours=8), 4)
        await _shift(monitor, "alice", T0 + timedelta(hours=16), 4)
        m = monitor.get_metrics("alice", ts=T0 + timedelta(hours=20))
        assert m["consecutive_shifts"] == 3

    @pytest.mark.asyncio
    async def test_consecutive_shifts_reset_by_long_rest(
        self, monitor: FatigueMonitor
    ) -> None:
        await _shift(monitor, "alice", T0, 4)
        await _shift(monitor, "alice", T0 + timedelta(hours=20), 4)  # 16h rest
        m = monitor.get_metrics("alice", ts=T0 + timedelta(hours=24))
        assert m["consecutive_shifts"] == 1


# =============================================================================
# Fatigue score
# =============================================================================

class TestFatigueScore:
    """get_fatigue_score: 0..1 score driven by the tracked metrics."""

    @pytest.mark.asyncio
    async def test_rested_crew_scores_zero(self, monitor: FatigueMonitor) -> None:
        await _shift(monitor, "alice", T0, 4)
        score = monitor.get_fatigue_score("alice", ts=T0 + timedelta(days=30))
        assert score == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_score_in_range(self, monitor: FatigueMonitor) -> None:
        await _shift(monitor, "alice", T0, 4)
        score = monitor.get_fatigue_score("alice", ts=T0 + timedelta(hours=4))
        assert 0.0 < score < 1.0

    @pytest.mark.asyncio
    async def test_score_rises_with_watch_length(
        self, monitor: FatigueMonitor
    ) -> None:
        await monitor.log_watch_start("alice", ts=T0)
        early = monitor.get_fatigue_score("alice", ts=T0 + timedelta(hours=2))
        late = monitor.get_fatigue_score("alice", ts=T0 + timedelta(hours=8))
        assert late > early

    @pytest.mark.asyncio
    async def test_score_saturates_at_one(self, monitor: FatigueMonitor) -> None:
        await monitor.log_watch_start("alice", ts=T0)
        score = monitor.get_fatigue_score("alice", ts=T0 + timedelta(hours=100))
        assert score == 1.0


# =============================================================================
# Compliance
# =============================================================================

class TestCompliance:
    """check_compliance: 10h max shift, 8h min rest, 24h weekly limit."""

    @pytest.mark.asyncio
    async def test_compliant_crew(self, monitor: FatigueMonitor) -> None:
        await _shift(monitor, "alice", T0, 6)
        report = monitor.check_compliance(ts=T0 + timedelta(hours=20))
        assert report["alice"]["compliant"] is True
        assert report["alice"]["violations"] == []

    @pytest.mark.asyncio
    async def test_shift_exceeded(self, monitor: FatigueMonitor) -> None:
        await monitor.log_watch_start("alice", ts=T0)
        report = monitor.check_compliance(ts=T0 + timedelta(hours=MAX_SHIFT_HOURS + 1))
        v = report["alice"]["violations"]
        assert report["alice"]["compliant"] is False
        assert any(x["rule"] == "shift_exceeded" for x in v)

    @pytest.mark.asyncio
    async def test_shift_at_limit_is_compliant(
        self, monitor: FatigueMonitor
    ) -> None:
        await monitor.log_watch_start("alice", ts=T0)
        report = monitor.check_compliance(ts=T0 + timedelta(hours=MAX_SHIFT_HOURS))
        assert not any(
            x["rule"] == "shift_exceeded" for x in report["alice"]["violations"]
        )

    @pytest.mark.asyncio
    async def test_rest_violation(self, monitor: FatigueMonitor) -> None:
        await _shift(monitor, "alice", T0, 4)
        # Only 4h rest before the next shift (< 8h minimum).
        await _shift(monitor, "alice", T0 + timedelta(hours=8), 4)
        report = monitor.check_compliance(ts=T0 + timedelta(hours=12))
        v = report["alice"]["violations"]
        assert any(x["rule"] == "rest_violation" for x in v)
        rest = next(x for x in v if x["rule"] == "rest_violation")
        assert rest["value"] == pytest.approx(4.0)
        assert rest["limit"] == MIN_REST_HOURS

    @pytest.mark.asyncio
    async def test_weekly_exceeded(self, monitor: FatigueMonitor) -> None:
        # 5 x 6h shifts with full rest = 30h in the trailing 7 days.
        for i in range(5):
            await _shift(monitor, "alice", T0 + timedelta(days=i), 6)
        report = monitor.check_compliance(ts=T0 + timedelta(days=5))
        v = report["alice"]["violations"]
        assert any(x["rule"] == "weekly_exceeded" for x in v)
        weekly = next(x for x in v if x["rule"] == "weekly_exceeded")
        assert weekly["limit"] == MAX_WEEKLY_HOURS

    @pytest.mark.asyncio
    async def test_weekly_window_slide(self, monitor: FatigueMonitor) -> None:
        for i in range(5):
            await _shift(monitor, "alice", T0 + timedelta(days=i), 6)
        # 8 days after the last shift, the window is clear again.
        report = monitor.check_compliance(ts=T0 + timedelta(days=13))
        assert not any(
            x["rule"] == "weekly_exceeded" for x in report["alice"]["violations"]
        )

    @pytest.mark.asyncio
    async def test_multiple_crew_reported(self, monitor: FatigueMonitor) -> None:
        await _shift(monitor, "alice", T0, 4)
        await _shift(monitor, "bob", T0, 4)
        report = monitor.check_compliance(ts=T0 + timedelta(hours=4))
        assert set(report) == {"alice", "bob"}


# =============================================================================
# CrewScheduler integration
# =============================================================================

class TestSchedulerIntegration:
    """Roster validation and watch-history sync from CrewScheduler."""

    @pytest.mark.asyncio
    async def test_unknown_crew_rejected(self, linked: FatigueMonitor) -> None:
        with pytest.raises(ValueError, match="unknown crew member"):
            await linked.log_watch_start("mallory", ts=T0)

    @pytest.mark.asyncio
    async def test_roster_member_accepted(self, linked: FatigueMonitor) -> None:
        session = await linked.log_watch_start("alice", ts=T0)
        assert session["end"] is None

    @pytest.mark.asyncio
    async def test_sync_imports_watches(self, linked: FatigueMonitor) -> None:
        sched = linked._scheduler
        await sched.assign_watch(
            "nav", "alice", start=T0, duration_hours=4
        )
        await sched.assign_watch(
            "engine", ["bob"], start=T0, duration_hours=6
        )
        imported = await linked.sync_from_scheduler()
        assert imported == 2
        m = linked.get_metrics("alice", ts=T0 + timedelta(hours=4))
        assert m["hours_worked_last_24h"] == pytest.approx(4.0)
        m = linked.get_metrics("bob", ts=T0 + timedelta(hours=6))
        assert m["hours_worked_last_24h"] == pytest.approx(6.0)

    @pytest.mark.asyncio
    async def test_sync_is_idempotent(self, linked: FatigueMonitor) -> None:
        sched = linked._scheduler
        await sched.assign_watch("nav", "alice", start=T0, duration_hours=4)
        assert await linked.sync_from_scheduler() == 1
        assert await linked.sync_from_scheduler() == 0
        m = linked.get_metrics("alice", ts=T0 + timedelta(hours=4))
        assert m["hours_worked_last_24h"] == pytest.approx(4.0)

    @pytest.mark.asyncio
    async def test_sync_ongoing_watch(self, linked: FatigueMonitor) -> None:
        sched = linked._scheduler
        await sched.assign_watch("nav", "alice", start=T0)
        await linked.sync_from_scheduler()
        m = linked.get_metrics("alice", ts=T0 + timedelta(hours=3))
        assert m["on_watch"] is True
        assert m["hours_on_watch"] == pytest.approx(3.0)

    @pytest.mark.asyncio
    async def test_sync_without_scheduler(
        self, monitor: FatigueMonitor
    ) -> None:
        with pytest.raises(RuntimeError, match="no CrewScheduler"):
            await monitor.sync_from_scheduler()


# =============================================================================
# WatcherRegistry integration
# =============================================================================

class TestWatcherIntegration:
    """register_watchers: crew-fatigue-risk rule flags fatigued crew."""

    @pytest.mark.asyncio
    async def test_registers_rule(self, monitor: FatigueMonitor) -> None:
        reg = WatcherRegistry()
        rule_id = monitor.register_watchers(reg)
        assert rule_id == "crew-fatigue-risk"
        assert reg.get(rule_id)["action"] == "raise_alert"

    @pytest.mark.asyncio
    async def test_no_fire_when_rested(self, monitor: FatigueMonitor) -> None:
        reg = WatcherRegistry()
        monitor.register_watchers(reg)
        await _shift(monitor, "alice", T0, 4)
        frame = monitor.build_frame(ts=T0 + timedelta(hours=20))
        assert reg.evaluate(frame) == []

    @pytest.mark.asyncio
    async def test_fires_on_fatigued_crew(self, monitor: FatigueMonitor) -> None:
        reg = WatcherRegistry()
        monitor.register_watchers(reg)
        await monitor.log_watch_start("alice", ts=T0)
        frame = monitor.build_frame(ts=T0 + timedelta(hours=MAX_SHIFT_HOURS + 2))
        actions = reg.evaluate(frame)
        assert len(actions) == 1
        action = actions[0]
        assert action["action"] == "raise_alert"
        assert action["payload"]["kind"] == "crew_fatigue"
        assert action["payload"]["crew"] == ["alice"]
        assert any(
            v["rule"] == "shift_exceeded"
            for v in action["payload"]["violations"]["alice"]
        )
        assert "alice" in action["reason"]
        assert 0.0 <= action["priority"] <= 1.0

    @pytest.mark.asyncio
    async def test_fires_on_rest_violation(self, monitor: FatigueMonitor) -> None:
        reg = WatcherRegistry()
        monitor.register_watchers(reg)
        await _shift(monitor, "alice", T0, 4)
        await _shift(monitor, "alice", T0 + timedelta(hours=8), 4)  # 4h rest
        frame = monitor.build_frame(ts=T0 + timedelta(hours=12))
        actions = reg.evaluate(frame)
        assert len(actions) == 1
        assert "alice" in actions[0]["payload"]["crew"]

    @pytest.mark.asyncio
    async def test_cooldown_suppression(self, monitor: FatigueMonitor) -> None:
        clock = [1000.0]
        history = WatcherHistory()
        reg = WatcherRegistry(history=history, now=lambda: clock[0])
        monitor.register_watchers(reg, cooldown_s=300.0)
        await monitor.log_watch_start("alice", ts=T0)
        frame = monitor.build_frame(ts=T0 + timedelta(hours=MAX_SHIFT_HOURS + 2))
        assert len(reg.evaluate(frame)) == 1
        # Inside the cooldown window the rule is suppressed.
        clock[0] += 60.0
        assert reg.evaluate(frame) == []

    @pytest.mark.asyncio
    async def test_invalid_threshold(self, monitor: FatigueMonitor) -> None:
        reg = WatcherRegistry()
        with pytest.raises(ValueError, match="alert_threshold"):
            monitor.register_watchers(reg, alert_threshold=1.5)
        with pytest.raises(TypeError):
            monitor.register_watchers(reg, alert_threshold="high")


# =============================================================================
# Persistence and lifecycle
# =============================================================================

class TestStorage:
    """JSON storage: state resume across instances."""

    @pytest.mark.asyncio
    async def test_state_file_written(
        self, monitor: FatigueMonitor, temp_monitor_path: Path
    ) -> None:
        await monitor.log_watch_start("alice", ts=T0)
        state = json.loads(temp_monitor_path.read_text(encoding="utf-8"))
        assert state["kind"] == KIND_FATIGUE
        assert state["crew"]["alice"]["sessions"][0]["start"] == _iso(T0)

    @pytest.mark.asyncio
    async def test_resume_across_instances(
        self, temp_monitor_path: Path
    ) -> None:
        m1 = FatigueMonitor(temp_monitor_path)
        await _shift(m1, "alice", T0, 4)
        m2 = FatigueMonitor(temp_monitor_path)
        metrics = m2.get_metrics("alice", ts=T0 + timedelta(hours=4))
        assert metrics["hours_worked_last_24h"] == pytest.approx(4.0)

    @pytest.mark.asyncio
    async def test_ignores_unrecognized_state(
        self, temp_monitor_path: Path
    ) -> None:
        temp_monitor_path.write_text(
            json.dumps({"kind": "something_else", "crew": {"x": {}}}),
            encoding="utf-8",
        )
        monitor = FatigueMonitor(temp_monitor_path)
        assert monitor.get_metrics("x", ts=T0)["hours_on_watch"] == 0.0

    @pytest.mark.asyncio
    async def test_synced_ids_persisted(
        self, tmp_path: Path, scheduler: CrewScheduler
    ) -> None:
        path = tmp_path / "fatigue.json"
        await scheduler.assign_watch("nav", "alice", start=T0, duration_hours=4)
        m1 = FatigueMonitor(path, scheduler=scheduler)
        assert await m1.sync_from_scheduler() == 1
        m2 = FatigueMonitor(path, scheduler=scheduler)
        assert await m2.sync_from_scheduler() == 0

    @pytest.mark.asyncio
    async def test_close_blocks_mutations(self, monitor: FatigueMonitor) -> None:
        await monitor.close()
        with pytest.raises(RuntimeError, match="after close"):
            await monitor.log_watch_start("alice", ts=T0)

    @pytest.mark.asyncio
    async def test_stats(self, monitor: FatigueMonitor) -> None:
        await monitor.log_watch_start("alice", ts=T0)
        stats = await monitor.stats()
        assert stats["crew"] == 1
        assert stats["on_watch"] == 1
        assert stats["limits"]["max_shift_hours"] == MAX_SHIFT_HOURS
        assert stats["closed"] is False

    @pytest.mark.asyncio
    async def test_constructor_limit_validation(
        self, temp_monitor_path: Path
    ) -> None:
        with pytest.raises(ValueError):
            FatigueMonitor(temp_monitor_path, max_shift_hours=0)
        with pytest.raises(TypeError):
            FatigueMonitor(temp_monitor_path, min_rest_hours="8")
