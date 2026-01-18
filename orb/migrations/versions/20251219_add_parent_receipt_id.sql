-- Migration: Add parent_receipt_id to receipts table
-- Date: 2025-12-19
-- Purpose: Enable PLAN→EXECUTE→VERIFY phase linking via parent_receipt_id

-- Add parent_receipt_id column (nullable for backward compatibility)
ALTER TABLE receipts
ADD COLUMN parent_receipt_id VARCHAR(100);

-- Add index for efficient parent lookups and chain traversal
CREATE INDEX idx_receipt_parent ON receipts (parent_receipt_id);

-- Add comment for documentation
COMMENT ON COLUMN receipts.parent_receipt_id IS 'Parent receipt ID for phase/operation DAG traversal';
