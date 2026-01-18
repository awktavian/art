/**
 * Kagami Design System - Unified Design Tokens
 *
 * Single source of truth for all design tokens.
 * This file generates both Tailwind config values and CSS custom properties.
 *
 * Standard timing scale (ms):
 *   89, 144, 233, 377, 610, 987, 1597, 2584, 4181, 6765
 */

// ============================================================================
// Colony Colors
// ============================================================================

/**
 * Colony colors mapped to semantic meaning:
 * - Spark: Action, ignition, accomplishment
 * - Forge: Building, progress, creation
 * - Flow: Adaptation, sensing, water-like
 * - Nexus: Connection, integration, network
 * - Beacon: Attention, warning, guidance
 * - Grove: Growth, success, nature
 * - Crystal: Clarity, information, ice
 */
export const colonyColors = {
  spark: { hex: '#FF6B35', rgb: '255 107 53' },
  forge: { hex: '#FF9500', rgb: '255 149 0' },
  flow: { hex: '#5AC8FA', rgb: '90 200 250' },
  nexus: { hex: '#AF52DE', rgb: '175 82 222' },
  beacon: { hex: '#FFD60A', rgb: '255 214 10' },
  grove: { hex: '#32D74B', rgb: '50 215 75' },
  crystal: { hex: '#64D2FF', rgb: '100 210 255' },
} as const;

// ============================================================================
// Semantic Colors
// ============================================================================

export const voidColors = {
  DEFAULT: { hex: '#0A0A0F', rgb: '10 10 15' },
  light: { hex: '#1C1C24', rgb: '28 28 36' },
  lighter: { hex: '#2A2A36', rgb: '42 42 54' },
} as const;

export const safetyColors = {
  ok: { hex: '#32D74B', rgb: '50 215 75' },
  caution: { hex: '#FFD60A', rgb: '255 214 10' },
  violation: { hex: '#FF3B30', rgb: '255 59 48' },
} as const;

export const statusColors = {
  pass: { hex: '#32D74B', rgb: '50 215 75' },
  fail: { hex: '#FF3B30', rgb: '255 59 48' },
  progress: { hex: '#FF9500', rgb: '255 149 0' },
  pending: { hex: '#64D2FF', rgb: '100 210 255' },
  warning: { hex: '#FFD60A', rgb: '255 214 10' },
} as const;

export const textColors = {
  primary: { rgb: '255 255 255' },
  secondary: { rgb: '180 180 190' },
  tertiary: { rgb: '120 120 130' },
} as const;

export const goldColors = {
  DEFAULT: '#C4A35A',
  light: '#D4B76A',
  dark: '#A08040',
  muted: 'rgba(196, 163, 90, 0.3)',
} as const;

// ============================================================================
// Light Mode Overrides
// ============================================================================

export const lightModeOverrides = {
  void: { rgb: '250 250 252' },
  voidLight: { rgb: '240 240 244' },
  voidLighter: { rgb: '230 230 236' },
  textPrimary: { rgb: '10 10 15' },
  textSecondary: { rgb: '80 80 90' },
  textTertiary: { rgb: '140 140 150' },
} as const;

// ============================================================================
// Animation Timing
// ============================================================================

/**
 * Standard animation durations.
 *
 * Use cases:
 * - micro (89ms): Hover states, subtle feedback
 * - fast (144ms): Button clicks, toggles
 * - normal (233ms): Most transitions, fade in/out
 * - medium (377ms): Slide animations, modal entry
 * - slow (610ms): Complex transitions, staggered lists
 * - slower (987ms): Celebratory animations, emphasis
 * - slowest (1597ms): Breathing effects, background
 * - breathing (2584ms): Ambient animations, slow pulse
 * - celebration (4181ms): Success sequences, major events
 * - extended (6765ms): Long-running ambient effects
 */
export const fibonacciTiming = {
  micro: 89,
  fast: 144,
  normal: 233,
  medium: 377,
  slow: 610,
  slower: 987,
  slowest: 1597,
  breathing: 2584,
  celebration: 4181,
  extended: 6765,
} as const;

/**
 * Get Fibonacci duration as CSS string with 'ms' suffix.
 */
export const fibonacciDurations = Object.fromEntries(
  Object.entries(fibonacciTiming).map(([key, value]) => [key, `${value}ms`])
) as { [K in keyof typeof fibonacciTiming]: string };

/**
 * Select appropriate celebration duration based on context importance.
 *
 * @param importance - Scale from 1-5 where 5 is most important
 * @returns Duration in milliseconds
 */
export function getCelebrationDuration(importance: 1 | 2 | 3 | 4 | 5): number {
  const durations = [
    fibonacciTiming.normal,    // 1: Quick acknowledgment (233ms)
    fibonacciTiming.medium,    // 2: Minor success (377ms)
    fibonacciTiming.slow,      // 3: Standard celebration (610ms)
    fibonacciTiming.slower,    // 4: Notable achievement (987ms)
    fibonacciTiming.slowest,   // 5: Major milestone (1597ms)
  ];
  return durations[importance - 1];
}

// ============================================================================
// Easing Functions
// ============================================================================

/**
 * Custom easing curves for animations.
 *
 * - standard: General purpose, balanced entry and exit
 * - decelerate: Ease-out, for elements entering view
 * - accelerate: Ease-in, for elements exiting view
 * - sharp: Quick, decisive movements
 * - overshoot: Bouncy, playful feedback
 */
export const easingCurves = {
  standard: 'cubic-bezier(0.4, 0.0, 0.2, 1.0)',
  decelerate: 'cubic-bezier(0.0, 0.0, 0.2, 1.0)',
  accelerate: 'cubic-bezier(0.4, 0.0, 1.0, 1.0)',
  sharp: 'cubic-bezier(0.4, 0.0, 0.6, 1.0)',
  overshoot: 'cubic-bezier(0.34, 1.56, 0.64, 1.0)',
} as const;

// ============================================================================
// Spacing & Touch Targets
// ============================================================================

export const spacing = {
  minTouchTarget: '44px',
  custom: {
    '4.5': '18px',
    '13': '52px',
    '15': '60px',
    '18': '72px',
    '22': '88px',
  },
} as const;

// ============================================================================
// Border Radius
// ============================================================================

export const borderRadius = {
  xs: '4px',
  sm: '8px',
  md: '12px',
  lg: '16px',
  xl: '24px',
} as const;

// ============================================================================
// Typography
// ============================================================================

export const fontFamily = {
  sans: ['var(--font-inter)', 'Inter', 'SF Pro', 'system-ui', 'sans-serif'],
  display: ['var(--font-cormorant)', 'Cormorant Garamond', 'Georgia', 'serif'],
  mono: ['JetBrains Mono', 'SF Mono', 'Consolas', 'monospace'],
} as const;

export const fontSize = {
  xs: ['11px', { lineHeight: '1.5' }],
  sm: ['13px', { lineHeight: '1.5' }],
  base: ['15px', { lineHeight: '1.5' }],
  md: ['17px', { lineHeight: '1.5' }],
  lg: ['20px', { lineHeight: '1.4' }],
  xl: ['24px', { lineHeight: '1.3' }],
  '2xl': ['28px', { lineHeight: '1.2' }],
  '3xl': ['34px', { lineHeight: '1.1' }],
} as const;

// ============================================================================
// Shadows
// ============================================================================

export const boxShadow = {
  'glow-spark': `0 0 20px rgba(${colonyColors.spark.rgb.replace(/ /g, ', ')}, 0.3)`,
  'glow-forge': `0 0 20px rgba(${colonyColors.forge.rgb.replace(/ /g, ', ')}, 0.3)`,
  'glow-flow': `0 0 20px rgba(${colonyColors.flow.rgb.replace(/ /g, ', ')}, 0.3)`,
  'glow-nexus': `0 0 20px rgba(${colonyColors.nexus.rgb.replace(/ /g, ', ')}, 0.3)`,
  'glow-beacon': `0 0 20px rgba(${colonyColors.beacon.rgb.replace(/ /g, ', ')}, 0.3)`,
  'glow-grove': `0 0 20px rgba(${colonyColors.grove.rgb.replace(/ /g, ', ')}, 0.3)`,
  'glow-crystal': `0 0 20px rgba(${colonyColors.crystal.rgb.replace(/ /g, ', ')}, 0.3)`,
  card: '0 4px 24px rgba(0, 0, 0, 0.4)',
  'card-hover': '0 8px 32px rgba(0, 0, 0, 0.5)',
} as const;

// ============================================================================
// Animation Keyframes
// ============================================================================

export const keyframes = {
  fadeIn: {
    '0%': { opacity: '0' },
    '100%': { opacity: '1' },
  },
  fadeOut: {
    '0%': { opacity: '1' },
    '100%': { opacity: '0' },
  },
  slideUp: {
    '0%': { transform: 'translateY(16px)', opacity: '0' },
    '100%': { transform: 'translateY(0)', opacity: '1' },
  },
  slideDown: {
    '0%': { transform: 'translateY(-16px)', opacity: '0' },
    '100%': { transform: 'translateY(0)', opacity: '1' },
  },
  scaleIn: {
    '0%': { transform: 'scale(0.95)', opacity: '0' },
    '100%': { transform: 'scale(1)', opacity: '1' },
  },
  shimmer: {
    '0%': { backgroundPosition: '-200% 0' },
    '100%': { backgroundPosition: '200% 0' },
  },
} as const;

// ============================================================================
// Predefined Animations
// ============================================================================

export const animations = {
  'pulse-slow': `pulse ${fibonacciDurations.breathing} ${easingCurves.standard} infinite`,
  'fade-in': `fadeIn ${fibonacciDurations.normal} ${easingCurves.decelerate}`,
  'fade-out': `fadeOut ${fibonacciDurations.normal} ${easingCurves.accelerate}`,
  'slide-up': `slideUp ${fibonacciDurations.medium} ${easingCurves.decelerate}`,
  'slide-down': `slideDown ${fibonacciDurations.medium} ${easingCurves.accelerate}`,
  'scale-in': `scaleIn ${fibonacciDurations.normal} ${easingCurves.overshoot}`,
  shimmer: `shimmer ${fibonacciDurations.slowest} ease-in-out infinite`,
} as const;

// ============================================================================
// CSS Custom Properties Generator
// ============================================================================

/**
 * Generate CSS custom properties string for injection into :root.
 */
export function generateCSSVariables(): string {
  const lines: string[] = [];

  // Colony colors
  Object.entries(colonyColors).forEach(([name, { rgb }]) => {
    lines.push(`--color-${name}: ${rgb};`);
  });

  // Void colors
  lines.push(`--color-void: ${voidColors.DEFAULT.rgb};`);
  lines.push(`--color-void-light: ${voidColors.light.rgb};`);
  lines.push(`--color-void-lighter: ${voidColors.lighter.rgb};`);

  // Status colors
  Object.entries(statusColors).forEach(([name, { rgb }]) => {
    lines.push(`--color-${name}: ${rgb};`);
  });

  // Text colors
  lines.push(`--color-text-primary: ${textColors.primary.rgb};`);
  lines.push(`--color-text-secondary: ${textColors.secondary.rgb};`);
  lines.push(`--color-text-tertiary: ${textColors.tertiary.rgb};`);

  // Animation durations
  Object.entries(fibonacciDurations).forEach(([name, value]) => {
    lines.push(`--duration-${name}: ${value};`);
  });

  // Easing curves
  Object.entries(easingCurves).forEach(([name, value]) => {
    lines.push(`--ease-${name}: ${value};`);
  });

  // Spacing
  lines.push(`--min-touch-target: ${spacing.minTouchTarget};`);

  return lines.join('\n    ');
}

// ============================================================================
// Tailwind Config Export
// ============================================================================

/**
 * Export design tokens formatted for Tailwind CSS config.
 */
export const tailwindTokens = {
  colors: {
    colony: Object.fromEntries(
      Object.entries(colonyColors).map(([name, { hex }]) => [name, hex])
    ),
    gold: goldColors,
    void: {
      DEFAULT: voidColors.DEFAULT.hex,
      light: voidColors.light.hex,
      lighter: voidColors.lighter.hex,
    },
    safety: Object.fromEntries(
      Object.entries(safetyColors).map(([name, { hex }]) => [name, hex])
    ),
    status: Object.fromEntries(
      Object.entries(statusColors).map(([name, { hex }]) => [name, hex])
    ),
  },
  fontFamily,
  fontSize,
  spacing: spacing.custom,
  borderRadius,
  transitionDuration: fibonacciDurations,
  transitionTimingFunction: easingCurves,
  animation: animations,
  keyframes,
  boxShadow,
} as const;

// ============================================================================
// Type Exports
// ============================================================================

export type ColonyColorName = keyof typeof colonyColors;
export type FibonacciDuration = keyof typeof fibonacciTiming;
export type EasingCurve = keyof typeof easingCurves;

/*
 * Design tokens as the foundation of visual truth.
 */
