/**
 * AlertSystem - Marine vessel alert display
 * Shows active and historical alerts with severity grouping
 * Touch-optimized dismiss actions and filtering
 */

import React, { useMemo, useCallback, useState, useEffect, useRef } from 'react';
import { Alert, AlertSeverity, AlertPayload } from '../types/vessel';
import { MarineTheme } from '../types/theme';
import './AlertSystem.css';

export interface AlertSystemProps {
  alerts: Alert[];
  theme?: MarineTheme;
  onDismiss?: (alertId: string) => void;
  onClearAll?: () => void;
  maxHistory?: number;
  showHistory?: boolean;
  className?: string;
  autoGroup?: boolean;
  allowDismiss?: boolean;
}

/**
 * Get severity level from priority
 */
export function getPriorityLevel(priority: number): AlertSeverity {
  if (priority >= 0.9) return 'critical';
  if (priority >= 0.7) return 'high';
  if (priority >= 0.4) return 'medium';
  return 'low';
}

/**
 * Get color for priority level
 */
export function getPriorityColor(priority: number, theme?: MarineTheme): string {
  const level = getPriorityLevel(priority);
  if (!theme) {
    // Default colors
    switch (level) {
      case 'critical': return '#e04b4b';
      case 'high': return '#e0b13c';
      case 'medium': return '#35e08a';
      case 'low': return '#6f93b3';
    }
  }

  switch (level) {
    case 'critical': return theme.colors.critical;
    case 'high': return theme.colors.warning;
    case 'medium': return theme.colors.success;
    case 'low': return theme.colors.info;
  }
}

/**
 * Format timestamp for display
 */
function formatTimestamp(ns: bigint): string {
  const s = Math.floor(Number(ns) / 1e9);
  const date = new Date(s * 1000);
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

/**
 * Group alerts by severity
 */
function groupAlertsBySeverity(alerts: Alert[]): Record<AlertSeverity, Alert[]> {
  return alerts.reduce((groups, alert) => {
    const level = getPriorityLevel(alert.priority);
    if (!groups[level]) groups[level] = [];
    groups[level].push(alert);
    return groups;
  }, {} as Record<AlertSeverity, Alert[]>);
}

/**
 * Filter active alerts (not dismissed)
 */
function filterActiveAlerts(alerts: Alert[]): Alert[] {
  return alerts.filter(alert => !alert.dismissed);
}

/**
 * AlertSystem component
 */
export const AlertSystem: React.FC<AlertSystemProps> = ({
  alerts,
  theme,
  onDismiss,
  onClearAll,
  maxHistory = 20,
  showHistory = true,
  className = '',
  autoGroup = true,
  allowDismiss = true,
}) => {
  const [history, setHistory] = useState<Alert[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [filterLevel, setFilterLevel] = useState<AlertSeverity | 'all'>('all');
  const scrollRef = useRef<HTMLDivElement>(null);

  // Filter active alerts
  const activeAlerts = useMemo(
    () => filterActiveAlerts(alerts),
    [alerts]
  );

  // Group by severity if auto-group enabled
  const groupedAlerts = useMemo(() => {
    if (!autoGroup) return { all: activeAlerts };
    return groupAlertsBySeverity(activeAlerts);
  }, [activeAlerts, autoGroup]);

  // Filter by selected severity
  const filteredAlerts = useMemo(() => {
    if (filterLevel === 'all') return activeAlerts;
    return activeAlerts.filter(alert => getPriorityLevel(alert.priority) === filterLevel);
  }, [activeAlerts, filterLevel]);

  // Update history when alerts are added
  useEffect(() => {
    setHistory(prev => {
      const newHistory = [...alerts, ...prev];
      return newHistory.slice(0, maxHistory);
    });
  }, [alerts, maxHistory]);

  // Auto-scroll to new alerts
  useEffect(() => {
    if (scrollRef.current && filteredAlerts.length > 0) {
      scrollRef.current.scrollTop = 0;
    }
  }, [filteredAlerts.length]);

  // Dismiss handlers
  const handleDismiss = useCallback((alertId: string) => {
    if (onDismiss) {
      onDismiss(alertId);
    }
  }, [onDismiss]);

  const handleClearAll = useCallback(() => {
    if (onClearAll) {
      onClearAll();
    }
  }, [onClearAll]);

  // Alert selection
  const handleAlertClick = useCallback((alert: Alert) => {
    setSelectedAlert(alert);
  }, []);

  const handleCloseDetail = useCallback(() => {
    setSelectedAlert(null);
  }, []);

  // Severity filter
  const handleFilterChange = useCallback((level: AlertSeverity | 'all') => {
    setFilterLevel(level);
  }, []);

  // Calculate alert counts by severity
  const severityCounts = useMemo(() => {
    const counts = { critical: 0, high: 0, medium: 0, low: 0 };
    activeAlerts.forEach(alert => {
      const level = getPriorityLevel(alert.priority);
      counts[level]++;
    });
    return counts;
  }, [activeAlerts]);

  return (
    <div
      className={`alert-system ${className}`}
      data-theme={theme?.mode}
    >
      {/* Header */}
      <div className="alert-header">
        <h2 className="alert-title">Alerts</h2>
        <div className="alert-stats">
          {severityCounts.critical > 0 && (
            <span className="stat-badge critical">
              {severityCounts.critical} Critical
            </span>
          )}
          {severityCounts.high > 0 && (
            <span className="stat-badge high">
              {severityCounts.high} High
            </span>
          )}
          {severityCounts.medium > 0 && (
            <span className="stat-badge medium">
              {severityCounts.medium} Medium
            </span>
          )}
          {severityCounts.low > 0 && (
            <span className="stat-badge low">
              {severityCounts.low} Low
            </span>
          )}
        </div>
      </div>

      {/* Filter bar */}
      <div className="alert-filters">
        <FilterButton
          level="all"
          current={filterLevel}
          count={activeAlerts.length}
          onClick={handleFilterChange}
          theme={theme}
        />
        <FilterButton
          level="critical"
          current={filterLevel}
          count={severityCounts.critical}
          onClick={handleFilterChange}
          theme={theme}
        />
        <FilterButton
          level="high"
          current={filterLevel}
          count={severityCounts.high}
          onClick={handleFilterChange}
          theme={theme}
        />
        <FilterButton
          level="medium"
          current={filterLevel}
          count={severityCounts.medium}
          onClick={handleFilterChange}
          theme={theme}
        />
        <FilterButton
          level="low"
          current={filterLevel}
          count={severityCounts.low}
          onClick={handleFilterChange}
          theme={theme}
        />
      </div>

      {/* Alerts list */}
      <div className="alert-list" ref={scrollRef}>
        {filteredAlerts.length === 0 ? (
          <EmptyState message="No active alerts" />
        ) : (
          filteredAlerts.map(alert => (
            <AlertItem
              key={alert.id}
              alert={alert}
              theme={theme}
              onDismiss={allowDismiss ? handleDismiss : undefined}
              onClick={handleAlertClick}
              selected={selectedAlert?.id === alert.id}
            />
          ))
        )}
      </div>

      {/* Action buttons */}
      {allowDismiss && activeAlerts.length > 0 && (
        <div className="alert-actions">
          <button
            className="btn-clear-all"
            onClick={handleClearAll}
            style={{
              minHeight: theme?.touchTargets.minimum || '2.5rem',
            }}
          >
            ✕ Clear All
          </button>
        </div>
      )}

      {/* History section */}
      {showHistory && history.length > 0 && (
        <div className="alert-history">
          <h3 className="history-title">History</h3>
          <div className="history-list">
            {history.slice(0, 10).map(alert => (
              <HistoryItem
                key={alert.id}
                alert={alert}
                theme={theme}
              />
            ))}
          </div>
        </div>
      )}

      {/* Alert detail modal */}
      {selectedAlert && (
        <AlertDetailModal
          alert={selectedAlert}
          theme={theme}
          onClose={handleCloseDetail}
          onDismiss={allowDismiss ? handleDismiss : undefined}
        />
      )}
    </div>
  );
};

/**
 * AlertItem component
 */
interface AlertItemProps {
  alert: Alert;
  theme?: MarineTheme;
  onDismiss?: (alertId: string) => void;
  onClick?: (alert: Alert) => void;
  selected?: boolean;
}

const AlertItem: React.FC<AlertItemProps> = ({
  alert,
  theme,
  onDismiss,
  onClick,
  selected,
}) => {
  const level = getPriorityLevel(alert.priority);
  const color = getPriorityColor(alert.priority, theme);

  const handleClick = useCallback(() => {
    if (onClick) onClick(alert);
  }, [alert, onClick]);

  const handleDismiss = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    if (onDismiss) onDismiss(alert.id);
  }, [alert.id, onDismiss]);

  return (
    <div
      className={`alert-item priority-${level} ${selected ? 'selected' : ''}`}
      onClick={handleClick}
      style={{
        minHeight: theme?.touchTargets.minimum || '2.5rem',
        borderLeftColor: color,
      }}
    >
      {onDismiss && (
        <button
          className="btn-dismiss"
          onClick={handleDismiss}
          style={{
            width: theme?.touchTargets.minimum,
            height: theme?.touchTargets.minimum,
          }}
          aria-label="Dismiss alert"
        >
          ✕
        </button>
      )}

      <div className="alert-content">
        <div className="alert-header">
          <span className="alert-code">
            {alert.payload.code}
          </span>
          <span className="alert-time">
            {formatTimestamp(alert.timestamp_ns)}
          </span>
        </div>
        <div className="alert-message">
          {alert.payload.message}
        </div>
        {alert.reason && (
          <div className="alert-reason">
            {alert.reason}
          </div>
        )}
        <div
          className="alert-priority-bar"
          style={{
            width: `${alert.priority * 100}%`,
            backgroundColor: color,
          }}
        />
      </div>
    </div>
  );
};

/**
 * HistoryItem component
 */
interface HistoryItemProps {
  alert: Alert;
  theme?: MarineTheme;
}

const HistoryItem: React.FC<HistoryItemProps> = ({ alert, theme }) => {
  const level = getPriorityLevel(alert.priority);
  const color = getPriorityColor(alert.priority, theme);

  return (
    <div
      className={`history-item priority-${level}`}
      style={{
        borderLeftColor: color,
        minHeight: theme?.touchTargets.minimum || '2.5rem',
      }}
    >
      <span className="history-time">
        {formatTimestamp(alert.timestamp_ns)}
      </span>
      <span className="history-code">
        {alert.payload.code}
      </span>
      <span className="history-message">
        {alert.payload.message}
      </span>
    </div>
  );
};

/**
 * FilterButton component
 */
interface FilterButtonProps {
  level: AlertSeverity | 'all';
  current: AlertSeverity | 'all';
  count: number;
  onClick: (level: AlertSeverity | 'all') => void;
  theme?: MarineTheme;
}

const FilterButton: React.FC<FilterButtonProps> = ({
  level,
  current,
  count,
  onClick,
  theme,
}) => {
  const isActive = level === current;
  const color = level === 'all' ? undefined : getPriorityColor(
    level === 'critical' ? 0.9 :
    level === 'high' ? 0.7 :
    level === 'medium' ? 0.4 : 0.2,
    theme
  );

  const handleClick = useCallback(() => {
    onClick(level);
  }, [level, onClick]);

  return (
    <button
      className={`filter-btn ${isActive ? 'active' : ''} priority-${level}`}
      onClick={handleClick}
      style={{
        minHeight: theme?.touchTargets.minimum || '2.5rem',
        ...(isActive && color ? { borderColor: color, color } : {}),
      }}
    >
      {level === 'all' ? 'All' : level.charAt(0).toUpperCase() + level.slice(1)}
      {count > 0 && <span className="count">{count}</span>}
    </button>
  );
};

/**
 * EmptyState component
 */
interface EmptyStateProps {
  message: string;
}

const EmptyState: React.FC<EmptyStateProps> = ({ message }) => (
  <div className="empty-state">
    <div className="empty-icon">✓</div>
    <div className="empty-message">{message}</div>
  </div>
);

/**
 * AlertDetailModal component
 */
interface AlertDetailModalProps {
  alert: Alert;
  theme?: MarineTheme;
  onClose: () => void;
  onDismiss?: (alertId: string) => void;
}

const AlertDetailModal: React.FC<AlertDetailModalProps> = ({
  alert,
  theme,
  onClose,
  onDismiss,
}) => {
  const handleDismiss = useCallback(() => {
    if (onDismiss) onDismiss(alert.id);
    onClose();
  }, [alert.id, onDismiss, onClose]);

  const handleBackdropClick = useCallback((e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  }, [onClose]);

  return (
    <div className="alert-modal-backdrop" onClick={handleBackdropClick}>
      <div className="alert-modal-content" style={{ background: theme?.colors.surface }}>
        <div className="modal-header">
          <h3>{alert.payload.code}</h3>
          <button
            className="btn-close"
            onClick={onClose}
            style={{
              width: theme?.touchTargets.minimum,
              height: theme?.touchTargets.minimum,
            }}
          >
            ✕
          </button>
        </div>
        <div className="modal-body">
          <div className="detail-row">
            <span className="detail-label">Severity:</span>
            <span className="detail-value">{alert.payload.severity}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Priority:</span>
            <span className="detail-value">{(alert.priority * 100).toFixed(0)}%</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Time:</span>
            <span className="detail-value">{formatTimestamp(alert.timestamp_ns)}</span>
          </div>
          {alert.reason && (
            <div className="detail-row">
              <span className="detail-label">Reason:</span>
              <span className="detail-value">{alert.reason}</span>
            </div>
          )}
          <div className="detail-message">
            {alert.payload.message}
          </div>
          {alert.payload.details && (
            <div className="detail-details">
              <h4>Details</h4>
              <pre>{JSON.stringify(alert.payload.details, null, 2)}</pre>
            </div>
          )}
        </div>
        <div className="modal-actions">
          {onDismiss && (
            <button
              className="btn-dismiss-confirm"
              onClick={handleDismiss}
              style={{
                minHeight: theme?.touchTargets.comfortable || '3rem',
              }}
            >
              Dismiss Alert
            </button>
          )}
          <button
            className="btn-close-modal"
            onClick={onClose}
            style={{
              minHeight: theme?.touchTargets.comfortable || '3rem',
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default AlertSystem;
