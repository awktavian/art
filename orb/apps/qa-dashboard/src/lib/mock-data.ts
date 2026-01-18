/**
 * Kagami QA Dashboard - Mock Data
 *
 * Realistic mock data for development and testing.
 * Replace with actual API calls in production.
 */

import type {
  Platform,
  UserJourney,
  PlatformSummary,
  AIIssue,
  Checkpoint,
} from '@/types'

// =============================================================================
// MOCK CHECKPOINTS
// =============================================================================

const createCheckpoints = (count: number, passRate: number = 0.8): Checkpoint[] => {
  return Array.from({ length: count }, (_, i) => {
    const isPassing = Math.random() < passRate
    return {
      id: `checkpoint-${i + 1}`,
      name: [
        'App Launch',
        'Login Screen',
        'Dashboard Load',
        'Navigation Test',
        'Form Input',
        'Button Interaction',
        'API Response',
        'Data Display',
        'Settings Access',
        'Logout Flow',
      ][i % 10],
      timestamp: (i + 1) * 12,
      status: isPassing ? 'pass' : 'fail',
      description: isPassing
        ? 'Checkpoint completed successfully'
        : 'Element not found within timeout',
      expected: 'Element should be visible and interactive',
      actual: isPassing
        ? 'Element visible and responsive'
        : 'Timeout after 5000ms waiting for element',
      screenshot: `/screenshots/checkpoint-${i + 1}.png`,
      geminiAnalysis: isPassing
        ? 'UI rendered correctly with all expected elements present.'
        : 'The expected button element was not found. Possible causes: slow network, API error, or UI change.',
    }
  })
}

// =============================================================================
// MOCK USER JOURNEYS
// =============================================================================

const journeyNames = [
  'Complete Onboarding Flow',
  'Login and Dashboard Access',
  'Profile Settings Update',
  'Data Sync Verification',
  'Notification Preferences',
  'Search and Filter',
  'Item Creation Flow',
  'Share Functionality',
  'Offline Mode Test',
  'Performance Under Load',
  'Accessibility Navigation',
  'Voice Command Integration',
]

export const mockJourneys: UserJourney[] = [
  // iOS Journeys
  ...Array.from({ length: 6 }, (_, i) => ({
    id: `ios-journey-${i + 1}`,
    name: journeyNames[i % journeyNames.length],
    platform: 'ios' as Platform,
    status: i === 2 ? 'fail' : i === 5 ? 'in_progress' : 'pass',
    duration: 45 + Math.floor(Math.random() * 120),
    videoUrl: '/videos/ios-test.mp4',
    thumbnailUrl: '/thumbnails/ios-thumb.jpg',
    checkpoints: createCheckpoints(8, i === 2 ? 0.5 : 0.9),
    createdAt: new Date(Date.now() - i * 3600000).toISOString(),
    commitSha: 'a846b9c2e', // pragma: allowlist secret
    branch: 'main',
    runNumber: 1247 - i,
    geminiSummary: i === 2
      ? 'Test failed at Login Screen checkpoint. The login button was not responsive, possibly due to a race condition in the authentication module.'
      : 'All checkpoints passed successfully. The user journey completed within expected time bounds.',
    previousRunId: i > 0 ? `ios-journey-${i}` : undefined,
  } as UserJourney)),

  // Android Journeys
  ...Array.from({ length: 5 }, (_, i) => ({
    id: `android-journey-${i + 1}`,
    name: journeyNames[(i + 3) % journeyNames.length],
    platform: 'android' as Platform,
    status: i === 1 ? 'fail' : i === 4 ? 'warning' : 'pass',
    duration: 52 + Math.floor(Math.random() * 90),
    videoUrl: '/videos/android-test.mp4',
    thumbnailUrl: '/thumbnails/android-thumb.jpg',
    checkpoints: createCheckpoints(7, i === 1 ? 0.4 : 0.85),
    createdAt: new Date(Date.now() - (i + 6) * 3600000).toISOString(),
    commitSha: 'bdde21bba', // pragma: allowlist secret
    branch: 'develop',
    runNumber: 892 - i,
    geminiSummary: i === 1
      ? 'Multiple checkpoint failures detected. The navigation component appears to have timing issues on lower-end devices.'
      : 'Test completed with acceptable performance metrics.',
  } as UserJourney)),

  // visionOS Journeys
  ...Array.from({ length: 4 }, (_, i) => ({
    id: `visionos-journey-${i + 1}`,
    name: journeyNames[(i + 6) % journeyNames.length],
    platform: 'visionos' as Platform,
    status: i === 0 ? 'in_progress' : 'pass',
    duration: 68 + Math.floor(Math.random() * 60),
    videoUrl: '/videos/visionos-test.mp4',
    thumbnailUrl: '/thumbnails/visionos-thumb.jpg',
    checkpoints: createCheckpoints(6, 0.92),
    createdAt: new Date(Date.now() - (i + 11) * 3600000).toISOString(),
    commitSha: 'f1aade7a3', // pragma: allowlist secret
    branch: 'feature/spatial-ui',
    runNumber: 234 - i,
    geminiSummary: 'Spatial UI interactions working as expected. Hand tracking accuracy within tolerance.',
  } as UserJourney)),

  // Desktop Journeys
  ...Array.from({ length: 4 }, (_, i) => ({
    id: `desktop-journey-${i + 1}`,
    name: journeyNames[(i + 8) % journeyNames.length],
    platform: 'desktop' as Platform,
    status: i === 2 ? 'fail' : 'pass',
    duration: 38 + Math.floor(Math.random() * 50),
    videoUrl: '/videos/desktop-test.mp4',
    thumbnailUrl: '/thumbnails/desktop-thumb.jpg',
    checkpoints: createCheckpoints(9, i === 2 ? 0.6 : 0.95),
    createdAt: new Date(Date.now() - (i + 15) * 3600000).toISOString(),
    commitSha: 'd2d026fcd', // pragma: allowlist secret
    branch: 'main',
    runNumber: 567 - i,
    geminiSummary: i === 2
      ? 'Window resize handler not responding correctly. Menu items clipped at smaller viewport sizes.'
      : 'Desktop application performing within expected parameters.',
  } as UserJourney)),

  // watchOS Journeys
  ...Array.from({ length: 3 }, (_, i) => ({
    id: `watchos-journey-${i + 1}`,
    name: journeyNames[i % journeyNames.length],
    platform: 'watchos' as Platform,
    status: 'pass',
    duration: 28 + Math.floor(Math.random() * 30),
    videoUrl: '/videos/watchos-test.mp4',
    thumbnailUrl: '/thumbnails/watchos-thumb.jpg',
    checkpoints: createCheckpoints(5, 0.95),
    createdAt: new Date(Date.now() - (i + 19) * 3600000).toISOString(),
    commitSha: '6ee49bd79', // pragma: allowlist secret
    branch: 'main',
    runNumber: 123 - i,
    geminiSummary: 'Complications and glances rendering correctly. Haptic feedback timing accurate.',
  } as UserJourney)),

  // Hub Journeys
  ...Array.from({ length: 3 }, (_, i) => ({
    id: `hub-journey-${i + 1}`,
    name: ['Device Discovery', 'Protocol Handshake', 'Data Synchronization'][i],
    platform: 'hub' as Platform,
    status: i === 1 ? 'warning' : 'pass',
    duration: 95 + Math.floor(Math.random() * 60),
    videoUrl: '/videos/hub-test.mp4',
    thumbnailUrl: '/thumbnails/hub-thumb.jpg',
    checkpoints: createCheckpoints(10, i === 1 ? 0.75 : 0.9),
    createdAt: new Date(Date.now() - (i + 22) * 3600000).toISOString(),
    commitSha: 'a846b9c2e', // pragma: allowlist secret
    branch: 'main',
    runNumber: 456 - i,
    geminiSummary: i === 1
      ? 'Protocol handshake occasionally timing out with legacy devices. Consider increasing timeout threshold.'
      : 'Hub integration tests passing. All connected devices responding within SLA.',
  } as UserJourney)),
]

// =============================================================================
// MOCK PLATFORM SUMMARIES
// =============================================================================

export const mockPlatformSummaries: PlatformSummary[] = [
  {
    platform: 'ios',
    displayName: 'iOS',
    icon: 'Smartphone',
    totalJourneys: 6,
    passedJourneys: 4,
    failedJourneys: 1,
    inProgressJourneys: 1,
    lastTestTime: new Date(Date.now() - 1800000).toISOString(),
    healthScore: 85,
    trend: 'up',
    trendValue: 5,
  },
  {
    platform: 'android',
    displayName: 'Android',
    icon: 'Smartphone',
    totalJourneys: 5,
    passedJourneys: 3,
    failedJourneys: 1,
    inProgressJourneys: 0,
    lastTestTime: new Date(Date.now() - 7200000).toISOString(),
    healthScore: 72,
    trend: 'down',
    trendValue: -8,
  },
  {
    platform: 'visionos',
    displayName: 'visionOS',
    icon: 'Eye',
    totalJourneys: 4,
    passedJourneys: 3,
    failedJourneys: 0,
    inProgressJourneys: 1,
    lastTestTime: new Date(Date.now() - 3600000).toISOString(),
    healthScore: 95,
    trend: 'stable',
    trendValue: 0,
  },
  {
    platform: 'desktop',
    displayName: 'Desktop',
    icon: 'Monitor',
    totalJourneys: 4,
    passedJourneys: 3,
    failedJourneys: 1,
    inProgressJourneys: 0,
    lastTestTime: new Date(Date.now() - 5400000).toISOString(),
    healthScore: 78,
    trend: 'down',
    trendValue: -3,
  },
  {
    platform: 'watchos',
    displayName: 'watchOS',
    icon: 'Watch',
    totalJourneys: 3,
    passedJourneys: 3,
    failedJourneys: 0,
    inProgressJourneys: 0,
    lastTestTime: new Date(Date.now() - 10800000).toISOString(),
    healthScore: 100,
    trend: 'stable',
    trendValue: 0,
  },
  {
    platform: 'hub',
    displayName: 'Hub',
    icon: 'Server',
    totalJourneys: 3,
    passedJourneys: 2,
    failedJourneys: 0,
    inProgressJourneys: 0,
    lastTestTime: new Date(Date.now() - 14400000).toISOString(),
    healthScore: 88,
    trend: 'up',
    trendValue: 12,
  },
]

// =============================================================================
// MOCK AI ISSUES
// =============================================================================

export const mockAIIssues: AIIssue[] = [
  {
    id: 'issue-1',
    journeyId: 'ios-journey-3',
    severity: 'critical',
    title: 'Login Button Unresponsive',
    description: 'The login button did not respond to tap events after entering credentials. This appears to be a race condition between the keyboard dismiss animation and button enablement.',
    suggestedFix: 'Add a debounce delay to the keyboard dismiss handler before enabling the login button. Consider using a loading state to prevent double-taps.',
    videoClipUrl: '/clips/issue-1.mp4',
    startTime: 24,
    endTime: 32,
    category: 'Interaction',
    confidence: 0.94,
    createdAt: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: 'issue-2',
    journeyId: 'android-journey-2',
    severity: 'critical',
    title: 'Navigation Stack Corruption',
    description: 'Back navigation resulted in incorrect screen being displayed. The navigation stack appears to have been corrupted after a deep link was processed.',
    suggestedFix: 'Review deep link handling logic. Ensure navigation state is properly reset before processing new deep links.',
    videoClipUrl: '/clips/issue-2.mp4',
    startTime: 45,
    endTime: 58,
    category: 'Navigation',
    confidence: 0.89,
    createdAt: new Date(Date.now() - 7200000).toISOString(),
  },
  {
    id: 'issue-3',
    journeyId: 'desktop-journey-3',
    severity: 'warning',
    title: 'Menu Clipping at Small Viewport',
    description: 'Dropdown menu items are clipped when the window is resized below 1024px width. Users cannot access all menu options.',
    suggestedFix: 'Implement responsive menu that collapses to hamburger menu at smaller breakpoints. Add scroll behavior to dropdown when height is constrained.',
    videoClipUrl: '/clips/issue-3.mp4',
    startTime: 67,
    endTime: 75,
    category: 'Layout',
    confidence: 0.97,
    createdAt: new Date(Date.now() - 14400000).toISOString(),
  },
  {
    id: 'issue-4',
    journeyId: 'hub-journey-2',
    severity: 'warning',
    title: 'Protocol Timeout with Legacy Devices',
    description: 'Connection handshake timing out when communicating with devices running firmware v1.x. Modern devices connect without issue.',
    suggestedFix: 'Increase handshake timeout from 3s to 8s for detected legacy devices. Add fallback protocol version negotiation.',
    videoClipUrl: '/clips/issue-4.mp4',
    startTime: 89,
    endTime: 105,
    category: 'Protocol',
    confidence: 0.82,
    createdAt: new Date(Date.now() - 21600000).toISOString(),
  },
  {
    id: 'issue-5',
    journeyId: 'android-journey-5',
    severity: 'info',
    title: 'Animation Jank on First Load',
    description: 'Minor animation stutter observed on first app launch. Subsequent launches are smooth. Likely shader compilation or resource loading.',
    suggestedFix: 'Consider preloading animation resources during splash screen. Enable GPU shader caching.',
    videoClipUrl: '/clips/issue-5.mp4',
    startTime: 2,
    endTime: 5,
    category: 'Performance',
    confidence: 0.76,
    createdAt: new Date(Date.now() - 28800000).toISOString(),
  },
  {
    id: 'issue-6',
    journeyId: 'ios-journey-3',
    severity: 'info',
    title: 'Keyboard Overlap on Small Devices',
    description: 'On iPhone SE, the keyboard overlaps the bottom input field. Content is not scrolling into view automatically.',
    suggestedFix: 'Implement keyboard avoidance view with automatic content inset adjustment. Test on all device sizes.',
    videoClipUrl: '/clips/issue-6.mp4',
    startTime: 18,
    endTime: 23,
    category: 'Layout',
    confidence: 0.91,
    createdAt: new Date(Date.now() - 3700000).toISOString(),
  },
]

// =============================================================================
// MOCK TREND DATA (for charts)
// =============================================================================

export const mockTrendData = Array.from({ length: 14 }, (_, i) => {
  const date = new Date()
  date.setDate(date.getDate() - (13 - i))
  return {
    date: date.toISOString().split('T')[0],
    passRate: 75 + Math.floor(Math.random() * 20),
    totalTests: 20 + Math.floor(Math.random() * 15),
    avgDuration: 45 + Math.floor(Math.random() * 30),
  }
})

// =============================================================================
// API SIMULATION FUNCTIONS
// =============================================================================

export async function fetchPlatformSummaries(): Promise<PlatformSummary[]> {
  // Simulate network delay
  await new Promise((resolve) => setTimeout(resolve, 300))
  return mockPlatformSummaries
}

export async function fetchJourneys(platform?: Platform): Promise<UserJourney[]> {
  await new Promise((resolve) => setTimeout(resolve, 400))
  if (platform) {
    return mockJourneys.filter((j) => j.platform === platform)
  }
  return mockJourneys
}

export async function fetchJourney(id: string): Promise<UserJourney | null> {
  await new Promise((resolve) => setTimeout(resolve, 200))
  return mockJourneys.find((j) => j.id === id) || null
}

export async function fetchAIIssues(): Promise<AIIssue[]> {
  await new Promise((resolve) => setTimeout(resolve, 350))
  return mockAIIssues
}

export async function fetchTrendData() {
  await new Promise((resolve) => setTimeout(resolve, 250))
  return mockTrendData
}

// =============================================================================
// CALCULATE OVERALL HEALTH
// =============================================================================

export function calculateOverallHealth(summaries: PlatformSummary[]): number {
  if (summaries.length === 0) return 0
  const total = summaries.reduce((sum, s) => sum + s.healthScore, 0)
  return Math.round(total / summaries.length)
}
