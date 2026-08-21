# DAW Timeline Interface Patterns for Marine Vessel Telemetry

**Research Document:** Adapting Digital Audio Workstation timeline patterns for AELMA marine telemetry visualization

**Date:** 2026-07-28
**Status:** Research & Architecture Analysis
**Target System:** AELMA Phase 5 Viewer Interface

---

## Executive Summary

Digital Audio Workstations (DAWs) have evolved sophisticated timeline interfaces optimized for multi-track, real-time data visualization and manipulation. This research analyzes how DAW patterns from Ableton Live, Logic Pro, Reaper, and Bitwig Studio can be adapted for marine vessel telemetry visualization in the AELMA system.

**Key Finding:** DAW timeline patterns map exceptionally well to marine telemetry, with tracks representing data streams (NMEA, depth, speed, heading, alerts) and clips representing data segments or events. The core challenge is adapting time scales from audio (milliseconds/seconds) to operational timelines (seconds/hours/days).

---

## 1. DAW Timeline Pattern Analysis

### 1.1 Ableton Live - Arrangement View

**Pattern Characteristics:**
- **Linear Timeline:** Horizontal time axis from left to right
- **Clip-Based:** Audio/MIDI clips arranged on tracks
- **Non-Destructive:** Clips can be moved, resized, copied without affecting source
- **Real-Time:** Playback head with smooth scrubbing
- **Automation Lanes:** Separate lanes for parameter automation
- **Zoom Controls:** Horizontal (time) and vertical (track) zoom independent
- **Warp Markers:** Time stretching markers for alignment

**Key UI Elements:**
- Timeline ruler with time markers (measures/beat or timecode)
- Track headers with controls (mute, solo, arm, volume)
- Clip editors for detailed editing
- Browser panel for clip library
- Mixer/panel view
- Crossfades between clips

**Sources:**
- [Ableton Live Arrangement View - Official Manual](https://www.ableton.com/en/manual/arrangement-view/)
- [Ableton Live Redesign Concept](https://nndmlsvc.medium.com/ableton-live-redesign-26efebe73bfc)
- [Ableton UI Discussion - Reddit](https://www.reddit.com/r/ableton/comments/1e3m3z0/im_certain_theyve_purposefully_designed_abletons/)

---

### 1.2 Logic Pro - Track-Based Timeline

**Pattern Characteristics:**
- **Tracks and Regions:** Linear regions on tracks
- **Single Timeline:** One main timeline (no multiple timelines)
- **Take Folders:** Multiple takes stacked for comping
- **Flex Time:** Time stretching/compression
- **Track Stacks:** Nested track organization
- **Automation Points:** Parameter automation with curves

**Key UI Elements:**
- Track headers with icons and controls
- Region-based clips on tracks
- Piano roll for MIDI editing
- Step editor for precise automation
- Marker strips for sections

**Sources:**
- [Logic Pro Interface Guide - Apple](https://support.apple.com/en-in/guide/logicpro-ipad/lpip33be754d/ipados)
- [Logic Pro Multi-Timeline Discussion](https://www.logicprohelp.com/forums/topic/73629-multiple-timelines-organising-logic-project-like-a-nle/)
- [Logic Pro UI Tutorial - YouTube](https://www.youtube.com/watch?v=5PS2p1AZzFY)

---

### 1.3 Reaper - Multi-Track Synchronization

**Pattern Characteristics:**
- **Multi-Track Recording:** Simultaneous track recording
- **Timecode Sync:** External synchronization via MTC/MIDI clock
- **Grid Lines:** Visual reference grid
- **Item-Based:** Audio items on tracks
- **Envelope Automation:** Per-track and per-item automation
- **Grouping:** Track grouping for operations

**Key UI Elements:**
- Timeline ruler with grid lines
- Track control panel
- TCP (Track Control Panel) and MCP (Mixer Control Panel)
- Item selection and manipulation
- Envelope points and curves
- Razor editing for batch edits

**Sources:**
- [REAPER DAW Official Site](https://www.reaper.fm/)
- [Reaper Multi-Track Sync Tutorial](https://backstage.polyend.com/t/using-reaper-with-play-best-budget-daw-to-sync-midi-clock-to-and-record-in-multi-track-mode/22104)
- [Reaper Sync Setup Guide](https://non-lethal-applications.com/knowledge-base/VideoSync6/28_DAW%20Sync%20Option%2018)

---

### 1.4 Bitwig Studio - Clip Launcher + Arranger

**Pattern Characteristics:**
- **Dual Interface:** Clip Launcher (grid) + Arranger Timeline (linear)
- **Clip Aliases:** References to clips without duplication
- **Modulation System:** Per-project modulation routing
- **Layered Editing:** Multiple clip layers
- **Container Clips:** Nested clip organization

**Key UI Elements:**
- Arranger Timeline (bottom)
- Clip Launcher (top grid)
- Inspector panel
- Browser panel
- Mixer console

**Sources:**
- [Bitwig Studio User Guide PDF](https://www.bitwig.com/media/bitwig_userguide/pdf/Bitwig_Studio_User_Guide_English_G2qasDB.pdf)
- [Bitwig Clip Launcher Guide](https://www.bitwig.com/userguide/latest/the_clip_launcher)
- [Bitwig Arranger Tutorial](https://www.youtube.com/watch?v=Vx20E5qvW6A)

---

## 2. Marine Telemetry Adaptation

### 2.1 Concept Mapping: DAW → Marine

| DAW Concept | Marine Telemetry Equivalent | Data Type |
|-------------|----------------------------|-----------|
| **Audio Track** | Data Stream Track | Time series |
| **MIDI Track** | Event Track | Discrete events |
| **Audio Clip** | Data Segment | Continuous data |
| **MIDI Clip** | Event Group | Grouped events |
| **Automation Lane** | Threshold/State Lane | Parameter changes |
| **Marker** | Waypoint/Event Marker | Position marker |
| **Time Ruler** | UTC Timeline | Time scale |
| **Playhead** | Current Time Indicator | Vessel time |
| **Waveform** | Data Visualization | Chart/graph |
| **Mixer** | Data Controls | Display settings |

---

### 2.2 Track Types for Marine Telemetry

**Primary Data Tracks (Continuous):**

1. **NMEA-0183 Streams**
   - Position (GPS/GNSS)
   - Depth (sounder)
   - Speed (knots/log)
   - Heading (compass)
   - Wind (anemometer)
   - Water temperature

2. **Derived Data Tracks**
   - Course over ground (calculated)
   - Speed made good (calculated)
   - Rate of turn (calculated)
   - Acceleration (calculated)

3. **Equipment State Tracks**
   - Engine RPM
   - Fuel flow rate
   - Coolant temperature
   - Oil pressure
   - Transmission gear
   - Hydraulic pressure

4. **Environmental Tracks**
   - Air temperature
   - Barometric pressure
   - Sea state
   - Wave height
   - Tide level
   - Current speed/direction

**Event Tracks (Discrete):**

1. **Alert Events**
   - Watcher triggers
   - Threshold violations
   - Equipment faults
   - Safety events

2. **Operational Events**
   - Haul start/end
   - Gear deployment
   - Waypoint reached
   - Mode changes

3. **Compliance Events**
   - Area entry/exit
   - Gear changes
   - Catch reporting
   - Permit validations

**Automation Lanes (Parameter Changes):**

1. **Threshold Lanes**
   - Depth threshold changes
   - Speed limit adjustments
   - Equipment parameter changes

2. **State Lanes**
   - Operational mode (fishing/transit/anchored)
   - Watchkeeping status
   - Crew on watch

---

### 2.3 Clip Types for Marine Data

1. **Data Clips (Continuous)**
   - Time-bounded data segments
   - Can be moved, copied, resized
   - Visual representation: waveform-style chart
   - Example: "Haul 123 depth data"

2. **Event Clips (Discrete)**
   - Grouped events in time range
   - Markers for individual events
   - Visual representation: colored blocks with event icons
   - Example: "Haul 123 events"

3. **Annotation Clips**
   - Text notes attached to time ranges
   - Manual or automated (e.g., "Fishing intensive period")
   - Visual representation: colored label blocks

4. **Analysis Clips**
   - Derived data segments (e.g., JEPA predictions)
   - Statistical analysis results
   - Confidence intervals

---

## 3. Technical Implementation

### 3.1 Rendering Approach: Canvas vs DOM

**Canvas-Based Rendering (Recommended)**

**Advantages:**
- Performance for high-frequency real-time data (60 FPS)
- Efficient for large datasets (thousands of points)
- Smooth zoom/pan operations
- Hardware acceleration available
- Direct pixel manipulation for waveform visualization

**Disadvantages:**
- More complex implementation
- Accessibility challenges (screen readers)
- Text rendering less sharp than DOM
- Requires hit-testing for interaction

**Best Use Cases:**
- Real-time scrolling data displays
- Waveform/data visualization
- Smooth animations and transitions
- High-density data display

**Sources:**
- [Canvas vs DOM Performance Comparison](https://stackoverflow.com/questions/24019174/real-time-data-plotting-performance-html5-canvas-vs-dom-appending)
- [SciChart Real-Time Performance Demo](https://www.scichart.com/demo/javascript/chart-realtime-performance-demo)
- [WebGL vs Canvas Benchmarks](https://dev3lop.com/blog/real-time-dashboard-performance-webgl-vs-canvas-rendering-benchmarks/)
- [Canvas Performance Research](https://www.researchgate.net/publication/368518986_Web_Performance_Evaluation_of_High_Volume_Streaming_Data_Visualization)

**DOM-Based Rendering**

**Advantages:**
- Accessibility (semantic HTML, screen readers)
- CSS styling and animations
- Text handling superior
- Built-in event handling
- Easier debugging and inspection

**Disadvantages:**
- Performance limitations with many elements
- Memory overhead per element
- Layout thrashing with frequent updates
- Limited smooth animation performance

**Best Use Cases:**
- Track headers and controls
- Timeline ruler and markers
- Event markers and labels
- UI overlays and panels

**Hybrid Approach (Recommended for AELMA):**
- **Canvas:** Main timeline data visualization
- **DOM:** Track headers, controls, overlays, tooltips

---

### 3.2 Real-Time Data Performance

**Performance Targets:**

| Metric | Target | Notes |
|--------|--------|-------|
| **Frame Rate** | 60 FPS | Smooth scrolling and zoom |
| **Update Rate** | 10-30 Hz | Real-time data ingestion |
| **Data Points** | 10,000+ per track | Hours of data at 1 Hz |
| **Zoom Response** | < 100ms | Interactive zoom |
| **Pan Response** | < 50ms | Smooth scrubbing |
| **Memory** | < 500 MB | Full system with multiple tracks |

**Optimization Strategies:**

1. **Data Decimation**
   - Downsample data for zoomed-out views
   - Keep full resolution for zoomed-in views
   - Use RDP (Ramer-Douglas-Peucker) algorithm for line simplification
   - Level-of-detail (LOD) based on zoom level

2. **Canvas Rendering**
   - Use offscreen canvas for pre-rendering
   - Render only visible viewport
   - Use `requestAnimationFrame` for smooth updates
   - Batch draw operations
   - Use integer coordinates for sharper rendering

3. **Data Management**
   - Circular buffer for incoming real-time data
   - Indexed data structures for time-based queries
   - Web Workers for data processing
   - Lazy loading of historical data

4. **Memory Management**
   - Limit data in memory (e.g., 24 hours rolling window)
   - Archive older data to disk/database
   - Use typed arrays for numeric data
   - Object pooling for UI elements

**Sources:**
- [Building High-Performance Real-Time Chart in React](https://dev.to/ibtekar/building-a-high-performance-real-time-chart-in-react-lessons-learned-ij7)
- [Chart.js Performance Documentation](https://www.chartjs.org/docs/latest/general/performance.html)
- [LightningChart Performance Optimization](https://lightningchart.com/js-charts/docs/more-guides/optimizing-performance/)
- [High Performance Chart Tricks](https://medium.com/@christopheviau/6-weird-tricks-for-insane-chart-performance-afd29f90f271)

---

### 3.3 Time Scaling

**Challenge:** Marine data spans microseconds to weeks

**DAW Approach:**
- Audio: milliseconds to hours
- Beat-based: measures, beats, 16th notes
- Timecode: hours:minutes:seconds:frames

**Marine Adaptation:**

**Time Scale Tiers:**
1. **Microsecond**: Equipment timing, sensor intervals
2. **Second**: Real-time data updates, alerts
3. **Minute**: Trend analysis, short-term events
4. **Hour**: Trip segments, fishing operations
5. **Day**: Multi-day trips, weather patterns
6. **Week**: Fleet operations, seasonal analysis

**Implementation:**

```javascript
// Time scale configuration
const TIME_SCALES = {
  MICROSECONDS: { unit: 'us', factor: 1e-6, minZoom: 1e-3, maxZoom: 1 },
  SECONDS: { unit: 's', factor: 1, minZoom: 1, maxZoom: 3600 },
  MINUTES: { unit: 'min', factor: 60, minZoom: 60, maxZoom: 86400 },
  HOURS: { unit: 'hr', factor: 3600, minZoom: 3600, maxZoom: 604800 },
  DAYS: { unit: 'day', factor: 86400, minZoom: 86400, maxZoom: 2592000 },
  WEEKS: { unit: 'wk', factor: 604800, minZoom: 604800, maxZoom: Infinity }
};

// Adaptive time scale based on viewport
function getOptimalTimeScale(viewportDuration) {
  if (viewportDuration < 60) return TIME_SCALES.SECONDS;
  if (viewportDuration < 3600) return TIME_SCALES.MINUTES;
  if (viewportDuration < 86400) return TIME_SCALES.HOURS;
  if (viewportDuration < 604800) return TIME_SCALES.DAYS;
  return TIME_SCALES.WEEKS;
}

// Time ruler formatting
function formatTimeRuler(timestamp, scale) {
  const date = new Date(timestamp);
  switch (scale.unit) {
    case 's': return date.toISOString().substr(11, 8); // HH:MM:SS
    case 'min': return date.toISOString().substr(11, 5); // HH:MM
    case 'hr': return date.toISOString().substr(11, 2) + 'h'; // HH
    case 'day': return date.toISOString().substr(0, 10); // YYYY-MM-DD
    case 'wk': return `'${date.getWeek()}-${date.getFullYear()}`; // WW-YYYY
  }
}
```

**Zoom Controls:**

```javascript
// Zoom levels mapping
const ZOOM_LEVELS = [
  { duration: 60, label: '1 minute', grid: 1 },
  { duration: 300, label: '5 minutes', grid: 60 },
  { duration: 900, label: '15 minutes', grid: 300 },
  { duration: 3600, label: '1 hour', grid: 600 },
  { duration: 7200, label: '2 hours', grid: 1800 },
  { duration: 21600, label: '6 hours', grid: 3600 },
  { duration: 43200, label: '12 hours', grid: 7200 },
  { duration: 86400, label: '1 day', grid: 14400 },
  { duration: 172800, label: '2 days', grid: 43200 },
  { duration: 604800, label: '1 week', grid: 86400 },
  { duration: 1209600, label: '2 weeks', grid: 604800 }
];

// Wheel zoom handler
function handleWheelZoom(event, currentViewport) {
  const zoomFactor = 1.1;
  const delta = event.deltaY > 0 ? zoomFactor : 1 / zoomFactor;

  const newDuration = currentViewport.duration * delta;
  const mouseTime = screenToTime(event.clientX);

  // Keep mouse position stable during zoom
  const newStart = mouseTime - (mouseTime - currentViewport.start) * delta;
  const newEnd = newStart + newDuration;

  return { start: newStart, end: newEnd, duration: newDuration };
}
```

---

### 3.4 Data Density Handling

**Challenge:** Displaying thousands of data points without visual clutter

**DAW Strategies:**
- Waveform summarization (peak/rms averaging)
- Level-of-detail rendering
- Selective rendering based on zoom
- Overview + detail views

**Marine Adaptation:**

**1. Data Summarization**

```javascript
// Summarize data for zoomed-out views
function summarizeData(dataPoints, viewportWidth) {
  const targetPixels = viewportWidth * 2; // 2 pixels per point target
  const blockSize = Math.ceil(dataPoints.length / targetPixels);

  if (blockSize <= 1) return dataPoints; // No summarization needed

  const summarized = [];

  for (let i = 0; i < dataPoints.length; i += blockSize) {
    const block = dataPoints.slice(i, i + blockSize);
    const summary = {
      min: Math.min(...block.map(p => p.value)),
      max: Math.max(...block.map(p => p.value)),
      avg: block.reduce((sum, p) => sum + p.value, 0) / block.length,
      first: block[0].timestamp,
      last: block[block.length - 1].timestamp,
      count: block.length
    };
    summarized.push(summary);
  }

  return summarized;
}

// Render summarized data as vertical bars (like DAW waveforms)
function renderSummarizedWaveform(ctx, summaryData, x, y, width, height) {
  const valueToY = (value) => y + height - ((value - minVal) / (maxVal - minVal)) * height;

  summaryData.forEach((summary, i) => {
    const barX = x + (i / summaryData.length) * width;
    const barWidth = Math.max(1, (width / summaryData.length));

    // Draw min-max range
    const minY = valueToY(summary.min);
    const maxY = valueToY(summary.max);

    ctx.fillStyle = '#4a9eff';
    ctx.fillRect(barX, minY, barWidth, maxY - minY);

    // Draw average line
    const avgY = valueToY(summary.avg);
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(barX, avgY - 0.5, barWidth, 1);
  });
}
```

**2. Level-of-Detail (LOD) Rendering**

```javascript
// LOD configuration
const LOD_LEVELS = [
  { pixelsPerPoint: 0.1, strategy: 'summary', summarySize: 1000 },
  { pixelsPerPoint: 1, strategy: 'decimate', targetPoints: 10000 },
  { pixelsPerPoint: 5, strategy: 'full', maxPoints: 50000 }
];

function getLODLevel(dataLength, viewportWidth) {
  const pixelsPerPoint = viewportWidth / dataLength;
  return LOD_LEVELS.find(level => pixelsPerPoint >= level.pixelsPerPoint)
    || LOD_LEVELS[LOD_LEVELS.length - 1];
}

function renderWithLOD(ctx, data, viewport, rect) {
  const lod = getLODLevel(data.length, rect.width);

  switch (lod.strategy) {
    case 'summary':
      const summarized = summarizeData(data, lod.summarySize);
      renderSummarizedWaveform(ctx, summarized, rect.x, rect.y, rect.width, rect.height);
      break;
    case 'decimate':
      const decimated = ramerDouglasPeucker(data, lod.targetPoints);
      renderLineChart(ctx, decimated, viewport, rect);
      break;
    case 'full':
      renderLineChart(ctx, data, viewport, rect);
      break;
  }
}

// Ramer-Douglas-Peucker line simplification
function ramerDouglasPeucker(points, epsilon) {
  if (points.length <= 2) return points;

  let dmax = 0;
  let index = 0;

  for (let i = 1; i < points.length - 1; i++) {
    const d = perpendicularDistance(points[i], points[0], points[points.length - 1]);
    if (d > dmax) {
      dmax = d;
      index = i;
    }
  }

  if (dmax > epsilon) {
    const left = ramerDouglasPeucker(points.slice(0, index + 1), epsilon);
    const right = ramerDouglasPeucker(points.slice(index), epsilon);
    return [...left.slice(0, -1), ...right];
  }

  return [points[0], points[points.length - 1]];
}
```

**3. Selective Rendering**

```javascript
// Render only visible tracks and time ranges
class TimelineRenderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.visibleTracks = new Set();
    this.renderQueue = [];
    this.isRendering = false;
  }

  // Queue render for track
  queueTrackRender(trackId, data, viewport) {
    if (!this.visibleTracks.has(trackId)) return;

    this.renderQueue.push({ trackId, data, viewport });
    if (!this.isRendering) {
      this.isRendering = true;
      requestAnimationFrame(() => this.processRenderQueue());
    }
  }

  processRenderQueue() {
    const startTime = performance.now();
    const maxFrameTime = 16; // 60 FPS budget

    while (this.renderQueue.length > 0) {
      const job = this.renderQueue.shift();

      this.renderTrack(job.trackId, job.data, job.viewport);

      const elapsed = performance.now() - startTime;
      if (elapsed > maxFrameTime) {
        break; // Continue next frame
      }
    }

    if (this.renderQueue.length > 0) {
      requestAnimationFrame(() => this.processRenderQueue());
    } else {
      this.isRendering = false;
    }
  }

  renderTrack(trackId, data, viewport) {
    const trackRect = this.getTrackRect(trackId);
    this.ctx.save();
    this.ctx.beginPath();
    this.ctx.rect(trackRect.x, trackRect.y, trackRect.width, trackRect.height);
    this.ctx.clip();

    renderWithLOD(this.ctx, data, viewport, trackRect);

    this.ctx.restore();
  }
}
```

---

## 4. UI Components Needed

### 4.1 Timeline Ruler

**Purpose:** Display time scale with zoomable markers

**Features:**
- Adaptive time units (seconds → days)
- Major and minor grid lines
- Current time indicator
- Zoom buttons
- Time range display
- Scrubber interaction

**Implementation:**

```javascript
class TimelineRuler {
  constructor(canvas, options) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.options = {
      height: 40,
      majorGridColor: '#333',
      minorGridColor: '#222',
      textColor: '#888',
      currentTimeColor: '#ff6600',
      ...options
    };
    this.viewport = { start: 0, end: 86400, duration: 86400 }; // 1 day
    this.currentTime = Date.now();
  }

  render() {
    const { width, height } = this.canvas;
    const ctx = this.ctx;

    // Clear
    ctx.clearRect(0, 0, width, height);

    // Background
    ctx.fillStyle = '#1a1a1a';
    ctx.fillRect(0, 0, width, height);

    // Calculate grid spacing
    const gridSpacing = this.calculateGridSpacing();
    const minorGridSpacing = gridSpacing / 5;

    // Draw minor grid
    ctx.strokeStyle = this.options.minorGridColor;
    ctx.lineWidth = 1;
    for (let t = Math.floor(this.viewport.start / minorGridSpacing) * minorGridSpacing;
         t <= this.viewport.end; t += minorGridSpacing) {
      const x = this.timeToX(t);
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }

    // Draw major grid and labels
    ctx.strokeStyle = this.options.majorGridColor;
    ctx.fillStyle = this.options.textColor;
    ctx.font = '11px system-ui, -apple-system, sans-serif';
    ctx.textAlign = 'center';

    for (let t = Math.floor(this.viewport.start / gridSpacing) * gridSpacing;
         t <= this.viewport.end; t += gridSpacing) {
      const x = this.timeToX(t);

      // Major grid line
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();

      // Time label
      const label = this.formatTime(t);
      ctx.fillText(label, x, height - 5);
    }

    // Draw current time indicator
    const currentX = this.timeToX(this.currentTime);
    ctx.strokeStyle = this.options.currentTimeColor;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(currentX, 0);
    ctx.lineTo(currentX, height + this.canvas.height); // Extend into tracks
    ctx.stroke();

    // Current time knob
    ctx.fillStyle = this.options.currentTimeColor;
    ctx.beginPath();
    ctx.moveTo(currentX - 6, height);
    ctx.lineTo(currentX + 6, height);
    ctx.lineTo(currentX, height - 8);
    ctx.closePath();
    ctx.fill();
  }

  calculateGridSpacing() {
    const targetPixelSpacing = 100; // Desired pixels between grid lines
    const pixelsPerSecond = this.canvas.width / this.viewport.duration;

    const idealSpacing = targetPixelSpacing / pixelsPerSecond;

    // Round to nice intervals (powers of 10, 2, 5)
    const magnitude = Math.pow(10, Math.floor(Math.log10(idealSpacing)));
    const normalized = idealSpacing / magnitude;

    let niceSpacing;
    if (normalized < 2) niceSpacing = 1 * magnitude;
    else if (normalized < 5) niceSpacing = 2 * magnitude;
    else if (normalized < 10) niceSpacing = 5 * magnitude;
    else niceSpacing = 10 * magnitude;

    return niceSpacing;
  }

  timeToX(timestamp) {
    return ((timestamp - this.viewport.start) / this.viewport.duration) * this.canvas.width;
  }

  xToTime(x) {
    return this.viewport.start + (x / this.canvas.width) * this.viewport.duration;
  }

  formatTime(timestamp) {
    const date = new Date(timestamp);
    const duration = this.viewport.duration;

    if (duration < 60) {
      // Seconds
      return date.toISOString().substr(11, 8); // HH:MM:SS
    } else if (duration < 3600) {
      // Minutes
      return date.toISOString().substr(11, 5); // HH:MM
    } else if (duration < 86400) {
      // Hours
      return `${date.getHours()}:00`;
    } else if (duration < 604800) {
      // Days
      return date.toISOString().substr(0, 10); // YYYY-MM-DD
    } else {
      // Weeks
      return `W${this.getWeekNumber(date)}`;
    }
  }

  getWeekNumber(date) {
    const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
    const dayNum = d.getUTCDay() || 7;
    d.setUTCDate(d.getUTCDate() + 4 - dayNum);
    const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    return Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
  }
}
```

---

### 4.2 Track Headers

**Purpose:** Display track information and controls

**Features:**
- Track name and icon
- Mute/solo/record buttons
- Color indicator
- Expand/collapse button
- Height resize handle
- Track type badge (NMEA, Alert, Event)

**Implementation:**

```javascript
class TrackHeader {
  constructor(trackId, options) {
    this.trackId = trackId;
    this.options = {
      width: 200,
      minHeight: 30,
      maxHeight: 200,
      color: '#4a9eff',
      ...options
    };
    this.height = 60;
    this.isMuted = false;
    this.isSolo = false;
    this.isArmed = false;
    this.isExpanded = true;
  }

  render(container) {
    const header = document.createElement('div');
    header.className = 'track-header';
    header.style.cssText = `
      width: ${this.options.width}px;
      height: ${this.height}px;
      background: #2a2a2a;
      border-right: 1px solid #444;
      border-bottom: 1px solid #333;
      display: flex;
      flex-direction: column;
      position: relative;
    `;

    // Track info (top section)
    const info = document.createElement('div');
    info.className = 'track-info';
    info.style.cssText = `
      flex: 1;
      display: flex;
      align-items: center;
      padding: 8px;
      gap: 8px;
      cursor: pointer;
    `;

    // Color indicator
    const color = document.createElement('div');
    color.className = 'track-color';
    color.style.cssText = `
      width: 12px;
      height: 12px;
      background: ${this.options.color};
      border-radius: 2px;
    `;
    info.appendChild(color);

    // Track name
    const name = document.createElement('span');
    name.className = 'track-name';
    name.textContent = this.options.name;
    name.style.cssText = `
      flex: 1;
      font-size: 12px;
      font-weight: 500;
      color: #ccc;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    `;
    info.appendChild(name);

    // Track type badge
    const badge = document.createElement('span');
    badge.className = 'track-badge';
    badge.textContent = this.options.type;
    badge.style.cssText = `
      font-size: 9px;
      padding: 2px 6px;
      background: #444;
      border-radius: 3px;
      color: #999;
      text-transform: uppercase;
    `;
    info.appendChild(badge);

    header.appendChild(info);

    // Controls (bottom section)
    const controls = document.createElement('div');
    controls.className = 'track-controls';
    controls.style.cssText = `
      display: flex;
      gap: 4px;
      padding: 4px 8px;
      border-top: 1px solid #333;
    `;

    // Mute button
    const muteBtn = this.createControlButton('M', this.isMuted, '#666', '#ff6600');
    muteBtn.onclick = () => this.toggleMute();
    controls.appendChild(muteBtn);

    // Solo button
    const soloBtn = this.createControlButton('S', this.isSolo, '#666', '#ffcc00');
    soloBtn.onclick = () => this.toggleSolo();
    controls.appendChild(soloBtn);

    // Arm button
    const armBtn = this.createControlButton('R', this.isArmed, '#666', '#ff3333');
    armBtn.onclick = () => this.toggleArm();
    controls.appendChild(armBtn);

    header.appendChild(controls);

    // Resize handle
    const resizeHandle = document.createElement('div');
    resizeHandle.className = 'resize-handle';
    resizeHandle.style.cssText = `
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      height: 4px;
      cursor: ns-resize;
      background: transparent;
    `;

    let isResizing = false;
    let startY = 0;
    let startHeight = 0;

    resizeHandle.addEventListener('mousedown', (e) => {
      isResizing = true;
      startY = e.clientY;
      startHeight = this.height;
      e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
      if (!isResizing) return;
      const deltaY = e.clientY - startY;
      this.height = Math.max(
        this.options.minHeight,
        Math.min(this.options.maxHeight, startHeight + deltaY)
      );
      header.style.height = `${this.height}px`;
      this.onResize?.(this.height);
    });

    document.addEventListener('mouseup', () => {
      isResizing = false;
    });

    header.appendChild(resizeHandle);

    return header;
  }

  createControlButton(label, isActive, inactiveColor, activeColor) {
    const btn = document.createElement('button');
    btn.textContent = label;
    btn.style.cssText = `
      width: 20px;
      height: 20px;
      border: 1px solid ${isActive ? activeColor : '#555'};
      background: ${isActive ? activeColor : inactiveColor};
      color: ${isActive ? '#fff' : '#ccc'};
      border-radius: 3px;
      font-size: 10px;
      font-weight: bold;
      cursor: pointer;
      transition: all 0.1s;
    `;
    return btn;
  }

  toggleMute() {
    this.isMuted = !this.isMuted;
    this.onMuteToggle?.(this.isMuted);
  }

  toggleSolo() {
    this.isSolo = !this.isSolo;
    this.onSoloToggle?.(this.isSolo);
  }

  toggleArm() {
    this.isArmed = !this.isArmed;
    this.onArmToggle?.(this.isArmed);
  }
}
```

---

### 4.3 Track Content Area (Canvas)

**Purpose:** Display data visualization for each track

**Features:**
- Canvas-based rendering
- Waveform/line chart visualization
- Event markers
- Clip visualization
- Selection highlights
- Hover tooltips

**Implementation:**

```javascript
class TrackContent {
  constructor(trackId, canvas, options) {
    this.trackId = trackId;
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.options = {
      height: 60,
      backgroundColor: '#1e1e1e',
      gridColor: '#2a2a2a',
      lineColor: '#4a9eff',
      lineWidth: 1.5,
      fillColor: 'rgba(74, 158, 255, 0.1)',
      ...options
    };
    this.data = [];
    this.viewport = { start: 0, end: 86400 };
    this.selection = null;
    this.hoverX = null;
  }

  render() {
    const { width, height } = this.canvas;
    const ctx = this.ctx;

    // Clear
    ctx.clearRect(0, 0, width, height);

    // Background
    ctx.fillStyle = this.options.backgroundColor;
    ctx.fillRect(0, 0, width, height);

    // Grid lines (vertical time lines)
    ctx.strokeStyle = this.options.gridColor;
    ctx.lineWidth = 1;
    const gridSpacing = this.calculateGridSpacing();

    for (let t = Math.floor(this.viewport.start / gridSpacing) * gridSpacing;
         t <= this.viewport.end; t += gridSpacing) {
      const x = this.timeToX(t);
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }

    // Render data
    if (this.data.length > 0) {
      this.renderData();
    }

    // Render clips
    this.renderClips();

    // Render event markers
    this.renderEventMarkers();

    // Selection highlight
    if (this.selection) {
      this.renderSelection();
    }

    // Hover indicator
    if (this.hoverX !== null) {
      this.renderHover();
    }
  }

  renderData() {
    const ctx = this.ctx;
    const { width, height } = this.canvas;

    // Filter visible data points
    const visibleData = this.data.filter(
      d => d.timestamp >= this.viewport.start && d.timestamp <= this.viewport.end
    );

    if (visibleData.length === 0) return;

    // Calculate value range
    const values = visibleData.map(d => d.value);
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const valueRange = maxValue - minValue || 1;

    const padding = 4;
    const chartHeight = height - padding * 2;

    const valueToY = (value) => {
      return padding + chartHeight - ((value - minValue) / valueRange) * chartHeight;
    };

    // Draw fill
    ctx.fillStyle = this.options.fillColor;
    ctx.beginPath();
    ctx.moveTo(0, height);

    visibleData.forEach((point, i) => {
      const x = this.timeToX(point.timestamp);
      const y = valueToY(point.value);
      if (i === 0) ctx.lineTo(x, y);
      else ctx.lineTo(x, y);
    });

    ctx.lineTo(width, height);
    ctx.closePath();
    ctx.fill();

    // Draw line
    ctx.strokeStyle = this.options.lineColor;
    ctx.lineWidth = this.options.lineWidth;
    ctx.beginPath();

    visibleData.forEach((point, i) => {
      const x = this.timeToX(point.timestamp);
      const y = valueToY(point.value);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });

    ctx.stroke();
  }

  renderClips() {
    const ctx = this.ctx;
    const { height } = this.canvas;

    this.clips?.forEach(clip => {
      const x = this.timeToX(clip.startTime);
      const w = this.timeToX(clip.endTime) - x;

      // Clip background
      ctx.fillStyle = clip.color || '#4a9eff';
      ctx.globalAlpha = 0.2;
      ctx.fillRect(x, 0, w, height);
      ctx.globalAlpha = 1.0;

      // Clip border
      ctx.strokeStyle = clip.color || '#4a9eff';
      ctx.lineWidth = 2;
      ctx.strokeRect(x, 0, w, height);

      // Clip label
      ctx.fillStyle = '#fff';
      ctx.font = '11px system-ui, sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(clip.label, x + 6, 14);
    });
  }

  renderEventMarkers() {
    const ctx = this.ctx;
    const { height } = this.canvas;

    this.events?.forEach(event => {
      const x = this.timeToX(event.timestamp);

      // Marker triangle
      ctx.fillStyle = event.color || '#ffcc00';
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x - 6, 12);
      ctx.lineTo(x + 6, 12);
      ctx.closePath();
      ctx.fill();

      // Event label
      if (event.label) {
        ctx.fillStyle = '#ccc';
        ctx.font = '10px system-ui, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(event.label, x, 24);
      }
    });
  }

  renderSelection() {
    const ctx = this.ctx;
    const { height } = this.canvas;

    const startX = this.timeToX(this.selection.start);
    const endX = this.timeToX(this.selection.end);

    ctx.fillStyle = 'rgba(74, 158, 255, 0.1)';
    ctx.fillRect(startX, 0, endX - startX, height);

    ctx.strokeStyle = '#4a9eff';
    ctx.lineWidth = 2;
    ctx.strokeRect(startX, 0, endX - startX, height);
  }

  renderHover() {
    const ctx = this.ctx;
    const { height } = this.canvas;

    ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(this.hoverX, 0);
    ctx.lineTo(this.hoverX, height);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  timeToX(timestamp) {
    return ((timestamp - this.viewport.start) /
            (this.viewport.end - this.viewport.start)) * this.canvas.width;
  }

  xToTime(x) {
    return this.viewport.start +
           (x / this.canvas.width) * (this.viewport.end - this.viewport.start);
  }

  calculateGridSpacing() {
    const duration = this.viewport.end - this.viewport.start;
    const targetSpacing = this.canvas.width / 10;

    const idealSeconds = duration / (this.canvas.width / targetSpacing);

    // Round to nice intervals
    const magnitude = Math.pow(10, Math.floor(Math.log10(idealSeconds)));
    const normalized = idealSeconds / magnitude;

    let niceSpacing;
    if (normalized < 2) niceSpacing = 1 * magnitude;
    else if (normalized < 5) niceSpacing = 2 * magnitude;
    else if (normalized < 10) niceSpacing = 5 * magnitude;
    else niceSpacing = 10 * magnitude;

    return niceSpacing;
  }
}
```

---

### 4.4 Zoom/Pan Controls

**Purpose:** Interactive navigation of timeline

**Features:**
- Mouse wheel zoom (horizontal and vertical)
- Click and drag pan
- Pinch to zoom (touch)
- Zoom presets (1 min, 5 min, 1 hour, 1 day, 1 week)
- Fit to selection
- Go to current time

**Implementation:**

```javascript
class TimelineControls {
  constructor(ruler, tracksContainer) {
    this.ruler = ruler;
    this.tracksContainer = tracksContainer;
    this.viewport = { start: 0, end: 86400 };
    this.isPanning = false;
    this.isSelecting = false;
    this.selection = null;

    this.setupEventHandlers();
  }

  setupEventHandlers() {
    // Wheel zoom
    this.tracksContainer.addEventListener('wheel', (e) => {
      e.preventDefault();
      this.handleWheelZoom(e);
    }, { passive: false });

    // Pan
    this.tracksContainer.addEventListener('mousedown', (e) => {
      if (e.button === 0 && !e.shiftKey) { // Left click without shift
        this.isPanning = true;
        this.panStart = { x: e.clientX, y: e.clientY };
        this.viewportStart = { ...this.viewport };
      } else if (e.button === 0 && e.shiftKey) { // Left click with shift
        this.isSelecting = true;
        this.selectionStart = { x: e.clientX, y: e.clientY };
      }
    });

    document.addEventListener('mousemove', (e) => {
      if (this.isPanning) {
        this.handlePan(e);
      } else if (this.isSelecting) {
        this.handleSelection(e);
      }
    });

    document.addEventListener('mouseup', (e) => {
      if (this.isPanning) {
        this.isPanning = false;
      } else if (this.isSelecting) {
        this.isSelecting = false;
        this.finalizeSelection();
      }
    });

    // Touch pinch zoom
    let lastTouchDistance = null;
    this.tracksContainer.addEventListener('touchmove', (e) => {
      if (e.touches.length === 2) {
        e.preventDefault();
        const touch1 = e.touches[0];
        const touch2 = e.touches[1];
        const distance = Math.hypot(
          touch2.clientX - touch1.clientX,
          touch2.clientY - touch1.clientY
        );

        if (lastTouchDistance !== null) {
          const scale = lastTouchDistance / distance;
          const centerX = (touch1.clientX + touch2.clientX) / 2;
          const centerTime = this.xToTime(centerX);

          this.zoomAround(centerTime, scale);
        }

        lastTouchDistance = distance;
      }
    });

    this.tracksContainer.addEventListener('touchend', () => {
      lastTouchDistance = null;
    });
  }

  handleWheelZoom(e) {
    const zoomFactor = e.deltaY > 0 ? 1.1 : 1 / 1.1;
    const mouseX = e.clientX - this.tracksContainer.getBoundingClientRect().left;
    const mouseTime = this.xToTime(mouseX);

    this.zoomAround(mouseTime, zoomFactor);
  }

  zoomAround(centerTime, scale) {
    const duration = this.viewport.end - this.viewport.start;
    const newDuration = duration * scale;

    // Clamp minimum zoom (1 second) and maximum zoom (1 year)
    const clampedDuration = Math.max(1, Math.min(31536000, newDuration));

    // Keep centerTime stable during zoom
    const leftRatio = (centerTime - this.viewport.start) / duration;
    const newStart = centerTime - clampedDuration * leftRatio;
    const newEnd = newStart + clampedDuration;

    this.setViewport(newStart, newEnd);
  }

  handlePan(e) {
    const deltaX = e.clientX - this.panStart.x;
    const pixelsPerSecond = this.tracksContainer.clientWidth /
                            (this.viewport.end - this.viewport.start);

    const deltaTime = -deltaX / pixelsPerSecond;

    this.viewport.start = this.viewportStart.start + deltaTime;
    this.viewport.end = this.viewportStart.end + deltaTime;

    this.updateViewport();
  }

  handleSelection(e) {
    const startX = this.selectionStart.x;
    const currentX = e.clientX;

    this.selection = {
      start: this.xToTime(Math.min(startX, currentX)),
      end: this.xToTime(Math.max(startX, currentX))
    };

    this.renderSelection();
  }

  finalizeSelection() {
    if (this.selection) {
      this.onSelectionComplete?.(this.selection);
    }
    this.selection = null;
    this.renderSelection();
  }

  setZoomPreset(duration) {
    const centerTime = (this.viewport.start + this.viewport.end) / 2;
    const newStart = centerTime - duration / 2;
    const newEnd = centerTime + duration / 2;
    this.setViewport(newStart, newEnd);
  }

  fitToSelection(selection) {
    const padding = (selection.end - selection.start) * 0.1;
    this.setViewport(
      selection.start - padding,
      selection.end + padding
    );
  }

  goToCurrentTime() {
    const now = Date.now();
    const duration = this.viewport.end - this.viewport.start;
    this.setViewport(now - duration / 2, now + duration / 2);
  }

  setViewport(start, end) {
    this.viewport = { start, end };
    this.updateViewport();
  }

  updateViewport() {
    this.ruler.viewport = this.viewport;
    this.ruler.render();

    // Update all track viewports
    this.tracks.forEach(track => {
      track.viewport = this.viewport;
      track.render();
    });

    this.onViewportChange?.(this.viewport);
  }

  xToTime(x) {
    return this.viewport.start +
           (x / this.tracksContainer.clientWidth) *
           (this.viewport.end - this.viewport.start);
  }

  renderSelection() {
    // Trigger re-render of tracks with selection
    this.tracks.forEach(track => {
      track.selection = this.selection;
      track.render();
    });
  }
}
```

---

### 4.5 Component Integration

**Full Timeline Assembly:**

```javascript
class MarineTimeline {
  constructor(container, options) {
    this.container = container;
    this.options = {
      headerWidth: 200,
      rulerHeight: 40,
      trackHeight: 60,
      minTracks: 5,
      ...options
    };

    this.tracks = new Map();
    this.viewport = { start: Date.now() - 3600000, end: Date.now() };

    this.render();
  }

  render() {
    // Main container
    this.container.className = 'marine-timeline';
    this.container.style.cssText = `
      display: flex;
      flex-direction: column;
      background: #1a1a1a;
      font-family: system-ui, -apple-system, sans-serif;
      overflow: hidden;
      height: 100vh;
    `;

    // Top toolbar
    const toolbar = this.createToolbar();
    this.container.appendChild(toolbar);

    // Timeline area (horizontal flex)
    const timelineArea = document.createElement('div');
    timelineArea.style.cssText = `
      flex: 1;
      display: flex;
      overflow: hidden;
    `;

    // Track headers (left panel)
    this.trackHeadersContainer = document.createElement('div');
    this.trackHeadersContainer.className = 'track-headers';
    this.trackHeadersContainer.style.cssText = `
      width: ${this.options.headerWidth}px;
      background: #252525;
      border-right: 1px solid #444;
      overflow-y: auto;
      overflow-x: hidden;
    `;
    timelineArea.appendChild(this.trackHeadersContainer);

    // Tracks content (right panel)
    const tracksContent = document.createElement('div');
    tracksContent.style.cssText = `
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    `;

    // Timeline ruler
    this.rulerCanvas = document.createElement('canvas');
    this.rulerCanvas.className = 'timeline-ruler';
    this.rulerCanvas.style.cssText = `
      width: 100%;
      height: ${this.options.rulerHeight}px;
      background: #1a1a1a;
      border-bottom: 1px solid #333;
    `;
    this.rulerCanvas.width = tracksContent.clientWidth;
    this.rulerCanvas.height = this.options.rulerHeight;
    tracksContent.appendChild(this.rulerCanvas);

    this.ruler = new TimelineRuler(this.rulerCanvas, { viewport: this.viewport });
    this.ruler.render();

    // Tracks container
    this.tracksContainer = document.createElement('div');
    this.tracksContainer.className = 'tracks-container';
    this.tracksContainer.style.cssText = `
      flex: 1;
      overflow-y: auto;
      overflow-x: hidden;
      position: relative;
    `;
    tracksContent.appendChild(this.tracksContainer);

    timelineArea.appendChild(tracksContent);
    this.container.appendChild(timelineArea);

    // Initialize controls
    this.controls = new TimelineControls(this.ruler, this.tracksContainer);
    this.controls.onViewportChange = (viewport) => {
      this.viewport = viewport;
      this.onViewportChange?.(viewport);
    };
    this.controls.onSelectionComplete = (selection) => {
      this.onSelectionComplete?.(selection);
    };
  }

  createToolbar() {
    const toolbar = document.createElement('div');
    toolbar.className = 'timeline-toolbar';
    toolbar.style.cssText = `
      display: flex;
      gap: 8px;
      padding: 8px 12px;
      background: #252525;
      border-bottom: 1px solid #444;
      align-items: center;
    `;

    // Zoom presets
    const zoomPresets = [
      { label: '1m', duration: 60 },
      { label: '5m', duration: 300 },
      { label: '15m', duration: 900 },
      { label: '1h', duration: 3600 },
      { label: '6h', duration: 21600 },
      { label: '1d', duration: 86400 },
      { label: '1w', duration: 604800 }
    ];

    const zoomGroup = document.createElement('div');
    zoomGroup.className = 'zoom-group';
    zoomGroup.style.cssText = `
      display: flex;
      gap: 4px;
      align-items: center;
    `;

    const zoomLabel = document.createElement('span');
    zoomLabel.textContent = 'Zoom:';
    zoomLabel.style.cssText = `
      font-size: 11px;
      color: #888;
      margin-right: 4px;
    `;
    zoomGroup.appendChild(zoomLabel);

    zoomPresets.forEach(preset => {
      const btn = document.createElement('button');
      btn.textContent = preset.label;
      btn.style.cssText = `
        padding: 4px 8px;
        background: #333;
        border: 1px solid #555;
        color: #ccc;
        border-radius: 3px;
        font-size: 11px;
        cursor: pointer;
        transition: background 0.1s;
      `;
      btn.onmouseenter = () => btn.style.background = '#444';
      btn.onmouseleave = () => btn.style.background = '#333';
      btn.onclick = () => this.controls.setZoomPreset(preset.duration);
      zoomGroup.appendChild(btn);
    });

    toolbar.appendChild(zoomGroup);

    // Separator
    const sep = document.createElement('div');
    sep.style.cssText = 'width: 1px; height: 24px; background: #444; margin: 0 8px;';
    toolbar.appendChild(sep);

    // Current time button
    const nowBtn = document.createElement('button');
    nowBtn.textContent = 'Now';
    nowBtn.style.cssText = `
      padding: 6px 12px;
      background: #4a9eff;
      border: none;
      color: white;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 500;
      cursor: pointer;
      transition: opacity 0.1s;
    `;
    nowBtn.onmouseenter = () => nowBtn.style.opacity = '0.9';
    nowBtn.onmouseleave = () => nowBtn.style.opacity = '1';
    nowBtn.onclick = () => this.controls.goToCurrentTime();
    toolbar.appendChild(nowBtn);

    return toolbar;
  }

  addTrack(trackId, options) {
    // Track header
    const header = new TrackHeader(trackId, options);
    const headerEl = header.render(this.trackHeadersContainer);
    this.trackHeadersContainer.appendChild(headerEl);

    // Track content canvas
    const canvas = document.createElement('canvas');
    canvas.className = `track-${trackId}`;
    canvas.style.cssText = `
      width: 100%;
      height: ${options.height || this.options.trackHeight}px;
      border-bottom: 1px solid #333';
    `;
    canvas.width = this.tracksContainer.clientWidth;
    canvas.height = options.height || this.options.trackHeight;
    this.tracksContainer.appendChild(canvas);

    // Track content
    const track = new TrackContent(trackId, canvas, options);
    track.viewport = this.viewport;

    this.tracks.set(trackId, { header, track, canvas });

    return track;
  }

  removeTrack(trackId) {
    const trackData = this.tracks.get(trackId);
    if (!trackData) return;

    trackData.header.element.remove();
    trackData.canvas.remove();
    this.tracks.delete(trackId);
  }

  updateTrackData(trackId, data) {
    const trackData = this.tracks.get(trackId);
    if (!trackData) return;

    trackData.track.data = data;
    trackData.track.render();
  }

  setViewport(start, end) {
    this.controls.setViewport(start, end);
  }
}
```

---

## 5. Integration with AELMA System

### 5.1 Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      AELMA Timeline Integration                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │   Bridge     │───▶│   Twin       │───▶│   Timeline   │          │
│  │  (NMEA)      │    │   (State)    │    │   (UI)       │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│         │                  │                     │                   │
│         │                  │                     └─────┐             │
│         │                  │                           │             │
│         │                  │                      ┌────▼────┐         │
│         │                  │                      │ Track 1  │         │
│         │                  │                      │ Position │         │
│         │                  │                      └─────────┘         │
│         │                  │                      ┌────┬────┐         │
│         │                  │                      │Track 2│          │
│         │                  │                      │ Depth │          │
│         │                  │                      └────┬───┘          │
│         │                  │                           │             │
│         │                  │                      ┌────▼────┐         │
│         │                  │                      │Track 3  │         │
│         │                  │                      │ Alerts  │         │
│         │                  │                      └─────────┘         │
│         │                  │                                        │
│  ┌──────▼─────────┐                                              │
│  │  Simulator      │                                              │
│  │  (Historical)   │                                              │
│  └─────────────────┘                                              │
│                                                                        │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 WebSocket Integration

```javascript
class TimelineDataSource {
  constructor(timeline, twinWsUrl) {
    this.timeline = timeline;
    this.wsUrl = twinWsUrl;
    this.ws = null;
    this.dataBuffers = new Map();
    this.maxBufferPoints = 10000; // Keep last N points per track
  }

  connect() {
    this.ws = new WebSocket(this.wsUrl);

    this.ws.onopen = () => {
      console.log('Timeline connected to TwinCore');
      // Subscribe to track data
      this.sendSubscription();
    };

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      this.handleMessage(message);
    };

    this.ws.onerror = (error) => {
      console.error('Timeline WebSocket error:', error);
    };

    this.ws.onclose = () => {
      console.log('Timeline disconnected from TwinCore');
      // Auto-reconnect
      setTimeout(() => this.connect(), 5000);
    };
  }

  sendSubscription() {
    this.ws.send(JSON.stringify({
      type: 'subscribe',
      tracks: ['position', 'depth', 'speed', 'heading', 'alerts']
    }));
  }

  handleMessage(message) {
    switch (message.type) {
      case 'vessel_state':
        this.handleVesselState(message.data);
        break;
      case 'alert':
        this.handleAlert(message.data);
        break;
      case 'historical_data':
        this.handleHistoricalData(message.data);
        break;
    }
  }

  handleVesselState(state) {
    const timestamp = state.timestamp_ns / 1e6; // Convert ns to ms

    // Update track buffers
    this.updateTrackData('position', timestamp, {
      latitude: state.position.lat,
      longitude: state.position.lon
    });

    this.updateTrackData('depth', timestamp, {
      value: state.depth_m
    });

    this.updateTrackData('speed', timestamp, {
      value: state.speed_knots
    });

    this.updateTrackData('heading', timestamp, {
      value: state.heading_deg
    });
  }

  handleAlert(alert) {
    const timestamp = alert.timestamp_ns / 1e6;

    // Add event marker to alerts track
    const alertsTrack = this.timeline.tracks.get('alerts');
    if (alertsTrack) {
      if (!alertsTrack.track.events) {
        alertsTrack.track.events = [];
      }
      alertsTrack.track.events.push({
        timestamp,
        type: alert.alert_type,
        label: alert.message,
        color: this.getAlertColor(alert.severity)
      });
      alertsTrack.track.render();
    }
  }

  handleHistoricalData(data) {
    // Bulk load historical data
    data.track_data.forEach(trackData => {
      const track = this.timeline.tracks.get(trackData.track_id);
      if (!track) return;

      // Convert and buffer data
      const points = trackData.data.map(point => ({
        timestamp: point.timestamp_ns / 1e6,
        value: point.value
      }));

      this.updateTrackData(trackData.track_id, null, points, true);
    });
  }

  updateTrackData(trackId, timestamp, value, replace = false) {
    const track = this.timeline.tracks.get(trackId);
    if (!track) return;

    let buffer = this.dataBuffers.get(trackId);

    if (replace) {
      // Replace entire buffer
      buffer = value;
      this.dataBuffers.set(trackId, buffer);
    } else {
      // Append new point
      if (!buffer) {
        buffer = [];
        this.dataBuffers.set(trackId, buffer);
      }

      buffer.push({ timestamp, ...value });

      // Trim buffer if needed
      if (buffer.length > this.maxBufferPoints) {
        buffer.splice(0, buffer.length - this.maxBufferPoints);
      }
    }

    // Update track visualization
    track.track.data = buffer;
    track.track.render();
  }

  getAlertColor(severity) {
    switch (severity) {
      case 'critical': return '#ff3333';
      case 'warning': return '#ffcc00';
      case 'info': return '#4a9eff';
      default: return '#888888';
    }
  }

  requestHistoricalData(trackId, startTime, endTime) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'request_historical',
        track_id: trackId,
        start_time_ns: startTime * 1e6,
        end_time_ns: endTime * 1e6
      }));
    }
  }
}
```

### 5.3 Example Usage

```javascript
// Initialize timeline
const timelineContainer = document.getElementById('timeline-container');
const timeline = new MarineTimeline(timelineContainer, {
  headerWidth: 220,
  rulerHeight: 40,
  trackHeight: 80
});

// Add tracks
timeline.addTrack('position', {
  name: 'Position',
  type: 'NMEA',
  color: '#4a9eff',
  height: 100
});

timeline.addTrack('depth', {
  name: 'Depth',
  type: 'Sounder',
  color: '#ff6600',
  height: 80
});

timeline.addTrack('speed', {
  name: 'Speed',
  type: 'Log',
  color: '#00cc66',
  height: 60
});

timeline.addTrack('heading', {
  name: 'Heading',
  type: 'Compass',
  color: '#ffcc00',
  height: 60
});

timeline.addTrack('alerts', {
  name: 'Alerts',
  type: 'Event',
  color: '#ff3333',
  height: 100
});

// Connect to TwinCore
const dataSource = new TimelineDataSource(timeline, 'ws://localhost:8090');
dataSource.connect();

// Set initial viewport (last 6 hours)
const now = Date.now();
timeline.setViewport(now - 6 * 3600000, now);

// Handle selection
timeline.onSelectionComplete = (selection) => {
  console.log('Selected time range:', selection);
  // Could trigger analysis, export, etc.
};

// Handle viewport changes
timeline.onViewportChange = (viewport) => {
  console.log('Viewport changed:', viewport);
  // Could request historical data for new viewport
};
```

---

## 6. Best Practices & Recommendations

### 6.1 Performance Optimization

1. **Canvas Rendering**
   - Use offscreen canvas for static content
   - Implement LOD (Level of Detail) rendering
   - Batch draw operations
   - Use `requestAnimationFrame` for smooth updates

2. **Data Management**
   - Implement circular buffers for real-time data
   - Use Web Workers for data processing
   - Cache historical data on client
   - Implement progressive loading

3. **Memory Management**
   - Limit data in memory (e.g., 24-hour rolling window)
   - Use typed arrays for numeric data
   - Implement object pooling
   - Clear old data periodically

### 6.2 User Experience

1. **Responsive Design**
   - Support mouse and touch interactions
   - Smooth animations and transitions
   - Clear visual feedback
   - Keyboard shortcuts

2. **Visual Hierarchy**
   - Most important tracks at top
   - Color coding for track types
   - Clear time scale and grid
   - Obvious selection and hover states

3. **Accessibility**
   - Keyboard navigation
   - Screen reader support for track headers
   - High contrast mode
   - Font size scaling

### 6.3 AELMA-Specific Considerations

1. **Marine Context**
   - Use nautical time formats when appropriate
   - Support NMEA sentence display
   - Show tide and weather overlays
   - Integrate with bathymetry display

2. **Operational Needs**
   - Quick access to current time
   - Easy zoom to operational ranges (shift, haul, day)
   - Alert visibility at all zoom levels
   - Export functionality for compliance

3. **Integration**
   - WebSocket for real-time data
   - REST API for historical queries
   - Event system for alerts
   - State persistence for saved views

---

## 7. Existing Libraries and Resources

### 7.1 Timeline Libraries

**Web Audio/DAW-Inspired:**

1. **waveform-playlist** ([GitHub](https://github.com/naomiaro/waveform-playlist))
   - Multi-track audio editor with React
   - Canvas-based waveform visualization
   - Drag-and-drop clip editing
   - Zoom controls
   - 20+ audio effects via Tone.js

2. **Tone.js** ([Website](https://tonejs.github.io/))
   - Web Audio framework
   - Timeline and transport features
   - Signal analysis and visualization

3. **WaveSurfer.js** ([Website](https://wavesurfer-js.org/))
   - Audio waveform visualization
   - Multiple render modes
   - Plugins for markers, regions
   - Real-time updates

**General Timeline:**

4. **vis-timeline** ([Website](https://visjs.github.io/vis-timeline/))
   - General-purpose timeline
   - Event grouping and customization
   - Touch support
   - Flexible styling

5. **TimelineJS** ([Website](https://timeline.knightlab.com/))
   - Story-focused timelines
   - Media support
   - Easy embedding

### 7.2 Chart Libraries (Adaptable)

1. **SciChart.js** ([Website](https://www.scichart.com/javascript-chart-features/))
   - High-performance real-time charts
   - Maritime chart support
   - Zoom and pan capabilities

2. **LightningChart** ([Website](https://lightningchart.com/js-charts/))
   - Real-time data visualization
   - 3D capabilities
   - Performance optimization guides

3. **Plotly.js** ([Website](https://plotly.com/javascript/))
   - Scientific charting
   - Time series support
   - Interactive zoom/pan

### 7.3 Zoom/Pan Libraries

1. **react-zoom-pan-pinch** ([GitHub](https://github.com/BetterTyped/react-zoom-pan-pinch))
   - React zoom and pan component
   - Touch support
   - Easy integration

2. **d3-zoom** ([Documentation](https://github.com/d3/d3-zoom))
   - D3 zoom behavior
   - Flexible event handling
   - Canvas and DOM support

---

## 8. Conclusion

DAW timeline interface patterns provide an excellent foundation for marine vessel telemetry visualization in AELMA. The core concepts of tracks, clips, automation lanes, and zoomable time rulers map directly to marine data streams, events, parameter changes, and operational time scales.

**Key Recommendations:**

1. **Use Canvas-based rendering** for track content visualization (performance for real-time data)
2. **Use DOM elements** for track headers, controls, and UI overlays (accessibility and ease)
3. **Implement LOD rendering** for handling data density at different zoom levels
4. **Adaptive time scaling** from seconds to weeks based on viewport
5. **WebSocket integration** for real-time data from TwinCore
6. **Hybrid approach** combining DAW patterns with marine-specific needs

**Next Steps for AELMA:**

1. Create prototype timeline viewer with 3-5 core tracks
2. Implement Canvas-based rendering with LOD
3. Add WebSocket integration with TwinCore
4. Test with real vessel data (F/V EILEEN simulator)
5. Gather feedback from crew for usability
6. Add marine-specific features (NMEA display, tides, weather overlays)

**Sources Summary:**

- [Ableton Live Arrangement View Manual](https://www.ableton.com/en/manual/arrangement-view/)
- [Ableton Live Redesign Concept](https://nndmlsvc.medium.com/ableton-live-redesign-26efebe73bfc)
- [Logic Pro Interface Guide](https://support.apple.com/en-in/guide/logicpro-ipad/lpip33be754d/ipados)
- [REAPER Official Site](https://www.reaper.fm/)
- [Bitwig Studio User Guide](https://www.bitwig.com/media/bitwig_userguide/pdf/Bitwig_Studio_User_Guide_English_G2qasDB.pdf)
- [waveform-playlist GitHub](https://github.com/naomiaro/waveform-playlist)
- [MDN Web Audio API Visualizations](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Visualizations_with_Web_Audio_API)
- [Canvas vs DOM Performance](https://stackoverflow.com/questions/24019174/real-time-data-plotting-performance-html5-canvas-vs-dom-appending)
- [SciChart Real-Time Performance Demo](https://www.scichart.com/demo/javascript/chart-realtime-performance-demo)
- [Building High-Performance Real-Time Chart in React](https://dev.to/ibtekar/building-a-high-performance-real-time-chart-in-react-lessons-learned-ij7)
- [Chart.js Performance Documentation](https://www.chartjs.org/docs/latest/general/performance.html)
- [LightningChart Performance Optimization](https://lightningchart.com/js-charts/docs/more-guides/optimizing-performance/)
- [Marine Fleet Management Dashboard](https://marineinspection.app/blog/best-2026-marine-fleet-management-dashboard)
- [Telemetry Dashboard Real-Time Data](https://lightningchart.com/blog/telemetry-dashboard/)
- [Marine Vessel Telemetry ML Processing](https://www.researchgate.net/publication/340938819_Marine_Vessel_Telemetry_Data_Processing_Using_Machine_Learning)
- [NOAA PMEL Data Visualization](https://data.pmel.noaa.gov/viz/)

---

**Document Status:** Complete
**Last Updated:** 2026-07-28
**Version:** 1.0
**Author:** Research synthesis based on web sources and DAW patterns analysis

