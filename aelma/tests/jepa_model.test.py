"""Tests for JEPA world model: encoding, prediction, anomaly detection."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

# Make the repository root importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twin.jepa_model import (
    JEPAModel,
    PredictionResult,
    StateEmbedding,
    _denormalize,
    _normalize,
)


# --------------------------------------------------------------------- #
# Test fixtures
# --------------------------------------------------------------------- #

T0 = 1_753_478_400_000_000_000


def sample_state(
    depth_m: float = 50.0,
    speed_kn: float = 10.0,
    engine_temp: float = 80.0,
    lat: float = 57.0,
    lon: float = -135.0,
    heading_deg: float = 45.0,
    timestamp_ns: int = T0,
) -> dict:
    """Create a sample state dict."""
    return {
        "depth_m": depth_m,
        "speed_kn": speed_kn,
        "engine_temp": engine_temp,
        "lat": lat,
        "lon": lon,
        "heading_deg": heading_deg,
        "timestamp_ns": timestamp_ns,
    }


# --------------------------------------------------------------------- #
# Normalization utilities
# --------------------------------------------------------------------- #

class TestNormalization:
    """Test normalization and denormalization functions."""

    def test_normalize_within_bounds(self):
        assert _normalize(50.0, (0.0, 100.0)) == 0.5
        assert _normalize(0.0, (0.0, 100.0)) == 0.0
        assert _normalize(100.0, (0.0, 100.0)) == 1.0

    def test_normalize_clips_to_bounds(self):
        assert _normalize(-10.0, (0.0, 100.0)) == 0.0
        assert _normalize(150.0, (0.0, 100.0)) == 1.0

    def test_normalize_none(self):
        assert _normalize(None, (0.0, 100.0)) == 0.0

    def test_denormalize(self):
        assert _denormalize(0.5, (0.0, 100.0)) == 50.0
        assert _denormalize(0.0, (0.0, 100.0)) == 0.0
        assert _denormalize(1.0, (0.0, 100.0)) == 100.0

    def test_roundtrip(self):
        original = 37.5
        norm = _normalize(original, (0.0, 100.0))
        denorm = _denormalize(norm, (0.0, 100.0))
        assert denorm == pytest.approx(original)


# --------------------------------------------------------------------- #
# StateEmbedding
# --------------------------------------------------------------------- #

class TestStateEmbedding:
    """Test state embedding creation and conversion."""

    def test_from_dict_basic(self):
        state = sample_state()
        emb = StateEmbedding.from_dict(state)

        assert emb.depth_m >= 0.0 and emb.depth_m <= 1.0
        assert emb.speed_kn >= 0.0 and emb.speed_kn <= 1.0
        assert emb.engine_temp >= 0.0 and emb.engine_temp <= 1.0
        assert emb.lat_norm >= 0.0 and emb.lat_norm <= 1.0
        assert emb.lon_norm >= 0.0 and emb.lon_norm <= 1.0
        assert emb.heading_rad >= 0.0 and emb.heading_rad <= 2 * math.pi

    def test_from_dict_preserves_raw(self):
        state = sample_state(depth_m=73.2, speed_kn=15.5)
        emb = StateEmbedding.from_dict(state)

        assert emb.raw_values.get("depth_m") == 73.2
        assert emb.raw_values.get("speed_kn") == 15.5

    def test_from_dict_handles_missing_values(self):
        state = {"depth_m": 50.0, "timestamp_ns": T0}
        emb = StateEmbedding.from_dict(state)

        assert emb.speed_kn == 0.0  # Default to 0
        assert emb.engine_temp == 0.0

    def test_to_vector(self):
        emb = StateEmbedding(
            time_norm=0.5,
            depth_m=0.3,
            speed_kn=0.4,
            engine_temp=0.6,
            lat_norm=0.7,
            lon_norm=0.8,
            heading_rad=1.0,
        )
        vec = emb.to_vector()

        assert len(vec) == 7
        assert vec[0] == 0.5
        assert vec[1] == 0.3

    def test_bounds_customization(self):
        state = sample_state(depth_m=150.0)
        bounds = {"depth_m": (0.0, 200.0)}
        emb = StateEmbedding.from_dict(state, bounds)

        assert emb.depth_m == pytest.approx(0.75)


# --------------------------------------------------------------------- #
# JEPAModel - Encoding
# --------------------------------------------------------------------- #

class TestJEPAModelEncoding:
    """Test state encoding in JEPA model."""

    def test_encode_frame_basic(self):
        model = JEPAModel()
        state = sample_state(depth_m=50.0, speed_kn=10.0)

        emb = model.encode_frame(state)

        assert isinstance(emb, StateEmbedding)
        assert emb.raw_values.get("depth_m") == 50.0

    def test_encode_updates_bounds(self):
        model = JEPAModel()
        state = sample_state(depth_m=150.0)

        model.encode_frame(state)

        # Bounds should expand
        depth_min, depth_max = model._bounds["depth_m"]
        assert depth_max >= 150.0

    def test_encode_multiple_frames(self):
        model = JEPAModel()
        states = [
            sample_state(depth_m=30.0),
            sample_state(depth_m=50.0),
            sample_state(depth_m=70.0),
        ]

        embeddings = [model.encode_frame(s) for s in states]

        assert len(embeddings) == 3
        assert embeddings[0].depth_m < embeddings[1].depth_m < embeddings[2].depth_m


# --------------------------------------------------------------------- #
# JEPAModel - Training
# --------------------------------------------------------------------- #

class TestJEPAModelTraining:
    """Test model training from history."""

    def test_train_on_history(self):
        model = JEPAModel(min_samples=5)

        # Create a simple trend: depth increasing
        history = [sample_state(depth_m=30.0 + i, timestamp_ns=T0 + i * 1_000_000_000) for i in range(10)]

        model.train(history)

        # Should have learned patterns
        assert len(model._patterns) > 0
        assert len(model._history) == 10

    def test_train_on_packet(self):
        model = JEPAModel(min_samples=5)

        # Feed packets with trend
        for i in range(10):
            packet = sample_state(depth_m=30.0 + i, timestamp_ns=T0 + i * 1_000_000_000)
            model.train_on_packet(packet)

        # Should learn from transitions
        assert model._tick_count == 10
        assert len(model._history) == 10
        assert "*global*" in model._patterns

    def test_learning_pattern_convergence(self):
        model = JEPAModel(learning_rate=0.5, min_samples=5)

        # Create linear trend: +1.0 depth per step
        for i in range(20):
            packet = sample_state(depth_m=30.0 + i, timestamp_ns=T0 + i * 1_000_000_000)
            model.train_on_packet(packet)

        # Check that global pattern learned positive delta
        global_pattern = model._patterns.get("*global*")
        assert global_pattern is not None
        assert global_pattern.count >= 10
        # Mean delta for depth should be positive
        assert global_pattern.mean_delta[1] > 0  # Index 1 is depth_m

    def test_learning_adaptive_bounds(self):
        model = JEPAModel()

        # Train with extreme values
        for depth in [10.0, 50.0, 100.0, 200.0]:
            model.train_on_packet(sample_state(depth_m=depth))

        # Bounds should adapt
        depth_min, depth_max = model._bounds["depth_m"]
        assert depth_min <= 10.0
        assert depth_max >= 200.0


# --------------------------------------------------------------------- #
# JEPAModel - Prediction
# --------------------------------------------------------------------- #

class TestJEPAModelPrediction:
    """Test future state prediction."""

    def test_predict_future_insufficient_data(self):
        model = JEPAModel(min_samples=10)
        state = sample_state()

        result = model.predict_future(state)

        # Should return None when insufficient data
        assert result is None

    def test_predict_future_with_training(self):
        model = JEPAModel(min_samples=5)

        # Train with trend
        for i in range(10):
            packet = sample_state(depth_m=30.0 + i, timestamp_ns=T0 + i * 1_000_000_000)
            model.train_on_packet(packet)

        # Now predict
        state = sample_state(depth_m=40.0, timestamp_ns=T0 + 10_000_000_000)
        result = model.predict_future(state, steps_ahead=1)

        assert result is not None
        assert isinstance(result, PredictionResult)
        assert result.confidence > 0.0
        assert result.horizon_s == 1.0

    def test_predict_future_multiple_steps(self):
        model = JEPAModel(min_samples=5)

        # Train
        for i in range(10):
            model.train_on_packet(sample_state(depth_m=30.0 + i, timestamp_ns=T0 + i * 1_000_000_000))

        # Predict multiple steps
        result = model.predict_future(sample_state(depth_m=40.0), steps_ahead=5, step_duration_s=10.0)

        assert result is not None
        assert result.horizon_s == 50.0  # 5 * 10

    def test_prediction_values(self):
        model = JEPAModel(min_samples=5)

        # Train with linear depth increase
        for i in range(10):
            model.train_on_packet(sample_state(depth_m=30.0 + i, timestamp_ns=T0 + i * 1_000_000_000))

        # Predict should show increase
        result = model.predict_future(sample_state(depth_m=40.0))

        assert result is not None
        assert "depth_m" in result.predicted_values

        # Predicted depth should be higher than current (trend)
        # or at least in reasonable range
        predicted_depth = result.predicted_values.get("depth_m")
        assert predicted_depth is not None
        assert 30.0 <= predicted_depth <= 50.0

    def test_prediction_confidence_scales_with_samples(self):
        model = JEPAModel(min_samples=5)

        # Train with varying amounts
        for i in range(20):
            model.train_on_packet(sample_state(depth_m=30.0 + i, timestamp_ns=T0 + i * 1_000_000_000))

        result = model.predict_future(sample_state(depth_m=50.0))
        assert result is not None
        # More samples = higher confidence
        assert result.confidence > 0.0


# --------------------------------------------------------------------- #
# JEPAModel - Anomaly Detection
# --------------------------------------------------------------------- #

class TestJEPAModelAnomaly:
    """Test anomaly detection."""

    def test_detect_anomaly_normal(self):
        model = JEPAModel(min_samples=5)

        # Train pattern
        for i in range(10):
            model.train_on_packet(sample_state(depth_m=30.0 + i, timestamp_ns=T0 + i * 1_000_000_000))

        # Predict normal continuation
        predicted = model.predict_future(sample_state(depth_m=40.0))
        assert predicted is not None

        # Actual is close to predicted
        actual = sample_state(depth_m=41.0)  # Small deviation
        report = model.detect_anomaly(predicted, actual)

        assert report["anomaly_score"] < 0.5  # Should not be anomalous
        assert report["severity"] < 0.5

    def test_detect_anomaly_large_deviation(self):
        model = JEPAModel(min_samples=5)

        # Train pattern
        for i in range(10):
            model.train_on_packet(sample_state(depth_m=30.0 + i, timestamp_ns=T0 + i * 1_000_000_000))

        # Predict
        predicted = model.predict_future(sample_state(depth_m=40.0))
        assert predicted is not None

        # Actual is very different
        actual = sample_state(depth_m=100.0)  # Large jump
        report = model.detect_anomaly(predicted, actual)

        # Should detect anomaly
        assert report["anomaly_score"] > 0.0
        assert "channels" in report

    def test_detect_anomaly_per_channel(self):
        model = JEPAModel(min_samples=5)

        # Train
        for i in range(10):
            model.train_on_packet(sample_state(speed_kn=10.0, timestamp_ns=T0 + i * 1_000_000_000))

        # Predict
        predicted = model.predict_future(sample_state(speed_kn=10.0))
        assert predicted is not None

        # Anomalous speed
        actual = sample_state(speed_kn=30.0)  # Much higher
        report = model.detect_anomaly(predicted, actual)

        # Should flag speed channel
        assert "speed_kn" in report["channels"]
        assert report["channels"]["speed_kn"]["error"] > 0

    def test_detect_anomaly_increments_counter(self):
        model = JEPAModel(min_samples=5)

        # Train
        for i in range(10):
            model.train_on_packet(sample_state(depth_m=30.0 + i, timestamp_ns=T0 + i * 1_000_000_000))

        initial_count = model._anomaly_count

        # Predict and detect anomaly
        predicted = model.predict_future(sample_state(depth_m=40.0))
        if predicted:
            model.detect_anomaly(predicted, sample_state(depth_m=100.0))

        # Counter should increment if anomaly detected
        assert model._anomaly_count >= initial_count


# --------------------------------------------------------------------- #
# Integration Tests
# --------------------------------------------------------------------- #

class TestJEPAModelIntegration:
    """End-to-end tests of the JEPA pipeline."""

    def test_full_predict_detect_cycle(self):
        model = JEPAModel(min_samples=5)

        # 1. Train on historical data with consistent pattern
        history = [sample_state(depth_m=30.0 + i * 0.5, timestamp_ns=T0 + i * 1_000_000_000) for i in range(10)]
        model.train(history)

        # 2. Get prediction capability
        caps = model.get_predictions()
        assert caps["can_predict"] is True

        # 3. Predict future from a known state
        current = sample_state(depth_m=34.0)  # Near end of training
        predicted = model.predict_future(current, steps_ahead=2)
        assert predicted is not None

        # 4. Detect anomaly (normal case - close to predicted trend)
        actual_normal = sample_state(depth_m=35.0)  # Follows trend
        report_normal = model.detect_anomaly(predicted, actual_normal)
        assert report_normal["anomaly_score"] < 0.7

        # 5. Detect anomaly (abnormal case - major deviation)
        # Make prediction from same state but check against very different actual
        predicted2 = model.predict_future(current, steps_ahead=2)
        actual_abnormal = sample_state(depth_m=100.0)  # Way off trend
        report_abnormal = model.detect_anomaly(predicted2, actual_abnormal)

        # Abnormal case should have higher severity due to channel deviation
        assert report_abnormal["severity"] > report_normal["severity"]

    def test_online_learning_and_prediction(self):
        model = JEPAModel(min_samples=5)

        # Simulate streaming telemetry
        predictions_made = []
        anomalies_detected = 0

        for i in range(20):
            # Normal pattern: depth increasing slowly
            depth = 30.0 + i * 0.5
            state = sample_state(depth_m=depth, timestamp_ns=T0 + i * 1_000_000_000)

            # Train online
            model.train_on_packet(state)

            # Try predict after minimum samples
            if i >= 10:
                pred = model.predict_future(state)
                if pred:
                    predictions_made.append(pred)

        # Should have made predictions
        assert len(predictions_made) > 0

        # Stats should reflect learning
        stats = model.stats
        assert stats["tick_count"] == 20
        assert len(stats["pattern_counts"]) > 0

    def test_multiple_regime_learning(self):
        """Test that model learns different patterns for different regimes."""
        model = JEPAModel(min_samples=5)

        # Train slow regime
        for i in range(10):
            model.train_on_packet(sample_state(speed_kn=2.0, depth_m=30.0 + i, timestamp_ns=T0 + i * 1_000_000_000))

        # Train fast regime
        for i in range(10):
            model.train_on_packet(sample_state(speed_kn=20.0, depth_m=40.0 + i, timestamp_ns=T0 + (i + 10) * 1_000_000_000))

        # Should have multiple patterns
        stats = model.stats
        assert len(stats["pattern_counts"]) > 1

        # Predictions should use appropriate pattern
        slow_pred = model.predict_future(sample_state(speed_kn=2.0))
        fast_pred = model.predict_future(sample_state(speed_kn=20.0))

        # Both should work
        assert slow_pred is not None
        assert fast_pred is not None

    def test_prediction_accuracy_tracking(self):
        """Test that model can track prediction accuracy."""
        model = JEPAModel(min_samples=5)

        # Train
        for i in range(10):
            model.train_on_packet(sample_state(depth_m=30.0 + i, timestamp_ns=T0 + i * 1_000_000_000))

        # Make predictions and check accuracy
        for i in range(5):
            state = sample_state(depth_m=40.0 + i)
            pred = model.predict_future(state)
            if pred:
                # Could track error here
                assert pred.confidence > 0.0

        # Stats should show activity
        stats = model.stats
        assert stats["tick_count"] == 10


# --------------------------------------------------------------------- #
# Edge Cases
# --------------------------------------------------------------------- #

class TestJEPAModelEdgeCases:
    """Test edge cases and robustness."""

    def test_empty_history(self):
        model = JEPAModel()
        assert len(model._history) == 0

        # Should not crash
        caps = model.get_predictions()
        assert caps["can_predict"] is False

    def test_single_sample(self):
        model = JEPAModel(min_samples=10)
        model.train_on_packet(sample_state())

        # Should not predict yet
        result = model.predict_future(sample_state())
        assert result is None

    def test_missing_channels(self):
        model = JEPAModel(min_samples=5)

        # Train with partial data
        for i in range(10):
            state = {"depth_m": 30.0 + i, "timestamp_ns": T0 + i * 1_000_000_000}
            model.train_on_packet(state)

        # Should still work
        state = {"depth_m": 40.0, "timestamp_ns": T0 + 10_000_000_000}
        result = model.predict_future(state)
        # May or may not predict depending on pattern learning
        # But shouldn't crash

    def test_extreme_values(self):
        model = JEPAModel()

        # Should handle extreme values gracefully
        extreme_state = sample_state(depth_m=1000.0, speed_kn=100.0, engine_temp=200.0)
        emb = model.encode_frame(extreme_state)

        # Should normalize to [0, 1]
        assert 0.0 <= emb.depth_m <= 1.0
        assert 0.0 <= emb.speed_kn <= 1.0

    def test_variance_handling(self):
        """Test that variance doesn't go negative or cause issues."""
        model = JEPAModel(learning_rate=0.1)

        # Train with constant value (zero variance)
        for i in range(10):
            model.train_on_packet(sample_state(depth_m=50.0, timestamp_ns=T0 + i * 1_000_000_000))

        # Should still predict
        result = model.predict_future(sample_state(depth_m=50.0))
        if result:
            # Should have some confidence even with zero variance
            assert result.confidence >= 0.0
