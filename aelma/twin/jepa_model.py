"""JEPA (Joint Embedding Predictive Architecture) world model for AELMA.

A lightweight ML model that predicts future telemetry states and detects anomalies.
Uses pure Python (no torch) with simple statistical learning for fast inference.

The model learns temporal patterns in vessel state and predicts:
- depth_m (next 60 seconds)
- speed_kn (trend)
- engine_temp (increase rate)
- position_lat/lon (course projection)

Anomaly detection uses z-score based prediction error.
"""

from __future__ import annotations

import math
import statistics
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StateEmbedding:
    """Normalized embedding of vessel state."""

    # Time since epoch (normalized)
    time_norm: float = 0.0

    # Depth (normalized)
    depth_m: float = 0.0

    # Speed in knots (normalized)
    speed_kn: float = 0.0

    # Engine temp if available (normalized)
    engine_temp: float = 0.0

    # Position (normalized to local region)
    lat_norm: float = 0.0
    lon_norm: float = 0.0

    # Heading in radians (normalized)
    heading_rad: float = 0.0

    # Raw values for decoding
    raw_values: dict[str, Any] = field(default_factory=dict)

    def to_vector(self) -> list[float]:
        """Convert to vector for prediction."""
        return [
            self.time_norm,
            self.depth_m,
            self.speed_kn,
            self.engine_temp,
            self.lat_norm,
            self.lon_norm,
            self.heading_rad,
        ]

    @classmethod
    def from_dict(cls, state_dict: dict[str, Any], bounds: dict[str, tuple[float, float]] | None = None) -> "StateEmbedding":
        """Create embedding from raw state dict with normalization."""
        if bounds is None:
            bounds = {}

        raw = state_dict.copy()

        # Extract raw values
        depth = _get_float(state_dict.get("depth_m"))
        speed = _get_float(state_dict.get("speed_kn"))
        engine_temp = _get_float(state_dict.get("engine_temp"))
        lat = _get_float(state_dict.get("lat"))
        lon = _get_float(state_dict.get("lon"))
        heading = _get_float(state_dict.get("heading_deg"))

        # Normalize using bounds or defaults
        depth_norm = _normalize(depth, bounds.get("depth_m", (0, 200)))
        speed_norm = _normalize(speed, bounds.get("speed_kn", (0, 30)))
        temp_norm = _normalize(engine_temp, bounds.get("engine_temp", (60, 100)))
        lat_norm = _normalize(lat, bounds.get("lat", (lat - 1.0, lat + 1.0)) if lat else (0, 1))
        lon_norm = _normalize(lon, bounds.get("lon", (lon - 1.0, lon + 1.0)) if lon else (0, 1))

        # Normalize heading to radians
        heading_rad = math.radians(heading) if heading is not None else 0.0

        # Time normalization (use hour of day for cyclical patterns)
        ts = state_dict.get("timestamp_ns", time.time_ns())
        time_norm = (ts % 86400_000_000_000) / 86400_000_000_000  # Hour of day

        return cls(
            time_norm=time_norm,
            depth_m=depth_norm,
            speed_kn=speed_norm,
            engine_temp=temp_norm,
            lat_norm=lat_norm,
            lon_norm=lon_norm,
            heading_rad=heading_rad,
            raw_values=raw,
        )


@dataclass
class PredictionResult:
    """Prediction result with confidence and anomaly score."""

    # Predicted state embedding
    predicted: StateEmbedding

    # Predicted values (denormalized)
    predicted_values: dict[str, float]

    # Confidence score (0-1)
    confidence: float

    # Anomaly score (0-1, higher = more anomalous)
    anomaly_score: float

    # Per-channel prediction errors
    errors: dict[str, float]

    # Prediction horizon in seconds
    horizon_s: float


@dataclass
class TransitionPattern:
    """Learned state transition pattern."""

    # Mean change vector (deltas for each channel)
    mean_delta: list[float]

    # Variance of deltas (for uncertainty)
    variance: list[float]

    # Sample count
    count: int

    # Timestamp of last update
    last_update_ns: int


def _get_float(value: Any) -> float | None:
    """Safely extract float value."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize(value: float | None, bounds: tuple[float, float]) -> float:
    """Normalize value to [0, 1] range."""
    if value is None:
        return 0.0
    min_val, max_val = bounds
    if max_val <= min_val:
        return 0.0
    return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))


def _denormalize(norm: float, bounds: tuple[float, float]) -> float:
    """Denormalize from [0, 1] to original range."""
    min_val, max_val = bounds
    return min_val + norm * (max_val - min_val)


def _compute_z_score(value: float, mean: float, std: float) -> float:
    """Compute z-score, handling edge cases."""
    if std < 1e-6:
        return 0.0
    return abs((value - mean) / std)


class JEPAModel:
    """Joint Embedding Predictive Architecture for vessel telemetry.

    A simple but effective world model that:
    1. Encodes vessel state to normalized embeddings
    2. Learns transition patterns from history
    3. Predicts future states with uncertainty
    4. Detects anomalies via prediction error z-scores

    Uses moving average statistics (no torch) for fast online learning.
    """

    def __init__(
        self,
        history_size: int = 1000,
        learning_rate: float = 0.1,
        anomaly_threshold: float = 2.5,
        min_samples: int = 10,
    ) -> None:
        """Initialize JEPA model.

        Parameters
        ----------
        history_size:
            Maximum number of historical states to keep for learning.
        learning_rate:
            Exponential moving average alpha (0-1, higher = faster adaptation).
        anomaly_threshold:
            Z-score threshold for anomaly detection (typically 2-3).
        min_samples:
            Minimum samples before emitting predictions.
        """
        self.history_size = history_size
        self.learning_rate = learning_rate
        self.anomaly_threshold = anomaly_threshold
        self.min_samples = min_samples

        # Historical state embeddings
        self._history: deque[tuple[int, StateEmbedding]] = deque(maxlen=history_size)

        # Learned transition patterns
        self._patterns: dict[str, TransitionPattern] = {}

        # State bounds for normalization
        self._bounds: dict[str, tuple[float, float]] = {
            "depth_m": (0.0, 200.0),
            "speed_kn": (0.0, 30.0),
            "engine_temp": (60.0, 100.0),
            "lat": (0.0, 70.0),
            "lon": (-180.0, -120.0),
        }

        # Prediction accuracy tracking
        self._prediction_errors: deque[float] = deque(maxlen=100)

        # Statistics
        self._tick_count = 0
        self._anomaly_count = 0

        # Last embedding for incremental learning
        self._last_embedding: tuple[int, StateEmbedding] | None = None

    # ------------------------------------------------------------------ #
    # Encoding
    # ------------------------------------------------------------------ #
    def encode_frame(self, state_dict: dict[str, Any]) -> StateEmbedding:
        """Encode current vessel state to embedding.

        Parameters
        ----------
        state_dict:
            Raw state dict with channels (depth_m, speed_kn, etc).

        Returns
        -------
        StateEmbedding
            Normalized embedding vector.
        """
        # Update bounds online for robustness
        self._update_bounds(state_dict)

        # Create embedding
        embedding = StateEmbedding.from_dict(state_dict, self._bounds)
        return embedding

    def _update_bounds(self, state_dict: dict[str, Any]) -> None:
        """Incrementally update normalization bounds."""
        channels = ["depth_m", "speed_kn", "engine_temp", "lat", "lon"]
        for channel in channels:
            value = _get_float(state_dict.get(channel))
            if value is None:
                continue

            if channel not in self._bounds:
                self._bounds[channel] = (value, value)
                continue

            min_val, max_val = self._bounds[channel]
            # Expand bounds with margin
            self._bounds[channel] = (
                min(min_val, value - 10.0),
                max(max_val, value + 10.0),
            )

    # ------------------------------------------------------------------ #
    # Prediction
    # ------------------------------------------------------------------ #
    def predict_future(
        self,
        current_state: dict[str, Any],
        steps_ahead: int = 1,
        step_duration_s: float = 1.0,
    ) -> PredictionResult | None:
        """Predict future state.

        Parameters
        ----------
        current_state:
            Current vessel state dict.
        steps_ahead:
            Number of steps to predict ahead.
        step_duration_s:
            Duration of each step in seconds.

        Returns
        -------
        PredictionResult | None
            Prediction result with confidence, or None if insufficient data.
        """
        # Encode current state
        current_emb = self.encode_frame(current_state)

        # Check if we have enough data
        if len(self._history) < self.min_samples:
            return None

        # Compute prediction horizon
        horizon_s = steps_ahead * step_duration_s

        # Get learned pattern for prediction
        pattern_key = self._compute_pattern_key(current_emb)
        pattern = self._patterns.get(pattern_key)

        if pattern is None or pattern.count < self.min_samples:
            # Fallback to global pattern
            pattern = self._patterns.get("*global*")
            if pattern is None or pattern.count < self.min_samples:
                return None

        # Predict by applying learned delta
        current_vec = current_emb.to_vector()
        predicted_vec = [
            current_vec[i] + pattern.mean_delta[i] * steps_ahead
            for i in range(len(current_vec))
        ]

        # Decode predicted embedding
        predicted_emb = self._decode_to_embedding(predicted_vec, current_emb)
        predicted_values = self._decode_to_dict(predicted_emb, horizon_s)

        # Compute confidence based on variance and sample count
        variance_penalty = sum(pattern.variance) / len(pattern.variance)
        confidence = 1.0 / (1.0 + variance_penalty)
        confidence = min(1.0, confidence * (pattern.count / self.min_samples))

        # Compute errors and anomaly score
        errors = self._compute_errors(current_emb, predicted_emb)
        anomaly_score = self._compute_anomaly_score(errors, pattern)

        return PredictionResult(
            predicted=predicted_emb,
            predicted_values=predicted_values,
            confidence=confidence,
            anomaly_score=anomaly_score,
            errors=errors,
            horizon_s=horizon_s,
        )

    def _compute_pattern_key(self, emb: StateEmbedding) -> str:
        """Compute pattern key based on regime (speed, heading zone)."""
        speed_zone = "stopped" if emb.speed_kn < 0.1 else "slow" if emb.speed_kn < 0.5 else "fast"
        heading_zone = "north" if emb.heading_rad < 1.0 else "east" if emb.heading_rad < 2.0 else "south" if emb.heading_rad < 3.0 else "west"
        return f"{speed_zone}_{heading_zone}"

    def _decode_to_embedding(self, vec: list[float], reference: StateEmbedding) -> StateEmbedding:
        """Decode vector back to embedding."""
        return StateEmbedding(
            time_norm=vec[0],
            depth_m=vec[1],
            speed_kn=vec[2],
            engine_temp=vec[3],
            lat_norm=vec[4],
            lon_norm=vec[5],
            heading_rad=vec[6],
            raw_values=reference.raw_values.copy(),
        )

    def _decode_to_dict(self, emb: StateEmbedding, horizon_s: float) -> dict[str, float]:
        """Decode embedding to raw value dict."""
        result = {}

        # Denormalize each channel
        channels = ["depth_m", "speed_kn", "engine_temp", "lat", "lon"]
        emb_values = [emb.depth_m, emb.speed_kn, emb.engine_temp, emb.lat_norm, emb.lon_norm]

        for channel, emb_val in zip(channels, emb_values):
            if channel in self._bounds:
                result[channel] = _denormalize(emb_val, self._bounds[channel])

        # Add derived predictions
        if "speed_kn" in result:
            speed = result["speed_kn"]
            # Distance projection
            result["projected_distance_m"] = speed * (1852.0 / 3600.0) * horizon_s

        if "lat" in result and "lon" in result and "heading_rad" in emb.raw_values:
            heading = emb.raw_values.get("heading_deg", 0.0)
            result["projected_heading_deg"] = heading

        return result

    def _compute_errors(self, actual: StateEmbedding, predicted: StateEmbedding) -> dict[str, float]:
        """Compute per-channel prediction errors."""
        errors = {}

        # Compare normalized values
        channels = ["depth_m", "speed_kn", "engine_temp", "lat_norm", "lon_norm"]
        actual_vals = [actual.depth_m, actual.speed_kn, actual.engine_temp, actual.lat_norm, actual.lon_norm]
        pred_vals = [predicted.depth_m, predicted.speed_kn, predicted.engine_temp, predicted.lat_norm, predicted.lon_norm]

        for channel, act_val, pred_val in zip(channels, actual_vals, pred_vals):
            errors[channel] = abs(act_val - pred_val)

        return errors

    def _compute_anomaly_score(self, errors: dict[str, float], pattern: TransitionPattern) -> float:
        """Compute overall anomaly score from errors."""
        # Compute z-scores for each error
        z_scores = []
        for i, (channel, error) in enumerate(errors.items()):
            if i < len(pattern.variance):
                # Use minimum variance to avoid extreme z-scores
                var = max(pattern.variance[i], 0.01)  # Minimum variance
                std = math.sqrt(var)
                z_score = error / std if std > 1e-6 else 0.0
                z_scores.append(z_score)

        if not z_scores:
            return 0.0

        # Anomaly score based on how many channels exceed threshold
        exceed_count = sum(1 for z in z_scores if z > self.anomaly_threshold)
        score = exceed_count / max(len(z_scores), 1)

        # Also weight by max z-score
        max_z = max(z_scores) if z_scores else 0.0
        # Sigmoid for smoother transition
        z_factor = 1.0 / (1.0 + math.exp(-(max_z - self.anomaly_threshold)))

        # Combine: 70% threshold exceedance, 30% max z-score
        return 0.7 * score + 0.3 * z_factor

    # ------------------------------------------------------------------ #
    # Training
    # ------------------------------------------------------------------ #
    def train(self, history: list[dict[str, Any]] | None = None) -> None:
        """Update model from historical data.

        Parameters
        ----------
        history:
            List of historical state dicts. If None, uses internal history.
        """
        if history:
            # Add new history entries
            for state in history:
                ts = state.get("timestamp_ns", time.time_ns())
                emb = self.encode_frame(state)
                self._history.append((ts, emb))

        # Learn transitions from sequential pairs
        if len(self._history) < 2:
            return

        # Process sequential pairs for learning
        states = list(self._history)
        for i in range(1, len(states)):
            prev_ts, prev_emb = states[i - 1]
            curr_ts, curr_emb = states[i]

            # Compute delta
            prev_vec = prev_emb.to_vector()
            curr_vec = curr_emb.to_vector()
            delta = [curr_vec[j] - prev_vec[j] for j in range(len(prev_vec))]

            # Update pattern
            pattern_key = self._compute_pattern_key(curr_emb)
            self._update_pattern(pattern_key, delta)

            # Also update global pattern
            self._update_pattern("*global*", delta)

    def train_on_packet(self, packet: dict[str, Any]) -> None:
        """Online training: update model from single telemetry packet."""
        # Extract state dict from packet
        state_dict = self._extract_state_from_packet(packet)
        if not state_dict:
            return

        # Encode and store
        ts = state_dict.get("timestamp_ns", time.time_ns())
        emb = self.encode_frame(state_dict)

        # Learn from transition if we have previous state
        if self._last_embedding is not None:
            prev_ts, prev_emb = self._last_embedding
            prev_vec = prev_emb.to_vector()
            curr_vec = emb.to_vector()
            delta = [curr_vec[j] - prev_vec[j] for j in range(len(prev_vec))]

            # Update patterns
            pattern_key = self._compute_pattern_key(emb)
            self._update_pattern(pattern_key, delta)
            self._update_pattern("*global*", delta)

        # Store as last embedding
        self._last_embedding = (ts, emb)

        # Also add to history for batch learning
        self._history.append((ts, emb))

        # Tick counter
        self._tick_count += 1

    def _extract_state_from_packet(self, packet: dict[str, Any]) -> dict[str, Any]:
        """Extract state dict from telemetry packet."""
        if isinstance(packet, dict) and "channels" in packet:
            # Snapshot format
            return packet["channels"]

        # Check if it's already a state dict (has expected fields)
        if any(k in packet for k in ["depth_m", "speed_kn", "lat", "lon", "heading_deg"]):
            return packet

        # Single packet format
        channel = packet.get("channel")
        value = packet.get("value")
        if channel and value is not None:
            return {channel: value, "timestamp_ns": packet.get("timestamp_ns")}

        return {}

    def _update_pattern(self, key: str, delta: list[float]) -> None:
        """Update transition pattern with new delta using EMA."""
        if key not in self._patterns:
            self._patterns[key] = TransitionPattern(
                mean_delta=delta.copy(),
                variance=[0.0] * len(delta),
                count=1,
                last_update_ns=time.time_ns(),
            )
            return

        pattern = self._patterns[key]
        alpha = self.learning_rate

        # Update mean (EMA)
        for i in range(len(delta)):
            pattern.mean_delta[i] = alpha * delta[i] + (1 - alpha) * pattern.mean_delta[i]

        # Update variance (online)
        for i in range(len(delta)):
            diff = delta[i] - pattern.mean_delta[i]
            pattern.variance[i] = alpha * (diff * diff) + (1 - alpha) * pattern.variance[i]

        pattern.count += 1
        pattern.last_update_ns = time.time_ns()

    # ------------------------------------------------------------------ #
    # Anomaly Detection
    # ------------------------------------------------------------------ #
    def detect_anomaly(
        self,
        predicted: PredictionResult,
        actual_state: dict[str, Any],
    ) -> dict[str, Any]:
        """Compare prediction with actual and score deviations.

        Parameters
        ----------
        predicted:
            Prediction result from predict_future().
        actual_state:
            Actual observed state dict.

        Returns
        -------
        dict
            Anomaly report with channels, scores, and severity.
        """
        actual_emb = self.encode_frame(actual_state)

        # Compute errors
        errors = self._compute_errors(actual_emb, predicted.predicted)

        # Get pattern for variance
        pattern_key = self._compute_pattern_key(actual_emb)
        pattern = self._patterns.get(pattern_key) or self._patterns.get("*global*")

        if pattern is None:
            pattern = self._patterns.get("*global*")

        # Compute per-channel z-scores
        channel_scores = {}
        for channel, error in errors.items():
            idx = list(errors.keys()).index(channel)
            if idx < len(pattern.variance):
                std = math.sqrt(max(pattern.variance[idx], 1e-6))
                z_score = error / std if std > 1e-6 else 0.0
                is_anomalous = z_score > self.anomaly_threshold
                channel_scores[channel] = {
                    "error": float(error),
                    "z_score": float(z_score),
                    "is_anomalous": is_anomalous,
                    "threshold": self.anomaly_threshold,
                }

        # Compute overall severity
        anomalous_channels = [c for c, s in channel_scores.items() if s["is_anomalous"]]
        severity = len(anomalous_channels) / max(len(channel_scores), 1)

        # Update anomaly counter
        if severity > 0:
            self._anomaly_count += 1

        return {
            "anomaly_score": predicted.anomaly_score,
            "severity": severity,
            "channels": channel_scores,
            "anomalous_channels": anomalous_channels,
            "confidence": predicted.confidence,
        }

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #
    @property
    def stats(self) -> dict[str, Any]:
        """Model statistics."""
        pattern_counts = {k: p.count for k, p in self._patterns.items()}
        recent_errors = list(self._prediction_errors)

        return {
            "tick_count": self._tick_count,
            "anomaly_count": self._anomaly_count,
            "history_size": len(self._history),
            "pattern_count": len(self._patterns),
            "pattern_counts": pattern_counts,
            "recent_errors": recent_errors,
            "avg_error": statistics.mean(recent_errors) if recent_errors else 0.0,
            "bounds": self._bounds.copy(),
        }

    def get_predictions(self) -> dict[str, Any]:
        """Get current prediction capabilities."""
        return {
            "can_predict": len(self._history) >= self.min_samples,
            "sample_count": len(self._history),
            "min_samples": self.min_samples,
            "patterns": list(self._patterns.keys()),
        }
