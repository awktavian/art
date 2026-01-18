/**
 * Performance Module Exports
 *
 * This module provides performance tracking, regression detection,
 * and baseline management for the Kagami QA Pipeline.
 */

export {
  // Main tracker
  PerformanceTracker,
  getPerformanceTracker,
  resetPerformanceTracker,

  // Constants
  HARD_THRESHOLDS,
  REGRESSION_THRESHOLD_PERCENT,
  MIN_SAMPLE_SIZE,
  MAX_HISTORY_ENTRIES,

  // Utility functions
  calculatePercentiles,

  // Types
  type PercentileDistribution,
  type CheckpointBaseline,
  type JourneyBaseline,
  type PerformanceBaseline,
  type PerformanceMeasurement,
  type PerformanceRegression,
  type PerformanceReport,
  type HistoricalEntry,
  type PerformanceHistory,
} from './performance-tracker.js';
