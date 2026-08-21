# Marine Component Library - Integration Example

This guide demonstrates how to integrate the `@aelma/marine-components` library into the AELMA viewer system.

## Complete Integration Example

```tsx
/**
 * AELMA Viewer Integration
 * Complete marine digital twin interface
 */

import React, { useState, useCallback } from 'react';
import {
  TelemetryPanel,
  AlertSystem,
  VesselScene,
  TimelineTrack,
  BathymetryViewer,
  NMEAStream,
  useVesselState,
  useActionEvents,
  dayTheme,
  nightTheme,
  type VesselStateSnapshot,
  type Alert,
  type TimelineEvent,
  type NMEASentence,
} from '@aelma/marine-components';

const WS_URL = 'ws://localhost:8090';

interface AelmaViewerProps {
  wsUrl?: string;
  initialTheme?: 'day' | 'night';
}

export const AelmaViewer: React.FC<AelmaViewerProps> = ({
  wsUrl = WS_URL,
  initialTheme = 'day',
}) => {
  // Theme state
  const [theme, setTheme] = useState(initialTheme === 'day' ? dayTheme : nightTheme);
  const [isNight, setIsNight] = useState(initialTheme === 'night');

  // WebSocket connections
  const { vesselState, isConnected, error } = useVesselState(wsUrl, {
    enabled: true,
    onConnect: () => console.log('[AELMA] Connected to twin core'),
    onDisconnect: () => console.log('[AELMA] Disconnected from twin core'),
    onError: (err) => console.error('[AELMA] WebSocket error:', err),
  });

  const { actions, clearActions } = useActionEvents(wsUrl, {
    enabled: true,
  });

  // Derived state
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([]);
  const [nmeaSentences, setNmeaSentences] = useState<NMEASentence[]>([]);

  // Process actions into alerts
  useEffect(() => {
    const newAlerts = actions
      .filter(action => action.action === 'raise_alert')
      .map((action, index) => ({
        id: `alert-${action.timestamp_ns}-${index}`,
        action: action.action,
        payload: {
          severity: action.payload?.severity || 'WARNING',
          code: action.payload?.code || 'ALERT',
          message: action.payload?.message || action.reason || 'Unknown alert',
          source: action.payload?.source,
          details: action.payload?.details,
        },
        reason: action.reason || '',
        priority: action.priority || 0.5,
        rule_id: action.rule_id || 'unknown',
        timestamp_ns: action.timestamp_ns,
        created_at: Date.now(),
      }));

    setAlerts(newAlerts);
  }, [actions]);

  // Create timeline events from vessel state
  useEffect(() => {
    if (!vesselState) return;

    const events: TimelineEvent[] = [];

    // Add pose updates as events
    if (vesselState.pose) {
      events.push({
        id: `pose-${vesselState.timestamp_ns}`,
        type: 'state_change',
        timestamp: Number(vesselState.timestamp_ns) / 1e9,
        label: 'Position Update',
        color: '#1c5f8a',
        metadata: vesselState.pose,
      });
    }

    // Add alerts as events
    alerts.forEach(alert => {
      events.push({
        id: alert.id,
        type: 'alert',
        timestamp: Number(alert.timestamp_ns) / 1e9,
        duration: 5,
        label: alert.payload.code,
        color: alert.priority >= 0.9 ? '#e04b4b' : '#e0b13c',
        metadata: alert,
      });
    });

    setTimelineEvents(events);
  }, [vesselState, alerts]);

  // Theme toggle
  const toggleTheme = useCallback(() => {
    setIsNight(prev => !prev);
    setTheme(prev => prev === dayTheme ? nightTheme : dayTheme);
  }, []);

  // Alert handlers
  const handleDismissAlert = useCallback((alertId: string) => {
    setAlerts(prev => prev.filter(alert => alert.id !== alertId));
  }, []);

  const handleClearAlerts = useCallback(() => {
    setAlerts([]);
  }, []);

  // Mock NMEA sentences (in real app, these come from WebSocket)
  useEffect(() => {
    const mockNmea: NMEASentence[] = [
      {
        type: 'GPGGA',
        raw: '$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47',
        timestamp_ns: BigInt(Date.now() * 1e6),
        valid: true,
        checksum_valid: true,
      },
    ];
    setNmeaSentences(mockNmea);
  }, []);

  return (
    <div
      className="aelma-viewer"
      data-theme={isNight ? 'night' : 'day'}
      style={{
        width: '100vw',
        height: '100vh',
        display: 'grid',
        gridTemplateColumns: '350px 1fr 300px',
        gridTemplateRows: 'auto 1fr auto',
        gap: '8px',
        padding: '8px',
        background: theme.colors.background,
        color: theme.colors.text,
        fontFamily: theme.typography.fontFamily,
      }}
    >
      {/* Header */}
      <header
        style={{
          gridColumn: '1 / -1',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: theme.spacing.md,
          background: theme.colors.surface,
          borderRadius: theme.borders.lg,
          border: `1px solid ${theme.colors.border}`,
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: theme.typography.fontSizeXL }}>
            AELMA Viewer
          </h1>
          <div style={{ fontSize: theme.typography.fontSizeSM, color: theme.colors.textSecondary }}>
            {vesselState?.vessel_id || 'Connecting...'}
          </div>
        </div>

        <div style={{ display: 'flex', gap: theme.spacing.sm, alignItems: 'center' }}>
          <div
            className={`status-dot ${isConnected ? 'connected' : 'disconnected'}`}
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: isConnected ? theme.colors.success : theme.colors.error,
            }}
          />
          <span style={{ fontSize: theme.typography.fontSizeSM }}>
            {isConnected ? 'Live' : error || 'Connecting...'}
          </span>

          <button
            onClick={toggleTheme}
            style={{
              padding: theme.spacing.sm,
              minHeight: theme.touchTargets.minimum,
              background: theme.colors.surfaceVariant,
              border: `1px solid ${theme.colors.border}`,
              borderRadius: theme.borders.md,
              color: theme.colors.text,
              cursor: 'pointer',
            }}
          >
            {isNight ? '☀️ Day' : '🌙 Night'}
          </button>
        </div>
      </header>

      {/* Left sidebar - Telemetry */}
      <aside
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: theme.spacing.sm,
        }}
      >
        <TelemetryPanel
          vesselState={vesselState}
          theme={theme}
          className="panel"
        />

        <BathymetryViewer
          data={vesselState?.bathymetry || { voxel_count: 0, cells: [] }}
          theme={theme}
          className="panel"
          showStats={true}
          allowSelection={true}
        />
      </aside>

      {/* Center - 3D Scene */}
      <main
        style={{
          position: 'relative',
          background: theme.colors.surface,
          borderRadius: theme.borders.lg,
          border: `1px solid ${theme.colors.border}`,
          overflow: 'hidden',
        }}
      >
        <VesselScene
          vesselState={vesselState}
          alerts={alerts}
          theme={theme}
          config={{
            track_max: 500,
            bathy_max: 200000,
            water_opacity: isNight ? 0.3 : 0.55,
            auto_rotate_delay: 5000,
            vessel_color: 0xff7700,
          }}
        />

        {/* Scene overlay controls */}
        <div
          style={{
            position: 'absolute',
            top: theme.spacing.md,
            right: theme.spacing.md,
            display: 'flex',
            gap: theme.spacing.xs,
          }}
        >
          <button
            style={{
              padding: theme.spacing.xs,
              background: theme.colors.surface,
              border: `1px solid ${theme.colors.border}`,
              borderRadius: theme.borders.sm,
              color: theme.colors.text,
              minHeight: theme.touchTargets.minimum,
            }}
          >
            📍
          </button>
          <button
            style={{
              padding: theme.spacing.xs,
              background: theme.colors.surface,
              border: `1px solid ${theme.colors.border}`,
              borderRadius: theme.borders.sm,
              color: theme.colors.text,
              minHeight: theme.touchTargets.minimum,
            }}
          >
            🔄
          </button>
        </div>
      </main>

      {/* Right sidebar - Alerts & NMEA */}
      <aside
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: theme.spacing.sm,
        }}
      >
        <AlertSystem
          alerts={alerts}
          theme={theme}
          onDismiss={handleDismissAlert}
          onClearAll={handleClearAlerts}
          maxHistory={20}
          showHistory={true}
          className="panel"
        />

        <NMEAStream
          sentences={nmeaSentences}
          theme={theme}
          maxVisible={50}
          autoScroll={true}
          showTimestamp={true}
          showChecksum={true}
          className="panel"
        />
      </aside>

      {/* Bottom - Timeline */}
      <footer
        style={{
          gridColumn: '1 / -1',
          background: theme.colors.surface,
          borderRadius: theme.borders.lg,
          border: `1px solid ${theme.colors.border}`,
          padding: theme.spacing.sm,
        }}
      >
        <TimelineTrack
          events={timelineEvents}
          duration={3600}
          currentTime={vesselState ? Number(vesselState.timestamp_ns) / 1e9 % 3600 : 0}
          zoom={100}
          showTimeScale={true}
          showWaveform={false}
          theme={theme}
        />
      </footer>
    </div>
  );
};

export default AelmaViewer;
```

## WebSocket Integration

### Message Format

The library expects WebSocket messages in this format:

```typescript
// Snapshot message (vessel state)
{
  type: 'snapshot',
  data: {
    vessel_id: string,
    timestamp_ns: bigint,
    pose: {
      lat: number,
      lon: number,
      heading_deg: number,
      speed_kn: number,
    },
    channels: {
      depth_m: { value: number, quality: string, unit: string },
      // ... more channels
    },
    bathymetry: {
      voxel_count: number,
      cells: Array<[lat, lon, depth, confidence]>,
    },
  }
}

// Action message (alert/event)
{
  type: 'action',
  data: {
    action: string,
    payload: Record<string, unknown>,
    reason: string,
    priority: number,
    rule_id: string,
    timestamp_ns: bigint,
  }
}
```

### Server Integration

```python
# Python example using the existing AELMA twin core
import json
import asyncio
import websockets
from datetime import datetime

async def vessel_websocket_handler(websocket, path):
    """Handle WebSocket connections for vessel updates"""

    try:
        while True:
            # Get current vessel state from twin core
            state = twin_core.get_state_snapshot()

            # Convert to library format
            message = {
                'type': 'snapshot',
                'data': {
                    'vessel_id': state.vessel_id,
                    'timestamp_ns': int(datetime.now().timestamp() * 1e9),
                    'pose': {
                        'lat': state.position.lat,
                        'lon': state.position.lon,
                        'heading_deg': state.heading,
                        'speed_kn': state.speed,
                    },
                    'channels': {
                        'depth_m': {
                            'value': state.depth.value,
                            'quality': state.depth.quality,
                            'unit': 'm'
                        },
                        # ... more channels
                    },
                    'bathymetry': {
                        'voxel_count': len(state.bathymetry),
                        'cells': [[c.lat, c.lon, c.depth, c.confidence]
                                 for c in state.bathymetry]
                    }
                }
            }

            await websocket.send(json.dumps(message))
            await asyncio.sleep(0.1)  # 10Hz update rate

    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected")

# Start WebSocket server
async def main():
    async with websockets.serve(vessel_websocket_handler, "localhost", 8090):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())
```

## CSS Integration

Add the component styles to your build:

```tsx
// In your main CSS file
import '@aelma/marine-components/dist/index.css';

// Or import individual component styles
import '@aelma/marine-components/dist/TelemetryPanel.css';
import '@aelma/marine-components/dist/AlertSystem.css';
// ... etc
```

## Production Build

```bash
# Install dependencies
npm install

# Run Storybook for development
npm run storybook

# Build for production
npm run build

# Run tests
npm test

# Type checking
npm run typecheck

# Linting
npm run lint
```

## Deployment

```bash
# Build the library
npm run build

# The dist folder contains:
# - dist/index.js (CommonJS)
# - dist/index.esm.js (ES Modules)
# - dist/index.d.ts (TypeScript declarations)
# - dist/*.css (Component styles)
```

## Performance Tips

1. **Memoization**: Components use `useMemo` and `useCallback` internally
2. **Virtual Scrolling**: Large datasets use react-window
3. **WebGL Acceleration**: Three.js scenes use GPU acceleration
4. **Update Throttling**: WebSocket updates can be throttled

```tsx
// Throttle updates for performance
const { vesselState } = useVesselState(wsUrl, {
  enabled: true,
  onMessage: throttle((msg) => {
    // Handle message
  }, 100), // Throttle to 10Hz
});
```

## Browser Support

- Modern browsers with ES2020 support
- WebGL for 3D visualization
- WebSocket for real-time updates
- Touch events for mobile/tablet

## Accessibility

All components support:
- Keyboard navigation
- Screen reader compatibility
- ARIA labels
- Focus management
- Touch targets (WCAG 2.1 AAA)

## Troubleshooting

### WebSocket Connection Issues

```tsx
const { isConnected, error } = useVesselState(wsUrl, {
  onConnect: () => console.log('Connected'),
  onError: (err) => console.error('Error:', err),
});
```

### Theme Not Applying

```tsx
// Make sure to pass theme to all components
<ThemeProvider theme={theme}>
  <TelemetryPanel theme={theme} />
  <AlertSystem theme={theme} />
  {/* ... */}
</ThemeProvider>
```

### Performance Issues

```tsx
// Reduce update frequency
const { vesselState } = useVesselState(wsUrl, {
  // Add custom throttling
});
```

## Next Steps

1. **Customize Themes**: Create your own day/night themes
2. **Add Filters**: Implement custom filtering for NMEA streams
3. **Extend Components**: Build custom components on top of the library
4. **Integrate Backend**: Connect to your vessel twin core
5. **Deploy**: Use in production with proper WebSocket infrastructure
