/**
 * @fileoverview REST API Server with WebSocket support
 *
 * Provides HTTP endpoints for:
 * - Listing and viewing analyses
 * - Queuing new analysis jobs
 * - Retrieving detected issues
 * - Pipeline health monitoring
 *
 * Also provides WebSocket connections for real-time updates.
 */

import express, { Request, Response, NextFunction, Router } from 'express';
import { createServer, Server as HttpServer } from 'node:http';
import { WebSocketServer, WebSocket } from 'ws';
import { randomUUID } from 'node:crypto';
import { createChildLogger, logError } from './logger.js';
import { getConfig, loadConfig, setConfig } from './config.js';
import { getTracker } from './tracker.js';
import { getRunner, PipelineRunner } from './runner.js';
import {
  AnalyzeRequestSchema,
  ListAnalysesQuerySchema,
  ListIssuesQuerySchema
} from './types.js';
import type {
  WsMessage,
  WsEventType,
  PipelineHealth,
  AnalysisResult,
  DetectedIssue
} from './types.js';

const log = createChildLogger({ component: 'server' });

/**
 * Connected WebSocket client
 */
interface WsClient {
  id: string;
  ws: WebSocket;
  subscriptions: Set<WsEventType>;
}

/**
 * API response wrapper
 */
interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  meta?: {
    total?: number;
    offset?: number;
    limit?: number;
  };
}

/**
 * Create success response
 */
function success<T>(data: T, meta?: ApiResponse<T>['meta']): ApiResponse<T> {
  return { success: true, data, meta };
}

/**
 * Create error response
 */
function error(message: string): ApiResponse<never> {
  return { success: false, error: message };
}

/**
 * Create the API router
 */
function createApiRouter(runner: PipelineRunner): Router {
  const router = Router();

  // GET /api/health - Pipeline health check
  router.get('/health', async (_req: Request, res: Response) => {
    try {
      const health = runner.getHealth();
      res.json(success(health));
    } catch (err) {
      logError(err, { endpoint: '/health' });
      res.status(500).json(error('Failed to get health status'));
    }
  });

  // GET /api/analyses - List all analyses
  router.get('/analyses', async (req: Request, res: Response) => {
    try {
      const parsed = ListAnalysesQuerySchema.safeParse(req.query);
      if (!parsed.success) {
        res.status(400).json(error(`Invalid query parameters: ${parsed.error.message}`));
        return;
      }

      const tracker = await getTracker();
      const { analyses, total } = tracker.listAnalyses(parsed.data);

      res.json(success(analyses, {
        total,
        offset: parsed.data.offset,
        limit: parsed.data.limit
      }));
    } catch (err) {
      logError(err, { endpoint: '/analyses' });
      res.status(500).json(error('Failed to list analyses'));
    }
  });

  // GET /api/analyses/:id - Get specific analysis
  router.get('/analyses/:id', async (req: Request, res: Response) => {
    try {
      const { id } = req.params;
      if (!id) {
        res.status(400).json(error('Analysis ID required'));
        return;
      }

      const tracker = await getTracker();
      const analysis = tracker.getAnalysis(id);

      if (!analysis) {
        res.status(404).json(error('Analysis not found'));
        return;
      }

      res.json(success(analysis));
    } catch (err) {
      logError(err, { endpoint: '/analyses/:id' });
      res.status(500).json(error('Failed to get analysis'));
    }
  });

  // POST /api/analyze - Queue video for analysis
  router.post('/analyze', async (req: Request, res: Response) => {
    try {
      const parsed = AnalyzeRequestSchema.safeParse(req.body);
      if (!parsed.success) {
        res.status(400).json(error(`Invalid request: ${parsed.error.message}`));
        return;
      }

      const { videoPath, config, priority } = parsed.data;

      // Build full config with defaults
      const fullConfig = {
        platform: config.platform,
        testName: config.testName ?? 'API Analysis',
        testSuite: config.testSuite,
        frameInterval: config.frameInterval ?? 1,
        maxFrames: config.maxFrames ?? 100,
        customPrompts: config.customPrompts,
        excludeKnownIssues: config.excludeKnownIssues ?? false
      };

      // Queue the analysis (don't await - return immediately)
      const analysisPromise = runner.runAnalysis({
        videoPath,
        config: fullConfig,
        priority
      });

      // Get the job info
      const pendingJobs = runner.getPendingJobs();
      const activeJobs = runner.getActiveJobs();
      const allJobs = [...pendingJobs, ...activeJobs];
      const latestJob = allJobs[allJobs.length - 1];

      res.status(202).json(success({
        message: 'Analysis queued',
        jobId: latestJob?.id ?? 'unknown',
        queuePosition: pendingJobs.length
      }));

      // Handle result in background
      analysisPromise.catch(err => {
        logError(err, { videoPath, action: 'background-analysis' });
      });

    } catch (err) {
      logError(err, { endpoint: '/analyze' });
      res.status(500).json(error('Failed to queue analysis'));
    }
  });

  // GET /api/issues - Get all detected issues
  router.get('/issues', async (req: Request, res: Response) => {
    try {
      const parsed = ListIssuesQuerySchema.safeParse(req.query);
      if (!parsed.success) {
        res.status(400).json(error(`Invalid query parameters: ${parsed.error.message}`));
        return;
      }

      const tracker = await getTracker();
      const { issues, total } = tracker.listIssues(parsed.data);

      res.json(success(issues, {
        total,
        offset: parsed.data.offset,
        limit: parsed.data.limit
      }));
    } catch (err) {
      logError(err, { endpoint: '/issues' });
      res.status(500).json(error('Failed to list issues'));
    }
  });

  // GET /api/issues/stats - Get issue statistics
  router.get('/issues/stats', async (_req: Request, res: Response) => {
    try {
      const tracker = await getTracker();
      const stats = tracker.getIssueStats();
      res.json(success(stats));
    } catch (err) {
      logError(err, { endpoint: '/issues/stats' });
      res.status(500).json(error('Failed to get issue statistics'));
    }
  });

  // POST /api/issues/:fingerprint/resolve - Mark issue as resolved
  router.post('/issues/:fingerprint/resolve', async (req: Request, res: Response) => {
    try {
      const { fingerprint } = req.params;
      const { notes } = req.body as { notes?: string };

      if (!fingerprint) {
        res.status(400).json(error('Issue fingerprint required'));
        return;
      }

      const tracker = await getTracker();
      const resolved = tracker.resolveKnownIssue(fingerprint, notes);

      if (!resolved) {
        res.status(404).json(error('Issue not found'));
        return;
      }

      res.json(success({ message: 'Issue marked as resolved' }));
    } catch (err) {
      logError(err, { endpoint: '/issues/:fingerprint/resolve' });
      res.status(500).json(error('Failed to resolve issue'));
    }
  });

  // GET /api/queue - Get current queue status
  router.get('/queue', async (_req: Request, res: Response) => {
    try {
      res.json(success({
        pending: runner.getPendingJobs(),
        active: runner.getActiveJobs()
      }));
    } catch (err) {
      logError(err, { endpoint: '/queue' });
      res.status(500).json(error('Failed to get queue status'));
    }
  });

  // DELETE /api/queue/:id - Cancel a queued job
  router.delete('/queue/:id', async (req: Request, res: Response) => {
    try {
      const { id } = req.params;
      if (!id) {
        res.status(400).json(error('Job ID required'));
        return;
      }

      const cancelled = runner.cancelJob(id);
      if (!cancelled) {
        res.status(404).json(error('Job not found or already active'));
        return;
      }

      res.json(success({ message: 'Job cancelled' }));
    } catch (err) {
      logError(err, { endpoint: '/queue/:id' });
      res.status(500).json(error('Failed to cancel job'));
    }
  });

  // POST /api/pipeline/pause - Pause the pipeline
  router.post('/pipeline/pause', async (_req: Request, res: Response) => {
    try {
      runner.pause();
      res.json(success({ message: 'Pipeline paused' }));
    } catch (err) {
      logError(err, { endpoint: '/pipeline/pause' });
      res.status(500).json(error('Failed to pause pipeline'));
    }
  });

  // POST /api/pipeline/resume - Resume the pipeline
  router.post('/pipeline/resume', async (_req: Request, res: Response) => {
    try {
      runner.resume();
      res.json(success({ message: 'Pipeline resumed' }));
    } catch (err) {
      logError(err, { endpoint: '/pipeline/resume' });
      res.status(500).json(error('Failed to resume pipeline'));
    }
  });

  return router;
}

/**
 * API Server class
 *
 * Provides REST API and WebSocket endpoints.
 *
 * @example
 * ```typescript
 * const server = new ApiServer();
 * await server.start();
 *
 * // Server is now listening on configured port
 * // WebSocket available at ws://localhost:3847/ws
 * ```
 */
export class ApiServer {
  private config = getConfig();
  private app = express();
  private server: HttpServer;
  private wss: WebSocketServer;
  private clients = new Map<string, WsClient>();
  private runner: PipelineRunner;

  constructor() {
    this.runner = getRunner();
    this.server = createServer(this.app);
    this.wss = new WebSocketServer({ server: this.server, path: '/ws' });

    this.setupMiddleware();
    this.setupRoutes();
    this.setupWebSocket();
    this.setupPipelineEvents();
  }

  /**
   * Set up Express middleware
   */
  private setupMiddleware(): void {
    // Parse JSON bodies
    this.app.use(express.json());

    // Security headers
    this.app.use((_req: Request, res: Response, next: NextFunction) => {
      res.header('X-Content-Type-Options', 'nosniff');
      res.header('X-Frame-Options', 'DENY');
      res.header('X-XSS-Protection', '1; mode=block');
      next();
    });

    // CORS configuration - require explicit origins in production
    const isProduction = process.env['NODE_ENV'] === 'production';
    const corsOriginsEnv = process.env['CORS_ALLOWED_ORIGINS'];

    if (isProduction && !corsOriginsEnv) {
      throw new Error(
        'CORS_ALLOWED_ORIGINS environment variable is required in production. ' +
        'Set it to a comma-separated list of allowed origins (e.g., "https://dashboard.example.com,https://app.example.com")'
      );
    }

    // In production: use only the explicitly configured origins
    // In development: fall back to localhost if not configured
    const allowedOrigins = corsOriginsEnv
      ? corsOriginsEnv.split(',').map((origin) => origin.trim()).filter(Boolean)
      : isProduction
        ? [] // Should never reach here due to check above, but defensive
        : ['http://localhost:3000', 'http://localhost:3001', 'http://127.0.0.1:3000'];

    this.app.use((req: Request, res: Response, next: NextFunction) => {
      const origin = req.headers.origin;
      if (origin && allowedOrigins.includes(origin)) {
        res.header('Access-Control-Allow-Origin', origin);
        res.header('Access-Control-Allow-Credentials', 'true');
      }
      res.header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS');
      res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-API-Key');
      if (req.method === 'OPTIONS') {
        res.sendStatus(204);
        return;
      }
      next();
    });

    // API key authentication for protected routes
    this.app.use('/api', (req: Request, res: Response, next: NextFunction) => {
      // Allow health checks and OPTIONS without auth
      if (req.path === '/health' || req.method === 'OPTIONS') {
        next();
        return;
      }

      // Check for API key in header or query
      const apiKey = req.headers['x-api-key'] || req.query.apiKey;
      const expectedKey = process.env.QA_PIPELINE_API_KEY;

      // If no key configured, allow all (development mode)
      if (!expectedKey) {
        log.warn('QA_PIPELINE_API_KEY not set - API is unprotected');
        next();
        return;
      }

      if (apiKey !== expectedKey) {
        res.status(401).json({ success: false, error: 'Invalid or missing API key' });
        return;
      }

      next();
    });

    // Request logging
    this.app.use((req: Request, _res: Response, next: NextFunction) => {
      log.debug({ method: req.method, path: req.path }, 'Request received');
      next();
    });
  }

  /**
   * Set up API routes
   */
  private setupRoutes(): void {
    // API routes
    this.app.use('/api', createApiRouter(this.runner));

    // Health check at root
    this.app.get('/', (_req: Request, res: Response) => {
      res.json({
        name: 'Kagami QA Pipeline',
        version: '0.1.0',
        status: 'running',
        docs: '/api/health'
      });
    });

    // 404 handler
    this.app.use((_req: Request, res: Response) => {
      res.status(404).json(error('Not found'));
    });

    // Error handler
    this.app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
      logError(err, { action: 'request-handler' });
      res.status(500).json(error('Internal server error'));
    });
  }

  /**
   * Set up WebSocket server
   */
  private setupWebSocket(): void {
    this.wss.on('connection', (ws: WebSocket) => {
      const clientId = randomUUID();
      const client: WsClient = {
        id: clientId,
        ws,
        subscriptions: new Set(['analysis:completed', 'analysis:failed', 'pipeline:health'])
      };

      this.clients.set(clientId, client);
      log.debug({ clientId }, 'WebSocket client connected');

      // Send initial health status
      this.sendToClient(client, 'pipeline:health', { health: this.runner.getHealth() });

      // Handle messages from client
      ws.on('message', (data: Buffer) => {
        try {
          const message = JSON.parse(data.toString()) as {
            type: 'subscribe' | 'unsubscribe';
            events: WsEventType[];
          };

          if (message.type === 'subscribe') {
            for (const event of message.events) {
              client.subscriptions.add(event);
            }
            log.debug({ clientId, events: message.events }, 'Client subscribed');
          } else if (message.type === 'unsubscribe') {
            for (const event of message.events) {
              client.subscriptions.delete(event);
            }
            log.debug({ clientId, events: message.events }, 'Client unsubscribed');
          }
        } catch (err) {
          log.warn({ clientId, error: err }, 'Invalid WebSocket message');
        }
      });

      // Handle disconnect
      ws.on('close', () => {
        this.clients.delete(clientId);
        log.debug({ clientId }, 'WebSocket client disconnected');
      });

      // Handle errors
      ws.on('error', (err) => {
        logError(err, { clientId, action: 'websocket' });
        this.clients.delete(clientId);
      });
    });
  }

  /**
   * Set up pipeline event forwarding
   */
  private setupPipelineEvents(): void {
    // Forward all pipeline events to WebSocket clients
    const eventTypes: WsEventType[] = [
      'analysis:queued',
      'analysis:started',
      'analysis:progress',
      'analysis:completed',
      'analysis:failed',
      'issue:detected',
      'pipeline:health'
    ];

    for (const eventType of eventTypes) {
      this.runner.on(eventType, (payload: unknown) => {
        this.broadcast(eventType, payload);
      });
    }
  }

  /**
   * Send message to a specific client
   */
  private sendToClient(client: WsClient, type: WsEventType, payload: unknown): void {
    if (client.ws.readyState !== WebSocket.OPEN) {
      return;
    }

    const message: WsMessage = {
      type,
      payload,
      timestamp: new Date().toISOString()
    };

    client.ws.send(JSON.stringify(message));
  }

  /**
   * Broadcast message to all subscribed clients
   */
  private broadcast(type: WsEventType, payload: unknown): void {
    for (const client of this.clients.values()) {
      if (client.subscriptions.has(type)) {
        this.sendToClient(client, type, payload);
      }
    }
  }

  /**
   * Start the server
   */
  async start(): Promise<void> {
    // Start the pipeline runner
    await this.runner.start();

    // Start HTTP server
    return new Promise((resolve) => {
      this.server.listen(this.config.server.port, this.config.server.host, () => {
        log.info(
          { port: this.config.server.port, host: this.config.server.host },
          'API server started'
        );
        resolve();
      });
    });
  }

  /**
   * Stop the server
   */
  async stop(): Promise<void> {
    // Close all WebSocket connections
    for (const client of this.clients.values()) {
      client.ws.close();
    }
    this.clients.clear();

    // Stop the runner
    await this.runner.stop();

    // Close HTTP server
    return new Promise((resolve, reject) => {
      this.server.close((err) => {
        if (err) {
          reject(err);
        } else {
          log.info('API server stopped');
          resolve();
        }
      });
    });
  }

  /**
   * Get the Express app (for testing)
   */
  getApp(): express.Application {
    return this.app;
  }

  /**
   * Get connected client count
   */
  getClientCount(): number {
    return this.clients.size;
  }
}

/**
 * Singleton instance
 */
let serverInstance: ApiServer | null = null;

/**
 * Get the shared ApiServer instance
 */
export function getServer(): ApiServer {
  if (!serverInstance) {
    serverInstance = new ApiServer();
  }
  return serverInstance;
}

/**
 * Reset the server instance (for testing)
 */
export async function resetServer(): Promise<void> {
  if (serverInstance) {
    await serverInstance.stop();
    serverInstance = null;
  }
}

/**
 * Main entry point when running directly
 */
async function main(): Promise<void> {
  try {
    // Load configuration
    const config = loadConfig();
    setConfig(config);

    // Create and start server
    const server = getServer();
    await server.start();

    // Handle shutdown
    const shutdown = async () => {
      log.info('Shutting down...');
      await server.stop();
      process.exit(0);
    };

    process.on('SIGINT', shutdown);
    process.on('SIGTERM', shutdown);

  } catch (err) {
    logError(err, { action: 'server-startup' });
    process.exit(1);
  }
}

// Run if executed directly
const isMainModule = import.meta.url === `file://${process.argv[1]}`;
if (isMainModule) {
  main();
}
