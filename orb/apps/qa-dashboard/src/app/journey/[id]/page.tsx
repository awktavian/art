'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useState, useCallback } from 'react'
import {
  cn,
  formatRelativeTime,
  formatDuration,
  formatTimestamp,
  getPlatformName,
  getColonyHex,
} from '@/lib/utils'
import { api } from '@/lib/api'
import type { RunHistoryEntry } from '@/lib/api'
import type { Checkpoint } from '@/types'
import {
  Card,
  CardHeader,
  CardTitle,
  StatusBadge,
  Button,
} from '@/components/ui'
import { Sidebar } from '@/components/layout'
import { VideoPlayer } from '@/components/video'
import { motion, AnimatePresence } from 'framer-motion'
import { TIMING } from '@/types'
import {
  ArrowLeft,
  GitCommit,
  GitBranch,
  Calendar,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  ChevronRight,
  Play,
  Eye,
  RefreshCw,
  Download,
  ExternalLink,
  Brain,
  Image as ImageIcon,
} from 'lucide-react'

export default function JourneyDetailPage() {
  const params = useParams()
  const id = params.id as string

  const [selectedCheckpoint, setSelectedCheckpoint] = useState<Checkpoint | null>(null)
  const [activeTab, setActiveTab] = useState<'checkpoints' | 'analysis' | 'history'>('checkpoints')

  // Fetch platform summaries for sidebar
  const { data: platforms, error: platformsError } = useQuery({
    queryKey: ['platforms'],
    queryFn: api.fetchPlatformSummaries,
  })

  // Fetch journey details
  const {
    data: journey,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['journey', id],
    queryFn: () => api.fetchJourney(id),
  })

  // Fetch run history
  const {
    data: runHistory,
    isLoading: historyLoading,
    error: historyError,
  } = useQuery({
    queryKey: ['journey-history', id],
    queryFn: () => api.fetchRunHistory(id),
    enabled: !!id,
  })

  // Handle checkpoint click from video player
  const handleCheckpointClick = useCallback((checkpoint: Checkpoint) => {
    setSelectedCheckpoint(checkpoint)
    setActiveTab('checkpoints')
  }, [])

  // Handle video time update to highlight active checkpoint
  const handleTimeUpdate = useCallback((time: number) => {
    if (!journey) return
    const active = journey.checkpoints.find(
      (cp) => time >= cp.timestamp - 0.5 && time <= cp.timestamp + 0.5
    )
    if (active && active.id !== selectedCheckpoint?.id) {
      setSelectedCheckpoint(active)
    }
  }, [journey, selectedCheckpoint?.id])

  if (isLoading) {
    return (
      <div className="flex">
        <Sidebar platforms={platforms} />
        <div className="flex-1 p-6">
          <div className="animate-pulse space-y-6">
            <div className="h-8 w-64 bg-void-lighter rounded" />
            <div className="aspect-video bg-void-lighter rounded-lg" />
            <div className="h-64 bg-void-lighter rounded-lg" />
          </div>
        </div>
      </div>
    )
  }

  if (error || !journey) {
    return (
      <div className="flex">
        <Sidebar platforms={platforms} />
        <div className="flex-1 p-6">
          <div className="text-center py-16">
            <AlertCircle className="w-12 h-12 text-colony-spark mx-auto mb-4" />
            <h2 className="text-xl font-semibold mb-2">Journey Not Found</h2>
            <p className="text-white/60 mb-4">
              The requested journey could not be found.
            </p>
            <Link href="/">
              <Button variant="secondary">Return to Dashboard</Button>
            </Link>
          </div>
        </div>
      </div>
    )
  }

  const passedCheckpoints = journey.checkpoints.filter((c) => c.status === 'pass').length
  const failedCheckpoints = journey.checkpoints.filter((c) => c.status === 'fail').length

  return (
    <div className="flex">
      <Sidebar platforms={platforms} />

      <div className="flex-1 overflow-auto">
        <div className="flex flex-col lg:flex-row">
          {/* Main content */}
          <div className="flex-1 p-6">
            {/* Breadcrumb */}
            <motion.div
              className="flex items-center gap-2 text-sm text-white/60 mb-4"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: TIMING.fast / 1000 }}
            >
              <Link
                href="/"
                className="hover:text-white transition-colors flex items-center gap-1"
              >
                <ArrowLeft className="w-4 h-4" />
                Dashboard
              </Link>
              <span>/</span>
              <Link
                href={`/platform/${journey.platform}`}
                className="hover:text-white transition-colors"
              >
                {getPlatformName(journey.platform)}
              </Link>
              <span>/</span>
              <span className="text-white truncate max-w-[200px]">{journey.name}</span>
            </motion.div>

            {/* Header */}
            <motion.div
              className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6"
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: TIMING.normal / 1000 }}
            >
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <h1 className="text-2xl font-bold">{journey.name}</h1>
                  <StatusBadge status={journey.status} size="lg" />
                </div>
                <div className="flex flex-wrap items-center gap-4 text-sm text-white/60">
                  <span className="flex items-center gap-1">
                    <Calendar className="w-4 h-4" />
                    {formatRelativeTime(journey.createdAt)}
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock className="w-4 h-4" />
                    {formatDuration(journey.duration)}
                  </span>
                  {journey.commitSha && (
                    <span className="flex items-center gap-1">
                      <GitCommit className="w-4 h-4" />
                      <code className="text-colony-crystal">{journey.commitSha.slice(0, 7)}</code>
                    </span>
                  )}
                  {journey.branch && (
                    <span className="flex items-center gap-1">
                      <GitBranch className="w-4 h-4" />
                      {journey.branch}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex gap-2">
                <Button variant="secondary" leftIcon={<RefreshCw className="w-4 h-4" />}>
                  Re-run Test
                </Button>
                {journey.previousRunId && (
                  <Link href={`/journey/${journey.previousRunId}`}>
                    <Button variant="ghost" leftIcon={<Eye className="w-4 h-4" />}>
                      Compare
                    </Button>
                  </Link>
                )}
              </div>
            </motion.div>

            {/* Video player */}
            <motion.div
              className="mb-6"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: TIMING.normal / 1000, delay: TIMING.micro / 1000 }}
            >
              <VideoPlayer
                src={journey.videoUrl}
                poster={journey.thumbnailUrl}
                checkpoints={journey.checkpoints}
                onCheckpointClick={handleCheckpointClick}
                onTimeUpdate={handleTimeUpdate}
              />
            </motion.div>

            {/* Checkpoint progress bar */}
            <motion.div
              className="mb-6"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: TIMING.normal / 1000, delay: TIMING.fast / 1000 }}
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm font-medium">
                  Checkpoints: {passedCheckpoints}/{journey.checkpoints.length}
                </span>
                <span className="text-xs text-white/40">
                  ({Math.round((passedCheckpoints / journey.checkpoints.length) * 100)}% passed)
                </span>
              </div>
              <div className="flex gap-1">
                {journey.checkpoints.map((checkpoint) => (
                  <button
                    key={checkpoint.id}
                    onClick={() => setSelectedCheckpoint(checkpoint)}
                    className={cn(
                      'flex-1 h-2 rounded-sm transition-all duration-fast',
                      'hover:scale-y-150 cursor-pointer',
                      checkpoint.status === 'pass'
                        ? 'bg-colony-grove'
                        : checkpoint.status === 'fail'
                          ? 'bg-colony-spark'
                          : 'bg-colony-crystal',
                      selectedCheckpoint?.id === checkpoint.id && 'ring-2 ring-white ring-offset-2 ring-offset-void'
                    )}
                    title={checkpoint.name}
                    aria-label={`${checkpoint.name}: ${checkpoint.status}`}
                  />
                ))}
              </div>
            </motion.div>

            {/* Gemini Summary */}
            {journey.geminiSummary && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: TIMING.normal / 1000, delay: TIMING.normal / 1000 }}
              >
                <Card variant="colony" colonyColor="nexus" className="mb-6">
                  <div className="flex items-start gap-3">
                    <Brain className="w-5 h-5 text-colony-nexus flex-shrink-0 mt-0.5" />
                    <div>
                      <h3 className="font-medium text-colony-nexus mb-1">AI Analysis Summary</h3>
                      <p className="text-sm text-white/80">{journey.geminiSummary}</p>
                    </div>
                  </div>
                </Card>
              </motion.div>
            )}
          </div>

          {/* Side panel */}
          <motion.div
            className="w-full lg:w-96 border-t lg:border-t-0 lg:border-l border-white/10 bg-void-light/50"
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: TIMING.normal / 1000, delay: TIMING.fast / 1000 }}
          >
            {/* Tabs */}
            <div className="flex border-b border-white/10">
              {[
                { id: 'checkpoints', label: 'Checkpoints', count: journey.checkpoints.length },
                { id: 'analysis', label: 'Analysis' },
                { id: 'history', label: 'History' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as typeof activeTab)}
                  className={cn(
                    'flex-1 px-4 py-3 text-sm font-medium transition-colors duration-fast',
                    'border-b-2 -mb-px',
                    activeTab === tab.id
                      ? 'border-colony-crystal text-colony-crystal'
                      : 'border-transparent text-white/60 hover:text-white'
                  )}
                >
                  {tab.label}
                  {tab.count !== undefined && (
                    <span className="ml-1 text-white/40">({tab.count})</span>
                  )}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="p-4 overflow-y-auto max-h-[calc(100vh-16rem)] custom-scrollbar">
              <AnimatePresence mode="wait">
                {activeTab === 'checkpoints' && (
                  <motion.div
                    key="checkpoints"
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: TIMING.fast / 1000 }}
                    className="space-y-3"
                  >
                    {journey.checkpoints.map((checkpoint, index) => (
                      <CheckpointCard
                        key={checkpoint.id}
                        checkpoint={checkpoint}
                        index={index}
                        isSelected={selectedCheckpoint?.id === checkpoint.id}
                        onClick={() => setSelectedCheckpoint(checkpoint)}
                      />
                    ))}
                  </motion.div>
                )}

                {activeTab === 'analysis' && (
                  <motion.div
                    key="analysis"
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: TIMING.fast / 1000 }}
                    className="space-y-4"
                  >
                    {/* Analysis metrics */}
                    <div className="grid grid-cols-2 gap-3">
                      <Card className="p-3 text-center">
                        <div className="text-2xl font-bold text-colony-grove tabular-nums">
                          {passedCheckpoints}
                        </div>
                        <div className="text-xs text-white/60">Passed</div>
                      </Card>
                      <Card className="p-3 text-center">
                        <div className="text-2xl font-bold text-colony-spark tabular-nums">
                          {failedCheckpoints}
                        </div>
                        <div className="text-xs text-white/60">Failed</div>
                      </Card>
                    </div>

                    {/* Failed checkpoints analysis */}
                    {journey.checkpoints
                      .filter((c) => c.status === 'fail')
                      .map((checkpoint) => (
                        <Card key={checkpoint.id} variant="colony" colonyColor="spark" className="p-3">
                          <h4 className="font-medium text-colony-spark mb-2">{checkpoint.name}</h4>
                          {checkpoint.geminiAnalysis && (
                            <p className="text-sm text-white/80 mb-2">{checkpoint.geminiAnalysis}</p>
                          )}
                          {checkpoint.expected && checkpoint.actual && (
                            <div className="space-y-2 text-xs">
                              <div>
                                <span className="text-white/40">Expected: </span>
                                <span className="text-white/80">{checkpoint.expected}</span>
                              </div>
                              <div>
                                <span className="text-white/40">Actual: </span>
                                <span className="text-colony-spark">{checkpoint.actual}</span>
                              </div>
                            </div>
                          )}
                        </Card>
                      ))}

                    {failedCheckpoints === 0 && (
                      <div className="text-center py-8 text-white/40">
                        <CheckCircle className="w-12 h-12 mx-auto mb-3 text-colony-grove" />
                        <p>All checkpoints passed</p>
                      </div>
                    )}
                  </motion.div>
                )}

                {activeTab === 'history' && (
                  <motion.div
                    key="history"
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: TIMING.fast / 1000 }}
                    className="space-y-3"
                  >
                    {historyLoading ? (
                      <div className="space-y-3">
                        {Array.from({ length: 4 }).map((_, i) => (
                          <div key={i} className="h-14 bg-void-lighter rounded-lg animate-pulse" />
                        ))}
                      </div>
                    ) : historyError ? (
                      <div className="text-center py-8 text-white/40">
                        <AlertCircle className="w-8 h-8 mx-auto mb-2 text-colony-spark" />
                        <p className="text-sm">Failed to load history</p>
                      </div>
                    ) : runHistory && runHistory.length > 0 ? (
                      runHistory.map((run: RunHistoryEntry, index: number) => {
                        const isCurrent = run.id === journey.id
                        return (
                          <Card
                            key={run.id}
                            variant={isCurrent ? 'colony' : 'default'}
                            colonyColor={isCurrent ? 'crystal' : undefined}
                            className={cn('p-3', !isCurrent && 'hover:bg-void-lighter cursor-pointer')}
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <StatusBadge status={run.status} size="sm" showDot={false} />
                                <span className="text-sm">{formatRelativeTime(run.date)}</span>
                              </div>
                              {isCurrent ? (
                                <span className="text-xs text-colony-crystal">Current</span>
                              ) : (
                                <Link href={`/journey/${run.id}`}>
                                  <ChevronRight className="w-4 h-4 text-white/40 hover:text-white" />
                                </Link>
                              )}
                            </div>
                            {run.commitSha && (
                              <div className="text-xs text-white/40 mt-1">
                                <code className="text-colony-crystal/70">{run.commitSha.slice(0, 7)}</code>
                                {run.branch && <span className="ml-2">{run.branch}</span>}
                              </div>
                            )}
                          </Card>
                        )
                      })
                    ) : (
                      <div className="text-center py-8 text-white/40">
                        <p className="text-sm">No history available</p>
                      </div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  )
}

// Checkpoint card component
function CheckpointCard({
  checkpoint,
  index,
  isSelected,
  onClick,
}: {
  checkpoint: Checkpoint
  index: number
  isSelected: boolean
  onClick: () => void
}) {
  const StatusIcon = checkpoint.status === 'pass' ? CheckCircle : XCircle

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: TIMING.fast / 1000, delay: index * 30 }}
    >
      <Card
        variant={isSelected ? 'colony' : 'default'}
        colonyColor={isSelected ? (checkpoint.status === 'pass' ? 'grove' : 'spark') : undefined}
        interactive
        className={cn('p-3 cursor-pointer', isSelected && 'ring-1 ring-white/20')}
        onClick={onClick}
      >
        <div className="flex items-start gap-3">
          <StatusIcon
            className={cn(
              'w-5 h-5 flex-shrink-0 mt-0.5',
              checkpoint.status === 'pass' ? 'text-colony-grove' : 'text-colony-spark'
            )}
          />
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <h4 className="font-medium text-sm truncate">{checkpoint.name}</h4>
              <span className="text-xs text-white/40 tabular-nums flex-shrink-0">
                {formatTimestamp(checkpoint.timestamp)}
              </span>
            </div>
            {checkpoint.description && (
              <p className="text-xs text-white/60 mt-1 line-clamp-2">
                {checkpoint.description}
              </p>
            )}
          </div>
        </div>

        {/* Expanded details when selected */}
        <AnimatePresence>
          {isSelected && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: TIMING.fast / 1000 }}
              className="overflow-hidden"
            >
              <div className="pt-3 mt-3 border-t border-white/10 space-y-2">
                {checkpoint.screenshot && (
                  <button className="flex items-center gap-2 text-xs text-colony-crystal hover:underline">
                    <ImageIcon className="w-3 h-3" />
                    View Screenshot
                  </button>
                )}
                {checkpoint.geminiAnalysis && (
                  <p className="text-xs text-white/70">{checkpoint.geminiAnalysis}</p>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </Card>
    </motion.div>
  )
}
