'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { cn, formatRelativeTime, formatDuration, getPlatformName, calculatePassRate } from '@/lib/utils'
import { api } from '@/lib/api'
import type { Platform, UserJourney, TestStatus } from '@/types'
import {
  Card,
  CardHeader,
  CardTitle,
  CardSkeleton,
  StatusBadge,
  HealthBadge,
  Button,
} from '@/components/ui'
import { TrendChart, StatsCard } from '@/components/charts'
import { Sidebar } from '@/components/layout'
import { VideoThumbnail, VideoThumbnailSkeleton } from '@/components/video'
import { motion, AnimatePresence } from 'framer-motion'
import { TIMING } from '@/types'
import {
  ArrowLeft,
  Filter,
  Search,
  SortAsc,
  Grid,
  List,
  Play,
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
} from 'lucide-react'
import { useState, useMemo } from 'react'

type ViewMode = 'grid' | 'list'
type SortOption = 'date' | 'name' | 'status' | 'duration'

export default function PlatformPage() {
  const params = useParams()
  const platform = params.platform as Platform

  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [sortBy, setSortBy] = useState<SortOption>('date')
  const [filterStatus, setFilterStatus] = useState<TestStatus | 'all'>('all')
  const [searchQuery, setSearchQuery] = useState('')

  // Fetch platform summaries for sidebar
  const { data: platforms, error: platformsError } = useQuery({
    queryKey: ['platforms'],
    queryFn: api.fetchPlatformSummaries,
  })

  // Fetch journeys for this platform
  const {
    data: journeys,
    isLoading,
    error: journeysError,
  } = useQuery({
    queryKey: ['journeys', platform],
    queryFn: () => api.fetchJourneys(platform),
  })

  // Fetch trend data
  const { data: trendData, error: trendError } = useQuery({
    queryKey: ['trends', platform],
    queryFn: () => api.fetchTrendData(),
  })

  // Get platform summary
  const platformSummary = platforms?.find((p) => p.platform === platform)

  // Filter and sort journeys
  const filteredJourneys = useMemo(() => {
    if (!journeys) return []

    let result = [...journeys]

    // Filter by status
    if (filterStatus !== 'all') {
      result = result.filter((j) => j.status === filterStatus)
    }

    // Filter by search query
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(
        (j) =>
          j.name.toLowerCase().includes(query) ||
          j.geminiSummary?.toLowerCase().includes(query)
      )
    }

    // Sort
    result.sort((a, b) => {
      switch (sortBy) {
        case 'date':
          return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        case 'name':
          return a.name.localeCompare(b.name)
        case 'status':
          const statusOrder = { fail: 0, in_progress: 1, warning: 2, pending: 3, pass: 4 }
          return statusOrder[a.status] - statusOrder[b.status]
        case 'duration':
          return b.duration - a.duration
        default:
          return 0
      }
    })

    return result
  }, [journeys, filterStatus, searchQuery, sortBy])

  // Calculate stats
  const passRate = journeys
    ? calculatePassRate(
        journeys.filter((j) => j.status === 'pass').length,
        journeys.length
      )
    : 0
  const avgDuration = journeys
    ? Math.round(journeys.reduce((sum, j) => sum + j.duration, 0) / journeys.length)
    : 0

  return (
    <div className="flex">
      <Sidebar platforms={platforms} />

      <div className="flex-1 p-6 overflow-auto">
        {/* Breadcrumb */}
        <motion.div
          className="flex items-center gap-2 text-sm text-white/60 mb-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: TIMING.fast / 1000 }}
        >
          <Link href="/" className="hover:text-white transition-colors flex items-center gap-1">
            <ArrowLeft className="w-4 h-4" />
            Dashboard
          </Link>
          <span>/</span>
          <span className="text-white">{getPlatformName(platform)}</span>
        </motion.div>

        {/* Page header */}
        <motion.div
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: TIMING.normal / 1000 }}
        >
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-3">
              {getPlatformName(platform)}
              {platformSummary && (
                <HealthBadge score={platformSummary.healthScore} size="lg" />
              )}
            </h1>
            <p className="text-white/60 mt-1">
              {journeys?.length || 0} user journey tests
            </p>
          </div>

          <Button leftIcon={<Play className="w-4 h-4" />}>
            Run All Tests
          </Button>
        </motion.div>

        {/* Stats cards */}
        <motion.div
          className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: TIMING.normal / 1000, delay: TIMING.micro / 1000 }}
        >
          <StatsCard
            title="Pass Rate"
            value={`${passRate}%`}
            color="grove"
            icon={<CheckCircle className="w-5 h-5" />}
          />
          <StatsCard
            title="Failed Tests"
            value={journeys?.filter((j) => j.status === 'fail').length || 0}
            color="spark"
            icon={<XCircle className="w-5 h-5" />}
          />
          <StatsCard
            title="Avg Duration"
            value={formatDuration(avgDuration)}
            color="crystal"
            icon={<Clock className="w-5 h-5" />}
          />
          <StatsCard
            title="Warnings"
            value={journeys?.filter((j) => j.status === 'warning').length || 0}
            color="beacon"
            icon={<AlertTriangle className="w-5 h-5" />}
          />
        </motion.div>

        {/* Trend chart */}
        {trendData && (
          <motion.div
            className="mb-6"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: TIMING.normal / 1000, delay: TIMING.fast / 1000 }}
          >
            <Card variant="elevated" className="p-4">
              <TrendChart
                data={trendData}
                dataKey="passRate"
                title="Pass Rate Over Time"
                color="grove"
                height={180}
              />
            </Card>
          </motion.div>
        )}

        {/* Filters and view toggle */}
        <motion.div
          className="flex flex-col sm:flex-row gap-4 mb-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: TIMING.normal / 1000, delay: TIMING.normal / 1000 }}
        >
          {/* Search */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
            <input
              type="text"
              placeholder="Search journeys..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input pl-10"
              aria-label="Search journeys"
            />
          </div>

          {/* Status filter */}
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value as TestStatus | 'all')}
            className="input w-auto min-w-[140px]"
            aria-label="Filter by status"
          >
            <option value="all">All Status</option>
            <option value="pass">Passed</option>
            <option value="fail">Failed</option>
            <option value="in_progress">In Progress</option>
            <option value="warning">Warning</option>
            <option value="pending">Pending</option>
          </select>

          {/* Sort */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortOption)}
            className="input w-auto min-w-[140px]"
            aria-label="Sort by"
          >
            <option value="date">Newest First</option>
            <option value="name">Name A-Z</option>
            <option value="status">Status</option>
            <option value="duration">Duration</option>
          </select>

          {/* View toggle */}
          <div className="flex rounded-md overflow-hidden border border-white/10">
            <button
              onClick={() => setViewMode('grid')}
              className={cn(
                'p-2 transition-colors duration-fast',
                viewMode === 'grid' ? 'bg-colony-crystal text-void' : 'bg-void-lighter text-white/60 hover:text-white'
              )}
              aria-label="Grid view"
              aria-pressed={viewMode === 'grid'}
            >
              <Grid className="w-5 h-5" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={cn(
                'p-2 transition-colors duration-fast',
                viewMode === 'list' ? 'bg-colony-crystal text-void' : 'bg-void-lighter text-white/60 hover:text-white'
              )}
              aria-label="List view"
              aria-pressed={viewMode === 'list'}
            >
              <List className="w-5 h-5" />
            </button>
          </div>
        </motion.div>

        {/* Journey list */}
        <AnimatePresence mode="wait">
          {isLoading ? (
            <motion.div
              key="loading"
              className={cn(
                viewMode === 'grid'
                  ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4'
                  : 'space-y-3'
              )}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              {Array.from({ length: 6 }).map((_, i) => (
                viewMode === 'grid' ? (
                  <CardSkeleton key={i} />
                ) : (
                  <div key={i} className="h-20 bg-void-light rounded-lg animate-pulse" />
                )
              ))}
            </motion.div>
          ) : filteredJourneys.length === 0 ? (
            <motion.div
              key="empty"
              className="text-center py-16"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <p className="text-white/40 text-lg">No journeys found</p>
              <p className="text-white/30 text-sm mt-1">
                Try adjusting your filters or search query
              </p>
            </motion.div>
          ) : viewMode === 'grid' ? (
            <motion.div
              key="grid"
              className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              {filteredJourneys.map((journey, index) => (
                <JourneyGridCard key={journey.id} journey={journey} index={index} />
              ))}
            </motion.div>
          ) : (
            <motion.div
              key="list"
              className="space-y-2"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              {filteredJourneys.map((journey, index) => (
                <JourneyListRow key={journey.id} journey={journey} index={index} />
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

// Grid card component
function JourneyGridCard({ journey, index }: { journey: UserJourney; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: TIMING.fast / 1000,
        delay: index * (TIMING.micro / 2000),
      }}
    >
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

          <div className="flex items-center gap-2 text-xs text-white/40 mb-2">
            <span>{formatRelativeTime(journey.createdAt)}</span>
            {journey.commitSha && (
              <>
                <span>•</span>
                <code className="text-colony-crystal/70">{journey.commitSha.slice(0, 7)}</code>
              </>
            )}
          </div>

          <div className="flex items-center justify-between">
            <StatusBadge status={journey.status} size="sm" />
            <span className="text-xs text-white/40">
              {journey.checkpoints.filter((c) => c.status === 'pass').length}/
              {journey.checkpoints.length} checkpoints
            </span>
          </div>
        </Card>
      </Link>
    </motion.div>
  )
}

// List row component
function JourneyListRow({ journey, index }: { journey: UserJourney; index: number }) {
  const passedCheckpoints = journey.checkpoints.filter((c) => c.status === 'pass').length

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{
        duration: TIMING.fast / 1000,
        delay: index * (TIMING.micro / 2000),
      }}
    >
      <Link href={`/journey/${journey.id}`}>
        <Card
          variant="elevated"
          interactive
          className="flex items-center gap-4 py-3"
        >
          {/* Thumbnail */}
          <div className="w-32 flex-shrink-0">
            <VideoThumbnail
              src={journey.thumbnailUrl}
              alt={journey.name}
              duration={journey.duration}
            />
          </div>

          {/* Info */}
          <div className="flex-1 min-w-0">
            <h3 className="font-medium truncate group-hover:text-colony-crystal transition-colors">
              {journey.name}
            </h3>
            <div className="flex items-center gap-3 text-sm text-white/40 mt-1">
              <span>{formatRelativeTime(journey.createdAt)}</span>
              <span>{formatDuration(journey.duration)}</span>
              {journey.commitSha && (
                <code className="text-colony-crystal/70">{journey.commitSha.slice(0, 7)}</code>
              )}
            </div>
          </div>

          {/* Checkpoints */}
          <div className="text-right">
            <div className="text-sm font-medium tabular-nums">
              {passedCheckpoints}/{journey.checkpoints.length}
            </div>
            <div className="text-xs text-white/40">checkpoints</div>
          </div>

          {/* Status */}
          <div className="w-24 flex justify-end">
            <StatusBadge status={journey.status} />
          </div>
        </Card>
      </Link>
    </motion.div>
  )
}
