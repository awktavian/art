-- Migration: Multi-User Household System
-- Created: January 1, 2026
-- Purpose: Add persistent household storage for multi-user support
-- Part of: Apps 100/100 Transformation - Phase 1.1

-- =============================================================================
-- HOUSEHOLDS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS households (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    address TEXT,
    timezone VARCHAR(50) DEFAULT 'UTC',

    -- Settings
    guest_access_enabled BOOLEAN DEFAULT TRUE,
    guest_access_duration_hours INTEGER DEFAULT 24,
    require_2fa_for_device_control BOOLEAN DEFAULT FALSE,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for owner lookup
CREATE INDEX IF NOT EXISTS idx_households_owner ON households(owner_id);

-- =============================================================================
-- HOUSEHOLD MEMBERS TABLE (junction table with role)
-- =============================================================================

CREATE TABLE IF NOT EXISTS household_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    household_id UUID NOT NULL REFERENCES households(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Role: owner, admin, member, child, elder, caregiver, guest
    role VARCHAR(20) NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member', 'child', 'elder', 'caregiver', 'guest')),

    -- For guests: when access expires
    expires_at TIMESTAMP WITH TIME ZONE,

    -- Role-specific settings (JSONB for flexibility)
    -- Contains: child_settings, elder_settings, caregiver_settings
    settings JSONB DEFAULT '{}',

    -- Activity tracking
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    UNIQUE(household_id, user_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_household_members_household ON household_members(household_id);
CREATE INDEX IF NOT EXISTS idx_household_members_user ON household_members(user_id);
CREATE INDEX IF NOT EXISTS idx_household_members_role ON household_members(role);
CREATE INDEX IF NOT EXISTS idx_household_members_expires ON household_members(expires_at) WHERE expires_at IS NOT NULL;

-- =============================================================================
-- HOUSEHOLD INVITATIONS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS household_invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    household_id UUID NOT NULL REFERENCES households(id) ON DELETE CASCADE,

    -- Invitation details
    email VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member', 'child', 'elder', 'caregiver', 'guest')),
    code VARCHAR(64) NOT NULL UNIQUE,
    message TEXT,

    -- Who sent it
    invited_by_id UUID NOT NULL REFERENCES users(id),

    -- Status: pending, accepted, declined, expired, revoked
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined', 'expired', 'revoked')),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    accepted_at TIMESTAMP WITH TIME ZONE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_invitations_household ON household_invitations(household_id);
CREATE INDEX IF NOT EXISTS idx_invitations_email ON household_invitations(email);
CREATE INDEX IF NOT EXISTS idx_invitations_code ON household_invitations(code);
CREATE INDEX IF NOT EXISTS idx_invitations_status ON household_invitations(status);

-- =============================================================================
-- USER PREFERENCES TABLE (enhanced per-user settings)
-- =============================================================================

CREATE TABLE IF NOT EXISTS user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Preference key-value storage
    key VARCHAR(100) NOT NULL,
    value JSONB NOT NULL,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Unique per user per key
    UNIQUE(user_id, key)
);

-- Index for user lookup
CREATE INDEX IF NOT EXISTS idx_user_preferences_user ON user_preferences(user_id);

-- =============================================================================
-- ADD HOUSEHOLD_ID TO USERS TABLE (optional, for quick lookup)
-- =============================================================================

-- Add column if not exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'users' AND column_name = 'household_id') THEN
        ALTER TABLE users ADD COLUMN household_id UUID REFERENCES households(id) ON DELETE SET NULL;
        CREATE INDEX idx_users_household ON users(household_id);
    END IF;
END $$;

-- =============================================================================
-- ADD LANGUAGE PREFERENCE TO USERS TABLE
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'users' AND column_name = 'language') THEN
        ALTER TABLE users ADD COLUMN language VARCHAR(10) DEFAULT 'en';
    END IF;
END $$;

-- =============================================================================
-- OAUTH PROVIDERS TABLE (for Apple, Google SSO)
-- =============================================================================

CREATE TABLE IF NOT EXISTS oauth_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Provider: apple, google
    provider VARCHAR(20) NOT NULL,
    provider_user_id VARCHAR(255) NOT NULL,

    -- Tokens (encrypted in production)
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TIMESTAMP WITH TIME ZONE,

    -- Profile from provider
    email VARCHAR(255),
    name VARCHAR(255),
    profile_data JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Unique per provider per user
    UNIQUE(provider, provider_user_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_oauth_user ON oauth_connections(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_provider ON oauth_connections(provider, provider_user_id);

-- =============================================================================
-- FUNCTIONS FOR UPDATED_AT TRIGGER
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
DROP TRIGGER IF EXISTS update_households_updated_at ON households;
CREATE TRIGGER update_households_updated_at
    BEFORE UPDATE ON households
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_user_preferences_updated_at ON user_preferences;
CREATE TRIGGER update_user_preferences_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_oauth_connections_updated_at ON oauth_connections;
CREATE TRIGGER update_oauth_connections_updated_at
    BEFORE UPDATE ON oauth_connections
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
