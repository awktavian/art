/**
 * @fileoverview Gemini Video Analysis Integration for Byzantine Quality Scoring
 *
 * This module provides deep video analysis capabilities using Google's Gemini 2.0 Flash
 * model for comprehensive quality assessment of recorded test sessions.
 *
 * Key capabilities:
 * - Upload and analyze complete test videos
 * - Analyze specific frames at checkpoint timestamps
 * - Byzantine quality scoring across 6 dimensions
 * - Per-checkpoint and journey-level analysis
 * - Batch analysis for multiple videos
 *
 * Byzantine Quality Dimensions:
 * - Technical: UI correctness, element presence, standards compliance
 * - Aesthetic: Visual harmony, spacing, color usage, typography
 * - Accessibility: Touch targets, contrast ratios, WCAG compliance
 * - Emotional: Interaction feel, feedback appropriateness, flow
 * - Polish: Animation smoothness, transitions, attention to detail
 * - Delight: Joy moments, surprise elements, memorable interactions
 *
 * @example
 * ```typescript
 * import { GeminiAnalyzer, analyzeJourneyVideo } from './analysis/gemini-analyzer.js';
 *
 * const analyzer = new GeminiAnalyzer();
 * const result = await analyzeJourneyVideo(
 *   './test-recording.mp4',
 *   J01_MORNING_ROUTINE,
 *   [0, 2.5, 5.0, 7.5, 10.0]
 * );
 *
 * console.log(`Overall Score: ${result.overallScore}/100`);
 * console.log(`Technical: ${result.byzantineScores.technical}/100`);
 * ```
 *
 * Colony: Crystal (e7) -- Verification & Polish
 * h(x) >= 0. Always.
 */

import {
  GoogleGenerativeAI,
  HarmCategory,
  HarmBlockThreshold,
  type Part,
  type GenerativeModel,
} from '@google/generative-ai';
import {
  GoogleAIFileManager,
  FileState,
  type FileMetadataResponse,
} from '@google/generative-ai/server';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { createChildLogger, startTiming, logError } from '../logger.js';
import type { JourneySpec } from '../journeys/canonical-journeys.js';

const log = createChildLogger({ component: 'gemini-video-analyzer' });

// =============================================================================
// TYPES
// =============================================================================

/**
 * Byzantine Quality Scores - the 6 dimensions of virtuoso quality
 * Each score is 0-100 where 90+ is required for shipping
 */
export interface ByzantineScores {
  /** Technical correctness - UI correct, elements present, standards met */
  technical: number;
  /** Aesthetic harmony - visual beauty, spacing, color, typography */
  aesthetic: number;
  /** Accessibility compliance - touch targets, contrast, WCAG */
  accessibility: number;
  /** Emotional resonance - interaction feel, feedback, flow */
  emotional: number;
  /** Polish and refinement - animations, transitions, details */
  polish: number;
  /** Delight factor - joy, surprise, memorable moments */
  delight: number;
}

/**
 * Issue detected during video analysis
 */
export interface VideoAnalysisIssue {
  /** Unique identifier */
  id: string;
  /** Timestamp in video where issue occurs (seconds) */
  timestamp: number;
  /** Frame number reference */
  frameNumber?: number;
  /** Which checkpoint this relates to */
  checkpointId?: string;
  /** Severity level */
  severity: 'critical' | 'warning' | 'info';
  /** Which Byzantine dimension is affected */
  dimension: keyof ByzantineScores;
  /** Human-readable description */
  description: string;
  /** UI element involved (if applicable) */
  element?: string;
  /** Specific fix recommendation */
  suggestedFix?: string;
  /** Confidence score 0-1 */
  confidence: number;
}

/**
 * Analysis result for a single checkpoint
 */
export interface CheckpointAnalysis {
  /** Checkpoint ID from journey spec */
  checkpointId: string;
  /** Checkpoint name */
  checkpointName: string;
  /** Timestamp in video */
  timestamp: number;
  /** Whether checkpoint requirements were met */
  passed: boolean;
  /** Byzantine scores for this checkpoint */
  scores: ByzantineScores;
  /** Required elements that were found */
  elementsFound: string[];
  /** Required elements that were missing */
  elementsMissing: string[];
  /** Issues specific to this checkpoint */
  issues: VideoAnalysisIssue[];
  /** Duration to reach this checkpoint from previous (ms) */
  durationFromPrevious?: number;
  /** Expected max duration (ms) */
  expectedMaxDuration?: number;
  /** Whether timing requirement was met */
  timingMet: boolean;
  /** Analysis notes */
  notes: string;
}

/**
 * Complete analysis result for a journey video
 */
export interface AnalysisResult {
  /** Unique analysis ID */
  id: string;
  /** Video file path */
  videoPath: string;
  /** Journey spec that was tested */
  journeyId: string;
  /** Journey name */
  journeyName: string;
  /** When analysis started */
  analyzedAt: string;
  /** Analysis duration in ms */
  analysisDurationMs: number;
  /** Video duration in seconds */
  videoDuration: number;
  /** Overall Byzantine scores (aggregate) */
  byzantineScores: ByzantineScores;
  /** Overall score (average of Byzantine dimensions) */
  overallScore: number;
  /** Whether journey meets quality bar (all dimensions >= 90) */
  meetsQualityBar: boolean;
  /** Per-checkpoint analysis */
  checkpointAnalyses: CheckpointAnalysis[];
  /** All issues found */
  issues: VideoAnalysisIssue[];
  /** Executive summary */
  summary: string;
  /** Specific improvement recommendations */
  recommendations: string[];
  /** Raw Gemini response for debugging */
  rawResponse?: string;
}

/**
 * Options for batch analysis
 */
export interface BatchAnalysisOptions {
  /** Maximum concurrent analyses */
  concurrency?: number;
  /** Progress callback */
  onProgress?: (completed: number, total: number, current: string) => void;
  /** Whether to continue on error */
  continueOnError?: boolean;
}

/**
 * Batch analysis result
 */
export interface BatchAnalysisResult {
  /** Results keyed by video path */
  results: Map<string, AnalysisResult>;
  /** Errors keyed by video path */
  errors: Map<string, Error>;
  /** Total analysis time */
  totalDurationMs: number;
}

// =============================================================================
// PROMPTS
// =============================================================================

/**
 * Generate the comprehensive Byzantine quality analysis prompt
 */
function generateByzantineAnalysisPrompt(
  journeySpec: JourneySpec,
  checkpointTimestamps: number[]
): string {
  const checkpointDescriptions = journeySpec.phases
    .flatMap((phase, phaseIdx) =>
      phase.checkpoints.map((cp, cpIdx) => {
        const timestamp = checkpointTimestamps[phaseIdx * 10 + cpIdx] ?? 'unknown';
        return `- **${cp.id}** (${cp.name}) at ~${timestamp}s: ${cp.description}
    Required elements: ${cp.requiredElements.join(', ')}
    Max duration: ${cp.maxDurationMs}ms`;
      })
    )
    .join('\n');

  return `You are a senior QA engineer and design critic performing a Byzantine Quality Audit on a recorded user journey test.

## Journey Being Tested
**${journeySpec.name}** (${journeySpec.id})
${journeySpec.description}

## Checkpoints to Verify
${checkpointDescriptions}

## Byzantine Quality Dimensions

You MUST score each of these 6 dimensions from 0-100. A score of 90+ is required for shipping.

### 1. Technical (0-100)
- Are all required UI elements present and correctly rendered?
- Do interactive elements respond correctly?
- Is data displayed accurately?
- Are there any bugs, crashes, or unexpected behaviors?
- Does the app follow platform conventions (iOS/Android guidelines)?

### 2. Aesthetic (0-100)
- Is there visual harmony and coherence?
- Is spacing consistent and following a grid system?
- Are colors used appropriately and consistently?
- Is typography clear and hierarchical?
- Does the UI feel polished and professional?
- Are Fibonacci timing ratios respected (89, 144, 233, 377, 610, 987ms)?

### 3. Accessibility (0-100)
- Are touch targets at least 44pt (iOS) or 48dp (Android)?
- Do contrast ratios meet WCAG AA (4.5:1 for text, 3:1 for large text)?
- Are focus indicators visible and clear?
- Is content readable at different text sizes?
- Would this work for users with visual impairments?

### 4. Emotional (0-100)
- Does the interaction feel right and natural?
- Is feedback appropriate and timely?
- Does the flow make sense from user's perspective?
- Would this frustrate or delight users?
- Is the experience intuitive or confusing?

### 5. Polish (0-100)
- Are animations smooth (60fps, no jank)?
- Do transitions feel natural (proper easing)?
- Are there any rough edges or unfinished details?
- Is loading handled gracefully?
- Are all edge cases considered?

### 6. Delight (0-100)
- Are there any moments of joy or surprise?
- Does the app feel alive and responsive?
- Would users want to show this to others?
- Are there thoughtful micro-interactions?
- Does using this app make the user smile?

## Output Format

Respond with ONLY valid JSON in this exact structure:

{
  "byzantineScores": {
    "technical": <0-100>,
    "aesthetic": <0-100>,
    "accessibility": <0-100>,
    "emotional": <0-100>,
    "polish": <0-100>,
    "delight": <0-100>
  },
  "checkpointAnalyses": [
    {
      "checkpointId": "<checkpoint ID>",
      "checkpointName": "<checkpoint name>",
      "timestamp": <seconds in video>,
      "passed": <true/false>,
      "scores": {
        "technical": <0-100>,
        "aesthetic": <0-100>,
        "accessibility": <0-100>,
        "emotional": <0-100>,
        "polish": <0-100>,
        "delight": <0-100>
      },
      "elementsFound": ["<element1>", "<element2>"],
      "elementsMissing": ["<element3>"],
      "timingMet": <true/false>,
      "notes": "<observations about this checkpoint>"
    }
  ],
  "issues": [
    {
      "timestamp": <seconds>,
      "frameNumber": <optional frame number>,
      "checkpointId": "<optional checkpoint ID>",
      "severity": "<critical|warning|info>",
      "dimension": "<technical|aesthetic|accessibility|emotional|polish|delight>",
      "description": "<clear description>",
      "element": "<UI element involved>",
      "suggestedFix": "<specific fix>",
      "confidence": <0-1>
    }
  ],
  "summary": "<executive summary of findings - 2-3 sentences>",
  "recommendations": [
    "<specific improvement 1>",
    "<specific improvement 2>"
  ],
  "videoDuration": <total video duration in seconds>
}

## Scoring Guidelines

- **90-100**: Exceptional, ready for ship
- **80-89**: Good, minor improvements needed
- **70-79**: Acceptable, notable issues to address
- **60-69**: Below standard, significant work required
- **Below 60**: Failing, major problems

## Severity Guidelines

- **critical**: Blocks user, crashes, data loss, major accessibility violation
- **warning**: Degrades experience, minor accessibility issues, visual glitches
- **info**: Polish suggestions, minor improvements

## Important Notes

1. Be thorough but avoid false positives
2. Reference specific timestamps when reporting issues
3. Consider the PLATFORM context (iOS vs Android conventions)
4. Score honestly - don't inflate scores
5. The quality bar is 90+ on ALL dimensions to ship
6. If something looks good, say so! Acknowledge strengths.`;
}

// =============================================================================
// GEMINI ANALYZER CLASS
// =============================================================================

/**
 * GeminiAnalyzer - Comprehensive video analysis for Byzantine quality scoring
 *
 * Uses Gemini 2.0 Flash model's native video understanding capabilities
 * to analyze recorded test sessions and score them across 6 quality dimensions.
 */
export class GeminiAnalyzer {
  private genAI: GoogleGenerativeAI;
  private fileManager: GoogleAIFileManager;
  private model: GenerativeModel;
  private apiKey: string;
  private requestCount = 0;
  private lastRequestTime = 0;
  private requestsThisMinute = 0;
  private minuteStart = Date.now();
  private readonly maxRequestsPerMinute: number;

  /**
   * Create a new GeminiAnalyzer
   *
   * @param apiKey - Gemini API key (defaults to GEMINI_API_KEY env var)
   * @param options - Configuration options
   */
  constructor(
    apiKey?: string,
    options: {
      model?: string;
      maxRequestsPerMinute?: number;
    } = {}
  ) {
    this.apiKey = apiKey ?? process.env['GEMINI_API_KEY'] ?? '';
    if (!this.apiKey) {
      throw new Error('GEMINI_API_KEY environment variable is required');
    }

    this.maxRequestsPerMinute = options.maxRequestsPerMinute ?? 10;

    this.genAI = new GoogleGenerativeAI(this.apiKey);
    this.fileManager = new GoogleAIFileManager(this.apiKey);

    // Use Gemini 2.0 Flash for video analysis
    const modelName = options.model ?? 'gemini-2.0-flash-exp';
    this.model = this.genAI.getGenerativeModel({
      model: modelName,
      generationConfig: {
        temperature: 0.1, // Low temperature for consistent scoring
        topP: 0.8,
        topK: 40,
        maxOutputTokens: 16384, // Large output for detailed analysis
      },
      safetySettings: [
        { category: HarmCategory.HARM_CATEGORY_HARASSMENT, threshold: HarmBlockThreshold.BLOCK_ONLY_HIGH },
        { category: HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold: HarmBlockThreshold.BLOCK_ONLY_HIGH },
        { category: HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold: HarmBlockThreshold.BLOCK_ONLY_HIGH },
        { category: HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold: HarmBlockThreshold.BLOCK_ONLY_HIGH },
      ],
    });

    log.info({ model: modelName }, 'Gemini video analyzer initialized');
  }

  /**
   * Upload a video file to Gemini for analysis
   *
   * @param videoPath - Path to video file
   * @returns File metadata from Gemini
   */
  async uploadVideo(videoPath: string): Promise<FileMetadataResponse> {
    const done = startTiming('upload-video');
    log.info({ videoPath }, 'Uploading video to Gemini');

    try {
      // Verify file exists
      await fs.access(videoPath);
      const stats = await fs.stat(videoPath);
      const fileSizeMB = stats.size / (1024 * 1024);

      log.debug({ videoPath, fileSizeMB: fileSizeMB.toFixed(2) }, 'Video file stats');

      // Determine MIME type from extension
      const ext = path.extname(videoPath).toLowerCase();
      const mimeTypeMap: Record<string, string> = {
        '.mp4': 'video/mp4',
        '.mov': 'video/quicktime',
        '.avi': 'video/x-msvideo',
        '.webm': 'video/webm',
        '.mkv': 'video/x-matroska',
        '.m4v': 'video/x-m4v',
      };
      const mimeType = mimeTypeMap[ext] ?? 'video/mp4';

      // Upload the file
      const uploadResult = await this.fileManager.uploadFile(videoPath, {
        mimeType,
        displayName: path.basename(videoPath),
      });

      // Wait for processing to complete
      let file = await this.fileManager.getFile(uploadResult.file.name);
      while (file.state === FileState.PROCESSING) {
        log.debug({ name: file.name, state: file.state }, 'Waiting for video processing');
        await this.sleep(5000);
        file = await this.fileManager.getFile(uploadResult.file.name);
      }

      if (file.state === FileState.FAILED) {
        throw new Error(`Video processing failed: ${file.name}`);
      }

      done();
      log.info(
        { name: file.name, uri: file.uri, state: file.state },
        'Video uploaded and processed'
      );

      return file;
    } catch (error) {
      logError(error, { videoPath });
      throw error;
    }
  }

  /**
   * Delete an uploaded video file from Gemini
   *
   * @param fileName - The file name from Gemini (files/xxx format)
   */
  async deleteVideo(fileName: string): Promise<void> {
    try {
      await this.fileManager.deleteFile(fileName);
      log.debug({ fileName }, 'Deleted video from Gemini');
    } catch (error) {
      log.warn({ fileName, error }, 'Failed to delete video from Gemini');
    }
  }

  /**
   * Analyze a journey video with Byzantine quality scoring
   *
   * @param videoPath - Path to the test video
   * @param journeySpec - Journey specification being tested
   * @param checkpointTimestamps - Timestamps where checkpoints should occur
   * @returns Complete analysis result
   */
  async analyzeJourney(
    videoPath: string,
    journeySpec: JourneySpec,
    checkpointTimestamps: number[]
  ): Promise<AnalysisResult> {
    const analysisId = randomUUID();
    const startTime = Date.now();
    const done = startTiming('analyze-journey');

    log.info(
      { analysisId, videoPath, journeyId: journeySpec.id, checkpoints: checkpointTimestamps.length },
      'Starting journey analysis'
    );

    let uploadedFile: FileMetadataResponse | null = null;

    try {
      // Rate limiting
      await this.waitForRateLimit();

      // Upload video
      uploadedFile = await this.uploadVideo(videoPath);

      // Generate analysis prompt
      const prompt = generateByzantineAnalysisPrompt(journeySpec, checkpointTimestamps);

      // Build content with video reference
      const content: Part[] = [
        {
          fileData: {
            mimeType: uploadedFile.mimeType,
            fileUri: uploadedFile.uri,
          },
        },
        { text: prompt },
      ];

      // Call Gemini
      log.debug({ analysisId }, 'Sending video to Gemini for analysis');
      const response = await this.callGeminiWithRetry(content);

      // Parse response
      const parsed = this.parseAnalysisResponse(response, journeySpec, checkpointTimestamps);

      const analysisDurationMs = Date.now() - startTime;
      done();

      // Build final result
      const result: AnalysisResult = {
        id: analysisId,
        videoPath,
        journeyId: journeySpec.id,
        journeyName: journeySpec.name,
        analyzedAt: new Date().toISOString(),
        analysisDurationMs,
        videoDuration: parsed.videoDuration,
        byzantineScores: parsed.byzantineScores,
        overallScore: this.calculateOverallScore(parsed.byzantineScores),
        meetsQualityBar: this.meetsQualityBar(parsed.byzantineScores),
        checkpointAnalyses: parsed.checkpointAnalyses,
        issues: parsed.issues.map((issue) => ({
          ...issue,
          id: randomUUID(),
        })),
        summary: parsed.summary,
        recommendations: parsed.recommendations,
        rawResponse: response,
      };

      log.info(
        {
          analysisId,
          overallScore: result.overallScore,
          meetsQualityBar: result.meetsQualityBar,
          issueCount: result.issues.length,
          analysisDurationMs,
        },
        'Journey analysis complete'
      );

      return result;
    } finally {
      // Clean up uploaded file
      if (uploadedFile) {
        await this.deleteVideo(uploadedFile.name);
      }
    }
  }

  /**
   * Analyze specific frames at checkpoint timestamps
   *
   * @param videoPath - Path to the test video
   * @param timestamps - Specific timestamps to analyze (seconds)
   * @param context - Optional context about what's being tested
   * @returns Analysis of each frame
   */
  async analyzeFramesAtTimestamps(
    videoPath: string,
    timestamps: number[],
    context?: string
  ): Promise<{
    frames: Array<{
      timestamp: number;
      scores: ByzantineScores;
      issues: VideoAnalysisIssue[];
      notes: string;
    }>;
    overallScores: ByzantineScores;
  }> {
    const done = startTiming('analyze-frames');

    let uploadedFile: FileMetadataResponse | null = null;

    try {
      await this.waitForRateLimit();

      uploadedFile = await this.uploadVideo(videoPath);

      const prompt = `Analyze the following specific timestamps in this video and score the UI quality at each moment.

Timestamps to analyze: ${timestamps.map((t) => `${t}s`).join(', ')}

${context ? `Context: ${context}` : ''}

For EACH timestamp, provide Byzantine quality scores (0-100) for:
- technical: UI correctness, elements present
- aesthetic: Visual harmony, spacing, colors
- accessibility: Touch targets, contrast
- emotional: Interaction feel, feedback
- polish: Animation smoothness, transitions
- delight: Joy, surprise moments

Output JSON format:
{
  "frames": [
    {
      "timestamp": <seconds>,
      "scores": { "technical": <0-100>, "aesthetic": <0-100>, ... },
      "issues": [{ "timestamp": <>, "severity": "<>", "dimension": "<>", "description": "<>", "confidence": <0-1> }],
      "notes": "<observations>"
    }
  ],
  "overallScores": { "technical": <0-100>, "aesthetic": <0-100>, ... }
}`;

      const content: Part[] = [
        {
          fileData: {
            mimeType: uploadedFile.mimeType,
            fileUri: uploadedFile.uri,
          },
        },
        { text: prompt },
      ];

      const response = await this.callGeminiWithRetry(content);
      const parsed = this.parseFrameAnalysisResponse(response);

      done();

      return parsed;
    } finally {
      if (uploadedFile) {
        await this.deleteVideo(uploadedFile.name);
      }
    }
  }

  /**
   * Batch analyze multiple videos
   *
   * @param videos - Array of { videoPath, journeySpec, timestamps }
   * @param options - Batch options
   * @returns Batch results
   */
  async analyzeBatch(
    videos: Array<{
      videoPath: string;
      journeySpec: JourneySpec;
      checkpointTimestamps: number[];
    }>,
    options: BatchAnalysisOptions = {}
  ): Promise<BatchAnalysisResult> {
    const { concurrency = 1, onProgress, continueOnError = true } = options;
    const startTime = Date.now();

    const results = new Map<string, AnalysisResult>();
    const errors = new Map<string, Error>();

    // Process in batches based on concurrency
    for (let i = 0; i < videos.length; i += concurrency) {
      const batch = videos.slice(i, i + concurrency);

      const batchPromises = batch.map(async ({ videoPath, journeySpec, checkpointTimestamps }) => {
        try {
          const result = await this.analyzeJourney(videoPath, journeySpec, checkpointTimestamps);
          results.set(videoPath, result);
          onProgress?.(results.size + errors.size, videos.length, videoPath);
        } catch (error) {
          if (continueOnError) {
            errors.set(videoPath, error as Error);
            log.error({ videoPath, error }, 'Batch analysis failed for video');
            onProgress?.(results.size + errors.size, videos.length, videoPath);
          } else {
            throw error;
          }
        }
      });

      await Promise.all(batchPromises);
    }

    return {
      results,
      errors,
      totalDurationMs: Date.now() - startTime,
    };
  }

  /**
   * Test API connectivity
   */
  async testConnection(): Promise<boolean> {
    try {
      const result = await this.model.generateContent('Reply with just: "connected"');
      const text = result.response.text();
      return text.toLowerCase().includes('connected');
    } catch (error) {
      logError(error, { action: 'test-connection' });
      return false;
    }
  }

  /**
   * Get API usage statistics
   */
  getUsageStats(): {
    totalRequests: number;
    requestsThisMinute: number;
    lastRequestTime: Date | null;
  } {
    return {
      totalRequests: this.requestCount,
      requestsThisMinute: this.requestsThisMinute,
      lastRequestTime: this.lastRequestTime ? new Date(this.lastRequestTime) : null,
    };
  }

  // =========================================================================
  // PRIVATE METHODS
  // =========================================================================

  /**
   * Call Gemini with automatic retry and backoff
   */
  private async callGeminiWithRetry(content: Part[], attempt = 1): Promise<string> {
    const maxRetries = 3;

    try {
      this.requestCount++;
      this.requestsThisMinute++;

      const result = await this.model.generateContent(content);
      const text = result.response.text();

      this.lastRequestTime = Date.now();
      return text;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      const isRateLimit = errorMessage.includes('429') || errorMessage.includes('quota');
      const isTemporary = errorMessage.includes('503') || errorMessage.includes('500');

      if ((isRateLimit || isTemporary) && attempt <= maxRetries) {
        const backoffMs = isRateLimit
          ? Math.min(1000 * Math.pow(2, attempt), 60000)
          : 1000 * attempt;

        log.warn({ attempt, backoffMs, isRateLimit }, 'Retrying Gemini request');
        await this.sleep(backoffMs);
        return this.callGeminiWithRetry(content, attempt + 1);
      }

      throw error;
    }
  }

  /**
   * Wait for rate limit if necessary
   */
  private async waitForRateLimit(): Promise<void> {
    // Reset counter if minute has passed
    if (Date.now() - this.minuteStart > 60000) {
      this.requestsThisMinute = 0;
      this.minuteStart = Date.now();
    }

    // Wait if at limit
    if (this.requestsThisMinute >= this.maxRequestsPerMinute) {
      const waitTime = 60000 - (Date.now() - this.minuteStart) + 100;
      log.debug({ waitTime }, 'Waiting for rate limit');
      await this.sleep(waitTime);
      this.requestsThisMinute = 0;
      this.minuteStart = Date.now();
    }

    // Minimum 100ms between requests
    const timeSinceLast = Date.now() - this.lastRequestTime;
    if (timeSinceLast < 100) {
      await this.sleep(100 - timeSinceLast);
    }
  }

  /**
   * Parse the analysis response from Gemini
   */
  private parseAnalysisResponse(
    rawResponse: string,
    journeySpec: JourneySpec,
    checkpointTimestamps: number[]
  ): {
    byzantineScores: ByzantineScores;
    checkpointAnalyses: CheckpointAnalysis[];
    issues: Omit<VideoAnalysisIssue, 'id'>[];
    summary: string;
    recommendations: string[];
    videoDuration: number;
  } {
    try {
      // Extract JSON from response
      let jsonStr = rawResponse.trim();
      const jsonMatch = jsonStr.match(/```(?:json)?\s*([\s\S]*?)```/);
      if (jsonMatch?.[1]) {
        jsonStr = jsonMatch[1].trim();
      }

      const parsed = JSON.parse(jsonStr);

      // Validate and normalize byzantine scores
      const byzantineScores = this.validateByzantineScores(parsed.byzantineScores);

      // Build checkpoint analyses
      const expectedCheckpoints = journeySpec.phases.flatMap((phase) => phase.checkpoints);
      const checkpointAnalyses: CheckpointAnalysis[] = (parsed.checkpointAnalyses ?? []).map(
        (cp: Record<string, unknown>, idx: number) => {
          const expectedCp = expectedCheckpoints[idx];
          return {
            checkpointId: String(cp['checkpointId'] ?? expectedCp?.id ?? `CP${idx}`),
            checkpointName: String(cp['checkpointName'] ?? expectedCp?.name ?? `Checkpoint ${idx}`),
            timestamp: Number(cp['timestamp']) || checkpointTimestamps[idx] || 0,
            passed: Boolean(cp['passed']),
            scores: this.validateByzantineScores(cp['scores'] as Record<string, number>),
            elementsFound: Array.isArray(cp['elementsFound']) ? cp['elementsFound'].map(String) : [],
            elementsMissing: Array.isArray(cp['elementsMissing']) ? cp['elementsMissing'].map(String) : [],
            timingMet: Boolean(cp['timingMet']),
            issues: [],
            notes: String(cp['notes'] ?? ''),
          };
        }
      );

      // Parse issues
      const issues: Omit<VideoAnalysisIssue, 'id'>[] = (parsed.issues ?? [])
        .filter((issue: Record<string, unknown>) => issue && typeof issue === 'object')
        .map((issue: Record<string, unknown>) => ({
          timestamp: Number(issue['timestamp']) || 0,
          frameNumber: issue['frameNumber'] ? Number(issue['frameNumber']) : undefined,
          checkpointId: issue['checkpointId'] ? String(issue['checkpointId']) : undefined,
          severity: this.validateSeverity(issue['severity']),
          dimension: this.validateDimension(issue['dimension']),
          description: String(issue['description'] ?? 'Unknown issue'),
          element: issue['element'] ? String(issue['element']) : undefined,
          suggestedFix: issue['suggestedFix'] ? String(issue['suggestedFix']) : undefined,
          confidence: Math.max(0, Math.min(1, Number(issue['confidence']) || 0.8)),
        }));

      // Assign issues to checkpoints
      for (const issue of issues) {
        if (issue.checkpointId) {
          const cp = checkpointAnalyses.find((c) => c.checkpointId === issue.checkpointId);
          if (cp) {
            cp.issues.push({ ...issue, id: randomUUID() });
          }
        }
      }

      return {
        byzantineScores,
        checkpointAnalyses,
        issues,
        summary: String(parsed.summary ?? 'Analysis complete'),
        recommendations: Array.isArray(parsed.recommendations)
          ? parsed.recommendations.map(String)
          : [],
        videoDuration: Number(parsed.videoDuration) || 0,
      };
    } catch (error) {
      log.error({ error, rawResponse: rawResponse.substring(0, 1000) }, 'Failed to parse response');

      // Return safe defaults
      return {
        byzantineScores: this.defaultByzantineScores(),
        checkpointAnalyses: [],
        issues: [],
        summary: 'Failed to parse analysis response',
        recommendations: ['Re-run analysis'],
        videoDuration: 0,
      };
    }
  }

  /**
   * Parse frame analysis response
   */
  private parseFrameAnalysisResponse(rawResponse: string): {
    frames: Array<{
      timestamp: number;
      scores: ByzantineScores;
      issues: VideoAnalysisIssue[];
      notes: string;
    }>;
    overallScores: ByzantineScores;
  } {
    try {
      let jsonStr = rawResponse.trim();
      const jsonMatch = jsonStr.match(/```(?:json)?\s*([\s\S]*?)```/);
      if (jsonMatch?.[1]) {
        jsonStr = jsonMatch[1].trim();
      }

      const parsed = JSON.parse(jsonStr);

      const frames = (parsed.frames ?? []).map((frame: Record<string, unknown>) => ({
        timestamp: Number(frame['timestamp']) || 0,
        scores: this.validateByzantineScores(frame['scores'] as Record<string, number>),
        issues: (Array.isArray(frame['issues']) ? frame['issues'] : []).map(
          (issue: Record<string, unknown>) => ({
            id: randomUUID(),
            timestamp: Number(issue['timestamp']) || 0,
            severity: this.validateSeverity(issue['severity']),
            dimension: this.validateDimension(issue['dimension']),
            description: String(issue['description'] ?? ''),
            confidence: Number(issue['confidence']) || 0.8,
          })
        ),
        notes: String(frame['notes'] ?? ''),
      }));

      return {
        frames,
        overallScores: this.validateByzantineScores(parsed.overallScores),
      };
    } catch (error) {
      log.error({ error }, 'Failed to parse frame analysis response');
      return {
        frames: [],
        overallScores: this.defaultByzantineScores(),
      };
    }
  }

  /**
   * Validate and normalize byzantine scores
   */
  private validateByzantineScores(scores: Record<string, number> | undefined): ByzantineScores {
    const defaults = this.defaultByzantineScores();
    if (!scores || typeof scores !== 'object') return defaults;

    return {
      technical: this.clampScore(scores['technical'] ?? defaults.technical),
      aesthetic: this.clampScore(scores['aesthetic'] ?? defaults.aesthetic),
      accessibility: this.clampScore(scores['accessibility'] ?? defaults.accessibility),
      emotional: this.clampScore(scores['emotional'] ?? defaults.emotional),
      polish: this.clampScore(scores['polish'] ?? defaults.polish),
      delight: this.clampScore(scores['delight'] ?? defaults.delight),
    };
  }

  /**
   * Default byzantine scores (50 = needs review)
   */
  private defaultByzantineScores(): ByzantineScores {
    return {
      technical: 50,
      aesthetic: 50,
      accessibility: 50,
      emotional: 50,
      polish: 50,
      delight: 50,
    };
  }

  /**
   * Clamp score to 0-100 range
   */
  private clampScore(value: unknown): number {
    const num = Number(value);
    if (isNaN(num)) return 50;
    return Math.max(0, Math.min(100, num));
  }

  /**
   * Validate severity value
   */
  private validateSeverity(value: unknown): 'critical' | 'warning' | 'info' {
    if (value === 'critical' || value === 'warning' || value === 'info') {
      return value;
    }
    return 'info';
  }

  /**
   * Validate dimension value
   */
  private validateDimension(value: unknown): keyof ByzantineScores {
    const valid: Array<keyof ByzantineScores> = [
      'technical',
      'aesthetic',
      'accessibility',
      'emotional',
      'polish',
      'delight',
    ];
    if (valid.includes(value as keyof ByzantineScores)) {
      return value as keyof ByzantineScores;
    }
    return 'technical';
  }

  /**
   * Calculate overall score from byzantine dimensions
   */
  private calculateOverallScore(scores: ByzantineScores): number {
    const values = Object.values(scores);
    const sum = values.reduce((a, b) => a + b, 0);
    return Math.round(sum / values.length);
  }

  /**
   * Check if scores meet quality bar (all dimensions >= 90)
   */
  private meetsQualityBar(scores: ByzantineScores): boolean {
    return Object.values(scores).every((score) => score >= 90);
  }

  /**
   * Sleep utility
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

// =============================================================================
// CONVENIENCE FUNCTIONS
// =============================================================================

/**
 * Singleton analyzer instance
 */
let analyzerInstance: GeminiAnalyzer | null = null;

/**
 * Get the shared GeminiAnalyzer instance
 */
export function getGeminiAnalyzer(): GeminiAnalyzer {
  if (!analyzerInstance) {
    analyzerInstance = new GeminiAnalyzer();
  }
  return analyzerInstance;
}

/**
 * Reset the analyzer instance (for testing)
 */
export function resetGeminiAnalyzer(): void {
  analyzerInstance = null;
}

/**
 * Analyze a journey video with Byzantine quality scoring
 *
 * Convenience function that creates/uses the singleton analyzer.
 *
 * @param videoPath - Path to the test video
 * @param journeySpec - Journey specification being tested
 * @param checkpointTimestamps - Timestamps where checkpoints should occur (seconds)
 * @returns Complete analysis result with Byzantine scores
 *
 * @example
 * ```typescript
 * import { analyzeJourneyVideo, J01_MORNING_ROUTINE } from '@kagami/qa-pipeline';
 *
 * const result = await analyzeJourneyVideo(
 *   './recording.mp4',
 *   J01_MORNING_ROUTINE,
 *   [0, 3, 5, 8, 12, 15, 18, 22, 25, 28]
 * );
 *
 * if (result.meetsQualityBar) {
 *   console.log('Ready to ship!');
 * } else {
 *   console.log('Issues to fix:', result.issues);
 * }
 * ```
 */
export async function analyzeJourneyVideo(
  videoPath: string,
  journeySpec: JourneySpec,
  checkpointTimestamps: number[]
): Promise<AnalysisResult> {
  const analyzer = getGeminiAnalyzer();
  return analyzer.analyzeJourney(videoPath, journeySpec, checkpointTimestamps);
}

/**
 * Batch analyze multiple journey videos
 *
 * @param videos - Array of video analysis requests
 * @param options - Batch options (concurrency, progress callback, etc.)
 * @returns Results and any errors
 */
export async function analyzeJourneyVideoBatch(
  videos: Array<{
    videoPath: string;
    journeySpec: JourneySpec;
    checkpointTimestamps: number[];
  }>,
  options?: BatchAnalysisOptions
): Promise<BatchAnalysisResult> {
  const analyzer = getGeminiAnalyzer();
  return analyzer.analyzeBatch(videos, options);
}
