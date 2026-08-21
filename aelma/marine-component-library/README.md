# @aelma/marine-components

A comprehensive React component library for marine digital twin interfaces with touch-optimized UX, real-time data handling, and TypeScript integration.

## Features

- **Marine-Specific Components**
  - `TelemetryPanel` - Depth, speed, heading, position display
  - `AlertSystem` - Severity-based alert grouping and history
  - `VesselScene` - Three.js 3D vessel visualization
  - `TimelineTrack` - DAW-style event timeline
  - `BathymetryViewer` - Interactive depth heatmap
  - `NMEAStream` - Real-time sentence display

- **Touch-Optimized UX**
  - 20mm minimum touch targets (wet-hand operation)
  - High-contrast day mode themes
  - Red-preserving night mode
  - Gesture controls (pinch zoom, pan, selection)
  - Responsive layouts (desktop/tablet/mobile)

- **Real-Time Data Handling**
  - WebSocket integration hooks
  - Automatic reconnection with backoff
  - Offline-first capabilities
  - React optimization with memoization

- **TypeScript Integration**
  - Complete type definitions
  - Type-safe interfaces
  - NMEA sentence types
  - Alert system types

## Installation

```bash
npm install @aelma/marine-components
```

## Quick Start

```tsx
import React, { useState } from 'react';
import {
  TelemetryPanel,
  AlertSystem,
  VesselScene,
  useVesselState,
  dayTheme,
} from '@aelma/marine-components';

function App() {
  const { vesselState, isConnected, error } = useVesselState('ws://localhost:8090');

  return (
    <div className="app" style={{ background: dayTheme.colors.background }}>
      {/* 3D Scene */}
      <VesselScene vesselState={vesselState} theme={dayTheme} />

      {/* Telemetry Display */}
      <TelemetryPanel vesselState={vesselState} theme={dayTheme} />

      {/* Alerts */}
      <AlertSystem
        alerts={vesselState?.actions || []}
        theme={dayTheme}
        onDismiss={(alertId) => console.log('Dismiss:', alertId)}
      />
    </div>
  );
}
```

## Components

### TelemetryPanel

Displays vessel telemetry with quality indicators.

```tsx
<TelemetryPanel
  vesselState={vesselState}
  theme={dayTheme}
  showChannels={['speed_kn', 'heading_deg']}
  compact={false}
  onUpdate={(state) => console.log('State updated:', state)}
/>
```

### AlertSystem

Real-time alert management with severity grouping.

```tsx
<AlertSystem
  alerts={alerts}
  theme={nightTheme}
  onDismiss={(alertId) => dismissAlert(alertId)}
  onClearAll={() => clearAllAlerts()}
  maxHistory={20}
  showHistory={true}
  autoGroup={true}
  allowDismiss={true}
/>
```

### VesselScene

3D vessel visualization with Three.js.

```tsx
<VesselScene
  vesselState={vesselState}
  alerts={alerts}
  theme={dayTheme}
  config={{
    track_max: 500,
    bathy_max: 200000,
    water_opacity: 0.55,
    auto_rotate_delay: 5000,
  }}
  onCameraChange={(position, target) => console.log('Camera changed')}
/>
```

### TimelineTrack

DAW-style timeline for event playback.

```tsx
<TimelineTrack
  events={timelineEvents}
  duration={3600}
  currentTime={120}
  onSeek={(time) => setCurrentTime(time)}
  zoom={100}
  onZoom={(zoom) => setZoom(zoom)}
  showTimeScale={true}
  showWaveform={false}
  allowCreateEvent={true}
/>
```

### BathymetryViewer

Interactive depth heatmap visualization.

```tsx
<BathymetryViewer
  data={bathymetryData}
  theme={dayTheme}
  pointSize={3}
  showColorScale={true}
  allowSelection={true}
  showStats={true}
  onPointClick={(cell) => console.log('Clicked:', cell)}
  onPointHover={(cell) => console.log('Hovered:', cell)}
/>
```

### NMEAStream

Real-time NMEA sentence display with filtering.

```tsx
<NMEAStream
  sentences={nmeaSentences}
  theme={dayTheme}
  maxVisible={100}
  filterTypes={['GPGGA', 'GPRMC']}
  highlightRules=[[/ALARM/, /ERROR/]]
  autoScroll={true}
  showTimestamp={true}
  showChecksum={true}
  onSentenceClick={(sentence) => console.log('Clicked:', sentence)}
/>
```

## Hooks

### useWebSocket

Raw WebSocket connection management.

```tsx
const {
  isConnected,
  isConnecting,
  error,
  reconnectAttempts,
  sendMessage,
  connect,
  disconnect,
  manualReconnect,
} = useWebSocket({
  url: 'ws://localhost:8090',
  reconnectInterval: 1000,
  maxReconnectAttempts: 5,
  onMessage: (message) => console.log('Message:', message),
  onConnect: () => console.log('Connected'),
  onDisconnect: () => console.log('Disconnected'),
  enabled: true,
});
```

### useVesselState

Vessel state updates from twin core.

```tsx
const {
  vesselState,
  isConnected,
  error,
} = useVesselState('ws://localhost:8090', {
  enabled: true,
});
```

### useActionEvents

Action event stream from watcher registry.

```tsx
const {
  actions,
  isConnected,
  clearActions,
} = useActionEvents('ws://localhost:8090', {
  enabled: true,
});
```

### useOfflineSync

Offline-first data synchronization.

```tsx
const {
  items,
  addItem,
  clearItems,
  isOnline,
  syncStatus,
  forceSync,
} = useOfflineSync('ws://localhost:8090', {
  storageKey: 'marine-vessel-data',
  enabled: true,
  syncInterval: 30000,
  maxStoredItems: 1000,
});
```

## Themes

### Day Mode

High-contrast theme for bright conditions.

```tsx
import { dayTheme } from '@aelma/marine-components';

<ThemeProvider theme={dayTheme}>
  <YourApp />
</ThemeProvider>
```

### Night Mode

Red-preserving theme for dark conditions.

```tsx
import { nightTheme } from '@aelma/marine-components';

<ThemeProvider theme={nightTheme}>
  <YourApp />
</ThemeProvider>
```

### Custom Theme

```tsx
import { MarineTheme } from '@aelma/marine-components';

const customTheme: MarineTheme = {
  name: 'Custom Theme',
  mode: 'day',
  colors: {
    // ... custom colors
  },
  // ... other theme properties
};
```

## TypeScript Types

All components export full TypeScript types:

```tsx
import type {
  VesselStateSnapshot,
  VesselPose,
  TelemetryChannel,
  BathymetryData,
  Alert,
  AlertSeverity,
  TimelineEvent,
  NMEASentence,
  MarineTheme,
} from '@aelma/marine-components';
```

## Styling

Components include built-in CSS that can be imported:

```tsx
import '@aelma/marine-components/dist/index.css';
```

Or use CSS modules for custom styling:

```css
.telemetry-panel {
  --marine-surface: #ffffff;
  --marine-text: #1a1a1a;
  /* ... custom CSS variables */
}
```

## Accessibility

All components support:
- Keyboard navigation
- Screen reader support
- ARIA labels
- Focus management
- Touch targets meeting WCAG 2.1 AAA

## Performance

- Memoization for expensive calculations
- Virtual scrolling for large datasets
- RequestAnimationFrame for animations
- WebGL acceleration for 3D rendering
- Optimized re-render patterns

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+
- iOS Safari 14+
- Chrome Android 90+

## License

MIT

## Contributing

Contributions welcome! Please read our contributing guidelines.

## Support

For issues and questions, please use the issue tracker.
