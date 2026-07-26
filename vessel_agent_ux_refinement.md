# Vessel Agent UX Refinement - 3-Viewer Architecture

**Date:** 2026-07-24
**Status:** UX Architecture Clarified
**MVP Focus:** Theia-based Markdown/Code Editor with TZ Pro Integration

---

## Overview

The vessel agent UI consists of **3 viewers** (accessible as tabs or windows) plus a **collapsible chatbot panel** that can appear on either side. This is a more practical, boat-friendly approach than simultaneous multi-panel displays.

---

## The 3 Viewers

### 1. Markdown/Code Editor (Front View - Cross-Section Analysis)

**Metaphor:** IDE/Code Editor - Analysis as first-class objects

**Purpose:**
- Group and organize analysis results as structured documents
- First-class citizens: Markdown documents, JSON data structures, analysis reports
- Primary interface for human-AI collaboration

**Technology:**
- **Theia IDE** (open-source, agent-native, web-based)
- Serves from boat workstation or cloud instance
- Edge devices connect headless
- Phones connect with minimal resources (STT/TTS only)

**Example Content:**
```markdown
# Daily Catch Summary - July 23, 2026

## Species Breakdown
- King Salmon: 5 fish, avg 12.4lbs
- Chum Salmon: 23 fish, avg 8.2lbs

## Acoustic Signatures Detected
| Time | Position | Depth | Confidence | Species |
|------|----------|-------|------------|---------|
| 14:32:15 | 56.3°N, -134.5°W | 35fm | 94% | Chum |
| 14:45:22 | 56.31°N, -134.52°W | 42fm | 87% | King |

## Environmental Conditions
- Surface Temp: 12.4°C
- Thermocline: 18-22m
- Wind: NW 8 knots
```

**JSON Objects as First-Class:**
```json
{
  "analysis_id": "daily_catch_2026-07-23",
  "acoustic_signatures": [
    {
      "timestamp_ns": 1721741135000000000,
      "h3_index": "0x8a21104523fffff",
      "depth_fm": 35,
      "sv_mean": -38.4,
      "classification": {"species": "chum", "confidence": 0.94}
    }
  ]
}
```

---

### 2. DAW Timeline Viewer (Side View - Time-First Representation)

**Metaphor:** Digital Audio Workstation - Multi-track temporal orchestration

**Purpose:**
- Timing-critical correlation between multiple data streams
- Visualize temporal relationships: Sounder ping → Line bite → Catch
- Multi-track overlay for pattern detection

**Tracks:**
1. **Acoustic Track** - Sounder pings, backscatter values
2. **GPS Track** - Position, heading, speed over ground
3. **Catch Track** - Bite events, landed fish
4. **Gear Track** - Line deployment, retrieval, lure changes
5. **Environmental Track** - Temperature, wind, tide

**Phase 1 (MVP):**
- Basic timeline based on file timestamps
- Simple visualization of events over time
- No full DAW features needed yet

**Phase 2 (Later):**
- Full scrubbing and playback
- Multi-track overlay and correlation views
- Waveform-style acoustic visualization
- Temporal zoom levels (day/hour/minute)

**Timing-Critical Correlation Example:**
```
14:32:15 - Sounder detects fish at 35fm, position X
14:32:17 - Boat at position X, heading 180°
14:37:20 - Bite on line #3 (5 minutes 3 seconds later)
14:37:22 - Boat at position Y (line passed through position X)
→ Correlation: Fish was at position X, line intercepted at X 5m3s later
```

---

### 3. Spatial Chart Viewer (Top View - Space-First Representation)

**Metaphor:** Marine Chart - Spatial positioning and motion vectors

**Purpose:**
- Spatial visualization of fishing operations
- Depth + motion vectors as first-class citizens
- Integration with existing TZ Pro workflow

**Human UI Strategy:**
- **Use TZ Pro directly** for human visualization
- Tracklines, marks, layers already familiar
- Agent injects objects into TZ Pro object layer

**Agent Strategy:**
- **Headless OpenCPN** as digital twin for spatial awareness
- Agent can perform spatial queries without UI
- Spatial awareness available for all agent operations

**First-Class Spatial Data:**
- **SOC/COG** (Speed/Course Over Ground)
- **Heading** (Vessel orientation)
- **STW** (Speed Through Water)
- **Depth** (Sounder reading at each point)
- **Vectors** (Motion direction and velocity)

**Injection Example:**
```python
# Agent injects marks into TZ Pro
query = "Drop marks where yesterday's 5 king salmon were caught"

result = agent.query(query)
# Injects into TZ Pro object layer:
for catch in result:
    tzpro.inject_object({
        'type': 'mark',
        'position': (catch.lat, catch.lon),
        'label': f"King Salmon - {catch.weight}lbs",
        'timestamp': catch.timestamp_ns,
        'layer': 'catch_events_2026-07-23'
    })
```

---

## Chatbot Panel (Collapsible - Either Side)

**Purpose:**
- AI assistant available across all viewers
- Context-aware based on current viewer
- Can collapse/expand and move to either side

**Behaviors by Viewer:**

**In Markdown Editor:**
- "Create a daily catch summary from today's data"
- "Add a section to this document analyzing acoustic signatures"
- "Format this JSON as a readable table"

**In DAW Timeline:**
- "Show me 15 minutes before and after the 14:32 bite event"
- "Highlight all acoustic signatures > -30dB"
- "Create a new track for water temperature"

**In Spatial Chart:**
- "Drop marks where we caught king salmon yesterday"
- "Show me the trackline for the morning set"
- "Highlight all H3 cells with biomass density > threshold"

---

## Cross-Viewer Linking

**Core Concept:** An event highlighted in one viewer can be found in others to see cross-dimensional correlations.

**Event ID System:**
```typescript
interface CrossViewerEvent {
  event_id: string;  // Unique across all viewers
  timestamp_ns: number;
  position: { lat: number, lon: number, depth_fm: number };

  // Viewer-specific representations
  daw: {
    track_id: string;
    start_time: number;
    duration: number;
  };
  spatial: {
    tzpro_object_id: string;
    opencpn_waypoint: string;
  };
  markdown: {
    document_id: string;
    section_id: string;
  };
}
```

**Linking Examples:**

1. **DAW → Markdown:**
   - Click acoustic signature at 14:32:15
   - Opens Markdown editor showing analysis of that signature

2. **Spatial → DAW:**
   - Click mark on chart (king salmon catch)
   - DAW scrubs to 15 minutes before/after catch time

3. **Markdown → Spatial:**
   - Click analysis entry for chum school detection
   - TZ Pro highlights position and injects mark

---

## Implementation Phases

### Phase 1 (MVP - Immediate)

**Deliverables:**
1. ✅ **Theia-based Markdown/Code Editor**
   - Vessel agent extension
   - Markdown preview
   - JSON syntax highlighting
   - Document templates

2. ✅ **Spatial Injection to TZ Pro**
   - Agent can drop marks in TZ Pro
   - Read TZ Pro project files/logs
   - Basic spatial queries

3. ✅ **Basic Timeline Visualization**
   - File timestamps only
   - Simple event plotting
   - No full DAW yet

4. ✅ **Chatbot Panel**
   - Collapsible, movable
   - Context-aware per viewer
   - Voice I/O (STT/TTS) for phones

**Success Criteria:**
- Captain can view analysis in Markdown editor
- Captain can ask agent to drop marks in TZ Pro
- Captain can see basic timeline of events
- System works on boat workstation + phone

### Phase 2 (Enhanced Visualization)

**Deliverables:**
1. 🔄 **Full DAW Timeline Viewer**
   - Multi-track overlay
   - Scrubbing and playback
   - Temporal correlation views
   - Waveform-style acoustic viz

2. 🔄 **Headless OpenCPN Integration**
   - Agent spatial awareness without UI
   - Advanced spatial queries
   - Vector field visualization

3. 🔄 **Advanced Cross-Viewer Linking**
   - Click-to-find across all viewers
   - Bidirectional event linking
   - Multi-dimensional correlations

### Phase 3 (Fleet Intelligence)

**Deliverables:**
1. ⏳ **Fleet Data Sharing**
   - Shared marks layers (anonymized)
   - Collaborative analysis documents
   - Fleet-wide timeline views

2. ⏳ **Advanced AI Features**
   - Catch prediction
   - Biomass density mapping
   - Pattern recognition

---

## Technical Architecture

### Theia IDE Setup

**Server:**
- Runs on boat workstation or cloud instance
- Web-based, accessible from any device
- Handles all heavy computation

**Clients:**
- **Laptop/Tablet:** Full Theia UI with all 3 viewers (IDE, DAW, Chart)
- **Phone:** Voice-first conversational interface (STT/TTS)
- **Edge Devices:** Headless connection (data ingest only)

**Phone UX - Voice-First Retrospective Queries:**
- **Primary Interaction:** Human asks questions about past data via voice
- **Response:** Two-way STT/TTS conversation about historical patterns
- **Knowledge Capture:** Conversation automatically logged to Markdown with time/location anchors
- **Search:** Similar questions find previously processed thoughts via time/space search
- **Use Case:** "How did we do here last Tuesday?" → Full conversation logged and retrievable

**Extensions:**
```yaml
extensions:
  - @theia/markdown-preview
  - @theia/json-language-server
  - vessel-agent-markdown-templates
  - vessel-agent-tzpro-injector
  - vessel-agent-timeline-view
  - vessel-agent-chatbot-panel
```

### TZ Pro Integration

**Read Path:**
```
TZ Pro Project Files → Agent Parser → Spatial Awareness
```

**Write Path (Injection):**
```
Agent Query → TZ Pro Object API → Mark/Layer Creation → TZ Pro Display
```

**Data Types:**
- Marks (point features)
- Tracklines (line features)
- Layers (feature collections)
- Object properties (timestamp, depth, species, etc.)

### DAW Architecture

**Phase 1 (File Timestamps):**
```
File System → Timestamp Extraction → Timeline Plot → Basic Visualization
```

**Phase 2 (Full DAW):**
```
Parquet Archive → Time-Series Data → Multi-Track Renderer → Interactive Timeline
```

**Track Data:**
- Acoustic: Parquet files with timestamp_ns
- GPS: NMEA logs with time
- Catch: Event logs with timestamp
- Environment: Sensor data with timestamps

---

## Data Flow Across Viewers

```
┌─────────────────────────────────────────────────────────────┐
│                     VESSEL AGENT CORE                         │
│  (Time/Location/Source Anchored Parquet Archive)             │
└────────────┬────────────────────────────────────────────────┘
             │
    ┌────────┴────────┐
    │                 │
    ▼                 ▼
┌─────────┐      ┌─────────┐      ┌─────────┐
│ Markdown│      │   DAW   │      │ Spatial │
│ Editor  │      │ Timeline│      │  Chart  │
└────┬────┘      └────┬────┘      └────┬────┘
     │                 │                │
     └─────────┬───────┴────────────────┘
               │
        ┌──────▼──────┐
        │  Chatbot    │
        │  Panel      │
        └─────────────┘
```

**Cross-Viewer Event Bus:**
```typescript
// Event system for linking
class CrossViewerEventBus {
  highlight(eventId: string) {
    // Notify all viewers
    markdown.showEvent(eventId);
    daw.showEvent(eventId);
    spatial.showEvent(eventId);
  }
}
```

---

## User Experience Scenarios

### Scenario 1: Post-Trip Analysis

**User:** "Create a summary of yesterday's king salmon catch"

**System:**
1. Chatbot receives query
2. Agent queries Parquet archive for king salmon catch events
3. Agent creates Markdown document with summary
4. Agent drops marks in TZ Pro at catch locations
5. Markdown editor opens with new document

**Result:**
```markdown
# King Salmon Catch Summary - July 23, 2026

## Catch Locations
[Interactive Map - 5 locations]

## Details
| Time | Position | Depth | Weight | Lure |
|------|----------|-------|--------|------|
| 14:32 | 56.3°N, -134.5°W | 35fm | 12.4lbs | Spoon |
```

### Scenario 2: Temporal Correlation

**User:** "Show me what happened before the 14:32 bite"

**System:**
1. Chatbot receives query
2. Agent finds bite event at 14:32:15
3. Agent extracts 15 minutes prior data
4. DAW viewer opens with timeline centered on 14:32:15
5. All tracks show data from 14:17-14:32

**Result:**
- Acoustic track shows fish detection at 14:32:15
- GPS track shows boat trajectory approaching position
- Environmental track shows conditions at that time

### Scenario 3: Spatial Pattern Analysis

**User:** "Where did we catch fish in water < 10°C?"

**System:**
1. Chatbot receives query
2. Agent queries catch events + temperature data
3. Agent filters for catches with surface temp < 10°C
4. Agent drops colored marks in TZ Pro
5. Markdown editor shows summary table

**Result:**
- TZ Pro shows 8 marks in cold water regions
- Markdown shows table with temperature correlations
- Agent suggests: "Cold water catches were 2.3lbs larger on average"

---

## Device Support Matrix

| Device | Markdown Editor | DAW Timeline | Spatial Chart | Chatbot |
|--------|----------------|--------------|---------------|---------|
| Boat Workstation | ✅ Full | ✅ Full | ✅ TZ Pro + Injection | ✅ Full |
| Tablet | ✅ Full | ⚠️ Limited | ✅ TZ Pro View Only | ✅ Full |
| Phone | ⚠️ Read Only | ❌ Not Available | ❌ Not Available | ✅ Voice Only |
| Edge Device | ❌ Headless Only | ❌ Headless Only | ❌ Headless Only | ❌ Headless Only |

---

## Success Metrics

### Phase 1 (MVP)
- Captain can create and edit Markdown analysis documents
- Agent can drop marks in TZ Pro from natural language queries
- Captain can view basic timeline of daily events
- System accessible from boat workstation + phone
- Latency < 2s for chatbot responses
- Data capture > 99.9% (non-renewable resource principle)

### Phase 2 (Enhanced)
- Full DAW timeline with scrubbing and playback
- Headless OpenCPN providing spatial awareness
- Cross-viewer linking working seamlessly
- All viewers support click-to-find events

### Phase 3 (Fleet)
- Fleet data sharing with privacy preservation
- Advanced AI predictions and recommendations
- Multi-vessel timeline correlations

---

## Next Steps

1. ✅ **UX Architecture Clarified** (This Document)
2. 🔄 **Update Memory Schema** with refined viewer definitions
3. 🔄 **Create Theia Extension Specification**
4. 🔄 **Design TZ Pro Injection API**
5. 🔄 **Specify Phase 1 Implementation Tasks**

---

**Document Version:** 1.0
**Date:** 2026-07-24
**Status:** UX Architecture Complete → Implementation Planning
**MVP Focus:** Theia-based Markdown/Code Editor + TZ Pro Injection

---

*"The ocean forgets nothing. The vessel agent remembers everything."*
