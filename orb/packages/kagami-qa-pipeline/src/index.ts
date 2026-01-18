/**
 * @fileoverview Kagami QA Pipeline - Main Entry Point
 *
 * A Gemini-powered video analysis pipeline for automated QA testing.
 *
 * This module exports all public APIs for programmatic usage:
 *
 * - VideoProcessor: Extract frames and segments from test videos
 * - GeminiAnalyzer: AI-powered frame analysis
 * - IssueTracker: SQLite storage for issues and analysis results
 * - PipelineRunner: Orchestrates the complete analysis workflow
 * - ApiServer: REST API and WebSocket server
 *
 * @example
 * ```typescript
 * import {
 *   getRunner,
 *   getAnalyzer,
 *   loadConfig,
 *   setConfig
 * } from '@kagami/qa-pipeline';
 *
 * // Configure
 * const config = loadConfig();
 * setConfig(config);
 *
 * // Run analysis
 * const runner = getRunner();
 * await runner.start();
 *
 * const result = await runner.runAnalysis({
 *   videoPath: './test-recording.mp4',
 *   config: {
 *     platform: 'ios',
 *     testName: 'Login Flow'
 *   }
 * });
 *
 * console.log(`Quality Score: ${result.qualityScore}/100`);
 * console.log(`Issues: ${result.issues.length}`);
 * ```
 *
 * @module @kagami/qa-pipeline
 */

// Types
export type {
  Platform,
  Severity,
  IssueCategory,
  DetectedIssue,
  AnalysisStatus,
  AnalysisConfig,
  AnalysisResult,
  ExtractedFrame,
  VideoSegment,
  QueuedJob,
  PipelineHealth,
  AnalyzeRequest,
  ListAnalysesQuery,
  ListIssuesQuery,
  WsEventType,
  WsMessage,
  IssueRecord,
  AnalysisRecord
} from './types.js';

// Schemas for validation
export {
  PlatformSchema,
  SeveritySchema,
  IssueCategorySchema,
  DetectedIssueSchema,
  AnalysisStatusSchema,
  AnalysisConfigSchema,
  AnalysisResultSchema,
  ExtractedFrameSchema,
  VideoSegmentSchema,
  QueuedJobSchema,
  PipelineHealthSchema,
  AnalyzeRequestSchema,
  ListAnalysesQuerySchema,
  ListIssuesQuerySchema,
  WsEventTypeSchema,
  WsMessageSchema
} from './types.js';

// Configuration
export {
  loadConfig,
  getConfig,
  setConfig,
  resetConfig
} from './config.js';
export type { Config } from './config.js';

// Logger
export {
  logger,
  createChildLogger,
  startTiming,
  logError
} from './logger.js';
export type { LogLevel } from './logger.js';

// Video Processor
export {
  VideoProcessor,
  getProcessor,
  resetProcessor
} from './processor.js';
export type {
  VideoMetadata,
  FrameExtractionOptions,
  SegmentOptions
} from './processor.js';

// Gemini Analyzer
export {
  GeminiAnalyzer,
  getAnalyzer,
  resetAnalyzer
} from './analyzer.js';
export type { AnalysisProgressCallback } from './analyzer.js';

// Issue Tracker
export {
  IssueTracker,
  getTracker,
  resetTracker
} from './tracker.js';
export type {
  IssueStats,
  AnalysisSummary
} from './tracker.js';

// Pipeline Runner
export {
  PipelineRunner,
  getRunner,
  resetRunner
} from './runner.js';
export type {
  PipelineEvents,
  RunAnalysisOptions
} from './runner.js';

// API Server
export {
  ApiServer,
  getServer,
  resetServer
} from './server.js';

// Constellation Orchestrator
export {
  ConstellationOrchestrator,
  SimulatedMDNS,
  ADBDriver,
  SimctlDriver,
  HubTCPDriver,
  DesktopWebSocketDriver,
  FIBONACCI_TIMEOUTS,
  getFibonacciTimeout,
} from './orchestrator/constellation-orchestrator.js';
export type {
  ConstellationJourneySpec,
  DeviceConnectionState,
  DiscoveredDevice,
  DeviceConnection,
  DeviceCommand,
  DeviceResponse,
  PhaseResult,
  CheckpointResult,
  ConstellationResult,
  MDNSServiceRecord,
  ConstellationOrchestratorOptions,
  DeviceDriver,
} from './orchestrator/constellation-orchestrator.js';

// Canonical Journeys
export {
  Platform as JourneyPlatform,
  PLATFORM_CAPABILITIES,
  JourneyId,
  SINGLE_DEVICE_JOURNEYS,
  CONSTELLATION_JOURNEYS,
  getJourneysForPlatform,
  getConstellationJourneysForPlatform,
  validateJourneyResult,
} from './journeys/canonical-journeys.js';
export type {
  PlatformCapabilities,
  Checkpoint,
  Phase,
  JourneySpec,
  ConstellationRole,
  ConstellationDevice,
} from './journeys/canonical-journeys.js';

// Gemini Video Analysis (Byzantine Quality Scoring)
export {
  GeminiAnalyzer as GeminiVideoAnalyzer,
  getGeminiAnalyzer,
  resetGeminiAnalyzer,
  analyzeJourneyVideo,
  analyzeJourneyVideoBatch,
} from './analysis/index.js';
export type {
  ByzantineScores,
  VideoAnalysisIssue,
  CheckpointAnalysis,
  AnalysisResult as VideoAnalysisResult,
  BatchAnalysisOptions,
  BatchAnalysisResult,
} from './analysis/index.js';

// Test Harness (Central Orchestration)
export {
  TestHarness,
  VideoRecorder,
  ResultCollector,
  DashboardPublisher,
  getTestHarness,
  resetTestHarness,
  QUALITY_DIMENSIONS,
  VIDEO_SETTINGS,
  DEFAULT_OUTPUT_DIR,
} from './harness/test-harness.js';
export type {
  RecordingState,
  VideoRecorderConfig,
  VideoRecording,
  CheckpointTimestamp,
  JourneyExecutionResult,
  PhaseExecutionResult,
  CheckpointExecutionResult,
  TestHarnessConfig,
  GeminiAnalysisHandoff,
  DashboardUpdate,
  TestSummary,
  QualityDimension,
} from './harness/test-harness.js';

// Dashboard Result Publisher (REST API + WebSocket Integration)
export {
  DashboardPublisher as DashboardResultPublisher,
  getPublisher,
  resetPublisher,
  publishTestResult,
  pushRealtimeUpdate,
  uploadVideo,
  formatPhaseResult,
  formatConstellationResult,
  formatAnalysisResult,
  calculateByzantineScores,
} from './publisher/index.js';
export type {
  TestEventType,
  ConnectionState,
  ByzantineScores as DashboardByzantineScores,
  VideoTimestamp,
  TestUpdateEvent,
  TestEventPayload,
  TestStartedPayload,
  CheckpointPassedPayload,
  CheckpointFailedPayload,
  TestCompletedPayload,
  AnalysisCompletePayload,
  ConstellationSyncPayload,
  TestResult,
  HistoricalResult,
  DashboardPublisherConfig,
} from './publisher/index.js';
