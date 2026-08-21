/**
 * Theme system for marine digital twin interfaces
 * Supports day mode (high contrast) and night mode (red-preserving)
 */

/**
 * Color palette for marine themes
 */
export interface MarineColorPalette {
  // Primary colors
  primary: string;
  secondary: string;
  accent: string;

  // Semantic colors
  success: string;
  warning: string;
  error: string;
  critical: string;
  info: string;

  // Neutral colors
  background: string;
  surface: string;
  surfaceVariant: string;
  text: string;
  textSecondary: string;
  textDisabled: string;
  border: string;
  divider: string;

  // Marine-specific
  water: string;
  waterSurface: string;
  vessel: string;
  track: string;
  shallowDepth: string;
  midDepth: string;
  deepDepth: string;

  // Night mode red-preserving
  nightRed: string;
  nightDim: string;
  nightBackground: string;
}

/**
 * Typography settings
 */
export interface MarineTypography {
  fontFamily: string;
  fontFamilyMono: string;

  // Font sizes (rem)
  fontSizeXS: string;
  fontSizeSM: string;
  fontSizeMD: string;
  fontSizeLG: string;
  fontSizeXL: string;
  fontSizeXXL: string;

  // Font weights
  fontWeightNormal: number;
  fontWeightMedium: number;
  fontWeightBold: number;

  // Line heights
  lineHeightTight: number;
  lineHeightNormal: number;
  lineHeightRelaxed: number;
}

/**
 * Spacing scale (based on 8px grid)
 */
export interface MarineSpacing {
  unit: string; // Base unit (8px)

  // Scale values (rem)
  xxxs: string;
  xxs: string;
  xs: string;
  sm: string;
  md: string;
  lg: string;
  xl: string;
  xxl: string;
  xxxl: string;
}

/**
 * Touch target sizes (critical for wet-hand operation)
 */
export interface MarineTouchTargets {
  minimum: string; // 20mm minimum
  comfortable: string; // 24mm comfortable
  spacious: string; // 28mm spacious
}

/**
 * Border radius
 */
export interface MarineBorders {
  none: string;
  sm: string;
  md: string;
  lg: string;
  xl: string;
  full: string;
}

/**
 * Shadows for depth perception
 */
export interface MarineShadows {
  sm: string;
  md: string;
  lg: string;
  xl: string;
}

/**
 * Animation durations
 */
export interface MarineAnimation {
  fast: string;
  normal: string;
  slow: string;
}

/**
 * Complete marine theme
 */
export interface MarineTheme {
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

/**
 * Day theme - High contrast for bright conditions
 */
export const dayTheme: MarineTheme = {
  name: 'Day Mode',
  mode: 'day',
  colors: {
    primary: '#1c5f8a',
    secondary: '#2f6fd0',
    accent: '#ff7700',

    success: '#35e08a',
    warning: '#e0b13c',
    error: '#e04b4b',
    critical: '#ff0000',
    info: '#6f93b3',

    background: '#f5f5f5',
    surface: '#ffffff',
    surfaceVariant: '#e8e8e8',
    text: '#1a1a1a',
    textSecondary: '#555555',
    textDisabled: '#999999',
    border: '#cccccc',
    divider: '#e0e0e0',

    water: '#1c5f8a',
    waterSurface: 'rgba(28, 95, 138, 0.55)',
    vessel: '#ff7700',
    track: '#ff7700',
    shallowDepth: '#ff9a3c',
    midDepth: '#3fd68c',
    deepDepth: '#2f6fd0',

    nightRed: '#ff3333',
    nightDim: '#333333',
    nightBackground: '#0a0a0a',
  },
  typography: {
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    fontFamilyMono: '"SF Mono", "Monaco", "Consolas", "Liberation Mono", "Courier New", monospace',

    fontSizeXS: '0.75rem',   // 12px
    fontSizeSM: '0.875rem',  // 14px
    fontSizeMD: '1rem',      // 16px
    fontSizeLG: '1.125rem',  // 18px
    fontSizeXL: '1.25rem',   // 20px
    fontSizeXXL: '1.5rem',   // 24px

    fontWeightNormal: 400,
    fontWeightMedium: 500,
    fontWeightBold: 600,

    lineHeightTight: 1.25,
    lineHeightNormal: 1.5,
    lineHeightRelaxed: 1.75,
  },
  spacing: {
    unit: '0.5rem', // 8px

    xxxs: '0.25rem', // 4px
    xxs: '0.5rem',   // 8px
    xs: '0.75rem',   // 12px
    sm: '1rem',      // 16px
    md: '1.5rem',    // 24px
    lg: '2rem',      // 32px
    xl: '3rem',      // 48px
    xxl: '4rem',     // 64px
    xxxl: '6rem',    // 96px
  },
  touchTargets: {
    minimum: '2.5rem',    // 40px - 20mm at 160dpi
    comfortable: '3rem',  // 48px - 24mm at 160dpi
    spacious: '3.5rem',   // 56px - 28mm at 160dpi
  },
  borders: {
    none: '0',
    sm: '0.125rem',
    md: '0.25rem',
    lg: '0.5rem',
    xl: '0.75rem',
    full: '9999px',
  },
  shadows: {
    sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
    md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
    lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
    xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
  },
  animation: {
    fast: '150ms',
    normal: '300ms',
    slow: '500ms',
  },
};

/**
 * Night theme - Red-preserving for dark conditions
 * Uses predominantly red hues to preserve night vision
 */
export const nightTheme: MarineTheme = {
  name: 'Night Mode',
  mode: 'night',
  colors: {
    primary: '#cc0000',
    secondary: '#ff3333',
    accent: '#ff6666',

    success: '#cc6633',
    warning: '#cc9933',
    error: '#ff3333',
    critical: '#ff0000',
    info: '#996633',

    background: '#0a0a0a',
    surface: '#1a1a1a',
    surfaceVariant: '#2a2a2a',
    text: '#ffcccc',
    textSecondary: '#cc9999',
    textDisabled: '#663333',
    border: '#441111',
    divider: '#331111',

    water: '#331111',
    waterSurface: 'rgba(51, 17, 17, 0.55)',
    vessel: '#cc3333',
    track: '#cc3333',
    shallowDepth: '#cc6666',
    midDepth: '#994444',
    deepDepth: '#662222',

    nightRed: '#ff3333',
    nightDim: '#331111',
    nightBackground: '#0a0a0a',
  },
  typography: {
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    fontFamilyMono: '"SF Mono", "Monaco", "Consolas", "Liberation Mono", "Courier New", monospace',

    fontSizeXS: '0.75rem',
    fontSizeSM: '0.875rem',
    fontSizeMD: '1rem',
    fontSizeLG: '1.125rem',
    fontSizeXL: '1.25rem',
    fontSizeXXL: '1.5rem',

    fontWeightNormal: 400,
    fontWeightMedium: 500,
    fontWeightBold: 600,

    lineHeightTight: 1.25,
    lineHeightNormal: 1.5,
    lineHeightRelaxed: 1.75,
  },
  spacing: {
    unit: '0.5rem',

    xxxs: '0.25rem',
    xxs: '0.5rem',
    xs: '0.75rem',
    sm: '1rem',
    md: '1.5rem',
    lg: '2rem',
    xl: '3rem',
    xxl: '4rem',
    xxxl: '6rem',
  },
  touchTargets: {
    minimum: '2.5rem',
    comfortable: '3rem',
    spacious: '3.5rem',
  },
  borders: {
    none: '0',
    sm: '0.125rem',
    md: '0.25rem',
    lg: '0.5rem',
    xl: '0.75rem',
    full: '9999px',
  },
  shadows: {
    sm: '0 1px 2px 0 rgba(0, 0, 0, 0.5)',
    md: '0 4px 6px -1px rgba(0, 0, 0, 0.7), 0 2px 4px -1px rgba(0, 0, 0, 0.6)',
    lg: '0 10px 15px -3px rgba(0, 0, 0, 0.8), 0 4px 6px -2px rgba(0, 0, 0, 0.7)',
    xl: '0 20px 25px -5px rgba(0, 0, 0, 0.9), 0 10px 10px -5px rgba(0, 0, 0, 0.8)',
  },
  animation: {
    fast: '150ms',
    normal: '300ms',
    slow: '500ms',
  },
};

/**
 * Get theme by mode
 */
export function getTheme(mode: 'day' | 'night'): MarineTheme {
  return mode === 'day' ? dayTheme : nightTheme;
}

/**
 * Default theme export
 */
export default dayTheme;
