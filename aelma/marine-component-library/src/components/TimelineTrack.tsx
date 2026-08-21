/**
 * TimelineTrack - DAW-style timeline component for event playback
 * Touch-optimized with pinch zoom, pan, and event selection
 */

import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import { TimelineEvent } from '../types/vessel';
import { MarineTheme } from '../types/theme';
import './TimelineTrack.css';

export interface TimelineTrackProps {
  events: TimelineEvent[];
  duration: number; // seconds
  currentTime: number;
  onSeek?: (time: number) => void;
  zoom?: number;
  onZoom?: (zoom: number) => void;
  theme?: MarineTheme;
  className?: string;
  showTimeScale?: boolean;
  showWaveform?: boolean;
  allowCreateEvent?: boolean;
  onCreateEvent?: (time: number, type: string) => void;
}

interface TimelineTrackState {
  scale: number; // pixels per second
  scrollOffset: number; // pixels
  isDragging: boolean;
  dragStartX: number;
  dragStartScroll: number;
  selectedEvent: string | null;
  isZooming: boolean;
  zoomStartDistance: number;
  zoomStartScale: number;
  currentTimeMarker: number;
}

const ZOOM_MIN = 10; // 10 pixels per second
const ZOOM_MAX = 500; // 500 pixels per second

/**
 * TimelineTrack component
 */
export const TimelineTrack: React.FC<TimelineTrackProps> = ({
  events,
      duration,
  currentTime,
  onSeek,
  zoom = 100,
  onZoom,
  theme,
  className = '',
  showTimeScale = true,
  showWaveform = false,
  allowCreateEvent = false,
  onCreateEvent,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const eventsRef = useRef<HTMLDivElement>(null);

  const [state, setState] = useState<TimelineTrackState>({
    scale: zoom,
    scrollOffset: 0,
    isDragging: false,
    dragStartX: 0,
    dragStartScroll: 0,
    selectedEvent: null,
    isZooming: false,
    zoomStartDistance: 0,
    zoomStartScale: zoom,
    currentTimeMarker: currentTime,
  });

  const { scale, scrollOffset, isDragging, selectedEvent } = state;

  /**
   * Format time for display
   */
  const formatTime = useCallback((seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 100);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
  }, []);

  /**
   * Convert time to X position
   */
  const timeToX = useCallback((time: number): number => {
    return time * scale;
  }, [scale]);

  /**
   * Convert X position to time
   */
  const xToTime = useCallback((x: number): number => {
    return x / scale;
  }, [scale]);

  /**
   * Calculate total timeline width
   */
  const timelineWidth = useMemo(() => {
    return duration * scale;
  }, [duration, scale]);

  /**
   * Handle wheel for zooming
   */
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();

    const delta = e.deltaY;
    const newScale = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, scale - delta * 0.1));

    setState(prev => ({
      ...prev,
      scale: newScale,
    }));

    if (onZoom) {
      onZoom(newScale);
    }
  }, [scale, onZoom]);

  /**
   * Handle pointer down for dragging/seeking
   */
  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    if (!containerRef.current) return;

    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left + scrollOffset;

    setState(prev => ({
      ...prev,
      isDragging: true,
      dragStartX: e.clientX,
      dragStartScroll: scrollOffset,
      currentTimeMarker: xToTime(x),
    }));

    containerRef.current.setPointerCapture(e.pointerId);
  }, [scrollOffset, xToTime]);

  /**
   * Handle pointer move for dragging
   */
  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!isDragging) return;

    const deltaX = e.clientX - state.dragStartX;
    const newScrollOffset = Math.max(0, Math.min(timelineWidth - (containerRef.current?.clientWidth || 0), state.dragStartScroll - deltaX));

    setState(prev => ({
      ...prev,
      scrollOffset: newScrollOffset,
      currentTimeMarker: xToTime(e.clientX - (containerRef.current?.getBoundingClientRect().left || 0) + newScrollOffset),
    }));
  }, [isDragging, state.dragStartX, state.dragStartScroll, timelineWidth, xToTime]);

  /**
   * Handle pointer up to seek
   */
  const handlePointerUp = useCallback((e: React.PointerEvent) => {
    if (!isDragging) return;

    const seekTime = Math.max(0, Math.min(duration, state.currentTimeMarker));

    setState(prev => ({
      ...prev,
      isDragging: false,
    }));

    if (onSeek) {
      onSeek(seekTime);
    }

    if (containerRef.current) {
      containerRef.current.releasePointerCapture(e.pointerId);
    }
  }, [isDragging, state.currentTimeMarker, duration, onSeek]);

  /**
   * Handle touch start for pinch zoom
   */
  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    if (e.touches.length === 2) {
      const touch1 = e.touches[0];
      const touch2 = e.touches[1];
      const distance = Math.hypot(touch2.clientX - touch1.clientX, touch2.clientY - touch1.clientY);

      setState(prev => ({
        ...prev,
        isZooming: true,
        zoomStartDistance: distance,
        zoomStartScale: prev.scale,
      }));
    }
  }, []);

  /**
   * Handle touch move for pinch zoom
   */
  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    if (state.isZooming && e.touches.length === 2) {
      e.preventDefault();

      const touch1 = e.touches[0];
      const touch2 = e.touches[1];
      const distance = Math.hypot(touch2.clientX - touch1.clientX, touch2.clientY - touch1.clientY);

      const scaleRatio = distance / state.zoomStartDistance;
      const newScale = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, state.zoomStartScale * scaleRatio));

      setState(prev => ({
        ...prev,
        scale: newScale,
      }));

      if (onZoom) {
        onZoom(newScale);
      }
    }
  }, [state.isZooming, state.zoomStartDistance, state.zoomStartScale, onZoom]);

  /**
   * Handle touch end
   */
  const handleTouchEnd = useCallback(() => {
    setState(prev => ({
      ...prev,
      isZooming: false,
    }));
  }, []);

  /**
   * Handle event click
   */
  const handleEventClick = useCallback((event: TimelineEvent) => {
    setState(prev => ({
      ...prev,
      selectedEvent: event.id === prev.selectedEvent ? null : event.id,
    }));

    if (onSeek) {
      onSeek(event.timestamp);
    }
  }, [onSeek]);

  /**
   * Handle double-click to create event
   */
  const handleDoubleClick = useCallback((e: React.MouseEvent) => {
    if (!allowCreateEvent || !containerRef.current) return;

    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left + scrollOffset;
    const time = xToTime(x);

    if (onCreateEvent) {
      onCreateEvent(time, 'waypoint');
    }
  }, [allowCreateEvent, scrollOffset, xToTime, onCreateEvent]);

  /**
   * Render time scale marks
   */
  const renderTimeScale = useCallback(() => {
    const marks: JSX.Element[] = [];
    const interval = scale < 50 ? 10 : scale < 100 ? 5 : scale < 200 ? 2 : 1;

    for (let time = 0; time <= duration; time += interval) {
      const x = timeToX(time);
      if (x < scrollOffset - 50 || x > scrollOffset + (containerRef.current?.clientWidth || 0) + 50) continue;

      marks.push(
        <div
          key={time}
          className="timeline-mark"
          style={{ left: `${x - scrollOffset}px` }}
        >
          <span className="mark-label">{formatTime(time)}</span>
        </div>
      );
    }

    return marks;
  }, [duration, scale, scrollOffset, timeToX, formatTime]);

  /**
   * Render events
   */
  const renderEvents = useCallback(() => {
    return events.map(event => {
      const x = timeToX(event.timestamp);
      const width = event.duration ? timeToX(event.timestamp + event.duration) - x : 8;

      if (x < scrollOffset - 100 || x > scrollOffset + (containerRef.current?.clientWidth || 0) + 100) {
        return null;
      }

      return (
        <div
          key={event.id}
          className={`timeline-event ${event.type} ${selectedEvent === event.id ? 'selected' : ''}`}
          style={{
            left: `${x - scrollOffset}px`,
            width: `${width}px`,
            backgroundColor: event.color,
            minHeight: theme?.touchTargets.minimum || '2.5rem',
          }}
          onClick={() => handleEventClick(event)}
        >
          <span className="event-label">{event.label}</span>
        </div>
      );
    });
  }, [events, scale, scrollOffset, selectedEvent, timeToX, handleEventClick, theme]);

  /**
   * Update scroll offset when currentTime changes externally
   */
  useEffect(() => {
    const currentTimeX = timeToX(currentTime);

    if (containerRef.current) {
      const containerWidth = containerRef.current.clientWidth;
      const padding = 100;

      if (currentTimeX < scrollOffset + padding) {
        setState(prev => ({ ...prev, scrollOffset: Math.max(0, currentTimeX - padding) }));
      } else if (currentTimeX > scrollOffset + containerWidth - padding) {
        setState(prev => ({ ...prev, scrollOffset: Math.min(timelineWidth - containerWidth, currentTimeX - containerWidth + padding) }));
      }
    }
  }, [currentTime, timeToX, timelineWidth]);

  /**
   * Update scale when zoom prop changes
   */
  useEffect(() => {
    setState(prev => ({ ...prev, scale: zoom }));
  }, [zoom]);

  return (
    <div
      ref={containerRef}
      className={`timeline-track ${className}`}
      onWheel={handleWheel}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      onDoubleClick={handleDoubleClick}
      style={{
        '--timeline-width': `${timelineWidth}px`,
        touchAction: 'none',
      } as React.CSSProperties}
    >
      {/* Time scale */}
      {showTimeScale && (
        <div className="timeline-scale">
          {renderTimeScale()}
        </div>
      )}

      {/* Events container */}
      <div
        ref={eventsRef}
        className="timeline-events"
        style={{
          width: `${timelineWidth}px`,
        }}
      >
        {renderEvents()}
      </div>

      {/* Current time marker */}
      <div
        className="timeline-cursor"
        style={{
          left: `${timeToX(currentTime) - scrollOffset}px`,
        }}
      >
        <div className="cursor-head" />
      </div>

      {/* Background waveform visualization */}
      {showWaveform && (
        <canvas
          ref={canvasRef}
          className="timeline-waveform"
          width={timelineWidth}
          height={60}
          style={{
            left: `-${scrollOffset}px`,
          }}
        />
      )}

      {/* Zoom indicator */}
      {state.isZooming && (
        <div className="zoom-indicator">
          {Math.round(scale)} px/s
        </div>
      )}
    </div>
  );
};

export default TimelineTrack;
