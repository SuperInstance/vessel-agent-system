# JEPA World Model Integration for AELMA

## Summary

A complete JEPA (Joint Embedding Predictive Architecture) world model has been implemented for AELMA that predicts future vessel telemetry and detects anomalies. The system uses pure Python (no torch) with simple statistical learning for fast, efficient inference.

## What Was Built

### 1. Core JEPA Model (`twin/jepa_model.py`)

**Key Classes:**
- `StateEmbedding` - Normalized embedding of vessel state
- `PredictionResult` - Prediction with confidence and anomaly scores
- `TransitionPattern` - Learned state transition patterns
- `JEPAModel` - Main world model class

**Core Methods:**
- `encode_frame(state_dict)` - Encodes current vessel state to normalized embedding
- `predict_future(current_state, steps_ahead)` - Predicts future states with uncertainty
- `train(history)` - Batch training from historical data
- `train_on_packet(packet)` - Online training from telemetry packets
- `detect_anomaly(predicted, actual)` - Compares predictions with observations

**State Channels Predicted:**
- `depth_m` - Next 60 seconds depth projection
- `speed_kn` - Speed trend prediction
- `engine_temp` - Temperature increase rate
- `position_lat/lon` - Course projection

### 2. TwinCore Integration (`twin/core.py`)

**Integration Points:**
- JEPA model instantiated in `TwinCore.__init__()` with configurable parameters
- `handle_packet()` trains JEPA on every telemetry packet
- `_run_jepa_prediction()` runs predictions and anomaly detection
- `build_snapshot()` includes JEPA stats in vessel snapshots

**Configuration Parameters:**
```python
enable_jepa: bool = True                    # Master switch
jepa_history_size: int = 1000              # Max historical states
jepa_learning_rate: float = 0.1             # EMA alpha (0-1)
jepa_anomaly_threshold: float = 2.5         # Z-score threshold
jepa_min_samples: int = 10                 # Minimum samples before predicting
```

### 3. Comprehensive Test Suite

**Unit Tests (`tests/jepa_model.test.py`):**
- 35 tests covering normalization, encoding, training, prediction, and anomaly detection
- Tests for edge cases, integration patterns, and online learning

**Integration Tests (`twin/tests/test_jepa_integration.py`):**
- 9 tests covering TwinCore integration
- Tests for configuration, stats reporting, and normal operations

**Total Coverage:** 44 tests, all passing

## Technical Implementation

### Simple ML Approach (Pure Python)

**Embedding:**
- Normalized state vector with 7 dimensions
- Adaptive bounds learning for robustness
- Handles missing/invalid data gracefully

**Prediction:**
- Linear extrapolation with learned transition patterns
- Exponential moving average (EMA) for online learning
- Regime-specific patterns (fast/slow, heading zones)

**Anomaly Detection:**
- Z-score based on prediction error variance
- Minimum variance floor to prevent extreme scores
- Combined threshold exceedance and max z-score

**Training:**
- Moving average of state transitions
- Per-regime pattern learning
- Global pattern fallback for robustness

### Data Flow

```
Telemetry Packet → handle_packet()
                      ↓
                  train_on_packet()
                      ↓
              Learn transition patterns
                      ↓
              predict_future() on depth packets
                      ↓
              detect_anomaly() if score > 0.5
                      ↓
              Log warnings for anomalies
```

### Anomaly Scoring

**Score Components:**
1. **Threshold Exceedance (70%)** - How many channels exceed z-score threshold
2. **Max Z-Score (30%)** - Sigmoid-normalized maximum deviation

**Score Range:** 0.0 (normal) to 1.0 (highly anomalous)

**Warning Threshold:** 0.5 (configurable via anomaly_threshold)

## Usage Example

```python
from twin.core import TwinCore

# Create twin with JEPA enabled
core = TwinCore(
    enable_jepa=True,
    jepa_learning_rate=0.1,
    jepa_anomaly_threshold=2.5,
    jepa_min_samples=10,
)

# JEPA automatically trains on packets
# and predicts anomalies during normal operation

# Get JEPA stats from snapshot
snap = core.build_snapshot()
print(snap["jepa"])  # tick_count, anomaly_count, patterns, etc.
```

## Files Created/Modified

### Created:
1. `twin/jepa_model.py` - JEPA world model implementation (600+ lines)
2. `tests/jepa_model.test.py` - Unit tests (350+ lines)
3. `twin/tests/test_jepa_integration.py` - Integration tests (200+ lines)

### Modified:
1. `twin/core.py` - Added JEPA integration (~100 lines)

## Performance Characteristics

**Training:** O(1) per packet (EMA updates)
**Prediction:** O(1) per query (simple vector operations)
**Memory:** O(history_size) for state storage
**Latency:** <1ms per prediction (pure Python)

## Future Enhancements

**Potential Improvements:**
1. Watcher integration for anomaly events
2. Persistence for learned patterns
3. Multi-horizon prediction (60s, 5min, 15min)
4. Channel-specific confidence scores
5. Trend analysis (increasing/decreasing detection)
6. Correlation analysis between channels

**Production Considerations:**
1. Add Prometheus metrics for anomaly rates
2. Configure alert thresholds per vessel
3. Add pattern export/import for fleet learning
4. Implement pattern versioning

## Testing Results

All 44 tests passing:
- 35 unit tests for JEPA model
- 9 integration tests for TwinCore
- All existing TwinCore tests still pass

## References

- Mini-agent JEPA work: `C:\Users\casey\Downloads\mini-agent-freeze.txt`
- AELMA twin architecture: `twin/core.py`, `twin/state.py`
- Testing patterns: `twin/tests/test_twin.py`

---

**Status:** ✅ Complete and tested
**Total Lines:** ~1,200 lines of code + tests
**Test Coverage:** Comprehensive (44 tests)
**Integration:** Full TwinCore integration with stats reporting
