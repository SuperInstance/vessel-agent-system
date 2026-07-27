"""WatcherRegistry: deterministic threshold rules over twin state frames.

Python/asyncio adaptation of the mini-agent ``backend/watchers.js``
pattern (the "Watcher" design reviewed in the minimax agent log): pure
predicate rules that turn a state frame into viewer-facing actions
*without* involving any model reasoning. Watchers are the fast path —
they run on every snapshot tick and must stay cheap, deterministic, and
side-effect free.

A rule maps one frame to at most one action:

    reg = WatcherRegistry(history=WatcherHistory())
    reg.add({
        "id": "shallow-water",
        "name": "Shallow water warning",
        "when": lambda f: 0 < f.get("depth_m", 999) < 2.0,
        "action": {
            "name": "raise_alert",
            "payload": lambda f: {"kind": "shallow_water", "depth": f["depth_m"]},
            "reason": lambda f: f"depth={f['depth_m']:.2f}m",
            "priority": lambda f: 0.85,
        },
        "cooldown_s": 30.0,
    })
    actions = reg.evaluate(frame)          # sync, pure — safe in any loop

Contracts (carried over from the mini-agent review):

* ``when`` and the action callbacks must be PURE: no I/O, no mutation,
  no awaiting. Exceptions they raise are isolated — the registry emits an
  ``error`` event naming the failing stage and continues with the next
  rule.
* When a :class:`~twin.watcher_history.WatcherHistory` is attached, a
  matched rule is suppressed while inside its cooldown window
  (:meth:`WatcherHistory.should_fire`). History errors are likewise
  contained under the ``history-decide`` stage.
* ``evaluate`` never raises for rule-level failures; it raises
  ``TypeError`` only for a non-mapping frame (a caller bug).

The frame is any mapping — in AELMA it is typically the latest per-channel
reading dict from :class:`~twin.state.VesselState` plus derived pose
fields, so rules read plain keys like ``depth_m`` or ``speed_kn``.
"""

from __future__ import annotations

import inspect
import logging
import math
import time
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .watcher_history import WatcherHistory

log = logging.getLogger("aelma.twin.watchers")

#: Priority used when a rule declares no priority callback. 0.5 is the
#: middle of the road: above ambient announcements, below real hazards.
DEFAULT_PRIORITY = 0.5

#: Action names the viewer layer understands. A rule whose action is not
#: in this set is rejected at registration time, so a typo fails fast
#: instead of silently producing actions the viewer drops.
ALLOWED_ACTIONS = frozenset(
    {
        "morph_to_hazard_mode",
        "morph_to_navigation_mode",
        "morph_to_engineering_mode",
        "highlight_waypoint",
        "raise_alert",
        "clear_alerts",
        "set_panel_focus",
        "announce",
    }
)


@dataclass(frozen=True)
class WatcherRule:
    """Normalized rule. Callbacks are optional; defaults are trivial."""

    id: str
    name: str
    when: Callable[[Mapping[str, Any]], bool]
    action_name: str
    payload: Callable[[Mapping[str, Any]], Any] | None = None
    reason: Callable[[Mapping[str, Any]], str] | None = None
    priority: Callable[[Mapping[str, Any]], float] | None = None
    cooldown_s: float = 0.0


class WatcherRegistry:
    """Ordered set of watcher rules plus optional suppression history.

    Parameters
    ----------
    verbose:
        Log every firing at INFO level.
    history:
        Optional :class:`WatcherHistory`. When absent, nothing is ever
        suppressed and ``stats["history"]`` is ``None``.
    now:
        Clock returning seconds (defaults to :func:`time.monotonic`).
        Injected for deterministic tests.
    """

    def __init__(
        self,
        *,
        verbose: bool = False,
        history: WatcherHistory | None = None,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self.verbose = verbose
        self.history = history
        self._now = now
        self._rules: dict[str, WatcherRule] = {}
        self._listeners: dict[str, list[Callable[..., Any]]] = {
            "fired": [],
            "suppressed": [],
            "error": [],
        }

    # ------------------------------------------------------------------ #
    # Events
    # ------------------------------------------------------------------ #
    def on(self, event: str, callback: Callable[..., Any]) -> None:
        """Subscribe to ``fired`` / ``suppressed`` / ``error`` events."""
        if event not in self._listeners:
            raise ValueError(f"unknown watcher event: {event!r}")
        self._listeners[event].append(callback)

    def _emit(self, event: str, *args: Any) -> None:
        for cb in self._listeners[event]:
            try:
                cb(*args)
            except Exception:  # listener bugs must not break evaluation
                log.exception("watcher %r listener failed", event)

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #
    def add(self, rule: Mapping[str, Any] | WatcherRule) -> str:
        """Validate, normalize, and register a rule. Returns the rule id."""
        normalized = self._normalize(rule)
        if normalized.id in self._rules:
            raise ValueError(f"duplicate watcher rule id: {normalized.id!r}")
        self._rules[normalized.id] = normalized
        return normalized.id

    @staticmethod
    def _normalize(rule: Mapping[str, Any] | WatcherRule) -> WatcherRule:
        if isinstance(rule, WatcherRule):
            spec: Mapping[str, Any] = {
                "id": rule.id,
                "name": rule.name,
                "when": rule.when,
                "action": {"name": rule.action_name},
                "cooldown_s": rule.cooldown_s,
            }
            out = rule
        elif isinstance(rule, Mapping):
            spec = rule
            out = None
        else:
            raise TypeError("watcher rule must be a mapping or WatcherRule")

        rid = spec.get("id")
        if not isinstance(rid, str) or not rid:
            raise TypeError("watcher rule.id must be a non-empty string")
        name = spec.get("name")
        if not isinstance(name, str) or not name:
            raise TypeError("watcher rule.name must be a non-empty string")
        when = spec.get("when")
        if not callable(when):
            raise TypeError("watcher rule.when must be callable")
        action = spec.get("action")
        if not isinstance(action, Mapping):
            raise TypeError("watcher rule.action must be a mapping")
        action_name = action.get("name")
        if action_name not in ALLOWED_ACTIONS:
            raise ValueError(
                f"watcher action {action_name!r} not in ALLOWED_ACTIONS"
            )
        for field_name in ("payload", "reason", "priority"):
            fn = action.get(field_name)
            if fn is not None and not callable(fn):
                raise TypeError(f"watcher action.{field_name} must be callable")
        cooldown_s = spec.get("cooldown_s", 0.0)
        if not isinstance(cooldown_s, (int, float)) or cooldown_s < 0:
            raise TypeError("watcher rule.cooldown_s must be a number >= 0")

        if out is not None:
            return out
        return WatcherRule(
            id=rid,
            name=name,
            when=when,
            action_name=str(action_name),
            payload=action.get("payload"),
            reason=action.get("reason"),
            priority=action.get("priority"),
            cooldown_s=float(cooldown_s),
        )

    def remove(self, rule_id: str) -> bool:
        """Unregister a rule; returns True when it existed."""
        return self._rules.pop(rule_id, None) is not None

    def get(self, rule_id: str) -> dict[str, Any] | None:
        """Public (callback-free) view of one rule, or None."""
        rule = self._rules.get(rule_id)
        if rule is None:
            return None
        return {
            "id": rule.id,
            "name": rule.name,
            "action": rule.action_name,
            "cooldown_s": rule.cooldown_s,
        }

    def list(self) -> list[dict[str, Any]]:
        """Public view of all rules, in registration order."""
        return [self.get(rid) for rid in self._rules]  # type: ignore[misc]

    def __len__(self) -> int:
        return len(self._rules)

    # ------------------------------------------------------------------ #
    # Evaluation
    # ------------------------------------------------------------------ #
    def evaluate(self, frame: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Evaluate all rules against ``frame``; return fired actions.

        Actions are returned in registration order. Rule-level failures
        (predicate, action callbacks, history) are contained per rule and
        reported through the ``error`` event; they never abort the pass.
        """
        if not isinstance(frame, Mapping):
            raise TypeError("watcher frame must be a mapping")
        fired: list[dict[str, Any]] = []
        now = self._now()
        for rule in self._rules.values():
            try:
                matched = bool(rule.when(frame))
            except Exception as exc:
                self._emit(
                    "error", exc,
                    {"rule_id": rule.id, "rule_name": rule.name, "stage": "when"},
                )
                continue
            if not matched:
                continue
            try:
                payload = rule.payload(frame) if rule.payload else {}
                reason = rule.reason(frame) if rule.reason else ""
                priority = (
                    float(rule.priority(frame))
                    if rule.priority
                    else DEFAULT_PRIORITY
                )
                if not math.isfinite(priority):
                    raise ValueError(f"non-finite priority: {priority!r}")
                priority = min(1.0, max(0.0, priority))
            except Exception as exc:
                self._emit(
                    "error", exc,
                    {"rule_id": rule.id, "rule_name": rule.name, "stage": "action"},
                )
                continue

            if self.history is not None:
                try:
                    allowed, why = self.history.should_fire(
                        rule.id, now, rule.cooldown_s, payload
                    )
                except Exception as exc:
                    self._emit(
                        "error", exc,
                        {
                            "rule_id": rule.id,
                            "rule_name": rule.name,
                            "stage": "history-decide",
                        },
                    )
                    continue
                if not allowed:
                    self.history.mark_suppressed(rule.id, why or "cooldown")
                    self._emit("suppressed", rule.id, why)
                    continue

            action = {
                "action": rule.action_name,
                "payload": payload,
                "reason": reason,
                "priority": priority,
                "rule_id": rule.id,
            }
            fired.append(action)
            if self.history is not None:
                self.history.record(rule.id, now, payload, priority)
            if self.verbose:
                log.info("[watcher] %s -> %s p=%.2f", rule.id,
                         rule.action_name, priority)
            self._emit("fired", action)
        return fired

    async def run(
        self,
        frames: AsyncIterator[Mapping[str, Any]],
        dispatch: Callable[[dict[str, Any]], Any],
    ) -> None:
        """Async driver: evaluate each frame from ``frames``, dispatch fires.

        ``dispatch`` may be a plain callable or a coroutine function; the
        result is awaited when awaitable. This is the asyncio-native way to
        hang the registry off a twin packet/snapshot stream::

            async def frames():
                while True:
                    await asyncio.sleep(twin.broadcast_interval)
                    yield latest_channels()

            await registry.run(frames(), viewer.broadcast_action)
        """
        async for frame in frames:
            for action in self.evaluate(frame):
                result = dispatch(action)
                if inspect.isawaitable(result):
                    await result

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #
    @property
    def stats(self) -> dict[str, Any]:
        """Registry stats; ``history`` is None when no history is attached."""
        return {
            "rule_count": len(self._rules),
            "rules": self.list(),
            "history": self.history.get_stats() if self.history else None,
        }


# Kept for parity with the mini-agent exports and for type checkers.
__all__ = ["ALLOWED_ACTIONS", "DEFAULT_PRIORITY", "WatcherRegistry", "WatcherRule"]
