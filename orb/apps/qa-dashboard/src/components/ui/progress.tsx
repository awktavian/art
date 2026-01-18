'use client'

import { cn, getColonyHex } from '@/lib/utils'
import type { ColonyColor } from '@/types'
import { motion } from 'framer-motion'
import { TIMING } from '@/types'

interface ProgressProps {
  value: number
  max?: number
  size?: 'sm' | 'md' | 'lg'
  color?: ColonyColor
  showValue?: boolean
  animate?: boolean
  className?: string
}

interface CircularProgressProps extends Omit<ProgressProps, 'size'> {
  size?: number
  strokeWidth?: number
}

const heightClasses = {
  sm: 'h-1',
  md: 'h-2',
  lg: 'h-3',
}

export function Progress({
  value,
  max = 100,
  size = 'md',
  color = 'crystal',
  showValue = false,
  animate = true,
  className,
}: ProgressProps) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100)

  // Determine color based on value if not specified
  const barColor =
    color === 'crystal'
      ? percentage >= 90
        ? 'grove'
        : percentage >= 70
          ? 'beacon'
          : percentage >= 50
            ? 'forge'
            : 'spark'
      : color

  const colorClasses: Record<ColonyColor, string> = {
    spark: 'bg-colony-spark',
    forge: 'bg-colony-forge',
    flow: 'bg-colony-flow',
    nexus: 'bg-colony-nexus',
    beacon: 'bg-colony-beacon',
    grove: 'bg-colony-grove',
    crystal: 'bg-colony-crystal',
  }

  return (
    <div className={cn('w-full', className)}>
      <div
        className={cn(
          'w-full bg-void-lighter rounded-full overflow-hidden',
          heightClasses[size]
        )}
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-label={`Progress: ${Math.round(percentage)}%`}
      >
        <motion.div
          className={cn('h-full rounded-full', colorClasses[barColor])}
          initial={animate ? { width: 0 } : undefined}
          animate={{ width: `${percentage}%` }}
          transition={{
            duration: TIMING.medium / 1000,
            ease: [0, 0, 0.2, 1],
          }}
        />
      </div>
      {showValue && (
        <span className="text-sm text-white/60 mt-1 tabular-nums">
          {Math.round(percentage)}%
        </span>
      )}
    </div>
  )
}

export function CircularProgress({
  value,
  max = 100,
  size = 64,
  strokeWidth = 4,
  color = 'crystal',
  showValue = true,
  animate = true,
  className,
}: CircularProgressProps) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100)
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius

  // Determine color based on value
  const strokeColor =
    color === 'crystal'
      ? percentage >= 90
        ? 'grove'
        : percentage >= 70
          ? 'beacon'
          : percentage >= 50
            ? 'forge'
            : 'spark'
      : color

  return (
    <div
      className={cn('relative inline-flex items-center justify-center', className)}
      style={{ width: size, height: size }}
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={`Progress: ${Math.round(percentage)}%`}
    >
      <svg width={size} height={size} className="transform -rotate-90">
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-void-lighter"
        />
        {/* Progress circle */}
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={getColonyHex(strokeColor)}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={animate ? { strokeDashoffset: circumference } : undefined}
          animate={{
            strokeDashoffset: circumference - (percentage / 100) * circumference,
          }}
          transition={{
            duration: TIMING.slow / 1000,
            ease: [0, 0, 0.2, 1],
          }}
        />
      </svg>
      {showValue && (
        <span
          className="absolute text-sm font-bold tabular-nums"
          style={{ color: getColonyHex(strokeColor) }}
        >
          {Math.round(percentage)}
        </span>
      )}
    </div>
  )
}

// Health score ring with label
export function HealthRing({
  score,
  size = 120,
  label = 'Health Score',
  className,
}: {
  score: number
  size?: number
  label?: string
  className?: string
}) {
  return (
    <div className={cn('flex flex-col items-center gap-2', className)}>
      <CircularProgress
        value={score}
        size={size}
        strokeWidth={8}
        showValue={false}
      />
      <div className="absolute flex flex-col items-center">
        <span
          className="text-3xl font-bold tabular-nums"
          style={{
            color: getColonyHex(
              score >= 90
                ? 'grove'
                : score >= 70
                  ? 'beacon'
                  : score >= 50
                    ? 'forge'
                    : 'spark'
            ),
          }}
        >
          {score}
        </span>
      </div>
      {label && (
        <span className="text-sm text-white/60 font-medium">{label}</span>
      )}
    </div>
  )
}
