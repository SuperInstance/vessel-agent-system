# AELMA Phase 4 Plan

**From a Vessel That Advises to a Vessel That Acts**

**Date:** 2026-07-28
**Status:** Planning
**Prerequisite:** Phase 2 production ✅ · Phase 3 components delivered ✅ (pilot in progress)

---

## 1. Phases 1–3 Review: The Autonomy Stack Is Already Half Built

Every phase of AELMA has shipped what it promised, on the same design principles the project started with: **air-gap first, standard library Python, schemas as contracts**. Phase 4 is not a pivot — it is the destination the architecture has been pointing at since day one.

### Phase 1 — The Vessel Sees Itself

- End-to-end data spine: **Bridge** (NMEA 0183 → quality-checked TelemetryPackets), **Twin** (live VesselState + progressive TSDF bathymetry), **Simulator** (hardware-free F/V EILEEN trips), **Viewer** (3D browser scene)
- JSON Schema contracts at every boundary — telemetry, vessel state, bathymetry voxels
- Sub-100ms sounder-to-screen latency on a Raspberry Pi 5, zero internet dependency

### Phase 2 — The Vessel Reports Itself

- **Production-ready observability:** WatcherRegistry (deterministic alerting), A2A Log + Query (agents can ask the vessel questions), HealthChecker, Prometheus metrics, CircuitBreaker
- **Signal K / NMEA 2000 ingestion**, StratifiedSampler, LLM Narrator, real-time dashboard UI
- One-command deployment: Docker Compose, systemd, cross-platform start/stop/status scripts
- **407 automated tests, 100% passing** — 4,000+ lines of production code

### Phase 3 — The Vessel Thinks Ahead

- **Fleet management system** (`twin/fleet_manager.py`, `twin/fleet_server.py`): multi-vessel registration, fleet analytics, shared bathymetry with per-vessel provenance, inter-vessel distance matrix, fleet dashboard API
- **JEPA world model** (`twin/jepa_model.py`): online-trained predictive model embedded in the twin core — forecasts depth, speed, engine temperature, and position 60 seconds ahead, and flags anomalies by comparing prediction to observation
- Advisor/sentinel roadmap (LLM route optimization, graduated auto-response) defined and under pilot

### What This Means

| Capability | Status | Phase 4 Builds On It |
|---|---|---|
| Trusted, schema-validated telemetry | ✅ | Autonomy consumes the same packets — no new plumbing |
| Live world model (JEPA) | ✅ | Short-horizon prediction extends to route-level planning |
| Action logging & query (A2A) | ✅ | Every autonomous decision is already auditable by design |
| Anomaly detection + watchers | ✅ | Safety layer for supervised autonomy |
| Fleet sync + shared bathymetry | ✅ | Fleet-scale autonomy and shoreside oversight |
| Graduated response ladder (schema/actions.py) | ✅ | The actuation contract already exists |

Phase 3 gave the vessel a nervous system and a brain. **Phase 4 gives it the helm.**

---

## 2. Phase 4 Vision: The Fully Autonomous Fishing Vessel

**Phase 3 answered: "What should the vessel do next?"**
**Phase 4 answers: "Do it — safely, verifiably, and with the captain's trust."**

Phase 4 closes the loop. The vessel navigates itself to the grounds, finds the fish, identifies what comes over the rail, and stays connected to the fleet and shore from anywhere on the ocean — with a human supervising, not steering.

Four pillars:

- **Autonomous Navigation** — waypoint-to-waypoint transit and on-grounds station-keeping under COLREGs, driven by the twin's own bathymetry and JEPA predictions, with a human-on-the-loop safety envelope.
- **Computer Vision Catch Identification** — rail-mounted cameras identify species and estimate size/count as catch comes aboard, logging directly into the catch record. No more manual tally at 3 a.m.
- **Advanced ML Catch Prediction** — from "fish were here last week" to per-cell, per-species probability maps that update with every haul, fused across the fleet.
- **Satellite Communications** — the air-gap principle becomes air-gap *tolerance*: continuous low-bandwidth sync to shore and fleet via LEO satellite, with graceful degradation when the link drops.

**The north star:** a vessel that runs a survey-and-fish pattern overnight on its own, identifies and logs every fish it catches, phones home its position and haul over satellite, and wakes the captain only when something genuinely needs a human — with every decision logged, explained, and reversible.

**Autonomy doctrine (non-negotiable):**
1. Humans command, the system executes. Autonomy is a mode, not a mutiny — one button always returns manual control, instantly, from the wheelhouse.
2. The physics validator disposes; ML proposes. No model output reaches the helm without passing deterministic constraint checks (depth minimums, speed limits, geofences, COLREGs separation).
3. Every actuation is logged to the A2A log with the full decision context. If it isn't auditable, it doesn't ship.
4. Air-gap tolerance is preserved: loss of satellite link degrades capability, never safety.

---

## 3. Phase 4 Projects

### Project 4.1 — Autonomous Navigation (`helm/`)

**Goal:** Supervised autonomous transit and station-keeping: the vessel follows validated routes and holds position on the grounds without continuous human steering.

**How it works:**

- A new `helm` component subscribes to VesselStateSnapshots and consumes route proposals from the Phase 3 advisor — the same `route_proposal.schema.json` contract, now executable.
- **Waypoint follower** with cross-track-error control; **dynamic positioning** mode for station-keeping over a fishing spot using JEPA short-horizon predictions for wind/current drift compensation.
- **Safety envelope** (deterministic, always on): geofence, minimum-depth floor from the vessel's own fused bathymetry, speed limits, and COLREGs-aware standoff from fleet vessels (positions already available via the fleet manager's distance matrix).
- **Autonomy state machine:** `MANUAL → SUPERVISED (shadow) → ENGAGED (human-on-loop) → DEGRADED → MANUAL`. Every transition logged with cause.
- Actuation goes through the existing `schema/actions.py` contract to the autopilot/ECU interface — rudder and throttle commands only, strictly rate- and authority-limited.

**Deliverables:**
- `helm/` component: waypoint follower, station-keeping, safety envelope, autonomy state machine
- `schema/helm_command.schema.json` + deterministic validator
- Viewer "Helm" panel: active route, envelope status, one-touch manual override
- Simulator harbor trials: full autonomous trips, obstacle injection, GPS-denial drift scenarios
- 60+ new tests

**Why stakeholders care:** Crew cost and fatigue are the two largest constraints on fishing operations. A vessel that transits and holds station on its own turns overnight dead time into productive survey time — with a safety envelope stricter than any tired helmsman.

---

### Project 4.2 — Computer Vision Catch Identification (`vision/`)

**Goal:** Automatic species identification, size estimation, and count of catch as it comes over the rail or across the sorting table — written straight into the catch log.

**How it works:**

- Rail/sorting-table cameras feed an edge inference node (see §5 compute). A quantized detection + classification model identifies species and estimates length from a calibrated reference plane.
- **Confidence-gated logging:** high-confidence identifications write directly to `twin/catch_log.py` with image provenance; low-confidence frames queue for one-tap crew confirmation on the dashboard. The human confirms exceptions, not every fish.
- **On-vessel continual learning:** confirmed/corrected identifications become new training samples; model updates batch-sync to shore and back across the fleet (a fish learned by one vessel is learned by all).
- Fully air-gap capable: inference is local; satellite is only for model/data sync.

**Deliverables:**
- `vision/` component: capture, inference, confidence gating, catch-log integration
- Camera calibration rig + reference-plane sizing pipeline
- Viewer "Catch ID" panel: live identification stream with confirm/correct UI
- Fleet model-sync protocol for classifier updates
- 40+ new tests (frame fixtures, gating logic, log integrity)

**Why stakeholders care:** Accurate catch records are a regulatory obligation and a quota-management asset. Automating identification removes hours of crew labor per haul, eliminates tally errors, and produces audit-ready documentation with photographic evidence for every entry.

---

### Project 4.3 — Advanced ML Catch Prediction (`oracle/`)

**Goal:** Per-cell, per-species catch probability maps that predict where the fish will be tomorrow — learning continuously from the fleet's own hauls, soundings, and the vision system's species-confirmed catch data.

**How it works:**

- `oracle` extends the JEPA world-model approach from telemetry to ecology: spatiotemporal models over bathymetry, temperature, season, tide (existing `docs/tide_prediction.md`), effort, and — crucially — **vision-confirmed catch events** from Project 4.2, which provide species-labeled ground truth no competitor has.
- Outputs a `catch_forecast.schema.json` probability grid consumed by the Phase 3 advisor (better routes) and Project 4.1's helm (autonomous survey patterns weighted toward high-uncertainty/high-expected-yield cells).
- **Fleet learning:** haul outcomes from every vessel improve every vessel's forecast through the fleet sync layer. Exploration is coordinated — the fleet stops re-sampling known water.
- Runs incremental updates on-vessel; heavy retraining batch-jobs to shore over satellite.

**Deliverables:**
- `oracle/` component: feature pipeline, species probability grid, forecast API
- `schema/catch_forecast.schema.json` + validator
- Viewer forecast overlay: probability heatmaps on the bathymetry map
- Backtesting harness against historical catch logs (report: hit-rate vs. captain baseline)
- 40+ new tests

**Why stakeholders care:** This is the revenue engine. Vision-confirmed catch data feeding fleet-wide prediction creates a data flywheel competitors cannot replicate: every haul by every vessel makes the whole fleet smarter. Even a single-digit percentage lift in catch-per-unit-effort is transformative at fleet scale.

---

### Project 4.4 — Satellite Communications (`skylink/`)

**Goal:** Always-reachable vessels: continuous telemetry, fleet sync, and shoreside oversight from anywhere at sea — upgrading AELMA from air-gapped to air-gap-*tolerant*.

**How it works:**

- `skylink` is a store-and-forward sync gateway over LEO satellite (Starlink Maritime-class terminal): prioritized, bandwidth-adaptive uplink of telemetry digests, catch records, alerts, and fleet bathymetry deltas; downlink of model updates, forecasts, weather, and shore commands.
- **Tiered link budget:** full-fidelity sync on broadband; a lean <10 kbps safety tier (position, health heartbeat, distress) falls back to narrowband (Iridium Certus-class) when the primary link degrades.
- **Air-gap tolerance by design:** everything queues locally when disconnected and reconciles with per-record provenance on reconnect — the same eventual-consistency discipline proven in the Phase 3 fleet layer. Autonomy never depends on the link.
- Security: signed command channel (shore → vessel commands require dual authorization), encrypted transport, schema validation on everything inbound.

**Deliverables:**
- `skylink/` gateway: store-and-forward queue, tiered link management, signed command channel
- Shoreside relay + fleet operations console (all vessels, all the time)
- Simulator link-budget scenarios (dropouts, congestion, failover)
- 40+ new tests

**Why stakeholders care:** Shoreside managers see every vessel live, autonomous operations stay supervised from anywhere, and the safety heartbeat means a vessel in trouble is never silent. This is also the channel that makes the fleet learning flywheel (4.3) and fleet-wide vision models (4.2) possible.

---

## 4. Timeline — Q4 2026

Ambitious, sequenced for dependencies: `helm/` and `vision/` are independent tracks; `oracle/` feeds on vision data; `skylink/` underpins fleet-scale everything and lands early.

| Milestone | Target | Deliverable | Exit Criteria |
|---|---|---|---|
| **M0 — Kickoff & hardware** | 2026-10-01 | Edge compute + cameras + sat terminal ordered/installed on pilot vessel; schemas drafted (`helm_command`, `catch_forecast`) | Hardware on bench; schemas pass validation; simulator scenarios running |
| **M1 — Skylink alpha** | 2026-10-15 | Store-and-forward sync live on test link; safety heartbeat tier | 7-day continuous link with 100% queue reconciliation after induced dropouts |
| **M2 — Helm shadow** | 2026-11-01 | Full autonomy stack in shadow mode on simulator + pilot vessel: proposes, never actuates | 100+ shadow hours; zero constraint-validator violations; every divergence from human helm logged |
| **M3 — Vision alpha** | 2026-11-15 | Rail camera identifying 5 priority species on pilot vessel; catch-log integration | ≥90% top-1 accuracy on priority species; 100% of entries carry image provenance |
| **M4 — Helm engaged (supervised)** | 2026-12-01 | Human-on-the-loop autonomous transit + station-keeping on pilot vessel in designated test area | 50+ engaged hours, zero safety-envelope breaches, ≤2 manual interventions per 10h |
| **M5 — Oracle alpha + Skylink GA** | 2026-12-15 | Catch probability maps backtested vs. historical logs; fleet ops console live for pilot fleet | Backtest hit-rate ≥ captain baseline; shore console tracking all pilot vessels continuously |
| **M6 — Phase 4 feature-complete** | 2026-12-31 | All four projects integrated on pilot vessel; autonomous survey pattern demo (helm + oracle + vision + skylink together) | Overnight autonomous survey: route executed, catch identified & logged, shore supervised end-to-end |

**Post-Q4 (2027, for honesty):** Q4 delivers the integrated pilot. Fleet-wide GA, expanded species coverage, and regulator engagement for broader autonomous operation continue into 2027 alongside Phase 3 GA — the winter/shoulder season is when captains have time to be part of this.

---

## 5. Resource Requirements

### Compute

| Item | Purpose | Notes |
|---|---|---|
| Existing Pi 5-class vessel computer | `helm/`, `oracle/` inference, `skylink/` | Phase 1–3 stack already runs here; helm/oracle are stdlib-Python by design |
| Edge AI node (Jetson Orin-class) ×2 | Vision inference (4.2), CV model retraining prep | ~40W; redundant pair on pilot vessel |
| Shoreside server / modest cloud | Fleet retraining (oracle, vision models), ops console | Existing shoreside infra + ~$100–200/month |

### Sensors & Actuation

| Item | Purpose | Est. Cost (pilot vessel) |
|---|---|---|
| 2× industrial IP cameras (rail + sorting table) + lighting | Catch identification | $2k–4k |
| Autopilot/ECU interface (NMEA 2000 helm gateway) | Actuation for `helm/` | $5k–8k installed |
| GNSS heading upgrade (dual-antenna) | Precision station-keeping | $3k–5k |
| Existing sounder, engine telemetry, wind instruments | Already ingested by bridge | $0 |

### Connectivity

| Item | Purpose | Est. Cost |
|---|---|---|
| LEO satellite terminal (Starlink Maritime-class) | Primary broadband sync | ~$2.5k hardware + ~$250–1k/mo |
| Narrowband backup (Iridium Certus-class) | Safety heartbeat tier | ~$1.5k hardware + ~$100/mo |

### People

| Role | Commitment | Duration | Focus |
|---|---|---|---|
| Senior Python engineer | 1.0 FTE | 3 months | `helm/`, `skylink/`, twin integration |
| ML engineer (vision) | 1.0 FTE | 3 months | `vision/` models, calibration, fleet model sync |
| ML engineer (prediction) | 0.5 FTE | 3 months | `oracle/` pipeline, backtesting |
| Frontend engineer | 0.3 FTE | 2 months | Helm / Catch ID / forecast panels, ops console |
| Marine autonomy / safety advisor | 0.2 FTE | Throughout | Envelope design, COLREGs review, regulator liaison |
| Pilot captain + crew | 0.2 FTE | M2–M6 | Shadow trials, catch-ID confirmation, acceptance |
| QA / test engineering | 0.4 FTE | 3 months | 180+ new tests, fault injection, trial telemetry analysis |

### Budget Summary (indicative, Q4 2026 pilot)

| Category | Estimate |
|---|---|
| Personnel (blended, 3 months) | $160k – $210k |
| Pilot vessel hardware (compute, cameras, autopilot interface, GNSS) | $15k – $20k |
| Connectivity (hardware + 3 months service) | $6k – $10k |
| Shoreside/cloud | $2k – $3k |
| Contingency (20% — hardware lead times) | ~$40k |
| **Total** | **~$225k – $285k** |

---

## 6. Risk Assessment & Mitigation

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | **Autonomy acts unsafely** (collision, grounding) | Low | Critical | Deterministic safety envelope independent of all ML; geofence + own-bathymetry depth floor + COLREGs standoff; one-touch manual override hardwired at wheelhouse; shadow mode (M2) must show 100+ clean hours before any actuation; actuation authority rate- and magnitude-limited |
| R2 | **Regulatory exposure** — autonomous operation outside permitted frameworks | Medium | High | Phase 4 Q4 is *supervised* autonomy only: a licensed mariner is always on watch and legally in command. Marine autonomy advisor engaged from M0; trial area coordinated with authorities before M4. No unsupervised operation in scope this quarter |
| R3 | **Vision model misidentifies catch** → bad regulatory records | Medium | High | Confidence gating: low-confidence identifications require crew confirmation; every entry carries image provenance for audit; species rollout limited to 5 priority species until accuracy is proven; correction workflow feeds retraining |
| R4 | **Satellite link failure mid-operation** | Medium | Medium | Air-gap tolerance is architectural, not aspirational: autonomy, vision, and prediction are fully local; link loss degrades sync only. Narrowband safety tier fails over automatically; store-and-forward reconciliation proven in M1 exit criteria |
| R5 | **ML catch prediction underperforms** → wasted positioning effort | Medium | Medium | Oracle is advisory weighting, not a sole driver; M5 backtest gate vs. captain baseline before forecasts influence autonomous routing; graceful fallback to historical-density routing |
| R6 | **Hardware lead times slip Q4** | Medium | Medium | M0 orders hardware first; simulator substitutes for hardware (proven Phase 1 pattern) so software tracks never block; contingency budget carries expedited shipping |
| R7 | **Crew resistance / trust erosion** | Medium | High | Autonomy doctrine puts crew in command; vision confirmation UI saves labor rather than surveilling; pilot captain is a paid stakeholder from M0, and every system decision is explainable via the A2A log |
| R8 | **Scope creep — four projects in one quarter** | Medium | High | Tracks are dependency-sequenced and independently shippable: skylink and vision deliver value even if helm slips; M6 integration demo is the only all-hands milestone, and it degrades gracefully to "helm + vision" if oracle misses M5 |

---

## The Bottom Line

Phases 1–3 built a vessel that sees itself, reports itself, and thinks ahead — 400+ tests, a live world model, a fleet that shares everything it learns. Phase 4 closes the loop: **a vessel that fishes itself, knows what it caught, predicts where to go next, and is never out of reach** — with the captain's hand always on the override and every decision on the record.

This is the moment AELMA stops being the best-instrumented vessel in the fleet and becomes the fleet others can't catch.

**Next step:** Approve M0 kickoff and hardware procurement — target start 2026-10-01.
