/**
 * Configuration System — Data-driven theming and settings
 * All magic numbers centralized here for maintainability
 */

export const CONFIG = {
  version: '4.0.0',
  
  // Performance tuning
  performance: {
    maxVisibleNodes: 5000,
    spatialGridSize: 50,
    debounceMs: 16,
    tooltipDelayMs: 150,
    expandDelayMs: 800,
    animationDuration: 300,
  },
  
  // 3D Camera defaults
  camera: {
    fov: 400,
    distance: 1.5,
    defaultRotX: 0.3,
    defaultRotY: 0,
    defaultZoom: 1,
    minZoom: 0.3,
    maxZoom: 5,
    rotationSpeed: 0.005,
    autoRotateSpeed: 0.0005,
  },
  
  // Treemap settings
  treemap: {
    minCellSize: 4,
    padding: 2,
    cornerRadius: 4,
    labelMinSize: 40,
  },
  
  // Node sizing
  nodes: {
    minSize: 2,
    maxSize: 30,
    sizeScale: 0.06,
    importanceWeight: 0.4,
  },
};

// Theme system — CSS custom properties
export const THEME = {
  colors: {
    void: '#06060a',
    voidLight: '#0c0c14',
    surface: '#12121a',
    surfaceHover: '#1a1a24',
    
    textPrimary: '#f5f2eb',
    textSecondary: '#c8c4ba',
    textTertiary: '#9a978e',
    textQuaternary: '#8a8880',
    
    borderSubtle: 'rgba(255,255,255,0.06)',
    borderMedium: 'rgba(255,255,255,0.12)',
    borderStrong: 'rgba(255,255,255,0.2)',
    
    gold: '#f0c860',
    goldBright: '#f8d878',
    goldDim: '#a08840',
    goldGlow: 'rgba(240,200,96,0.4)',
  },
  
  // Category colors — vibrant and accessible
  categories: {
    Python: { h: 220, s: 70, l: 55, hex: '#3b82f6' },
    JavaScript: { h: 48, s: 90, l: 55, hex: '#facc15' },
    TypeScript: { h: 211, s: 60, l: 48, hex: '#3178c6' },
    React: { h: 193, s: 95, l: 68, hex: '#61dafb' },
    Rust: { h: 24, s: 95, l: 52, hex: '#f97316' },
    Swift: { h: 8, s: 85, l: 58, hex: '#f05138' },
    Kotlin: { h: 256, s: 100, l: 66, hex: '#7f52ff' },
    Go: { h: 192, s: 75, l: 55, hex: '#00add8' },
    Java: { h: 20, s: 80, l: 50, hex: '#f89820' },
    Config: { h: 215, s: 15, l: 45, hex: '#64748b' },
    Docs: { h: 142, s: 70, l: 45, hex: '#22c55e' },
    Test: { h: 330, s: 80, l: 65, hex: '#f472b6' },
    API: { h: 260, s: 70, l: 65, hex: '#a78bfa' },
    Core: { h: 200, s: 80, l: 50, hex: '#0ea5e9' },
    Security: { h: 0, s: 75, l: 60, hex: '#ef4444' },
    Shell: { h: 80, s: 60, l: 50, hex: '#84cc16' },
    Web: { h: 290, s: 75, l: 70, hex: '#e879f9' },
    Style: { h: 330, s: 85, l: 60, hex: '#ec4899' },
    Database: { h: 35, s: 90, l: 55, hex: '#f59e0b' },
    Model: { h: 170, s: 60, l: 45, hex: '#14b8a6' },
    Service: { h: 240, s: 60, l: 60, hex: '#818cf8' },
    Utility: { h: 190, s: 50, l: 50, hex: '#22d3ee' },
    Other: { h: 220, s: 10, l: 45, hex: '#6b7280' },
    default: { h: 220, s: 10, l: 45, hex: '#6b7280' },
  },
  
  fonts: {
    sans: '"IBM Plex Sans", -apple-system, BlinkMacSystemFont, sans-serif',
    mono: '"IBM Plex Mono", "SF Mono", "Fira Code", monospace',
  },
  
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
  },
  
  timing: {
    fast: '150ms',
    normal: '250ms',
    slow: '400ms',
    easeOut: 'cubic-bezier(0.16, 1, 0.3, 1)',
    easeSpring: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
  },
};

// Get category color with optional alpha
export function getCategoryColor(category, alpha = 1) {
  const cat = THEME.categories[category] || THEME.categories.default;
  return alpha === 1 
    ? cat.hex 
    : `hsla(${cat.h}, ${cat.s}%, ${cat.l}%, ${alpha})`;
}

// Get category HSL for canvas operations
export function getCategoryHSL(category) {
  return THEME.categories[category] || THEME.categories.default;
}

// Apply theme to document
export function applyTheme() {
  const root = document.documentElement;
  
  // Colors
  Object.entries(THEME.colors).forEach(([key, value]) => {
    const cssVar = `--${key.replace(/([A-Z])/g, '-$1').toLowerCase()}`;
    root.style.setProperty(cssVar, value);
  });
  
  // Fonts
  root.style.setProperty('--font-sans', THEME.fonts.sans);
  root.style.setProperty('--font-mono', THEME.fonts.mono);
  
  // Spacing
  Object.entries(THEME.spacing).forEach(([key, value]) => {
    root.style.setProperty(`--space-${key}`, value);
  });
}
