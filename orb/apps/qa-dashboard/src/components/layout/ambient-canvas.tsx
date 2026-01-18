'use client'

import { useEffect, useRef, useCallback } from 'react'
import { TIMING } from '@/types'

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  r: number
  color: string
  phase: number
  type: 'small' | 'medium' | 'large'
}

/**
 * Colony colors at low opacity for ambient effect
 * Inspired by ~/projects/art/catastrophes.html
 */
const COLONY_COLORS = [
  'rgba(100, 210, 255, 0.04)', // crystal
  'rgba(50, 215, 75, 0.03)',   // grove
  'rgba(255, 107, 53, 0.025)', // spark
  'rgba(175, 82, 222, 0.02)',  // nexus
  'rgba(196, 163, 90, 0.03)',  // gold accent
]

/**
 * AmbientCanvas - Subtle animated background for visual atmosphere
 *
 * Creates gentle floating particles in Colony colors that breathe
 * with Fibonacci-based timing. Respects reduced motion preferences.
 */
export function AmbientCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const particlesRef = useRef<Particle[]>([])
  const animationRef = useRef<number>(0)
  const timeRef = useRef(0)

  const createParticles = useCallback((width: number, height: number) => {
    const particles: Particle[] = []
    const isMobile = width < 768
    const count = isMobile ? 25 : 45

    for (let i = 0; i < count; i++) {
      const type = Math.random()
      let r: number, speed: number

      if (type < 0.6) {
        // Small, faster particles (60%)
        r = 1 + Math.random() * 2
        speed = 0.08 + Math.random() * 0.12
      } else if (type < 0.85) {
        // Medium particles (25%)
        r = 2.5 + Math.random() * 2
        speed = 0.04 + Math.random() * 0.08
      } else {
        // Large, slow particles (15%)
        r = 4 + Math.random() * 3
        speed = 0.02 + Math.random() * 0.04
      }

      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * speed,
        vy: (Math.random() - 0.5) * speed,
        r,
        color: COLONY_COLORS[Math.floor(Math.random() * COLONY_COLORS.length)],
        phase: Math.random() * Math.PI * 2,
        type: type < 0.6 ? 'small' : type < 0.85 ? 'medium' : 'large',
      })
    }

    return particles
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    // Check for reduced motion preference
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (prefersReducedMotion) {
      return // Don't animate if user prefers reduced motion
    }

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = Math.min(window.devicePixelRatio || 1, 2)

    const resize = () => {
      const rect = canvas.parentElement?.getBoundingClientRect()
      if (!rect) return

      canvas.width = rect.width * dpr
      canvas.height = rect.height * dpr
      canvas.style.width = `${rect.width}px`
      canvas.style.height = `${rect.height}px`
      ctx.scale(dpr, dpr)

      // Recreate particles on resize
      particlesRef.current = createParticles(rect.width, rect.height)
    }

    resize()
    window.addEventListener('resize', resize)

    const animate = () => {
      const rect = canvas.parentElement?.getBoundingClientRect()
      if (!rect) return

      const width = rect.width
      const height = rect.height

      // Use Fibonacci-based time increment (based on 610ms)
      timeRef.current += TIMING.slow / 60000

      ctx.clearRect(0, 0, canvas.width, canvas.height)

      // Draw subtle connections between nearby medium/large particles
      ctx.strokeStyle = 'rgba(196, 163, 90, 0.015)'
      ctx.lineWidth = 0.5

      for (let i = 0; i < particlesRef.current.length; i++) {
        const p1 = particlesRef.current[i]
        if (p1.type === 'small') continue

        for (let j = i + 1; j < particlesRef.current.length; j++) {
          const p2 = particlesRef.current[j]
          if (p2.type === 'small') continue

          const dx = p2.x - p1.x
          const dy = p2.y - p1.y
          const dist = Math.sqrt(dx * dx + dy * dy)

          if (dist < 120 && dist > 0) {
            const alpha = (1 - dist / 120) * 0.02
            ctx.strokeStyle = `rgba(196, 163, 90, ${alpha})`
            ctx.beginPath()
            ctx.moveTo(p1.x, p1.y)
            ctx.lineTo(p2.x, p2.y)
            ctx.stroke()
          }
        }
      }

      // Draw and update particles
      particlesRef.current.forEach((p) => {
        // Gentle floating motion (Fibonacci-influenced)
        p.x += p.vx + Math.sin(timeRef.current * 0.5 + p.phase) * 0.06
        p.y += p.vy + Math.cos(timeRef.current * 0.3 + p.phase) * 0.04

        // Wrap around edges
        if (p.x < -15) p.x = width + 15
        if (p.x > width + 15) p.x = -15
        if (p.y < -15) p.y = height + 15
        if (p.y > height + 15) p.y = -15

        // Subtle pulse (breathing effect)
        const pulse = 0.8 + Math.sin(timeRef.current * 0.4 + p.phase) * 0.2

        // Draw particle
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r * pulse, 0, Math.PI * 2)
        ctx.fillStyle = p.color
        ctx.fill()

        // Add soft glow for larger particles
        if (p.type === 'large') {
          const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 3 * pulse)
          glow.addColorStop(0, p.color)
          glow.addColorStop(1, 'transparent')
          ctx.fillStyle = glow
          ctx.beginPath()
          ctx.arc(p.x, p.y, p.r * 3 * pulse, 0, Math.PI * 2)
          ctx.fill()
        }
      })

      animationRef.current = requestAnimationFrame(animate)
    }

    animate()

    return () => {
      window.removeEventListener('resize', resize)
      cancelAnimationFrame(animationRef.current)
    }
  }, [createParticles])

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0"
      aria-hidden="true"
      style={{ width: '100vw', height: '100vh' }}
    />
  )
}
