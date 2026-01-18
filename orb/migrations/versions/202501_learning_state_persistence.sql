-- Learning State Persistence Tables
-- Created: January 2025
-- Purpose: Persist all learning state (performance matrix, RL checkpoints, instincts, etc.)

-- Performance matrix for multi-model routing
CREATE TABLE IF NOT EXISTS learning_performance_matrix (
    task_type VARCHAR(50) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    success_rate FLOAT NOT NULL DEFAULT 0.5,
    usage_count INT NOT NULL DEFAULT 0,
    last_updated TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (task_type, model_name)
);

CREATE INDEX IF NOT EXISTS idx_performance_task ON learning_performance_matrix(task_type);
CREATE INDEX IF NOT EXISTS idx_performance_model ON learning_performance_matrix(model_name);

-- RL policy checkpoints (keep best 3 per type)
CREATE TABLE IF NOT EXISTS rl_policy_checkpoints (
    checkpoint_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_type VARCHAR(50) NOT NULL,  -- 'actor' or 'critic'
    weights_blob BYTEA NOT NULL,
    performance_score FLOAT,
    episode_number INT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rl_checkpoints_performance
ON rl_policy_checkpoints(policy_type, performance_score DESC);

-- Instinct neural network states
CREATE TABLE IF NOT EXISTS instinct_states (
    instinct_name VARCHAR(50) PRIMARY KEY,  -- 'prediction', 'threat', 'learning'
    state_dict JSONB NOT NULL,
    training_steps INT NOT NULL DEFAULT 0,
    avg_loss FLOAT,
    last_updated TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Agent specialization tracking
CREATE TABLE IF NOT EXISTS agent_specialization (
    agent_name VARCHAR(50) NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    success_rate FLOAT NOT NULL DEFAULT 0.5,
    attempt_count INT NOT NULL DEFAULT 0,
    last_attempt TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (agent_name, task_type)
);

CREATE INDEX IF NOT EXISTS idx_specialization_agent ON agent_specialization(agent_name);

-- Success trails (pheromone-style pattern reinforcement)
CREATE TABLE IF NOT EXISTS success_trails (
    pattern_id VARCHAR(100) PRIMARY KEY,
    strength FLOAT NOT NULL DEFAULT 1.0,
    success_count INT NOT NULL DEFAULT 0,
    failure_count INT NOT NULL DEFAULT 0,
    last_reinforced TIMESTAMP NOT NULL DEFAULT NOW(),
    decay_rate FLOAT NOT NULL DEFAULT 0.05
);

CREATE INDEX IF NOT EXISTS idx_trails_strength ON success_trails(strength DESC);

-- Distributed replay buffer (shared across fleet)
CREATE TABLE IF NOT EXISTS replay_buffer (
    experience_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    context JSONB NOT NULL,
    action JSONB NOT NULL,
    outcome JSONB NOT NULL,
    valence FLOAT NOT NULL,
    importance FLOAT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    sampled_count INT NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_replay_importance
ON replay_buffer(importance DESC, sampled_count ASC);

CREATE INDEX IF NOT EXISTS idx_replay_created
ON replay_buffer(created_at DESC);

-- Auto-cleanup trigger: keep only 100K most important experiences
CREATE OR REPLACE FUNCTION cleanup_old_experiences() RETURNS TRIGGER AS $$
BEGIN
    -- Only run cleanup occasionally (every 1000 inserts)
    IF (SELECT COUNT(*) FROM replay_buffer) > 101000 THEN
        DELETE FROM replay_buffer
        WHERE experience_id IN (
            SELECT experience_id FROM replay_buffer
            ORDER BY importance ASC, created_at ASC
            LIMIT 1000
        );
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_cleanup_replay ON replay_buffer;
CREATE TRIGGER trigger_cleanup_replay
AFTER INSERT ON replay_buffer
FOR EACH STATEMENT
EXECUTE FUNCTION cleanup_old_experiences();

-- Model checkpoint metadata (file paths + performance)
CREATE TABLE IF NOT EXISTS model_checkpoints (
    checkpoint_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_type VARCHAR(50) NOT NULL,  -- 'embeddings', 'world_model', 'llm'
    file_path VARCHAR(500) NOT NULL,
    performance_score FLOAT,
    training_steps INT,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_type
ON model_checkpoints(model_type, performance_score DESC);

-- Grant permissions (adjust as needed)
-- GRANT ALL ON ALL TABLES IN SCHEMA public TO kagami_user;
-- GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO kagami_user;
