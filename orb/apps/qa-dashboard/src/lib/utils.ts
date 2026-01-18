/**
 * Kagami QA Dashboard - Utility Functions
 */

import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { TestStatus, Severity, ColonyColor, Platform } from '@/types'

/**
 * Merge Tailwind CSS classes with proper precedence
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

/**
 * Format duration from seconds to human readable string
 */
export function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`
}

/**
 * Format timestamp for display
 */
export function formatTimestamp(timestamp: number): string {
  const minutes = Math.floor(timestamp / 60)
  const secs = Math.floor(timestamp % 60)
  return `${minutes}:${secs.toString().padStart(2, '0')}`
}

/**
 * Format date to relative time
 */
export function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / (1000 * 60))
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  })
}

/**
 * Format date for display
 */
export function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

/**
 * Get status color class
 */
export function getStatusColor(status: TestStatus): ColonyColor {
  const map: Record<TestStatus, ColonyColor> = {
    pass: 'grove',
    fail: 'spark',
    in_progress: 'forge',
    pending: 'crystal',
    warning: 'beacon',
  }
  return map[status]
}

/**
 * Get severity color class
 */
export function getSeverityColor(severity: Severity): ColonyColor {
  const map: Record<Severity, ColonyColor> = {
    critical: 'spark',
    warning: 'beacon',
    info: 'crystal',
  }
  return map[severity]
}

/**
 * Get colony color hex value
 */
export function getColonyHex(colony: ColonyColor): string {
  const colors: Record<ColonyColor, string> = {
    spark: '#FF6B35',
    forge: '#FF9500',
    flow: '#5AC8FA',
    nexus: '#AF52DE',
    beacon: '#FFD60A',
    grove: '#32D74B',
    crystal: '#64D2FF',
  }
  return colors[colony]
}

/**
 * Get status text
 */
export function getStatusText(status: TestStatus): string {
  const map: Record<TestStatus, string> = {
    pass: 'Passed',
    fail: 'Failed',
    in_progress: 'In Progress',
    pending: 'Pending',
    warning: 'Warning',
  }
  return map[status]
}

/**
 * Calculate health score color based on value
 */
export function getHealthColor(score: number): ColonyColor {
  if (score >= 90) return 'grove'
  if (score >= 70) return 'beacon'
  if (score >= 50) return 'forge'
  return 'spark'
}

/**
 * Calculate pass rate from counts
 */
export function calculatePassRate(passed: number, total: number): number {
  if (total === 0) return 0
  return Math.round((passed / total) * 100)
}

/**
 * Get platform icon name
 */
export function getPlatformIcon(platform: Platform): string {
  const icons: Record<Platform, string> = {
    ios: 'Smartphone',
    android: 'Smartphone',
    'android-xr': 'Glasses',
    visionos: 'Eye',
    watchos: 'Watch',
    tvos: 'Tv',
    desktop: 'Monitor',
    hub: 'Server',
  }
  return icons[platform]
}

/**
 * Get platform display name
 */
export function getPlatformName(platform: Platform): string {
  const names: Record<Platform, string> = {
    ios: 'iOS',
    android: 'Android',
    'android-xr': 'Android XR',
    visionos: 'visionOS',
    watchos: 'watchOS',
    tvos: 'tvOS',
    desktop: 'Desktop',
    hub: 'Hub',
  }
  return names[platform]
}

/**
 * Truncate text with ellipsis
 */
export function truncate(str: string, length: number): string {
  if (str.length <= length) return str
  return str.slice(0, length - 3) + '...'
}

/**
 * Generate a unique ID
 */
export function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`
}

/**
 * Debounce function
 */
export function debounce<T extends (...args: Parameters<T>) => ReturnType<T>>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout> | null = null

  return function (...args: Parameters<T>) {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    timeoutId = setTimeout(() => func(...args), wait)
  }
}

/**
 * Throttle function
 */
export function throttle<T extends (...args: Parameters<T>) => ReturnType<T>>(
  func: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle = false

  return function (...args: Parameters<T>) {
    if (!inThrottle) {
      func(...args)
      inThrottle = true
      setTimeout(() => (inThrottle = false), limit)
    }
  }
}

/**
 * Check if running in browser
 */
export function isBrowser(): boolean {
  return typeof window !== 'undefined'
}

/**
 * Get contrast color for text on a given background
 */
export function getContrastColor(hexColor: string): 'white' | 'black' {
  const r = parseInt(hexColor.slice(1, 3), 16)
  const g = parseInt(hexColor.slice(3, 5), 16)
  const b = parseInt(hexColor.slice(5, 7), 16)

  // Using relative luminance formula
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255

  return luminance > 0.5 ? 'black' : 'white'
}

/**
 * Deep clone an object
 */
export function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj))
}

/**
 * Check if two arrays are equal (shallow)
 */
export function arraysEqual<T>(a: T[], b: T[]): boolean {
  if (a.length !== b.length) return false
  return a.every((val, idx) => val === b[idx])
}

/**
 * Group array by key
 */
export function groupBy<T>(array: T[], key: keyof T): Record<string, T[]> {
  return array.reduce(
    (groups, item) => {
      const keyValue = String(item[key])
      if (!groups[keyValue]) {
        groups[keyValue] = []
      }
      groups[keyValue].push(item)
      return groups
    },
    {} as Record<string, T[]>
  )
}

/**
 * Sort array by key
 */
export function sortBy<T>(
  array: T[],
  key: keyof T,
  direction: 'asc' | 'desc' = 'asc'
): T[] {
  return [...array].sort((a, b) => {
    const aVal = a[key]
    const bVal = b[key]

    if (aVal < bVal) return direction === 'asc' ? -1 : 1
    if (aVal > bVal) return direction === 'asc' ? 1 : -1
    return 0
  })
}
