# AELMA Phase 3 Roadmap

**From Watching the Ocean to Deciding On It**

**Date:** 2026-07-28
**Status:** Planning
**Prerequisite:** Phase 2 complete ✅

---

## 1. Phase 2 Review: The Foundation Is Solid

Phase 2 transformed AELMA from a working prototype into a production-grade vessel intelligence platform. Every planned component shipped, and the system is now observable, self-healing, and deployable with a single command.

### What Was Delivered

| Component | What It Does | Location |
|---|---|---|
| **Bridge** | NMEA 0183 parsing, quality scoring, Signal K ingestion, TelemetryPacket broadcast | `bridge/` |
| **Twin** | Live vessel state, progressive TSDF bathymetry, WebSocket viewer broadcast | `twin/` |
| **Watcher Engine** | Rule-based alerting with cooldowns, priorities, and a live registry | `twin/` (watchers) |
| **A2A System** | Agent-to-agent query interface: other software can *ask the vessel questions* | `twin/a2a_query.py` |
| **Circuit Breaker** | Automatic failure isolation and recovery between components | `twin/circuit_breaker.py` |
| **Health Monitor** | Component liveness, heartbeat tracking, degradation reporting | `twin/health.py` |
| **Simulator** | Realistic F/V EILEEN trip simulation for hardware-free development | `simulator/` |
| **Viewer** | 3D Three.js scene + full telemetry dashboard with gauges, charts, and bathymetry heatmap | `viewer/` |
| **Schemas** | JSON Schema contracts: telemetry, vessel state, bathymetry voxels | `schema/` |
| **Deployment** | One-command Docker Compose, systemd units, cross-platform start/stop/status scripts | `scripts/`, `docker-compose.yml` |

### The Numbers

- **220+ automated tests** — unit, integration, schema validation, circuit breaker, health, A2A, and end-to-end stack tests, all green
- **15 JSON Schema contracts** enforced at every component boundary
- **4 delivery packages** shipped (dashboard, Signal K integration, watcher system, deployment automation)
- **Zero external runtime dependencies** beyond `websockets` — still deployable on a Raspberry Pi 5 on an air-gapped vessel LAN

### Why This Matters for Phase 3

Phase 2 gave us three things Phase 3 will build directly on:

1. **A clean data spine.** Every telemetry reading flows through schema-validated packets. AI models can consume the same contracts — no new plumbing.
2. **A query interface.** The A2A system already lets external agents ask structured questions about vessel state. An LLM decision engine is just a smarter A2A client.
3. **An alert-and-act skeleton.** Watchers detect conditions; Phase 3 extends them from "notify a human" to "propose (and eventually take) action."

---

## 2. Phase 3 Vision: The Vessel That Thinks Ahead

**Phase 2 answered: "What is the vessel doing right now?"**
**Phase 3 answers: "What should the vessel do next — and why?"**

Phase 3 layers AI-powered decision making on top of the live digital twin, turning AELMA from a monitoring system into an advisory system across three axes:

- **AI-Powered Decision Making** — An LLM-based reasoning layer that consumes live twin state, bathymetry, weather, and catch history to produce recommendations a captain can trust: where to go, how fast, when to come home. Recommendations arrive with reasoning, not just numbers.
- **Fleet Optimization** — Everything built for one vessel generalizes to N vessels. Coordinated routing, shared bathymetry fusion across the fleet, and fleet-level situational awareness — each vessel's soundings improve every other vessel's charts.
- **Predictive Maintenance** — Continuous anomaly detection on engine, electrical, and hull telemetry catches failures *before* they happen, and the auto-response layer reacts in seconds — not after the weekend engineer reads the log.

**The north star:** a captain asks the tablet, *"Where should we set tomorrow given the forecast, our fuel, and where the fish were last week?"* — and gets a defensible answer, backed by the vessel's own data, in plain language.

---

## 3. Phase 3 Projects

### Project 3.1 — LLM-Based Route Optimization (`advisor/`)

**Goal:** A route recommendation engine that combines the live twin state, fused bathymetry, historical catch/effort data, and weather forecasts into ranked route options with natural-language justification.

**How it works:**

- A new `advisor` component subscribes to the twin's VesselStateSnapshot stream (existing WS :8090) and queries history through the A2A interface.
- On request (or on schedule), it assembles a structured context packet — position, bathymetry confidence map, fuel state, weather, season, past catch density — and calls an LLM (cloud API when connected; local small model when air-gapped).
- The LLM returns candidate routes as structured JSON conforming to a new `route_proposal.schema.json`. A deterministic validator scores each candidate against hard constraints (fuel range, depth minimums, weather limits) — the LLM proposes, physics disposes.
- The viewer gains a **Route Advisor panel**: up to 3 ranked routes drawn on the bathymetry map, each with a one-paragraph rationale and projected fuel/time/catch-density estimates.

**Deliverables:**
- `advisor/` component (Python asyncio, same conventions as `twin/`)
- `schema/route_proposal.schema.json` + validator
- Viewer Route Advisor panel
- Simulator scenarios for validation (weather front arrival, fuel-limited day)
- 40+ new tests

**Why stakeholders care:** Every wasted hour trolling empty water is fuel burned and catch lost. Even a 10% improvement in daily route efficiency pays for the entire project within a single season.

---

### Project 3.2 — Anomaly Detection with Auto-Response (`sentinel/`)

**Goal:** Move from threshold alarms ("RPM > 4000!") to learned anomaly detection ("vibration signature on the main has drifted 2.3σ from its 30-day baseline — early bearing wear pattern") with graduated automatic responses.

**How it works:**

- A `sentinel` component maintains rolling statistical baselines per telemetry channel (mean, variance, autocorrelation) — pure stdlib math, no heavy ML frameworks, honoring the air-gap-first principle.
- Multi-channel correlation rules detect compound signatures: e.g., rising exhaust temp + falling oil pressure + RPM instability = impeller failure in progress, hours before a single threshold trips.
- **Graduated auto-response ladder:**
  1. *Log & flag* — annotate the A2A log, raise a low-priority watcher event
  2. *Notify* — dashboard alert with diagnosis and recommended action
  3. *Advise in real time* — "reduce to 1400 RPM to reach harbor safely"
  4. *Act (opt-in only)* — trigger hardware-safe actions through a strictly-scoped action API (`schema/actions.py` already defines the contract)
- Every detection and response is recorded to an immutable maintenance log, building the per-vessel failure history that makes future predictions better.

**Deliverables:**
- `sentinel/` component with baseline learning + correlation engine
- Auto-response ladder wired into the existing watcher registry
- Maintenance log + viewer "Vessel Health" panel with per-system health scores
- Simulator fault-injection scenarios (impeller wear, fuel contamination, electrical degradation)
- 50+ new tests

**Why stakeholders care:** One avoided at-sea engine failure — tow fees, lost fishing days, safety risk — justifies this project alone. Unplanned downtime drops; insurance conversations get easier.

---

### Project 3.3 — Multi-Vessel Coordination (`fleet/`)

**Goal:** Generalize the twin from one vessel to a fleet, with shared bathymetry fusion and coordinated operations.

**How it works:**

- A shoreside (or flagship-side) `fleet` aggregator consumes VesselStateSnapshots from N vessel twins over the existing WebSocket protocol — vessels sync when in range (WiFi/cellular/satellite), queue when not. Air-gap tolerance is preserved: the fleet layer is eventually consistent, never a single point of failure.
- **Shared bathymetry:** soundings from every vessel fuse into one fleet-wide grid with per-vessel provenance. A spot one boat surveyed on Monday improves everyone's charts on Tuesday.
- **Fleet awareness panel** in the viewer: all vessels on one map, with separation alerts, coverage heatmaps (who's surveyed what), and coordination suggestions ("Vessel B, the 40m contour 2nm northeast is unmapped this season").
- **Coordinated routing (stretch):** Project 3.1's advisor extends to fleet level — divide survey/fishing effort across vessels to maximize fleet-wide yield instead of each boat fishing the same history.

**Deliverables:**
- `fleet/` aggregator with eventual-consistency sync
- Fleet-wide bathymetry grid with provenance tracking
- Viewer fleet map + coverage heatmap
- Multi-vessel simulator configuration
- 40+ new tests

**Why stakeholders care:** This is the multiplier. Bathymetry, routes, and anomaly knowledge stop being per-boat silos. A 3-vessel fleet doesn't get 3× the data — it gets compounding coverage.

---

## 4. Timeline & Milestones

Assuming a single focused team starting **2026-08-01**. Projects overlap deliberately — the shared infrastructure lands first.

| Milestone | Target Date | Deliverable | Exit Criteria |
|---|---|---|---|
| **M0 — Kickoff & data prep** | 2026-08-15 | Historical telemetry/catch dataset curated; LLM provider + local-model fallback selected; `route_proposal` schema drafted | Schemas pass validation; dataset loads in replay mode |
| **M1 — Sentinel alpha** | 2026-09-15 | Baseline learning + graduated response ladder on simulator faults | Detects all 5 injected fault scenarios ≥ 30 min before threshold alarms |
| **M2 — Advisor alpha** | 2026-10-01 | Single-vessel route proposals in the viewer with validator-gated LLM output | 3 ranked routes with rationale; 100% of proposals satisfy hard constraints |
| **M3 — Fleet alpha** | 2026-11-01 | Two-vessel sync with shared bathymetry grid and fleet map | Soundings from vessel A appear in vessel B's grid with provenance |
| **M4 — Sentinel beta** | 2026-11-15 | Auto-response levels 1–3 live on test vessel; maintenance log + health panel | 2 weeks shadow-mode on real telemetry, zero false auto-actions |
| **M5 — Advisor beta** | 2026-12-01 | Weather + catch-history integration; captain feedback loop ("accept/modify/reject" captured) | ≥ 60% of proposals accepted or lightly modified over trial period |
| **M6 — Fleet beta** | 2027-01-15 | 3+ vessel pilot; coverage heatmaps; coordinated routing demo | Full-season replay showing measurable coverage gain vs. independent ops |
| **M7 — Phase 3 GA** | 2027-02-28 | All components production-ready; docs; 350+ total tests green | Full stack deploys with one command; sign-off from pilot captains |

**Seasonal note:** milestones are paced so M4–M6 hit the winter/shoulder season — pilots run when captains have time to give feedback, and GA lands before the 2027 season opens.

---

## 5. Resource Requirements

### People

| Role | Commitment | Duration | Focus |
|---|---|---|---|
| Senior Python engineer | 1.0 FTE | 7 months | `sentinel/`, `fleet/` core, twin integration |
| ML/decision-systems engineer | 1.0 FTE | 6 months | `advisor/` LLM pipeline, anomaly models, validators |
| Frontend engineer | 0.5 FTE | 4 months | Viewer panels (Route Advisor, Vessel Health, Fleet Map) |
| Domain advisor (captain/fleet manager) | 0.1 FTE | Throughout | Requirement validation, pilot feedback, acceptance |
| QA / test engineering | 0.3 FTE | 6 months | Test suites, fault-injection scenarios, pilot telemetry analysis |

### Infrastructure

- **Compute:** existing vessel hardware (Pi 5-class) handles `sentinel/` and `fleet/` sync; `advisor/` LLM calls use a cloud API where connected, with a small local model (≤ 4B params, quantized) for air-gapped fallback — runs on the same Pi
- **Pilot vessels:** 3 vessels instrumented for M6 pilot (one can be the F/V EILEEN reference vessel)
- **Cloud (optional, minimal):** LLM API budget ~$50–150/month during trials; fleet sync relay for the pilot (~$20/month VPS or existing shoreside server)
- **No new hardware dependencies:** Phase 3 is pure software on the Phase 2 stack

### Budget Summary (indicative)

| Category | Estimate |
|---|---|
| Personnel (blended, 7 months) | $280k – $340k |
| LLM API + cloud services | $1k – $2k |
| Pilot vessel instrumentation | $3k – $5k (mostly crew time) |
| Contingency (15%) | ~$45k |
| **Total** | **~$330k – $390k** |

### Risks & Mitigations

| Risk | Mitigation |
|---|---|
| LLM route proposals are unsafe or nonsensical | Hard-constraint validator rejects any proposal violating physics/regulations; LLM never actuates directly |
| Auto-response acts on a false positive | Ladder starts advisory-only; level-4 actuation is opt-in per vessel and per action type; shadow mode for 2+ weeks first |
| Fleet sync conflicts | Eventual consistency with per-voxel provenance; last-writer-wins only within confidence scoring, never destructive |
| Air-gap breaks LLM advisor | Local fallback model with reduced fidelity; cloud is an enhancement, never a requirement |

---

## The Bottom Line

Phase 2 built a vessel that can see itself. Phase 3 builds a vessel — and then a fleet — that can **think ahead**: routes that learn, failures caught before they happen, and every sounding from every hull making every chart better. The architecture is already ready for it; Phase 3 is where AELMA stops being instrumentation and starts being an advantage.

---

**Next step:** Approve M0 kickoff and the historical data curation effort — target start 2026-08-01.
