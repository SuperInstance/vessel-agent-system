# AELMA — Agent-Engine Linked Marine Architecture

A hardware-in-the-loop digital twin for the **F/V EILEEN**, a 51-foot commercial fishing vessel home-ported in Sitka, Alaska.

**Current Status:** Phase 2 Complete — Production Ready (407 tests passing)

**Phase 2 delivers:** A production-ready marine telemetry system with real-time alerting, health monitoring, metrics collection, and a dashboard UI — all running on the vessel LAN with zero internet dependency.

---

## Quickstart (5 minutes)

You need Python 3.11+ on Linux, macOS, or Windows.

```bash
# 1. Install the one Python dep
pip install websockets

# 2. Open four terminals (or use tmux / docker compose below)

# Terminal 1 — bridge (NMEA parser + WS server)
cd aelma/bridge
python -m bridge --ws-port 8000 --tcp-port 8001

# Terminal 2 — simulator (pretends to be the F/V EILEEN)
cd aelma/simulator
python -m simulator --duration-min 60 --speedup 10

# Terminal 3 — twin (state + bathymetry + Phase 2 features)
cd aelma/twin
python -m twin --bridge-url ws://localhost:8000 --viewer-port 8090 \
    --health-port 8091 --metrics-port 9090

# Terminal 4 — viewer (static file server + dashboard)
cd aelma/viewer
python serve.py --port 8080
```

Open `http://localhost:8080` in any browser (Chrome/Safari/Firefox). You should see:
- **3D View** (`index.html`): The F/V EILEEN as an orange boat hull + cabin, moving southwest
- **Dashboard** (`dashboard.html`): Real-time gauges, charts, alerts, bathymetry heatmap

For Phase 2 features:
- **Health Monitoring:** `http://localhost:8091/health`
- **Metrics Export:** `http://localhost:9090/metrics`

Connect from an iPad on the same LAN: `http://<your-laptop-ip>:8080`. Touch drag to rotate, pinch to zoom.

---

## Phase 2 Highlights

### New Features

**Watchers** — Deterministic threshold rules with cooldown suppression
```python
twin.add_watcher({
    "id": "shallow-water",
    "when": lambda f: f.get("depth_m", 999) < 2.0,
    "action": {"name": "raise_alert", "priority": lambda f: 0.85},
    "cooldown_s": 30.0,
})
```

**Health Endpoints** — Kubernetes-ready health probes
- `GET /health` — Overall health + component details
- `GET /ready` — Readiness probe
- `GET /live` — Liveness probe

**Prometheus Metrics** — Monitoring integration
- `aelma_packets_received_total` — Telemetry counter
- `aelma_actions_fired_total` — Alert counter
- `aelma_websocket_connections` — Connection gauge
- `aelma_packet_handling_seconds` — Performance histogram

**Dashboard UI** — Real-time monitoring dashboard
- 6 live gauges (depth, speed, heading, temp, wind, RPM)
- 2 time-series charts with configurable windows
- Alert history panel with color coding
- Bathymetry heatmap visualization
- Data export functionality

**Signal K Support** — NMEA 2000 integration via Signal K delta parsing

**A2A Log** — Append-only audit trail of all agent-to-agent actions

**Historical Queries** — Time-range telemetry queries with aggregation

### What's New Since Phase 1

| Feature | Phase 1 | Phase 2 |
|---------|---------|---------|
| Alerting | ❌ | ✅ WatcherRegistry (45 tests) |
| Audit Trail | ❌ | ✅ A2ALog (38 tests) |
| Health Monitoring | ❌ | ✅ HealthChecker (35 tests) |
| Metrics Export | ❌ | ✅ MetricsCollector (29 tests) |
| Dashboard UI | ❌ | ✅ dashboard.html (self-contained) |
| Signal K | ❌ | ✅ NMEA 2000 support (28 tests) |
| Historical Queries | ❌ | ✅ TelemetryQuery (41 tests) |
| Resilience | Basic retry | ✅ CircuitBreaker (23 tests) |
| Test Coverage | ~150 tests | ✅ 407 tests (100% passing) |

---

## Docker Compose (one command)

```bash
cd aelma
docker compose up
# Then open http://localhost:8080
# Dashboard: http://localhost:8080/dashboard.html
# Health: http://localhost:8091/health
# Metrics: http://localhost:9090/metrics
```

Brings up all services. Use `--build` after editing code.

---

## What each component does

| Component | Role | Tech |
|---|---|---|
| `simulator/` | Emits realistic NMEA 0183 sentences simulating F/V EILEEN trolling near Sitka | Python stdlib |
| `bridge/` | TCP :8001 receives NMEA text; parses, quality-checks, serves as JSON TelemetryPackets over WS :8000 | Python asyncio + websockets |
| `twin/` | WS client of bridge; maintains vessel state + progressive TSDF bathymetry; serves VesselStateSnapshots to viewers over WS :8090 | Python asyncio |
| `twin/watchers.py` | Phase 2: Watcher registry for threshold-based alerting | Python stdlib |
| `twin/a2a_log.py` | Phase 2: Append-only action audit trail | Python stdlib |
| `twin/a2a_query.py` | Phase 2: Action log queries | Python stdlib |
| `twin/telemetry_query.py` | Phase 2: Historical telemetry queries | Python stdlib |
| `twin/health.py` | Phase 2: HTTP health/readiness/liveness endpoints | Python asyncio |
| `twin/metrics.py` | Phase 2: Prometheus metrics export | Python stdlib |
| `twin/circuit_breaker.py` | Phase 2: Resilient WebSocket handling | Python stdlib |
| `twin/stratified_sampler.py` | Phase 2: Depth-stratified bathymetry sampling | Python stdlib |
| `twin/llm_narrator.py` | Phase 2: AI-powered vessel narration | Python stdlib |
| `bridge/signalk.py` | Phase 2: Signal K delta parser for NMEA 2000 | Python stdlib |
| `viewer/` | Browser client; Three.js 3D scene + dashboard UI | HTML/CSS/JS |
| `viewer/dashboard.html` | Phase 2: Real-time monitoring dashboard | HTML5/Canvas (self-contained) |
| `schema/` | JSON Schemas that are the contracts between components | JSON Schema Draft 2020-12 |

---

## Wiring real hardware

Replace the simulator with real NMEA 0183 from your sounder, GPS, wind instrument:

```bash
# USB-to-serial from your MFD or instrument bus
socat TCP-CONNECT:localhost:8001 /dev/ttyUSB0,b9600,raw,cr

# Or from a networked chartplotter (Garmin BlueTop, Furuno NavNet, etc.)
# Point its NMEA-0183-over-IP output at <bridge-host>:8001
```

**NMEA 2000** — Phase 2 adds Signal K support. Connect Signal K Server to the bridge:

```bash
# Signal K Server sends deltas to bridge
# Bridge auto-parses supported paths
# Supported: navigation.*, environment.*, etc.
```

---

## Design philosophy

1. **Air-gap first.** No cloud, no phone-home. A Raspberry Pi 5 + tablet is a complete deployment.
2. **Standard library Python.** A captain with a Python tutorial can read every line.
3. **Schemas are contracts.** Components are independently replaceable as long as they honor the JSON Schemas.
4. **Simulator substitutes for hardware.** Develop and test the whole stack with zero sensors attached.
5. **Progressive world refinement.** Every sounding is non-renewable evidence — log it, fuse it, never delete it.
6. **Test-driven.** 407 tests ensure reliability. All new code includes tests.

---

## Documentation

### Phase 2 Documentation (New)

- **[`PHASE2_COMPLETE.md`](PHASE2_COMPLETE.md)** — Phase 2 delivery summary with architecture, features, and success metrics
- **[`PHASE2_API_REFERENCE.md`](PHASE2_API_REFERENCE.md)** — Complete API documentation for all Phase 2 components
- **[`PHASE2_MIGRATION_GUIDE.md`](PHASE2_MIGRATION_GUIDE.md)** — Upgrade guide from Phase 1 to Phase 2

### Component Documentation

- **[`docs/watcher_registry_guide.md`](docs/watcher_registry_guide.md)** — Watcher system deep dive
- **[`docs/a2a_system.md`](docs/a2a_system.md)** — A2A log and query architecture
- **[`docs/signalk_integration.md`](docs/signalk_integration.md)** — Signal K integration guide
- **[`docs/stratified_sampler.md`](docs/stratified_sampler.md)** — Progressive bathymetry refinement
- **[`docs/deployment.md`](docs/deployment.md)** — Production deployment guide
- **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** — System architecture and design patterns

### Supporting Documentation

- **[`SIGNALK_INTEGRATION_SUMMARY.md`](SIGNALK_INTEGRATION_SUMMARY.md)** — Signal K implementation summary
- **[`DASHBOARD_DELIVERY_SUMMARY.md`](DASHBOARD_DELIVERY_SUMMARY.md)** — Dashboard UI delivery summary
- **[`DEPLOYMENT_AUTOMATION_DELIVERY.md`](DEPLOYMENT_AUTOMATION_DELIVERY.md)** — Deployment scripts summary

### Reference

- **[`../AELMA_synthesis_memo.md`](../AELMA_synthesis_memo.md)** — Research foundation and full roadmap
- **[`../aelma_literature_survey.md`](../aelma_literature_survey.md)** — Academic literature survey

---

## Roadmap

### Current Status

- ✅ **Phase 1** — Core vessel telemetry stack (NMEA 0183, state, bathymetry, 3D viewer)
- ✅ **Phase 2** — Production-ready system (alerting, health, metrics, dashboard, Signal K)

### Future Phases

- **Phase 3:** Human-feedback stylization loop ("coral good, dogfish wrong") — the publishable academic contribution
- **Phase 4:** Divination sandbox (NVIDIA Isaac Sim or Unity ML-Agents) for predictive what-if sims
- **Phase 5:** Roblox shoreside experience (replay past trips, son game-mode, training)
- **Phase 6:** Agent spatial queries and actuation under regulatory frameworks (USCG PL 22-01, ABS Guide 323, DNV AROS)

---

## Quick Links

- **3D Viewer:** `http://localhost:8080/index.html`
- **Dashboard:** `http://localhost:8080/dashboard.html`
- **Health:** `http://localhost:8091/health`
- **Ready:** `http://localhost:8091/ready`
- **Live:** `http://localhost:8091/live`
- **Metrics:** `http://localhost:9090/metrics`

---

**Status:** Phase 2 Complete — Production Ready
**Test Coverage:** 407 tests passing (100%)
**Documentation:** 20,000+ lines
**Last Updated:** 2026-07-27
