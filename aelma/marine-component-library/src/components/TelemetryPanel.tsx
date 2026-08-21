/**
 * TelemetryPanel - Marine vessel telemetry display
 * Shows depth, speed, heading, position, and custom channels
 * Touch-optimized with wet-hand operation targets
 */

import React, { useMemo, useCallback, useEffect } from 'react';
import { VesselStateSnapshot, TelemetryChannel, VesselPose } from '../types/vessel';
import { MarineTheme } from '../types/theme';
import './TelemetryPanel.css';

export interface TelemetryPanelProps {
  vesselState: VesselStateSnapshot | null;
  theme?: MarineTheme;
  className?: string;
  showChannels?: string[];
  compact?: boolean;
  onUpdate?: (state: VesselStateSnapshot) => void;
}

interface TelemetryField {
  name: string;
  label: string;
  unit: string;
  value: number | string | null;
  quality?: string;
  priority: number; // 0-1, for sorting
  isBig?: boolean; // Show as large display (depth)
}

/**
 * Priority levels for telemetry fields
 */
const FIELD_PRIORITIES: Record<string, number> = {
  depth_m: 1.0,
  speed_kn: 0.9,
  heading_deg: 0.8,
  position: 0.7,
  alt_m: 0.6,
};

/**
 * Extract telemetry fields from vessel state
 */
function extractTelemetryFields(
  state: VesselStateSnapshot,
  showChannels?: string[]
): TelemetryField[] {
  if (!state) return [];

  const { pose, channels } = state;
  const fields: TelemetryField[] = [];

  // Extract from pose (derived channels)
  if (pose) {
    fields.push({
      name: 'speed',
      label: 'Speed',
      unit: 'kn',
      value: pose.speed_kn ?? null,
      priority: FIELD_PRIORITIES.speed_kn,
    });

    fields.push({
      name: 'heading',
      label: 'Heading',
      unit: '°',
      value: pose.heading_deg ?? null,
      priority: FIELD_PRIORITIES.heading_deg,
    });

    fields.push({
      name: 'position',
      label: 'Position',
      unit: '',
      value: pose.lat && pose.lon
        ? `${pose.lat.toFixed(5)}, ${pose.lon.toFixed(5)}`
        : null,
      priority: FIELD_PRIORITIES.position,
    });

    if (pose.alt_m !== undefined) {
      fields.push({
        name: 'altitude',
        label: 'Altitude',
        unit: 'm',
        value: pose.alt_m,
        priority: FIELD_PRIORITIES.alt_m,
      });
    }
  }

  // Extract from channels
  if (channels) {
    for (const [name, channel] of Object.entries(channels)) {
      // Skip if not in filter
      if (showChannels && !showChannels.includes(name)) {
        continue;
      }

      // Extract unit from name
      const unitMatch = name.match(/_([a-z]+)$/i);
      const unit = unitMatch ? unitMatch[1] : '';

      // Format label (remove unit and underscores)
      const label = name.replace(/_[a-z]+$/i, '').replace(/_/g, ' ');

      const isBig = name === 'depth_m';

      fields.push({
        name: label,
        label,
        unit,
        value: typeof channel.value === 'number' ? channel.value : null,
        quality: channel.quality,
        priority: FIELD_PRIORITIES[name] || 0.5,
        isBig,
      });
    }
  }

  // Sort by priority
  return fields.sort((a, b) => b.priority - a.priority);
}

/**
 * Format numeric value with precision
 */
function formatValue(value: number | string | null, digits = 1): string {
  if (value === null) return '—';
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value.toFixed(digits) : '—';
  }
  return String(value);
}

/**
 * Get quality CSS class
 */
function getQualityClass(quality?: string): string {
  if (!quality) return 'q-none';
  const q = quality.toLowerCase();
  if (q === 'good') return 'q-good';
  if (q === 'degraded' || q === 'fair') return 'q-fair';
  if (q === 'bad') return 'q-bad';
  return 'q-none';
}

/**
 * TelemetryPanel component
 */
export const TelemetryPanel: React.FC<TelemetryPanelProps> = ({
  vesselState,
  theme,
  className = '',
  showChannels,
  compact = false,
  onUpdate,
}) => {
  // Extract and memoize fields
  const fields = useMemo(
    () => extractTelemetryFields(vesselState, showChannels),
    [vesselState, showChannels]
  );

  // Separate big display (depth) from regular fields
  const bigField = fields.find(f => f.isBig);
  const regularFields = fields.filter(f => !f.isBig);

  // Call update callback when state changes
  useEffect(() => {
    if (vesselState && onUpdate) {
      onUpdate(vesselState);
    }
  }, [vesselState, onUpdate]);

  // Handle field click (for future expansion)
  const handleFieldClick = useCallback((field: TelemetryField) => {
    console.log('[TelemetryPanel] Field clicked:', field.name);
  }, []);

  return (
    <div className={`telemetry-panel ${compact ? 'compact' : ''} ${className}`}>
      {/* Connection status header */}
      <div className="telemetry-header">
        <div className="vessel-id">
          {vesselState?.vessel_id || 'UNKNOWN VESSEL'}
        </div>
        {!compact && (
          <div className="connection-status">
            <span className="status-dot connected" />
            Live
          </div>
        )}
      </div>

      {/* Big depth display */}
      {bigField && (
        <div className="depth-panel">
          <div className="label">{bigField.label.toUpperCase()}</div>
          <div className={`depth-big ${getQualityClass(bigField.quality)}`}>
            {formatValue(bigField.value)}
          </div>
          {bigField.quality && (
            <div className="depth-quality">
              quality: {bigField.quality}
            </div>
          )}
        </div>
      )}

      {/* Regular telemetry grid */}
      {regularFields.length > 0 && (
        <div className="telemetry-grid">
          {regularFields.map((field) => (
            <TelemetryField
              key={field.name}
              field={field}
              theme={theme}
              onClick={() => handleFieldClick(field)}
            />
          ))}
        </div>
      )}

      {/* Empty state */}
      {fields.length === 0 && (
        <div className="empty-state">
          No telemetry data
        </div>
      )}
    </div>
  );
};

/**
 * Individual telemetry field component
 */
interface TelemetryFieldProps {
  field: TelemetryField;
  theme?: MarineTheme;
  onClick?: () => void;
}

const TelemetryField: React.FC<TelemetryFieldProps> = ({
  field,
  theme,
  onClick,
}) => {
  const handleClick = useCallback(() => {
    if (onClick) onClick();
  }, [onClick]);

  return (
    <button
      className="telemetry-field"
      onClick={handleClick}
      style={{
        minHeight: theme?.touchTargets.comfortable || '3rem',
        backgroundColor: theme?.colors.surface,
        border: `1px solid ${theme?.colors.border}`,
      }}
    >
      <div className="field-name">{field.label}</div>
      <div className="field-value">
        {formatValue(field.value)}
        {field.unit && (
          <span className="field-unit"> {field.unit}</span>
        )}
      </div>
    </button>
  );
};

export default TelemetryPanel;
