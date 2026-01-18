'use client'

import { forwardRef, type HTMLAttributes, type KeyboardEvent } from 'react'
import { cn } from '@/lib/utils'
import { motion, type HTMLMotionProps } from 'framer-motion'
import { TIMING } from '@/types'
import type { ColonyColor } from '@/types'
import { useReducedMotion } from '@/hooks/use-reduced-motion'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'elevated' | 'outlined' | 'colony'
  colonyColor?: ColonyColor
  interactive?: boolean
  asMotion?: boolean
  /** Accessible label for the card region */
  'aria-label'?: string
  /** ID of the heading element that labels this card */
  'aria-labelledby'?: string
}

const colonyGradients: Record<ColonyColor, string> = {
  spark: 'bg-colony-spark-gradient border-colony-spark/30',
  forge: 'bg-colony-forge-gradient border-colony-forge/30',
  flow: 'bg-colony-flow-gradient border-colony-flow/30',
  nexus: 'bg-colony-nexus-gradient border-colony-nexus/30',
  beacon: 'bg-colony-beacon-gradient border-colony-beacon/30',
  grove: 'bg-colony-grove-gradient border-colony-grove/30',
  crystal: 'bg-colony-crystal-gradient border-colony-crystal/30',
}

const variantClasses = {
  default: 'bg-void-light',
  elevated: 'bg-void-light shadow-card',
  outlined: 'bg-transparent border border-white/10',
  colony: 'border',
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  (
    {
      className,
      variant = 'default',
      colonyColor,
      interactive = false,
      asMotion = false,
      children,
      onClick,
      onKeyDown,
      'aria-label': ariaLabel,
      'aria-labelledby': ariaLabelledBy,
      ...props
    },
    ref
  ) => {
    const prefersReducedMotion = useReducedMotion()

    // Keyboard handler for interactive cards
    const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
      onKeyDown?.(event)

      // Make interactive cards keyboard accessible
      if (interactive && onClick && (event.key === 'Enter' || event.key === ' ')) {
        event.preventDefault()
        onClick(event as unknown as React.MouseEvent<HTMLDivElement>)
      }
    }

    const baseClasses = cn(
      'rounded-lg p-4',
      'transition-all duration-normal ease-standard',
      variant === 'colony' && colonyColor
        ? colonyGradients[colonyColor]
        : variantClasses[variant],
      interactive && 'cursor-pointer hover:shadow-card-hover hover:-translate-y-0.5',
      interactive && 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-colony-crystal focus-visible:ring-offset-2 focus-visible:ring-offset-void',
      className
    )

    // Accessibility props for cards acting as regions
    const accessibilityProps = {
      role: 'region' as const,
      'aria-label': ariaLabel,
      'aria-labelledby': ariaLabelledBy,
      ...(interactive && {
        tabIndex: 0,
        role: 'button' as const,
        'aria-pressed': undefined, // Can be set by parent if needed
      }),
    }

    // Motion animation props respecting reduced motion preference
    const motionAnimationProps = prefersReducedMotion
      ? {
          initial: { opacity: 1, y: 0 },
          animate: { opacity: 1, y: 0 },
        }
      : {
          initial: { opacity: 0, y: 8 },
          animate: { opacity: 1, y: 0 },
          transition: { duration: TIMING.normal / 1000, ease: [0, 0, 0.2, 1] },
        }

    const hoverProps =
      interactive && !prefersReducedMotion
        ? {
            whileHover: {
              y: -2,
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
            },
          }
        : {}

    if (asMotion || interactive) {
      return (
        <motion.div
          ref={ref}
          className={baseClasses}
          onClick={onClick}
          onKeyDown={handleKeyDown}
          {...accessibilityProps}
          {...motionAnimationProps}
          {...hoverProps}
          {...(props as HTMLMotionProps<'div'>)}
        >
          {children}
        </motion.div>
      )
    }

    return (
      <div
        ref={ref}
        className={baseClasses}
        onClick={onClick}
        onKeyDown={handleKeyDown}
        {...accessibilityProps}
        {...props}
      >
        {children}
      </div>
    )
  }
)

Card.displayName = 'Card'

export function CardHeader({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('flex items-center justify-between mb-3', className)} {...props}>
      {children}
    </div>
  )
}

interface CardTitleProps extends HTMLAttributes<HTMLHeadingElement> {
  /** Heading level (h2-h6). Defaults to h3. */
  as?: 'h2' | 'h3' | 'h4' | 'h5' | 'h6'
}

export function CardTitle({
  className,
  children,
  as: Component = 'h3',
  id,
  ...props
}: CardTitleProps) {
  return (
    <Component
      id={id}
      className={cn('text-lg font-semibold text-white', className)}
      {...props}
    >
      {children}
    </Component>
  )
}

export function CardDescription({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={cn('text-sm text-white/60', className)} {...props}>
      {children}
    </p>
  )
}

export function CardContent({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('', className)} {...props}>
      {children}
    </div>
  )
}

export function CardFooter({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('flex items-center justify-between mt-4 pt-4 border-t border-white/10', className)}
      {...props}
    >
      {children}
    </div>
  )
}

// Skeleton card for loading states
export function CardSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'rounded-lg bg-void-light p-4 animate-pulse',
        className
      )}
    >
      <div className="flex items-center justify-between mb-4">
        <div className="h-5 w-32 bg-void-lighter rounded" />
        <div className="h-5 w-16 bg-void-lighter rounded-full" />
      </div>
      <div className="space-y-2">
        <div className="h-4 w-full bg-void-lighter rounded" />
        <div className="h-4 w-3/4 bg-void-lighter rounded" />
      </div>
      <div className="flex items-center gap-4 mt-4 pt-4 border-t border-white/5">
        <div className="h-4 w-20 bg-void-lighter rounded" />
        <div className="h-4 w-20 bg-void-lighter rounded" />
      </div>
    </div>
  )
}
