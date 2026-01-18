-- Add Multi-Tenancy Support
-- Created: November 16, 2025 (Q4 Production Roadmap)

-- Add tenant_id to all major tables
ALTER TABLE receipts ADD COLUMN tenant_id UUID;
ALTER TABLE intents ADD COLUMN tenant_id UUID;
ALTER TABLE users ADD COLUMN tenant_id UUID;
ALTER TABLE idempotency_keys ADD COLUMN IF NOT EXISTS tenant_id UUID;

-- Create tenants table
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Add indexes for tenant_id lookups
CREATE INDEX IF NOT EXISTS idx_receipts_tenant ON receipts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_intents_tenant ON intents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_idempotency_tenant ON idempotency_keys(tenant_id);

-- Create default tenant for existing data
INSERT INTO tenants (id, name, slug)
VALUES ('00000000-0000-0000-0000-000000000000', 'Default', 'default')
ON CONFLICT DO NOTHING;

-- Backfill existing records with default tenant
UPDATE receipts SET tenant_id = '00000000-0000-0000-0000-000000000000' WHERE tenant_id IS NULL;
UPDATE intents SET tenant_id = '00000000-0000-0000-0000-000000000000' WHERE tenant_id IS NULL;
UPDATE users SET tenant_id = '00000000-0000-0000-0000-000000000000' WHERE tenant_id IS NULL;

-- Make tenant_id NOT NULL after backfill
ALTER TABLE receipts ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE intents ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE users ALTER COLUMN tenant_id SET NOT NULL;

COMMENT ON TABLE tenants IS 'Multi-tenancy support - each tenant has isolated data';
COMMENT ON COLUMN receipts.tenant_id IS 'Tenant isolation for receipts';
COMMENT ON COLUMN intents.tenant_id IS 'Tenant isolation for intents';
COMMENT ON COLUMN users.tenant_id IS 'Tenant membership';
