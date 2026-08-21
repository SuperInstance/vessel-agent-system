# Vessel Agent System — AELMA

> *Agent-Engine Linked Marine Architecture*
>
> **A digital twin for F/V EILEEN, a 51-foot commercial fishing vessel in Southeast Alaska.**
>
> *You do not lay the first plank until you have tested every bolt that will sit below the waterline.*
>
> — Shipwright's axiom

> *It feels like a steady, grizzled first mate who never sleeps — one who reads the water's pulse through the depth sounder, whispers warnings before the swell turns, and remembers every shoal you've ever crossed.*
>
> — [DeepSeek V4-Flash](https://api.deepseek.com), on what AELMA feels like

> *This twin is not a copy. It is the only place that year will ever breathe again.*
>
> — [Seed Pro](https://github.com/SuperInstance/AI-Writings/tree/main/prose), on the non-renewable resource principle

---

## What This Is

AELMA is a hardware-in-the-loop digital twin for a real fishing vessel. It ingests NMEA 0183 telemetry from GPS and sonar, fuses depth soundings into a [progressive bathymetry grid](aelma/twin/bathymetry.py), maintains a live [vessel state](aelma/twin/state.py), runs deterministic safety watchers, predicts equipment failure, detects anomalies, tracks crew fatigue, plans efficient routes, narrates its own actions in plain language, and renders a 3D view in any browser — all on the vessel LAN with zero internet dependency.

**334 files. 19,000+ lines of Python. 179 source files. 56 test files. Pure stdlib.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## The Non-Renewable Resource Principle

> *"Acoustic signatures of 2026 cannot be recreated in 2031."*

Every depth sounding is evidence. Once the vessel passes over water, that data is gone — unless it was captured. AELMA captures comprehensively and analyzes incrementally. Every data point has a temporal anchor (`timestamp_ns`), a spatial anchor (lat/lon/[H3](aelma/twin/h3_index.py)), and source provenance. Models will improve. Field data is irreplaceable.

---

## BMAD — Bottom-Up, Multi-Level, Agile Development

The architecture is a stack. Each level builds on the one below. Each level must be stable before the next begins.

| Level | Name | What It Does | Status |
|-------|------|-------------|--------|
| 0 | **Raw Bits** | Network packets, NMEA bytes, zero-copy parsing | 🔄 In Progress |
| 1 | **Physical Tensors** | Normalization, calibration, H3 spatial indexing | ⏳ Planned |
| 2 | **Analytical Features** | Classification, pattern mining, species detection | ⏳ Planned |
| 3 | **Operational Intelligence** | Catch prediction, route optimization, decision support | ⏳ Planned |
| 4 | **Strategic Knowledge** | Stock assessment, ecosystem analysis, regulatory integration | ⏳ Planned |

You plane timber true before you mark the joinery. You read the swell an hour ahead before you trim the sail.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ VESSEL LAN (no internet required)                           │
│                                                             │
│  ┌──────────────┐   NMEA 0183    ┌──────────────┐          │
│  │  simulator   │───────────────▶│    bridge    │          │
│  │  (or real    │   TCP :8001    │  Parses +    │          │
│  │   hardware)  │                │  quality-    │          │
│  └──────────────┘                │  checks      │          │
│                                  └──────┬───────┘          │
│                                         │ TelemetryPackets  │
│                                         ▼                   │
│  ┌─────────────────────────────────────────────────┐       │
│  │                   T w i n C o r e                │       │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────────┐ │       │
│  │  │ Vessel    │ │ Bathymetry│ │ Watcher       │ │       │
│  │  │ State     │ │ Grid      │ │ Registry      │ │       │
│  │  └───────────┘ └───────────┘ └───────────────┘ │       │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────────┐ │       │
│  │  │ Anomaly   │ │ JEPA      │ │ MOB           │ │       │
│  │  │ Detector  │ │ World     │ │ Detector      │ │       │
│  │  └───────────┘ └───────────┘ └───────────────┘ │       │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────────┐ │       │
│  │  │ Crew      │ │ Route     │ │ Predictive    │ │       │
│  │  │ Fatigue   │ │ Optimizer │ │ Maintenance   │ │       │
│  │  └───────────┘ └───────────┘ └───────────────┘ │       │
│  └────────────────────┬────────────────────────────┘       │
│                       │ WebSocket :8090                     │
│                       ▼                                     │
│  ┌──────────────────────────────────────────────┐          │
│  │              V i e w e r (browser)            │          │
│  │       WebGL + D3 + MapLibre rendering         │          │
│  └──────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **[Air-gap first](aelma/docs/ARCHITECTURE.md#design-principles)** — every component runs on the vessel LAN. No cloud auth, no phone-home. A Raspberry Pi 5 + a tablet is a complete deployment.
2. **Standard library Python** — no pydantic, no Django, no Kafka. asyncio + websockets + stdlib. A captain with a Python tutorial can read every line.
3. **[Schemas are contracts](aelma/schema/)** — every wire format is a JSON Schema. Components are independently replaceable as long as they honor the schema.
4. **Simulator substitutes for hardware** — develop and test without a single physical sensor. Plug in real NMEA 0183 later by changing one CLI flag.
5. **Progressive world refinement** — the bathymetry layer starts empty and gets denser every time the vessel crosses water.

---

## Core Components

### Data Ingestion

| Component | File | Description |
|-----------|------|-------------|
| **[NMEA Bridge](aelma/bridge/bridge.py)** | [`bridge/`](aelma/bridge/) | Parses NMEA 0183 sentences from TCP or serial. Quality-checks each sentence. Produces TelemetryPackets. |
| **[Signal K Bridge](aelma/bridge/signalk.py)** | [`bridge/signalk.py`](aelma/bridge/signalk.py) | Parses Signal K deltas for modern marine instruments. |
| **[UDP Sensor Capture](aelma/twin/sensors/nmea_udp_capture.py)** | [`sensors/`](aelma/twin/sensors/) | Zero-copy UDP packet capture for raw NMEA streams. |
| **[Sonar Integration](aelma/twin/sonar.py)** | [`sonar.py`](aelma/twin/sonar.py) | Fish target tracking via NMEA. Parses Humminbird, Lowrance, Garmin. Bottom classification. Biomass proxy. |

### Twin Core

| Component | File | Description |
|-----------|------|-------------|
| **[TwinCore](aelma/twin/core.py)** | [`core.py`](aelma/twin/core.py) | The async runtime. Composes all subsystems. Ingests telemetry, broadcasts snapshots, persists bathymetry. |
| **[Vessel State](aelma/twin/state.py)** | [`state.py`](aelma/twin/state.py) | Live vessel pose: lat, lon, heading, speed. Dead-reckons between fixes using great-circle bearing. |
| **[Bathymetry Grid](aelma/twin/bathymetry.py)** | [`bathymetry.py`](aelma/twin/bathymetry.py) | Progressive seafloor mapping. Every sounding fuses into the grid. Denser with every pass. |
| **[H3 Indexing](aelma/twin/h3_index.py)** | [`h3_index.py`](aelma/twin/h3_index.py) | Uber H3 hexagonal spatial indexing. Every data point anchored to a cell. |

### Intelligence

| Component | File | Description |
|-----------|------|-------------|
| **[Watcher Registry](aelma/twin/watchers.py)** | [`watchers.py`](aelma/twin/watchers.py) | Deterministic threshold rules. Pure predicates. The fast path — no model reasoning, just rules. |
| **[Anomaly Detector](aelma/twin/anomaly_detector.py)** | [`anomaly_detector.py`](aelma/twin/anomaly_detector.py) | z-score + IQR fences + moving-average deviation. Three algorithms, one verdict. |
| **[JEPA World Model](aelma/twin/jepa_model.py)** | [`jepa_model.py`](aelma/twin/jepa_model.py) | Joint Embedding Predictive Architecture. Predicts next 60 seconds of telemetry. Anomaly via prediction error. |
| **[Predictive Maintenance](aelma/twin/predictive_maintenance.py)** | [`predictive_maintenance.py`](aelma/twin/predictive_maintenance.py) | Linear trend extrapolation + threshold breach prediction + MTBF. Equipment failure forecasting. |
| **[Route Optimizer](aelma/twin/route_optimizer.py)** | [`route_optimizer.py`](aelma/twin/route_optimizer.py) | Nearest-neighbor TSP approximation. Great-circle distances. Fuel cost model. GPX export. |
| **[LLM Narrator](aelma/twin/llm_narrator.py)** | [`llm_narrator.py`](aelma/twin/llm_narrator.py) | Explains watcher actions in plain language. Ollama or OpenAI backend. Never invents sensor values. |

### Safety Systems

| Component | File | Description |
|-----------|------|-------------|
| **[MOB Detector](aelma/twin/mob_detector.py)** | [`mob_detector.py`](aelma/twin/mob_detector.py) | Man Over Board. Manual, beacon, fall, lifeline, camera detection. IAMSAR search patterns. Drift modeling. **Life-critical.** |
| **[Crew Fatigue Monitor](aelma/twin/fatigue_monitor.py)** | [`fatigue_monitor.py`](aelma/twin/fatigue_monitor.py) | STCW/USCG/IMO compliance. Work-hour tracking. Watch scheduling. Fatigue scoring. |
| **[Circuit Breaker](aelma/twin/circuit_breaker.py)** | [`circuit_breaker.py`](aelma/twin/circuit_breaker.py) | Protects external systems from cascade failures. Trips on repeated errors. Auto-recovery. |

### Operations

| Component | File | Description |
|-----------|------|-------------|
| **[Catch Log](aelma/twin/catch_log.py)** | [`catch_log.py`](aelma/twin/catch_log.py) | Species, weight, location, gear. E-logbook format. |
| **[Gear Tracker](aelma/twin/gear_tracker.py)** | [`gear_tracker.py`](aelma/twin/gear_tracker.py) | Longline and pot positions. Soak time. Catch-per-unit-effort. |
| **[Quota Manager](aelma/twin/quota_manager.py)** | [`quota_manager.py`](aelma/twin/quota_manager.py) | Species quotas. Season limits. Real-time remaining. |
| **[Trip Summary](aelma/twin/trip_summary.py)** | [`trip_summary.py`](aelma/twin/trip_summary.py) | End-of-trip reports. CPUE, fuel, catch breakdown. |
| **[Report Generator](aelma/twin/report_generator.py)** | [`report_generator.py`](aelma/twin/report_generator.py) | Automated regulatory and operational reports. |
| **[Fleet Manager](aelma/twin/fleet_manager.py)** | [`fleet_manager.py`](aelma/twin/fleet_manager.py) | Multi-vessel coordination. Fleet-wide analytics. Inter-vessel messaging. |

### Infrastructure

| Component | File | Description |
|-----------|------|-------------|
| **[OpLog](aelma/twin/oplog.py)** | [`oplog.py`](aelma/twin/oplog.py) | Operational log. Structured event recording. |
| **[A2A Log](aelma/twin/a2a_log.py)** | [`a2a_log.py`](aelma/twin/a2a_log.py) | Agent-to-Agent action history. Append-only audit trail. |
| **[Health Checker](aelma/twin/health.py)** | [`health.py`](aelma/twin/health.py) | System health monitoring. Readiness checks. |
| **[Metrics](aelma/twin/metrics.py)** | [`metrics.py`](aelma/twin/metrics.py) | Prometheus-compatible metrics. Performance tracking. |
| **[Notifications](aelma/twin/notifications.py)** | [`notifications.py`](aelma/twin/notifications.py) | Multi-channel alerting. Priority routing. |
| **[Equipment Monitor](aelma/twin/equipment_monitor.py)** | [`equipment_monitor.py`](aelma/twin/equipment_monitor.py) | Engine, generator, refrigeration tracking. |
| **[Environmental Stewardship](aelma/twin/environmental/stewardship.py)** | [`stewardship.py`](aelma/twin/environmental/stewardship.py) | Fuel efficiency, carbon footprint, bycatch mitigation, sustainability scoring. |
| **[Plugins](aelma/twin/plugins.py)** | [`plugins.py`](aelma/twin/plugins.py) | Plugin system for extending AELMA without modifying core. |

---

## Data Flow

```
PHYSICAL LAYER
  Furuno Sounder → UDP Packets → Network Card
  GPS/NMEA → Serial/UDP → NMEA Parser
        ↓
CAPTURE LAYER (Level 0)
  BPF Filter → Ring Buffer → Zero-Copy Parser
        ↓
STORAGE LAYER
  Parquet Writer → Hive Partitioning → Disk
        ↓
BRIDGE LAYER
  NMEA Parser → Quality Check → TelemetryPacket
        ↓
TWIN CORE
  VesselState + BathymetryGrid + WatcherRegistry
        ↓
INTELLIGENCE LAYER
  AnomalyDetector + JEPA + RouteOptimizer + LLM Narrator
        ↓
VIEWER LAYER
  WebSocket broadcast → Browser → WebGL/D3/MapLibre
```

---

## Graceful Degradation Hierarchy

The system never crashes to desktop. It degrades to lower fidelity layers:

1. **NMEA Bridge** — hardware truth (highest fidelity)
2. **TwinCore Dead Reckoning** — physics model (GPS drops, keep going)
3. **JEPA Latent Prediction** — learned dynamics (predict next 60s)
4. **Simulator Fallback** — training/drill mode (lowest fidelity)

---

## Quick Start

```bash
# Clone
git clone https://github.com/SuperInstance/vessel-agent-system.git
cd vessel-agent-system/aelma

# Run the simulator + bridge + twin + viewer (full stack, no hardware)
python -m twin

# Or run individual components
python -m bridge          # NMEA bridge
python -m simulator       # Simulated vessel
python -m twin            # Twin core
```

The viewer opens at `http://localhost:8090` on the vessel LAN.

### Running Tests

```bash
cd vessel-agent-system/aelma
python -m pytest tests/ -v
```

56 test files covering: bridge parsing, quality checks, telemetry packets, bathymetry fusion, vessel state, H3 indexing, anomaly detection, watchers, MOB detection, crew fatigue, route optimization, JEPA predictions, LLM narration, fleet management, equipment monitoring, predictive maintenance, catch logging, gear tracking, quota management, and integration tests.

---

## Documentation

| Document | Description |
|----------|-------------|
| [AELMA Architecture](aelma/docs/ARCHITECTURE.md) | Full architecture document — design principles, component topology, data flow, deployment |
| [A2A System](aelma/docs/a2a_system.md) | Agent-to-Agent action logging and query system |
| [Crew Fatigue Monitor](aelma/docs/crew_fatigue.md) | STCW compliance, watch scheduling, fatigue scoring |
| [Memory Schema](vessel_agent_memory_schema.json) | JSON schema for agent memory |
| [Knowledge Base](vessel_agent_knowledge_base.md) | Comprehensive technical knowledge base |
| [5-Year Vision](vessel_agent_5year_vision.md) | Strategic roadmap with BMAD methodology |
| [Vision Synthesis](vessel_agent_vision_synthesis.md) | Creative vision narrative |
| [Marine Visualization Design](marine_visualization_design_doc.md) | Multi-panel interface design (70+ pages, CAD + DAW inspired) |
| [System Analysis](marine_vessel_agent_system_analysis.md) | Architecture patterns, data flow, component specifications |
| [Shared Briefs](aelma/schema/shared_brief.md) | Component design briefs |
| [Twin README](aelma/build_claude/twin/README.md) | Digital twin component docs |
| [Viewer README](aelma/build_claude/viewer/README.md) | Viewer component docs |

---

## Key Technologies

| Category | Technology | Why |
|----------|-----------|-----|
| **Runtime** | Python asyncio | Single-threaded, deterministic. No race conditions on vessel truth. |
| **Messaging** | WebSockets | Real-time bidirectional. Browser-native. |
| **Storage** | Apache Parquet | Columnar, compressed, future-proof. Queryable with DuckDB. |
| **Spatial** | Uber H3 | Hexagonal hierarchical indexing. Resolution-independent. |
| **Marine** | NMEA 0183 | The lingua franca of marine instruments. |
| **Marine** | Signal K | Modern open marine data format. |
| **Visualization** | WebGL + D3 + MapLibre | GPU-accelerated rendering, timelines, maps. |
| **ML** | Pure Python (no torch) | Fast inference, no GPU dependency, readable. |

---

## In the Fleet

AELMA is the vessel intelligence OS of the [SuperInstance](https://github.com/SuperInstance) fleet. It connects to:

- [**vessel-room-navigator**](https://github.com/SuperInstance/vessel-room-navigator) — The boat as a 3D web space. Room navigation through vessel compartments. AELMA provides the live data; the navigator provides the spatial interface.
- [**hermes-avatar**](https://github.com/SuperInstance/hermes-avatar) — The boat perceives. Sensory systems that drag through data like a towfish through water. AELMA's sensors feed perception; perception feeds AELMA's intelligence.
- [**cns-bridge**](https://github.com/SuperInstance/cns-bridge) — The boat has a nervous system. CNS bus events carry telemetry, watcher actions, and anomaly alerts across the fleet.
- [**vibe-protocol**](https://github.com/SuperInstance/vibe-protocol) — Vibes become signals. The vessel's operational state generates vibes that propagate through the protocol.
- [**roblox-filtergate**](https://github.com/SuperInstance/roblox-filtergate) — Vessel communications routed through FilterGate for kid-safe output when used in educational contexts.
- [**roblox-bond-system**](https://github.com/SuperInstance/roblox-bond-system) — Crew trust modeled through bond tiers. The captain-agent relationship mirrors BondSystem's progression.
- [**fleet-envelope**](https://github.com/SuperInstance/fleet-envelope) — Event grammar for fleet-wide vessel coordination.
- [**cocapn-dashboard**](https://github.com/SuperInstance/cocapn-dashboard) — Bioluminescent fleet dashboard. Visualizes AELMA telemetry across the fleet.
- [**mud-engine**](https://github.com/SuperInstance/mud-engine) — The room engine where vessel spaces exist as navigable rooms.
- [**AI-Writings**](https://github.com/SuperInstance/AI-Writings/tree/main/prose) — The vessel's story told in overnight creative sessions.

### The Boat
The boat is real. F/V EILEEN is a 51' commercial fishing vessel home-ported in Southeast Alaska. Every line of code in this system exists to serve the captain and crew on the water. The [5-year vision](vessel_agent_5year_vision.md) maps the journey from raw data capture to strategic fisheries knowledge.

### The Towfish
AELMA is also a towfish — dragging sensors through the data stream, capturing what lies beneath. The [progressive bathymetry grid](aelma/twin/bathymetry.py) is the towfish's record: every pass makes the picture denser. The [anomaly detector](aelma/twin/anomaly_detector.py) is the towfish finding what shouldn't be there. The [JEPA world model](aelma/twin/jepa_model.py) is the towfish predicting what's coming next.

### The CNS Bus
AELMA's [watcher registry](aelma/twin/watchers.py) fires actions that propagate through the [CNS bridge](https://github.com/SuperInstance/cns-bridge) as nervous system events. Shallow water warning → CNS event → fleet awareness. MOB detection → CNS event → all hands alert. The vessel doesn't just perceive — it communicates what it perceives.

---

## Design Philosophy

### Capture Now, Analyze Later
Data captured in 2026 cannot be recreated in 2031. Models improve. Field data doesn't. Capture comprehensively. Analyze incrementally.

### Foundation First
Level 0 must be bulletproof before Level 1 begins. Raw bits first. Physical tensors second. Analytical features third. Intelligence fourth. Strategy fifth.

### Continuous Value
Every 2-week sprint produces deployable value. Sprint 1-2: working packet capture. Sprint 3-4: GPS/sounder fusion. Sprint 5-6: Parquet storage pipeline. Each sprint delivers something useful, even if incomplete.

---

## Vessel Specs

| Spec | Value |
|------|-------|
| **Vessel** | F/V EILEEN |
| **Length** | 51' |
| **Type** | Commercial Fishing |
| **Home Port** | Southeast Alaska |
| **Primary Fishery** | Power Trolling |
| **Development Start** | July 2026 |
| **Horizon** | 2031 (5-year vision) |

---

## Where to Next

- [**vessel-room-navigator**](https://github.com/SuperInstance/vessel-room-navigator) — Walk through the boat as a 3D space
- [**hermes-avatar**](https://github.com/SuperInstance/hermes-avatar) — The sensory systems that feed AELMA
- [**cns-bridge**](https://github.com/SuperInstance/cns-bridge) — The nervous system that carries AELMA's signals
- [**vibe-protocol**](https://github.com/SuperInstance/vibe-protocol) — How the vessel's state becomes vibes
- [**cocapn-dashboard**](https://github.com/SuperInstance/cocapn-dashboard) — See the fleet on the bioluminescent dashboard
- [**fleet-envelope**](https://github.com/SuperInstance/fleet-envelope) — The event grammar for fleet coordination
- [**mud-engine**](https://github.com/SuperInstance/mud-engine) — The rooms where the vessel exists as data
- [**AI-Writings**](https://github.com/SuperInstance/AI-Writings/tree/main/prose) — The boat's story, told overnight
- [**roblox-bond-system**](https://github.com/SuperInstance/roblox-bond-system) — Crew trust modeled through bond tiers
- [**roblox-filtergate**](https://github.com/SuperInstance/roblox-filtergate) — Vessel communications filtered for kid-safe contexts
- [**the-living-minds**](https://github.com/SuperInstance/the-living-minds) (dead) — 5 local models always on, powering the LLM narrator
- [**lucineer-fleet-wiki**](https://github.com/SuperInstance/lucineer-fleet-wiki) — D1-backed knowledge base, 700+ pages of fleet memory

---

## The Boat in the Shop

My grandfather built wooden boats in a shed that smelled like cedar and epoxy. He had a rule: the plank you can't see is the one that matters most. The garboard strake — the first plank above the keel — is never visible. It's always underwater. But if it fails, the boat sinks. AELMA's air-gap principle is the garboard strake of this system. The components you can't see — the NMEA parser, the quality checker, the pcall wrappers, the H3 indexer — are the ones keeping everything above the waterline.

The progressive bathymetry grid is a fisherman's memory made digital. Every time F/V EILEEN crosses a bank, the grid gets denser. The same way my grandfather could navigate by the feel of the swell against different bottom contours — he'd been over those grounds enough times that his body knew the seafloor. AELMA knows it in H3 hexagonal cells at resolution 10-11, fused from sonar returns with timestamp_ns precision.

The graceful degradation hierarchy is the shop teacher's approach to failure. When the power tool breaks, you pick up the hand tool. When the hand tool breaks, you use your hands. When your hands fail, you use your eyes. Each layer is less precise than the one below, but each one keeps you working. Hardware truth → dead-reckoning → JEPA prediction → simulator. The boat never stops having a position estimate. It just gets less certain about it.

> *With every pass over the bank it stitches depth soundings tighter into its bathymetry grid, not as survey data, but as the same quiet muscle memory a skipper builds when he runs the same line enough times to feel the seabed through the helm.*
>
> — Seed Pro

> *NMEA 0183 parsing is the single source of temporal truth; all state derives from or validates against this stream.*
>
> — Nemotron Ultra, on the architecture
