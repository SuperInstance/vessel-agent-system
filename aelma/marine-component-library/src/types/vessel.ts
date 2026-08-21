/**
 * VesselStateSnapshot - Complete vessel state from twin core
 * Represents the digital twin state at a specific timestamp
 */
export interface VesselStateSnapshot {
  vessel_id?: string;
  timestamp_ns?: bigint;
  pose: VesselPose;
  channels?: Record<string, TelemetryChannel>;
  bathymetry?: BathymetryData;
  actions?: ActionEvent[];
}

/**
 * VesselPose - Position and orientation
 */
export interface VesselPose {
  lat: number;
  lon: number;
  heading_deg: number;
  speed_kn: number;
  depth_m?: number;
  alt_m?: number;
}

/**
 * TelemetryChannel - Generic sensor data channel
 */
export interface TelemetryChannel {
  value: number | string | boolean;
  quality?: 'good' | 'degraded' | 'fair' | 'bad';
  unit?: string;
  timestamp_ns?: bigint;
}

/**
 * BathymetryData - Depth mapping data
 */
export interface BathymetryData {
  voxel_count: number;
  cells?: BathymetryCell[];
  resolution_m?: number;
  extent_km?: number;
}

/**
 * BathymetryCell - Single depth measurement point
 */
export interface BathymetryCell {
  lat: number;
  lon: number;
  depth: number;
  confidence: number;
}

/**
 * ActionEvent - Action or alert from vessel system
 */
export interface ActionEvent {
  action: string;
  payload?: Record<string, unknown>;
  reason?: string;
  priority: number; // 0.0 - 1.0
  rule_id?: string;
  timestamp_ns: bigint;
}

/**
 * Alert - Specific alert with display info
 */
export interface Alert {
  id: string;
  action: string;
  payload: AlertPayload;
  reason: string;
  priority: number;
  rule_id: string;
  timestamp_ns: bigint;
  created_at: number;
  dismissed?: boolean;
}

/**
 * AlertPayload - Alert-specific data
 */
export interface AlertPayload {
  severity: 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
  code: string;
  message: string;
  source?: string;
  details?: Record<string, unknown>;
}

/**
 * AlertSeverity - Computed severity from priority
 */
export type AlertSeverity = 'critical' | 'high' | 'medium' | 'low';

/**
 * VesselTrack - Historical position track
 */
export interface VesselTrack {
  points: TrackPoint[];
  max_points: number;
}

/**
 * TrackPoint - Single track position
 */
export interface TrackPoint {
  lat: number;
  lon: number;
  timestamp_ns: bigint;
  heading_deg?: number;
  speed_kn?: number;
}

/**
 * ENUCoordinate - Local tangent plane coordinates
 */
export interface ENUCoordinate {
  x: number; // East
  y: number; // Up (negative depth)
  z: number; // North
}

/**
 * ENUCoords - Local coordinate reference frame
 */
export interface ENUOrigin {
  lat0: number;
  lon0: number;
  cosLat0: number;
}

/**
 * VesselSceneConfig - 3D scene configuration
 */
export interface VesselSceneConfig {
  track_max?: number;
  bathy_max?: number;
  water_opacity?: number;
  fog_distance?: [number, number];
  auto_rotate_delay?: number;
  vessel_color?: number;
}

/**
 * BathymetryColor - Depth coloring configuration
 */
export interface BathymetryColor {
  shallow_depth: number; // meters
  deep_depth: number; // meters
  shallow_color: number; // hex
  mid_color: number; // hex
  deep_color: number; // hex
}

/**
 * TelemetryPanelProps - Main telemetry display props
 */
export interface TelemetryPanelProps {
  vesselState: VesselStateSnapshot | null;
  className?: string;
  showChannels?: string[];
  compact?: boolean;
  onUpdate?: (state: VesselStateSnapshot) => void;
}

/**
 * AlertSystemProps - Alert display system props
 */
export interface AlertSystemProps {
  alerts: Alert[];
  onDismiss?: (alertId: string) => void;
  onClearAll?: () => void;
  maxHistory?: number;
  showHistory?: boolean;
  className?: string;
}

/**
 * VesselSceneProps - 3D vessel scene props
 */
export interface VesselSceneProps {
  vesselState: VesselStateSnapshot | null;
  config?: VesselSceneConfig;
  className?: string;
  onCameraChange?: (position: ENUCoordinate, target: ENUCoordinate) => void;
  onAlertClick?: (alert: Alert) => void;
  alerts?: Alert[];
}

/**
 * TimelineTrackProps - DAW-style timeline props
 */
export interface TimelineTrackProps {
  events: TimelineEvent[];
  duration: number; // seconds
  currentTime: number;
  onSeek?: (time: number) => void;
  zoom: number;
  onZoom?: (zoom: number) => void;
  className?: string;
}

/**
 * TimelineEvent - Event on timeline
 */
export interface TimelineEvent {
  id: string;
  type: 'alert' | 'action' | 'state_change' | 'waypoint';
  timestamp: number; // seconds from start
  duration?: number;
  label: string;
  color: string;
  metadata?: Record<string, unknown>;
}

/**
 * BathymetryViewerProps - Depth map visualization props
 */
export interface BathymetryViewerProps {
  data: BathymetryData;
  colorScheme?: BathymetryColor;
  pointSize?: number;
  showColorScale?: boolean;
  className?: string;
  onPointClick?: (cell: BathymetryCell) => void;
}

/**
 * NMEAStreamProps - Real-time NMEA display props
 */
export interface NMEAStreamProps {
  sentences: NMEASentence[];
  maxVisible?: number;
  filterTypes?: string[];
  highlightRules?: RegExp[];
  className?: string;
  onSentenceClick?: (sentence: NMEASentence) => void;
}

/**
 * NMEASentence - Parsed NMEA sentence
 */
export interface NMEASentence {
  type: string;
  raw: string;
  timestamp_ns: bigint;
  parsed?: Record<string, unknown>;
  valid: boolean;
  checksum_valid?: boolean;
}

/**
 * WebSocketMessage - Message from twin core
 */
export interface WebSocketMessage {
  type?: 'snapshot' | 'action';
  data?: VesselStateSnapshot | ActionEvent;
}
