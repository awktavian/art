/**
 * @fileoverview Gemini Analyzer - AI-powered video analysis for QA
 *
 * This module interfaces with Google's Gemini Pro Vision API to analyze
 * video frames and detect quality issues. It uses structured prompts
 * tailored for different platforms and issue categories.
 *
 * Key capabilities:
 * - Multi-frame analysis with context
 * - Platform-specific QA checks
 * - Structured JSON output parsing
 * - Automatic retry with exponential backoff
 */

import { GoogleGenerativeAI, HarmCategory, HarmBlockThreshold } from '@google/generative-ai';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { createChildLogger, startTiming, logError } from './logger.js';
import { getConfig } from './config.js';
import type {
  Platform,
  DetectedIssue,
  ExtractedFrame,
  Severity,
  IssueCategory,
  AnalysisConfig
} from './types.js';

const log = createChildLogger({ component: 'analyzer' });

/**
 * Gemini analysis response structure
 */
interface GeminiAnalysisResponse {
  issues: Array<{
    timestamp: number;
    severity: Severity;
    category: IssueCategory;
    description: string;
    suggestedFix?: string;
    confidence: number;
    frameIndex?: number;
  }>;
  qualityScore: number;
  summary: string;
}

/**
 * Analysis progress callback
 */
export type AnalysisProgressCallback = (progress: {
  phase: 'preparing' | 'analyzing' | 'parsing';
  framesProcessed?: number;
  totalFrames?: number;
  message?: string;
}) => void;

/**
 * Generate the QA analysis prompt for Gemini
 */
function generateAnalysisPrompt(platform: Platform, customPrompts?: string[]): string {
  const basePrompt = `You are a senior QA engineer analyzing a user journey test video for the ${platform.toUpperCase()} app.

Your task is to identify any quality issues in the UI and user experience. Analyze each frame carefully.

## Check for these issue categories:

1. **UI Consistency** (ui_consistency)
   - Are colony colors correct and consistent with the design system?
   - Is the Fibonacci timing respected for animations (89, 144, 233, 377, 610, 987ms)?
   - Are UI elements consistent with the platform's design guidelines?
   - Are fonts, colors, and spacing uniform throughout?

2. **Accessibility** (accessibility)
   - Are contrast ratios WCAG AA compliant (4.5:1 for text, 3:1 for large text)?
   - Are touch targets at least 44x44 points on iOS or 48x48dp on Android?
   - Are focus indicators visible and clear?
   - Is there proper support for dynamic type / text scaling?

3. **Animation Smoothness** (animation)
   - Any janky or stuttering transitions?
   - Are there frame drops visible?
   - Do animations feel natural (proper easing)?
   - Are there any frozen or stuck animations?

4. **Layout Issues** (layout)
   - Any overlapping elements?
   - Truncated or clipped text?
   - Misaligned components?
   - Improper spacing or margins?
   - Content extending beyond safe areas?

5. **State Correctness** (state)
   - Does the UI reflect the expected state at each checkpoint?
   - Are loading states properly shown and dismissed?
   - Are empty states handled gracefully?
   - Are error states recoverable?

6. **Error States** (error)
   - Any unexpected error messages?
   - Unhandled exceptions visible in UI?
   - Infinite loading states?
   - Broken images or missing assets?

7. **Performance** (performance)
   - Slow response times visible in UI?
   - Memory warning indicators?
   - Battery usage warnings?

## Output Format

Respond with ONLY valid JSON in this exact structure:

{
  "issues": [
    {
      "timestamp": <number - seconds from start where issue is visible>,
      "severity": "<critical | warning | info>",
      "category": "<ui_consistency | accessibility | animation | layout | state | error | performance | other>",
      "description": "<clear description of the issue>",
      "suggestedFix": "<specific fix recommendation>",
      "confidence": <number 0-1 - how confident you are this is a real issue>,
      "frameIndex": <number - which frame shows the issue most clearly>
    }
  ],
  "qualityScore": <number 0-100 - overall quality assessment>,
  "summary": "<brief summary of overall findings>"
}

## Severity Guidelines

- **critical**: Blocks user from completing task, crashes, data loss, major accessibility violation
- **warning**: Degrades experience but doesn't block, minor accessibility issues, visual glitches
- **info**: Minor polish issues, suggestions for improvement

## Important

- Be thorough but avoid false positives
- Only report issues you can clearly see evidence of
- Include frame index when possible for easier debugging
- Set confidence based on how clearly the issue is visible
- If the UI looks correct, qualityScore should be high (90+)
- If unsure about an issue, lower the confidence score`;

  const customSection = customPrompts?.length
    ? `\n\n## Additional Checks\n\n${customPrompts.map((p, i) => `${i + 1}. ${p}`).join('\n')}`
    : '';

  return basePrompt + customSection;
}

/**
 * Gemini Analyzer class
 *
 * Handles all interactions with the Gemini API for video analysis.
 *
 * @example
 * ```typescript
 * const analyzer = new GeminiAnalyzer();
 *
 * const result = await analyzer.analyzeFrames(frames, {
 *   platform: 'ios',
 *   testName: 'Login Flow'
 * });
 *
 * console.log(`Quality Score: ${result.qualityScore}`);
 * console.log(`Issues found: ${result.issues.length}`);
 * ```
 */
export class GeminiAnalyzer {
  private config = getConfig();
  private genAI: GoogleGenerativeAI;
  private model;
  private requestCount = 0;
  private lastRequestTime = 0;
  private requestsThisMinute = 0;
  private minuteStart = Date.now();

  constructor() {
    this.genAI = new GoogleGenerativeAI(this.config.gemini.apiKey);
    this.model = this.genAI.getGenerativeModel({
      model: this.config.gemini.model,
      generationConfig: {
        temperature: 0.2, // Lower temperature for more consistent analysis
        topP: 0.8,
        topK: 40,
        maxOutputTokens: 8192
      },
      safetySettings: [
        {
          category: HarmCategory.HARM_CATEGORY_HARASSMENT,
          threshold: HarmBlockThreshold.BLOCK_ONLY_HIGH
        },
        {
          category: HarmCategory.HARM_CATEGORY_HATE_SPEECH,
          threshold: HarmBlockThreshold.BLOCK_ONLY_HIGH
        },
        {
          category: HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
          threshold: HarmBlockThreshold.BLOCK_ONLY_HIGH
        },
        {
          category: HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
          threshold: HarmBlockThreshold.BLOCK_ONLY_HIGH
        }
      ]
    });

    log.info(
      { model: this.config.gemini.model },
      'Gemini analyzer initialized'
    );
  }

  /**
   * Analyze a set of video frames for quality issues
   *
   * @param frames - Extracted frames to analyze
   * @param config - Analysis configuration
   * @param onProgress - Progress callback
   * @returns Analysis results with detected issues
   */
  async analyzeFrames(
    frames: ExtractedFrame[],
    config: AnalysisConfig,
    onProgress?: AnalysisProgressCallback
  ): Promise<{
    issues: DetectedIssue[];
    qualityScore: number;
    summary: string;
    rawResponse: string;
  }> {
    const done = startTiming('analyze-frames');

    onProgress?.({ phase: 'preparing', totalFrames: frames.length });

    log.info(
      { platform: config.platform, testName: config.testName, frameCount: frames.length },
      'Starting frame analysis'
    );

    try {
      // Rate limiting
      await this.waitForRateLimit();

      // Prepare image parts for the API
      onProgress?.({ phase: 'preparing', message: 'Loading frame images' });
      const imageParts = await this.prepareImageParts(frames);

      // Generate the analysis prompt
      const prompt = generateAnalysisPrompt(config.platform, config.customPrompts);

      // Build the content array with images and prompt
      const content = [
        {
          text: `Analyzing ${frames.length} frames from a ${config.platform} app test: "${config.testName}"\n\nTimestamps of frames (in seconds): ${frames.map(f => f.timestamp.toFixed(1)).join(', ')}`
        },
        ...imageParts,
        { text: prompt }
      ];

      // Make the API call
      onProgress?.({ phase: 'analyzing', message: 'Sending to Gemini API' });
      log.debug({ frameCount: frames.length }, 'Sending request to Gemini');

      const result = await this.callGeminiWithRetry(content);
      const rawResponse = result;

      // Parse the response
      onProgress?.({ phase: 'parsing', message: 'Parsing analysis results' });
      const parsed = this.parseResponse(rawResponse, frames);

      done();

      log.info(
        {
          platform: config.platform,
          issueCount: parsed.issues.length,
          qualityScore: parsed.qualityScore
        },
        'Frame analysis complete'
      );

      return {
        issues: parsed.issues,
        qualityScore: parsed.qualityScore,
        summary: parsed.summary,
        rawResponse
      };
    } catch (error) {
      logError(error, { platform: config.platform, frameCount: frames.length });
      throw error;
    }
  }

  /**
   * Analyze a single frame for quick checks
   *
   * @param frame - Frame to analyze
   * @param platform - Target platform
   * @returns Quick analysis results
   */
  async analyzeSingleFrame(
    frame: ExtractedFrame,
    platform: Platform
  ): Promise<{
    issues: DetectedIssue[];
    qualityScore: number;
  }> {
    const config: AnalysisConfig = {
      platform,
      testName: 'Single Frame Analysis',
      frameInterval: 1,
      maxFrames: 1
    };

    const result = await this.analyzeFrames([frame], config);
    return {
      issues: result.issues,
      qualityScore: result.qualityScore
    };
  }

  /**
   * Prepare image parts for the Gemini API
   */
  private async prepareImageParts(
    frames: ExtractedFrame[]
  ): Promise<Array<{ inlineData: { data: string; mimeType: string } }>> {
    const parts: Array<{ inlineData: { data: string; mimeType: string } }> = [];

    for (const frame of frames) {
      const imageBuffer = await fs.readFile(frame.path);
      const base64Data = imageBuffer.toString('base64');
      const ext = path.extname(frame.path).toLowerCase();
      const mimeType = ext === '.png' ? 'image/png' : ext === '.webp' ? 'image/webp' : 'image/jpeg';

      parts.push({
        inlineData: {
          data: base64Data,
          mimeType
        }
      });
    }

    return parts;
  }

  /**
   * Call Gemini API with automatic retry and exponential backoff
   */
  private async callGeminiWithRetry(
    content: Array<{ text: string } | { inlineData: { data: string; mimeType: string } }>,
    attempt = 1
  ): Promise<string> {
    try {
      this.requestCount++;
      this.requestsThisMinute++;

      const result = await this.model.generateContent(content);
      const response = result.response;
      const text = response.text();

      this.lastRequestTime = Date.now();
      return text;
    } catch (error) {
      const isRateLimit = error instanceof Error &&
        (error.message.includes('429') || error.message.includes('quota'));

      if (isRateLimit && attempt <= this.config.gemini.maxRetries) {
        const backoffMs = Math.min(1000 * Math.pow(2, attempt), 60000);
        log.warn(
          { attempt, backoffMs },
          'Rate limited, retrying with backoff'
        );
        await this.sleep(backoffMs);
        return this.callGeminiWithRetry(content, attempt + 1);
      }

      const isTemporary = error instanceof Error &&
        (error.message.includes('503') || error.message.includes('500'));

      if (isTemporary && attempt <= this.config.gemini.maxRetries) {
        const backoffMs = 1000 * attempt;
        log.warn({ attempt, backoffMs }, 'Temporary error, retrying');
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
    // Reset minute counter if a minute has passed
    if (Date.now() - this.minuteStart > 60000) {
      this.requestsThisMinute = 0;
      this.minuteStart = Date.now();
    }

    // Check if we're at the rate limit
    if (this.requestsThisMinute >= this.config.gemini.requestsPerMinute) {
      const waitTime = 60000 - (Date.now() - this.minuteStart) + 100;
      log.debug({ waitTime }, 'Waiting for rate limit');
      await this.sleep(waitTime);
      this.requestsThisMinute = 0;
      this.minuteStart = Date.now();
    }

    // Ensure minimum time between requests (100ms)
    const timeSinceLast = Date.now() - this.lastRequestTime;
    if (timeSinceLast < 100) {
      await this.sleep(100 - timeSinceLast);
    }
  }

  /**
   * Parse the Gemini response into structured issues
   */
  private parseResponse(
    rawResponse: string,
    frames: ExtractedFrame[]
  ): GeminiAnalysisResponse {
    try {
      // Extract JSON from the response (handle markdown code blocks)
      let jsonStr = rawResponse.trim();

      // Remove markdown code blocks if present
      const jsonMatch = jsonStr.match(/```(?:json)?\s*([\s\S]*?)```/);
      if (jsonMatch?.[1]) {
        jsonStr = jsonMatch[1].trim();
      }

      const parsed = JSON.parse(jsonStr) as GeminiAnalysisResponse;

      // Validate and normalize the response
      if (!Array.isArray(parsed.issues)) {
        parsed.issues = [];
      }

      // Add UUIDs and validate each issue
      parsed.issues = parsed.issues
        .filter(issue => {
          // Basic validation
          return (
            typeof issue.timestamp === 'number' &&
            typeof issue.description === 'string' &&
            issue.description.length > 0
          );
        })
        .map(issue => ({
          ...issue,
          timestamp: Math.max(0, issue.timestamp),
          severity: this.validateSeverity(issue.severity),
          category: this.validateCategory(issue.category),
          confidence: Math.max(0, Math.min(1, issue.confidence ?? 0.8)),
          frameIndex: issue.frameIndex !== undefined
            ? Math.min(issue.frameIndex, frames.length - 1)
            : this.findClosestFrameIndex(issue.timestamp, frames)
        }));

      parsed.qualityScore = Math.max(0, Math.min(100, parsed.qualityScore ?? 50));
      parsed.summary = parsed.summary ?? 'Analysis complete';

      return parsed;
    } catch (error) {
      log.error({ error, rawResponse: rawResponse.substring(0, 500) }, 'Failed to parse Gemini response');

      // Return a safe default
      return {
        issues: [],
        qualityScore: 50,
        summary: 'Failed to parse analysis response'
      };
    }
  }

  /**
   * Validate severity value
   */
  private validateSeverity(value: unknown): Severity {
    if (value === 'critical' || value === 'warning' || value === 'info') {
      return value;
    }
    return 'info';
  }

  /**
   * Validate category value
   */
  private validateCategory(value: unknown): IssueCategory {
    const validCategories: IssueCategory[] = [
      'ui_consistency', 'accessibility', 'animation', 'layout',
      'state', 'error', 'performance', 'other'
    ];
    if (validCategories.includes(value as IssueCategory)) {
      return value as IssueCategory;
    }
    return 'other';
  }

  /**
   * Find the closest frame index for a given timestamp
   */
  private findClosestFrameIndex(timestamp: number, frames: ExtractedFrame[]): number {
    let closestIndex = 0;
    let closestDiff = Infinity;

    for (let i = 0; i < frames.length; i++) {
      const diff = Math.abs((frames[i]?.timestamp ?? 0) - timestamp);
      if (diff < closestDiff) {
        closestDiff = diff;
        closestIndex = i;
      }
    }

    return closestIndex;
  }

  /**
   * Convert parsed issues to DetectedIssue format with UUIDs
   */
  enrichIssues(
    parsedIssues: GeminiAnalysisResponse['issues'],
    frames: ExtractedFrame[]
  ): DetectedIssue[] {
    return parsedIssues.map(issue => {
      const frameIndex = issue.frameIndex ?? this.findClosestFrameIndex(issue.timestamp, frames);
      const frame = frames[frameIndex];

      return {
        id: randomUUID(),
        timestamp: issue.timestamp,
        severity: issue.severity,
        category: issue.category,
        description: issue.description,
        framePath: frame?.path,
        suggestedFix: issue.suggestedFix,
        confidence: issue.confidence
      };
    });
  }

  /**
   * Get current API usage statistics
   */
  getUsageStats(): {
    totalRequests: number;
    requestsThisMinute: number;
    lastRequestTime: Date | null;
  } {
    return {
      totalRequests: this.requestCount,
      requestsThisMinute: this.requestsThisMinute,
      lastRequestTime: this.lastRequestTime ? new Date(this.lastRequestTime) : null
    };
  }

  /**
   * Test connectivity to the Gemini API
   */
  async testConnection(): Promise<boolean> {
    try {
      const result = await this.model.generateContent('Reply with just the word "connected"');
      const text = result.response.text();
      return text.toLowerCase().includes('connected');
    } catch (error) {
      logError(error, { action: 'test-connection' });
      return false;
    }
  }

  /**
   * Sleep utility
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

/**
 * Singleton instance for convenient access
 */
let analyzerInstance: GeminiAnalyzer | null = null;

/**
 * Get the shared GeminiAnalyzer instance
 */
export function getAnalyzer(): GeminiAnalyzer {
  if (!analyzerInstance) {
    analyzerInstance = new GeminiAnalyzer();
  }
  return analyzerInstance;
}

/**
 * Reset the analyzer instance (for testing)
 */
export function resetAnalyzer(): void {
  analyzerInstance = null;
}
