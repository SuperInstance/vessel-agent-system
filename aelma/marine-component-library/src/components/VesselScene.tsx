/**
 * VesselScene - 3D vessel visualization with Three.js
 * Renders vessel, track, bathymetry, and alert indicators
 * Touch-optimized controls for mobile/tablet operation
 */

import React, { useRef, useEffect, useCallback, useState, useMemo } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';
import {
  VesselStateSnapshot,
  ENUCoordinate,
  ENUOrigin,
  BathymetryCell,
  Alert,
  VesselSceneConfig,
  BathymetryColor,
} from '../types/vessel';
import { MarineTheme } from '../types/theme';
import './VesselScene.css';

export interface VesselSceneProps {
  vesselState: VesselStateSnapshot | null;
  alerts?: Alert[];
  config?: VesselSceneConfig;
  theme?: MarineTheme;
  className?: string;
  onCameraChange?: (position: ENUCoordinate, target: ENUCoordinate) => void;
  onAlertClick?: (alert: Alert) => void;
}

const DEFAULT_CONFIG: VesselSceneConfig = {
  track_max: 500,
  bathy_max: 200000,
  water_opacity: 0.55,
  fog_distance: [400, 2500],
  auto_rotate_delay: 5000,
  vessel_color: 0xff7700,
};

const DEFAULT_BATHY_COLORS: BathymetryColor = {
  shallow_depth: 30,
  deep_depth: 80,
  shallow_color: 0xff9a3c,
  mid_color: 0x3fd68c,
  deep_color: 0x2f6fd0,
};

const METERS_PER_DEG = 111000;

/**
 * VesselScene component
 */
export const VesselScene: React.FC<VesselSceneProps> = ({
  vesselState,
  alerts = [],
  config = {},
  theme,
  className = '',
  onCameraChange,
  onAlertClick,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);

  // Scene objects
  const vesselRef = useRef<THREE.Group | null>(null);
  const trackRef = useRef<THREE.Line | null>(null);
  const trackDataRef = useRef<Float32Array | null>(null);
  const trackCountRef = useRef(0);
  const bathymetryRef = useRef<THREE.Points | null>(null);
  const bathyPosRef = useRef<Float32Array | null>(null);
  const bathyColRef = useRef<Float32Array | null>(null);
  const bathyCountRef = useRef(0);

  // State
  const [origin, setOrigin] = useState<ENUOrigin | null>(null);
  const [cameraLocked, setCameraLocked] = useState(false);
  const [lastInputTime, setLastInputTime] = useState(Date.now());

  // Alert markers
  const alertMarkersRef = useRef<Map<string, THREE.Group>>(new Map());
  const alertLabelsRef = useRef<Map<string, HTMLDivElement>>(new Map());

  // Merge config with defaults
  const sceneConfig = useMemo(() => ({ ...DEFAULT_CONFIG, ...config }), [config]);

  /**
   * Convert lat/lon to ENU coordinates
   */
  const toENU = useCallback((lat: number, lon: number, origin: ENUOrigin): ENUCoordinate => {
    return {
      x: (lon - origin.lon0) * METERS_PER_DEG * origin.cosLat0,
      z: (lat - origin.lat0) * METERS_PER_DEG,
      y: 0,
    };
  }, []);

  /**
   * Initialize Three.js scene
   */
  useEffect(() => {
    if (!containerRef.current) return;

    // Scene
    const scene = new THREE.Scene();
    sceneRef.current = scene;

    // Set background based on theme
    if (theme?.mode === 'night') {
      scene.background = new THREE.Color(0x0a0a0a);
      scene.fog = new THREE.Fog(0x0a0a0a, ...sceneConfig.fog_distance!);
    } else {
      scene.background = new THREE.Color(0x87b5d9);
      scene.fog = new THREE.Fog(0x87b5d9, ...sceneConfig.fog_distance!);
    }

    // Camera
    const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 6000);
    camera.position.set(60, 80, 120);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    containerRef.current.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.maxPolarAngle = Math.PI * 0.495; // Stay above seabed
    controls.autoRotateSpeed = 0.8;

    // Touch controls
    controls.touches = {
      ONE: THREE.TOUCH.ROTATE,
      TWO: THREE.TOUCH.DOLLY_PAN,
    };

    // Input tracking for auto-rotate
    const noteInput = () => setLastInputTime(Date.now());
    controls.addEventListener('start', noteInput);
    renderer.domElement.addEventListener('pointerdown', noteInput);
    renderer.domElement.addEventListener('wheel', noteInput, { passive: true } as any);
    renderer.domElement.addEventListener('touchstart', noteInput, { passive: true } as any);

    controlsRef.current = controls;

    // Lighting
    scene.add(new THREE.HemisphereLight(0xcfe8ff, 0x1a2f45, 1.1));
    const sun = new THREE.DirectionalLight(0xfff2dd, 1.6);
    sun.position.set(200, 400, 150);
    scene.add(sun);

    // Water surface
    const water = new THREE.Mesh(
      new THREE.PlaneGeometry(1000, 1000),
      new THREE.MeshPhongMaterial({
        color: theme?.mode === 'night' ? 0x331111 : 0x1c5f8a,
        transparent: true,
        opacity: sceneConfig.water_opacity,
        shininess: 90,
        side: THREE.DoubleSide,
      })
    );
    water.rotation.x = -Math.PI / 2;
    water.userData.type = 'water';
    scene.add(water);

    // Create vessel
    createVessel(scene);

    // Create track line
    createTrackLine(scene);

    // Create bathymetry point cloud
    createBathymetry(scene);

    // Handle resize
    const handleResize = () => {
      if (!containerRef.current || !camera || !renderer) return;
      const w = containerRef.current.clientWidth;
      const h = containerRef.current.clientHeight;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };

    window.addEventListener('resize', handleResize);
    handleResize();

    // Animation loop
    let animationId: number;
    const animate = () => {
      animationId = requestAnimationFrame(animate);

      if (controls && camera) {
        // Auto-rotate after delay
        controls.autoRotate = Date.now() - lastInputTime > sceneConfig.auto_rotate_delay!;
        controls.update();

        // Update alert indicators
        updateAlertIndicators();

        renderer.render(scene, camera);
      }
    };
    animate();

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationId);

      if (containerRef.current && renderer.domElement) {
        containerRef.current.removeChild(renderer.domElement);
      }

      renderer.dispose();
      controls.dispose();

      // Clear alert labels
      alertLabelsRef.current.forEach(label => label.remove());
      alertLabelsRef.current.clear();
    };
  }, []); // Empty deps - run once on mount

  /**
   * Create vessel mesh
   */
  const createVessel = (scene: THREE.Scene) => {
    const vessel = new THREE.Group();

    // Hull
    const hullGeo = new THREE.ConeGeometry(2.2, 8, 12);
    hullGeo.rotateX(Math.PI / 2);
    const hullMat = new THREE.MeshPhongMaterial({
      color: sceneConfig.vessel_color,
      shininess: 60,
    });
    vessel.add(new THREE.Mesh(hullGeo, hullMat));

    // Cabin
    const cabin = new THREE.Mesh(
      new THREE.BoxGeometry(2.6, 2.2, 3),
      new THREE.MeshPhongMaterial({ color: 0xe8e2d4 })
    );
    cabin.position.set(0, 1.4, -1.2);
    vessel.add(cabin);

    scene.add(vessel);
    vesselRef.current = vessel;
  };

  /**
   * Create track line
   */
  const createTrackLine = (scene: THREE.Scene) => {
    const trackPositions = new Float32Array(sceneConfig.track_max! * 3);
    trackDataRef.current = trackPositions;

    const trackGeo = new THREE.BufferGeometry();
    trackGeo.setAttribute('position', new THREE.BufferAttribute(trackPositions, 3));
    trackGeo.setDrawRange(0, 0);

    const track = new THREE.Line(
      trackGeo,
      new THREE.LineBasicMaterial({
        color: sceneConfig.vessel_color,
        transparent: true,
        opacity: 0.9,
      })
    );
    track.frustumCulled = false;
    scene.add(track);
    trackRef.current = track;
  };

  /**
   * Create bathymetry point cloud
   */
  const createBathymetry = (scene: THREE.Scene) => {
    const bathyPos = new Float32Array(sceneConfig.bathy_max! * 3);
    const bathyCol = new Float32Array(sceneConfig.bathy_max! * 4);
    bathyPosRef.current = bathyPos;
    bathyColRef.current = bathyCol;

    const bathyGeo = new THREE.BufferGeometry();
    bathyGeo.setAttribute('position', new THREE.BufferAttribute(bathyPos, 3));
    bathyGeo.setAttribute('color', new THREE.BufferAttribute(bathyCol, 4));
    bathyGeo.setDrawRange(0, 0);

    const bathy = new THREE.Points(bathyGeo, new THREE.PointsMaterial({
      size: 3,
      vertexColors: true,
      transparent: true,
      sizeAttenuation: true,
      depthWrite: false,
    }));
    bathy.frustumCulled = false;
    scene.add(bathy);
    bathymetryRef.current = bathy;
  };

  /**
   * Add point to track
   */
  const pushTrackPoint = useCallback((x: number, y: number, z: number) => {
    if (!trackDataRef.current || !trackRef.current) return;

    const trackPositions = trackDataRef.current;
    const trackGeo = trackRef.current.geometry;

    if (trackCountRef.current === sceneConfig.track_max!) {
      trackPositions.copyWithin(0, 3);
      trackCountRef.current = sceneConfig.track_max! - 1;
    }

    trackPositions.set([x, y, z], trackCountRef.current * 3);
    trackCountRef.current++;

    trackGeo.attributes.position.needsUpdate = true;
    trackGeo.setDrawRange(0, trackCountRef.current);
  }, [sceneConfig.track_max]);

  /**
   * Add bathymetry cell
   */
  const addBathyCell = useCallback((x: number, depth: number, z: number, confidence: number) => {
    if (!bathyPosRef.current || !bathyColRef.current || !bathymetryRef.current) return;

    if (bathyCountRef.current >= sceneConfig.bathy_max!) return;

    const c = depth < DEFAULT_BATHY_COLORS.shallow_depth
      ? new THREE.Color(DEFAULT_BATHY_COLORS.shallow_color)
      : depth <= DEFAULT_BATHY_COLORS.deep_depth
        ? new THREE.Color(DEFAULT_BATHY_COLORS.mid_color)
        : new THREE.Color(DEFAULT_BATHY_COLORS.deep_color);

    bathyPosRef.current.set([x, -depth, z], bathyCountRef.current * 3);
    bathyColRef.current.set([c.r, c.g, c.b, Math.min(1, Math.max(0.1, confidence))], bathyCountRef.current * 4);
    bathyCountRef.current++;
  }, [sceneConfig.bathy_max]);

  /**
   * Update vessel position and data
   */
  useEffect(() => {
    if (!vesselState?.pose || !vesselRef.current || !trackRef.current) return;

    const { pose, bathymetry } = vesselState;

    // Initialize origin if needed
    if (!origin) {
      const newOrigin: ENUOrigin = {
        lat0: pose.lat,
        lon0: pose.lon,
        cosLat0: Math.cos(THREE.MathUtils.degToRad(pose.lat)),
      };
      setOrigin(newOrigin);
      return;
    }

    // Update vessel position
    const pos = toENU(pose.lat, pose.lon, origin);
    vesselRef.current.position.set(pos.x, 0, pos.z);
    vesselRef.current.rotation.y = THREE.MathUtils.degToRad(pose.heading_deg || 0);

    // Add to track
    pushTrackPoint(pos.x, 0, pos.z);

    // Update camera if not locked
    if (!cameraLocked && cameraRef.current && controlsRef.current) {
      controlsRef.current.target.set(pos.x, 0, pos.z);
      cameraRef.current.position.set(pos.x + 60, 80, pos.z + 120);
      setCameraLocked(true);
    }

    // Update bathymetry
    if (bathymetry?.cells) {
      for (const cell of bathymetry.cells) {
        const bp = toENU(cell.lat, cell.lon, origin);
        addBathyCell(bp.x, cell.depth, bp.z, cell.confidence);
      }

      if (bathymetryRef.current) {
        const geo = bathymetryRef.current.geometry;
        geo.attributes.position.needsUpdate = true;
        geo.attributes.color.needsUpdate = true;
        geo.setDrawRange(0, bathyCountRef.current);
      }
    }

    // Notify camera change
    if (onCameraChange && cameraRef.current) {
      const camPos = cameraRef.current.position;
      const target = controlsRef.current?.target;
      if (target) {
        onCameraChange(
          { x: camPos.x, y: camPos.y, z: camPos.z },
          { x: target.x, y: target.y, z: target.z }
        );
      }
    }
  }, [vesselState, origin, toENU, pushTrackPoint, addBathyCell, cameraLocked, onCameraChange]);

  /**
   * Update 3D alert indicators
   */
  const updateAlertIndicators = useCallback(() => {
    if (!vesselRef.current || !cameraRef.current) return;

    const vessel = vesselRef.current;
    const camera = cameraRef.current;

    // Move markers with vessel
    for (const [alertId, marker] of alertMarkersRef.current) {
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
    if (containerRef.current) {
      for (const [alertId, label] of alertLabelsRef.current) {
        const marker = alertMarkersRef.current.get(alertId);
        if (!marker) continue;

        const pos = marker.position.clone();
        pos.y += 3;
        pos.project(camera);

        const x = (pos.x * 0.5 + 0.5) * containerRef.current.clientWidth;
        const y = (pos.y * -0.5 + 0.5) * containerRef.current.clientHeight;

        if (pos.z > 1) {
          label.style.display = 'none';
        } else {
          label.style.display = 'block';
          label.style.transform = `translate(${x}px, ${y}px)`;
        }
      }
    }
  }, []);

  /**
   * Update alert markers when alerts change
   */
  useEffect(() => {
    if (!sceneRef.current || !vesselRef.current) return;

    const scene = sceneRef.current;
    const vessel = vesselRef.current;

    // Remove old markers
    for (const [alertId, marker] of alertMarkersRef.current) {
      scene.remove(marker);
    }
    alertMarkersRef.current.clear();

    // Remove old labels
    for (const [alertId, label] of alertLabelsRef.current) {
      label.remove();
    }
    alertLabelsRef.current.clear();

    // Add new markers for active alerts
    for (const alert of alerts) {
      if (alert.dismissed) continue;

      const priority = alert.priority || 0.5;
      const isCritical = priority >= 0.9;

      const marker = new THREE.Group();
      marker.position.copy(vessel.position);
      marker.position.y += 5;

      // Sphere for critical alerts
      if (isCritical) {
        const sphereGeo = new THREE.SphereGeometry(1.5, 16, 16);
        const sphereMat = new THREE.MeshBasicMaterial({
          color: getPriorityColor(priority),
          transparent: true,
          opacity: 0.6,
        });
        const sphere = new THREE.Mesh(sphereGeo, sphereMat);
        marker.add(sphere);

        marker.userData.pulse = true;
        marker.userData.pulsePhase = 0;
      }

      // Ring for non-critical alerts
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
      alertMarkersRef.current.set(alert.id, marker);

      // Add label for critical alerts
      if (isCritical && containerRef.current) {
        const label = document.createElement('div');
        label.className = 'alert-marker';
        label.innerHTML = `<div class="alert-label">${alert.payload.code}</div>`;
        containerRef.current.appendChild(label);
        alertLabelsRef.current.set(alert.id, label);
      }
    }
  }, [alerts]);

  return (
    <div
      ref={containerRef}
      className={`vessel-scene ${className}`}
      style={{
        width: '100%',
        height: '100%',
        touchAction: 'none',
      }}
    />
  );
};

/**
 * Get color for priority level
 */
function getPriorityColor(priority: number): number {
  if (priority >= 0.9) return 0xe04b4b; // red
  if (priority >= 0.7) return 0xe0b13c; // yellow
  if (priority >= 0.4) return 0x35e08a; // green
  return 0x6f93b3; // blue
}

export default VesselScene;
