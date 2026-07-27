"""Tests for the AELMA watcher layer: WatcherRegistry + WatcherHistory.

Mirrors the mini-agent's three JS suites (watchers / watcherHistory /
watchersWithHistory) adapted to pytest and asyncio. Coverage:

  1. WatcherHistory — should_fire state machine, payload dedup,
     mark_suppressed counters, stats, reset, payload_key stability.
  2. Registry construction & rule registration (validation, dedupe).
  3. Rule lookup / removal.
  4. evaluate() — match / no-match, ordering, defaults, frame contract.
  5. Error isolation (stages: when / action / history-decide).
  6. Registry ↔ history integration (cooldown, suppression, stats).
  7. Asyncio driver (run over an async frame stream).

Run from the repo root:  python -m pytest tests/watchers.test.py -v
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

# Make the repository root importable regardless of pytest's rootdir handling.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twin.watcher_history import (  # noqa: E402
    REASON_COOLDOWN,
    REASON_DUPLICATE,
    WatcherHistory,
    payload_key,
)
from twin.watchers import (  # noqa: E402
    ALLOWED_ACTIONS,
    DEFAULT_PRIORITY,
    WatcherRegistry,
    WatcherRule,
)


class FakeClock:
    """Deterministic monotonic clock, advanced manually by tests."""

    def __init__(self, start: float = 1_000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def frame(**over):
    """A plausible twin frame: latest channel readings plus pose."""
    base = {
        "lat": 57.0531,
        "lon": -135.33,
        "speed_kn": 5.4,
        "heading_deg": 214.5,
        "depth_m": 11.4,
        "trajectory_progress": 0.42,
    }
    base.update(over)
    return base


def shallow_rule(**over):
    """A minimal valid rule dict; keyword overrides tweak any field."""
    rule = {
        "id": "r-shallow",
        "name": "Shallow water warning",
        "when": lambda f: 0 < f.get("depth_m", 999.0) < 2.0,
        "action": {
            "name": "raise_alert",
            "payload": lambda f: {"kind": "shallow_water", "depth": f["depth_m"]},
            "reason": lambda f: f"depth={f['depth_m']:.2f}m",
            "priority": lambda f: 0.85,
        },
    }
    rule.update(over)
    return rule


# --------------------------------------------------------------------- #
# WatcherHistory — unit
# --------------------------------------------------------------------- #

class TestPayloadKey:
    def test_stable_regardless_of_key_order(self):
        a = {"depth": 1.2, "kind": "shallow_water"}
        b = {"kind": "shallow_water", "depth": 1.2}
        assert payload_key(a) == payload_key(b)

    def test_different_content_different_key(self):
        assert payload_key({"depth": 1.2}) != payload_key({"depth": 3.4})

    def test_non_serializable_does_not_crash(self):
        key = payload_key({"obj": object()})
        assert isinstance(key, str) and len(key) == 16


class TestShouldFireStateMachine:
    def test_first_fire_always_allowed(self):
        h = WatcherHistory()
        assert h.should_fire("r1", 100.0, 10.0, {}) == (True, None)

    def test_within_cooldown_same_payload_is_duplicate(self):
        h = WatcherHistory()
        h.record("r1", 100.0, {"a": 1}, 0.5)
        assert h.should_fire("r1", 105.0, 10.0, {"a": 1}) == (
            False, REASON_DUPLICATE)

    def test_within_cooldown_changed_payload_is_cooldown(self):
        h = WatcherHistory()
        h.record("r1", 100.0, {"a": 1}, 0.5)
        assert h.should_fire("r1", 105.0, 10.0, {"a": 2}) == (
            False, REASON_COOLDOWN)

    def test_after_cooldown_allowed_even_with_same_payload(self):
        h = WatcherHistory()
        h.record("r1", 100.0, {"a": 1}, 0.5)
        assert h.should_fire("r1", 110.0, 10.0, {"a": 1}) == (True, None)

    def test_zero_rule_cooldown_uses_history_default(self):
        h = WatcherHistory(default_cooldown_s=10.0)
        h.record("r1", 100.0, {"a": 1}, 0.5)
        allowed, reason = h.should_fire("r1", 105.0, 0.0, {"a": 1})
        assert (allowed, reason) == (False, REASON_DUPLICATE)

    def test_zero_effective_cooldown_never_suppresses(self):
        h = WatcherHistory()
        h.record("r1", 100.0, {"a": 1}, 0.5)
        assert h.should_fire("r1", 100.0, 0.0, {"a": 1}) == (True, None)

    def test_does_not_mutate_state(self):
        h = WatcherHistory()
        h.record("r1", 100.0, {"a": 1}, 0.5)
        for _ in range(3):
            h.should_fire("r1", 105.0, 10.0, {"a": 1})
        stats = h.get_stats()["rules"]["r1"]
        assert stats["total_fires"] == 1
        assert stats["total_suppressed"] == 0


class TestMarkSuppressedAndStats:
    def test_counters_and_reasons(self):
        h = WatcherHistory()
        h.mark_suppressed("r1", REASON_DUPLICATE)
        h.mark_suppressed("r1", REASON_DUPLICATE)
        h.mark_suppressed("r1", REASON_COOLDOWN)
        rec = h.get_stats()["rules"]["r1"]
        assert rec["total_suppressed"] == 3
        assert rec["last_suppressed_reason"] == REASON_COOLDOWN
        assert rec["suppressed_by_reason"] == {"duplicate": 2, "cooldown": 1}

    def test_aggregate_stats(self):
        h = WatcherHistory()
        h.record("r1", 100.0, {}, 0.7)
        h.record("r2", 100.0, {}, 0.3)
        h.mark_suppressed("r2", REASON_COOLDOWN)
        stats = h.get_stats()
        assert stats["total_fires"] == 2
        assert stats["total_suppressed"] == 1
        assert stats["rules"]["r1"]["last_priority"] == 0.7
        assert stats["default_cooldown_s"] == 0.0

    def test_reset_one_rule_and_all(self):
        h = WatcherHistory()
        h.record("r1", 100.0, {}, 0.5)
        h.record("r2", 100.0, {}, 0.5)
        h.reset("r1")
        assert h.should_fire("r1", 100.0, 60.0, {})[0] is True
        assert "r2" in h.get_stats()["rules"]
        h.reset()
        assert h.get_stats()["rules"] == {}

    def test_negative_default_cooldown_rejected(self):
        with pytest.raises(ValueError):
            WatcherHistory(default_cooldown_s=-1.0)


# --------------------------------------------------------------------- #
# Registry — construction, registration, lookup
# --------------------------------------------------------------------- #

class TestRegistration:
    def test_constructs_with_defaults(self):
        reg = WatcherRegistry()
        assert len(reg) == 0
        assert reg.verbose is False
        assert reg.stats["history"] is None

    def test_default_priority_is_half(self):
        assert DEFAULT_PRIORITY == 0.5

    def test_add_returns_id(self):
        assert WatcherRegistry().add(shallow_rule()) == "r-shallow"

    def test_duplicate_id_rejected(self):
        reg = WatcherRegistry()
        reg.add(shallow_rule())
        with pytest.raises(ValueError, match="duplicate"):
            reg.add(shallow_rule())

    @pytest.mark.parametrize("bad", [
        {"id": "", "name": "x", "when": lambda f: True,
         "action": {"name": "raise_alert"}},
        {"id": "r", "name": "", "when": lambda f: True,
         "action": {"name": "raise_alert"}},
        {"id": "r", "name": "x", "when": "not-callable",
         "action": {"name": "raise_alert"}},
        {"id": "r", "name": "x", "when": lambda f: True, "action": None},
        {"id": "r", "name": "x", "when": lambda f: True,
         "action": {"name": "raise_alert"}, "cooldown_s": -5},
    ])
    def test_invalid_rules_rejected(self, bad):
        with pytest.raises((TypeError, ValueError)):
            WatcherRegistry().add(bad)

    def test_unknown_action_rejected(self):
        with pytest.raises(ValueError, match="ALLOWED_ACTIONS"):
            WatcherRegistry().add(shallow_rule(action={"name": "self_destruct"}))

    def test_all_allowed_actions_accepted(self):
        reg = WatcherRegistry()
        for i, name in enumerate(sorted(ALLOWED_ACTIONS)):
            reg.add(shallow_rule(id=f"r-{i}", action={"name": name}))
        assert len(reg) == len(ALLOWED_ACTIONS) == 8

    def test_remove_and_lookup(self):
        reg = WatcherRegistry()
        reg.add(shallow_rule(cooldown_s=12.5))
        view = reg.get("r-shallow")
        assert view["cooldown_s"] == 12.5  # round-trips through get()
        assert view["action"] == "raise_alert"
        assert reg.get("nope") is None
        assert reg.remove("r-shallow") is True
        assert reg.remove("r-shallow") is False
        assert reg.list() == []


# --------------------------------------------------------------------- #
# Registry — evaluate basics
# --------------------------------------------------------------------- #

class TestEvaluate:
    def test_match_produces_action(self):
        reg = WatcherRegistry()
        reg.add(shallow_rule())
        out = reg.evaluate(frame(depth_m=1.2))
        assert len(out) == 1
        assert out[0]["action"] == "raise_alert"
        assert out[0]["payload"] == {"kind": "shallow_water", "depth": 1.2}
        assert out[0]["reason"] == "depth=1.20m"
        assert out[0]["priority"] == 0.85
        assert out[0]["rule_id"] == "r-shallow"

    def test_no_match_produces_nothing(self):
        reg = WatcherRegistry()
        reg.add(shallow_rule())
        assert reg.evaluate(frame(depth_m=11.4)) == []

    def test_registration_order_preserved(self):
        reg = WatcherRegistry()
        reg.add(shallow_rule(id="r-a", when=lambda f: True,
                             action={"name": "announce"}))
        reg.add(shallow_rule(id="r-b", when=lambda f: True,
                             action={"name": "clear_alerts"}))
        out = reg.evaluate(frame())
        assert [a["rule_id"] for a in out] == ["r-a", "r-b"]

    def test_defaults_when_action_callbacks_omitted(self):
        reg = WatcherRegistry()
        reg.add(shallow_rule(action={"name": "announce"}))
        out = reg.evaluate(frame(depth_m=1.0))
        assert out[0]["payload"] == {}
        assert out[0]["reason"] == ""
        assert out[0]["priority"] == DEFAULT_PRIORITY

    def test_priority_clamped_to_unit_interval(self):
        reg = WatcherRegistry()
        reg.add(shallow_rule(action={"name": "raise_alert",
                                     "priority": lambda f: 42.0}))
        assert reg.evaluate(frame(depth_m=1.0))[0]["priority"] == 1.0

    @pytest.mark.parametrize("bad", [None, "frame", 42, [1, 2]])
    def test_non_mapping_frame_raises_type_error(self, bad):
        with pytest.raises(TypeError):
            WatcherRegistry().evaluate(bad)

    def test_fired_event_emitted(self):
        seen = []
        reg = WatcherRegistry()
        reg.on("fired", seen.append)
        reg.add(shallow_rule())
        reg.evaluate(frame(depth_m=1.0))
        assert len(seen) == 1 and seen[0]["rule_id"] == "r-shallow"


# --------------------------------------------------------------------- #
# Error isolation
# --------------------------------------------------------------------- #

class TestErrorIsolation:
    def test_when_exception_emits_error_and_continues(self):
        errors = []

        def boom(f):
            raise RuntimeError("sensor exploded")

        reg = WatcherRegistry()
        reg.on("error", lambda exc, ctx: errors.append(ctx))
        reg.add(shallow_rule(id="r-bad", when=boom))
        reg.add(shallow_rule(id="r-good", when=lambda f: True,
                             action={"name": "announce"}))
        out = reg.evaluate(frame())
        assert [a["rule_id"] for a in out] == ["r-good"]
        assert errors[0]["stage"] == "when"
        assert errors[0]["rule_id"] == "r-bad"

    def test_action_callback_exception_contained(self):
        errors = []
        reg = WatcherRegistry()
        reg.on("error", lambda exc, ctx: errors.append(ctx))
        reg.add(shallow_rule(action={
            "name": "raise_alert",
            "payload": lambda f: 1 / 0,
        }))
        assert reg.evaluate(frame(depth_m=1.0)) == []
        assert errors[0]["stage"] == "action"

    def test_listener_exception_does_not_break_evaluate(self):
        reg = WatcherRegistry()
        reg.on("fired", lambda a: 1 / 0)
        reg.add(shallow_rule())
        assert len(reg.evaluate(frame(depth_m=1.0))) == 1


# --------------------------------------------------------------------- #
# Registry ↔ history integration
# --------------------------------------------------------------------- #

class TestHistoryIntegration:
    def test_without_history_fires_every_evaluate(self):
        reg = WatcherRegistry()
        reg.add(shallow_rule(cooldown_s=60.0))  # ignored: no history
        for _ in range(3):
            assert len(reg.evaluate(frame(depth_m=1.0))) == 1
        assert reg.stats["history"] is None

    def test_with_history_zero_cooldown_fires_every_evaluate(self):
        clock = FakeClock()
        reg = WatcherRegistry(history=WatcherHistory(), now=clock)
        reg.add(shallow_rule())  # cooldown_s defaults to 0
        for _ in range(3):
            assert len(reg.evaluate(frame(depth_m=1.0))) == 1

    def test_cooldown_suppresses_then_expires(self):
        clock = FakeClock()
        reg = WatcherRegistry(history=WatcherHistory(), now=clock)
        reg.add(shallow_rule(cooldown_s=10.0))
        assert len(reg.evaluate(frame(depth_m=1.0))) == 1  # t=1000: fires
        clock.advance(5.0)
        assert reg.evaluate(frame(depth_m=1.0)) == []       # suppressed
        clock.advance(5.0)
        assert len(reg.evaluate(frame(depth_m=1.0))) == 1  # t=1010: fires

    def test_changed_payload_still_suppressed_within_cooldown(self):
        clock = FakeClock()
        reg = WatcherRegistry(history=WatcherHistory(), now=clock)
        reg.add(shallow_rule(cooldown_s=10.0))
        assert len(reg.evaluate(frame(depth_m=1.0))) == 1
        clock.advance(1.0)
        assert reg.evaluate(frame(depth_m=1.5)) == []  # new payload, cooldown

    def test_suppressed_event_and_stats(self):
        events = []
        clock = FakeClock()
        reg = WatcherRegistry(history=WatcherHistory(), now=clock)
        reg.on("suppressed", lambda rid, why: events.append((rid, why)))
        reg.add(shallow_rule(cooldown_s=10.0))
        reg.evaluate(frame(depth_m=1.0))
        reg.evaluate(frame(depth_m=1.0))
        assert events == [("r-shallow", REASON_DUPLICATE)]
        hist = reg.stats["history"]
        assert hist["total_fires"] == 1
        assert hist["total_suppressed"] == 1
        assert hist["rules"]["r-shallow"]["last_suppressed_reason"] == (
            REASON_DUPLICATE)

    def test_cooldowns_are_per_rule(self):
        clock = FakeClock()
        reg = WatcherRegistry(history=WatcherHistory(), now=clock)
        reg.add(shallow_rule(id="r-slow", cooldown_s=60.0))
        reg.add(shallow_rule(id="r-fast", action={"name": "announce"}))
        reg.evaluate(frame(depth_m=1.0))
        out = reg.evaluate(frame(depth_m=1.0))
        assert [a["rule_id"] for a in out] == ["r-fast"]

    def test_history_decide_error_is_contained(self):
        clock = FakeClock()
        hist = WatcherHistory()

        def broken(*args):
            raise RuntimeError("history offline")

        hist.should_fire = broken  # type: ignore[method-assign]
        errors = []
        reg = WatcherRegistry(history=hist, now=clock)
        reg.on("error", lambda exc, ctx: errors.append(ctx))
        reg.add(shallow_rule())
        reg.add(shallow_rule(id="r-2", action={"name": "announce"}))
        assert reg.evaluate(frame(depth_m=1.0)) == []
        assert {e["stage"] for e in errors} == {"history-decide"}
        assert len(errors) == 2  # both rules contained, evaluation continued


# --------------------------------------------------------------------- #
# Asyncio driver
# --------------------------------------------------------------------- #

class TestAsyncRun:
    @pytest.mark.asyncio
    async def test_run_dispatches_fired_actions(self):
        async def frames():
            for depth in (11.0, 1.2, 8.0, 1.5):
                await asyncio.sleep(0)
                yield frame(depth_m=depth)

        reg = WatcherRegistry()
        reg.add(shallow_rule())
        sent = []

        async def dispatch(action):
            sent.append(action)

        await reg.run(frames(), dispatch)
        assert [a["payload"]["depth"] for a in sent] == [1.2, 1.5]

    @pytest.mark.asyncio
    async def test_run_accepts_sync_dispatch(self):
        async def frames():
            yield frame(depth_m=1.0)

        reg = WatcherRegistry()
        reg.add(shallow_rule())
        sent = []
        await reg.run(frames(), sent.append)
        assert len(sent) == 1

    @pytest.mark.asyncio
    async def test_run_respects_history_cooldown(self):
        clock = FakeClock()

        async def frames():
            for _ in range(3):
                yield frame(depth_m=1.0)
                clock.advance(1.0)

        reg = WatcherRegistry(history=WatcherHistory(), now=clock)
        reg.add(shallow_rule(cooldown_s=10.0))
        sent = []
        await reg.run(frames(), sent.append)
        assert len(sent) == 1  # first tick fires; next two are duplicates


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
