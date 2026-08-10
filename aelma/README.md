# aelma/ — Agent-Engine Linked Marine Architecture

The production system for F/V EILEEN. Phase 2 complete: 407 tests passing.

## Structure

| Directory | Purpose |
|-----------|---------|
| [`bridge/`](./bridge/) | NMEA 0183 parser + WebSocket server. Signal K (NMEA 2000) support. |
| [`twin/`](./twin/) | The digital twin core. State, bathymetry, 20+ intelligence modules. |
| [`simulator/`](./simulator/) | Hardware simulator. Pretends to be F/V EILEEN for testing. |
| [`viewer/`](./viewer/) | Static file server. 3D vessel view + real-time dashboard. |
| [`tests/`](./tests/) | 30+ test files, 14,000+ lines of tests. |
| [`examples/`](./examples/) | Fleet demo, fleet viewer, watcher demo, oplog examples. |
| [`build_claude/`](./build_claude/) | Claude-built subsystem: twin, simulator, viewer. |
| [`build_kimi/`](./build_kimi/) | Kimi-built subsystem: twin with extended modules. |
| [`docs/`](./docs/) | API docs, guides. |
| [`plugins/`](./plugins/) | Runtime-loadable extensions. |
| [`scripts/`](./scripts/) | Operational scripts. |

## Key Files

- [README.md](./README.md) — AELMA entry point and quickstart
- [PHASE2_API_REFERENCE.md](./PHASE2_API_REFERENCE.md) — Full API documentation
- [STARTUP_GUIDE.md](./STARTUP_GUIDE.md) — How to run the system
- [docker-compose.yml](./docker-compose.yml) — Container deployment

## Phase Status

| Phase | Status | Key Deliverables |
|-------|--------|-----------------|
| Phase 0 | ✅ Complete | NMEA bridge, simulator, Parquet capture |
| Phase 1 | ✅ Complete | Twin core, state, bathymetry, H3 indexing |
| Phase 2 | ✅ Complete | Watchers, health, metrics, dashboard, Signal K, A2A log, circuit breaker, historical queries — 407 tests |
| Phase 3 | 🔄 Planned | See [PHASE3_ROADMAP.md](./PHASE3_ROADMAP.md) |
| Phase 4 | 📋 Planned | See [PHASE4_PLAN.md](./PHASE4_PLAN.md) |
| Phase 5 | 📋 Planned | See [PHASE5_PLAN.md](./PHASE5_PLAN.md) |

---

← Back to [Vessel Agent System](../README.md)
