// AELMA Viewer — live 3D digital-twin front end for the F/V EILEEN.
// Connects to the twin core over WebSocket and renders the vessel,
// its track, and progressive bathymetry in a local ENU frame.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// ---------------------------------------------------------------- constants
const WS_URL = 'ws://localhost:8090';
const METERS_PER_DEG = 111000;
const TRACK_MAX = 500;          // vessel positions kept in the track line
const BATHY_MAX = 200000;       // preallocated bathymetry point capacity
const VESSEL_COLOR = 0xff7700;
const QUALITY_CLASS = { good: 'q-good', degraded: 'q-fair', fair: 'q-fair', bad: 'q-bad' };

// ---------------------------------------------------------------- DOM refs
const $ = (id) => document.getElementById(id);
const el = {
  container: $('scene-container'),
  vesselId: $('vessel-id'),
  statusDot: $('status-dot'),
  connStatus: $('conn-status'),
  depthBig: $('depth-big'),
  depthQuality: $('depth-quality'),
  channelGrid: $('channel-grid'),
  voxelCount: $('voxel-count'),
  sessionTime: $('session-time'),
  position: $('position'),
  // Alert elements
  alertsList: $('alerts-list'),
  alertsHistoryList: $('alerts-history-list'),
  clearAllAlerts: $('clear-all-alerts'),
  actionDialog: $('action-dialog'),
  dialogTitle: $('dialog-title'),
  dialogMessage: $('dialog-message'),
  dialogPayload: $('dialog-payload'),
  dialogConfirm: $('dialog-confirm'),
  dialogCancel: $('dialog-cancel'),
};

// ---------------------------------------------------------------- renderer / scene
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
el.container.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x87b5d9);                    // sky blue
scene.fog = new THREE.Fog(0x87b5d9, 400, 2500);

const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 6000);
camera.position.set(60, 80, 120);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.maxPolarAngle = Math.PI * 0.495;                        // stay above the seabed plane
controls.autoRotateSpeed = 0.8;

// touch (iPad): one finger rotates, pinch zooms — OrbitControls defaults,
// stated explicitly so they survive future library updates.
controls.touches = { ONE: THREE.TOUCH.ROTATE, TWO: THREE.TOUCH.DOLLY_PAN };

// auto-rotate after 5 s without input
let lastInputAt = performance.now();
const noteInput = () => { lastInputAt = performance.now(); };
controls.addEventListener('start', noteInput);
renderer.domElement.addEventListener('pointerdown', noteInput);
renderer.domElement.addEventListener('wheel', noteInput, { passive: true });
renderer.domElement.addEventListener('touchstart', noteInput, { passive: true });

// ---------------------------------------------------------------- lighting
scene.add(new THREE.HemisphereLight(0xcfe8ff, 0x1a2f45, 1.1));
const sun = new THREE.DirectionalLight(0xfff2dd, 1.6);
sun.position.set(200, 400, 150);
scene.add(sun);

// ---------------------------------------------------------------- water surface
const water = new THREE.Mesh(
  new THREE.PlaneGeometry(1000, 1000),
  new THREE.MeshPhongMaterial({
    color: 0x1c5f8a, transparent: true, opacity: 0.55,
    shininess: 90, side: THREE.DoubleSide,
  })
);
water.rotation.x = -Math.PI / 2;   // horizontal at y = 0
scene.add(water);

// ---------------------------------------------------------------- vessel
const vessel = new THREE.Group();

const hullGeo = new THREE.ConeGeometry(2.2, 8, 12);              // 8 m hull
hullGeo.rotateX(Math.PI / 2);                                    // point bow toward +z (north)
const hullMat = new THREE.MeshPhongMaterial({ color: VESSEL_COLOR, shininess: 60 });
vessel.add(new THREE.Mesh(hullGeo, hullMat));

const cabin = new THREE.Mesh(
  new THREE.BoxGeometry(2.6, 2.2, 3),                            // 3 m cabin
  new THREE.MeshPhongMaterial({ color: 0xe8e2d4 })
);
cabin.position.set(0, 1.4, -1.2);
vessel.add(cabin);
scene.add(vessel);

// ---------------------------------------------------------------- track line
const trackPositions = new Float32Array(TRACK_MAX * 3);
const trackGeo = new THREE.BufferGeometry();
trackGeo.setAttribute('position', new THREE.BufferAttribute(trackPositions, 3));
trackGeo.setDrawRange(0, 0);
const track = new THREE.Line(
  trackGeo,
  new THREE.LineBasicMaterial({ color: VESSEL_COLOR, transparent: true, opacity: 0.9 })
);
track.frustumCulled = false;
scene.add(track);
let trackCount = 0;

function pushTrackPoint(x, y, z) {
  if (trackCount === TRACK_MAX) {
    trackPositions.copyWithin(0, 3);                             // drop oldest
    trackCount = TRACK_MAX - 1;
  }
  trackPositions.set([x, y, z], trackCount * 3);
  trackCount++;
  trackGeo.attributes.position.needsUpdate = true;
  trackGeo.setDrawRange(0, trackCount);
}

// ---------------------------------------------------------------- bathymetry point cloud
const bathyPos = new Float32Array(BATHY_MAX * 3);
const bathyCol = new Float32Array(BATHY_MAX * 4);                // RGBA: alpha = confidence
const bathyGeo = new THREE.BufferGeometry();
bathyGeo.setAttribute('position', new THREE.BufferAttribute(bathyPos, 3));
bathyGeo.setAttribute('color', new THREE.BufferAttribute(bathyCol, 4));
bathyGeo.setDrawRange(0, 0);
const bathy = new THREE.Points(bathyGeo, new THREE.PointsMaterial({
  size: 3, vertexColors: true, transparent: true,
  sizeAttenuation: true, depthWrite: false,
}));
bathy.frustumCulled = false;
scene.add(bathy);
let bathyCount = 0;

const C_SHALLOW = new THREE.Color(0xff9a3c);   // < 30 m  warm orange
const C_MID     = new THREE.Color(0x3fd68c);   // 30–80 m green
const C_DEEP    = new THREE.Color(0x2f6fd0);   // > 80 m  blue

// ---------------------------------------------------------------- Alert system
const activeAlerts = new Map();  // alert_id -> alert data
const alertHistory = [];
const MAX_HISTORY = 20;
let alertIdCounter = 0;

// 3D Alert indicators
const alertMarkers = new Map();  // alert_id -> THREE.Group
const alertLabels = new Map();   // alert_id -> DOM element

function getPriorityLevel(priority) {
  if (priority >= 0.9) return 'critical';
  if (priority >= 0.7) return 'high';
  if (priority >= 0.4) return 'medium';
  return 'low';
}

function getPriorityColor(priority) {
  if (priority >= 0.9) return 0xe04b4b;  // red
  if (priority >= 0.7) return 0xe0b13c;  // yellow
  if (priority >= 0.4) return 0x35e08a; // green
  return 0x6f93b3;                       // blue
}

function formatTimestamp(ns) {
  const s = Math.floor(ns / 1e9);
  const date = new Date(s * 1000);
  return date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function addAlert(action) {
  const alertId = `alert-${++alertIdCounter}`;
  const alert = {
    id: alertId,
    action: action.action,
    payload: action.payload || {},
    reason: action.reason || '',
    priority: action.priority || 0.5,
    rule_id: action.rule_id || 'unknown',
    timestamp_ns: action.timestamp_ns || BigInt(Date.now() * 1e6),
    created_at: Date.now(),
  };

  activeAlerts.set(alertId, alert);
  renderAlert(alert);
  add3DAlertIndicator(alert);

  // Also add to history
  addToHistory(alert);
}

function renderAlert(alert) {
  const item = document.createElement('div');
  item.className = `alert-item priority-${getPriorityLevel(alert.priority)}`;
  item.id = alert.id;
  item.style.setProperty('--priority-percent', `${alert.priority * 100}%`);

  const severity = alert.payload?.severity || 'WARNING';
  const code = alert.payload?.code || 'ALERT';
  const message = alert.payload?.message || alert.reason || alert.action;

  item.innerHTML = `
    <button class="btn-dismiss-alert" onclick="dismissAlert('${alert.id}')">✕</button>
    <div class="alert-header">
      <span class="alert-code">${code}</span>
      <span class="alert-time">${formatTimestamp(alert.timestamp_ns)}</span>
    </div>
    <div class="alert-message">${message}</div>
    <div class="alert-reason">${alert.reason}</div>
    <div class="alert-priority-bar"></div>
  `;

  el.alertsList.appendChild(item);
}

function dismissAlert(alertId) {
  const alert = activeAlerts.get(alertId);
  if (!alert) return;

  // Remove from UI
  const item = document.getElementById(alertId);
  if (item) item.remove();

  // Remove 3D indicator
  remove3DAlertIndicator(alertId);

  // Remove from active alerts
  activeAlerts.delete(alertId);
}

function clearAllAlerts() {
  for (const alertId of activeAlerts.keys()) {
    dismissAlert(alertId);
  }
}

function addToHistory(alert) {
  alertHistory.unshift(alert);
  if (alertHistory.length > MAX_HISTORY) {
    alertHistory.pop();
  }
  renderHistory();
}

function renderHistory() {
  el.alertsHistoryList.innerHTML = '';

  if (alertHistory.length === 0) {
    el.alertsHistoryList.innerHTML = '<div class="empty-state">No alert history</div>';
    return;
  }

  for (const alert of alertHistory) {
    const item = document.createElement('div');
    item.className = `history-item ${getPriorityLevel(alert.priority)}`;
    const code = alert.payload?.code || 'ALERT';
    item.textContent = `${formatTimestamp(alert.timestamp_ns)} - ${code}`;
    el.alertsHistoryList.appendChild(item);
  }
}

// ---------------------------------------------------------------- 3D Alert Indicators
function add3DAlertIndicator(alert) {
  const priority = alert.priority || 0.5;
  const isCritical = priority >= 0.9;

  // Create a marker group at vessel position
  const marker = new THREE.Group();
  marker.position.copy(vessel.position);
  marker.position.y += 5; // Float above vessel

  // Create a glowing sphere for critical alerts
  if (isCritical) {
    const sphereGeo = new THREE.SphereGeometry(1.5, 16, 16);
    const sphereMat = new THREE.MeshBasicMaterial({
      color: getPriorityColor(priority),
      transparent: true,
      opacity: 0.6,
    });
    const sphere = new THREE.Mesh(sphereGeo, sphereMat);
    marker.add(sphere);

    // Add pulsing animation data
    marker.userData.pulse = true;
    marker.userData.pulsePhase = 0;
  }

  // Create a ring for non-critical alerts
  if (!isCritical) {
    const ringGeo = new THREE.RingGeometry(1.8, 2.2, 32);
    const ringMat = new THREE.MeshBasicMaterial({
      color: getPriorityColor(priority),
      transparent: true,
      opacity: 0.8,
      side: THREE.DoubleSide,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = -Math.PI / 2;
    marker.add(ring);
  }

  scene.add(marker);
  alertMarkers.set(alert.id, marker);

  // Create floating label
  if (isCritical) {
    const label = document.createElement('div');
    label.className = 'alert-marker';
    label.innerHTML = `<div class="alert-label">${alert.payload?.code || 'ALERT'}</div>`;
    el.container.appendChild(label);
    alertLabels.set(alert.id, label);
  }
}

function remove3DAlertIndicator(alertId) {
  const marker = alertMarkers.get(alertId);
  if (marker) {
    scene.remove(marker);
    alertMarkers.delete(alertId);
  }

  const label = alertLabels.get(alertId);
  if (label) {
    label.remove();
    alertLabels.delete(alertId);
  }
}

function updateAlertIndicators() {
  // Move markers with vessel
  for (const [alertId, marker] of alertMarkers) {
    marker.position.x = vessel.position.x;
    marker.position.z = vessel.position.z;
    marker.position.y = vessel.position.y + 5;

    // Pulsing animation for critical alerts
    if (marker.userData.pulse) {
      marker.userData.pulsePhase += 0.05;
      const scale = 1 + Math.sin(marker.userData.pulsePhase) * 0.3;
      marker.scale.set(scale, scale, scale);
    }
  }

  // Update label positions
  for (const [alertId, label] of alertLabels) {
    const marker = alertMarkers.get(alertId);
    if (!marker) continue;

    // Project 3D position to 2D screen
    const pos = marker.position.clone();
    pos.y += 3;
    pos.project(camera);

    const x = (pos.x * 0.5 + 0.5) * el.container.clientWidth;
    const y = (pos.y * -0.5 + 0.5) * el.container.clientHeight;

    // Hide if behind camera or too far
    if (pos.z > 1) {
      label.style.display = 'none';
    } else {
      label.style.display = 'block';
      label.style.transform = `translate(${x}px, ${y}px)`;
    }
  }
}

// ---------------------------------------------------------------- Action handling
let pendingAction = null;

function showActionDialog(actionName, message = 'Are you sure?', payload = null) {
  pendingAction = { action: actionName, payload };

  el.dialogTitle.textContent = `Confirm ${actionName.replace(/_/g, ' ').toUpperCase()}`;
  el.dialogMessage.textContent = message;
  el.dialogPayload.textContent = payload ? JSON.stringify(payload, null, 2) : '';
  el.actionDialog.classList.remove('hidden');
}

function hideActionDialog() {
  el.actionDialog.classList.add('hidden');
  pendingAction = null;
}

function executeAction(action, payload = {}) {
  const actionMsg = {
    type: 'action_request',
    data: {
      action,
      payload,
      timestamp_ns: BigInt(Date.now() * 1e6),
    },
  };

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(actionMsg));
    console.log('[action] Sent:', actionMsg);
  } else {
    console.warn('[action] Cannot send action - WebSocket not connected');
  }
}

function addBathyCell(x, depth, z, confidence) {
  if (bathyCount >= BATHY_MAX) return;
  const c = depth < 30 ? C_SHALLOW : depth <= 80 ? C_MID : C_DEEP;
  bathyPos.set([x, -depth, z], bathyCount * 3);
  bathyCol.set([c.r, c.g, c.b, Math.min(1, Math.max(0.1, confidence))], bathyCount * 4);
  bathyCount++;
}

// ---------------------------------------------------------------- ENU projection
// Local tangent frame anchored at the first received fix.
//   x = (lon - lon0) * 111000 * cos(lat0)   (east)
//   z = (lat - lat0) * 111000               (north)
//   y = -depth                              (up)
let origin = null;   // { lat0, lon0, cosLat0 }

function toENU(lat, lon) {
  return {
    x: (lon - origin.lon0) * METERS_PER_DEG * origin.cosLat0,
    z: (lat - origin.lat0) * METERS_PER_DEG,
  };
}

// ---------------------------------------------------------------- sidebar
const sessionStart = Date.now();
const channelEls = new Map();    // channel name -> value element

function pulse(node) {
  node.classList.remove('pulse');
  void node.offsetWidth;         // restart the CSS animation
  node.classList.add('pulse');
}

function fmt(value, digits = 1) {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : String(value);
}

function updateSidebar(msg) {
  const { pose, channels, bathymetry } = msg;

  el.vesselId.textContent = msg.vessel_id || 'UNKNOWN VESSEL';

  // pose-derived channels
  setChannel('speed', pose.speed_kn, 'kn');
  setChannel('heading', pose.heading_deg, '°', 0);
  el.position.textContent = `${pose.lat.toFixed(5)}, ${pose.lon.toFixed(5)}`;

  // big depth readout, colored by quality
  const depth = channels?.depth_m;
  if (depth && typeof depth.value === 'number') {
    el.depthBig.textContent = fmt(depth.value);
    const q = (depth.quality || '').toLowerCase();
    el.depthBig.className = `depth-big ${QUALITY_CLASS[q] || 'q-none'}`;
    el.depthQuality.textContent = depth.quality ? `quality: ${depth.quality}` : '';
    pulse(el.depthBig);
  }

  // remaining telemetry channels
  if (channels) {
    for (const [name, ch] of Object.entries(channels)) {
      if (name === 'depth_m') continue;                          // shown big above
      const unit = name.match(/_([a-z]+)$/i)?.[1] || '';
      setChannel(name.replace(/_[a-z]+$/i, '').replace(/_/g, ' '), ch.value, unit);
    }
  }

  if (bathymetry && typeof bathymetry.voxel_count === 'number') {
    el.voxelCount.textContent = bathymetry.voxel_count.toLocaleString();
    pulse(el.voxelCount);
  }
}

function setChannel(name, value, unit, digits = 1) {
  let node = channelEls.get(name);
  if (!node) {
    const box = document.createElement('div');
    box.className = 'channel';
    box.innerHTML = `<div class="ch-name"></div><div class="ch-value"></div>`;
    box.querySelector('.ch-name').textContent = name;
    el.channelGrid.appendChild(box);
    node = box.querySelector('.ch-value');
    channelEls.set(name, node);
  }
  node.innerHTML = `${fmt(value, digits)} <span class="ch-unit">${unit}</span>`;
  pulse(node);
}

function fmtDuration(ms) {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = s % 60;
  const mm = String(m).padStart(2, '0');
  const pad = String(ss).padStart(2, '0');
  return h > 0 ? `${h}:${mm}:${pad}` : `${mm}:${pad}`;
}

setInterval(() => { el.sessionTime.textContent = fmtDuration(Date.now() - sessionStart); }, 1000);

// ---------------------------------------------------------------- snapshot handling
let cameraLocked = false;

// ---------------------------------------------------------------- Action event handler
function handleActionEvent(action) {
  console.log('[action] Received:', action);

  if (action.action === 'raise_alert') {
    addAlert(action);
  } else if (action.action === 'clear_alerts') {
    clearAllAlerts();
  } else {
    // For other actions, show a notification
    console.log('[action] Non-alert action:', action);
  }
}

// ---------------------------------------------------------------- Event listeners
el.clearAllAlerts?.addEventListener('click', clearAllAlerts);

el.dialogConfirm?.addEventListener('click', () => {
  if (pendingAction) {
    executeAction(pendingAction.action, pendingAction.payload || {});
    hideActionDialog();
  }
});

el.dialogCancel?.addEventListener('click', hideActionDialog);

// Quick action buttons
document.querySelectorAll('.action-btn').forEach(btn => {
  btn.addEventListener('click', (e) => {
    const action = e.target.dataset.action;
    if (!action) return;

    // Show confirmation dialog
    const messages = {
      'haul_gear': 'Haul gear now? This will retrieve all deployed gear.',
      'anchor_drop': 'Drop anchor now? This will stop the vessel.',
      'clear_alerts': 'Clear all active alerts?',
    };

    showActionDialog(action, messages[action] || 'Execute this action?');
  });
});

// Make functions globally available for onclick handlers
window.dismissAlert = dismissAlert;
window.clearAllAlerts = clearAllAlerts;

function onSnapshot(msg) {
  const { pose, bathymetry } = msg;
  if (!pose) return;

  if (!origin) {
    origin = {
      lat0: pose.lat,
      lon0: pose.lon,
      cosLat0: Math.cos(THREE.MathUtils.degToRad(pose.lat)),
    };
  }

  const p = toENU(pose.lat, pose.lon);
  vessel.position.set(p.x, 0, p.z);
  vessel.rotation.y = THREE.MathUtils.degToRad(pose.heading_deg || 0);
  pushTrackPoint(p.x, 0, p.z);

  if (!cameraLocked) {
    controls.target.set(p.x, 0, p.z);
    camera.position.set(p.x + 60, 80, p.z + 120);
    cameraLocked = true;
  }

  if (bathymetry?.cells) {
    for (const cell of bathymetry.cells) {
      const [lat, lon, depth, conf] = cell;
      const bp = toENU(lat, lon);
      addBathyCell(bp.x, depth, bp.z, conf);
    }
    bathyGeo.attributes.position.needsUpdate = true;
    bathyGeo.attributes.color.needsUpdate = true;
    bathyGeo.setDrawRange(0, bathyCount);
  }

  updateSidebar(msg);
}

// ---------------------------------------------------------------- WebSocket
let ws = null;
let retryDelay = 250;            // exponential backoff, capped at 5 s

function setConnState(state, text) {
  el.statusDot.className = `dot dot-${state}`;
  el.connStatus.textContent = text;
}

function connect() {
  setConnState('connecting', `connecting to ${WS_URL}…`);
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    retryDelay = 250;
    setConnState('connected', 'live — twin core connected');
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);

      // Handle action events from WatcherRegistry
      if (msg.type === 'action') {
        handleActionEvent(msg.data);
        return;
      }

      // Handle regular snapshots
      onSnapshot(msg);
    } catch (err) {
      console.warn('bad message ignored:', err);
    }
  };

  ws.onclose = () => {
    setConnState('disconnected', `disconnected — retrying in ${(retryDelay / 1000).toFixed(1)} s`);
    setTimeout(connect, retryDelay);
    retryDelay = Math.min(retryDelay * 2, 5000);
  };

  ws.onerror = () => ws.close();
}

connect();

// ---------------------------------------------------------------- resize / loop
function resize() {
  const w = el.container.clientWidth;
  const h = el.container.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
resize();

renderer.setAnimationLoop(() => {
  controls.autoRotate = performance.now() - lastInputAt > 5000;
  controls.update();
  updateAlertIndicators();
  renderer.render(scene, camera);
});
