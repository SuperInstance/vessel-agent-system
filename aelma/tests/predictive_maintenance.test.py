"""Tests for the AELMA predictive maintenance forecaster
(twin/predictive_maintenance.py).

Coverage:

  1. Construction & validation (window, min_samples, threshold overrides).
  2. log_reading — metric recording, timestamp handling, rejection of
     non-numeric / non-finite values, rolling window.
  3. Linear trend extrapolation — slope, intercept, r_squared, learning gate.
  4. Threshold breach prediction — rising metrics (temperature, vibration,
     engine_hours), falling metric (oil_pressure), flat and retreating
     trends, already-breached readings.
  5. MTBF — no/one/many failure events, next-failure projection.
  6. predict_failure — fused risk, severity ladder, drivers, horizon.
  7. get_maintenance_schedule — ordering, action strings, mixed fleet.

Run from the repo root:  python -m pytest tests/predictive_maintenance.test.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the repository root importable regardless of pytest's rootdir handling.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twin.predictive_maintenance import (  # noqa: E402
    DEFAULT_THRESHOLDS,
    PredictiveMaintenance,
)

DAY = 86400.0
T0 = 1_700_000_000.0  # fixed epoch base for deterministic series


class FakeClock:
    """Deterministic clock, advanced manually by tests."""

    def __init__(self, start: float = T0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def feed_series(pm: PredictiveMaintenance, equipment_id: str, metric: str,
                start_value: float, step_per_day: float, days: int,
                start_ts: float = T0) -> None:
    """Feed a perfectly linear daily series for one metric."""
    for i in range(days):
        pm.log_reading(equipment_id, {
            "timestamp": start_ts + i * DAY,
            metric: start_value + i * step_per_day,
        })


# --------------------------------------------------------------------- #
# Construction & validation
# --------------------------------------------------------------------- #

class TestConstruction:
    def test_defaults(self):
        pm = PredictiveMaintenance()
        assert pm.window_size == 500
        assert pm.min_samples == 5

    def test_rejects_tiny_window(self):
        with pytest.raises(ValueError):
            PredictiveMaintenance(window_size=1)

    def test_rejects_tiny_min_samples(self):
        with pytest.raises(ValueError):
            PredictiveMaintenance(min_samples=1)

    def test_rejects_unknown_metric_override(self):
        with pytest.raises(ValueError):
            PredictiveMaintenance(thresholds={"boost_pressure": {"threshold": 5}})

    def test_rejects_bad_direction_and_threshold(self):
        with pytest.raises(ValueError):
            PredictiveMaintenance(
                thresholds={"temperature": {"direction": "sideways"}})
        with pytest.raises(ValueError):
            PredictiveMaintenance(
                thresholds={"temperature": {"threshold": 0}})

    def test_threshold_override_merges_with_defaults(self):
        pm = PredictiveMaintenance(
            thresholds={"temperature": {"threshold": 95.0}})
        clock = FakeClock()
        pm._now = clock
        # Rising 0.5 degC/day from 90 -> last value 92, breach in 6 days.
        feed_series(pm, "eng", "temperature", 90.0, 0.5, 5)
        report = pm.predict_failure("eng", days_ahead=30)
        entry = report["metrics"]["temperature"]
        assert entry["threshold"] == 95.0
        assert entry["days_until_breach"] == pytest.approx(6.0)


# --------------------------------------------------------------------- #
# log_reading
# --------------------------------------------------------------------- #

class TestLogReading:
    def test_records_known_metrics_and_returns_them(self):
        pm = PredictiveMaintenance()
        recorded = pm.log_reading("eng", {
            "timestamp": T0,
            "engine_hours": 120.0,
            "temperature": 85.0,
            "vibration": 4.0,
            "oil_pressure": 45.0,
            "unrelated": 999.0,
        })
        assert sorted(recorded) == [
            "engine_hours", "oil_pressure", "temperature", "vibration"]

    def test_defaults_timestamp_to_now(self):
        clock = FakeClock()
        pm = PredictiveMaintenance(now=clock)
        pm.log_reading("eng", {"temperature": 80.0})
        fit_points = pm._series["eng"]["temperature"]
        assert list(fit_points) == [(T0, 80.0)]

    def test_rejects_non_numeric_and_non_finite_values(self):
        pm = PredictiveMaintenance()
        recorded = pm.log_reading("eng", {
            "timestamp": T0,
            "temperature": "hot",
            "vibration": True,
            "oil_pressure": float("nan"),
            "engine_hours": float("inf"),
        })
        assert recorded == []
        assert pm._series.get("eng", {}).get("temperature") is None

    def test_rejects_bad_arguments(self):
        pm = PredictiveMaintenance()
        with pytest.raises(ValueError):
            pm.log_reading("", {"temperature": 1.0})
        with pytest.raises(TypeError):
            pm.log_reading("eng", [("temperature", 1.0)])
        with pytest.raises(ValueError):
            pm.log_reading("eng", {"timestamp": "now", "temperature": 1.0})
        with pytest.raises(ValueError):
            pm.log_reading(
                "eng", {"timestamp": float("nan"), "temperature": 1.0})

    def test_rolling_window_drops_oldest(self):
        pm = PredictiveMaintenance(window_size=3, min_samples=2)
        for i in range(6):
            pm.log_reading("eng", {"timestamp": T0 + i * DAY, "temperature": i})
        window = pm._series["eng"]["temperature"]
        assert len(window) == 3
        assert window[0] == (T0 + 3 * DAY, 3.0)


# --------------------------------------------------------------------- #
# Linear trend extrapolation
# --------------------------------------------------------------------- #

class TestTrend:
    def test_perfect_linear_series(self):
        pm = PredictiveMaintenance()
        feed_series(pm, "eng", "temperature", 80.0, 1.5, 10)
        fit = pm.trend("eng", "temperature")
        assert fit.samples == 10
        assert fit.slope_per_day == pytest.approx(1.5)
        assert fit.r_squared == pytest.approx(1.0)
        assert fit.last_value == pytest.approx(80.0 + 9 * 1.5)
        # Intercept + slope*t reproduces the series origin.
        assert fit.intercept + (fit.slope_per_day / DAY) * T0 == pytest.approx(
            80.0, rel=1e-9)

    def test_learning_gate_below_min_samples(self):
        pm = PredictiveMaintenance(min_samples=5)
        feed_series(pm, "eng", "temperature", 80.0, 1.0, 4)
        assert pm.trend("eng", "temperature") is None
        feed_series(pm, "eng", "temperature", 84.0, 1.0, 1,
                    start_ts=T0 + 4 * DAY)
        assert pm.trend("eng", "temperature") is not None

    def test_unseen_equipment_and_metric(self):
        pm = PredictiveMaintenance()
        assert pm.trend("ghost", "temperature") is None
        feed_series(pm, "eng", "temperature", 80.0, 1.0, 6)
        assert pm.trend("eng", "vibration") is None
        with pytest.raises(ValueError):
            pm.trend("eng", "boost_pressure")

    def test_zero_time_variance_returns_none(self):
        pm = PredictiveMaintenance(min_samples=2)
        for _ in range(5):
            pm.log_reading("eng", {"timestamp": T0, "temperature": 80.0})
        assert pm.trend("eng", "temperature") is None


# --------------------------------------------------------------------- #
# Threshold breach prediction
# --------------------------------------------------------------------- #

class TestThresholdBreach:
    def test_rising_temperature_projects_breach(self):
        clock = FakeClock(start=T0 + 9 * DAY)
        pm = PredictiveMaintenance(now=clock)
        # 80 degC rising 2 degC/day for 10 days -> last value 98, breach
        # of 110 in (110 - 98) / 2 = 6 days.
        feed_series(pm, "eng", "temperature", 80.0, 2.0, 10)
        report = pm.predict_failure("eng", days_ahead=30)
        entry = report["metrics"]["temperature"]
        assert entry["days_until_breach"] == pytest.approx(6.0)
        assert entry["risk"] == pytest.approx(1.0 - 6.0 / 30.0)

    def test_falling_oil_pressure_projects_breach(self):
        clock = FakeClock(start=T0 + 9 * DAY)
        pm = PredictiveMaintenance(now=clock)
        # 50 psi falling 2 psi/day -> last value 32, breach of 20 in 6 days.
        feed_series(pm, "eng", "oil_pressure", 50.0, -2.0, 10)
        report = pm.predict_failure("eng", days_ahead=30)
        entry = report["metrics"]["oil_pressure"]
        assert entry["direction"] == "low"
        assert entry["days_until_breach"] == pytest.approx(6.0)

    def test_engine_hours_usage_rate_projects_service(self):
        clock = FakeClock(start=T0 + 9 * DAY)
        pm = PredictiveMaintenance(now=clock)
        # 300 h accumulating 10 h/day -> last value 390, 500 h interval
        # reached in (500 - 390) / 10 = 11 days.
        feed_series(pm, "eng", "engine_hours", 300.0, 10.0, 10)
        report = pm.predict_failure("eng", days_ahead=30)
        entry = report["metrics"]["engine_hours"]
        assert entry["days_until_breach"] == pytest.approx(11.0)

    def test_flat_trend_never_breaches(self):
        pm = PredictiveMaintenance()
        feed_series(pm, "eng", "temperature", 85.0, 0.0, 10)
        report = pm.predict_failure("eng", days_ahead=30)
        entry = report["metrics"]["temperature"]
        assert entry["days_until_breach"] is None
        assert entry["risk"] == 0.0

    def test_retreating_trend_never_breaches(self):
        pm = PredictiveMaintenance()
        feed_series(pm, "eng", "temperature", 100.0, -1.0, 10)  # cooling down
        feed_series(pm, "eng", "oil_pressure", 25.0, 0.5, 10)   # recovering
        report = pm.predict_failure("eng", days_ahead=30)
        assert report["metrics"]["temperature"]["days_until_breach"] is None
        assert report["metrics"]["oil_pressure"]["days_until_breach"] is None

    def test_already_breached_scores_zero_days(self):
        clock = FakeClock(start=T0 + 9 * DAY)
        pm = PredictiveMaintenance(now=clock)
        # Last reading already above the 110 threshold.
        feed_series(pm, "eng", "temperature", 100.0, 2.0, 10)  # last = 118
        report = pm.predict_failure("eng", days_ahead=30)
        entry = report["metrics"]["temperature"]
        assert entry["days_until_breach"] == 0.0
        assert entry["risk"] == 1.0
        assert report["severity"] == "critical"

    def test_breach_beyond_horizon_scores_zero_risk(self):
        clock = FakeClock(start=T0 + 9 * DAY)
        pm = PredictiveMaintenance(now=clock)
        # Breach in 51 days, horizon 30 -> known but not urgent.
        feed_series(pm, "eng", "temperature", 80.0, 0.5, 10)
        report = pm.predict_failure("eng", days_ahead=30)
        entry = report["metrics"]["temperature"]
        assert entry["days_until_breach"] == pytest.approx(51.0)
        assert entry["risk"] == 0.0
        assert report["predicted_failure"] is False


# --------------------------------------------------------------------- #
# MTBF
# --------------------------------------------------------------------- #

class TestMTBF:
    def test_no_failures(self):
        pm = PredictiveMaintenance()
        summary = pm.mtbf("eng")
        assert summary["failure_count"] == 0
        assert summary["mtbf_days"] is None
        assert summary["days_until_next_failure"] is None

    def test_single_failure_has_no_interval(self):
        clock = FakeClock(start=T0 + 10 * DAY)
        pm = PredictiveMaintenance(now=clock)
        pm.log_failure("eng", timestamp=T0)
        summary = pm.mtbf("eng")
        assert summary["failure_count"] == 1
        assert summary["mtbf_days"] is None
        assert summary["days_since_last_failure"] == pytest.approx(10.0)
        assert summary["days_until_next_failure"] is None

    def test_mtbf_from_multiple_failures(self):
        clock = FakeClock(start=T0 + 90 * DAY)
        pm = PredictiveMaintenance(now=clock)
        for day in (0, 30, 60):
            pm.log_failure("eng", timestamp=T0 + day * DAY)
        summary = pm.mtbf("eng")
        assert summary["mtbf_days"] == pytest.approx(30.0)
        assert summary["days_since_last_failure"] == pytest.approx(30.0)
        # MTBF exactly consumed -> next failure due now.
        assert summary["days_until_next_failure"] == pytest.approx(0.0)

    def test_unsorted_failure_timestamps_are_ordered(self):
        pm = PredictiveMaintenance(now=FakeClock(start=T0 + 40 * DAY))
        pm.log_failure("eng", timestamp=T0 + 30 * DAY)
        pm.log_failure("eng", timestamp=T0)
        summary = pm.mtbf("eng")
        assert summary["mtbf_days"] == pytest.approx(30.0)
        assert summary["days_since_last_failure"] == pytest.approx(10.0)

    def test_log_failure_defaults_to_now_and_validates_id(self):
        clock = FakeClock()
        pm = PredictiveMaintenance(now=clock)
        pm.log_failure("eng")
        assert pm._failures["eng"] == [T0]
        with pytest.raises(ValueError):
            pm.log_failure("")


# --------------------------------------------------------------------- #
# predict_failure — fused verdict
# --------------------------------------------------------------------- #

class TestPredictFailure:
    def test_healthy_equipment(self):
        pm = PredictiveMaintenance()
        feed_series(pm, "eng", "temperature", 85.0, 0.0, 10)
        feed_series(pm, "eng", "vibration", 4.0, 0.0, 10)
        feed_series(pm, "eng", "oil_pressure", 45.0, 0.0, 10)
        feed_series(pm, "eng", "engine_hours", 100.0, 2.0, 10)
        report = pm.predict_failure("eng", days_ahead=30)
        assert report["predicted_failure"] is False
        assert report["drivers"] == []
        assert report["risk"] == 0.0
        assert report["severity"] == "info"
        # engine_hours still trends toward its 500 h interval, so a
        # far-future breach is reported even though nothing is urgent.
        assert report["earliest_breach_days"] == pytest.approx(191.0)

    def test_learning_metrics_reported(self):
        pm = PredictiveMaintenance(min_samples=5)
        feed_series(pm, "eng", "temperature", 80.0, 1.0, 3)
        report = pm.predict_failure("eng", days_ahead=30)
        assert report["metrics"]["temperature"] == {"status": "learning"}
        assert report["metrics"]["vibration"] == {"status": "learning"}

    def test_worst_metric_wins_and_is_a_driver(self):
        clock = FakeClock(start=T0 + 9 * DAY)
        pm = PredictiveMaintenance(now=clock)
        feed_series(pm, "eng", "temperature", 80.0, 0.5, 10)  # breach in 52 d
        feed_series(pm, "eng", "vibration", 4.0, 0.5, 10)     # breach in ~3 d
        report = pm.predict_failure("eng", days_ahead=30)
        assert report["predicted_failure"] is True
        assert "vibration" in report["drivers"]
        assert "temperature" not in report["drivers"]
        assert report["risk"] == report["metrics"]["vibration"]["risk"]
        assert report["earliest_breach_days"] == pytest.approx(
            report["metrics"]["vibration"]["days_until_breach"])

    def test_mtbf_can_drive_prediction(self):
        clock = FakeClock(start=T0 + 58 * DAY)
        pm = PredictiveMaintenance(now=clock)
        for day in (0, 30):
            pm.log_failure("eng", timestamp=T0 + day * DAY)
        # MTBF 30 days, 28 elapsed -> next failure in 2 days.
        report = pm.predict_failure("eng", days_ahead=30)
        assert "mtbf" in report["drivers"]
        assert report["mtbf"]["days_until_next_failure"] == pytest.approx(2.0)
        assert report["risk"] == pytest.approx(1.0 - 2.0 / 30.0)

    def test_severity_ladder(self):
        clock = FakeClock(start=T0 + 9 * DAY)
        pm = PredictiveMaintenance(now=clock)
        # Breach in 6 days over a 30-day horizon -> risk 0.8 -> critical.
        feed_series(pm, "eng", "temperature", 80.0, 2.0, 10)
        assert pm.predict_failure("eng", days_ahead=30)["severity"] == "critical"
        # Same trend, tighter horizon -> lower risk band.
        report = pm.predict_failure("eng", days_ahead=30)
        assert report["risk"] == pytest.approx(0.8)

        pm2 = PredictiveMaintenance(now=clock)
        # Breach in 11 days over 30 -> risk ~0.633 -> warning.
        feed_series(pm2, "eng", "temperature", 80.0, 1.5, 10)  # last 93.5
        assert pm2.predict_failure("eng", days_ahead=30)["severity"] == "warning"

    def test_rejects_nonpositive_horizon(self):
        pm = PredictiveMaintenance()
        with pytest.raises(ValueError):
            pm.predict_failure("eng", days_ahead=0)

    def test_unknown_equipment_is_inert(self):
        pm = PredictiveMaintenance()
        report = pm.predict_failure("ghost", days_ahead=30)
        assert report["predicted_failure"] is False
        assert report["risk"] == 0.0
        assert all(m == {"status": "learning"}
                   for m in report["metrics"].values())


# --------------------------------------------------------------------- #
# Maintenance schedule
# --------------------------------------------------------------------- #

class TestMaintenanceSchedule:
    def build_fleet(self):
        clock = FakeClock(start=T0 + 9 * DAY)
        pm = PredictiveMaintenance(now=clock)
        # urgent: vibration breaches in ~3 days.
        feed_series(pm, "urgent", "vibration", 4.0, 0.5, 10)
        # soon: temperature breaches in 6 days.
        feed_series(pm, "soon", "temperature", 80.0, 2.0, 10)
        # healthy: flat everywhere.
        feed_series(pm, "healthy", "temperature", 85.0, 0.0, 10)
        feed_series(pm, "healthy", "vibration", 4.0, 0.0, 10)
        return pm

    def test_sorted_soonest_first(self):
        schedule = self.build_fleet().get_maintenance_schedule()
        ids = [item["equipment_id"] for item in schedule]
        assert ids[0] == "urgent"
        assert ids[1] == "soon"
        assert ids[-1] == "healthy"
        assert schedule[0]["due_in_days"] < schedule[1]["due_in_days"]
        assert schedule[-1]["due_in_days"] is None

    def test_entry_shape_and_actions(self):
        schedule = self.build_fleet().get_maintenance_schedule()
        urgent = schedule[0]
        assert urgent["drivers"] == ["vibration"]
        assert urgent["recommended_action"] == "inspect vibration trend"
        assert urgent["severity"] in ("warning", "critical")
        healthy = schedule[-1]
        assert healthy["drivers"] == []
        assert healthy["recommended_action"] == "routine check"
        assert healthy["risk"] == 0.0

    def test_includes_failure_only_equipment(self):
        clock = FakeClock(start=T0 + 58 * DAY)
        pm = PredictiveMaintenance(now=clock)
        for day in (0, 30):
            pm.log_failure("mtbf-only", timestamp=T0 + day * DAY)
        feed_series(pm, "healthy", "temperature", 85.0, 0.0, 10)
        schedule = pm.get_maintenance_schedule(days_ahead=30)
        assert schedule[0]["equipment_id"] == "mtbf-only"
        assert schedule[0]["drivers"] == ["mtbf"]
        assert schedule[0]["recommended_action"] == "inspect mtbf"

    def test_empty_fleet_returns_empty_schedule(self):
        assert PredictiveMaintenance().get_maintenance_schedule() == []

    def test_reset_clears_equipment(self):
        pm = self.build_fleet()
        pm.reset("urgent")
        ids = [i["equipment_id"] for i in pm.get_maintenance_schedule()]
        assert "urgent" not in ids
        pm.reset()
        assert pm.get_maintenance_schedule() == []


# --------------------------------------------------------------------- #
# End to end
# --------------------------------------------------------------------- #

class TestEndToEnd:
    def test_degrading_engine_rises_to_critical(self):
        """An engine degrading over a simulated month must escalate from
        routine to a critical, dated prediction naming the right driver."""
        pm = PredictiveMaintenance()
        clock = FakeClock()
        pm._now = clock

        # 30 days of telemetry: temperature creeping 0.8 degC/day from 85;
        # engine hours and oil pressure move too slowly to matter here.
        for day in range(30):
            clock.t = T0 + day * DAY
            pm.log_reading("main-engine", {
                "engine_hours": 100.0 + 2.0 * day,
                "temperature": 85.0 + 0.8 * day,
                "vibration": 4.0,
                "oil_pressure": 45.0 - 0.1 * day,
            })

        report = pm.predict_failure("main-engine", days_ahead=45)
        # Temperature: last = 108.2, breach of 110 in (110-108.2)/0.8 = 2.25 d.
        assert report["metrics"]["temperature"]["days_until_breach"] == \
            pytest.approx(2.25)
        assert report["predicted_failure"] is True
        assert report["drivers"] == ["temperature"]
        assert report["severity"] == "critical"
        assert report["earliest_breach_days"] == pytest.approx(2.25)

        schedule = pm.get_maintenance_schedule(days_ahead=45)
        assert schedule[0]["equipment_id"] == "main-engine"
        assert schedule[0]["due_in_days"] == pytest.approx(2.25)

    def test_default_thresholds_are_exposed(self):
        assert set(DEFAULT_THRESHOLDS) == {
            "engine_hours", "temperature", "vibration", "oil_pressure"}
        assert DEFAULT_THRESHOLDS["oil_pressure"]["direction"] == "low"
