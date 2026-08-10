# aelma/tests/ — Test Suite

> *Sea trials. 25 test files. Every life-critical path verified.*

## Test Files

| File | What It Tests |
|------|---------------|
| [`catch_log.test.py`](catch_log.test.py) | Catch event logging and retrieval |
| [`schemas.test.py`](schemas.test.py) | JSON Schema validation for all wire formats |
| [`trip_summary.test.py`](trip_summary.test.py) | Trip-level summary generation |
| [`signalk.test.py`](signalk.test.py) | SignalK integration |
| [`test_mob_detector.py`](test_mob_detector.py) | **Life-critical** MOB detection — all methods, drift modeling, search patterns |
| [`plugins.test.py`](plugins.test.py) | Plugin extension system |
| [`oplog.test.py`](oplog.test.py) | Operational log read/write/rotate |
| [`benchmarks.test.py`](benchmarks.test.py) | Performance benchmarks |
| [`tide_predictor.test.py`](tide_predictor.test.py) | Tide prediction algorithms |
| [`a2a.test.py`](a2a.test.py) | Agent-to-agent communication |
| [`deployment.test.py`](deployment.test.py) | Deployment automation |
| [`anomaly_detector.test.py`](anomaly_detector.test.py) | Anomaly detection patterns |
| [`test_quota_manager.py`](test_quota_manager.py) | Catch quota tracking |
| [`circuit_breaker.test.py`](circuit_breaker.test.py) | Circuit breaker state machine |
| [`notifications.test.py`](notifications.test.py) | Notification system |
| [`fatigue_monitor.test.py`](fatigue_monitor.test.py) | Crew fatigue compliance |
| [`crew_schedule.test.py`](crew_schedule.test.py) | Watch rotation scheduling |
| [`test_watchers.py`](test_watchers.py) | Rule engine for automated actions |
| [`health.test.py`](health.test.py) | Health check system |
| [`llm_route_optimizer.test.py`](llm_route_optimizer.test.py) | LLM-enh route optimization |
| [`gear_tracker.test.py`](gear_tracker.test.py) | Fishing gear tracking |
| [`test_integration.py`](test_integration.py) | End-to-end integration tests |
| [`test_report_generator.py`](test_report_generator.py) | Report generation |
| [`h3_index.test.py`](h3_index.test.py) | H3 spatial indexing |
| [`fleet_manager.test.py`](fleet_manager.test.py) | Multi-vessel fleet management |
| [`route_optimizer.test.py`](route_optimizer.test.py) | Route optimization |
| [`stratified_sampler.test.py`](stratified_sampler.test.py) | Stratified sampling |
| [`predictive_maintenance.test.py`](predictive_maintenance.test.py) | Predictive maintenance |
| [`jepa_model.test.py`](jepa_model.test.py) | JEPA model |
| [`llm_narrator.test.py`](llm_narrator.test.py) | LLM narration |

## Running Tests

```bash
cd aelma && pytest tests/ -v
```

---

[← Back to AELMA](../README.md)
