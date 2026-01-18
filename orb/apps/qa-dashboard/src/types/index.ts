/**
 * Kagami QA Dashboard - Type Definitions
 *
 * Core types for the user journey test video dashboard.
 */

// =============================================================================
// ENUMS
// =============================================================================

export type Platform =
  | 'ios'
  | 'android'
  | 'android-xr'
  | 'visionos'
  | 'watchos'
  | 'tvos'
  | 'desktop'
  | 'hub'

export type TestStatus =
  | 'pass'
  | 'fail'
  | 'in_progress'
  | 'pending'
  | 'warning'

export type Severity =
  | 'critical'
  | 'warning'
  | 'info'

export type ColonyColor =
  | 'spark'
  | 'forge'
  | 'flow'
  | 'nexus'
  | 'beacon'
  | 'grove'
  | 'crystal'

// =============================================================================
// CHECKPOINT
// =============================================================================

export interface Checkpoint {
  id: string
  name: string
  timestamp: number // seconds into video
  status: TestStatus
  screenshot?: string
  description?: string
  expected?: string
  actual?: string
  geminiAnalysis?: string
}

// =============================================================================
// USER JOURNEY
// =============================================================================

export interface UserJourney {
  id: string
  name: string
  platform: Platform
  status: TestStatus
  duration: number // seconds
  videoUrl: string
  thumbnailUrl: string
  checkpoints: Checkpoint[]
  createdAt: string // ISO date
  commitSha?: string
  branch?: string
  runNumber?: number
  geminiSummary?: string
  previousRunId?: string
}

// =============================================================================
// PLATFORM SUMMARY
// =============================================================================

export interface PlatformSummary {
  platform: Platform
  displayName: string
  icon: string
  totalJourneys: number
  passedJourneys: number
  failedJourneys: number
  inProgressJourneys: number
  lastTestTime: string
  healthScore: number // 0-100
  trend: 'up' | 'down' | 'stable'
  trendValue: number // percentage change
}

// =============================================================================
// AI ANALYSIS
// =============================================================================

export interface AIIssue {
  id: string
  journeyId: string
  severity: Severity
  title: string
  description: string
  suggestedFix?: string
  videoClipUrl?: string
  startTime: number
  endTime: number
  checkpoint?: Checkpoint
  category: string
  confidence: number // 0-1
  createdAt: string
}

export interface GeminiAnalysis {
  journeyId: string
  summary: string
  issues: AIIssue[]
  recommendations: string[]
  overallScore: number // 0-100
  analyzedAt: string
}

// =============================================================================
// REPORTS
// =============================================================================

export interface ReportFilter {
  platforms?: Platform[]
  dateFrom?: string
  dateTo?: string
  status?: TestStatus[]
  minHealthScore?: number
}

export interface Report {
  id: string
  name: string
  generatedAt: string
  filter: ReportFilter
  platforms: PlatformSummary[]
  journeys: UserJourney[]
  overallHealth: number
  totalTests: number
  passRate: number
  avgDuration: number
  accessibilityScore?: number
}

// =============================================================================
// WEBSOCKET EVENTS
// =============================================================================

/**
 * Event types from the dashboard publisher:
 * - test_started: A new test journey has begun
 * - checkpoint_passed: A checkpoint within the journey passed
 * - checkpoint_failed: A checkpoint within the journey failed
 * - test_completed: The test journey has finished
 * - analysis_complete: Gemini AI analysis is ready
 * - constellation_sync: Full state sync from constellation
 */
export type WebSocketEventType =
  | 'test_started'
  | 'checkpoint_passed'
  | 'checkpoint_failed'
  | 'test_completed'
  | 'analysis_complete'
  | 'constellation_sync'
  | 'ping'
  | 'pong'

export interface TestUpdateEvent {
  type: WebSocketEventType
  journeyId: string
  platform: Platform
  timestamp: string
  data: {
    status?: TestStatus
    checkpoint?: Checkpoint
    progress?: number
    // For analysis_complete events
    analysis?: GeminiAnalysis
    // For constellation_sync events
    journeys?: UserJourney[]
    platforms?: PlatformSummary[]
  }
}

export type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'reconnecting'

export interface ConnectionStatus {
  state: ConnectionState
  connected: boolean
  lastPing?: string
  reconnectAttempts: number
  maxReconnectAttempts: number
  lastError?: string
}

// =============================================================================
// API RESPONSES
// =============================================================================

export interface ApiResponse<T> {
  data: T
  success: boolean
  error?: string
  timestamp: string
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  page: number
  pageSize: number
  totalCount: number
  totalPages: number
}

// =============================================================================
// UI STATE
// =============================================================================

export interface FilterState {
  platforms: Platform[]
  status: TestStatus[]
  dateRange: {
    from: string | null
    to: string | null
  }
  searchQuery: string
}

export interface VideoPlayerState {
  currentTime: number
  duration: number
  isPlaying: boolean
  volume: number
  isMuted: boolean
  playbackRate: number
  activeCheckpoint: Checkpoint | null
}

// =============================================================================
// THEME
// =============================================================================

export type ThemeMode = 'dark' | 'light' | 'system'

export interface ThemeContext {
  mode: ThemeMode
  resolvedMode: 'dark' | 'light'
  setMode: (mode: ThemeMode) => void
}

// =============================================================================
// CONSTANTS
// =============================================================================

export const PLATFORM_DISPLAY_NAMES: Record<Platform, string> = {
  ios: 'iOS',
  android: 'Android',
  'android-xr': 'Android XR',
  visionos: 'visionOS',
  watchos: 'watchOS',
  tvos: 'tvOS',
  desktop: 'Desktop',
  hub: 'Hub',
}

export const PLATFORM_ICONS: Record<Platform, string> = {
  ios: 'apple',
  android: 'smartphone',
  'android-xr': 'glasses',
  visionos: 'eye',
  watchos: 'watch',
  tvos: 'tv',
  desktop: 'monitor',
  hub: 'server',
}

export const STATUS_COLORS: Record<TestStatus, ColonyColor> = {
  pass: 'grove',
  fail: 'spark',
  in_progress: 'forge',
  pending: 'crystal',
  warning: 'beacon',
}

export const SEVERITY_COLORS: Record<Severity, ColonyColor> = {
  critical: 'spark',
  warning: 'beacon',
  info: 'crystal',
}

// Fibonacci timing constants (ms)
export const TIMING = {
  micro: 89,
  fast: 144,
  normal: 233,
  medium: 377,
  slow: 610,
  slower: 987,
  slowest: 1597,
  breathing: 2584,
} as const
