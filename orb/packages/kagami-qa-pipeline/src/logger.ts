/**
 * @fileoverview Structured logging configuration using Pino
 *
 * Provides consistent, performant logging throughout the QA pipeline.
 */

import pino from 'pino';

/**
 * Log levels available
 */
export type LogLevel = 'fatal' | 'error' | 'warn' | 'info' | 'debug' | 'trace';

/**
 * Environment-based configuration
 */
const isDevelopment = process.env['NODE_ENV'] !== 'production';
const logLevel = (process.env['LOG_LEVEL'] as LogLevel) ?? (isDevelopment ? 'debug' : 'info');

/**
 * Base logger configuration
 */
const baseConfig: pino.LoggerOptions = {
  level: logLevel,
  base: {
    service: 'kagami-qa-pipeline',
    version: process.env['npm_package_version'] ?? '0.1.0'
  },
  timestamp: pino.stdTimeFunctions.isoTime,
  formatters: {
    level: (label) => ({ level: label })
  }
};

/**
 * Development transport for pretty printing
 */
const devTransport: pino.TransportSingleOptions = {
  target: 'pino-pretty',
  options: {
    colorize: true,
    translateTime: 'SYS:standard',
    ignore: 'pid,hostname',
    messageFormat: '{msg}'
  }
};

/**
 * Create the root logger instance
 */
export const logger = isDevelopment
  ? pino(baseConfig, pino.transport(devTransport))
  : pino(baseConfig);

/**
 * Create a child logger with additional context
 *
 * @param bindings - Additional context to include in all log entries
 * @returns Child logger instance
 *
 * @example
 * ```typescript
 * const log = createChildLogger({ component: 'analyzer', videoId: 'abc123' });
 * log.info('Starting analysis');
 * // Output: { level: 'info', component: 'analyzer', videoId: 'abc123', msg: 'Starting analysis' }
 * ```
 */
export function createChildLogger(bindings: Record<string, unknown>): pino.Logger {
  return logger.child(bindings);
}

/**
 * Performance timing utility
 *
 * @param label - Label for the timing measurement
 * @returns Function to call when operation completes
 *
 * @example
 * ```typescript
 * const done = startTiming('frame-extraction');
 * await extractFrames(video);
 * done(); // Logs: "frame-extraction completed in 1234ms"
 * ```
 */
export function startTiming(label: string): () => void {
  const start = performance.now();
  return () => {
    const duration = Math.round(performance.now() - start);
    logger.debug({ label, durationMs: duration }, `${label} completed in ${duration}ms`);
  };
}

/**
 * Error logging with stack trace preservation
 *
 * @param error - Error object
 * @param context - Additional context
 */
export function logError(error: unknown, context?: Record<string, unknown>): void {
  if (error instanceof Error) {
    logger.error(
      {
        err: {
          message: error.message,
          name: error.name,
          stack: error.stack
        },
        ...context
      },
      error.message
    );
  } else {
    logger.error({ err: error, ...context }, 'Unknown error occurred');
  }
}

export default logger;
