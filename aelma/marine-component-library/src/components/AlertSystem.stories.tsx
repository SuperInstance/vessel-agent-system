import type { Meta, StoryObj } from '@storybook/react';
import { AlertSystem } from './AlertSystem';
import { dayTheme, nightTheme } from '../types/theme';
import type { Alert } from '../types/vessel';

const meta: Meta<typeof AlertSystem> = {
  title: 'Marine Components/AlertSystem',
  component: AlertSystem,
  tags: ['autodocs'],
  argTypes: {
    className: { control: 'text' },
    autoGroup: { control: 'boolean' },
    allowDismiss: { control: 'boolean' },
    showHistory: { control: 'boolean' },
    maxHistory: { control: 'number' },
  },
};

export default meta;
type Story = StoryObj<typeof AlertSystem>;

// Mock alerts
const mockAlerts: Alert[] = [
  {
    id: 'alert-1',
    action: 'raise_alert',
    payload: {
      severity: 'CRITICAL',
      code: 'DEPTH_LOW',
      message: 'Depth below minimum safe threshold',
      source: 'depth_sensor',
    },
    reason: 'Vessel operating in shallow water (< 10m)',
    priority: 0.95,
    rule_id: 'depth_safety_001',
    timestamp_ns: BigInt(Date.now() * 1e6),
    created_at: Date.now(),
  },
  {
    id: 'alert-2',
    action: 'raise_alert',
    payload: {
      severity: 'WARNING',
      code: 'SPEED_HIGH',
      message: 'Speed exceeds recommended limit',
      source: 'gps_sensor',
    },
    reason: 'Vessel speed > 15kn in restricted zone',
    priority: 0.75,
    rule_id: 'speed_limit_001',
    timestamp_ns: BigInt((Date.now() - 60000) * 1e6),
    created_at: Date.now() - 60000,
  },
  {
    id: 'alert-3',
    action: 'raise_alert',
    payload: {
      severity: 'INFO',
      code: 'WAYPOINT_REACHED',
      message: 'Vessel reached waypoint WP-001',
      source: 'navigation',
    },
    reason: 'Navigation waypoint reached',
    priority: 0.4,
    rule_id: 'waypoint_001',
    timestamp_ns: BigInt((Date.now() - 120000) * 1e6),
    created_at: Date.now() - 120000,
  },
  {
    id: 'alert-4',
    action: 'raise_alert',
    payload: {
      severity: 'ERROR',
      code: 'SENSOR_FAIL',
      message: 'Wind sensor communication lost',
      source: 'wind_sensor',
    },
    reason: 'Sensor not responding',
    priority: 0.6,
    rule_id: 'sensor_health_001',
    timestamp_ns: BigInt((Date.now() - 180000) * 1e6),
    created_at: Date.now() - 180000,
  },
];

export const DayMode: Story = {
  args: {
    alerts: mockAlerts,
    theme: dayTheme,
    autoGroup: true,
    allowDismiss: true,
    showHistory: true,
    maxHistory: 20,
  },
};

export const NightMode: Story = {
  args: {
    alerts: mockAlerts,
    theme: nightTheme,
    autoGroup: true,
    allowDismiss: true,
    showHistory: true,
  },
  parameters: {
    theme: 'night',
  },
};

export const CriticalOnly: Story = {
  args: {
    alerts: mockAlerts.filter(a => a.priority >= 0.9),
    theme: dayTheme,
  },
};

export const NoAlerts: Story = {
  args: {
    alerts: [],
    theme: dayTheme,
  },
};

export const ManyAlerts: Story = {
  args: {
    alerts: Array.from({ length: 25 }, (_, i) => ({
      id: `alert-${i}`,
      action: 'raise_alert',
      payload: {
        severity: i % 3 === 0 ? 'WARNING' : 'INFO',
        code: `TEST_${i}`,
        message: `Test alert message ${i + 1}`,
        source: 'test',
      },
      reason: `Test reason ${i + 1}`,
      priority: 0.3 + (i % 7) * 0.1,
      rule_id: `test_${i}`,
      timestamp_ns: BigInt((Date.now() - i * 30000) * 1e6),
      created_at: Date.now() - i * 30000,
    })),
    theme: dayTheme,
    autoGroup: true,
  },
};

export const NoDismiss: Story = {
  args: {
    alerts: mockAlerts,
    theme: dayTheme,
    allowDismiss: false,
  },
};

export const NoGrouping: Story = {
  args: {
    alerts: mockAlerts,
    theme: dayTheme,
    autoGroup: false,
  },
};

export const Interactive: Story = {
  args: {
    alerts: mockAlerts,
    theme: dayTheme,
  },
  parameters: {
    actions: {
      handles: ['onDismiss', 'onClearAll'],
    },
  },
};
