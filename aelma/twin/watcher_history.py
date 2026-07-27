"""WatcherHistory: per-rule suppression state for the WatcherRegistry.

Adapted from the mini-agent ``backend/watcherHistory.js`` pattern and
translated to Python asyncio-era idioms (stdlib only, seconds-based clock).

Why this exists
---------------
Watchers fire on every frame where their predicate is true. A steady-state
condition ("depth < 2 m" while anchored over a shoal) would otherwise emit
the same alert on every evaluation tick, flooding the viewer, the alert
log, and any downstream consumer. WatcherHistory is the deterministic
suppression layer that sits between "rule matched" and "action emitted":

* **Cooldown** — after a rule fires, it may not fire again until
  ``cooldown_s`` seconds have elapsed.
* **Payload dedup** — within that cooldown window an *identical* payload
  is reported as a ``duplicate``; a *changed* payload is reported as a
  plain ``cooldown`` suppression, so operators can tell "same alert
  repeating" from "new alert arriving too fast".

Suppression is per rule id. The history is deliberately a separate class
from the registry: the registry stays a pure rule engine, and the history
can be shared, inspected (``get_stats``), or swapped out wholesale.

Clock: all times are seconds from a monotonic clock. The registry injects
its ``now`` callable so tests can drive time deterministically.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

#: Suppression reasons reported through :meth:`WatcherHistory.should_fire`.
REASON_COOLDOWN = "cooldown"
REASON_DUPLICATE = "duplicate"


def payload_key(payload: Any) -> str:
    """Stable identity key for a fired payload (used for dedup).

    The payload is serialized canonically (sorted keys, tight separators)
    so that two dicts with equal content hash identically regardless of
    insertion order. Non-JSON-serializable payloads fall back to ``repr``
    via ``default=str``, so a weird payload degrades dedup quality but
    never crashes the watcher pipeline. The first 16 hex chars of the
    SHA-256 are plenty of entropy for per-rule dedup.
    """
    try:
        canonical = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), default=str
        )
    except (TypeError, ValueError):
        canonical = repr(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


@dataclass
class RuleHistory:
    """Bookkeeping for one watcher rule."""

    last_fired_at: float | None = None
    last_payload_key: str | None = None
    last_priority: float | None = None
    total_fires: int = 0
    total_suppressed: int = 0
    last_suppressed_reason: str | None = None
    suppressed_by_reason: dict[str, int] = field(default_factory=dict)


class WatcherHistory:
    """Per-rule cooldown + payload-dedup state for a WatcherRegistry.

    ``default_cooldown_s`` is the fallback for rules that declare no
    cooldown of their own (``cooldown_s == 0``). With the default of 0.0,
    attaching a history changes no firing behavior — it only records
    statistics — which keeps the integration backward compatible.
    """

    def __init__(self, default_cooldown_s: float = 0.0) -> None:
        """Initialize empty history; ``default_cooldown_s`` must be >= 0."""
        if default_cooldown_s < 0:
            raise ValueError("default_cooldown_s must be >= 0")
        self.default_cooldown_s = float(default_cooldown_s)
        self._rules: dict[str, RuleHistory] = {}

    # ------------------------------------------------------------------ #
    # Decision
    # ------------------------------------------------------------------ #
    def should_fire(
        self,
        rule_id: str,
        now: float,
        cooldown_s: float,
        payload: Any,
    ) -> tuple[bool, str | None]:
        """Decide whether ``rule_id`` may fire at ``now``.

        Returns ``(allowed, reason)`` where ``reason`` is ``None`` when the
        fire is allowed, or one of :data:`REASON_COOLDOWN` /
        :data:`REASON_DUPLICATE` when it is suppressed. This method is pure
        — it never mutates state — so the registry pairs it with an
        explicit :meth:`record` (fire) or :meth:`mark_suppressed` call.

        ``cooldown_s`` is the rule's own cooldown; when it is 0 the
        history's ``default_cooldown_s`` applies. An effective cooldown of
        0 means no suppression at all.
        """
        rec = self._rules.get(rule_id)
        if rec is None or rec.last_fired_at is None:
            return True, None
        effective = cooldown_s if cooldown_s > 0 else self.default_cooldown_s
        if effective <= 0:
            return True, None
        elapsed = now - rec.last_fired_at
        if elapsed >= effective:
            return True, None
        if payload_key(payload) == rec.last_payload_key:
            return False, REASON_DUPLICATE
        return False, REASON_COOLDOWN

    # ------------------------------------------------------------------ #
    # Bookkeeping
    # ------------------------------------------------------------------ #
    def record(
        self, rule_id: str, now: float, payload: Any, priority: float
    ) -> None:
        """Note that ``rule_id`` fired at ``now`` with ``payload``."""
        rec = self._rules.setdefault(rule_id, RuleHistory())
        rec.last_fired_at = float(now)
        rec.last_payload_key = payload_key(payload)
        rec.last_priority = float(priority)
        rec.total_fires += 1

    def mark_suppressed(self, rule_id: str, reason: str) -> None:
        """Note that a firing of ``rule_id`` was suppressed for ``reason``."""
        rec = self._rules.setdefault(rule_id, RuleHistory())
        rec.total_suppressed += 1
        rec.last_suppressed_reason = reason
        rec.suppressed_by_reason[reason] = (
            rec.suppressed_by_reason.get(reason, 0) + 1
        )

    def reset(self, rule_id: str | None = None) -> None:
        """Clear state for one rule, or everything when ``rule_id`` is None."""
        if rule_id is None:
            self._rules.clear()
        else:
            self._rules.pop(rule_id, None)

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #
    def get_stats(self) -> dict[str, Any]:
        """Snapshot of aggregate and per-rule counters (JSON-friendly)."""
        rules = {
            rid: {
                "total_fires": rec.total_fires,
                "total_suppressed": rec.total_suppressed,
                "last_fired_at": rec.last_fired_at,
                "last_payload_key": rec.last_payload_key,
                "last_priority": rec.last_priority,
                "last_suppressed_reason": rec.last_suppressed_reason,
                "suppressed_by_reason": dict(rec.suppressed_by_reason),
            }
            for rid, rec in self._rules.items()
        }
        return {
            "default_cooldown_s": self.default_cooldown_s,
            "total_fires": sum(r.total_fires for r in self._rules.values()),
            "total_suppressed": sum(
                r.total_suppressed for r in self._rules.values()
            ),
            "rules": rules,
        }
