/**
 * @fileoverview Core type definitions for the QA Pipeline
 *
 * This module defines all the shared types used throughout the pipeline,
 * ensuring type safety and consistency across components.
 */

import { z } from 'zod';

// ============================================================================
// Platform Types
// ============================================================================

/**
 * Supported platforms for QA analysis
 */
export const PlatformSchema = z.enum([
  'ios',
  'android',
  'watchos',
  'tvos',
  'visionos',
  'desktop',
  'web'
]);

export type Platform = z.infer<typeof PlatformSchema>;

// ============================================================================
// Issue Types
// ============================================================================

/**
 * Severity levels for detected issues
 */
export const SeveritySchema = z.enum(['critical', 'warning', 'info']);
export type Severity = z.infer<typeof SeveritySchema>;

/**
 * Categories of issues that can be detected
 */
export const IssueCategorySchema = z.enum([
  'ui_consistency',
  'accessibility',
  'animation',
  'layout',
  'state',
  'error',
  'performance',
  'other'
]);
export type IssueCategory = z.infer<typeof IssueCategorySchema>;

/**
 * A single issue detected during video analysis
 */
export const DetectedIssueSchema = z.object({
  /** Unique identifier for this issue */
  id: z.string().uuid(),
  /** Timestamp in the video where the issue occurs (seconds) */
  timestamp: z.number().nonnegative(),
  /** Severity level of the issue */
  severity: SeveritySchema,
  /** Category of the issue */
  category: IssueCategorySchema,
  /** Human-readable description of the issue */
  description: z.string(),
  /** Path to the extracted frame showing the issue */
  framePath: z.string().optional(),
  /** Base64-encoded frame data (for API responses) */
  frameData: z.string().optional(),
  /** AI-suggested fix for the issue */
  suggestedFix: z.string().optional(),
  /** Confidence score from the AI (0-1) */
  confidence: z.number().min(0).max(1),
  /** Additional context or metadata */
  metadata: z.record(z.unknown()).optional()
});

export type DetectedIssue = z.infer<typeof DetectedIssueSchema>;

// ============================================================================
// Analysis Types
// ============================================================================

/**
 * Status of an analysis job
 */
export const AnalysisStatusSchema = z.enum([
  'pending',
  'processing',
  'analyzing',
  'completed',
  'failed',
  'cancelled'
]);
export type AnalysisStatus = z.infer<typeof AnalysisStatusSchema>;

/**
 * Configuration for a single analysis run
 */
export const AnalysisConfigSchema = z.object({
  /** Platform being tested */
  platform: PlatformSchema,
  /** Test name or identifier */
  testName: z.string(),
  /** Optional test suite name */
  testSuite: z.string().optional(),
  /** Frame extraction interval in seconds */
  frameInterval: z.number().positive().default(1),
  /** Maximum frames to extract */
  maxFrames: z.number().positive().default(100),
  /** Custom prompts to include in analysis */
  customPrompts: z.array(z.string()).optional(),
  /** Known issues to exclude from results */
  excludeKnownIssues: z.boolean().default(false)
});

export type AnalysisConfig = z.infer<typeof AnalysisConfigSchema>;

/**
 * Result of a complete video analysis
 */
export const AnalysisResultSchema = z.object({
  /** Unique identifier for this analysis */
  id: z.string().uuid(),
  /** Path to the analyzed video */
  videoPath: z.string(),
  /** Analysis configuration used */
  config: AnalysisConfigSchema,
  /** Current status of the analysis */
  status: AnalysisStatusSchema,
  /** When the analysis was created */
  createdAt: z.string().datetime(),
  /** When the analysis started processing */
  startedAt: z.string().datetime().optional(),
  /** When the analysis completed */
  completedAt: z.string().datetime().optional(),
  /** Duration of the analysis in milliseconds */
  durationMs: z.number().nonnegative().optional(),
  /** Video duration in seconds */
  videoDuration: z.number().nonnegative().optional(),
  /** Number of frames analyzed */
  framesAnalyzed: z.number().nonnegative().default(0),
  /** Issues detected during analysis */
  issues: z.array(DetectedIssueSchema).default([]),
  /** Overall quality score (0-100) */
  qualityScore: z.number().min(0).max(100).optional(),
  /** Error message if analysis failed */
  error: z.string().optional(),
  /** Raw AI response for debugging */
  rawResponse: z.string().optional()
});

export type AnalysisResult = z.infer<typeof AnalysisResultSchema>;

// ============================================================================
// Frame Types
// ============================================================================

/**
 * Extracted video frame metadata
 */
export const ExtractedFrameSchema = z.object({
  /** Frame index in the video */
  index: z.number().nonnegative(),
  /** Timestamp in the video (seconds) */
  timestamp: z.number().nonnegative(),
  /** Path to the extracted frame image */
  path: z.string(),
  /** Frame width in pixels */
  width: z.number().positive(),
  /** Frame height in pixels */
  height: z.number().positive(),
  /** File size in bytes */
  size: z.number().positive()
});

export type ExtractedFrame = z.infer<typeof ExtractedFrameSchema>;

/**
 * Video segment prepared for analysis
 */
export const VideoSegmentSchema = z.object({
  /** Start timestamp in seconds */
  startTime: z.number().nonnegative(),
  /** End timestamp in seconds */
  endTime: z.number().nonnegative(),
  /** Path to the segment video file */
  path: z.string(),
  /** Frames extracted from this segment */
  frames: z.array(ExtractedFrameSchema)
});

export type VideoSegment = z.infer<typeof VideoSegmentSchema>;

// ============================================================================
// Pipeline Types
// ============================================================================

/**
 * Job queued for processing
 */
export const QueuedJobSchema = z.object({
  /** Unique job identifier */
  id: z.string().uuid(),
  /** Path to the video file */
  videoPath: z.string(),
  /** Analysis configuration */
  config: AnalysisConfigSchema,
  /** Priority (higher = more urgent) */
  priority: z.number().int().default(0),
  /** When the job was queued */
  queuedAt: z.string().datetime(),
  /** Number of retry attempts */
  retries: z.number().int().nonnegative().default(0),
  /** Maximum retry attempts */
  maxRetries: z.number().int().nonnegative().default(3)
});

export type QueuedJob = z.infer<typeof QueuedJobSchema>;

/**
 * Pipeline health status
 */
export const PipelineHealthSchema = z.object({
  /** Whether the pipeline is operational */
  healthy: z.boolean(),
  /** Current queue depth */
  queueDepth: z.number().nonnegative(),
  /** Jobs currently processing */
  activeJobs: z.number().nonnegative(),
  /** Total jobs completed */
  completedJobs: z.number().nonnegative(),
  /** Total jobs failed */
  failedJobs: z.number().nonnegative(),
  /** Gemini API status */
  geminiStatus: z.enum(['connected', 'rate_limited', 'error', 'unknown']),
  /** Storage status - available (>10GB), low (1-10GB), full (<1GB), error, unknown */
  storageStatus: z.enum(['available', 'low', 'full', 'error', 'unknown']),
  /** Last check timestamp */
  lastCheck: z.string().datetime(),
  /** Uptime in milliseconds */
  uptimeMs: z.number().nonnegative()
});

export type PipelineHealth = z.infer<typeof PipelineHealthSchema>;

// ============================================================================
// API Types
// ============================================================================

/**
 * Request to queue a video for analysis
 */
export const AnalyzeRequestSchema = z.object({
  /** Path to video file or URL */
  videoPath: z.string(),
  /** Analysis configuration */
  config: AnalysisConfigSchema.partial().extend({
    platform: PlatformSchema
  }),
  /** Priority for the job */
  priority: z.number().int().optional()
});

export type AnalyzeRequest = z.infer<typeof AnalyzeRequestSchema>;

/**
 * Query parameters for listing analyses
 */
export const ListAnalysesQuerySchema = z.object({
  /** Filter by status */
  status: AnalysisStatusSchema.optional(),
  /** Filter by platform */
  platform: PlatformSchema.optional(),
  /** Filter by test name */
  testName: z.string().optional(),
  /** Pagination offset */
  offset: z.coerce.number().int().nonnegative().default(0),
  /** Pagination limit */
  limit: z.coerce.number().int().positive().max(100).default(20),
  /** Sort field */
  sortBy: z.enum(['createdAt', 'qualityScore', 'issueCount']).default('createdAt'),
  /** Sort direction */
  sortDir: z.enum(['asc', 'desc']).default('desc')
});

export type ListAnalysesQuery = z.infer<typeof ListAnalysesQuerySchema>;

/**
 * Query parameters for listing issues
 */
export const ListIssuesQuerySchema = z.object({
  /** Filter by analysis ID */
  analysisId: z.string().uuid().optional(),
  /** Filter by severity */
  severity: SeveritySchema.optional(),
  /** Filter by category */
  category: IssueCategorySchema.optional(),
  /** Filter by platform */
  platform: PlatformSchema.optional(),
  /** Only show issues from analyses after this date */
  since: z.string().datetime().optional(),
  /** Pagination offset */
  offset: z.coerce.number().int().nonnegative().default(0),
  /** Pagination limit */
  limit: z.coerce.number().int().positive().max(100).default(50)
});

export type ListIssuesQuery = z.infer<typeof ListIssuesQuerySchema>;

// ============================================================================
// WebSocket Types
// ============================================================================

/**
 * WebSocket event types
 */
export const WsEventTypeSchema = z.enum([
  'analysis:queued',
  'analysis:started',
  'analysis:progress',
  'analysis:completed',
  'analysis:failed',
  'issue:detected',
  'pipeline:health'
]);

export type WsEventType = z.infer<typeof WsEventTypeSchema>;

/**
 * WebSocket message structure
 */
export const WsMessageSchema = z.object({
  /** Event type */
  type: WsEventTypeSchema,
  /** Event payload */
  payload: z.unknown(),
  /** Timestamp */
  timestamp: z.string().datetime()
});

export type WsMessage = z.infer<typeof WsMessageSchema>;

// ============================================================================
// Database Types
// ============================================================================

/**
 * Issue record as stored in database
 */
export interface IssueRecord {
  id: string;
  analysis_id: string;
  timestamp: number;
  severity: Severity;
  category: IssueCategory;
  description: string;
  frame_path: string | null;
  suggested_fix: string | null;
  confidence: number;
  metadata: string | null;
  created_at: string;
  is_known: number;
  first_seen_at: string;
  last_seen_at: string;
  occurrence_count: number;
}

/**
 * Analysis record as stored in database
 */
export interface AnalysisRecord {
  id: string;
  video_path: string;
  platform: Platform;
  test_name: string;
  test_suite: string | null;
  status: AnalysisStatus;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  video_duration: number | null;
  frames_analyzed: number;
  quality_score: number | null;
  error: string | null;
  config: string;
  raw_response: string | null;
}
