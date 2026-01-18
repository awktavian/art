'use client'

import { useQuery } from '@tanstack/react-query'
import { useState, useCallback, useRef } from 'react'
import {
  cn,
  formatDate,
  formatDuration,
  calculatePassRate,
  getColonyHex,
  getPlatformName,
} from '@/lib/utils'
import { api } from '@/lib/api'
import type { Platform, ReportFilter } from '@/types'
import {
  Card,
  CardHeader,
  CardTitle,
  StatusBadge,
  HealthBadge,
  Button,
  CircularProgress,
} from '@/components/ui'
import { TrendChart, StatsCard } from '@/components/charts'
import { Sidebar } from '@/components/layout'
import { motion } from 'framer-motion'
import { TIMING } from '@/types'
import {
  FileText,
  Download,
  Calendar,
  Filter,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  TrendingUp,
  BarChart3,
  Printer,
} from 'lucide-react'

export default function ReportsPage() {
  const reportRef = useRef<HTMLDivElement>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [dateRange, setDateRange] = useState({
    from: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    to: new Date().toISOString().split('T')[0],
  })
  const [selectedPlatforms, setSelectedPlatforms] = useState<Platform[]>([])

  // Fetch data
  const { data: platforms, error: platformsError } = useQuery({
    queryKey: ['platforms'],
    queryFn: api.fetchPlatformSummaries,
  })

  const { data: journeys, error: journeysError } = useQuery({
    queryKey: ['journeys'],
    queryFn: () => api.fetchJourneys(),
  })

  const { data: trendData, error: trendError } = useQuery({
    queryKey: ['trends'],
    queryFn: () => api.fetchTrendData(),
  })

  const { data: issues, error: issuesError } = useQuery({
    queryKey: ['ai-issues'],
    queryFn: api.fetchAIIssues,
  })

  // Calculate report metrics
  const filteredPlatforms =
    selectedPlatforms.length > 0
      ? platforms?.filter((p) => selectedPlatforms.includes(p.platform))
      : platforms

  const filteredJourneys =
    selectedPlatforms.length > 0
      ? journeys?.filter((j) => selectedPlatforms.includes(j.platform))
      : journeys

  const overallHealth = filteredPlatforms ? api.calculateOverallHealth(filteredPlatforms) : 0
  const totalTests = filteredJourneys?.length || 0
  const passedTests = filteredJourneys?.filter((j) => j.status === 'pass').length || 0
  const failedTests = filteredJourneys?.filter((j) => j.status === 'fail').length || 0
  const passRate = calculatePassRate(passedTests, totalTests)
  const avgDuration = filteredJourneys
    ? Math.round(filteredJourneys.reduce((sum, j) => sum + j.duration, 0) / (filteredJourneys.length || 1))
    : 0
  const criticalIssues = issues?.filter((i) => i.severity === 'critical').length || 0

  // Toggle platform selection
  const togglePlatform = (platform: Platform) => {
    setSelectedPlatforms((prev) =>
      prev.includes(platform)
        ? prev.filter((p) => p !== platform)
        : [...prev, platform]
    )
  }

  // Generate PDF report
  const generatePDF = useCallback(async () => {
    setIsGenerating(true)

    try {
      // Dynamic import to avoid SSR issues
      const [jsPDFModule, html2canvasModule] = await Promise.all([
        import('jspdf'),
        import('html2canvas'),
      ])
      const jsPDF = jsPDFModule.default
      const html2canvas = html2canvasModule.default

      if (!reportRef.current) return

      // Create canvas from report content
      const canvas = await html2canvas(reportRef.current, {
        scale: 2,
        backgroundColor: '#0A0A0F',
        logging: false,
      })

      // Create PDF
      const imgData = canvas.toDataURL('image/png')
      const pdf = new jsPDF({
        orientation: 'portrait',
        unit: 'mm',
        format: 'a4',
      })

      const pdfWidth = pdf.internal.pageSize.getWidth()
      const pdfHeight = pdf.internal.pageSize.getHeight()
      const imgWidth = canvas.width
      const imgHeight = canvas.height
      const ratio = Math.min(pdfWidth / imgWidth, pdfHeight / imgHeight)
      const imgX = (pdfWidth - imgWidth * ratio) / 2
      const imgY = 10

      pdf.addImage(imgData, 'PNG', imgX, imgY, imgWidth * ratio, imgHeight * ratio)

      // Save PDF
      pdf.save(`kagami-qa-report-${new Date().toISOString().split('T')[0]}.pdf`)
    } catch (error) {
      console.error('Failed to generate PDF:', error)
    } finally {
      setIsGenerating(false)
    }
  }, [])

  // Print report
  const printReport = useCallback(() => {
    window.print()
  }, [])

  return (
    <div className="flex">
      <Sidebar platforms={platforms} />

      <div className="flex-1 p-6 overflow-auto">
        {/* Page header */}
        <motion.div
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: TIMING.normal / 1000 }}
        >
          <div>
            <h1 className="text-3xl font-bold mb-2">Reports</h1>
            <p className="text-white/60">
              Generate and export QA reports
            </p>
          </div>

          <div className="flex gap-2 no-print">
            <Button
              variant="secondary"
              leftIcon={<Printer className="w-4 h-4" />}
              onClick={printReport}
            >
              Print
            </Button>
            <Button
              leftIcon={
                isGenerating ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Download className="w-4 h-4" />
                )
              }
              onClick={generatePDF}
              disabled={isGenerating}
            >
              {isGenerating ? 'Generating...' : 'Download PDF'}
            </Button>
          </div>
        </motion.div>

        {/* Filters */}
        <motion.div
          className="mb-6 no-print"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: TIMING.normal / 1000, delay: TIMING.micro / 1000 }}
        >
          <Card variant="elevated" className="p-4">
            <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <Filter className="w-4 h-4" />
              Report Filters
            </h2>

            <div className="flex flex-col sm:flex-row gap-4">
              {/* Date range */}
              <div className="flex gap-2 items-center">
                <Calendar className="w-4 h-4 text-white/40" />
                <input
                  type="date"
                  value={dateRange.from}
                  onChange={(e) => setDateRange((prev) => ({ ...prev, from: e.target.value }))}
                  className="input py-1.5 text-sm"
                  aria-label="From date"
                />
                <span className="text-white/40">to</span>
                <input
                  type="date"
                  value={dateRange.to}
                  onChange={(e) => setDateRange((prev) => ({ ...prev, to: e.target.value }))}
                  className="input py-1.5 text-sm"
                  aria-label="To date"
                />
              </div>

              {/* Platform toggles */}
              <div className="flex flex-wrap gap-2">
                {platforms?.map((p) => (
                  <button
                    key={p.platform}
                    onClick={() => togglePlatform(p.platform)}
                    className={cn(
                      'px-3 py-1.5 rounded-md text-sm font-medium transition-colors duration-fast',
                      selectedPlatforms.includes(p.platform)
                        ? 'bg-colony-crystal text-void'
                        : 'bg-void-lighter text-white/60 hover:text-white'
                    )}
                  >
                    {p.displayName}
                  </button>
                ))}
              </div>
            </div>
          </Card>
        </motion.div>

        {/* Report content */}
        <div ref={reportRef} className="space-y-6">
          {/* Report header */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: TIMING.normal / 1000, delay: TIMING.fast / 1000 }}
          >
            <Card variant="elevated" className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-2xl font-bold">Kagami QA Report</h2>
                  <p className="text-white/60 text-sm">
                    Generated on {formatDate(new Date().toISOString())}
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-sm text-white/60">Report Period</div>
                  <div className="font-medium">
                    {dateRange.from} to {dateRange.to}
                  </div>
                </div>
              </div>

              {/* Overall health */}
              <div className="flex items-center gap-8 pt-4 border-t border-white/10">
                <div className="relative">
                  <CircularProgress
                    value={overallHealth}
                    size={100}
                    strokeWidth={8}
                    showValue={false}
                  />
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span
                      className="text-3xl font-bold tabular-nums"
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

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 flex-1">
                  <div>
                    <div className="text-2xl font-bold text-colony-crystal tabular-nums">
                      {totalTests}
                    </div>
                    <div className="text-sm text-white/60">Total Tests</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-colony-grove tabular-nums">
                      {passRate}%
                    </div>
                    <div className="text-sm text-white/60">Pass Rate</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-colony-spark tabular-nums">
                      {failedTests}
                    </div>
                    <div className="text-sm text-white/60">Failed</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-colony-beacon tabular-nums">
                      {criticalIssues}
                    </div>
                    <div className="text-sm text-white/60">Critical Issues</div>
                  </div>
                </div>
              </div>
            </Card>
          </motion.div>

          {/* Platform breakdown */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: TIMING.normal / 1000, delay: TIMING.normal / 1000 }}
          >
            <Card variant="elevated" className="p-6">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <BarChart3 className="w-5 h-5" />
                Platform Breakdown
              </h2>

              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-white/10">
                      <th className="table-header">Platform</th>
                      <th className="table-header text-center">Health</th>
                      <th className="table-header text-center">Total</th>
                      <th className="table-header text-center">Passed</th>
                      <th className="table-header text-center">Failed</th>
                      <th className="table-header text-center">Pass Rate</th>
                      <th className="table-header text-center">Trend</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredPlatforms?.map((platform) => (
                      <tr key={platform.platform} className="table-row">
                        <td className="table-cell font-medium">{platform.displayName}</td>
                        <td className="table-cell text-center">
                          <HealthBadge score={platform.healthScore} size="sm" />
                        </td>
                        <td className="table-cell text-center tabular-nums">
                          {platform.totalJourneys}
                        </td>
                        <td className="table-cell text-center tabular-nums text-colony-grove">
                          {platform.passedJourneys}
                        </td>
                        <td className="table-cell text-center tabular-nums text-colony-spark">
                          {platform.failedJourneys}
                        </td>
                        <td className="table-cell text-center tabular-nums">
                          {calculatePassRate(platform.passedJourneys, platform.totalJourneys)}%
                        </td>
                        <td className="table-cell text-center">
                          <span
                            className={cn(
                              'inline-flex items-center gap-1',
                              platform.trend === 'up'
                                ? 'text-colony-grove'
                                : platform.trend === 'down'
                                  ? 'text-colony-spark'
                                  : 'text-white/60'
                            )}
                          >
                            {platform.trend === 'up' && <TrendingUp className="w-3 h-3" />}
                            {platform.trend === 'down' && (
                              <TrendingUp className="w-3 h-3 rotate-180" />
                            )}
                            {platform.trendValue !== 0 && (
                              <span className="tabular-nums">
                                {platform.trendValue > 0 ? '+' : ''}
                                {platform.trendValue}%
                              </span>
                            )}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </motion.div>

          {/* Trend chart */}
          {trendData && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: TIMING.normal / 1000, delay: TIMING.medium / 1000 }}
            >
              <Card variant="elevated" className="p-6">
                <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <TrendingUp className="w-5 h-5" />
                  Pass Rate Trend
                </h2>
                <TrendChart
                  data={trendData}
                  dataKey="passRate"
                  color="grove"
                  height={250}
                />
              </Card>
            </motion.div>
          )}

          {/* Critical issues */}
          {issues && issues.filter((i) => i.severity === 'critical').length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: TIMING.normal / 1000, delay: TIMING.slow / 1000 }}
            >
              <Card variant="elevated" className="p-6">
                <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-colony-spark" />
                  Critical Issues
                </h2>

                <div className="space-y-3">
                  {issues
                    .filter((i) => i.severity === 'critical')
                    .slice(0, 5)
                    .map((issue) => (
                      <div
                        key={issue.id}
                        className="p-3 bg-colony-spark/10 border border-colony-spark/30 rounded-md"
                      >
                        <h3 className="font-medium text-colony-spark mb-1">{issue.title}</h3>
                        <p className="text-sm text-white/70 line-clamp-2">{issue.description}</p>
                        <div className="flex items-center gap-3 mt-2 text-xs text-white/40">
                          <span className="px-2 py-0.5 bg-white/5 rounded">{issue.category}</span>
                          <span>{Math.round(issue.confidence * 100)}% confidence</span>
                        </div>
                      </div>
                    ))}
                </div>
              </Card>
            </motion.div>
          )}

          {/* Summary recommendations */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: TIMING.normal / 1000, delay: TIMING.slower / 1000 }}
          >
            <Card variant="colony" colonyColor="nexus" className="p-6">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <FileText className="w-5 h-5" />
                Recommendations
              </h2>

              <ul className="space-y-2">
                {failedTests > 0 && (
                  <li className="flex items-start gap-2">
                    <XCircle className="w-4 h-4 text-colony-spark mt-0.5 flex-shrink-0" />
                    <span className="text-sm">
                      Investigate {failedTests} failed test{failedTests !== 1 ? 's' : ''} to improve
                      overall pass rate
                    </span>
                  </li>
                )}
                {criticalIssues > 0 && (
                  <li className="flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 text-colony-beacon mt-0.5 flex-shrink-0" />
                    <span className="text-sm">
                      Address {criticalIssues} critical issue{criticalIssues !== 1 ? 's' : ''}{' '}
                      identified by AI analysis
                    </span>
                  </li>
                )}
                {filteredPlatforms?.some((p) => p.trend === 'down') && (
                  <li className="flex items-start gap-2">
                    <TrendingUp className="w-4 h-4 text-colony-forge mt-0.5 flex-shrink-0 rotate-180" />
                    <span className="text-sm">
                      Some platforms show declining trends - review recent changes
                    </span>
                  </li>
                )}
                {overallHealth >= 90 && (
                  <li className="flex items-start gap-2">
                    <CheckCircle className="w-4 h-4 text-colony-grove mt-0.5 flex-shrink-0" />
                    <span className="text-sm">
                      Excellent overall health score! Continue monitoring for regressions
                    </span>
                  </li>
                )}
              </ul>
            </Card>
          </motion.div>
        </div>
      </div>
    </div>
  )
}
