/**
 * @fileoverview Tests for type definitions and Zod schemas
 */

import { describe, it, expect } from 'vitest';
import {
  PlatformSchema,
  SeveritySchema,
  IssueCategorySchema,
  DetectedIssueSchema,
  AnalysisConfigSchema,
  AnalysisResultSchema,
  ListAnalysesQuerySchema,
  ListIssuesQuerySchema,
  AnalyzeRequestSchema
} from '../src/types.js';

describe('Type Schemas', () => {
  describe('PlatformSchema', () => {
    it('should accept valid platforms', () => {
      const platforms = ['ios', 'android', 'watchos', 'tvos', 'visionos', 'desktop', 'web'];
      for (const platform of platforms) {
        expect(PlatformSchema.parse(platform)).toBe(platform);
      }
    });

    it('should reject invalid platforms', () => {
      expect(() => PlatformSchema.parse('invalid')).toThrow();
      expect(() => PlatformSchema.parse('')).toThrow();
      expect(() => PlatformSchema.parse(123)).toThrow();
    });
  });

  describe('SeveritySchema', () => {
    it('should accept valid severities', () => {
      expect(SeveritySchema.parse('critical')).toBe('critical');
      expect(SeveritySchema.parse('warning')).toBe('warning');
      expect(SeveritySchema.parse('info')).toBe('info');
    });

    it('should reject invalid severities', () => {
      expect(() => SeveritySchema.parse('error')).toThrow();
      expect(() => SeveritySchema.parse('HIGH')).toThrow();
    });
  });

  describe('IssueCategorySchema', () => {
    it('should accept valid categories', () => {
      const categories = [
        'ui_consistency',
        'accessibility',
        'animation',
        'layout',
        'state',
        'error',
        'performance',
        'other'
      ];
      for (const category of categories) {
        expect(IssueCategorySchema.parse(category)).toBe(category);
      }
    });

    it('should reject invalid categories', () => {
      expect(() => IssueCategorySchema.parse('bug')).toThrow();
      expect(() => IssueCategorySchema.parse('UI')).toThrow();
    });
  });

  describe('DetectedIssueSchema', () => {
    it('should accept valid issue', () => {
      const issue = {
        id: '550e8400-e29b-41d4-a716-446655440000',
        timestamp: 5.5,
        severity: 'warning',
        category: 'layout',
        description: 'Text is truncated in button',
        confidence: 0.85
      };

      const result = DetectedIssueSchema.parse(issue);
      expect(result.id).toBe(issue.id);
      expect(result.timestamp).toBe(5.5);
      expect(result.severity).toBe('warning');
    });

    it('should accept issue with optional fields', () => {
      const issue = {
        id: '550e8400-e29b-41d4-a716-446655440000',
        timestamp: 10,
        severity: 'critical',
        category: 'accessibility',
        description: 'Low contrast ratio',
        framePath: '/path/to/frame.jpg',
        suggestedFix: 'Increase text contrast to 4.5:1',
        confidence: 0.95,
        metadata: { contrastRatio: 2.5 }
      };

      const result = DetectedIssueSchema.parse(issue);
      expect(result.framePath).toBe('/path/to/frame.jpg');
      expect(result.suggestedFix).toBeDefined();
      expect(result.metadata).toEqual({ contrastRatio: 2.5 });
    });

    it('should reject invalid issue', () => {
      // Missing required fields
      expect(() => DetectedIssueSchema.parse({})).toThrow();

      // Invalid UUID
      expect(() => DetectedIssueSchema.parse({
        id: 'not-a-uuid',
        timestamp: 0,
        severity: 'warning',
        category: 'layout',
        description: 'Test',
        confidence: 0.5
      })).toThrow();

      // Negative timestamp
      expect(() => DetectedIssueSchema.parse({
        id: '550e8400-e29b-41d4-a716-446655440000',
        timestamp: -1,
        severity: 'warning',
        category: 'layout',
        description: 'Test',
        confidence: 0.5
      })).toThrow();

      // Confidence out of range
      expect(() => DetectedIssueSchema.parse({
        id: '550e8400-e29b-41d4-a716-446655440000',
        timestamp: 0,
        severity: 'warning',
        category: 'layout',
        description: 'Test',
        confidence: 1.5
      })).toThrow();
    });
  });

  describe('AnalysisConfigSchema', () => {
    it('should accept minimal config', () => {
      const config = {
        platform: 'ios',
        testName: 'Login Flow'
      };

      const result = AnalysisConfigSchema.parse(config);
      expect(result.platform).toBe('ios');
      expect(result.testName).toBe('Login Flow');
      expect(result.frameInterval).toBe(1); // default
      expect(result.maxFrames).toBe(100); // default
    });

    it('should accept full config', () => {
      const config = {
        platform: 'android',
        testName: 'Checkout Flow',
        testSuite: 'E2E Tests',
        frameInterval: 0.5,
        maxFrames: 200,
        customPrompts: ['Check for loading spinners', 'Verify price formatting'],
        excludeKnownIssues: true
      };

      const result = AnalysisConfigSchema.parse(config);
      expect(result.testSuite).toBe('E2E Tests');
      expect(result.frameInterval).toBe(0.5);
      expect(result.customPrompts).toHaveLength(2);
    });
  });

  describe('ListAnalysesQuerySchema', () => {
    it('should apply defaults', () => {
      const result = ListAnalysesQuerySchema.parse({});
      expect(result.offset).toBe(0);
      expect(result.limit).toBe(20);
      expect(result.sortBy).toBe('createdAt');
      expect(result.sortDir).toBe('desc');
    });

    it('should coerce string numbers', () => {
      const result = ListAnalysesQuerySchema.parse({
        offset: '10',
        limit: '50'
      });
      expect(result.offset).toBe(10);
      expect(result.limit).toBe(50);
    });

    it('should accept filters', () => {
      const result = ListAnalysesQuerySchema.parse({
        status: 'completed',
        platform: 'ios',
        testName: 'Login'
      });
      expect(result.status).toBe('completed');
      expect(result.platform).toBe('ios');
      expect(result.testName).toBe('Login');
    });

    it('should reject invalid limit', () => {
      expect(() => ListAnalysesQuerySchema.parse({ limit: 0 })).toThrow();
      expect(() => ListAnalysesQuerySchema.parse({ limit: 101 })).toThrow();
    });
  });

  describe('ListIssuesQuerySchema', () => {
    it('should apply defaults', () => {
      const result = ListIssuesQuerySchema.parse({});
      expect(result.offset).toBe(0);
      expect(result.limit).toBe(50);
    });

    it('should accept filters', () => {
      const result = ListIssuesQuerySchema.parse({
        analysisId: '550e8400-e29b-41d4-a716-446655440000',
        severity: 'critical',
        category: 'accessibility',
        platform: 'android'
      });
      expect(result.analysisId).toBe('550e8400-e29b-41d4-a716-446655440000');
      expect(result.severity).toBe('critical');
    });
  });

  describe('AnalyzeRequestSchema', () => {
    it('should accept valid request', () => {
      const request = {
        videoPath: '/path/to/video.mp4',
        config: {
          platform: 'ios'
        }
      };

      const result = AnalyzeRequestSchema.parse(request);
      expect(result.videoPath).toBe('/path/to/video.mp4');
      expect(result.config.platform).toBe('ios');
    });

    it('should accept request with priority', () => {
      const request = {
        videoPath: '/video.mp4',
        config: {
          platform: 'web',
          testName: 'Dashboard'
        },
        priority: 10
      };

      const result = AnalyzeRequestSchema.parse(request);
      expect(result.priority).toBe(10);
    });

    it('should require platform', () => {
      expect(() => AnalyzeRequestSchema.parse({
        videoPath: '/video.mp4',
        config: {}
      })).toThrow();
    });
  });

  describe('AnalysisResultSchema', () => {
    it('should accept minimal result', () => {
      const result = AnalysisResultSchema.parse({
        id: '550e8400-e29b-41d4-a716-446655440000',
        videoPath: '/path/to/video.mp4',
        config: {
          platform: 'ios',
          testName: 'Test'
        },
        status: 'pending',
        createdAt: '2024-01-15T10:00:00Z'
      });

      expect(result.id).toBeDefined();
      expect(result.framesAnalyzed).toBe(0);
      expect(result.issues).toEqual([]);
    });

    it('should accept complete result', () => {
      const result = AnalysisResultSchema.parse({
        id: '550e8400-e29b-41d4-a716-446655440000',
        videoPath: '/path/to/video.mp4',
        config: {
          platform: 'android',
          testName: 'Checkout'
        },
        status: 'completed',
        createdAt: '2024-01-15T10:00:00Z',
        startedAt: '2024-01-15T10:00:01Z',
        completedAt: '2024-01-15T10:01:00Z',
        durationMs: 59000,
        videoDuration: 120,
        framesAnalyzed: 100,
        issues: [
          {
            id: '660e8400-e29b-41d4-a716-446655440000',
            timestamp: 5,
            severity: 'warning',
            category: 'layout',
            description: 'Button text truncated',
            confidence: 0.9
          }
        ],
        qualityScore: 85
      });

      expect(result.status).toBe('completed');
      expect(result.qualityScore).toBe(85);
      expect(result.issues).toHaveLength(1);
    });
  });
});
