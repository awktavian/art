-- Correlation ID Uniqueness Constraint
-- Created: December 16, 2025
-- Purpose: Add unique constraint on (correlation_id, phase, ts) to prevent duplicate receipts
--
-- Security Fix: Prevents race conditions where duplicate receipts could be created
-- for the same correlation_id + phase + timestamp tuple, breaking audit trail integrity.
--
-- Pattern: Unique index ensures database-level atomicity for receipt insertion
--
-- CRITICAL: This constraint makes receipt deduplication atomic at the database level,
-- eliminating Time-of-Check-Time-of-Use (TOCTOU) vulnerabilities.

-- Add unique constraint on (correlation_id, phase, ts)
-- This prevents duplicate receipts for same correlation+phase+timestamp
-- Using CONCURRENTLY to avoid locking the receipts table during index creation
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_receipts_correlation_uniqueness
ON receipts(correlation_id, phase, ts);

-- This constraint ensures:
-- 1. Only one receipt with a given (correlation_id, phase, ts) can be stored
-- 2. Concurrent inserts will cause IntegrityError on duplicate
-- 3. Database enforces atomicity (no application-level locks needed)
-- 4. Preserves audit trail integrity for PLAN-EXECUTE-VERIFY cycles

-- Performance note: This is a covering index that also speeds up queries
-- filtering by correlation_id + phase, which are common access patterns.

-- Note on timestamp precision:
-- CockroachDB stores timestamps with microsecond precision. In practice,
-- duplicate ts values are rare unless receipts are emitted in tight loops
-- without proper correlation_id generation.

-- Rollback:
-- DROP INDEX CONCURRENTLY IF EXISTS idx_receipts_correlation_uniqueness;
