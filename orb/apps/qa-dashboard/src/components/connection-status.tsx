'use client'

import { cn } from '@/lib/utils'
import { useConnectionStatus } from '@/hooks/use-websocket'
import type { ConnectionState } from '@/types'
import { TIMING } from '@/types'
import { motion, AnimatePresence } from 'framer-motion'
import { Wifi, WifiOff, Loader2, AlertCircle } from 'lucide-react'

interface ConnectionStatusProps {
  /** Show full status text or just icon */
  variant?: 'full' | 'compact' | 'icon'
  /** Additional class names */
  className?: string
  /** Show reconnection progress */
  showReconnectProgress?: boolean
}

const stateConfig: Record<
  ConnectionState,
  {
    icon: typeof Wifi
    label: string
    shortLabel: string
    color: string
    bgColor: string
    animate?: boolean
  }
> = {
  connected: {
    icon: Wifi,
    label: 'Connected',
    shortLabel: 'Live',
    color: 'text-colony-grove',
    bgColor: 'bg-colony-grove/20',
    animate: false,
  },
  connecting: {
    icon: Loader2,
    label: 'Connecting...',
    shortLabel: 'Connecting',
    color: 'text-colony-forge',
    bgColor: 'bg-colony-forge/20',
    animate: true,
  },
  reconnecting: {
    icon: Loader2,
    label: 'Reconnecting...',
    shortLabel: 'Reconnecting',
    color: 'text-colony-beacon',
    bgColor: 'bg-colony-beacon/20',
    animate: true,
  },
  disconnected: {
    icon: WifiOff,
    label: 'Disconnected',
    shortLabel: 'Offline',
    color: 'text-colony-spark',
    bgColor: 'bg-colony-spark/20',
    animate: false,
  },
}

export function ConnectionStatus({
  variant = 'full',
  className,
  showReconnectProgress = true,
}: ConnectionStatusProps) {
  const status = useConnectionStatus()
  const config = stateConfig[status.state]
  const Icon = config.icon

  // Calculate reconnect progress for visual feedback
  const reconnectProgress =
    status.state === 'reconnecting'
      ? Math.round((status.reconnectAttempts / status.maxReconnectAttempts) * 100)
      : 0

  if (variant === 'icon') {
    return (
      <div
        className={cn('relative', className)}
        role="status"
        aria-label={config.label}
      >
        <Icon
          className={cn(
            'w-4 h-4 transition-colors duration-fast',
            config.color,
            config.animate && 'animate-spin'
          )}
        />
        {/* Pulse indicator for connected state */}
        {status.state === 'connected' && (
          <motion.span
            className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-colony-grove"
            animate={{ scale: [1, 1.2, 1], opacity: [1, 0.7, 1] }}
            transition={{
              duration: TIMING.breathing / 1000,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
          />
        )}
      </div>
    )
  }

  if (variant === 'compact') {
    return (
      <div
        className={cn(
          'inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium',
          'transition-colors duration-fast',
          config.bgColor,
          config.color,
          className
        )}
        role="status"
        aria-label={config.label}
      >
        <Icon className={cn('w-3 h-3', config.animate && 'animate-spin')} />
        <span>{config.shortLabel}</span>
      </div>
    )
  }

  // Full variant with more details
  return (
    <div
      className={cn(
        'inline-flex items-center gap-2 px-3 py-1.5 rounded-lg',
        'transition-all duration-normal',
        config.bgColor,
        className
      )}
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      <div className="relative">
        <Icon
          className={cn(
            'w-4 h-4 transition-colors duration-fast',
            config.color,
            config.animate && 'animate-spin'
          )}
        />
        {/* Pulse indicator for connected state */}
        {status.state === 'connected' && (
          <motion.span
            className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-colony-grove"
            animate={{ scale: [1, 1.3, 1], opacity: [1, 0.6, 1] }}
            transition={{
              duration: TIMING.breathing / 1000,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
          />
        )}
      </div>

      <div className="flex flex-col">
        <span className={cn('text-xs font-medium leading-tight', config.color)}>
          {config.label}
        </span>

        <AnimatePresence mode="wait">
          {/* Show reconnect attempts */}
          {status.state === 'reconnecting' && showReconnectProgress && (
            <motion.span
              key="reconnect-info"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: TIMING.fast / 1000 }}
              className="text-[10px] text-white/50 leading-tight"
            >
              Attempt {status.reconnectAttempts}/{status.maxReconnectAttempts}
            </motion.span>
          )}

          {/* Show last error if disconnected */}
          {status.state === 'disconnected' && status.lastError && (
            <motion.span
              key="error-info"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: TIMING.fast / 1000 }}
              className="text-[10px] text-colony-spark/70 leading-tight flex items-center gap-1"
            >
              <AlertCircle className="w-2.5 h-2.5" />
              {status.lastError.length > 20
                ? status.lastError.slice(0, 20) + '...'
                : status.lastError}
            </motion.span>
          )}

          {/* Show last ping time if connected */}
          {status.state === 'connected' && status.lastPing && (
            <motion.span
              key="ping-info"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: TIMING.fast / 1000 }}
              className="text-[10px] text-white/40 leading-tight"
            >
              Last ping: {formatRelativeTime(status.lastPing)}
            </motion.span>
          )}
        </AnimatePresence>
      </div>

      {/* Reconnect progress bar */}
      {status.state === 'reconnecting' && showReconnectProgress && (
        <div className="w-12 h-1 bg-white/10 rounded-full overflow-hidden ml-1">
          <motion.div
            className="h-full bg-colony-beacon"
            initial={{ width: 0 }}
            animate={{ width: `${reconnectProgress}%` }}
            transition={{ duration: TIMING.normal / 1000 }}
          />
        </div>
      )}
    </div>
  )
}

/**
 * Format a timestamp as relative time (e.g., "2s ago", "1m ago")
 */
function formatRelativeTime(isoString: string): string {
  const now = Date.now()
  const then = new Date(isoString).getTime()
  const diffSeconds = Math.floor((now - then) / 1000)

  if (diffSeconds < 5) return 'just now'
  if (diffSeconds < 60) return `${diffSeconds}s ago`
  if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)}m ago`
  return `${Math.floor(diffSeconds / 3600)}h ago`
}

/**
 * Minimal connection indicator for use in tight spaces
 */
export function ConnectionDot({ className }: { className?: string }) {
  const status = useConnectionStatus()
  const config = stateConfig[status.state]

  return (
    <motion.span
      className={cn(
        'w-2 h-2 rounded-full transition-colors duration-fast',
        status.state === 'connected' && 'bg-colony-grove',
        status.state === 'connecting' && 'bg-colony-forge',
        status.state === 'reconnecting' && 'bg-colony-beacon',
        status.state === 'disconnected' && 'bg-colony-spark',
        className
      )}
      animate={
        status.state === 'connected'
          ? { scale: [1, 1.2, 1], opacity: [1, 0.7, 1] }
          : status.state === 'connecting' || status.state === 'reconnecting'
          ? { opacity: [1, 0.4, 1] }
          : undefined
      }
      transition={{
        duration: TIMING.breathing / 1000,
        repeat: Infinity,
        ease: 'easeInOut',
      }}
      role="status"
      aria-label={config.label}
    />
  )
}
