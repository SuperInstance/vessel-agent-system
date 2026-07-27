# AELMA Architecture

**Agent-Engine Linked Marine Architecture** — a hardware-in-the-loop digital twin for a commercial fishing vessel. This is the live implementation of the design described in `AELMA_synthesis_memo.md` (parent dir). Phase 1 is the vessel-side core: a LAN-deployable system that ingests NMEA telemetry, maintains a live vessel state with progressive bathymetry, and renders a 3D view in any browser.

---

## Design Principles

1. **Air-gap first.** Every component runs on the vessel LAN with zero internet dependency. No cloud auth, no phone-home. A Raspberry Pi 5 + a tablet is a complete deployment.
2. **Standard library Python.** No pydantic, no Django, no Kafka. asyncio + websockets + stdlib. A captain with a Python tutorial can read every line.
3. **Schemas are contracts.** Every wire format is a JSON Schema in `schema/`. Components are independently replaceable as long as they honor the schema.
4. **Simulator substitutes for hardware.** The entire system can be developed and tested without a single physical sensor. Plug in real NMEA 0183 later by changing one CLI flag.
5. **Progressive world refinement.** The bathymetry layer starts empty and gets denser every time the vessel crosses water. This is the "best-current-render" vision from the synthesis memo — every sounding is non-renewable evidence.

---

## Component Topology

```
┌──────────────────────────────────────────────────────────────────┐
│ VESSEL LAN (no internet required)                                │
│                                                                  │
│  ┌──────────────┐    NMEA 0183 text    ┌──────────────┐          │
│  │  simulator   │ ────────────────────▶│    bridge    │          │
│  │  (or real    │   TCP :8001           │              │          │
│  │   hardware)  │                       │  Parses +    │          │
│  └──────────────┘                       │  quality-    │          │
│                                         │  checks      │          │
│                                         └──────┬───────┘          │
│                                                │                  │
│                                                │ TelemetryPacket  │
│                                                │ (JSON)           │
│                                                ▼                  │
│                                         ┌──────────────┐          │
│                                         │     twin     │          │
│                                         │              │          │
│                                         │  VesselState │          │
│                                         │  + Bathymetry│          │
│                                         │   Grid (TSDF)│          │
│                                         └──────┬───────┘          │
│                                                │                  │
│                                                │ VesselState      │
│                                                │  Snapshot (JSON) │
│                                                ▼                  │
│  ┌──────────────┐   WebSocket :8090    ┌──────────────┐          │
│  │   viewer     │ ◀────────────────────│  (any LAN    │          │
│  │  (browser)   │                       │   client)    │          │
│  └──────────────┘                       └──────────────┘          │
└──────────────────────────────────────────────────────────────────┘
```

---

## Data Flow (one depth reading)

1. **Sounder** emits `$SDDPT,73.2,-1.5,*3A` over NMEA 0183 (or the simulator does, during dev).
2. **Bridge** TCP-receiver picks it up, calls `nmea.parse("$SDDPT,...")`, which returns `[{channel:"depth_m", value:73.2, source:"nmea0183", sentence:"$SDDPT,..."}]`.
3. **Bridge** assigns `timestamp_ns = time.time_ns()`, runs `quality.check("depth_m", 73.2)` → `"good"`, assembles a full `TelemetryPacket` (schema: `schema/telemetry_packet.schema.json`), and broadcasts as JSON to every connected WebSocket subscriber.
4. **Twin** receives the packet. Calls `state.apply_packet(packet)` (updates the `depth_m` channel). Because channel is `depth_m`, also calls `bathymetry.fuse(state.pose.lat, state.pose.lon, 73.2, packet.timestamp_ns)` — quantizes (lat, lon) into a 10m cell, updates the running average depth and sample count.
5. **Twin** broadcast loop ticks every 1 second: `state.snapshot()` produces a `VesselStateSnapshot` (schema: `schema/vessel_state.schema.json`) including a downsampled bathymetry viewport, JSON-encodes, sends to all viewer WS clients on :8090.
6. **Viewer** receives snapshot, updates its Three.js scene: moves the vessel mesh, adds/updates points in the bathymetry cloud, updates sidebar readouts.

End-to-end latency target: under 100 ms (sounder → screen).

---

## Why Python instead of Godot for Phase 1

The synthesis memo recommended Godot 4 as the headless core. We're starting in Python for Phase 1 because:

- **Faster iteration** for the bathymetry/state/schema work — no build step, no engine reload
- **Direct integration** with the existing vessel-quest scoring engine (which is Python)
- **Trivial deployment** on a Raspberry Pi 5 with no GPU
- **All the heavy lifting** (TSDF, dead-reckoning, haversine) is pure Python anyway

Godot remains the plan for Phase 2 — once the data model and wire formats are stable, porting the twin to Godot (or Bevy) is a clean substitution at the `TelemetryPacket`/`VesselStateSnapshot` boundary. The schemas are the contract.

---

## Phase 1 Scope

| Component | Status | Location |
|---|---|---|
| Schemas (telemetry, vessel_state, bathymetry_voxel) | Done | `schema/` |
| Bridge (NMEA → TelemetryPacket) | Building (parallel) | `bridge/` |
| Twin (state + bathymetry + broadcaster) | Building (parallel) | `twin/` |
| Simulator (mock F/V EILEEN trip) | Building (parallel) | `simulator/` |
| Viewer (Three.js browser client) | Building (parallel) | `viewer/` |
| Integration tests | Pending | `tests/` |
| Docker compose | Pending | `docker-compose.yml` |

## Phase 2+ (out of scope here, see `AELMA_synthesis_memo.md`)

- NMEA 2000 ingestion (currently NMEA 0183 only)
- Signal K integration
- Cesium World Bathymetry basemap
- Drone photogrammetry overlay
- 3D Gaussian Splatting underwater reconstruction
- Human-feedback stylization loop (the publishable novelty)
- Roblox shoreside experience (replay, training, son game-mode)
- Divination sandbox (Isaac Sim / Unity ML-Agents)
- Agent spatial queries (workspace:GetPartsInPart equivalent)
- Regulatory engagement (USCG PL 22-01, ABS Guide 323)

---

## Operational Notes

### Running on a Raspberry Pi 5

```
bridge      — Python 3.11+, ~30MB RAM, ~1% CPU at 50Hz
twin        — Python 3.11+, ~80MB RAM (depends on bathymetry size), ~3% CPU
viewer      — Served from any HTTP server; rendering happens on the client device
simulator   — Dev only; not deployed on the real vessel
```

Total power draw: under 5W for the twin stack on a Pi 5. Fits comfortably on the vessel's 12V house bank with a small inverter or direct 5V USB-C.

### NMEA 0183 wiring (real hardware)

The bridge listens on TCP :8001 for plain-text NMEA 0183. To connect real hardware:

- **USB-to-serial adapter** (e.g., FTDI RS-422) → `socat TCP-CONNECT:localhost:8001 /dev/ttyUSB0,b9600,raw`
- **Networked MFD** (Garmin, Furuno, Simrad) → point its NMEA-0183-over-IP output at the bridge host :8001
- **Actisense W2K-1 / Yacht Devices YDEN-02** → bridge becomes a subscriber of those gateways

NMEA 2000 support arrives in Phase 2 via Signal K Server (`signalk-server-node`) running alongside, forwarding to the bridge.

---

## File Layout

```
aelma/
├── schema/
│   ├── telemetry_packet.schema.json    # bridge → twin wire format
│   ├── vessel_state.schema.json        # twin → viewer wire format
│   ├── bathymetry_voxel.schema.json    # twin internal storage
│   ├── shared_brief.md                 # build briefs (parallel builders)
│   ├── shared_twin_brief.md
│   ├── shared_sim_brief.md
│   └── shared_viewer_brief.md
├── bridge/                             # NMEA → TelemetryPacket
├── twin/                               # state + bathymetry + broadcaster
├── simulator/                          # mock F/V EILEEN trip
├── viewer/                             # Three.js browser client
├── tests/                              # integration tests
├── docs/
│   └── ARCHITECTURE.md                 # this file
├── docker-compose.yml                  # one-command stack
└── README.md                           # quickstart
```
