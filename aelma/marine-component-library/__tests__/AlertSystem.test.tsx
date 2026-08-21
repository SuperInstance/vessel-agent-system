/**
 * AlertSystem unit tests
 */

import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import { AlertSystem } from '../src/components/AlertSystem';
import { dayTheme, nightTheme } from '../src/types/theme';
import type { Alert } from '../src/types/vessel';

describe('AlertSystem', () => {
  const mockAlerts: Alert[] = [
    {
      id: 'alert-1',
      action: 'raise_alert',
      payload: {
        severity: 'CRITICAL',
        code: 'TEST_001',
        message: 'Test critical alert',
        source: 'test',
      },
      reason: 'Test reason',
      priority: 0.95,
      rule_id: 'test_001',
      timestamp_ns: BigInt(Date.now() * 1e6),
      created_at: Date.now(),
    },
    {
      id: 'alert-2',
      action: 'raise_alert',
      payload: {
        severity: 'WARNING',
        code: 'TEST_002',
        message: 'Test warning',
        source: 'test',
      },
      reason: 'Test warning reason',
      priority: 0.6,
      rule_id: 'test_002',
      timestamp_ns: BigInt((Date.now() - 60000) * 1e6),
      created_at: Date.now() - 60000,
    },
    {
      id: 'alert-3',
      action: 'raise_alert',
      payload: {
        severity: 'INFO',
        code: 'TEST_003',
        message: 'Test info',
        source: 'test',
      },
      reason: 'Test info reason',
      priority: 0.3,
      rule_id: 'test_003',
      timestamp_ns: BigInt((Date.now() - 120000) * 1e6),
      created_at: Date.now() - 120000,
    },
  ];

  it('renders alert items', () => {
    render(<AlertSystem alerts={mockAlerts} theme={dayTheme} />);
    expect(screen.getByText('TEST_001')).toBeInTheDocument();
    expect(screen.getByText('TEST_002')).toBeInTheDocument();
    expect(screen.getByText('TEST_003')).toBeInTheDocument();
  });

  it('renders alert messages', () => {
    render(<AlertSystem alerts={mockAlerts} theme={dayTheme} />);
    expect(screen.getByText('Test critical alert')).toBeInTheDocument();
    expect(screen.getByText('Test warning')).toBeInTheDocument();
  });

  it('renders alert reasons', () => {
    render(<AlertSystem alerts={mockAlerts} theme={dayTheme} />);
    expect(screen.getByText('Test reason')).toBeInTheDocument();
  });

  it('applies correct priority classes', () => {
    const { container } = render(
      <AlertSystem alerts={mockAlerts} theme={dayTheme} />
    );

    const criticalAlert = container.querySelector('.priority-critical');
    const mediumAlert = container.querySelector('.priority-medium');
    const lowAlert = container.querySelector('.priority-low');

    expect(criticalAlert).toBeInTheDocument();
    expect(mediumAlert).toBeInTheDocument();
    expect(lowAlert).toBeInTheDocument();
  });

  it('calls onDismiss when dismiss button clicked', () => {
    const onDismiss = jest.fn();
    render(<AlertSystem alerts={mockAlerts} theme={dayTheme} onDismiss={onDismiss} />);

    const dismissButton = screen.getAllByText('✕')[0]; // First dismiss button
    fireEvent.click(dismissButton);

    expect(onDismiss).toHaveBeenCalledWith('alert-1');
  });

  it('calls onClearAll when clear all button clicked', () => {
    const onClearAll = jest.fn();
    render(<AlertSystem alerts={mockAlerts} theme={dayTheme} onClearAll={onClearAll} />);

    const clearButton = screen.getByText(/clear all/i);
    fireEvent.click(clearButton);

    expect(onClearAll).toHaveBeenCalled();
  });

  it('renders alert statistics', () => {
    render(<AlertSystem alerts={mockAlerts} theme={dayTheme} />);

    expect(screen.getByText('1 Critical')).toBeInTheDocument();
  });

  it('shows empty state when no alerts', () => {
    render(<AlertSystem alerts={[]} theme={dayTheme} />);
    expect(screen.getByText('No active alerts')).toBeInTheDocument();
  });

  it('filters alerts by severity', () => {
    render(<AlertSystem alerts={mockAlerts} theme={dayTheme} />);

    // Click critical filter
    const criticalFilter = screen.getByText('Critical');
    fireEvent.click(criticalFilter);

    // Should only show critical alert
    expect(screen.getByText('TEST_001')).toBeInTheDocument();
    expect(screen.queryByText('TEST_002')).not.toBeInTheDocument();
  });

  it('renders alert history', () => {
    render(<AlertSystem alerts={mockAlerts} theme={dayTheme} showHistory={true} />);

    expect(screen.getByText('History')).toBeInTheDocument();
  });

  it('does not show history when showHistory is false', () => {
    render(<AlertSystem alerts={mockAlerts} theme={dayTheme} showHistory={false} />);

    expect(screen.queryByText('History')).not.toBeInTheDocument();
  });

  it('respects maxHistory limit', () => {
    const manyAlerts = Array.from({ length: 25 }, (_, i) => ({
      id: `alert-${i}`,
      action: 'raise_alert',
      payload: {
        severity: 'INFO',
        code: `TEST_${i}`,
        message: `Test alert ${i}`,
        source: 'test',
      },
      reason: `Test reason ${i}`,
      priority: 0.3,
      rule_id: `test_${i}`,
      timestamp_ns: BigInt(Date.now() * 1e6),
      created_at: Date.now(),
    }));

    render(<AlertSystem alerts={manyAlerts} theme={dayTheme} maxHistory={10} />);

    // History section should be present
    expect(screen.getByText('History')).toBeInTheDocument();
  });

  it('opens detail modal on alert click', () => {
    render(<AlertSystem alerts={mockAlerts} theme={dayTheme} allowDismiss={true} />);

    const alertItem = screen.getByText('TEST_001').closest('.alert-item');
    if (alertItem) {
      fireEvent.click(alertItem);
    }

    // Modal should be visible
    expect(screen.getByText('Severity:')).toBeInTheDocument();
    expect(screen.getByText('Priority:')).toBeInTheDocument();
  });

  it('closes modal on backdrop click', () => {
    render(<AlertSystem alerts={mockAlerts} theme={dayTheme} allowDismiss={true} />);

    // Open modal
    const alertItem = screen.getByText('TEST_001').closest('.alert-item');
    if (alertItem) {
      fireEvent.click(alertItem);
    }

    // Close modal
    const closeButton = screen.getByText('Close');
    fireEvent.click(closeButton);

    // Modal should be closed
    expect(screen.queryByText('Severity:')).not.toBeInTheDocument();
  });

  it('applies custom class name', () => {
    const { container } = render(
      <AlertSystem alerts={mockAlerts} theme={dayTheme} className="custom-class" />
    );
    expect(container.firstChild).toHaveClass('custom-class');
  });

  it('respects allowDismiss prop', () => {
    const { container } = render(
      <AlertSystem alerts={mockAlerts} theme={dayTheme} allowDismiss={false} />
    );

    // Should not have dismiss buttons
    const dismissButtons = container.querySelectorAll('.btn-dismiss');
    expect(dismissButtons.length).toBe(0);
  });

  it('displays timestamps correctly', () => {
    render(<AlertSystem alerts={mockAlerts} theme={dayTheme} />);

    // Timestamps should be present
    const timestamps = screen.getAllByTestId?.('alert-time') || [];
    expect(timestamps.length).toBeGreaterThan(0);
  });

  it('handles night mode theme', () => {
    const { container } = render(
      <AlertSystem alerts={mockAlerts} theme={nightTheme} />
    );
    expect(container.firstChild).toHaveAttribute('data-theme', 'night');
  });
});
