/**
 * @fileoverview Pipeline Runner - Orchestrates video analysis workflow
 *
 * This module coordinates the complete analysis pipeline:
 * - Watches directories for new test videos
 * - Queues videos for analysis with priority
 * - Manages concurrent job execution
 * - Rate limits API calls
 * - Notifies observers of progress and results
 *
 * Uses p-queue for concurrency control and chokidar for file watching.
 */

import PQueue from 'p-queue';
import chokidar, { FSWatcher } from 'chokidar';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { EventEmitter } from 'node:events';
import { createChildLogger, startTiming, logError } from './logger.js';
import { getConfig } from './config.js';
import { VideoProcessor, getProcessor } from './processor.js';
import { GeminiAnalyzer, getAnalyzer } from './analyzer.js';
import { IssueTracker, getTracker } from './tracker.js';
import type {
  QueuedJob,
  AnalysisResult,
  AnalysisConfig,
  PipelineHealth,
  WsEventType,
  Platform,
  DetectedIssue
} from './types.js';

const log = createChildLogger({ component: 'runner' });

/**
 * Pipeline event types
 */
export interface PipelineEvents {
  'analysis:queued': { job: QueuedJob };
  'analysis:started': { job: QueuedJob };
  'analysis:progress': { jobId: string; phase: string; progress: number; message?: string };
  'analysis:completed': { result: AnalysisResult };
  'analysis:failed': { jobId: string; error: string };
  'issue:detected': { issue: DetectedIssue; analysisId: string };
  'pipeline:health': { health: PipelineHealth };
}

/**
 * Options for running a single analysis
 */
export interface RunAnalysisOptions {
  /** Path to the video file */
  videoPath: string;
  /** Analysis configuration */
  config: AnalysisConfig;
  /** Priority (higher = more urgent) */
  priority?: number;
  /** Callback for progress updates */
  onProgress?: (progress: { phase: string; progress: number; message?: string }) => void;
}

/**
 * Pipeline Runner class
 *
 * Orchestrates the entire video analysis pipeline.
 *
 * @example
 * ```typescript
 * const runner = new PipelineRunner();
 * await runner.start();
 *
 * // Queue a video for analysis
 * const result = await runner.runAnalysis({
 *   videoPath: '/path/to/video.mp4',
 *   config: {
 *     platform: 'ios',
 *     testName: 'Login Flow'
 *   }
 * });
 *
 * // Listen for events
 * runner.on('analysis:completed', ({ result }) => {
 *   console.log(`Analysis complete: ${result.qualityScore}/100`);
 * });
 *
 * // Watch directories for new videos
 * runner.watchDirectory('/path/to/test-videos');
 * ```
 */
export class PipelineRunner extends EventEmitter {
  private config = getConfig();
  private processor: VideoProcessor;
  private analyzer: GeminiAnalyzer;
  private tracker: IssueTracker | null = null;
  private queue: PQueue;
  private watchers: FSWatcher[] = [];
  private pendingJobs = new Map<string, QueuedJob>();
  private activeJobs = new Map<string, QueuedJob>();
  private completedCount = 0;
  private failedCount = 0;
  private startTime = Date.now();
  private running = false;
  /**
   * Health check interval ID - must be cleared on stop() to prevent memory leaks.
   * PERFORMANCE FIX (Jan 2026): Previously this interval was never cleared.
   */
  private healthInterval: NodeJS.Timeout | null = null;

  constructor() {
    super();
    this.processor = getProcessor();
    this.analyzer = getAnalyzer();

    // Initialize queue with concurrency control
    this.queue = new PQueue({
      concurrency: this.config.processing.maxConcurrentJobs,
      intervalCap: this.config.gemini.requestsPerMinute,
      interval: 60000, // 1 minute
      carryoverConcurrencyCount: true
    });

    // Emit health updates periodically
    // PERFORMANCE FIX (Jan 2026): Store interval ID to clear on stop()
    this.healthInterval = setInterval(() => this.emitHealth(), 30000);
  }

  /**
   * Start the pipeline runner
   */
  async start(): Promise<void> {
    if (this.running) {
      log.warn('Pipeline runner already started');
      return;
    }

    const done = startTiming('pipeline-start');

    // Initialize tracker
    this.tracker = await getTracker();

    // Start watching configured directories
    for (const dir of this.config.pipeline.watchDirs) {
      await this.watchDirectory(dir);
    }

    this.running = true;
    this.startTime = Date.now();
    done();

    log.info({
      concurrency: this.config.processing.maxConcurrentJobs,
      watchDirs: this.config.pipeline.watchDirs.length
    }, 'Pipeline runner started');
  }

  /**
   * Stop the pipeline runner
   */
  async stop(): Promise<void> {
    if (!this.running) {
      return;
    }

    log.info('Stopping pipeline runner');

    // PERFORMANCE FIX (Jan 2026): Clear health interval to prevent memory leak
    if (this.healthInterval) {
      clearInterval(this.healthInterval);
      this.healthInterval = null;
    }

    // Stop file watchers
    for (const watcher of this.watchers) {
      await watcher.close();
    }
    this.watchers = [];

    // Clear the queue (cancel pending jobs)
    this.queue.clear();

    // Wait for active jobs to complete
    await this.queue.onIdle();

    this.running = false;
    log.info('Pipeline runner stopped');
  }

  /**
   * Validate video path to prevent path traversal attacks
   */
  private validateVideoPath(videoPath: string): void {
    // Resolve to absolute path
    const resolvedPath = path.resolve(videoPath);

    // Check for path traversal patterns
    if (videoPath.includes('..')) {
      throw new Error('Path traversal detected: ".." not allowed in video path');
    }

    // Get allowed directories (configured watch dirs + temp dir)
    const allowedDirs = [
      ...this.config.pipeline.watchDirs,
      this.config.processing.tempDir,
      process.env.QA_VIDEO_UPLOAD_DIR,
    ].filter(Boolean).map(d => path.resolve(d as string));

    // Check if path is within allowed directories
    const isAllowed = allowedDirs.some(dir => resolvedPath.startsWith(dir));

    if (!isAllowed && allowedDirs.length > 0) {
      throw new Error(
        `Access denied: Video path must be within allowed directories. ` +
        `Allowed: ${allowedDirs.join(', ')}`
      );
    }

    // Check file extension
    const ext = path.extname(resolvedPath).toLowerCase();
    const allowedExtensions = ['.mp4', '.mov', '.webm', '.mkv', '.avi'];
    if (!allowedExtensions.includes(ext)) {
      throw new Error(`Invalid file type: Only video files are allowed (${allowedExtensions.join(', ')})`);
    }
  }

  /**
   * Run a single video analysis
   */
  async runAnalysis(options: RunAnalysisOptions): Promise<AnalysisResult> {
    const { videoPath, config, priority = 0, onProgress } = options;

    // Validate path to prevent path traversal
    this.validateVideoPath(videoPath);

    // Create job
    const job: QueuedJob = {
      id: randomUUID(),
      videoPath: path.resolve(videoPath), // Use resolved path
      config,
      priority,
      queuedAt: new Date().toISOString(),
      retries: 0,
      maxRetries: 3
    };

    // Queue the job
    this.pendingJobs.set(job.id, job);
    this.emit('analysis:queued', { job });

    log.info({ jobId: job.id, videoPath, platform: config.platform }, 'Analysis queued');

    // Execute in queue
    return this.queue.add(
      async () => this.executeJob(job, onProgress),
      { priority }
    ) as Promise<AnalysisResult>;
  }

  /**
   * Watch a directory for new video files
   */
  async watchDirectory(dirPath: string): Promise<void> {
    // Ensure directory exists
    try {
      await fs.access(dirPath);
    } catch {
      log.warn({ dirPath }, 'Watch directory does not exist, creating');
      await fs.mkdir(dirPath, { recursive: true });
    }

    const watcher = chokidar.watch(dirPath, {
      ignored: /(^|[\/\\])\../, // Ignore dotfiles
      persistent: true,
      ignoreInitial: true,
      awaitWriteFinish: {
        stabilityThreshold: 2000,
        pollInterval: 100
      }
    });

    watcher.on('add', async (filePath) => {
      // Only process video files
      const ext = path.extname(filePath).toLowerCase();
      if (!['.mp4', '.mov', '.webm', '.mkv'].includes(ext)) {
        return;
      }

      if (!this.config.pipeline.autoAnalyze) {
        log.debug({ filePath }, 'New video detected but auto-analyze is disabled');
        return;
      }

      log.info({ filePath }, 'New video detected, queueing for analysis');

      // Try to determine platform from path
      const platform = this.inferPlatform(filePath);
      const testName = path.basename(filePath, ext);

      await this.runAnalysis({
        videoPath: filePath,
        config: {
          platform,
          testName,
          frameInterval: this.config.processing.frameInterval,
          maxFrames: this.config.processing.maxFramesPerVideo
        }
      });
    });

    watcher.on('error', (error) => {
      logError(error, { dirPath, action: 'watch' });
    });

    this.watchers.push(watcher);
    log.debug({ dirPath }, 'Directory watcher started');
  }

  /**
   * Execute a single analysis job
   */
  private async executeJob(
    job: QueuedJob,
    onProgress?: (progress: { phase: string; progress: number; message?: string }) => void
  ): Promise<AnalysisResult> {
    const done = startTiming('execute-job');
    const tracker = this.tracker!;

    // Move from pending to active
    this.pendingJobs.delete(job.id);
    this.activeJobs.set(job.id, job);

    // Create analysis record
    const analysis = tracker.createAnalysis(job.videoPath, job.config);
    const startTime = Date.now();

    this.emit('analysis:started', { job });

    const emitProgress = (phase: string, progress: number, message?: string) => {
      const payload = { jobId: job.id, phase, progress, message };
      this.emit('analysis:progress', payload);
      onProgress?.(payload);
    };

    try {
      // Update status to processing
      tracker.updateAnalysisStatus(analysis.id, 'processing', {
        startedAt: new Date().toISOString()
      });

      // Step 1: Validate video
      emitProgress('validating', 0, 'Validating video file');
      const validation = await this.processor.validateVideo(job.videoPath);

      if (!validation.valid) {
        throw new Error(`Video validation failed: ${validation.issues.join(', ')}`);
      }

      // Step 2: Extract frames
      emitProgress('extracting', 10, 'Extracting frames from video');
      const frames = await this.processor.extractFrames(job.videoPath, {
        interval: job.config.frameInterval,
        maxFrames: job.config.maxFrames
      });

      tracker.updateAnalysisStatus(analysis.id, 'analyzing', {
        framesAnalyzed: frames.length,
        videoDuration: validation.metadata?.duration
      });

      // Step 3: Analyze with Gemini
      emitProgress('analyzing', 40, 'Analyzing frames with Gemini AI');
      const analysisResult = await this.analyzer.analyzeFrames(
        frames,
        job.config,
        (progress) => {
          const progressPercent = 40 + (progress.framesProcessed ?? 0) / (progress.totalFrames ?? 1) * 40;
          emitProgress(progress.phase, progressPercent, progress.message);
        }
      );

      // Enrich issues with frame paths and UUIDs
      const enrichedIssues = this.analyzer.enrichIssues(
        analysisResult.issues.map(issue => ({
          ...issue,
          frameIndex: issue.frameIndex ?? 0
        })),
        frames
      );

      // Step 4: Detect regressions
      emitProgress('detecting', 85, 'Detecting regressions');
      const { regressions, known } = tracker.detectRegressions(
        enrichedIssues,
        job.config.platform
      );

      // Step 5: Store results
      emitProgress('storing', 95, 'Storing results');
      tracker.storeIssues(analysis.id, enrichedIssues, job.config.platform);

      const completedAt = new Date().toISOString();
      const durationMs = Date.now() - startTime;

      tracker.updateAnalysisStatus(analysis.id, 'completed', {
        completedAt,
        durationMs,
        qualityScore: analysisResult.qualityScore,
        rawResponse: analysisResult.rawResponse
      });

      // Build final result
      const result: AnalysisResult = {
        ...analysis,
        status: 'completed',
        completedAt,
        durationMs,
        videoDuration: validation.metadata?.duration,
        framesAnalyzed: frames.length,
        issues: enrichedIssues,
        qualityScore: analysisResult.qualityScore,
        rawResponse: analysisResult.rawResponse
      };

      // Emit events for each issue
      for (const issue of enrichedIssues) {
        this.emit('issue:detected', { issue, analysisId: analysis.id });
      }

      this.completedCount++;
      this.activeJobs.delete(job.id);
      done();

      emitProgress('completed', 100, `Analysis complete. Quality: ${analysisResult.qualityScore}/100`);
      this.emit('analysis:completed', { result });

      log.info({
        jobId: job.id,
        analysisId: analysis.id,
        qualityScore: analysisResult.qualityScore,
        issueCount: enrichedIssues.length,
        regressions: regressions.length,
        durationMs
      }, 'Analysis completed successfully');

      return result;

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      logError(error, { jobId: job.id, analysisId: analysis.id });

      tracker.updateAnalysisStatus(analysis.id, 'failed', {
        completedAt: new Date().toISOString(),
        durationMs: Date.now() - startTime,
        error: errorMessage
      });

      this.failedCount++;
      this.activeJobs.delete(job.id);
      done();

      this.emit('analysis:failed', { jobId: job.id, error: errorMessage });

      // Check if we should retry
      if (job.retries < job.maxRetries) {
        log.warn({ jobId: job.id, retries: job.retries }, 'Retrying failed job');
        job.retries++;
        return this.queue.add(() => this.executeJob(job, onProgress)) as Promise<AnalysisResult>;
      }

      throw error;
    }
  }

  /**
   * Infer platform from file path
   */
  private inferPlatform(filePath: string): Platform {
    const lowerPath = filePath.toLowerCase();

    if (lowerPath.includes('ios') || lowerPath.includes('iphone') || lowerPath.includes('ipad')) {
      return 'ios';
    }
    if (lowerPath.includes('android')) {
      return 'android';
    }
    if (lowerPath.includes('watch')) {
      return 'watchos';
    }
    if (lowerPath.includes('vision') || lowerPath.includes('vr') || lowerPath.includes('xr')) {
      return 'visionos';
    }
    if (lowerPath.includes('tv') || lowerPath.includes('tvos')) {
      return 'tvos';
    }
    if (lowerPath.includes('desktop') || lowerPath.includes('mac') || lowerPath.includes('windows')) {
      return 'desktop';
    }
    if (lowerPath.includes('web')) {
      return 'web';
    }

    // Default to iOS
    return 'ios';
  }

  /**
   * Check available disk space and return storage status
   * Thresholds: >10GB = available, 1-10GB = low, <1GB = full
   */
  private async checkStorageStatus(): Promise<PipelineHealth['storageStatus']> {
    const GB = 1024 * 1024 * 1024;
    const THRESHOLD_AVAILABLE = 10 * GB; // 10GB
    const THRESHOLD_LOW = 1 * GB; // 1GB

    try {
      // Check the storage path configured for the pipeline
      const storagePath = path.resolve(this.config.storage.localPath);

      // Ensure the directory exists before checking
      await fs.mkdir(storagePath, { recursive: true });

      // Use fs.statfs to check disk space (Node.js 18.15+)
      const stats = await fs.statfs(storagePath);
      const availableBytes = stats.bavail * stats.bsize;

      if (availableBytes >= THRESHOLD_AVAILABLE) {
        return 'available';
      } else if (availableBytes >= THRESHOLD_LOW) {
        return 'low';
      } else {
        return 'full';
      }
    } catch (error) {
      log.error({ error }, 'Failed to check storage status');
      return 'error';
    }
  }

  /**
   * Get current pipeline health
   */
  async getHealth(): Promise<PipelineHealth> {
    const geminiStats = this.analyzer.getUsageStats();

    let geminiStatus: PipelineHealth['geminiStatus'] = 'unknown';
    if (geminiStats.lastRequestTime) {
      const timeSinceLastRequest = Date.now() - geminiStats.lastRequestTime.getTime();
      if (timeSinceLastRequest < 60000) {
        geminiStatus = 'connected';
      }
    }

    const storageStatus = await this.checkStorageStatus();

    return {
      healthy: this.running && this.queue.isPaused === false,
      queueDepth: this.pendingJobs.size,
      activeJobs: this.activeJobs.size,
      completedJobs: this.completedCount,
      failedJobs: this.failedCount,
      geminiStatus,
      storageStatus,
      lastCheck: new Date().toISOString(),
      uptimeMs: Date.now() - this.startTime
    };
  }

  /**
   * Emit health status event
   */
  private async emitHealth(): Promise<void> {
    if (!this.running) {
      return;
    }

    const health = await this.getHealth();
    this.emit('pipeline:health', { health });
  }

  /**
   * Get all pending jobs
   */
  getPendingJobs(): QueuedJob[] {
    return Array.from(this.pendingJobs.values());
  }

  /**
   * Get all active jobs
   */
  getActiveJobs(): QueuedJob[] {
    return Array.from(this.activeJobs.values());
  }

  /**
   * Cancel a pending job
   */
  cancelJob(jobId: string): boolean {
    if (this.pendingJobs.has(jobId)) {
      this.pendingJobs.delete(jobId);
      log.info({ jobId }, 'Job cancelled');
      return true;
    }

    if (this.activeJobs.has(jobId)) {
      log.warn({ jobId }, 'Cannot cancel active job');
      return false;
    }

    return false;
  }

  /**
   * Pause the queue
   */
  pause(): void {
    this.queue.pause();
    log.info('Pipeline queue paused');
  }

  /**
   * Resume the queue
   */
  resume(): void {
    this.queue.start();
    log.info('Pipeline queue resumed');
  }

  /**
   * Wait for queue to be empty
   */
  async onIdle(): Promise<void> {
    await this.queue.onIdle();
  }

  /**
   * Type-safe event emitter methods
   */
  override emit<K extends WsEventType>(event: K, payload: PipelineEvents[K]): boolean {
    return super.emit(event, payload);
  }

  override on<K extends WsEventType>(
    event: K,
    listener: (payload: PipelineEvents[K]) => void
  ): this {
    return super.on(event, listener);
  }

  override once<K extends WsEventType>(
    event: K,
    listener: (payload: PipelineEvents[K]) => void
  ): this {
    return super.once(event, listener);
  }
}

/**
 * Singleton instance for convenient access
 */
let runnerInstance: PipelineRunner | null = null;

/**
 * Get the shared PipelineRunner instance
 */
export function getRunner(): PipelineRunner {
  if (!runnerInstance) {
    runnerInstance = new PipelineRunner();
  }
  return runnerInstance;
}

/**
 * Reset the runner instance (for testing)
 */
export async function resetRunner(): Promise<void> {
  if (runnerInstance) {
    await runnerInstance.stop();
    runnerInstance = null;
  }
}
