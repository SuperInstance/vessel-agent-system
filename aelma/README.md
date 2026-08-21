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

## Fleet Connections

- [vessel-room-navigator](https://github.com/SuperInstance/vessel-room-navigator) — Walk through the boat as a 3D web space
- [hermes-avatar](https://github.com/SuperInstance/hermes-avatar) — The towfish: sensory systems that feed AELMA
- [cns-bridge](https://github.com/SuperInstance/cns-bridge) — The nervous system carrying AELMA's watcher events
- [vibe-protocol](https://github.com/SuperInstance/vibe-protocol) — Vessel state becomes vibes
- [cocapn-dashboard](https://github.com/SuperInstance/cocapn-dashboard) — Bioluminescent fleet dashboard visualizing AELMA telemetry
- [fleet-envelope](https://github.com/SuperInstance/fleet-envelope) — Event grammar for fleet-wide vessel coordination
- [roblox-bond-system](https://github.com/SuperInstance/roblox-bond-system) — Crew trust modeled through bond tiers
- [roblox-filtergate](https://github.com/SuperInstance/roblox-filtergate) — Vessel comms filtered for kid-safe contexts
- [the-living-minds](https://github.com/SuperInstance/the-living-minds) (dead) — 5 local models powering the LLM narrator
- [lucineer-fleet-wiki](https://github.com/SuperInstance/lucineer-fleet-wiki) — 700+ pages of fleet knowledge
- [AI-Writings](https://github.com/SuperInstance/AI-Writings/tree/main/prose) — The boat's story in overnight creative sessions
- [mud-engine](https://github.com/SuperInstance/mud-engine) — The room engine where vessel spaces exist

---

← Back to [Vessel Agent System](../README.md)
