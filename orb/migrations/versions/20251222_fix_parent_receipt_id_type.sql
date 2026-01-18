-- Migration: 20251222_fix_parent_receipt_id_type
-- Date: December 22, 2025
-- Purpose: Fix parent_receipt_id column type from UUID to VARCHAR(100)
-- Issue: Column was incorrectly created as UUID but should be VARCHAR(100) for correlation_id matching
-- Status: CRITICAL - Required for receipt persistence

-- ==============================================================================
-- FIX: parent_receipt_id should be VARCHAR(100), not UUID
-- ==============================================================================

-- Drop existing index if present
DROP INDEX IF EXISTS idx_receipt_parent;

-- Alter column type from UUID to VARCHAR(100)
-- Using USING clause to handle existing UUID values by casting to text
ALTER TABLE receipts
  ALTER COLUMN parent_receipt_id TYPE VARCHAR(100)
  USING parent_receipt_id::text;

-- Recreate index
CREATE INDEX idx_receipt_parent ON receipts (parent_receipt_id)
  WHERE parent_receipt_id IS NOT NULL;

-- Add comment
COMMENT ON COLUMN receipts.parent_receipt_id IS
  'Parent receipt correlation_id for PLAN→EXECUTE→VERIFY phase linking. VARCHAR(100) to match correlation_id format.';

-- ==============================================================================
-- VERIFY
-- ==============================================================================

-- This should return 'character varying' or 'varchar' after migration
-- SELECT data_type FROM information_schema.columns
--   WHERE table_name = 'receipts' AND column_name = 'parent_receipt_id';
