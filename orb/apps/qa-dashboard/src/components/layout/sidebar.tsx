'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn, getPlatformIcon, getPlatformName } from '@/lib/utils'
import type { Platform, PlatformSummary } from '@/types'
import { HealthBadge } from '@/components/ui'
import { motion } from 'framer-motion'
import { TIMING } from '@/types'
import {
  Smartphone,
  Monitor,
  Server,
  Watch,
  Tv,
  Eye,
  Glasses,
  ChevronRight,
} from 'lucide-react'

interface SidebarProps {
  platforms?: PlatformSummary[]
  className?: string
}

const platformIcons: Record<Platform, typeof Smartphone> = {
  ios: Smartphone,
  android: Smartphone,
  'android-xr': Glasses,
  visionos: Eye,
  watchos: Watch,
  tvos: Tv,
  desktop: Monitor,
  hub: Server,
}

export function Sidebar({ platforms = [], className }: SidebarProps) {
  const pathname = usePathname()

  return (
    <aside
      className={cn(
        'w-64 h-[calc(100vh-4rem)] sticky top-16',
        'border-r border-white/10 bg-void-light/50',
        'overflow-y-auto custom-scrollbar',
        className
      )}
      aria-label="Platform sidebar"
    >
      <div className="p-4">
        <h2 className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-3">
          Platforms
        </h2>

        <nav className="space-y-1" aria-label="Platform navigation">
          {platforms.map((platform, index) => {
            const href = `/platform/${platform.platform}`
            const isActive = pathname === href
            const Icon = platformIcons[platform.platform]
            const hasIssues = platform.failedJourneys > 0
            const hasProgress = platform.inProgressJourneys > 0

            return (
              <motion.div
                key={platform.platform}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{
                  duration: TIMING.fast / 1000,
                  delay: index * (TIMING.micro / 1000),
                }}
              >
                <Link
                  href={href}
                  className={cn(
                    'group flex items-center gap-3 px-3 py-2.5 rounded-md',
                    'transition-all duration-fast',
                    'focus-visible:ring-2 focus-visible:ring-colony-crystal focus-visible:ring-offset-2 focus-visible:ring-offset-void-light',
                    isActive
                      ? 'bg-colony-crystal/10 text-colony-crystal'
                      : 'text-white/70 hover:text-white hover:bg-white/5'
                  )}
                  aria-current={isActive ? 'page' : undefined}
                >
                  <Icon className="w-5 h-5 flex-shrink-0" />

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium truncate">
                        {platform.displayName}
                      </span>
                      <HealthBadge score={platform.healthScore} size="sm" />
                    </div>

                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-white/40">
                        {platform.totalJourneys} tests
                      </span>
                      {hasIssues && (
                        <span className="text-xs text-colony-spark">
                          {platform.failedJourneys} failed
                        </span>
                      )}
                      {hasProgress && (
                        <span className="text-xs text-colony-forge">
                          {platform.inProgressJourneys} running
                        </span>
                      )}
                    </div>
                  </div>

                  <ChevronRight
                    className={cn(
                      'w-4 h-4 text-white/30 transition-transform duration-fast',
                      'group-hover:text-white/60 group-hover:translate-x-0.5',
                      isActive && 'text-colony-crystal'
                    )}
                  />
                </Link>
              </motion.div>
            )
          })}
        </nav>

        {platforms.length === 0 && (
          <div className="text-center py-8 text-white/40 text-sm">
            No platforms available
          </div>
        )}
      </div>

      {/* Quick actions */}
      <div className="p-4 border-t border-white/10">
        <h2 className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-3">
          Quick Actions
        </h2>
        <div className="space-y-1">
          <button
            className={cn(
              'w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm',
              'text-white/60 hover:text-white hover:bg-white/5',
              'transition-colors duration-fast'
            )}
          >
            Run All Tests
          </button>
          <button
            className={cn(
              'w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm',
              'text-white/60 hover:text-white hover:bg-white/5',
              'transition-colors duration-fast'
            )}
          >
            Generate Report
          </button>
        </div>
      </div>
    </aside>
  )
}

// Skeleton for loading state
export function SidebarSkeleton() {
  return (
    <aside className="w-64 h-[calc(100vh-4rem)] border-r border-white/10 bg-void-light/50 p-4">
      <div className="h-4 w-20 bg-void-lighter rounded mb-4" />
      <div className="space-y-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3 px-3 py-2.5">
            <div className="w-5 h-5 bg-void-lighter rounded" />
            <div className="flex-1">
              <div className="h-4 w-24 bg-void-lighter rounded mb-1" />
              <div className="h-3 w-16 bg-void-lighter rounded" />
            </div>
          </div>
        ))}
      </div>
    </aside>
  )
}
