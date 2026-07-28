"""Example AELMA plugin: depth-anomaly detection.

Watches ``depth_m`` telemetry packets and emits a ``raise_alert`` action
when the seabed depth changes faster than a configured rate — a sign of
a sudden shoal, a sounder glitch, or a fish-school false bottom.

Config keys (passed via ``init``):

* ``max_rate_m_per_s`` — maximum plausible depth change rate (default 1.0).
* ``min_depth_m`` — ignore readings shallower than this (default 0.5),
  which filters transducer noise at the surface.

No core-code changes are needed: drop this file into ``plugins/`` and the
:class:`~twin.plugins.PluginManager` picks it up on the next start.
"""

from __future__ import annotations

from typing import Any

from twin.plugins import Plugin


class DepthAnomalyPlugin(Plugin):
    """Emit an alert when depth changes implausibly fast."""

    name = "depth_anomaly"
    version = "1.0.0"
    description = "Alert on sudden depth changes (shoal or sounder glitch)."

    def init(self, config: dict[str, Any]) -> None:
        self.max_rate = float(config.get("max_rate_m_per_s", 1.0))
        self.min_depth = float(config.get("min_depth_m", 0.5))
        self._last_depth: float | None = None
        self._last_ts_ns: int | None = None

    def on_packet(self, packet: dict[str, Any]) -> None:
        if packet.get("channel") != "depth_m":
            return
        value = packet.get("value")
        ts_ns = packet.get("timestamp_ns")
        if not isinstance(value, (int, float)) or not isinstance(ts_ns, int):
            return
        depth = float(value)
        if depth < self.min_depth:
            return  # surface noise; also leaves the baseline untouched
        if self._last_depth is not None and self._last_ts_ns is not None:
            dt_s = (ts_ns - self._last_ts_ns) / 1e9
            if dt_s > 0:
                rate = abs(depth - self._last_depth) / dt_s
                if rate > self.max_rate:
                    self.context.emit_action(
                        "raise_alert",
                        {
                            "kind": "depth_anomaly",
                            "depth_m": depth,
                            "previous_depth_m": self._last_depth,
                            "rate_m_per_s": round(rate, 3),
                        },
                        reason=(
                            f"depth changed {self._last_depth:.1f}m -> "
                            f"{depth:.1f}m in {dt_s:.1f}s "
                            f"({rate:.2f} m/s > {self.max_rate} m/s)"
                        ),
                        priority=0.8,
                    )
        self._last_depth = depth
        self._last_ts_ns = ts_ns

    def shutdown(self) -> None:
        self._last_depth = None
        self._last_ts_ns = None
