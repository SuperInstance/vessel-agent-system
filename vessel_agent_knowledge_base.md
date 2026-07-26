# Vessel Agent System Knowledge Base

**Version:** 1.0
**Date:** 2026-07-24
**Vessel:** F/V EILEEN (51' Commercial Fishing Vessel)
**Home Port:** Southeast Alaska
**Primary Fishery:** Power Trolling

---

## Knowledge Base Architecture

This knowledge base is structured as a long-term memory system for vessel-agent development. It's designed to survive multiple context compactions and provide foundational knowledge for future agent iterations.

### Core Principles

1. **Capture Now, Analyze Later** - Data capture formats must remain valuable across decades of technological change
2. **Time/Location/Source Anchoring** - Every data point has temporal, spatial, and provenance metadata
3. **Multi-Panel Analysis** - CAD + DAW inspired interface for spatial-temporal reasoning
4. **Agentic Consumption** - Data structured for AI agents, not human visual inspection

---

## System Architecture Overview

### Physical Layer

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            VESSEL LAYER                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [WHEELHOUSE WORKSTATION]                                                   │
│  • ProArt PX13 HN7306WU_HN7306WU                                           │
│  • TimeZero Professional (Nobeltec)                                         │
│  • Furuno Sounder Module (echogram waveforms)                              │
│  • NMEA0183 GPS/AIS/Radio streams                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DATA CAPTURE LAYER                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [NETWORK INTERCEPTION]                                                      │
│  • UDP packet capture (BPF filter)                                          │
│  • Zero-copy ring buffer                                                    │
│  • Furuno header parsing                                                     │
│                                                                             │
│  [NMEA INTERCEPTION]                                                         │
│  • Serial/UDP sentence capture                                              │
│  • Sub-second interpolation                                                  │
│  • Vector clock synchronization                                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PROCESSING LAYER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [SPATIAL TENSOR TRANSFORMATION]                                            │
│  • Raw amplitude → Physical Sv (dB)                                         │
│  • Device bins → Meters per bin                                              │
│  • H3 spatial indexing                                                      │
│  • Time/Location/Source anchoring                                           │
│                                                                             │
│  [STORAGE ENGINE]                                                             │
│  • Apache Arrow / Parquet columnar storage                                   │
│  • Hive partitioning (year/month/day/vessel_id)                            │
│  • Zero-copy tensor serialization                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ANALYSIS LAYER                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [MULTI-PANEL INTERFACE]                                                      │
│  • Side View: Water column profile (echogram)                              │
│  • Top View: Spatial chart overlay (H3 cells)                               │
│  • Front View: Cross-section (depth vs cross-track)                         │
│  • Timeline: DAW-style temporal tracks                                      │
│  • Inspector: IDE-style data properties                                     │
│                                                                             │
│  [AGENT ECOSYSTEM]                                                            │
│  • Ingestion agents (real-time processing)                                   │
│  • Analysis agents (pattern recognition)                                     │
│  • Supervisor agents (cross-sensor auto-labeling)                           │
│  • Communication agents (crew feedback loop)                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Schema Definitions

### Core Data Anchor

Every data point in the system must include:

```json
{
  "temporal_anchor": {
    "timestamp_ns": 1784883660123456789,
    "ping_sequence_id": 123456789,
    "mutation_epoch_ms": 1784883660123
  },
  "spatial_anchor": {
    "latitude": 54.3210987654,
    "longitude": -147.6543210987,
    "h3_index_uint64": "0x8a21104523fffff",
    "heading_true": 184.2,
    "transducer_depth_m": 2.4
  },
  "source_provenance": {
    "vessel_uuid": "US-AK-FVCATCHER-01",
    "hardware_source": "FURUNO_DFF3_UHD",
    "pipeline_version": "v1.0.0"
  },
  "environmental_context": {
    "surface_temp_c": 11.2,
    "sound_velocity_mps": 1485.0,
    "frequency_hz": 200000,
    "transmit_power_watts": 2000
  }
}
```

### Acoustic Data Record

```json
{
  "type": "acoustic_ping",
  "timestamp_ns": 1784883660123456789,
  "ping_sequence_id": 123456789,
  "vessel_uuid": "US-AK-FVCATCHER-01",

  "spatial": {
    "latitude": 54.3210987654,
    "longitude": -147.6543210987,
    "h3_index_uint64": "0x8a21104523fffff",
    "heading_true": 184.2,
    "transducer_depth_m": 2.4
  },

  "acoustic": {
    "frequency_hz": 200000,
    "pulse_length_ms": 0.3,
    "configured_range_meters": 50.0,
    "meters_per_bin": 0.125,
    "sound_velocity_mps": 1485.0,
    "backscatter_tensor_db": [
      -90.0, -85.2, -78.4, -65.3, -55.1, -48.2, -42.1,
      -40.5, -38.9, -35.2, -30.1, -28.4, -25.6, -22.1
    ]
  },

  "environmental": {
    "surface_temp_c": 11.2,
    "transmit_power_watts": 2000,
    "gain_setting": 0.3
  },

  "metadata": {
    "hardware_source": "FURUNO_DFF3_UHD",
    "pipeline_version": "v1.0.0",
    "classification": null,
    "confidence": null,
    "ground_truth_label": null
  }
}
```

### Catch Event Record

```json
{
  "type": "catch_event",
  "timestamp_start_ns": 1784883600000000000,
  "timestamp_end_ns": 1784887200000000000,
  "vessel_uuid": "US-AK-FVCATCHER-01",

  "location": {
    "h3_cells": [
      "0x8a21104523fffff",
      "0x8a21104523ffffe",
      "0x8a21104523ffffd"
    ],
    "bounding_box": {
      "min_lat": 54.320,
      "max_lat": 54.322,
      "min_lon": -147.655,
      "max_lon": -147.653
    }
  },

  "catch": {
    "species": "chum_salmon",
    "weight_lbs": 300,
    "count_estimate": 150,
    "depth_range_fm": [25, 45]
  },

  "gear": {
    "type": "power_troll",
    "deployment_duration_min": 120,
    "avg_speed_knots": 3.5,
    "lure_depth_fm": 35
  },

  "environmental": {
    "surface_temp_c": 11.2,
    "wind_speed_knots": 12,
    "wave_height_m": 1.2,
    "bottom_depth_m": 180
  },

  "metadata": {
    "crew_report_source": "voice_catch_log",
    "report_confidence": "high",
    "observer_id": "captain"
  }
}
```

### Crew Report Record

```json
{
  "type": "crew_report",
  "timestamp_ns": 1784885400123456789,
  "vessel_uuid": "US-AK-FVCATCHER-01",

  "report_source": {
    "type": "voice_transcript",
    "original_audio_path": "/archive/audio/2026-07-24/crew_report_143240.wav",
    "transcript_text": "Good chum marks coming on at 35 fathoms, lots of bait in the area",
    "speaker_id": "captain",
    "confidence": 0.94
  },

  "spatial": {
    "latitude": 54.3210987654,
    "longitude": -147.6543210987,
    "h3_index_uint64": "0x8a21104523fffff"
  },

  "observations": {
    "species_mentioned": ["chum"],
    "depth_range_fm": [35, 35],
    "bait_presence": true,
    "water_clarity": "good"
  },

  "metadata": {
    "processing_model": "whisper_large_v3",
    "pipeline_version": "v1.0.0"
  }
}
```

---

## Multi-Panel Interface Architecture

### Panel Definitions

#### 1. Side View (Water Column Profile)

**Purpose:** Traditional echogram display showing acoustic backscatter over time

**Data Structure:**
```typescript
interface SideViewData {
  depthRange: [number, number];        // [0, 500] meters
  temporalWindow: number;              // 256 pings
  colorMap: 'ek60' | 'sonar5' | 'custom';
  frequencies: number[];              // [18000, 38000, 70000, 120000, 200000]

  renderEchogram(data: AcousticTensor): HTMLCanvasElement;
  detectBottom(signal: Float32Array): number;
  classifySpecies(region: BoundingBox): SpeciesPrediction[];
}
```

**Key Interactions:**
- Scroll vertically: Zoom depth axis
- Scroll horizontally: Pan through temporal history
- Click-drag: Select region for inspection
- Right-click: Context menu (export, label, analyze)

#### 2. Top View (Spatial Chart Overlay)

**Purpose:** Bird's-eye view of fishing grounds with biomass heatmaps

**Data Structure:**
```typescript
interface TopViewData {
  centerCoordinate: [number, number]; // [lat, lon]
  zoomLevel: number;                  // H3 resolution (0-15)
  visibleLayers: LayerType[];

  layers: {
    baseChart: ENCData;
    biomassHeatmap: H3DensityMap;
    trajectory: GPSTrace[];
    catchMarkers: CatchEvent[];
    h3Grid: H3Cell[];
    bathymetry: DepthContours;
    predictions: SpeciesProbabilityMap;
    uncertainty: ConfidenceContours;
  };

  renderMap(): HTMLCanvasElement;
  queryH3Cell(cell: string): AcousticHistory;
  getVisibleBounds(): BoundingBox;
}
```

**Key Interactions:**
- Click H3 cell: View temporal history
- Shift+Click: Compare multiple cells
- Scroll wheel: Zoom in/out
- Click-drag: Create selection region

#### 3. Front View (Cross-Section Analysis)

**Purpose:** Vertical slice through water column at current vessel heading

**Data Structure:**
```typescript
interface FrontViewData {
  vesselHeading: number;              // degrees true
  crossTrackRange: number;            // meters port/starboard
  depthRange: [number, number];       // same as SideView
  currentTime: timestamp_ns;

  renderCrossSection(): HTMLCanvasElement;
  extractTargets(): Target[];
  interpolateSlice(pingId: number): CrossSectionData;
}
```

**Key Interactions:**
- Scroll: Move along vessel track
- Drag: Adjust slice angle/heading
- Click: Select target for tracking

#### 4. Timeline (DAW-Style Temporal Interface)

**Purpose:** Track-based temporal organization of all data streams

**Data Structure:**
```typescript
interface TimelineData {
  tracks: Track[];
  clips: DataClip[];
  playhead: Playhead;

  scrubTo(timestamp_ns: number): void;
  addClip(clip: DataClip): void;
  splitClip(clipId: string, timestamp: timestamp_ns): DataClip[];
  addMarker(marker: TimelineMarker): void;
}
```

**Track Types:**
- Acoustic (18kHz, 38kHz, 120kHz, 200kHz)
- GPS Position
- Catch Log
- Gear Deployment
- Crew Reports
- Environmental (temp, wind, waves)
- Depth/Bathymetry

**Key Interactions:**
- Click: Jump to timestamp
- Drag: Smooth scrub through time
- Shift+Drag: Frame-by-frame scrubbing
- Scroll: Zoom time axis

#### 5. Inspector (IDE-Style Data Properties)

**Purpose:** Display detailed properties of selected data

**Data Structure:**
```typescript
interface InspectorData {
  selectedObject: DataObject | null;
  activeTab: 'properties' | 'metadata' | 'analysis' | 'correlations';

  showData(data: DataObject): void;
  editProperty(property: string, value: any): void;
  runAnalysis(data: DataObject): AnalysisResult;
}
```

**Tabs:**
- Properties: Core data values
- Metadata: Provenance and versioning
- Analysis: Model predictions and classifications
- Correlations: Cross-sensor relationships

---

## Cross-Panel Selection System

### Selection Bus Architecture

All panels communicate through a central selection bus:

```typescript
class SelectionBus {
  private subscribers: Panel[] = [];

  broadcast(selection: Selection) {
    // Transform selection for each panel type
    for (const panel of this.subscribers) {
      const transformed = this.transformForPanel(selection, panel.type);
      panel.onSelection(transformed);
    }
  }

  transformForPanel(selection: Selection, panelType: PanelType): Selection {
    // Convert spatial selection to temporal range for timeline
    // Convert temporal selection to spatial region for map
    // Convert depth selection to time range for timeline
    // etc.
  }
}
```

### Selection Types

```typescript
type Selection =
  | SpatialSelection      // H3 cells, bounding box
  | TemporalSelection     // Time range
  | DepthSelection        // Depth band
  | DataSelection         // SQL query
  | CompoundSelection;   // Combination of above
```

### Linking Patterns

**Spatial → Temporal:**
- Click H3 cell → Highlight time ranges when vessel was in cell

**Temporal → Spatial:**
- Scrub timeline → Highlight vessel position at timestamp

**Depth → Temporal:**
- Select depth band → Filter timeline to show acoustic activity at depth

**Compound Selection:**
- Select spatial region + time range + depth band → Precise data extraction

---

## Data Query API

### Unified Query Interface

```typescript
class MarineDataQueryEngine {
  // SPATIAL QUERIES
  queryByH3(cells: string[], timeRange?: TimeRange): Promise<QueryResult>;
  queryByBoundingBox(bounds: BoundingBox, timeRange?: TimeRange): Promise<QueryResult>;
  queryByVesselTrajectory(vesselId: string, timeRange: TimeRange): Promise<QueryResult>;

  // TEMPORAL QUERIES
  queryByTime(range: TimeRange, spatialFilter?: BoundingBox): Promise<QueryResult>;
  queryAtTimestamp(timestamp: timestamp_ns): Promise<SystemState>;

  // DEPTH QUERIES
  queryByDepthRange(range: [number, number], constraints?: Constraints): Promise<QueryResult>;
  queryBottomDepth(location: [number, number]): number;

  // SPECIES QUERIES
  querySpecies(species: string, confidenceThreshold?: number): Promise<QueryResult>;
  classifyAcousticSignature(acousticData: Float32Array): SpeciesPrediction[];

  // COMPOUND QUERIES
  query(selection: CompoundSelection): Promise<QueryResult>;

  // ANALYTICAL QUERIES
  correlateBiomassWithEnvironment(species: string): Promise<CorrelationResult>;
  predictCatchProbability(location: [number, number], time: timestamp_ns): Promise<number>;
}
```

### SQL Examples

```sql
-- Query acoustic data for specific H3 cell
SELECT timestamp_ns, backscatter_db, depth_bins_m
FROM read_parquet('archive_root/year=*/month=*/*.parquet')
WHERE h3_index_uint64 = 0x8a21104523fffff
  AND timestamp_ns BETWEEN 1784883600000000000 AND 1784883660000000000
ORDER BY timestamp_ns;

-- Correlate catch events with acoustic signatures
SELECT
  c.species,
  c.weight_lbs,
  AVG(a.backscatter_db) as avg_backscatter,
  STDDEV(a.backscatter_db) as backscatter_variance
FROM catch_events c
JOIN acoustic_data a ON a.h3_index_uint64 IN c.h3_cells
  AND a.timestamp_ns BETWEEN c.timestamp_start_ns AND c.timestamp_end_ns
GROUP BY c.species, c.weight_lbs;

-- Biomass by depth band
SELECT
  FLOOR(depth_bins_m / 50) * 50 as depth_band,
  AVG(backscatter_db) as avg_sv,
  COUNT(*) as sample_count
FROM acoustic_data
WHERE timestamp_ns >= ? AND timestamp_ns <= ?
GROUP BY depth_band
ORDER BY depth_band;
```

---

## Agent Ecosystem Architecture

### Agent Types

#### 1. Ingestion Agent

**Purpose:** Real-time processing of raw data streams

**Responsibilities:**
- Subscribe to ZeroMQ acoustic tensor stream
- Perform real-time classification
- Detect anomalies (bottom depth changes, biomass spikes)
- Publish to analysis bus

```python
class IngestionAgent:
    def __init__(self):
        self.zmq_sub = zmq.Socket(zmq.SUB)
        self.zmq_sub.connect("ipc://fused_spatial_tensor.ipc")
        self.model = load_model("biomass_classifier_v1.pt")

    def run(self):
        while True:
            tensor = self.receive_tensor()
            features = self.extract_features(tensor)
            classification = self.model.classify(features)
            self.publish(classification)
```

#### 2. Analysis Agent

**Purpose:** Pattern recognition and historical analysis

**Responsibilities:**
- Process accumulated acoustic data
- Identify species-specific signatures
- Generate biomass density maps
- Create catch probability predictions

```python
class AnalysisAgent:
    def analyze_species_signature(self, catch_events, acoustic_data):
        # Match catch reports to acoustic signatures
        signatures = {}
        for event in catch_events:
            acoustic_window = acoustic_data.get_window(
                event.location,
                event.time_range
            )
            signature = self.extract_signature(acoustic_window)
            signatures[event.species] = signature
        return signatures
```

#### 3. Supervisor Agent

**Purpose:** Cross-sensor auto-labeling and continuous learning

**Responsibilities:**
- Monitor catch events and gear deployment
- Auto-label acoustic data with ground truth
- Trigger model retraining
- Manage training data pool

```python
class SupervisorAgent:
    def on_catch_event(self, catch_event):
        # Query acoustic data for catch location and time
        acoustic_data = self.query_engine.query_by_h3(
            catch_event.h3_cells,
            catch_event.time_range
        )

        # Auto-label with species and confidence
        labeled_data = self.label_data(acoustic_data, catch_event)

        # Add to training pool
        self.training_pool.add(labeled_data)

        # Trigger retraining if threshold reached
        if len(self.training_pool) > self.retrain_threshold:
            self.trigger_retraining()
```

#### 4. Communication Agent

**Purpose:** Crew feedback loop and voice reporting

**Responsibilities:**
- Process voice catch reports
- Transcribe crew observations
- Extract species/depth/bait information
- Link transcripts to acoustic data

```python
class CommunicationAgent:
    def process_voice_report(self, audio_file):
        # Transcribe with timestamp
        transcript = self.whisper_model.transcribe(audio_file)

        # Extract entities
        entities = self.extract_entities(transcript.text)

        # Create crew report record
        report = CrewReport(
            timestamp_ns=transcript.timestamp_ns,
            location=self.current_location,
            transcript_text=transcript.text,
            observations=entities
        )

        # Store in database
        self.db.store(report)
```

### Agent Communication Pattern

```typescript
// ZeroMQ pub/sub pattern for agent communication
interface AgentBus {
  // Publishers
  publishAcousticTensor(tensor: AcousticTensor): void;
  publishClassification(classification: Classification): void;
  publishCatchEvent(event: CatchEvent): void;
  publishCrewReport(report: CrewReport): void;

  // Subscribers
  subscribeToAcousticTensor(callback: (tensor: AcousticTensor) => void): void;
  subscribeToClassifications(callback: (classification: Classification) => void): void;
  subscribeToCatchEvents(callback: (event: CatchEvent) => void): void;
  subscribeToCrewReports(callback: (report: CrewReport) => void): void;
}
```

---

## Storage Architecture

### Hive Partitioning Strategy

```
/archive_root/
  └── year=2026/
      └── month=07/
          └── day=24/
              └── vessel_id=US-AK-FVCATCHER-01/
                  ├── data_stream_v1_00000.parquet
                  ├── data_stream_v1_00001.parquet
                  └── data_stream_v1_00002.parquet
```

### Parquet Schema (ICES-aligned)

```python
acoustic_v1_schema = pa.schema([
    # Temporal & Spatial Primary Keys
    ('timestamp_ns', pa.int64()),
    ('vessel_uuid', pa.string()),
    ('ping_id', pa.uint64()),

    # Hardware State (Context)
    ('frequency_hz', pa.uint32()),
    ('transmit_power_watts', pa.uint16()),
    ('pulse_length_ms', pa.float32()),

    # Spatial Normalization Coefficients
    ('meters_per_bin', pa.float32()),
    ('surface_temp_c', pa.float32()),
    ('sound_velocity_mps', pa.float32()),
    ('transducer_depth_m', pa.float32()),

    # Position
    ('latitude', pa.float64()),
    ('longitude', pa.float64()),
    ('heading_true', pa.float32()),
    ('h3_index_uint64', pa.uint64()),

    # The Core Data Matrix
    ('backscatter_tensor_db', pa.list_(pa.float32())),

    # Extensibility Block (future-proof)
    ('metadata_extension', pa.map_(pa.string(), pa.string()))
])
```

### Zero-Copy Processing

```python
def process_packet_zero_copy(raw_packet_bytes):
    # Cast to memoryview (zero-copy)
    packet_view = memoryview(raw_packet_bytes)

    # Extract metadata by offset
    ping_id = int.from_bytes(packet_view[4:8], byteorder='big')
    frequency = int.from_bytes(packet_view[12:16], byteorder='big')

    # Extract acoustic payload (skip 64-byte header)
    raw_bins = packet_view[64:]

    # Convert to calibrated dB
    calibrated_db = (np.frombuffer(raw_bins, dtype=np.uint8)
                     * 0.3) - 90.0

    return {
        'ping_id': ping_id,
        'frequency': frequency,
        'backscatter_db': calibrated_db
    }
```

---

## Implementation Roadmap

### Phase 1: Core Data Capture (Current)

**Status:** In Progress
**Focus:** Robust, comprehensive data collection

**Components:**
1. Network packet capture (UDP interception)
2. NMEA sentence parsing and interpolation
3. Zero-copy ring buffer
4. Parquet write pipeline
5. Hive partitioning

**Deliverables:**
- Continuous acoustic data capture
- GPS-positioned echogram records
- Hourly Parquet file flushes
- Auto-purge safety (15% disk threshold)

### Phase 2: Spatial Processing

**Focus:** Time/Location/Source anchoring

**Components:**
1. H3 spatial indexing
2. Sub-second GPS interpolation
3. Physical normalization (Sv dB, meters_per_bin)
4. Metadata extension blocks

**Deliverables:**
- All data points triply-anchored
- Hardware-agnostic storage
- Query-ready spatial database

### Phase 3: Multi-Panel Interface

**Focus:** CAD + DAW visualization

**Components:**
1. Side View (water column profile)
2. Top View (spatial chart overlay)
3. Front View (cross-section)
4. Timeline (DAW-style tracks)
5. Inspector (IDE-style properties)

**Deliverables:**
- Interactive data exploration
- Cross-panel selection and linking
- Temporal scrubbing and playback

### Phase 4: Agent Ecosystem

**Focus:** Autonomous analysis and learning

**Components:**
1. Ingestion agents (real-time processing)
2. Analysis agents (pattern recognition)
3. Supervisor agents (auto-labeling)
4. Communication agents (crew feedback)

**Deliverables:**
- Species classification from acoustic data
- Auto-labeled training datasets
- Continuous model improvement
- Catch probability predictions

### Phase 5: Fleet Intelligence

**Focus:** Multi-vessel collaboration

**Components:**
1. Federated learning across vessels
2. Fleet-wide pattern discovery
3. Shared vocabulary (with privacy)
4. Predictive analytics

**Deliverables:**
- Transfer-learned species predictions
- Fleet-level biomass trends
- Migration pattern tracking
- Collaborative intelligence

---

## Key Reference Documents

### External Documentation

1. **ICES SONAR-netCDF4 Convention**
   - Standard for water column data
   - Hardware-agnostic normalization
   - https://echopype.readthedocs.io

2. **Apache Parquet Specification**
   - Columnar storage format
   - Schema evolution support
   - https://parquet.apache.org

3. **Uber H3 Spatial Index**
   - Hexagonal hierarchical geospatial indexing
   - https://h3geo.org/docs

4. **TimeZero Professional Integration**
   - Nobeltec TZ Pro API
   - Furuno sounder module
   - https://www.nobeltec.com

### Internal Documentation

1. **tzrawcapturesystem1.md** - Raw capture conversation with Gemini
2. **marine_visualization_design_doc.md** - Multi-panel interface design
3. **marine_vessel_agent_system_analysis.md** - Comprehensive system analysis
4. **tzpro-agent repository** - Existing vessel agent implementation

---

## Memory Architecture for Agent Continuity

This knowledge base is designed to survive multiple agent context compactions. When a new agent session begins:

1. **Read this file first** - Establish foundational understanding
2. **Review reference documents** - Deep-dive into specific topics
3. **Check implementation status** - Review roadmap progress
4. **Continue from last state** - Resume development without knowledge loss

### Memory Update Protocol

When significant architectural decisions are made:

1. Update the relevant section in this document
2. Add timestamp and rationale for changes
3. Update implementation roadmap status
4. Create supplementary documentation for complex topics

### Knowledge Compression Strategy

When context limits are approached:

1. Core schema definitions are immutable
2. Architecture overview is stable reference
3. Implementation roadmap is updated regularly
4. Agent-specific context is ephemeral

---

## Quick Reference for Agents

### Data Flow Summary

```
Sounder UDP → Ring Buffer → Zero-Copy Parser → Parquet Writer → Disk
GPS/NMEA → Interpolator → Spatial Index → Metadata → Parquet Writer
```

### Key Technologies

- **Capture:** Python + pypcap + memoryview
- **Storage:** Apache Arrow + Parquet + DuckDB
- **Spatial:** Uber H3 + ICES normalization
- **Visualization:** React + WebGL + D3.js
- **Agents:** Python + PyTorch + ZeroMQ

### Critical Principles

1. **Capture now, analyze later** - Raw data retention is priority
2. **Hardware-agnostic** - Normalize to physical units
3. **Triply-anchored** - Time/Location/Source on every record
4. **Future-proof** - Schema extensibility blocks
5. **Agent-first** - Structure data for AI consumption

---

**Document Version:** 1.0
**Last Updated:** 2026-07-24
**Next Review:** After Phase 1 completion
