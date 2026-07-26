# Theia-Based MVP Implementation Specification

**Date:** 2026-07-24
**Status:** Implementation Specification
**Priority:** Phase 1 MVP - Primary UI Interface
**Technology:** Eclipse Theia (Open-source, agent-native IDE framework)

---

## Overview

The Theia-based Markdown/Code Editor is the **primary MVP interface** for the vessel agent system. It provides a web-native, agent-aware environment where analysis documents and data structures are first-class citizens.

**Key Advantages:**
- Open-source and extensible
- Built-in agent/extension support
- Web-based (boat workstation or cloud deployment)
- Edge device compatibility (headless connection)
- Phone support (minimal resources, STT/TTS only)

---

## Architecture

### Deployment Model

```
┌─────────────────────────────────────────────────────────────┐
│                    THEIA SERVER                              │
│  (Boat Workstation or Cloud Instance)                       │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Theia Core + Vessel Agent Extensions                  │ │
│  │  • Markdown Preview                                     │ │
│  │  • JSON Language Server                                │ │
│  │  • Vessel Agent Chatbot Panel                          │ │
│  │  • TZ Pro Injection Connector                          │ │
│  │  • Timeline Viewer (Basic)                             │ │
│  └────────────────────────────────────────────────────────┘ │
└────────────┬────────────────────────────────────────────────┘
             │
    ┌────────┴────────┐
    │                 │
    ▼                 ▼
┌─────────┐      ┌─────────┐      ┌─────────┐
│Laptop/  │      │ Tablet  │      │  Phone  │
│Tablet   │      │         │      │         │
│(Full UI)│      │(Full UI)│      │(Voice)  │
└─────────┘      └─────────┘      └─────────┘
```

### Server Requirements

**Minimum (Boat Workstation):**
- CPU: 4 cores
- RAM: 8GB
- Storage: 100GB (for Parquet archive + Theia workspace)
- Network: Local LAN (no internet required)

**Recommended (Cloud Instance):**
- CPU: 8 cores
- RAM: 16GB
- Storage: 500GB SSD
- Network: Good cell/internet for remote access

### Client Requirements

**Laptop/Tablet (Full UI):**
- Modern web browser (Chrome, Firefox, Safari)
- Screen: 10" or larger
- Network: LAN or internet connection

**Phone (Minimal):**
- STT/TTS capability
- Basic web browser
- Network: LAN or internet connection
- Minimal on-device resources

---

## Extension Architecture

### Core Extensions

```yaml
theia_extensions:
  # Built-in Theia Extensions
  - @theia/core
  - @theia/markdown-preview
  - @theia/json-language-server
  - @theia/file-search
  - @theia/navigator

  # Vessel Agent Custom Extensions
  - vessel-agent-chatbot-panel      # Collapsible AI assistant
  - vessel-agent-markdown-templates  # Document templates
  - vessel-agent-tzpro-injector     # TZ Pro object injection
  - vessel-agent-timeline-view      # Basic timeline viewer
  - vessel-agent-data-explorer      # Parquet data browser
  - vessel-agent-voice-io           # STT/TTS for phones
```

### Extension: Vessel Agent Chatbot Panel

**Purpose:** Collapsible AI assistant available in all viewers

**Features:**
- Collapsible panel (left or right side)
- Context-aware based on current viewer/document
- Voice I/O (STT/TTS) for phones
- Natural language queries
- Agent-generated content insertion

**API:**
```typescript
interface VesselAgentChatbotPanel {
  // Panel control
  toggle(side: 'left' | 'right'): void;
  expand(): void;
  collapse(): void;

  // Chat interface
  sendMessage(message: string): Promise<AgentResponse>;
  sendVoice(audioBlob: Blob): Promise<AgentResponse>;

  // Context awareness
  getCurrentContext(): ViewerContext;
  setContext(viewer: ViewerType, document?: string): void;

  // Content insertion
  insertContent(content: string, format: 'markdown' | 'json'): void;
  createDocument(template: string): void;
}

interface AgentResponse {
  text: string;
  audio?: Blob;  // For TTS
  actions?: Action[];
  context?: ViewerContext;
}

interface Action {
  type: 'insert' | 'create' | 'query' | 'navigate';
  target?: string;
  content?: string;
}
```

**Context-Aware Behaviors:**

```typescript
// In Markdown Editor context
chatbot.setContext('markdown', 'daily_catch_summary.md');

// Example queries for markdown context
queries = [
  "Create a daily catch summary from today's data",
  "Add a section analyzing acoustic signatures",
  "Format this JSON as a readable table",
  "Generate species distribution table"
];

// In Timeline Viewer context
chatbot.setContext('timeline');

// Example queries for timeline context
queries = [
  "Show me 15 minutes before the 14:32 bite event",
  "Highlight all acoustic signatures > -30dB",
  "Create a new track for water temperature"
];
```

### Extension: Markdown Templates

**Purpose:** Pre-built templates for common analysis documents

**Template Locations:**
```
vessel-agent-templates/
├── daily-catch-summary.md
├── acoustic-signature-analysis.md
├── species-distribution.md
├── environmental-summary.md
├── trip-report.md
└── gear-performance-analysis.md
```

**Template Example:**
```markdown
---
template: daily-catch-summary
version: 1.0.0
generated: {{timestamp_ns}}
vessel: {{vessel_uuid}}
date: {{date}}
---

# Daily Catch Summary - {{date}}

## Captain's Log
{{crew_report_summary}}

## Species Breakdown
{{species_table}}

## Catch Locations
{{tzpro_marks_reference}}

## Acoustic Signatures Detected
{{acoustic_signatures_table}}

## Environmental Conditions
- Surface Temp: {{surface_temp_c}}°C
- Wind: {{wind_direction}} {{wind_speed}} knots
- Wave Height: {{wave_height_m}}m
- Bottom Depth: {{bottom_depth_m}}m

## Gear Performance
{{gear_performance_table}}

## Notes
{{freeform_notes}}
```

**Template API:**
```typescript
interface MarkdownTemplates {
  // List available templates
  listTemplates(): Template[];

  // Create document from template
  createFromTemplate(template: string, data: TemplateData): Promise<Document>;

  // Insert template section
  insertSection(section: string, data: TemplateData): void;
}

interface Template {
  name: string;
  description: string;
  category: 'daily' | 'analysis' | 'report' | 'custom';
  variables: Variable[];
}

interface TemplateData {
  date: string;
  timestamp_ns: number;
  vessel_uuid: string;
  crew_report_summary?: string;
  species_table?: string;
  acoustic_signatures_table?: string;
  environmental_conditions?: EnvironmentalData;
  // ... other variables
}
```

### Extension: TZ Pro Injector

**Purpose:** Inject marks and objects into TZ Pro from agent queries

**Architecture:**
```
Theia Extension → Vessel Agent Backend → TZ Pro Object API → TZ Pro Display
```

**API:**
```typescript
interface TZProInjector {
  // Inject a single mark
  injectMark(mark: TZProMark): Promise<void>;

  // Inject multiple marks as a layer
  injectLayer(layer: TZProLayer): Promise<void>;

  // Query TZ Pro project files
  readProject(): Promise<TZProProject>;

  // Read existing marks/layers
  readMarks(layer?: string): Promise<TZProMark[]>;
  readLayers(): Promise<TZProLayer[]>;
}

interface TZProMark {
  type: 'mark';
  position: {
    latitude: number;
    longitude: number;
  };
  label: string;
  timestamp_ns: number;
  properties: {
    depth_fm?: number;
    species?: string;
    weight_lbs?: number;
    confidence?: number;
    [key: string]: any;
  };
  layer: string;  // Layer name
  style?: {
    color?: string;
    icon?: string;
    size?: number;
  };
}

interface TZProLayer {
  type: 'layer';
  name: string;
  description?: string;
  visible: boolean;
  marks: TZProMark[];
  style?: {
    color?: string;
    opacity?: number;
  };
}
```

**Usage Examples:**

```typescript
// Inject catch event marks
const catches = await agent.query('catch_events for 2026-07-23');

const marks = catches.map(catch => ({
  type: 'mark',
  position: { latitude: catch.lat, longitude: catch.lon },
  label: `${catch.species} - ${catch.weight_lbs}lbs`,
  timestamp_ns: catch.timestamp_ns,
  properties: {
    depth_fm: catch.depth_fm,
    species: catch.species,
    weight_lbs: catch.weight_lbs
  },
  layer: 'catch_events_2026-07-23',
  style: { color: '#FF5733', icon: 'fish' }
}));

await tzpro.injectLayer({
  type: 'layer',
  name: 'catch_events_2026-07-23',
  description: 'King salmon caught on July 23, 2026',
  visible: true,
  marks: marks,
  style: { color: '#FF5733', opacity: 0.8 }
});
```

### Extension: Timeline Viewer (Basic)

**Purpose:** Simple timeline visualization based on file timestamps

**Phase 1 MVP Features:**
- Display events over time based on file timestamps
- Basic event filtering
- Click to view event details
- Export to Markdown

**Data Structure:**
```typescript
interface TimelineEvent {
  event_id: string;
  timestamp_ns: number;
  event_type: 'acoustic' | 'catch' | 'gear' | 'environmental';
  label: string;
  position?: { lat: number; lon: number };
  properties: Record<string, any>;
}

interface TimelineView {
  events: TimelineEvent[];
  timeRange: { start: number; end: number };
  filters: EventTypeFilter[];
  selectedEvent?: string;
}
```

**API:**
```typescript
interface TimelineViewer {
  // Load events from Parquet archive
  loadEvents(timeRange: TimeRange): Promise<void>;

  // Filter events
  setFilters(filters: EventTypeFilter[]): void;

  // Event selection
  selectEvent(eventId: string): void;
  getEventDetails(eventId: string): TimelineEvent;

  // Export
  exportToMarkdown(events: TimelineEvent[]): string;
  exportToJSON(events: TimelineEvent[]): string;

  // Cross-viewer linking
  linkToSpatial(eventId: string): void;
  linkToMarkdown(eventId: string): void;
}
```

**Implementation (Phase 1):**
```typescript
// Simple file timestamp-based timeline
class BasicTimelineViewer {
  async loadEvents(date: string) {
    // Read Parquet files for date
    const files = await parquetReader.readDate(date);

    // Extract events with timestamps
    const events: TimelineEvent[] = [];

    for (const file of files) {
      const timestamp = file.stat.mtimeMs * 1_000_000;  // Convert to ns

      events.push({
        event_id: generateEventId(file.path),
        timestamp_ns: timestamp,
        event_type: this.detectEventType(file.path),
        label: file.basename,
        properties: { file_path: file.path }
      });
    }

    return events;
  }

  private detectEventType(path: string): 'acoustic' | 'catch' | 'gear' | 'environmental' {
    if (path.includes('acoustic')) return 'acoustic';
    if (path.includes('catch')) return 'catch';
    if (path.includes('gear')) return 'gear';
    if (path.includes('environment')) return 'environmental';
    return 'environmental';  // default
  }
}
```

### Extension: Data Explorer

**Purpose:** Browse and query Parquet archive

**Features:**
- Browse Hive-partitioned Parquet files
- Query with SQL (DuckDB)
- Preview acoustic data
- Export queries

**API:**
```typescript
interface DataExplorer {
  // Browse archive structure
  listYears(): Promise<string[]>;
  listMonths(year: number): Promise<number[]>;
  listDays(year: number, month: number): Promise<number[]>;

  // Query data
  query(sql: string): Promise<QueryResult>;
  previewTable(table: string, limit?: number): Promise<DataRow[]>;

  // Export
  exportQuery(query: string, format: 'csv' | 'json' | 'parquet'): Promise<Blob>;
}

interface QueryResult {
  columns: string[];
  rows: any[][];
  rowCount: number;
  executionTimeMs: number;
}
```

---

## Integration with Vessel Agent Backend

### Backend Communication

```
Theia Extension → HTTP/WebSocket → Vessel Agent Backend → Parquet Archive
```

**API Endpoints:**

```typescript
// Backend API
interface VesselAgentAPI {
  // Data queries
  GET  /api/query/sql        : SQL query on Parquet archive
  GET  /api/query/events     : Get events for time range
  GET  /api/data/:date       : Get all data for date

  // Agent queries
  POST /api/agent/query      : Natural language query
  POST /api/agent/generate   : Generate content from template
  POST /api/agent/analyze    : Analyze data

  // TZ Pro integration
  POST /api/tzpro/inject     : Inject marks/layers
  GET  /api/tzpro/project    : Read TZ Pro project

  // Timeline
  GET  /api/timeline/events  : Get events for timeline
  POST /api/timeline/filter  : Filter timeline events
}
```

**WebSocket Events:**

```typescript
// Real-time updates
interface WebSocketEvents {
  // Server → Client
  'data:ingested': { timestamp_ns: number; record_count: number };
  'analysis:complete': { analysis_id: string; result: any };
  'alert:new': { alert: Alert };

  // Client → Server
  'subscribe:channel': (channel: string) => void;
  'unsubscribe:channel': (channel: string) => void;
}
```

---

## Phone-Specific Features

### Voice I/O Extension

**Purpose:** Enable phone usage with minimal resources

**Features:**
- Speech-to-Text (STT) for voice input
- Text-to-Speech (TTS) for voice output
- Simplified UI for small screens
- Offline mode (cached responses)

**API:**
```typescript
interface VoiceIO {
  // Speech recognition
  startListening(): void;
  stopListening(): Promise<string>;

  // Text-to-speech
  speak(text: string, options?: TTSOptions): Promise<void>;

  // Voice commands
  executeCommand(command: string): Promise<CommandResult>;
}

interface TTSOptions {
  voice?: string;
  rate?: number;
  pitch?: number;
  language?: string;
}

interface CommandResult {
  success: boolean;
  response: string;
  actions?: Action[];
}
```

**Voice Commands:**

```typescript
// Common voice commands
const voiceCommands = [
  "Create a daily catch summary",
  "Where did we catch fish yesterday?",
  "Show me the acoustic signatures from today",
  "Drop marks at king salmon locations",
  "What's the water temperature?",
  "Read the daily log"
];
```

---

## Implementation Roadmap

### Phase 1A: Core Theia Setup (Week 1-2)

**Tasks:**
1. ✅ Install and configure Theia server
2. ✅ Set up vessel agent workspace
3. ✅ Install base extensions (Markdown, JSON LSP)
4. ✅ Configure file system access to Parquet archive
5. ✅ Test web client access

**Deliverables:**
- Working Theia instance
- Markdown editing capability
- JSON syntax highlighting
- File browser for Parquet archive

### Phase 1B: Chatbot Panel (Week 3-4)

**Tasks:**
1. ✅ Develop vessel-agent-chatbot-panel extension
2. ✅ Implement collapsible panel UI
3. ✅ Connect to vessel agent backend API
4. ✅ Implement context-aware behavior
5. ✅ Add basic natural language queries

**Deliverables:**
- Working chatbot panel
- Agent query interface
- Context-aware responses
- Basic Markdown document generation

### Phase 1C: TZ Pro Integration (Week 5-6)

**Tasks:**
1. ✅ Develop vessel-agent-tzpro-injector extension
2. ✅ Implement TZ Pro project file parser
3. ✅ Connect to TZ Pro object API
4. ✅ Implement mark/layer injection
5. ✅ Test injection workflows

**Deliverables:**
- TZ Pro mark injection
- Layer creation
- Project file reading
- Spatial query integration

### Phase 1D: Timeline Viewer (Week 7-8)

**Tasks:**
1. ✅ Develop basic timeline viewer extension
2. ✅ Implement file timestamp extraction
3. ✅ Create event timeline visualization
4. ✅ Add event filtering
5. ✅ Implement cross-viewer linking

**Deliverables:**
- Basic timeline viewer
- File timestamp events
- Event filtering
- Cross-viewer linking

### Phase 1E: Phone Support (Week 9-10)

**Tasks:**
1. ✅ Develop vessel-agent-voice-io extension
2. ✅ Implement STT/TTS integration
3. ✅ Create simplified phone UI
4. ✅ Add voice command recognition
5. ✅ Test offline mode

**Deliverables:**
- Voice I/O working
- Phone-accessible interface
- Voice commands functional
- Offline mode operational

---

## Success Metrics

### Phase 1 Success Criteria

**Technical:**
- ✅ Theia server running on boat workstation
- ✅ Markdown editor with syntax highlighting
- ✅ Chatbot panel with agent queries
- ✅ TZ Pro injection working
- ✅ Basic timeline viewer functional
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

---

## Testing Strategy

### Unit Tests

```typescript
// Extension unit tests
describe('VesselAgentChatbotPanel', () => {
  test('should toggle panel visibility', () => {
    const panel = new VesselAgentChatbotPanel();
    panel.toggle('left');
    expect(panel.isVisible).toBe(true);
  });

  test('should send message and receive response', async () => {
    const panel = new VesselAgentChatbotPanel();
    const response = await panel.sendMessage('Create daily summary');
    expect(response.text).toBeDefined();
  });
});

describe('TZProInjector', () => {
  test('should inject mark into TZ Pro', async () => {
    const injector = new TZProInjector();
    const mark = createTestMark();
    await injector.injectMark(mark);
    // Verify mark appears in TZ Pro
  });
});
```

### Integration Tests

```typescript
// Backend integration tests
describe('VesselAgentAPI', () => {
  test('should query Parquet archive', async () => {
    const result = await api.query('/api/query/sql', {
      sql: 'SELECT * FROM acoustic_data WHERE date = 2026-07-23'
    });
    expect(result.rowCount).toBeGreaterThan(0);
  });

  test('should execute agent query', async () => {
    const result = await api.query('/api/agent/query', {
      query: 'Create daily catch summary'
    });
    expect(result.content).toBeDefined();
  });
});
```

### End-to-End Tests

```typescript
// User workflow tests
describe('Captain Workflow', () => {
  test('should create daily catch summary', async () => {
    // 1. Captain opens Theia
    const theia = await Theia.connect();

    // 2. Captain opens chatbot panel
    const chatbot = theia.getExtension('chatbot');
    await chatbot.expand();

    // 3. Captain sends voice command
    const response = await chatbot.sendMessage('Create daily catch summary');

    // 4. Verify document created
    const documents = theia.getDocuments();
    expect(documents).toContain('daily_catch_summary_2026-07-23.md');
  });

  test('should inject marks into TZ Pro', async () => {
    // 1. Captain queries agent
    const chatbot = theia.getExtension('chatbot');
    const response = await chatbot.sendMessage('Drop marks where we caught king salmon yesterday');

    // 2. Verify TZ Pro injection
    const tzpro = theia.getExtension('tzpro');
    const marks = await tzpro.readMarks('king_salmon_2026-07-22');
    expect(marks.length).toBeGreaterThan(0);
  });
});
```

---

## Documentation

### User Documentation

**Getting Started:**
1. "Connecting to Theia from your devices"
2. "Creating your first daily catch summary"
3. "Querying the agent with voice commands"
4. "Dropping marks in TZ Pro"

**Feature Guides:**
1. "Markdown editor overview"
2. "Chatbot panel reference"
3. "Timeline viewer usage"
4. "Phone voice commands"

### Developer Documentation

**Extension Development:**
1. "Theia extension development guide"
2. "Vessel agent API reference"
3. "TZ Pro integration patterns"
4. "Cross-viewer linking implementation"

**Deployment:**
1. "Theia server setup on boat workstation"
2. "Cloud deployment guide"
3. "Network configuration for LAN access"
4. "Security best practices"

---

## Next Steps

1. ✅ **Specification Complete** (This Document)
2. 🔄 **Theia Server Setup** (Phase 1A)
3. 🔄 **Chatbot Panel Development** (Phase 1B)
4. 🔄 **TZ Pro Integration** (Phase 1C)
5. 🔄 **Timeline Viewer** (Phase 1D)
6. 🔄 **Phone Support** (Phase 1E)

---

**Document Version:** 1.0
**Date:** 2026-07-24
**Status:** Specification Complete → Implementation Ready
**Priority:** Phase 1 MVP - Primary UI Interface

---

*"The ocean forgets nothing. The vessel agent remembers everything."*
