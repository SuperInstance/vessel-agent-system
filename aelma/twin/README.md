# aelma/twin/ — Digital Twin Core

> *The second hull. State, bathymetry, safety — the vessel in software.*

## Core Modules

| File | Description |
|------|-------------|
| [`core.py`](core.py) | TwinCore — asyncio runtime composing all subsystems |
| [`state.py`](state.py) | VesselState — position, heading, speed, dead-reckoning between fixes |
| [`bathymetry.py`](bathymetry.py) | BathymetryGrid — progressive seafloor map (10m cells, running average) |
| [`mob_detector.py`](mob_detector.py) | **Life-critical** MOB detection — manual, beacon, fall, lifeline, camera, AIS |
| [`circuit_breaker.py`](circuit_breaker.py) | Fault isolation — CLOSED/OPEN/HALF_OPEN state machine |
| [`fatigue_monitor.py`](fatigue_monitor.py) | Crew rest compliance — 10hr shift, 8hr rest, 24hr weekly |
| [`equipment_monitor.py`](equipment_monitor.py) | Machinery health tracking |
| [`fleet_manager.py`](fleet_manager.py) | Multi-vessel fleet management |
| [`quota_manager.py`](quota_manager.py) | Catch quota tracking |
| [`route_optimizer.py`](route_optimizer.py) | Route optimization |
| [`llm_route_optimizer.py`](llm_route_optimizer.py) | LLM-enh route optimization |
| [`anomaly_detector.py`](anomaly_detector.py) | Pattern deviation detection |
| [`predictive_maintenance.py`](predictive_maintenance.py) | Failure prediction |
| [`jepa_model.py`](jepa_model.py) | Joint Embedding Predictive Architecture |
| [`report_generator.py`](report_generator.py) | Automated report generation |
| [`trip_summary.py`](trip_summary.py) | Trip-level summaries |
| [`catch_log.py`](catch_log.py) | Catch event logging |
| [`gear_tracker.py`](gear_tracker.py) | Fishing gear tracking |
| [`crew_schedule.py`](crew_schedule.py) | Watch rotation scheduling |
| [`h3_index.py`](h3_index.py) | Uber H3 hexagonal spatial indexing |
| [`oplog.py`](oplog.py) | Operational log |
| [`a2a_log.py`](a2a_log.py) | Agent-to-agent communication log |
| [`a2a_query.py`](a2a_query.py) | A2A query system |
| [`watchers.py`](watchers.py) | Rule engine for automated actions |
| [`plugins.py`](plugins.py) | Extension system |
| [`llm_narrator.py`](llm_narrator.py) | LLM-powered situation narration |
| [`stratified_sampler.py`](stratified_sampler.py) | Stratified data sampling |

## Subpackages

| Directory | Description |
|-----------|-------------|
| [`sensors/`](sensors/) | Sensor capture — NMEA UDP capture coordinator |
| [`safety/`](safety/) | Crew safety systems |
| [`environmental/`](environmental/) | Environmental stewardship modules |

## Design

The twin connects to the bridge via WebSocket, ingests TelemetryPackets, maintains vessel state with dead-reckoning, fuses depth soundings into progressive bathymetry, and broadcasts snapshots to viewers. All failures are isolated by circuit breakers. All safety systems are life-critical priority.

See [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) for the full topology.

---

[← Back to AELMA](../README.md)
