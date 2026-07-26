# Vessel Agent Research Synthesis - July 2026

**Date:** 2026-07-24
**Vessel:** F/V EILEEN (51' Commercial Fishing Vessel)
**Location:** Southeast Alaska
**Purpose:** Synthesis of GitHub research for spatial, temporal, and agentic IDE systems

---

## Executive Summary

This document synthesizes comprehensive research across SuperInstance repositories, maritime VaaS platforms, spatial-temporal data processing libraries, and agentic IDE frameworks. The findings reveal clear integration paths for the vessel agent system currently deployed on F/V EILEEN in SE Alaska.

---

## 1. SuperInstance Ecosystem Analysis

### Core Repositories (Production Ready)

#### boat-agent/ ⭐ DEPLOYED ON F/V EILEEN
**Status:** Production deployed (v0.1.0 Foundation Complete)
**Architecture:** Rust microkernel with 5 primitives (Bus, State, Envelope, Playbooks, Memory)
**Deployment:** Sounder watch (LEVEL 2) operational on F/V EILEEN
**Key Features:**
- Agent-centric design (agents operate, human supervises)
- Safety envelope with 7-check pipeline
- Deterministic replay architecture
- Local-first memory with opportunistic cloud sync
- 31/31 tests passing

**Integration with Vessel Agent System:**
- **Direct Integration:** boat-agent IS the vessel operating system
- **Data Flow:** NMEA → Bus → Envelope → Playbooks → Agents → Human
- **Relevance:** Foundation for all spatial/temporal data capture

#### constrainttheory/
**Purpose:** Geometric substrate for cellular agents
**Tech Stack:** Rust (2,244 LOC, 68/68 tests)
**Integration:** Spatial reasoning for fishing grounds optimization
**Use Case:** Geometric constraint satisfaction for gear deployment
**Value:** Mathematical rigor in spatial decisions

#### claw/
**Purpose:** Cellular agent engine
**Tech Stack:** Rust (15,686 LOC, 163/163 tests)
**Integration:** Modular vessel subsystem agents (engine, sounder, GPS, autopilot)
**Use Case:** Independent cellular agents with fault tolerance
**Value:** Replaces Python playbooks with high-performance Rust agents

#### dodecet-encoder/
**Purpose:** 12-bit geometric encoding
**Tech Stack:** Rust (4,066 LOC, 170/170 tests)
**Integration:** Compact position/state encoding for blackbox logging
**Use Case:** Memory compression, efficient pattern matching
**Value:** Reduced storage requirements for long-term data capture

#### spreadsheet-moment/
**Purpose:** Agentic spreadsheet platform
**Tech Stack:** TypeScript (~5,000 LOC, 192/268 tests)
**Integration:** Vessel data visualization in familiar spreadsheet interface
**Use Case:** Catch history, maintenance logs, financial tracking
**Value:** Low barrier to entry for captains

### Supporting SuperInstance Repositories

#### tzpro-agent/
**Status:** Production deployed on F/V EILEEN
**Components:**
- NMEA bridge (GPS/sounder parsing)
- Sounder analyzer (real-time sonar interpretation)
- Voice catch (captain observation transcription)
- Capture tray (screen recording with metadata)
- Memory system (catch logging, vocabulary learning)

**Integration Path:**
- Current: Runs independently, logging to vessel_state.jsonl
- Future: Emit events on boat-agent bus protocol
- Value: Working software provides immediate data capture

#### ratatui/ (formerly open-tui)
**Purpose:** Rust TUI (Terminal User Interface)
**Integration:** Vessel terminal interfaces for low-bandwidth situations
**Value:** Offline operation when GUI unavailable

#### equilibrium-tokens/
**Purpose:** Constraint-grammar system for human-machine conversation
**Integration:** Voice interaction systems for vessel agents
**Value:** Structured voice command processing

---

## 2. Maritime Technology Integration Opportunities

### HIGH PRIORITY - Immediate Integration

#### AeroRust/nmea ⭐ TOP PICK
**Repository:** https://github.com/AeroRust/nmea
**Features:**
- 38 NMEA sentence types supported
- AIS decoder (16 message types)
- Zero dependencies
- Bidirectional (parse + encode)

**Integration:**
- Replace custom NMEA parsing in boat-agent sounder driver
- Add AIS message decoding for fleet awareness
- **Impact:** Improved reliability, reduced maintenance
- **Effort:** Low (drop-in replacement)

#### SignalK Server ⭐ MARINE DATA STANDARD
**Repository:** https://github.com/SignalK/signalk-server
**Features:**
- Universal marine data exchange (JSON-based)
- Unifies NMEA 0183, NMEA 2000, SeaTalk
- IoT and embedded device support
- Industry standard adoption

**Integration:**
- Create boat-agent to SignalK translation layer
- Enable interoperability with marine electronics ecosystem
- **Impact:** Hardware compatibility, ecosystem integration
- **Effort:** Medium (bridge layer)

#### NOAA AFSC Repositories ⭐ ALASKA-SPECIFIC
**Organization:** https://github.com/noaa-afsc (48 repositories)
**Features:**
- Alaska-focused fisheries research
- Groundfish assessment data
- Data-limited methods for Tier 6 species
- Regulatory compliance information

**Integration:**
- Integrate Alaska fisheries data into Analyst agent
- Add regulatory compliance checks
- **Impact:** Legal compliance, local knowledge
- **Effort:** Medium (data integration)

### MEDIUM PRIORITY - Season 2026

#### OpenCPN + OpenPlotter
**Repository:** https://github.com/opencpn/OpenCPN
**Features:**
- Cross-platform chart plotter
- BSB raster charts, S57 vector ENC
- GPS/GPSD position input
- Helm station design

**Integration:**
- Connect boat-agent state to OpenCPN display
- Show agent suggestions on chart plotter
- **Impact:** Enhanced situational awareness
- **Effort:** Medium (UI integration)

#### Global Fishing Watch
**Organization:** https://github.com/globalfishingwatch
**Features:**
- Global fishing pattern database
- Satellite AIS data processing
- Fishing activity detection
- Interactive global map

**Integration:**
- Add fishing grounds intelligence to memory
- Inform fishing location decisions
- **Impact:** Data-driven fishing decisions
- **Effort:** Low (API integration)

#### Monitorfish
**Repository:** https://github.com/MTES-MCT/monitorfish
**Features:**
- French fisheries monitoring system
- Real-time vessel monitoring
- Catch reporting
- Compliance tracking

**Integration:**
- Study regulatory compliance architecture
- Adopt applicable features for US fisheries
- **Impact:** Regulatory preparation
- **Effort:** High (feature comparison)

---

## 3. Agentic IDE Integration

### Eclipse Theia ⭐ PRIMARY RECOMMENDATION

**Repository:** https://github.com/eclipse-theia/theia
**Status:** Production-Ready, Vendor-Neutral Open Source
**License:** Eclipse Public License 2.0

**Key Features:**
- AI-native architecture (Theia AI framework)
- VS Code extension protocol support
- Deep AI integration (throughout entire IDE)
- Multi-language support (cloud & desktop)
- Modular architecture for custom tooling

**2026 Release Status:**
- Theia AI 1.66 (December 2025): Optional mode support
- 2026-05 Release: AI coding features graduated to stable
- Active work on AI-Agent-Skills support

**Integration with Vessel Agent System:**
- **Deployment:** Docker container on vessel workstation
- **Customization:** TypeScript extensions for vessel-specific features
- **Offline:** Excellent - designed for both cloud and desktop
- **Voice:** Extensible via VS Code voice extensions

**Value Proposition:**
- Vendor-neutral (no lock-in)
- VS Code extension compatibility
- TypeScript enables Rust integration
- Open-source governance

### Agent Voice (Voice Interface)

**Repository:** https://github.com/PlagueHO/agent-voice
**Status:** Active Development
**License:** Apache 2.0

**Key Features:**
- Full-duplex voice control
- Hands/eyes-free operation
- AI Manager Agent orchestration
- Real-time streaming with Azure AI

**Adaptation for Vessel Use:**
- Replace Azure services with local equivalents:
  - Whisper for STT
  - Piper TTS for synthesis
- Natural conversation for planning/specification
- Integration: Theia extension

**Value:**
- Purpose-built for hands-free vessel operation
- Ideal for navigation, maintenance situations
- Accessibility-first design

### Cline (Multi-Agent Orchestration)

**Repository:** https://github.com/cline/cline
**Status:** Production-Ready, Highly Active
**Stars:** 15,000+ | Installs: 4.3M+

**Key Features:**
- Multi-agent teams (coordinator + specialists)
- Local model support (Ollama, LM Studio)
- CLI mode for headless operation
- Scheduled automations (daily reports, health checks)
- MCP server integration

**Integration:**
- CLI mode perfect for headless vessel workstation
- Multi-agent coordination for vessel operations
- Local model support for offline operation
- Kanban board for visual task management

**Value:**
- Complete offline operation
- Multi-agent coordination
- Production-ready with active development

---

## 4. Complete Technology Stack for F/V EILEEN

### Recommended Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    F/V EILENE VESSEL SYSTEM                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                    ECLIPSE THEIA (IDE)                        │ │
│  │  • Markdown/Code Editor (Primary UI)                          │ │
│  │  • Agent Voice Extension (Hands-free operation)              │ │
│  │  • Rust Backend Integration                                  │ │
│  │  • MCP Clients (Vessel Systems)                              │ │
│  └────────────────────────────┬──────────────────────────────────┘ │
│                             │                                       │
│  ┌────────────────────────────▼──────────────────────────────────┐ │
│  │                    BOAT-AGENT KERNEL (Rust)                   │ │
│  │  • Bus (3 lanes: Critical, Telemetry, Narrative)              │ │
│  │  • Safety Envelope (7-check pipeline)                         │ │
│  │  • State Management (Deterministic reducer)                   │ │
│  │  • Playbooks (AI-authored control bundles)                   │ │
│  │  • Memory (Local-first, versioned)                            │ │
│  └────────────────────────────┬──────────────────────────────────┘ │
│                             │                                       │
│  ┌────────────────────────────▼──────────────────────────────────┐ │
│  │                 AGENTS (5 Roles)                               │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐          │ │
│  │  │  Operator    │ │  Engineer    │ │  Analyst     │          │ │
│  │  │  (Real-time) │ │  (Playbooks) │ │  (Mining)    │          │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘          │ │
│  │  ┌──────────────┐ ┌──────────────┐                          │ │
│  │  │  Auditor     │ │  Fleet       │                          │ │
│  │  │  (Safety)    │ │  (Learning)  │                          │ │
│  │  └──────────────┘ └──────────────┘                          │ │
│  └────────────────────────────┬──────────────────────────────────┘ │
│                             │                                       │
│  ┌────────────────────────────▼──────────────────────────────────┐ │
│  │              DRIVERS & INTEGRATION LAYER                      │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐          │ │
│  │  │ AeroRust/nmea│ │  SignalK     │ │  Cline CLI   │          │ │
│  │  │ (NMEA/AIS)   │ │  (Marine)    │ │  (Agents)    │          │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘          │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐          │ │
│  │  │  NOAA AFSC   │ │  OpenCPN     │ │  tzpro-agent │          │ │
│  │  │  (Fisheries) │ │  (Charts)    │ │  (Working)   │          │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘          │ │
│  └────────────────────────────┬──────────────────────────────────┘ │
│                             │                                       │
│  ┌────────────────────────────▼──────────────────────────────────┐ │
│  │              HARDWARE & SENSORS                               │ │
│  │  GPS, Sounder, Compass, Engine, Autopilot, Jog Lever          │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### Offline/Local Deployment

```
┌─────────────────────────────────────────────────────────────────┐
│                    VESSEL WORKSTATION                            │
│  (No internet required for full operation)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐      ┌──────────────────┐                  │
│  │   Eclipse Theia  │      │  Boat-Agent Core │                  │
│  │   (IDE Platform) │◄────►│  (Rust Kernel)   │                  │
│  └──────────────────┘      └──────────────────┘                  │
│           │                         │                             │
│           │                         │                             │
│  ┌────────▼─────────┐      ┌────────▼─────────┐                  │
│  │ Local Services   │      │  Local Models    │                  │
│  │                  │      │                  │                  │
│  │  • Whisper (STT)│      │  • Ollama        │                  │
│  │  • Piper TTS    │      │  • LM Studio     │                  │
│  │  • SignalK      │      │  • Local LLMs    │                  │
│  │  • NMEA Server  │      │                  │                  │
│  └──────────────────┘      └──────────────────┘                  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Integration Roadmap

### Phase 0: Foundation (COMPLETE ✅)
- ✅ boat-agent kernel deployed on F/V EILEEN
- ✅ tzpro-agent providing working software
- ✅ Sounder watch (LEVEL 2) operational
- ✅ Safety envelope with 7-check pipeline
- ✅ 31/31 tests passing

### Phase 1A: Core Theia Setup (Week 1-2)
- 🔄 Install and configure Theia server
- 🔄 Set up vessel agent workspace
- 🔄 Install base extensions (Markdown, JSON LSP)
- 🔄 Configure file system access to Parquet archive
- 🔄 Test web client access

### Phase 1B: Chatbot Panel (Week 3-4)
- 📋 Develop vessel-agent-chatbot-panel extension
- 📋 Implement collapsible panel UI
- 📋 Connect to boat-agent backend API
- 📋 Implement context-aware behavior
- 📋 Add basic natural language queries

### Phase 1C: NMEA Integration (Week 5-6)
- 📋 Integrate AeroRust/nmea into boat-agent
- 📋 Replace custom NMEA parsing
- 📋 Add AIS message decoding
- 📋 Test with F/V EILEEN GPS/sounder
- 📋 Validate signal quality

### Phase 1D: SignalK Bridge (Week 7-8)
- 📋 Set up SignalK Server
- 📋 Create boat-agent to SignalK translation
- 📋 Enable interoperability with marine electronics
- 📋 Test ecosystem integration

### Phase 1E: Phone Support (Week 9-10)
- 📋 Develop vessel-agent-voice-io extension
- 📋 Implement STT/TTS integration (Whisper + Piper)
- 📋 Create simplified phone UI
- 📋 Add voice command recognition
- 📋 Test offline mode

### Phase 2: Advanced Integration (Season 2026)
- 📋 NOAA AFSC data integration
- 📋 OpenCPN chart plotting
- 📋 Global Fishing Watch intelligence
- 📋 Monitorfish compliance features

### Phase 3: Ecosystem Integration (2026+)
- 📋 constrainttheory spatial reasoning
- 📋 claw cellular agents
- 📋 dodecet-encoder compression
- 📋 spreadsheet-moment visualization

---

## 6. Unique Value Proposition

### boat-agent vs. Traditional Maritime Systems

| Feature | boat-agent | Traccar | Monitorfish | Global Fishing Watch |
|---------|-----------|---------|-------------|---------------------|
| **Voice Interaction** | ✅ Yes | ❌ No | ❌ No | ❌ No |
| **Sounder Watch** | ✅ Yes | ❌ No | ❌ No | ❌ No |
| **Local-First** | ✅ Yes | ⚠️ Mixed | ❌ No | ❌ No |
| **Safety Envelope** | ✅ Yes | ⚠️ Basic | ⚠️ Basic | ❌ No |
| **Rust Core** | ✅ Yes | ❌ Java | ❌ Unknown | ❌ Unknown |
| **Agent-Centric** | ✅ Yes | ❌ No | ❌ No | ❌ No |
| **Alaska Fishing** | ✅ F/V EILEEN | ❌ Generic | ❌ France | ❌ Global |
| **Offline Operation** | ✅ Full | ⚠️ Partial | ❌ No | ❌ No |
| **Human Supervision** | ✅ Core | ❌ No | ❌ No | ❌ No |
| **Deterministic** | ✅ Replay | ❌ No | ❌ No | ❌ No |

### SuperInstance Ecosystem Advantages

**No existing system combines:**
1. Agent-centric architecture (agents operate, human supervises)
2. Safety-first design (7-check envelope, human veto, watchdog)
3. Local-first memory (vessel intelligent offline, cloud as amplifier)
4. Voice interaction (hands-free vessel operation)
5. Real-world deployment (working fishing vessel in SE Alaska)
6. SuperInstance cellular programming foundation

---

## 7. Success Metrics

### Phase 1 Success Criteria

**Technical:**
- ✅ Theia server running on boat workstation
- ✅ Boat-agent kernel operational (31/31 tests)
- ✅ AeroRust/nmea integrated
- ✅ SignalK bridge functional
- ✅ Phone voice I/O operational

**User Experience:**
- ✅ Captain can create daily catch summary
- ✅ Captain can query agent for analysis
- ✅ Captain can drop marks in TZ Pro
- ✅ Captain can view timeline of events
- ✅ Captain can use voice commands from phone

**Performance:**
- ✅ Chatbot response latency < 2s
- ✅ Markdown generation < 5s
- ✅ TZ Pro injection < 1s
- ✅ Timeline load < 3s for daily view
- ✅ Voice command recognition > 90%

**Data Quality:**
- ✅ Capture rate > 99.9%
- ✅ Packet loss < 0.1%
- ✅ Query performance < 1s for any day
- ✅ Uptime > 99% during operations

---

## 8. Key Research Findings

### Spatial Data Processing

**Top Libraries:**
1. **AeroRust/nmea** - NMEA/AIS parsing (Rust)
2. **tools4msp** - Marine spatial planning (Python)
3. **marine-gis topic** - Coastal & marine analysis

**Integration:**
- AeroRust/nmea immediate (driver replacement)
- tools4msp long-term (fishing grounds optimization)

### Temporal Data Processing

**Top Libraries:**
1. **Cline** - Multi-agent orchestration with local models
2. **AIS_project** - Time series analysis for vessel behavior
3. **LangGraph Studio** - Visual debugging for temporal agents

**Integration:**
- Cline immediate (multi-agent coordination)
- AIS_project long-term (pattern recognition)

### Agentic IDEs

**Top Tools:**
1. **Eclipse Theia** - Vendor-neutral, AI-native
2. **Agent Voice** - Full-duplex voice control
3. **Cline** - Local model support, CLI mode

**Integration:**
- Theia as primary platform
- Agent Voice adapted for local STT/TTS
- Cline for multi-agent orchestration

### Maritime Standards

**Top Standards:**
1. **SignalK** - Universal marine data exchange
2. **OpenCPN** - Chart plotting standard
3. **NOAA AFSC** - Alaska fisheries data

**Integration:**
- SignalK as marine data bridge
- OpenCPN for navigation visualization
- NOAA AFSC for compliance

---

## 9. Immediate Next Steps

### This Week (Priority Order)

1. **Integrate AeroRust/nmea** into boat-agent
   - Replace custom NMEA parsing
   - Add AIS decoding
   - Test with F/V EILEN sounder

2. **Set up Eclipse Theia** on test workstation
   - Docker deployment
   - Workspace configuration
   - Extension testing

3. **Configure local LLM** (Ollama/LM Studio)
   - Test local model performance
   - Evaluate boat workstation capacity
   - Select appropriate models

### Next 30 Days

4. **Develop Theia extensions** (Phase 1A-1B)
   - Chatbot panel
   - Markdown templates
   - TZ Pro injector

5. **Complete NMEA integration** (Phase 1C)
   - AeroRust/nmea testing
   - Signal validation
   - AIS decoding

6. **Set up SignalK bridge** (Phase 1D)
   - SignalK Server deployment
   - Boat-agent translation layer
   - Ecosystem testing

### Season 2026

7. **Advanced features** (Phase 2)
   - NOAA AFSC integration
   - OpenCPN display
   - Global Fishing Watch data
   - Phone voice I/O

8. **SuperInstance integration** (Phase 3)
   - constrainttheory spatial reasoning
   - claw cellular agents
   - dodecet-encoder compression
   - spreadsheet-moment visualization

---

## 10. Conclusion

The research reveals a clear path forward for the vessel agent system on F/V EILEEN:

**Immediate high-value integrations:**
1. **AeroRust/nmea** - Industry-standard NMEA/AIS parsing
2. **SignalK Server** - Marine data ecosystem bridge
3. **Eclipse Theia** - Agent-native IDE platform
4. **Cline** - Multi-agent orchestration

**Unique competitive advantage:**
- boat-agent's agent-centric, safety-first architecture
- Voice interaction for hands-free vessel operation
- Local-first memory with offline operation
- Real-world deployment on working fishing vessel
- SuperInstance cellular programming foundation

**No existing system combines these features.** The vessel agent system represents a genuine innovation in autonomous maritime systems: instead of humans operating with AI assistance, AI agents operate with human supervision.

The integration path is incremental, practical, and aligned with the BMAD methodology. Each phase delivers deployable value while building toward the 5-year vision of a complete fleet intelligence ecosystem.

---

**"The ocean forgets nothing. The vessel agent remembers everything."**

---

**Document Version:** 1.0
**Date:** 2026-07-24
**Status:** Research Complete → Integration Planning
**Vessel:** F/V EILEEN, US-AK-FVCATCHER-01
**Methodology:** BMAD (Bottom-up, Multi-level, Agile Development)

---

## Sources

### SuperInstance Repositories
- https://github.com/SuperInstance/boat-agent
- https://github.com/SuperInstance/constrainttheory
- https://github.com/SuperInstance/claw
- https://github.com/SuperInstance/dodecet-encoder
- https://github.com/SuperInstance/spreadsheet-moment
- https://github.com/SuperInstance/SuperInstance-papers

### Maritime Technology
- https://github.com/AeroRust/nmea
- https://github.com/SignalK/signalk-server
- https://github.com/opencpn/OpenCPN
- https://github.com/noaa-afsc (48 repositories)
- https://github.com/MTES-MCT/monitorfish
- https://github.com/globalfishingwatch

### Agentic IDEs
- https://github.com/eclipse-theia/theia
- https://github.com/PlagueHO/agent-voice
- https://github.com/cline/cline

### Spatial/Temporal Analysis
- https://github.com/CNR-ISMAR/tools4msp
- https://github.com/ishan-chaudhary/AIS_project
- https://github.com/topics/marine-gis

### VaaS & Maritime Platforms
- https://github.com/traccar/traccar
- https://github.com/josna-14/Maritime_Vessel_Tracking
- https://github.com/erikk03/seeSea

### Agent Frameworks
- https://github.com/crewAIInc/crewAI
- https://github.com/microsoft/autogen
- https://github.com/langchain-ai/langgraph-studio

### Additional Research
- C:\Users\casey\boat-agent (local analysis)
- C:\Users\casey\tzpro-agent (referenced)
- Existing knowledge base documents
