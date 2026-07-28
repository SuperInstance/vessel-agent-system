"""AnomalyDetector: statistical outlier detection over telemetry channels.

Pure-Python (stdlib only) rolling-window anomaly detection for the twin's
telemetry stream. Three complementary algorithms run side by side over a
per-channel sliding window of recent observations:

* **z-score** — flags values more than ``z_threshold`` standard
  deviations from the window mean. Good for Gaussian-ish channels
  (depth, barometric pressure).
* **IQR fences** — flags values outside
  ``[Q1 - iqr_k * IQR, Q3 + iqr_k * IQR]``. Robust to a contaminated
  window (a few past outliers do not move the fences much), so it
  catches regime shifts that z-score absorbs.
* **moving-average deviation** — flags values whose relative deviation
  from the window mean exceeds ``ma_dev_threshold``. Catches slow
  channels with near-zero variance where z-score explodes on noise.

A value is an anomaly when *any* enabled algorithm flags it. The anomaly
score is a smooth squash of the worst exceedance ratio ``r`` (how many
times past its flagging threshold the value is)::

    score = r / (r + 1)        # r = 1 at the flagging threshold -> 0.5

so ``is_anomaly`` is exactly ``score > 0.5`` and the score keeps growing
toward 1.0 as the value moves further out. That makes the score directly
usable as a watcher priority and as a severity ladder:

    score >= 0.75  (r >= 3)  -> "critical"
    score >  0.50  (r >  1)  -> "warning"
    else                     -> "info"

WatcherRegistry integration — one ``raise_alert`` rule per channel::

    detector = AnomalyDetector(window_size=60)
    detector.register_watchers(registry, channels=["depth_m", "sog_kn"],
                               cooldown_s=30.0)

    for packet in stream:                       # or per snapshot tick
        detector.observe_telemetry(packet["channel"], packet["value"])
        for action in registry.evaluate(frame): # fires on anomalies
            dispatch(action)

The detector is synchronous, allocation-cheap, and side-effect free apart
from its own windows — safe to call on the hot packet path like the
watchers themselves.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("aelma.twin.anomaly_detector")

#: Algorithm names accepted by the ``algorithms`` constructor parameter.
ALGO_ZSCORE = "zscore"
ALGO_IQR = "iqr"
ALGO_MA_DEV = "ma_dev"
ALL_ALGORITHMS = (ALGO_ZSCORE, ALGO_IQR, ALGO_MA_DEV)

#: Small floor that keeps relative deviations and IQR ratios finite when
#: the window mean or spread is (near) zero.
_EPS = 1e-9


@dataclass(frozen=True)
class ChannelStats:
    """Snapshot of the rolling-window statistics for one channel."""

    channel: str
    count: int
    mean: float
    stdev: float
    q1: float
    median: float
    q3: float
    iqr: float


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _pstdev(values: list[float], mean: float) -> float:
    """Population standard deviation (the window *is* the population)."""
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


def _percentile(sorted_values: list[float], p: float) -> float:
    """Linear-interpolation percentile (numpy's default 'linear' method)."""
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    rank = (p / 100.0) * (n - 1)
    lo = int(math.floor(rank))
    hi = min(lo + 1, n - 1)
    frac = rank - lo
    return sorted_values[lo] + frac * (sorted_values[hi] - sorted_values[lo])


def _severity_for_score(score: float) -> str:
    if score >= 0.75:
        return "critical"
    if score > 0.5:
        return "warning"
    return "info"


class AnomalyDetector:
    """Rolling-window statistical anomaly detector for telemetry channels.

    Parameters
    ----------
    window_size:
        Maximum number of recent observations kept per channel. Older
        values are dropped, so the detector tracks slow drift.
    min_samples:
        Minimum window fill before any algorithm may flag. Below this
        the detector is still learning and reports everything normal.
    z_threshold:
        Flag when ``|z|`` exceeds this many standard deviations.
    iqr_k:
        Fence width multiplier for the IQR rule (1.5 = Tukey 'outlier',
        3.0 = 'far out').
    ma_dev_threshold:
        Flag when the relative deviation from the window mean,
        ``|x - mean| / (|mean| + eps)``, exceeds this ratio.
    algorithms:
        Subset of ``ALL_ALGORITHMS`` to enable. Defaults to all three.
    """

    def __init__(
        self,
        *,
        window_size: int = 60,
        min_samples: int = 10,
        z_threshold: float = 3.0,
        iqr_k: float = 1.5,
        ma_dev_threshold: float = 0.5,
        algorithms: tuple[str, ...] = ALL_ALGORITHMS,
    ) -> None:
        if window_size < 4:
            raise ValueError("window_size must be >= 4 for quartiles")
        if not 1 <= min_samples:
            raise ValueError("min_samples must be >= 1")
        if z_threshold <= 0 or iqr_k <= 0 or ma_dev_threshold <= 0:
            raise ValueError("thresholds must be positive")
        unknown = set(algorithms) - set(ALL_ALGORITHMS)
        if unknown:
            raise ValueError(f"unknown algorithms: {sorted(unknown)!r}")
        if not algorithms:
            raise ValueError("at least one algorithm must be enabled")

        self.window_size = int(window_size)
        self.min_samples = int(min_samples)
        self.z_threshold = float(z_threshold)
        self.iqr_k = float(iqr_k)
        self.ma_dev_threshold = float(ma_dev_threshold)
        self.algorithms = tuple(algorithms)
        self._windows: dict[str, deque[float]] = {}

    # ------------------------------------------------------------------ #
    # Observation
    # ------------------------------------------------------------------ #
    def observe_telemetry(self, channel: str, value: Any) -> None:
        """Record one reading. Non-numeric / non-finite values are ignored."""
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return
        x = float(value)
        if not math.isfinite(x):
            log.debug("ignoring non-finite value on %s: %r", channel, value)
            return
        window = self._windows.get(channel)
        if window is None:
            window = self._windows[channel] = deque(maxlen=self.window_size)
        window.append(x)

    def observe_frame(self, frame: Mapping[str, Any]) -> list[str]:
        """Observe every numeric value in a watcher-style frame.

        Returns the channels that were recorded — handy for tests and for
        feeding a :class:`~twin.watchers.WatcherRegistry` frame straight
        into the detector before evaluation.
        """
        observed = []
        for channel, value in frame.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            if math.isfinite(float(value)):
                self.observe_telemetry(channel, value)
                observed.append(channel)
        return observed

    def reset(self, channel: str | None = None) -> None:
        """Drop learned state for one channel, or everything when None."""
        if channel is None:
            self._windows.clear()
        else:
            self._windows.pop(channel, None)

    # ------------------------------------------------------------------ #
    # Window statistics
    # ------------------------------------------------------------------ #
    def stats(self, channel: str) -> ChannelStats | None:
        """Current window statistics for ``channel`` (None if unseen)."""
        window = self._windows.get(channel)
        if not window:
            return None
        values = list(window)
        ordered = sorted(values)
        mean = _mean(values)
        q1 = _percentile(ordered, 25.0)
        q3 = _percentile(ordered, 75.0)
        return ChannelStats(
            channel=channel,
            count=len(values),
            mean=mean,
            stdev=_pstdev(values, mean),
            q1=q1,
            median=_percentile(ordered, 50.0),
            q3=q3,
            iqr=q3 - q1,
        )

    # ------------------------------------------------------------------ #
    # Detection
    # ------------------------------------------------------------------ #
    def explain(self, channel: str, value: float) -> dict[str, Any]:
        """Full per-algorithm breakdown for one candidate value.

        The ``ratio`` of each algorithm is its exceedance ratio: ``r > 1``
        means that algorithm flags the value, and the overall ``score`` is
        ``r / (r + 1)`` of the worst algorithm. Algorithms report
        ``flagged: False`` with ``ratio: 0.0`` while the window has fewer
        than ``min_samples`` observations.
        """
        result: dict[str, Any] = {
            "channel": channel,
            "value": value,
            "score": 0.0,
            "is_anomaly": False,
            "algorithms": {},
        }
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            result["error"] = "non-numeric value"
            return result
        x = float(value)
        if not math.isfinite(x):
            result["error"] = "non-finite value"
            return result

        stats = self.stats(channel)
        ready = stats is not None and stats.count >= self.min_samples
        worst = 0.0
        for algo in self.algorithms:
            if not ready or stats is None:
                detail = {"flagged": False, "ratio": 0.0, "detail": "learning"}
            elif algo == ALGO_ZSCORE:
                detail = self._zscore(x, stats)
            elif algo == ALGO_IQR:
                detail = self._iqr(x, stats)
            else:
                detail = self._ma_dev(x, stats)
            result["algorithms"][algo] = detail
            worst = max(worst, detail["ratio"])

        result["score"] = worst / (worst + 1.0) if worst > 0 else 0.0
        result["is_anomaly"] = worst > 1.0
        result["severity"] = _severity_for_score(result["score"])
        return result

    def is_anomaly(self, channel: str, value: float) -> bool:
        """True when any enabled algorithm flags ``value`` on ``channel``."""
        return bool(self.explain(channel, value)["is_anomaly"])

    def get_anomaly_score(
        self,
        channel: str | None = None,
        value: float | None = None,
    ) -> float:
        """Anomaly score in ``[0, 1)``; scores above 0.5 are anomalies.

        With a ``channel`` and ``value`` the candidate is scored against
        that channel's window. With only a ``channel``, its most recent
        observation is scored. With neither, the worst score across all
        channels' latest observations is returned — a cheap "is anything
        weird right now" probe for dashboards.
        """
        if channel is not None:
            if value is None:
                window = self._windows.get(channel)
                if not window:
                    return 0.0
                value = window[-1]
            return float(self.explain(channel, value)["score"])

        best = 0.0
        for ch, window in self._windows.items():
            if window:
                best = max(best, self.get_anomaly_score(ch, window[-1]))
        return best

    # ------------------------------------------------------------------ #
    # Algorithms — each returns {"flagged", "ratio", "detail"}
    # ------------------------------------------------------------------ #
    def _zscore(self, x: float, stats: ChannelStats) -> dict[str, Any]:
        if stats.stdev <= _EPS:
            # Zero-variance window: no z-score exists, so fall back to a
            # relative-deviation ratio scaled by the z threshold — tiny
            # float noise around a constant channel must not flag.
            dev = abs(x - stats.mean) / (abs(stats.mean) + _EPS)
            ratio = dev / self.z_threshold
            return {
                "flagged": ratio > 1.0,
                "ratio": ratio,
                "detail": f"flat window, rel_dev={dev:.3g}",
            }
        z = abs(x - stats.mean) / stats.stdev
        return {
            "flagged": z > self.z_threshold,
            "ratio": z / self.z_threshold,
            "detail": f"|z|={z:.2f} vs {self.z_threshold:.2f}",
        }

    def _iqr(self, x: float, stats: ChannelStats) -> dict[str, Any]:
        lower = stats.q1 - self.iqr_k * stats.iqr
        upper = stats.q3 + self.iqr_k * stats.iqr
        span = stats.iqr + _EPS
        if x > upper:
            ratio = 1.0 + (x - upper) / span
        elif x < lower:
            ratio = 1.0 + (lower - x) / span
        else:
            ratio = 0.0
        return {
            "flagged": ratio > 1.0,
            "ratio": ratio,
            "detail": f"fences=[{lower:.4g}, {upper:.4g}]",
        }

    def _ma_dev(self, x: float, stats: ChannelStats) -> dict[str, Any]:
        dev = abs(x - stats.mean) / (abs(stats.mean) + _EPS)
        ratio = dev / self.ma_dev_threshold
        return {
            "flagged": ratio > 1.0,
            "ratio": ratio,
            "detail": f"dev={dev:.3f} vs {self.ma_dev_threshold:.3f}",
        }

    # ------------------------------------------------------------------ #
    # WatcherRegistry integration
    # ------------------------------------------------------------------ #
    def register_watchers(
        self,
        registry: Any,
        *,
        channels: list[str] | None = None,
        cooldown_s: float = 30.0,
        rule_prefix: str = "anomaly",
    ) -> list[str]:
        """Register one ``raise_alert`` watcher rule per channel.

        Each rule fires when the frame's value for its channel is an
        anomaly against this detector's learned window. The payload
        follows the ``raise_alert`` schema (``severity`` / ``code`` /
        ``message``) plus the detector's per-algorithm breakdown; the
        priority is ``0.5 + 0.5 * score`` so deeper anomalies outrank
        marginal ones. Returns the registered rule ids.

        ``channels`` defaults to every channel the detector has already
        observed. Rules are bound to this detector instance, so the same
        windows drive both learning and alerting.
        """
        if channels is None:
            channels = sorted(self._windows)
        rule_ids = []
        for channel in channels:
            rule_id = f"{rule_prefix}-{channel}"
            registry.add({
                "id": rule_id,
                "name": f"Statistical anomaly on {channel}",
                "when": lambda f, ch=channel: self._frame_value(f, ch) is not None
                and self.is_anomaly(ch, self._frame_value(f, ch)),
                "action": {
                    "name": "raise_alert",
                    "payload": lambda f, ch=channel: self._alert_payload(
                        ch, self._frame_value(f, ch)),
                    "reason": lambda f, ch=channel: self._alert_reason(
                        ch, self._frame_value(f, ch)),
                    "priority": lambda f, ch=channel: (
                        0.5 + 0.5 * self.get_anomaly_score(
                            ch, self._frame_value(f, ch))),
                },
                "cooldown_s": cooldown_s,
            })
            rule_ids.append(rule_id)
        return rule_ids

    @staticmethod
    def _frame_value(frame: Mapping[str, Any], channel: str) -> float | None:
        value = frame.get(channel)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        x = float(value)
        return x if math.isfinite(x) else None

    def _alert_payload(self, channel: str, value: float) -> dict[str, Any]:
        report = self.explain(channel, value)
        flagged = [a for a, d in report["algorithms"].items() if d["flagged"]]
        return {
            "severity": report["severity"],
            "code": f"ANOMALY_{channel.upper().replace('.', '_')}",
            "message": (
                f"{channel}={value:.4g} flagged by {', '.join(flagged)} "
                f"(score={report['score']:.2f})"
            ),
            "channel": channel,
            "value": value,
            "score": report["score"],
            "algorithms": report["algorithms"],
        }

    def _alert_reason(self, channel: str, value: float) -> str:
        report = self.explain(channel, value)
        flagged = {
            a: d["detail"] for a, d in report["algorithms"].items() if d["flagged"]
        }
        parts = "; ".join(f"{a}: {d}" for a, d in flagged.items())
        return f"{channel}={value:.4g} anomalous ({parts})"


__all__ = [
    "ALGO_IQR",
    "ALGO_MA_DEV",
    "ALGO_ZSCORE",
    "ALL_ALGORITHMS",
    "AnomalyDetector",
    "ChannelStats",
]
