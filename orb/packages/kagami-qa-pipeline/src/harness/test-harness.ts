/**
 * Central Test Harness for Kagami QA Pipeline
 *
 * This harness orchestrates test execution across all platforms,
 * captures video recordings, collects results with Byzantine quality
 * scoring, and prepares data for Gemini analysis.
 *
 * Colony: Crystal (e7) -- Verification & Polish
 * h(x) >= 0. Always.
 */

import { ChildProcess, spawn, execSync } from 'child_process';
import { EventEmitter } from 'events';
import * as fs from 'fs';
import * as path from 'path';
import * as WebSocket from 'ws';
import { createChildLogger, startTiming } from '../logger.js';
import {
  Platform,
  JourneySpec,
  ConstellationJourneySpec,
  Checkpoint,
  Phase,
  SINGLE_DEVICE_JOURNEYS,
  CONSTELLATION_JOURNEYS,
  JourneyId,
} from '../journeys/canonical-journeys.js';
import {
  ConstellationOrchestrator,
  ConstellationResult,
  ConstellationOrchestratorOptions,
  FIBONACCI_TIMEOUTS,
  getFibonacciTimeout,
} from '../orchestrator/constellation-orchestrator.js';
import {
  PerformanceTracker,
  getPerformanceTracker,
  type PerformanceReport,
} from '../performance/index.js';

// =============================================================================
// CONSTANTS
// =============================================================================

/**
 * Default output directory for test artifacts
 */
const DEFAULT_OUTPUT_DIR = './qa-output';

/**
 * Video format settings
 */
const VIDEO_SETTINGS = {
  format: 'mp4',
  codec: 'libx264',
  preset: 'ultrafast',
  crf: 23,
  fps: 30,
} as const;

/**
 * Android screenrecord constants
 */
const ANDROID_RECORDING = {
  /** Maximum duration in seconds (Android hard limit is 180s = 3 minutes) */
  maxDurationSeconds: 180,
  /** Temp file path on device - use /data/local/tmp for better compatibility with scoped storage */
  devicePath: '/data/local/tmp/kagami_recording.mp4',
  /** Default bitrate */
  bitRate: '4M',
} as const;

/**
 * Characters invalid in file names across platforms (Windows is most restrictive)
 */
const INVALID_FILENAME_CHARS = /[<>:"/\\|?*\x00-\x1f]/g;

/**
 * Byzantine quality dimensions
 */
const QUALITY_DIMENSIONS = [
  'technical',
  'aesthetic',
  'accessibility',
  'emotional',
  'polish',
  'delight',
] as const;

type QualityDimension = typeof QUALITY_DIMENSIONS[number];

// =============================================================================
// TYPES
// =============================================================================

/**
 * Video recording state
 */
export type RecordingState =
  | 'idle'
  | 'starting'
  | 'recording'
  | 'stopping'
  | 'completed'
  | 'error';

/**
 * Video recorder configuration
 */
export interface VideoRecorderConfig {
  /** Output directory for videos */
  outputDir: string;
  /** Video format (mp4, mov) */
  format: 'mp4' | 'mov';
  /** Frame rate */
  fps: number;
  /** Quality (0-51 for CRF, lower is better) */
  quality: number;
  /** Maximum recording duration in seconds */
  maxDuration: number;
  /** Whether to capture audio */
  captureAudio: boolean;
}

/**
 * Video recording metadata
 */
export interface VideoRecording {
  /** Unique ID for the recording */
  id: string;
  /** Journey ID this recording is for */
  journeyId: string;
  /** Platform being recorded */
  platform: Platform;
  /** Path to the video file */
  path: string;
  /** Recording state */
  state: RecordingState;
  /** Start timestamp */
  startedAt: number;
  /** End timestamp */
  endedAt?: number;
  /** Duration in milliseconds */
  durationMs?: number;
  /** File size in bytes */
  fileSize?: number;
  /** Checkpoint timestamps for frame correlation */
  checkpointTimestamps: CheckpointTimestamp[];
  /** Error message if recording failed */
  error?: string;
}

/**
 * Checkpoint timestamp for video correlation
 */
export interface CheckpointTimestamp {
  /** Checkpoint ID */
  checkpointId: string;
  /** Checkpoint name */
  checkpointName: string;
  /** Video timestamp in milliseconds */
  videoTimestampMs: number;
  /** Wall clock timestamp */
  wallClockTimestamp: number;
  /** Whether checkpoint passed */
  passed: boolean;
}

/**
 * Single-device journey execution result
 */
export interface JourneyExecutionResult {
  /** Journey ID */
  journeyId: string;
  /** Journey name */
  journeyName: string;
  /** Platform executed on */
  platform: Platform;
  /** Whether the journey passed */
  success: boolean;
  /** Phase results */
  phaseResults: PhaseExecutionResult[];
  /** Total duration in milliseconds */
  totalDurationMs: number;
  /** Byzantine quality scores */
  qualityScores: Record<QualityDimension, number>;
  /** Overall quality score (average) */
  overallScore: number;
  /** Video recording info (undefined if not recorded) */
  recording: VideoRecording | undefined;
  /** Errors encountered */
  errors: string[];
  /** Execution timestamp */
  executedAt: string;
}

/**
 * Phase execution result
 */
export interface PhaseExecutionResult {
  /** Phase ID */
  phaseId: string;
  /** Phase name */
  phaseName: string;
  /** Whether the phase passed */
  success: boolean;
  /** Checkpoint results */
  checkpointResults: CheckpointExecutionResult[];
  /** Duration in milliseconds */
  durationMs: number;
  /** Errors encountered */
  errors: string[];
}

/**
 * Checkpoint execution result
 */
export interface CheckpointExecutionResult {
  /** Checkpoint ID */
  checkpointId: string;
  /** Checkpoint name */
  checkpointName: string;
  /** Whether the checkpoint passed */
  success: boolean;
  /** Elements found */
  elementsFound: string[];
  /** Elements missing */
  elementsMissing: string[];
  /** Duration in milliseconds */
  durationMs: number;
  /** Maximum duration allowed from canonical spec (for Gemini analysis) */
  maxDurationMs: number;
  /** Duration vs expected */
  durationVsExpected: 'within' | 'exceeded';
  /** Whether the checkpoint failed specifically due to timing */
  failedDueToTiming: boolean;
  /** Video timestamp in milliseconds (undefined if not recording) */
  videoTimestampMs: number | undefined;
  /** Actual state captured (undefined if not captured) */
  actualState: Record<string, unknown> | undefined;
  /** Error message if checkpoint failed */
  error?: string;
}

/**
 * Performance tracking configuration
 */
export interface PerformanceTrackingConfig {
  /** Enable performance tracking */
  enabled: boolean;
  /** Path to performance baseline file */
  baselinePath: string;
  /** Path to performance history file */
  historyPath: string;
  /** Fail the run if any hard threshold is exceeded */
  failOnThresholdExceeded: boolean;
  /** Fail the run if any regression is detected */
  failOnRegression: boolean;
  /** Auto-generate baseline if none exists */
  autoGenerateBaseline: boolean;
}

/**
 * Test harness configuration
 */
export interface TestHarnessConfig {
  /** Output directory for all artifacts */
  outputDir: string;
  /** Video recorder configuration */
  video: VideoRecorderConfig;
  /** Orchestrator options for constellation tests */
  orchestrator: Partial<ConstellationOrchestratorOptions>;
  /** Dashboard WebSocket URL for real-time updates (undefined to disable) */
  dashboardUrl: string | undefined;
  /** Whether to automatically push results to dashboard */
  autoPushToDashboard: boolean;
  /** Whether to prepare videos for Gemini analysis */
  prepareForGemini: boolean;
  /** Gemini analysis output directory */
  geminiOutputDir: string;
  /** Verbose logging */
  verbose: boolean;
  /** Performance tracking configuration */
  performance: PerformanceTrackingConfig;
}

/**
 * Checkpoint timing metrics for Gemini analysis
 */
export interface CheckpointTimingMetrics {
  /** Checkpoint ID */
  checkpointId: string;
  /** Checkpoint name */
  checkpointName: string;
  /** Actual duration in milliseconds */
  actualDurationMs: number;
  /** Maximum allowed duration from canonical spec */
  maxDurationMs: number;
  /** Whether timing was exceeded */
  exceeded: boolean;
  /** Amount exceeded by (negative if within budget) */
  exceededByMs: number;
  /** Percentage of max duration used */
  percentageOfMax: number;
}

/**
 * Gemini analysis handoff data
 */
export interface GeminiAnalysisHandoff {
  /** Video file path */
  videoPath: string;
  /** Journey ID */
  journeyId: string;
  /** Platform */
  platform: Platform;
  /** Checkpoint timestamps for frame correlation */
  checkpointTimestamps: CheckpointTimestamp[];
  /** Journey execution result summary */
  executionSummary: {
    success: boolean;
    totalDurationMs: number;
    qualityScores: Record<QualityDimension, number>;
    errors: string[];
  };
  /** Detailed checkpoint timing metrics for performance analysis */
  timingMetrics: CheckpointTimingMetrics[];
  /** Summary of timing performance */
  timingSummary: {
    /** Total checkpoints */
    totalCheckpoints: number;
    /** Checkpoints that exceeded timing */
    checkpointsExceededTiming: number;
    /** Average percentage of max duration used */
    averagePercentageOfMax: number;
    /** Slowest checkpoint */
    slowestCheckpoint: string | null;
    /** Fastest checkpoint */
    fastestCheckpoint: string | null;
  };
  /** Analysis prompts based on journey */
  analysisPrompts: string[];
  /** Expected elements to verify */
  expectedElements: string[];
  /** Timestamp */
  createdAt: string;
}

/**
 * Dashboard update payload
 */
export interface DashboardUpdate {
  type:
    | 'journey:started'
    | 'journey:checkpoint'
    | 'journey:phase'
    | 'journey:completed'
    | 'constellation:started'
    | 'constellation:checkpoint'
    | 'constellation:completed';
  journeyId: string;
  platform: Platform;
  data: unknown;
  timestamp: string;
}

/**
 * Test harness summary statistics
 */
export interface TestSummary {
  /** Total journeys executed */
  totalJourneys: number;
  /** Journeys passed */
  journeysPassed: number;
  /** Journeys failed */
  journeysFailed: number;
  /** Total checkpoints */
  totalCheckpoints: number;
  /** Checkpoints passed */
  checkpointsPassed: number;
  /** Average quality score */
  averageQualityScore: number;
  /** Quality scores by dimension */
  qualityByDimension: Record<QualityDimension, number>;
  /** Total duration */
  totalDurationMs: number;
  /** Platforms tested */
  platformsTested: Platform[];
  /** Timestamp */
  generatedAt: string;
}

// =============================================================================
// VIDEO RECORDER
// =============================================================================

/**
 * Platform-specific video capture
 */
export class VideoRecorder extends EventEmitter {
  private logger = createChildLogger({ component: 'video-recorder' });
  private config: VideoRecorderConfig;
  private activeRecordings: Map<string, VideoRecording> = new Map();
  private recordingProcesses: Map<string, ChildProcess> = new Map();

  constructor(config: Partial<VideoRecorderConfig> = {}) {
    super();
    this.config = {
      outputDir: config.outputDir ?? DEFAULT_OUTPUT_DIR,
      format: config.format ?? 'mp4',
      fps: config.fps ?? VIDEO_SETTINGS.fps,
      quality: config.quality ?? VIDEO_SETTINGS.crf,
      maxDuration: config.maxDuration ?? 300,
      captureAudio: config.captureAudio ?? false,
    };

    // Ensure output directory exists
    this.ensureOutputDir();
  }

  /**
   * Ensure output directory exists
   */
  private ensureOutputDir(): void {
    const videosDir = path.join(this.config.outputDir, 'videos');
    if (!fs.existsSync(videosDir)) {
      fs.mkdirSync(videosDir, { recursive: true });
    }
  }

  /**
   * Sanitize a string for use in filenames across all platforms
   */
  private sanitizeForFilename(input: string): string {
    return input
      .replace(INVALID_FILENAME_CHARS, '_')
      .replace(/_{2,}/g, '_') // Collapse multiple underscores
      .replace(/^_|_$/g, ''); // Trim leading/trailing underscores
  }

  /**
   * Escape a string for use in shell commands
   */
  private shellEscape(input: string): string {
    // For Windows, use double quotes and escape internal double quotes
    if (process.platform === 'win32') {
      return `"${input.replace(/"/g, '\\"')}"`;
    }
    // For Unix-like systems, use single quotes (which don't interpret anything)
    // and handle embedded single quotes by ending quote, adding escaped quote, starting new quote
    return `'${input.replace(/'/g, "'\\''")}'`;
  }

  /**
   * Generate unique recording ID (sanitized for cross-platform filenames)
   */
  private generateRecordingId(journeyId: string, platform: Platform): string {
    const timestamp = Date.now();
    const sanitizedJourneyId = this.sanitizeForFilename(journeyId);
    const sanitizedPlatform = this.sanitizeForFilename(platform);
    return `${sanitizedJourneyId}_${sanitizedPlatform}_${timestamp}`;
  }

  /**
   * Get video file path for a recording
   */
  private getVideoPath(recordingId: string): string {
    return path.join(
      this.config.outputDir,
      'videos',
      `${recordingId}.${this.config.format}`
    );
  }

  /**
   * Start recording video for a journey
   *
   * @param journeyId - Journey being executed
   * @param platform - Platform being recorded
   * @param deviceId - Optional device ID for simulators/emulators
   * @returns Recording info
   */
  async startRecording(
    journeyId: string,
    platform: Platform,
    deviceId?: string
  ): Promise<VideoRecording> {
    const recordingId = this.generateRecordingId(journeyId, platform);
    const videoPath = this.getVideoPath(recordingId);

    const recording: VideoRecording = {
      id: recordingId,
      journeyId,
      platform,
      path: videoPath,
      state: 'starting',
      startedAt: Date.now(),
      checkpointTimestamps: [],
    };

    this.activeRecordings.set(recordingId, recording);
    this.logger.info({ recordingId, platform, videoPath }, 'Starting video recording');

    try {
      const process = await this.startPlatformRecording(platform, videoPath, deviceId);
      this.recordingProcesses.set(recordingId, process);
      recording.state = 'recording';

      this.emit('recording:started', recording);
      return recording;
    } catch (error) {
      recording.state = 'error';
      recording.error = error instanceof Error ? error.message : String(error);
      this.logger.error({ recordingId, error }, 'Failed to start recording');
      this.emit('recording:error', recording);
      return recording;
    }
  }

  /**
   * Start platform-specific recording
   */
  private async startPlatformRecording(
    platform: Platform,
    outputPath: string,
    deviceId?: string
  ): Promise<ChildProcess> {
    let command: string;
    let args: string[];

    switch (platform) {
      case 'ios':
      case 'tvos':
      case 'watchos':
      case 'visionos':
        // Use xcrun simctl for iOS family
        command = 'xcrun';
        args = [
          'simctl',
          'io',
          deviceId ?? 'booted',
          'recordVideo',
          '--codec=h264',
          outputPath,
        ];
        break;

      case 'android':
      case 'wearos':
      case 'androidxr':
        // Use adb screenrecord for Android family
        // IMPORTANT: screenrecord has a 3-minute (180s) hard limit enforced by Android
        // Valid options: --size, --bit-rate, --time-limit, --verbose, --bugreport
        // Note: --output-format does NOT exist despite some outdated documentation
        command = 'adb';
        {
          const screenrecordArgs = [
            'shell',
            'screenrecord',
            '--bit-rate', ANDROID_RECORDING.bitRate,
            '--time-limit', String(ANDROID_RECORDING.maxDurationSeconds),
            '--verbose',
            ANDROID_RECORDING.devicePath,
          ];
          args = deviceId
            ? ['-s', deviceId, ...screenrecordArgs]
            : screenrecordArgs;
        }
        this.logger.warn(
          { maxDuration: ANDROID_RECORDING.maxDurationSeconds },
          'Android screenrecord has a maximum duration of 3 minutes'
        );
        break;

      case 'desktop':
        // Use FFmpeg for desktop screen capture
        command = 'ffmpeg';
        args = this.getFFmpegDesktopArgs(outputPath);
        break;

      case 'hub':
        // Hub has no visual interface - use deferred video generation
        // We'll collect events during the test and generate a status visualization
        // video at stopRecording time using generateHubStatusVideo()
        this.logger.info('Hub platform: deferring video generation to capture status events');
        // Create a placeholder process that does nothing but stays alive
        // We mark this specially so stopRecording knows to generate the status video
        command = 'sleep';
        args = ['infinity'];
        break;

      default:
        throw new Error(`Unsupported platform for video recording: ${platform}`);
    }

    this.logger.debug({ command, args }, 'Spawning recording process');

    const process = spawn(command, args, {
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    process.stderr?.on('data', (data) => {
      this.logger.debug({ output: data.toString() }, 'Recording stderr');
    });

    // Wait for recording to actually start
    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => {
        resolve(); // Assume started after timeout
      }, FIBONACCI_TIMEOUTS.F5);

      process.on('error', (err) => {
        clearTimeout(timeout);
        reject(err);
      });

      // For simctl, it outputs to stderr when starting
      process.stderr?.once('data', () => {
        clearTimeout(timeout);
        resolve();
      });
    });

    return process;
  }

  /**
   * Get screen dimensions for Linux x11grab
   * Returns dimensions in WIDTHxHEIGHT format
   */
  private getLinuxScreenDimensions(): string {
    try {
      // Try xdpyinfo first
      const output = execSync('xdpyinfo 2>/dev/null | grep dimensions | head -1', {
        encoding: 'utf8',
        timeout: 5000,
      });
      const match = output.match(/(\d+x\d+)/);
      if (match && match[1]) {
        return match[1];
      }
    } catch {
      // xdpyinfo not available or failed
    }

    try {
      // Fall back to xrandr
      const output = execSync('xrandr 2>/dev/null | grep "\\*" | head -1', {
        encoding: 'utf8',
        timeout: 5000,
      });
      const match = output.match(/(\d+)x(\d+)/);
      if (match && match[1] && match[2]) {
        return `${match[1]}x${match[2]}`;
      }
    } catch {
      // xrandr not available or failed
    }

    // Default fallback - common resolution
    this.logger.warn('Could not detect screen dimensions, using 1920x1080 default');
    return '1920x1080';
  }

  /**
   * Get FFmpeg args for desktop screen capture
   *
   * Platform-specific notes:
   * - macOS: avfoundation requires screen index (0 = main display)
   * - Linux: x11grab REQUIRES -video_size before -i
   * - Windows: gdigrab captures "desktop" or specific window titles
   *
   * Common FFmpeg gotchas:
   * - Input options (framerate, video_size) MUST come BEFORE -i
   * - Output options (codec, preset) come AFTER -i
   * - Use -framerate for input, -r for output frame rate
   */
  private getFFmpegDesktopArgs(outputPath: string): string[] {
    const isMac = process.platform === 'darwin';
    const isLinux = process.platform === 'linux';

    if (isMac) {
      // avfoundation input format for macOS
      // Device index format: "video_device_index:audio_device_index"
      // Use 'none' for audio to disable audio capture
      // Screen index 0 = main display, 1 = secondary, etc.
      // List devices with: ffmpeg -f avfoundation -list_devices true -i ""
      return [
        '-f', 'avfoundation',
        '-framerate', String(this.config.fps),
        '-capture_cursor', '1',   // Capture mouse cursor
        '-i', '0:none',           // Screen 0 (main display), no audio
        '-c:v', 'libx264',
        '-preset', VIDEO_SETTINGS.preset,
        '-crf', String(this.config.quality),
        '-pix_fmt', 'yuv420p',    // Required for compatibility
        '-movflags', '+faststart', // Enable streaming playback
        outputPath,
      ];
    }

    if (isLinux) {
      // x11grab input format for Linux
      // CRITICAL: -video_size MUST be specified before -i
      // CRITICAL: -framerate must come before -i for input specification
      const screenSize = this.getLinuxScreenDimensions();
      return [
        '-f', 'x11grab',
        '-framerate', String(this.config.fps),
        '-video_size', screenSize,  // REQUIRED for x11grab
        '-i', ':0.0+0,0',            // Display :0, screen 0, offset 0,0
        '-draw_mouse', '1',          // Capture mouse cursor
        '-c:v', 'libx264',
        '-preset', VIDEO_SETTINGS.preset,
        '-crf', String(this.config.quality),
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
        outputPath,
      ];
    }

    // Windows - gdigrab
    // Note: gdigrab can capture "desktop" or specific windows by title
    return [
      '-f', 'gdigrab',
      '-framerate', String(this.config.fps),
      '-draw_mouse', '1',          // Capture mouse cursor
      '-i', 'desktop',             // Capture entire desktop
      '-c:v', 'libx264',
      '-preset', VIDEO_SETTINGS.preset,
      '-crf', String(this.config.quality),
      '-pix_fmt', 'yuv420p',
      '-movflags', '+faststart',
      outputPath,
    ];
  }

  /**
   * Record a checkpoint timestamp
   *
   * @param recordingId - Recording ID
   * @param checkpoint - Checkpoint that was reached
   * @param passed - Whether the checkpoint passed
   */
  recordCheckpoint(
    recordingId: string,
    checkpoint: Checkpoint,
    passed: boolean
  ): void {
    const recording = this.activeRecordings.get(recordingId);
    if (!recording) {
      this.logger.warn({ recordingId }, 'Recording not found for checkpoint');
      return;
    }

    const wallClock = Date.now();
    const videoTimestamp = wallClock - recording.startedAt;

    recording.checkpointTimestamps.push({
      checkpointId: checkpoint.id,
      checkpointName: checkpoint.name,
      videoTimestampMs: videoTimestamp,
      wallClockTimestamp: wallClock,
      passed,
    });

    this.logger.debug(
      { recordingId, checkpointId: checkpoint.id, videoTimestamp },
      'Recorded checkpoint timestamp'
    );

    this.emit('recording:checkpoint', { recordingId, checkpoint, passed, videoTimestamp });
  }

  /**
   * Stop recording video
   *
   * @param recordingId - Recording ID to stop
   * @returns Final recording info
   */
  async stopRecording(recordingId: string): Promise<VideoRecording> {
    const recording = this.activeRecordings.get(recordingId);
    if (!recording) {
      throw new Error(`Recording not found: ${recordingId}`);
    }

    const process = this.recordingProcesses.get(recordingId);
    if (!process) {
      throw new Error(`Recording process not found: ${recordingId}`);
    }

    this.logger.info({ recordingId }, 'Stopping video recording');
    recording.state = 'stopping';

    try {
      // For Hub platform, generate the status visualization video instead of stopping a real recording
      if (recording.platform === 'hub') {
        // Kill the placeholder sleep process
        process.kill('SIGTERM');
        this.recordingProcesses.delete(recordingId);

        // Generate the Hub status visualization video
        recording.endedAt = Date.now();
        recording.durationMs = recording.endedAt - recording.startedAt;
        await this.generateHubStatusVideo(recording);

        recording.state = 'completed';

        // Get file size
        if (fs.existsSync(recording.path)) {
          const stats = fs.statSync(recording.path);
          recording.fileSize = stats.size;
        }

        this.logger.info(
          { recordingId, durationMs: recording.durationMs, fileSize: recording.fileSize },
          'Hub status video generated'
        );

        this.emit('recording:completed', recording);
        return recording;
      }

      // Stop the recording process gracefully (non-Hub platforms)
      await this.stopPlatformRecording(recording.platform, process, recordingId);

      recording.endedAt = Date.now();
      recording.durationMs = recording.endedAt - recording.startedAt;
      recording.state = 'completed';

      // Get file size
      if (fs.existsSync(recording.path)) {
        const stats = fs.statSync(recording.path);
        recording.fileSize = stats.size;
      }

      this.recordingProcesses.delete(recordingId);
      this.logger.info(
        { recordingId, durationMs: recording.durationMs, fileSize: recording.fileSize },
        'Recording completed'
      );

      this.emit('recording:completed', recording);
      return recording;
    } catch (error) {
      recording.state = 'error';
      recording.error = error instanceof Error ? error.message : String(error);
      this.logger.error({ recordingId, error }, 'Failed to stop recording');
      this.emit('recording:error', recording);
      return recording;
    }
  }

  /**
   * Generate a Hub status visualization video from collected checkpoint data
   *
   * Since the Hub has no visual interface, this method creates a video that visualizes:
   * - Test timeline with checkpoint markers
   * - Pass/fail status for each checkpoint
   * - Timing information and state changes
   *
   * Uses FFmpeg to generate a video with text overlays showing the Hub's status during the test.
   */
  private async generateHubStatusVideo(recording: VideoRecording): Promise<void> {
    const checkpoints = recording.checkpointTimestamps;
    const outputPath = recording.path;
    const durationSeconds = Math.max(1, Math.ceil((recording.durationMs ?? 1000) / 1000));

    // Calculate video dimensions
    const width = 1280;
    const height = 720;
    const fps = this.config.fps;

    // Escape text for FFmpeg drawtext filter
    const escapeFFmpegText = (text: string): string => {
      return text
        .replace(/\\/g, '\\\\')
        .replace(/'/g, "'\\''")
        .replace(/:/g, '\\:')
        .replace(/\[/g, '\\[')
        .replace(/\]/g, '\\]');
    };

    // Build FFmpeg filter_complex for status visualization
    // This creates a video with:
    // - Dark background
    // - Title showing "Hub Status Monitor"
    // - Journey ID and platform info
    // - Timeline of checkpoints with pass/fail indicators
    // - Current checkpoint highlight that moves through the video

    const titleText = escapeFFmpegText('Kagami Hub Status Monitor');
    const journeyText = escapeFFmpegText(`Journey: ${recording.journeyId}`);
    const platformText = escapeFFmpegText('Platform: Hub (Coordinator)');

    // Create checkpoint status lines
    const checkpointLines: string[] = [];
    for (let i = 0; i < checkpoints.length; i++) {
      const cp = checkpoints[i]!;
      const status = cp.passed ? '[PASS]' : '[FAIL]';
      const timeStr = `${(cp.videoTimestampMs / 1000).toFixed(1)}s`;
      checkpointLines.push(`${status} ${cp.checkpointName} @ ${timeStr}`);
    }

    // Generate drawtext filters for each checkpoint to appear at the right time
    const filters: string[] = [];

    // Base video with dark navy background
    filters.push(`color=c=0x1a1a2e:s=${width}x${height}:r=${fps}:d=${durationSeconds}`);

    // Add grid pattern overlay for visual interest
    filters.push(`drawbox=x=0:y=0:w=${width}:h=60:c=0x16213e:t=fill`); // Header bar
    filters.push(`drawbox=x=0:y=${height - 40}:w=${width}:h=40:c=0x16213e:t=fill`); // Footer bar

    // Title
    filters.push(
      `drawtext=text='${titleText}':fontcolor=0x00ff88:fontsize=32:x=(w-text_w)/2:y=15`
    );

    // Journey info
    filters.push(
      `drawtext=text='${journeyText}':fontcolor=0xaaaaaa:fontsize=18:x=30:y=80`
    );
    filters.push(
      `drawtext=text='${platformText}':fontcolor=0xaaaaaa:fontsize=18:x=30:y=105`
    );

    // Status label
    filters.push(
      `drawtext=text='Checkpoint Status':fontcolor=0x4ecdc4:fontsize=24:x=30:y=150`
    );

    // Checkpoint status lines (static list)
    const startY = 190;
    const lineHeight = 28;
    for (let i = 0; i < Math.min(checkpointLines.length, 15); i++) {
      const line = escapeFFmpegText(checkpointLines[i]!);
      const color = checkpoints[i]?.passed ? '0x00ff88' : '0xff4757';
      filters.push(
        `drawtext=text='${line}':fontcolor=${color}:fontsize=16:x=50:y=${startY + i * lineHeight}`
      );
    }

    // Progress indicator - shows current time
    filters.push(
      `drawtext=text='Time\\: %{pts\\:hms}':fontcolor=0xffffff:fontsize=14:x=w-150:y=h-30`
    );

    // Total checkpoints summary
    const passedCount = checkpoints.filter((cp) => cp.passed).length;
    const totalCount = checkpoints.length;
    const summaryText = escapeFFmpegText(`Checkpoints: ${passedCount}/${totalCount} passed`);
    const summaryColor = passedCount === totalCount ? '0x00ff88' : '0xffaa00';
    filters.push(
      `drawtext=text='${summaryText}':fontcolor=${summaryColor}:fontsize=18:x=30:y=h-30`
    );

    // Dynamic highlight bar that moves based on time to show progress
    // This creates an animated progress indicator
    const progressBarY = height - 50;
    filters.push(
      `drawbox=x=0:y=${progressBarY}:w='t/${durationSeconds}*${width}':h=5:c=0x00ff88:t=fill`
    );

    // Add checkpoint markers on the progress bar
    for (const cp of checkpoints) {
      const xPos = Math.round((cp.videoTimestampMs / (recording.durationMs ?? 1000)) * width);
      const markerColor = cp.passed ? '0x00ff88' : '0xff4757';
      filters.push(
        `drawbox=x=${xPos - 2}:y=${progressBarY - 5}:w=4:h=15:c=${markerColor}:t=fill`
      );
    }

    // Combine all filters
    const filterComplex = filters.join(',');

    // Build FFmpeg command
    const args = [
      '-y', // Overwrite output
      '-f', 'lavfi',
      '-i', `color=c=0x1a1a2e:s=${width}x${height}:r=${fps}:d=${durationSeconds}`,
      '-vf', filterComplex,
      '-c:v', 'libx264',
      '-preset', 'ultrafast',
      '-crf', '23',
      '-pix_fmt', 'yuv420p',
      outputPath,
    ];

    this.logger.debug({ args }, 'Generating Hub status video with FFmpeg');

    return new Promise((resolve, reject) => {
      const ffmpegProcess = spawn('ffmpeg', args, {
        stdio: ['pipe', 'pipe', 'pipe'],
      });

      let stderr = '';
      ffmpegProcess.stderr?.on('data', (data) => {
        stderr += data.toString();
      });

      ffmpegProcess.on('error', (error) => {
        this.logger.error({ error, stderr }, 'FFmpeg process error');
        reject(error);
      });

      ffmpegProcess.on('close', (code) => {
        if (code === 0) {
          this.logger.info({ outputPath }, 'Hub status video generated successfully');
          resolve();
        } else {
          this.logger.error({ code, stderr }, 'FFmpeg failed to generate Hub status video');
          reject(new Error(`FFmpeg exited with code ${code}: ${stderr}`));
        }
      });
    });
  }

  /**
   * Stop platform-specific recording
   *
   * Different platforms require different shutdown strategies:
   * - iOS: SIGINT to simctl process
   * - Android: Send SIGINT to screenrecord ON THE DEVICE (not adb), then pull file
   * - Desktop: Send 'q' to FFmpeg stdin for graceful shutdown
   */
  private async stopPlatformRecording(
    platform: Platform,
    childProcess: ChildProcess,
    recordingId: string
  ): Promise<void> {
    const recording = this.activeRecordings.get(recordingId);
    const isAndroid = platform === 'android' || platform === 'wearos' || platform === 'androidxr';

    return new Promise((resolve, reject) => {
      // Timeout with SIGKILL as last resort
      const timeout = setTimeout(() => {
        this.logger.warn({ recordingId, platform }, 'Recording stop timeout, forcing kill');
        childProcess.kill('SIGKILL');

        // For Android, also try to kill screenrecord on device
        if (isAndroid) {
          try {
            execSync('adb shell pkill -9 screenrecord 2>/dev/null || true', { timeout: 5000 });
          } catch {
            // Ignore - best effort
          }
        }

        reject(new Error('Recording stop timeout - forced kill'));
      }, FIBONACCI_TIMEOUTS.F7);

      childProcess.on('close', (code) => {
        clearTimeout(timeout);
        this.logger.debug({ recordingId, platform, exitCode: code }, 'Recording process closed');

        // For Android, pull the recording from the device
        if (isAndroid && recording) {
          this.pullAndroidRecording(recording);
        }

        resolve();
      });

      // Send appropriate stop signal based on platform
      if (platform === 'ios' || platform === 'tvos' || platform === 'watchos' || platform === 'visionos') {
        // simctl recordVideo responds to SIGINT for graceful stop
        childProcess.kill('SIGINT');
      } else if (isAndroid) {
        // For Android, we need to signal the screenrecord process ON THE DEVICE
        // The adb shell process will exit when screenrecord exits
        // Send SIGINT (signal 2) to screenrecord via adb
        try {
          execSync('adb shell pkill -2 screenrecord 2>/dev/null || true', { timeout: 5000 });
        } catch {
          // If pkill fails, fall back to killing the local process
          this.logger.warn('pkill screenrecord failed, falling back to SIGINT');
          childProcess.kill('SIGINT');
        }
      } else {
        // FFmpeg responds to 'q' on stdin for graceful shutdown
        // This ensures proper file finalization (moov atom, etc.)
        if (childProcess.stdin && !childProcess.stdin.destroyed) {
          childProcess.stdin.write('q');
          childProcess.stdin.end();
        } else {
          // Fallback to SIGINT if stdin is not available
          childProcess.kill('SIGINT');
        }
      }
    });
  }

  /**
   * Pull Android recording from device to local filesystem
   */
  private pullAndroidRecording(recording: VideoRecording): void {
    const devicePath = ANDROID_RECORDING.devicePath;
    const localPath = recording.path;

    try {
      // Verify the file exists on device before pulling
      const checkResult = execSync(
        `adb shell "[ -f '${devicePath}' ] && echo exists || echo missing"`,
        { encoding: 'utf8', timeout: 5000 }
      ).trim();

      if (checkResult !== 'exists') {
        this.logger.warn({ devicePath }, 'Android recording file not found on device');
        return;
      }

      // Pull the file - adb pull does NOT run through shell, so we only need
      // to escape the local path for the shell that execSync uses.
      // Device path is passed directly to adb, not through a shell on the device.
      // Double-escaping would cause "file not found" errors.
      const escapedLocalPath = this.shellEscape(localPath);
      execSync(`adb pull "${devicePath}" ${escapedLocalPath}`, {
        timeout: 30000, // 30 second timeout for large files
      });

      // Clean up the device file
      // Use simple quoting for device path - it's a fixed path with no special chars
      execSync(`adb shell rm '${devicePath}' 2>/dev/null || true`, {
        timeout: 5000,
      });

      this.logger.info({ localPath }, 'Successfully pulled Android recording');
    } catch (error) {
      this.logger.error({ error, devicePath, localPath }, 'Failed to pull Android recording');
    }
  }

  /**
   * Get recording by ID
   */
  getRecording(recordingId: string): VideoRecording | undefined {
    return this.activeRecordings.get(recordingId);
  }

  /**
   * Get all active recordings
   */
  getActiveRecordings(): VideoRecording[] {
    return Array.from(this.activeRecordings.values()).filter(
      (r) => r.state === 'recording'
    );
  }

  /**
   * Cleanup completed recordings and kill any remaining processes
   *
   * This is called during shutdown to ensure no orphaned processes remain.
   * For Android, we also clean up any screenrecord processes on the device.
   */
  cleanup(): void {
    this.logger.info(
      { activeRecordings: this.recordingProcesses.size },
      'Cleaning up video recorder'
    );

    // Check if any Android recordings were active
    let hadAndroidRecordings = false;
    for (const recording of this.activeRecordings.values()) {
      if (
        recording.state === 'recording' &&
        (recording.platform === 'android' ||
          recording.platform === 'wearos' ||
          recording.platform === 'androidxr')
      ) {
        hadAndroidRecordings = true;
        break;
      }
    }

    // Kill any remaining local processes
    for (const [id, childProcess] of this.recordingProcesses) {
      try {
        // Try graceful shutdown first
        if (childProcess.stdin && !childProcess.stdin.destroyed) {
          childProcess.stdin.write('q');
          childProcess.stdin.end();
        }

        // Give a short grace period then force kill
        setTimeout(() => {
          try {
            childProcess.kill('SIGKILL');
          } catch {
            // Process may have already exited
          }
        }, 1000);
      } catch {
        // Ignore errors during cleanup
      }
      this.recordingProcesses.delete(id);
    }

    // Clean up any orphaned screenrecord processes on Android devices
    if (hadAndroidRecordings) {
      try {
        execSync('adb shell pkill -9 screenrecord 2>/dev/null || true', {
          timeout: 5000,
        });
        // Also clean up any leftover recording files
        execSync(`adb shell rm ${ANDROID_RECORDING.devicePath} 2>/dev/null || true`, {
          timeout: 5000,
        });
      } catch {
        // Best effort cleanup
      }
    }

    // Mark all active recordings as errored
    for (const recording of this.activeRecordings.values()) {
      if (recording.state === 'recording' || recording.state === 'starting') {
        recording.state = 'error';
        recording.error = 'Recording terminated during cleanup';
      }
    }
  }
}

// =============================================================================
// RESULT COLLECTOR
// =============================================================================

/**
 * Collects and aggregates test results with Byzantine quality scoring
 */
export class ResultCollector extends EventEmitter {
  private logger = createChildLogger({ component: 'result-collector' });
  private outputDir: string;
  private results: Map<string, JourneyExecutionResult> = new Map();
  private constellationResults: Map<string, ConstellationResult> = new Map();

  constructor(outputDir: string = DEFAULT_OUTPUT_DIR) {
    super();
    this.outputDir = outputDir;
    this.ensureOutputDir();
  }

  /**
   * Ensure output directories exist
   */
  private ensureOutputDir(): void {
    const resultsDir = path.join(this.outputDir, 'results');
    if (!fs.existsSync(resultsDir)) {
      fs.mkdirSync(resultsDir, { recursive: true });
    }
  }

  /**
   * Calculate Byzantine quality scores from journey results
   */
  calculateQualityScores(
    journey: JourneySpec,
    phaseResults: PhaseExecutionResult[]
  ): Record<QualityDimension, number> {
    const scores: Record<QualityDimension, number> = {
      technical: 100,
      aesthetic: 100,
      accessibility: 100,
      emotional: 100,
      polish: 100,
      delight: 100,
    };

    // Technical: Based on checkpoint pass rate and timing
    const allCheckpoints = phaseResults.flatMap((p) => p.checkpointResults);
    const passedCheckpoints = allCheckpoints.filter((c) => c.success);
    const passRate = passedCheckpoints.length / Math.max(allCheckpoints.length, 1);
    scores.technical = Math.round(passRate * 100);

    // Timing penalties
    const exceededTiming = allCheckpoints.filter(
      (c) => c.durationVsExpected === 'exceeded'
    ).length;
    if (exceededTiming > 0) {
      scores.technical -= Math.min(exceededTiming * 5, 30);
    }

    // Aesthetic: Based on element presence and consistency
    // (Would be enhanced by Gemini analysis)
    const missingElements = allCheckpoints.flatMap((c) => c.elementsMissing);
    if (missingElements.length > 0) {
      scores.aesthetic -= Math.min(missingElements.length * 3, 40);
    }

    // Accessibility: Based on accessibility requirements in checkpoints
    const accessibilityCheckpoints = journey.phases
      .flatMap((p) => p.checkpoints)
      .filter((c) => c.accessibility);
    if (accessibilityCheckpoints.length > 0) {
      const passedAccessibility = allCheckpoints.filter((c) => {
        const spec = accessibilityCheckpoints.find((ac) => ac.id === c.checkpointId);
        return spec && c.success;
      });
      scores.accessibility = Math.round(
        (passedAccessibility.length / accessibilityCheckpoints.length) * 100
      );
    }

    // Emotional: Based on haptic feedback verification and timing
    // (Would be enhanced by user feedback integration)
    const hapticCheckpoints = journey.phases
      .flatMap((p) => p.checkpoints)
      .filter((c) => c.expectedHaptic && c.expectedHaptic !== 'none');
    if (hapticCheckpoints.length > 0) {
      // For now, assume haptics work if checkpoint passes
      const passedHaptic = allCheckpoints.filter((c) => {
        const spec = hapticCheckpoints.find((hc) => hc.id === c.checkpointId);
        return spec && c.success;
      });
      scores.emotional = Math.round(
        (passedHaptic.length / hapticCheckpoints.length) * 100
      );
    }

    // Polish: Based on smooth transitions (timing consistency)
    const timingVariances = allCheckpoints
      .filter((c) => c.durationMs > 0)
      .map((c) => {
        const spec = journey.phases
          .flatMap((p) => p.checkpoints)
          .find((cp) => cp.id === c.checkpointId);
        if (!spec) return 0;
        return Math.abs(c.durationMs - spec.maxDurationMs) / spec.maxDurationMs;
      });
    if (timingVariances.length > 0) {
      const avgVariance = timingVariances.reduce((a, b) => a + b, 0) / timingVariances.length;
      scores.polish = Math.round((1 - Math.min(avgVariance, 1)) * 100);
    }

    // Delight: Based on success rate of optional/enhancement checkpoints
    // (Would be enhanced by Gemini analysis of animations, transitions)
    scores.delight = Math.round((scores.technical + scores.aesthetic + scores.polish) / 3);

    // Clamp all scores to 0-100
    for (const dim of QUALITY_DIMENSIONS) {
      scores[dim] = Math.max(0, Math.min(100, scores[dim]));
    }

    return scores;
  }

  /**
   * Calculate overall quality score
   */
  calculateOverallScore(scores: Record<QualityDimension, number>): number {
    const values = Object.values(scores);
    return Math.round(values.reduce((a, b) => a + b, 0) / values.length);
  }

  /**
   * Collect results from a journey execution
   */
  collectJourneyResult(
    journey: JourneySpec,
    platform: Platform,
    phaseResults: PhaseExecutionResult[],
    recording?: VideoRecording,
    errors: string[] = []
  ): JourneyExecutionResult {
    const qualityScores = this.calculateQualityScores(journey, phaseResults);
    const overallScore = this.calculateOverallScore(qualityScores);

    const totalDuration = phaseResults.reduce((sum, p) => sum + p.durationMs, 0);
    const allCheckpointsPassed = phaseResults.every((p) =>
      p.checkpointResults.every((c) => c.success)
    );

    const result: JourneyExecutionResult = {
      journeyId: journey.id,
      journeyName: journey.name,
      platform,
      success: allCheckpointsPassed && errors.length === 0,
      phaseResults,
      totalDurationMs: totalDuration,
      qualityScores,
      overallScore,
      recording,
      errors,
      executedAt: new Date().toISOString(),
    };

    this.results.set(`${journey.id}_${platform}_${Date.now()}`, result);
    this.logger.info(
      {
        journeyId: journey.id,
        platform,
        success: result.success,
        overallScore,
      },
      'Journey result collected'
    );

    this.emit('result:collected', result);
    return result;
  }

  /**
   * Collect constellation journey result
   */
  collectConstellationResult(result: ConstellationResult): void {
    this.constellationResults.set(`${result.journeyId}_${Date.now()}`, result);
    this.logger.info(
      {
        journeyId: result.journeyId,
        success: result.success,
        devices: result.devicesParticipated,
      },
      'Constellation result collected'
    );

    this.emit('constellation:collected', result);
  }

  /**
   * Get all collected results
   */
  getAllResults(): JourneyExecutionResult[] {
    return Array.from(this.results.values());
  }

  /**
   * Get results for a specific journey
   */
  getResultsForJourney(journeyId: string): JourneyExecutionResult[] {
    return Array.from(this.results.values()).filter(
      (r) => r.journeyId === journeyId
    );
  }

  /**
   * Get results for a specific platform
   */
  getResultsForPlatform(platform: Platform): JourneyExecutionResult[] {
    return Array.from(this.results.values()).filter(
      (r) => r.platform === platform
    );
  }

  /**
   * Generate summary statistics
   */
  generateSummary(): TestSummary {
    const results = Array.from(this.results.values());
    const passed = results.filter((r) => r.success);
    const failed = results.filter((r) => !r.success);

    const allCheckpoints = results.flatMap((r) =>
      r.phaseResults.flatMap((p) => p.checkpointResults)
    );
    const passedCheckpoints = allCheckpoints.filter((c) => c.success);

    const platformSet = new Set<Platform>();
    results.forEach((r) => platformSet.add(r.platform));

    // Average scores by dimension
    const dimensionTotals: Record<QualityDimension, number[]> = {
      technical: [],
      aesthetic: [],
      accessibility: [],
      emotional: [],
      polish: [],
      delight: [],
    };

    for (const result of results) {
      for (const dim of QUALITY_DIMENSIONS) {
        dimensionTotals[dim].push(result.qualityScores[dim]);
      }
    }

    const qualityByDimension: Record<QualityDimension, number> = {
      technical: 0,
      aesthetic: 0,
      accessibility: 0,
      emotional: 0,
      polish: 0,
      delight: 0,
    };

    for (const dim of QUALITY_DIMENSIONS) {
      const values = dimensionTotals[dim];
      qualityByDimension[dim] = values.length > 0
        ? Math.round(values.reduce((a, b) => a + b, 0) / values.length)
        : 0;
    }

    return {
      totalJourneys: results.length,
      journeysPassed: passed.length,
      journeysFailed: failed.length,
      totalCheckpoints: allCheckpoints.length,
      checkpointsPassed: passedCheckpoints.length,
      averageQualityScore: results.length > 0
        ? Math.round(results.reduce((sum, r) => sum + r.overallScore, 0) / results.length)
        : 0,
      qualityByDimension,
      totalDurationMs: results.reduce((sum, r) => sum + r.totalDurationMs, 0),
      platformsTested: Array.from(platformSet),
      generatedAt: new Date().toISOString(),
    };
  }

  /**
   * Save results to JSON file
   */
  saveResults(filename?: string): string {
    const outputPath = path.join(
      this.outputDir,
      'results',
      filename ?? `results_${Date.now()}.json`
    );

    const data = {
      summary: this.generateSummary(),
      journeyResults: Array.from(this.results.values()),
      constellationResults: Array.from(this.constellationResults.values()),
    };

    fs.writeFileSync(outputPath, JSON.stringify(data, null, 2));
    this.logger.info({ outputPath }, 'Results saved');

    return outputPath;
  }

  /**
   * Clear collected results
   */
  clear(): void {
    this.results.clear();
    this.constellationResults.clear();
  }
}

// =============================================================================
// DASHBOARD PUBLISHER
// =============================================================================

/**
 * Publishes real-time updates to the QA Dashboard
 */
export class DashboardPublisher extends EventEmitter {
  private logger = createChildLogger({ component: 'dashboard-publisher' });
  private ws: WebSocket.WebSocket | null = null;
  private url: string | null = null;
  private connected: boolean = false;
  private messageQueue: DashboardUpdate[] = [];
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 5;

  constructor(url?: string) {
    super();
    if (url) {
      this.connect(url);
    }
  }

  /**
   * Connect to dashboard WebSocket
   */
  connect(url: string): void {
    this.url = url;
    this.logger.info({ url }, 'Connecting to dashboard');

    try {
      this.ws = new WebSocket.WebSocket(url);

      this.ws.on('open', () => {
        this.connected = true;
        this.reconnectAttempts = 0;
        this.logger.info('Connected to dashboard');
        this.emit('connected');

        // Flush queued messages
        while (this.messageQueue.length > 0) {
          const msg = this.messageQueue.shift();
          if (msg) {
            this.send(msg);
          }
        }
      });

      this.ws.on('close', () => {
        this.connected = false;
        this.logger.warn('Disconnected from dashboard');
        this.emit('disconnected');
        this.attemptReconnect();
      });

      this.ws.on('error', (error) => {
        this.logger.error({ error }, 'Dashboard WebSocket error');
        this.emit('error', error);
      });
    } catch (error) {
      this.logger.error({ error }, 'Failed to connect to dashboard');
    }
  }

  /**
   * Attempt to reconnect with exponential backoff
   */
  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.logger.error('Max reconnect attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = getFibonacciTimeout(this.reconnectAttempts + 2);
    this.logger.info({ attempt: this.reconnectAttempts, delay }, 'Reconnecting...');

    setTimeout(() => {
      if (this.url) {
        this.connect(this.url);
      }
    }, delay);
  }

  /**
   * Send update to dashboard
   */
  send(update: DashboardUpdate): void {
    if (!this.connected || !this.ws) {
      this.messageQueue.push(update);
      return;
    }

    try {
      this.ws.send(JSON.stringify(update));
      this.logger.debug({ type: update.type, journeyId: update.journeyId }, 'Sent dashboard update');
    } catch (error) {
      this.logger.error({ error }, 'Failed to send dashboard update');
      this.messageQueue.push(update);
    }
  }

  /**
   * Publish journey started event
   */
  publishJourneyStarted(journeyId: string, platform: Platform): void {
    this.send({
      type: 'journey:started',
      journeyId,
      platform,
      data: { startedAt: Date.now() },
      timestamp: new Date().toISOString(),
    });
  }

  /**
   * Publish checkpoint result
   */
  publishCheckpoint(
    journeyId: string,
    platform: Platform,
    checkpoint: CheckpointExecutionResult
  ): void {
    this.send({
      type: 'journey:checkpoint',
      journeyId,
      platform,
      data: checkpoint,
      timestamp: new Date().toISOString(),
    });
  }

  /**
   * Publish phase result
   */
  publishPhase(
    journeyId: string,
    platform: Platform,
    phase: PhaseExecutionResult
  ): void {
    this.send({
      type: 'journey:phase',
      journeyId,
      platform,
      data: phase,
      timestamp: new Date().toISOString(),
    });
  }

  /**
   * Publish journey completed event
   */
  publishJourneyCompleted(result: JourneyExecutionResult): void {
    this.send({
      type: 'journey:completed',
      journeyId: result.journeyId,
      platform: result.platform,
      data: {
        success: result.success,
        overallScore: result.overallScore,
        qualityScores: result.qualityScores,
        totalDurationMs: result.totalDurationMs,
        errors: result.errors,
      },
      timestamp: new Date().toISOString(),
    });
  }

  /**
   * Publish constellation started event
   */
  publishConstellationStarted(
    journeyId: string,
    devices: Platform[]
  ): void {
    this.send({
      type: 'constellation:started',
      journeyId,
      platform: devices[0] ?? 'hub',
      data: { devices, startedAt: Date.now() },
      timestamp: new Date().toISOString(),
    });
  }

  /**
   * Publish constellation completed event
   */
  publishConstellationCompleted(result: ConstellationResult): void {
    this.send({
      type: 'constellation:completed',
      journeyId: result.journeyId,
      platform: result.devicesParticipated[0] ?? 'hub',
      data: {
        success: result.success,
        devicesParticipated: result.devicesParticipated,
        totalDurationMs: result.totalDurationMs,
        syncVerified: result.syncVerified,
        errors: result.errors,
      },
      timestamp: new Date().toISOString(),
    });
  }

  /**
   * Disconnect from dashboard
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.connected = false;
    this.messageQueue = [];
  }
}

// =============================================================================
// TEST HARNESS
// =============================================================================

/**
 * Central Test Harness for orchestrating QA pipeline tests
 *
 * This is the CENTRAL piece that all platforms wire into.
 * It coordinates video recording, test execution, result collection,
 * and Gemini analysis handoff.
 *
 * @example
 * ```typescript
 * const harness = new TestHarness({
 *   outputDir: './qa-output',
 *   dashboardUrl: 'ws://localhost:3848',
 *   prepareForGemini: true,
 * });
 *
 * // Execute single-device journey
 * const result = await harness.executeJourney('J01_MORNING_ROUTINE', 'ios');
 *
 * // Execute constellation journey
 * const constellationResult = await harness.executeConstellationJourney(
 *   'C01_WATCH_TO_PHONE_HANDOFF'
 * );
 *
 * // Get summary
 * const summary = harness.getSummary();
 *
 * // Cleanup
 * await harness.cleanup();
 * ```
 */
export class TestHarness extends EventEmitter {
  private logger = createChildLogger({ component: 'test-harness' });
  private config: TestHarnessConfig;
  private videoRecorder: VideoRecorder;
  private resultCollector: ResultCollector;
  private dashboardPublisher: DashboardPublisher;
  private orchestrator: ConstellationOrchestrator | null = null;
  private performanceTracker: PerformanceTracker | null = null;
  private activeJourneyId: string | null = null;
  private lastPerformanceReport: PerformanceReport | null = null;

  constructor(config: Partial<TestHarnessConfig> = {}) {
    super();

    const outputDir = config.outputDir ?? DEFAULT_OUTPUT_DIR;

    this.config = {
      outputDir,
      video: config.video ?? {
        outputDir,
        format: 'mp4',
        fps: VIDEO_SETTINGS.fps,
        quality: VIDEO_SETTINGS.crf,
        maxDuration: 300,
        captureAudio: false,
      },
      orchestrator: config.orchestrator ?? {
        enableSimulatedMDNS: true,
        verbose: false,
      },
      dashboardUrl: config.dashboardUrl,
      autoPushToDashboard: config.autoPushToDashboard ?? true,
      prepareForGemini: config.prepareForGemini ?? true,
      geminiOutputDir: config.geminiOutputDir ?? path.join(outputDir, 'gemini'),
      verbose: config.verbose ?? false,
      performance: config.performance ?? {
        enabled: true,
        baselinePath: path.join(outputDir, 'data', 'performance-baseline.json'),
        historyPath: path.join(outputDir, 'data', 'performance-history.json'),
        failOnThresholdExceeded: true,
        failOnRegression: false,
        autoGenerateBaseline: true,
      },
    };

    // Ensure directories exist
    this.ensureDirectories();

    // Initialize components
    this.videoRecorder = new VideoRecorder(this.config.video);
    this.resultCollector = new ResultCollector(this.config.outputDir);
    this.dashboardPublisher = new DashboardPublisher(this.config.dashboardUrl);

    // Initialize performance tracker if enabled
    if (this.config.performance.enabled) {
      this.performanceTracker = getPerformanceTracker({
        baselinePath: this.config.performance.baselinePath,
        historyPath: this.config.performance.historyPath,
      });
    }

    // Wire up events
    this.setupEventHandlers();

    this.logger.info({ config: this.config }, 'TestHarness initialized');
  }

  /**
   * Ensure all output directories exist
   */
  private ensureDirectories(): void {
    const dirs = [
      this.config.outputDir,
      path.join(this.config.outputDir, 'videos'),
      path.join(this.config.outputDir, 'results'),
      this.config.geminiOutputDir,
    ];

    for (const dir of dirs) {
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
    }
  }

  /**
   * Setup event handlers between components
   */
  private setupEventHandlers(): void {
    // Forward video recorder events
    this.videoRecorder.on('recording:started', (recording) => {
      this.emit('recording:started', recording);
    });

    this.videoRecorder.on('recording:completed', (recording) => {
      this.emit('recording:completed', recording);
    });

    this.videoRecorder.on('recording:error', (recording) => {
      this.emit('recording:error', recording);
    });

    // Forward result collector events
    this.resultCollector.on('result:collected', (result) => {
      this.emit('result:collected', result);
    });
  }

  /**
   * Get journey specification by ID
   */
  private getJourneySpec(journeyId: string): JourneySpec | undefined {
    return SINGLE_DEVICE_JOURNEYS.find((j) => j.id === journeyId);
  }

  /**
   * Get constellation journey specification by ID
   */
  private getConstellationSpec(journeyId: string): ConstellationJourneySpec | undefined {
    return CONSTELLATION_JOURNEYS.find((j) => j.id === journeyId);
  }

  /**
   * Execute a single-device journey
   *
   * @param journeyId - Journey ID to execute
   * @param platform - Platform to execute on
   * @param deviceId - Optional specific device ID
   * @returns Journey execution result
   */
  async executeJourney(
    journeyId: JourneyId | string,
    platform: Platform,
    deviceId?: string
  ): Promise<JourneyExecutionResult> {
    const journey = this.getJourneySpec(journeyId);
    if (!journey) {
      throw new Error(`Unknown journey: ${journeyId}`);
    }

    // Verify platform is supported
    if (!journey.requiredPlatforms.includes(platform)) {
      throw new Error(
        `Journey ${journeyId} does not support platform ${platform}. ` +
        `Supported: ${journey.requiredPlatforms.join(', ')}`
      );
    }

    this.activeJourneyId = journeyId;
    const done = startTiming(`journey:${journeyId}:${platform}`);
    const journeyStartTime = performance.now();

    this.logger.info({ journeyId, platform, deviceId }, 'Executing journey');

    // Initialize performance tracking for this run
    if (this.performanceTracker && this.config.performance.enabled) {
      await this.performanceTracker.initialize();
      const runId = `${journeyId}_${platform}_${Date.now()}`;
      this.performanceTracker.startRun(runId);
    }

    // Publish to dashboard
    if (this.config.autoPushToDashboard) {
      this.dashboardPublisher.publishJourneyStarted(journeyId, platform);
    }

    // Start video recording
    let recording: VideoRecording | undefined;
    try {
      recording = await this.videoRecorder.startRecording(journeyId, platform, deviceId);
    } catch (error) {
      this.logger.warn({ error }, 'Failed to start video recording, continuing without');
    }

    const phaseResults: PhaseExecutionResult[] = [];
    const errors: string[] = [];

    // Execute each phase
    for (const phase of journey.phases) {
      const phaseResult = await this.executePhase(phase, platform, recording?.id, journeyId);
      phaseResults.push(phaseResult);

      if (!phaseResult.success) {
        errors.push(`Phase ${phase.id} failed: ${phaseResult.errors.join(', ')}`);
      }

      // Publish phase result
      if (this.config.autoPushToDashboard) {
        this.dashboardPublisher.publishPhase(journeyId, platform, phaseResult);
      }
    }

    // Calculate total journey duration
    const totalDurationMs = Math.round(performance.now() - journeyStartTime);

    // Complete performance tracking and generate report
    let performanceReport: PerformanceReport | null = null;
    if (this.performanceTracker && this.config.performance.enabled) {
      performanceReport = this.performanceTracker.completeRun(journeyId, platform, totalDurationMs);
      this.lastPerformanceReport = performanceReport;

      // Log performance summary
      this.logger.info(
        {
          journeyId,
          platform,
          totalDurationMs,
          passed: performanceReport.passed,
          regressionCount: performanceReport.regressions.length,
          thresholdExceeded: performanceReport.summary.checkpointsExceededThreshold,
        },
        'Performance tracking complete'
      );

      // Auto-generate baseline if none exists and configured
      if (
        this.config.performance.autoGenerateBaseline &&
        !this.performanceTracker.hasBaseline() &&
        performanceReport.passed
      ) {
        try {
          await this.performanceTracker.generateBaseline();
          this.logger.info('Auto-generated performance baseline from successful run');
        } catch (error) {
          this.logger.warn({ error }, 'Failed to auto-generate baseline');
        }
      }

      // Save history
      await this.performanceTracker.saveHistory();

      // Emit performance report event
      this.emit('performance:report', performanceReport);

      // Check if we should fail the run
      if (
        this.config.performance.failOnThresholdExceeded &&
        performanceReport.summary.checkpointsExceededThreshold > 0
      ) {
        errors.push(
          `Performance: ${performanceReport.summary.checkpointsExceededThreshold} ` +
          `checkpoint(s) exceeded hard threshold`
        );
      }

      if (
        this.config.performance.failOnRegression &&
        performanceReport.regressions.length > 0
      ) {
        errors.push(
          `Performance: ${performanceReport.regressions.length} regression(s) detected`
        );
      }
    }

    // Stop video recording
    if (recording) {
      try {
        recording = await this.videoRecorder.stopRecording(recording.id);
      } catch (error) {
        this.logger.warn({ error }, 'Failed to stop video recording');
      }
    }

    // Collect results
    const result = this.resultCollector.collectJourneyResult(
      journey,
      platform,
      phaseResults,
      recording,
      errors
    );

    // Publish completion
    if (this.config.autoPushToDashboard) {
      this.dashboardPublisher.publishJourneyCompleted(result);
    }

    // Prepare for Gemini analysis
    if (this.config.prepareForGemini && recording && recording.state === 'completed') {
      this.prepareGeminiHandoff(journey, platform, result, recording);
    }

    done();
    this.activeJourneyId = null;
    this.emit('journey:completed', result);

    return result;
  }

  /**
   * Execute a single phase
   */
  private async executePhase(
    phase: Phase,
    platform: Platform,
    recordingId?: string,
    journeyId?: string
  ): Promise<PhaseExecutionResult> {
    const phaseStart = Date.now();
    const checkpointResults: CheckpointExecutionResult[] = [];
    const errors: string[] = [];

    this.logger.debug({ phaseId: phase.id, platform }, 'Executing phase');

    for (const checkpoint of phase.checkpoints) {
      const result = await this.executeCheckpoint(checkpoint, platform, recordingId, journeyId);
      checkpointResults.push(result);

      if (!result.success) {
        // Include detailed error message if available (e.g., timing exceeded)
        if (result.error) {
          errors.push(result.error);
        } else if (result.failedDueToTiming) {
          errors.push(
            `Checkpoint ${checkpoint.id} exceeded max duration: ` +
            `${result.durationMs}ms > ${result.maxDurationMs}ms`
          );
        } else {
          errors.push(`Checkpoint ${checkpoint.id} failed`);
        }
      }

      // Publish checkpoint
      if (this.config.autoPushToDashboard && this.activeJourneyId) {
        this.dashboardPublisher.publishCheckpoint(
          this.activeJourneyId,
          platform,
          result
        );
      }
    }

    return {
      phaseId: phase.id,
      phaseName: phase.name,
      success: errors.length === 0,
      checkpointResults,
      durationMs: Date.now() - phaseStart,
      errors,
    };
  }

  /**
   * Execute a single checkpoint
   *
   * This is a simplified implementation that can be overridden
   * by platform-specific harness implementations.
   *
   * TIMING VALIDATION: Checkpoints that exceed their maxDurationMs will FAIL.
   * This enforces the canonical timing specifications from canonical-journeys.ts.
   */
  private async executeCheckpoint(
    checkpoint: Checkpoint,
    platform: Platform,
    recordingId?: string,
    journeyId?: string
  ): Promise<CheckpointExecutionResult> {
    // Use performance.now() for higher precision timing
    const checkpointStart = performance.now();

    // Record timestamp in video
    if (recordingId) {
      this.videoRecorder.recordCheckpoint(recordingId, checkpoint, true);
    }

    // Simulate checkpoint execution
    // In a real implementation, this would interact with the actual device
    // using the platform parameter to select the appropriate driver
    await this.sleep(getFibonacciTimeout(2)); // Simulate some work

    // Calculate duration with high precision
    const checkpointEnd = performance.now();
    const durationMs = Math.round(checkpointEnd - checkpointStart);

    // CRITICAL: Validate against canonical maxDurationMs
    const timingExceeded = durationMs > checkpoint.maxDurationMs;
    const durationVsExpected = timingExceeded ? 'exceeded' : 'within';

    // Record measurement in performance tracker
    if (this.performanceTracker && this.config.performance.enabled && journeyId) {
      this.performanceTracker.recordCheckpoint(
        journeyId,
        checkpoint.id,
        platform,
        durationMs
      );
    }

    // Build error message if timing exceeded
    let timingError: string | undefined;
    if (timingExceeded) {
      timingError = `Checkpoint ${checkpoint.id} exceeded max duration: ` +
        `${durationMs}ms > ${checkpoint.maxDurationMs}ms (exceeded by ${durationMs - checkpoint.maxDurationMs}ms)`;
      this.logger.warn(
        {
          checkpointId: checkpoint.id,
          durationMs,
          maxDurationMs: checkpoint.maxDurationMs,
          exceededBy: durationMs - checkpoint.maxDurationMs,
        },
        'Checkpoint exceeded maximum duration - FAILING'
      );
    }

    // For the base implementation, we assume element checks pass
    // Platform-specific harnesses should override this
    // BUT timing is strictly enforced
    const result: CheckpointExecutionResult = {
      checkpointId: checkpoint.id,
      checkpointName: checkpoint.name,
      success: !timingExceeded, // FAIL if timing exceeded
      elementsFound: checkpoint.requiredElements,
      elementsMissing: [],
      durationMs,
      maxDurationMs: checkpoint.maxDurationMs,
      durationVsExpected,
      failedDueToTiming: timingExceeded,
      videoTimestampMs: recordingId
        ? Date.now() - (this.videoRecorder.getRecording(recordingId)?.startedAt ?? Date.now())
        : undefined,
      actualState: undefined,
      // Only set error property if there's an actual error (exactOptionalPropertyTypes compliance)
      ...(timingError !== undefined ? { error: timingError } : {}),
    };

    // Update video recording checkpoint with actual pass/fail status
    if (recordingId && timingExceeded) {
      // Re-record with correct pass/fail status for video correlation
      this.videoRecorder.recordCheckpoint(recordingId, checkpoint, false);
    }

    this.logger.debug(
      {
        checkpointId: checkpoint.id,
        success: result.success,
        durationMs,
        maxDurationMs: checkpoint.maxDurationMs,
        timingExceeded,
      },
      'Checkpoint executed'
    );

    return result;
  }

  /**
   * Execute a constellation journey across multiple devices
   *
   * @param journeyId - Constellation journey ID
   * @returns Constellation result
   */
  async executeConstellationJourney(journeyId: string): Promise<ConstellationResult> {
    const journey = this.getConstellationSpec(journeyId);
    if (!journey) {
      throw new Error(`Unknown constellation journey: ${journeyId}`);
    }

    const done = startTiming(`constellation:${journeyId}`);
    this.logger.info({ journeyId, devices: journey.devices.length }, 'Executing constellation journey');

    // Initialize orchestrator if not already done
    if (!this.orchestrator) {
      this.orchestrator = new ConstellationOrchestrator(this.config.orchestrator);
    }

    // Publish start
    if (this.config.autoPushToDashboard) {
      this.dashboardPublisher.publishConstellationStarted(
        journeyId,
        journey.devices.map((d) => d.platform)
      );
    }

    // Start video recording on each device
    const recordings = new Map<Platform, VideoRecording>();
    for (const device of journey.devices) {
      try {
        const recording = await this.videoRecorder.startRecording(
          journeyId,
          device.platform
        );
        recordings.set(device.platform, recording);
      } catch (error) {
        this.logger.warn(
          { platform: device.platform, error },
          'Failed to start recording for device'
        );
      }
    }

    // Discover devices
    await this.orchestrator.discoverDevices();

    // Execute the constellation
    const result = await this.orchestrator.startConstellation(journeyId);

    // Stop all recordings
    for (const [platform, recording] of recordings) {
      try {
        await this.videoRecorder.stopRecording(recording.id);
      } catch (error) {
        this.logger.warn({ platform, error }, 'Failed to stop recording');
      }
    }

    // Collect result
    this.resultCollector.collectConstellationResult(result);

    // Publish completion
    if (this.config.autoPushToDashboard) {
      this.dashboardPublisher.publishConstellationCompleted(result);
    }

    done();
    this.emit('constellation:completed', result);

    return result;
  }

  /**
   * Prepare video and metadata for Gemini analysis
   */
  private prepareGeminiHandoff(
    journey: JourneySpec,
    platform: Platform,
    result: JourneyExecutionResult,
    recording: VideoRecording
  ): void {
    const handoffDir = path.join(this.config.geminiOutputDir, result.journeyId, platform);
    if (!fs.existsSync(handoffDir)) {
      fs.mkdirSync(handoffDir, { recursive: true });
    }

    // Generate analysis prompts based on journey
    const analysisPrompts = this.generateAnalysisPrompts(journey, platform);

    // Collect expected elements
    const expectedElements = journey.phases.flatMap((p) =>
      p.checkpoints.flatMap((c) => c.requiredElements)
    );

    // Extract timing metrics from checkpoint results for Gemini analysis
    const timingMetrics: CheckpointTimingMetrics[] = result.phaseResults.flatMap((phase) =>
      phase.checkpointResults.map((cp) => ({
        checkpointId: cp.checkpointId,
        checkpointName: cp.checkpointName,
        actualDurationMs: cp.durationMs,
        maxDurationMs: cp.maxDurationMs,
        exceeded: cp.failedDueToTiming,
        exceededByMs: cp.durationMs - cp.maxDurationMs,
        percentageOfMax: Math.round((cp.durationMs / cp.maxDurationMs) * 100),
      }))
    );

    // Calculate timing summary
    const checkpointsExceededTiming = timingMetrics.filter((m) => m.exceeded).length;
    const avgPercentage = timingMetrics.length > 0
      ? Math.round(timingMetrics.reduce((sum, m) => sum + m.percentageOfMax, 0) / timingMetrics.length)
      : 0;

    // Find slowest and fastest checkpoints (by percentage of max used)
    let slowestCheckpoint: string | null = null;
    let fastestCheckpoint: string | null = null;
    if (timingMetrics.length > 0) {
      const sorted = [...timingMetrics].sort((a, b) => b.percentageOfMax - a.percentageOfMax);
      slowestCheckpoint = sorted[0]?.checkpointId ?? null;
      fastestCheckpoint = sorted[sorted.length - 1]?.checkpointId ?? null;
    }

    const timingSummary = {
      totalCheckpoints: timingMetrics.length,
      checkpointsExceededTiming,
      averagePercentageOfMax: avgPercentage,
      slowestCheckpoint,
      fastestCheckpoint,
    };

    const handoff: GeminiAnalysisHandoff = {
      videoPath: recording.path,
      journeyId: journey.id,
      platform,
      checkpointTimestamps: recording.checkpointTimestamps,
      executionSummary: {
        success: result.success,
        totalDurationMs: result.totalDurationMs,
        qualityScores: result.qualityScores,
        errors: result.errors,
      },
      timingMetrics,
      timingSummary,
      analysisPrompts,
      expectedElements,
      createdAt: new Date().toISOString(),
    };

    const handoffPath = path.join(handoffDir, `handoff_${Date.now()}.json`);
    fs.writeFileSync(handoffPath, JSON.stringify(handoff, null, 2));

    this.logger.info({ handoffPath, videoPath: recording.path }, 'Gemini handoff prepared');
    this.emit('gemini:handoff', handoff);
  }

  /**
   * Generate analysis prompts for Gemini based on journey
   */
  private generateAnalysisPrompts(journey: JourneySpec, platform: Platform): string[] {
    const prompts: string[] = [];

    // Base prompt
    prompts.push(
      `Analyze this ${platform} app recording for the "${journey.name}" user journey. ` +
      `Look for UI issues, missing elements, animation problems, and accessibility concerns.`
    );

    // Technical prompt
    prompts.push(
      `Verify that all required UI elements are present and functional: ` +
      journey.phases.flatMap((p) =>
        p.checkpoints.flatMap((c) => c.requiredElements)
      ).join(', ')
    );

    // Aesthetic prompt
    prompts.push(
      `Evaluate the visual design consistency, color harmony, typography, and spacing. ` +
      `Look for any visual glitches or misalignments.`
    );

    // Accessibility prompt
    prompts.push(
      `Check accessibility: Are touch targets at least 44x44 points? ` +
      `Is there sufficient color contrast? Are labels present for screen readers?`
    );

    // Animation prompt
    prompts.push(
      `Analyze animations and transitions. Are they smooth? ` +
      `Do they follow natural timing (Fibonacci: 89, 144, 233, 377, 610, 987ms)? ` +
      `Are there any janky or stuttering animations?`
    );

    // Platform-specific prompts
    if (platform === 'ios') {
      prompts.push(
        `Check for iOS Human Interface Guidelines compliance: ` +
        `Safe area handling, system colors usage, SF Symbols, and navigation patterns.`
      );
    } else if (platform === 'android') {
      prompts.push(
        `Check for Material Design compliance: ` +
        `Proper elevation, ripple effects, bottom navigation, and Material components.`
      );
    } else if (platform === 'watchos') {
      prompts.push(
        `Check for watchOS guidelines: Glanceable content, crown usage, ` +
        `complications, and appropriate information density.`
      );
    } else if (platform === 'visionos') {
      prompts.push(
        `Check for visionOS spatial design: Window placement, depth usage, ` +
        `gaze target sizing, and hand tracking feedback.`
      );
    }

    return prompts;
  }

  /**
   * Get summary statistics
   */
  getSummary(): TestSummary {
    return this.resultCollector.generateSummary();
  }

  /**
   * Get all collected results
   */
  getResults(): JourneyExecutionResult[] {
    return this.resultCollector.getAllResults();
  }

  /**
   * Save all results to file
   */
  saveResults(filename?: string): string {
    return this.resultCollector.saveResults(filename);
  }

  /**
   * Export results in dashboard-consumable format
   */
  exportForDashboard(): {
    summary: TestSummary;
    results: JourneyExecutionResult[];
    timestamp: string;
  } {
    return {
      summary: this.getSummary(),
      results: this.getResults(),
      timestamp: new Date().toISOString(),
    };
  }

  /**
   * Get the last performance report
   */
  getLastPerformanceReport(): PerformanceReport | null {
    return this.lastPerformanceReport;
  }

  /**
   * Get the performance tracker instance
   */
  getPerformanceTracker(): PerformanceTracker | null {
    return this.performanceTracker;
  }

  /**
   * Generate and save a performance baseline from current history
   * Call this after a successful test run to establish baseline
   */
  async generatePerformanceBaseline(options?: {
    gitCommit?: string;
    gitBranch?: string;
  }): Promise<void> {
    if (!this.performanceTracker) {
      throw new Error('Performance tracking is not enabled');
    }

    await this.performanceTracker.generateBaseline(options);
    this.logger.info('Performance baseline generated');
  }

  /**
   * Update the performance baseline with recent history
   * Use onlyImproved=true to only update if performance has improved
   */
  async updatePerformanceBaseline(options?: {
    onlyImproved?: boolean;
    gitCommit?: string;
  }): Promise<void> {
    if (!this.performanceTracker) {
      throw new Error('Performance tracking is not enabled');
    }

    await this.performanceTracker.updateBaseline(options);
    this.logger.info('Performance baseline updated');
  }

  /**
   * Get historical trend for a checkpoint
   */
  getCheckpointTrend(
    journeyId: string,
    checkpointId: string,
    platform: Platform,
    limit: number = 50
  ): { timestamp: string; durationMs: number; passed: boolean }[] {
    if (!this.performanceTracker) {
      return [];
    }
    return this.performanceTracker.getCheckpointTrend(journeyId, checkpointId, platform, limit);
  }

  /**
   * Get historical trend for a journey
   */
  getJourneyTrend(
    journeyId: string,
    platform: Platform,
    limit: number = 50
  ): { timestamp: string; durationMs: number; passed: boolean }[] {
    if (!this.performanceTracker) {
      return [];
    }
    return this.performanceTracker.getJourneyTrend(journeyId, platform, limit);
  }

  /**
   * Format the last performance report as human-readable text
   */
  formatPerformanceReport(): string {
    if (!this.lastPerformanceReport || !this.performanceTracker) {
      return 'No performance report available';
    }
    return this.performanceTracker.formatReport(this.lastPerformanceReport);
  }

  /**
   * Cleanup all resources
   */
  async cleanup(): Promise<void> {
    this.logger.info('Cleaning up test harness');

    // Cleanup video recorder
    this.videoRecorder.cleanup();

    // Cleanup orchestrator
    if (this.orchestrator) {
      await this.orchestrator.cleanup();
      this.orchestrator = null;
    }

    // Disconnect dashboard
    this.dashboardPublisher.disconnect();

    this.emit('cleanup:complete');
  }

  /**
   * Sleep utility
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

// =============================================================================
// FACTORY FUNCTIONS
// =============================================================================

let harnessInstance: TestHarness | null = null;

/**
 * Get or create the global test harness instance
 */
export function getTestHarness(config?: Partial<TestHarnessConfig>): TestHarness {
  if (!harnessInstance) {
    harnessInstance = new TestHarness(config);
  }
  return harnessInstance;
}

/**
 * Reset the global test harness instance
 */
export async function resetTestHarness(): Promise<void> {
  if (harnessInstance) {
    await harnessInstance.cleanup();
    harnessInstance = null;
  }
}

// =============================================================================
// EXPORTS
// =============================================================================

export {
  QUALITY_DIMENSIONS,
  VIDEO_SETTINGS,
  DEFAULT_OUTPUT_DIR,
};

export type { QualityDimension };
