# DAW Timeline Implementation Guide for AELMA

**Practical Implementation Guide:** Step-by-step code examples for building a DAW-style timeline interface for marine telemetry

**Date:** 2026-07-28
**Status:** Implementation Guide
**Target:** AELMA Phase 5 Viewer Development

---

## Quick Start

This guide provides complete, copy-pasteable code examples for implementing a DAW-style timeline interface adapted for marine vessel telemetry in the AELMA system.

**Prerequisites:**
- Modern browser with Canvas support
- Basic understanding of JavaScript/HTML5 Canvas
- AELMA TwinCore running (WebSocket endpoint)

**Estimated Implementation Time:** 2-3 days for basic timeline, 1 week for full feature set

---

## Part 1: Basic Timeline Structure

### 1.1 HTML Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AELMA Marine Timeline</title>
  <style>
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #1a1a1a;
      color: #ccc;
      overflow: hidden;
      height: 100vh;
    }

    .timeline-container {
      display: flex;
      flex-direction: column;
      height: 100vh;
    }

    .timeline-toolbar {
      display: flex;
      gap: 8px;
      padding: 8px 12px;
      background: #252525;
      border-bottom: 1px solid #444;
      align-items: center;
    }

    .timeline-main {
      flex: 1;
      display: flex;
      overflow: hidden;
    }

    .track-headers {
      width: 220px;
      background: #252525;
      border-right: 1px solid #444;
      overflow-y: auto;
      flex-shrink: 0;
    }

    .tracks-content {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    .timeline-ruler {
      height: 40px;
      background: #1a1a1a;
      border-bottom: 1px solid #333;
      flex-shrink: 0;
    }

    .tracks-container {
      flex: 1;
      overflow-y: auto;
      overflow-x: hidden;
      position: relative;
    }

    .track-header {
      border-bottom: 1px solid #333;
      display: flex;
      flex-direction: column;
      position: relative;
    }

    .track-info {
      flex: 1;
      display: flex;
      align-items: center;
      padding: 8px;
      gap: 8px;
      cursor: pointer;
    }

    .track-info:hover {
      background: #2a2a2a;
    }

    .track-color {
      width: 12px;
      height: 12px;
      border-radius: 2px;
      flex-shrink: 0;
    }

    .track-name {
      flex: 1;
      font-size: 12px;
      font-weight: 500;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .track-badge {
      font-size: 9px;
      padding: 2px 6px;
      background: #444;
      border-radius: 3px;
      color: #999;
      text-transform: uppercase;
      flex-shrink: 0;
    }

    .track-controls {
      display: flex;
      gap: 4px;
      padding: 4px 8px;
      border-top: 1px solid #333;
    }

    .track-btn {
      width: 20px;
      height: 20px;
      border: 1px solid #555;
      background: #444;
      color: #ccc;
      border-radius: 3px;
      font-size: 10px;
      font-weight: bold;
      cursor: pointer;
      transition: all 0.1s;
    }

    .track-btn:hover {
      background: #555;
    }

    .track-btn.active {
      border-color: var(--active-color, #4a9eff);
      background: var(--active-color, #4a9eff);
      color: white;
    }

    .resize-handle {
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      height: 4px;
      cursor: ns-resize;
    }

    .toolbar-btn {
      padding: 6px 12px;
      background: #333;
      border: 1px solid #555;
      color: #ccc;
      border-radius: 4px;
      font-size: 11px;
      cursor: pointer;
      transition: background 0.1s;
    }

    .toolbar-btn:hover {
      background: #444;
    }

    .toolbar-btn.primary {
      background: #4a9eff;
      border-color: #4a9eff;
      color: white;
    }

    .toolbar-btn.primary:hover {
      background: #3a8eef;
    }

    .zoom-group {
      display: flex;
      gap: 4px;
      align-items: center;
    }

    .zoom-label {
      font-size: 11px;
      color: #888;
      margin-right: 4px;
    }

    .track-canvas {
      border-bottom: 1px solid #333;
      display: block;
    }

    .loading-overlay {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(26, 26, 26, 0.8);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 14px;
      color: #888;
    }

    .tooltip {
      position: absolute;
      background: #333;
      border: 1px solid #555;
      border-radius: 4px;
      padding: 8px 12px;
      font-size: 11px;
      pointer-events: none;
      z-index: 1000;
      max-width: 250px;
    }

    .tooltip-time {
      color: #4a9eff;
      font-weight: 500;
      margin-bottom: 4px;
    }

    .tooltip-value {
      color: #ccc;
    }

    .current-time-line {
      position: absolute;
      top: 0;
      bottom: 0;
      width: 2px;
      background: #ff6600;
      pointer-events: none;
      z-index: 100;
    }

    .current-time-knob {
      position: absolute;
      top: 0;
      width: 12px;
      height: 8px;
      background: #ff6600;
      clip-path: polygon(50% 100%, 0 0, 100% 0);
      transform: translateX(-50%);
    }
  </style>
</head>
<body>
  <div class="timeline-container">
    <div class="timeline-toolbar">
      <div class="zoom-group">
        <span class="zoom-label">Zoom:</span>
        <button class="toolbar-btn zoom-preset" data-duration="60">1m</button>
        <button class="toolbar-btn zoom-preset" data-duration="300">5m</button>
        <button class="toolbar-btn zoom-preset" data-duration="900">15m</button>
        <button class="toolbar-btn zoom-preset" data-duration="3600">1h</button>
        <button class="toolbar-btn zoom-preset" data-duration="21600">6h</button>
        <button class="toolbar-btn zoom-preset" data-duration="86400">1d</button>
        <button class="toolbar-btn zoom-preset" data-duration="604800">1w</button>
      </div>
      <div style="flex: 1;"></div>
      <button class="toolbar-btn primary" id="go-to-now">Now</button>
    </div>

    <div class="timeline-main">
      <div class="track-headers" id="track-headers">
        <!-- Track headers will be inserted here -->
      </div>

      <div class="tracks-content">
        <canvas class="timeline-ruler" id="timeline-ruler"></canvas>
        <div class="tracks-container" id="tracks-container">
          <!-- Track canvases will be inserted here -->
        </div>
      </div>
    </div>
  </div>

  <div class="tooltip" id="tooltip" style="display: none;"></div>
  <div class="current-time-line" id="current-time-line">
    <div class="current-time-knob"></div>
  </div>

  <script src="timeline.js"></script>
</body>
</html>
```

---

## Part 2: Core Timeline JavaScript

### 2.1 Main Timeline Class (timeline.js)

```javascript
/**
 * AELMA Marine Timeline - DAW-style interface for vessel telemetry
 * Adapted from Digital Audio Workstation patterns for marine data visualization
 */

class MarineTimeline {
  constructor(containerSelector, options = {}) {
    this.container = document.querySelector(containerSelector);
    if (!this.container) {
      throw new Error(`Container not found: ${containerSelector}`);
    }

    this.options = {
      headerWidth: 220,
      rulerHeight: 40,
      defaultTrackHeight: 80,
      minTrackHeight: 30,
      maxTrackHeight: 200,
      maxDataPoints: 10000,
      ...options
    };

    // State
    this.tracks = new Map();
    this.viewport = {
      start: Date.now() - 3600000, // 1 hour ago
      end: Date.now(),
      duration: 3600000
    };
    this.currentTime = Date.now();
    this.selection = null;
    this.isPanning = false;
    this.isSelecting = false;
    this.panStart = null;
    this.selectionStart = null;

    // DOM elements
    this.trackHeadersContainer = this.container.querySelector('#track-headers');
    this.tracksContainer = this.container.querySelector('#tracks-container');
    this.rulerCanvas = this.container.querySelector('#timeline-ruler');
    this.tooltip = this.container.querySelector('#tooltip');
    this.currentTimeLine = this.container.querySelector('#current-time-line');

    // Initialize
    this.initRuler();
    this.setupEventHandlers();
    this.setupToolbar();

    // Start render loop
    this.startRenderLoop();
  }

  /**
   * Initialize timeline ruler
   */
  initRuler() {
    const dpr = window.devicePixelRatio || 1;
    const rect = this.rulerCanvas.getBoundingClientRect();

    this.rulerCanvas.width = rect.width * dpr;
    this.rulerCanvas.height = this.options.rulerHeight * dpr;

    this.rulerCtx = this.rulerCanvas.getContext('2d');
    this.rulerCtx.scale(dpr, dpr);

    this.renderRuler();
  }

  /**
   * Setup event handlers for pan, zoom, selection
   */
  setupEventHandlers() {
    // Wheel zoom
    this.tracksContainer.addEventListener('wheel', (e) => {
      e.preventDefault();
      this.handleWheelZoom(e);
    }, { passive: false });

    // Pan and selection
    this.tracksContainer.addEventListener('mousedown', (e) => {
      const rect = this.tracksContainer.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      if (e.button === 0 && !e.shiftKey) {
        // Left click: pan
        this.isPanning = true;
        this.panStart = { x: e.clientX, y: e.clientY };
        this.viewportStart = { ...this.viewport };
        e.preventDefault();
      } else if (e.button === 0 && e.shiftKey) {
        // Shift + left click: select
        this.isSelecting = true;
        this.selectionStart = { x, y };
        e.preventDefault();
      }
    });

    document.addEventListener('mousemove', (e) => {
      if (this.isPanning) {
        this.handlePan(e);
      } else if (this.isSelecting) {
        this.handleSelection(e);
      } else {
        this.handleHover(e);
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

    // Window resize
    window.addEventListener('resize', () => {
      this.handleResize();
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
      this.handleKeyDown(e);
    });

    // Update current time indicator position
    this.updateCurrentTimeLine();
  }

  /**
   * Setup toolbar buttons
   */
  setupToolbar() {
    // Zoom presets
    this.container.querySelectorAll('.zoom-preset').forEach(btn => {
      btn.addEventListener('click', () => {
        const duration = parseInt(btn.dataset.duration);
        this.setZoomPreset(duration);
      });
    });

    // Go to current time
    this.container.querySelector('#go-to-now').addEventListener('click', () => {
      this.goToCurrentTime();
    });
  }

  /**
   * Handle wheel zoom
   */
  handleWheelZoom(e) {
    const zoomFactor = e.deltaY > 0 ? 1.1 : 1 / 1.1;

    const rect = this.tracksContainer.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseTime = this.xToTime(mouseX);

    this.zoomAround(mouseTime, zoomFactor);
  }

  /**
   * Zoom around a specific time point
   */
  zoomAround(centerTime, scale) {
    const duration = this.viewport.end - this.viewport.start;
    const newDuration = duration * scale;

    // Clamp minimum (1 second) and maximum (1 year) zoom
    const clampedDuration = Math.max(1000, Math.min(31536000000, newDuration));

    // Keep centerTime stable during zoom
    const leftRatio = (centerTime - this.viewport.start) / duration;
    const newStart = centerTime - clampedDuration * leftRatio;
    const newEnd = newStart + clampedDuration;

    this.setViewport(newStart, newEnd);
  }

  /**
   * Handle panning
   */
  handlePan(e) {
    const deltaX = e.clientX - this.panStart.x;
    const deltaY = e.clientY - this.panStart.y;

    const pixelsPerMs = this.tracksContainer.clientWidth / this.viewport.duration;
    const deltaTime = -deltaX / pixelsPerMs;

    this.viewport.start = this.viewportStart.start + deltaTime;
    this.viewport.end = this.viewportStart.end + deltaTime;
    this.viewport.duration = this.viewport.end - this.viewport.start;

    // Update vertical scroll
    this.tracksContainer.scrollTop = this.tracksContainer.scrollTop - deltaY;

    this.renderAll();
  }

  /**
   * Handle time selection
   */
  handleSelection(e) {
    const rect = this.tracksContainer.getBoundingClientRect();
    const x = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
    const startX = Math.max(0, Math.min(rect.width, this.selectionStart.x));

    this.selection = {
      start: this.xToTime(Math.min(startX, x)),
      end: this.xToTime(Math.max(startX, x))
    };

    this.renderAll();
  }

  /**
   * Finalize selection
   */
  finalizeSelection() {
    if (this.selection && this.selection.end - this.selection.start > 1000) {
      // Only trigger if selection is > 1 second
      this.onSelectionComplete?.(this.selection);
    }
    this.selection = null;
    this.renderAll();
  }

  /**
   * Handle hover (tooltip)
   */
  handleHover(e) {
    const rect = this.tracksContainer.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Find which track we're hovering
    const trackEl = e.target.closest('.track-canvas');
    if (!trackEl) {
      this.tooltip.style.display = 'none';
      return;
    }

    const trackId = trackEl.dataset.trackId;
    const track = this.tracks.get(trackId);
    if (!track) return;

    const time = this.xToTime(x);
    const dataPoint = this.findDataPoint(track, time, y);

    if (dataPoint) {
      this.showTooltip(e.clientX, e.clientY, time, dataPoint, track);
    } else {
      this.tooltip.style.display = 'none';
    }
  }

  /**
   * Find data point at position
   */
  findDataPoint(track, time, y) {
    if (!track.data || track.data.length === 0) return null;

    // Find closest data point
    const closest = track.data.reduce((prev, curr) => {
      return Math.abs(curr.timestamp - time) < Math.abs(prev.timestamp - time) ? curr : prev;
    });

    // Check if within reasonable time range (10 pixels worth)
    const timeThreshold = this.viewport.duration / this.tracksContainer.clientWidth * 10;
    if (Math.abs(closest.timestamp - time) > timeThreshold) return null;

    return closest;
  }

  /**
   * Show tooltip
   */
  showTooltip(x, y, time, dataPoint, track) {
    const timeStr = new Date(time).toLocaleTimeString();
    const valueStr = this.formatDataValue(dataPoint, track);

    this.tooltip.innerHTML = `
      <div class="tooltip-time">${timeStr}</div>
      <div class="tooltip-value">${valueStr}</div>
    `;

    this.tooltip.style.display = 'block';
    this.tooltip.style.left = (x + 15) + 'px';
    this.tooltip.style.top = (y + 15) + 'px';
  }

  /**
   * Format data value for tooltip
   */
  formatDataValue(dataPoint, track) {
    switch (track.type) {
      case 'position':
        return `Pos: ${dataPoint.latitude?.toFixed(6)}°, ${dataPoint.longitude?.toFixed(6)}°`;
      case 'depth':
        return `Depth: ${dataPoint.value?.toFixed(1)} m`;
      case 'speed':
        return `Speed: ${dataPoint.value?.toFixed(1)} kn`;
      case 'heading':
        return `Heading: ${dataPoint.value?.toFixed(0)}°`;
      default:
        return JSON.stringify(dataPoint);
    }
  }

  /**
   * Handle keyboard shortcuts
   */
  handleKeyDown(e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    switch (e.key) {
      case 'n':
      case 'N':
        this.goToCurrentTime();
        break;
      case 'f':
      case 'F':
        this.fitToSelection();
        break;
      case 'Escape':
        this.selection = null;
        this.renderAll();
        break;
    }
  }

  /**
   * Handle window resize
   */
  handleResize() {
    this.initRuler();
    this.resizeTracks();
    this.renderAll();
  }

  /**
   * Resize track canvases
   */
  resizeTracks() {
    const dpr = window.devicePixelRatio || 1;
    const width = this.tracksContainer.clientWidth;

    this.tracks.forEach(track => {
      track.canvas.width = width * dpr;
      track.canvas.height = track.height * dpr;
      track.ctx.scale(dpr, dpr);
    });
  }

  /**
   * Add a new track
   */
  addTrack(trackId, options = {}) {
    const trackOptions = {
      name: trackId,
      type: 'data',
      color: '#4a9eff',
      height: this.options.defaultTrackHeight,
      data: [],
      events: [],
      clips: [],
      ...options
    };

    // Create track header
    const headerEl = this.createTrackHeader(trackId, trackOptions);
    this.trackHeadersContainer.appendChild(headerEl);

    // Create track canvas
    const canvas = document.createElement('canvas');
    canvas.className = 'track-canvas';
    canvas.dataset.trackId = trackId;
    canvas.style.cssText = `
      width: 100%;
      height: ${trackOptions.height}px;
    `;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = this.tracksContainer.clientWidth * dpr;
    canvas.height = trackOptions.height * dpr;

    this.tracksContainer.appendChild(canvas);

    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);

    // Store track
    this.tracks.set(trackId, {
      id: trackId,
      ...trackOptions,
      canvas,
      ctx,
      element: headerEl
    });

    // Setup track event handlers
    this.setupTrackEvents(trackId);

    return trackId;
  }

  /**
   * Create track header element
   */
  createTrackHeader(trackId, options) {
    const header = document.createElement('div');
    header.className = 'track-header';
    header.dataset.trackId = trackId;
    header.style.height = options.height + 'px';

    header.innerHTML = `
      <div class="track-info">
        <div class="track-color" style="background: ${options.color};"></div>
        <div class="track-name">${options.name}</div>
        <div class="track-badge">${options.type}</div>
      </div>
      <div class="track-controls">
        <button class="track-btn mute-btn" data-track="${trackId}" style="--active-color: #ff6600;">M</button>
        <button class="track-btn solo-btn" data-track="${trackId}" style="--active-color: #ffcc00;">S</button>
        <button class="track-btn arm-btn" data-track="${trackId}" style="--active-color: #ff3333;">R</button>
      </div>
      <div class="resize-handle" data-track="${trackId}"></div>
    `;

    // Setup button handlers
    header.querySelector('.mute-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggleTrackMute(trackId);
    });

    header.querySelector('.solo-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggleTrackSolo(trackId);
    });

    header.querySelector('.arm-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      this.toggleTrackArm(trackId);
    });

    // Setup resize handler
    const resizeHandle = header.querySelector('.resize-handle');
    let isResizing = false;
    let startY = 0;
    let startHeight = 0;

    resizeHandle.addEventListener('mousedown', (e) => {
      isResizing = true;
      startY = e.clientY;
      startHeight = options.height;
      e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
      if (!isResizing) return;

      const deltaY = e.clientY - startY;
      const newHeight = Math.max(
        this.options.minTrackHeight,
        Math.min(this.options.maxTrackHeight, startHeight + deltaY)
      );

      this.setTrackHeight(trackId, newHeight);
    });

    document.addEventListener('mouseup', () => {
      isResizing = false;
    });

    return header;
  }

  /**
   * Setup track-specific event handlers
   */
  setupTrackEvents(trackId) {
    const track = this.tracks.get(trackId);
    if (!track) return;

    let isDragging = false;
    let dragStart = null;

    track.canvas.addEventListener('mousedown', (e) => {
      isDragging = true;
      dragStart = { x: e.clientX, y: e.clientY };
    });

    track.canvas.addEventListener('mousemove', (e) => {
      if (!isDragging) return;

      const deltaX = e.clientX - dragStart.x;
      const pixelsPerMs = this.tracksContainer.clientWidth / this.viewport.duration;
      const deltaTime = -deltaX / pixelsPerMs;

      this.viewport.start += deltaTime;
      this.viewport.end += deltaTime;
      this.renderAll();
    });

    track.canvas.addEventListener('mouseup', () => {
      isDragging = false;
    });
  }

  /**
   * Set track height
   */
  setTrackHeight(trackId, height) {
    const track = this.tracks.get(trackId);
    if (!track) return;

    track.height = height;
    track.element.style.height = height + 'px';
    track.canvas.style.height = height + 'px';

    const dpr = window.devicePixelRatio || 1;
    track.canvas.height = height * dpr;
    track.ctx.scale(dpr, dpr);

    this.renderTrack(trackId);
  }

  /**
   * Toggle track mute
   */
  toggleTrackMute(trackId) {
    const track = this.tracks.get(trackId);
    if (!track) return;

    track.isMuted = !track.isMuted;
    track.element.querySelector('.mute-btn').classList.toggle('active', track.isMuted);

    this.onTrackMuteToggle?.(trackId, track.isMuted);
  }

  /**
   * Toggle track solo
   */
  toggleTrackSolo(trackId) {
    const track = this.tracks.get(trackId);
    if (!track) return;

    track.isSolo = !track.isSolo;
    track.element.querySelector('.solo-btn').classList.toggle('active', track.isSolo);

    this.onTrackSoloToggle?.(trackId, track.isSolo);
  }

  /**
   * Toggle track arm (recording/armed)
   */
  toggleTrackArm(trackId) {
    const track = this.tracks.get(trackId);
    if (!track) return;

    track.isArmed = !track.isArmed;
    track.element.querySelector('.arm-btn').classList.toggle('active', track.isArmed);

    this.onTrackArmToggle?.(trackId, track.isArmed);
  }

  /**
   * Update track data
   */
  updateTrackData(trackId, data, append = true) {
    const track = this.tracks.get(trackId);
    if (!track) return;

    if (append) {
      track.data.push(...data);
      // Trim if needed
      if (track.data.length > this.options.maxDataPoints) {
        track.data = track.data.slice(-this.options.maxDataPoints);
      }
    } else {
      track.data = data;
    }

    this.renderTrack(trackId);
  }

  /**
   * Add event marker to track
   */
  addTrackEvent(trackId, event) {
    const track = this.tracks.get(trackId);
    if (!track) return;

    track.events.push(event);
    this.renderTrack(trackId);
  }

  /**
   * Add clip to track
   */
  addTrackClip(trackId, clip) {
    const track = this.tracks.get(trackId);
    if (!track) return;

    track.clips.push(clip);
    this.renderTrack(trackId);
  }

  /**
   * Set viewport
   */
  setViewport(start, end) {
    this.viewport = { start, end, duration: end - start };
    this.renderAll();
    this.onViewportChange?.(this.viewport);
  }

  /**
   * Set zoom preset
   */
  setZoomPreset(duration) {
    const centerTime = (this.viewport.start + this.viewport.end) / 2;
    const newStart = centerTime - duration / 2;
    const newEnd = centerTime + duration / 2;
    this.setViewport(newStart, newEnd);
  }

  /**
   * Go to current time
   */
  goToCurrentTime() {
    const now = Date.now();
    const duration = this.viewport.duration;
    this.setViewport(now - duration / 2, now + duration / 2);
  }

  /**
   * Fit to selection
   */
  fitToSelection() {
    if (!this.selection) return;

    const padding = (this.selection.end - this.selection.start) * 0.1;
    this.setViewport(
      this.selection.start - padding,
      this.selection.end + padding
    );
  }

  /**
   * Update current time indicator
   */
  updateCurrentTimeLine() {
    const x = this.timeToX(this.currentTime);
    this.currentTimeLine.style.left = x + 'px';
  }

  /**
   * Convert time to X position
   */
  timeToX(time) {
    return ((time - this.viewport.start) / this.viewport.duration) *
           this.tracksContainer.clientWidth;
  }

  /**
   * Convert X position to time
   */
  xToTime(x) {
    return this.viewport.start +
           (x / this.tracksContainer.clientWidth) * this.viewport.duration;
  }

  /**
   * Render all components
   */
  renderAll() {
    this.renderRuler();
    this.renderTracks();
    this.updateCurrentTimeLine();
  }

  /**
   * Render timeline ruler
   */
  renderRuler() {
    const ctx = this.rulerCtx;
    const width = this.rulerCanvas.width / window.devicePixelRatio;
    const height = this.options.rulerHeight;

    // Clear
    ctx.clearRect(0, 0, width, height);

    // Background
    ctx.fillStyle = '#1a1a1a';
    ctx.fillRect(0, 0, width, height);

    // Calculate grid spacing
    const gridSpacing = this.calculateGridSpacing();

    // Draw minor grid
    ctx.strokeStyle = '#2a2a2a';
    ctx.lineWidth = 1;

    for (let t = Math.floor(this.viewport.start / gridSpacing) * gridSpacing;
         t <= this.viewport.end; t += gridSpacing) {
      const x = this.timeToX(t);
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }

    // Draw major grid and labels
    ctx.strokeStyle = '#333';
    ctx.fillStyle = '#888';
    ctx.font = '11px -apple-system, BlinkMacSystemFont, sans-serif';
    ctx.textAlign = 'center';

    for (let t = Math.floor(this.viewport.start / gridSpacing) * gridSpacing;
         t <= this.viewport.end; t += gridSpacing) {
      const x = this.timeToX(t);

      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();

      const label = this.formatTime(t);
      ctx.fillText(label, x, height - 8);
    }
  }

  /**
   * Calculate grid spacing based on viewport
   */
  calculateGridSpacing() {
    const targetPixelSpacing = 100;
    const pixelsPerMs = this.tracksContainer.clientWidth / this.viewport.duration;
    const idealSpacing = targetPixelSpacing / pixelsPerMs;

    // Round to nice intervals
    const magnitude = Math.pow(10, Math.floor(Math.log10(idealSpacing)));
    const normalized = idealSpacing / magnitude;

    let niceSpacing;
    if (normalized < 2) niceSpacing = 1 * magnitude;
    else if (normalized < 5) niceSpacing = 2 * magnitude;
    else if (normalized < 10) niceSpacing = 5 * magnitude;
    else niceSpacing = 10 * magnitude;

    return niceSpacing;
  }

  /**
   * Format time for ruler
   */
  formatTime(timestamp) {
    const date = new Date(timestamp);
    const duration = this.viewport.duration;

    if (duration < 60000) {
      // < 1 minute: show seconds
      return date.toLocaleTimeString();
    } else if (duration < 3600000) {
      // < 1 hour: show minutes
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else if (duration < 86400000) {
      // < 1 day: show hours
      return `${date.getHours()}:00`;
    } else if (duration < 604800000) {
      // < 1 week: show date
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } else {
      // >= 1 week: show week
      return `W${this.getWeekNumber(date)}`;
    }
  }

  /**
   * Get week number
   */
  getWeekNumber(date) {
    const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
    const dayNum = d.getUTCDay() || 7;
    d.setUTCDate(d.getUTCDate() + 4 - dayNum);
    const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    return Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
  }

  /**
   * Render all tracks
   */
  renderTracks() {
    this.tracks.forEach((track, trackId) => {
      this.renderTrack(trackId);
    });
  }

  /**
   * Render single track
   */
  renderTrack(trackId) {
    const track = this.tracks.get(trackId);
    if (!track || track.isMuted) return;

    const ctx = track.ctx;
    const width = track.canvas.width / window.devicePixelRatio;
    const height = track.height;

    // Clear
    ctx.clearRect(0, 0, width, height);

    // Background
    ctx.fillStyle = '#1e1e1e';
    ctx.fillRect(0, 0, width, height);

    // Grid lines
    ctx.strokeStyle = '#2a2a2a';
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
    if (track.data && track.data.length > 0) {
      this.renderTrackData(ctx, track, width, height);
    }

    // Render clips
    if (track.clips && track.clips.length > 0) {
      this.renderTrackClips(ctx, track, width, height);
    }

    // Render events
    if (track.events && track.events.length > 0) {
      this.renderTrackEvents(ctx, track, height);
    }

    // Selection highlight
    if (this.selection) {
      this.renderSelection(ctx, width, height);
    }
  }

  /**
   * Render track data
   */
  renderTrackData(ctx, track, width, height) {
    // Filter visible data points
    const visibleData = track.data.filter(
      d => d.timestamp >= this.viewport.start && d.timestamp <= this.viewport.end
    );

    if (visibleData.length === 0) return;

    // Get value range
    const values = visibleData.map(d => this.getTrackValue(d, track));
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const valueRange = maxValue - minValue || 1;

    const padding = 4;
    const chartHeight = height - padding * 2;

    const valueToY = (value) => {
      return padding + chartHeight - ((value - minValue) / valueRange) * chartHeight;
    };

    const timeToX = (timestamp) => {
      return ((timestamp - this.viewport.start) / this.viewport.duration) * width;
    };

    // Draw fill
    ctx.fillStyle = track.color + '20'; // 20 hex = low opacity
    ctx.beginPath();
    ctx.moveTo(0, height);

    visibleData.forEach((point, i) => {
      const x = timeToX(point.timestamp);
      const y = valueToY(this.getTrackValue(point, track));
      if (i === 0) ctx.lineTo(x, y);
      else ctx.lineTo(x, y);
    });

    ctx.lineTo(width, height);
    ctx.closePath();
    ctx.fill();

    // Draw line
    ctx.strokeStyle = track.color;
    ctx.lineWidth = 1.5;
    ctx.beginPath();

    visibleData.forEach((point, i) => {
      const x = timeToX(point.timestamp);
      const y = valueToY(this.getTrackValue(point, track));
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });

    ctx.stroke();
  }

  /**
   * Get value from data point based on track type
   */
  getTrackValue(point, track) {
    switch (track.type) {
      case 'position':
        return point.latitude || 0;
      case 'depth':
      case 'speed':
      case 'heading':
        return point.value || 0;
      default:
        return point.value || 0;
    }
  }

  /**
   * Render track clips
   */
  renderTrackClips(ctx, track, width, height) {
    track.clips.forEach(clip => {
      const x = this.timeToX(clip.startTime);
      const w = this.timeToX(clip.endTime) - x;

      // Clip background
      ctx.fillStyle = (clip.color || track.color) + '30';
      ctx.fillRect(x, 0, w, height);

      // Clip border
      ctx.strokeStyle = clip.color || track.color;
      ctx.lineWidth = 2;
      ctx.strokeRect(x, 0, w, height);

      // Clip label
      ctx.fillStyle = '#fff';
      ctx.font = '11px -apple-system, sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(clip.label, x + 6, 14);
    });
  }

  /**
   * Render track events
   */
  renderTrackEvents(ctx, track, height) {
    track.events.forEach(event => {
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
        ctx.font = '10px -apple-system, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(event.label, x, 24);
      }
    });
  }

  /**
   * Render selection on track
   */
  renderSelection(ctx, width, height) {
    const startX = this.timeToX(this.selection.start);
    const endX = this.timeToX(this.selection.end);

    ctx.fillStyle = 'rgba(74, 158, 255, 0.1)';
    ctx.fillRect(startX, 0, endX - startX, height);

    ctx.strokeStyle = '#4a9eff';
    ctx.lineWidth = 2;
    ctx.strokeRect(startX, 0, endX - startX, height);
  }

  /**
   * Start render loop
   */
  startRenderLoop() {
    let lastTime = 0;
    const targetFPS = 60;
    const frameInterval = 1000 / targetFPS;

    const animate = (currentTime) => {
      requestAnimationFrame(animate);

      const elapsed = currentTime - lastTime;
      if (elapsed < frameInterval) return;

      lastTime = currentTime - (elapsed % frameInterval);

      // Update current time
      this.currentTime = Date.now();

      // Auto-scroll if near current time
      const timeToEdge = this.viewport.end - this.currentTime;
      if (timeToEdge < this.viewport.duration * 0.1) {
        // Auto-extend viewport
        const duration = this.viewport.duration;
        this.viewport.start = this.currentTime - duration * 0.9;
        this.viewport.end = this.currentTime + duration * 0.1;
        this.renderAll();
      }

      // Update current time indicator
      this.updateCurrentTimeLine();
    };

    requestAnimationFrame(animate);
  }

  /**
   * Event callbacks (to be overridden)
   */
  onViewportChange(viewport) {}
  onSelectionComplete(selection) {}
  onTrackMuteToggle(trackId, isMuted) {}
  onTrackSoloToggle(trackId, isSoloed) {}
  onTrackArmToggle(trackId, isArmed) {}
}
```

---

## Part 3: WebSocket Integration

### 3.1 Data Source Class

```javascript
/**
 * Timeline data source - connects to AELMA TwinCore via WebSocket
 */
class TimelineDataSource {
  constructor(timeline, wsUrl) {
    this.timeline = timeline;
    this.wsUrl = wsUrl;
    this.ws = null;
    this.dataBuffers = new Map();
    this.reconnectDelay = 5000;
    this.isConnected = false;
  }

  /**
   * Connect to TwinCore
   */
  connect() {
    console.log(`Connecting to TwinCore at ${this.wsUrl}`);

    this.ws = new WebSocket(this.wsUrl);

    this.ws.onopen = () => {
      console.log('Timeline connected to TwinCore');
      this.isConnected = true;
      this.sendSubscription();
    };

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        this.handleMessage(message);
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    this.ws.onerror = (error) => {
      console.error('Timeline WebSocket error:', error);
    };

    this.ws.onclose = () => {
      console.log('Timeline disconnected from TwinCore');
      this.isConnected = false;

      // Auto-reconnect
      setTimeout(() => {
        console.log('Attempting to reconnect...');
        this.connect();
      }, this.reconnectDelay);
    };
  }

  /**
   * Send subscription message
   */
  sendSubscription() {
    if (!this.isConnected) return;

    this.ws.send(JSON.stringify({
      type: 'subscribe',
      tracks: ['position', 'depth', 'speed', 'heading', 'alerts'],
      formats: ['vessel_state', 'alert', 'historical_data']
    }));
  }

  /**
   * Handle incoming message
   */
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

      case 'watcher_event':
        this.handleWatcherEvent(message.data);
        break;

      default:
        console.log('Unknown message type:', message.type);
    }
  }

  /**
   * Handle vessel state update
   */
  handleVesselState(state) {
    const timestamp = state.timestamp_ns / 1e6; // Convert ns to ms

    // Update position track
    this.updateTrackData('position', timestamp, {
      timestamp,
      latitude: state.position.lat,
      longitude: state.position.lon
    });

    // Update depth track
    this.updateTrackData('depth', timestamp, {
      timestamp,
      value: state.depth_m
    });

    // Update speed track
    this.updateTrackData('speed', timestamp, {
      timestamp,
      value: state.speed_knots
    });

    // Update heading track
    this.updateTrackData('heading', timestamp, {
      timestamp,
      value: state.heading_deg
    });
  }

  /**
   * Handle alert
   */
  handleAlert(alert) {
    const timestamp = alert.timestamp_ns / 1e6;

    // Add event marker to alerts track
    this.timeline.addTrackEvent('alerts', {
      timestamp,
      type: alert.alert_type,
      label: alert.message || alert.alert_type,
      color: this.getAlertColor(alert.severity),
      data: alert
    });
  }

  /**
   * Handle watcher event
   */
  handleWatcherEvent(event) {
    const timestamp = event.timestamp_ns / 1e6;

    this.timeline.addTrackEvent('alerts', {
      timestamp,
      type: 'watcher',
      label: `${event.watcher_id}: ${event.trigger_condition}`,
      color: this.getWatcherColor(event.severity),
      data: event
    });
  }

  /**
   * Handle historical data
   */
  handleHistoricalData(data) {
    // Bulk load historical data for each track
    data.track_data.forEach(trackData => {
      const trackId = trackData.track_id;
      const points = trackData.data.map(point => ({
        timestamp: point.timestamp_ns / 1e6,
        value: point.value,
        ...point.metadata
      }));

      this.updateTrackData(trackId, null, points, false);
    });
  }

  /**
   * Update track data
   */
  updateTrackData(trackId, timestamp, value, append = true) {
    const track = this.timeline.tracks.get(trackId);
    if (!track) return;

    if (append) {
      if (timestamp && value) {
        track.data.push({ timestamp, ...value });
      }

      // Trim buffer if needed
      if (track.data.length > 10000) {
        track.data = track.data.slice(-10000);
      }
    } else {
      track.data = value;
    }

    this.timeline.renderTrack(trackId);
  }

  /**
   * Get color for alert severity
   */
  getAlertColor(severity) {
    switch (severity) {
      case 'critical': return '#ff3333';
      case 'warning': return '#ffcc00';
      case 'info': return '#4a9eff';
      default: return '#888888';
    }
  }

  /**
   * Get color for watcher severity
   */
  getWatcherColor(severity) {
    switch (severity) {
      case 'critical': return '#ff3333';
      case 'warning': return '#ff9900';
      case 'caution': return '#ffcc00';
      default: return '#4a9eff';
    }
  }

  /**
   * Request historical data
   */
  requestHistoricalData(trackId, startTime, endTime) {
    if (!this.isConnected) return;

    this.ws.send(JSON.stringify({
      type: 'request_historical',
      track_id: trackId,
      start_time_ns: startTime * 1e6,
      end_time_ns: endTime * 1e6
    }));
  }

  /**
   * Disconnect
   */
  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.isConnected = false;
  }
}
```

---

## Part 4: Example Usage

### 4.1 Initialize Timeline

```javascript
// Initialize timeline
const timeline = new MarineTimeline('.timeline-container', {
  headerWidth: 220,
  rulerHeight: 40,
  defaultTrackHeight: 80
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
  console.log('Selected time range:', {
    start: new Date(selection.start),
    end: new Date(selection.end),
    duration: (selection.end - selection.start) / 1000 + ' seconds'
  });

  // Could trigger analysis, export, etc.
};

// Handle viewport changes
timeline.onViewportChange = (viewport) => {
  console.log('Viewport changed:', {
    start: new Date(viewport.start),
    end: new Date(viewport.end),
    duration: (viewport.duration / 1000 / 60) + ' minutes'
  });

  // Could request historical data for new viewport
  const trackIds = ['position', 'depth', 'speed', 'heading'];
  trackIds.forEach(trackId => {
    dataSource.requestHistoricalData(trackId, viewport.start, viewport.end);
  });
};

// Handle track controls
timeline.onTrackMuteToggle = (trackId, isMuted) => {
  console.log(`${trackId} muted: ${isMuted}`);
};

timeline.onTrackSoloToggle = (trackId, isSoloed) => {
  console.log(`${trackId} soloed: ${isSoloed}`);
};

timeline.onTrackArmToggle = (trackId, isArmed) => {
  console.log(`${trackId} armed: ${isArmed}`);
};
```

### 4.2 Add Sample Data (for testing)

```javascript
// Add sample data for testing
function addSampleData() {
  const now = Date.now();
  const duration = 3600000; // 1 hour

  // Generate sample position data
  const positionData = [];
  for (let i = 0; i < 3600; i++) {
    const timestamp = now - duration + (i * 1000);
    positionData.push({
      timestamp,
      latitude: 57.1 + Math.sin(i / 600) * 0.01,
      longitude: -135.5 + Math.cos(i / 600) * 0.01
    });
  }
  timeline.updateTrackData('position', positionData, false);

  // Generate sample depth data
  const depthData = [];
  for (let i = 0; i < 3600; i++) {
    const timestamp = now - duration + (i * 1000);
    depthData.push({
      timestamp,
      value: 50 + Math.sin(i / 300) * 20 + Math.random() * 5
    });
  }
  timeline.updateTrackData('depth', depthData, false);

  // Generate sample speed data
  const speedData = [];
  for (let i = 0; i < 3600; i++) {
    const timestamp = now - duration + (i * 1000);
    speedData.push({
      timestamp,
      value: 8 + Math.sin(i / 600) * 2 + Math.random() * 1
    });
  }
  timeline.updateTrackData('speed', speedData, false);

  // Generate sample heading data
  const headingData = [];
  for (let i = 0; i < 3600; i++) {
    const timestamp = now - duration + (i * 1000);
    headingData.push({
      timestamp,
      value: 180 + Math.sin(i / 900) * 30
    });
  }
  timeline.updateTrackData('heading', headingData, false);

  // Add sample events
  const sampleEvents = [
    { timestamp: now - duration + 600000, label: 'Haul Start', color: '#00cc00' },
    { timestamp: now - duration + 1200000, label: 'Gear Change', color: '#ffcc00' },
    { timestamp: now - duration + 1800000, label: 'Haul End', color: '#00cc00' },
    { timestamp: now - duration + 2400000, label: 'Shallow Depth', color: '#ff3333' },
    { timestamp: now - duration + 3000000, label: 'Speed Warning', color: '#ff9900' }
  ];

  sampleEvents.forEach(event => {
    timeline.addTrackEvent('alerts', event);
  });

  console.log('Sample data added');
}

// Call to add sample data
addSampleData();
```

---

## Part 5: Advanced Features

### 5.1 Export Selection

```javascript
/**
 * Export selected time range data
 */
function exportSelection(selection, format = 'json') {
  const tracks = ['position', 'depth', 'speed', 'heading'];
  const exportData = {
    time_range: {
      start: new Date(selection.start).toISOString(),
      end: new Date(selection.end).toISOString()
    },
    tracks: {}
  };

  tracks.forEach(trackId => {
    const track = timeline.tracks.get(trackId);
    if (!track) return;

    const filteredData = track.data.filter(
      d => d.timestamp >= selection.start && d.timestamp <= selection.end
    );

    exportData.tracks[trackId] = {
      name: track.name,
      type: track.type,
      data_points: filteredData.length,
      data: filteredData
    };
  });

  if (format === 'json') {
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `aelma_export_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return exportData;
}

// Usage
timeline.onSelectionComplete = (selection) => {
  const exported = exportSelection(selection);
  console.log('Exported data:', exported);
};
```

### 5.2 Bookmarks/Markers

```javascript
/**
 * Add bookmark/marker
 */
function addBookmark(name, time, color = '#ffcc00') {
  const bookmark = {
    timestamp: time,
    label: name,
    color: color,
    type: 'bookmark'
  };

  timeline.addTrackEvent('alerts', bookmark);
  return bookmark;
}

// Usage
addBookmark('Waypoint Alpha', Date.now(), '#00cc00');
addBookmark('Fishing Start', Date.now() - 3600000, '#00ff00');
addBookmark('Gear Failure', Date.now() - 7200000, '#ff0000');
```

### 5.3 Data Analysis on Selection

```javascript
/**
 * Analyze selected time range
 */
function analyzeSelection(selection) {
  const analysis = {
    time_range: {
      start: new Date(selection.start),
      end: new Date(selection.end),
      duration_seconds: (selection.end - selection.start) / 1000
    },
    tracks: {}
  };

  ['depth', 'speed'].forEach(trackId => {
    const track = timeline.tracks.get(trackId);
    if (!track) return;

    const filteredData = track.data.filter(
      d => d.timestamp >= selection.start && d.timestamp <= selection.end
    );

    if (filteredData.length === 0) return;

    const values = filteredData.map(d => d.value);

    analysis.tracks[trackId] = {
      min: Math.min(...values),
      max: Math.max(...values),
      avg: values.reduce((a, b) => a + b, 0) / values.length,
      std: Math.sqrt(values.reduce((sum, v) => sum + Math.pow(v - analysis.tracks[trackId].avg, 2), 0) / values.length),
      samples: filteredData.length
    };
  });

  return analysis;
}

// Usage
timeline.onSelectionComplete = (selection) => {
  const analysis = analyzeSelection(selection);
  console.log('Selection analysis:', analysis);

  // Display analysis in UI
  displayAnalysis(analysis);
};

function displayAnalysis(analysis) {
  // Create analysis panel
  const panel = document.createElement('div');
  panel.style.cssText = `
    position: fixed;
    top: 60px;
    right: 20px;
    width: 250px;
    background: #252525;
    border: 1px solid #444;
    border-radius: 8px;
    padding: 16px;
    color: #ccc;
    font-size: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
  `;

  panel.innerHTML = `
    <div style="font-weight: bold; margin-bottom: 12px; color: #4a9eff;">
      Selection Analysis
    </div>
    <div style="margin-bottom: 8px;">
      Duration: ${analysis.time_range.duration_seconds.toFixed(1)}s
    </div>
    ${Object.entries(analysis.tracks).map(([trackId, stats]) => `
      <div style="margin-top: 12px; padding-top: 8px; border-top: 1px solid #333;">
        <div style="font-weight: 500; margin-bottom: 4px;">${trackId}</div>
        <div>Min: ${stats.min.toFixed(2)}</div>
        <div>Max: ${stats.max.toFixed(2)}</div>
        <div>Avg: ${stats.avg.toFixed(2)}</div>
        <div>Std: ${stats.std.toFixed(2)}</div>
      </div>
    `).join('')}
    <button onclick="this.parentElement.remove()" style="
      margin-top: 12px;
      padding: 6px 12px;
      background: #444;
      border: 1px solid #555;
      color: #ccc;
      border-radius: 4px;
      cursor: pointer;
      width: 100%;
    ">Close</button>
  `;

  document.body.appendChild(panel);
}
```

---

## Part 6: Styling and Theming

### 6.1 Dark Theme (Default)

The implementation uses a dark theme optimized for marine environments:

```css
/* Core colors */
--bg-primary: #1a1a1a;
--bg-secondary: #252525;
--bg-tertiary: #2a2a2a;
--border-color: #444;
--text-primary: #ccc;
--text-secondary: #888;

/* Accent colors */
--accent-blue: #4a9eff;
--accent-green: #00cc66;
--accent-yellow: #ffcc00;
--accent-orange: #ff6600;
--accent-red: #ff3333;

/* Track colors */
--track-position: #4a9eff;
--track-depth: #ff6600;
--track-speed: #00cc66;
--track-heading: #ffcc00;
--track-alert: #ff3333;
```

### 6.2 High Contrast Mode

```css
.theme-high-contrast {
  --bg-primary: #000000;
  --bg-secondary: #1a1a1a;
  --border-color: #666;
  --text-primary: #ffffff;
  --text-secondary: #cccccc;
}
```

### 6.3 Day Mode (for bright conditions)

```css
.theme-day {
  --bg-primary: #f5f5f5;
  --bg-secondary: #e8e8e8;
  --bg-tertiary: #d8d8d8;
  --border-color: #999;
  --text-primary: #333;
  --text-secondary: #666;
}
```

---

## Summary

This implementation guide provides a complete DAW-style timeline interface adapted for marine vessel telemetry in AELMA. The key features include:

**Core Features:**
- Multi-track timeline visualization
- Canvas-based rendering for performance
- Zoom and pan controls
- Time selection
- Track controls (mute, solo, arm)
- Real-time data updates
- WebSocket integration with TwinCore

**Advanced Features:**
- Data export
- Bookmarks and markers
- Selection analysis
- Multiple time scales
- Event markers
- Clip visualization

**Next Steps:**
1. Implement the basic timeline (Parts 1-4)
2. Test with simulator data
3. Add advanced features (Part 5)
4. Integrate with AELMA viewer
5. Gather feedback from crew
6. Iterate based on usage

**Sources:**
- [waveform-playlist GitHub](https://github.com/naomiaro/waveform-playlist)
- [MDN Web Audio API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Visualizations_with_Web_Audio_API)
- [SciChart Performance](https://www.scichart.com/demo/javascript/chart-realtime-performance-demo)
- [Building High-Performance Charts](https://dev.to/ibtekar/building-a-high-performance-real-time-chart-in-react-lessons-learned-ij7)

---

**Document Status:** Complete
**Last Updated:** 2026-07-28
**Version:** 1.0
