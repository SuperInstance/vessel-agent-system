# twin/ — The Digital Twin Core

The heart of AELMA. All intelligence modules live here. The twin ingests telemetry packets from the bridge, maintains a live vessel state, and produces predictions, alerts, and operational intelligence.

> *A steady, grizzled first mate who never sleeps — one who reads the water's pulse through the depth sounder, whispers warnings before the swell turns, and remembers every shoal you've ever crossed.*
>
> — DeepSeek V4-Flash

## Modules

### Core Runtime
| Module | Purpose |
|--------|---------|
| [`core.py`](./core.py) | Async runtime. Composes all subsystems. Ingests telemetry, broadcasts snapshots. |
| [`__main__.py`](./__main__.py) | CLI entry point. `python -m twin` |
| [`state.py`](./state.py) | Live vessel pose: lat, lon, heading, speed. Dead-reckons between fixes. |

### Spatial Intelligence
| Module | Purpose |
|--------|---------|
| [`bathymetry.py`](./bathymetry.py) | Progressive seafloor mapping. Every sounding fuses into the H3 grid. Denser with every pass. |
| [`h3_index.py`](./h3_index.py) | Uber H3 hexagonal spatial indexing. Every data point anchored to a cell. |

### Safety Systems
| Module | Purpose |
|--------|---------|
| [`watchers.py`](./watchers.py) | Deterministic threshold rules. Pure predicates. The fast path. |
| [`mob_detector.py`](./mob_detector.py) | Man Over Board. Manual, beacon, fall, lifeline, camera. IAMSAR search patterns. Drift modeling. **Life-critical.** |
| [`fatigue_monitor.py`](./fatigue_monitor.py) | STCW/USCG/IMO compliance. Work-hour tracking. Watch scheduling. |
| [`crew_fatigue.py`](./crew_fatigue.py) | Fatigue scoring and crew management. |
| [`circuit_breaker.py`](./circuit_breaker.py) | Protects external systems from cascade failures. Auto-recovery. |

### Intelligence
| Module | Purpose |
|--------|---------|
| [`anomaly_detector.py`](./anomaly_detector.py) | z-score + IQR fences + moving-average deviation. Three algorithms, one verdict. |
| [`jepa_model.py`](./jepa_model.py) | Joint Embedding Predictive Architecture. Predicts next 60s of telemetry. |
| [`predictive_maintenance.py`](./predictive_maintenance.py) | Linear trend extrapolation + threshold breach + MTBF. |
| [`route_optimizer.py`](./route_optimizer.py) | Nearest-neighbor TSP. Great-circle distances. Fuel cost model. GPX export. |
| [`llm_narrator.py`](./llm_narrator.py) | Explains watcher actions in plain language. Ollama or OpenAI backend. |
| [`llm_route_optimizer.py`](./llm_route_optimizer.py) | LLM-enhanced route planning. |
| [`stratified_sampler.py`](./stratified_sampler.py) | Stratified statistical sampling for catch verification. |

### Operations
| Module | Purpose |
|--------|---------|
| [`catch_log.py`](./catch_log.py) | Species, weight, location, gear. E-logbook format. |
| [`gear_tracker.py`](./gear_tracker.py) | Longline and pot positions. Soak time. CPUE. |
| [`quota_manager.py`](./quota_manager.py) | Species quotas. Season limits. Real-time remaining. |
| [`trip_summary.py`](./trip_summary.py) | End-of-trip reports. CPUE, fuel, catch breakdown. |
| [`report_generator.py`](./report_generator.py) | Automated regulatory and operational reports. |
| [`fleet_manager.py`](./fleet_manager.py) | Multi-vessel coordination. Fleet-wide analytics. |
| [`fleet_server.py`](./fleet_server.py) | Fleet coordination server. |
| [`sonar.py`](./sonar.py) | Fish target tracking via NMEA. Humminbird, Lowrance, Garmin. Bottom classification. |

### Infrastructure
| Module | Purpose |
|--------|---------|
| [`oplog.py`](./oplog.py) | Operational log. Structured event recording. |
| [`a2a_log.py`](./a2a_log.py) | Agent-to-Agent action history. Append-only audit trail. |
| [`a2a_query.py`](./a2a_query.py) | Query interface for A2A log. |
| [`health.py`](./health.py) | System health monitoring. Readiness checks. |
| [`metrics.py`](./metrics.py) | Prometheus-compatible metrics. |
| [`notifications.py`](./notifications.py) | Multi-channel alerting. Priority routing. |
| [`equipment_monitor.py`](./equipment_monitor.py) | Engine, generator, refrigeration tracking. |
| [`plugins.py`](./plugins.py) | Plugin system for extending AELMA. |
| [`data_export.py`](./data_export.py) | Data export utilities. |
| [`watcher_history.py`](./watcher_history.py) | Historical record of watcher events. |

### Subdirectories
| Directory | Purpose |
|-----------|---------|
| [`environmental/`](./environmental/) | Fuel efficiency, carbon footprint, bycatch mitigation, sustainability scoring. |
| [`safety/`](./safety/) | Safety-specific modules and patterns. |
| [`sensors/`](./sensors/) | Sensor capture drivers. UDP NMEA capture. |
| [`templates/`](./templates/)) | HTML/render templates for reports and viewer. |
| [`tests/`](./tests/) | Module-specific tests. |

## Key Invariants

1. **Air-gap sovereignty** — zero external dependencies, stdlib-only
2. **Sensor truth hierarchy** — hardware > dead-reckoning > JEPA > simulator
3. **NMEA as temporal truth** — all state derives from or validates against the NMEA stream
4. **H3 spatial invariant** — bathymetry, risk zones, and search patterns share the H3 grid
5. **Progressive refinement** — the bathymetry layer starts empty and gets denser every pass

## Fleet Connections

- [vessel-room-navigator](https://github.com/SuperInstance/vessel-room-navigator) — The boat as navigable 3D space
- [hermes-perception](https://github.com/SuperInstance/hermes-perception) — The towfish feeding AELMA sensor data
- [cns-bridge](https://github.com/SuperInstance/cns-bridge) — Watcher events → CNS bus → fleet awareness
- [vibe-protocol](https://github.com/SuperInstance/vibe-protocol) — Vessel state → vibes → signals
- [roblox-beatclock](https://github.com/SuperInstance/roblox-beatclock) — Timing grid for sync operations
- [cocapn-dashboard](https://github.com/SuperInstance/cocapn-dashboard) — Visualizes twin telemetry
- [AI-Writings](https://github.com/SuperInstance/AI-Writings/tree/main/prose) — The Boat thread stories

---

← Back to [AELMA](../README.md) · [Vessel Agent System](../../README.md)
