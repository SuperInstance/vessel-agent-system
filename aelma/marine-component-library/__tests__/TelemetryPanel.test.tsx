/**
 * TelemetryPanel unit tests
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { TelemetryPanel } from '../src/components/TelemetryPanel';
import { dayTheme } from '../src/types/theme';
import type { VesselStateSnapshot } from '../src/types/vessel';

describe('TelemetryPanel', () => {
  const mockVesselState: VesselStateSnapshot = {
    vessel_id: 'TEST_VESSEL',
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
    },
    bathymetry: {
      voxel_count: 1000,
    },
  };

  it('renders vessel ID', () => {
    render(<TelemetryPanel vesselState={mockVesselState} theme={dayTheme} />);
    expect(screen.getByText('TEST_VESSEL')).toBeInTheDocument();
  });

  it('renders depth display', () => {
    render(<TelemetryPanel vesselState={mockVesselState} theme={dayTheme} />);
    expect(screen.getByText('45.2')).toBeInTheDocument();
  });

  it('renders speed channel', () => {
    render(<TelemetryPanel vesselState={mockVesselState} theme={dayTheme} />);
    expect(screen.getByText(/12\.3/)).toBeInTheDocument();
    expect(screen.getByText('kn')).toBeInTheDocument();
  });

  it('renders heading channel', () => {
    render(<TelemetryPanel vesselState={mockVesselState} theme={dayTheme} />);
    expect(screen.getByText(/135\.5/)).toBeInTheDocument();
    expect(screen.getByText('°')).toBeInTheDocument();
  });

  it('shows connection status', () => {
    render(<TelemetryPanel vesselState={mockVesselState} theme={dayTheme} />);
    expect(screen.getByText('Live')).toBeInTheDocument();
  });

  it('renders empty state when no vessel state', () => {
    render(<TelemetryPanel vesselState={null} theme={dayTheme} />);
    expect(screen.getByText('No telemetry data')).toBeInTheDocument();
  });

  it('applies quality class for good depth', () => {
    const { container } = render(
      <TelemetryPanel vesselState={mockVesselState} theme={dayTheme} />
    );
    const depthElement = container.querySelector('.depth-big');
    expect(depthElement).toHaveClass('q-good');
  });

  it('applies quality class for degraded depth', () => {
    const degradedState = {
      ...mockVesselState,
      channels: {
        ...mockVesselState.channels,
        depth_m: { value: 45.2, quality: 'degraded', unit: 'm' },
      },
    };
    const { container } = render(
      <TelemetryPanel vesselState={degradedState} theme={dayTheme} />
    );
    const depthElement = container.querySelector('.depth-big');
    expect(depthElement).toHaveClass('q-fair');
  });

  it('applies custom class name', () => {
    const { container } = render(
      <TelemetryPanel vesselState={mockVesselState} theme={dayTheme} className="custom-class" />
    );
    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('filters channels when showChannels is provided', () => {
    render(
      <TelemetryPanel
        vesselState={mockVesselState}
        theme={dayTheme}
        showChannels={['depth_m', 'speed_kn']}
      />
    );
    expect(screen.getByText('Depth')).toBeInTheDocument();
    expect(screen.getByText('Speed')).toBeInTheDocument();
    // Heading should not be shown
    const headingElement = screen.queryByText('Heading');
    expect(headingElement).not.toBeInTheDocument();
  });

  it('calls onUpdate when vessel state changes', () => {
    const onUpdate = jest.fn();
    const { rerender } = render(
      <TelemetryPanel vesselState={null} theme={dayTheme} onUpdate={onUpdate} />
    );

    rerender(<TelemetryPanel vesselState={mockVesselState} theme={dayTheme} onUpdate={onUpdate} />);

    expect(onUpdate).toHaveBeenCalledWith(mockVesselState);
  });

  it('handles field clicks', () => {
    const consoleSpy = jest.spyOn(console, 'log').mockImplementation();
    render(<TelemetryPanel vesselState={mockVesselState} theme={dayTheme} />);

    const speedField = screen.getByText('Speed').closest('.telemetry-field');
    if (speedField) {
      fireEvent.click(speedField);
    }

    expect(consoleSpy).toHaveBeenCalledWith(expect.stringContaining('Field clicked'));
    consoleSpy.mockRestore();
  });

  it('renders compact mode', () => {
    const { container } = render(
      <TelemetryPanel vesselState={mockVesselState} theme={dayTheme} compact={true} />
    );
    expect(container.firstChild).toHaveClass('compact');
  });

  it('handles null channel values', () => {
    const nullState = {
      ...mockVesselState,
      channels: {
        ...mockVesselState.channels,
        depth_m: { value: null, quality: 'bad', unit: 'm' },
      },
    };
    render(<TelemetryPanel vesselState={nullState} theme={dayTheme} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('formats position correctly', () => {
    render(<TelemetryPanel vesselState={mockVesselState} theme={dayTheme} />);
    expect(screen.getByText(/47\.60620/)).toBeInTheDocument();
    expect(screen.getByText(/-122\.33210/)).toBeInTheDocument();
  });
});
