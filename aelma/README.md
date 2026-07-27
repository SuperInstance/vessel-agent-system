# AELMA — Agent-Engine Linked Marine Architecture

A hardware-in-the-loop digital twin for the **F/V EILEEN**, a 51-foot commercial fishing vessel home-ported in Sitka, Alaska. This is the live Phase 1 implementation of the design in [`../AELMA_synthesis_memo.md`](../AELMA_synthesis_memo.md).

**Phase 1 goal:** a complete vessel-side stack that ingests NMEA 0183 telemetry, maintains a live vessel state with progressive bathymetry, and renders a 3D view in any browser — all running on the vessel LAN with zero internet dependency.

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
python -m simulator --duration-min 60 --speedup 1

# Terminal 3 — twin (state + bathymetry + viewer broadcaster)
cd aelma/twin
python -m twin --bridge-url ws://localhost:8000 --viewer-port 8090

# Terminal 4 — viewer (static file server)
cd aelma/viewer
python serve.py --port 8080
```

Open `http://localhost:8080` in any browser (Chrome/Safari/Firefox). You should see:
- The F/V EILEEN as an orange boat hull + cabin, moving southwest
- A blue water plane
- Bathymetry points appearing under the vessel as it trolls (warm orange when shallow, green mid-depth, blue when deep)
- A sidebar with live depth, position, wind, and water temperature
- Voxel count growing in the corner

Connect from an iPad on the same LAN: `http://<your-laptop-ip>:8080`. Touch drag to rotate, pinch to zoom.

---

## Docker Compose (one command)

```bash
cd aelma
docker compose up
# Then open http://localhost:8080
```

Brings up all four services. Use `--build` after editing code.

---

## What each component does

| Component | Role | Tech |
|---|---|---|
| `simulator/` | Emits realistic NMEA 0183 sentences simulating F/V EILEEN trolling near Sitka | Python stdlib |
| `bridge/` | TCP :8001 receives NMEA text; parses, quality-checks, serves as JSON TelemetryPackets over WS :8000 | Python asyncio + websockets |
| `twin/` | WS client of bridge; maintains vessel state + progressive TSDF bathymetry; serves VesselStateSnapshots to viewers over WS :8090 | Python asyncio |
| `viewer/` | Browser client; Three.js 3D scene with vessel, water, bathymetry points; live sidebar readouts | HTML/CSS/JS, Three.js CDN |
| `schema/` | JSON Schemas that are the contracts between components | JSON Schema Draft 2020-12 |

---

## Wiring real hardware (Phase 1 → Phase 2 upgrade path)

Replace the simulator with real NMEA 0183 from your sounder, GPS, wind instrument:

```bash
# USB-to-serial from your MFD or instrument bus
socat TCP-CONNECT:localhost:8001 /dev/ttyUSB0,b9600,raw,cr

# Or from a networked chartplotter (Garmin BlueTop, Furuno NavNet, etc.)
# Point its NMEA-0183-over-IP output at <bridge-host>:8001
```

NMEA 2000 arrives via Signal K Server (Phase 2) — `signalk-server-node` translates N2K to Signal K JSON, which the bridge can ingest as a sibling source.

---

## Design philosophy

1. **Air-gap first.** No cloud, no phone-home. A Raspberry Pi 5 + tablet is a complete deployment.
2. **Standard library Python.** A captain with a Python tutorial can read every line.
3. **Schemas are contracts.** Components are independently replaceable as long as they honor the JSON Schemas.
4. **Simulator substitutes for hardware.** Develop and test the whole stack with zero sensors attached.
5. **Progressive world refinement.** Every sounding is non-renewable evidence — log it, fuse it, never delete it.

---

## Where this is going

Phase 1 is the foundation. See [`../AELMA_synthesis_memo.md`](../AELMA_synthesis_memo.md) for the full roadmap:

- **Phase 2:** NMEA 2000, Signal K, Cesium World Bathymetry basemap, drone photogrammetry overlay
- **Phase 3:** Human-feedback stylization loop ("coral good, dogfish wrong") — the publishable academic contribution
- **Phase 4:** Divination sandbox (NVIDIA Isaac Sim or Unity ML-Agents) for predictive what-if sims
- **Phase 5:** Roblox shoreside experience (replay past trips, son game-mode, training)
- **Phase 6:** Agent spatial queries and actuation under regulatory frameworks (USCG PL 22-01, ABS Guide 323, DNV AROS)

---

## Reference

- Architecture detail: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- Schemas: [`schema/`](schema/)
- Research foundation: [`../AELMA_synthesis_memo.md`](../AELMA_synthesis_memo.md), [`../aelma_literature_survey.md`](../aelma_literature_survey.md)
