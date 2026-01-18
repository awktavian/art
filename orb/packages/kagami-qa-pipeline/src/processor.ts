/**
 * @fileoverview Video Processor - Frame extraction and video segment generation
 *
 * This module handles all video processing operations including:
 * - Frame extraction at configurable intervals
 * - Video segment generation for chunk-based analysis
 * - Thumbnail generation for quick previews
 * - Video metadata extraction
 *
 * Uses FFmpeg for video processing and Sharp for image optimization.
 */

import { promises as fs } from 'node:fs';
import { existsSync, createWriteStream } from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import ffmpeg from 'fluent-ffmpeg';
import sharp from 'sharp';
import { createChildLogger, startTiming } from './logger.js';
import { getConfig } from './config.js';
import type { ExtractedFrame, VideoSegment } from './types.js';

const log = createChildLogger({ component: 'processor' });

/**
 * Video metadata information
 */
export interface VideoMetadata {
  /** Duration in seconds */
  duration: number;
  /** Width in pixels */
  width: number;
  /** Height in pixels */
  height: number;
  /** Frame rate (fps) */
  frameRate: number;
  /** Video codec */
  codec: string;
  /** File size in bytes */
  fileSize: number;
  /** Bitrate in bps */
  bitrate: number;
}

/**
 * Options for frame extraction
 */
export interface FrameExtractionOptions {
  /** Interval between frames in seconds */
  interval?: number;
  /** Maximum number of frames to extract */
  maxFrames?: number;
  /** Output directory for frames */
  outputDir?: string;
  /** Output image format */
  format?: 'jpg' | 'png' | 'webp';
  /** Image quality (1-100) */
  quality?: number;
  /** Maximum dimension for frame images */
  maxDimension?: number;
}

/**
 * Options for video segment extraction
 */
export interface SegmentOptions {
  /** Segment duration in seconds */
  segmentDuration?: number;
  /** Output directory for segments */
  outputDir?: string;
  /** Include frames for each segment */
  includeFrames?: boolean;
  /** Frame extraction options for segments */
  frameOptions?: FrameExtractionOptions;
}

/**
 * Video Processor class
 *
 * Handles all video processing operations for the QA pipeline.
 *
 * @example
 * ```typescript
 * const processor = new VideoProcessor();
 *
 * // Get video metadata
 * const metadata = await processor.getMetadata('/path/to/video.mp4');
 *
 * // Extract frames
 * const frames = await processor.extractFrames('/path/to/video.mp4', {
 *   interval: 1,
 *   maxFrames: 50
 * });
 *
 * // Generate segments
 * const segments = await processor.generateSegments('/path/to/video.mp4', {
 *   segmentDuration: 30,
 *   includeFrames: true
 * });
 * ```
 */
export class VideoProcessor {
  private config = getConfig();
  private processingJobs = new Map<string, AbortController>();

  /**
   * Get metadata from a video file
   *
   * @param videoPath - Path to the video file
   * @returns Video metadata
   */
  async getMetadata(videoPath: string): Promise<VideoMetadata> {
    const done = startTiming('get-metadata');

    return new Promise((resolve, reject) => {
      ffmpeg.ffprobe(videoPath, (err, metadata) => {
        done();

        if (err) {
          log.error({ err, videoPath }, 'Failed to get video metadata');
          reject(new Error(`Failed to get video metadata: ${err.message}`));
          return;
        }

        const videoStream = metadata.streams.find(s => s.codec_type === 'video');
        if (!videoStream) {
          reject(new Error('No video stream found in file'));
          return;
        }

        const duration = metadata.format.duration ?? 0;
        const fileSize = metadata.format.size ?? 0;
        const bitrate = metadata.format.bit_rate ?? 0;

        // Parse frame rate (can be "30/1" format)
        let frameRate = 30;
        if (videoStream.r_frame_rate) {
          const parts = videoStream.r_frame_rate.split('/');
          if (parts.length === 2) {
            frameRate = parseInt(parts[0] ?? '30', 10) / parseInt(parts[1] ?? '1', 10);
          } else {
            frameRate = parseFloat(parts[0] ?? '30');
          }
        }

        const result: VideoMetadata = {
          duration,
          width: videoStream.width ?? 0,
          height: videoStream.height ?? 0,
          frameRate,
          codec: videoStream.codec_name ?? 'unknown',
          fileSize,
          bitrate
        };

        log.debug({ videoPath, ...result }, 'Video metadata extracted');
        resolve(result);
      });
    });
  }

  /**
   * Extract frames from a video at specified intervals
   *
   * @param videoPath - Path to the video file
   * @param options - Frame extraction options
   * @returns Array of extracted frame information
   */
  async extractFrames(
    videoPath: string,
    options: FrameExtractionOptions = {}
  ): Promise<ExtractedFrame[]> {
    const done = startTiming('extract-frames');
    const jobId = randomUUID();
    const controller = new AbortController();
    this.processingJobs.set(jobId, controller);

    try {
      // Validate video file exists
      if (!existsSync(videoPath)) {
        throw new Error(`Video file not found: ${videoPath}`);
      }

      // Get video metadata
      const metadata = await this.getMetadata(videoPath);

      // Configure options with defaults
      const interval = options.interval ?? this.config.processing.frameInterval;
      const maxFrames = options.maxFrames ?? this.config.processing.maxFramesPerVideo;
      const format = options.format ?? 'jpg';
      const quality = options.quality ?? 85;
      const maxDimension = options.maxDimension ?? 1920;

      // Set up output directory
      const outputDir = options.outputDir ?? path.join(
        this.config.processing.tempDir,
        'frames',
        jobId
      );
      await fs.mkdir(outputDir, { recursive: true });

      // Calculate frame timestamps
      const timestamps: number[] = [];
      let currentTime = 0;
      while (currentTime <= metadata.duration && timestamps.length < maxFrames) {
        timestamps.push(currentTime);
        currentTime += interval;
      }

      log.info(
        { videoPath, frameCount: timestamps.length, interval, outputDir },
        'Extracting frames from video'
      );

      // Extract frames
      const frames: ExtractedFrame[] = [];
      for (let i = 0; i < timestamps.length; i++) {
        if (controller.signal.aborted) {
          throw new Error('Frame extraction cancelled');
        }

        const timestamp = timestamps[i]!;
        const outputPath = path.join(outputDir, `frame_${i.toString().padStart(5, '0')}.${format}`);

        await this.extractSingleFrame(
          videoPath,
          timestamp,
          outputPath,
          { quality, maxDimension, format }
        );

        const stats = await fs.stat(outputPath);
        const imageInfo = await sharp(outputPath).metadata();

        frames.push({
          index: i,
          timestamp,
          path: outputPath,
          width: imageInfo.width ?? metadata.width,
          height: imageInfo.height ?? metadata.height,
          size: stats.size
        });

        // Log progress every 10 frames
        if ((i + 1) % 10 === 0) {
          log.debug({ progress: i + 1, total: timestamps.length }, 'Frame extraction progress');
        }
      }

      done();
      log.info(
        { videoPath, framesExtracted: frames.length, outputDir },
        'Frame extraction complete'
      );

      return frames;
    } finally {
      this.processingJobs.delete(jobId);
    }
  }

  /**
   * Extract a single frame at a specific timestamp
   *
   * @param videoPath - Path to the video file
   * @param timestamp - Timestamp in seconds
   * @param outputPath - Output path for the frame image
   * @param options - Image options
   */
  private async extractSingleFrame(
    videoPath: string,
    timestamp: number,
    outputPath: string,
    options: { quality: number; maxDimension: number; format: string }
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      ffmpeg(videoPath)
        .seekInput(timestamp)
        .frames(1)
        .outputOptions([
          '-vf', `scale='min(${options.maxDimension},iw)':'-2'`,
          '-q:v', Math.ceil((100 - options.quality) / 10).toString()
        ])
        .output(outputPath)
        .on('end', () => resolve())
        .on('error', (err) => reject(new Error(`Failed to extract frame: ${err.message}`)))
        .run();
    });
  }

  /**
   * Generate video segments for chunk-based analysis
   *
   * @param videoPath - Path to the video file
   * @param options - Segment generation options
   * @returns Array of video segments
   */
  async generateSegments(
    videoPath: string,
    options: SegmentOptions = {}
  ): Promise<VideoSegment[]> {
    const done = startTiming('generate-segments');
    const jobId = randomUUID();

    try {
      const metadata = await this.getMetadata(videoPath);

      const segmentDuration = options.segmentDuration ?? 30;
      const includeFrames = options.includeFrames ?? true;
      const outputDir = options.outputDir ?? path.join(
        this.config.processing.tempDir,
        'segments',
        jobId
      );
      await fs.mkdir(outputDir, { recursive: true });

      // Calculate segment boundaries
      const segments: VideoSegment[] = [];
      let segmentStart = 0;
      let segmentIndex = 0;

      while (segmentStart < metadata.duration) {
        const segmentEnd = Math.min(segmentStart + segmentDuration, metadata.duration);
        const segmentPath = path.join(
          outputDir,
          `segment_${segmentIndex.toString().padStart(3, '0')}.mp4`
        );

        log.debug(
          { segmentIndex, startTime: segmentStart, endTime: segmentEnd },
          'Extracting video segment'
        );

        // Extract segment
        await this.extractSegment(videoPath, segmentStart, segmentEnd - segmentStart, segmentPath);

        // Extract frames for this segment if requested
        let frames: ExtractedFrame[] = [];
        if (includeFrames) {
          const frameDir = path.join(outputDir, `segment_${segmentIndex}_frames`);
          frames = await this.extractFrames(segmentPath, {
            ...options.frameOptions,
            outputDir: frameDir
          });
        }

        segments.push({
          startTime: segmentStart,
          endTime: segmentEnd,
          path: segmentPath,
          frames
        });

        segmentStart = segmentEnd;
        segmentIndex++;
      }

      done();
      log.info(
        { videoPath, segmentCount: segments.length, totalDuration: metadata.duration },
        'Segment generation complete'
      );

      return segments;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      log.error({ error: message, videoPath }, 'Failed to generate segments');
      throw error;
    }
  }

  /**
   * Extract a video segment
   *
   * @param videoPath - Source video path
   * @param startTime - Start time in seconds
   * @param duration - Duration in seconds
   * @param outputPath - Output path for segment
   */
  private async extractSegment(
    videoPath: string,
    startTime: number,
    duration: number,
    outputPath: string
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      ffmpeg(videoPath)
        .seekInput(startTime)
        .duration(duration)
        .outputOptions([
          '-c:v', 'libx264',
          '-preset', 'fast',
          '-crf', '23',
          '-c:a', 'aac',
          '-b:a', '128k'
        ])
        .output(outputPath)
        .on('end', () => resolve())
        .on('error', (err) => reject(new Error(`Failed to extract segment: ${err.message}`)))
        .run();
    });
  }

  /**
   * Generate a thumbnail for a video
   *
   * @param videoPath - Path to the video file
   * @param outputPath - Output path for thumbnail
   * @param options - Thumbnail options
   */
  async generateThumbnail(
    videoPath: string,
    outputPath?: string,
    options: { timestamp?: number; width?: number; height?: number } = {}
  ): Promise<string> {
    const metadata = await this.getMetadata(videoPath);
    const timestamp = options.timestamp ?? metadata.duration / 2;
    const width = options.width ?? 320;
    const height = options.height ?? 180;

    const output = outputPath ?? path.join(
      this.config.processing.tempDir,
      'thumbnails',
      `${path.basename(videoPath, path.extname(videoPath))}_thumb.jpg`
    );

    await fs.mkdir(path.dirname(output), { recursive: true });

    return new Promise((resolve, reject) => {
      ffmpeg(videoPath)
        .seekInput(timestamp)
        .frames(1)
        .size(`${width}x${height}`)
        .output(output)
        .on('end', () => {
          log.debug({ videoPath, thumbnail: output, timestamp }, 'Thumbnail generated');
          resolve(output);
        })
        .on('error', (err) => reject(new Error(`Failed to generate thumbnail: ${err.message}`)))
        .run();
    });
  }

  /**
   * Clean up temporary files for a job
   *
   * @param jobId - Job ID to clean up
   */
  async cleanup(jobId: string): Promise<void> {
    const framesDir = path.join(this.config.processing.tempDir, 'frames', jobId);
    const segmentsDir = path.join(this.config.processing.tempDir, 'segments', jobId);

    try {
      await fs.rm(framesDir, { recursive: true, force: true });
      await fs.rm(segmentsDir, { recursive: true, force: true });
      log.debug({ jobId }, 'Temporary files cleaned up');
    } catch (error) {
      log.warn({ error, jobId }, 'Failed to clean up temporary files');
    }
  }

  /**
   * Cancel an in-progress processing job
   *
   * @param jobId - Job ID to cancel
   */
  cancelJob(jobId: string): boolean {
    const controller = this.processingJobs.get(jobId);
    if (controller) {
      controller.abort();
      this.processingJobs.delete(jobId);
      log.info({ jobId }, 'Processing job cancelled');
      return true;
    }
    return false;
  }

  /**
   * Validate that a video file is suitable for analysis
   *
   * @param videoPath - Path to the video file
   * @returns Validation result with any issues
   */
  async validateVideo(videoPath: string): Promise<{
    valid: boolean;
    issues: string[];
    metadata?: VideoMetadata;
  }> {
    const issues: string[] = [];

    try {
      // Check file exists
      if (!existsSync(videoPath)) {
        return { valid: false, issues: ['Video file not found'] };
      }

      // Check file size
      const stats = await fs.stat(videoPath);
      const maxSizeBytes = this.config.processing.maxVideoSizeMb * 1024 * 1024;
      if (stats.size > maxSizeBytes) {
        issues.push(`Video file too large (${(stats.size / 1024 / 1024).toFixed(1)}MB > ${this.config.processing.maxVideoSizeMb}MB)`);
      }

      // Get and validate metadata
      const metadata = await this.getMetadata(videoPath);

      if (metadata.duration === 0) {
        issues.push('Video has zero duration');
      }

      if (metadata.width === 0 || metadata.height === 0) {
        issues.push('Invalid video dimensions');
      }

      if (metadata.duration > 3600) {
        issues.push('Video longer than 1 hour may take significant time to analyze');
      }

      return {
        valid: issues.filter(i => !i.includes('may take')).length === 0,
        issues,
        metadata
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      return {
        valid: false,
        issues: [`Failed to validate video: ${message}`]
      };
    }
  }
}

/**
 * Singleton instance for convenient access
 */
let processorInstance: VideoProcessor | null = null;

/**
 * Get the shared VideoProcessor instance
 */
export function getProcessor(): VideoProcessor {
  if (!processorInstance) {
    processorInstance = new VideoProcessor();
  }
  return processorInstance;
}

/**
 * Reset the processor instance (for testing)
 */
export function resetProcessor(): void {
  processorInstance = null;
}
