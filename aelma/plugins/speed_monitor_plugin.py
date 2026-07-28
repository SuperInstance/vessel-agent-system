"""Example AELMA plugin: vessel speed monitoring.

Watches ``speed_kn`` telemetry packets and emits a ``raise_alert`` action
when the vessel exceeds a configured speed limit — useful for no-wake
zones or harbor speed restrictions. The alert fires once per threshold
crossing (rising edge) and arms again only after speed drops back below
``reset_kn``, so a vessel hovering at the limit does not spam the log.

Config keys (passed via ``init``):

* ``max_speed_kn`` — speed limit that triggers the alert (default 15.0).
* ``reset_kn`` — speed must fall below this to re-arm (default: 90% of
  ``max_speed_kn``).
"""

from __future__ import annotations

from typing import Any

from twin.plugins import Plugin


class SpeedMonitorPlugin(Plugin):
    """Emit an alert when speed exceeds a configured limit."""

    name = "speed_monitor"
    version = "1.0.0"
    description = "Alert when vessel speed exceeds a configured limit."

    def init(self, config: dict[str, Any]) -> None:
        self.max_speed = float(config.get("max_speed_kn", 15.0))
        self.reset_speed = float(config.get("reset_kn", self.max_speed * 0.9))
        self._alarming = False

    def on_packet(self, packet: dict[str, Any]) -> None:
        if packet.get("channel") != "speed_kn":
            return
        value = packet.get("value")
        if not isinstance(value, (int, float)):
            return
        speed = float(value)
        if speed > self.max_speed and not self._alarming:
            self._alarming = True
            self.context.emit_action(
                "raise_alert",
                {"kind": "speed_limit", "speed_kn": speed, "limit_kn": self.max_speed},
                reason=f"speed {speed:.1f} kn exceeds limit {self.max_speed:.1f} kn",
                priority=0.7,
            )
        elif speed < self.reset_speed:
            self._alarming = False

    def on_action(self, record: dict[str, Any]) -> None:
        # Acknowledge an operator action: a logged "reduce_speed" command
        # clears the alarm state so a fresh violation re-alerts.
        if record.get("action") == "reduce_speed":
            self._alarming = False

    def shutdown(self) -> None:
        self._alarming = False
