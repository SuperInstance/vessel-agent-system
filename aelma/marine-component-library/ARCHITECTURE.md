# Marine Component Library - Architecture Documentation

## Overview

The `@aelma/marine-components` library is a comprehensive React component system designed specifically for marine digital twin interfaces. It provides production-ready components for vessel monitoring, alert management, 3D visualization, and real-time data display.

## Architecture Principles

### 1. Marine-First Design
All components are designed with marine operations in mind:
- **Wet-hand operation**: 20mm minimum touch targets
- **Day/night modes**: High-contrast day mode, red-preserving night mode
- **Glo-friendly controls**: Large buttons, clear indicators
- **Motion tolerance**: Clear visual feedback for all interactions

### 2. Real-Time Performance
- **WebSocket integration**: Built-in hooks for real-time data
- **Optimized rendering**: Memoization and virtual scrolling
- **Efficient updates**: RequestAnimationFrame for animations
- **GPU acceleration**: WebGL for 3D visualization

### 3. Type Safety
- **Complete TypeScript types**: Full type definitions for all APIs
- **Type-safe interfaces**: No `any` types in public APIs
- **Documentation types**: JSDoc comments for IDE support

### 4. Accessibility
- **WCAG 2.1 AAA**: All touch targets meet accessibility standards
- **Keyboard navigation**: Full keyboard support
- **Screen reader support**: ARIA labels and semantic HTML
- **Focus management**: Proper focus handling in all components

## Component Architecture

### Component Hierarchy

```
MarineComponentLibrary
├── Display Components
│   ├── TelemetryPanel      // Sensor data display
│   ├── AlertSystem         // Alert management
│   └── NMEAStream         // NMEA sentence display
├── Visualization Components
│   ├── VesselScene        // 3D vessel visualization
│   ├── BathymetryViewer   // Depth heatmap
│   └── TimelineTrack      // Event timeline
├── Data Hooks
│   ├── useWebSocket       // Raw WebSocket
│   ├── useVesselState     // Vessel state updates
│   ├── useActionEvents    // Action event stream
│   └── useOfflineSync     // Offline-first sync
└── Theme System
    ├── dayTheme           // High-contrast day mode
    └── nightTheme         // Red-preserving night mode
```

### Component Communication

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Layer                       │
└──────────────┬────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│                      WebSocket Layer                         │
│  • useWebSocket                                            │
│  • useVesselState                                          │
│  • useActionEvents                                         │
└──────────────┬────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│                    Component Layer                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ TelemetryPanel│  │  AlertSystem │  │  NMEAStream  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ VesselScene   │  │BathymetryView│  │ TimelineTrack│     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└──────────────┬────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│                      Theme Layer                              │
│  • dayTheme                                                 │
│  • nightTheme                                               │
│  • Custom themes                                            │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

### WebSocket Data Flow

```
┌─────────────┐
│   Twin Core │
└──────┬──────┘
       │ WebSocket Message
       ▼
┌──────────────────┐
│ useWebSocket     │
│ • Connection     │
│ • Parsing        │
│ • Error Handling │
└──────┬───────────┘
       │ Parsed Data
       ▼
┌──────────────────┐
│ useVesselState   │
│ • State Updates  │
│ • Memoization    │
└──────┬───────────┘
       │ VesselState
       ▼
┌──────────────────┐
│   Components     │
│ • TelemetryPanel │
│ • VesselScene    │
│ • BathymetryView │
└──────────────────┘
```

### Alert Data Flow

```
┌─────────────┐
│ Action Event│
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│ useActionEvents  │
│ • Collection     │
│ • Filtering      │
└──────┬───────────┘
       │ Alert[]
       ▼
┌──────────────────┐
│  AlertSystem     │
│ • Display        │
│ • Grouping       │
│ • Dismissal      │
└──────┬───────────┘
       │ User Action
       ▼
┌──────────────────┐
│ Alert Handlers   │
│ • onDismiss      │
│ • onClearAll     │
└──────────────────┘
```

## Performance Optimization

### 1. Component Memoization

```tsx
// Memoized calculations
const fields = useMemo(
  () => extractTelemetryFields(vesselState, showChannels),
  [vesselState, showChannels]
);

// Stable callbacks
const handleClick = useCallback(() => {
  doSomething();
}, [dependency]);
```

### 2. Virtual Scrolling

```tsx
// Large datasets use react-window
import { FixedSizeList } from 'react-window';

<FixedSizeList
  height={600}
  itemCount={items.length}
  itemSize={50}
>
  {Row}
</FixedSizeList>
```

### 3. Three.js Optimization

```tsx
// Reuse geometries and materials
const geometryRef = useRef(new THREE.BufferGeometry());
const materialRef = useRef(new THREE.PointsMaterial());

// Update only what changes
useEffect(() => {
  if (bathyRef.current) {
    bathyRef.current.geometry.attributes.position.needsUpdate = true;
  }
}, [bathyData]);
```

### 4. WebSocket Throttling

```tsx
// Throttle expensive operations
const throttledUpdate = useThrottle(updateScene, 100); // 10Hz max

useEffect(() => {
  if (vesselState) {
    throttledUpdate(vesselState);
  }
}, [vesselState]);
```

## Theme System

### Theme Structure

```typescript
interface MarineTheme {
  name: string;
  mode: 'day' | 'night';
  colors: MarineColorPalette;
  typography: MarineTypography;
  spacing: MarineSpacing;
  touchTargets: MarineTouchTargets;
  borders: MarineBorders;
  shadows: MarineShadows;
  animation: MarineAnimation;
}
```

### CSS Custom Properties

```css
.telemetry-panel {
  --marine-surface: #ffffff;
  --marine-text: #1a1a1a;
  --marine-border: #cccccc;
  /* ... */
}
```

### Theme Switching

```tsx
// Day/Night toggle
const [theme, setTheme] = useState(dayTheme);

const toggleTheme = () => {
  setTheme(prev => prev === dayTheme ? nightTheme : dayTheme);
};
```

## Type System

### Core Types

```typescript
// Vessel state
interface VesselStateSnapshot {
  vessel_id?: string;
  timestamp_ns?: bigint;
  pose: VesselPose;
  channels?: Record<string, TelemetryChannel>;
  bathymetry?: BathymetryData;
}

// Alert system
interface Alert {
  id: string;
  action: string;
  payload: AlertPayload;
  reason: string;
  priority: number;
  rule_id: string;
  timestamp_ns: bigint;
  created_at: number;
}

// Timeline events
interface TimelineEvent {
  id: string;
  type: 'alert' | 'action' | 'state_change' | 'waypoint';
  timestamp: number;
  duration?: number;
  label: string;
  color: string;
}
```

### Component Props

All components export their props types:

```typescript
import type {
  TelemetryPanelProps,
  AlertSystemProps,
  VesselSceneProps,
  TimelineTrackProps,
  BathymetryViewerProps,
  NMEAStreamProps,
} from '@aelma/marine-components';
```

## Testing Strategy

### Unit Tests

```tsx
// Component testing
describe('TelemetryPanel', () => {
  it('renders vessel ID', () => {
    render(<TelemetryPanel vesselState={mockState} />);
    expect(screen.getByText('TEST_VESSEL')).toBeInTheDocument();
  });
});
```

### Integration Tests

```tsx
// WebSocket integration testing
describe('useVesselState', () => {
  it('connects to WebSocket and receives updates', async () => {
    const { result } = renderHook(() => useVesselState(wsUrl));
    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });
  });
});
```

### Visual Tests

```tsx
// Storybook stories for visual testing
export const DayMode: Story = {
  args: {
    vesselState: mockState,
    theme: dayTheme,
  },
};
```

## Build System

### Rollup Configuration

```javascript
// rollup.config.js
export default [
  {
    input: 'src/index.ts',
    output: [
      { file: 'dist/index.js', format: 'cjs' },
      { file: 'dist/index.esm.js', format: 'esm' },
    ],
    plugins: [
      peerDepsExternal(),
      resolve(),
      commonjs(),
      typescript(),
      postcss(),
    ],
  },
];
```

### TypeScript Compilation

```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "jsx": "react-jsx",
    "strict": true,
    "declaration": true,
    "declarationMap": true
  }
}
```

## Deployment

### NPM Package Structure

```
@aelma/marine-components/
├── dist/
│   ├── index.js           # CommonJS
│   ├── index.esm.js       # ES Modules
│   ├── index.d.ts         # TypeScript declarations
│   ├── *.css              # Component styles
│   └── *.css.map          # Source maps
├── package.json
├── README.md
└── LICENSE
```

### Installation

```bash
# NPM
npm install @aelma/marine-components

# Yarn
yarn add @aelma/marine-components

# PNPM
pnpm add @aelma/marine-components
```

### Usage

```tsx
import { TelemetryPanel, useVesselState, dayTheme } from '@aelma/marine-components';

function App() {
  const { vesselState } = useVesselState('ws://localhost:8090');

  return <TelemetryPanel vesselState={vesselState} theme={dayTheme} />;
}
```

## Future Enhancements

### Planned Features

1. **Additional Components**
   - Chart library integration (temperature, fuel, etc.)
   - Route planning interface
   - Weather overlay system
   - Equipment status panels

2. **Performance Improvements**
   - WebWorker for data processing
   - Service Worker for offline caching
   - WebGL renderer optimizations
   - Delta update protocol

3. **Developer Experience**
   - CLI tool for component generation
   - VS Code extension
   - Performance monitoring tools
   - Debug mode for development

4. **Integration**
   - SignalK support
   - CAN bus integration
   - AIS vessel tracking
   - Weather API integration

## Contributing

### Development Setup

```bash
# Clone repository
git clone https://github.com/aelma/marine-components

# Install dependencies
npm install

# Start Storybook
npm run storybook

# Run tests
npm test

# Build library
npm run build
```

### Component Development

1. Create component in `src/components/`
2. Add TypeScript types
3. Write CSS in `src/components/*.css`
4. Create stories in `src/components/*.stories.tsx`
5. Write tests in `__tests__/*.test.tsx`
6. Update `src/index.ts` exports

### Code Style

- Use TypeScript strict mode
- Follow React best practices
- Use CSS custom properties for theming
- Document all public APIs
- Maintain 70%+ test coverage

## License

MIT License - see LICENSE file for details

## Support

For issues, questions, or contributions:
- GitHub Issues: https://github.com/aelma/marine-components/issues
- Documentation: https://docs.aelma.com/marine-components
- Discord: https://discord.gg/aelma
