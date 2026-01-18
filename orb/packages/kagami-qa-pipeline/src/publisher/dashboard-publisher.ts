/**
 * Dashboard Result Publisher
 *
 * Connects the test harness to the QA Dashboard web app.
 * Provides real-time WebSocket updates and REST API integration
 * for publishing test results, video URLs, and analysis data.
 *
 * Colony: Crystal (e7) -- Verification & Polish
 * h(x) >= 0. Always.
 */

import { EventEmitter } from 'events';
import * as fs from 'node:fs/promises';
import * as path from 'node:path';
import { createChildLogger } from '../logger.js';
import { Platform } from '../journeys/canonical-journeys.js';
import type {
  AnalysisResult,
  Severity,
  IssueCategory,
} from '../types.js';
import type {
  PhaseResult,
  ConstellationResult,
} from '../orchestrator/constellation-orchestrator.js';

// =============================================================================
// FIBONACCI BACKOFF
// =============================================================================

/**
 * Fibonacci sequence for backoff intervals (milliseconds)
 */
const FIBONACCI_BACKOFF = [89, 144, 233, 377, 610, 987, 1597, 2584, 4181, 6765];

/**
 * Get Fibonacci backoff delay for retry attempt
 */
function getFibonacciBackoff(attempt: number): number {
  const index = Math.min(attempt, FIBONACCI_BACKOFF.length - 1);
  return FIBONACCI_BACKOFF[index] ?? 6765;
}

// =============================================================================
// TYPES
// =============================================================================

/**
 * Test event types for dashboard updates
 */
export type TestEventType =
  | 'test_started'
  | 'checkpoint_passed'
  | 'checkpoint_failed'
  | 'test_completed'
  | 'analysis_complete'
  | 'constellation_sync';

/**
 * WebSocket connection state
 */
export type ConnectionState =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'error';

/**
 * Byzantine quality dimension scores
 */
export interface ByzantineScores {
  technical: number;
  aesthetic: number;
  accessibility: number;
  emotional: number;
  polish: number;
  delight: number;
  overall: number;
}

/**
 * Video timestamp marker for scrubbing
 */
export interface VideoTimestamp {
  /** Timestamp in seconds */
  time: number;
  /** Label for this marker */
  label: string;
  /** Associated checkpoint ID */
  checkpointId?: string;
  /** Event type at this timestamp */
  type: 'checkpoint' | 'issue' | 'sync' | 'phase_start' | 'phase_end';
}

/**
 * Test update event payload - sent to dashboard
 */
export interface TestUpdateEvent {
  /** Event type */
  type: TestEventType;
  /** Unique event ID */
  eventId: string;
  /** Test run ID */
  testRunId: string;
  /** Journey being tested */
  journeyId: string;
  /** Platform under test */
  platform: Platform;
  /** Persona being simulated */
  persona?: string;
  /** Timestamp of event */
  timestamp: string;
  /** Event-specific payload */
  payload: TestEventPayload;
}

/**
 * Union type for event payloads
 */
export type TestEventPayload =
  | TestStartedPayload
  | CheckpointPassedPayload
  | CheckpointFailedPayload
  | TestCompletedPayload
  | AnalysisCompletePayload
  | ConstellationSyncPayload;

/**
 * Payload for test_started event
 */
export interface TestStartedPayload {
  /** Journey name */
  journeyName: string;
  /** Expected duration in ms */
  expectedDurationMs: number;
  /** Total checkpoints in journey */
  totalCheckpoints: number;
  /** Video recording URL (if available) */
  videoUrl?: string;
}

/**
 * Payload for checkpoint_passed event
 */
export interface CheckpointPassedPayload {
  /** Checkpoint ID */
  checkpointId: string;
  /** Checkpoint name */
  checkpointName: string;
  /** Phase this checkpoint belongs to */
  phaseId: string;
  /** Duration to complete checkpoint */
  durationMs: number;
  /** Video timestamp for this checkpoint */
  videoTimestamp?: number;
  /** Elements that were verified */
  elementsVerified: string[];
  /** Haptic feedback verified */
  hapticVerified?: boolean;
}

/**
 * Payload for checkpoint_failed event
 */
export interface CheckpointFailedPayload {
  /** Checkpoint ID */
  checkpointId: string;
  /** Checkpoint name */
  checkpointName: string;
  /** Phase this checkpoint belongs to */
  phaseId: string;
  /** Duration before failure */
  durationMs: number;
  /** Video timestamp for this checkpoint */
  videoTimestamp?: number;
  /** Elements that were missing */
  elementsMissing: string[];
  /** Error message */
  error: string;
  /** Screenshot URL if captured */
  screenshotUrl?: string;
}

/**
 * Payload for test_completed event
 */
export interface TestCompletedPayload {
  /** Overall success */
  success: boolean;
  /** Total duration */
  totalDurationMs: number;
  /** Checkpoints passed */
  checkpointsPassed: number;
  /** Checkpoints failed */
  checkpointsFailed: number;
  /** Byzantine quality scores */
  byzantineScores?: ByzantineScores;
  /** Video URL for playback */
  videoUrl?: string;
  /** Video timestamps for scrubbing */
  videoTimestamps?: VideoTimestamp[];
  /** Errors encountered */
  errors: string[];
}

/**
 * Payload for analysis_complete event
 */
export interface AnalysisCompletePayload {
  /** Analysis ID */
  analysisId: string;
  /** Quality score from Gemini */
  qualityScore: number;
  /** Issues detected */
  issues: Array<{
    id: string;
    timestamp: number;
    severity: Severity;
    category: IssueCategory;
    description: string;
    confidence: number;
    suggestedFix?: string;
  }>;
  /** Frames analyzed */
  framesAnalyzed: number;
  /** Analysis duration */
  durationMs: number;
  /** Byzantine scores from analysis */
  byzantineScores?: ByzantineScores;
}

/**
 * Payload for constellation_sync event
 */
export interface ConstellationSyncPayload {
  /** Source device platform */
  sourcePlatform: Platform;
  /** Target devices that synced */
  targetPlatforms: Platform[];
  /** Sync successful */
  syncSuccess: boolean;
  /** Latency measurements */
  latencies: Record<Platform, number>;
  /** State that was synced */
  syncedState: Record<string, unknown>;
  /** Video timestamp for sync event */
  videoTimestamp?: number;
}

/**
 * Test result to POST to dashboard API
 */
export interface TestResult {
  /** Test run ID */
  testRunId: string;
  /** Journey ID */
  journeyId: string;
  /** Journey name */
  journeyName: string;
  /** Platform tested */
  platform: Platform;
  /** Persona used */
  persona?: string;
  /** Start time */
  startedAt: string;
  /** Completion time */
  completedAt: string;
  /** Total duration */
  durationMs: number;
  /** Expected duration from journey spec (for timing calculations) */
  expectedDurationMs?: number;
  /** Success status */
  success: boolean;
  /** Checkpoint results */
  checkpoints: Array<{
    id: string;
    name: string;
    phaseId: string;
    success: boolean;
    durationMs: number;
    /** Expected duration for this checkpoint */
    expectedDurationMs?: number;
    videoTimestamp?: number;
    elementsFound: string[];
    elementsMissing: string[];
    /** Accessibility ID was present and verified */
    accessibilityIdVerified?: boolean;
    /** Haptic feedback was expected and verified */
    hapticVerified?: boolean;
    error?: string;
  }>;
  /** Video URL */
  videoUrl?: string;
  /** Video timestamps */
  videoTimestamps: VideoTimestamp[];
  /** Byzantine scores */
  byzantineScores?: ByzantineScores;
  /** Gemini analysis results */
  analysis?: {
    id: string;
    qualityScore: number;
    issueCount: number;
    framesAnalyzed: number;
  };
  /** Errors */
  errors: string[];
  /** Metadata */
  metadata?: Record<string, unknown>;
}

/**
 * Historical result for comparison
 */
export interface HistoricalResult {
  testRunId: string;
  journeyId: string;
  platform: Platform;
  completedAt: string;
  success: boolean;
  durationMs: number;
  byzantineScores?: ByzantineScores;
  qualityScore?: number;
}

/**
 * Publisher configuration
 */
export interface DashboardPublisherConfig {
  /** Dashboard REST API base URL */
  dashboardUrl: string;
  /** Dashboard WebSocket URL */
  websocketUrl: string;
  /** API key for authentication */
  apiKey?: string;
  /** Enable auto-reconnect */
  autoReconnect: boolean;
  /** Maximum reconnection attempts */
  maxReconnectAttempts: number;
  /** Connection timeout in ms */
  connectionTimeout: number;
  /** Request timeout in ms */
  requestTimeout: number;
  /** Enable verbose logging */
  verbose: boolean;
}

// =============================================================================
// WEBSOCKET WRAPPER
// =============================================================================

/**
 * WebSocket wrapper with reconnection logic
 */
class ReconnectingWebSocket extends EventEmitter {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxAttempts: number;
  private reconnecting = false;
  private closed = false;
  private logger = createChildLogger({ component: 'reconnecting-ws' });

  constructor(url: string, maxAttempts: number) {
    super();
    this.url = url;
    this.maxAttempts = maxAttempts;
  }

  get state(): ConnectionState {
    if (this.closed) return 'disconnected';
    if (this.reconnecting) return 'reconnecting';
    if (!this.ws) return 'disconnected';
    switch (this.ws.readyState) {
      case WebSocket.CONNECTING:
        return 'connecting';
      case WebSocket.OPEN:
        return 'connected';
      case WebSocket.CLOSING:
      case WebSocket.CLOSED:
        return this.reconnecting ? 'reconnecting' : 'disconnected';
      default:
        return 'disconnected';
    }
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.closed) {
        reject(new Error('WebSocket has been closed'));
        return;
      }

      try {
        this.ws = new WebSocket(this.url);

        const timeout = setTimeout(() => {
          if (this.ws?.readyState !== WebSocket.OPEN) {
            this.ws?.close();
            reject(new Error('Connection timeout'));
          }
        }, 10000);

        this.ws.onopen = () => {
          clearTimeout(timeout);
          this.reconnectAttempts = 0;
          this.reconnecting = false;
          this.logger.info({ url: this.url }, 'WebSocket connected');
          this.emit('open');
          resolve();
        };

        this.ws.onclose = (event) => {
          clearTimeout(timeout);
          this.logger.debug({ code: event.code, reason: event.reason }, 'WebSocket closed');
          this.emit('close', event);
          if (!this.closed) {
            this.scheduleReconnect();
          }
        };

        this.ws.onerror = (event) => {
          clearTimeout(timeout);
          this.logger.warn({ error: event }, 'WebSocket error');
          this.emit('error', event);
        };

        this.ws.onmessage = (event) => {
          this.emit('message', event.data);
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  private scheduleReconnect(): void {
    if (this.closed || this.reconnecting) return;
    if (this.reconnectAttempts >= this.maxAttempts) {
      this.logger.error({ attempts: this.reconnectAttempts }, 'Max reconnection attempts reached');
      this.emit('max_reconnects');
      return;
    }

    this.reconnecting = true;
    this.reconnectAttempts++;

    const delay = getFibonacciBackoff(this.reconnectAttempts);
    this.logger.info({ attempt: this.reconnectAttempts, delay }, 'Scheduling reconnect');

    setTimeout(async () => {
      try {
        await this.connect();
      } catch (error) {
        this.logger.warn({ error }, 'Reconnection failed');
        this.scheduleReconnect();
      }
    }, delay);
  }

  send(data: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(data);
    } else {
      this.logger.warn('Cannot send - WebSocket not open');
    }
  }

  close(): void {
    this.closed = true;
    this.reconnecting = false;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

// =============================================================================
// DASHBOARD PUBLISHER
// =============================================================================

const log = createChildLogger({ component: 'dashboard-publisher' });

/**
 * DashboardPublisher connects the QA test harness to the QA Dashboard.
 *
 * Features:
 * - Real-time WebSocket updates with Fibonacci backoff reconnection
 * - REST API integration for result submission
 * - Video upload support
 * - Historical result comparison
 *
 * @example
 * ```typescript
 * const publisher = new DashboardPublisher({
 *   dashboardUrl: 'http://localhost:3000/api',
 *   websocketUrl: 'ws://localhost:3000/ws',
 * });
 *
 * await publisher.connect();
 *
 * // Push real-time updates
 * await publisher.pushRealtimeUpdate({
 *   type: 'test_started',
 *   testRunId: 'abc123',
 *   journeyId: 'J01_MORNING_ROUTINE',
 *   platform: 'ios',
 *   timestamp: new Date().toISOString(),
 *   payload: {
 *     journeyName: 'Morning Routine',
 *     expectedDurationMs: 30000,
 *     totalCheckpoints: 10,
 *   },
 * });
 *
 * // Publish final results
 * await publisher.publishTestResult(testResult);
 *
 * await publisher.disconnect();
 * ```
 */
export class DashboardPublisher extends EventEmitter {
  private config: DashboardPublisherConfig;
  private ws: ReconnectingWebSocket | null = null;
  private eventQueue: TestUpdateEvent[] = [];
  private connected = false;

  constructor(config?: Partial<DashboardPublisherConfig>) {
    super();

    // Load from environment with defaults
    const apiKey = config?.apiKey ?? process.env['QA_DASHBOARD_API_KEY'];

    this.config = {
      dashboardUrl:
        config?.dashboardUrl ??
        process.env['QA_DASHBOARD_URL'] ??
        'http://localhost:3000/api',
      websocketUrl:
        config?.websocketUrl ??
        process.env['QA_DASHBOARD_WS_URL'] ??
        'ws://localhost:3000/ws',
      autoReconnect: config?.autoReconnect ?? true,
      maxReconnectAttempts: config?.maxReconnectAttempts ?? 10,
      connectionTimeout: config?.connectionTimeout ?? 10000,
      requestTimeout: config?.requestTimeout ?? 30000,
      verbose: config?.verbose ?? false,
    };

    // Only set apiKey if it's defined (to satisfy exactOptionalPropertyTypes)
    if (apiKey) {
      this.config.apiKey = apiKey;
    }

    log.info(
      { dashboardUrl: this.config.dashboardUrl, wsUrl: this.config.websocketUrl },
      'DashboardPublisher initialized'
    );
  }

  /**
   * Get current connection state
   */
  get connectionState(): ConnectionState {
    return this.ws?.state ?? 'disconnected';
  }

  /**
   * Connect to the dashboard WebSocket
   */
  async connect(): Promise<void> {
    if (this.connected) {
      log.warn('Already connected');
      return;
    }

    this.ws = new ReconnectingWebSocket(
      this.config.websocketUrl,
      this.config.autoReconnect ? this.config.maxReconnectAttempts : 0
    );

    this.ws.on('open', () => {
      this.connected = true;
      this.emit('connected');
      this.flushEventQueue();
    });

    this.ws.on('close', () => {
      this.connected = false;
      this.emit('disconnected');
    });

    this.ws.on('error', (error) => {
      this.emit('error', error);
    });

    this.ws.on('message', (data: string) => {
      try {
        const message = JSON.parse(data);
        this.emit('message', message);
      } catch {
        log.warn({ data }, 'Received non-JSON message');
      }
    });

    this.ws.on('max_reconnects', () => {
      this.emit('max_reconnects');
    });

    try {
      await this.ws.connect();
    } catch (error) {
      log.error({ error }, 'Failed to connect to dashboard');
      throw error;
    }
  }

  /**
   * Disconnect from the dashboard
   */
  async disconnect(): Promise<void> {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.connected = false;
    log.info('Disconnected from dashboard');
  }

  /**
   * Push a real-time update event to the dashboard
   */
  async pushRealtimeUpdate(event: TestUpdateEvent): Promise<void> {
    // Generate event ID if not provided
    if (!event.eventId) {
      event.eventId = crypto.randomUUID();
    }

    if (this.config.verbose) {
      log.debug({ eventType: event.type, testRunId: event.testRunId }, 'Pushing realtime update');
    }

    if (this.connected && this.ws) {
      this.ws.send(JSON.stringify(event));
    } else {
      // Queue for later delivery
      this.eventQueue.push(event);
      log.debug({ queueSize: this.eventQueue.length }, 'Event queued (not connected)');
    }

    this.emit('event_sent', event);
  }

  /**
   * Flush queued events after reconnection
   */
  private flushEventQueue(): void {
    if (this.eventQueue.length === 0) return;

    log.info({ count: this.eventQueue.length }, 'Flushing event queue');

    while (this.eventQueue.length > 0) {
      const event = this.eventQueue.shift();
      if (event && this.ws) {
        this.ws.send(JSON.stringify(event));
      }
    }
  }

  /**
   * Publish a complete test result to the dashboard API
   */
  async publishTestResult(result: TestResult): Promise<{ id: string }> {
    log.info(
      { testRunId: result.testRunId, journeyId: result.journeyId },
      'Publishing test result'
    );

    const response = await this.apiRequest('POST', '/results', result);

    this.emit('result_published', { testRunId: result.testRunId, response });
    return response as { id: string };
  }

  /**
   * Upload a video file to the dashboard
   */
  async uploadVideo(videoPath: string): Promise<{ url: string }> {
    log.info({ videoPath }, 'Uploading video');

    // Read file
    const videoBuffer = await fs.readFile(videoPath);
    const filename = path.basename(videoPath);
    const mimeType = this.getMimeType(filename);

    // Create form data manually since we're in Node
    const boundary = `----FormBoundary${crypto.randomUUID().replace(/-/g, '')}`;
    const formParts: Buffer[] = [];

    // Add file part
    formParts.push(Buffer.from(
      `--${boundary}\r\n` +
      `Content-Disposition: form-data; name="video"; filename="${filename}"\r\n` +
      `Content-Type: ${mimeType}\r\n\r\n`
    ));
    formParts.push(videoBuffer);
    formParts.push(Buffer.from(`\r\n--${boundary}--\r\n`));

    const body = Buffer.concat(formParts);

    const response = await fetch(`${this.config.dashboardUrl}/videos`, {
      method: 'POST',
      headers: {
        'Content-Type': `multipart/form-data; boundary=${boundary}`,
        ...this.getAuthHeaders(),
      },
      body,
      signal: AbortSignal.timeout(this.config.requestTimeout * 2), // Longer timeout for uploads
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Video upload failed: ${response.status} - ${error}`);
    }

    const data = await response.json() as { url: string };
    log.info({ videoPath, url: data.url }, 'Video uploaded');

    return data;
  }

  /**
   * Query historical results for comparison
   */
  async queryHistoricalResults(query: {
    journeyId?: string;
    platform?: Platform;
    since?: string;
    limit?: number;
  }): Promise<HistoricalResult[]> {
    const params = new URLSearchParams();
    if (query.journeyId) params.set('journeyId', query.journeyId);
    if (query.platform) params.set('platform', query.platform);
    if (query.since) params.set('since', query.since);
    if (query.limit) params.set('limit', query.limit.toString());

    const response = await this.apiRequest(
      'GET',
      `/results/history?${params.toString()}`
    );

    return response as HistoricalResult[];
  }

  /**
   * Make an API request to the dashboard
   */
  private async apiRequest(
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    path: string,
    body?: unknown
  ): Promise<unknown> {
    const url = `${this.config.dashboardUrl}${path}`;

    const options: RequestInit = {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
      },
      signal: AbortSignal.timeout(this.config.requestTimeout),
    };

    if (body && method !== 'GET') {
      options.body = JSON.stringify(body);
    }

    const response = await fetch(url, options);

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`API request failed: ${response.status} - ${error}`);
    }

    return response.json();
  }

  /**
   * Get authentication headers
   */
  private getAuthHeaders(): Record<string, string> {
    const headers: Record<string, string> = {};
    if (this.config.apiKey) {
      headers['X-API-Key'] = this.config.apiKey;
    }
    return headers;
  }

  /**
   * Get MIME type for video file
   */
  private getMimeType(filename: string): string {
    const ext = path.extname(filename).toLowerCase();
    switch (ext) {
      case '.mp4':
        return 'video/mp4';
      case '.webm':
        return 'video/webm';
      case '.mov':
        return 'video/quicktime';
      case '.avi':
        return 'video/x-msvideo';
      default:
        return 'application/octet-stream';
    }
  }
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Format a phase result for dashboard consumption
 */
export function formatPhaseResult(
  phase: PhaseResult,
  checkpointNames: Map<string, string>
): Array<CheckpointPassedPayload | CheckpointFailedPayload> {
  return phase.checkpointResults.map((cp) => {
    if (cp.success) {
      return {
        checkpointId: cp.checkpointId,
        checkpointName: checkpointNames.get(cp.checkpointId) ?? cp.checkpointId,
        phaseId: phase.phaseId,
        durationMs: cp.durationMs,
        elementsVerified: cp.elementsFound,
        hapticVerified: cp.hapticVerified,
      } as CheckpointPassedPayload;
    } else {
      return {
        checkpointId: cp.checkpointId,
        checkpointName: checkpointNames.get(cp.checkpointId) ?? cp.checkpointId,
        phaseId: phase.phaseId,
        durationMs: cp.durationMs,
        elementsMissing: cp.elementsMissing,
        error: `Missing elements: ${cp.elementsMissing.join(', ')}`,
      } as CheckpointFailedPayload;
    }
  });
}

/**
 * Format a constellation result for dashboard
 */
export function formatConstellationResult(
  result: ConstellationResult,
  videoUrl?: string
): TestResult {
  const checkpoints: TestResult['checkpoints'] = [];
  const videoTimestamps: VideoTimestamp[] = [];
  let timestampOffset = 0;

  for (const phase of result.phaseResults) {
    videoTimestamps.push({
      time: timestampOffset,
      label: `Phase: ${phase.phaseId}`,
      type: 'phase_start',
    });

    for (const cp of phase.checkpointResults) {
      const checkpoint: TestResult['checkpoints'][number] = {
        id: cp.checkpointId,
        name: cp.checkpointId,
        phaseId: phase.phaseId,
        success: cp.success,
        durationMs: cp.durationMs,
        videoTimestamp: timestampOffset,
        elementsFound: cp.elementsFound,
        elementsMissing: cp.elementsMissing,
      };
      if (cp.elementsMissing.length > 0) {
        checkpoint.error = `Missing: ${cp.elementsMissing.join(', ')}`;
      }
      checkpoints.push(checkpoint);

      videoTimestamps.push({
        time: timestampOffset,
        label: cp.checkpointId,
        checkpointId: cp.checkpointId,
        type: cp.success ? 'checkpoint' : 'issue',
      });

      timestampOffset += cp.durationMs / 1000;
    }

    videoTimestamps.push({
      time: timestampOffset,
      label: `Phase End: ${phase.phaseId}`,
      type: 'phase_end',
    });
  }

  const testResult: TestResult = {
    testRunId: crypto.randomUUID(),
    journeyId: result.journeyId,
    journeyName: result.journeyId,
    platform: result.devicesParticipated[0] ?? 'ios',
    startedAt: new Date(Date.now() - result.totalDurationMs).toISOString(),
    completedAt: new Date().toISOString(),
    durationMs: result.totalDurationMs,
    success: result.success,
    checkpoints,
    videoTimestamps,
    errors: result.errors,
    metadata: {
      constellationDevices: result.devicesParticipated,
      syncVerified: result.syncVerified,
    },
  };

  if (videoUrl) {
    testResult.videoUrl = videoUrl;
  }

  return testResult;
}

/**
 * Format an analysis result for dashboard
 */
export function formatAnalysisResult(result: AnalysisResult): AnalysisCompletePayload {
  return {
    analysisId: result.id,
    qualityScore: result.qualityScore ?? 0,
    issues: result.issues.map((issue) => {
      const formatted: AnalysisCompletePayload['issues'][number] = {
        id: issue.id,
        timestamp: issue.timestamp,
        severity: issue.severity,
        category: issue.category,
        description: issue.description,
        confidence: issue.confidence,
      };
      if (issue.suggestedFix) {
        formatted.suggestedFix = issue.suggestedFix;
      }
      return formatted;
    }),
    framesAnalyzed: result.framesAnalyzed,
    durationMs: result.durationMs ?? 0,
  };
}

/**
 * Calculate Byzantine scores from test results
 *
 * Each dimension is calculated based on real metrics:
 * - Technical: Pass rate, error count, element verification
 * - Aesthetic: Timing performance (actual vs expected duration)
 * - Accessibility: Accessibility ID verification rate
 * - Emotional: Haptic feedback completion and smooth progression
 * - Polish: Timing variance across checkpoints (consistency)
 * - Delight: Composite of all positive factors
 */
export function calculateByzantineScores(result: TestResult): ByzantineScores {
  const totalCheckpoints = result.checkpoints.length;
  const passedCheckpoints = result.checkpoints.filter((cp) => cp.success).length;
  const passRate = totalCheckpoints > 0 ? passedCheckpoints / totalCheckpoints : 0;

  // =========================================================================
  // TECHNICAL: Based on pass rate, error count, and element verification
  // =========================================================================
  const elementsVerifiedTotal = result.checkpoints.reduce(
    (sum, cp) => sum + cp.elementsFound.length, 0
  );
  const elementsMissingTotal = result.checkpoints.reduce(
    (sum, cp) => sum + cp.elementsMissing.length, 0
  );
  const elementVerificationRate = elementsVerifiedTotal > 0
    ? elementsVerifiedTotal / (elementsVerifiedTotal + elementsMissingTotal)
    : passRate; // Fall back to pass rate if no element data

  const technicalBase = passRate * 70 + elementVerificationRate * 30;
  const errorPenalty = Math.min(result.errors.length * 5, 30);
  const technical = Math.round(technicalBase - errorPenalty);

  // =========================================================================
  // AESTHETIC: Based on timing performance (actual vs expected duration)
  // =========================================================================
  let aesthetic: number;
  if (result.expectedDurationMs && result.expectedDurationMs > 0) {
    // Calculate how close actual duration is to expected
    const timingRatio = result.durationMs / result.expectedDurationMs;

    if (timingRatio <= 1.0) {
      // Faster than expected: excellent (95-100)
      aesthetic = 95 + Math.round((1.0 - timingRatio) * 5);
    } else if (timingRatio <= 1.2) {
      // Within 20% slower: good (85-95)
      aesthetic = 95 - Math.round((timingRatio - 1.0) * 50);
    } else if (timingRatio <= 1.5) {
      // 20-50% slower: acceptable (70-85)
      aesthetic = 85 - Math.round((timingRatio - 1.2) * 50);
    } else {
      // More than 50% slower: poor (50-70)
      aesthetic = Math.max(50, 70 - Math.round((timingRatio - 1.5) * 40));
    }
  } else {
    // No expected duration - calculate from checkpoint timing variance
    const checkpointDurations = result.checkpoints
      .filter((cp) => cp.success && cp.durationMs > 0)
      .map((cp) => cp.durationMs);

    if (checkpointDurations.length > 1) {
      const avgDuration = checkpointDurations.reduce((a, b) => a + b, 0) / checkpointDurations.length;
      const variance = checkpointDurations.reduce(
        (sum, d) => sum + Math.pow(d - avgDuration, 2), 0
      ) / checkpointDurations.length;
      const stdDev = Math.sqrt(variance);
      const coefficientOfVariation = avgDuration > 0 ? stdDev / avgDuration : 0;

      // Lower variance = better aesthetic (consistent timing)
      aesthetic = Math.round(95 - Math.min(coefficientOfVariation * 100, 45));
    } else {
      aesthetic = passRate >= 1 ? 85 : 70;
    }
  }

  // =========================================================================
  // ACCESSIBILITY: Based on accessibility ID verification across checkpoints
  // =========================================================================
  let accessibility: number;
  const checkpointsWithAccessibility = result.checkpoints.filter(
    (cp) => cp.accessibilityIdVerified !== undefined
  );

  if (checkpointsWithAccessibility.length > 0) {
    const accessibilityVerified = checkpointsWithAccessibility.filter(
      (cp) => cp.accessibilityIdVerified === true
    ).length;
    const accessibilityRate = accessibilityVerified / checkpointsWithAccessibility.length;

    // Scale: 100% verified = 100, 0% = 50, with pass rate factoring in
    accessibility = Math.round(50 + accessibilityRate * 40 + passRate * 10);
  } else {
    // No accessibility data - use element verification as proxy
    // Elements with testID/accessibilityId patterns indicate accessibility support
    const hasAccessibilityElements = result.checkpoints.some((cp) =>
      cp.elementsFound.some((el) =>
        el.includes('accessibility') ||
        el.includes('testID') ||
        el.includes('a11y')
      )
    );
    accessibility = hasAccessibilityElements
      ? Math.round(75 + passRate * 20)
      : Math.round(60 + passRate * 20);
  }

  // =========================================================================
  // EMOTIONAL: Based on haptic feedback and smooth progression
  // =========================================================================
  const checkpointsWithHaptic = result.checkpoints.filter(
    (cp) => cp.hapticVerified !== undefined
  );

  let hapticScore: number;
  if (checkpointsWithHaptic.length > 0) {
    const hapticVerified = checkpointsWithHaptic.filter(
      (cp) => cp.hapticVerified === true
    ).length;
    hapticScore = hapticVerified / checkpointsWithHaptic.length;
  } else {
    // No haptic data - assume neutral (0.7 baseline)
    hapticScore = 0.7;
  }

  // Smooth progression: check for any failed checkpoints interrupting flow
  const failedIndices = result.checkpoints
    .map((cp, i) => ({ success: cp.success, index: i }))
    .filter((item) => !item.success)
    .map((item) => item.index);

  let progressionScore = 1.0;
  if (failedIndices.length > 0) {
    // Penalize early failures more than late failures
    const avgFailurePosition = failedIndices.reduce((a, b) => a + b, 0) / failedIndices.length;
    const normalizedPosition = totalCheckpoints > 1
      ? avgFailurePosition / (totalCheckpoints - 1)
      : 0;
    // Early failures (position 0-0.3) = heavy penalty, late failures = minor
    progressionScore = 0.5 + normalizedPosition * 0.5;
  }

  const emotional = Math.round(hapticScore * 50 + progressionScore * 30 + passRate * 20);

  // =========================================================================
  // POLISH: Based on timing variance (consistency) across checkpoints
  // =========================================================================
  let polish: number;
  const successfulCheckpoints = result.checkpoints.filter((cp) => cp.success);

  if (successfulCheckpoints.length > 1) {
    // Calculate timing variance relative to expected durations
    const timingDeviations: number[] = [];

    for (const cp of successfulCheckpoints) {
      if (cp.expectedDurationMs && cp.expectedDurationMs > 0) {
        const deviation = Math.abs(cp.durationMs - cp.expectedDurationMs) / cp.expectedDurationMs;
        timingDeviations.push(deviation);
      }
    }

    let varianceScore: number;
    if (timingDeviations.length > 0) {
      const avgDeviation = timingDeviations.reduce((a, b) => a + b, 0) / timingDeviations.length;
      // 0% deviation = 100, 50% deviation = 50
      varianceScore = Math.max(0, 100 - avgDeviation * 100);
    } else {
      // No expected durations - use coefficient of variation of actual durations
      const durations = successfulCheckpoints.map((cp) => cp.durationMs).filter((d) => d > 0);
      if (durations.length > 1) {
        const avgDuration = durations.reduce((a, b) => a + b, 0) / durations.length;
        const variance = durations.reduce(
          (sum, d) => sum + Math.pow(d - avgDuration, 2), 0
        ) / durations.length;
        const stdDev = Math.sqrt(variance);
        const cv = avgDuration > 0 ? stdDev / avgDuration : 0;
        // CV of 0 = 100, CV of 1 = 50
        varianceScore = Math.max(50, 100 - cv * 50);
      } else {
        varianceScore = 75;
      }
    }

    // Factor in error-free execution
    const errorPenaltyPolish = result.errors.length > 0 ? Math.min(result.errors.length * 3, 15) : 0;
    polish = Math.round(varianceScore * 0.7 + passRate * 30 - errorPenaltyPolish);
  } else {
    // Single or no checkpoints - base on pass rate and errors
    polish = Math.round(passRate * 80 + (result.errors.length === 0 ? 20 : 0));
  }

  // =========================================================================
  // DELIGHT: Composite score weighing all positive factors
  // =========================================================================
  // Delight represents the "joy" of the experience - combines:
  // - Fast completion (beating expected time)
  // - Zero errors
  // - All checkpoints passing
  // - Smooth haptic feedback
  // - Consistent timing

  let delightFactors = 0;
  let delightWeight = 0;

  // Factor 1: Timing delight (completed faster than expected)
  if (result.expectedDurationMs && result.expectedDurationMs > 0) {
    const timeSaved = result.expectedDurationMs - result.durationMs;
    const timeSavedRatio = timeSaved / result.expectedDurationMs;
    delightFactors += Math.max(0, timeSavedRatio) * 100 * 0.25;
    delightWeight += 0.25;
  }

  // Factor 2: Error-free execution
  if (result.errors.length === 0) {
    delightFactors += 100 * 0.25;
  } else {
    delightFactors += Math.max(0, 100 - result.errors.length * 20) * 0.25;
  }
  delightWeight += 0.25;

  // Factor 3: Perfect checkpoint execution
  delightFactors += passRate * 100 * 0.25;
  delightWeight += 0.25;

  // Factor 4: Haptic and emotional satisfaction
  delightFactors += hapticScore * 100 * 0.25;
  delightWeight += 0.25;

  const delight = delightWeight > 0
    ? Math.round(delightFactors / delightWeight)
    : Math.round(passRate * 70 + (result.success ? 30 : 0));

  // =========================================================================
  // OVERALL: Weighted average of all dimensions
  // =========================================================================
  const overall = Math.round(
    technical * 0.20 +
    aesthetic * 0.15 +
    accessibility * 0.20 +
    emotional * 0.15 +
    polish * 0.15 +
    delight * 0.15
  );

  return {
    technical: Math.max(0, Math.min(100, technical)),
    aesthetic: Math.max(0, Math.min(100, aesthetic)),
    accessibility: Math.max(0, Math.min(100, accessibility)),
    emotional: Math.max(0, Math.min(100, emotional)),
    polish: Math.max(0, Math.min(100, polish)),
    delight: Math.max(0, Math.min(100, delight)),
    overall: Math.max(0, Math.min(100, overall)),
  };
}

// =============================================================================
// SINGLETON INSTANCE
// =============================================================================

let publisherInstance: DashboardPublisher | null = null;

/**
 * Get the shared DashboardPublisher instance
 */
export function getPublisher(config?: Partial<DashboardPublisherConfig>): DashboardPublisher {
  if (!publisherInstance) {
    publisherInstance = new DashboardPublisher(config);
  }
  return publisherInstance;
}

/**
 * Reset the publisher instance (for testing)
 */
export async function resetPublisher(): Promise<void> {
  if (publisherInstance) {
    await publisherInstance.disconnect();
    publisherInstance = null;
  }
}

// =============================================================================
// CONVENIENCE EXPORTS
// =============================================================================

/**
 * Publish a test result to the dashboard
 */
export async function publishTestResult(result: TestResult): Promise<{ id: string }> {
  const publisher = getPublisher();
  if (publisher.connectionState !== 'connected') {
    await publisher.connect();
  }
  return publisher.publishTestResult(result);
}

/**
 * Push a realtime update to the dashboard
 */
export async function pushRealtimeUpdate(event: TestUpdateEvent): Promise<void> {
  const publisher = getPublisher();
  if (publisher.connectionState !== 'connected') {
    await publisher.connect();
  }
  return publisher.pushRealtimeUpdate(event);
}

/**
 * Upload a video file to the dashboard
 */
export async function uploadVideo(videoPath: string): Promise<{ url: string }> {
  const publisher = getPublisher();
  return publisher.uploadVideo(videoPath);
}
