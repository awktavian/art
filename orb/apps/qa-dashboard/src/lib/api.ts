/**
 * Kagami QA Dashboard - API Client
 *
 * Real HTTP client for connecting to the QA Pipeline server.
 * Falls back to mock data in development when API is unavailable.
 */

import type {
  Platform,
  UserJourney,
  PlatformSummary,
  AIIssue,
  TestStatus,
} from '@/types'

// =============================================================================
// CONFIGURATION
// =============================================================================

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080'

// =============================================================================
// RATE LIMITING & RETRY CONFIGURATION
// =============================================================================

/** Maximum number of retry attempts for failed requests */
const MAX_RETRIES = 3

/** Initial backoff delay in milliseconds */
const INITIAL_BACKOFF_MS = 500

/** Maximum backoff delay in milliseconds */
const MAX_BACKOFF_MS = 10000

/** Jitter factor (0-1) to add randomness to backoff */
const BACKOFF_JITTER = 0.3

/** HTTP status codes that should trigger a retry */
const RETRYABLE_STATUS_CODES = new Set([408, 429, 500, 502, 503, 504])

// =============================================================================
// HTTP CLIENT
// =============================================================================

interface ApiError {
  message: string
  status: number
  details?: unknown
}

class ApiClientError extends Error {
  status: number
  details?: unknown
  retryable: boolean

  constructor(message: string, status: number, details?: unknown) {
    super(message)
    this.name = 'ApiClientError'
    this.status = status
    this.details = details
    // Determine if this error is retryable based on status code
    this.retryable = RETRYABLE_STATUS_CODES.has(status)
  }
}

/**
 * Calculate exponential backoff with jitter
 * @param attempt - The current attempt number (0-indexed)
 * @returns Delay in milliseconds
 */
function calculateBackoff(attempt: number): number {
  const exponentialDelay = INITIAL_BACKOFF_MS * Math.pow(2, attempt)
  const cappedDelay = Math.min(exponentialDelay, MAX_BACKOFF_MS)
  // Add jitter to prevent thundering herd
  const jitter = cappedDelay * BACKOFF_JITTER * Math.random()
  return Math.floor(cappedDelay + jitter)
}

/**
 * Sleep for a specified duration
 */
function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeout: number = 10000
): Promise<Response> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeout)

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        ...options.headers,
      },
    })
    clearTimeout(timeoutId)
    return response
  } catch (error) {
    clearTimeout(timeoutId)
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiClientError('Request timeout', 408)
    }
    throw error
  }
}

/**
 * Make an API request with exponential backoff retry logic
 *
 * Retries on:
 * - 408 Request Timeout
 * - 429 Too Many Requests
 * - 500 Internal Server Error
 * - 502 Bad Gateway
 * - 503 Service Unavailable
 * - 504 Gateway Timeout
 * - Network errors
 */
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`
  let lastError: ApiClientError | null = null

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      // Wait before retrying (skip on first attempt)
      if (attempt > 0) {
        const backoffMs = calculateBackoff(attempt - 1)
        console.warn(`[API] Retry ${attempt}/${MAX_RETRIES} after ${backoffMs}ms delay for ${endpoint}`)
        await sleep(backoffMs)
      }

      const response = await fetchWithTimeout(url, options)

      if (!response.ok) {
        let errorDetails: unknown
        try {
          errorDetails = await response.json()
        } catch {
          errorDetails = await response.text()
        }

        const error = new ApiClientError(
          `API request failed: ${response.statusText}`,
          response.status,
          errorDetails
        )

        // Check if we should retry
        if (error.retryable && attempt < MAX_RETRIES) {
          lastError = error
          continue // Retry
        }

        throw error
      }

      const data = await response.json()

      // Handle wrapped API responses
      if (data && typeof data === 'object' && 'data' in data) {
        return data.data as T
      }

      return data as T
    } catch (error) {
      if (error instanceof ApiClientError) {
        // If it's retryable and we haven't exhausted retries, continue
        if (error.retryable && attempt < MAX_RETRIES) {
          lastError = error
          continue
        }
        throw error
      }

      // Network errors are retryable
      if (attempt < MAX_RETRIES) {
        lastError = new ApiClientError(
          error instanceof Error ? error.message : 'Unknown error occurred',
          0
        )
        continue
      }

      throw new ApiClientError(
        error instanceof Error ? error.message : 'Unknown error occurred',
        0
      )
    }
  }

  // If we've exhausted all retries, throw the last error
  throw lastError || new ApiClientError('Request failed after retries', 0)
}

// =============================================================================
// API FUNCTIONS
// =============================================================================

/**
 * Fetch platform summaries from the API
 */
export async function fetchPlatformSummaries(): Promise<PlatformSummary[]> {
  return apiRequest<PlatformSummary[]>('/api/platforms')
}

/**
 * Filters for fetching journeys
 */
export interface JourneyFilters {
  platform?: Platform
  status?: TestStatus
  branch?: string
  commitSha?: string
  limit?: number
  offset?: number
}

/**
 * Fetch user journeys with optional filters
 */
export async function fetchJourneys(
  filters?: JourneyFilters | Platform
): Promise<UserJourney[]> {
  const params = new URLSearchParams()

  // Handle legacy single platform parameter
  if (typeof filters === 'string') {
    params.append('platform', filters)
  } else if (filters) {
    if (filters.platform) params.append('platform', filters.platform)
    if (filters.status) params.append('status', filters.status)
    if (filters.branch) params.append('branch', filters.branch)
    if (filters.commitSha) params.append('commitSha', filters.commitSha)
    if (filters.limit) params.append('limit', filters.limit.toString())
    if (filters.offset) params.append('offset', filters.offset.toString())
  }

  const queryString = params.toString()
  const endpoint = `/api/journeys${queryString ? `?${queryString}` : ''}`

  return apiRequest<UserJourney[]>(endpoint)
}

/**
 * Fetch a single journey by ID
 */
export async function fetchJourney(id: string): Promise<UserJourney | null> {
  try {
    return await apiRequest<UserJourney>(`/api/journeys/${id}`)
  } catch (error) {
    if (error instanceof ApiClientError && error.status === 404) {
      return null
    }
    throw error
  }
}

/**
 * Fetch AI-detected issues
 */
export async function fetchAIIssues(): Promise<AIIssue[]> {
  return apiRequest<AIIssue[]>('/api/analysis/issues')
}

/**
 * Trend data point type
 * Uses index signature to be compatible with chart components
 */
export interface TrendDataPoint {
  date: string
  passRate: number
  totalTests: number
  avgDuration: number
  [key: string]: number | string
}

/**
 * Fetch trend data for the specified number of days
 */
export async function fetchTrendData(days: number = 14): Promise<TrendDataPoint[]> {
  return apiRequest<TrendDataPoint[]>(`/api/metrics/trends?days=${days}`)
}

/**
 * Run history entry type
 */
export interface RunHistoryEntry {
  id: string
  status: TestStatus
  date: string
  commitSha?: string
  branch?: string
  duration?: number
  passedCheckpoints?: number
  totalCheckpoints?: number
}

/**
 * Fetch run history for a specific journey
 */
export async function fetchRunHistory(journeyId: string): Promise<RunHistoryEntry[]> {
  return apiRequest<RunHistoryEntry[]>(`/api/journeys/${journeyId}/history`)
}

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

/**
 * Calculate overall health score from platform summaries
 */
export function calculateOverallHealth(summaries: PlatformSummary[]): number {
  if (summaries.length === 0) return 0
  const total = summaries.reduce((sum, s) => sum + s.healthScore, 0)
  return Math.round(total / summaries.length)
}

/**
 * Check if the API is available
 */
export async function checkApiHealth(): Promise<boolean> {
  try {
    const response = await fetchWithTimeout(`${API_BASE_URL}/api/health`, {}, 5000)
    return response.ok
  } catch {
    return false
  }
}

// =============================================================================
// MOCK DATA FALLBACK (for development)
// =============================================================================

import {
  mockPlatformSummaries,
  mockJourneys,
  mockAIIssues,
  mockTrendData,
} from './mock-data'

/**
 * Wrapper that falls back to mock data when API is unavailable
 */
export function withMockFallback<T extends (...args: Parameters<T>) => Promise<unknown>>(
  apiFn: T,
  mockFn: (...args: Parameters<T>) => ReturnType<T>
): T {
  return (async (...args: Parameters<T>): Promise<ReturnType<T>> => {
    try {
      return await apiFn(...args) as ReturnType<T>
    } catch (error) {
      // In development, fall back to mock data
      if (process.env.NODE_ENV === 'development') {
        console.warn(`API call failed, using mock data:`, error)
        return mockFn(...args)
      }
      throw error
    }
  }) as T
}

// Create fallback versions of each API function
const mockFetchPlatformSummaries = async (): Promise<PlatformSummary[]> => {
  await new Promise((resolve) => setTimeout(resolve, 300))
  return mockPlatformSummaries
}

const mockFetchJourneys = async (
  filters?: JourneyFilters | Platform
): Promise<UserJourney[]> => {
  await new Promise((resolve) => setTimeout(resolve, 400))
  let journeys = [...mockJourneys]

  if (typeof filters === 'string') {
    journeys = journeys.filter((j) => j.platform === filters)
  } else if (filters?.platform) {
    journeys = journeys.filter((j) => j.platform === filters.platform)
  }

  return journeys
}

const mockFetchJourney = async (id: string): Promise<UserJourney | null> => {
  await new Promise((resolve) => setTimeout(resolve, 200))
  return mockJourneys.find((j) => j.id === id) || null
}

const mockFetchAIIssues = async (): Promise<AIIssue[]> => {
  await new Promise((resolve) => setTimeout(resolve, 350))
  return mockAIIssues
}

const mockFetchTrendData = async (_days?: number): Promise<TrendDataPoint[]> => {
  await new Promise((resolve) => setTimeout(resolve, 250))
  return mockTrendData
}

const mockFetchRunHistory = async (journeyId: string): Promise<RunHistoryEntry[]> => {
  await new Promise((resolve) => setTimeout(resolve, 200))
  const journey = mockJourneys.find((j) => j.id === journeyId)
  if (!journey) return []

  // Generate mock history
  return [
    {
      id: journey.id,
      status: journey.status,
      date: journey.createdAt,
      commitSha: journey.commitSha,
      branch: journey.branch,
    },
    {
      id: 'prev-1',
      status: 'pass',
      date: new Date(Date.now() - 86400000).toISOString(),
    },
    {
      id: 'prev-2',
      status: 'fail',
      date: new Date(Date.now() - 172800000).toISOString(),
    },
    {
      id: 'prev-3',
      status: 'pass',
      date: new Date(Date.now() - 259200000).toISOString(),
    },
  ]
}

// =============================================================================
// EXPORTED API FUNCTIONS (with fallback support)
// =============================================================================

/**
 * Use these exports in components - they will automatically fall back
 * to mock data in development if the API is unavailable.
 */
export const api = {
  fetchPlatformSummaries: withMockFallback(fetchPlatformSummaries, mockFetchPlatformSummaries),
  fetchJourneys: withMockFallback(fetchJourneys, mockFetchJourneys),
  fetchJourney: withMockFallback(fetchJourney, mockFetchJourney),
  fetchAIIssues: withMockFallback(fetchAIIssues, mockFetchAIIssues),
  fetchTrendData: withMockFallback(fetchTrendData, mockFetchTrendData),
  fetchRunHistory: withMockFallback(fetchRunHistory, mockFetchRunHistory),
  calculateOverallHealth,
  checkApiHealth,
}

// Default export for convenience
export default api
