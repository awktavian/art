/**
 * @fileoverview CI Results Publisher for QA Dashboard
 *
 * Publishes Byzantine quality analysis results from CI pipelines
 * to the QA dashboard for tracking and visualization.
 *
 * Colony: Crystal (e7) -- Verification & Polish
 * h(x) >= 0. Always.
 */

import { promises as fs } from 'node:fs';
import path from 'node:path';
import { createChildLogger, logError } from '../logger.js';

const log = createChildLogger({ component: 'ci-publisher' });

// =============================================================================
// TYPES
// =============================================================================

/**
 * Byzantine scores structure matching the analyzer output
 */
export interface ByzantineScores {
  technical: number;
  aesthetic: number;
  accessibility: number;
  emotional: number;
  polish: number;
  delight: number;
}

/**
 * CI analysis result payload
 */
export interface CIAnalysisPayload {
  type: 'byzantine_analysis';
  timestamp: string;
  workflowRunId: string;
  repository: string;
  commit: string;
  branch: string;
  sourceWorkflow?: string | undefined;
  videoCount: number;
  qualityGate: {
    threshold: number;
    passed: boolean;
    overallScore: number;
  };
  byzantineScores: ByzantineScores;
  criticalIssues: number;
  artifactsUrl?: string | undefined;
  videos?: Array<{
    path: string;
    scores: ByzantineScores;
    overallScore: number;
    issueCount: number;
  }> | undefined;
  issues?: Array<{
    severity: string;
    dimension: string;
    description: string;
  }> | undefined;
}

/**
 * Dashboard API configuration
 */
export interface DashboardConfig {
  url: string;
  token?: string | undefined;
  timeout?: number | undefined;
}

/**
 * Historical trend data point
 */
export interface TrendDataPoint {
  timestamp: string;
  commit: string;
  branch: string;
  overallScore: number;
  byzantineScores: ByzantineScores;
  passed: boolean;
}

// =============================================================================
// CI RESULTS PUBLISHER
// =============================================================================

/**
 * CIPublisher - Publishes analysis results to the QA dashboard
 *
 * Handles:
 * - Sending results to dashboard API
 * - Local storage for offline/development mode
 * - Trend data aggregation
 * - GitHub Actions summary generation
 */
export class CIPublisher {
  private config: DashboardConfig | null;
  private localStoragePath: string;

  constructor(config?: DashboardConfig) {
    this.config = config ?? null;
    this.localStoragePath = process.env['CI_RESULTS_PATH'] ?? './ci-results';
  }

  /**
   * Publish analysis results to the dashboard
   *
   * @param payload - Analysis results payload
   * @returns Whether publish was successful
   */
  async publish(payload: CIAnalysisPayload): Promise<boolean> {
    log.info(
      {
        workflowRunId: payload.workflowRunId,
        commit: payload.commit,
        passed: payload.qualityGate.passed,
      },
      'Publishing CI results'
    );

    let success = true;

    // Try to publish to dashboard API if configured
    if (this.config?.url) {
      try {
        await this.publishToAPI(payload);
        log.info('Published to dashboard API');
      } catch (error) {
        logError(error, { action: 'publish-to-api' });
        success = false;
      }
    }

    // Always save locally for backup/debugging
    try {
      await this.saveLocally(payload);
      log.debug('Saved results locally');
    } catch (error) {
      logError(error, { action: 'save-locally' });
    }

    // Generate GitHub Actions summary if in CI
    if (process.env['GITHUB_ACTIONS'] === 'true') {
      try {
        await this.generateGitHubSummary(payload);
      } catch (error) {
        logError(error, { action: 'github-summary' });
      }
    }

    return success;
  }

  /**
   * Publish to dashboard API
   */
  private async publishToAPI(payload: CIAnalysisPayload): Promise<void> {
    if (!this.config?.url) {
      throw new Error('Dashboard URL not configured');
    }

    const response = await fetch(`${this.config.url}/api/v1/byzantine-analysis`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(this.config.token && { Authorization: `Bearer ${this.config.token}` }),
      },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(this.config.timeout ?? 30000),
    });

    if (!response.ok) {
      throw new Error(`Dashboard API error: ${response.status} ${response.statusText}`);
    }
  }

  /**
   * Save results locally for backup
   */
  private async saveLocally(payload: CIAnalysisPayload): Promise<void> {
    await fs.mkdir(this.localStoragePath, { recursive: true });

    const filename = `analysis-${payload.commit.substring(0, 8)}-${Date.now()}.json`;
    const filepath = path.join(this.localStoragePath, filename);

    await fs.writeFile(filepath, JSON.stringify(payload, null, 2));

    // Update trends file
    await this.updateTrends(payload);
  }

  /**
   * Update historical trends data
   */
  private async updateTrends(payload: CIAnalysisPayload): Promise<void> {
    const trendsPath = path.join(this.localStoragePath, 'trends.json');

    let trends: TrendDataPoint[] = [];

    try {
      const existing = await fs.readFile(trendsPath, 'utf-8');
      trends = JSON.parse(existing);
    } catch {
      // File doesn't exist, start fresh
    }

    // Add new data point
    trends.push({
      timestamp: payload.timestamp,
      commit: payload.commit,
      branch: payload.branch,
      overallScore: payload.qualityGate.overallScore,
      byzantineScores: payload.byzantineScores,
      passed: payload.qualityGate.passed,
    });

    // Keep last 100 data points
    if (trends.length > 100) {
      trends = trends.slice(-100);
    }

    await fs.writeFile(trendsPath, JSON.stringify(trends, null, 2));
  }

  /**
   * Generate GitHub Actions summary
   */
  private async generateGitHubSummary(payload: CIAnalysisPayload): Promise<void> {
    const summaryFile = process.env['GITHUB_STEP_SUMMARY'];
    if (!summaryFile) return;

    const { byzantineScores, qualityGate } = payload;

    let summary = `## Byzantine Quality Analysis\n\n`;
    summary += `### Quality Gate: ${qualityGate.passed ? ':white_check_mark: PASSED' : ':x: FAILED'}\n\n`;
    summary += `**Threshold: ${qualityGate.threshold}/100**\n\n`;

    summary += `### Scores\n\n`;
    summary += `| Dimension | Score | Status |\n`;
    summary += `|-----------|-------|--------|\n`;

    const dimensions: (keyof ByzantineScores)[] = [
      'technical',
      'aesthetic',
      'accessibility',
      'emotional',
      'polish',
      'delight',
    ];

    for (const dim of dimensions) {
      const score = byzantineScores[dim];
      const status = score >= qualityGate.threshold ? ':white_check_mark:' : ':x:';
      const dimName = dim.charAt(0).toUpperCase() + dim.slice(1);
      summary += `| ${dimName} | ${score}/100 | ${status} |\n`;
    }

    summary += `\n**Overall: ${qualityGate.overallScore}/100**\n\n`;

    if (payload.criticalIssues > 0) {
      summary += `### :warning: Critical Issues: ${payload.criticalIssues}\n\n`;
    }

    if (payload.videoCount > 0) {
      summary += `### Videos Analyzed: ${payload.videoCount}\n\n`;
    }

    if (payload.artifactsUrl) {
      summary += `[View Analysis Artifacts](${payload.artifactsUrl})\n\n`;
    }

    summary += `---\n`;
    summary += `*h(x) >= 0. Always.*\n`;
    summary += `*craft(x) → ∞ always*\n`;

    await fs.appendFile(summaryFile, summary);
  }

  /**
   * Get trend data for visualization
   *
   * @param branch - Filter by branch (optional)
   * @param limit - Maximum data points to return
   * @returns Array of trend data points
   */
  async getTrends(branch?: string, limit = 50): Promise<TrendDataPoint[]> {
    const trendsPath = path.join(this.localStoragePath, 'trends.json');

    try {
      const data = await fs.readFile(trendsPath, 'utf-8');
      let trends: TrendDataPoint[] = JSON.parse(data);

      if (branch) {
        trends = trends.filter((t) => t.branch === branch);
      }

      return trends.slice(-limit);
    } catch {
      return [];
    }
  }

  /**
   * Get aggregated statistics
   */
  async getStats(): Promise<{
    totalAnalyses: number;
    passRate: number;
    averageScore: number;
    byDimension: Record<keyof ByzantineScores, { avg: number; min: number; max: number }>;
  }> {
    const trends = await this.getTrends(undefined, 100);

    if (trends.length === 0) {
      return {
        totalAnalyses: 0,
        passRate: 0,
        averageScore: 0,
        byDimension: {
          technical: { avg: 0, min: 0, max: 0 },
          aesthetic: { avg: 0, min: 0, max: 0 },
          accessibility: { avg: 0, min: 0, max: 0 },
          emotional: { avg: 0, min: 0, max: 0 },
          polish: { avg: 0, min: 0, max: 0 },
          delight: { avg: 0, min: 0, max: 0 },
        },
      };
    }

    const passCount = trends.filter((t) => t.passed).length;
    const avgScore =
      trends.reduce((sum, t) => sum + t.overallScore, 0) / trends.length;

    const dimensions: (keyof ByzantineScores)[] = [
      'technical',
      'aesthetic',
      'accessibility',
      'emotional',
      'polish',
      'delight',
    ];

    const byDimension: Record<
      keyof ByzantineScores,
      { avg: number; min: number; max: number }
    > = {} as Record<keyof ByzantineScores, { avg: number; min: number; max: number }>;

    for (const dim of dimensions) {
      const scores = trends.map((t) => t.byzantineScores[dim]);
      byDimension[dim] = {
        avg: Math.round(scores.reduce((a, b) => a + b, 0) / scores.length),
        min: Math.min(...scores),
        max: Math.max(...scores),
      };
    }

    return {
      totalAnalyses: trends.length,
      passRate: Math.round((passCount / trends.length) * 100),
      averageScore: Math.round(avgScore),
      byDimension,
    };
  }
}

// =============================================================================
// CONVENIENCE FUNCTIONS
// =============================================================================

/**
 * Singleton publisher instance
 */
let publisherInstance: CIPublisher | null = null;

/**
 * Get the shared publisher instance
 */
export function getPublisher(): CIPublisher {
  if (!publisherInstance) {
    // Try to configure from environment
    const url = process.env['QA_DASHBOARD_URL'];
    const token = process.env['QA_DASHBOARD_TOKEN'];

    publisherInstance = new CIPublisher(url ? { url, token } : undefined);
  }
  return publisherInstance;
}

/**
 * Publish CI results to dashboard
 *
 * Convenience function for quick publishing.
 *
 * @param payload - Analysis results
 * @returns Whether publish succeeded
 */
export async function publishCIResults(payload: CIAnalysisPayload): Promise<boolean> {
  return getPublisher().publish(payload);
}

/**
 * Create a payload from local analysis results file
 *
 * @param resultsPath - Path to results JSON file
 * @param context - Additional CI context
 * @returns Formatted payload for publishing
 */
export async function createPayloadFromResults(
  resultsPath: string,
  context: {
    workflowRunId: string;
    repository: string;
    commit: string;
    branch: string;
    artifactsUrl?: string;
  }
): Promise<CIAnalysisPayload> {
  const data = await fs.readFile(resultsPath, 'utf-8');
  const results = JSON.parse(data);

  return {
    type: 'byzantine_analysis',
    timestamp: results.timestamp ?? new Date().toISOString(),
    workflowRunId: context.workflowRunId,
    repository: context.repository,
    commit: context.commit,
    branch: context.branch,
    artifactsUrl: context.artifactsUrl,
    videoCount: results.videos?.length ?? 0,
    qualityGate: {
      threshold: results.threshold ?? 90,
      passed: results.meetsQualityBar ?? false,
      overallScore: results.overallScore ?? 0,
    },
    byzantineScores: results.byzantineScores ?? {
      technical: 0,
      aesthetic: 0,
      accessibility: 0,
      emotional: 0,
      polish: 0,
      delight: 0,
    },
    criticalIssues: results.issues?.filter(
      (i: { severity: string }) => i.severity === 'critical'
    ).length ?? 0,
    videos: results.videos,
    issues: results.issues,
  };
}
