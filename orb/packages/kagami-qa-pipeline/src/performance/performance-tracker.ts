/**
 * Performance Tracker for Kagami QA Pipeline
 *
 * Provides performance regression detection, baseline management,
 * and historical performance tracking with percentile distributions.
 *
 * Features:
 * - Hard thresholds from canonical journey specs
 * - Baseline storage and auto-generation
 * - Regression detection (>10% slower triggers alert)
 * - Percentile tracking (p50, p95, p99)
 * - Historical trend analysis
 *
 * Colony: Crystal (e7) -- Verification & Polish
 * h(x) >= 0. Always.
 */

import * as fs from 'fs';
import * as path from 'path';
import { createChildLogger } from '../logger.js';
import {
  type Platform,
  SINGLE_DEVICE_JOURNEYS,
  CONSTELLATION_JOURNEYS,
} from '../journeys/canonical-journeys.js';

// =============================================================================
// CONSTANTS
// =============================================================================

const logger = createChildLogger({ component: 'performance-tracker' });

/**
 * Hard performance thresholds from canonical specs
 * These are non-negotiable limits that MUST NOT be exceeded
 */
export const HARD_THRESHOLDS = {
  /** Maximum time for scene execution */
  SCENE_EXECUTION_MS: 500,
  /** Maximum time for device control operations */
  DEVICE_CONTROL_MS: 200,
  /** Maximum latency for voice streaming */
  VOICE_STREAMING_LATENCY_MS: 150,
  /** Maximum time for mDNS discovery */
  MDNS_DISCOVERY_MS: 3000,
  /** Maximum time for mesh sync operations */
  MESH_SYNC_MS: 2000,
  /** Maximum time for emergency broadcast */
  EMERGENCY_BROADCAST_MS: 500,
  /** Maximum time for app launch to responsive */
  APP_LAUNCH_MS: 3000,
  /** Maximum time for navigation transitions */
  NAVIGATION_TRANSITION_MS: 1000,
} as const;

/**
 * Regression detection threshold (percentage)
 * If current run is >10% slower than baseline, it's a regression
 */
export const REGRESSION_THRESHOLD_PERCENT = 10;

/**
 * Minimum sample size before calculating reliable percentiles
 */
export const MIN_SAMPLE_SIZE = 5;

/**
 * Maximum history entries to keep per checkpoint
 */
export const MAX_HISTORY_ENTRIES = 1000;

// =============================================================================
// TYPES
// =============================================================================

/**
 * Percentile distribution for performance metrics
 */
export interface PercentileDistribution {
  p50: number;
  p75: number;
  p90: number;
  p95: number;
  p99: number;
  min: number;
  max: number;
  mean: number;
  stdDev: number;
  count: number;
}

/**
 * Performance baseline for a single checkpoint
 */
export interface CheckpointBaseline {
  checkpointId: string;
  checkpointName: string;
  journeyId: string;
  platform: Platform;
  /** Hard threshold from canonical spec (ms) */
  hardThresholdMs: number;
  /** Baseline percentiles from historical runs */
  baseline: PercentileDistribution;
  /** When the baseline was last updated */
  lastUpdated: string;
  /** Number of samples used to calculate baseline */
  sampleCount: number;
}

/**
 * Performance baseline for a journey
 */
export interface JourneyBaseline {
  journeyId: string;
  journeyName: string;
  platform: Platform;
  /** Expected total duration from spec */
  expectedDurationMs: number;
  /** Baseline for total journey duration */
  totalDurationBaseline: PercentileDistribution;
  /** Baselines for each checkpoint */
  checkpointBaselines: CheckpointBaseline[];
  /** When the baseline was last updated */
  lastUpdated: string;
}

/**
 * Complete baseline file structure
 */
export interface PerformanceBaseline {
  version: string;
  generatedAt: string;
  updatedAt: string;
  gitCommit?: string;
  gitBranch?: string;
  journeyBaselines: JourneyBaseline[];
}

/**
 * Single performance measurement
 */
export interface PerformanceMeasurement {
  checkpointId: string;
  journeyId: string;
  platform: Platform;
  durationMs: number;
  timestamp: string;
  /** Whether this measurement exceeded hard threshold */
  exceededHardThreshold: boolean;
  /** Whether this is a regression from baseline */
  isRegression: boolean;
  /** Percentage difference from baseline p50 */
  baselineDiffPercent: number | null;
}

/**
 * Performance regression alert
 */
export interface PerformanceRegression {
  checkpointId: string;
  checkpointName: string;
  journeyId: string;
  platform: Platform;
  currentDurationMs: number;
  baselineP50Ms: number;
  hardThresholdMs: number;
  percentSlower: number;
  exceededHardThreshold: boolean;
  severity: 'warning' | 'critical';
  timestamp: string;
}

/**
 * Performance report for a test run
 */
export interface PerformanceReport {
  runId: string;
  startedAt: string;
  completedAt: string;
  journeyId: string;
  platform: Platform;
  /** Overall pass/fail based on hard thresholds */
  passed: boolean;
  /** Total duration for the journey */
  totalDurationMs: number;
  /** Expected duration from spec */
  expectedDurationMs: number;
  /** Whether total duration regressed */
  totalDurationRegressed: boolean;
  /** Individual checkpoint measurements */
  measurements: PerformanceMeasurement[];
  /** Detected regressions */
  regressions: PerformanceRegression[];
  /** Summary statistics */
  summary: {
    checkpointsTotal: number;
    checkpointsPassed: number;
    checkpointsExceededThreshold: number;
    checkpointsRegressed: number;
    avgDurationVsBaseline: number;
  };
  /** Current vs baseline comparison */
  comparison: {
    currentPercentiles: PercentileDistribution;
    baselinePercentiles: PercentileDistribution | null;
  } | null;
}

/**
 * Historical performance entry
 */
export interface HistoricalEntry {
  timestamp: string;
  durationMs: number;
  gitCommit?: string;
  passed: boolean;
}

/**
 * Historical data structure for trend analysis
 */
export interface PerformanceHistory {
  version: string;
  checkpointHistory: Record<string, HistoricalEntry[]>;
  journeyHistory: Record<string, HistoricalEntry[]>;
}

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

/**
 * Calculate percentile from sorted array
 */
function percentile(sortedArray: number[], p: number): number {
  if (sortedArray.length === 0) return 0;
  const index = (p / 100) * (sortedArray.length - 1);
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) return sortedArray[lower]!;
  return sortedArray[lower]! + (sortedArray[upper]! - sortedArray[lower]!) * (index - lower);
}

/**
 * Calculate percentile distribution from array of durations
 */
export function calculatePercentiles(durations: number[]): PercentileDistribution {
  if (durations.length === 0) {
    return {
      p50: 0,
      p75: 0,
      p90: 0,
      p95: 0,
      p99: 0,
      min: 0,
      max: 0,
      mean: 0,
      stdDev: 0,
      count: 0,
    };
  }

  const sorted = [...durations].sort((a, b) => a - b);
  const sum = sorted.reduce((a, b) => a + b, 0);
  const mean = sum / sorted.length;
  const squaredDiffs = sorted.map((d) => Math.pow(d - mean, 2));
  const variance = squaredDiffs.reduce((a, b) => a + b, 0) / sorted.length;

  return {
    p50: percentile(sorted, 50),
    p75: percentile(sorted, 75),
    p90: percentile(sorted, 90),
    p95: percentile(sorted, 95),
    p99: percentile(sorted, 99),
    min: sorted[0]!,
    max: sorted[sorted.length - 1]!,
    mean,
    stdDev: Math.sqrt(variance),
    count: sorted.length,
  };
}

/**
 * Generate a unique key for a checkpoint
 */
function getCheckpointKey(journeyId: string, checkpointId: string, platform: Platform): string {
  return `${journeyId}:${checkpointId}:${platform}`;
}

/**
 * Generate a unique key for a journey
 */
function getJourneyKey(journeyId: string, platform: Platform): string {
  return `${journeyId}:${platform}`;
}

// =============================================================================
// PERFORMANCE TRACKER CLASS
// =============================================================================

/**
 * Performance Tracker
 *
 * Manages performance baselines, detects regressions, and generates reports.
 */
export class PerformanceTracker {
  private baselinePath: string;
  private historyPath: string;
  private baseline: PerformanceBaseline | null = null;
  private history: PerformanceHistory | null = null;
  private currentRunMeasurements: PerformanceMeasurement[] = [];
  private currentRunId: string | null = null;
  private currentRunStart: string | null = null;

  constructor(options: { baselinePath?: string; historyPath?: string } = {}) {
    this.baselinePath = options.baselinePath ?? './data/performance-baseline.json';
    this.historyPath = options.historyPath ?? './data/performance-history.json';
  }

  /**
   * Initialize the tracker by loading baseline and history
   */
  async initialize(): Promise<void> {
    await this.loadBaseline();
    await this.loadHistory();
    logger.info(
      {
        hasBaseline: this.baseline !== null,
        historyCheckpoints: this.history
          ? Object.keys(this.history.checkpointHistory).length
          : 0,
      },
      'Performance tracker initialized'
    );
  }

  /**
   * Load baseline from file
   */
  private async loadBaseline(): Promise<void> {
    try {
      if (fs.existsSync(this.baselinePath)) {
        const content = fs.readFileSync(this.baselinePath, 'utf-8');
        this.baseline = JSON.parse(content) as PerformanceBaseline;
        logger.debug({ path: this.baselinePath }, 'Loaded performance baseline');
      } else {
        logger.info('No baseline file found, will create on first successful run');
      }
    } catch (error) {
      logger.error({ error, path: this.baselinePath }, 'Failed to load baseline');
    }
  }

  /**
   * Load history from file
   */
  private async loadHistory(): Promise<void> {
    try {
      if (fs.existsSync(this.historyPath)) {
        const content = fs.readFileSync(this.historyPath, 'utf-8');
        this.history = JSON.parse(content) as PerformanceHistory;
        logger.debug({ path: this.historyPath }, 'Loaded performance history');
      } else {
        this.history = {
          version: '1.0.0',
          checkpointHistory: {},
          journeyHistory: {},
        };
      }
    } catch (error) {
      logger.error({ error, path: this.historyPath }, 'Failed to load history');
      this.history = {
        version: '1.0.0',
        checkpointHistory: {},
        journeyHistory: {},
      };
    }
  }

  /**
   * Save baseline to file
   */
  async saveBaseline(): Promise<void> {
    if (!this.baseline) return;

    try {
      const dir = path.dirname(this.baselinePath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
      fs.writeFileSync(this.baselinePath, JSON.stringify(this.baseline, null, 2));
      logger.info({ path: this.baselinePath }, 'Saved performance baseline');
    } catch (error) {
      logger.error({ error, path: this.baselinePath }, 'Failed to save baseline');
    }
  }

  /**
   * Save history to file
   */
  async saveHistory(): Promise<void> {
    if (!this.history) return;

    try {
      const dir = path.dirname(this.historyPath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
      fs.writeFileSync(this.historyPath, JSON.stringify(this.history, null, 2));
      logger.debug({ path: this.historyPath }, 'Saved performance history');
    } catch (error) {
      logger.error({ error, path: this.historyPath }, 'Failed to save history');
    }
  }

  /**
   * Get hard threshold for a checkpoint from canonical spec
   */
  getHardThreshold(journeyId: string, checkpointId: string): number {
    // Find the journey and checkpoint in canonical specs
    const journey = SINGLE_DEVICE_JOURNEYS.find((j) => j.id === journeyId);
    if (journey) {
      for (const phase of journey.phases) {
        const checkpoint = phase.checkpoints.find((c) => c.id === checkpointId);
        if (checkpoint) {
          return checkpoint.maxDurationMs;
        }
      }
    }

    // Check constellation journeys
    const constellation = CONSTELLATION_JOURNEYS.find((j) => j.id === journeyId);
    if (constellation) {
      for (const phase of constellation.phases) {
        const checkpoint = phase.checkpoints.find((c) => c.id === checkpointId);
        if (checkpoint) {
          return checkpoint.maxDurationMs;
        }
      }
    }

    // Default fallback thresholds based on checkpoint naming conventions
    if (checkpointId.includes('LAUNCH') || checkpointId.includes('REACHED')) {
      return HARD_THRESHOLDS.APP_LAUNCH_MS;
    }
    if (checkpointId.includes('SCENE') || checkpointId.includes('ACTIVATED')) {
      return HARD_THRESHOLDS.SCENE_EXECUTION_MS;
    }
    if (checkpointId.includes('VOICE') || checkpointId.includes('COMMAND')) {
      return HARD_THRESHOLDS.VOICE_STREAMING_LATENCY_MS;
    }
    if (checkpointId.includes('EMERGENCY')) {
      return HARD_THRESHOLDS.EMERGENCY_BROADCAST_MS;
    }
    if (checkpointId.includes('DISCOVER') || checkpointId.includes('MDNS')) {
      return HARD_THRESHOLDS.MDNS_DISCOVERY_MS;
    }

    // Default to navigation transition
    return HARD_THRESHOLDS.NAVIGATION_TRANSITION_MS;
  }

  /**
   * Get baseline for a checkpoint
   */
  getCheckpointBaseline(
    journeyId: string,
    checkpointId: string,
    platform: Platform
  ): CheckpointBaseline | null {
    if (!this.baseline) return null;

    const journeyBaseline = this.baseline.journeyBaselines.find(
      (jb) => jb.journeyId === journeyId && jb.platform === platform
    );
    if (!journeyBaseline) return null;

    return (
      journeyBaseline.checkpointBaselines.find(
        (cb) => cb.checkpointId === checkpointId
      ) ?? null
    );
  }

  /**
   * Start a new performance tracking run
   */
  startRun(runId: string): void {
    this.currentRunId = runId;
    this.currentRunStart = new Date().toISOString();
    this.currentRunMeasurements = [];
    logger.debug({ runId }, 'Started performance tracking run');
  }

  /**
   * Record a checkpoint measurement
   */
  recordCheckpoint(
    journeyId: string,
    checkpointId: string,
    platform: Platform,
    durationMs: number
  ): PerformanceMeasurement {
    const hardThreshold = this.getHardThreshold(journeyId, checkpointId);
    const baseline = this.getCheckpointBaseline(journeyId, checkpointId, platform);

    const exceededHardThreshold = durationMs > hardThreshold;
    let isRegression = false;
    let baselineDiffPercent: number | null = null;

    if (baseline && baseline.baseline.count >= MIN_SAMPLE_SIZE) {
      const baselineP50 = baseline.baseline.p50;
      baselineDiffPercent = ((durationMs - baselineP50) / baselineP50) * 100;
      isRegression = baselineDiffPercent > REGRESSION_THRESHOLD_PERCENT;
    }

    const measurement: PerformanceMeasurement = {
      checkpointId,
      journeyId,
      platform,
      durationMs,
      timestamp: new Date().toISOString(),
      exceededHardThreshold,
      isRegression,
      baselineDiffPercent,
    };

    this.currentRunMeasurements.push(measurement);

    // Add to history
    this.addToHistory(journeyId, checkpointId, platform, durationMs, !exceededHardThreshold);

    if (exceededHardThreshold) {
      logger.warn(
        {
          checkpointId,
          journeyId,
          platform,
          durationMs,
          hardThreshold,
        },
        'Checkpoint exceeded hard threshold'
      );
    }

    if (isRegression) {
      logger.warn(
        {
          checkpointId,
          journeyId,
          platform,
          durationMs,
          baselineP50: baseline?.baseline.p50,
          diffPercent: baselineDiffPercent,
        },
        'Performance regression detected'
      );
    }

    return measurement;
  }

  /**
   * Add measurement to history
   */
  private addToHistory(
    journeyId: string,
    checkpointId: string,
    platform: Platform,
    durationMs: number,
    passed: boolean
  ): void {
    if (!this.history) {
      this.history = {
        version: '1.0.0',
        checkpointHistory: {},
        journeyHistory: {},
      };
    }

    const key = getCheckpointKey(journeyId, checkpointId, platform);
    if (!this.history.checkpointHistory[key]) {
      this.history.checkpointHistory[key] = [];
    }

    const entry: HistoricalEntry = {
      timestamp: new Date().toISOString(),
      durationMs,
      passed,
    };

    this.history.checkpointHistory[key]!.push(entry);

    // Trim to max entries
    if (this.history.checkpointHistory[key]!.length > MAX_HISTORY_ENTRIES) {
      this.history.checkpointHistory[key] = this.history.checkpointHistory[key]!.slice(
        -MAX_HISTORY_ENTRIES
      );
    }
  }

  /**
   * Complete a run and generate report
   */
  completeRun(
    journeyId: string,
    platform: Platform,
    totalDurationMs: number
  ): PerformanceReport {
    const journey =
      SINGLE_DEVICE_JOURNEYS.find((j) => j.id === journeyId) ??
      CONSTELLATION_JOURNEYS.find((j) => j.id === journeyId);

    const expectedDurationMs = journey?.expectedDurationMs ?? 30000;

    // Detect regressions
    const regressions: PerformanceRegression[] = [];
    for (const measurement of this.currentRunMeasurements) {
      if (measurement.isRegression || measurement.exceededHardThreshold) {
        const baseline = this.getCheckpointBaseline(
          journeyId,
          measurement.checkpointId,
          platform
        );
        const checkpointName = this.getCheckpointName(journeyId, measurement.checkpointId);

        const regression: PerformanceRegression = {
          checkpointId: measurement.checkpointId,
          checkpointName,
          journeyId,
          platform,
          currentDurationMs: measurement.durationMs,
          baselineP50Ms: baseline?.baseline.p50 ?? 0,
          hardThresholdMs: this.getHardThreshold(journeyId, measurement.checkpointId),
          percentSlower: measurement.baselineDiffPercent ?? 0,
          exceededHardThreshold: measurement.exceededHardThreshold,
          severity: measurement.exceededHardThreshold ? 'critical' : 'warning',
          timestamp: measurement.timestamp,
        };
        regressions.push(regression);
      }
    }

    // Calculate summary
    const checkpointsTotal = this.currentRunMeasurements.length;
    const checkpointsPassed = this.currentRunMeasurements.filter(
      (m) => !m.exceededHardThreshold
    ).length;
    const checkpointsExceededThreshold = this.currentRunMeasurements.filter(
      (m) => m.exceededHardThreshold
    ).length;
    const checkpointsRegressed = this.currentRunMeasurements.filter(
      (m) => m.isRegression
    ).length;

    const baselineDiffs = this.currentRunMeasurements
      .filter((m) => m.baselineDiffPercent !== null)
      .map((m) => m.baselineDiffPercent!);
    const avgDurationVsBaseline =
      baselineDiffs.length > 0
        ? baselineDiffs.reduce((a, b) => a + b, 0) / baselineDiffs.length
        : 0;

    // Calculate current percentiles
    const durations = this.currentRunMeasurements.map((m) => m.durationMs);
    const currentPercentiles = calculatePercentiles(durations);

    // Get baseline percentiles for comparison
    const journeyBaseline = this.baseline?.journeyBaselines.find(
      (jb) => jb.journeyId === journeyId && jb.platform === platform
    );
    const baselinePercentiles = journeyBaseline?.totalDurationBaseline ?? null;

    // Check if total duration regressed
    let totalDurationRegressed = false;
    if (baselinePercentiles && baselinePercentiles.count >= MIN_SAMPLE_SIZE) {
      const diffPercent =
        ((totalDurationMs - baselinePercentiles.p50) / baselinePercentiles.p50) * 100;
      totalDurationRegressed = diffPercent > REGRESSION_THRESHOLD_PERCENT;
    }

    const report: PerformanceReport = {
      runId: this.currentRunId ?? 'unknown',
      startedAt: this.currentRunStart ?? new Date().toISOString(),
      completedAt: new Date().toISOString(),
      journeyId,
      platform,
      passed: checkpointsExceededThreshold === 0,
      totalDurationMs,
      expectedDurationMs,
      totalDurationRegressed,
      measurements: [...this.currentRunMeasurements],
      regressions,
      summary: {
        checkpointsTotal,
        checkpointsPassed,
        checkpointsExceededThreshold,
        checkpointsRegressed,
        avgDurationVsBaseline,
      },
      comparison:
        durations.length > 0
          ? {
              currentPercentiles,
              baselinePercentiles,
            }
          : null,
    };

    // Add to journey history
    this.addJourneyToHistory(journeyId, platform, totalDurationMs, report.passed);

    // Reset for next run
    this.currentRunId = null;
    this.currentRunStart = null;
    this.currentRunMeasurements = [];

    logger.info(
      {
        runId: report.runId,
        journeyId,
        platform,
        passed: report.passed,
        regressionCount: regressions.length,
        totalDurationMs,
      },
      'Performance run completed'
    );

    return report;
  }

  /**
   * Add journey to history
   */
  private addJourneyToHistory(
    journeyId: string,
    platform: Platform,
    durationMs: number,
    passed: boolean
  ): void {
    if (!this.history) return;

    const key = getJourneyKey(journeyId, platform);
    if (!this.history.journeyHistory[key]) {
      this.history.journeyHistory[key] = [];
    }

    this.history.journeyHistory[key]!.push({
      timestamp: new Date().toISOString(),
      durationMs,
      passed,
    });

    // Trim to max entries
    if (this.history.journeyHistory[key]!.length > MAX_HISTORY_ENTRIES) {
      this.history.journeyHistory[key] = this.history.journeyHistory[key]!.slice(
        -MAX_HISTORY_ENTRIES
      );
    }
  }

  /**
   * Get checkpoint name from journey spec
   */
  private getCheckpointName(journeyId: string, checkpointId: string): string {
    const journey =
      SINGLE_DEVICE_JOURNEYS.find((j) => j.id === journeyId) ??
      CONSTELLATION_JOURNEYS.find((j) => j.id === journeyId);

    if (journey) {
      for (const phase of journey.phases) {
        const checkpoint = phase.checkpoints.find((c) => c.id === checkpointId);
        if (checkpoint) {
          return checkpoint.name;
        }
      }
    }

    return checkpointId;
  }

  /**
   * Generate baseline from historical data
   */
  async generateBaseline(options: { gitCommit?: string; gitBranch?: string } = {}): Promise<PerformanceBaseline> {
    if (!this.history) {
      throw new Error('No history data available to generate baseline');
    }

    const now = new Date().toISOString();
    const journeyBaselines: JourneyBaseline[] = [];

    // Group history by journey and platform
    const journeyKeys = new Set<string>();
    for (const key of Object.keys(this.history.journeyHistory)) {
      journeyKeys.add(key);
    }

    for (const journeyKey of journeyKeys) {
      const [journeyId, platform] = journeyKey.split(':') as [string, Platform];
      const journeyHistory = this.history.journeyHistory[journeyKey] ?? [];

      if (journeyHistory.length < MIN_SAMPLE_SIZE) {
        logger.debug(
          { journeyId, platform, count: journeyHistory.length },
          'Insufficient history for baseline'
        );
        continue;
      }

      const journey =
        SINGLE_DEVICE_JOURNEYS.find((j) => j.id === journeyId) ??
        CONSTELLATION_JOURNEYS.find((j) => j.id === journeyId);

      if (!journey) continue;

      // Calculate journey duration baseline
      const durations = journeyHistory.map((h) => h.durationMs);
      const totalDurationBaseline = calculatePercentiles(durations);

      // Build checkpoint baselines
      const checkpointBaselines: CheckpointBaseline[] = [];
      for (const phase of journey.phases) {
        for (const checkpoint of phase.checkpoints) {
          const cpKey = getCheckpointKey(journeyId, checkpoint.id, platform);
          const cpHistory = this.history.checkpointHistory[cpKey] ?? [];

          if (cpHistory.length < MIN_SAMPLE_SIZE) continue;

          const cpDurations = cpHistory.map((h) => h.durationMs);
          const cpBaseline = calculatePercentiles(cpDurations);

          checkpointBaselines.push({
            checkpointId: checkpoint.id,
            checkpointName: checkpoint.name,
            journeyId,
            platform,
            hardThresholdMs: checkpoint.maxDurationMs,
            baseline: cpBaseline,
            lastUpdated: now,
            sampleCount: cpHistory.length,
          });
        }
      }

      journeyBaselines.push({
        journeyId,
        journeyName: journey.name,
        platform,
        expectedDurationMs: journey.expectedDurationMs,
        totalDurationBaseline,
        checkpointBaselines,
        lastUpdated: now,
      });
    }

    const baseline: PerformanceBaseline = {
      version: '1.0.0',
      generatedAt: now,
      updatedAt: now,
      journeyBaselines,
    };

    // Only set optional fields if they have values
    if (options.gitCommit !== undefined) {
      baseline.gitCommit = options.gitCommit;
    }
    if (options.gitBranch !== undefined) {
      baseline.gitBranch = options.gitBranch;
    }

    this.baseline = baseline;

    await this.saveBaseline();

    logger.info(
      {
        journeyCount: journeyBaselines.length,
        checkpointCount: journeyBaselines.reduce(
          (sum, jb) => sum + jb.checkpointBaselines.length,
          0
        ),
      },
      'Generated performance baseline'
    );

    return baseline;
  }

  /**
   * Update baseline with new measurements (for CI improvements)
   */
  async updateBaseline(options: {
    onlyImproved?: boolean;
    gitCommit?: string;
  } = {}): Promise<void> {
    if (!this.baseline || !this.history) {
      logger.warn('Cannot update baseline: no existing baseline or history');
      return;
    }

    const now = new Date().toISOString();
    let updatedCount = 0;

    for (const journeyBaseline of this.baseline.journeyBaselines) {
      const journeyKey = getJourneyKey(journeyBaseline.journeyId, journeyBaseline.platform);
      const journeyHistory = this.history.journeyHistory[journeyKey] ?? [];

      if (journeyHistory.length < MIN_SAMPLE_SIZE) continue;

      // Recalculate journey baseline
      const durations = journeyHistory.map((h) => h.durationMs);
      const newBaseline = calculatePercentiles(durations);

      // Only update if improved (or if not restricted)
      if (
        !options.onlyImproved ||
        newBaseline.p50 < journeyBaseline.totalDurationBaseline.p50
      ) {
        journeyBaseline.totalDurationBaseline = newBaseline;
        journeyBaseline.lastUpdated = now;
        updatedCount++;
      }

      // Update checkpoint baselines
      for (const cpBaseline of journeyBaseline.checkpointBaselines) {
        const cpKey = getCheckpointKey(
          journeyBaseline.journeyId,
          cpBaseline.checkpointId,
          journeyBaseline.platform
        );
        const cpHistory = this.history.checkpointHistory[cpKey] ?? [];

        if (cpHistory.length < MIN_SAMPLE_SIZE) continue;

        const cpDurations = cpHistory.map((h) => h.durationMs);
        const newCpBaseline = calculatePercentiles(cpDurations);

        if (!options.onlyImproved || newCpBaseline.p50 < cpBaseline.baseline.p50) {
          cpBaseline.baseline = newCpBaseline;
          cpBaseline.sampleCount = cpHistory.length;
          cpBaseline.lastUpdated = now;
        }
      }
    }

    this.baseline.updatedAt = now;
    if (options.gitCommit) {
      this.baseline.gitCommit = options.gitCommit;
    }

    await this.saveBaseline();

    logger.info({ updatedCount }, 'Updated performance baseline');
  }

  /**
   * Get historical trend for a checkpoint
   */
  getCheckpointTrend(
    journeyId: string,
    checkpointId: string,
    platform: Platform,
    limit: number = 50
  ): HistoricalEntry[] {
    if (!this.history) return [];

    const key = getCheckpointKey(journeyId, checkpointId, platform);
    const history = this.history.checkpointHistory[key] ?? [];

    return history.slice(-limit);
  }

  /**
   * Get historical trend for a journey
   */
  getJourneyTrend(
    journeyId: string,
    platform: Platform,
    limit: number = 50
  ): HistoricalEntry[] {
    if (!this.history) return [];

    const key = getJourneyKey(journeyId, platform);
    const history = this.history.journeyHistory[key] ?? [];

    return history.slice(-limit);
  }

  /**
   * Format a performance report as human-readable text
   */
  formatReport(report: PerformanceReport): string {
    const lines: string[] = [];

    lines.push('='.repeat(60));
    lines.push('PERFORMANCE REPORT');
    lines.push('='.repeat(60));
    lines.push('');
    lines.push(`Run ID: ${report.runId}`);
    lines.push(`Journey: ${report.journeyId}`);
    lines.push(`Platform: ${report.platform}`);
    lines.push(`Status: ${report.passed ? 'PASSED' : 'FAILED'}`);
    lines.push('');
    lines.push(`Total Duration: ${report.totalDurationMs}ms (expected: ${report.expectedDurationMs}ms)`);
    if (report.totalDurationRegressed) {
      lines.push('  WARNING: Total duration regressed from baseline');
    }
    lines.push('');

    lines.push('-'.repeat(40));
    lines.push('SUMMARY');
    lines.push('-'.repeat(40));
    lines.push(`Checkpoints Total: ${report.summary.checkpointsTotal}`);
    lines.push(`Checkpoints Passed: ${report.summary.checkpointsPassed}`);
    lines.push(`Exceeded Threshold: ${report.summary.checkpointsExceededThreshold}`);
    lines.push(`Regressed: ${report.summary.checkpointsRegressed}`);
    lines.push(`Avg vs Baseline: ${report.summary.avgDurationVsBaseline.toFixed(1)}%`);
    lines.push('');

    if (report.comparison) {
      lines.push('-'.repeat(40));
      lines.push('PERCENTILES (current run)');
      lines.push('-'.repeat(40));
      const p = report.comparison.currentPercentiles;
      lines.push(`  p50: ${p.p50.toFixed(0)}ms`);
      lines.push(`  p95: ${p.p95.toFixed(0)}ms`);
      lines.push(`  p99: ${p.p99.toFixed(0)}ms`);
      lines.push(`  min: ${p.min.toFixed(0)}ms, max: ${p.max.toFixed(0)}ms`);
      lines.push('');

      if (report.comparison.baselinePercentiles) {
        lines.push('-'.repeat(40));
        lines.push('PERCENTILES (baseline)');
        lines.push('-'.repeat(40));
        const b = report.comparison.baselinePercentiles;
        lines.push(`  p50: ${b.p50.toFixed(0)}ms`);
        lines.push(`  p95: ${b.p95.toFixed(0)}ms`);
        lines.push(`  p99: ${b.p99.toFixed(0)}ms`);
        lines.push(`  samples: ${b.count}`);
        lines.push('');
      }
    }

    if (report.regressions.length > 0) {
      lines.push('-'.repeat(40));
      lines.push('REGRESSIONS');
      lines.push('-'.repeat(40));
      for (const reg of report.regressions) {
        const severity = reg.severity === 'critical' ? '[CRITICAL]' : '[WARNING]';
        lines.push(`${severity} ${reg.checkpointName}`);
        lines.push(`  Current: ${reg.currentDurationMs}ms`);
        lines.push(`  Baseline p50: ${reg.baselineP50Ms}ms`);
        lines.push(`  Hard Threshold: ${reg.hardThresholdMs}ms`);
        lines.push(`  Regression: +${reg.percentSlower.toFixed(1)}%`);
        lines.push('');
      }
    }

    lines.push('='.repeat(60));

    return lines.join('\n');
  }

  /**
   * Get the current baseline
   */
  getBaseline(): PerformanceBaseline | null {
    return this.baseline;
  }

  /**
   * Check if a baseline exists
   */
  hasBaseline(): boolean {
    return this.baseline !== null;
  }
}

// =============================================================================
// SINGLETON
// =============================================================================

let trackerInstance: PerformanceTracker | null = null;

/**
 * Get the global performance tracker instance
 */
export function getPerformanceTracker(
  options?: { baselinePath?: string; historyPath?: string }
): PerformanceTracker {
  if (!trackerInstance) {
    trackerInstance = new PerformanceTracker(options);
  }
  return trackerInstance;
}

/**
 * Reset the performance tracker (for testing)
 */
export function resetPerformanceTracker(): void {
  trackerInstance = null;
}
