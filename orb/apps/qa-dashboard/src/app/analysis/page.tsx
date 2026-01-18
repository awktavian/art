'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { useState, useMemo } from 'react'
import {
  cn,
  formatRelativeTime,
  formatTimestamp,
  getColonyHex,
  getPlatformName,
} from '@/lib/utils'
import { api } from '@/lib/api'
import type { Severity, AIIssue, Platform } from '@/types'
import {
  Card,
  CardHeader,
  CardTitle,
  SeverityBadge,
  StatusBadge,
  Button,
} from '@/components/ui'
import { StatsCard } from '@/components/charts'
import { Sidebar } from '@/components/layout'
import { motion, AnimatePresence } from 'framer-motion'
import { TIMING } from '@/types'
import {
  AlertTriangle,
  AlertCircle,
  Info,
  Search,
  Filter,
  ExternalLink,
  Play,
  Lightbulb,
  Brain,
  ChevronDown,
  ChevronRight,
  Copy,
  Check,
} from 'lucide-react'

type FilterSeverity = Severity | 'all'
type FilterCategory = string | 'all'

const severityIcons: Record<Severity, typeof AlertCircle> = {
  critical: AlertCircle,
  warning: AlertTriangle,
  info: Info,
}

export default function AnalysisPage() {
  const [filterSeverity, setFilterSeverity] = useState<FilterSeverity>('all')
  const [filterCategory, setFilterCategory] = useState<FilterCategory>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedIssue, setExpandedIssue] = useState<string | null>(null)

  // Fetch data
  const { data: platforms, error: platformsError } = useQuery({
    queryKey: ['platforms'],
    queryFn: api.fetchPlatformSummaries,
  })

  const { data: issues, isLoading, error: issuesError } = useQuery({
    queryKey: ['ai-issues'],
    queryFn: api.fetchAIIssues,
  })

  const { data: journeys, error: journeysError } = useQuery({
    queryKey: ['journeys'],
    queryFn: () => api.fetchJourneys(),
  })

  // Get unique categories
  const categories = useMemo(() => {
    if (!issues) return []
    const cats = [...new Set(issues.map((i) => i.category))]
    return cats.sort()
  }, [issues])

  // Filter issues
  const filteredIssues = useMemo(() => {
    if (!issues) return []

    let result = [...issues]

    if (filterSeverity !== 'all') {
      result = result.filter((i) => i.severity === filterSeverity)
    }

    if (filterCategory !== 'all') {
      result = result.filter((i) => i.category === filterCategory)
    }

    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(
        (i) =>
          i.title.toLowerCase().includes(query) ||
          i.description.toLowerCase().includes(query) ||
          i.suggestedFix?.toLowerCase().includes(query)
      )
    }

    // Sort by severity (critical first) then by date
    const severityOrder: Record<Severity, number> = { critical: 0, warning: 1, info: 2 }
    result.sort((a, b) => {
      const severityDiff = severityOrder[a.severity] - severityOrder[b.severity]
      if (severityDiff !== 0) return severityDiff
      return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    })

    return result
  }, [issues, filterSeverity, filterCategory, searchQuery])

  // Calculate stats
  const criticalCount = issues?.filter((i) => i.severity === 'critical').length || 0
  const warningCount = issues?.filter((i) => i.severity === 'warning').length || 0
  const infoCount = issues?.filter((i) => i.severity === 'info').length || 0

  return (
    <div className="flex">
      <Sidebar platforms={platforms} />

      <div className="flex-1 p-6 overflow-auto">
        {/* Page header */}
        <motion.div
          className="mb-6"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: TIMING.normal / 1000 }}
        >
          <h1 className="text-3xl font-bold mb-2">AI Analysis</h1>
          <p className="text-white/60">
            Gemini-detected issues and recommendations across all tests
          </p>
        </motion.div>

        {/* Stats */}
        <motion.div
          className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: TIMING.normal / 1000, delay: TIMING.micro / 1000 }}
        >
          <StatsCard
            title="Critical Issues"
            value={criticalCount}
            color="spark"
            icon={<AlertCircle className="w-5 h-5" />}
          />
          <StatsCard
            title="Warnings"
            value={warningCount}
            color="beacon"
            icon={<AlertTriangle className="w-5 h-5" />}
          />
          <StatsCard
            title="Info"
            value={infoCount}
            color="crystal"
            icon={<Info className="w-5 h-5" />}
          />
        </motion.div>

        {/* Filters */}
        <motion.div
          className="flex flex-col sm:flex-row gap-4 mb-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: TIMING.normal / 1000, delay: TIMING.fast / 1000 }}
        >
          {/* Search */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
            <input
              type="text"
              placeholder="Search issues..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input pl-10"
              aria-label="Search issues"
            />
          </div>

          {/* Severity filter */}
          <select
            value={filterSeverity}
            onChange={(e) => setFilterSeverity(e.target.value as FilterSeverity)}
            className="input w-auto min-w-[140px]"
            aria-label="Filter by severity"
          >
            <option value="all">All Severity</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>

          {/* Category filter */}
          <select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
            className="input w-auto min-w-[140px]"
            aria-label="Filter by category"
          >
            <option value="all">All Categories</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </motion.div>

        {/* Issues list */}
        <AnimatePresence mode="wait">
          {isLoading ? (
            <motion.div
              key="loading"
              className="space-y-4"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-32 bg-void-light rounded-lg animate-pulse" />
              ))}
            </motion.div>
          ) : filteredIssues.length === 0 ? (
            <motion.div
              key="empty"
              className="text-center py-16"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <Brain className="w-12 h-12 text-colony-nexus mx-auto mb-4" />
              <p className="text-white/40 text-lg">No issues found</p>
              <p className="text-white/30 text-sm mt-1">
                {issues?.length === 0
                  ? 'All tests are passing without detected issues'
                  : 'Try adjusting your filters or search query'}
              </p>
            </motion.div>
          ) : (
            <motion.div
              key="issues"
              className="space-y-4"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              {filteredIssues.map((issue, index) => (
                <IssueCard
                  key={issue.id}
                  issue={issue}
                  journey={journeys?.find((j) => j.id === issue.journeyId)}
                  index={index}
                  isExpanded={expandedIssue === issue.id}
                  onToggle={() =>
                    setExpandedIssue(expandedIssue === issue.id ? null : issue.id)
                  }
                />
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

// Issue card component
function IssueCard({
  issue,
  journey,
  index,
  isExpanded,
  onToggle,
}: {
  issue: AIIssue
  journey?: { name: string; platform: Platform }
  index: number
  isExpanded: boolean
  onToggle: () => void
}) {
  const [copied, setCopied] = useState(false)
  const SeverityIcon = severityIcons[issue.severity]

  const copyFix = async () => {
    if (issue.suggestedFix) {
      await navigator.clipboard.writeText(issue.suggestedFix)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: TIMING.fast / 1000,
        delay: index * (TIMING.micro / 2000),
      }}
    >
      <Card
        variant="colony"
        colonyColor={
          issue.severity === 'critical'
            ? 'spark'
            : issue.severity === 'warning'
              ? 'beacon'
              : 'crystal'
        }
        className={cn('overflow-hidden', isExpanded && 'ring-1 ring-white/20')}
      >
        {/* Header - always visible */}
        <button
          className="w-full p-4 text-left flex items-start gap-4"
          onClick={onToggle}
          aria-expanded={isExpanded}
        >
          <SeverityIcon
            className="w-5 h-5 flex-shrink-0 mt-0.5"
            style={{
              color: getColonyHex(
                issue.severity === 'critical'
                  ? 'spark'
                  : issue.severity === 'warning'
                    ? 'beacon'
                    : 'crystal'
              ),
            }}
          />

          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="font-semibold mb-1">{issue.title}</h3>
                <p className="text-sm text-white/60 line-clamp-2">{issue.description}</p>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <SeverityBadge severity={issue.severity} size="sm" />
                {isExpanded ? (
                  <ChevronDown className="w-5 h-5 text-white/40" />
                ) : (
                  <ChevronRight className="w-5 h-5 text-white/40" />
                )}
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-white/40">
              {journey && (
                <span className="flex items-center gap-1">
                  <span className="capitalize">{getPlatformName(journey.platform)}</span>
                  <span>•</span>
                  <span className="truncate max-w-[150px]">{journey.name}</span>
                </span>
              )}
              <span className="px-2 py-0.5 bg-white/5 rounded">{issue.category}</span>
              <span>{formatRelativeTime(issue.createdAt)}</span>
              <span className="text-colony-crystal">
                {Math.round(issue.confidence * 100)}% confidence
              </span>
            </div>
          </div>
        </button>

        {/* Expanded content */}
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: TIMING.fast / 1000 }}
              className="overflow-hidden"
            >
              <div className="px-4 pb-4 pt-0 border-t border-white/10 mt-0">
                {/* Video clip */}
                {issue.videoClipUrl && (
                  <div className="mt-4">
                    <div className="text-xs text-white/40 mb-2">Video Clip</div>
                    <div className="relative aspect-video bg-void-lighter rounded-lg overflow-hidden">
                      <div className="absolute inset-0 flex items-center justify-center">
                        <Link
                          href={`/journey/${issue.journeyId}?t=${issue.startTime}`}
                          className="flex items-center gap-2 px-4 py-2 bg-colony-crystal text-void rounded-md font-medium hover:bg-colony-crystal/90 transition-colors"
                        >
                          <Play className="w-4 h-4" />
                          Watch in Context
                        </Link>
                      </div>
                    </div>
                    <div className="flex justify-between text-xs text-white/40 mt-1">
                      <span>{formatTimestamp(issue.startTime)}</span>
                      <span>{formatTimestamp(issue.endTime)}</span>
                    </div>
                  </div>
                )}

                {/* Suggested fix */}
                {issue.suggestedFix && (
                  <div className="mt-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-1 text-xs text-white/40">
                        <Lightbulb className="w-3 h-3" />
                        Suggested Fix
                      </div>
                      <button
                        onClick={copyFix}
                        className="flex items-center gap-1 text-xs text-colony-crystal hover:text-colony-crystal/80 transition-colors"
                      >
                        {copied ? (
                          <>
                            <Check className="w-3 h-3" />
                            Copied
                          </>
                        ) : (
                          <>
                            <Copy className="w-3 h-3" />
                            Copy
                          </>
                        )}
                      </button>
                    </div>
                    <div className="p-3 bg-void rounded-md text-sm text-white/80 font-mono whitespace-pre-wrap">
                      {issue.suggestedFix}
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-2 mt-4">
                  <Link href={`/journey/${issue.journeyId}`}>
                    <Button variant="secondary" size="sm" leftIcon={<ExternalLink className="w-4 h-4" />}>
                      View Journey
                    </Button>
                  </Link>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </Card>
    </motion.div>
  )
}
