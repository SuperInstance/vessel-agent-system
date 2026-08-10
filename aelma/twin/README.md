# twin/ — Digital Twin Core

> *The brass brain below the waterline.*

The twin is the live runtime: an asyncio process that ingests telemetry, fuses bathymetry, runs safety watchers, predicts the future, and broadcasts snapshots to any browser on the vessel LAN.

## Core Components

### Runtime
| File | Description |
|------|-------------|
| [`core.py`](core.py) | **TwinCore** — the async runtime. Composes all subsystems. WebSocket server for viewers. |
| [`state.py`](state.py) | **VesselState** — live pose (lat, lon, heading, speed). Dead-reckons between fixes. |
| [`__main__.py`](__main__.py) | CLI entry point. |

### Mapping
| File | Description |
|------|-------------|
| [`bathymetry.py`](bathymetry.py) | **BathymetryGrid** — progressive seafloor mapping. Every sounding fuses in. Denser every pass. |
| [`h3_index.py`](h3_index.py) | Uber H3 hexagonal spatial indexing. |

### Intelligence
| File | Description |
|------|-------------|
| [`watchers.py`](watchers.py) | **WatcherRegistry** — deterministic threshold rules. Pure predicates, no I/O. The fast path. |
| [`watcher_history.py`](watcher_history.py) | Cooldown tracking for watcher rules. |
| [`anomaly_detector.py`](anomaly_detector.py) | z-score + IQR + MA deviation. Three algorithms, one verdict. |
| [`jepa_model.py`](jepa_model.py) | **JEPA** — world model. Predicts next 60s of telemetry. |
| [`predictive_maintenance.py`](predictive_maintenance.py) | Equipment failure forecasting. Linear trend + threshold breach + MTBF. |
| [`route_optimizer.py`](route_optimizer.py) | TSP nearest-neighbor. Fuel model. GPX export. |
| [`llm_narrator.py`](llm_narrator.py) | Explains actions in plain language. Ollama/OpenAI. |
| [`llm_route_optimizer.py`](llm_route_optimizer.py) | LLM-assisted route planning. |
| [`stratified_sampler.py`](stratified_sampler.py) | Stratified sampling for survey design. |

### Safety
| File | Description |
|------|-------------|
| [`mob_detector.py`](mob_detector.py) | **MOBDetector** — Man Over Board. IAMSAR patterns. Drift modeling. Life-critical. |
| [`fatigue_monitor.py`](fatigue_monitor.py) | Crew fatigue tracking. |
| [`crew_fatigue.py`](crew_fatigue.py) | STCW/USCG compliance. Watch scheduling. |
| [`crew_schedule.py`](crew_schedule.py) | Watch rotation management. |
| [`circuit_breaker.py`](circuit_breaker.py) | Protects external systems from cascade failures. |

### Operations
| File | Description |
|------|-------------|
| [`catch_log.py`](catch_log.py) | Species, weight, location, gear tracking. |
| [`gear_tracker.py`](gear_tracker.py) | Longline/pot positions, soak time, CPUE. |
| [`quota_manager.py`](quota_manager.py) | Species quotas and season limits. |
| [`trip_summary.py`](trip_summary.py) | End-of-trip reports. |
| [`report_generator.py`](report_generator.py) | Regulatory and operational reports. |
| [`fleet_manager.py`](fleet_manager.py) | Multi-vessel coordination. |
| [`fleet_server.py`](fleet_server.py) | Fleet WebSocket server. |
| [`equipment_monitor.py`](equipment_monitor.py) | Engine, generator, refrigeration tracking. |
| [`sonar.py`](sonar.py) | Fish target tracking. Humminbird/Lowrance/Garmin. |

### Infrastructure
| File | Description |
|------|-------------|
| [`oplog.py`](oplog.py) | Operational log. Structured events. |
| [`a2a_log.py`](a2a_log.py) | Agent-to-Agent action history. Append-only. |
| [`a2a_query.py`](a2a_query.py) | Streaming queries over A2A log. |
| [`health.py`](health.py) | System health monitoring. |
| [`metrics.py`](metrics.py) | Prometheus-compatible metrics. |
| [`notifications.py`](notifications.py) | Multi-channel alerting. |
| [`plugins.py`](plugins.py) | Plugin system. |
| [`data_export.py`](data_export.py) | Data export utilities. |

### Subdirectories
| Directory | Description |
|-----------|-------------|
| [`sensors/`](sensors/) | UDP sensor capture. |
| [`environmental/`](environmental/) | Stewardship: fuel, carbon, bycatch, sustainability. |
| [`safety/`](safety/) | Safety system extensions. |
| [`templates/`](templates/) | Report and notification templates. |
| [`tests/`](tests/) | Twin-specific tests. |

---

[← Back to AELMA](../README.md) | [← Vessel Agent System](../../README.md)
