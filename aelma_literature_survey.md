# AELMA Literature & Prior-Art Survey
## Game-Engine-as-HIL-Digital-Twin for a Commercial Fishing Vessel

**Compiled:** 2026-07-26
**Purpose:** Prior-art survey for a research paper on **AELMA (Agent-Engine Linked Marine Architecture)** — using a real-time game engine (Roblox/Luau primary, alternatives considered) as the core of a hardware-in-the-loop (HIL) digital twin for a commercial fishing vessel.

This document is organized into six sections: (1) game-engine survey for HIL twins, (2) ROS 2 + Gazebo baseline, (3) game-engine-as-OS prior art, (4) agentic/LLM agents in game engines, (5) predictive "what-if" / Divination prior art, and (6) key risks and open questions. A concluding "Engine Verdict" matrix summarizes where each engine is genuinely strong vs. weak for AELMA's use case.

---

## Table of Contents

1. [Game Engines for HIL Simulation & Digital Twins — Survey](#1-game-engines-for-hil-simulation--digital-twins--survey)
2. [ROS 2 + Gazebo: The "Serious" Baseline](#2-ros-2--gazebo-the-serious-baseline)
3. [Game-Engine-as-OS Prior Art](#3-game-engine-as-os-prior-art)
4. [Agentic / LLM-Driven Agents in Game Engines](#4-agentic--llm-driven-agents-in-game-engines)
5. [Predictive / "What-If" Physics in Game Engines (The "Divination" Sandbox)](#5-predictive--what-if-physics-in-game-engines-the-divination-sandbox)
6. [Key Risks & Open Questions](#6-key-risks--open-questions)
7. [Engine Verdict Matrix & Recommendation](#7-engine-verdict-matrix--recommendation)

---

## 1. Game Engines for HIL Simulation & Digital Twins — Survey

This section surveys the realistic candidate engines one might pick instead of (or alongside) Roblox for the AELMA architecture. For each: license, headless feasibility, networking model, scripting language, agentic ecosystem maturity, and recommended use case.

### 1.1 Unity

**License:** Tiered — "Personal" (free, <$200K revenue), "Pro" ($2,200/seat/yr), "Enterprise" ($4,950/seat/yr). Runtime is royalty-free. The controversial 2023 "Runtime Fee" proposal was [walked back](https://unity.com/) after community revolt; current model is seat-based. [Unity Industrial](https://unity.com/products/unity-industry) is a separate, more expensive SKU aimed at non-game enterprise.

**Headless server feasibility:** Strong. Unity supports dedicated server builds (`--headless` / batchmode) and a [Linux dedicated server export target](https://docs.unity3d.com/Manual/dedicated-server.html). Multiple cloud providers (AWS, Azure, Unity Gaming Services/Game Server Hosting) run Unity headless at scale. Realvirtual.io and similar industrial platforms run Unity headless for [virtual commissioning](https://realvirtual.io/en/).

**Networking model:** Mature ecosystem. Options include:
- **Unity Transport Protocol (UTP)** — low-level UDP/TCP, used by Netcode for GameObjects / Entities.
- **Netcode for GameObjects (NGO)** — official high-level multiplayer.
- **Mirror / Fish-Networking / Photon / Unity Relay** — third-party and hosted options.
- **WebSocket** — available via .NET `ClientWebSocket`.
- ROS integration via [ROS-TCP-Connector](https://github.com/Unity-Technologies/ROS-TCP-Connector) (Unity Robotics).

**Scripting language:** C# (via .NET / Mono / CoreCLR-as-of-Unity-6). Mature, strongly typed, with a vast ecosystem.

**Digital-twin story:** Strong. [Unity Industrial](https://unity.com/products/unity-industry) explicitly targets advanced visualization, simulation, AR/VR, and interactive industrial applications. Siemens has a longstanding partnership — the **Siemens Xcelerator** platform's [comprehensive Digital Twin](https://www.siemens.com/en-us/campaigns/digital-twin/) integrates Unity-based visualization at the presentation layer, while Simcenter handles physics. Unity is used for [non-game runtime applications](https://www.reddit.com/r/Unity3D/comments/1epd7ll/anyone_here_use_unity_not_for_games/) including architectural viz, AEC (architecture, engineering, construction), virtual commissioning ([realvirtual.io](https://realvirtual.io/en/), 25+ PLC interfaces), and industrial training.

**HIL story:** Solid. [Unity Robotics](https://github.com/Unity-Technologies/ROS-TCP-Connector) includes ROS-TCP-Connector and URDF import. Academic work: [Wang et al., "Digital Twin Simulation of Connected and Automated Vehicles with the Unity Game Engine"](https://www.researchgate.net/publication/354771791_Digital_Twin_Simulation_of_Connected_and_Automated_Vehicles_with_the_Unity_Game_Engine) (IEEE). The [Unity non-game showcase](https://discussions.unity.com/t/non-game-unity3d-showcase/464734) includes CVNF ship-familiarization training. Notably, JLR's "Journey to Unity" appears to refer to an internal unification initiative rather than the Unity engine itself; JLR's actual digital twin work uses [NVIDIA Omniverse](https://www.jlr.com/innovation) (NVIDIA DRIVE platform) and [MathWorks/Simulink](https://www.mathworks.com/content/dam/mathworks/mathworks-dot-com/solutions/automotive/files/uk-expo-2012/simulating-highly-complex-systems-to-deliver-next-gen-jaguar-land-rover-vehicles.pdf), with [HIL rigs running on NI/Elastic Stack](https://www.elastic.co/customers/jaguar-land-rover).

**Agentic ecosystem:** [Unity ML-Agents](https://github.com/unity-technologies/ml-agents) is the most mature game-integrated RL toolkit (PPO, SAC, curriculum learning, multi-agent). Production-trained agents shipped in *Obstacle Tower*, *Hungry Birds*, and ML-Agents is widely used in academia for RL benchmark environments. Supports [training on Amazon SageMaker RL](https://aws.amazon.com/blogs/machine-learning/training-a-reinforcement-learning-agent-with-unity-and-amazon-sagemaker-rl/).

**Learning curve:** Moderate. C# is widely known, Unity Editor has a gentle on-ramp, and the asset store is enormous. However, the industrial tooling has real learning cost.

**Recommended AELMA use case:** Strongest "serious" alternative if Roblox is rejected. Native headless server, mature ROS bridge, ML-Agents for the "Divination" sandbox, and a real industrial ecosystem via Unity Industrial.

### 1.2 Unreal Engine

**License:** Free to download; Epic takes 5% royalty only after $1M revenue (waived for revenue on the Epic Games Store). Source available via [Unreal Engine EULA](https://www.unrealengine.com/en-US/eula) — *not* OSI-approved open source. U.S. export restrictions apply.

**Headless server feasibility:** Strong. Unreal ships a dedicated server build target. Widely deployed at scale (Fortnite, etc.).

**Networking model:** Mature.
- **Replication system** — built-in server-authoritative netcode.
- **Network Prediction / Iris (UE 5.4+)** — Epic's next-gen rollback prediction.
- **TCP/UDP/QUIC** — all supported at the C++ / socket layer.
- **Pixel Streaming** — render server-side, stream to web/mobile (very relevant for AELMA's "any screen" thesis).
- ROS bridge via [ROSIntegration](https://github.com/code-iai/ROSIntegration) (TCP + WebSocket to rosbridge; ROS1 + ROS2).

**Scripting language:** Blueprints (visual) and C++. Verse (Epic's new functional language, Ulf Tossell Jr.) is early/experimental.

**Digital-twin story:** Strong and actively investing. [Unreal Fest 2024 "Practical Digital Twins"](https://www.youtube.com/watch?v=nZVJFjWH7N4) session by WWT and Another Reality Studio. **NVIDIA Omniverse–Unreal connector** enables co-simulation — the ["SpaceVerse" GTC demo](https://dev.epicgames.com/community/learning/tutorials/e9EJ/unreal-engine-co-simulation-ue-and-omniverse-spaceverse-gtc-demo-return-on-experience) showed a rocket-launch digital twin with UE rendering and Omniverse physics co-simulating.

**HIL story:** [UE5 + ROS2 integration](https://www.youtube.com/watch?v=Ar0Ns4gVKME) is well-trodden. UE excels at photorealism (Lumen, Nanite) and VFX (Niagara, including [Niagara fluid sim](https://dev.epicgames.com/community/learning/tutorials/e9EJ/unreal-engine-co-simulation-ue-and-omniverse-spaceverse-gtc-demo-return-on-experience) — relevant to water/fire/smoke on a vessel).

**Agentic ecosystem:** Weaker than Unity for *in-engine* RL. ML-Agent equivalents exist (e.g., [Hololinks DeepRL](https://github.com/code-iai/ROSIntegration), various academic plugins) but no first-party ML-Agents equivalent. The Unreal + Inworld/Convai/NVIDIA ACE pipeline is strong for NPC dialog but not for control policies.

**Recommended AELMA use case:** Best choice if visual fidelity for crew training / ship familiarization / "kid plays the world" matters more than RL training loops. Pixel Streaming is a unique advantage — render the vessel twin server-side and stream to any browser/tablet on the LAN.

### 1.3 Godot

**License:** [MIT](https://godotengine.org/license). Completely free, no royalties, no restrictions. The most permissive license in this survey.

**Headless server feasibility:** [First-class since 4.0](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_dedicated_servers.html). Any Godot binary accepts `--headless`; a dedicated-server export preset strips rendering/audio. No separate "server" build to maintain.

**Networking model:** Clean, transport-agnostic.
- **High-level multiplayer API** (`MultiplayerAPI`) — RPC, scene replication, separation of concerns.
- **`ENetMultiplayerPeer`** — UDP, native, best for desktop/embedded.
- **`WebSocketMultiplayerPeer`** — TCP, ideal for HTML5 / browser clients.
- **`WebRTCMultiplayerPeer`** — peer-to-peer with NAT traversal.
- See the [official multiplayer docs](https://docs.godotengine.org/en/stable/tutorials/networking/high_level_multiplayer.html) and [Godot 4.0 multiplayer changes](https://godotengine.org/article/multiplayer-changes-godot-4-0-report-3/).
- **GDScript** — high-level, Python-like, beginner-friendly.

**Digital-twin story:** Emerging. Godot 4 is increasingly used for [non-game industrial applications](https://forum.godotengine.org/t/using-headless-godot-as-a-server-game-instance-for-a-multiplayer-setup/37142), but lacks dedicated industrial partners (no Siemens/Mitsubishi/NVIDIA-tier relationships). The rendering pipeline is competitive (Vulkan, clustered forward, deferred renderer) but not at Unreal/Unity photorealism.

**HIL story:** DIY. No first-party ROS bridge; community projects exist (e.g., [godot_ros](https://github.com/vincentroumier/godot_ros)). The clean headless story and MIT license are extremely attractive for air-gapped/vessel-embedded use.

**Agentic ecosystem:** Immature. No first-party ML-Agents equivalent. Some third-party RL plugins exist.

**Recommended AELMA use case:** The dark-horse strategic pick. MIT license + trivially headless + transport-agnostic multiplayer = the cleanest path to a vessel-LAN-deployable, no-phone-home twin. The tradeoff is ecosystem maturity — you'll build more plumbing yourself.

### 1.4 Bevy

**License:** [MIT](https://bevy.org/) — free and open source forever.

**Headless server feasibility:** Excellent. Bevy is Rust-native; you can `cargo build` a binary with `--no-default-features` for a pure-logic, no-render server. WASM compilation is first-class.

**Networking model:** Bring-your-own. Bevy doesn't ship a built-in multiplayer stack, but `bevy_renet` (Renet), `bevy_replicon`, and `lightyear` are popular. UDP, WebSocket, and WebTransport are all achievable.

**Scripting language:** Rust. No visual scripting, no Lua. Strong type system, fearless concurrency, memory safety.

**Digital-twin story:** Early but interesting. [Avian physics](https://www.reddit.com/r/rust/comments/1o5hsbi/avian_04_ecsdriven_physics_for_bevy/) v0.5 ships an `enhanced-determinism` feature using `libm` for cross-platform reproducible physics — directly relevant to AELMA's "Divination" sandbox. The [Bevy determinism audit](https://github.com/bevyengine/bevy/discussions/2480) is an active, ongoing conversation.

**HIL story:** DIY. No ROS bridge out of the box. But the Rust ecosystem has [ros2_rust](https://github.com/ros2-rust/ros2_rust) (ROS 2 client library), and Bevy's ECS maps cleanly to agent-per-entity models.

**Agentic ecosystem:** Immature as a *game engine*, but Rust's agent/ML story ( Candle, Burn, ort) is strong if you're willing to wire it up yourself.

**Recommended AELMA use case:** The "Rust maximalist" pick. Compelling if AELMA's vessel-side runtime should be deterministic, memory-safe, WASM-compilable, and MIT-licensed. Not recommended if you need a polished editor or a kid-friendly scripting surface.

### 1.5 NVIDIA Omniverse / Isaac Sim

**License:** [Omniverse](https://www.nvidia.com/en-us/omniverse/) is free for individual creators; enterprise licensing applies for commercial-scale deployment. [Isaac Sim](https://developer.nvidia.com/isaac/sim) is free for non-commercial use; commercial requires NVIDIA enterprise licenses. **Not open source** — proprietary NVIDIA binaries.

**Hardware requirements:** Heavy. Isaac Sim realistically requires an RTX GPU (3090/4090 class for serious work). The "physical AI" thesis assumes a CUDA-grade GPU on the host. On a vessel, this means a workstation-class PC — non-trivial.

**Headless server feasibility:** Possible (Omniverse supports headless via Kit SDK), but heavy. Cloud streaming is the assumed deployment model.

**Networking model:** Omniverse uses **Nucleus** (collaboration server) and USD as the data fabric. RTC (real-time collaboration) is built-in. Isaac Sim speaks DDS/ROS 2 natively.

**Scripting:** Python (Kit, Isaac Sim), C++ (low-level). [OpenUSD](https://github.com/nvidia) is the scene-description layer.

**Digital-twin story:** The gold standard for *physical AI*. NVIDIA's [Omniverse Blueprint for Digital Twins](https://www.digitalengineering247.com/article/nvidia-launches-omniverse-blueprint-for-building-digital-twin) (SC24 announcement) and the [Isaac Sim arXiv paper](https://arxiv.org/pdf/2606.03551) document the architecture: GPU-accelerated PhysX 5 + RTX rendering + OpenUSD. [Simio × Omniverse](https://www.simio.com/nvidia-omniverse-digital-twin-integration/) integrates discrete-event simulation.

**HIL story:** Native. Isaac Sim + Isaac Lab is *the* serious robotics RL training pipeline. Supports [multiple RL frameworks](https://isaac-sim.github.io/IsaacLab/main/source/overview/reinforcement-learning/index.html) (RSL-RL, SKRL, Stable Baselines3, RL Games) and [massively parallel training](https://docs.nvidia.com/learning/physical-ai/getting-started-with-isaac-lab/latest/train-your-first-robot-with-isaac-lab/02-how-isaac-lab-accelerates-reinforcement-learning.html). In 2024-2025, NVIDIA released [open-source agent skills](https://www.barchart.com/story/news/2226951/nvidia-releases-major-collection-of-open-source-agent-tools-and-skills-for-physical-ai) that let LLM agents launch sim sessions, author scenes, capture data, and validate environments — the closest thing to AELMA's vision that already exists.

**Agentic ecosystem:** The most mature. NVIDIA's [CVPR 2024 "Agent Skills"](https://blogs.nvidia.com/blog/cvpr-physical-ai-research-agent-skills/) announcement and the [Hugging Face "State of Simulation for Physical AI"](https://huggingface.co/blog/nvidia/state-of-simulation-for-physical-ai) blog describe exactly the loop AELMA proposes — agents spawning sim sessions to test hypotheses.

**Recommended AELMA use case:** The "right answer" if cost, hardware, and complexity were no object. Probably *overkill* for a fishing vessel unless you're serious about RL-trained autopilot policies. Best as a co-simulation partner to a lighter-weight engine (UE or Unity renders, Omniverse provides physics ground-truth).

### 1.6 Three.js / Babylon.js (Web-Native)

**License:** Both MIT. Three.js is a renderer; [Babylon.js 9.0](https://www.babylonjs.com/) is a fuller game-engine-in-browser.

**Headless server feasibility:** N/A — these are browser renderers. The "server" is whatever you serve them from (Node.js, Rust, Python). Headless logic runs server-side; rendering is purely client.

**Networking:** WebSocket, WebRTC, fetch — all native to the browser.

**Scripting:** JavaScript / TypeScript.

**Digital-twin story:** Lightweight, instantly distributable. WebGPU support is broadening (Chrome, Edge, Firefox, Safari/iOS as of 2025), with [automatic fallback to WebGL2](https://www.utsubo.com/blog/threejs-2026-what-changed). Babylon.js ships [full WebGPU support](https://babylonjs.medium.com/babylon-js-5-0-beyond-the-stars-2d11d4c3d07) including compute shaders. The [ACM WebGPU paper](https://dl.acm.org/doi/10.1145/3746237.3746305) explicitly notes web-native engines for real-time industrial applications.

**Recommended AELMA use case:** Best "thin client" rendering layer for crew/child phones and tablets. Pair with a headless Godot/Unity/Rust backend.

### 1.7 Open 3D Engine (O3DE)

**License:** [Apache 2.0](https://aws.amazon.com/blogs/gametech/aws-for-games-latest-contribution-to-the-open-3d-engine-o3de/) — the most permissive license of any full-featured engine in this survey, contributed by AWS (evolved from Lumberyard).

**Headless server feasibility:** Supported. AWS positions O3DE for [digital twins, automotive, healthcare, and simulations](https://aws.amazon.com/blogs/gametech/aws-for-games-latest-contribution-to-the-open-3d-engine-o3de/) — explicitly non-game use cases.

**Networking:** Modular "Gems" system includes networking components. No first-party ROS bridge (but ROS 2 Conversions Gem exists in the ecosystem).

**Scripting:** Lua and Script Canvas (visual). C++ for systems.

**Digital-twin story:** [O3DE 24.09](https://tfir.io/open-3d-engines-o3de-24-09-release-boosts-capabilities-and-ease-of-use/) (2024 release) continues active development. [ROSCon 2023 talk](https://roscon.ros.org/2023/talks/Simulate_robots_like_never_before_with_Open_3D_Engine.pdf) pitched O3DE for robotics simulation, emphasizing perception/scenario strengths.

**Agentic ecosystem:** Immature.

**Recommended AELMA use case:** Viable Apache-2.0 alternative if Godot feels too lightweight but Unity/Unreal licensing is unacceptable. Smaller community than Godot, however.

### 1.8 CesiumJS / Cesium for Unreal/Unity (Geospatial Layer)

**License:** [Apache 2.0](https://cesium.com/platform/cesium-for-unreal/) for the engine integrations; Cesium ion (cloud tiling service) has a freemium tier.

**Why this matters for AELMA:** [Cesium World Bathymetry](https://cesium.com/blog/2024/01/23/introducing-cesium-world-bathymetry/) (launched January 2024) is a global bathymetry + topographic terrain tileset explicitly designed for "[3D visualizations, simulations, and analytics](https://cesium.com/platform/cesium-ion/content/cesium-world-bathymetry/)" including "**navigation by unmanned vessels**" and oil/gas exploration. This is the closest off-the-shelf data source for a real-world coastline/sea-floor twin.

**Integrations:**
- [Cesium for Unreal](https://github.com/CesiumGS/cesium-unreal) — WGS84 globe, 3D Tiles, photorealistic tiles from Google Maps Platform.
- [Cesium for Unity](https://unity.com/blog/cesium-for-unity-3d-geospatial-web) — Unity-integrated.
- [CesiumJS](https://cesium.com/platform/cesiumjs/) — pure web (WebGL/WebGPU), pairs with Three.js/Babylon.js.

[Cesium's underground/undersea use case page](https://cesium.com/use-cases/underground-undersea/) explicitly calls out coastal and ocean visualization. Community [has asked for Unity bathymetry samples](https://community.cesium.com/t/bathymetry-in-unity/29729).

**Recommended AELMA use case:** Strongly recommended as the **geospatial substrate** regardless of which engine AELMA picks. Bathymetry + coastline + port infrastructure is the spatial backbone of the vessel twin.

---

## 2. ROS 2 + Gazebo: The "Serious" Baseline

What does the robotics world *actually* use for HIL? This is the baseline AELMA must justify departing from.

### 2.1 ROS 2 Distributions

Active LTS-relevant distributions as of mid-2026:
- **Humble Hawksbill** (May 2022 – May 2027) — paired with **Gazebo Garden/Harmonic**, Ubuntu 22.04. The workhorse for most production deployments.
- **Iron Irwini** (May 2023 – Nov 2024) — EOL.
- **Jazzy Jalisco** (May 2024 – May 2029) — current LTS, paired with **Gazebo Harmonic**, Ubuntu 24.04. The new "stable target."
- **Rolling Ridley** — continuous bleeding edge.

The [Humble → Jazzy migration](https://robotics.stackexchange.com/questions/114470/seeking-guidance-on-migrating-a-ros2-humble-project-to-jazzy-with-gazebo-harmoni) is actively underway in the community.

### 2.2 Client libraries

- **rclcpp** — C++, the production-grade client. Most ROS 2 code is here.
- **rclpy** — Python, dominant for prototyping, scripting, and tooling.
- **[rcllua](https://github.com/jbbjarnason/rcllua)** — Lua bindings *do exist* (jbbjarnason/rcllua), built on the C core `rcl`. This is the critical fact for AELMA: **Luau is not Lua**, but rcllua demonstrates that a Lua-family client library for ROS 2 is achievable. A Luau binding is a fork-and-port project, not a from-scratch effort. There was also [roslua](http://wiki.ros.org/roslua) for ROS 1.
- Other bindings: rclada (Ada), rcljava, [rclrust](https://github.com/ros2-rust/ros2_rust), etc.

### 2.3 Gazebo

The simulator formerly known as Ignition:
- **Gazebo Garden** (2023) — paired with Humble/Iron.
- **Gazebo Harmonic** (2024) — paired with Jazzy/Rolling. LTS.
- **Gazebo Ionic** (late 2024) — bleeding edge.

Gazebo provides physically-accurate rigid-body dynamics (ODE/Bullet/DART/PhysX plugin), sensors (camera, LiDAR, IMU, GPS, contact, depth), and is ROS 2-native. See [ROS 2 + Gazebo Harmonic robot simulation tutorial](https://www.youtube.com/watch?v=b8VwSsbZYn0).

### 2.4 Micro-ROS for ESP32 — *the critical real path*

This is the bridge that makes AELMA's "ESP32 sensor → game engine" architecture plausible without inventing new middleware:

- [micro-ROS](https://micro.vulcanexus.org/) is the official ROS 2 story for microcontrollers, built on DDS-XRCE (DDS for eXtremely Resource-Constrained Environments).
- ESP32 support is mature via [micro_ros_platformio](https://github.com/micro-ROS/micro_ros_platformio) (PlatformIO), [micro-ROS for Arduino](https://github.com/micro-ROS/micro_ros_arduino), and the [ESP-IDF component](https://answers.ros.org/question/379267).
- Real-world working examples: [ESP32 publishing ROS 2 messages over WiFi + UDP](https://robofoundry.medium.com/esp32-micro-ros-actually-working-over-wifi-and-udp-transport-519a8ad52f65), [Ibrahim Bin Mansur's LinkedIn walkthrough](https://www.linkedin.com/pulse/micro-ros-esp32-ibrahim-bin-mansur-kmzwf), [ros2_control with ESP32](https://robotics.stackexchange.com/questions/111604/how-would-i-implement-ros2-control-with-an-es-p32-running-micro-ros).
- A common topology: ESP32 (sensor) → Micro XRCE-DDS Agent (vessel PC) → DDS bus → ROS 2 nodes (game-engine bridge, vessel dynamics, agent logic).

This is the **most defensible technical choice** in the entire AELMA architecture. The robotics community has spent years hardening this path.

### 2.5 Game-Engine Bridges

- **Unity:** [ROS-TCP-Connector](https://github.com/Unity-Technologies/ROS-TCP-Connector) (Unity Robotics) — official, TCP to a ROS endpoint.
- **Unreal:** [ROSIntegration](https://github.com/code-iai/ROSIntegration) — supports [both TCP and WebSocket to rosbridge, ROS1 and ROS2](https://github.com/code-iai/ROSIntegration). [Important caveat for ROS2: rosbridge_suite dropped TCP socket, only WebSocket remains](https://github.com/code-iai/ROSIntegration/issues/102).
- **Web:** [rosbridge_suite](http://wiki.ros.org/rosbridge_suite) provides a WebSocket interface to ROS ([Foxglove tutorial](https://foxglove.dev/blog/using-rosbridge-with-ros2)).
- **Roblox:** No first-party bridge. Would require either (a) HttpService → rosbridge_server HTTP endpoint, or (b) the newly-arriving WebSocket support → rosbridge WebSocket. See §6.

### 2.6 Where ROS+Gazebo Falls Down vs. a Game Engine (Vessel-Level)

The [Open Robotics Discourse thread "Why do we use Gazebo instead of Unreal or Unity?"](https://discourse.openrobotics.org/t/why-do-we-use-gazebo-instead-of-unreal-or-unity/25890) is canonical on this. Summarized for AELMA:

| Aspect | ROS + Gazebo | Game Engine (Unity/UE/Roblox) |
|---|---|---|
| **Physics accuracy (hydrodynamics, control surfaces)** | Strong | Often lacking — game physics optimizes for "looks right," not "is right" ([SMaRCSim arXiv 2506.07781](https://arxiv.org/html/2506.07781v1)) |
| **ROS integration** | Native | Requires bridges |
| **Visual photorealism** | Limited | Excellent |
| **Maritime sensors (sonar, hydrophones, AIS)** | Better support | Needs custom modules |
| **Best for** | Control design, autonomy testing | Perception, scenario simulation, datasets, **crew-facing UX** |
| **Multi-user "game" UX (kid + crew)** | Absent | Native |
| **Cost to deploy to a phone/tablet** | High (ROS on Android exists but is awkward) | Low (especially Roblox) |

For AELMA — where the *agent + crew + child* interface is a first-class requirement, not an afterthought — the game-engine column is genuinely compelling. The bridge is: **ROS 2 + micro-ROS handle the hardware**, the **game engine handles the visualization and the human-facing interaction**. This is the [LOTUSim architecture pattern](https://arxiv.org/html/2607.03072v1) (ROS2 + Gazebo + Unity, distributed).

---

## 3. Game-Engine-as-OS Prior Art

Who has tried to use a game engine as a general-purpose operating environment? The AELMA paper's "Vessel MUD" metaphor places it in a long lineage.

### 3.1 Unity as a Runtime for Non-Game Apps

- [Unity Industry](https://unity.com/products/unity-industry) is explicitly positioned for "visualization, simulation, AR/VR, and interactive applications" beyond gaming.
- [realvirtual.io](https://realvirtual.io/en/) is a Unity-based plant/robot simulation platform with 25+ PLC interfaces and virtual commissioning — the closest commercial analog to "Unity as industrial OS."
- [Non-game Unity showcase](https://discussions.unity.com/t/non-game-unity3d-showcase/464734) includes the **CVNF ship-familiarization training aid** — spatial awareness, system manipulation — directly on-point for AELMA's vessel-training mode.
- [Vision 2017 "Unity Beyond Games"](https://www.youtube.com/watch?v=D0djcOIiUUU) panel on AEC (architecture, engineering, construction) industry adoption.

### 3.2 Metaverse Platforms — Lessons Learned

**[VRChat](https://hello.vrchat.com/)** — Survived. The strongest "social VR as platform" survivor. Lesson: **UGC (user-generated content) is the moat**. AELMA's "vessel as evolving world" thesis depends on the same dynamic.

**[Roblox](https://www.roblox.com/)** — Survived and dominant. Lesson: **The platform beats the engine**. Roblox's value is the distribution, monetization, and discovery layer, not Luau or the renderer. For AELMA on a vessel (offline, single-vessel), *the platform is missing* — you'd be using Roblox as a pure engine.

**[Mozilla Hubs](https://hubs.mozilla.com/)** — [Discontinued by Mozilla](https://realitylearning.org/the-sun-sets-on-mozilla-hubs-and-where-to-next-for-user-generated-vr/). Lesson: **Open-web metaverse is hard to fund**. Hubs was technically excellent (WebXR, no install) but Mozilla couldn't justify the cost. A community fork continues.

**[Sansar](https://en.wikipedia.org/wiki/Sansar_(video_game))** — [Linden Lab sold it off in 2020](https://techcrunch.com/2020/03/24/second-life-maker-calls-it-quits-on-their-vr-follow-up-sansar/) after [layoffs and a hiring freeze](https://trilo.org/2020/02/28/sansar-commentary/). [Engadget's postmortem](https://www.engadget.com/2020-03-27-why-second-life-linden-lab-sold-sansar.html) cites **profitability** as the core reason. Lessons: Windows-only limited the user base; VR adoption didn't materialize as fast as hoped; the **"build it and they will come"** assumption for metaverse platforms is false.

**Common lesson:** Every surviving "metaverse" platform has either (a) a massive UGC+discovery moat (Roblox, VRChat), or (b) a focused industrial use case (Unity Industrial). AELMA's vessel-twin is *not* a metaverse — it's an industrial control surface with a game-like UX. The relevant prior art is industrial, not social.

### 3.3 Military Simulation (VBS4, OneSAF)

This is where "game engine as OS for simulation" is most established:

- **[VBS4](https://onearc.com/products/vbs4/)** (BAE Systems / OneArc, formerly Bohemia Interactive Simulations) — A whole-earth virtual + constructive simulation, [used by 60+ NATO and allied nations](https://www.baesystems.com/en/article/norwegian-armed-forces-upgrade-enterprise-simulation-capabilities-with-bae-systems-onearcs-vbs4). Grew out of *Operation Flashpoint / Arma* (Real Virtuality engine). [US Army upgrades continue through 2025](https://thedefensepost.com/2025/07/29/us-army-vtirtual-battlespace-training/).
- **[OneSAF](https://www.leidos.com/sites/leidos/files/2019-10/FS-OneSAF-Overview-Leidos.pdf)** (Leidos) — The US Army's brigade-and-below constructive simulation. OneSAF + VBS4 compose for Live-Virtual-Constructive (LVC) training.
- Both support NATO interoperability standards (**HLA/DIS/CSSL**). This matters: if AELMA ever needs to interoperate with maritime training simulators, these are the protocols.

**Lesson for AELMA:** Military sim started with game engines (Operation Flashpoint → VBS) and *evolved toward* physics-faithful simulation + interoperability standards. AELMA is starting from the same place.

### 3.4 MUDs / MOOs — The "Vessel MUD" Precedent

This is the historical lens the AELMA paper explicitly invokes:

- **[MUD (Multi-User Dungeon)](https://en.wikipedia.org/wiki/MUD)** — Created 1978 by Roy Trubshaw and Richard Bartle at Essex University. The original multi-user virtual world.
- **[LambdaMOO](https://en.wikipedia.org/wiki/LambdaMOO)** — Founded 1990 by Pavel Curtis at Xerox PARC, building on Stephen White's MOO ("MUD, Object-Oriented"). [The Stanford history](https://cs.stanford.edu/people/eroberts/cs181/projects/controlling-the-virtual-world/history/mud.html) and [Aaron Reed's IF50 piece](https://if50.substack.com/p/1990-lambdamoo) document the era.
- LambdaMOO was simultaneously: **a multi-user virtual world**, **a collaborative programming environment** (with its own [compiler, VM, object database, and permissions system](https://www.reddit.com/r/rust/comments/16q9xeg/i_rewrote_the_90s_lambdamoo_mud_server_from/)), and **a social experiment**. As [one retrospective puts it](https://medium.com/@sixcupsofcoffee/tiny-life-the-virtual-textual-reality-of-lambdamoo-509a8a504672): "part game, part programming environment, part experimental community."
- The MOO programming language let users build and modify the world in real time — the original "spatial programming environment."

**Lesson for AELMA:** The "vessel as programmable space" idea is 35+ years old. The novelty is doing it with modern game-engine rendering and LLM agents.

### 3.5 Spatial Computing Platforms ("Room as OS")

- **Apple Vision Pro** (visionOS) — Premium ($3,500) "spatial computer." A [UC San Diego clinical trial](https://today.ucsd.edu/story/clinical-trial-evaluates-spatial-computing-app-on-apple-vision-pro-in-operating-room) uses it to display patient imaging and vitals *in the operating room* — the "room as platform" concept in production.
- **Meta Quest** — Affordable spatial computing ($500+). Quest 3's pass-through MR is the volume play.
- **Magic Leap** — [Lumin OS](https://www.youtube.com/watch?v=RVd0K8hKc9w) was "the world's first operating system built specifically for spatial computing." Magic Leap 2 is [standalone, self-contained](https://stagemeta.world/blog/spatial-computing-devices-top-5-picks/), AR-first (truly transparent optics, not video pass-through).
- [Qualium Systems' comparative analysis](https://qualium-systems.com/blog/ar-vr/elevating-spatial-computing-examining-technological-feats-of-apple-vision-pro-magic-leap-meta-quest-pro-and-microsoft-hololens/) frames these as competing to define "the OS of spatial computing."

**Relevance to AELMA:** A fishing vessel is already a "spatial computer" in the analog sense — the bridge, the deck, the engine room are spatially-organized information surfaces. AELMA's "vessel MUD" thesis is the digital twin of this. AR headsets (Quest/Vision/Magic Leap) are the obvious future UX, but a tablet/phone is the realistic *today* UX on a working fishing boat.

---

## 4. Agentic / LLM-Driven Agents in Game Engines

### 4.1 Roblox's AI Features (2024–2026)

What's actually shipping:

- **[Code Assist](https://devforum.roblox.com/t/code-assist-full-release-ai-powered-code-completion/2848978)** — AI code completion in Studio's Script Editor. [41% of beta users](https://www.pocketgamer.biz/41-percent-of-beta-users-are-utilising-robloxs-ai-code-assist/) adopted it. Full release shipped.
- **[Assistant for Studio](https://create.roblox.com/docs/assistant/guide)** — Generative AI helper: [answers questions, generates content, inserts LocalScripts/ServerScripts/ModuleScripts/RemoteEvents](https://devforum.roblox.com/t/full-release-use-assistant-to-boost-your-productivity/3294217), explains code, and **generates materials and textures via text prompts**. [Introduced in Studio Beta](https://devforum.roblox.com/t/introducing-assistant-in-studio-beta/2725977).
- **Generative materials** — users can [generate graphics, materials, textures, and code from text prompts](https://voicebot.ai/2023/09/12/roblox-debuts-generative-ai-assistant-for-building-virtual-worlds/).
- **Roblox-generated games and agentic ecosystem** — Roblox is investing heavily in [agentic game creation](https://devforum.roblox.com/t/code-assist-beta-ai-powered-code-completion/2224387). Internal AI uses (likely custom + Anthropic/OpenAI partnerships) are not fully public, but the trajectory is clear: Roblox wants Assistant to build entire experiences from natural language.

**Important caveat:** All of Roblox's AI features are **Studio-time authoring aids**, not **runtime agentic NPCs**. There is no first-party Roblox LLM-NPC product. You'd wire up your own via HttpService → external LLM API.

### 4.2 NVIDIA ACE (Avatar Cloud Engine)

[NVIDIA ACE](https://developer.nvidia.com/ace-for-games) is a suite of generative AI technologies for **conversational, knowledgeable, actionable in-game characters**. CES 2024 demoed [direct voice input for natural NPC conversations](https://hothardware.com/news/nvidia-ace-ces-2024). The 2024-2025 push is toward ["Autonomous Game Characters"](https://www.reddit.com/r/Games/comments/1i9rzre/nvidia_redefines_game_ai_with_ace_autonomous_game/) — NPCs that perceive, decide, converse, and act. Partners with [Convai](https://convai.com/blog/elevating-conversational-npcs-nvidia-ace-for-games-taps-convai-for-creating-humanlike-characters) for humanlike characters. Audio2Face provides facial animation. ACE integrates with Unreal Engine.

### 4.3 Inworld AI, Convai, Charisma.ai — Agentic NPC Middleware

Comparison based on [loreweaver.ink's 2026 analysis](https://loreweaver.ink/insights/inworld-convai-alternatives/) and [Streamoji's alternatives guide](https://streamoji.com/blog/best-convai-alternatives-2026):

| Platform | Strength | Engine Integration |
|---|---|---|
| **[Inworld AI](https://inworld.ai/)** | Emotionally complex, character-driven NPCs | Unity, Unreal |
| **[Convai](https://convai.com/)** | Most flexible; strong knowledge base and learning features | Unity, Unreal, Roblox (limited) |
| **[Charisma.ai](https://charisma.ai/)** | Interactive narrative and training (not pure gameplay) | Unity, Unreal, web |

[Aftermath's hands-on review](https://aftermath.site/ai-npcs-nvidia-unity-ubisoft-convai-inworld/) is a useful critical perspective — the state of the art in 2024-2025 is "impressive demos, awkward in shipped games." The middleware is split between **cloud-based** (Convai, Inworld default) and emerging **on-device/local-first** solutions — the latter being critical for an air-gapped vessel.

### 4.4 Foundational Papers on LLM Agents in Interactive Environments

The four papers AELMA must cite:

1. **[Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442)** (Park et al., Stanford/Google, UIST 2023, ~6,869 citations). The "**Smallville**" sandbox — 25 LLM agents with **memory stream → reflection → planning** architecture. This is the foundational architecture for any "agents in a simulated world" system, AELMA included. [GitHub](https://github.com/joonspk-research/generative_agents), [Joon Sung Park talk](https://www.youtube.com/watch?v=XY5Wncq5vAE).

2. **[Voyager: An Open-Ended Embodied Agent with Large Language Models](https://arxiv.org/abs/2305.16291)** (Wang et al., NVIDIA/Caltech, NeurIPS 2023, ~2,927 citations). The first LLM-powered embodied lifelong learning agent — in Minecraft. Key contribution: **automatic curriculum + skill library + iterative prompting**. [Project page](https://voyager.minedojo.org/), [GitHub](https://github.com/minedojo/voyager). Directly relevant to AELMA's "vessel agent that learns the boat."

3. **[MindAgent: Emergent Gaming Interaction](https://arxiv.org/abs/2309.09971)** (Gong et al., 2023, 183+ citations). Multi-agent LLM coordination in a virtual kitchen ("CuisineWorld"). [Project page](https://mindagent.github.io/). Relevant to AELMA's multi-agent crew-coordination scenarios.

4. **[GITM (Ghost in the Maze)](https://github.com/git-disl/awesome-LLM-game-agent-papers)** — Listed in the [Awesome LLM Game Agent Papers](https://github.com/git-disl/awesome-LLM-game-agent-papers) collection. (Note: "GITM" commonly refers to "Ghost in the Maze" — a multi-agent LLM navigation paper.)

The [Awesome LLM Game Agent Papers](https://github.com/git-disl/awesome-LLM-game-agent-papers) repo (accepted to ACM Computing Surveys) is the comprehensive reading list.

### 4.5 LLM Agents Controlling Real Hardware Through a Game Engine

This is the *specific* question AELMA depends on, and the prior art is thin:

- **[LA-RCS: LLM-Agent Based Robot Control System](https://arxiv.org/html/2505.18214v1)** — Autonomous robot control using LLM agents. Closest to AELMA's "agent controls hardware" loop, but no game engine in the middle.
- **[MIT CSAIL SceneSmith](https://news.mit.edu/2026/ai-agents-create-virtual-playgrounds-to-help-robots-get-crucial-training-data-0713)** — AI agents generate virtual indoor scenes to train robots. Simulation-to-real bridging.
- **[MALMM (Multi-Agent LLM for Manipulation)](https://malmm1.github.io/assets/IROS_2025_malmm_v8.pdf)** — Distributes planning across three LLM agents (high-level planning, low-level control, supervisor).
- **[The Reddit r/AI_Agents discussion "Is anyone building an engine for AI agents like game engines?"](https://www.reddit.com/r/AI_Agents/comments/1o9cq1h/is_anyone_building_an_engine_for_ai_agents_like/)** — Community exploration of exactly the AELMA concept.
- **[LLM-Powered AI Agent Systems survey](https://arxiv.org/html/2505.16120v1)** — Comprehensive survey.
- **[LLM controlling a robot via Jetson Orin Nano](https://www.youtube.com/watch?v=0O8RHxpkcGc)** — Practical demo.

**Honest assessment:** AELMA's specific contribution — **LLM agent → game engine → real hardware (vessel)** — appears to be genuinely novel. The closest prior art is LLM-robot-control papers that skip the game-engine layer, and metaverse-style agent-in-simulation work that skips the hardware layer. AELMA's bet is that the game engine is the right *intermediary*.

### 4.6 Roblox ConnectWebSocket — Factual Investigation

This is the specific factual question the AELMA paper depends on. Here is the honest finding:

- **[WebSockets Support in Studio is now available!](https://devforum.roblox.com/t/websockets-support-in-studio-is-now-available/4021932)** — Roblox DevForum announcement. **WebSocket support has shipped** (the discussion thread dates it to ~October 2025 based on the [TikTok coverage](https://www.tiktok.com/@lastlevelstudios/video/7569208810351398166)).
- Historically, Roblox **did not** have native WebSocket client support. The community built workarounds: [RoSocket](https://github.com/RoSocket/rosocket) (open-source WebSocket replication), long-polling via `HttpService`, external proxy servers.
- The new native support is **Studio-first**, with server-side rollout being the open question.
- **Class/API surface:** Details are in the DevForum thread. The community has long requested [`Add WebSocket Client Support`](https://devforum.roblox.com/t/add-websocket-client-support/239808) and [`Web Sockets for servers`](https://devforum.roblox.com/t/web-sockets-for-servers/20769).

**Honest assessment for AELMA:** If WebSocket support is Studio-only (not yet on live game servers, not yet on Roblox's hosted infrastructure), then AELMA's "Roblox server ↔ vessel daemon over WebSocket" architecture has a foundational dependency on a feature that may not be production-ready. This is a **first-order risk** — see §6.

---

## 5. Predictive / "What-If" Physics in Game Engines (The "Divination" Sandbox)

AELMA proposes a "Divination" sandbox: clone the world state, accelerate time 5x, test a maneuver. What prior art exists?

### 5.1 NVIDIA Isaac Lab — RL Policy Training Loops

[Isaac Lab](https://isaac-sim.github.io/IsaacLab/main/source/overview/reinforcement-learning/index.html) (built on Isaac Sim) is the state-of-the-art for "spawn many parallel environments, train a policy, evaluate." Supports RSL-RL, SKRL, Stable Baselines3, RL Games. [AWS SageMaker integration](https://aws.amazon.com/blogs/machine-learning/scale-robot-reinforcement-learning-with-nvidia-isaac-lab-on-amazon-sagemaker-ai/) scales to humanoid-robot training. NVIDIA's [agent skills](https://blogs.nvidia.com/blog/cvpr-physical-ai-research-agent-skills/) can autonomously launch sim sessions — the closest existing thing to AELMA's Divination.

### 5.2 Unity ML-Agents

[ML-Agents](https://github.com/unity-technologies/ml-agents) is the most accessible game-engine-integrated RL toolkit. PPO and SAC, curriculum learning, multi-agent. [Unity Learn "Hummingbirds" course](https://learn.unity.com/course/ml-agents-hummingbirds) is a gentle on-ramp. [Arm Developer tutorial](https://developer.arm.com/additional-resources/video-tutorials/devhub/using-unitys-machine-learning-agents-on-arm) covers mobile deployment. [Academic study of PPO and SAC in ML-Agents](https://ijctcm.researchcommons.org/cgi/viewcontent.cgi?article=1722&context=journal).

**Relevance to AELMA:** If "Divination" is *RL policy training*, Unity ML-Agents or Isaac Lab is the answer. If "Divination" is *one-shot accelerated-time rollouts of a fixed scenario* (no learning), then it's simpler — a pure simulation question.

### 5.3 Tesla Shadow Mode (and Waymo / comma.ai)

**[Tesla shadow mode](https://www.reddit.com/r/teslamotors/comments/aqy832/deepdive_into_autopilot_shadow_mode_verygreen_on/)** is the canonical "Divination"-adjacent pattern: while the driver manually steers, the onboard computer silently computes autonomous decisions and compares them to driver actions — a "silent simulation" running alongside reality. See [The Verge (2016)](https://www.theverge.com/2016/10/19/13341194/tesla-autopilot-shadow-mode-autonomous-regulations), [Forbes (Templeton, 2019)](https://www.forbes.com/sites/bradtempleton/2019/04/29/teslas-shadow-testing-offers-a-useful-advantage-on-the-biggest-problem-in-robocars/), [NotATeslaApp explainer](https://www.notateslaapp.com/news/3108/teslas-fsd-shadow-mode-what-it-is-and-how-it-improves-fsd).

Waymo and comma.ai take different approaches:
- **Waymo** — Heavy offline simulation (Carcraft, Structured Testing). Billion-mile sim runs.
- **comma.ai** — Open-source [openpilot](https://github.com/commaai/openpilot); community-driven. Their simulation story is lighter than Tesla's but the [comma.ai philosophy](https://comma.ai/) emphasizes on-device inference and fleet learning.

**Relevance to AELMA:** Tesla shadow mode is *exactly* the Divination pattern AELMA proposes — a parallel "what would the AI do" computation running alongside human operation. The difference: Tesla does it at 1x real-time (no time acceleration) because the constraint is *comparison to human behavior*. AELMA's 5x acceleration is harder — it requires the physics sim to run faster than real-time, which is straightforward offline but non-trivial when the sim is coupled to live hardware.

### 5.4 Digital Twin "Shadow" / "Sibling" Patterns in Manufacturing

The academic literature distinguishes:

| Concept | Data Flow | Use Case |
|---|---|---|
| **Digital Model** | No automatic data exchange | Simulation / design |
| **Digital Shadow** | One-way (physical → digital) | Monitoring, optimization |
| **Digital Twin** | Two-way (bidirectional) | Active control, predictive maintenance |

Source: [Bergs et al., "The Concept of Digital Twin and Digital Shadow in Manufacturing"](https://www.researchgate.net/publication/354393364_The_Concept_of_Digital_Twin_and_Digital_Shadow_in_Manufacturing) (287 citations). Also [Oxford Insights](https://oxfordinsights.com/insights/exploring-the-concepts-of-digital-twin-digital-shadow-and-digital-model/), [Analog IC Tips](https://www.analogictips.com/whats-a-digital-shadow-and-how-does-it-relate-to-a-digital-twin-faq/), [RWTH Aachen](https://www.se-rwth.de/research/Digital-Twins/).

**Industrial platforms:**
- **[GE Predix](https://www.researchgate.net/publication/319303600_GE_'predix'_the_future_of_manufacturing)** — Cloud OS for industrial IoT. [GE burned ~$7B on the platform play](https://platformengineering.org/blog/how-general-electric-burned-7-billion-on-their-platform) — a cautionary tale. Now reorganized as GE Vernova.
- **[Siemens MindSphere / Xcelerator](https://www.siemens.com/en-us/company/digital-twin/comprehensive-digital-twin-for-industry/)** — Siemens' IoT operating system. The [comprehensive Digital Twin](https://www.siemens.com/en-us/campaigns/digital-twin/) runs "what-if" scenarios and predicts future performance. [Simcenter xDT](https://www.siemens.com/en-us/products/simcenter/integration-solutions/executable-digital-twin/) is the "Executable Digital Twin" — directly HIL-integrable.
- **Comparison:** [GE Digital (Predix/APM) models the physics, Siemens (MindSphere/Tecnomatix) is best for automation and design simulation](https://www.fabrico.io/tr/blog/best-digital-twin-software-manufacturing/).

**Market size:** Asia Pacific digital twin market projected to grow from $4.57B (2025) to $32.57B (2030), 48.1% CAGR, with [Siemens and GE Vernova leading](https://www.marketsandmarkets.com/ResearchInsight/asia-pacific-digital-twin-companies.asp).

### 5.5 Accelerated-Time HIL for Vessels — Academic Prior Art

Marine-specific HIL is a real field, though "accelerated time" is rare:

- **[Speedgoat marine HIL webinar](https://www.speedgoat.com/knowledge-center/webinars/advancing-marine-power-systems-using-hardware-in-the-loop-testing)** — Multi-target HIL for marine power systems.
- **[Cui et al., "Hardware in the Loop Simulation and Control Design for Autonomous Free Running Ship Models"](https://www.researchgate.net/publication/343132995_Hardware_in_the_Loop_Simulation_and_Control_Design_for_Autonomous_Free_Running_Ship_Models)** — HIL for autonomous ship-model testing.
- **[Johansen et al., "Hardware-in-the-loop Testing of DP Systems"](https://dynamic-positioning.com/wp-content/uploads/2025/12/control_johansen.pdf)** (60+ citations) — Classic DP-HIL vessel simulator.
- **[Tree-C marine HIL simulators](https://www.tree-c.nl/general/hardware-in-the-loop-simulators-for-marine-environments-explained/)** — Commercial HIL for offshore/subsea.
- **[Huijgens et al., "Hardware in the loop experiments on propeller-hull interaction"](https://www.tandfonline.com/doi/full/10.1080/20464177.2022.2138736)** (2023).
- **[Open Simulation Platform Gunnerus-DP demo](https://open-simulation-platform.github.io/cosim-demo-app/Gunnerus-DP)** — Open-source co-simulation for vessel dynamic positioning.

**Gap:** These are all **real-time** HIL. AELMA's "**accelerated-time (5x) HIL**" for vessel maneuver prediction appears genuinely novel — the marine literature focuses on real-time validation, not predictive rollouts. This is both an opportunity (novel contribution) and a risk (no proven prior art).

---

## 6. Key Risks & Open Questions

What are the biggest technical objections an expert would raise to AELMA-on-Roblox?

### 6.1 Roblox Headless Air-Gapped Servers — **Blocking Risk**

**Claim in AELMA paper:** Roblox can run on a vessel without internet.

**Finding:** **Roblox does not officially support air-gapped or fully offline server hosting.** Evidence:
- [Roblox Studio offline feature request](https://devforum.roblox.com/t/it-should-be-possible-to-use-roblox-studio-offline/153244?page=3) — Studio itself often fails without internet for authentication.
- [How to run a Roblox Studio game over LAN](https://devforum.roblox.com/t/how-to-run-a-roblox-studio-game-over-lan/313822) — LAN testing requires initial internet for auth.
- [Error Code 277](https://en.help.roblox.com/hc/en-us/articles/36795858515860-Error-Code-277-Lost-connection-to-the-game-server-please-reconnect-Please-check-your-internet-connection-and-try-again) — clients require persistent connection.
- [Roblox Offline Mode YouTube workaround](https://www.youtube.com/watch?v=EytAWYUHgMM) — solo play only, not server hosting.
- [Rboxlo2](https://github.com/inposs2/Rboxlo2) — community reverse-engineering project; legally and technically fragile.

**Verdict:** **Roblox's architecture is cloud-based.** Authentication, asset delivery, and server orchestration all run through Roblox's infrastructure. A `.rbxl` file is a place file, not a self-contained server binary. **If AELMA requires true air-gapped operation, Roblox is the wrong engine.** This is the single biggest technical objection.

**Mitigation options:**
1. Accept intermittent connectivity (vessel has Starlink or coastal LTE). Run Roblox on live servers when online; cache and replay when offline.
2. Use Roblox only for the UX/visualization layer (Studio-time or client-side), and run a different headless engine (Godot/Unity/Bevy) for the vessel-side twin.
3. Switch engines entirely to Godot/Bevy/O3DE — all of which support true air-gapped headless servers.

### 6.2 HttpService Limits — **Serious Risk**

**Claim in AELMA paper:** HttpService is "unrestricted on local network."

**Finding:** **False.** Evidence:
- [Rate limit: 500 HTTP requests per minute per game server](https://create.roblox.com/docs/cloud-services/http-service) (standard).
- [2,500 Open Cloud requests per minute](https://create.roblox.com/docs/reference/engine/classes/HttpService/RequestAsync) per game server.
- [WebStreamClient: max 6 concurrent clients](https://create.roblox.com/docs/reference/engine/classes/HttpService).
- **[Trust check blocks private/local IPs](https://devforum.roblox.com/t/how-to-access-localhost-using-httpservice-in-roblox-studio/1496085):** `127.0.0.1`, `192.168.x.x`, `10.x.x.x` are all blocked. The classic error is `"127.0.0.1: Trust check failed."`
- [Workarounds](https://stackoverflow.com/questions/70284349/i-am-struggling-to-discover-a-good-method-to-link-my-server-to-my-roblox-game): deploy backend on a public HTTPS domain, or use ngrok/Cloudflare Tunnel during dev. **None of these work on an air-gapped vessel LAN.**

**Verdict:** **HttpService is not "unrestricted on local network" — it is actively hostile to local network targets.** This is a security feature (SSRF prevention) baked into Roblox's cloud infrastructure. The AELMA paper's claim here is incorrect and must be revised.

### 6.3 Roblox HttpService — Rate Limits and Allowed Protocols

| Limit | Value |
|---|---|
| Standard HttpService requests | **500 per minute** per game server |
| Open Cloud requests (in-game) | **2,500 per minute** per game server |
| WebStreamClient concurrent clients | **6 at one time** |
| Allowed protocols | **HTTP and HTTPS** (HTTPS strongly recommended) |

Sources: [Roblox Creator Hub — Rate limits](https://create.roblox.com/docs/cloud/reference/rate-limits), [In-game HTTP requests](https://create.roblox.com/docs/cloud-services/http-service), [HttpService reference](https://create.roblox.com/docs/reference/engine/classes/HttpService).

**Relevance to AELMA:** 500 req/min = ~8.3 req/sec. For a vessel with multiple sensors at 10Hz each, you're already over budget. The daemon-hop architecture (Roblox → local daemon → multiple sensors) is essential, but the Roblox→daemon link itself is the bottleneck.

### 6.4 Latency Claims — Sub-50ms on a Vessel LAN

**Claim in AELMA paper:** Sub-50ms latency is realistic.

**Finding:** Mixed.
- [Roblox ping benchmarks](https://pingtestlive.com/roblox) confirm **sub-50ms is "excellent" and the competitive-player target** — on Roblox's hosted infrastructure, with nearby servers.
- [Average ping by region](https://devforum.roblox.com/t/average-ping-in-your-country-or-region/3737421) — 0–50ms is "best performance."
- However: **this is ping to Roblox's cloud servers**, not to a vessel-LAN daemon. The actual loop is: `Roblox client → Roblox server (cloud) → HttpService → vessel daemon → sensor → return`. The cloud hop alone can easily exceed 50ms.
- [HttpService can be "extremely sluggish in Studio"](https://devforum.roblox.com/t/httpservice-extremely-sluggish-in-studio/2658364) — ~4 minutes per request in worst cases.

**Verdict:** Sub-50ms end-to-end on a vessel LAN is **not realistic** if the loop includes Roblox's cloud. It is realistic only if the loop is: `Roblox client (vessel tablet) → vessel daemon (LAN)` — which requires either (a) the new WebSocket support working on live servers, or (b) a fundamentally different architecture.

### 6.5 Physics Determinism in Roblox

**Finding:** Roblox physics is **not deterministic** in the lockstep sense. It uses Havok-like real-time physics with [client-side prediction and server reconciliation](https://create.roblox.com/docs/reference/engine/classes/BasePart#SetNetworkOwner), not deterministic lockstep.

For comparison, see [Gaffer on Games — Deterministic Lockstep](https://gafferongames.com/post/deterministic_lockstep/), [Mieschke 2024 — Deterministic Lockstep in Networked Games](https://hdms.bsz-bw.de/files/7107/DeterministicLockstepInNetworkedGamesPaper.pdf), and the [Bevy determinism audit discussion](https://github.com/bevyengine/bevy/discussions/2480).

**Relevance to AELMA's Divination sandbox:** If Divination requires *reproducible* physics (same inputs → same outputs), Roblox's physics won't deliver. The Bevy + Avian (`enhanced-determinism`) stack would. Unity and Unreal also have non-deterministic physics by default.

**Verdict:** **Physics determinism is a real problem for AELMA's Divination feature on Roblox.** Workaround: use a separate deterministic simulator (Isaac Sim, Gazebo, or a custom Bevy sim) for Divination rollouts, and use Roblox only for visualization.

### 6.6 Luau → ESP32 C++ Code Generation — Feasibility

**Finding:** **No existing tool transpiles Luau to C++ for the ESP32.**

- [Luau native codegen](https://luau.org/performance/) targets x64/ARM64 host CPUs, not the ESP32's Xtensa LX6/LX7.
- **Standard Lua** (not Luau) runs on ESP32 via [Xedge32](https://www.instructables.com/How-to-Code-With-Lua-on-ESP32-With-Xedge32/), [Lua-RTOS-ESP32](https://github.com/whitecatboard/Lua-RTOS-ESP32), and NodeMCU. These interpret Lua bytecode on-device — they don't transpile to C++.
- [RealtimeLogic analysis](https://realtimelogic.com/articles/Using-Lua-for-Embedded-Development-vs-Traditional-C-Code) notes Lua is "not well-suited for ultra-low-resource microcontrollers."
- The reverse direction exists: [C/C++/Rust → Luau compilation](https://devforum.roblox.com/t/c-c-rust-in-roblox-compile-to-luau/3915431).
- Luau and Lua are **not bytecode-compatible** — Luau has a custom bytecode format and a gradual type system.

**Verdict:** Building a Luau-to-C++ transpiler for ESP32 is **theoretically feasible but would be a novel research project.** The realistic path is: Luau on the game-engine side, **C/C++ (with micro-ROS)** on the ESP32 side, and an interface contract (ROS 2 topics or a custom protocol) between them.

---

## 7. Engine Verdict Matrix & Recommendation

### 7.1 Summary Matrix

| Criterion | Roblox | Unity | Unreal | Godot | Bevy | Omniverse/Isaac | O3DE |
|---|---|---|---|---|---|---|---|
| **License** | Proprietary (free to dev) | Tiered (free–$4,950/seat) | Proprietary + 5% royalty | **MIT** | **MIT** | Proprietary ($$) | **Apache 2.0** |
| **Air-gapped/headless** | **No** | Yes | Yes | **Yes (trivial)** | Yes | Possible (heavy) | Yes |
| **Networking** | Cloud-locked, WS new | Mature (UTP/NGO) | Mature (Iris/Pixel Streaming) | **Clean (ENet/WS/WebRTC)** | DIY (renet/lightyear) | Nucleus + RTC | Modular Gems |
| **Scripting** | Luau | C# | C++/Blueprints/Verse | **GDScript/C++/C#** | Rust | Python/C++ | Lua/C++ |
| **ROS 2 bridge** | DIY (HttpService→rosbridge) | [ROS-TCP-Connector](https://github.com/Unity-Technologies/ROS-TCP-Connector) | [ROSIntegration](https://github.com/code-iai/ROSIntegration) | DIY (ros2_rust adjacent) | DIY (ros2_rust) | **Native** | Community Gem |
| **Photorealism** | Cartoon | Strong | **Best (Lumen/Nanite)** | Moderate | Low | **Best (RTX)** | Moderate |
| **RL/Agentic ecosystem** | Studio-only AI aids | **ML-Agents (mature)** | Weak (third-party) | Weak | DIY (Candle/Burn) | **Isaac Lab (gold standard)** | Weak |
| **Kid-friendly UX** | **Best (it's Roblox)** | Good | Good | Good | Poor (no editor polish) | Poor | Moderate |
| **Deterministic physics** | No | No | No | No (improving) | **Yes (Avian + libm)** | No (PhysX 5) | No |
| **Bathymetry/geospatial** | DIY | Cesium for Unity | **Cesium for Unreal** | DIY | DIY | **Cesium + USD** | DIY |
| **Local-network HTTP** | **Blocked (trust check)** | Free | Free | Free | Free | Free | Free |

### 7.2 Where Roblox Is Genuinely a Good Choice

1. **The "kid plays the world" angle.** If AELMA's vision includes the captain's son genuinely playing the vessel twin as a Roblox game, no other engine comes close. The Roblox catalog, the avatar system, the social discovery — it's all there.
2. **Transferable skills.** Luau is a clean, modern Lua dialect. Roblox Studio has a gentle learning curve. The skills transfer to Unity (C#) and Unreal (C++) with reasonable effort.
3. **Charming aesthetic.** Roblox's stylized look is appropriate for a "game as UX" thesis. Photorealism can be a liability (uncanny valley) for crew-facing tools.
4. **Distribution.** Roblox runs on phones, tablets, cheap laptops, VR headsets — the actual devices on a fishing vessel.

### 7.3 Where Roblox Is Genuinely a Bad Choice

1. **Air-gapped operation.** This is the dealbreaker. Roblox cannot run without Roblox's cloud. AELMA either accepts intermittent connectivity or switches engines.
2. **HttpService on local network.** The trust check blocks private IPs. The AELMA paper's claim here is wrong.
3. **Physics determinism.** Roblox physics is non-deterministic. Divination rollouts won't reproduce.
4. **Luau → ESP32.** No transpiler exists. The ESP32 will run C/C++ with micro-ROS regardless of engine choice.
5. **Vendor lock-in.** Roblox Corporation controls the platform, the distribution, the monetization, and — ultimately — whether your experience continues to exist.

### 7.4 Recommendation

**Honest recommendation for the AELMA paper:**

The strongest architecture is a **hybrid**:

1. **Vessel-side twin runtime:** [Godot 4 headless](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_dedicated_servers.html) or [Bevy](https://bevy.org/) (both MIT, both trivially headless, both run air-gapped). This is the "serious" twin that talks to micro-ROS ESP32 sensors over the vessel LAN.
2. **Crew/child UX layer:** Roblox client (or Unity/Unreal if Roblox's cloud dependency is disqualifying). Connects to the vessel-side twin over WebSockets.
3. **Divination sandbox:** A separate deterministic simulator (Bevy + Avian, or Gazebo, or Isaac Lab if budget allows). The twin clones its state into this sandbox, accelerates time, runs the maneuver, reports back.
4. **Geospatial substrate:** [Cesium World Bathymetry](https://cesium.com/blog/2024/01/23/introducing-cesium-world-bathymetry/) via [Cesium for Unreal/Unity](https://cesium.com/platform/cesium-for-unreal/) or CesiumJS.
5. **Hardware bridge:** ESP32 sensors running [micro-ROS](https://micro.vulcanexus.org/) → Micro XRCE-DDS Agent → ROS 2 → game-engine bridge.

**If Roblox must be the single engine**, the paper should:
- Acknowledge the air-gapped limitation honestly and propose a "Starlink-connected vessel" assumption.
- Correct the HttpService "unrestricted local" claim.
- Use the new [WebSocket support](https://devforum.roblox.com/t/websockets-support-in-studio-is-now-available/4021932) for the Roblox↔daemon link (and document its current production-readiness honestly).
- Offload Divination to an external deterministic simulator (do not claim Roblox physics can do it).

**If the paper is open to switching engines**, [Godot 4](https://godotengine.org/) is the strongest single-engine pick: MIT, headless, clean multiplayer, GDScript is kid-friendly, and the ecosystem is growing fast. The tradeoff is ecosystem maturity vs. Roblox/Unity.

---

## Appendix: Key Sources by Section

### Section 1 — Game Engine Survey
- [Siemens Xcelerator Digital Twin](https://www.siemens.com/en-us/campaigns/digital-twin/)
- [Siemens Simcenter xDT](https://www.siemens.com/en-us/products/simcenter/integration-solutions/executable-digital-twin)
- [Unity Industry](https://unity.com/products/unity-industry)
- [realvirtual.io](https://realvirtual.io/en/)
- [Non-game Unity showcase](https://discussions.unity.com/t/non-game-unity3d-showcase/464734)
- [Unreal Fest 2024 — Practical Digital Twins](https://www.youtube.com/watch?v=nZVJFjWH7N4)
- [UE × Omniverse SpaceVerse GTC demo](https://dev.epicgames.com/community/learning/tutorials/e9EJ/unreal-engine-co-simulation-ue-and-omniverse-spaceverse-gtc-demo-return-on-experience)
- [NVIDIA Omniverse](https://www.nvidia.com/en-us/omniverse/)
- [NVIDIA Omniverse Blueprint (SC24)](https://www.digitalengineering247.com/article/nvidia-launches-omniverse-blueprint-for-building-digital-twin)
- [Isaac Sim arXiv paper](https://arxiv.org/pdf/2606.03551)
- [State of Simulation for Physical AI (Hugging Face × NVIDIA)](https://huggingface.co/blog/nvidia/state-of-simulation-for-physical-ai)
- [Godot dedicated server docs](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_dedicated_servers.html)
- [Godot high-level multiplayer](https://docs.godotengine.org/en/stable/tutorials/networking/high_level_multiplayer.html)
- [Godot 4.0 multiplayer changes](https://godotengine.org/article/multiplayer-changes-godot-4-0-report-3/)
- [Bevy determinism audit](https://github.com/bevyengine/bevy/discussions/2480)
- [Avian physics for Bevy](https://www.reddit.com/r/rust/comments/1o5hsbi/avian_04_ecsdriven_physics_for_bevy/)
- [Babylon.js 9.0](https://www.babylonjs.com/)
- [Three.js WebGPU status 2026](https://www.utsubo.com/blog/threejs-2026-what-changed)
- [Babylon.js 5.0 WebGPU](https://babylonjs.medium.com/babylon-js-5-0-beyond-the-stars-2d11d4c3d07)
- [O3DE on AWS](https://aws.amazon.com/blogs/gametech/aws-for-games-latest-contribution-to-the-open-3d-engine-o3de/)
- [O3DE 24.09 release](https://tfir.io/open-3d-engines-o3de-24-09-release-boosts-capabilities-and-ease-of-use/)
- [Cesium for Unreal](https://cesium.com/platform/cesium-for-unreal/)
- [Cesium for Unity](https://cesium.com/platform/cesium-for-unity/)
- [Cesium World Bathymetry](https://cesium.com/blog/2024/01/23/introducing-cesium-world-bathymetry/)
- [Cesium undersea use case](https://cesium.com/use-cases/underground-undersea/)

### Section 2 — ROS 2 + Gazebo
- [ROS 2 + Gazebo Harmonic tutorial](https://www.youtube.com/watch?v=b8VwSsbZYn0)
- [Gazebo in ROS 2 Humble docs](https://docs.ros.org/en/humble/Tutorials/Advanced/Simulators/Gazebo/Simulation-Gazebo.html)
- [PX4 + ROS 2 + Gazebo HIL setup](https://medium.com/@erdem.ku.3.14/ros2-humble-gazebo-harmonic-px4-ve-micro-xrce-dds-agent-client-installation-aad32d8f5669)
- [micro-ROS official site](https://micro.vulcanexus.org/)
- [ESP32 micro-ROS over WiFi/UDP](https://robofoundry.medium.com/esp32-micro-ros-actually-working-over-wifi-and-udp-transport-519a8ad52f65)
- [micro-ROS on ESP32 (LinkedIn walkthrough)](https://www.linkedin.com/pulse/micro-ros-esp32-ibrahim-bin-mansur-kmzwf)
- [ros2_control + ESP32](https://robotics.stackexchange.com/questions/111604/how-would-i-implement-ros2-control-with-an-es-p32-running-micro-ros)
- [rcllua GitHub](https://github.com/jbbjarnason/rcllua)
- [ROSIntegration for Unreal](https://github.com/code-iai/ROSIntegration)
- [rosbridge_suite ROS wiki](http://wiki.ros.org/rosbridge_suite)
- [Foxglove rosbridge for ROS 2](https://foxglove.dev/blog/using-rosbridge-with-ros2)
- [Why Gazebo instead of Unity/Unreal? (Open Robotics)](https://discourse.openrobotics.org/t/why-do-we-use-gazebo-instead-of-unreal-or-unity/25890)
- [SMaRCSim (marine robotics sim)](https://arxiv.org/html/2506.07781v1)
- [LOTUSim (ROS2 + Gazebo + Unity)](https://arxiv.org/html/2607.03072v1)
- [Comparing photorealism for maritime datasets (DLR)](https://elib.dlr.de/211642/1/MARESEC_2024_paper_46.pdf)

### Section 3 — Game-Engine-as-OS
- [Unity Industry](https://unity.com/products/unity-industry)
- [VBS4 (BAE OneArc)](https://onearc.com/products/vbs4/)
- [VBS4 NATO deployment](https://www.baesystems.com/en/article/norwegian-armed-forces-upgrade-enterprise-simulation-capabilities-with-bae-systems-onearcs-vbs4)
- [OneSAF (Leidos)](https://www.leidos.com/sites/leidos/files/2019-10/FS-OneSAF-Overview-Leidos.pdf)
- [LambdaMOO Wikipedia](https://en.wikipedia.org/wiki/LambdaMOO)
- [Stanford LambdaMOO history](https://cs.stanford.edu/people/eroberts/cs181/projects/controlling-the-virtual-world/history/mud.html)
- [LambdaMOO IF50](https://if50.substack.com/p/1990-lambdamoo)
- [Mozilla Hubs sunset](https://realitylearning.org/the-sun-sets-on-mozilla-hubs-and-where-to-next-for-user-generated-vr/)
- [Sansar Wikipedia](https://en.wikipedia.org/wiki/Sansar_(video_game))
- [Engadget: Linden Lab sold Sansar](https://www.engadget.com/2020-03-27-why-second-life-linden-lab-sold-sansar.html)
- [Sansar commentary (Trilo)](https://trilo.org/2020/02/28/sansar-commentary/)
- [Spatial computing headsets compared](https://qualium-systems.com/blog/ar-vr/elevating-spatial-computing-examining-technological-feats-of-apple-vision-pro-magic-leap-meta-quest-pro-and-microsoft-hololens/)
- [Vision Pro in operating room (UCSD)](https://today.ucsd.edu/story/clinical-trial-evaluating-spatial-computing-app-on-apple-vision-pro-in-operating-room)

### Section 4 — Agentic / LLM Agents
- [Roblox Code Assist full release](https://devforum.roblox.com/t/code-assist-full-release-ai-powered-code-completion/2848978)
- [Roblox Assistant docs](https://create.roblox.com/docs/assistant/guide)
- [Roblox Assistant full release](https://devforum.roblox.com/t/full-release-use-assistant-to-boost-your-productivity/3294217)
- [41% beta adoption](https://www.pocketgamer.biz/41-percent-of-beta-users-are-utilising-robloxs-ai-code-assist/)
- [NVIDIA ACE for Games](https://developer.nvidia.com/ace-for-games)
- [NVIDIA ACE CES 2024](https://hothardware.com/news/nvidia-ace-ces-2024)
- [NVIDIA ACE Autonomous Game Characters](https://www.reddit.com/r/Games/comments/1i9rzre/nvidia_redefines_game_ai_with_ace_autonomous_game/)
- [Convai × NVIDIA ACE](https://convai.com/blog/elevating-conversational-npcs-nvidia-ace-for-games-taps-convai-for-creating-humanlike-characters)
- [Inworld/Convai alternatives](https://loreweaver.ink/insights/inworld-convai-alternatives/)
- [Best Convai alternatives 2026](https://streamoji.com/blog/best-convai-alternatives-2026)
- [Generative Agents (Park et al.)](https://arxiv.org/abs/2304.03442)
- [Generative Agents GitHub](https://github.com/joonspk-research/generative_agents)
- [Voyager](https://arxiv.org/abs/2305.16291)
- [Voyager project page](https://voyager.minedojo.org/)
- [MindAgent](https://arxiv.org/abs/2309.09971)
- [MindAgent project page](https://mindagent.github.io/)
- [Awesome LLM Game Agent Papers](https://github.com/git-disl/awesome-LLM-game-agent-papers)
- [LA-RCS LLM robot control](https://arxiv.org/html/2505.18214v1)
- [MIT SceneSmith](https://news.mit.edu/2026/ai-agents-create-virtual-playgrounds-to-help-robots-get-crucial-training-data-0713)
- [Roblox WebSockets announcement](https://devforum.roblox.com/t/websockets-support-in-studio-is-now-available/4021932)
- [RoSocket GitHub](https://github.com/RoSocket/rosocket)

### Section 5 — Predictive / What-If Physics
- [Isaac Lab RL docs](https://isaac-sim.github.io/IsaacLab/main/source/overview/reinforcement-learning/index.html)
- [How Isaac Lab accelerates RL](https://docs.nvidia.com/learning/physical-ai/getting-started-with-isaac-lab/latest/train-your-first-robot-with-isaac-lab/02-how-isaac-lab-accelerates-reinforcement-learning.html)
- [Isaac Lab on SageMaker](https://aws.amazon.com/blogs/machine-learning/scale-robot-reinforcement-learning-with-nvidia-isaac-lab-on-amazon-sagemaker-ai/)
- [NVIDIA Agent Skills for Physical AI](https://blogs.nvidia.com/blog/cvpr-physical-ai-research-agent-skills/)
- [Unity ML-Agents](https://github.com/unity-technologies/ml-agents)
- [Unity ML-Agents on AWS SageMaker RL](https://aws.amazon.com/blogs/machine-learning/training-a-reinforcement-learning-agent-with-unity-and-amazon-sagemaker-rl/)
- [PPO and SAC in ML-Agents (paper)](https://ijctcm.researchcommons.org/cgi/viewcontent.cgi?article=1722&context=journal)
- [Tesla shadow mode deep dive](https://www.reddit.com/r/teslamotors/comments/aqy832/deepdive_into_autopilot_shadow_mode_verygreen_on/)
- [Tesla shadow mode (The Verge)](https://www.theverge.com/2016/10/19/13341194/tesla-autopilot-shadow-mode-autonomous-regulations)
- [Tesla shadow testing (Forbes)](https://www.forbes.com/sites/bradtempleton/2019/04/29/teslas-shadow-testing-offers-a-useful-advantage-on-the-biggest-problem-in-robocars/)
- [Bergs et al. — Digital Twin/Shadow in Manufacturing](https://www.researchgate.net/publication/354393364_The_Concept_of_Digital_Twin_and_Digital_Shadow_in_Manufacturing)
- [Oxford Insights — Twin/Shadow/Model](https://oxfordinsights.com/insights/exploring-the-concepts-of-digital-twin-digital-shadow-and-digital-model/)
- [RWTH Aachen Digital Twins](https://www.se-rwth.de/research/Digital-Twins/)
- [GE Predix future of manufacturing](https://www.researchgate.net/publication/319303600_GE_'predix'_the_future_of_manufacturing)
- [GE burned $7B on platform](https://platformengineering.org/blog/how-general-electric-burned-7-billion-on-their-platform)
- [Siemens comprehensive Digital Twin](https://www.siemens.com/en-us/company/digital-twin/comprehensive-digital-twin-for-industry/)
- [Best digital twin software 2026 (Fabrico)](https://www.fabrico.io/tr/blog/best-digital-twin-software-manufacturing/)
- [Asia Pacific digital twin market](https://www.marketsandmarkets.com/ResearchInsight/asia-pacific-digital-twin-companies.asp)
- [Speedgoat marine HIL](https://www.speedgoat.com/knowledge-center/webinars/advancing-marine-power-systems-using-hardware-in-the-loop-testing)
- [HIL for autonomous ship models](https://www.researchgate.net/publication/343132995_Hardware_in_the_Loop_Simulation_and_Control_Design_for_Autonomous_Free_Running_Ship_Models)
- [DP-HIL (Johansen et al.)](https://dynamic-positioning.com/wp-content/uploads/2025/12/control_johansen.pdf)
- [Tree-C marine HIL simulators](https://www.tree-c.nl/general/hardware-in-the-loop-simulators-for-marine-environments-explained/)
- [Open Simulation Platform — Gunnerus-DP](https://open-simulation-platform.github.io/cosim-demo-app/Gunnerus-DP)

### Section 6 — Risks & Roblox-Specific Facts
- [Roblox Studio offline (DevForum)](https://devforum.roblox.com/t/it-should-be-possible-to-use-roblox-studio-offline/153244?page=3)
- [Roblox Studio game over LAN](https://devforum.roblox.com/t/how-to-run-a-roblox-studio-game-over-lan/313822)
- [Error Code 277](https://en.help.roblox.com/hc/en-us/articles/36795858515860-Error-Code-277-Lost-connection-to-the-game-server-please-reconnect-Please-check-your-internet-connection-and-try-again)
- [Rboxlo2 GitHub](https://github.com/inposs2/Rboxlo2)
- [Roblox rate limits](https://create.roblox.com/docs/cloud/reference/rate-limits)
- [HttpService in-game requests](https://create.roblox.com/docs/cloud-services/http-service)
- [HttpService reference](https://create.roblox.com/docs/reference/engine/classes/HttpService)
- [HttpService RequestAsync](https://create.roblox.com/docs/reference/engine/classes/HttpService/RequestAsync)
- [Localhost via HttpService — Trust check failed](https://devforum.roblox.com/t/how-to-access-localhost-using-httpservice-in-roblox-studio/1496085)
- [Will HttpService work with localhost?](https://devforum.roblox.com/t/will-http-service-work-with-local-host/86806)
- [HttpService sluggish in Studio](https://devforum.roblox.com/t/httpservice-extremely-sluggish-in-studio/2658364)
- [Roblox ping test](https://pingtestlive.com/roblox)
- [Average ping by region](https://devforum.roblox.com/t/average-ping-in-your-country-or-region/3737421)
- [Lower ping in Roblox (hone.gg)](https://hone.gg/blog/lower-ping-in-roblox/)
- [Gaffer on Games — Deterministic Lockstep](https://gafferongames.com/post/deterministic_lockstep/)
- [Mieschke 2024 — Deterministic Lockstep paper](https://hdms.bsz-bw.de/files/7107/DeterministicLockstepInNetworkedGamesPaper.pdf)
- [Luau native codegen](https://luau.org/performance/)
- [Xedge32 Lua on ESP32](https://www.instructables.com/How-to-Code-With-Lua-on-ESP32-With-Xedge32/)
- [Lua-RTOS-ESP32](https://github.com/whitecatboard/Lua-RTOS-ESP32)
- [Lua vs C for embedded](https://realtimelogic.com/articles/Using-Lua-for-Embedded-Development-vs-Traditional-C-Code)
- [C/C++/Rust → Luau compiler](https://devforum.roblox.com/t/c-c-rust-in-roblox-compile-to-luau/3915431)

---

*End of AELMA Literature & Prior-Art Survey.*
