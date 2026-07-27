# AELMA Deep Research Synthesis
## Agent-Engine Linked Marine Architecture — Prior-Art Memo & Strategic Recommendations

**Date:** 2026-07-26
**Author:** Research synthesis from 4 parallel deep-research streams
**Source document:** `## The Vessel-Roblox Digital Twin Archit.txt` (VRDTA/AELMA vision, 785 lines)
**Companion documents:**
- `aelma_literature_survey.md` — HIL + game-engine survey (full detail)
- This memo — cross-cutting synthesis, novelty assessment, recommendations

---

## Executive Summary (Read This First)

The AELMA vision document proposes using Roblox/Luau as the core of a hardware-in-the-loop digital twin for a commercial fishing vessel, with ESP32 sensors, AI agents, spatial reasoning, predictive "Divination" simulations, and crew interaction via phones/tablets. The vision is compelling and contains **several genuinely novel contributions**. However, four parallel research streams into marine digital-twin prior art, game-engine HIL ecosystems, Roblox's actual capabilities, and sensor-fusion techniques reveal **three blocking technical realities** that must shape any implementation path forward.

### The Three Blocking Realities

1. **Roblox WebSockets are Studio-only.** The actual API (`HttpService:CreateWebStreamClient`) is explicitly blocked in published experiences. There is no `ConnectWebSocket` method. For 50Hz telemetry you'd fall back to HTTP polling at 500 req/min/server ≈ **8.3 Hz** — 6× under target. ([DevForum announcement, Oct 2025](https://devforum.roblox.com/t/websockets-support-in-studio-is-now-available/4021932))

2. **Roblox blocks private IPs and requires cloud authentication.** `HttpService` from published experiences cannot egress to RFC1918 space (10.x, 192.168.x, 127.x). There is **no officially supported air-gapped, LAN-only, or offline mode.** A vessel without persistent internet cannot run a live Roblox experience.

3. **Roblox physics are not vessel-grade.** The engine is a custom in-house design (NOT PhysX/Havok), with no fluid dynamics solver, no wave forcing, no hydrodynamic drag primitive. Community reports describe vessel-scale buoyancy as "rocket science" with ships that "bop uncontrollably." Engineering certification is out of reach.

### The Strategic Recommendation

**Roblox is an excellent visualization, training, and "game-mode" layer. It is the wrong core for a HIL vessel twin.** The user's own framing — "Roblox is just one easy-to-use game-engine that's easy to transfer skills over for players who know it. But there are others that offer distinct advantages" — points directly to the right architecture.

**Recommended hybrid architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│  VESSEL SIDE (air-gapped LAN, no internet required)              │
│                                                                  │
│  Sensors ──▶ Signal K Server ──▶ Deterministic Twin Core         │
│  (NMEA 2000)    (Raspberry Pi)     (Godot/Bevy headless,         │
│  (ESP32s)                          micro-ROS, real physics)      │
│                                    ▲                             │
│                                    │                             │
│                                    │  Cesium World Bathymetry    │
│                                    │  + progressive sonar/TSDF   │
│                                    │  + drone photogrammetry     │
│                                    │  + human-feedback stylize   │
│                                                                  │
│  Local tablets (browser or native client) ◀── LAN streaming     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ (satellite, when available)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  SHORESIDE / GAME-MODE LAYER                                     │
│                                                                  │
│  Roblox experience ──▶ son plays, captain reviews, fleet shares  │
│  (or Unity/Unreal ──▶ if higher fidelity needed)                │
│  (or Web/WebRTC   ──▶ for zero-install)                         │
│                                                                  │
│  "Divination" sandbox ──▶ parallel physics for what-if sims      │
│  (NVIDIA Isaac Sim / Unity ML-Agents)                            │
└─────────────────────────────────────────────────────────────────┘
```

This preserves every good idea in the AELMA vision — the charming aesthetic, the spatial reasoning, the replay-as-play, the progressive world refinement — while routing around Roblox's three hard blockers.

---

## Part 1 — What's Genuinely Novel About AELMA

The research confirms that **no prior system combines all of these elements**. The AELMA vision sits at an unstudied intersection.

### 1.1 Well-Trodden Ground (do not claim novelty)

| Area | Prior Art |
|---|---|
| Marine digital twins as concept | DNV OSP, Kongsberg Kognitwin, ABB OCTOPUS, Wärtsilä Eniram, Siemens Simcenter |
| Game engines in maritime simulation | MARUS (Unity, cited 60×), Kong et al. 2024 (Unity), Li et al. 2024 (UE5) |
| NMEA 2000 → IP bridging | Signal K, canboat, Maretron IPG100, Actisense, Yacht Devices YDEN-02 |
| AI for fishing operations | Catchvision (EM video review), GreenFish (fish prediction), NOAA eTrips |
| VR/AR marine training | VR-ME (fishing-vessel emergencies), Maersk Training, Propel SAYFR |
| HIL for marine systems | Lee et al. 2024 (MDPI), Liu et al. 2024 (ROV HIL), DNV OSP DP-Ship demo |
| Autonomous vessel regulations | IMO MASS, USCG Policy Letter 22-01, ABS Guide 323, DNV AROS (2025) |
| 3D Gaussian Splatting for underwater | WaterSplatting, UW-GS, Aqua-Splat, Z-Splat (all 2024-2025) |
| Progressive bathymetry | Navionics SonarChart Live (closest commercial analog) |

### 1.2 Genuinely Novel AELMA Contributions

After cross-referencing all four research streams, **five contributions stand out as defensibly novel**:

**1. Consumer game engine as live operational vessel twin (not training simulator).**
Every existing game-engine maritime project targets training simulators or USV/ROV autonomy testing. Nobody runs a game engine as a live operational twin ingesting 50Hz HIL telemetry from a physical vessel. The closest prior art — Kongsberg K-Sim — is disconnected from live operations. DNV's OSP does co-simulation but uses engineering models (FMI/FMU), not an interactive 3D world.

**2. AI agents that reason about the vessel's 3D spatial geometry.**
Existing vessel AI/ML operates on tabular time-series data (engine RPM, fuel flow, catch logs). The paradigm of an LLM-driven agent issuing spatial queries (`workspace:GetPartsInPart`) against a live 3D vessel model — "is the crane load path clear of the rigging?" — is unstudied in marine literature. The closest academic analog is Meta's AI Habitat 3.0, which trains embodied agents in photorealistic 3D worlds but has never been applied to a vessel.

**3. Human-in-the-loop RLHF for stylized marine rendering.**
This is the user's distinctive "best-current-render" vision: drone flies overhead, sonar pings below, and the system renders its best guess at the world. The captain says "coral good, dogfish wrong" and the renderer improves. **No prior art exists for this**. Generative-AI scene stylization (GauGAN, DreamFusion, Magic3D, Shap-E) exists, and Roblox Procedural Models (Beta) exists, but the feedback loop from captain-vision to sensor-fused 3D render does not. This is genuinely patentable territory.

**4. Fishing-vessel-specific spatial digital twin.**
The only fishing-vessel digital twin found is the Naoned project (France, 2024) — a 76-foot seine trawler fitted with sensors for hybrid-propulsion energy optimization. It uses 2D econometric models, not spatial reasoning. AELMA's integration of hull + engines + hydraulics + winches + catch + crew into a single live 3D physics world has no precedent.

**5. "Replay past trips" as consumer/family entertainment.**
Maritime trip replay exists only in VDR (voyage data recorder) forensics and regulatory contexts. The AELMA concept of replaying a fishing trip as a shareable, playable experience — "watch dad catch the halibut" — borrows from fitness apps (Strava Flyby, Relive.cc) and gaming replays. Nobody does this for fishing.

**Secondary contributions (less novel but underexplored):**
- Predictive "Divination" sandbox (Tesla shadow mode is the analog; DNV OSP does engineering co-sim)
- Crew interaction via personal phones/tablets (US Navy uses custom tablets; consumer-game-client-as-HMI is new)
- Integrating hull + engines + hydraulics + winches + catch into one spatial model (existing systems are siloed)

---

## Part 2 — Marine Industry Prior Art (The Competition That Isn't)

**Key finding: No major marine vendor uses a game engine for live operational digital twins. None offers interactive 3D spatial reasoning for AI agents.**

| Vendor | Product | Physics | Visualization | Game Engine? | Live HIL? |
|---|---|---|---|---|---|
| Kongsberg | K-Sim (training) | Proprietary hydrodynamic | Bridge mockup 2D/3D | No | No |
| Kongsberg | Kognitwin (ops) | None (data integration) | 2D dashboards | No | No |
| DNV | OSP | FMI/FMU co-simulation | Engineering data | No | Yes (virtual commissioning) |
| ABB | OCTOPUS | Motion/energy models | KPI dashboards | No | No |
| Wärtsilä | Eniram | Hydrodynamic + AI | Dashboards | No | No |
| Siemens | Simcenter | CFD/FEA (STAR-CCM+) | CAE post-processing | No | Yes |
| **AELMA** | *(proposed)* | **Game-engine physics** | **Interactive 3D world** | **Yes** | **Yes** |

### Critical prior art to build on

**Signal K** ([signalk.org](https://signalk.org/)) is the **most critical existing infrastructure** for AELMA. It is an open-source marine data platform that:
- Converts NMEA 0183 + NMEA 2000 into unified JSON
- Serves via WebSocket and REST APIs
- Runs on a Raspberry Pi via OpenPlotter
- Has hundreds of plugins

**AELMA's gateway daemon should extend Signal K, not replace it.** The NMEA-to-IP bridge problem is solved; building on Signal K + canboat + a hardware gateway (Actisense NGT-1 or Yacht Devices YDEN-02) is the well-trodden path.

**DNV Open Simulation Platform (OSP)** is the most sophisticated "what-if" prior art. It uses FMI/FMU co-simulation to interconnect engineering models from Simulink, Dymola, etc. without remodelling. The OSP explicitly assesses **emergent properties** — failures that arise only from system interactions. AELMA's "Divination" sandbox should be benchmarked against OSP's approach.

### Regulatory landscape (matters for actuation)

If AELMA ever intends to actuate throttle/hydraulics from a game client:

- **USCG Policy Letter 22-01 (Change 1, April 2024)** — Guidelines for Human-Supervised Testing of Remote Controlled and Autonomous Systems. The operative US document.
- **ABS Guide 323 (Oct 2024)** — Requirements for Autonomous and Remote Control Functions. Goal-based, risk-based.
- **DNV AROS (2025)** — Autonomous and Remotely Operated Ships class notation family, replacing RU-AUTOS.
- **IMO MASS Code** — in draft, addressing regulatory gaps for autonomous ships.

**The gap:** All existing frameworks assume remote control from dedicated shore control centers with certified operators. Consumer-game-client actuation is novel regulatory territory. **A phased path starts advisory-only (read + recommend) and progresses to supervised control.**

---

## Part 3 — Roblox Technical Reality Check

### 3.1 What Roblox is genuinely good at

| Capability | Assessment | AELMA fit |
|---|---|---|
| **Spatial queries** (Raycast, GetPartsInPart, Blockcast, Sweepcast) | Solid, well-engineered | Excellent for agent perception |
| **Spatial audio** (3D positional, Acoustic Simulation beta) | Native, works well | "AI voice from the fault direction" works |
| **Cross-platform install base** | 151M DAU Q3 2025; iOS/Android/Win/Mac/Xbox/PS/Quest | BYOD is trivial — captain installs app |
| **Luau scripting** | Fast interpreter, well-debugged, easy to learn | Fine for game logic, spatial queries, UI |
| **Multi-user 3D collaboration** | Roblox's bread and butter | Captain + crew + son in shared scene |
| **Charming aesthetic** | Established suspension-of-disbelief | "Good enough" rendering is a feature |

### 3.2 The three blockers (detailed)

**Blocker 1: WebSockets are Studio-only.**
- The actual API is `HttpService:CreateWebStreamClient(Enum.WebStreamClientType.WebSocket, {Url=...})`.
- The DevForum announcement (Oct 2025) states explicitly: *"Can I use WebSockets in experiences? Just like Server-Sent Events, this feature is Studio-only. Any `CreateWebStreamClient()` requests made in live experiences will be blocked."*
- There is no method called `ConnectWebSocket`. The AELMA paper's code samples reference a non-existent API.
- **Workaround:** HTTP polling at 500 req/min = ~8.3 Hz. For 50Hz telemetry you'd need Open Cloud endpoints (2500 req/min, ~42Hz) but those only work for Roblox's own cloud APIs, not arbitrary LAN hardware.

**Blocker 2: No air-gapped/LAN operation.**
- Published-game `HttpService` runs from Roblox datacenters. `localhost` refers to the Roblox server machine, not your hardware.
- Private IPs (10.x, 192.168.x) are **blocked** from published-game egress.
- **No officially supported offline-auth mechanism.** New clients cannot join without internet. Server rental/matchmaking stops. HttpService stops. Open Cloud APIs stop.
- Community workarounds (RFD, studio-offline) are ToS-gray and unsupported.
- **A trawler without reliable satellite internet cannot run a live Roblox experience.**

**Blocker 3: Physics are not vessel-grade.**
- Custom in-house physics engine (NOT PhysX/Havok). 240Hz internal step, 60Hz Lua callbacks.
- **No fluid dynamics solver. No wave forcing. No hydrodynamic drag primitive.** "Terrain Water" is a voxel approximation.
- Realistic buoyancy is hand-rolled in Luau via `VectorForce`/`LinearVelocity`. Community consensus: vessel-scale is "rocket science" and ships "bop uncontrollably" without hacks (e.g., make ship massless except for one large low-density box).
- `RopeConstraint`/`SpringConstraint` exist but are game-grade, not engineering-certified.
- **You'd end up maintaining a parallel "physics truth" in a real solver and teleoperating Roblox parts to match — at which point you don't need Roblox's physics.**

### 3.3 Secondary Roblox weaknesses

- **Attributes for 50Hz telemetry = BAD IDEA.** Community horror story: 40 MB/s server data surge from attribute replication. Attributes are for low-frequency config, not telemetry. Use batched `RemoteEvent`s with binary-packed payloads instead.
- **RemoteEvent effective ceiling:** ~500/sec per client, ~50 KB/sec de facto bandwidth cap, replication at ~20 Hz. 50Hz with small payloads is doable for one captain's iPad; not for multi-client rich data.
- **LLM agents in-experience:** No native function-calling/tools API. Assistant and Code Assist are Studio-only. The only viable pattern is external LLM → Open Cloud Luau Execution (multi-second latency per turn).
- **glTF export:** Beta, no animations, 20K triangle limit per mesh. Luau scripts are a rewrite, not a port, to any other engine. **Roblox is write-mostly.**
- **ToS gray area:** No SLA, no fitness-for-purpose warranty, no enterprise SKU, no kiosk/MDM mode. Fine for research; risky for production vessel OS.

### 3.4 Roblox verdict

**Roblox is great for:**
- Rapid 3D visualization of vessel interior/exterior
- Cross-platform BYOD access (captain's iPad, son's phone)
- Spatial audio UX
- Agent spatial queries
- Multi-user shared scenes
- Education, training, onboarding
- The "game-mode" where the son plays

**Roblox is wrong for:**
- HIL core at 50Hz+
- Air-gapped/LAN-only deployment
- Real-time in-experience LLM agents
- Vessel-scale hydrodynamics
- Engineering certification
- Long-term vendor independence

---

## Part 4 — The Sensor-Fusion "Best-Current-Render" Vision

The user's custom research-goal answer describes the most distinctive part of AELMA:

> *"flying a drone and the drone's ground truth helps render a game state that's as close as it can be to the real world and dynamically gets better as more sounder information comes in or radar or unmanned vessel with its own sonar or underwater cameras and bathy etc. then the system can attempt to render better and better and get feedback from the user to try something else or that, for example, a rendering of coral or dogfish is good. by being roblox, the graphic quality has a charming feel instead of needing to be cutting edge hyper-real."*

This is the **most genuinely novel** part of the vision. Here's what the research found:

### 4.1 The data sources that feed progressive world refinement

**Bathymetry layers (low → high resolution):**
| Source | Resolution | Coverage | Cost |
|---|---|---|---|
| GEBCO 2024 | ~450m globally | Global ocean | Free |
| NOAA BlueTopo / BAG | Variable, cm to meters | US EEZ | Free |
| Cesium World Bathymetry (Jan 2024) | Varies | Global | Free (Cesium ion tier) |
| NMEA 2000 PGN 128267 (Depth) | Vessel-track point cloud | Where you've been | Sensor cost |
| Navionics SonarChart Live | 1ft contours | Community-sourced | Subscription |
| Drone bathymetry (DJI M300 + YellowScan Navigator) | cm | Shallow water | Hardware cost |

**Above-water:**
- Drone photogrammetry → mesh + texture (standard pipeline)
- NeRF / 3D Gaussian Splatting (3DGS) → real-time renderable scene reconstruction
- For vessels: **WaterSplatting, UW-GS, Aqua-Splat, Z-Splat** (2024-2025) handle underwater light refraction

**Progressive reconstruction techniques:**
- **OctoMap / Voxblox / NVBlox** — TSDF (truncated signed distance field) volumetric reconstruction, gets denser as more soundings arrive
- **Underwater SLAM** (SVIn2, ORB-SLAM3) for ROV/sonar trajectory + map

### 4.2 AI stylization (the "charming aesthetic")

- **2D:** GauGAN (NVIDIA), stable-diffusion ControlNet for texture style transfer
- **3D:** DreamFusion, Magic3D, Shap-E (text-to-3D mesh); Roblox Procedural Models (Beta) for in-engine generation
- **Stylization cache:** Pre-compute "Roblox-style" versions of identified species (coral, dogfish, kelp forest). Catalog grows over seasons.

### 4.3 The human-feedback loop (genuinely novel)

This is where AELMA breaks new ground. The captain sees the render and gives feedback:

```
Sensor data ──▶ Initial 3D reconstruction ──▶ Captain feedback
   ▲                                              │
   │                                              ▼
   └──── Updated sensor fusion ◀── Stylization refinement
```

**No prior art exists for RLHF applied to visual rendering of marine sensor data.** The closest analog is:
- Text-to-image RLHF (InstructGPT, DALL-E 3): captain feedback refines a 2D image
- Tesla's Autopilot shadow mode: compares AI prediction to driver action — but for control, not rendering

AELMA's twist is novel because:
1. The feedback targets **3D scene composition** (not just a 2D image)
2. The scene is **sensor-grounded** (sonar says there IS something there)
3. The stylization is **taxonomically meaningful** ("coral right, dogfish wrong" trains the species classifier)
4. The charming aesthetic **lowers the bar for "good enough"** — Roblox's blocky style means less rendering pressure than photoreal

### 4.4 Marine life and environmental data

- **Fish behavior models:** Atlantis/EwE (scientific ecosystem models), Boids for schooling
- **Fish detection:** DIDSON/ARIS imaging sonar + FishNet CNNs for species ID
- **Environmental ingestion:** NOAA NDBC (buoys), NOMADS (forecast), Open-Meteo (API), CO-OPS (tides), Sentinel-3 / MODIS (ocean color, chlorophyll, SST)

### 4.5 Replay systems (the "watch dad catch the halibut" feature)

- **MCAP / ROS bag** — the industry standard for recording + replaying sensor streams with timing
- **Foxglove Studio** — visualize/playback MCAP recordings
- **Relive.cc / Strava Flyby** — consumer-grade activity replay (the UX template AELMA should copy)

---

## Part 5 — Game-Engine Alternatives & The Hybrid Recommendation

### 5.1 Engine verdict matrix

| Engine | License | Headless | Air-gapped | Physics | ROS bridge | Agentic (RL) | AELMA best fit |
|---|---|---|---|---|---|---|---|
| **Roblox** | Proprietary | Cloud-only | No | Weak (no fluid) | None | Studio-only | UX/training/game-mode |
| **Unity 6** | Seat-based | Strong | Yes | PhysX/Havok | [ROS-TCP-Connector](https://github.com/Unity-Technologies/ROS-TCP-Connector) | [ML-Agents](https://github.com/unity-technologies/ml-agents) (mature) | Best "serious" alternative |
| **Unreal 5** | Royalty (5% >$1M) | Strong | Yes | Chaos (strong) | [ROSIntegration](https://github.com/code-iai/ROSIntegration) | Weak (third-party) | Best visual fidelity; Pixel Streaming |
| **Godot 4** | MIT | Trivial (`--headless`) | Yes | Adequate | Community | Immature | Dark-horse for vessel-LAN core |
| **Bevy** | MIT | Native | Yes | [Avian](https://github.com/jondolf/avian) (deterministic) | DIY | Early | Rust-shop, telemetry-first |
| **NVIDIA Isaac Sim** | Proprietary (free) | Container | Yes (local GPU) | PhysX 5 + marine (VRX) | Native (ROS 2) | [Isaac Lab](https://github.com/isaac-sim/IsaacLab) (gold standard) | Divination sandbox |
| **Web (Three.js / Babylon)** | MIT/Apache | Server | Yes | Lightweight | WebSocket | DIY | Zero-install fallback |

### 5.2 The recommended hybrid architecture

**Vessel-side core (air-gapped LAN):**
- **Sensors** → NMEA 2000 bus → **Signal K Server** (Raspberry Pi) → **Headless twin core**
- **Twin core engine:** Godot 4 (MIT, trivially headless, WebSocket multiplayer) or Bevy (Rust, deterministic Avian physics, telemetry-first design)
- **Spatial substrate:** Cesium World Bathymetry + progressive TSDF from NMEA depth + drone/ROV photogrammetry overlays
- **Local clients:** Ruggedized Android tablets running a light native client or browser (WebRTC stream from headless core)

**Shoreside / game-mode layer (when internet is available):**
- **Roblox experience** for: captain's family replay, fleet social features, son's game-mode, training/onboarding, the "charming aesthetic" showcase
- **Optional:** Unity/Unreal for higher-fidelity training scenarios; Web (Three.js/Babylon) for zero-install guest access
- **Sync:** Vessel uploads MCAP recordings when satellite is available; shoreside experience consumes recordings + live stream when connected

**Divination sandbox (predictive what-if):**
- **NVIDIA Isaac Sim + Isaac Lab** for serious RL training of control policies (vessel handling, crane operations)
- **Unity ML-Agents** as a lighter alternative if Isaac Sim's GPU requirements are prohibitive
- **Tesla shadow mode** pattern: run Divination in parallel with live operations, compare predictions to outcomes, log discrepancies

### 5.3 Why this architecture is better than "Roblox for everything"

| Requirement | Roblox-only | Hybrid |
|---|---|---|
| 50Hz HIL telemetry | Blocked (8.3 Hz max) | Native (WebSocket at full rate on LAN) |
| Air-gapped vessel operation | Impossible | Core runs offline indefinitely |
| Vessel-scale physics | Inadequate | Real physics in Godot/Bevy/Isaac Sim |
| Charming aesthetic for family | Excellent | Preserved (Roblox shoreside) |
| Cross-platform BYOD | Excellent | Preserved (browser + Roblox app) |
| Agent spatial reasoning | Solid (spatial queries) | Solid (same APIs in Godot/Unity) |
| Engineering certification path | None | DNV OSP / ABS path via real physics |
| Vendor independence | Write-mostly (glTF escape hatch only) | MIT-licensed core, portable everything |
| Son plays in game-mode | Excellent | Preserved (Roblox experience) |
| Replay as entertainment | Build in Roblox | Build in Roblox from MCAP recordings |

---

## Part 6 — Implementation Path Recommendation

### Phase 0 — Signal K foundation (already documented in this repo)
The existing Phase 0 documentation (`phase0_implementation_plan.md`, `nmea_implementation_guide.md`) is correct: build on Signal K, ingest NMEA 2000, log everything. This is the **non-renewable resource** — start capturing data now.

### Phase 1 — Vessel-side headless twin
- Deploy Godot 4 (`--headless`) or Bevy on a Jetson/Raspberry Pi 5
- Consume Signal K WebSocket stream
- Build the progressive bathymetry layer (Cesium + TSDF from NMEA depth)
- Spatial queries for simple agent reasoning (depth alarm zone, gear proximity)
- Local browser-based viewer (WebRTC stream from headless core)

### Phase 2 — Shoreside Roblox experience
- Consume MCAP recordings uploaded via satellite
- Build the "replay past trips" feature (this is where Roblox shines)
- Spatial audio ("AI voice from the direction of the fault" — native Roblox strength)
- Son's game-mode with charming stylization

### Phase 3 — Human-feedback stylization loop
- Captain tags species in the render ("coral right", "dogfish wrong")
- Stylization cache grows season over season
- This is the **publishable academic contribution** — RLHF for sensor-grounded 3D marine scene composition

### Phase 4 — Divination sandbox
- Parallel Isaac Sim or Unity ML-Agents instance
- "What if we changed the longline set location?" → run 1000 simulated soaks
- Predictions compared to actual outcomes (Tesla shadow mode pattern)

### Phase 5 — Agent actuation (long road)
- Advisory-only first (read + recommend)
- Phased regulatory engagement: USCG Policy Letter 22-01 framework for supervised testing
- Progress to supervised control only after ABS Guide 323 / DNV AROS review

---

## Part 7 — Academic Paper Structure (if pursuing publication)

Based on the prior-art survey, structure the related-work section as:

1. **Marine Digital Twins** — DNV OSP, Kognitwin, Eniram, OCTOPUS, reviews (Hu 2025, Li 2025, Lee 2022)
2. **Game Engines in Maritime Simulation** — MARUS (Loncar 2022), Kong (2024), Li (2024) UE5, Leite (2023), Ervin (2023) VR physics
3. **Hardware-in-the-Loop for Marine Systems** — Lee et al. (2024), Liu et al. (2024), DNV OSP DP-Ship demo
4. **Marine Data Standards and Gateways** — Signal K, canboat, NMEA 2000 standard
5. **Embodied AI and Spatial Reasoning** — AI Habitat 3.0, Embodied AI Agents (arXiv 2025), Weistroffer (2022)
6. **Fishing-Vessel Technology** — Pelagic Data Systems, Naoned project, NOAA VMS/EM, GreenFish
7. **Progressive 3D Reconstruction** — OctoMap, Voxblox, 3D Gaussian Splatting, underwater SLAM
8. **Regulatory Landscape** — IMO MASS, USCG PL 22-01, ABS Guide 323, DNV AROS, DNV-RP-A204

**The novelty thesis:** AELMA is the first system to combine game-engine-based live operation, spatial AI reasoning, consumer-client crew interaction, progressive sensor-fused world refinement with human-feedback stylization, and predictive what-if simulation — applied to commercial fishing.

The five genuinely novel contributions (Section 1.2 above) are the defensible claims. Everything else is well-trodden ground that should be cited, not claimed.

---

## Appendix — Companion Research Documents

The following companion documents contain the full detail behind this synthesis:

1. **`aelma_literature_survey.md`** (703 lines, HIL + game-engine survey)
   - Full engine-by-engine analysis (Unity, Unreal, Godot, Bevy, Omniverse, Three.js, O3DE, Cesium)
   - ROS 2 + Gazebo baseline
   - Game-engine-as-OS prior art (VBS4, LambdaMOO, metaverse lessons)
   - Agentic/LLM agents in game engines (Generative Agents, Voyager, NVIDIA ACE)
   - Predictive physics (Tesla shadow mode, Isaac Lab, ML-Agents)
   - Engine verdict matrix

2. **Marine prior-art research** (returned as task output, embedded in this memo)
   - Industry vendors: Kongsberg, DNV, ABB, Wärtsilä, Siemens, Rolls-Royce
   - 30+ academic papers cataloged
   - Signal K, NMEA 2000, hardware gateways
   - Regulatory landscape (IMO, USCG, ABS, DNV, ClassNK, BV, LR)

3. **Roblox technical reality check** (returned as task output, embedded in this memo)
   - 15 claims verified against current Roblox docs and DevForum
   - 3 blocking risks identified and documented
   - Spatial queries, audio, Luau performance, cross-platform — all assessed
   - Asset portability and ToS analysis

4. **Sensor-fusion research** (returned as task output, embedded in this memo)
   - Bathymetric data sources (GEBCO, BlueTopo, BAG, SonarChart Live)
   - Drone-based photogrammetry and bathymetry hardware
   - Progressive 3D reconstruction (OctoMap, Voxblox, 3DGS, SLAM)
   - AI-assisted scene stylization
   - Marine-life modeling and environmental data ingestion
   - 5 novel contributions identified

---

## Sources (Selected)

### Marine industry
- [DNV Open Simulation Platform](https://www.dnv.com/expert-story/maritime-impact/Open-Simulation-Platform-the-next-generation-of-digital-twins/)
- [DNV AROS Class Notations (2025)](https://www.dnv.com/maritime/autonomous-remotely-operated-ships/aros-class-notation/)
- [ABB OCTOPUS Marine Advisory System](https://new.abb.com/marine/systems-and-solutions/digital/ABB-Ability-OCTOPUS-Marine-Advisory-System)
- [Wärtsilä Eniram Fleet Optimization](https://www.wartsila.com/marine/products/eniram-by-wartsila-fleet-optimisation-solution)
- [Kongsberg K-Sim Navigation (MarineLink)](https://www.marinelink.com/news/navigation-kongsberg380493)
- [Signal K — open marine data platform](https://signalk.org/)
- [Naoned Digital Twin Project (National Fisherman)](https://www.nationalfisherman.com/revolutionize-fishing-with-naoned-digital-twin-project)
- [Pelagic Data Systems](https://www.pelagicdata.com/)
- [GreenFish AI Fish Forecasting](https://www.globalseafood.org/advocate/here-to-stay-and-evolving-fast-how-greenfishs-ai-powered-fish-forecasting-tech-is-modernizing-commercial-fisheries/)

### Regulatory
- [USCG Policy Letter 22-01 (Change 1, April 2024)](https://www.dco.uscg.mil/Portals/9/DCO%20Documents/5p/CG-5PC/CG-CVC/Policy%20Letters/2022/Testing%20of%20remote%20and%20autonomous%20systems%2022-01%20%28CH1%29.pdf)
- [ABS Requirements for Autonomous and Remote Control Functions 2024](https://ww2.eagle.org/content/dam/eagle/rules-and-guides/current/other/323-requirements-for-autonomous-and-remote-control-functions-2024/323-autonomous-reqts-oct24.pdf)
- [IMO MASS regulatory scoping](https://www.imo.org/en/mediacentre/hottopics/pages/autonomous-shipping.aspx)

### Academic (game engines in maritime)
- [MARUS — Marine Robotics Simulator (Unity, cited 60×)](https://www.researchgate.net/publication/366430822_MARUS_-_A_Marine_Robotics_Simulator)
- [Kong et al. 2024 — Ship Navigation Simulator in Unity](https://www.sciencedirect.com/science/article/pii/S2092678224000232)
- [Li et al. 2024 — Maritime Simulation with UE5](https://www.mdpi.com/2077-1312/12/9/1587)
- [Lee et al. 2024 — HILS for Marine Systems](https://www.mdpi.com/2077-1312/12/7/1236)

### Roblox technical
- [HttpService — Roblox Creator Hub](https://create.roblox.com/docs/reference/engine/classes/HttpService)
- [In-game HTTP requests — rate limits](https://create.roblox.com/docs/cloud-services/http-service)
- [WebSockets Support in Studio (DevForum, Oct 2025)](https://devforum.roblox.com/t/websockets-support-in-studio-is-now-available/4021932)
- [Scaling a Physics Engine to Millions of Players (GameDeveloper)](https://www.gamedeveloper.com/programming/scaling-a-physics-engine-to-millions-of-players)
- [How we make Luau fast](https://luau.org/performance/)
- [glTF Export Beta (DevForum)](https://devforum.roblox.com/t/gltf-export-beta-available-now/3905928)
- [Roblox Q3 2025: 151M DAU (GamesBeat)](https://gamesbeat.com/roblox-had-151m-daily-active-users-in-q3-2025/)

### Game engines (alternatives)
- [Unity Industrial](https://unity.com/products/unity-industry)
- [Unity ML-Agents](https://github.com/unity-technologies/ml-agents)
- [Unity ROS-TCP-Connector](https://github.com/Unity-Technologies/ROS-TCP-Connector)
- [Godot dedicated server export](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_dedicated_servers.html)
- [Bevy (Rust game engine)](https://bevy.org/)
- [NVIDIA Isaac Sim](https://developer.nvidia.com/isaac-sim)
- [NVIDIA Isaac Lab](https://github.com/isaac-sim/IsaacLab)

### Sensor fusion & reconstruction
- [GEBCO Bathymetric Grid](https://www.gebco.net/)
- [Cesium World Bathymetry](https://cesium.com/blog/2024/01/30/world-bathymetry/)
- [NOAA BlueTopo](https://www.nauticalcharts.noaa.gov/data/bluetopo.html)
- [Navionics SonarChart Live](https://www.navionics.com/usa/articles/sonarchart-live)
- [CSS Electronics — NMEA 2000 tutorial (PGN 128267)](https://www.csselectronics.com/pages/nmea-2000-n2k-intro-tutorial)
- [canboat (open-source NMEA 2000)](https://github.com/canboat/canboat)
