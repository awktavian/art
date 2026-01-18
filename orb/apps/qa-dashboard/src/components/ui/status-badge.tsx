'use client'

import { cn, getStatusText, getStatusColor } from '@/lib/utils'
import type { TestStatus, Severity, ColonyColor } from '@/types'
import { motion } from 'framer-motion'
import { TIMING } from '@/types'
import { useReducedMotion } from '@/hooks/use-reduced-motion'

interface StatusBadgeProps {
  status: TestStatus
  size?: 'sm' | 'md' | 'lg'
  /** Show status icon (recommended for color-blind accessibility) */
  showIcon?: boolean
  showDot?: boolean
  animate?: boolean
  className?: string
}

interface SeverityBadgeProps {
  severity: Severity
  size?: 'sm' | 'md' | 'lg'
  /** Show severity icon (recommended for color-blind accessibility) */
  showIcon?: boolean
  className?: string
}

// WCAG 2.1 SC 1.4.1: Don't use color as the only visual means of conveying information
// Status icons provide non-color indicators for accessibility
const StatusIcon = ({ status, size }: { status: TestStatus; size: 'sm' | 'md' | 'lg' }) => {
  const sizeClasses = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  }

  const iconClass = cn(sizeClasses[size], 'flex-shrink-0')

  switch (status) {
    case 'pass':
      // Checkmark icon
      return (
        <svg className={iconClass} viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
        </svg>
      )
    case 'fail':
      // X icon
      return (
        <svg className={iconClass} viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
        </svg>
      )
    case 'in_progress':
      // Spinner/loading icon
      return (
        <svg className={cn(iconClass, 'animate-spin')} viewBox="0 0 20 20" fill="none" stroke="currentColor" aria-hidden="true">
          <circle cx="10" cy="10" r="7" strokeWidth="2" strokeDasharray="22" strokeDashoffset="11" strokeLinecap="round" />
        </svg>
      )
    case 'pending':
      // Clock icon
      return (
        <svg className={iconClass} viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
        </svg>
      )
    case 'warning':
      // Warning triangle icon
      return (
        <svg className={iconClass} viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
        </svg>
      )
    default:
      return null
  }
}

const SeverityIcon = ({ severity, size }: { severity: Severity; size: 'sm' | 'md' | 'lg' }) => {
  const sizeClasses = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  }

  const iconClass = cn(sizeClasses[size], 'flex-shrink-0')

  switch (severity) {
    case 'critical':
      // Exclamation in circle
      return (
        <svg className={iconClass} viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
        </svg>
      )
    case 'warning':
      // Warning triangle
      return (
        <svg className={iconClass} viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
        </svg>
      )
    case 'info':
      // Info circle
      return (
        <svg className={iconClass} viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
        </svg>
      )
    default:
      return null
  }
}

const sizeClasses = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-2.5 py-1 text-sm',
  lg: 'px-3 py-1.5 text-base',
}

const dotSizeClasses = {
  sm: 'w-1.5 h-1.5',
  md: 'w-2 h-2',
  lg: 'w-2.5 h-2.5',
}

const colonyColorClasses: Record<ColonyColor, { bg: string; text: string; dot: string }> = {
  spark: {
    bg: 'bg-colony-spark/20',
    text: 'text-colony-spark',
    dot: 'bg-colony-spark',
  },
  forge: {
    bg: 'bg-colony-forge/20',
    text: 'text-colony-forge',
    dot: 'bg-colony-forge',
  },
  flow: {
    bg: 'bg-colony-flow/20',
    text: 'text-colony-flow',
    dot: 'bg-colony-flow',
  },
  nexus: {
    bg: 'bg-colony-nexus/20',
    text: 'text-colony-nexus',
    dot: 'bg-colony-nexus',
  },
  beacon: {
    bg: 'bg-colony-beacon/20',
    text: 'text-colony-beacon',
    dot: 'bg-colony-beacon',
  },
  grove: {
    bg: 'bg-colony-grove/20',
    text: 'text-colony-grove',
    dot: 'bg-colony-grove',
  },
  crystal: {
    bg: 'bg-colony-crystal/20',
    text: 'text-colony-crystal',
    dot: 'bg-colony-crystal',
  },
}

const statusToColony: Record<TestStatus, ColonyColor> = {
  pass: 'grove',
  fail: 'spark',
  in_progress: 'forge',
  pending: 'crystal',
  warning: 'beacon',
}

const severityToColony: Record<Severity, ColonyColor> = {
  critical: 'spark',
  warning: 'beacon',
  info: 'crystal',
}

export function StatusBadge({
  status,
  size = 'md',
  showIcon = true, // Default to true for WCAG 1.4.1 compliance
  showDot = false, // Deprecated in favor of showIcon
  animate = true,
  className,
}: StatusBadgeProps) {
  const colony = statusToColony[status]
  const colors = colonyColorClasses[colony]
  const text = getStatusText(status)
  const isAnimating = animate && (status === 'in_progress' || status === 'pending')
  const prefersReducedMotion = useReducedMotion()

  // Disable animations if user prefers reduced motion
  const shouldAnimate = isAnimating && !prefersReducedMotion

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full font-medium',
        'transition-colors duration-fast ease-standard',
        sizeClasses[size],
        colors.bg,
        colors.text,
        className
      )}
      role="status"
      aria-label={`Status: ${text}`}
    >
      {/* Icon provides non-color indicator (WCAG 1.4.1 compliance) */}
      {showIcon && <StatusIcon status={status} size={size} />}
      {/* Legacy dot support - deprecated, use showIcon instead */}
      {!showIcon && showDot && (
        <motion.span
          className={cn('rounded-full', dotSizeClasses[size], colors.dot)}
          animate={shouldAnimate ? { opacity: [1, 0.4, 1] } : undefined}
          transition={
            shouldAnimate
              ? {
                  duration: TIMING.breathing / 1000,
                  repeat: Infinity,
                  ease: 'easeInOut',
                }
              : undefined
          }
          aria-hidden="true"
        />
      )}
      {text}
    </span>
  )
}

export function SeverityBadge({
  severity,
  size = 'md',
  showIcon = true, // Default to true for WCAG 1.4.1 compliance
  className,
}: SeverityBadgeProps) {
  const colony = severityToColony[severity]
  const colors = colonyColorClasses[colony]
  const text = severity.charAt(0).toUpperCase() + severity.slice(1)

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full font-medium',
        'transition-colors duration-fast ease-standard',
        sizeClasses[size],
        colors.bg,
        colors.text,
        className
      )}
      role="status"
      aria-label={`Severity: ${text}`}
    >
      {/* Icon provides non-color indicator (WCAG 1.4.1 compliance) */}
      {showIcon ? (
        <SeverityIcon severity={severity} size={size} />
      ) : (
        <span className={cn('rounded-full', dotSizeClasses[size], colors.dot)} aria-hidden="true" />
      )}
      {text}
    </span>
  )
}

// Health icon that changes based on score level (non-color indicator)
const HealthIcon = ({ score, size }: { score: number; size: 'sm' | 'md' | 'lg' }) => {
  const sizeClasses = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  }

  const iconClass = cn(sizeClasses[size], 'flex-shrink-0')

  if (score >= 90) {
    // Heart icon for excellent health
    return (
      <svg className={iconClass} viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
        <path fillRule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clipRule="evenodd" />
      </svg>
    )
  } else if (score >= 70) {
    // Thumbs up for good health
    return (
      <svg className={iconClass} viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
        <path d="M2 10.5a1.5 1.5 0 113 0v6a1.5 1.5 0 01-3 0v-6zM6 10.333v5.43a2 2 0 001.106 1.79l.05.025A4 4 0 008.943 18h5.416a2 2 0 001.962-1.608l1.2-6A2 2 0 0015.56 8H12V4a2 2 0 00-2-2 1 1 0 00-1 1v.667a4 4 0 01-.8 2.4L6.8 7.933a4 4 0 00-.8 2.4z" />
      </svg>
    )
  } else if (score >= 50) {
    // Minus circle for moderate health
    return (
      <svg className={iconClass} viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM7 9a1 1 0 000 2h6a1 1 0 100-2H7z" clipRule="evenodd" />
      </svg>
    )
  } else {
    // Exclamation for poor health
    return (
      <svg className={iconClass} viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
        <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
      </svg>
    )
  }
}

export function HealthBadge({
  score,
  size = 'md',
  showIcon = true,
  className,
}: {
  score: number
  size?: 'sm' | 'md' | 'lg'
  /** Show health icon (recommended for color-blind accessibility) */
  showIcon?: boolean
  className?: string
}) {
  const colony: ColonyColor =
    score >= 90 ? 'grove' : score >= 70 ? 'beacon' : score >= 50 ? 'forge' : 'spark'
  const colors = colonyColorClasses[colony]

  // Descriptive health level for screen readers
  const healthLevel = score >= 90 ? 'Excellent' : score >= 70 ? 'Good' : score >= 50 ? 'Fair' : 'Poor'

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full font-bold tabular-nums',
        'transition-colors duration-fast ease-standard',
        sizeClasses[size],
        colors.bg,
        colors.text,
        className
      )}
      role="meter"
      aria-valuenow={score}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`Health score: ${score}% - ${healthLevel}`}
    >
      {/* Icon provides non-color indicator (WCAG 1.4.1 compliance) */}
      {showIcon && <HealthIcon score={score} size={size} />}
      {score}%
    </span>
  )
}
