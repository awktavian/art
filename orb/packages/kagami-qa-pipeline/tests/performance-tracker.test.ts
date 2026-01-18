/**
 * Performance Tracker Tests
 *
 * Tests for performance tracking, regression detection,
 * baseline management, and percentile calculations.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import {
  PerformanceTracker,
  resetPerformanceTracker,
  calculatePercentiles,
  HARD_THRESHOLDS,
  REGRESSION_THRESHOLD_PERCENT,
  MIN_SAMPLE_SIZE,
  PerformanceReport,
  PerformanceBaseline,
} from '../src/performance/index.js';

describe('PerformanceTracker', () => {
  const testDataDir = '/tmp/kagami-qa-test-performance';
  const baselinePath = path.join(testDataDir, 'baseline.json');
  const historyPath = path.join(testDataDir, 'history.json');

  beforeEach(() => {
    // Clean up before each test
    resetPerformanceTracker();
    if (fs.existsSync(testDataDir)) {
      fs.rmSync(testDataDir, { recursive: true });
    }
    fs.mkdirSync(testDataDir, { recursive: true });
  });

  afterEach(() => {
    // Clean up after each test
    resetPerformanceTracker();
    if (fs.existsSync(testDataDir)) {
      fs.rmSync(testDataDir, { recursive: true });
    }
  });

  describe('calculatePercentiles', () => {
    it('should calculate percentiles correctly for a simple array', () => {
      const data = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000];
      const result = calculatePercentiles(data);

      expect(result.count).toBe(10);
      expect(result.min).toBe(100);
      expect(result.max).toBe(1000);
      expect(result.mean).toBe(550);
      expect(result.p50).toBeCloseTo(550, 0);
      expect(result.p95).toBeGreaterThan(900);
      expect(result.p99).toBeGreaterThan(950);
    });

    it('should handle empty array', () => {
      const result = calculatePercentiles([]);

      expect(result.count).toBe(0);
      expect(result.min).toBe(0);
      expect(result.max).toBe(0);
      expect(result.mean).toBe(0);
      expect(result.p50).toBe(0);
    });

    it('should handle single element', () => {
      const result = calculatePercentiles([500]);

      expect(result.count).toBe(1);
      expect(result.min).toBe(500);
      expect(result.max).toBe(500);
      expect(result.mean).toBe(500);
      expect(result.p50).toBe(500);
    });

    it('should calculate standard deviation correctly', () => {
      // Array with known variance
      const data = [10, 20, 30, 40, 50];
      const result = calculatePercentiles(data);

      // Mean = 30, variance = 200, stdDev ~= 14.14
      expect(result.mean).toBe(30);
      expect(result.stdDev).toBeCloseTo(14.14, 1);
    });
  });

  describe('HARD_THRESHOLDS', () => {
    it('should have correct threshold values', () => {
      expect(HARD_THRESHOLDS.SCENE_EXECUTION_MS).toBe(500);
      expect(HARD_THRESHOLDS.DEVICE_CONTROL_MS).toBe(200);
      expect(HARD_THRESHOLDS.VOICE_STREAMING_LATENCY_MS).toBe(150);
      expect(HARD_THRESHOLDS.MDNS_DISCOVERY_MS).toBe(3000);
      expect(HARD_THRESHOLDS.MESH_SYNC_MS).toBe(2000);
      expect(HARD_THRESHOLDS.EMERGENCY_BROADCAST_MS).toBe(500);
      expect(HARD_THRESHOLDS.APP_LAUNCH_MS).toBe(3000);
      expect(HARD_THRESHOLDS.NAVIGATION_TRANSITION_MS).toBe(1000);
    });
  });

  describe('PerformanceTracker initialization', () => {
    it('should create tracker with default paths', () => {
      const tracker = new PerformanceTracker();
      expect(tracker).toBeDefined();
    });

    it('should create tracker with custom paths', () => {
      const tracker = new PerformanceTracker({
        baselinePath,
        historyPath,
      });
      expect(tracker).toBeDefined();
    });

    it('should not have baseline when none exists', async () => {
      const tracker = new PerformanceTracker({
        baselinePath,
        historyPath,
      });
      await tracker.initialize();
      expect(tracker.hasBaseline()).toBe(false);
    });
  });

  describe('getHardThreshold', () => {
    let tracker: PerformanceTracker;

    beforeEach(async () => {
      tracker = new PerformanceTracker({
        baselinePath,
        historyPath,
      });
      await tracker.initialize();
    });

    it('should return correct threshold from canonical journey spec', () => {
      // J01_MORNING_ROUTINE CP1_APP_LAUNCHED has maxDurationMs: 3000
      const threshold = tracker.getHardThreshold('J01_MORNING_ROUTINE', 'CP1_APP_LAUNCHED');
      expect(threshold).toBe(3000);
    });

    it('should return correct threshold for scene checkpoints', () => {
      // CP7_SCENE_ACTIVATED has maxDurationMs: 2000
      const threshold = tracker.getHardThreshold('J01_MORNING_ROUTINE', 'CP7_SCENE_ACTIVATED');
      expect(threshold).toBe(2000);
    });

    it('should return fallback threshold for unknown checkpoint', () => {
      const threshold = tracker.getHardThreshold('UNKNOWN_JOURNEY', 'UNKNOWN_CP');
      // Default fallback is NAVIGATION_TRANSITION_MS
      expect(threshold).toBe(HARD_THRESHOLDS.NAVIGATION_TRANSITION_MS);
    });
  });

  describe('recordCheckpoint', () => {
    let tracker: PerformanceTracker;

    beforeEach(async () => {
      tracker = new PerformanceTracker({
        baselinePath,
        historyPath,
      });
      await tracker.initialize();
      tracker.startRun('test-run-1');
    });

    it('should record checkpoint measurement', () => {
      const measurement = tracker.recordCheckpoint(
        'J01_MORNING_ROUTINE',
        'CP1_APP_LAUNCHED',
        'ios',
        1500
      );

      expect(measurement.checkpointId).toBe('CP1_APP_LAUNCHED');
      expect(measurement.journeyId).toBe('J01_MORNING_ROUTINE');
      expect(measurement.platform).toBe('ios');
      expect(measurement.durationMs).toBe(1500);
      expect(measurement.exceededHardThreshold).toBe(false); // 1500 < 3000
    });

    it('should detect hard threshold exceeded', () => {
      const measurement = tracker.recordCheckpoint(
        'J01_MORNING_ROUTINE',
        'CP1_APP_LAUNCHED',
        'ios',
        5000 // Exceeds 3000ms threshold
      );

      expect(measurement.exceededHardThreshold).toBe(true);
    });

    it('should have null baseline diff when no baseline exists', () => {
      const measurement = tracker.recordCheckpoint(
        'J01_MORNING_ROUTINE',
        'CP1_APP_LAUNCHED',
        'ios',
        1500
      );

      expect(measurement.baselineDiffPercent).toBeNull();
      expect(measurement.isRegression).toBe(false);
    });
  });

  describe('completeRun', () => {
    let tracker: PerformanceTracker;

    beforeEach(async () => {
      tracker = new PerformanceTracker({
        baselinePath,
        historyPath,
      });
      await tracker.initialize();
    });

    it('should generate performance report', () => {
      tracker.startRun('test-run-1');

      // Record some checkpoints
      tracker.recordCheckpoint('J01_MORNING_ROUTINE', 'CP1_APP_LAUNCHED', 'ios', 1500);
      tracker.recordCheckpoint('J01_MORNING_ROUTINE', 'CP2_HOME_REACHED', 'ios', 800);
      tracker.recordCheckpoint('J01_MORNING_ROUTINE', 'CP3_SAFETY_VISIBLE', 'ios', 500);

      const report = tracker.completeRun('J01_MORNING_ROUTINE', 'ios', 5000);

      expect(report.runId).toBe('test-run-1');
      expect(report.journeyId).toBe('J01_MORNING_ROUTINE');
      expect(report.platform).toBe('ios');
      expect(report.totalDurationMs).toBe(5000);
      expect(report.measurements).toHaveLength(3);
      expect(report.passed).toBe(true); // All within thresholds
    });

    it('should detect threshold exceeded in report', () => {
      tracker.startRun('test-run-2');

      // Exceed a threshold
      tracker.recordCheckpoint('J01_MORNING_ROUTINE', 'CP1_APP_LAUNCHED', 'ios', 5000); // >3000

      const report = tracker.completeRun('J01_MORNING_ROUTINE', 'ios', 6000);

      expect(report.passed).toBe(false);
      expect(report.summary.checkpointsExceededThreshold).toBe(1);
      expect(report.regressions).toHaveLength(1);
      expect(report.regressions[0]!.severity).toBe('critical');
    });

    it('should calculate summary statistics', () => {
      tracker.startRun('test-run-3');

      tracker.recordCheckpoint('J01_MORNING_ROUTINE', 'CP1_APP_LAUNCHED', 'ios', 1500);
      tracker.recordCheckpoint('J01_MORNING_ROUTINE', 'CP2_HOME_REACHED', 'ios', 800);
      tracker.recordCheckpoint('J01_MORNING_ROUTINE', 'CP3_SAFETY_VISIBLE', 'ios', 500);

      const report = tracker.completeRun('J01_MORNING_ROUTINE', 'ios', 5000);

      expect(report.summary.checkpointsTotal).toBe(3);
      expect(report.summary.checkpointsPassed).toBe(3);
      expect(report.summary.checkpointsExceededThreshold).toBe(0);
    });
  });

  describe('baseline generation', () => {
    let tracker: PerformanceTracker;

    beforeEach(async () => {
      tracker = new PerformanceTracker({
        baselinePath,
        historyPath,
      });
      await tracker.initialize();
    });

    it('should require minimum samples before generating baseline', async () => {
      // Record fewer samples than MIN_SAMPLE_SIZE
      for (let i = 0; i < MIN_SAMPLE_SIZE - 1; i++) {
        tracker.startRun(`run-${i}`);
        tracker.recordCheckpoint('J01_MORNING_ROUTINE', 'CP1_APP_LAUNCHED', 'ios', 1500);
        tracker.completeRun('J01_MORNING_ROUTINE', 'ios', 5000);
      }

      // Save history
      await tracker.saveHistory();

      // Try to generate baseline
      const baseline = await tracker.generateBaseline();

      // Should have empty or minimal baseline due to insufficient samples
      expect(baseline.journeyBaselines.length).toBe(0);
    });

    it('should generate baseline with sufficient samples', async () => {
      // Record enough samples
      for (let i = 0; i < MIN_SAMPLE_SIZE + 1; i++) {
        tracker.startRun(`run-${i}`);
        tracker.recordCheckpoint('J01_MORNING_ROUTINE', 'CP1_APP_LAUNCHED', 'ios', 1500 + i * 10);
        tracker.completeRun('J01_MORNING_ROUTINE', 'ios', 5000 + i * 10);
      }

      await tracker.saveHistory();

      const baseline = await tracker.generateBaseline();

      expect(baseline.version).toBe('1.0.0');
      expect(baseline.generatedAt).toBeDefined();
      expect(baseline.journeyBaselines.length).toBeGreaterThan(0);
    });

    it('should save and load baseline', async () => {
      // Record samples
      for (let i = 0; i < MIN_SAMPLE_SIZE + 1; i++) {
        tracker.startRun(`run-${i}`);
        tracker.recordCheckpoint('J01_MORNING_ROUTINE', 'CP1_APP_LAUNCHED', 'ios', 1500);
        tracker.completeRun('J01_MORNING_ROUTINE', 'ios', 5000);
      }

      await tracker.saveHistory();
      await tracker.generateBaseline();

      // Create new tracker and load baseline
      const tracker2 = new PerformanceTracker({
        baselinePath,
        historyPath,
      });
      await tracker2.initialize();

      expect(tracker2.hasBaseline()).toBe(true);
    });
  });

  describe('regression detection', () => {
    let tracker: PerformanceTracker;

    beforeEach(async () => {
      tracker = new PerformanceTracker({
        baselinePath,
        historyPath,
      });
      await tracker.initialize();

      // Create baseline with consistent performance
      for (let i = 0; i < MIN_SAMPLE_SIZE + 1; i++) {
        tracker.startRun(`baseline-run-${i}`);
        tracker.recordCheckpoint('J01_MORNING_ROUTINE', 'CP1_APP_LAUNCHED', 'ios', 1000);
        tracker.completeRun('J01_MORNING_ROUTINE', 'ios', 3000);
      }

      await tracker.saveHistory();
      await tracker.generateBaseline();
    });

    it('should detect regression when performance degrades >10%', () => {
      tracker.startRun('regression-run');

      // 1100ms is 10% slower than 1000ms baseline - should trigger regression
      // We need >10%, so let's use 1150ms (15% slower)
      const measurement = tracker.recordCheckpoint(
        'J01_MORNING_ROUTINE',
        'CP1_APP_LAUNCHED',
        'ios',
        1150
      );

      expect(measurement.isRegression).toBe(true);
      expect(measurement.baselineDiffPercent).toBeGreaterThan(REGRESSION_THRESHOLD_PERCENT);
    });

    it('should not flag regression when performance is within threshold', () => {
      tracker.startRun('normal-run');

      // 1050ms is 5% slower than 1000ms baseline - should not trigger regression
      const measurement = tracker.recordCheckpoint(
        'J01_MORNING_ROUTINE',
        'CP1_APP_LAUNCHED',
        'ios',
        1050
      );

      expect(measurement.isRegression).toBe(false);
      expect(measurement.baselineDiffPercent).toBeLessThanOrEqual(REGRESSION_THRESHOLD_PERCENT);
    });

    it('should not flag regression when performance improves', () => {
      tracker.startRun('improved-run');

      // 900ms is 10% faster than 1000ms baseline - definitely not a regression
      const measurement = tracker.recordCheckpoint(
        'J01_MORNING_ROUTINE',
        'CP1_APP_LAUNCHED',
        'ios',
        900
      );

      expect(measurement.isRegression).toBe(false);
      expect(measurement.baselineDiffPercent).toBeLessThan(0);
    });
  });

  describe('historical trends', () => {
    let tracker: PerformanceTracker;

    beforeEach(async () => {
      tracker = new PerformanceTracker({
        baselinePath,
        historyPath,
      });
      await tracker.initialize();
    });

    it('should return checkpoint trend data', () => {
      // Record several runs
      for (let i = 0; i < 10; i++) {
        tracker.startRun(`trend-run-${i}`);
        tracker.recordCheckpoint('J01_MORNING_ROUTINE', 'CP1_APP_LAUNCHED', 'ios', 1000 + i * 50);
        tracker.completeRun('J01_MORNING_ROUTINE', 'ios', 3000);
      }

      const trend = tracker.getCheckpointTrend(
        'J01_MORNING_ROUTINE',
        'CP1_APP_LAUNCHED',
        'ios',
        5
      );

      expect(trend.length).toBe(5);
      // Trends should be most recent entries
      expect(trend[trend.length - 1]!.durationMs).toBe(1450); // Last entry
    });

    it('should return journey trend data', () => {
      for (let i = 0; i < 10; i++) {
        tracker.startRun(`trend-run-${i}`);
        tracker.recordCheckpoint('J01_MORNING_ROUTINE', 'CP1_APP_LAUNCHED', 'ios', 1000);
        tracker.completeRun('J01_MORNING_ROUTINE', 'ios', 3000 + i * 100);
      }

      const trend = tracker.getJourneyTrend('J01_MORNING_ROUTINE', 'ios', 5);

      expect(trend.length).toBe(5);
    });

    it('should limit trend data to specified count', () => {
      for (let i = 0; i < 20; i++) {
        tracker.startRun(`trend-run-${i}`);
        tracker.recordCheckpoint('J01_MORNING_ROUTINE', 'CP1_APP_LAUNCHED', 'ios', 1000);
        tracker.completeRun('J01_MORNING_ROUTINE', 'ios', 3000);
      }

      const trend = tracker.getCheckpointTrend(
        'J01_MORNING_ROUTINE',
        'CP1_APP_LAUNCHED',
        'ios',
        10
      );

      expect(trend.length).toBe(10);
    });
  });

  describe('formatReport', () => {
    let tracker: PerformanceTracker;

    beforeEach(async () => {
      tracker = new PerformanceTracker({
        baselinePath,
        historyPath,
      });
      await tracker.initialize();
    });

    it('should format report as human-readable text', () => {
      tracker.startRun('format-test');
      tracker.recordCheckpoint('J01_MORNING_ROUTINE', 'CP1_APP_LAUNCHED', 'ios', 1500);
      tracker.recordCheckpoint('J01_MORNING_ROUTINE', 'CP2_HOME_REACHED', 'ios', 800);
      const report = tracker.completeRun('J01_MORNING_ROUTINE', 'ios', 5000);

      const formatted = tracker.formatReport(report);

      expect(formatted).toContain('PERFORMANCE REPORT');
      expect(formatted).toContain('J01_MORNING_ROUTINE');
      expect(formatted).toContain('ios');
      expect(formatted).toContain('PASSED');
      expect(formatted).toContain('SUMMARY');
    });

    it('should show regressions in formatted report', () => {
      tracker.startRun('regression-format-test');
      tracker.recordCheckpoint('J01_MORNING_ROUTINE', 'CP1_APP_LAUNCHED', 'ios', 5000); // Exceeds 3000
      const report = tracker.completeRun('J01_MORNING_ROUTINE', 'ios', 6000);

      const formatted = tracker.formatReport(report);

      expect(formatted).toContain('FAILED');
      expect(formatted).toContain('REGRESSIONS');
      expect(formatted).toContain('[CRITICAL]');
    });
  });

  describe('baseline update', () => {
    let tracker: PerformanceTracker;

    beforeEach(async () => {
      tracker = new PerformanceTracker({
        baselinePath,
        historyPath,
      });
      await tracker.initialize();

      // Create initial baseline
      for (let i = 0; i < MIN_SAMPLE_SIZE + 1; i++) {
        tracker.startRun(`init-run-${i}`);
        tracker.recordCheckpoint('J01_MORNING_ROUTINE', 'CP1_APP_LAUNCHED', 'ios', 1500);
        tracker.completeRun('J01_MORNING_ROUTINE', 'ios', 5000);
      }

      await tracker.saveHistory();
      await tracker.generateBaseline();
    });

    it('should update baseline with new measurements', async () => {
      // Add more measurements with better performance
      for (let i = 0; i < MIN_SAMPLE_SIZE + 1; i++) {
        tracker.startRun(`improved-run-${i}`);
        tracker.recordCheckpoint('J01_MORNING_ROUTINE', 'CP1_APP_LAUNCHED', 'ios', 1200);
        tracker.completeRun('J01_MORNING_ROUTINE', 'ios', 4000);
      }

      await tracker.saveHistory();

      // Update baseline
      await tracker.updateBaseline();

      // The baseline should be updated
      const baseline = tracker.getBaseline();
      expect(baseline).not.toBeNull();
    });

    it('should only update baseline when improved if onlyImproved is true', async () => {
      const baselineBefore = tracker.getBaseline();
      const originalP50 = baselineBefore?.journeyBaselines[0]?.totalDurationBaseline.p50;

      // Add worse measurements
      for (let i = 0; i < MIN_SAMPLE_SIZE + 1; i++) {
        tracker.startRun(`worse-run-${i}`);
        tracker.recordCheckpoint('J01_MORNING_ROUTINE', 'CP1_APP_LAUNCHED', 'ios', 2000);
        tracker.completeRun('J01_MORNING_ROUTINE', 'ios', 7000);
      }

      await tracker.saveHistory();
      await tracker.updateBaseline({ onlyImproved: true });

      const baselineAfter = tracker.getBaseline();
      const updatedP50 = baselineAfter?.journeyBaselines[0]?.totalDurationBaseline.p50;

      // With onlyImproved=true, baseline should not have gotten worse
      // It either stays the same or improves
      if (originalP50 !== undefined && updatedP50 !== undefined) {
        expect(updatedP50).toBeLessThanOrEqual(originalP50);
      }
    });
  });
});
