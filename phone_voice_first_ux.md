# Phone Voice-First UX - Retrospective Query Interface

**Date:** 2026-07-24
**Status:** UX Architecture Refinement
**Device:** Phone (Headset-Optimized)

---

## Overview

The phone is **not a limited version** of the workstation interface. It's a **different interaction paradigm** optimized for:

1. **Voice-first** two-way conversation (STT/TTS with headset)
2. **Retrospective querying** about past data and patterns
3. **Automatic knowledge capture** - conversations logged to Markdown
4. **Time/space search** - similar questions find previously processed thoughts

---

## Phone vs Workstation

### Workstation (Active Creation & Analysis)
- **Primary Use:** Creating documents, analyzing data, visualizing patterns
- **Interaction:** Chatbot panel + IDE/DAW/Chart (3 viewers as tabs)
- **Focus:** Real-time analysis, document creation, visualization
- **Example:** Creating daily catch summary, dropping marks in TZ Pro

### Phone (Retrospective Voice Queries)
- **Primary Use:** Asking questions about past data via voice
- **Interaction:** Two-way STT/TTS conversation (headset preferred)
- **Focus:** Historical patterns, retrospective analysis, knowledge retrieval
- **Example:** "How did we do here last Tuesday?" (while on the grounds)

---

## Voice Conversation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHONE VOICE INTERFACE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Captain (via headset): "How did we do here last Tuesday?"     │
│           │                                                       │
│           ▼                                                       │
│  ┌───────────────────┐      ┌───────────────────┐               │
│  │  STT (Whisper)    │─────►│  Question Parser   │               │
│  └───────────────────┘      └───────────────────┘               │
│           │                           │                           │
│           │                           ▼                           │
│           │              ┌───────────────────────┐               │
│           │              │  Time/Space Search    │               │
│           │              │  (Parquet + Memory)   │               │
│           │              └───────────────────────┘               │
│           │                           │                           │
│           │                           ▼                           │
│           │              ┌───────────────────────┐               │
│           │              │  Response Generator   │               │
│           │              └───────────────────────┘               │
│           │                           │                           │
│           ▼                           ▼                           │
│  ┌───────────────────┐      ┌───────────────────┐               │
│  │  TTS (Piper)      │◄─────│  Natural Language │               │
│  └───────────────────┘      └───────────────────┘               │
│           │                                                       │
│           ▼                                                       │
│  Agent (via headset): "Last Tuesday July 15th, you caught 8     │
│   king salmon averaging 14.2 pounds between 8am and 2pm in     │
│   Chatham Strait near Point Arden. Water temperature was        │
│   11.5°C, fish were at 35-40 fathoms. Success rate was 67%     │
│   higher than your seasonal average."                            │
│           │                                                       │
│           ▼                                                       │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  AUTO-LOG TO MARKDOWN (with anchors)                      │  │
│  │  • timestamp_ns: 1721741135000000000                        │  │
│  │  • location: 56.3°N, -134.5°W                              │  │
│  │  • question: "How did we do here last Tuesday?"            │  │
│  │  • answer: [full response text]                            │  │
│  │  • context: {date: "2026-07-15", location: "Chatham Strait"}│ │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Auto-Logged Markdown Format

Every voice conversation is automatically logged to a Markdown file with full time/location/source anchoring:

```markdown
---
type: voice_conversation
timestamp_ns: 1721741135000000000
location:
  latitude: 56.3
  longitude: -134.5
  h3_index: "0x8a21104523fffff"
vessel_id: "US-AK-FVCATCHER-01"
source: "phone_voice_interface"
version: "1.0.0"
---

# Voice Conversation - 2026-07-24 14:32:15 AKST

## Context
- **Location:** 56.3°N, -134.5°W (Chatham Strait near Point Arden)
- **Device:** Phone (Voice-first interface)
- **Headset:** Bluetooth (preferred)

## Question
*"How did we do here last Tuesday?"*

## Answer
Last Tuesday July 15th, you caught 8 king salmon averaging 14.2 pounds between 8am and 2pm in Chatham Strait near Point Arden.

**Details:**
- **Date:** July 15, 2026
- **Time Range:** 08:00 - 14:00 AKST
- **Location:** Chatham Strait near Point Arden
- **Species:** King Salmon (Oncorhynchus tshawytscha)
- **Count:** 8 fish
- **Average Weight:** 14.2 lbs
- **Depth Range:** 35-40 fathoms
- **Water Temperature:** 11.5°C

**Comparison:**
- Success rate was 67% higher than your seasonal average
- This location has been productive on 4 out of 5 visits this season

## Follow-up Questions
*"What depth were they at?"*
*"What's the best tide for this spot?"*
*"How does this compare to last year?"*

## Metadata
- **Query Duration:** 3.2 seconds
- **Data Sources:** catch_events_2026-07-15, acoustic_data_2026-07-15
- **Confidence:** High (verified catch log data)
- **Related Conversations:**
  - [2026-07-20 09:15] "Best spots for king salmon this week?"
  - [2026-07-10 16:42] "Chatham Strait patterns July 2025"
```

---

## Time/Space Search for Similar Questions

When a question is asked, the system first searches for similar conversations that already have processed answers:

```typescript
interface VoiceConversationSearch {
  // Search by semantic similarity
  semanticSimilarity(query: string): Conversation[];

  // Search by time proximity
  timeProximity(timestamp_ns: number, window_hours: number): Conversation[];

  // Search by spatial proximity (H3 cells)
  spatialProximity(h3_index: string, resolution: number): Conversation[];

  // Combined search (time + space + semantics)
  contextSearch(query: string, context: SearchContext): Conversation[];
}

interface SearchContext {
  time?: { start: number; end: number };
  location?: { h3_index: string; resolution: number };
  season?: 'spring' | 'summer' | 'fall' | 'winter';
  species?: string[];
}

// Example search flow
const search = new VoiceConversationSearch();

// Captain asks: "How's the fishing been here this week?"
const similar = search.contextSearch("How's the fishing been here this week?", {
  location: { h3_index: currentH3, resolution: 8 },
  time: { start: sevenDaysAgo, end: now },
  season: 'summer'
});

// If similar conversation found (< 3 days old, same H3 cell):
if (similar.length > 0 && similar[0].age_hours < 72) {
  return similar[0].answer;  // Reuse processed thought
}

// Otherwise, query Parquet archive and process new answer
const answer = await queryParrchiveAndAnalyze();
return answer;
```

---

## Phone UX Scenarios

### Scenario 1: On-Grounds Pattern Query

**Context:** Captain is on the grounds, trolling, wants to know historical performance

**Conversation:**
```
Captain: "How did we do here on this tide last week?"

Agent: "Last Tuesday on this flood tide, you caught 6 chum between
2pm and 4pm at 38 fathoms. Water was 12°C, wind was NW 10 knots.
Success rate was 40% above average for this spot."

[Auto-logged to Markdown with GPS position from current location]
```

**Value:** Captain gets immediate context without stopping work or touching screens.

### Scenario 2: Seasonal Pattern Query

**Context:** Captain is planning the season, wants to know multi-year patterns

**Conversation:**
```
Captain: "When's the best time for king salmon in Chatham Strait?"

Agent: "Based on 5 years of data, king salmon peak in Chatham Strait
is July 15-25. Best time of day is 6-10am. Best depth is 35-45 fathoms.
Water temperature optimum is 11-13°C. Success rate drops 30% outside
these parameters."

[Auto-logged to Markdown with timestamp]
```

**Value:** Captain gets synthesized multi-year intelligence without manual analysis.

### Scenario 3: Real-Time Comparison

**Context:** Captain is fishing, wants to know how current conditions compare to history

**Conversation:**
```
Captain: "How does today compare to last year at this spot?"

Agent: "Last year at this location, you caught 4 fish averaging 11.2 lbs.
Today so far, you've caught 3 averaging 13.1 lbs. Water temperature
is similar (12.1°C today vs 11.8°C last year), but wind is stronger
(NW 15 knots vs NW 8 knots). Depth is the same at 40 fathoms."

[Auto-logged to Markdown with current conditions]
```

**Value:** Captain gets real-time context without manually checking workstations.

---

## Voice-First Interface Architecture

```typescript
interface VoiceFirstInterface {
  // Input (STT)
  listen(): Promise<string>;
  detectWakeWord(): boolean;

  // Processing
  parseQuery(text: string): ParsedQuery;
  searchMemory(query: ParsedQuery): VoiceConversation | null;
  generateAnswer(query: ParsedQuery): Promise<string>;

  // Output (TTS)
  speak(text: string): Promise<void>;

  // Logging
  logToMarkdown(conversation: VoiceConversation): Promise<void>;

  // Search
  findSimilarConversations(query: string, context: SearchContext): VoiceConversation[];
}

interface ParsedQuery {
  original: string;
  intent: string;
  time_range?: { start: number; end: number };
  location?: { h3_index: string; resolution: number };
  species?: string[];
  entities: Entity[];
}

interface VoiceConversation {
  id: string;
  timestamp_ns: number;
  location: { lat: number; lon: number; h3_index: string };
  question: string;
  answer: string;
  context: any;
  metadata: {
    query_duration_ms: number;
    data_sources: string[];
    confidence: number;
    related_conversations: string[];
  };
}
```

---

## Phone-Specific Features

### Wake Word Activation
- **Wake Word:** "Hey F/V EILEEN" or "Hey Captain"
- **Activation:** Hands-free, headset-optimized
- **Context:** Always listening (local processing)

### Two-Way Conversation
- **STT:** Whisper (local, <500ms latency)
- **TTS:** Piper (local, <200ms latency)
- **Natural:** Conversational, not command-based
- **Context:** Remembers conversation history

### Automatic Logging
- **Every conversation** logged to Markdown
- **Full anchoring:** time/location/source
- **Searchable:** Future queries find past answers
- **Versioned:** All conversations preserved

### Headset Optimization
- **Bluetooth:** Primary interface
- **Wired:** Fallback option
- **Phone speaker:** Last resort (noisy environments)
- **Microphone:** Noise-canceling preferred

---

## Workstation vs Phone Interaction Matrix

| Aspect | Workstation | Phone |
|--------|-------------|-------|
| **Primary Use** | Active creation & analysis | Retrospective voice queries |
| **Interaction** | Chatbot panel + IDE/DAW/Chart | Two-way STT/TTS conversation |
| **Focus** | Real-time analysis, visualization | Historical patterns, knowledge retrieval |
| **Viewers** | 3 viewers (IDE, DAW, Chart) | None (voice-first) |
| **Input** | Keyboard + mouse + voice | Voice (headset) |
| **Output** | Visual + voice | Voice (headset) |
| **Document Creation** | Yes (Markdown editor) | No (auto-logged conversations) |
| **Data Visualization** | Yes (DAW, charts) | No (voice description only) |
| **Query Type** | Active ("Create summary") | Retrospective ("How did we do?") |
| **Typical Context** | In wheelhouse, at anchor | On grounds, in bunk, anywhere |
| **Knowledge Capture** | Manual documents | Auto-logged conversations |
| **Screen Dependency** | Required (large display) | Optional (small display) |

---

## Technical Implementation

### STT (Speech-to-Text)

**Whisper.cpp (Local)**
- Model: base (~140MB) or small (~70MB)
- Latency: <500ms
- Accuracy: 95%+ with marine vocabulary
- Platform: Runs on phone via mobile app

```typescript
interface STTConfig {
  model: 'base' | 'small' | 'medium';
  language: 'en';
  vocabulary: string[];  // Marine-specific terms
  latency_target_ms: 500;
}
```

### TTS (Text-to-Speech)

**Piper TTS (Local)**
- Voice: vessel-en-us (trained on captain's voice ideally)
- Latency: <200ms
- Quality: Natural, conversational
- Platform: Runs on phone via mobile app

```typescript
interface TTSConfig {
  voice: 'vessel-en-us' | 'en-us-lessac';
  rate: 1.0;  // Speed
  pitch: 1.0;  // Pitch
  volume: 0.8;  // Volume
  latency_target_ms: 200;
}
```

### Conversation Storage

**Markdown Files with Frontmatter**
- Location: `/conversations/2026/07/24/`
- Format: `conversation-{timestamp_ns}.md`
- Anchoring: Full time/location/source metadata
- Search: Indexed by Elasticsearch/Lunr

```typescript
interface ConversationStorage {
  save(conversation: VoiceConversation): Promise<string>;
  search(query: SearchQuery): Promise<VoiceConversation[]>;
  getByTimeRange(start: number, end: number): Promise<VoiceConversation[]>;
  getByLocation(h3_index: string): Promise<VoiceConversation[]>;
}
```

---

## Integration with Workstation

### Phone Conversations → Workstation Documents

When a phone conversation reveals insights, they can be elevated to workstation documents:

```typescript
// Phone conversation identifies pattern
const conversation = await phone.voiceQuery("What's the best tide for this spot?");
// Answer: "Flood tide has 67% success rate, ebb tide has 33%"

// Captain: "Save this to my patterns"
await phone.elevateToDocument(conversation.id, 'patterns/king_salmon_tides.md');

// Workstation now has formal document
// Phone can reference it in future conversations
```

### Workstation Documents → Phone Answers

When workstation creates analysis, phone can query it:

```typescript
// Workstation creates daily summary
const summary = await workstation.createDailySummary('2026-07-23');

// Phone can now answer questions about it
const answer = await phone.voiceQuery("What was yesterday's catch?");
// Answer drawn from workstation-generated summary
```

---

## Success Metrics

### Phone UX Metrics

**Query Performance:**
- STT latency: <500ms
- Query processing: <2s
- TTS latency: <200ms
- Total response time: <3s

**Knowledge Capture:**
- 100% of conversations logged to Markdown
- Full time/location/source anchoring
- Searchable within 1 second

**Search Performance:**
- Similar question found: <500ms (cache hit)
- New question processed: <2s (cache miss)
- Cache hit rate target: >40%

**User Experience:**
- Wake word detection: >95%
- Voice recognition accuracy: >95%
- Conversation naturalness: >4/5 user rating
- Hands-free operation: 100% of scenarios

---

## Next Steps

1. ✅ **Phone UX Architecture** (This document)
2. 🔄 **STT/TTS Integration** (Whisper + Piper)
3. 🔄 **Conversation Logging** (Markdown with anchors)
4. 🔄 **Time/Space Search** (Semantic similarity)
5. 🔄 **Workstation Integration** (Document elevation)

---

**Document Version:** 1.0
**Date:** 2026-07-24
**Status:** Phone UX Architecture Complete → Implementation Planning
**Device:** Phone (Headset-Optimized, Voice-First)

---

*"The ocean forgets nothing. The vessel agent remembers everything. The phone never forgets a conversation."*
