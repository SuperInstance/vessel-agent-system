/**
 * BathymetryViewer - Depth heatmap visualization
 * Shows bathymetry data with interactive controls
 */

import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import { BathymetryData, BathymetryCell, BathymetryColor } from '../types/vessel';
import { MarineTheme } from '../types/theme';
import './BathymetryViewer.css';

export interface BathymetryViewerProps {
  data: BathymetryData;
  colorScheme?: BathymetryColor;
  pointSize?: number;
  showColorScale?: boolean;
  theme?: MarineTheme;
  className?: string;
  onPointClick?: (cell: BathymetryCell) => void;
  onPointHover?: (cell: BathymetryCell | null) => void;
  allowSelection?: boolean;
  showStats?: boolean;
}

const DEFAULT_COLOR_SCHEME: BathymetryColor = {
  shallow_depth: 30,
  deep_depth: 80,
  shallow_color: 0xff9a3c,
  mid_color: 0x3fd68c,
  deep_color: 0x2f6fd0,
};

interface BathymetryViewerState {
  hoveredCell: BathymetryCell | null;
  selectedCells: Set<string>;
  zoom: number;
  panX: number;
  panY: number;
  isDragging: boolean;
  dragStartX: number;
  dragStartY: number;
  dragStartPanX: number;
  dragStartPanY: number;
  showLabels: boolean;
  showGrid: boolean;
}

/**
 * BathymetryViewer component
 */
export const BathymetryViewer: React.FC<BathymetryViewerProps> = ({
  data,
  colorScheme = DEFAULT_COLOR_SCHEME,
  pointSize = 3,
  showColorScale = true,
  theme,
  className = '',
  onPointClick,
  onPointHover,
  allowSelection = true,
  showStats = true,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const [state, setState] = useState<BathymetryViewerState>({
    hoveredCell: null,
    selectedCells: new Set(),
    zoom: 1,
    panX: 0,
    panY: 0,
    isDragging: false,
    dragStartX: 0,
    dragStartY: 0,
    dragStartPanX: 0,
    dragStartPanY: 0,
    showLabels: false,
    showGrid: false,
  });

  /**
   * Get color for depth
   */
  const getDepthColor = useCallback((depth: number): string => {
    const { shallow_depth, deep_depth, shallow_color, mid_color, deep_color } = colorScheme;

    let color: number;
    if (depth < shallow_depth) {
      color = shallow_color;
    } else if (depth <= deep_depth) {
      // Interpolate between mid and deep
      const t = (depth - shallow_depth) / (deep_depth - shallow_depth);
      const midRgb = hexToRgb(mid_color);
      const deepRgb = hexToRgb(deep_color);
      color = rgbToHex(
        Math.round(midRgb.r + (deepRgb.r - midRgb.r) * t),
        Math.round(midRgb.g + (deepRgb.g - midRgb.g) * t),
        Math.round(midRgb.b + (deepRgb.b - midRgb.b) * t)
      );
    } else {
      color = deep_color;
    }

    return `#${color.toString(16).padStart(6, '0')}`;
  }, [colorScheme]);

  /**
   * Calculate data bounds
   */
  const bounds = useMemo(() => {
    if (!data.cells || data.cells.length === 0) {
      return { minLat: 0, maxLat: 0, minLon: 0, maxLon: 0, minDepth: 0, maxDepth: 0 };
    }

    let minLat = Infinity, maxLat = -Infinity;
    let minLon = Infinity, maxLon = -Infinity;
    let minDepth = Infinity, maxDepth = -Infinity;

    for (const cell of data.cells) {
      minLat = Math.min(minLat, cell.lat);
      maxLat = Math.max(maxLat, cell.lat);
      minLon = Math.min(minLon, cell.lon);
      maxLon = Math.max(maxLon, cell.lon);
      minDepth = Math.min(minDepth, cell.depth);
      maxDepth = Math.max(maxDepth, cell.depth);
    }

    return { minLat, maxLat, minLon, maxLon, minDepth, maxDepth };
  }, [data]);

  /**
   * Render canvas
   */
  const renderCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx || !data.cells) return;

    const width = canvas.width;
    const height = canvas.height;

    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    // Calculate scale
    const latRange = bounds.maxLat - bounds.minLat || 1;
    const lonRange = bounds.maxLon - bounds.minLon || 1;
    const scale = Math.min(width / lonRange, height / latRange) * state.zoom;

    // Apply pan
    ctx.save();
    ctx.translate(state.panX, state.panY);

    // Draw grid if enabled
    if (state.showGrid) {
      ctx.strokeStyle = theme?.colors.divider || '#e0e0e0';
      ctx.lineWidth = 1;

      const gridSpacing = 0.001; // ~100m at equator
      for (let lat = Math.floor(bounds.minLat / gridSpacing) * gridSpacing; lat <= bounds.maxLat; lat += gridSpacing) {
        const y = height - ((lat - bounds.minLat) / latRange) * (height / scale) * scale;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }
      for (let lon = Math.floor(bounds.minLon / gridSpacing) * gridSpacing; lon <= bounds.maxLon; lon += gridSpacing) {
        const x = ((lon - bounds.minLon) / lonRange) * (width / scale) * scale;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
    }

    // Draw bathymetry points
    for (const cell of data.cells) {
      const x = ((cell.lon - bounds.minLon) / lonRange) * (width / scale) * scale;
      const y = height - ((cell.lat - bounds.minLat) / latRange) * (height / scale) * scale;

      // Skip if out of bounds
      if (x < -10 || x > width + 10 || y < -10 || y > height + 10) continue;

      // Draw point
      const color = getDepthColor(cell.depth);
      const alpha = Math.min(1, Math.max(0.1, cell.confidence));
      const size = pointSize * state.zoom;

      ctx.globalAlpha = alpha;
      ctx.fillStyle = color;

      // Highlight if hovered or selected
      const cellId = `${cell.lat.toFixed(6)}_${cell.lon.toFixed(6)}`;
      if (state.hoveredCell === cell || state.selectedCells.has(cellId)) {
        ctx.beginPath();
        ctx.arc(x, y, size * 1.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = theme?.colors.text || '#1a1a1a';
        ctx.lineWidth = 1;
        ctx.stroke();
      } else {
        ctx.beginPath();
        ctx.arc(x, y, size, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    ctx.restore();
  }, [data, bounds, state, pointSize, getDepthColor, theme]);

  /**
   * Handle canvas click
   */
  const handleCanvasClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!allowSelection || !data.cells || !canvasRef.current) return;

    const rect = canvasRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left - state.panX) / state.zoom;
    const y = (e.clientY - rect.top - state.panY) / state.zoom;

    const width = canvasRef.current.width;
    const height = canvasRef.current.height;

    const latRange = bounds.maxLat - bounds.minLat || 1;
    const lonRange = bounds.maxLon - bounds.minLon || 1;

    // Find clicked cell
    for (const cell of data.cells) {
      const cellX = ((cell.lon - bounds.minLon) / lonRange) * width;
      const cellY = height - ((cell.lat - bounds.minLat) / latRange) * height;

      const distance = Math.hypot(cellX - x, cellY - y);
      if (distance < 5 * state.zoom) {
        const cellId = `${cell.lat.toFixed(6)}_${cell.lon.toFixed(6)}`;

        setState(prev => {
          const newSelected = new Set(prev.selectedCells);
          if (newSelected.has(cellId)) {
            newSelected.delete(cellId);
          } else {
            newSelected.add(cellId);
          }
          return { ...prev, selectedCells: newSelected };
        });

        if (onPointClick) {
          onPointClick(cell);
        }
        break;
      }
    }
  }, [allowSelection, data.cells, state, bounds, onPointClick]);

  /**
   * Handle canvas hover
   */
  const handleCanvasHover = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!data.cells || !canvasRef.current) return;

    const rect = canvasRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left - state.panX) / state.zoom;
    const y = (e.clientY - rect.top - state.panY) / state.zoom;

    const width = canvasRef.current.width;
    const height = canvasRef.current.height;

    const latRange = bounds.maxLat - bounds.minLat || 1;
    const lonRange = bounds.maxLon - bounds.minLon || 1;

    // Find hovered cell
    let foundCell: BathymetryCell | null = null;
    for (const cell of data.cells) {
      const cellX = ((cell.lon - bounds.minLon) / lonRange) * width;
      const cellY = height - ((cell.lat - bounds.minLat) / latRange) * height;

      const distance = Math.hypot(cellX - x, cellY - y);
      if (distance < 5 * state.zoom) {
        foundCell = cell;
        break;
      }
    }

    setState(prev => ({ ...prev, hoveredCell: foundCell }));

    if (onPointHover) {
      onPointHover(foundCell);
    }
  }, [data.cells, state, bounds, onPointHover]);

  /**
   * Handle wheel for zoom
   */
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();

    const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
    const newZoom = Math.max(0.5, Math.min(10, state.zoom * zoomFactor));

    setState(prev => ({ ...prev, zoom: newZoom }));
  }, [state.zoom]);

  /**
   * Handle pan start
   */
  const handlePanStart = useCallback((e: React.PointerEvent) => {
    setState(prev => ({
      ...prev,
      isDragging: true,
      dragStartX: e.clientX,
      dragStartY: e.clientY,
      dragStartPanX: prev.panX,
      dragStartPanY: prev.panY,
    }));

    if (containerRef.current) {
      containerRef.current.setPointerCapture(e.pointerId);
    }
  }, []);

  /**
   * Handle pan move
   */
  const handlePanMove = useCallback((e: React.PointerEvent) => {
    if (!state.isDragging) return;

    const deltaX = e.clientX - state.dragStartX;
    const deltaY = e.clientY - state.dragStartY;

    setState(prev => ({
      ...prev,
      panX: prev.dragStartPanX + deltaX,
      panY: prev.dragStartPanY + deltaY,
    }));
  }, [state]);

  /**
   * Handle pan end
   */
  const handlePanEnd = useCallback((e: React.PointerEvent) => {
    setState(prev => ({ ...prev, isDragging: false }));

    if (containerRef.current) {
      containerRef.current.releasePointerCapture(e.pointerId);
    }
  }, []);

  /**
   * Reset view
   */
  const handleReset = useCallback(() => {
    setState(prev => ({
      ...prev,
      zoom: 1,
      panX: 0,
      panY: 0,
    }));
  }, []);

  /**
   * Toggle labels
   */
  const handleToggleLabels = useCallback(() => {
    setState(prev => ({ ...prev, showLabels: !prev.showLabels }));
  }, []);

  /**
   * Toggle grid
   */
  const handleToggleGrid = useCallback(() => {
    setState(prev => ({ ...prev, showGrid: !prev.showGrid }));
  }, []);

  /**
   * Render canvas on state change
   */
  useEffect(() => {
    renderCanvas();
  }, [renderCanvas]);

  /**
   * Handle canvas resize
   */
  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const resizeObserver = new ResizeObserver(() => {
      canvas.width = container.clientWidth;
      canvas.height = container.clientHeight;
      renderCanvas();
    });

    resizeObserver.observe(container);

    return () => resizeObserver.disconnect();
  }, [renderCanvas]);

  const selectedCellsArray = Array.from(state.selectedCells);

  return (
    <div
      ref={containerRef}
      className={`bathymetry-viewer ${className}`}
      data-theme={theme?.mode}
    >
      {/* Controls toolbar */}
      <div className="bathy-controls">
        <button
          onClick={handleReset}
          style={{ minHeight: theme?.touchTargets.minimum || '2.5rem' }}
          title="Reset view"
        >
          ⟲ Reset
        </button>
        <button
          onClick={handleToggleLabels}
          style={{ minHeight: theme?.touchTargets.minimum || '2.5rem' }}
          title="Toggle depth labels"
        >
          {state.showLabels ? '🏷' : '🏷️'} Labels
        </button>
        <button
          onClick={handleToggleGrid}
          style={{ minHeight: theme?.touchTargets.minimum || '2.5rem' }}
          title="Toggle grid"
        >
          {state.showGrid ? '▦' : '▥'} Grid
        </button>
      </div>

      {/* Canvas */}
      <canvas
        ref={canvasRef}
        className="bathy-canvas"
        onClick={handleCanvasClick}
        onMouseMove={handleCanvasHover}
        onMouseLeave={() => setState(prev => ({ ...prev, hoveredCell: null }))}
        onWheel={handleWheel}
        onPointerDown={handlePanStart}
        onPointerMove={handlePanMove}
        onPointerUp={handlePanEnd}
        style={{ touchAction: 'none' }}
      />

      {/* Color scale */}
      {showColorScale && (
        <div className="color-scale">
          <div className="scale-gradient" style={{
            background: `linear-gradient(to right,
              #${DEFAULT_COLOR_SCHEME.shallow_color.toString(16).padStart(6, '0')} 0%,
              #${DEFAULT_COLOR_SCHEME.mid_color.toString(16).padStart(6, '0')} 50%,
              #${DEFAULT_COLOR_SCHEME.deep_color.toString(16).padStart(6, '0')} 100%)`
          }} />
          <div className="scale-labels">
            <span>{bounds.minDepth.toFixed(1)}m</span>
            <span>{bounds.maxDepth.toFixed(1)}m</span>
          </div>
        </div>
      )}

      {/* Hover tooltip */}
      {state.hoveredCell && state.showLabels && (
        <div className="bathy-tooltip" style={{
          left: `${state.hoveredCell.lon}px`,
          top: `${state.hoveredCell.lat}px`,
        }}>
          <div className="tooltip-row">
            <span className="tooltip-label">Depth:</span>
            <span className="tooltip-value">{state.hoveredCell.depth.toFixed(1)}m</span>
          </div>
          <div className="tooltip-row">
            <span className="tooltip-label">Confidence:</span>
            <span className="tooltip-value">{(state.hoveredCell.confidence * 100).toFixed(0)}%</span>
          </div>
          <div className="tooltip-row">
            <span className="tooltip-label">Position:</span>
            <span className="tooltip-value">
              {state.hoveredCell.lat.toFixed(4)}, {state.hoveredCell.lon.toFixed(4)}
            </span>
          </div>
        </div>
      )}

      {/* Stats panel */}
      {showStats && (
        <div className="bathy-stats">
          <div className="stat-item">
            <span className="stat-label">Voxels:</span>
            <span className="stat-value">{data.voxel_count?.toLocaleString() || data.cells?.length || 0}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Selected:</span>
            <span className="stat-value">{selectedCellsArray.length}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Zoom:</span>
            <span className="stat-value">{state.zoom.toFixed(1)}x</span>
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * Helper: Convert hex to RGB
 */
function hexToRgb(hex: number): { r: number; g: number; b: number } {
  return {
    r: (hex >> 16) & 0xff,
    g: (hex >> 8) & 0xff,
    b: hex & 0xff,
  };
}

/**
 * Helper: Convert RGB to hex
 */
function rgbToHex(r: number, g: number, b: number): number {
  return (r << 16) | (g << 8) | b;
}

export default BathymetryViewer;
