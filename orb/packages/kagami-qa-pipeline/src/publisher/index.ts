/**
 * Publisher Module
 *
 * Exports for connecting QA test harness to dashboard and external systems.
 */

export {
  // Main class
  DashboardPublisher,

  // Singleton access
  getPublisher,
  resetPublisher,

  // Convenience functions
  publishTestResult,
  pushRealtimeUpdate,
  uploadVideo,

  // Helper functions
  formatPhaseResult,
  formatConstellationResult,
  formatAnalysisResult,
  calculateByzantineScores,

  // Types
  type TestEventType,
  type ConnectionState,
  type ByzantineScores,
  type VideoTimestamp,
  type TestUpdateEvent,
  type TestEventPayload,
  type TestStartedPayload,
  type CheckpointPassedPayload,
  type CheckpointFailedPayload,
  type TestCompletedPayload,
  type AnalysisCompletePayload,
  type ConstellationSyncPayload,
  type TestResult,
  type HistoricalResult,
  type DashboardPublisherConfig,
} from './dashboard-publisher.js';
