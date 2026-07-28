"""NotificationManager: outbound alerts from the twin to external systems.

Watchers and anomaly detectors inside the twin are silent by design —
they surface actions to the viewer over the local WebSocket. This module
is the *external* escape hatch: it pushes alerts to channels the crew
actually watches (email, generic webhooks, SMS via Twilio, Slack) with
three guards so a flapping sensor cannot spam the wheelhouse:

* **Severity filtering** — each channel declares a minimum severity;
  notifications below it are dropped before any network I/O.
* **Rate limiting** — a per-channel sliding window caps how many
  notifications per minute actually leave the process.
* **Retry logic** — transient delivery failures are retried with
  exponential backoff before the send is declared failed.

Channels are plain registrations on a manager::

    mgr = NotificationManager()
    mgr.register_channel(
        "ops-slack", "slack",
        config={"webhook_url": "https://hooks.slack.com/services/..."},
        min_severity="warning",
    )
    mgr.send_notification("ops-slack", "depth=1.2m", severity="critical")

Watcher integration (auto-send critical alerts)::

    mgr.attach_to_watchers(registry, min_priority=0.9)

subscribes to the registry's ``fired`` event; any ``raise_alert`` action
whose priority clears the threshold is broadcast to every channel that
accepts ``critical`` severity.

All network delivery goes through injectable sender callables (one per
channel kind) so tests never touch the network, and the clock/sleep are
injectable for deterministic rate-limit and retry tests. The default
senders use only the standard library (``smtplib``, ``urllib.request``);
Twilio is spoken to over its REST API, so no third-party SDK is needed.
"""

from __future__ import annotations

import base64
import json
import logging
import smtplib
import time
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Any

log = logging.getLogger("aelma.twin.notifications")

# --------------------------------------------------------------------- #
# Severity
# --------------------------------------------------------------------- #

#: Severity ranking. Numeric so comparisons and filters stay trivial.
SEVERITY_LEVELS: dict[str, int] = {"info": 0, "warning": 1, "critical": 2}

DEFAULT_SEVERITY = "info"


def normalize_severity(severity: str) -> str:
    """Validate and normalize a severity label."""
    if not isinstance(severity, str):
        raise TypeError("severity must be a string")
    sev = severity.lower().strip()
    if sev not in SEVERITY_LEVELS:
        raise ValueError(
            f"unknown severity {severity!r}; expected one of {sorted(SEVERITY_LEVELS)}"
        )
    return sev


# --------------------------------------------------------------------- #
# Channel model
# --------------------------------------------------------------------- #

#: Channel kinds the manager knows how to deliver to.
CHANNEL_KINDS = frozenset({"email", "webhook", "sms", "slack"})


@dataclass(frozen=True)
class NotificationChannel:
    """A registered delivery target.

    ``min_severity`` gates filtering; ``rate_limit_per_minute`` gates
    throughput. ``config`` is kind-specific (see the default senders).
    """

    name: str
    kind: str
    config: Mapping[str, Any] = field(default_factory=dict)
    min_severity: str = DEFAULT_SEVERITY
    rate_limit_per_minute: float = 30.0


#: Sender signature: (channel config, payload) -> None; raise on failure.
#: ``payload`` is the dict built by :meth:`NotificationManager._build_payload`.
Sender = Callable[[Mapping[str, Any], Mapping[str, Any]], None]


# --------------------------------------------------------------------- #
# Default senders (stdlib only)
# --------------------------------------------------------------------- #

_HTTP_TIMEOUT_S = 10.0


def _http_post(url: str, body: bytes, headers: dict[str, str]) -> None:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_S) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"HTTP {resp.status} from {url}")


def send_email(config: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
    """Deliver via SMTP. Config: smtp_host, smtp_port, from_addr, to_addrs,
    optional username/password, use_tls (default True)."""
    msg = EmailMessage()
    msg["From"] = config["from_addr"]
    msg["To"] = ", ".join(config["to_addrs"])
    msg["Subject"] = f"[AELMA:{payload['severity']}] {payload['title']}"
    msg.set_content(json.dumps(payload, indent=2, default=str))

    port = int(config.get("smtp_port", 587))
    if config.get("use_tls", True):
        smtp: smtplib.SMTP = smtplib.SMTP(config["smtp_host"], port, timeout=_HTTP_TIMEOUT_S)
        smtp.starttls()
    else:
        smtp = smtplib.SMTP(config["smtp_host"], port, timeout=_HTTP_TIMEOUT_S)
    with smtp:
        if config.get("username"):
            smtp.login(config["username"], config.get("password", ""))
        smtp.send_message(msg)


def send_webhook(config: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
    """POST the payload as JSON. Config: url, optional headers."""
    headers = {"Content-Type": "application/json"}
    headers.update(config.get("headers", {}))
    _http_post(
        config["url"],
        json.dumps(payload, default=str).encode("utf-8"),
        headers,
    )


def send_slack(config: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
    """POST to a Slack incoming webhook. Config: webhook_url."""
    text = f"*[{payload['severity'].upper()}]* {payload['title']}\n{payload['message']}"
    body = json.dumps({"text": text}).encode("utf-8")
    _http_post(config["webhook_url"], body, {"Content-Type": "application/json"})


def send_sms(config: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
    """Deliver via the Twilio REST API. Config: account_sid, auth_token,
    from_number, to_number."""
    sid = config["account_sid"]
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    form = urllib.parse.urlencode(
        {
            "To": config["to_number"],
            "From": config["from_number"],
            "Body": f"[{payload['severity'].upper()}] {payload['title']}: {payload['message']}",
        }
    ).encode("utf-8")
    auth = base64.b64encode(f"{sid}:{config['auth_token']}".encode()).decode()
    _http_post(
        url,
        form,
        {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {auth}",
        },
    )


#: Kind -> default sender. Overridable per manager via the ``senders`` arg.
DEFAULT_SENDERS: dict[str, Sender] = {
    "email": send_email,
    "webhook": send_webhook,
    "sms": send_sms,
    "slack": send_slack,
}


# --------------------------------------------------------------------- #
# Manager
# --------------------------------------------------------------------- #

#: Priority at or above which a watcher ``raise_alert`` counts as critical
#: for :meth:`NotificationManager.attach_to_watchers`.
DEFAULT_CRITICAL_PRIORITY = 0.9


class NotificationManager:
    """Registry of outbound channels with filtering, rate limits, retries.

    Parameters
    ----------
    senders:
        Optional ``{kind: sender}`` overrides (merged over
        :data:`DEFAULT_SENDERS`); tests inject fakes here.
    max_retries:
        Delivery attempts after the first before a send fails (0 = no retry).
    base_backoff_s:
        Delay after attempt *n* is ``base_backoff_s * 2**n`` seconds.
    now:
        Monotonic clock, injectable for deterministic tests.
    sleep:
        Sleep callable used between retries, injectable for tests.
    """

    def __init__(
        self,
        *,
        senders: Mapping[str, Sender] | None = None,
        max_retries: int = 2,
        base_backoff_s: float = 0.5,
        now: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if base_backoff_s < 0:
            raise ValueError("base_backoff_s must be >= 0")
        self.max_retries = max_retries
        self.base_backoff_s = base_backoff_s
        self._now = now
        self._sleep = sleep
        self._senders: dict[str, Sender] = {**DEFAULT_SENDERS, **(senders or {})}
        self._channels: dict[str, NotificationChannel] = {}
        # Sliding-window send timestamps per channel, for rate limiting.
        self._send_log: dict[str, list[float]] = {}
        self._sent = 0
        self._filtered = 0
        self._rate_limited = 0
        self._failed = 0

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #
    def register_channel(
        self,
        name: str,
        kind: str,
        *,
        config: Mapping[str, Any] | None = None,
        min_severity: str = DEFAULT_SEVERITY,
        rate_limit_per_minute: float = 30.0,
    ) -> str:
        """Validate and register a channel. Returns the channel name."""
        if not isinstance(name, str) or not name:
            raise TypeError("channel name must be a non-empty string")
        if kind not in CHANNEL_KINDS:
            raise ValueError(
                f"unknown channel kind {kind!r}; expected one of {sorted(CHANNEL_KINDS)}"
            )
        if kind not in self._senders:
            raise ValueError(f"no sender available for channel kind {kind!r}")
        min_sev = normalize_severity(min_severity)
        if not isinstance(rate_limit_per_minute, (int, float)) or rate_limit_per_minute <= 0:
            raise TypeError("rate_limit_per_minute must be a number > 0")
        if name in self._channels:
            raise ValueError(f"duplicate channel name: {name!r}")
        self._channels[name] = NotificationChannel(
            name=name,
            kind=kind,
            config=dict(config or {}),
            min_severity=min_sev,
            rate_limit_per_minute=float(rate_limit_per_minute),
        )
        return name

    def unregister_channel(self, name: str) -> bool:
        """Remove a channel; returns True when it existed."""
        self._send_log.pop(name, None)
        return self._channels.pop(name, None) is not None

    def get_channel(self, name: str) -> dict[str, Any] | None:
        """Public (config-redacted keys kept, values hidden) view, or None."""
        ch = self._channels.get(name)
        if ch is None:
            return None
        return {
            "name": ch.name,
            "kind": ch.kind,
            "config_keys": sorted(ch.config),
            "min_severity": ch.min_severity,
            "rate_limit_per_minute": ch.rate_limit_per_minute,
        }

    def list_channels(self) -> list[dict[str, Any]]:
        """Public view of all channels, in registration order."""
        return [self.get_channel(n) for n in self._channels]  # type: ignore[misc]

    # ------------------------------------------------------------------ #
    # Sending
    # ------------------------------------------------------------------ #
    @staticmethod
    def _build_payload(
        channel: NotificationChannel,
        message: str,
        severity: str,
        metadata: Mapping[str, Any] | None,
        title: str,
    ) -> dict[str, Any]:
        return {
            "title": title,
            "message": message,
            "severity": severity,
            "channel": channel.name,
            "source": "aelma-twin",
            "metadata": dict(metadata or {}),
        }

    def _rate_limit_allows(self, channel: NotificationChannel, now: float) -> bool:
        """Sliding-window check; prunes entries older than 60 seconds."""
        log_entries = self._send_log.setdefault(channel.name, [])
        cutoff = now - 60.0
        while log_entries and log_entries[0] <= cutoff:
            log_entries.pop(0)
        return len(log_entries) < channel.rate_limit_per_minute

    def send_notification(
        self,
        channel: str,
        message: str,
        severity: str = DEFAULT_SEVERITY,
        *,
        title: str = "AELMA alert",
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send ``message`` to one channel with filtering/limits/retries.

        Returns a result dict: ``{"ok", "channel", "severity", "status",
        "attempts", "error"}`` where ``status`` is one of ``sent``,
        ``filtered``, ``rate_limited``, or ``failed``. Never raises for
        delivery failures — the failure is reported in the result.
        """
        ch = self._channels.get(channel)
        if ch is None:
            raise ValueError(f"unknown channel: {channel!r}")
        sev = normalize_severity(severity)
        result: dict[str, Any] = {
            "ok": False,
            "channel": channel,
            "severity": sev,
            "status": "failed",
            "attempts": 0,
            "error": None,
        }

        # 1. Severity filter — cheapest gate first.
        if SEVERITY_LEVELS[sev] < SEVERITY_LEVELS[ch.min_severity]:
            result["status"] = "filtered"
            self._filtered += 1
            return result

        # 2. Rate limit.
        now = self._now()
        if not self._rate_limit_allows(ch, now):
            result["status"] = "rate_limited"
            self._rate_limited += 1
            log.warning("channel %r rate limited; dropping %s alert", channel, sev)
            return result

        # 3. Deliver with retry + exponential backoff.
        payload = self._build_payload(ch, message, sev, metadata, title)
        sender = self._senders[ch.kind]
        last_exc: Exception | None = None
        for attempt in range(1 + self.max_retries):
            result["attempts"] = attempt + 1
            try:
                sender(ch.config, payload)
                result["ok"] = True
                result["status"] = "sent"
                self._send_log[channel].append(now)
                self._sent += 1
                return result
            except Exception as exc:  # delivery failures never propagate
                last_exc = exc
                log.warning(
                    "channel %r attempt %d failed: %s", channel, attempt + 1, exc
                )
                if attempt < self.max_retries:
                    self._sleep(self.base_backoff_s * (2**attempt))
        result["error"] = str(last_exc)
        self._failed += 1
        return result

    def broadcast(
        self,
        message: str,
        severity: str = DEFAULT_SEVERITY,
        *,
        title: str = "AELMA alert",
        metadata: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Send to every registered channel; returns per-channel results."""
        return [
            self.send_notification(name, message, severity, title=title, metadata=metadata)
            for name in self._channels
        ]

    def test_channel(self, name: str) -> dict[str, Any]:
        """Send a synthetic test notification to verify a channel works.

        Bypasses the channel's severity filter by sending at ``critical``;
        rate limiting and retries still apply.
        """
        if name not in self._channels:
            raise ValueError(f"unknown channel: {name!r}")
        return self.send_notification(
            name,
            "test notification from NotificationManager.test_channel",
            severity="critical",
            title="AELMA channel test",
            metadata={"test": True},
        )

    # ------------------------------------------------------------------ #
    # WatcherRegistry integration
    # ------------------------------------------------------------------ #
    def attach_to_watchers(
        self,
        registry: Any,
        *,
        min_priority: float = DEFAULT_CRITICAL_PRIORITY,
    ) -> None:
        """Auto-send critical alerts: subscribe to the registry's ``fired``
        event and broadcast any ``raise_alert`` action whose priority is at
        or above ``min_priority``, at ``critical`` severity.

        The listener never raises into the registry — watcher event
        listeners are isolated, but we keep it quiet anyway.
        """

        def _on_fired(action: Mapping[str, Any]) -> None:
            try:
                if action.get("action") != "raise_alert":
                    return
                if float(action.get("priority", 0.0)) < min_priority:
                    return
                payload = action.get("payload") or {}
                kind = payload.get("kind", "watcher_alert")
                self.broadcast(
                    action.get("reason") or f"watcher {action.get('rule_id')} fired",
                    severity="critical",
                    title=f"AELMA critical alert: {kind}",
                    metadata={"rule_id": action.get("rule_id"), **payload},
                )
            except Exception:
                log.exception("watcher-to-notification bridge failed")

        registry.on("fired", _on_fired)

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #
    @property
    def stats(self) -> dict[str, Any]:
        """Manager stats: counters plus the registered channel list."""
        return {
            "channel_count": len(self._channels),
            "channels": self.list_channels(),
            "sent": self._sent,
            "filtered": self._filtered,
            "rate_limited": self._rate_limited,
            "failed": self._failed,
        }


__all__ = [
    "CHANNEL_KINDS",
    "DEFAULT_CRITICAL_PRIORITY",
    "DEFAULT_SENDERS",
    "DEFAULT_SEVERITY",
    "NotificationChannel",
    "NotificationManager",
    "SEVERITY_LEVELS",
    "normalize_severity",
    "send_email",
    "send_slack",
    "send_sms",
    "send_webhook",
]
