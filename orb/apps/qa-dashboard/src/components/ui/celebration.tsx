'use client'

import { useEffect, useRef, useCallback, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { TIMING } from '@/types'
import { announce } from './live-region'

// ============================================================================
// Achievement Tiers - Celebrations that SCALE with magnitude
// ============================================================================

/**
 * Achievement tier determines celebration intensity.
 *
 * MINOR: Single test pass, small wins (subtle acknowledgment)
 * SIGNIFICANT: Suite completion, milestone reached (satisfying celebration)
 * TRIUMPH: Full test run pass, major achievement (full sensory experience)
 */
export type AchievementTier = 'MINOR' | 'SIGNIFICANT' | 'TRIUMPH'

interface TierConfig {
  /** Number of particles (scales with viewport) */
  baseParticleCount: number
  /** Animation duration (Fibonacci, of course) */
  duration: number
  /** Initial burst velocity multiplier */
  velocityMultiplier: number
  /** Gravity strength */
  gravity: number
  /** Glow class to apply */
  glowClass: 'glow-grove' | 'glow-beacon' | 'glow-nexus'
  /** Screen reader announcement */
  announcement: string
  /** Haptic pattern for watch (tap durations in ms) */
  hapticPattern: number[]
}

/**
 * Tier configurations - each level brings MORE joy
 */
const TIER_CONFIG: Record<AchievementTier, TierConfig> = {
  MINOR: {
    baseParticleCount: 30,
    duration: TIMING.slow, // 610ms
    velocityMultiplier: 0.7,
    gravity: 0.2,
    glowClass: 'glow-grove',
    announcement: 'Test passed!',
    hapticPattern: [50], // Single gentle tap
  },
  SIGNIFICANT: {
    baseParticleCount: 50,
    duration: TIMING.slower, // 987ms
    velocityMultiplier: 1.0,
    gravity: 0.15,
    glowClass: 'glow-grove',
    announcement: 'All tests in suite passed!',
    hapticPattern: [50, 30, 50], // Double tap with pause
  },
  TRIUMPH: {
    baseParticleCount: 80,
    duration: TIMING.slowest, // 1597ms
    velocityMultiplier: 1.3,
    gravity: 0.12,
    glowClass: 'glow-beacon',
    announcement: 'TRIUMPH! Full test run passed with flying colors!',
    hapticPattern: [50, 30, 50, 30, 100], // Crescendo pattern
  },
}

interface ConfettiParticle {
  x: number
  y: number
  vx: number
  vy: number
  color: string
  rotation: number
  rotationSpeed: number
  size: number
  shape: 'square' | 'circle' | 'triangle' | 'star'
  /** Sparkle phase for twinkling effect */
  sparklePhase: number
}

const CELEBRATION_COLORS = [
  '#32D74B', // grove - success
  '#64D2FF', // crystal
  '#C4A35A', // gold
  '#AF52DE', // nexus
  '#FFD60A', // beacon
]

/** Extra colors for TRIUMPH tier - go all out! */
const TRIUMPH_COLORS = [
  ...CELEBRATION_COLORS,
  '#FF6B35', // spark
  '#FF2D55', // rose
  '#5E5CE6', // indigo
]

interface CelebrationCanvasProps {
  /** Whether to show the celebration */
  active: boolean
  /** Callback when celebration ends */
  onComplete?: () => void
  /** Duration in ms (default: Fibonacci 1597ms) - DEPRECATED: use tier instead */
  duration?: number
  /** Achievement tier - determines celebration intensity */
  tier?: AchievementTier
}

/**
 * Calculate viewport-scaled particle count.
 *
 * Larger screens get MORE particles for visual density.
 * Formula: baseCount * (viewportArea / referenceArea)
 *
 * Reference: 1920x1080 = ~2M pixels = factor of 1.0
 */
function calculateParticleCount(baseCount: number, width: number, height: number): number {
  const viewportArea = width * height
  const referenceArea = 50000 // Tuned for visual density
  const scaleFactor = Math.max(0.5, Math.min(2.0, viewportArea / referenceArea))
  return Math.round(baseCount * scaleFactor)
}

/**
 * Draw a star shape (for TRIUMPH celebrations)
 */
function drawStar(ctx: CanvasRenderingContext2D, size: number) {
  const spikes = 5
  const outerRadius = size / 2
  const innerRadius = size / 4

  ctx.beginPath()
  for (let i = 0; i < spikes * 2; i++) {
    const radius = i % 2 === 0 ? outerRadius : innerRadius
    const angle = (Math.PI / spikes) * i - Math.PI / 2
    const x = Math.cos(angle) * radius
    const y = Math.sin(angle) * radius
    if (i === 0) {
      ctx.moveTo(x, y)
    } else {
      ctx.lineTo(x, y)
    }
  }
  ctx.closePath()
  ctx.fill()
}

/**
 * CelebrationCanvas - Confetti burst for success moments
 *
 * NOW WITH TIERED CELEBRATIONS!
 * - MINOR: 30 particles, 610ms - subtle acknowledgment
 * - SIGNIFICANT: 50 particles, 987ms - satisfying win
 * - TRIUMPH: 80 particles, 1597ms - FULL sensory experience
 *
 * Respects prefers-reduced-motion. In reduced motion mode,
 * shows a simple checkmark animation instead.
 */
export function CelebrationCanvas({
  active,
  onComplete,
  duration,
  tier = 'SIGNIFICANT',
}: CelebrationCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animationRef = useRef<number>(0)
  const particlesRef = useRef<ConfettiParticle[]>([])
  const startTimeRef = useRef<number>(0)
  const glowRef = useRef<HTMLDivElement>(null)

  // Get tier configuration
  const config = TIER_CONFIG[tier]
  const effectiveDuration = duration ?? config.duration

  // Memoize color palette based on tier
  const colorPalette = useMemo(
    () => (tier === 'TRIUMPH' ? TRIUMPH_COLORS : CELEBRATION_COLORS),
    [tier]
  )

  const createParticles = useCallback(
    (width: number, height: number) => {
      const particles: ConfettiParticle[] = []
      const count = calculateParticleCount(config.baseParticleCount, width, height)

      // Include stars only for TRIUMPH tier
      const shapes: ConfettiParticle['shape'][] =
        tier === 'TRIUMPH'
          ? ['square', 'circle', 'triangle', 'star', 'star']
          : ['square', 'circle', 'triangle']

      for (let i = 0; i < count; i++) {
        const angle = (Math.PI * 2 * i) / count + (Math.random() - 0.5) * 0.5
        const baseSpeed = 8 + Math.random() * 8
        const speed = baseSpeed * config.velocityMultiplier

        particles.push({
          x: width / 2,
          y: height / 2,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed - 4 * config.velocityMultiplier,
          color: colorPalette[Math.floor(Math.random() * colorPalette.length)],
          rotation: Math.random() * Math.PI * 2,
          rotationSpeed: (Math.random() - 0.5) * 0.3,
          size: 6 + Math.random() * 6,
          shape: shapes[Math.floor(Math.random() * shapes.length)],
          sparklePhase: Math.random() * Math.PI * 2,
        })
      }

      return particles
    },
    [config, tier, colorPalette]
  )

  useEffect(() => {
    if (!active) return

    const canvas = canvasRef.current
    if (!canvas) return

    // Check for reduced motion preference
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (prefersReducedMotion) {
      // In reduced motion mode, just announce and skip animation
      announce(config.announcement, 'polite')
      setTimeout(() => onComplete?.(), TIMING.normal)
      return
    }

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const rect = canvas.getBoundingClientRect()
    const dpr = window.devicePixelRatio || 1
    canvas.width = rect.width * dpr
    canvas.height = rect.height * dpr
    ctx.scale(dpr, dpr)

    particlesRef.current = createParticles(rect.width, rect.height)
    startTimeRef.current = performance.now()

    // Apply glow effect for the tier
    if (glowRef.current) {
      glowRef.current.classList.add(config.glowClass)
    }

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTimeRef.current

      if (elapsed >= effectiveDuration) {
        ctx.clearRect(0, 0, canvas.width, canvas.height)
        if (glowRef.current) {
          glowRef.current.classList.remove(config.glowClass)
        }
        onComplete?.()
        return
      }

      ctx.clearRect(0, 0, rect.width, rect.height)

      const progress = elapsed / effectiveDuration
      const fadeOut = Math.max(0, 1 - (progress - 0.7) / 0.3)

      particlesRef.current.forEach((p) => {
        // Physics update with tier-specific gravity
        p.x += p.vx
        p.y += p.vy
        p.vy += config.gravity
        p.vx *= 0.99 // air resistance
        p.rotation += p.rotationSpeed

        // Sparkle effect for stars (TRIUMPH tier)
        const sparkle = p.shape === 'star' ? 0.7 + 0.3 * Math.sin(currentTime * 0.01 + p.sparklePhase) : 1

        // Draw particle
        ctx.save()
        ctx.translate(p.x, p.y)
        ctx.rotate(p.rotation)
        ctx.globalAlpha = fadeOut * sparkle

        ctx.fillStyle = p.color

        if (p.shape === 'square') {
          ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size)
        } else if (p.shape === 'circle') {
          ctx.beginPath()
          ctx.arc(0, 0, p.size / 2, 0, Math.PI * 2)
          ctx.fill()
        } else if (p.shape === 'star') {
          drawStar(ctx, p.size * 1.2) // Stars slightly larger for visibility
        } else {
          // triangle
          ctx.beginPath()
          ctx.moveTo(0, -p.size / 2)
          ctx.lineTo(p.size / 2, p.size / 2)
          ctx.lineTo(-p.size / 2, p.size / 2)
          ctx.closePath()
          ctx.fill()
        }

        ctx.restore()
      })

      animationRef.current = requestAnimationFrame(animate)
    }

    // Announce with tier-appropriate message
    announce(config.announcement, 'polite')
    animationRef.current = requestAnimationFrame(animate)

    return () => {
      cancelAnimationFrame(animationRef.current)
      if (glowRef.current) {
        glowRef.current.classList.remove(config.glowClass)
      }
    }
  }, [active, createParticles, effectiveDuration, onComplete, config, tier])

  if (!active) return null

  return (
    <>
      {/* Glow overlay for sensory richness */}
      <div
        ref={glowRef}
        className="fixed inset-0 pointer-events-none z-40 transition-all duration-slow"
        style={{ opacity: 0.3 }}
        aria-hidden="true"
      />
      <canvas
        ref={canvasRef}
        className="fixed inset-0 pointer-events-none z-50"
        style={{ width: '100vw', height: '100vh' }}
        aria-hidden="true"
      />
    </>
  )
}

// ============================================================================
// Haptic Feedback Utility
// ============================================================================

/**
 * Trigger haptic feedback pattern (for platforms that support it).
 *
 * Uses the Web Vibration API where available.
 * Falls back gracefully on unsupported platforms.
 *
 * @param tier - Achievement tier determines pattern intensity
 */
export function triggerHapticFeedback(tier: AchievementTier): void {
  const config = TIER_CONFIG[tier]

  // Check for Vibration API support
  if (typeof navigator !== 'undefined' && 'vibrate' in navigator) {
    navigator.vibrate(config.hapticPattern)
  }

  // Log for debugging (platforms can hook into this)
  if (process.env.NODE_ENV === 'development') {
    console.log(`[Haptic] Tier: ${tier}, Pattern: [${config.hapticPattern.join(', ')}]ms`)
  }
}

/**
 * Get haptic pattern for a tier (for native platforms).
 *
 * Watch platforms can use this to trigger WKHapticEngine patterns.
 */
export function getHapticPattern(tier: AchievementTier): number[] {
  return TIER_CONFIG[tier].hapticPattern
}

/**
 * Get the full tier configuration for external use.
 *
 * Useful for native platforms that need access to all tier parameters.
 */
export function getTierConfig(tier: AchievementTier): TierConfig {
  return TIER_CONFIG[tier]
}

/** Export tier configurations for reference */
export { TIER_CONFIG }

interface SuccessCheckmarkProps {
  /** Whether to show the checkmark */
  show: boolean
  /** Size of the checkmark */
  size?: number
}

/**
 * SuccessCheckmark - Animated checkmark for success state
 */
export function SuccessCheckmark({ show, size = 64 }: SuccessCheckmarkProps) {
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0, opacity: 0 }}
          transition={{
            type: 'spring',
            stiffness: 300,
            damping: 20,
            duration: TIMING.normal / 1000,
          }}
          className="flex items-center justify-center"
        >
          <svg
            width={size}
            height={size}
            viewBox="0 0 64 64"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            role="img"
            aria-label="Success"
          >
            <motion.circle
              cx="32"
              cy="32"
              r="30"
              stroke="#32D74B"
              strokeWidth="4"
              fill="none"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: TIMING.medium / 1000, ease: 'easeOut' }}
            />
            <motion.path
              d="M20 32L28 40L44 24"
              stroke="#32D74B"
              strokeWidth="4"
              strokeLinecap="round"
              strokeLinejoin="round"
              fill="none"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{
                duration: TIMING.fast / 1000,
                delay: TIMING.fast / 1000,
                ease: 'easeOut',
              }}
            />
          </svg>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

/**
 * Personality messages for different states
 *
 * These should spark JOY. Kagami has personality - let it shine!
 */
export const PERSONALITY_MESSAGES = {
  loading: [
    'Analyzing test footage...',
    'Teaching the AI to spot bugs...',
    'Running through the pixels...',
    'Consulting the quality oracle...',
    'Checking every frame...',
    'Channeling my inner perfectionist...',
    'Making sure every pixel earns its place...',
  ],
  success: [
    'All tests passing!',
    'Quality looks great!',
    'Ship it!',
    'Looking good!',
    'Nailed it!',
    'This is what excellence looks like.',
    '*chef\'s kiss*',
    'Tim would be proud.',
  ],
  failure: [
    'Found some issues to fix',
    'A few things need attention',
    'Some tests need love',
    'Quality check found concerns',
    'Time to investigate',
    'Nothing we can\'t fix together.',
    'Let\'s make this shine.',
  ],
  /**
   * Empty states - reimagined to be EXCITING, not boring!
   *
   * These messages should make users WANT to upload tests,
   * not feel like they're staring at a placeholder.
   */
  empty: [
    'The stage is set. Drop your test videos and let\'s hunt some bugs.',
    'I\'m ready to analyze anything you throw at me. Bring it.',
    'No tests yet? This is your moment. Let\'s find some quality wins.',
    'Feed me test videos and watch the magic happen.',
    'Waiting for you to unleash me on some footage...',
    'My neural networks are warmed up and ready. What are we testing?',
    'Quality doesn\'t test itself. Well, it does when I\'m involved.',
    'Drop it like it\'s hot. (The test videos, I mean.)',
  ],
  /** Micro-celebrations for small wins */
  microWin: [
    'Nice!',
    'Got it.',
    'Done.',
    'Check.',
    'Boom.',
  ],
  /** Messages for processing states */
  processing: [
    'Working on it...',
    'Give me a sec...',
    'Crunching numbers...',
    'Almost there...',
    'Making it perfect...',
  ],
}

/**
 * Get a random personality message for a given state
 */
export function getPersonalityMessage(state: keyof typeof PERSONALITY_MESSAGES): string {
  const messages = PERSONALITY_MESSAGES[state]
  return messages[Math.floor(Math.random() * messages.length)]
}
