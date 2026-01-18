/**
 * @fileoverview Configuration management for the QA Pipeline
 *
 * Centralized configuration with environment variable support
 * and sensible defaults for development.
 */

import { z } from 'zod';
import { logger } from './logger.js';

/**
 * Configuration schema with validation
 */
const ConfigSchema = z.object({
  // Server configuration
  server: z.object({
    port: z.coerce.number().int().positive().default(3847),
    host: z.string().default('localhost')
  }),

  // Gemini API configuration
  gemini: z.object({
    apiKey: z.string().min(1),
    model: z.string().default('gemini-2.0-flash-exp'),
    maxRetries: z.coerce.number().int().positive().default(3),
    requestsPerMinute: z.coerce.number().int().positive().default(10),
    requestsPerDay: z.coerce.number().int().positive().default(1500)
  }),

  // Storage configuration
  storage: z.object({
    type: z.enum(['local', 'gcs']).default('local'),
    localPath: z.string().default('./data'),
    gcsBucket: z.string().optional(),
    gcsKeyFile: z.string().optional()
  }),

  // Database configuration
  database: z.object({
    path: z.string().default('./data/qa-pipeline.db')
  }),

  // Processing configuration
  processing: z.object({
    maxConcurrentJobs: z.coerce.number().int().positive().default(2),
    frameInterval: z.coerce.number().positive().default(1),
    maxFramesPerVideo: z.coerce.number().int().positive().default(100),
    tempDir: z.string().default('./data/temp'),
    maxVideoSizeMb: z.coerce.number().positive().default(500)
  }),

  // Pipeline configuration
  pipeline: z.object({
    watchDirs: z.array(z.string()).default([]),
    autoAnalyze: z.boolean().default(false),
    retainAnalysisDays: z.coerce.number().int().positive().default(30)
  })
});

export type Config = z.infer<typeof ConfigSchema>;

/**
 * Load configuration from environment variables
 */
function loadFromEnv(): Record<string, unknown> {
  return {
    server: {
      port: process.env['QA_PIPELINE_PORT'],
      host: process.env['QA_PIPELINE_HOST']
    },
    gemini: {
      apiKey: process.env['GEMINI_API_KEY'] ?? process.env['GOOGLE_API_KEY'],
      model: process.env['GEMINI_MODEL'],
      maxRetries: process.env['GEMINI_MAX_RETRIES'],
      requestsPerMinute: process.env['GEMINI_RPM'],
      requestsPerDay: process.env['GEMINI_RPD']
    },
    storage: {
      type: process.env['STORAGE_TYPE'],
      localPath: process.env['STORAGE_LOCAL_PATH'],
      gcsBucket: process.env['GCS_BUCKET'],
      gcsKeyFile: process.env['GCS_KEY_FILE']
    },
    database: {
      path: process.env['DATABASE_PATH']
    },
    processing: {
      maxConcurrentJobs: process.env['MAX_CONCURRENT_JOBS'],
      frameInterval: process.env['FRAME_INTERVAL'],
      maxFramesPerVideo: process.env['MAX_FRAMES'],
      tempDir: process.env['TEMP_DIR'],
      maxVideoSizeMb: process.env['MAX_VIDEO_SIZE_MB']
    },
    pipeline: {
      watchDirs: process.env['WATCH_DIRS']?.split(',').filter(Boolean),
      autoAnalyze: process.env['AUTO_ANALYZE'] === 'true',
      retainAnalysisDays: process.env['RETAIN_DAYS']
    }
  };
}

/**
 * Deep merge objects, filtering out undefined values
 */
function deepMerge(target: Record<string, unknown>, source: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = { ...target };

  for (const [key, value] of Object.entries(source)) {
    if (value === undefined || value === null || value === '') {
      continue;
    }

    if (typeof value === 'object' && !Array.isArray(value)) {
      result[key] = deepMerge(
        (target[key] as Record<string, unknown>) ?? {},
        value as Record<string, unknown>
      );
    } else {
      result[key] = value;
    }
  }

  return result;
}

/**
 * Load and validate configuration
 *
 * @param overrides - Optional configuration overrides
 * @returns Validated configuration object
 * @throws If required configuration is missing
 */
export function loadConfig(overrides?: Partial<Config>): Config {
  const envConfig = loadFromEnv();
  const merged = deepMerge(envConfig, (overrides ?? {}) as Record<string, unknown>);

  const result = ConfigSchema.safeParse(merged);

  if (!result.success) {
    const errors = result.error.errors.map(e => `${e.path.join('.')}: ${e.message}`);
    logger.error({ errors }, 'Configuration validation failed');
    throw new Error(`Configuration validation failed:\n${errors.join('\n')}`);
  }

  logger.info(
    {
      serverPort: result.data.server.port,
      storageType: result.data.storage.type,
      geminiModel: result.data.gemini.model,
      maxConcurrentJobs: result.data.processing.maxConcurrentJobs
    },
    'Configuration loaded'
  );

  return result.data;
}

/**
 * Global configuration instance (lazy loaded)
 */
let configInstance: Config | null = null;

/**
 * Get the global configuration instance
 *
 * @returns Configuration object
 */
export function getConfig(): Config {
  if (!configInstance) {
    configInstance = loadConfig();
  }
  return configInstance;
}

/**
 * Reset the global configuration (useful for testing)
 */
export function resetConfig(): void {
  configInstance = null;
}

/**
 * Set custom configuration (useful for testing)
 */
export function setConfig(config: Config): void {
  configInstance = config;
}
