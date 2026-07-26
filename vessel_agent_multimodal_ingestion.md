# Multi-Modal Data Ingestion Architecture

**Date:** 2026-07-24
**Status:** Architecture Specification
**Purpose:** Phone and laptop as multi-modal data sources for vessel knowledge repository

---

## Overview

The phone and laptop are **not just interfaces** - they are **primary data ingestion points** for the vessel's knowledge repository. Every piece of information that matters in time gets:

1. **Time/Location/Source anchored** (Triply anchored)
2. **Ingested into the knowledge repository** (not Git repo)
3. **Made available across all viewers** (DAW, Markdown, Spatial)

---

## Data Source Categories

### 1. Human-Reported Information (Phone)

#### Fleet Trade Information
**Example:** Fellow boat reports catch locations

**Conversation:**
```
Captain (via phone): "Hey vessel agent, the F/V Osprey just radioed they're
hearing catches at Point Arden, 40 fathoms, chum salmon, flood tide"
```

**Ingestion:**
```json
{
  "type": "fleet_report",
  "timestamp_ns": 1721741135000000000,
  "source": "phone_voice_input",
  "reporter": "US-AK-FVCATCHER-01",
  "informant": {
    "vessel": "F/V Osprey",
    "vessel_id": "US-AK-FVCATCHER-02",
    "communication_method": "VHF radio"
  },
  "location": {
    "name": "Point Arden",
    "h3_index": "0x8a21104523fffff",
    "depth_fm": 40,
    "approximate": true
  },
  "catch_info": {
    "species": "chum_salmon",
    "tide": "flood",
    "confidence": "reported_by_crew"
  },
  "verification": "pending"
}
```

**Storage:** `/fleet_reports/2026/07/24/report-{timestamp_ns}.json`
**DAW Visualization:** Appears on "Fleet Intelligence" track
**Spatial Overlay:** Point Arden highlighted with confidence indicator

---

### 2. Visual Data Capture (Phone)

#### Photo/Video Ingestion
**Example:** Captain takes photo of unusual water condition

**Conversation:**
```
Captain (via phone): "Take a picture of this slick"
[Phone captures photo with timestamp + GPS]
Captain: "Send this to the agent"
```

**Ingestion:**
```json
{
  "type": "visual_observation",
  "timestamp_ns": 1721741135000000000,
  "source": "phone_camera",
  "media_type": "photo",
  "file_path": "/repository/visual/2026/07/24/{timestamp_ns}.jpg",
  "location": {
    "latitude": 56.3,
    "longitude": -134.5,
    "h3_index": "0x8a21104523fffff"
  },
  "context": {
    "captain_note": "Unusual slick - potential bait ball",
    "weather_conditions": "calm, overcast",
    "time_of_day": "morning"
  },
  "analysis": {
    "detected_features": ["surface_slick", "bird_activity"],
    "confidence": 0.87
  }
}
```

**Storage:**
- Photo: `/repository/visual/2026/07/24/photos/{timestamp_ns}.jpg`
- Metadata: `/repository/visual/2026/07/24/metadata/{timestamp_ns}.json`

**DAW Visualization:** Appears on "Environmental/Observations" track
**Spatial Overlay:** Photo marker at GPS location
**Markdown Reference:** Auto-linked in daily summary

---

### 3. Environmental Data Streams (Laptop)

#### Weather Information
**Source:** Laptop weather API (NOAA, Weather.gov, etc.)

**Ingestion:**
```json
{
  "type": "weather_observation",
  "timestamp_ns": 1721741135000000000,
  "source": "laptop_weather_api",
  "provider": "NOAA",
  "location": {
    "latitude": 56.3,
    "longitude": -134.5,
    "h3_index": "0x8a21104523fffff"
  },
  "conditions": {
    "wind_speed_knots": 12,
    "wind_direction_deg": 320,
    "wind_gust_knots": 18,
    "air_temp_c": 14.2,
    "sea_level_pressure_mb": 1013.2,
    "visibility_nm": 10,
    "cloud_cover_pct": 75,
    "precipitation_type": "none"
  },
  "forecast": {
    "next_6_hours": {
      "wind_trend": "increasing",
      "temp_trend": "stable",
      "precipitation_probability": 0.1
    }
  }
}
```

**Storage:** `/repository/weather/2026/07/24/{timestamp_ns}.json`
**DAW Track:** "Weather" - continuous graph
**Spatial Overlay:** Wind arrows at vessel position
**Markdown Reference:** Weather summary in daily log

---

#### Tide Information
**Source:** Laptop tide API (NOAA Tides & Currents)

**Ingestion:**
```json
{
  "type": "tide_observation",
  "timestamp_ns": 1721741135000000000,
  "source": "laptop_tide_api",
  "provider": "NOAA Tides & Currents",
  "station_id": "8454560",  // Point Arden
  "location": {
    "name": "Point Arden",
    "latitude": 56.3,
    "longitude": -134.5,
    "h3_index": "0x8a21104523fffff"
  },
  "tide": {
    "type": "flood",
    "height_m": 3.2,
    "sl_time": "2026-07-24T14:32:00Z",
    "range_m": 2.8,
    "current_speed_mps": 1.2
  },
  "prediction": {
    "next_high_slack": "2026-07-24T16:45:00Z",
    "next_low_slack": "2026-07-24T22:30:00Z"
  }
}
```

**Storage:** `/repository/tides/2026/07/24/{timestamp_ns}.json`
**DAW Track:** "Tides" - continuous graph
**Spatial Overlay:** Tide vectors at station locations
**Markdown Reference:** Tide summary in daily log

---

### 4. Market Information (Laptop)

**Source:** Laptop market API (fish auctions, price boards)

**Ingestion:**
```json
{
  "type": "market_price",
  "timestamp_ns": 1721741135000000000,
  "source": "laptop_market_api",
  "provider": "Sitka Fish Auction",
  "species": "king_salmon",
  "prices": {
    "per_lbs": 7.50,
    "currency": "USD",
    "trend": "rising"
  },
  "volume": {
    "total_lbs": 15000,
    "your_share_lbs": null
  },
  "quality_adjustments": {
    "premium_grades": "+1.50/lbs",
    "bonus_for": "bled_iced, >24hr"
  }
}
```

**Storage:** `/repository/market/2026/07/24/{timestamp_ns}.json`
**DAW Track:** "Market Prices" - discrete events
**Markdown Reference:** Price summary in catch analysis
**Spatial Overlay:** N/A (market is spatial, not location-specific)

---

## Complete Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    MULTI-MODAL DATA INGESTION                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                      PHONE (Data Sources)                    ││
│  │  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐ ││
│  │  │ Voice Input     │  │ Camera         │  │ Touch Input   │ ││
│  │  │ (Fleet reports) │  │ (Photos/Videos)│  │ (Manual entry)│ ││
│  │  └────────┬───────┘  └────────┬───────┘  └───────┬───────┘ ││
│  └───────────┼──────────────────┼───────────────────┼─────────┘│
│              │                  │                   │           │
│              ▼                  ▼                   ▼           │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              VESSEL AGENT BACKEND (Ingestion)                ││
│  │  • Time/Location/Source anchoring                             ││
│  │  • Validation and enrichment                                ││
│  │  • Metadata extraction                                       ││
│  └───────────┬───────────────────────────────────────────────────┘│
│              │                                                   │
│              ▼                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              KNOWLEDGE REPOSITORY (Storage)                  ││
│  │  ┌─────────────────────────────────────────────────────────┐││
│  │  │ /repository/                                             │││
│  │  │  ├── fleet_reports/     (JSON)                          │││
│  │  │  ├── visual/             (Photos/Videos + JSON)          │││
│  │  │  ├── weather/            (JSON)                          │││
│  │  │  ├── tides/              (JSON)                          │││
│  │  │  ├── market/             (JSON)                          │││
│  │  │  ├── nmea0183/           (NDJSON - from boat-agent)      │││
│  │  │  ├── acoustic/           (Parquet - from boat-agent)     │││
│  │  │  ├── catch_events/       (JSON)                          │││
│  │  │  └── conversations/      (Markdown - from phone)         │││
│  │  └─────────────────────────────────────────────────────────┘││
│  └─────────────────────────────────────────────────────────────┘│
│              │                                                   │
│              ▼                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              DISTRIBUTION TO VIEWERS                         ││
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐ ││
│  │  │ DAW      │  │ Markdown │  │ Spatial  │  │ Phone Voice  │ ││
│  │  │ Timeline │  │ Editor   │  │ Chart    │  │ Response     │ ││
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────┘ ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Ingestion by Source Type

### Phone Ingestion Sources

| Source | Data Type | Storage Format | DAW Track | Spatial | Markdown |
|--------|-----------|----------------|-----------|---------|----------|
| **Voice Input** | Fleet reports | JSON | Fleet Intelligence | Point marker | Linked |
| **Camera** | Photos | JPG + JSON | Observations | Photo marker | Auto-linked |
| **Camera** | Videos | MP4 + JSON | Observations | Video marker | Auto-linked |
| **Touch Input** | Manual notes | JSON + Markdown | Notes | Point marker | Full text |
| **Microphone** | Audio recordings | WAV + JSON | Audio | Point marker | Transcribed |

### Laptop Ingestion Sources

| Source | Data Type | Storage Format | DAW Track | Spatial | Markdown |
|--------|-----------|----------------|-----------|---------|----------|
| **NMEA 0183** | GPS/Depth/Sensor | NDJSON | Sensors | Vessel track | Summary |
| **Weather API** | Wind/Temp/Pressure | JSON | Weather | Grid overlay | Summary |
| **Tide API** | Water level/currents | JSON | Tides | Station vectors | Summary |
| **Market API** | Fish prices | JSON | Market | N/A | Analysis |
| **Browser** | Manual data entry | JSON + Markdown | Notes | Point marker | Full text |

---

## DAW Visualization by Data Type

### Continuous Data (Graphed)
```
Track: NMEA Sensors
├── GPS Speed Over Ground (continuous line)
├── Depth (continuous line)
├── Engine RPM (continuous line)
└── Water Temperature (continuous line)

Track: Weather
├── Wind Speed (continuous line)
├── Wind Direction (continuous line)
├── Barometric Pressure (continuous line)
└── Air Temperature (continuous line)

Track: Tides
├── Water Level (continuous line)
├── Current Speed (continuous line)
└── Current Direction (continuous line)
```

### Discrete Data (Events)
```
Track: Fleet Intelligence
├── F/V Osprey report (point event)
├── F/V Mary Ann report (point event)
└── VHF chatter summary (point event)

Track: Market Prices
├── King salmon price update (point event)
├── Chum salmon price update (point event)
└── Sockeye salmon price update (point event)

Track: Catch Events
├── King salmon landed (point event)
├── Chum salmon landed (point event)
└── Species confirmed (point event)
```

### Visual Data (Embedded)
```
Track: Visual Observations
├── Photo: Unusual slick (thumbnail + time)
├── Video: Bird activity (thumbnail + time)
└── Screenshot: Sounder display (thumbnail + time)
```

---

## Spatial Visualization by Data Type

### Point-Based Overlays
```
Spatial Layer: Fleet Reports
├── F/V Osprey at Point Arden (blue circle)
├── F/V Mary Ann at Gary's knob (blue circle)
└── VHF reported activity (heatmap)

Spatial Layer: Visual Observations
├── Photo: Slick at 56.3°N, -134.5°W (camera icon)
├── Video: Birds at 56.31°N, -134.52°W (video icon)
└── Screenshot: Sounder marks (screen icon)

Spatial Layer: Catch Locations
├── King salmon at Point Arden (fish icon)
├── Chum salmon at Gary's knob (fish icon)
└── Mixed species at Inner Point (fish icon)
```

### Grid-Based Overlays
```
Spatial Layer: Weather
├── Wind speed grid (colored arrows)
├── Temperature grid (colored cells)
└── Pressure grid (isobars)

Spatial Layer: Tides
├── Current speed at stations (colored arrows)
├── Water level at stations (colored circles)
└── Slack water times (text labels)
```

---

## Markdown Integration by Data Type

### Auto-Generated Markdown Sections

```markdown
# Daily Summary - 2026-07-24

## Fleet Intelligence
- **08:32** - F/V Osprey reports chum at Point Arden, 40fm, flood tide
- **10:15** - VHF chatter: Good marks heard near Gary's knob
- **14:45** - F/V Mary Ann reports slow fishing inside

## Weather Conditions
- **Wind:** NW 12 gusting to 18 knots
- **Temperature:** 14.2°C (57°F)
- **Pressure:** 1013.2 mb (steady)
- **Visibility:** 10 nm
- **Forecast:** Winds increasing, front approaching

## Tide Summary
- **Current Tide:** Flood (3.2m at 14:32)
- **Next High Slack:** 16:45 (3.8m)
- **Next Low Slack:** 22:30 (0.8m)
- **Range:** 2.8m (moderate)

## Market Prices
- **King Salmon:** $7.50/lbs (rising trend)
- **Chum Salmon:** $3.25/lbs (stable)
- **Sockeye Salmon:** $5.75/lbs (falling)

## Visual Observations
- [Photo] Unusual slick at 08:45 - potential bait ball
- [Screenshot] Sounder showing school at 35fm
- [Video] Bird activity over slick

## Catch Performance
- **Total Catch:** 12 fish (8 king, 4 chum)
- **Average Weight:** 12.4 lbs
- **Best Location:** Point Arden (40fm, flood tide)
- **Best Time:** 08:00-10:00

## NMEA Sensor Summary
- **Total Pings:** 14,532
- **Data Gaps:** 0
- **GPS Health:** Excellent (HDOP 0.8)
- **Sounder Health:** Good (bottom tracking continuous)
```

---

## Knowledge Repository Structure

### Directory Layout
```
/repository/
├── fleet_reports/
│   └── 2026/07/24/
│       └── report-{timestamp_ns}.json
├── visual/
│   ├── 2026/07/24/
│   │   ├── photos/
│   │   │   └── {timestamp_ns}.jpg
│   │   ├── videos/
│   │   │   └── {timestamp_ns}.mp4
│   │   └── metadata/
│   │       └── {timestamp_ns}.json
├── weather/
│   └── 2026/07/24/
│       └── {timestamp_ns}.json
├── tides/
│   └── 2026/07/24/
│       └── {timestamp_ns}.json
├── market/
│   └── 2026/07/24/
│       └── {timestamp_ns}.json
├── nmea0183/
│   └── 2026/07/24/
│       └── nmea_{date}.ndjson
├── acoustic/
│   └── 2026/07/24/
│       └── acoustic_{date}.parquet
├── catch_events/
│   └── 2026/07/24/
│       └── catch_{timestamp_ns}.json
├── conversations/
│   └── 2026/07/24/
│       └── conversation-{timestamp_ns}.md
└── summaries/
    └── 2026/07/24/
        └── daily_summary.md
```

### Not Git Repository

**Why not Git?**
- Binary data (photos/videos) not suited for Git
- Large time-series data (acoustic, NMEA) not suited for Git
- Frequent updates would create massive commit history
- Merge conflicts undesirable for multi-source data

**Alternative:** Versioned file system with:
- Immutable files (never overwritten)
- Time-based partitioning
- Hash-based references
- Optional cloud backup (rsync, S3)

---

## Ingestion API Examples

### Fleet Report Ingestion (Voice)
```typescript
interface FleetReportInput {
  vessel: string;
  location: string;
  depth_fm: number;
  species: string;
  tide: string;
  communication_method: 'vhf_radio' | 'cell_phone' | 'in_person';
}

// Voice input processed
const report: FleetReport = {
  type: 'fleet_report',
  timestamp_ns: Date.now() * 1_000_000,
  source: 'phone_voice_input',
  informant: {
    vessel: 'F/V Osprey',
    vessel_id: 'US-AK-FVCATCHER-02',
    communication_method: 'vhf_radio'
  },
  location: {
    name: 'Point Arden',
    h3_index: '0x8a21104523fffff',
    depth_fm: 40
  },
  catch_info: {
    species: 'chum_salmon',
    tide: 'flood'
  }
};

// Store in repository
await repository.store('/fleet_reports/2026/07/24/', report);

// Distribute to viewers
await daw.addEvent('Fleet Intelligence', report);
await spatial.addMarker('Fleet Reports', report.location, 'F/V Osprey');
await markdown.addSection('Fleet Intelligence', formatReport(report));
```

### Visual Observation Ingestion (Camera)
```typescript
interface VisualObservationInput {
  media_type: 'photo' | 'video';
  file_path: string;
  captain_note: string;
  location?: { latitude: number; longitude: number };
}

// Camera capture
const observation: VisualObservation = {
  type: 'visual_observation',
  timestamp_ns: Date.now() * 1_000_000,
  source: 'phone_camera',
  media_type: 'photo',
  file_path: '/repository/visual/2026/07/24/photos/' + timestamp_ns + '.jpg',
  location: {
    latitude: 56.3,
    longitude: -134.5,
    h3_index: '0x8a21104523fffff'
  },
  context: {
    captain_note: 'Unusual slick - potential bait ball'
  }
};

// Store media and metadata
await repository.storeMedia(observation.file_path, photoData);
await repository.store('/repository/visual/2026/07/24/metadata/', observation);

// Distribute to viewers
await daw.addEvent('Observations', observation);
await spatial.addMarker('Visual Observations', observation.location, '📷');
await markdown.addImage('Visual Observations', observation.file_path, observation.context.captain_note);
```

### Weather Data Ingestion (Laptop API)
```typescript
interface WeatherDataInput {
  provider: string;
  conditions: WeatherConditions;
  forecast: WeatherForecast;
}

// API poll
const weather: WeatherObservation = {
  type: 'weather_observation',
  timestamp_ns: Date.now() * 1_000_000,
  source: 'laptop_weather_api',
  provider: 'NOAA',
  location: currentVesselLocation,
  conditions: {
    wind_speed_knots: 12,
    wind_direction_deg: 320,
    air_temp_c: 14.2
  },
  forecast: {
    next_6_hours: { wind_trend: 'increasing' }
  }
};

// Store in repository
await repository.store('/weather/2026/07/24/', weather);

// Distribute to viewers
await daw.addContinuousData('Weather', weather);
await spatial.addGridOverlay('Weather', weatherForecastGrid);
await markdown.addSection('Weather', formatWeather(weather));
```

---

## Cross-Viewer Data Flow

```
FLEET REPORT (Voice Input)
    │
    ├──► DAW Timeline ──► Fleet Intelligence Track (point event)
    ├──► Spatial Chart ──► Point Arden marker (blue circle)
    └──► Markdown ──────► Fleet Intelligence section (linked)
        │
        └──► Phone Voice Response ──► "F/V Osprey reports chum at Point Arden"

VISUAL OBSERVATION (Camera)
    │
    ├──► DAW Timeline ──► Observations Track (thumbnail + time)
    ├──► Spatial Chart ──► Photo marker (camera icon)
    └──► Markdown ──────► Visual Observations section (auto-linked)
        │
        └──► Phone Voice Response ──► "Photo logged at 56.3°N, -134.5°W"

WEATHER DATA (Laptop API)
    │
    ├──► DAW Timeline ──► Weather Track (continuous graph)
    ├──► Spatial Chart ──► Wind arrows overlay
    └──► Markdown ──────► Weather Conditions section (summary)
        │
        └──► Phone Voice Response ──► "Wind NW 12 knots, temperature 14.2°C"

TIDE DATA (Laptop API)
    │
    ├──► DAW Timeline ──► Tides Track (continuous graph)
    ├──► Spatial Chart ──► Tide vectors at stations
    └──► Markdown ──────► Tide Summary section (summary)
        │
        └──► Phone Voice Response ──► "Current tide: flood at 3.2m, next high slack at 16:45"

MARKET DATA (Laptop API)
    │
    ├──► DAW Timeline ──► Market Prices Track (point events)
    ├──► Spatial Chart ──► N/A (market is not location-specific)
    └──► Markdown ──────► Market Prices section (analysis)
        │
        └──► Phone Voice Response ──► "King salmon $7.50/lbs, rising trend"
```

---

## Temporal Graphing in DAW

### Everything That Matters in Time

```
DAW TIMELINE VIEW (24 hours)
│
├── 00:00 ────────────────────────────────────────────────────── 24:00
│   ┌─────────────────────────────────────────────────────────────┐
│   │ NMEA SENSORS (Continuous)                                   │
│   │  • Speed Over Ground ────────────────────                   │
│   │  • Depth ─────────────────────────────                      │
│   │  • Water Temperature ───────────────────                   │
│   └─────────────────────────────────────────────────────────────┘
│
│   ┌─────────────────────────────────────────────────────────────┐
│   │ WEATHER (Continuous)                                         │
│   │  • Wind Speed ───────────────────────────                  │
│   │  • Wind Direction ─────────────────────                     │
│   │  • Barometric Pressure ─────────────────                    │
│   └─────────────────────────────────────────────────────────────┘
│
│   ┌─────────────────────────────────────────────────────────────┐
│   │ TIDES (Continuous)                                          │
│   │  • Water Level ───────────────────────────                  │
│   │  • Current Speed ────────────────────────                   │
│   └─────────────────────────────────────────────────────────────┘
│
│   ┌─────────────────────────────────────────────────────────────┐
│   │ FLEET INTELLIGENCE (Events)                                 │
│   │  08:32 ● F/V Osprey report                                  │
│   │  10:15 ● VHF chatter                                        │
│   │  14:45 ● F/V Mary Ann report                                │
│   └─────────────────────────────────────────────────────────────┘
│
│   ┌─────────────────────────────────────────────────────────────┐
│   │ MARKET PRICES (Events)                                      │
│   │  06:00 ● King salmon: $7.50/lbs                             │
│   │  12:00 ● Chum salmon: $3.25/lbs                             │
│   └─────────────────────────────────────────────────────────────┘
│
│   ┌─────────────────────────────────────────────────────────────┐
│   │ CATCH EVENTS (Events)                                       │
│   │  08:15 ● King salmon (14.2 lbs)                            │
│   │  09:45 ● Chum salmon (8.4 lbs)                              │
│   │  14:20 ● King salmon (15.1 lbs)                            │
│   └─────────────────────────────────────────────────────────────┘
│
│   ┌─────────────────────────────────────────────────────────────┐
│   │ VISUAL OBSERVATIONS (Events)                                │
│   │  08:45 📷 Photo: Unusual slick                              │
│   │  10:20 📹 Video: Bird activity                              │
│   │  14:30 🖥️ Screenshot: Sounder display                       │
│   └─────────────────────────────────────────────────────────────┘
│
│   ┌─────────────────────────────────────────────────────────────┐
│   │ PHONE CONVERSATIONS (Events)                                │
│   │  07:30 💬 "How did we do here last Tuesday?"              │
│   │  12:15 💬 "What's the best tide for this spot?"            │
│   │  18:45 💬 "F/V Osprey reports chum at Point Arden"         │
│   └─────────────────────────────────────────────────────────────┘
```

---

## Success Metrics

### Ingestion Performance
- Voice processing latency: <500ms
- Photo storage time: <2s
- Video storage time: <5s
- Weather API poll: <1s
- Market API poll: <1s

### Data Quality
- 100% of data time/location/source anchored
- 0% data loss (redundant storage)
- 99.9% query availability

### Cross-Viewer Sync
- DAW update latency: <1s
- Spatial overlay update: <1s
- Markdown update: <2s
- Phone voice response: <3s total

---

## Next Steps

1. ✅ **Multi-modal ingestion architecture** (This document)
2. 🔄 **Ingestion API implementation**
3. 🔄 **Repository structure setup**
4. 🔄 **DAW track definitions**
5. 🔄 **Spatial overlay system**
6. 🔄 **Markdown auto-generation**

---

**Document Version:** 1.0
**Date:** 2026-07-24
**Status:** Multi-Modal Ingestion Architecture Complete

---

*"The ocean forgets nothing. The vessel agent remembers everything - from voice reports to photos, from weather to market prices."*
