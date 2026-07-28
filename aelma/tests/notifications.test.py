"""Tests for the AELMA notification layer: NotificationManager + channels.

Coverage:

  1. Severity normalization (validation, unknown labels).
  2. Channel registration (validation, duplicates, listing, removal).
  3. send_notification — success, severity filtering, unknown channel.
  4. Rate limiting (sliding window, injectable clock).
  5. Retry logic (fail-then-succeed, exhausted retries, backoff timing).
  6. broadcast / test_channel.
  7. WatcherRegistry integration (critical auto-send, priority gating).

All delivery goes through fake senders — no network is touched.

Run from the repo root:  python -m pytest tests/notifications.test.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the repository root importable regardless of pytest's rootdir handling.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twin.notifications import (  # noqa: E402
    DEFAULT_CRITICAL_PRIORITY,
    NotificationManager,
    normalize_severity,
)
from twin.watcher_history import WatcherHistory  # noqa: E402
from twin.watchers import WatcherRegistry  # noqa: E402


class FakeClock:
    """Deterministic monotonic clock, advanced manually by tests."""

    def __init__(self, start: float = 1_000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class FakeSender:
    """Records deliveries; fails the first ``fail_times`` calls."""

    def __init__(self, fail_times: int = 0, exc: Exception | None = None) -> None:
        self.calls: list[tuple[dict, dict]] = []
        self.fail_times = fail_times
        self.exc = exc or RuntimeError("boom")

    def __call__(self, config, payload) -> None:
        self.calls.append((dict(config), dict(payload)))
        if len(self.calls) <= self.fail_times:
            raise self.exc


def make_manager(clock=None, **kw):
    clock = clock or FakeClock()
    sleeps: list[float] = []
    kw.setdefault("sleep", sleeps.append)
    mgr = NotificationManager(now=clock, **kw)
    return mgr, clock, sleeps


# --------------------------------------------------------------------- #
# 1. Severity normalization
# --------------------------------------------------------------------- #


class TestNormalizeSeverity:
    def test_valid_labels(self):
        assert normalize_severity("info") == "info"
        assert normalize_severity("WARNING") == "warning"
        assert normalize_severity(" critical ") == "critical"

    def test_unknown_label_rejected(self):
        with pytest.raises(ValueError):
            normalize_severity("fatal")

    def test_non_string_rejected(self):
        with pytest.raises(TypeError):
            normalize_severity(3)


# --------------------------------------------------------------------- #
# 2. Registration
# --------------------------------------------------------------------- #


class TestRegistration:
    def test_register_and_list(self):
        mgr, _, _ = make_manager()
        mgr.register_channel("ops", "slack", config={"webhook_url": "http://x"})
        mgr.register_channel("dev", "webhook", min_severity="critical")
        channels = mgr.list_channels()
        assert [c["name"] for c in channels] == ["ops", "dev"]
        assert channels[0]["kind"] == "slack"
        assert channels[0]["config_keys"] == ["webhook_url"]
        assert channels[1]["min_severity"] == "critical"
        assert mgr.stats["channel_count"] == 2

    def test_unknown_kind_rejected(self):
        mgr, _, _ = make_manager()
        with pytest.raises(ValueError):
            mgr.register_channel("x", "pager")

    def test_duplicate_name_rejected(self):
        mgr, _, _ = make_manager()
        mgr.register_channel("ops", "slack")
        with pytest.raises(ValueError):
            mgr.register_channel("ops", "email")

    def test_bad_name_and_rate_limit_rejected(self):
        mgr, _, _ = make_manager()
        with pytest.raises(TypeError):
            mgr.register_channel("", "slack")
        with pytest.raises(TypeError):
            mgr.register_channel("x", "slack", rate_limit_per_minute=0)

    def test_unregister(self):
        mgr, _, _ = make_manager()
        mgr.register_channel("ops", "slack")
        assert mgr.unregister_channel("ops") is True
        assert mgr.unregister_channel("ops") is False
        assert mgr.list_channels() == []


# --------------------------------------------------------------------- #
# 3. send_notification basics
# --------------------------------------------------------------------- #


class TestSendNotification:
    def test_successful_send(self):
        sender = FakeSender()
        mgr, _, _ = make_manager(senders={"slack": sender})
        mgr.register_channel("ops", "slack", config={"webhook_url": "http://x"})
        res = mgr.send_notification(
            "ops", "depth=1.2m", "warning",
            title="Shallow water", metadata={"rule_id": "shallow"},
        )
        assert res == {
            "ok": True,
            "channel": "ops",
            "severity": "warning",
            "status": "sent",
            "attempts": 1,
            "error": None,
        }
        assert len(sender.calls) == 1
        config, payload = sender.calls[0]
        assert config == {"webhook_url": "http://x"}
        assert payload["message"] == "depth=1.2m"
        assert payload["severity"] == "warning"
        assert payload["title"] == "Shallow water"
        assert payload["metadata"] == {"rule_id": "shallow"}
        assert mgr.stats["sent"] == 1

    def test_unknown_channel_raises(self):
        mgr, _, _ = make_manager()
        with pytest.raises(ValueError):
            mgr.send_notification("ghost", "hi", "info")

    def test_severity_filtering(self):
        sender = FakeSender()
        mgr, _, _ = make_manager(senders={"slack": sender})
        mgr.register_channel("crit-only", "slack", min_severity="critical")

        res = mgr.send_notification("crit-only", "low", "info")
        assert res["status"] == "filtered"
        assert res["ok"] is False
        res = mgr.send_notification("crit-only", "mid", "warning")
        assert res["status"] == "filtered"
        assert sender.calls == []

        res = mgr.send_notification("crit-only", "high", "critical")
        assert res["status"] == "sent"
        assert len(sender.calls) == 1
        assert mgr.stats["filtered"] == 2


# --------------------------------------------------------------------- #
# 4. Rate limiting
# --------------------------------------------------------------------- #


class TestRateLimiting:
    def test_window_caps_sends(self):
        sender = FakeSender()
        mgr, clock, _ = make_manager(senders={"slack": sender})
        mgr.register_channel("ops", "slack", rate_limit_per_minute=2)

        assert mgr.send_notification("ops", "a", "info")["status"] == "sent"
        assert mgr.send_notification("ops", "b", "info")["status"] == "sent"
        res = mgr.send_notification("ops", "c", "info")
        assert res["status"] == "rate_limited"
        assert len(sender.calls) == 2

        # Sliding window: after 61s the oldest entries have expired.
        clock.advance(61.0)
        assert mgr.send_notification("ops", "d", "info")["status"] == "sent"
        assert len(sender.calls) == 3
        assert mgr.stats["rate_limited"] == 1

    def test_limits_are_per_channel(self):
        sender = FakeSender()
        mgr, _, _ = make_manager(senders={"slack": sender, "webhook": sender})
        mgr.register_channel("a", "slack", rate_limit_per_minute=1)
        mgr.register_channel("b", "webhook", rate_limit_per_minute=1)
        assert mgr.send_notification("a", "x", "info")["status"] == "sent"
        assert mgr.send_notification("b", "x", "info")["status"] == "sent"


# --------------------------------------------------------------------- #
# 5. Retry logic
# --------------------------------------------------------------------- #


class TestRetryLogic:
    def test_fail_then_succeed_with_backoff(self):
        sender = FakeSender(fail_times=2)
        mgr, _, sleeps = make_manager(
            senders={"slack": sender}, max_retries=3, base_backoff_s=0.5
        )
        mgr.register_channel("ops", "slack")
        res = mgr.send_notification("ops", "msg", "info")
        assert res["status"] == "sent"
        assert res["attempts"] == 3
        assert sleeps == [0.5, 1.0]  # base * 2**attempt
        assert mgr.stats["sent"] == 1

    def test_exhausted_retries_reports_failure(self):
        sender = FakeSender(fail_times=99, exc=RuntimeError("smtp down"))
        mgr, _, sleeps = make_manager(
            senders={"email": sender}, max_retries=2, base_backoff_s=0.25
        )
        mgr.register_channel("mail", "email")
        res = mgr.send_notification("mail", "msg", "critical")
        assert res == {
            "ok": False,
            "channel": "mail",
            "severity": "critical",
            "status": "failed",
            "attempts": 3,
            "error": "smtp down",
        }
        assert len(sleeps) == 2
        assert mgr.stats["failed"] == 1

    def test_zero_retries_single_attempt(self):
        sender = FakeSender(fail_times=1)
        mgr, _, sleeps = make_manager(senders={"slack": sender}, max_retries=0)
        mgr.register_channel("ops", "slack")
        res = mgr.send_notification("ops", "msg", "info")
        assert res["status"] == "failed"
        assert res["attempts"] == 1
        assert sleeps == []

    def test_failed_attempts_do_not_consume_rate_limit(self):
        sender = FakeSender(fail_times=99)
        mgr, _, _ = make_manager(
            senders={"slack": sender}, max_retries=0
        )
        mgr.register_channel("ops", "slack", rate_limit_per_minute=1)
        res1 = mgr.send_notification("ops", "a", "info")
        res2 = mgr.send_notification("ops", "b", "info")
        assert res1["status"] == "failed"
        assert res2["status"] == "failed"  # not rate_limited


# --------------------------------------------------------------------- #
# 6. broadcast / test_channel
# --------------------------------------------------------------------- #


class TestBroadcastAndTestChannel:
    def test_broadcast_hits_all_channels(self):
        slack, hook = FakeSender(), FakeSender()
        mgr, _, _ = make_manager(senders={"slack": slack, "webhook": hook})
        mgr.register_channel("ops", "slack")
        mgr.register_channel("hook", "webhook", min_severity="warning")
        results = mgr.broadcast("engine temp high", "warning")
        assert [r["status"] for r in results] == ["sent", "sent"]
        assert len(slack.calls) == 1
        assert len(hook.calls) == 1

    def test_test_channel_bypasses_severity_filter(self):
        sender = FakeSender()
        mgr, _, _ = make_manager(senders={"slack": sender})
        mgr.register_channel("crit-only", "slack", min_severity="critical")
        res = mgr.test_channel("crit-only")
        assert res["status"] == "sent"
        assert sender.calls[0][1]["metadata"] == {"test": True}

    def test_test_channel_unknown_raises(self):
        mgr, _, _ = make_manager()
        with pytest.raises(ValueError):
            mgr.test_channel("ghost")


# --------------------------------------------------------------------- #
# 7. WatcherRegistry integration
# --------------------------------------------------------------------- #


def critical_registry(sender, clock):
    """Watcher registry + manager wired via attach_to_watchers."""
    registry = WatcherRegistry(history=WatcherHistory(), now=clock)
    mgr = NotificationManager(now=clock, sleep=lambda s: None,
                              senders={"slack": sender})
    mgr.register_channel("ops", "slack")
    mgr.attach_to_watchers(registry)
    return registry, mgr


class TestWatcherIntegration:
    def test_critical_alert_auto_sent(self):
        sender = FakeSender()
        clock = FakeClock()
        registry, mgr = critical_registry(sender, clock)
        registry.add({
            "id": "shallow-water",
            "name": "Shallow water warning",
            "when": lambda f: 0 < f.get("depth_m", 999) < 2.0,
            "action": {
                "name": "raise_alert",
                "payload": lambda f: {"kind": "shallow_water",
                                      "depth": f["depth_m"]},
                "reason": lambda f: f"depth={f['depth_m']:.2f}m",
                "priority": lambda f: 0.95,
            },
        })
        fired = registry.evaluate({"depth_m": 1.2})
        assert len(fired) == 1
        assert len(sender.calls) == 1
        _, payload = sender.calls[0]
        assert payload["severity"] == "critical"
        assert payload["title"] == "AELMA critical alert: shallow_water"
        assert payload["message"] == "depth=1.20m"
        assert payload["metadata"]["rule_id"] == "shallow-water"
        assert payload["metadata"]["depth"] == 1.2

    def test_below_threshold_priority_not_sent(self):
        sender = FakeSender()
        clock = FakeClock()
        registry, _ = critical_registry(sender, clock)
        registry.add({
            "id": "mild",
            "name": "Mild alert",
            "when": lambda f: True,
            "action": {"name": "raise_alert", "priority": lambda f: 0.5},
        })
        registry.evaluate({})
        assert sender.calls == []

    def test_non_alert_actions_not_sent(self):
        sender = FakeSender()
        clock = FakeClock()
        registry, _ = critical_registry(sender, clock)
        registry.add({
            "id": "morph",
            "name": "Mode morph",
            "when": lambda f: True,
            "action": {"name": "morph_to_hazard_mode", "priority": lambda f: 1.0},
        })
        registry.evaluate({})
        assert sender.calls == []

    def test_custom_min_priority(self):
        sender = FakeSender()
        clock = FakeClock()
        registry = WatcherRegistry(now=clock)
        mgr = NotificationManager(now=clock, sleep=lambda s: None,
                                  senders={"slack": sender})
        mgr.register_channel("ops", "slack")
        mgr.attach_to_watchers(registry, min_priority=0.4)
        registry.add({
            "id": "medium",
            "name": "Medium alert",
            "when": lambda f: True,
            "action": {"name": "raise_alert", "priority": lambda f: 0.5},
        })
        registry.evaluate({})
        assert len(sender.calls) == 1
        assert DEFAULT_CRITICAL_PRIORITY == 0.9
