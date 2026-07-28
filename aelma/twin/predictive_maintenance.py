"""PredictiveMaintenance: equipment failure forecasting from telemetry trends.

Pure-Python (stdlib only) predictive maintenance over per-equipment time
series of condition readings. Each equipment item accumulates a rolling
history of readings for four tracked metrics:

* ``engine_hours`` — cumulative running hours; serviced on an interval
  (default 500 h). The "trend" here is the *usage rate* (hours per day),
  which projects when the next service interval is consumed.
* ``temperature`` — trend upward toward an overheat threshold
  (default 110 degC).
* ``vibration`` — trend upward toward a mechanical-wear threshold
  (default 10 mm/s RMS).
* ``oil_pressure`` — trend *downward* toward a low-pressure threshold
  (default 20 psi), so its threshold direction is "low".

Three complementary algorithms run over each metric's history:

* **linear trend extrapolation** — least-squares fit of value vs. time;
  the slope projects the metric forward.
* **threshold breach prediction** — from the fitted line, the time at
  which the metric crosses its (directional) threshold. A flat or
  retreating trend never breaches.
* **mean time between failures (MTBF)** — from explicitly logged failure
  events, the average inter-failure interval projects the next failure
  independently of sensor trends. Useful for failure modes the metrics
  do not see coming.

``predict_failure`` fuses the per-metric breach forecasts and the MTBF
forecast into a risk score in ``[0, 1]`` with the same severity ladder as
the anomaly detector::

    risk >= 0.75  -> "critical"
    risk >  0.50  -> "warning"
    else          -> "info"

``get_maintenance_schedule`` runs that prediction across every known
equipment item and returns the work list sorted by soonest predicted
breach, ready to drive a maintenance dashboard or watcher rule.

Typical use::

    pm = PredictiveMaintenance()
    for packet in stream:
        pm.log_reading("main-engine", {
            "timestamp": packet["ts"],
            "engine_hours": packet["engine_hours"],
            "temperature": packet["coolant_temp_c"],
            "vibration": packet["vibration_mm_s"],
            "oil_pressure": packet["oil_pressure_psi"],
        })
    report = pm.predict_failure("main-engine", days_ahead=30)
    schedule = pm.get_maintenance_schedule()
"""

from __future__ import annotations

import logging
import math
import statistics
import time
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("aelma.twin.predictive_maintenance")

SECONDS_PER_DAY = 86400.0

#: Default per-metric service / failure thresholds.
DEFAULT_THRESHOLDS: dict[str, dict[str, Any]] = {
    "engine_hours": {"threshold": 500.0, "direction": "high", "unit": "h"},
    "temperature": {"threshold": 110.0, "direction": "high", "unit": "degC"},
    "vibration": {"threshold": 10.0, "direction": "high", "unit": "mm/s"},
    "oil_pressure": {"threshold": 20.0, "direction": "low", "unit": "psi"},
}


@dataclass(frozen=True)
class TrendFit:
    """Least-squares fit of one metric's history: value = intercept + slope*t."""

    metric: str
    samples: int
    slope_per_day: float
    intercept: float
    r_squared: float
    last_value: float
    last_timestamp: float


def _linregress(points: list[tuple[float, float]]) -> tuple[float, float, float]:
    """Least-squares fit over ``(t, value)`` points.

    Returns ``(slope, intercept, r_squared)``. Requires at least two
    points with non-zero time variance; callers gate on sample count
    before calling. ``r_squared`` is 0.0 when the value variance is zero
    (flat series — the fit is exact but uninformative).
    """
    n = len(points)
    ts = [p[0] for p in points]
    vs = [p[1] for p in points]
    mean_t = statistics.fmean(ts)
    mean_v = statistics.fmean(vs)
    s_tt = sum((t - mean_t) ** 2 for t in ts)
    if s_tt <= 0.0:
        raise ValueError("zero time variance")
    s_tv = sum((t - mean_t) * (v - mean_v) for t, v in points)
    slope = s_tv / s_tt
    intercept = mean_v - slope * mean_t
    s_vv = sum((v - mean_v) ** 2 for v in vs)
    r_squared = (s_tv ** 2) / (s_tt * s_vv) if s_vv > 0.0 else 0.0
    return slope, intercept, r_squared


def _severity_for_risk(risk: float) -> str:
    if risk >= 0.75:
        return "critical"
    if risk > 0.5:
        return "warning"
    return "info"


def _risk_from_days(days_until: float | None, horizon_days: float) -> float:
    """Map a days-until-breach forecast onto a risk score in [0, 1].

    Already breached (or breach inside the horizon) scores proportionally
    to urgency; a breach beyond the horizon — or no breach at all —
    scores zero.
    """
    if days_until is None:
        return 0.0
    if days_until <= 0.0:
        return 1.0
    if days_until >= horizon_days:
        return 0.0
    return 1.0 - days_until / horizon_days


class PredictiveMaintenance:
    """Trend-based failure forecasting and maintenance scheduling.

    Parameters
    ----------
    window_size:
        Maximum number of readings kept per equipment per metric. Older
        readings are dropped so forecasts track current condition.
    min_samples:
        Minimum readings per metric before its trend is fitted. Below
        this the metric reports ``status: "learning"``.
    thresholds:
        Per-metric overrides of ``DEFAULT_THRESHOLDS``; each entry maps a
        metric name to ``{"threshold", "direction", "unit"}``. Unknown
        metric names are rejected.
    now:
        Time source (seconds since epoch), injectable for tests.
        Defaults to :func:`time.time`.
    """

    def __init__(
        self,
        *,
        window_size: int = 500,
        min_samples: int = 5,
        thresholds: Mapping[str, Mapping[str, Any]] | None = None,
        now: Any = None,
    ) -> None:
        if window_size < 2:
            raise ValueError("window_size must be >= 2")
        if min_samples < 2:
            raise ValueError("min_samples must be >= 2")

        self.window_size = int(window_size)
        self.min_samples = int(min_samples)
        self._now = now if now is not None else time.time

        self._metrics: dict[str, dict[str, Any]] = {
            name: dict(spec) for name, spec in DEFAULT_THRESHOLDS.items()
        }
        for name, spec in (thresholds or {}).items():
            if name not in self._metrics:
                raise ValueError(f"unknown metric: {name!r}")
            merged = {**self._metrics[name], **dict(spec)}
            if merged["direction"] not in ("high", "low"):
                raise ValueError(
                    f"direction for {name!r} must be 'high' or 'low'")
            if merged["threshold"] <= 0:
                raise ValueError(f"threshold for {name!r} must be positive")
            self._metrics[name] = merged

        # equipment_id -> metric -> deque[(timestamp, value)]
        self._series: dict[str, dict[str, deque[tuple[float, float]]]] = {}
        # equipment_id -> [failure timestamps]
        self._failures: dict[str, list[float]] = {}

    # ------------------------------------------------------------------ #
    # Ingestion
    # ------------------------------------------------------------------ #
    def log_reading(
        self,
        equipment_id: str,
        reading: Mapping[str, Any],
    ) -> list[str]:
        """Record one reading for an equipment item.

        ``reading`` is a mapping that may carry ``timestamp`` (epoch
        seconds; defaults to now) plus any subset of the tracked metrics
        (``engine_hours``, ``temperature``, ``vibration``,
        ``oil_pressure``). Non-numeric or non-finite values are skipped.
        Returns the metric names actually recorded.
        """
        if not equipment_id:
            raise ValueError("equipment_id must be a non-empty string")
        if not isinstance(reading, Mapping):
            raise TypeError("reading must be a mapping")

        ts = reading.get("timestamp", None)
        if ts is None:
            timestamp = float(self._now())
        elif isinstance(ts, bool) or not isinstance(ts, (int, float)):
            raise ValueError("timestamp must be numeric epoch seconds")
        elif not math.isfinite(float(ts)):
            raise ValueError("timestamp must be finite")
        else:
            timestamp = float(ts)

        recorded: list[str] = []
        for metric in self._metrics:
            value = reading.get(metric)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            x = float(value)
            if not math.isfinite(x):
                log.debug("ignoring non-finite %s on %s: %r",
                          metric, equipment_id, value)
                continue
            series = self._series.setdefault(equipment_id, {})
            window = series.get(metric)
            if window is None:
                window = series[metric] = deque(maxlen=self.window_size)
            window.append((timestamp, x))
            recorded.append(metric)
        return recorded

    def log_failure(
        self,
        equipment_id: str,
        timestamp: float | None = None,
    ) -> None:
        """Record a failure event for MTBF tracking.

        Timestamps are kept sorted; an explicit ``timestamp`` (epoch
        seconds) keeps tests and replayed logs deterministic.
        """
        if not equipment_id:
            raise ValueError("equipment_id must be a non-empty string")
        ts = float(self._now()) if timestamp is None else float(timestamp)
        events = self._failures.setdefault(equipment_id, [])
        events.append(ts)
        events.sort()

    def reset(self, equipment_id: str | None = None) -> None:
        """Drop all state for one equipment item, or everything when None."""
        if equipment_id is None:
            self._series.clear()
            self._failures.clear()
        else:
            self._series.pop(equipment_id, None)
            self._failures.pop(equipment_id, None)

    # ------------------------------------------------------------------ #
    # Trend analysis
    # ------------------------------------------------------------------ #
    def trend(self, equipment_id: str, metric: str) -> TrendFit | None:
        """Least-squares trend for one metric (None if insufficient data)."""
        if metric not in self._metrics:
            raise ValueError(f"unknown metric: {metric!r}")
        window = self._series.get(equipment_id, {}).get(metric)
        if not window or len(window) < self.min_samples:
            return None
        points = sorted(window)
        try:
            slope, intercept, r2 = _linregress(points)
        except ValueError:
            # All readings share one timestamp — no trend exists.
            return None
        return TrendFit(
            metric=metric,
            samples=len(points),
            slope_per_day=slope * SECONDS_PER_DAY,
            intercept=intercept,
            r_squared=r2,
            last_value=points[-1][1],
            last_timestamp=points[-1][0],
        )

    def _days_until_breach(self, fit: TrendFit, spec: Mapping[str, Any]) -> float | None:
        """Projected days until the fitted trend crosses the threshold.

        ``None`` when the trend is flat or moving away from the threshold;
        ``0.0`` when the latest reading has already breached.
        """
        threshold = float(spec["threshold"])
        direction = spec["direction"]
        slope = fit.slope_per_day
        gap = threshold - fit.last_value

        if direction == "high":
            if fit.last_value >= threshold:
                return 0.0
            if slope <= 0.0:
                return None
            return gap / slope
        # direction == "low": breach when the value falls to the threshold.
        if fit.last_value <= threshold:
            return 0.0
        if slope >= 0.0:
            return None
        return gap / slope  # gap < 0 and slope < 0 -> positive day count

    # ------------------------------------------------------------------ #
    # MTBF
    # ------------------------------------------------------------------ #
    def mtbf(self, equipment_id: str) -> dict[str, Any]:
        """Mean-time-between-failures summary for one equipment item.

        Needs at least two logged failures for an interval estimate; with
        one failure only the elapsed time since it is known.
        """
        events = self._failures.get(equipment_id, [])
        result: dict[str, Any] = {
            "equipment_id": equipment_id,
            "failure_count": len(events),
            "mtbf_days": None,
            "days_since_last_failure": None,
            "days_until_next_failure": None,
        }
        if not events:
            return result
        now = float(self._now())
        result["days_since_last_failure"] = max(
            0.0, (now - events[-1]) / SECONDS_PER_DAY)
        if len(events) >= 2:
            intervals = [(b - a) / SECONDS_PER_DAY
                         for a, b in zip(events, events[1:]) if b > a]
            if intervals:
                mtbf_days = statistics.fmean(intervals)
                result["mtbf_days"] = mtbf_days
                result["days_until_next_failure"] = (
                    mtbf_days - result["days_since_last_failure"])
        return result

    # ------------------------------------------------------------------ #
    # Prediction
    # ------------------------------------------------------------------ #
    def predict_failure(
        self,
        equipment_id: str,
        days_ahead: float = 30.0,
    ) -> dict[str, Any]:
        """Failure forecast for one equipment item over ``days_ahead`` days.

        Returns a report with a per-metric breakdown (trend, projected
        breach date, per-metric risk), the MTBF forecast, and a fused
        ``risk`` / ``severity`` / ``predicted_failure`` verdict.
        """
        if days_ahead <= 0:
            raise ValueError("days_ahead must be positive")
        now = float(self._now())

        metrics_report: dict[str, Any] = {}
        risks: list[float] = []
        drivers: list[str] = []
        earliest_days: float | None = None

        for metric, spec in self._metrics.items():
            fit = self.trend(equipment_id, metric)
            if fit is None:
                metrics_report[metric] = {"status": "learning"}
                continue
            days_until = self._days_until_breach(fit, spec)
            risk = _risk_from_days(days_until, days_ahead)
            entry: dict[str, Any] = {
                "status": "ok",
                "samples": fit.samples,
                "last_value": fit.last_value,
                "threshold": spec["threshold"],
                "direction": spec["direction"],
                "unit": spec["unit"],
                "slope_per_day": fit.slope_per_day,
                "r_squared": fit.r_squared,
                "days_until_breach": days_until,
                "risk": risk,
            }
            if days_until is not None:
                entry["breach_eta_days"] = days_until
                if days_until <= days_ahead:
                    drivers.append(metric)
                if earliest_days is None or days_until < earliest_days:
                    earliest_days = days_until
            metrics_report[metric] = entry
            risks.append(risk)

        mtbf_report = self.mtbf(equipment_id)
        mtbf_days_until = mtbf_report["days_until_next_failure"]
        mtbf_risk = _risk_from_days(mtbf_days_until, days_ahead)
        if mtbf_days_until is not None and mtbf_days_until <= days_ahead:
            drivers.append("mtbf")
            if earliest_days is None or mtbf_days_until < earliest_days:
                earliest_days = mtbf_days_until
        risks.append(mtbf_risk)

        risk = max(risks) if risks else 0.0
        return {
            "equipment_id": equipment_id,
            "generated_at": now,
            "days_ahead": days_ahead,
            "metrics": metrics_report,
            "mtbf": mtbf_report,
            "risk": risk,
            "severity": _severity_for_risk(risk),
            "predicted_failure": bool(drivers),
            "drivers": drivers,
            "earliest_breach_days": earliest_days,
        }

    # ------------------------------------------------------------------ #
    # Scheduling
    # ------------------------------------------------------------------ #
    def get_maintenance_schedule(
        self,
        days_ahead: float = 90.0,
    ) -> list[dict[str, Any]]:
        """Prioritized maintenance work list across all known equipment.

        Every equipment item with readings or logged failures is scored
        over the ``days_ahead`` horizon. Items are sorted by soonest
        predicted breach (items with none sort last, by descending risk),
        so the top of the list is always the most urgent work.
        """
        equipment_ids = sorted(set(self._series) | set(self._failures))
        schedule: list[dict[str, Any]] = []
        for equipment_id in equipment_ids:
            report = self.predict_failure(equipment_id, days_ahead=days_ahead)
            drivers = report["drivers"]
            if drivers:
                action = "inspect " + ", ".join(
                    d if d == "mtbf" else f"{d} trend" for d in drivers)
            else:
                action = "routine check"
            schedule.append({
                "equipment_id": equipment_id,
                "due_in_days": report["earliest_breach_days"],
                "risk": report["risk"],
                "severity": report["severity"],
                "drivers": drivers,
                "recommended_action": action,
            })

        def sort_key(item: dict[str, Any]) -> tuple[float, float]:
            due = item["due_in_days"]
            # Items with no predicted breach sort after everything dated.
            return (
                due if due is not None else float("inf"),
                -item["risk"],
            )

        schedule.sort(key=sort_key)
        return schedule


__all__ = [
    "DEFAULT_THRESHOLDS",
    "PredictiveMaintenance",
    "TrendFit",
]
