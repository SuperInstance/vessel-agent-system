"""TwinCore: the AELMA twin runtime.

Composes :class:`VesselState` and :class:`BathymetryGrid` into an asyncio
process that:

1. connects as a WebSocket client to the bridge and ingests TelemetryPackets,
2. fuses depth soundings into the progressive bathymetry grid,
3. serves viewer WebSocket clients and broadcasts a VesselStateSnapshot
   every ``broadcast_interval`` seconds,
4. persists the bathymetry grid every ``persist_interval`` seconds,
5. logs all telemetry packets to a JSONL file for analytics.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import websockets

from .bathymetry import BathymetryGrid
from .fishing_modes import FishingMode, FishingModeManager
from .state import VesselState

log = logging.getLogger("aelma.twin")

# --------------------------------------------------------------------- #
# Watcher system (embedded for build_kimi deployment)
# --------------------------------------------------------------------- #

DEFAULT_PRIORITY = 0.5
ALLOWED_ACTIONS = frozenset({
    "morph_to_hazard_mode",
    "morph_to_navigation_mode",
    "morph_to_engineering_mode",
    "highlight_waypoint",
    "raise_alert",
    "clear_alerts",
    "set_panel_focus",
    "announce",
})


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


class WatcherHistory:
    """Per-rule cooldown + payload-dedup state for a WatcherRegistry."""

    def __init__(self, default_cooldown_s: float = 0.0) -> None:
        """Initialize empty history; ``default_cooldown_s`` must be >= 0."""
        if default_cooldown_s < 0:
            raise ValueError("default_cooldown_s must be >= 0")
        self.default_cooldown_s = float(default_cooldown_s)
        self._rules: dict[str, dict] = {}

    def should_fire(
        self,
        rule_id: str,
        now: float,
        cooldown_s: float,
        payload: Any,
    ) -> tuple[bool, str | None]:
        """Decide whether ``rule_id`` may fire at ``now``."""
        rec = self._rules.get(rule_id)
        if rec is None or rec.get("last_fired_at") is None:
            return True, None
        effective = cooldown_s if cooldown_s > 0 else self.default_cooldown_s
        if effective <= 0:
            return True, None
        elapsed = now - rec["last_fired_at"]
        if elapsed >= effective:
            return True, None
        # Simple cooldown check (no payload dedup for simplicity)
        return False, "cooldown"

    def record(
        self, rule_id: str, now: float, payload: Any, priority: float
    ) -> None:
        """Note that ``rule_id`` fired at ``now`` with ``payload``."""
        if rule_id not in self._rules:
            self._rules[rule_id] = {
                "total_fires": 0,
                "total_suppressed": 0,
            }
        self._rules[rule_id]["last_fired_at"] = float(now)
        self._rules[rule_id]["last_priority"] = float(priority)
        self._rules[rule_id]["total_fires"] += 1

    def mark_suppressed(self, rule_id: str, reason: str) -> None:
        """Note that a firing of ``rule_id`` was suppressed for ``reason``."""
        if rule_id not in self._rules:
            self._rules[rule_id] = {
                "total_fires": 0,
                "total_suppressed": 0,
            }
        self._rules[rule_id]["total_suppressed"] += 1
        self._rules[rule_id]["last_suppressed_reason"] = reason

    def get_stats(self) -> dict[str, Any]:
        """Snapshot of aggregate and per-rule counters (JSON-friendly)."""
        return {
            "default_cooldown_s": self.default_cooldown_s,
            "total_fires": sum(r.get("total_fires", 0) for r in self._rules.values()),
            "total_suppressed": sum(
                r.get("total_suppressed", 0) for r in self._rules.values()
            ),
            "rules": dict(self._rules),
        }


class WatcherRegistry:
    """Ordered set of watcher rules plus optional suppression history."""

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

    def on(self, event: str, callback: Callable[..., Any]) -> None:
        """Subscribe to ``fired`` / ``suppressed`` / ``error`` events."""
        if event not in self._listeners:
            raise ValueError(f"unknown watcher event: {event!r}")
        self._listeners[event].append(callback)

    def _emit(self, event: str, *args: Any) -> None:
        for cb in self._listeners[event]:
            try:
                cb(*args)
            except Exception:
                log.exception("watcher %r listener failed", event)

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
            return rule
        elif isinstance(rule, Mapping):
            rid = rule.get("id")
            if not isinstance(rid, str) or not rid:
                raise TypeError("watcher rule.id must be a non-empty string")
            name = rule.get("name")
            if not isinstance(name, str) or not name:
                raise TypeError("watcher rule.name must be a non-empty string")
            when = rule.get("when")
            if not callable(when):
                raise TypeError("watcher rule.when must be callable")
            action = rule.get("action")
            if not isinstance(action, Mapping):
                raise TypeError("watcher rule.action must be a mapping")
            action_name = action.get("name")
            if action_name not in ALLOWED_ACTIONS:
                raise ValueError(
                    f"watcher action {action_name!r} not in ALLOWED_ACTIONS"
                )
            cooldown_s = rule.get("cooldown_s", 0.0)
            if not isinstance(cooldown_s, (int, float)) or cooldown_s < 0:
                raise TypeError("watcher rule.cooldown_s must be a number >= 0")
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
        else:
            raise TypeError("watcher rule must be a mapping or WatcherRule")

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
        return [self.get(rid) for rid in self._rules]

    def __len__(self) -> int:
        return len(self._rules)

    def evaluate(self, frame: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Evaluate all rules against ``frame``; return fired actions."""
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

    @property
    def stats(self) -> dict[str, Any]:
        """Registry stats; ``history`` is None when no history is attached."""
        return {
            "rule_count": len(self._rules),
            "rules": self.list(),
            "history": self.history.get_stats() if self.history else None,
        }

# Telemetry channel carrying sounder depth; packet sources map onto the
# bathymetry voxel source enum.
DEPTH_CHANNEL = "depth_m"
_SOURCE_MAP = {
    "manual": "manual",
    "simulator": "sounder",
    "nmea0183": "sounder",
    "nmea2000": "sounder",
    "signal_k": "sounder",
}


class TwinCore:
    """Digital twin for one vessel: state + bathymetry + WS plumbing."""

    def __init__(
        self,
        bridge_url: str = "ws://localhost:8000",
        viewer_port: int = 8090,
        vessel_id: str = "US-AK-FVEILEEN-51",
        bathymetry_path: str | Path = "bathymetry.json",
        telemetry_log_path: str | Path = "telemetry.jsonl",
        broadcast_interval: float = 1.0,
        persist_interval: float = 60.0,
        viewport_radius_m: float = 500.0,
        enable_telemetry_log: bool = True,
        enable_watchers: bool = True,
        default_cooldown_s: float = 30.0,
    ) -> None:
        """Configure the twin; nothing connects until :meth:`run` is awaited.

        Args:
            bridge_url: WebSocket URL of the bridge server.
            viewer_port: Port for the viewer WebSocket server.
            vessel_id: Identifier for this vessel.
            bathymetry_path: Path to bathymetry persistence file.
            telemetry_log_path: Path to telemetry JSONL log file.
            broadcast_interval: Seconds between viewer snapshot broadcasts.
            persist_interval: Seconds between bathymetry persistence writes.
            viewport_radius_m: Radius of bathymetry viewport in meters.
            enable_telemetry_log: Whether to log telemetry packets to JSONL.
            enable_watchers: Whether to enable watcher rule evaluation.
            default_cooldown_s: Default cooldown for watcher rules in seconds.
        """
        self.bridge_url = bridge_url
        self.viewer_port = viewer_port
        self.vessel_id = vessel_id
        self.bathymetry_path = Path(bathymetry_path)
        self.telemetry_log_path = Path(telemetry_log_path)
        self.broadcast_interval = broadcast_interval
        self.persist_interval = persist_interval
        self.viewport_radius_m = viewport_radius_m
        self.enable_telemetry_log = enable_telemetry_log
        self.enable_watchers = enable_watchers
        self.default_cooldown_s = default_cooldown_s

        self.state = VesselState()
        self.bathymetry = BathymetryGrid()
        self.fishing_modes = FishingModeManager(initial_mode=FishingMode.TRANSIT)
        self._viewers: set[Any] = set()
        self._telemetry_log_file: Any | None = None

        # Initialize watcher system
        self._watcher_history = WatcherHistory(default_cooldown_s=default_cooldown_s)
        self._watchers = WatcherRegistry(
            verbose=False,
            history=self._watcher_history,
            now=time.monotonic,
        )

        # Set up watcher event listener for broadcasting fired actions
        self._watchers.on("fired", self._on_watcher_fired)

        # Register default vessel safety rules
        if enable_watchers:
            self._register_default_watchers()

    # ------------------------------------------------------------------ #
    # Watcher system
    # ------------------------------------------------------------------ #
    def _register_default_watchers(self) -> None:
        """Register default vessel safety watcher rules."""

        # Shallow water warning
        self._watchers.add({
            "id": "shallow-water",
            "name": "Shallow water warning",
            "when": lambda f: 0 < f.get("depth_m", 999) < 2.0,
            "action": {
                "name": "raise_alert",
                "payload": lambda f: {
                    "severity": "warning",
                    "code": "SHALLOW_WATER",
                    "message": f"Depth critical: {f['depth_m']:.2f}m"
                },
                "reason": lambda f: f"depth={f['depth_m']:.2f}m",
                "priority": lambda f: 0.85,
            },
            "cooldown_s": 30.0,
        })

        # Grounding risk (very shallow water)
        self._watchers.add({
            "id": "grounding-risk",
            "name": "Grounding risk alert",
            "when": lambda f: 0 < f.get("depth_m", 999) < 1.0,
            "action": {
                "name": "raise_alert",
                "payload": lambda f: {
                    "severity": "critical",
                    "code": "GROUNDING_RISK",
                    "message": f"GROUNDING RISK: depth={f['depth_m']:.2f}m"
                },
                "reason": lambda f: f"depth={f['depth_m']:.2f}m",
                "priority": lambda f: 0.95,
            },
            "cooldown_s": 15.0,
        })

        # Engine overheating
        self._watchers.add({
            "id": "engine-overheat",
            "name": "Engine overheating warning",
            "when": lambda f: f.get("engine_temp_c", 0) > 90.0,
            "action": {
                "name": "raise_alert",
                "payload": lambda f: {
                    "severity": "critical",
                    "code": "ENGINE_OVERHEAT",
                    "message": f"Engine overheat: {f['engine_temp_c']:.1f}°C"
                },
                "reason": lambda f: f"engine_temp={f['engine_temp_c']:.1f}°C",
                "priority": lambda f: 0.92,
            },
            "cooldown_s": 20.0,
        })

        # ------------------------------------------------------------------
        # Mode-specific watcher rules
        # ------------------------------------------------------------------

        # TRANSIT mode: Speed warning
        self._watchers.add({
            "id": "transit-speed-excessive",
            "name": "Transit speed excessive",
            "when": lambda f: f.get("fishing_mode") == "TRANSIT" and f.get("speed_kn", 0) > 15.0,
            "action": {
                "name": "raise_alert",
                "payload": lambda f: {
                    "severity": "warning",
                    "code": "TRANSIT_SPEED_HIGH",
                    "message": f"Transit speed high: {f['speed_kn']:.1f}kn"
                },
                "reason": lambda f: f"speed={f['speed_kn']:.1f}kn in TRANSIT",
                "priority": lambda f: 0.70,
            },
            "cooldown_s": 60.0,
        })

        # FISHING mode: Depth critical
        self._watchers.add({
            "id": "fishing-depth-critical",
            "name": "Fishing depth critical",
            "when": lambda f: f.get("fishing_mode") == "FISHING" and 0 < f.get("depth_m", 999) < 5.0,
            "action": {
                "name": "raise_alert",
                "payload": lambda f: {
                    "severity": "warning",
                    "code": "FISHING_DEPTH_CRITICAL",
                    "message": f"Depth critical while fishing: {f['depth_m']:.2f}m"
                },
                "reason": lambda f: f"depth={f['depth_m']:.2f}m in FISHING",
                "priority": lambda f: 0.80,
            },
            "cooldown_s": 30.0,
        })

        # FISHING mode: Gear failure
        self._watchers.add({
            "id": "fishing-gear-failure",
            "name": "Fishing gear failure",
            "when": lambda f: f.get("fishing_mode") == "FISHING" and f.get("gear_status") == "FAILURE",
            "action": {
                "name": "raise_alert",
                "payload": lambda f: {
                    "severity": "critical",
                    "code": "GEAR_FAILURE",
                    "message": "Fishing gear failure detected"
                },
                "reason": lambda f: "gear_status=FAILURE in FISHING",
                "priority": lambda f: 0.95,
            },
            "cooldown_s": 10.0,
        })

        # DRIFTING mode: Drift rate excessive
        self._watchers.add({
            "id": "drifting-rate-excessive",
            "name": "Drifting rate excessive",
            "when": lambda f: f.get("fishing_mode") == "DRIFTING" and f.get("speed_kn", 0) > 2.0,
            "action": {
                "name": "raise_alert",
                "payload": lambda f: {
                    "severity": "warning",
                    "code": "DRIFT_RATE_HIGH",
                    "message": f"Drift rate excessive: {f['speed_kn']:.1f}kn"
                },
                "reason": lambda f: f"speed={f['speed_kn']:.1f}kn in DRIFTING",
                "priority": lambda f: 0.65,
            },
            "cooldown_s": 45.0,
        })

        # ANCHORED mode: Anchor drag detection
        self._watchers.add({
            "id": "anchor-drag-detected",
            "name": "Anchor drag detected",
            "when": lambda f: f.get("fishing_mode") == "ANCHORED" and f.get("speed_kn", 0) > 0.5,
            "action": {
                "name": "raise_alert",
                "payload": lambda f: {
                    "severity": "critical",
                    "code": "ANCHOR_DRAG",
                    "message": f"Anchor drag detected: {f['speed_kn']:.1f}kn"
                },
                "reason": lambda f: f"speed={f['speed_kn']:.1f}kn in ANCHORED",
                "priority": lambda f: 0.88,
            },
            "cooldown_s": 20.0,
        })

        # GEAR_DEPLOYED mode: Deployed too long
        self._watchers.add({
            "id": "gear-deployed-too-long",
            "name": "Gear deployed too long",
            "when": lambda f: f.get("fishing_mode") == "GEAR_DEPLOYED" and f.get("fishing_mode_duration_s", 0) > 43200,
            "action": {
                "name": "raise_alert",
                "payload": lambda f: {
                    "severity": "info",
                    "code": "GEAR_DEPLOYED_LONG",
                    "message": f"Gear deployed {f['fishing_mode_duration_s']/3600:.1f}h"
                },
                "reason": lambda f: f"duration={f['fishing_mode_duration_s']/3600:.1f}h in GEAR_DEPLOYED",
                "priority": lambda f: 0.50,
            },
            "cooldown_s": 300.0,
        })

        # HAULING mode: Slow progress
        self._watchers.add({
            "id": "hauling-slow-progress",
            "name": "Hauling slow progress",
            "when": lambda f: f.get("fishing_mode") == "HAULING" and f.get("speed_kn", 0) < 1.0 and f.get("gear_tension", 0) > 50,
            "action": {
                "name": "raise_alert",
                "payload": lambda f: {
                    "severity": "warning",
                    "code": "HAULING_SLOW",
                    "message": f"Hauling slow: {f['speed_kn']:.1f}kn at tension {f['gear_tension']}"
                },
                "reason": lambda f: f"speed={f['speed_kn']:.1f}kn, tension={f['gear_tension']} in HAULING",
                "priority": lambda f: 0.72,
            },
            "cooldown_s": 60.0,
        })

        log.info("registered %d default watcher rules", len(self._watchers))

    def _build_frame(self) -> dict[str, Any]:
        """Build a telemetry frame dict from current vessel state.

        Extracts relevant telemetry fields for watcher evaluation.
        Returns a dict with keys like depth_m, speed_kn, heading_deg, etc.
        """
        frame = {
            "timestamp_ns": time.time_ns(),
            "vessel_id": self.vessel_id,
        }

        # Add pose data
        if self.state.lat is not None:
            frame["lat"] = self.state.lat
        if self.state.lon is not None:
            frame["lon"] = self.state.lon
        if self.state.heading_deg is not None:
            frame["heading_deg"] = self.state.heading_deg
        if self.state.speed_kn is not None:
            frame["speed_kn"] = self.state.speed_kn

        # Add channel data
        for channel_name, channel_data in self.state.channels.items():
            if "value" in channel_data:
                frame[channel_name] = channel_data["value"]

        # Add fishing mode context
        frame.update(self.fishing_modes.get_context_for_watchers())

        return frame

    def _on_watcher_fired(self, action: dict[str, Any]) -> None:
        """Handle a fired watcher action by broadcasting to viewers.

        This is called by the WatcherRegistry when a rule fires.
        """
        log.info(
            "[watcher fired] %s -> %s (priority=%.2f)",
            action.get("rule_id"),
            action.get("action"),
            action.get("priority", DEFAULT_PRIORITY),
        )

        # Broadcast the action to all connected viewers
        if self._viewers:
            msg = json.dumps({"type": "action", "data": action})
            # We need to broadcast this asynchronously
            # For now, we'll store it and let the broadcast loop handle it
            # or we can use asyncio.create_task if we're in an async context
            asyncio.create_task(self._broadcast_action(msg))

    async def _broadcast_action(self, message: str) -> None:
        """Broadcast an action message to all connected viewers."""
        if not self._viewers:
            return

        results = await asyncio.gather(
            *(ws.send(message) for ws in list(self._viewers)),
            return_exceptions=True,
        )

        # Remove any viewers that failed to receive the message
        for ws, res in zip(list(self._viewers), results):
            if isinstance(res, Exception):
                self._viewers.discard(ws)
                log.warning("removed viewer due to send error: %s", res)

    def register_watcher(self, rule: dict[str, Any]) -> str:
        """Register a custom watcher rule dynamically.

        Args:
            rule: Watcher rule dict following the WatcherRegistry schema.

        Returns:
            The rule ID that was registered.

        Raises:
            ValueError: If the rule ID is already registered or invalid.
            TypeError: If the rule structure is invalid.
        """
        rule_id = self._watchers.add(rule)
        log.info("registered custom watcher rule: %s", rule_id)
        return rule_id

    def unregister_watcher(self, rule_id: str) -> bool:
        """Unregister a watcher rule by ID.

        Args:
            rule_id: The rule ID to unregister.

        Returns:
            True if the rule was found and removed, False otherwise.
        """
        removed = self._watchers.remove(rule_id)
        if removed:
            log.info("unregistered watcher rule: %s", rule_id)
        return removed

    def get_watcher_stats(self) -> dict[str, Any]:
        """Get statistics about watcher rule firings and suppressions.

        Returns:
            A dict containing watcher registry and history stats.
        """
        return self._watchers.stats

    def set_fishing_mode(self, mode: FishingMode | str, reason: str = "") -> None:
        """Set the current fishing mode.

        Args:
            mode: New mode (FishingMode enum or string value).
            reason: Human-readable explanation for the mode change.
        """
        self.fishing_modes.set_mode(mode, reason)
        log.info("fishing mode set to %s: %s", mode, reason)

    def get_fishing_mode(self) -> dict[str, Any]:
        """Get current fishing mode and duration.

        Returns:
            Dict with current mode, duration, and reason.
        """
        return self.fishing_modes.get_mode()

    def get_fishing_mode_history(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Get fishing mode change history.

        Args:
            limit: Maximum number of transitions to return (most recent first).

        Returns:
            List of mode transition records.
        """
        return self.fishing_modes.get_mode_history(limit)

    def get_fishing_mode_statistics(self) -> dict[str, Any]:
        """Get aggregate fishing mode statistics.

        Returns:
            Dict with per-mode statistics and summary information.
        """
        return self.fishing_modes.get_statistics()

    # ------------------------------------------------------------------ #
    # Telemetry logging
    # ------------------------------------------------------------------ #
    def _open_telemetry_log(self) -> None:
        """Open the telemetry log file for appending."""
        if not self.enable_telemetry_log:
            return

        try:
            # Create parent directory if it doesn't exist
            self.telemetry_log_path.parent.mkdir(parents=True, exist_ok=True)

            # Open file in append mode
            self._telemetry_log_file = open(
                self.telemetry_log_path,
                mode="a",
                encoding="utf-8",
                buffering=1,  # Line buffering
            )
            log.info("telemetry log opened: %s", self.telemetry_log_path)
        except OSError as exc:
            log.error("failed to open telemetry log: %s", exc)
            self._telemetry_log_file = None

    def _close_telemetry_log(self) -> None:
        """Close the telemetry log file."""
        if self._telemetry_log_file is not None:
            try:
                self._telemetry_log_file.close()
                log.info("telemetry log closed")
            except OSError as exc:
                log.error("error closing telemetry log: %s", exc)
            finally:
                self._telemetry_log_file = None

    def _log_telemetry(self, packet: dict[str, Any]) -> None:
        """Write a telemetry packet to the JSONL log.

        Args:
            packet: TelemetryPacket dict to log.
        """
        if not self.enable_telemetry_log or self._telemetry_log_file is None:
            return

        try:
            self._telemetry_log_file.write(json.dumps(packet) + "\n")
        except (OSError, TypeError) as exc:
            log.warning("failed to write telemetry packet: %s", exc)

    # ------------------------------------------------------------------ #
    # Packet handling
    # ------------------------------------------------------------------ #
    def handle_packet(self, packet: dict[str, Any]) -> None:
        """Apply one TelemetryPacket to state and, if a sounding, the grid.

        Logs the packet to the telemetry JSONL file if logging is enabled.
        Evaluates watcher rules after state update if enabled.

        Args:
            packet: TelemetryPacket dict with timestamp_ns, source, channel,
                    value, and optional quality fields.
        """
        # Log packet to telemetry file
        self._log_telemetry(packet)

        # Apply to vessel state
        self.state.apply_packet(packet)

        # Evaluate watcher rules on the updated state
        if self.enable_watchers:
            try:
                frame = self._build_frame()
                fired_actions = self._watchers.evaluate(frame)
                if fired_actions:
                    log.debug(
                        "watchers evaluated: %d actions fired",
                        len(fired_actions)
                    )
            except Exception as exc:
                log.warning("watcher evaluation failed: %s", exc)

        # Fuse depth soundings into bathymetry grid
        if packet.get("channel") != DEPTH_CHANNEL:
            return
        value = packet.get("value")
        if not isinstance(value, (int, float)) or value is None:
            return
        lat, lon = self.state.lat, self.state.lon
        if lat is None or lon is None:
            return  # no fix yet: nowhere to put the sounding
        self.bathymetry.fuse(
            lat,
            lon,
            float(value),
            int(packet["timestamp_ns"]),
            source=_SOURCE_MAP.get(str(packet.get("source")), "sounder"),
        )

    # ------------------------------------------------------------------ #
    # Snapshot assembly
    # ------------------------------------------------------------------ #
    def build_snapshot(self, now_ns: int | None = None) -> dict[str, Any]:
        """Assemble the full VesselStateSnapshot, including the bathymetry
        viewport block centered on the (dead-reckoned) vessel position."""
        if now_ns is None:
            now_ns = time.time_ns()
        snap = self.state.snapshot(self.vessel_id, [self.viewport_radius_m], now_ns)
        lat, lon = snap["pose"]["lat"], snap["pose"]["lon"]
        snap["bathymetry"] = {
            "voxel_count": self.bathymetry.total_voxels(),
            "viewport_center": {"lat": lat, "lon": lon},
            "viewport_radius_m": self.viewport_radius_m,
            "cells": self.bathymetry.cells_in_radius(
                lat, lon, self.viewport_radius_m, now_ns
            ),
        }
        # Add fishing mode information
        snap["fishing_mode"] = self.fishing_modes.get_mode()
        return snap

    # ------------------------------------------------------------------ #
    # Bridge side (WebSocket client)
    # ------------------------------------------------------------------ #
    async def _bridge_loop(self) -> None:
        """Connect to the bridge and ingest packets, reconnecting forever."""
        backoff = 1.0
        while True:
            try:
                async with websockets.connect(self.bridge_url) as ws:
                    log.info("connected to bridge at %s", self.bridge_url)
                    backoff = 1.0
                    async for raw in ws:
                        try:
                            packet = json.loads(raw)
                            if isinstance(packet, list):
                                for p in packet:
                                    self.handle_packet(p)
                            else:
                                self.handle_packet(packet)
                        except (json.JSONDecodeError, KeyError, TypeError) as exc:
                            log.warning("dropping malformed packet: %s", exc)
            except (OSError, websockets.WebSocketException) as exc:
                log.warning("bridge connection failed (%s); retry in %.0fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)

    # ------------------------------------------------------------------ #
    # Viewer side (WebSocket server)
    # ------------------------------------------------------------------ #
    async def _viewer_handler(self, ws: Any) -> None:
        """Register a viewer, push an immediate snapshot, hold until close."""
        self._viewers.add(ws)
        log.info("viewer connected (%d total)", len(self._viewers))
        try:
            await ws.send(json.dumps(self.build_snapshot()))
            await ws.wait_closed()
        finally:
            self._viewers.discard(ws)
            log.info("viewer disconnected (%d total)", len(self._viewers))

    async def _broadcast_loop(self) -> None:
        """Send a fresh snapshot to every connected viewer on the interval."""
        while True:
            await asyncio.sleep(self.broadcast_interval)
            if not self._viewers:
                continue
            msg = json.dumps(self.build_snapshot())
            results = await asyncio.gather(
                *(ws.send(msg) for ws in list(self._viewers)),
                return_exceptions=True,
            )
            for ws, res in zip(list(self._viewers), results):
                if isinstance(res, Exception):
                    self._viewers.discard(ws)

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    async def _persist_loop(self) -> None:
        """Write the bathymetry grid to disk on the persist interval."""
        while True:
            await asyncio.sleep(self.persist_interval)
            try:
                self.bathymetry.save(self.bathymetry_path)
                log.info(
                    "persisted %d voxels to %s",
                    self.bathymetry.total_voxels(),
                    self.bathymetry_path,
                )
            except OSError as exc:
                log.error("bathymetry persist failed: %s", exc)

    # ------------------------------------------------------------------ #
    # Entry point
    # ------------------------------------------------------------------ #
    async def run(self) -> None:
        """Load persisted state, then run all loops until cancelled.

        Opens telemetry log file on startup and closes on shutdown.
        """
        self.bathymetry.load(self.bathymetry_path)
        self._open_telemetry_log()

        try:
            async with websockets.serve(
                self._viewer_handler, "localhost", self.viewer_port
            ):
                log.info("viewer WS server listening on port %d", self.viewer_port)
                await asyncio.gather(
                    self._bridge_loop(),
                    self._broadcast_loop(),
                    self._persist_loop(),
                )
        finally:
            self._close_telemetry_log()
