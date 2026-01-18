/**
 * @fileoverview Issue Tracker - SQLite-based storage and tracking of QA issues
 *
 * This module provides persistent storage for analysis results and detected issues,
 * with capabilities for:
 * - Storing and retrieving analysis results
 * - Tracking issues across multiple test runs
 * - Detecting regressions (new issues) vs known issues
 * - Generating issue reports and statistics
 *
 * Uses better-sqlite3 for performant, synchronous database access.
 */

import Database from 'better-sqlite3';
import { promises as fs } from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { createChildLogger, startTiming } from './logger.js';
import { getConfig } from './config.js';
import type {
  AnalysisResult,
  AnalysisRecord,
  DetectedIssue,
  IssueRecord,
  Platform,
  Severity,
  IssueCategory,
  AnalysisStatus,
  AnalysisConfig,
  ListAnalysesQuery,
  ListIssuesQuery
} from './types.js';

const log = createChildLogger({ component: 'tracker' });

/**
 * Database schema version for migrations
 */
const SCHEMA_VERSION = 1;

/**
 * Issue fingerprint for deduplication
 */
interface IssueFingerprint {
  category: IssueCategory;
  description: string;
  platform: Platform;
}

/**
 * Issue statistics summary
 */
export interface IssueStats {
  total: number;
  bySeverity: Record<Severity, number>;
  byCategory: Record<IssueCategory, number>;
  byPlatform: Record<Platform, number>;
  newThisWeek: number;
  resolved: number;
}

/**
 * Analysis summary for reporting
 */
export interface AnalysisSummary {
  id: string;
  videoPath: string;
  platform: Platform;
  testName: string;
  status: AnalysisStatus;
  qualityScore: number | null;
  issueCount: number;
  criticalCount: number;
  createdAt: string;
  completedAt: string | null;
}

/**
 * Issue Tracker class
 *
 * Manages persistent storage of analyses and issues in SQLite.
 *
 * @example
 * ```typescript
 * const tracker = new IssueTracker();
 * await tracker.initialize();
 *
 * // Store an analysis
 * await tracker.storeAnalysis(analysisResult);
 *
 * // Get all issues
 * const issues = tracker.getIssues({ severity: 'critical' });
 *
 * // Check for regressions
 * const regressions = tracker.detectRegressions(newIssues, platform);
 * ```
 */
export class IssueTracker {
  private config = getConfig();
  private db: Database.Database | null = null;
  private initialized = false;

  /**
   * Initialize the database and create tables
   */
  async initialize(): Promise<void> {
    if (this.initialized) {
      return;
    }

    const done = startTiming('tracker-initialize');

    // Ensure directory exists
    await fs.mkdir(path.dirname(this.config.database.path), { recursive: true });

    // Open database
    this.db = new Database(this.config.database.path);
    this.db.pragma('journal_mode = WAL');
    this.db.pragma('foreign_keys = ON');

    // Create tables
    this.createTables();

    // Run migrations if needed
    this.runMigrations();

    this.initialized = true;
    done();

    log.info({ dbPath: this.config.database.path }, 'Issue tracker initialized');
  }

  /**
   * Create database tables
   */
  private createTables(): void {
    const db = this.getDb();

    // Analyses table
    db.exec(`
      CREATE TABLE IF NOT EXISTS analyses (
        id TEXT PRIMARY KEY,
        video_path TEXT NOT NULL,
        platform TEXT NOT NULL,
        test_name TEXT NOT NULL,
        test_suite TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        started_at TEXT,
        completed_at TEXT,
        duration_ms INTEGER,
        video_duration REAL,
        frames_analyzed INTEGER DEFAULT 0,
        quality_score INTEGER,
        error TEXT,
        config TEXT NOT NULL,
        raw_response TEXT
      );

      CREATE INDEX IF NOT EXISTS idx_analyses_status ON analyses(status);
      CREATE INDEX IF NOT EXISTS idx_analyses_platform ON analyses(platform);
      CREATE INDEX IF NOT EXISTS idx_analyses_created ON analyses(created_at);
    `);

    // Issues table
    db.exec(`
      CREATE TABLE IF NOT EXISTS issues (
        id TEXT PRIMARY KEY,
        analysis_id TEXT NOT NULL,
        timestamp REAL NOT NULL,
        severity TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT NOT NULL,
        frame_path TEXT,
        suggested_fix TEXT,
        confidence REAL NOT NULL DEFAULT 0.8,
        metadata TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        is_known INTEGER DEFAULT 0,
        first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
        last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
        occurrence_count INTEGER DEFAULT 1,
        fingerprint TEXT,
        FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
      );

      CREATE INDEX IF NOT EXISTS idx_issues_analysis ON issues(analysis_id);
      CREATE INDEX IF NOT EXISTS idx_issues_severity ON issues(severity);
      CREATE INDEX IF NOT EXISTS idx_issues_category ON issues(category);
      CREATE INDEX IF NOT EXISTS idx_issues_fingerprint ON issues(fingerprint);
    `);

    // Known issues table (for tracking recurring issues)
    db.exec(`
      CREATE TABLE IF NOT EXISTS known_issues (
        id TEXT PRIMARY KEY,
        fingerprint TEXT UNIQUE NOT NULL,
        platform TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT NOT NULL,
        first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
        last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
        occurrence_count INTEGER DEFAULT 1,
        is_resolved INTEGER DEFAULT 0,
        resolved_at TEXT,
        notes TEXT
      );

      CREATE INDEX IF NOT EXISTS idx_known_fingerprint ON known_issues(fingerprint);
      CREATE INDEX IF NOT EXISTS idx_known_resolved ON known_issues(is_resolved);
    `);

    // Schema version table
    db.exec(`
      CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY
      );

      INSERT OR IGNORE INTO schema_version (version) VALUES (${SCHEMA_VERSION});
    `);
  }

  /**
   * Run database migrations if needed
   */
  private runMigrations(): void {
    const db = this.getDb();
    const versionRow = db.prepare('SELECT version FROM schema_version').get() as { version: number } | undefined;
    const currentVersion = versionRow?.version ?? 0;

    if (currentVersion < SCHEMA_VERSION) {
      log.info({ from: currentVersion, to: SCHEMA_VERSION }, 'Running database migrations');
      // Add migration logic here as schema evolves
      db.prepare('UPDATE schema_version SET version = ?').run(SCHEMA_VERSION);
    }
  }

  /**
   * Get database instance, throwing if not initialized
   */
  private getDb(): Database.Database {
    if (!this.db) {
      throw new Error('Issue tracker not initialized. Call initialize() first.');
    }
    return this.db;
  }

  /**
   * Create a new analysis record
   */
  createAnalysis(
    videoPath: string,
    config: AnalysisConfig
  ): AnalysisResult {
    const db = this.getDb();
    const id = randomUUID();
    const createdAt = new Date().toISOString();

    const analysis: AnalysisResult = {
      id,
      videoPath,
      config,
      status: 'pending',
      createdAt,
      framesAnalyzed: 0,
      issues: []
    };

    const stmt = db.prepare(`
      INSERT INTO analyses (id, video_path, platform, test_name, test_suite, status, created_at, config)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `);

    stmt.run(
      id,
      videoPath,
      config.platform,
      config.testName,
      config.testSuite ?? null,
      'pending',
      createdAt,
      JSON.stringify(config)
    );

    log.debug({ analysisId: id, videoPath }, 'Analysis record created');
    return analysis;
  }

  /**
   * Update analysis status
   */
  updateAnalysisStatus(
    id: string,
    status: AnalysisStatus,
    updates?: Partial<{
      startedAt: string;
      completedAt: string;
      durationMs: number;
      videoDuration: number;
      framesAnalyzed: number;
      qualityScore: number;
      error: string;
      rawResponse: string;
    }>
  ): void {
    const db = this.getDb();

    const setClauses = ['status = ?'];
    const values: unknown[] = [status];

    if (updates?.startedAt !== undefined) {
      setClauses.push('started_at = ?');
      values.push(updates.startedAt);
    }
    if (updates?.completedAt !== undefined) {
      setClauses.push('completed_at = ?');
      values.push(updates.completedAt);
    }
    if (updates?.durationMs !== undefined) {
      setClauses.push('duration_ms = ?');
      values.push(updates.durationMs);
    }
    if (updates?.videoDuration !== undefined) {
      setClauses.push('video_duration = ?');
      values.push(updates.videoDuration);
    }
    if (updates?.framesAnalyzed !== undefined) {
      setClauses.push('frames_analyzed = ?');
      values.push(updates.framesAnalyzed);
    }
    if (updates?.qualityScore !== undefined) {
      setClauses.push('quality_score = ?');
      values.push(updates.qualityScore);
    }
    if (updates?.error !== undefined) {
      setClauses.push('error = ?');
      values.push(updates.error);
    }
    if (updates?.rawResponse !== undefined) {
      setClauses.push('raw_response = ?');
      values.push(updates.rawResponse);
    }

    values.push(id);

    const stmt = db.prepare(`
      UPDATE analyses SET ${setClauses.join(', ')} WHERE id = ?
    `);

    stmt.run(...values);
    log.debug({ analysisId: id, status }, 'Analysis status updated');
  }

  /**
   * Store issues for an analysis
   */
  storeIssues(analysisId: string, issues: DetectedIssue[], platform: Platform): void {
    const db = this.getDb();

    const insertStmt = db.prepare(`
      INSERT INTO issues (id, analysis_id, timestamp, severity, category, description, frame_path, suggested_fix, confidence, metadata, fingerprint)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);

    const updateKnownStmt = db.prepare(`
      INSERT INTO known_issues (id, fingerprint, platform, category, description)
      VALUES (?, ?, ?, ?, ?)
      ON CONFLICT(fingerprint) DO UPDATE SET
        last_seen_at = datetime('now'),
        occurrence_count = occurrence_count + 1
    `);

    const transaction = db.transaction(() => {
      for (const issue of issues) {
        const fingerprint = this.generateFingerprint({
          category: issue.category,
          description: issue.description,
          platform
        });

        insertStmt.run(
          issue.id,
          analysisId,
          issue.timestamp,
          issue.severity,
          issue.category,
          issue.description,
          issue.framePath ?? null,
          issue.suggestedFix ?? null,
          issue.confidence,
          issue.metadata ? JSON.stringify(issue.metadata) : null,
          fingerprint
        );

        updateKnownStmt.run(
          randomUUID(),
          fingerprint,
          platform,
          issue.category,
          issue.description
        );
      }
    });

    transaction();
    log.debug({ analysisId, issueCount: issues.length }, 'Issues stored');
  }

  /**
   * Get an analysis by ID
   */
  getAnalysis(id: string): AnalysisResult | null {
    const db = this.getDb();

    const row = db.prepare(`
      SELECT * FROM analyses WHERE id = ?
    `).get(id) as AnalysisRecord | undefined;

    if (!row) {
      return null;
    }

    const issues = this.getIssuesForAnalysis(id);
    return this.recordToResult(row, issues);
  }

  /**
   * Get issues for a specific analysis
   */
  getIssuesForAnalysis(analysisId: string): DetectedIssue[] {
    const db = this.getDb();

    const rows = db.prepare(`
      SELECT * FROM issues WHERE analysis_id = ? ORDER BY timestamp
    `).all(analysisId) as IssueRecord[];

    return rows.map(this.issueRecordToDetectedIssue);
  }

  /**
   * List analyses with filtering and pagination
   */
  listAnalyses(query: ListAnalysesQuery): {
    analyses: AnalysisSummary[];
    total: number;
  } {
    const db = this.getDb();

    const whereClauses: string[] = [];
    const params: unknown[] = [];

    if (query.status) {
      whereClauses.push('a.status = ?');
      params.push(query.status);
    }
    if (query.platform) {
      whereClauses.push('a.platform = ?');
      params.push(query.platform);
    }
    if (query.testName) {
      whereClauses.push('a.test_name LIKE ?');
      params.push(`%${query.testName}%`);
    }

    const whereClause = whereClauses.length > 0
      ? `WHERE ${whereClauses.join(' AND ')}`
      : '';

    // Get total count
    const countRow = db.prepare(`
      SELECT COUNT(*) as count FROM analyses a ${whereClause}
    `).get(...params) as { count: number };

    // Sort mapping
    const sortMapping: Record<string, string> = {
      createdAt: 'a.created_at',
      qualityScore: 'a.quality_score',
      issueCount: 'issue_count'
    };
    const sortColumn = sortMapping[query.sortBy] ?? 'a.created_at';

    // Get analyses with issue counts
    const rows = db.prepare(`
      SELECT
        a.id,
        a.video_path,
        a.platform,
        a.test_name,
        a.status,
        a.quality_score,
        a.created_at,
        a.completed_at,
        COUNT(i.id) as issue_count,
        SUM(CASE WHEN i.severity = 'critical' THEN 1 ELSE 0 END) as critical_count
      FROM analyses a
      LEFT JOIN issues i ON a.id = i.analysis_id
      ${whereClause}
      GROUP BY a.id
      ORDER BY ${sortColumn} ${query.sortDir.toUpperCase()}
      LIMIT ? OFFSET ?
    `).all(...params, query.limit, query.offset) as Array<{
      id: string;
      video_path: string;
      platform: Platform;
      test_name: string;
      status: AnalysisStatus;
      quality_score: number | null;
      created_at: string;
      completed_at: string | null;
      issue_count: number;
      critical_count: number;
    }>;

    return {
      analyses: rows.map(row => ({
        id: row.id,
        videoPath: row.video_path,
        platform: row.platform,
        testName: row.test_name,
        status: row.status,
        qualityScore: row.quality_score,
        issueCount: row.issue_count,
        criticalCount: row.critical_count,
        createdAt: row.created_at,
        completedAt: row.completed_at
      })),
      total: countRow.count
    };
  }

  /**
   * List issues with filtering and pagination
   */
  listIssues(query: ListIssuesQuery): {
    issues: Array<DetectedIssue & { analysisId: string; platform: Platform; testName: string }>;
    total: number;
  } {
    const db = this.getDb();

    const whereClauses: string[] = [];
    const params: unknown[] = [];

    if (query.analysisId) {
      whereClauses.push('i.analysis_id = ?');
      params.push(query.analysisId);
    }
    if (query.severity) {
      whereClauses.push('i.severity = ?');
      params.push(query.severity);
    }
    if (query.category) {
      whereClauses.push('i.category = ?');
      params.push(query.category);
    }
    if (query.platform) {
      whereClauses.push('a.platform = ?');
      params.push(query.platform);
    }
    if (query.since) {
      whereClauses.push('i.created_at >= ?');
      params.push(query.since);
    }

    const whereClause = whereClauses.length > 0
      ? `WHERE ${whereClauses.join(' AND ')}`
      : '';

    // Get total count
    const countRow = db.prepare(`
      SELECT COUNT(*) as count
      FROM issues i
      JOIN analyses a ON i.analysis_id = a.id
      ${whereClause}
    `).get(...params) as { count: number };

    // Get issues with analysis info
    const rows = db.prepare(`
      SELECT
        i.*,
        a.platform,
        a.test_name
      FROM issues i
      JOIN analyses a ON i.analysis_id = a.id
      ${whereClause}
      ORDER BY i.created_at DESC
      LIMIT ? OFFSET ?
    `).all(...params, query.limit, query.offset) as Array<IssueRecord & { platform: Platform; test_name: string }>;

    return {
      issues: rows.map(row => ({
        ...this.issueRecordToDetectedIssue(row),
        analysisId: row.analysis_id,
        platform: row.platform,
        testName: row.test_name
      })),
      total: countRow.count
    };
  }

  /**
   * Detect regressions (new issues not seen before)
   */
  detectRegressions(issues: DetectedIssue[], platform: Platform): {
    regressions: DetectedIssue[];
    known: DetectedIssue[];
  } {
    const db = this.getDb();
    const regressions: DetectedIssue[] = [];
    const known: DetectedIssue[] = [];

    const checkStmt = db.prepare(`
      SELECT id, is_resolved FROM known_issues WHERE fingerprint = ?
    `);

    for (const issue of issues) {
      const fingerprint = this.generateFingerprint({
        category: issue.category,
        description: issue.description,
        platform
      });

      const existing = checkStmt.get(fingerprint) as { id: string; is_resolved: number } | undefined;

      if (!existing) {
        regressions.push(issue);
      } else if (existing.is_resolved === 1) {
        // Issue was resolved but has reappeared - this is a regression
        regressions.push(issue);
      } else {
        known.push(issue);
      }
    }

    log.debug(
      { total: issues.length, regressions: regressions.length, known: known.length },
      'Regression detection complete'
    );

    return { regressions, known };
  }

  /**
   * Mark a known issue as resolved
   */
  resolveKnownIssue(fingerprint: string, notes?: string): boolean {
    const db = this.getDb();

    const result = db.prepare(`
      UPDATE known_issues
      SET is_resolved = 1, resolved_at = datetime('now'), notes = COALESCE(?, notes)
      WHERE fingerprint = ?
    `).run(notes ?? null, fingerprint);

    return result.changes > 0;
  }

  /**
   * Get issue statistics
   */
  getIssueStats(): IssueStats {
    const db = this.getDb();

    const totalRow = db.prepare('SELECT COUNT(*) as count FROM issues').get() as { count: number };

    const severityRows = db.prepare(`
      SELECT severity, COUNT(*) as count FROM issues GROUP BY severity
    `).all() as Array<{ severity: Severity; count: number }>;

    const categoryRows = db.prepare(`
      SELECT category, COUNT(*) as count FROM issues GROUP BY category
    `).all() as Array<{ category: IssueCategory; count: number }>;

    const platformRows = db.prepare(`
      SELECT a.platform, COUNT(i.id) as count
      FROM issues i
      JOIN analyses a ON i.analysis_id = a.id
      GROUP BY a.platform
    `).all() as Array<{ platform: Platform; count: number }>;

    const newThisWeekRow = db.prepare(`
      SELECT COUNT(*) as count FROM issues WHERE created_at >= datetime('now', '-7 days')
    `).get() as { count: number };

    const resolvedRow = db.prepare(`
      SELECT COUNT(*) as count FROM known_issues WHERE is_resolved = 1
    `).get() as { count: number };

    return {
      total: totalRow.count,
      bySeverity: Object.fromEntries(severityRows.map(r => [r.severity, r.count])) as Record<Severity, number>,
      byCategory: Object.fromEntries(categoryRows.map(r => [r.category, r.count])) as Record<IssueCategory, number>,
      byPlatform: Object.fromEntries(platformRows.map(r => [r.platform, r.count])) as Record<Platform, number>,
      newThisWeek: newThisWeekRow.count,
      resolved: resolvedRow.count
    };
  }

  /**
   * Clean up old analyses
   */
  cleanupOldAnalyses(retainDays?: number): number {
    const db = this.getDb();
    const days = retainDays ?? this.config.pipeline.retainAnalysisDays;

    const result = db.prepare(`
      DELETE FROM analyses WHERE created_at < datetime('now', '-' || ? || ' days')
    `).run(days);

    log.info({ deleted: result.changes, retainDays: days }, 'Cleaned up old analyses');
    return result.changes;
  }

  /**
   * Generate a fingerprint for issue deduplication
   */
  private generateFingerprint(input: IssueFingerprint): string {
    // Normalize description for comparison
    const normalizedDesc = input.description
      .toLowerCase()
      .replace(/\d+/g, 'N') // Replace numbers with N
      .replace(/\s+/g, ' ') // Normalize whitespace
      .trim();

    return `${input.platform}:${input.category}:${normalizedDesc}`;
  }

  /**
   * Convert database record to AnalysisResult
   */
  private recordToResult(record: AnalysisRecord, issues: DetectedIssue[]): AnalysisResult {
    return {
      id: record.id,
      videoPath: record.video_path,
      config: JSON.parse(record.config) as AnalysisConfig,
      status: record.status,
      createdAt: record.created_at,
      startedAt: record.started_at ?? undefined,
      completedAt: record.completed_at ?? undefined,
      durationMs: record.duration_ms ?? undefined,
      videoDuration: record.video_duration ?? undefined,
      framesAnalyzed: record.frames_analyzed,
      issues,
      qualityScore: record.quality_score ?? undefined,
      error: record.error ?? undefined,
      rawResponse: record.raw_response ?? undefined
    };
  }

  /**
   * Convert database issue record to DetectedIssue
   */
  private issueRecordToDetectedIssue(record: IssueRecord): DetectedIssue {
    return {
      id: record.id,
      timestamp: record.timestamp,
      severity: record.severity,
      category: record.category,
      description: record.description,
      framePath: record.frame_path ?? undefined,
      suggestedFix: record.suggested_fix ?? undefined,
      confidence: record.confidence,
      metadata: record.metadata ? JSON.parse(record.metadata) : undefined
    };
  }

  /**
   * Close the database connection
   */
  close(): void {
    if (this.db) {
      this.db.close();
      this.db = null;
      this.initialized = false;
      log.debug('Issue tracker database closed');
    }
  }
}

/**
 * Singleton instance for convenient access
 */
let trackerInstance: IssueTracker | null = null;

/**
 * Get the shared IssueTracker instance
 */
export async function getTracker(): Promise<IssueTracker> {
  if (!trackerInstance) {
    trackerInstance = new IssueTracker();
    await trackerInstance.initialize();
  }
  return trackerInstance;
}

/**
 * Reset the tracker instance (for testing)
 */
export function resetTracker(): void {
  if (trackerInstance) {
    trackerInstance.close();
    trackerInstance = null;
  }
}
