# Vessel Agent System - Knowledge Index

**Vessel:** F/V EILEEN (51' Commercial Fishing Vessel)
**Home Port:** Southeast Alaska
**Primary Fishery:** Power Trolling
**Development Start:** July 2026
**Methodology:** BMAD (Bottom-up, Multi-level, Agile Development)

---

## Quick Start for Agents

**If you are a new agent session starting work on this system:**

1. **Read this file first** (5 minutes)
2. **Read the Memory Schema** (10 minutes) - `vessel_agent_memory_schema.json`
3. **Read the Knowledge Base** (20 minutes) - `vessel_agent_knowledge_base.md`
4. **Check the 5-Year Vision** (15 minutes) - `vessel_agent_5year_vision.md`
5. **Review Current Status** (5 minutes) - Check implementation roadmap in schema

**Total Context Loading Time:** ~1 hour

---

## Knowledge Base Architecture

This directory contains the foundational knowledge for the vessel-agent system. All documents are designed to survive multiple context compactions and provide continuity across agent sessions.

### Core Documents (Read in Order)

#### 1. README.md (This File)
- Purpose: Entry point and index
- Status: Current
- Update Frequency: As needed

#### 2. vessel_agent_memory_schema.json
- Purpose: JSON schema for agent memory
- Contains: All data structures, interfaces, success metrics
- Critical For: System architecture understanding
- Status: Current (v1.0.0)
- When to Read: First thing in every new session

#### 3. vessel_agent_knowledge_base.md
- Purpose: Comprehensive technical knowledge base
- Contains: Architecture, data schemas, API definitions, implementation roadmap
- Critical For: Implementation details and technical decisions
- Status: Current (v1.0.0)
- When to Read: After schema, for deep technical understanding

#### 4. vessel_agent_5year_vision.md
- Purpose: Strategic roadmap with BMAD methodology
- Contains: 5-year breakdown, success metrics, risk mitigation
- Critical For: Long-term planning and strategic decisions
- Status: Current (v1.0.0)
- When to Read: For roadmap context and implementation prioritization

#### 5. vessel_agent_vision_synthesis.md
- Purpose: Creative vision narrative
- Contains: What the system becomes in 5 years, philosophical foundations
- Critical For: Motivation and understanding the "why"
- Status: Current (v1.0.0)
- When to Read: For inspiration and big-picture context

### Supporting Documents

#### 6. marine_visualization_design_doc.md
- Purpose: Multi-panel interface design (CAD + DAW inspired)
- Contains: Complete UI/UX specifications
- Status: Complete (70+ pages)
- Critical For: Frontend development

#### 7. marine_vessel_agent_system_analysis.md
- Purpose: Technical system analysis
- Contains: Architecture patterns, data flow, component specifications
- Status: Current
- Critical For: Deep technical implementation

#### 8. tzrawcapturesystem1.md (Reference)
- Purpose: Original conversation with Gemini about raw capture
- Contains: Foundational technical discussion
- Status: Reference document
- Critical For: Understanding capture system origins

---

## System Status Summary

### Current Phase: Phase 0 - Data Capture Emergency

**Timeline:** July 2026 (Days 1-30)
**Priority:** CRITICAL
**Focus:** Level 0 - Raw Bits (network packets, NMEA bytes)

**Completed:**
- ✅ Vessel agent framework (tzpro-agent repo)
- ✅ Basic capture system (capture_v3.py)
- ✅ NMEA bridge (nmea_bridge.py)
- ✅ Knowledge base structure (this directory)

**In Progress:**
- 🔄 Robust network packet capture
- 🔄 NMEA interpolation engine
- 🔄 Parquet storage pipeline
- 🔄 Data quality monitoring

**Pending:**
- ⏳ Physical normalization (Level 1)
- ⏳ Feature extraction (Level 2)
- ⏳ Multi-panel interface
- ⏳ Agent ecosystem

### BMAD Level Status

| Level | Name | Status | Progress |
|-------|------|--------|----------|
| 0 | Raw Bits | 🔄 In Progress | 60% |
| 1 | Physical Tensors | ⏳ Planned | 0% |
| 2 | Analytical Features | ⏳ Planned | 0% |
| 3 | Operational Intelligence | ⏳ Planned | 0% |
| 4 | Strategic Knowledge | ⏳ Planned | 0% |

---

## Critical Principles

### 1. Capture Now, Analyze Later
- Data captured in 2026 cannot be recreated in 2031
- Models will improve, but field data is non-renewable
- Capture comprehensively, analyze incrementally

### 2. Time/Location/Source Anchoring
- Every data point has temporal anchor (timestamp_ns)
- Every data point has spatial anchor (lat/lon/H3)
- Every data point has source provenance (vessel/hardware)

### 3. Bottom-Up Development (BMAD)
- Build from raw bits upward through abstraction layers
- Each level must be stable before building the next
- Clear interfaces between levels

### 4. Multi-Level Architecture
- Maintain boundaries between abstraction levels
- Well-defined contracts via interfaces
- Parallel development at different levels

### 5. Agile Iteration
- 2-week sprints with deployable output
- Continuous validation and course correction
- Each sprint contributes to long-term vision

---

## Data Flow Overview

```
PHYSICAL LAYER
  Furuno Sounder → UDP Packets → Network Card
  GPS/NMEA → Serial/UDP → NMEA Parser
        ↓
CAPTURE LAYER (Level 0)
  BPF Filter → Ring Buffer → Zero-Copy Parser
        ↓
STORAGE LAYER (Level 0-1)
  Parquet Writer → Hive Partitioning → Disk
        ↓
PROCESSING LAYER (Level 1)
  Physical Normalization → H3 Indexing → Metadata
        ↓
ANALYSIS LAYER (Level 2)
  Feature Extraction → Classification → Pattern Mining
        ↓
INTELLIGENCE LAYER (Level 3)
  Prediction → Recommendation → Decision Support
        ↓
STRATEGY LAYER (Level 4)
  Stock Assessment → Ecosystem Analysis → Scenario Planning
```

---

## Quick Reference Commands

### System Operations
```bash
# Start capture daemon
python capture_daemon.py run

# Check system status
python capture_daemon.py status

# Validate data quality
python capture_daemon.py doctor

# Single capture
python capture_daemon.py once

# Stop capture
python capture_daemon.py stop
```

### Data Queries
```sql
-- Query acoustic data for H3 cell
SELECT timestamp_ns, backscatter_db, latitude, longitude
FROM read_parquet('archive_root/year=*/month=*/*.parquet')
WHERE h3_index_uint64 = 0x8a21104523fffff
  AND timestamp_ns BETWEEN ? AND ?
ORDER BY timestamp_ns;

-- Correlate catch with acoustic signatures
SELECT c.species, AVG(a.backscatter_db) as avg_sv
FROM catch_events c
JOIN acoustic_data a ON a.h3_index_uint64 IN c.h3_cells
GROUP BY c.species;
```

---

## Key Technologies

### Data Capture
- **Python** + pypcap + memoryview (zero-copy packet processing)
- **BPF filters** (kernel-level network interception)
- **Ring buffers** (lossless ingestion)

### Data Storage
- **Apache Arrow** (columnar in-memory format)
- **Parquet** (compressed columnar storage)
- **Hive partitioning** (year/month/day/vessel_id)
- **DuckDB** (local SQL query engine)

### Spatial Processing
- **Uber H3** (hexagonal spatial indexing)
- **ICES SONAR-netCDF4** (water column data standard)
- **Sub-second interpolation** (GPS/sounder fusion)

### Visualization
- **React** + TypeScript (UI framework)
- **WebGL** (GPU-accelerated rendering)
- **D3.js** (timeline visualization)
- **MapLibre GL** (map rendering)

### Agents
- **PyTorch** (ML models)
- **ZeroMQ** (real-time messaging)
- **OpenCV** (image processing)
- **Whisper** (voice transcription)

---

## Success Metrics

### Level 0 (Raw Bits)
- Capture rate: >99.9%
- Packet loss: <0.1%
- Query performance: <1s for any day
- Uptime: >99% during operations

### Level 1 (Physical Tensors)
- Position error: <5m at 10 knots
- Depth precision: <0.5m
- Sv calibration: <1dB variance
- H3 coverage: 100%

### Level 2 (Analytical Features)
- Species accuracy: >70% for 3 species
- Biomass precision: >80%
- Bottom classification: >85%
- Thermocline detection: <2m

### Level 3 (Operational Intelligence)
- Catch prediction: >60% at 24h
- CPUE improvement: >15%
- Fleet adoption: 5+ vessels
- Alert latency: <1 minute

### Level 4 (Strategic Knowledge)
- Biomass estimate: within 20% of surveys
- Publications: 3+ peer-reviewed
- Regulatory acceptance: ADF&G integration
- Open tools: 50+ vessel adoption

---

## File Structure

```
claudetz/
├── README.md                           # This file (entry point)
├── vessel_agent_memory_schema.json     # Agent memory structure
├── vessel_agent_knowledge_base.md      # Technical knowledge base
├── vessel_agent_5year_vision.md        # 5-year roadmap (BMAD)
├── vessel_agent_vision_synthesis.md    # Creative vision narrative
├── marine_visualization_design_doc.md   # Multi-panel interface design
├── marine_vessel_agent_system_analysis.md  # Technical analysis
└── tzrawcapturesystem1.md              # Original capture conversation
```

---

## Agent Continuity Protocol

### When Starting a New Session

1. **Load Core Context** (1 hour)
   - Read README.md (this file)
   - Parse memory schema JSON
   - Review knowledge base
   - Check 5-year vision

2. **Check Implementation Status** (15 minutes)
   - Review current phase in schema
   - Check completed tasks
   - Identify pending work

3. **Continue from Last State** (ongoing)
   - Use schemas as immutable reference
   - Update roadmap status as tasks complete
   - Add new learnings to knowledge base

4. **Maintain BMAD Principles** (always)
   - Bottom-up development
   - Multi-level architecture
   - Agile iteration
   - Long-term vision

### When Making Architectural Decisions

1. **Check Schema First** - Is there already a defined structure?
2. **Review BMAD Level** - Which abstraction level does this affect?
3. **Consider Impact** - How does this affect other levels?
4. **Update Documentation** - Add decision rationale to knowledge base
5. **Validate Against Vision** - Does this align with 5-year goals?

### When Approaching Context Limits

1. **Core schemas are immutable** - Don't modify, only extend
2. **Architecture is stable** - Major changes require vision review
3. **Roadmap is updated** - Status changes are routine
4. **Agent context is ephemeral** - Regenerate from schemas next session

---

## Development Philosophy

### The Non-Renewable Resource Principle

**"Acoustic signatures of 2026 cannot be recreated in 2031."**

This principle drives every technical decision:

- **Capture everything now** - We'll figure out how to use it later
- **Store in future-proof formats** - Parquet, ICES-aligned, hardware-agnostic
- **Never overwrite** - Version increment, append, extend
- **Query-ready** - Data must be instantly accessible for unknown future queries

### The Foundation First Principle

**"Level 0 must be bulletproof before Level 1 begins."**

BMAD bottom-up development means:

- **Raw bits first** - Packet capture, parsing, storage
- **Physical tensors second** - Normalization, calibration, indexing
- **Analytical features third** - Classification, pattern mining
- **Intelligence fourth** - Prediction, recommendation
- **Strategy fifth** - Stock assessment, ecosystem understanding

### The Continuous Value Principle

**"Every 2-week sprint must produce deployable value."**

Agile iteration means:

- **Sprint 1-2**: Working packet capture
- **Sprint 3-4**: GPS/sounder fusion
- **Sprint 5-6**: Parquet storage pipeline
- **Sprint 7-8**: Data quality monitoring

Each sprint delivers something useful, even if incomplete.

---

## Contact & Context

**Vessel:** F/V EILEEN
**Captain:** Casey
**Location:** Southeast Alaska
**Methodology:** BMAD
**Horizon:** 2031

**System Status:** Phase 0 (Data Capture Emergency)
**Next Milestone:** Complete Level 0 implementation (30 days)
**Current Focus:** Network packet capture, NMEA interpolation, Parquet storage

---

**This README is maintained as the single entry point for all agent sessions working on the vessel agent system. Update this file when architectural milestones are reached, but keep the core structure stable for continuity.**

---

*Version: 1.0.0*
*Last Updated: 2026-07-24*
*Next Review: After Phase 0 completion*
*Status: Foundation Complete → Implementation In Progress*
