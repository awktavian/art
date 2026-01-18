import type { Config } from 'tailwindcss'
import { tailwindTokens } from './src/styles/design-tokens'

/**
 * Kagami Design System - Tailwind Configuration
 *
 * This configuration imports all design tokens from the unified
 * design-tokens.ts file, ensuring consistency between CSS custom
 * properties and Tailwind utility classes.
 *
 * Colony colors mapped to test states:
 * - Spark (#FF6B35): Pass/Success - the fire of accomplishment
 * - Forge (#FF9500): In Progress - actively building/testing
 * - Crystal (#64D2FF): Fail/Error - clarity on what went wrong
 * - Grove (#32D74B): Pass (alternative) - nature/growth
 * - Beacon (#FFD60A): Warning - attention needed
 * - Nexus (#AF52DE): Integration - connected systems
 * - Flow (#5AC8FA): Resilience - recovery in progress
 *
 * All timing uses Fibonacci sequence (89, 144, 233, 377, 610, 987, 1597, 2584ms)
 * for mathematically harmonious, natural-feeling animations.
 */

const config: Config = {
  darkMode: 'class',
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      // Colors from unified design tokens
      colors: tailwindTokens.colors,

      // Typography from design tokens
      fontFamily: tailwindTokens.fontFamily,
      fontSize: tailwindTokens.fontSize,

      // Spacing from design tokens
      spacing: tailwindTokens.spacing,

      // Border radius from design tokens
      borderRadius: tailwindTokens.borderRadius,

      // Fibonacci-based animation durations from design tokens
      transitionDuration: tailwindTokens.transitionDuration,

      // Custom easing curves from design tokens
      transitionTimingFunction: tailwindTokens.transitionTimingFunction,

      // Animations from design tokens
      animation: tailwindTokens.animation,

      // Keyframes from design tokens
      keyframes: tailwindTokens.keyframes,

      // Shadows from design tokens
      boxShadow: tailwindTokens.boxShadow,

      // Background images (keeping these here as they're Tailwind-specific)
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-colony': 'linear-gradient(135deg, var(--tw-gradient-stops))',
        'shimmer': 'linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent)',
      },
    },
  },
  plugins: [],
}

export default config
