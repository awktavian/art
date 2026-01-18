/**
 * @fileoverview Tests for configuration management
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { loadConfig, getConfig, setConfig, resetConfig } from '../src/config.js';
import type { Config } from '../src/config.js';

describe('Configuration', () => {
  beforeEach(() => {
    resetConfig();
    // Set minimal required config
    process.env['GEMINI_API_KEY'] = 'test-api-key';
  });

  afterEach(() => {
    resetConfig();
    delete process.env['GEMINI_API_KEY'];
    delete process.env['QA_PIPELINE_PORT'];
    delete process.env['STORAGE_TYPE'];
    delete process.env['MAX_CONCURRENT_JOBS'];
  });

  describe('loadConfig', () => {
    it('should load config with defaults', () => {
      const config = loadConfig();

      expect(config.server.port).toBe(3847);
      expect(config.server.host).toBe('localhost');
      expect(config.gemini.model).toBe('gemini-2.0-flash-exp');
      expect(config.storage.type).toBe('local');
      expect(config.processing.maxConcurrentJobs).toBe(2);
    });

    it('should load from environment variables', () => {
      process.env['QA_PIPELINE_PORT'] = '4000';
      process.env['STORAGE_TYPE'] = 'gcs';
      process.env['MAX_CONCURRENT_JOBS'] = '4';

      const config = loadConfig();

      expect(config.server.port).toBe(4000);
      expect(config.storage.type).toBe('gcs');
      expect(config.processing.maxConcurrentJobs).toBe(4);
    });

    it('should accept overrides', () => {
      const config = loadConfig({
        server: { port: 5000, host: '0.0.0.0' },
        processing: { maxConcurrentJobs: 8, frameInterval: 2, maxFramesPerVideo: 50, tempDir: './temp', maxVideoSizeMb: 1000 }
      } as Partial<Config>);

      expect(config.server.port).toBe(5000);
      expect(config.server.host).toBe('0.0.0.0');
      expect(config.processing.maxConcurrentJobs).toBe(8);
    });

    it('should throw on missing API key', () => {
      delete process.env['GEMINI_API_KEY'];

      expect(() => loadConfig()).toThrow('Configuration validation failed');
    });

    it('should validate API key is not empty', () => {
      process.env['GEMINI_API_KEY'] = '';

      expect(() => loadConfig()).toThrow('Configuration validation failed');
    });
  });

  describe('getConfig', () => {
    it('should return cached config', () => {
      const config1 = getConfig();
      const config2 = getConfig();

      expect(config1).toBe(config2);
    });

    it('should lazy load if not set', () => {
      const config = getConfig();
      expect(config).toBeDefined();
      expect(config.gemini.apiKey).toBe('test-api-key');
    });
  });

  describe('setConfig', () => {
    it('should set custom config', () => {
      const customConfig = loadConfig({
        server: { port: 9999, host: 'custom' }
      } as Partial<Config>);

      setConfig(customConfig);

      const retrieved = getConfig();
      expect(retrieved.server.port).toBe(9999);
    });
  });

  describe('resetConfig', () => {
    it('should clear cached config', () => {
      const config1 = getConfig();
      expect(config1.server.port).toBe(3847);

      process.env['QA_PIPELINE_PORT'] = '8888';
      resetConfig();

      const config2 = getConfig();
      expect(config2.server.port).toBe(8888);
    });
  });

  describe('config validation', () => {
    it('should validate port is positive', () => {
      expect(() => loadConfig({
        gemini: { apiKey: 'test', model: 'model', maxRetries: 3, requestsPerMinute: 10, requestsPerDay: 1500 },
        server: { port: -1, host: 'localhost' }
      } as Partial<Config>)).toThrow();
    });

    it('should validate storage type enum', () => {
      process.env['STORAGE_TYPE'] = 'invalid';

      expect(() => loadConfig()).toThrow('Configuration validation failed');
    });

    it('should coerce string numbers from env', () => {
      process.env['QA_PIPELINE_PORT'] = '3000';
      process.env['GEMINI_RPM'] = '20';
      process.env['MAX_FRAMES'] = '200';

      const config = loadConfig();

      expect(config.server.port).toBe(3000);
      expect(config.gemini.requestsPerMinute).toBe(20);
      expect(config.processing.maxFramesPerVideo).toBe(200);
    });
  });
});
