/**
 * NMEAStream - Real-time NMEA sentence display
 * Shows incoming NMEA sentences with filtering and highlighting
 */

import React, { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import { NMEASentence } from '../types/vessel';
import { MarineTheme } from '../types/theme';
import './NMEAStream.css';

export interface NMEAStreamProps {
  sentences: NMEASentence[];
  maxVisible?: number;
  filterTypes?: string[];
  highlightRules?: RegExp[];
  theme?: MarineTheme;
  className?: string;
  onSentenceClick?: (sentence: NMEASentence) => void;
  autoScroll?: boolean;
  showTimestamp?: boolean;
  showChecksum?: boolean;
  compact?: boolean;
}

interface NMEAStreamState {
  selectedSentence: NMEASentence | null;
  hoveredSentence: NMEASentence | null;
  filter: string;
  autoScroll: boolean;
  showParsed: boolean;
}

/**
 * NMEAStream component
 */
export const NMEAStream: React.FC<NMEAStreamProps> = ({
  sentences,
  maxVisible = 100,
  filterTypes = [],
  highlightRules = [],
  theme,
  className = '',
  onSentenceClick,
  autoScroll: autoScrollProp = true,
  showTimestamp = true,
  showChecksum = true,
  compact = false,
}) => {
  const [state, setState] = useState<NMEAStreamState>({
    selectedSentence: null,
    hoveredSentence: null,
    filter: '',
    autoScroll: autoScrollProp,
    showParsed: false,
  });

  const containerRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  /**
   * Filter sentences by type and search filter
   */
  const filteredSentences = useMemo(() => {
    let filtered = sentences;

    // Filter by type
    if (filterTypes.length > 0) {
      filtered = filtered.filter(s => filterTypes.includes(s.type));
    }

    // Filter by search
    if (state.filter) {
      const searchLower = state.filter.toLowerCase();
      filtered = filtered.filter(s =>
        s.type.toLowerCase().includes(searchLower) ||
        s.raw.toLowerCase().includes(searchLower)
      );
    }

    // Limit visible
    return filtered.slice(-maxVisible);
  }, [sentences, filterTypes, state.filter, maxVisible]);

  /**
   * Get sentence color based on type and validation
   */
  const getSentenceColor = useCallback((sentence: NMEASentence): string => {
    if (!sentence.valid || sentence.checksum_valid === false) {
      return theme?.colors.error || '#e04b4b';
    }

    // Type-based coloring
    const typeColors: Record<string, string> = {
      'GPGGA': theme?.colors.success || '#35e08a',
      'GPGSA': theme?.colors.info || '#6f93b3',
      'GPGSV': theme?.colors.primary || '#1c5f8a',
      'GPRMC': theme?.colors.success || '#35e08a',
      'GPVTG': theme?.colors.info || '#6f93b3',
      'GPGLL': theme?.colors.success || '#35e08a',
      'GPZDA': theme?.colors.info || '#6f93b3',
    };

    return typeColors[sentence.type] || theme?.colors.textSecondary || '#555555';
  }, [theme]);

  /**
   * Check if sentence matches any highlight rule
   */
  const isHighlighted = useCallback((sentence: NMEASentence): boolean => {
    return highlightRules.some(rule => rule.test(sentence.raw));
  }, [highlightRules]);

  /**
   * Handle sentence click
   */
  const handleSentenceClick = useCallback((sentence: NMEASentence) => {
    setState(prev => ({
      ...prev,
      selectedSentence: prev.selectedSentence === sentence ? null : sentence,
    }));

    if (onSentenceClick) {
      onSentenceClick(sentence);
    }
  }, [onSentenceClick]);

  /**
   * Handle sentence hover
   */
  const handleSentenceHover = useCallback((sentence: NMEASentence | null) => {
    setState(prev => ({ ...prev, hoveredSentence: sentence }));
  }, []);

  /**
   * Handle filter change
   */
  const handleFilterChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setState(prev => ({ ...prev, filter: e.target.value }));
  }, []);

  /**
   * Toggle auto-scroll
   */
  const handleToggleAutoScroll = useCallback(() => {
    setState(prev => ({ ...prev, autoScroll: !prev.autoScroll }));
  }, []);

  /**
   * Toggle parsed view
   */
  const handleToggleParsed = useCallback(() => {
    setState(prev => ({ ...prev, showParsed: !prev.showParsed }));
  }, []);

  /**
   * Clear selection
   */
  const handleClearSelection = useCallback(() => {
    setState(prev => ({ ...prev, selectedSentence: null }));
  }, []);

  /**
   * Auto-scroll to bottom
   */
  useEffect(() => {
    if (state.autoScroll && endRef.current) {
      endRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [filteredSentences, state.autoScroll]);

  /**
   * Get unique sentence types for filter
   */
  const availableTypes = useMemo(() => {
    const types = new Set(sentences.map(s => s.type));
    return Array.from(types).sort();
  }, [sentences]);

  /**
   * Format timestamp for display
   */
  const formatTimestamp = useCallback((ns: bigint): string => {
    const s = Math.floor(Number(ns) / 1e9);
    const date = new Date(s * 1000);
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      fractionalSecondDigits: 3,
    });
  }, []);

  return (
    <div
      className={`nmea-stream ${compact ? 'compact' : ''} ${className}`}
      data-theme={theme?.mode}
    >
      {/* Header */}
      <div className="nmea-header">
        <h3 className="nmea-title">NMEA Stream</h3>
        <div className="nmea-stats">
          <span className="nmea-stat">
            {filteredSentences.length} / {sentences.length}
          </span>
        </div>
      </div>

      {/* Controls */}
      <div className="nmea-controls">
        <input
          type="text"
          placeholder="Filter sentences..."
          value={state.filter}
          onChange={handleFilterChange}
          className="nmea-filter"
          style={{
            minHeight: theme?.touchTargets.minimum || '2.5rem',
          }}
        />

        <button
          onClick={handleToggleAutoScroll}
          className={`nmea-btn ${state.autoScroll ? 'active' : ''}`}
          style={{ minHeight: theme?.touchTargets.minimum || '2.5rem' }}
          title={state.autoScroll ? 'Auto-scroll on' : 'Auto-scroll off'}
        >
          {state.autoScroll ? '⏬' : '⏹'}
        </button>

        <button
          onClick={handleToggleParsed}
          className={`nmea-btn ${state.showParsed ? 'active' : ''}`}
          style={{ minHeight: theme?.touchTargets.minimum || '2.5rem' }}
          title="Toggle parsed data"
        >
          {state.showParsed ? '{ }' : '{ }'}
        </button>

        {state.selectedSentence && (
          <button
            onClick={handleClearSelection}
            className="nmea-btn"
            style={{ minHeight: theme?.touchTargets.minimum || '2.5rem' }}
            title="Clear selection"
          >
            ✕
          </button>
        )}
      </div>

      {/* Type filter chips */}
      {availableTypes.length > 0 && (
        <div className="nmea-types">
          {availableTypes.map(type => (
            <button
              key={type}
              onClick={() => setState(prev => ({
                ...prev,
                filter: filterTypes.includes(type)
                  ? prev.filter.replace(type, '').trim()
                  : `${prev.filter} ${type}`.trim()
              }))}
              className={`type-chip ${filterTypes.includes(type) ? 'active' : ''}`}
              style={{
                minHeight: theme?.touchTargets.minimum || '2.5rem',
                border: filterTypes.includes(type)
                  ? `2px solid ${getSentenceColor({ type, raw: '', timestamp_ns: 0n, valid: true })}`
                  : undefined,
              }}
            >
              {type}
            </button>
          ))}
        </div>
      )}

      {/* Sentences list */}
      <div className="nmea-list" ref={containerRef}>
        {filteredSentences.length === 0 ? (
          <div className="nmea-empty">
            {sentences.length === 0 ? 'Waiting for NMEA data...' : 'No sentences match filter'}
          </div>
        ) : (
          filteredSentences.map((sentence, index) => (
            <NMEASentenceItem
              key={`${sentence.timestamp_ns}-${index}`}
              sentence={sentence}
              color={getSentenceColor(sentence)}
              highlighted={isHighlighted(sentence)}
              selected={state.selectedSentence === sentence}
              hovered={state.hoveredSentence === sentence}
              showTimestamp={showTimestamp}
              showChecksum={showChecksum}
              showParsed={state.showParsed}
              onClick={handleSentenceClick}
              onHover={handleSentenceHover}
              theme={theme}
              formatTimestamp={formatTimestamp}
            />
          ))
        )}
        <div ref={endRef} />
      </div>

      {/* Sentence detail modal */}
      {state.selectedSentence && (
        <NMEADetailModal
          sentence={state.selectedSentence}
          theme={theme}
          onClose={handleClearSelection}
          formatTimestamp={formatTimestamp}
        />
      )}
    </div>
  );
};

/**
 * NMEA sentence item component
 */
interface NMEASentenceItemProps {
  sentence: NMEASentence;
  color: string;
  highlighted: boolean;
  selected: boolean;
  hovered: boolean;
  showTimestamp: boolean;
  showChecksum: boolean;
  showParsed: boolean;
  onClick: (sentence: NMEASentence) => void;
  onHover: (sentence: NMEASentence | null) => void;
  theme?: MarineTheme;
  formatTimestamp: (ns: bigint) => string;
}

const NMEASentenceItem: React.FC<NMEASentenceItemProps> = ({
  sentence,
  color,
  highlighted,
  selected,
  hovered,
  showTimestamp,
  showChecksum,
  showParsed,
  onClick,
  onHover,
  theme,
  formatTimestamp,
}) => {
  const handleClick = useCallback(() => {
    onClick(sentence);
  }, [sentence, onClick]);

  const handleMouseEnter = useCallback(() => {
    onHover(sentence);
  }, [sentence, onHover]);

  const handleMouseLeave = useCallback(() => {
    onHover(null);
  }, [onHover]);

  return (
    <div
      className={`nmea-item ${selected ? 'selected' : ''} ${highlighted ? 'highlighted' : ''} ${!sentence.valid ? 'invalid' : ''}`}
      onClick={handleClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      style={{
        borderLeftColor: color,
        minHeight: theme?.touchTargets.minimum || '2.5rem',
      }}
    >
      {/* Type badge */}
      <div className="nmea-type" style={{ color }}>
        {sentence.type}
      </div>

      {/* Timestamp */}
      {showTimestamp && (
        <div className="nmea-time">
          {formatTimestamp(sentence.timestamp_ns)}
        </div>
      )}

      {/* Raw sentence */}
      <div className="nmea-raw">
        {sentence.raw}
      </div>

      {/* Checksum status */}
      {showChecksum && (
        <div className={`nmea-checksum ${sentence.checksum_valid ? 'valid' : 'invalid'}`}>
          {sentence.checksum_valid ? '✓' : '✗'}
        </div>
      )}

      {/* Parsed data */}
      {showParsed && sentence.parsed && (
        <div className="nmea-parsed">
          {Object.entries(sentence.parsed).map(([key, value]) => (
            <span key={key} className="parsed-item">
              <span className="parsed-key">{key}:</span>
              <span className="parsed-value">{String(value)}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
};

/**
 * NMEA detail modal
 */
interface NMEADetailModalProps {
  sentence: NMEASentence;
  theme?: MarineTheme;
  onClose: () => void;
  formatTimestamp: (ns: bigint) => string;
}

const NMEADetailModal: React.FC<NMEADetailModalProps> = ({
  sentence,
  theme,
  onClose,
  formatTimestamp,
}) => {
  const handleBackdropClick = useCallback((e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  }, [onClose]);

  return (
    <div className="nmea-modal-backdrop" onClick={handleBackdropClick}>
      <div className="nmea-modal-content" style={{ background: theme?.colors.surface }}>
        <div className="modal-header">
          <h3>{sentence.type}</h3>
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
            <span className="detail-label">Time:</span>
            <span className="detail-value">{formatTimestamp(sentence.timestamp_ns)}</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Valid:</span>
            <span className={`detail-value ${sentence.valid ? 'valid' : 'invalid'}`}>
              {sentence.valid ? 'Yes' : 'No'}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Checksum:</span>
            <span className={`detail-value ${sentence.checksum_valid ? 'valid' : 'invalid'}`}>
              {sentence.checksum_valid ? 'Valid' : 'Invalid'}
            </span>
          </div>
          <div className="detail-section">
            <h4>Raw Sentence</h4>
            <pre className="nmea-raw-display">{sentence.raw}</pre>
          </div>
          {sentence.parsed && (
            <div className="detail-section">
              <h4>Parsed Data</h4>
              <div className="parsed-data">
                {Object.entries(sentence.parsed).map(([key, value]) => (
                  <div key={key} className="parsed-row">
                    <span className="parsed-key">{key}:</span>
                    <span className="parsed-value">{String(value)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default NMEAStream;
