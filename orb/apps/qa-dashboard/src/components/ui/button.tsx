'use client'

import { forwardRef, type ButtonHTMLAttributes, type ReactNode, type KeyboardEvent } from 'react'
import { cn } from '@/lib/utils'
import { motion, type HTMLMotionProps } from 'framer-motion'
import { TIMING } from '@/types'
import { useReducedMotion } from '@/hooks/use-reduced-motion'

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'success'
type ButtonSize = 'sm' | 'md' | 'lg' | 'icon'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  isLoading?: boolean
  leftIcon?: ReactNode
  rightIcon?: ReactNode
  asMotion?: boolean
  /** Accessible label for icon-only buttons */
  'aria-label'?: string
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: cn(
    'bg-colony-crystal text-void',
    'hover:bg-colony-crystal/90',
    'focus-visible:ring-colony-crystal'
  ),
  secondary: cn(
    'bg-void-lighter text-white',
    'hover:bg-void-lighter/80',
    'focus-visible:ring-white/50'
  ),
  ghost: cn(
    'bg-transparent text-white/70',
    'hover:text-white hover:bg-white/10',
    'focus-visible:ring-white/50'
  ),
  danger: cn(
    'bg-status-fail/20 text-status-fail',
    'hover:bg-status-fail/30',
    'focus-visible:ring-status-fail'
  ),
  success: cn(
    'bg-status-pass/20 text-status-pass',
    'hover:bg-status-pass/30',
    'focus-visible:ring-status-pass'
  ),
}

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-sm gap-1.5',
  md: 'h-10 px-4 text-base gap-2',
  lg: 'h-12 px-6 text-lg gap-2.5',
  icon: 'h-10 w-10 p-0',
}

const LoadingSpinner = () => (
  <svg
    className="animate-spin h-4 w-4"
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    viewBox="0 0 24 24"
    aria-hidden="true"
  >
    <circle
      className="opacity-25"
      cx="12"
      cy="12"
      r="10"
      stroke="currentColor"
      strokeWidth="4"
    />
    <path
      className="opacity-75"
      fill="currentColor"
      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
    />
  </svg>
)

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'primary',
      size = 'md',
      isLoading = false,
      disabled,
      leftIcon,
      rightIcon,
      children,
      asMotion = false,
      onKeyDown,
      ...props
    },
    ref
  ) => {
    const isDisabled = disabled || isLoading
    const prefersReducedMotion = useReducedMotion()

    // Keyboard handler for accessibility - ensures Enter and Space work consistently
    const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
      // Call user's onKeyDown if provided
      onKeyDown?.(event)

      // Ensure Enter key triggers click (Space already does by default)
      if (event.key === 'Enter' && !isDisabled) {
        event.currentTarget.click()
      }
    }

    const baseClasses = cn(
      'inline-flex items-center justify-center rounded-md font-medium',
      'transition-all duration-fast ease-standard',
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-void',
      'disabled:opacity-50 disabled:cursor-not-allowed',
      variantClasses[variant],
      sizeClasses[size],
      className
    )

    const content = (
      <>
        {isLoading && <LoadingSpinner />}
        {!isLoading && leftIcon}
        {children}
        {!isLoading && rightIcon}
      </>
    )

    // Respect prefers-reduced-motion for Framer Motion animations
    const motionProps = prefersReducedMotion
      ? {}
      : {
          whileHover: { scale: isDisabled ? 1 : 1.02 },
          whileTap: { scale: isDisabled ? 1 : 0.98 },
          transition: { duration: TIMING.micro / 1000 },
        }

    if (asMotion) {
      return (
        <motion.button
          ref={ref}
          className={baseClasses}
          disabled={isDisabled}
          onKeyDown={handleKeyDown}
          aria-busy={isLoading}
          {...motionProps}
          {...(props as HTMLMotionProps<'button'>)}
        >
          {content}
        </motion.button>
      )
    }

    return (
      <button
        ref={ref}
        className={baseClasses}
        disabled={isDisabled}
        onKeyDown={handleKeyDown}
        aria-busy={isLoading}
        {...props}
      >
        {content}
      </button>
    )
  }
)

Button.displayName = 'Button'

// Icon button variant for common use cases
export function IconButton({
  icon,
  label,
  variant = 'ghost',
  size = 'icon',
  className,
  ...props
}: Omit<ButtonProps, 'children' | 'leftIcon' | 'rightIcon'> & {
  icon: ReactNode
  label: string
}) {
  return (
    <Button
      variant={variant}
      size={size}
      className={cn('rounded-full', className)}
      aria-label={label}
      title={label}
      {...props}
    >
      {icon}
    </Button>
  )
}
