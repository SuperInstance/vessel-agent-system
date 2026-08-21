import type { Meta, StoryObj } from '@storybook/react';
import { TelemetryPanel } from './TelemetryPanel';
import { dayTheme, nightTheme } from '../types/theme';
import type { VesselStateSnapshot } from '../types/vessel';

const meta: Meta<typeof TelemetryPanel> = {
  title: 'Marine Components/TelemetryPanel',
  component: TelemetryPanel,
  tags: ['autodocs'],
  argTypes: {
    className: { control: 'text' },
    compact: { control: 'boolean' },
    showChannels: { control: 'object' },
  },
};

export default meta;
type Story = StoryObj<typeof TelemetryPanel>;

// Mock vessel state
const mockVesselState: VesselStateSnapshot = {
  vessel_id: 'F/V EILEEN',
  timestamp_ns: BigInt(Date.now() * 1e6),
  pose: {
    lat: 47.6062,
    lon: -122.3321,
    heading_deg: 135.5,
    speed_kn: 12.3,
    depth_m: 45.2,
  },
  channels: {
    depth_m: { value: 45.2, quality: 'good', unit: 'm' },
    speed_kn: { value: 12.3, quality: 'good', unit: 'kn' },
    heading_deg: { value: 135.5, quality: 'good', unit: '°' },
    water_temp_c: { value: 12.5, quality: 'good', unit: '°C' },
    wind_speed_kn: { value: 15.2, quality: 'degraded', unit: 'kn' },
    wind_dir_deg: { value: 270, quality: 'good', unit: '°' },
    engine_rpm: { value: 1800, quality: 'good', unit: 'rpm' },
    fuel_consumption_l_h: { value: 45.2, quality: 'good', unit: 'L/h' },
  },
  bathymetry: {
    voxel_count: 15420,
    cells: [],
  },
};

export const DayMode: Story = {
  args: {
    vesselState: mockVesselState,
    theme: dayTheme,
    compact: false,
  },
};

export const NightMode: Story = {
  args: {
    vesselState: mockVesselState,
    theme: nightTheme,
    compact: false,
  },
  parameters: {
    theme: 'night',
  },
};

export const Compact: Story = {
  args: {
    vesselState: mockVesselState,
    theme: dayTheme,
    compact: true,
  },
};

export const FilteredChannels: Story = {
  args: {
    vesselState: mockVesselState,
    theme: dayTheme,
    showChannels: ['depth_m', 'speed_kn', 'heading_deg'],
  },
};

export const DegradedQuality: Story = {
  args: {
    vesselState: {
      ...mockVesselState,
      channels: {
        ...mockVesselState.channels,
        depth_m: { value: null, quality: 'bad', unit: 'm' },
        speed_kn: { value: 8.5, quality: 'degraded', unit: 'kn' },
      },
    },
    theme: dayTheme,
  },
};

export const NoData: Story = {
  args: {
    vesselState: null,
    theme: dayTheme,
  },
};

export const Interactive: Story = {
  args: {
    vesselState: mockVesselState,
    theme: dayTheme,
  },
  parameters: {
    actions: {
      handles: ['onUpdate'],
    },
  },
};
