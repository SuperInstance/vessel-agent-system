"""Tests for the AELMA statistical anomaly detector (twin/anomaly_detector.py).

Coverage:

  1. Construction & validation (window, thresholds, algorithm selection).
  2. Observation — rolling window, non-numeric / non-finite rejection,
     observe_frame, reset.
  3. z-score algorithm with a synthetic Gaussian-ish baseline + spike.
  4. IQR algorithm — robust fences, contaminated window.
  5. Moving-average deviation — flat channel where z-score is useless.
  6. Learning gate — no flags before min_samples.
  7. get_anomaly_score — bounds, threshold equivalence with is_anomaly,
     channel-less worst-score probe.
  8. WatcherRegistry integration — rule registration, raise_alert firing
     on synthetic anomalies, payload schema, priority ordering, cooldown
     suppression via WatcherHistory.

Run from the repo root:  python -m pytest tests/anomaly_detector.test.py -v
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import pytest

# Make the repository root importable regardless of pytest's rootdir handling.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twin.anomaly_detector import (  # noqa: E402
    ALGO_IQR,
    ALGO_MA_DEV,
    ALGO_ZSCORE,
    AnomalyDetector,
)
from twin.watcher_history import WatcherHistory  # noqa: E402
from twin.watchers import WatcherRegistry  # noqa: E402


def feed(detector: AnomalyDetector, channel: str, values) -> None:
    """Feed a baseline of observations into the detector."""
    for v in values:
        detector.observe_telemetry(channel, v)


class FakeClock:
    """Deterministic monotonic clock, advanced manually by tests."""

    def __init__(self, start: float = 1_000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def gaussian_baseline(mean: float, stdev: float, n: int, seed: int = 42):
    rng = random.Random(seed)
    return [rng.gauss(mean, stdev) for _ in range(n)]


# --------------------------------------------------------------------- #
# Construction & validation
# --------------------------------------------------------------------- #

class TestConstruction:
    def test_defaults(self):
        d = AnomalyDetector()
        assert d.window_size == 60
        assert d.min_samples == 10
        assert d.algorithms == (ALGO_ZSCORE, ALGO_IQR, ALGO_MA_DEV)

    def test_rejects_tiny_window(self):
        with pytest.raises(ValueError):
            AnomalyDetector(window_size=3)

    def test_rejects_nonpositive_thresholds(self):
        with pytest.raises(ValueError):
            AnomalyDetector(z_threshold=0)
        with pytest.raises(ValueError):
            AnomalyDetector(iqr_k=-1)
        with pytest.raises(ValueError):
            AnomalyDetector(ma_dev_threshold=0)

    def test_rejects_unknown_algorithm(self):
        with pytest.raises(ValueError):
            AnomalyDetector(algorithms=("grubbs",))

    def test_rejects_empty_algorithm_set(self):
        with pytest.raises(ValueError):
            AnomalyDetector(algorithms=())


# --------------------------------------------------------------------- #
# Observation
# --------------------------------------------------------------------- #

class TestObservation:
    def test_rolling_window_drops_oldest(self):
        d = AnomalyDetector(window_size=5, min_samples=1)
        feed(d, "depth_m", [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
        stats = d.stats("depth_m")
        assert stats.count == 5
        assert stats.mean == pytest.approx(5.0)  # 3..7

    def test_ignores_non_numeric_and_non_finite(self):
        d = AnomalyDetector(min_samples=1)
        for bad in ("deep", None, True, float("nan"), float("inf"), [1.0]):
            d.observe_telemetry("depth_m", bad)
        assert d.stats("depth_m") is None

    def test_observe_frame_records_numeric_channels_only(self):
        d = AnomalyDetector(min_samples=1)
        observed = d.observe_frame({
            "depth_m": 11.4,
            "sog_kn": 5,
            "source": "sim",
            "ok": True,
            "nan_channel": float("nan"),
        })
        assert sorted(observed) == ["depth_m", "sog_kn"]
        assert d.stats("depth_m").mean == pytest.approx(11.4)
        assert d.stats("sog_kn").mean == pytest.approx(5.0)

    def test_reset_single_channel_and_all(self):
        d = AnomalyDetector(min_samples=1)
        feed(d, "a", [1.0, 2.0])
        feed(d, "b", [1.0, 2.0])
        d.reset("a")
        assert d.stats("a") is None
        assert d.stats("b") is not None
        d.reset()
        assert d.stats("b") is None

    def test_stats_quartiles(self):
        d = AnomalyDetector(min_samples=1)
        feed(d, "x", [1.0, 2.0, 3.0, 4.0, 5.0])
        stats = d.stats("x")
        assert stats.median == pytest.approx(3.0)
        assert stats.q1 == pytest.approx(2.0)
        assert stats.q3 == pytest.approx(4.0)
        assert stats.iqr == pytest.approx(2.0)
        assert stats.stdev == pytest.approx(math.sqrt(2.0))


# --------------------------------------------------------------------- #
# z-score
# --------------------------------------------------------------------- #

class TestZScore:
    def test_spike_flags(self):
        d = AnomalyDetector(
            min_samples=20, z_threshold=3.0, algorithms=(ALGO_ZSCORE,))
        feed(d, "depth_m", gaussian_baseline(10.0, 0.5, 50))
        assert d.is_anomaly("depth_m", 15.0)   # ~10 sigma out
        assert not d.is_anomaly("depth_m", 10.5)

    def test_threshold_boundary(self):
        d = AnomalyDetector(
            min_samples=4, z_threshold=2.0, algorithms=(ALGO_ZSCORE,))
        # mean=10, pstdev=2 -> z(14.1) = 2.05 flags, z(13.9) = 1.95 doesn't
        feed(d, "x", [8.0, 12.0, 8.0, 12.0])
        assert not d.is_anomaly("x", 13.9)
        assert d.is_anomaly("x", 14.1)

    def test_zero_variance_window_uses_relative_deviation(self):
        d = AnomalyDetector(
            min_samples=5, z_threshold=3.0, algorithms=(ALGO_ZSCORE,))
        feed(d, "x", [100.0] * 20)
        assert not d.is_anomaly("x", 100.0)
        assert not d.is_anomaly("x", 100.0 + 1e-6)   # float noise
        assert d.is_anomaly("x", 200.0)              # real jump


# --------------------------------------------------------------------- #
# IQR
# --------------------------------------------------------------------- #

class TestIQR:
    def test_outlier_beyond_fences(self):
        d = AnomalyDetector(
            min_samples=8, iqr_k=1.5, algorithms=(ALGO_IQR,))
        feed(d, "sog_kn", [4.0, 4.5, 5.0, 5.0, 5.5, 6.0, 5.2, 4.8, 5.1, 5.4])
        assert d.is_anomaly("sog_kn", 25.0)
        assert d.is_anomaly("sog_kn", -10.0)
        assert not d.is_anomaly("sog_kn", 5.6)

    def test_contaminated_window_stays_robust(self):
        # A few past outliers barely move the quartiles, unlike the mean —
        # the fence still catches the next regime shift.
        d = AnomalyDetector(
            min_samples=10, iqr_k=1.5, algorithms=(ALGO_IQR,))
        baseline = gaussian_baseline(10.0, 0.3, 40)
        feed(d, "depth_m", baseline + [30.0, 32.0])  # two past outliers
        assert d.is_anomaly("depth_m", 25.0)
        assert not d.is_anomaly("depth_m", 10.2)

    def test_exact_fence_is_not_flagged(self):
        d = AnomalyDetector(
            min_samples=5, iqr_k=1.5, algorithms=(ALGO_IQR,))
        feed(d, "x", [1.0, 2.0, 3.0, 4.0, 5.0])
        # q1=2, q3=4, iqr=2 -> upper fence = 7.0 exactly
        assert not d.is_anomaly("x", 7.0)
        assert d.is_anomaly("x", 7.1)


# --------------------------------------------------------------------- #
# Moving-average deviation
# --------------------------------------------------------------------- #

class TestMovingAverageDeviation:
    def test_relative_deviation_flags(self):
        d = AnomalyDetector(
            min_samples=10, ma_dev_threshold=0.5, algorithms=(ALGO_MA_DEV,))
        feed(d, "sog_kn", [5.0] * 30)
        assert d.is_anomaly("sog_kn", 9.0)     # 80% above the mean
        assert not d.is_anomaly("sog_kn", 6.0)  # 20% above

    def test_flat_low_variance_channel(self):
        # RPM-like channel with tiny noise: z-score is hypersensitive here,
        # the relative-deviation rule is the useful signal.
        d = AnomalyDetector(
            min_samples=20, ma_dev_threshold=0.3, algorithms=(ALGO_MA_DEV,))
        feed(d, "rpm", gaussian_baseline(800.0, 0.5, 40))
        assert not d.is_anomaly("rpm", 801.0)
        assert d.is_anomaly("rpm", 1200.0)


# --------------------------------------------------------------------- #
# Learning gate
# --------------------------------------------------------------------- #

class TestLearningGate:
    def test_no_flags_below_min_samples(self):
        d = AnomalyDetector(min_samples=10)
        feed(d, "depth_m", [10.0] * 9)
        assert not d.is_anomaly("depth_m", 9999.0)
        report = d.explain("depth_m", 9999.0)
        assert report["is_anomaly"] is False
        assert all(
            a["detail"] == "learning" for a in report["algorithms"].values())

    def test_flags_once_window_ready(self):
        d = AnomalyDetector(min_samples=10, z_threshold=3.0)
        feed(d, "depth_m", gaussian_baseline(10.0, 0.5, 10))
        assert d.is_anomaly("depth_m", 9999.0)

    def test_unseen_channel_is_normal(self):
        d = AnomalyDetector()
        assert not d.is_anomaly("ghost", 1e9)
        assert d.get_anomaly_score("ghost", 1e9) == 0.0


# --------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------- #

class TestScoring:
    def test_score_bounds_and_threshold_equivalence(self):
        d = AnomalyDetector(min_samples=20, z_threshold=3.0)
        feed(d, "depth_m", gaussian_baseline(10.0, 0.5, 50))
        for value in (9.0, 10.0, 11.0, 12.0, 14.0, 20.0, 100.0):
            score = d.get_anomaly_score("depth_m", value)
            assert 0.0 <= score < 1.0
            assert (score > 0.5) == d.is_anomaly("depth_m", value)

    def test_score_grows_with_extremity(self):
        d = AnomalyDetector(min_samples=20, z_threshold=3.0)
        feed(d, "depth_m", gaussian_baseline(10.0, 0.5, 50))
        scores = [d.get_anomaly_score("depth_m", v)
                  for v in (10.0, 12.0, 14.0, 18.0)]
        assert scores == sorted(scores)
        assert scores[-1] > scores[0]

    def test_score_defaults_to_latest_observation(self):
        d = AnomalyDetector(min_samples=5, z_threshold=3.0)
        feed(d, "x", gaussian_baseline(10.0, 0.5, 20))
        d.observe_telemetry("x", 30.0)
        assert d.get_anomaly_score("x") == pytest.approx(
            d.get_anomaly_score("x", 30.0))

    def test_channel_less_score_is_worst_across_channels(self):
        d = AnomalyDetector(min_samples=5, z_threshold=3.0)
        feed(d, "calm", gaussian_baseline(10.0, 0.5, 20))
        feed(d, "wild", gaussian_baseline(10.0, 0.5, 20))
        d.observe_telemetry("calm", 10.1)
        d.observe_telemetry("wild", 30.0)
        assert d.get_anomaly_score() == pytest.approx(
            d.get_anomaly_score("wild"))
        assert d.get_anomaly_score() > 0.5

    def test_severity_ladder(self):
        d = AnomalyDetector(min_samples=20, z_threshold=3.0)
        feed(d, "depth_m", gaussian_baseline(10.0, 0.5, 60))
        assert d.explain("depth_m", 10.1)["severity"] == "info"
        assert d.explain("depth_m", 12.0)["severity"] == "warning"
        assert d.explain("depth_m", 15.0)["severity"] == "critical"

    def test_non_numeric_explain_reports_error(self):
        d = AnomalyDetector()
        assert d.explain("x", "nope")["error"] == "non-numeric value"
        assert d.explain("x", float("nan"))["error"] == "non-finite value"
        assert not d.is_anomaly("x", "nope")


# --------------------------------------------------------------------- #
# WatcherRegistry integration
# --------------------------------------------------------------------- #

def registry_with_detector(**detector_kw):
    """Detector + registry with anomaly rules for depth_m and sog_kn."""
    detector_kw.setdefault("min_samples", 10)
    detector_kw.setdefault("z_threshold", 3.0)
    detector = AnomalyDetector(**detector_kw)
    feed(detector, "depth_m", gaussian_baseline(10.0, 0.5, 60))
    feed(detector, "sog_kn", gaussian_baseline(5.0, 0.3, 60))
    registry = WatcherRegistry()
    rule_ids = detector.register_watchers(
        registry, channels=["depth_m", "sog_kn"], cooldown_s=30.0)
    return detector, registry, rule_ids


class TestWatcherIntegration:
    def test_registers_one_rule_per_channel(self):
        _, registry, rule_ids = registry_with_detector()
        assert rule_ids == ["anomaly-depth_m", "anomaly-sog_kn"]
        assert len(registry) == 2
        rule = registry.get("anomaly-depth_m")
        assert rule["action"] == "raise_alert"
        assert rule["cooldown_s"] == 30.0

    def test_normal_frame_fires_nothing(self):
        _, registry, _ = registry_with_detector()
        assert registry.evaluate({"depth_m": 10.2, "sog_kn": 5.1}) == []

    def test_synthetic_anomaly_fires_raise_alert(self):
        _, registry, _ = registry_with_detector()
        actions = registry.evaluate({"depth_m": 40.0, "sog_kn": 5.1})
        assert len(actions) == 1
        action = actions[0]
        assert action["action"] == "raise_alert"
        assert action["rule_id"] == "anomaly-depth_m"
        payload = action["payload"]
        # raise_alert schema fields
        assert payload["severity"] in ("warning", "critical")
        assert payload["code"] == "ANOMALY_DEPTH_M"
        assert "depth_m" in payload["message"]
        assert payload["channel"] == "depth_m"
        assert payload["value"] == 40.0
        assert payload["score"] > 0.5
        assert action["priority"] > 0.5
        assert action["reason"]

    def test_multiple_channels_fire_together(self):
        _, registry, _ = registry_with_detector()
        actions = registry.evaluate({"depth_m": 40.0, "sog_kn": 30.0})
        assert {a["rule_id"] for a in actions} == {
            "anomaly-depth_m", "anomaly-sog_kn"}

    def test_deeper_anomaly_outranks_marginal_one(self):
        detector, registry, _ = registry_with_detector()
        marginal = registry.evaluate({"depth_m": 12.0, "sog_kn": 5.0})
        extreme = registry.evaluate({"depth_m": 25.0, "sog_kn": 5.0})
        assert marginal and extreme
        assert extreme[0]["priority"] > marginal[0]["priority"]
        assert marginal[0]["payload"]["severity"] == "warning"
        assert extreme[0]["payload"]["severity"] == "critical"

    def test_missing_or_bad_channel_value_does_not_fire(self):
        _, registry, _ = registry_with_detector()
        assert registry.evaluate({"sog_kn": 5.1}) == []
        assert registry.evaluate({"depth_m": "deep", "sog_kn": 5.1}) == []
        assert registry.evaluate(
            {"depth_m": float("nan"), "sog_kn": 5.1}) == []

    def test_cooldown_suppresses_repeat_alerts(self):
        clock = FakeClock()
        detector = AnomalyDetector(min_samples=10, z_threshold=3.0)
        feed(detector, "depth_m", gaussian_baseline(10.0, 0.5, 60))
        registry = WatcherRegistry(history=WatcherHistory(), now=clock)
        detector.register_watchers(
            registry, channels=["depth_m"], cooldown_s=30.0)
        fired = []
        registry.on("fired", fired.append)

        first = registry.evaluate({"depth_m": 40.0})
        assert len(first) == 1 and len(fired) == 1

        # Inside the cooldown window any repeat is suppressed.
        assert registry.evaluate({"depth_m": 40.0}) == []
        assert registry.evaluate({"depth_m": 55.0}) == []
        assert len(fired) == 1

        # Past the cooldown the alert fires again.
        clock.advance(31.0)
        second = registry.evaluate({"depth_m": 40.0})
        assert len(second) == 1
        assert len(fired) == 2

    def test_default_channels_from_observed_windows(self):
        detector = AnomalyDetector(min_samples=1)
        feed(detector, "depth_m", [10.0, 11.0, 9.0, 10.0, 10.0])
        registry = WatcherRegistry()
        rule_ids = detector.register_watchers(registry)
        assert rule_ids == ["anomaly-depth_m"]

    def test_end_to_end_observe_then_evaluate_loop(self):
        """The canonical hot path: observe the frame, then evaluate it."""
        detector, registry, _ = registry_with_detector()
        fired = []
        registry.on("fired", fired.append)
        frames = [
            {"depth_m": v, "sog_kn": 5.0}
            for v in gaussian_baseline(10.0, 0.5, 30, seed=7)
        ]
        frames.append({"depth_m": 50.0, "sog_kn": 5.0})  # synthetic hit
        for f in frames:
            detector.observe_frame(f)
            registry.evaluate(f)
        # Exactly the injected anomaly fires; the baseline stays quiet.
        assert len(fired) == 1
        assert fired[0]["payload"]["channel"] == "depth_m"
        assert fired[0]["payload"]["value"] == 50.0
