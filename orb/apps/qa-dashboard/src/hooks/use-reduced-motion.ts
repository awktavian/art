'use client'

import { useState, useEffect } from 'react'

/**
 * Hook to detect user's prefers-reduced-motion preference.
 * Returns true if user has enabled reduced motion in their system settings.
 *
 * WCAG 2.1 SC 2.3.3 (Animation from Interactions) compliance:
 * Motion animation triggered by interaction can be disabled.
 *
 * @returns boolean - true if reduced motion is preferred
 */
export function useReducedMotion(): boolean {
  // Default to false on server (assume no preference)
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false)

  useEffect(() => {
    // Check if window is available (client-side only)
    if (typeof window === 'undefined') return

    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')

    // Set initial value
    setPrefersReducedMotion(mediaQuery.matches)

    // Listen for changes
    const handleChange = (event: MediaQueryListEvent) => {
      setPrefersReducedMotion(event.matches)
    }

    // Modern browsers
    mediaQuery.addEventListener('change', handleChange)

    return () => {
      mediaQuery.removeEventListener('change', handleChange)
    }
  }, [])

  return prefersReducedMotion
}

/**
 * Returns animation duration based on reduced motion preference.
 * If reduced motion is preferred, returns minimal duration (10ms).
 * Otherwise returns the provided duration.
 *
 * @param normalDuration - Duration in milliseconds when motion is allowed
 * @returns Appropriate duration based on user preference
 */
export function useAnimationDuration(normalDuration: number): number {
  const prefersReducedMotion = useReducedMotion()
  return prefersReducedMotion ? 10 : normalDuration
}

/**
 * Returns Framer Motion transition config respecting reduced motion.
 * Use this to create accessible motion animations.
 *
 * @param normalTransition - Transition config when motion is allowed
 * @returns Appropriate transition config based on user preference
 */
export function useMotionTransition(normalTransition: {
  duration?: number
  ease?: string | number[]
  delay?: number
}): typeof normalTransition {
  const prefersReducedMotion = useReducedMotion()

  if (prefersReducedMotion) {
    return {
      ...normalTransition,
      duration: 0.01,
      delay: 0,
    }
  }

  return normalTransition
}
