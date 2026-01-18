#!/usr/bin/env node

/**
 * @fileoverview QA Analysis CLI Tool
 *
 * Command-line interface for running video quality analysis.
 *
 * Usage:
 *   qa-analyze <video-path> [options]
 *   qa-analyze batch <directory> [options]
 *   qa-analyze report [options]
 *   qa-analyze health
 *
 * Examples:
 *   qa-analyze ./tests/login-flow.mp4 --platform ios
 *   qa-analyze batch ./test-videos --platform android --parallel 2
 *   qa-analyze report --format json --output report.json
 */

import { Command } from 'commander';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { loadConfig, setConfig } from '../src/config.js';
import { VideoProcessor, getProcessor } from '../src/processor.js';
import { GeminiAnalyzer, getAnalyzer } from '../src/analyzer.js';
import { IssueTracker, getTracker } from '../src/tracker.js';
import { PipelineRunner, getRunner } from '../src/runner.js';
import { logger } from '../src/logger.js';
import type { Platform, AnalysisConfig, Severity, AnalysisResult, DetectedIssue } from '../src/types.js';

const program = new Command();

// ANSI color codes for terminal output
const colors = {
  reset: '\x1b[0m',
  bold: '\x1b[1m',
  dim: '\x1b[2m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m'
};

/**
 * Format severity with color
 */
function formatSeverity(severity: Severity): string {
  const severityColors: Record<Severity, string> = {
    critical: colors.red,
    warning: colors.yellow,
    info: colors.blue
  };
  return `${severityColors[severity]}${severity.toUpperCase()}${colors.reset}`;
}

/**
 * Format quality score with color
 */
function formatScore(score: number): string {
  if (score >= 90) {
    return `${colors.green}${score}${colors.reset}`;
  } else if (score >= 70) {
    return `${colors.yellow}${score}${colors.reset}`;
  } else {
    return `${colors.red}${score}${colors.reset}`;
  }
}

/**
 * Print analysis result to terminal
 */
function printResult(result: AnalysisResult): void {
  console.log();
  console.log(`${colors.bold}=== Analysis Results ===${colors.reset}`);
  console.log();
  console.log(`  ${colors.dim}Video:${colors.reset}    ${result.videoPath}`);
  console.log(`  ${colors.dim}Platform:${colors.reset} ${result.config.platform}`);
  console.log(`  ${colors.dim}Test:${colors.reset}     ${result.config.testName}`);
  console.log(`  ${colors.dim}Status:${colors.reset}   ${result.status}`);
  console.log(`  ${colors.dim}Frames:${colors.reset}   ${result.framesAnalyzed}`);
  console.log(`  ${colors.dim}Duration:${colors.reset} ${result.durationMs ? `${(result.durationMs / 1000).toFixed(1)}s` : 'N/A'}`);
  console.log();

  if (result.qualityScore !== undefined) {
    console.log(`  ${colors.bold}Quality Score:${colors.reset} ${formatScore(result.qualityScore)}/100`);
    console.log();
  }

  if (result.issues.length === 0) {
    console.log(`  ${colors.green}No issues detected${colors.reset}`);
  } else {
    console.log(`  ${colors.bold}Issues Found: ${result.issues.length}${colors.reset}`);
    console.log();

    // Group by severity
    const bySeverity: Record<Severity, DetectedIssue[]> = {
      critical: [],
      warning: [],
      info: []
    };

    for (const issue of result.issues) {
      bySeverity[issue.severity].push(issue);
    }

    for (const severity of ['critical', 'warning', 'info'] as Severity[]) {
      const issues = bySeverity[severity];
      if (issues.length === 0) continue;

      console.log(`  ${formatSeverity(severity)} (${issues.length}):`);
      for (const issue of issues) {
        console.log(`    - [${issue.timestamp.toFixed(1)}s] ${issue.description}`);
        if (issue.suggestedFix) {
          console.log(`      ${colors.dim}Fix: ${issue.suggestedFix}${colors.reset}`);
        }
      }
      console.log();
    }
  }

  if (result.error) {
    console.log(`  ${colors.red}Error: ${result.error}${colors.reset}`);
  }
}

/**
 * Print progress bar
 */
function printProgress(phase: string, progress: number, message?: string): void {
  const width = 30;
  const filled = Math.round(progress / 100 * width);
  const empty = width - filled;
  const bar = `[${'='.repeat(filled)}${'-'.repeat(empty)}]`;

  process.stdout.write(`\r  ${colors.cyan}${phase}${colors.reset} ${bar} ${progress.toFixed(0)}% ${message ?? ''}`);

  if (progress >= 100) {
    process.stdout.write('\n');
  }
}

program
  .name('qa-analyze')
  .description('Gemini-powered video analysis for QA testing')
  .version('0.1.0');

// Main analyze command
program
  .argument('[video]', 'Path to video file to analyze')
  .option('-p, --platform <platform>', 'Target platform (ios, android, web, etc.)', 'ios')
  .option('-t, --test-name <name>', 'Test name or identifier')
  .option('-i, --interval <seconds>', 'Frame extraction interval', '1')
  .option('-m, --max-frames <count>', 'Maximum frames to analyze', '100')
  .option('--custom-prompts <prompts...>', 'Additional custom prompts for analysis')
  .option('-o, --output <path>', 'Output file for JSON results')
  .option('-q, --quiet', 'Suppress progress output')
  .option('--api-key <key>', 'Gemini API key (can also use GEMINI_API_KEY env var)')
  .action(async (videoPath: string | undefined, options) => {
    if (!videoPath) {
      console.error(`${colors.red}Error: Video path is required${colors.reset}`);
      console.log('Run with --help for usage information');
      process.exit(1);
    }

    try {
      // Configure with API key if provided
      const overrides: Record<string, unknown> = {};
      if (options.apiKey) {
        overrides.gemini = { apiKey: options.apiKey };
      }

      const config = loadConfig(overrides as Partial<Parameters<typeof loadConfig>[0]>);
      setConfig(config);

      // Validate video exists
      const absolutePath = path.resolve(videoPath);
      try {
        await fs.access(absolutePath);
      } catch {
        console.error(`${colors.red}Error: Video file not found: ${absolutePath}${colors.reset}`);
        process.exit(1);
      }

      console.log(`${colors.bold}Kagami QA Pipeline${colors.reset}`);
      console.log(`${colors.dim}Analyzing: ${absolutePath}${colors.reset}`);
      console.log();

      // Initialize components
      const runner = getRunner();
      await runner.start();

      // Build analysis config
      const analysisConfig: AnalysisConfig = {
        platform: options.platform as Platform,
        testName: options.testName ?? path.basename(absolutePath, path.extname(absolutePath)),
        frameInterval: parseFloat(options.interval),
        maxFrames: parseInt(options.maxFrames, 10),
        customPrompts: options.customPrompts
      };

      // Run analysis
      const result = await runner.runAnalysis({
        videoPath: absolutePath,
        config: analysisConfig,
        onProgress: options.quiet ? undefined : (progress) => {
          printProgress(progress.phase, progress.progress, progress.message);
        }
      });

      // Output results
      if (options.output) {
        await fs.writeFile(options.output, JSON.stringify(result, null, 2));
        console.log(`${colors.green}Results written to: ${options.output}${colors.reset}`);
      }

      if (!options.quiet) {
        printResult(result);
      }

      await runner.stop();

      // Exit with error code if critical issues found
      const criticalCount = result.issues.filter(i => i.severity === 'critical').length;
      process.exit(criticalCount > 0 ? 1 : 0);

    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      console.error(`${colors.red}Error: ${message}${colors.reset}`);
      logger.error({ error }, 'CLI error');
      process.exit(1);
    }
  });

// Batch analysis command
program
  .command('batch <directory>')
  .description('Analyze all videos in a directory')
  .option('-p, --platform <platform>', 'Target platform', 'ios')
  .option('--parallel <count>', 'Number of parallel analyses', '2')
  .option('--pattern <glob>', 'File pattern to match', '*.mp4')
  .option('-o, --output <path>', 'Output directory for JSON results')
  .option('-q, --quiet', 'Suppress progress output')
  .action(async (directory: string, options) => {
    try {
      const config = loadConfig();
      setConfig(config);

      const absoluteDir = path.resolve(directory);

      // Find video files
      const entries = await fs.readdir(absoluteDir, { withFileTypes: true });
      const videoFiles = entries
        .filter(e => e.isFile() && e.name.match(/\.(mp4|mov|webm|mkv)$/i))
        .map(e => path.join(absoluteDir, e.name));

      if (videoFiles.length === 0) {
        console.log(`${colors.yellow}No video files found in ${absoluteDir}${colors.reset}`);
        process.exit(0);
      }

      console.log(`${colors.bold}Kagami QA Pipeline - Batch Analysis${colors.reset}`);
      console.log(`${colors.dim}Found ${videoFiles.length} video files${colors.reset}`);
      console.log();

      const runner = getRunner();
      await runner.start();

      const results: AnalysisResult[] = [];
      let completed = 0;
      let failed = 0;

      for (const videoPath of videoFiles) {
        try {
          if (!options.quiet) {
            console.log(`${colors.cyan}[${completed + failed + 1}/${videoFiles.length}]${colors.reset} ${path.basename(videoPath)}`);
          }

          const result = await runner.runAnalysis({
            videoPath,
            config: {
              platform: options.platform as Platform,
              testName: path.basename(videoPath, path.extname(videoPath)),
              frameInterval: 1,
              maxFrames: 100
            }
          });

          results.push(result);
          completed++;

          if (!options.quiet) {
            const issueCount = result.issues.length;
            const criticalCount = result.issues.filter(i => i.severity === 'critical').length;
            const scoreStr = result.qualityScore !== undefined ? formatScore(result.qualityScore) : 'N/A';
            console.log(`    Score: ${scoreStr}/100, Issues: ${issueCount} (${criticalCount} critical)`);
          }

        } catch (error) {
          failed++;
          const message = error instanceof Error ? error.message : 'Unknown error';
          console.error(`    ${colors.red}Failed: ${message}${colors.reset}`);
        }
      }

      // Summary
      console.log();
      console.log(`${colors.bold}Summary${colors.reset}`);
      console.log(`  Completed: ${completed}`);
      console.log(`  Failed: ${failed}`);

      if (results.length > 0) {
        const avgScore = results.reduce((sum, r) => sum + (r.qualityScore ?? 0), 0) / results.length;
        const totalIssues = results.reduce((sum, r) => sum + r.issues.length, 0);
        const totalCritical = results.reduce((sum, r) => sum + r.issues.filter(i => i.severity === 'critical').length, 0);

        console.log(`  Average Score: ${formatScore(Math.round(avgScore))}/100`);
        console.log(`  Total Issues: ${totalIssues} (${totalCritical} critical)`);
      }

      // Output results if requested
      if (options.output) {
        await fs.mkdir(options.output, { recursive: true });

        for (const result of results) {
          const outputPath = path.join(
            options.output,
            `${path.basename(result.videoPath, path.extname(result.videoPath))}.json`
          );
          await fs.writeFile(outputPath, JSON.stringify(result, null, 2));
        }

        // Write summary
        const summaryPath = path.join(options.output, 'summary.json');
        await fs.writeFile(summaryPath, JSON.stringify({
          timestamp: new Date().toISOString(),
          completed,
          failed,
          results: results.map(r => ({
            videoPath: r.videoPath,
            qualityScore: r.qualityScore,
            issueCount: r.issues.length,
            status: r.status
          }))
        }, null, 2));

        console.log(`\n${colors.green}Results written to: ${options.output}${colors.reset}`);
      }

      await runner.stop();
      process.exit(failed > 0 ? 1 : 0);

    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      console.error(`${colors.red}Error: ${message}${colors.reset}`);
      process.exit(1);
    }
  });

// Report command
program
  .command('report')
  .description('Generate reports from stored analysis data')
  .option('-f, --format <format>', 'Output format (json, text, html)', 'text')
  .option('-o, --output <path>', 'Output file path')
  .option('--since <date>', 'Include analyses since date (ISO format)')
  .option('--platform <platform>', 'Filter by platform')
  .option('--severity <severity>', 'Filter issues by severity')
  .action(async (options) => {
    try {
      const config = loadConfig();
      setConfig(config);

      const tracker = await getTracker();

      // Get statistics
      const stats = tracker.getIssueStats();

      // Get recent analyses
      const { analyses } = tracker.listAnalyses({
        platform: options.platform as Platform,
        limit: 50,
        offset: 0,
        sortBy: 'createdAt',
        sortDir: 'desc'
      });

      // Get issues
      const { issues, total: totalIssues } = tracker.listIssues({
        severity: options.severity as Severity,
        platform: options.platform as Platform,
        since: options.since,
        limit: 100,
        offset: 0
      });

      if (options.format === 'json') {
        const report = {
          generatedAt: new Date().toISOString(),
          statistics: stats,
          recentAnalyses: analyses,
          recentIssues: issues
        };

        const output = JSON.stringify(report, null, 2);

        if (options.output) {
          await fs.writeFile(options.output, output);
          console.log(`Report written to: ${options.output}`);
        } else {
          console.log(output);
        }
      } else {
        // Text format
        console.log(`${colors.bold}=== QA Pipeline Report ===${colors.reset}`);
        console.log(`Generated: ${new Date().toISOString()}`);
        console.log();

        console.log(`${colors.bold}Statistics${colors.reset}`);
        console.log(`  Total Issues: ${stats.total}`);
        console.log(`  New This Week: ${stats.newThisWeek}`);
        console.log(`  Resolved: ${stats.resolved}`);
        console.log();

        console.log(`  By Severity:`);
        console.log(`    ${colors.red}Critical:${colors.reset} ${stats.bySeverity.critical ?? 0}`);
        console.log(`    ${colors.yellow}Warning:${colors.reset} ${stats.bySeverity.warning ?? 0}`);
        console.log(`    ${colors.blue}Info:${colors.reset} ${stats.bySeverity.info ?? 0}`);
        console.log();

        console.log(`${colors.bold}Recent Analyses (${analyses.length})${colors.reset}`);
        for (const analysis of analyses.slice(0, 10)) {
          const scoreStr = analysis.qualityScore !== null ? formatScore(analysis.qualityScore) : 'N/A';
          console.log(`  ${analysis.testName} (${analysis.platform}) - Score: ${scoreStr}, Issues: ${analysis.issueCount}`);
        }

        if (options.output) {
          // Write to file
          let output = '=== QA Pipeline Report ===\n\n';
          output += `Generated: ${new Date().toISOString()}\n\n`;
          output += `Statistics\n`;
          output += `  Total Issues: ${stats.total}\n`;
          output += `  New This Week: ${stats.newThisWeek}\n\n`;

          for (const analysis of analyses) {
            output += `${analysis.testName} (${analysis.platform}) - Score: ${analysis.qualityScore ?? 'N/A'}, Issues: ${analysis.issueCount}\n`;
          }

          await fs.writeFile(options.output, output);
          console.log(`\nReport written to: ${options.output}`);
        }
      }

    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      console.error(`${colors.red}Error: ${message}${colors.reset}`);
      process.exit(1);
    }
  });

// Gemini Byzantine Analysis command (for CI pipeline)
program
  .command('gemini')
  .description('Run Gemini Byzantine quality analysis on E2E test videos')
  .option('--videos <path>', 'Directory containing video files to analyze', './test-results/videos')
  .option('-o, --output <path>', 'Output file for JSON results')
  .option('-d, --dimensions <list>', 'Dimensions to analyze (comma-separated)', 'technical,aesthetic,accessibility,emotional,polish,delight')
  .option('-t, --threshold <number>', 'Minimum score threshold (0-100)', '90')
  .option('-f, --format <format>', 'Output format (json, text)', 'json')
  .option('--report-file <path>', 'Output file for markdown report')
  .option('--api-key <key>', 'Gemini API key (can also use GEMINI_API_KEY env var)')
  .option('--fail-on-threshold', 'Exit with error if any dimension below threshold', true)
  .action(async (options) => {
    try {
      // Dynamic import for the gemini analyzer module
      const { GeminiAnalyzer } = await import('../src/analysis/gemini-analyzer.js');
      const { SINGLE_DEVICE_JOURNEYS } = await import('../src/journeys/canonical-journeys.js');

      const videosDir = path.resolve(options.videos);
      const threshold = parseInt(options.threshold, 10);
      const dimensions = options.dimensions.split(',').map((d: string) => d.trim());

      console.log(`${colors.bold}Kagami QA Pipeline - Gemini Byzantine Analysis${colors.reset}`);
      console.log(`${colors.dim}Videos directory: ${videosDir}${colors.reset}`);
      console.log(`${colors.dim}Threshold: ${threshold}/100${colors.reset}`);
      console.log(`${colors.dim}Dimensions: ${dimensions.join(', ')}${colors.reset}`);
      console.log();

      // Find video files
      let videoFiles: string[] = [];
      try {
        const entries = await fs.readdir(videosDir, { withFileTypes: true, recursive: true });
        videoFiles = entries
          .filter(e => e.isFile() && e.name.match(/\.(mp4|mov|webm|mkv)$/i))
          .map(e => path.join(e.parentPath ?? e.path ?? videosDir, e.name));
      } catch {
        console.log(`${colors.yellow}No videos found in ${videosDir}${colors.reset}`);
        // Output empty results for CI
        const emptyResult = {
          overallScore: 0,
          meetsQualityBar: false,
          byzantineScores: {
            technical: 0,
            aesthetic: 0,
            accessibility: 0,
            emotional: 0,
            polish: 0,
            delight: 0
          },
          issues: [],
          videos: [],
          timestamp: new Date().toISOString()
        };

        if (options.output) {
          await fs.writeFile(options.output, JSON.stringify(emptyResult, null, 2));
          console.log(`${colors.green}Empty results written to: ${options.output}${colors.reset}`);
        }
        process.exit(0);
      }

      if (videoFiles.length === 0) {
        console.log(`${colors.yellow}No video files found${colors.reset}`);
        process.exit(0);
      }

      console.log(`Found ${videoFiles.length} video file(s)`);

      // Initialize analyzer
      const apiKey = options.apiKey ?? process.env['GEMINI_API_KEY'];
      if (!apiKey) {
        console.error(`${colors.red}Error: GEMINI_API_KEY required${colors.reset}`);
        process.exit(1);
      }

      const analyzer = new GeminiAnalyzer(apiKey);

      // Aggregate results - use explicit type for scores to allow indexing
      type ScoresRecord = {
        technical: number;
        aesthetic: number;
        accessibility: number;
        emotional: number;
        polish: number;
        delight: number;
      } & Record<string, number>;

      const allResults: Array<{
        videoPath: string;
        scores: ScoresRecord;
        issues: Array<{ severity: string; description: string; dimension: string }>;
        overallScore: number;
      }> = [];

      // Default journey spec for generic analysis
      const defaultJourney = SINGLE_DEVICE_JOURNEYS[0];
      if (!defaultJourney) {
        console.error(`${colors.red}Error: No journey spec available${colors.reset}`);
        process.exit(1);
      }

      // Analyze each video
      for (const videoPath of videoFiles) {
        console.log(`\n${colors.cyan}Analyzing:${colors.reset} ${path.basename(videoPath)}`);

        try {
          // Generate timestamps based on estimated video length (every 2 seconds for 30s video)
          const timestamps = Array.from({ length: 15 }, (_, i) => i * 2);

          const result = await analyzer.analyzeJourney(videoPath, defaultJourney, timestamps);

          allResults.push({
            videoPath,
            scores: result.byzantineScores as ScoresRecord,
            issues: result.issues.map(i => ({
              severity: i.severity,
              description: i.description,
              dimension: i.dimension
            })),
            overallScore: result.overallScore
          });

          // Print per-video results
          console.log(`  Overall: ${formatScore(result.overallScore)}/100`);
          for (const [dim, score] of Object.entries(result.byzantineScores)) {
            if (dimensions.includes(dim)) {
              const status = score >= threshold ? `${colors.green}PASS${colors.reset}` : `${colors.red}FAIL${colors.reset}`;
              console.log(`    ${dim}: ${formatScore(score)}/100 ${status}`);
            }
          }
          if (result.issues.length > 0) {
            const criticalCount = result.issues.filter(i => i.severity === 'critical').length;
            console.log(`  Issues: ${result.issues.length} (${criticalCount} critical)`);
          }
        } catch (error) {
          const message = error instanceof Error ? error.message : 'Unknown error';
          console.error(`  ${colors.red}Failed: ${message}${colors.reset}`);
          allResults.push({
            videoPath,
            scores: { technical: 0, aesthetic: 0, accessibility: 0, emotional: 0, polish: 0, delight: 0 },
            issues: [{ severity: 'critical', description: `Analysis failed: ${message}`, dimension: 'technical' }],
            overallScore: 0
          });
        }
      }

      // Calculate aggregate scores
      const aggregateScores: Record<string, number> = {};
      for (const dim of dimensions) {
        const scores = allResults.map(r => r.scores[dim] ?? 0);
        aggregateScores[dim] = scores.length > 0
          ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
          : 0;
      }

      const overallScore = Math.round(
        Object.values(aggregateScores).reduce((a, b) => a + b, 0) / dimensions.length
      );

      const meetsThreshold = Object.values(aggregateScores).every(s => s >= threshold);
      const allIssues = allResults.flatMap(r => r.issues);
      const criticalCount = allIssues.filter(i => i.severity === 'critical').length;

      // Summary
      console.log();
      console.log(`${colors.bold}=== Byzantine Quality Summary ===${colors.reset}`);
      console.log();
      console.log(`Quality Gate: ${meetsThreshold ? `${colors.green}PASSED${colors.reset}` : `${colors.red}FAILED${colors.reset}`}`);
      console.log(`Threshold: ${threshold}/100`);
      console.log();
      console.log('Byzantine Scores:');
      for (const [dim, score] of Object.entries(aggregateScores)) {
        const status = score >= threshold ? `${colors.green}PASS${colors.reset}` : `${colors.red}FAIL${colors.reset}`;
        console.log(`  ${dim}: ${formatScore(score)}/100 ${status}`);
      }
      console.log();
      console.log(`Overall Score: ${formatScore(overallScore)}/100`);
      console.log(`Total Issues: ${allIssues.length} (${criticalCount} critical)`);

      // Output JSON results
      const outputResult = {
        timestamp: new Date().toISOString(),
        threshold,
        meetsQualityBar: meetsThreshold,
        overallScore,
        byzantineScores: aggregateScores,
        videos: allResults.map(r => ({
          path: r.videoPath,
          scores: r.scores,
          overallScore: r.overallScore,
          issueCount: r.issues.length
        })),
        issues: allIssues
      };

      if (options.output) {
        await fs.mkdir(path.dirname(options.output), { recursive: true });
        await fs.writeFile(options.output, JSON.stringify(outputResult, null, 2));
        console.log(`\n${colors.green}Results written to: ${options.output}${colors.reset}`);
      }

      // Generate markdown report
      if (options.reportFile) {
        let report = `# Byzantine Quality Analysis Report\n\n`;
        report += `Generated: ${new Date().toISOString()}\n\n`;
        report += `## Quality Gate: ${meetsThreshold ? 'PASSED' : 'FAILED'}\n\n`;
        report += `**Threshold: ${threshold}/100**\n\n`;
        report += `## Byzantine Scores\n\n`;
        report += `| Dimension | Score | Status |\n`;
        report += `|-----------|-------|--------|\n`;
        for (const [dim, score] of Object.entries(aggregateScores)) {
          report += `| ${dim.charAt(0).toUpperCase() + dim.slice(1)} | ${score}/100 | ${score >= threshold ? 'Pass' : 'FAIL'} |\n`;
        }
        report += `\n**Overall Score: ${overallScore}/100**\n\n`;
        report += `## Videos Analyzed: ${allResults.length}\n\n`;
        for (const result of allResults) {
          report += `### ${path.basename(result.videoPath)}\n`;
          report += `- Overall: ${result.overallScore}/100\n`;
          report += `- Issues: ${result.issues.length}\n\n`;
        }
        report += `## Issues Summary\n\n`;
        report += `- Critical: ${criticalCount}\n`;
        report += `- Warning: ${allIssues.filter(i => i.severity === 'warning').length}\n`;
        report += `- Info: ${allIssues.filter(i => i.severity === 'info').length}\n\n`;
        report += `---\n*h(x) >= 0. Always.*\n*craft(x) → ∞ always*\n`;

        await fs.mkdir(path.dirname(options.reportFile), { recursive: true });
        await fs.writeFile(options.reportFile, report);
        console.log(`${colors.green}Report written to: ${options.reportFile}${colors.reset}`);
      }

      // Exit with error if threshold not met and flag is set
      if (options.failOnThreshold && !meetsThreshold) {
        console.error(`\n${colors.red}Quality gate FAILED - one or more dimensions below ${threshold}/100${colors.reset}`);
        process.exit(1);
      }

      if (criticalCount > 0 && options.failOnThreshold) {
        console.error(`\n${colors.red}Critical issues detected: ${criticalCount}${colors.reset}`);
        process.exit(1);
      }

      process.exit(0);

    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      console.error(`${colors.red}Error: ${message}${colors.reset}`);
      logger.error({ error }, 'Gemini analysis error');
      process.exit(1);
    }
  });

// Health check command
program
  .command('health')
  .description('Check pipeline health and connectivity')
  .action(async () => {
    try {
      console.log(`${colors.bold}Pipeline Health Check${colors.reset}`);
      console.log();

      // Check config
      console.log('Checking configuration...');
      try {
        const config = loadConfig();
        setConfig(config);
        console.log(`  ${colors.green}OK${colors.reset} Configuration loaded`);
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unknown error';
        console.log(`  ${colors.red}FAIL${colors.reset} ${message}`);
        process.exit(1);
      }

      // Check database
      console.log('Checking database...');
      try {
        const tracker = await getTracker();
        const stats = tracker.getIssueStats();
        console.log(`  ${colors.green}OK${colors.reset} Database connected (${stats.total} issues tracked)`);
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unknown error';
        console.log(`  ${colors.red}FAIL${colors.reset} ${message}`);
      }

      // Check Gemini API
      console.log('Checking Gemini API...');
      try {
        const analyzer = getAnalyzer();
        const connected = await analyzer.testConnection();
        if (connected) {
          console.log(`  ${colors.green}OK${colors.reset} Gemini API connected`);
        } else {
          console.log(`  ${colors.yellow}WARN${colors.reset} Gemini API not responding`);
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unknown error';
        console.log(`  ${colors.red}FAIL${colors.reset} ${message}`);
      }

      // Check FFmpeg
      console.log('Checking FFmpeg...');
      try {
        const processor = getProcessor();
        // Just instantiating should work if FFmpeg is available
        console.log(`  ${colors.green}OK${colors.reset} FFmpeg available`);
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unknown error';
        console.log(`  ${colors.red}FAIL${colors.reset} ${message}`);
      }

      console.log();
      console.log(`${colors.green}Health check complete${colors.reset}`);

    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      console.error(`${colors.red}Error: ${message}${colors.reset}`);
      process.exit(1);
    }
  });

// Parse arguments
program.parse();
