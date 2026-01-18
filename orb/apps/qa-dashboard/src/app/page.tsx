'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { cn, formatRelativeTime, calculatePassRate, getColonyHex } from '@/lib/utils'
import { api } from '@/lib/api'
import type { PlatformSummary, UserJourney } from '@/types'
import { Card, CardHeader, CardTitle, CardSkeleton, StatusBadge, HealthBadge, CircularProgress } from '@/components/ui'
import { StatsGrid, TrendChart } from '@/components/charts'
import { Sidebar, SidebarSkeleton } from '@/components/layout'
import { VideoThumbnail, VideoThumbnailSkeleton } from '@/components/video'
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
  TrendingUp,
  TrendingDown,
  Minus,
  Clock,
  CheckCircle,
  XCircle,
  PlayCircle,
  ArrowRight,
} from 'lucide-react'
import type { Platform } from '@/types'

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

export default function DashboardPage() {
  // Fetch platform summaries
  const {
    data: platforms,
    isLoading: platformsLoading,
    error: platformsError,
  } = useQuery({
    queryKey: ['platforms'],
    queryFn: api.fetchPlatformSummaries,
  })

  // Fetch recent journeys
  const {
    data: journeys,
    isLoading: journeysLoading,
    error: journeysError,
  } = useQuery({
    queryKey: ['journeys'],
    queryFn: () => api.fetchJourneys(),
  })

  // Fetch trend data
  const { data: trendData, error: trendError } = useQuery({
    queryKey: ['trends'],
    queryFn: () => api.fetchTrendData(),
  })

  const overallHealth = platforms ? api.calculateOverallHealth(platforms) : 0

  // Calculate aggregate stats
  const totalTests = platforms?.reduce((sum, p) => sum + p.totalJourneys, 0) || 0
  const totalPassed = platforms?.reduce((sum, p) => sum + p.passedJourneys, 0) || 0
  const totalFailed = platforms?.reduce((sum, p) => sum + p.failedJourneys, 0) || 0
  const inProgress = platforms?.reduce((sum, p) => sum + p.inProgressJourneys, 0) || 0
  const passRate = calculatePassRate(totalPassed, totalTests)

  // Get recent failed journeys
  const recentFailed = journeys?.filter((j) => j.status === 'fail').slice(0, 3) || []

  return (
    <div className="flex">
      {/* Sidebar */}
      {platformsLoading ? (
        <SidebarSkeleton />
      ) : (
        <Sidebar platforms={platforms} />
      )}

      {/* Main content */}
      <div className="flex-1 p-6 overflow-auto">
        {/* Page header with display typography */}
        <motion.div
          className="mb-8"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: TIMING.normal / 1000 }}
        >
          <h1 className="font-display text-4xl font-semibold tracking-wide mb-2">
            <span className="text-gold">Quality</span>
            <span className="text-white/80"> Dashboard</span>
          </h1>
          <p className="text-white/50 tracking-wide">
            Monitor test health across all platforms
          </p>
          {/* Decorative gold underline */}
          <div className="mt-4 h-px w-24 bg-gradient-to-r from-gold to-transparent" aria-hidden="true" />
        </motion.div>

        {/* Health score and stats */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-8">
          {/* Overall health ring */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: TIMING.normal / 1000 }}
          >
            <Card variant="elevated" className="h-full flex flex-col items-center justify-center py-8">
              <div className="relative">
                <CircularProgress
                  value={overallHealth}
                  size={140}
                  strokeWidth={12}
                  showValue={false}
                />
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span
                    className="text-4xl font-bold tabular-nums"
                    style={{
                      color: getColonyHex(
                        overallHealth >= 90
                          ? 'grove'
                          : overallHealth >= 70
                            ? 'beacon'
                            : overallHealth >= 50
                              ? 'forge'
                              : 'spark'
                      ),
                    }}
                  >
                    {overallHealth}
                  </span>
                </div>
              </div>
              <span className="text-sm text-white/60 mt-4 font-medium">
                Overall Health Score
              </span>
            </Card>
          </motion.div>

          {/* Stats cards */}
          <motion.div
            className="lg:col-span-3 grid grid-cols-2 sm:grid-cols-4 gap-4"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: TIMING.normal / 1000, delay: TIMING.micro / 1000 }}
          >
            <Card variant="colony" colonyColor="crystal" className="text-center py-6">
              <div className="text-3xl font-bold text-colony-crystal tabular-nums mb-1">
                {totalTests}
              </div>
              <div className="text-sm text-white/60">Total Tests</div>
            </Card>
            <Card variant="colony" colonyColor="grove" className="text-center py-6">
              <div className="text-3xl font-bold text-colony-grove tabular-nums mb-1">
                {passRate}%
              </div>
              <div className="text-sm text-white/60">Pass Rate</div>
            </Card>
            <Card variant="colony" colonyColor="spark" className="text-center py-6">
              <div className="text-3xl font-bold text-colony-spark tabular-nums mb-1">
                {totalFailed}
              </div>
              <div className="text-sm text-white/60">Failed</div>
            </Card>
            <Card variant="colony" colonyColor="forge" className="text-center py-6">
              <div className="text-3xl font-bold text-colony-forge tabular-nums mb-1">
                {inProgress}
              </div>
              <div className="text-sm text-white/60">In Progress</div>
            </Card>
          </motion.div>
        </div>

        {/* Platform grid */}
        <motion.section
          className="mb-8"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: TIMING.normal / 1000, delay: TIMING.fast / 1000 }}
        >
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-display text-2xl font-medium text-white/90">Platform Status</h2>
            <Link
              href="/reports"
              className="text-sm text-colony-crystal hover:underline flex items-center gap-1"
            >
              View all reports
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          {platformsLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <CardSkeleton key={i} />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {platforms?.map((platform, index) => (
                <PlatformCard key={platform.platform} platform={platform} index={index} />
              ))}
            </div>
          )}
        </motion.section>

        {/* Trend chart */}
        {trendData && (
          <motion.section
            className="mb-8"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: TIMING.normal / 1000, delay: TIMING.normal / 1000 }}
          >
            <Card variant="elevated" className="p-6">
              <h2 className="font-display text-2xl font-medium text-white/90 mb-4">Pass Rate Trend</h2>
              <TrendChart
                data={trendData}
                dataKey="passRate"
                color="grove"
                height={250}
              />
            </Card>
          </motion.section>
        )}

        {/* Recent failures */}
        {recentFailed.length > 0 && (
          <motion.section
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: TIMING.normal / 1000, delay: TIMING.medium / 1000 }}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-display text-2xl font-medium text-white/90">Recent Failures</h2>
              <Link
                href="/analysis"
                className="text-sm text-colony-crystal hover:underline flex items-center gap-1"
              >
                View analysis
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {recentFailed.map((journey) => (
                <JourneyCard key={journey.id} journey={journey} />
              ))}
            </div>
          </motion.section>
        )}
      </div>
    </div>
  )
}

// Platform card component
function PlatformCard({
  platform,
  index,
}: {
  platform: PlatformSummary
  index: number
}) {
  const Icon = platformIcons[platform.platform]
  const TrendIcon =
    platform.trend === 'up' ? TrendingUp : platform.trend === 'down' ? TrendingDown : Minus
  const trendColor =
    platform.trend === 'up' ? 'grove' : platform.trend === 'down' ? 'spark' : 'crystal'

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: TIMING.fast / 1000,
        delay: index * (TIMING.micro / 1000),
      }}
    >
      <Link href={`/platform/${platform.platform}`}>
        <Card
          variant="elevated"
          interactive
          className="group"
        >
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-colony-crystal/10">
                <Icon className="w-5 h-5 text-colony-crystal" />
              </div>
              <div>
                <CardTitle className="text-base">{platform.displayName}</CardTitle>
                <p className="text-xs text-white/40">
                  Last run {formatRelativeTime(platform.lastTestTime)}
                </p>
              </div>
            </div>
            <HealthBadge score={platform.healthScore} />
          </CardHeader>

          <div className="grid grid-cols-3 gap-4 mt-4">
            <div className="text-center">
              <div className="flex items-center justify-center gap-1 text-colony-grove mb-1">
                <CheckCircle className="w-4 h-4" />
                <span className="font-semibold tabular-nums">{platform.passedJourneys}</span>
              </div>
              <p className="text-xs text-white/40">Passed</p>
            </div>
            <div className="text-center">
              <div className="flex items-center justify-center gap-1 text-colony-spark mb-1">
                <XCircle className="w-4 h-4" />
                <span className="font-semibold tabular-nums">{platform.failedJourneys}</span>
              </div>
              <p className="text-xs text-white/40">Failed</p>
            </div>
            <div className="text-center">
              <div className="flex items-center justify-center gap-1 text-colony-forge mb-1">
                <PlayCircle className="w-4 h-4" />
                <span className="font-semibold tabular-nums">{platform.inProgressJourneys}</span>
              </div>
              <p className="text-xs text-white/40">Running</p>
            </div>
          </div>

          <div className="flex items-center justify-between mt-4 pt-4 border-t border-white/10">
            <div className="flex items-center gap-1 text-sm" style={{ color: getColonyHex(trendColor) }}>
              <TrendIcon className="w-4 h-4" />
              <span>
                {platform.trend === 'stable'
                  ? 'Stable'
                  : `${platform.trendValue > 0 ? '+' : ''}${platform.trendValue}%`}
              </span>
            </div>
            <span className="text-xs text-white/40">
              {platform.totalJourneys} total tests
            </span>
          </div>
        </Card>
      </Link>
    </motion.div>
  )
}

// Journey card component
function JourneyCard({ journey }: { journey: UserJourney }) {
  return (
    <Link href={`/journey/${journey.id}`}>
      <Card variant="elevated" interactive className="group">
        <VideoThumbnail
          src={journey.thumbnailUrl}
          alt={journey.name}
          duration={journey.duration}
          status={journey.status}
          className="mb-3"
        />

        <h3 className="font-medium mb-1 truncate group-hover:text-colony-crystal transition-colors">
          {journey.name}
        </h3>

        <div className="flex items-center gap-2 text-xs text-white/40">
          <span className="capitalize">{journey.platform}</span>
          <span>•</span>
          <span>{formatRelativeTime(journey.createdAt)}</span>
        </div>

        {journey.geminiSummary && (
          <p className="text-xs text-white/60 mt-2 line-clamp-2">
            {journey.geminiSummary}
          </p>
        )}
      </Card>
    </Link>
  )
}
