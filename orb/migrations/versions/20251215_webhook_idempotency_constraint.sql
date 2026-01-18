-- Webhook Idempotency Atomic Constraint
-- Created: December 15, 2025
-- Purpose: Add unique constraint to AppData for atomic webhook deduplication
--
-- Security Fix: Prevents race condition in webhook processing where two
-- concurrent requests could both pass the check-then-insert pattern.
--
-- Pattern: INSERT ... ON CONFLICT DO NOTHING (PostgreSQL/CockroachDB)
--
-- CRITICAL: This constraint makes webhook event_id deduplication atomic at
-- the database level, eliminating TOCTOU (Time-of-Check-Time-of-Use) vulnerability.

-- Add unique constraint for webhook idempotency
-- Composite key: (app_name, data_type, data_id)
CREATE UNIQUE INDEX IF NOT EXISTS idx_app_data_webhook_idempotency
ON app_data(app_name, data_type, data_id)
WHERE app_name = 'billing' AND data_type = 'stripe_webhook';

-- This constraint ensures:
-- 1. Only one webhook event with a given event_id can be stored
-- 2. Concurrent inserts will cause IntegrityError on duplicate
-- 3. Database enforces atomicity (no application-level locks needed)
-- 4. Fast lookups via partial index (only indexes webhook records)

-- Performance note: Partial index is more efficient than full unique constraint
-- since we only care about uniqueness within billing/stripe_webhook scope.

-- Rollback:
-- DROP INDEX IF EXISTS idx_app_data_webhook_idempotency;
