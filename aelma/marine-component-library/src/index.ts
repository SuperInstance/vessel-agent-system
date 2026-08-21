/**
 * @aelma/marine-components
 * React component library for marine digital twin interfaces
 */

// Components
export { TelemetryPanel } from './components/TelemetryPanel';
export { AlertSystem } from './components/AlertSystem';
export { getPriorityLevel, getPriorityColor } from './components/AlertSystem';
export { VesselScene } from './components/VesselScene';
export { TimelineTrack } from './components/TimelineTrack';
export { BathymetryViewer } from './components/BathymetryViewer';
export { NMEAStream } from './components/NMEAStream';

// Hooks
export {
  useWebSocket,
  useVesselState,
  useActionEvents,
  useOfflineSync,
} from './hooks/useWebSocket';

// Types
export type {
  // Vessel types
  VesselStateSnapshot,
  VesselPose,
  TelemetryChannel,
  BathymetryData,
  BathymetryCell,
  ActionEvent,
  Alert,
  AlertPayload,
  AlertSeverity,
  VesselTrack,
  TrackPoint,
  ENUCoordinate,
  ENUOrigin,
  VesselSceneConfig,
  BathymetryColor,
  TimelineEvent,
  NMEASentence,
  WebSocketMessage,

  // Component prop types
  TelemetryPanelProps,
  AlertSystemProps,
  VesselSceneProps,
  TimelineTrackProps,
  BathymetryViewerProps,
  NMEAStreamProps,
} from './types/vessel';

export type {
  MarineTheme,
  MarineColorPalette,
  MarineTypography,
  MarineSpacing,
  MarineTouchTargets,
  MarineBorders,
  MarineShadows,
  MarineAnimation,
} from './types/theme';

// Theme utilities
export { dayTheme, nightTheme, getTheme } from './types/theme';

// CSS (for consumers who want to import styles)
export './components/TelemetryPanel.css';
export './components/AlertSystem.css';
export './components/VesselScene.css';
export './components/TimelineTrack.css';
export './components/BathymetryViewer.css';
export './components/NMEAStream.css';
