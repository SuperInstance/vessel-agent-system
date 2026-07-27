/**
 * AELMA Viewer - Main Application Module
 *
 * Connects to the AELMA digital twin core via WebSocket and renders
 * a live 3D vessel + progressive bathymetry using Three.js.
 *
 * Coordinate System: ENU (East-North-Up)
 *   x = (lon - lon0) * 111000 * cos(lat0_rad)   [east]
 *   z = (lat - lat0) * 111000                    [north]
 *   y = -depth                                    [up]
 */

import * as THREE from 'https://unpkg.com/three@0.160.0/build/three.module.js';
import { OrbitControls } from 'https://unpkg.com/three@0.160.0/examples/jsm/controls/OrbitControls.js';

// ============================================================
// Configuration
// ============================================================

const WS_URL = 'ws://localhost:8090';
const MAX_BACKOFF_MS = 5000;
const INITIAL_BACKOFF_MS = 500;
const TRACK_MAX_POINTS = 500;
const AUTO_ROTATE_DELAY_MS = 5000;
const EARTH_RADIUS_M = 111000;

const VESSEL_COLOR = 0xff7700;
const HULL_HEIGHT = 8;
const CABIN_SIZE = 3;
const WATER_SIZE = 1000;

// ============================================================
// State
// ============================================================

const state = {
  ws: null,
  connected: false,
  backoff: INITIAL_BACKOFF_MS,
  reconnectTimer: null,
  originSet: false,
  originLat: 0,
  originLon: 0,
  originLatRad: 0,
  trackPositions: [],
  sessionStart: null,
  lastInputTime: Date.now(),
  depthQuality: 'good',
};

// ============================================================
// DOM References
// ============================================================

const dom = {
  statusDot: document.getElementById('status-dot'),
  statusText: document.getElementById('status-text'),
  depthValue: document.getElementById('depth-value'),
  channelGrid: document.getElementById('channel-grid'),
  voxelCount: document.getElementById('voxel-count'),
  speedValue: document.getElementById('speed-value'),
  headingValue: document.getElementById('heading-value'),
  sessionDuration: document.getElementById('session-duration'),
  positionValue: document.getElementById('position-value'),
  reconnectOverlay: document.getElementById('reconnect-overlay'),
  reconnectText: document.getElementById('reconnect-text'),
  sceneContainer: document.getElementById('scene-container'),
  vesselId: document.querySelector('.vessel-id'),
};

// ============================================================
// Three.js Scene Setup
// ============================================================

let scene, camera, renderer, controls;
let vesselGroup, bathymetryMesh, waterMesh, trackLine, trackGeometry;
let bathymetryPositions, bathymetryColors;

function initScene() {
  // Scene
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x87ceeb);
  scene.fog = new THREE.Fog(0x87ceeb, 300, 900);

  // Camera
  const aspect = dom.sceneContainer.clientWidth / dom.sceneContainer.clientHeight;
  camera = new THREE.PerspectiveCamera(55, aspect, 0.1, 2000);
  camera.position.set(50, 60, 80);
  camera.lookAt(0, 0, 0);

  // Renderer
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setSize(dom.sceneContainer.clientWidth, dom.sceneContainer.clientHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  dom.sceneContainer.appendChild(renderer.domElement);

  // Controls
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.minDistance = 10;
  controls.maxDistance = 500;
  controls.maxPolarAngle = Math.PI / 2 - 0.05;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.5;

  // Lighting
  const hemiLight = new THREE.HemisphereLight(0x87ceeb, 0x0a1628, 0.6);
  scene.add(hemiLight);

  const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
  dirLight.position.set(50, 100, 30);
  scene.add(dirLight);

  // Water surface
  createWaterSurface();

  // Vessel
  createVessel();

  // Track line
  createTrackLine();

  // Bathymetry point cloud (pre-allocated)
  createBathymetryCloud();

  // Resize handler
  window.addEventListener('resize', onResize);

  // Input detection for auto-rotate
  detectInput();

  // Start render loop
  animate();
}

function createWaterSurface() {
  const geometry = new THREE.PlaneGeometry(WATER_SIZE, WATER_SIZE, 1, 1);
  geometry.rotateX(-Math.PI / 2);
  const material = new THREE.MeshBasicMaterial({
    color: 0x0066aa,
    transparent: true,
    opacity: 0.45,
    side: THREE.DoubleSide,
  });
  waterMesh = new THREE.Mesh(geometry, material);
  waterMesh.position.y = 0;
  scene.add(waterMesh);
}

function createVessel() {
  vesselGroup = new THREE.Group();

  // Hull - cone
  const hullGeo = new THREE.ConeGeometry(2, HULL_HEIGHT, 8);
  hullGeo.rotateX(Math.PI / 2);
  const hullMat = new THREE.MeshPhongMaterial({
    color: VESSEL_COLOR,
    shininess: 60,
    specular: 0x444444,
  });
  const hull = new THREE.Mesh(hullGeo, hullMat);
  hull.position.z = 0;
  vesselGroup.add(hull);

  // Cabin - box
  const cabinGeo = new THREE.BoxGeometry(CABIN_SIZE, CABIN_SIZE * 0.8, CABIN_SIZE);
  const cabinMat = new THREE.MeshPhongMaterial({
    color: 0xeeeeee,
    shininess: 30,
  });
  const cabin = new THREE.Mesh(cabinGeo, cabinMat);
  cabin.position.set(0, CABIN_SIZE * 0.4, -1);
  vesselGroup.add(cabin);

  // Mast - thin cylinder
  const mastGeo = new THREE.CylinderGeometry(0.15, 0.15, 4, 6);
  const mastMat = new THREE.MeshPhongMaterial({ color: 0x333333 });
  const mast = new THREE.Mesh(mastGeo, mastMat);
  mast.position.set(0, 3.5, -1);
  vesselGroup.add(mast);

  vesselGroup.position.set(0, 0, 0);
  scene.add(vesselGroup);
}

function createTrackLine() {
  trackGeometry = new THREE.BufferGeometry();
  const positions = new Float32Array(TRACK_MAX_POINTS * 3);
  trackGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  trackGeometry.setDrawRange(0, 0);

  const material = new THREE.LineBasicMaterial({
    color: VESSEL_COLOR,
    transparent: true,
    opacity: 0.7,
    linewidth: 2,
  });

  trackLine = new THREE.Line(trackGeometry, material);
  scene.add(trackLine);
}

function createBathymetryCloud() {
  const maxPoints = 50000;
  bathymetryPositions = new Float32Array(maxPoints * 3);
  bathymetryColors = new Float32Array(maxPoints * 4); // r,g,b,a

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(bathymetryPositions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(bathymetryColors, 4));
  geometry.setDrawRange(0, 0);

  const material = new THREE.PointsMaterial({
    size: 2.5,
    vertexColors: true,
    transparent: true,
    opacity: 0.85,
    sizeAttenuation: true,
  });

  bathymetryMesh = new THREE.Points(geometry, material);
  scene.add(bathymetryMesh);
}

// ============================================================
// ENU Coordinate Projection
// ============================================================

function setOrigin(lat, lon) {
  state.originLat = lat;
  state.originLon = lon;
  state.originLatRad = lat * Math.PI / 180;
  state.originSet = true;
}

function projectLatLon(lat, lon, depth = 0) {
  const x = (lon - state.originLon) * EARTH_RADIUS_M * Math.cos(state.originLatRad);
  const z = (lat - state.originLat) * EARTH_RADIUS_M;
  const y = -depth;
  return { x, y, z };
}

// ============================================================
// Depth Color Mapping
// ============================================================

function depthToColor(depth) {
  // shallow < 30m: warm orange
  // 30-80m: green
  // > 80m: blue
  if (depth < 30) {
    return { r: 1.0, g: 0.5, b: 0.1 };
  } else if (depth <= 80) {
    return { r: 0.1, g: 0.8, b: 0.3 };
  } else {
    return { r: 0.1, g: 0.4, b: 0.9 };
  }
}

// ============================================================
// Update Functions
// ============================================================

function updateVesselPose(pose) {
  if (!state.originSet) {
    setOrigin(pose.lat, pose.lon);
  }

  const pos = projectLatLon(pose.lat, pose.lon, 0);
  vesselGroup.position.set(pos.x, 0, pos.z);
  vesselGroup.rotation.y = -(pose.heading_deg * Math.PI / 180);

  // Update track
  state.trackPositions.push([pos.x, 0, pos.z]);
  if (state.trackPositions.length > TRACK_MAX_POINTS) {
    state.trackPositions.shift();
  }
  updateTrackGeometry();

  // Update sidebar
  dom.speedValue.textContent = pose.speed_kn.toFixed(1) + ' kn';
  dom.headingValue.textContent = pose.heading_deg.toFixed(1) + '\u00b0';
  dom.positionValue.textContent = pose.lat.toFixed(5) + ', ' + pose.lon.toFixed(5);
}

function updateTrackGeometry() {
  const positions = trackGeometry.attributes.position.array;
  const n = state.trackPositions.length;
  for (let i = 0; i < n; i++) {
    positions[i * 3] = state.trackPositions[i][0];
    positions[i * 3 + 1] = state.trackPositions[i][1];
    positions[i * 3 + 2] = state.trackPositions[i][2];
  }
  trackGeometry.setDrawRange(0, n);
  trackGeometry.attributes.position.needsUpdate = true;
}

function updateBathymetry(bathy) {
  if (!bathy || !bathy.cells || bathy.cells.length === 0) return;

  const cells = bathy.cells;
  let offset = bathymetryMesh.geometry.attributes.position.count;

  for (let i = 0; i < cells.length; i++) {
    const cell = cells[i];
    const lat = cell[0];
    const lon = cell[1];
    const depth = cell[2];
    const confidence = cell.length > 3 ? cell[3] : 1.0;

    const pos = projectLatLon(lat, lon, depth);

    const idx = (offset + i) * 3;
    if (idx + 2 < bathymetryPositions.length) {
      bathymetryPositions[idx] = pos.x;
      bathymetryPositions[idx + 1] = pos.y;
      bathymetryPositions[idx + 2] = pos.z;

      const color = depthToColor(depth);
      const cidx = (offset + i) * 4;
      bathymetryColors[cidx] = color.r;
      bathymetryColors[cidx + 1] = color.g;
      bathymetryColors[cidx + 2] = color.b;
      bathymetryColors[cidx + 3] = confidence;
    }
  }

  const totalPoints = offset + cells.length;
  bathymetryMesh.geometry.setDrawRange(0, totalPoints);
  bathymetryMesh.geometry.attributes.position.needsUpdate = true;
  bathymetryMesh.geometry.attributes.color.needsUpdate = true;

  // Update sidebar
  if (bathy.voxel_count !== undefined) {
    dom.voxelCount.textContent = bathy.voxel_count.toLocaleString();
    pulseElement(dom.voxelCount);
  }
}

function updateChannels(channels) {
  if (!channels) return;

  for (const [name, data] of Object.entries(channels)) {
    if (name === 'depth_m') {
      const depthVal = data.value;
      const quality = data.quality || 'good';
      state.depthQuality = quality;

      dom.depthValue.textContent = depthVal.toFixed(1);
      dom.depthValue.className = 'quality-' + quality;
      pulseElement(dom.depthValue);
      continue;
    }

    // Other channels go in the grid
    let card = document.getElementById('ch-' + name);
    if (!card) {
      card = createChannelCard(name);
    }

    const valEl = card.querySelector('.channel-value-num');
    if (valEl) {
      let displayVal = data.value;
      if (typeof displayVal === 'number') {
        displayVal = displayVal.toFixed(1);
      }
      valEl.textContent = displayVal;
      pulseElement(valEl);
    }
  }
}

function createChannelCard(name) {
  const card = document.createElement('div');
  card.className = 'channel-card';
  card.id = 'ch-' + name;

  const label = document.createElement('div');
  label.className = 'channel-name';
  label.textContent = formatChannelName(name);

  const valWrap = document.createElement('div');
  valWrap.className = 'channel-value';

  const val = document.createElement('span');
  val.className = 'channel-value-num';
  val.textContent = '--';

  const unit = document.createElement('span');
  unit.className = 'channel-unit';

  const unitMap = {
    sea_temp_c: '\u00b0C',
    salinity_psu: 'PSU',
    wind_speed_kn: 'kn',
    wind_dir_deg: '\u00b0',
    engine_rpm: 'RPM',
    fuel_pct: '%',
  };
  unit.textContent = unitMap[name] || '';

  valWrap.appendChild(val);
  valWrap.appendChild(unit);
  card.appendChild(label);
  card.appendChild(valWrap);
  dom.channelGrid.appendChild(card);

  return card;
}

function formatChannelName(name) {
  const labelMap = {
    sea_temp_c: 'Sea Temp',
    salinity_psu: 'Salinity',
    wind_speed_kn: 'Wind Speed',
    wind_dir_deg: 'Wind Dir',
    engine_rpm: 'Engine',
    fuel_pct: 'Fuel',
  };
  return labelMap[name] || name.replace(/_/g, ' ');
}

// ============================================================
// Pulse Animation Helper
// ============================================================

function pulseElement(el) {
  if (!el) return;
  el.classList.remove('pulse-update');
  void el.offsetWidth; // trigger reflow
  el.classList.add('pulse-update');
}

// ============================================================
// Session Duration Timer
// ============================================================

function updateSessionDuration() {
  if (!state.sessionStart) return;
  const elapsed = Date.now() - state.sessionStart;
  const mins = Math.floor(elapsed / 60000);
  const secs = Math.floor((elapsed % 60000) / 1000);
  dom.sessionDuration.textContent =
    String(mins).padStart(2, '0') + ':' + String(secs).padStart(2, '0');
}

setInterval(updateSessionDuration, 1000);

// ============================================================
// Auto-Rotate Management
// ============================================================

function detectInput() {
  const events = ['pointerdown', 'pointermove', 'wheel', 'touchstart', 'touchmove'];
  events.forEach(evt => {
    dom.sceneContainer.addEventListener(evt, () => {
      state.lastInputTime = Date.now();
      controls.autoRotate = false;
    }, { passive: true });
  });
}

function checkAutoRotate() {
  if (Date.now() - state.lastInputTime > AUTO_ROTATE_DELAY_MS) {
    controls.autoRotate = true;
  }
}

// ============================================================
// Resize Handler
// ============================================================

function onResize() {
  const w = dom.sceneContainer.clientWidth;
  const h = dom.sceneContainer.clientHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
}

// ============================================================
// Animation Loop
// ============================================================

function animate() {
  requestAnimationFrame(animate);
  checkAutoRotate();
  controls.update();

  // Subtle water shimmer
  if (waterMesh) {
    waterMesh.material.opacity = 0.42 + Math.sin(Date.now() * 0.0008) * 0.05;
  }

  renderer.render(scene, camera);
}

// ============================================================
// WebSocket Connection
// ============================================================

function connectWebSocket() {
  setStatus('connecting');

  try {
    state.ws = new WebSocket(WS_URL);
  } catch (e) {
    console.error('WebSocket creation failed:', e);
    scheduleReconnect();
    return;
  }

  state.ws.onopen = () => {
    console.log('WebSocket connected');
    state.connected = true;
    state.backoff = INITIAL_BACKOFF_MS;
    setStatus('connected');
    dom.reconnectOverlay.classList.add('hidden');

    if (!state.sessionStart) {
      state.sessionStart = Date.now();
    }
  };

  state.ws.onmessage = (event) => {
    try {
      const snapshot = JSON.parse(event.data);
      handleSnapshot(snapshot);
    } catch (e) {
      console.error('Failed to parse message:', e);
    }
  };

  state.ws.onerror = (error) => {
    console.error('WebSocket error:', error);
  };

  state.ws.onclose = () => {
    console.log('WebSocket closed');
    state.connected = false;
    setStatus('disconnected');
    dom.reconnectOverlay.classList.remove('hidden');
    scheduleReconnect();
  };
}

function scheduleReconnect() {
  if (state.reconnectTimer) {
    clearTimeout(state.reconnectTimer);
  }

  const waitMs = state.backoff;
  dom.reconnectText.textContent = 'Reconnecting in ' + (waitMs / 1000).toFixed(1) + 's...';

  state.reconnectTimer = setTimeout(() => {
    state.backoff = Math.min(state.backoff * 2, MAX_BACKOFF_MS);
    connectWebSocket();
  }, waitMs);
}

function setStatus(status) {
  dom.statusDot.className = 'status-dot ' + status;

  switch (status) {
    case 'connected':
      dom.statusText.textContent = 'Connected';
      break;
    case 'connecting':
      dom.statusText.textContent = 'Connecting...';
      break;
    case 'disconnected':
      dom.statusText.textContent = 'Disconnected';
      break;
  }
}

// ============================================================
// Snapshot Handler
// ============================================================

function handleSnapshot(snapshot) {
  // Update vessel ID in header
  if (snapshot.vessel_id && dom.vesselId) {
    dom.vesselId.textContent = snapshot.vessel_id;
  }

  // Update pose
  if (snapshot.pose) {
    updateVesselPose(snapshot.pose);
  }

  // Update channels
  if (snapshot.channels) {
    updateChannels(snapshot.channels);
  }

  // Update bathymetry
  if (snapshot.bathymetry) {
    updateBathymetry(snapshot.bathymetry);
  }
}

// ============================================================
// Initialize
// ============================================================

initScene();
connectWebSocket();

console.log('AELMA Viewer initialized. Connecting to', WS_URL);
