"""Database models for K OS - Optimized for CockroachDB.

REWRITTEN: December 2, 2025

Key Optimizations:
1. UUID primary keys (no sequential hotspots)
2. Hash-sharded indexes for high-write tables
3. New tables: SafetyStateSnapshot, RewardSignal, ExpectedFreeEnergy, WorldModelPrediction, TICRecord
4. JSONB with inverted indexes for flexible queries
5. Proper tenant isolation with composite indexes
6. Time-series partitioning ready

Tables by Domain:
- Core: users, api_keys, sessions, verification_tokens, user_settings
- Safety: safety_state_snapshots, threat_classifications
- Learning: reward_signals, expected_free_energy, world_model_predictions, calibration_points
- Receipts: receipts, tic_records, idempotency_keys
- Goals: organism_goals, plans, plan_tasks
- Billing: tenant_plans, tenant_usage, settlement_records, marketplace_*
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from kagami.core.database.base import Base

# Use canonical generate_uuid from utils.ids
from kagami.core.utils.ids import generate_uuid

# =============================================================================
# CORE: USERS & AUTH
# =============================================================================


class User(Base):
    """User model for authentication and authorization."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    tenant_id = Column(String(100), nullable=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    roles = Column(JSON, default=list[Any])
    is_active = Column(Boolean, default=True, index=True)
    is_superuser = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)

    # SSO
    sso_provider = Column(String(50), nullable=True)
    sso_user_id = Column(String(255), nullable=True, unique=True)

    # Billing
    stripe_customer_id = Column(String(255), nullable=True, unique=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (Index("idx_user_tenant_active", "tenant_id", "is_active"),)


class APIKey(Base):
    """API key for programmatic access."""

    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    key = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    scopes = Column(JSON, default=list[Any])
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="api_keys")

    __table_args__ = (Index("idx_api_key_user_active", "user_id", "is_active"),)


class Session(Base):
    """User session tracking."""

    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    last_activity_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="sessions")

    __table_args__ = (
        Index("idx_session_user_active", "user_id", "is_active"),
        Index("idx_session_expires", "expires_at"),
    )


class VerificationToken(Base):
    """Email verification and password reset tokens."""

    __tablename__ = "verification_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    token_type = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime, nullable=True)

    user = relationship("User")

    __table_args__ = (Index("idx_verification_user_type", "user_id", "token_type"),)


class UserSettings(Base):
    """Per-user settings/preferences."""

    __tablename__ = "user_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    theme = Column(String(16), default="dark", nullable=False)
    language = Column(String(16), default="en", nullable=False)
    settings = Column(JSON, default=dict[str, Any], nullable=False)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# =============================================================================
# HOUSEHOLDS: MULTI-USER SUPPORT
# =============================================================================


class Household(Base):
    """Household for multi-user family/home sharing.

    A household represents a physical home with multiple users who share
    smart home control. One user is the owner, others have various roles.
    """

    __tablename__ = "households"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    address = Column(Text, nullable=True)
    timezone = Column(String(50), default="UTC")

    # Settings
    guest_access_enabled = Column(Boolean, default=True)
    guest_access_duration_hours = Column(Integer, default=24)
    require_2fa_for_device_control = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = relationship("User", foreign_keys=[owner_id])
    members = relationship(
        "HouseholdMember", back_populates="household", cascade="all, delete-orphan"
    )
    invitations = relationship(
        "HouseholdInvitation", back_populates="household", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_households_owner", "owner_id"),)


class HouseholdMember(Base):
    """Junction table for household membership with roles.

    Roles:
    - owner: Full control, billing, can delete household
    - admin: Manage members, all device control
    - member: Device control, can't manage members
    - child: Restricted access, parental controls
    - elder: Simplified interface, family monitoring opt-in
    - caregiver: Staff access, time-tracked shifts
    - guest: Limited device control, time-limited access
    """

    __tablename__ = "household_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Role
    role = Column(String(20), nullable=False, default="member")

    # For guests: when access expires
    expires_at = Column(DateTime, nullable=True)

    # Role-specific settings (JSONB)
    settings = Column(JSON, default=dict[str, Any])

    # Activity tracking
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_active = Column(DateTime, default=datetime.utcnow)

    # Relationships
    household = relationship("Household", back_populates="members")
    user = relationship("User")

    __table_args__ = (
        Index("idx_household_members_household", "household_id"),
        Index("idx_household_members_user", "user_id"),
        Index("idx_household_members_role", "role"),
    )


class HouseholdInvitation(Base):
    """Invitation to join a household."""

    __tablename__ = "household_invitations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id = Column(UUID(as_uuid=True), ForeignKey("households.id"), nullable=False)

    # Invitation details
    email = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="member")
    code = Column(String(64), nullable=False, unique=True, index=True)
    message = Column(Text, nullable=True)

    # Who sent it
    invited_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Status
    status = Column(String(20), nullable=False, default="pending")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime, nullable=True)

    # Relationships
    household = relationship("Household", back_populates="invitations")
    invited_by = relationship("User")

    __table_args__ = (
        Index("idx_invitations_household", "household_id"),
        Index("idx_invitations_email", "email"),
        Index("idx_invitations_status", "status"),
    )


class UserPreference(Base):
    """Per-user preference key-value storage.

    Flexible storage for user preferences including:
    - language: User's preferred language (en, es, ar, etc.)
    - schedule: Work schedule type (standard, night_shift, rotating)
    - accessibility: Accessibility settings (simplified_mode, visual_alerts, etc.)
    """

    __tablename__ = "user_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    key = Column(String(100), nullable=False)
    value = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("idx_user_preferences_user", "user_id"),)


class OAuthConnection(Base):
    """OAuth provider connections for SSO (Apple, Google).

    Stores OAuth tokens and profile data for connected accounts.
    """

    __tablename__ = "oauth_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Provider: apple, google
    provider = Column(String(20), nullable=False)
    provider_user_id = Column(String(255), nullable=False)

    # Tokens
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)

    # Profile from provider
    email = Column(String(255), nullable=True)
    name = Column(String(255), nullable=True)
    profile_data = Column(JSON, default=dict[str, Any])

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User")

    __table_args__ = (
        Index("idx_oauth_user", "user_id"),
        Index("idx_oauth_provider", "provider", "provider_user_id"),
    )


# =============================================================================
# RECEIPTS: PLAN/EXECUTE/VERIFY TRACKING
# =============================================================================


class Receipt(Base):
    """Receipt for PLAN/EXECUTE/VERIFY tracking.

    This is the core learning signal. Every operation emits triplets.
    Optimized for high-write with hash-sharded primary key.
    """

    __tablename__ = "receipts"

    # UUID primary key avoids sequential hotspots
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id = Column(String(100), nullable=False, index=True)

    # Parent receipt for phase/operation DAG
    # Note: Uses String(100) to match short correlation_id format (8-12 chars)
    # The parent_receipt_id links to another receipt's correlation_id, not its UUID id
    parent_receipt_id = Column(String(100), nullable=True, index=True)

    # Phase: PLAN, EXECUTE, VERIFY
    phase = Column(String(16), nullable=False, index=True)

    # Operation context
    action = Column(String(100), nullable=True, index=True)
    app = Column(String(50), nullable=True, index=True)
    status = Column(String(32), nullable=True, index=True)

    # Multi-tenant
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    tenant_id = Column(String(100), nullable=True, index=True)

    # Flexible data (JSONB with inverted index)
    intent = Column(JSON, nullable=False, default=dict[str, Any])
    event = Column(JSON, nullable=True)
    data = Column(JSON, nullable=True)
    metrics = Column(JSON, nullable=True)

    # TIC reference (foreign key to tic_records)
    tic_id = Column(UUID(as_uuid=True), ForeignKey("tic_records.id"), nullable=True)

    # Performance
    duration_ms = Column(Integer, nullable=False, default=0)

    # Timestamps (indexed for time-series queries)
    ts = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationship to TIC
    tic = relationship("TICRecord", backref="receipts")

    __table_args__ = (
        Index("idx_receipt_correlation", "correlation_id"),
        Index("idx_receipt_parent", "parent_receipt_id"),
        Index("idx_receipt_phase_ts", "phase", "ts"),
        Index("idx_receipt_app_action", "app", "action"),
        Index("idx_receipt_tenant_ts", "tenant_id", "ts"),
        Index("idx_receipt_status_ts", "status", "ts"),
        # CockroachDB: Add hash-sharded hint for high-write
        {"comment": "SHARDED BY (id) -- CockroachDB optimization"},
    )


class TICRecord(Base):
    """Typed Intent Calculus (TIC) tuple[Any, ...] storage.

    τ = {E, P, Q, I, T} - Effects, Preconditions, Postconditions, Invariants, Termination

    This provides formal verification data for receipts.
    """

    __tablename__ = "tic_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id = Column(String(100), nullable=False, index=True)

    # Operation identity
    operation = Column(String(255), nullable=False, index=True)
    operation_type = Column(String(100), nullable=False, index=True)

    # E: Effects (list[Any] of effect names)
    effects = Column(JSON, nullable=False, default=list[Any])

    # P: Preconditions (dict[str, Any] of condition -> status)
    preconditions = Column(JSON, nullable=False, default=dict[str, Any])

    # Q: Postconditions (dict[str, Any] of condition -> status)
    postconditions = Column(JSON, nullable=False, default=dict[str, Any])

    # I: Invariants (list[Any] of invariant expressions)
    invariants = Column(JSON, nullable=False, default=lambda: ["h(x) >= 0", "energy > 0"])

    # T: Termination
    termination_type = Column(String(32), nullable=True)  # bounded_fuel, timeout, ranking_function
    fuel_limit = Column(Integer, nullable=True)
    time_limit_ms = Column(Float, nullable=True)

    # Evidence
    evidence_type = Column(String(16), nullable=True)  # pco, mco, axiom
    evidence_verified = Column(Boolean, default=False)
    evidence_content = Column(JSON, nullable=True)

    # Safety: CBF barrier value at time of TIC creation
    barrier_value = Column(Float, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_tic_correlation", "correlation_id"),
        Index("idx_tic_operation", "operation", "operation_type"),
    )


class IdempotencyKey(Base):
    """Idempotency key for preventing duplicate operations."""

    __tablename__ = "idempotency_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(200), unique=True, nullable=False, index=True)
    path = Column(String(200), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    tenant_id = Column(String(100), nullable=True, index=True)
    status_code = Column(Integer, nullable=True)
    response_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True, index=True)

    __table_args__ = (
        Index("idx_idempo_path_user", "path", "user_id"),
        Index("idx_idempo_tenant", "tenant_id"),
    )


# =============================================================================
# SAFETY: CBF STATE TRACKING
# =============================================================================


class SafetyStateSnapshot(Base):
    """Control Barrier Function state snapshots.

    Tracks h(x) values over time for learning and auditing.
    State vector: x = [threat, uncertainty, complexity, predictive_risk]

    This is CRITICAL for:
    1. Learning what states are safe
    2. Auditing safety decisions
    3. Improving CBF parameters
    """

    __tablename__ = "safety_state_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id = Column(String(100), nullable=False, index=True)

    # State vector components x ∈ ℝ⁴
    threat = Column(Float, nullable=False)
    uncertainty = Column(Float, nullable=False)
    complexity = Column(Float, nullable=False)
    predictive_risk = Column(Float, nullable=False)

    # Barrier function h(x) - MUST be >= 0 for safe states
    barrier_value = Column(Float, nullable=False, index=True)
    barrier_derivative = Column(Float, nullable=True)  # ḣ(x)

    # Contraction rate κ(φ) for adaptive safety
    contraction_rate = Column(Float, nullable=True)

    # Action taken by CBF
    action_type = Column(String(32), nullable=True, index=True)  # allow, refuse, degrade
    action_adjusted = Column(Boolean, default=False)

    # Control input if modified
    control_input = Column(JSON, nullable=True)  # [aggression, speed]

    # QP solver info
    qp_iterations = Column(Integer, nullable=True)
    qp_converged = Column(Boolean, nullable=True)

    # Threat classification (from Safe RLHF paper)
    scenario = Column(String(50), nullable=True, index=True)  # insult, discrimination, etc.
    attack_type = Column(String(50), nullable=True, index=True)  # goal_hijacking, etc.
    risk_multiplier = Column(Float, nullable=True)

    # Context
    operation = Column(String(255), nullable=True)
    source = Column(String(50), nullable=True)

    # Timestamps
    ts = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_safety_correlation", "correlation_id"),
        Index("idx_safety_barrier_ts", "barrier_value", "ts"),
        Index("idx_safety_action_ts", "action_type", "ts"),
        Index("idx_safety_scenario", "scenario", "attack_type"),
        {"comment": "SHARDED BY (id) -- High-write table"},
    )


class ThreatClassification(Base):
    """Threat classification results (from Safe RLHF paper).

    Stores detected safety scenarios and attack patterns
    for learning and monitoring.
    """

    __tablename__ = "threat_classifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id = Column(String(100), nullable=False, index=True)

    # Scenario detection (8 types from Safe RLHF)
    scenario = Column(String(50), nullable=True, index=True)
    scenario_confidence = Column(Float, nullable=True)

    # Attack detection (6 types from Safe RLHF)
    attack_type = Column(String(50), nullable=True, index=True)
    attack_confidence = Column(Float, nullable=True)

    # Combined risk
    combined_risk_multiplier = Column(Float, nullable=True)
    requires_elevated_safety = Column(Boolean, default=False)

    # Raw input for learning
    prompt_hash = Column(String(64), nullable=True)
    context_hash = Column(String(64), nullable=True)

    # Timestamps
    ts = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (Index("idx_threat_scenario_attack", "scenario", "attack_type"),)


# =============================================================================
# LEARNING: REWARD, EFE, WORLD MODEL
# =============================================================================


class RewardSignal(Base):
    """Reward signal tracking for learning.

    Tracks multi-component rewards for Safe RLHF-style training:
    - Task reward (completion)
    - Safety reward (CBF constraint satisfaction)
    - Alignment reward (human preference)

    Combined via Lagrangian for constrained optimization.
    """

    __tablename__ = "reward_signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id = Column(String(100), nullable=False, index=True)

    # Reward components
    task_reward = Column(Float, nullable=True)
    safety_reward = Column(Float, nullable=True)
    alignment_reward = Column(Float, nullable=True)

    # Combined reward with Lagrangian
    combined_reward = Column(Float, nullable=True)
    lagrange_multiplier = Column(Float, nullable=True)

    # Constraint satisfaction
    safety_constraint_satisfied = Column(Boolean, nullable=True)
    constraint_margin = Column(Float, nullable=True)  # h(x)

    # Human feedback (if any)
    human_feedback_type = Column(String(32), nullable=True)  # comparison, rating, correction
    human_feedback_value = Column(JSON, nullable=True)

    # Context
    action = Column(String(255), nullable=True)
    state_before = Column(JSON, nullable=True)
    state_after = Column(JSON, nullable=True)

    # Timestamps
    ts = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_reward_correlation", "correlation_id"),
        Index("idx_reward_combined_ts", "combined_reward", "ts"),
        {"comment": "SHARDED BY (id) -- High-write table"},
    )


class ExpectedFreeEnergy(Base):
    """Expected Free Energy (EFE) tracking for Active Inference.

    G(π) = Epistemic + Pragmatic + Risk

    Tracks action selection rationale for explainability and learning.
    """

    __tablename__ = "expected_free_energy"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id = Column(String(100), nullable=False, index=True)

    # EFE components
    epistemic_value = Column(Float, nullable=True)  # Information gain
    pragmatic_value = Column(Float, nullable=True)  # Goal achievement
    risk_value = Column(Float, nullable=True)  # Safety/uncertainty

    # Total EFE (lower is better)
    total_efe = Column(Float, nullable=True, index=True)

    # Selected action
    action_selected = Column(String(255), nullable=True)
    action_index = Column(Integer, nullable=True)

    # Candidates (all considered actions with scores)
    action_candidates = Column(JSON, nullable=True)
    num_candidates = Column(Integer, nullable=True)

    # Entropy measures
    policy_entropy = Column(Float, nullable=True)
    state_entropy = Column(Float, nullable=True)

    # Timestamps
    ts = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_efe_correlation", "correlation_id"),
        Index("idx_efe_total_ts", "total_efe", "ts"),
    )


class WorldModelPrediction(Base):
    """World model prediction tracking.

    Tracks predictions vs actuals for world model learning.
    Enables counterfactual learning and model improvement.
    """

    __tablename__ = "world_model_predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id = Column(String(100), nullable=False, index=True)

    # Prediction
    predicted_state = Column(JSON, nullable=True)
    prediction_horizon = Column(Integer, nullable=True)
    prediction_confidence = Column(Float, nullable=True)

    # Actual outcome
    actual_state = Column(JSON, nullable=True)
    actual_observed = Column(Boolean, default=False)

    # Error metrics
    prediction_error = Column(Float, nullable=True, index=True)  # L2 error
    kl_divergence = Column(Float, nullable=True)
    surprise = Column(Float, nullable=True)  # -log P(actual|predicted)

    # Learning signal
    gradient_magnitude = Column(Float, nullable=True)
    learning_rate_used = Column(Float, nullable=True)
    loss_contribution = Column(Float, nullable=True)

    # Context
    action_taken = Column(String(255), nullable=True)
    model_version = Column(String(50), nullable=True)

    # Timestamps
    ts = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    observation_ts = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_wm_pred_correlation", "correlation_id"),
        Index("idx_wm_pred_error_ts", "prediction_error", "ts"),
        {"comment": "SHARDED BY (id) -- High-write table"},
    )


class CalibrationPoint(Base):
    """Confidence calibration data points.

    Tracks predicted confidence vs actual success for calibration.
    """

    __tablename__ = "calibration_points"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id = Column(String(255), nullable=False, index=True)

    predicted_confidence = Column(Float, nullable=False)
    actual_success = Column(Boolean, nullable=False)

    task_type = Column(String(255), nullable=False, index=True)
    timestamp = Column(Float, nullable=False, index=True)

    __table_args__ = (Index("idx_calib_task_ts", "task_type", "timestamp"),)


class IntegrationMeasurement(Base):
    """Integration heuristic measurements (formerly phi_measurements)."""

    __tablename__ = "integration_measurements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    integration_score = Column(Float, nullable=False)  # Heuristic in [0, 1]
    timestamp = Column(Float, nullable=False, index=True)
    task_complexity = Column(Float, nullable=False)
    task_type = Column(String(255), nullable=False, index=True)
    phase = Column(String(50), nullable=False)
    correlation_id = Column(String(255), nullable=False, index=True)
    extra_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)

    __table_args__ = (
        Index("idx_integration_ts", "timestamp"),
        Index("idx_integration_task", "task_type"),
    )


# =============================================================================
# COLONY STATE & COORDINATION
# =============================================================================


class ColonyState(Base):
    """Colony state persistence for distributed coordination.

    Stores z-states (latent states) for each colony instance.
    Enables CRDT-based state synchronization via etcd.
    """

    __tablename__ = "colony_states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    colony_id = Column(String(50), nullable=False, index=True)
    instance_id = Column(String(100), nullable=False, index=True)
    node_id = Column(String(100), nullable=False)

    # Z-state (latent state vector)
    z_state = Column(JSON, nullable=False)
    z_dim = Column(Integer, nullable=False, default=64)

    # CRDT metadata
    timestamp = Column(Float, nullable=False, index=True)
    vector_clock = Column(JSON, default=dict[str, Any])

    # Action history (GSet)
    action_history = Column(JSON, default=list[Any])
    last_action = Column(String(255), nullable=True)

    # Fano plane neighbors (octonion structure)
    fano_neighbors = Column(JSON, default=list[Any])

    # Health status
    is_active = Column(Boolean, default=True, index=True)
    last_heartbeat_at = Column(DateTime, nullable=True)

    # Metadata
    state_metadata = Column(JSON, default=dict[str, Any])
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_colony_state_colony_instance", "colony_id", "instance_id", unique=True),
        Index("idx_colony_state_active", "is_active", "colony_id"),
        Index("idx_colony_state_timestamp", "colony_id", "timestamp"),
    )


# =============================================================================
# TRAINING & LEARNING
# =============================================================================


class TrainingRun(Base):
    """Training run tracking and metrics.

    Tracks pretraining, fine-tuning, and reinforcement learning runs.
    Stores hyperparameters, metrics, and artifacts.
    """

    __tablename__ = "training_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)

    # Training type
    run_type = Column(String(50), nullable=False, index=True)  # pretrain, finetune, rl, joint

    # User/tenant
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    tenant_id = Column(String(100), nullable=True, index=True)

    # Configuration
    config = Column(JSON, nullable=False)
    model_architecture = Column(String(100), nullable=True)
    dataset_name = Column(String(255), nullable=True)

    # Status
    status = Column(
        String(32), nullable=False, default="pending", index=True
    )  # pending, running, completed, failed, cancelled
    progress = Column(Float, nullable=False, default=0.0)

    # Metrics (time-series stored as JSON arrays)
    metrics = Column(JSON, default=dict[str, Any])
    best_loss = Column(Float, nullable=True)
    best_accuracy = Column(Float, nullable=True)
    final_loss = Column(Float, nullable=True)

    # Training progress
    current_epoch = Column(Integer, default=0)
    total_epochs = Column(Integer, nullable=True)
    current_step = Column(Integer, default=0)
    total_steps = Column(Integer, nullable=True)

    # Resource usage
    gpu_hours = Column(Float, default=0.0)
    total_tokens_processed = Column(Integer, default=0)

    # Artifacts
    checkpoint_path = Column(String(512), nullable=True)
    model_path = Column(String(512), nullable=True)
    log_path = Column(String(512), nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)
    error_traceback = Column(Text, nullable=True)

    # Timestamps
    started_at = Column(DateTime, nullable=True, index=True)
    completed_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User")

    __table_args__ = (
        Index("idx_training_run_status", "status", "started_at"),
        Index("idx_training_run_user_status", "user_id", "status"),
        Index("idx_training_run_type", "run_type", "status"),
    )


class TrainingCheckpoint(Base):
    """Training checkpoint metadata.

    Tracks model checkpoints during training for recovery and analysis.
    """

    __tablename__ = "training_checkpoints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(String(100), ForeignKey("training_runs.run_id"), nullable=False, index=True)
    checkpoint_id = Column(String(100), unique=True, nullable=False, index=True)

    # Checkpoint info
    epoch = Column(Integer, nullable=False)
    step = Column(Integer, nullable=False)
    loss = Column(Float, nullable=True)
    accuracy = Column(Float, nullable=True)

    # Storage
    file_path = Column(String(512), nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    storage_backend = Column(String(50), default="local")

    # Metadata
    metrics = Column(JSON, default=dict[str, Any])
    is_best = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("idx_checkpoint_run_step", "run_id", "step"),
        Index("idx_checkpoint_run_best", "run_id", "is_best"),
    )


# =============================================================================
# GOALS & PLANS
# =============================================================================


class Goal(Base):
    """Organism goals for tracking and persistence."""

    __tablename__ = "organism_goals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    goal_id = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=False)
    success_criteria = Column(JSON, default=dict[str, Any])
    priority = Column(Integer, default=5)
    deadline = Column(DateTime, nullable=True)
    parent_goal_id = Column(String(100), nullable=True)

    status = Column(String(50), default="active", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_attempt_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    completion_percentage = Column(Float, default=0.0)
    estimated_steps = Column(Integer, default=0)
    completed_steps = Column(Integer, default=0)

    next_action = Column(String(255), nullable=True)
    prediction_error = Column(Float, default=0.0)
    actual_difficulty = Column(Float, default=0.5)

    goal_metadata = Column("metadata", JSON, default=dict[str, Any])

    __table_args__ = (
        Index("idx_goal_status", "status"),
        Index("idx_goal_parent", "parent_goal_id"),
        Index("idx_goal_priority", "priority", "status"),
    )


class Plan(Base):
    """Project plan entity."""

    __tablename__ = "plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(String(100), unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)

    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    type = Column(String(50), nullable=False, default="project", index=True)
    status = Column(String(32), nullable=False, default="active", index=True)
    progress = Column(Integer, nullable=False, default=0)
    target_date = Column(DateTime, nullable=True)
    emotional_tags = Column(JSON, nullable=True)
    plan_metadata = Column(JSON, nullable=True)
    visibility = Column(String(16), nullable=False, default="public", index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tasks = relationship(
        "PlanTask",
        back_populates="plan",
        cascade="all, delete-orphan",
        primaryjoin="Plan.plan_id==PlanTask.plan_id",
        foreign_keys="PlanTask.plan_id",
    )

    __table_args__ = (
        Index("idx_plan_user_status", "user_id", "status"),
        Index("idx_plan_progress", "status", "progress"),
    )


class PlanTask(Base):
    """Task records associated with a plan."""

    __tablename__ = "plan_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(String(100), unique=True, nullable=False, index=True)
    plan_id = Column(String(100), ForeignKey("plans.plan_id"), nullable=False, index=True)

    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="pending", index=True)
    priority = Column(String(16), nullable=True)
    due_date = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    plan = relationship(
        "Plan",
        back_populates="tasks",
        primaryjoin="PlanTask.plan_id==Plan.plan_id",
        foreign_keys=[plan_id],
    )

    __table_args__ = (
        Index("idx_task_plan_status", "plan_id", "status"),
        Index("idx_task_priority", "priority", "due_date"),
    )


# =============================================================================
# BILLING & TENANCY
# =============================================================================


class TenantPlan(Base):
    """Per-tenant billing plan and limits."""

    __tablename__ = "tenant_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(100), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    plan_name = Column(String(50), nullable=False, index=True)

    ops_price_per_k = Column(Numeric(10, 4), nullable=True)
    settlement_price_per_op = Column(Numeric(10, 4), nullable=True)
    ops_monthly_cap = Column(Integer, nullable=True)
    settlement_monthly_cap = Column(Integer, nullable=True)

    valid_from = Column(DateTime, default=datetime.utcnow, nullable=False)
    valid_to = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (Index("idx_tenant_plan", "tenant_id", "plan_name"),)


class TenantUsage(Base):
    """Aggregated monthly usage metrics per tenant."""

    __tablename__ = "tenant_usage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(100), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    period = Column(String(7), nullable=False, index=True)

    ops_count = Column(Integer, default=0, nullable=False)
    settlement_count = Column(Integer, default=0, nullable=False)
    tokens_used = Column(Integer, default=0, nullable=False)
    storage_bytes = Column(Integer, default=0, nullable=False)
    bandwidth_bytes = Column(Integer, default=0, nullable=False)
    cost_usd = Column(Numeric(15, 4), default=0, nullable=False)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("idx_usage_tenant_period", "tenant_id", "period", unique=True),)


class SettlementRecord(Base):
    """Settlement submissions for billing/compliance."""

    __tablename__ = "settlement_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    operation_id = Column(String(200), unique=True, nullable=False, index=True)
    protocol = Column(String(100), nullable=False, index=True)
    operation = Column(String(100), nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    parameters = Column(JSON, default=dict[str, Any])
    result_summary = Column(JSON, default=dict[str, Any])
    idempotency_key = Column(String(200), unique=True, nullable=True, index=True)
    source_ip = Column(String(45), nullable=True)
    tenant_id = Column(String(100), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)

    user = relationship("User")

    __table_args__ = (
        Index("idx_settlement_time", "timestamp"),
        Index("idx_settlement_user_time", "user_id", "timestamp"),
    )


class MarketplacePlugin(Base):
    """Marketplace plugin metadata and review status."""

    __tablename__ = "marketplace_plugins"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=False)
    category = Column(String(16), nullable=False, index=True)  # agent|integration|tool|ui|theme
    version = Column(String(32), nullable=False)

    repository_url = Column(String(512), nullable=True)
    documentation_url = Column(String(512), nullable=True)
    homepage_url = Column(String(512), nullable=True)

    pricing_model = Column(
        String(32), nullable=False, default="free", index=True
    )  # free|paid|freemium
    price_usd = Column(Float, nullable=True)
    stripe_price_id = Column(String(255), nullable=True)

    kagami_min_version = Column(String(32), nullable=True)
    required_permissions = Column(JSON, default=list[Any], nullable=False)
    external_dependencies = Column(JSON, default=list[Any], nullable=False)

    icon_url = Column(String(512), nullable=True)
    screenshot_urls = Column(JSON, default=list[Any], nullable=False)
    video_url = Column(String(512), nullable=True)

    tags = Column(JSON, default=list[Any], nullable=False)
    license = Column(String(64), default="MIT", nullable=False)

    status = Column(
        String(32), nullable=False, default="pending", index=True
    )  # pending|approved|rejected
    author_id = Column(String(100), nullable=True, index=True)
    author_name = Column(String(100), nullable=True)

    install_count = Column(Integer, default=0, nullable=False)
    average_rating = Column(Float, default=0.0, nullable=False)
    review_count = Column(Integer, default=0, nullable=False)

    moderation_notes = Column(JSON, default=dict[str, Any], nullable=True)
    rejection_reason = Column(Text, nullable=True)

    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    approved_at = Column(DateTime, nullable=True, index=True)
    rejected_at = Column(DateTime, nullable=True, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("idx_marketplace_plugins_status_category", "status", "category"),)


class MarketplacePluginReview(Base):
    """User reviews for marketplace plugins."""

    __tablename__ = "marketplace_plugin_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plugin_id = Column(
        UUID(as_uuid=True), ForeignKey("marketplace_plugins.id"), nullable=False, index=True
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    rating = Column(Integer, nullable=False)
    title = Column(String(100), nullable=False)
    comment = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="active", index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    plugin = relationship("MarketplacePlugin")
    user = relationship("User")

    __table_args__ = (
        Index("idx_marketplace_plugin_review_unique", "plugin_id", "user_id", unique=True),
        Index("idx_marketplace_plugin_review_plugin_time", "plugin_id", "created_at"),
    )


class MarketplacePurchase(Base):
    """Marketplace purchase entitlements."""

    __tablename__ = "marketplace_purchases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    item_type = Column(String(32), nullable=False, index=True)
    item_id = Column(String(100), nullable=False, index=True)
    price_model = Column(String(32), nullable=True)
    status = Column(String(32), nullable=False, default="active", index=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    purchase_metadata = Column(JSON, default=dict[str, Any])

    user = relationship("User")

    __table_args__ = (
        Index("idx_marketplace_entitlement", "user_id", "item_type", "item_id", unique=True),
    )


class MarketplacePayout(Base):
    """Creator payouts."""

    __tablename__ = "marketplace_payouts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    creator_id = Column(String(100), nullable=False, index=True)
    item_type = Column(String(32), nullable=False)
    item_id = Column(String(100), nullable=False)
    period = Column(String(7), nullable=False, index=True)
    attestations = Column(Integer, default=0, nullable=False)
    gross_usd = Column(Numeric(15, 4), default=0, nullable=False)
    platform_take_rate = Column(Float, default=0.2)
    payout_usd = Column(Numeric(15, 4), default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_payout_key", "creator_id", "item_type", "item_id", "period", unique=True),
    )


# =============================================================================
# GENERIC APP DATA
# =============================================================================


class AppData(Base):
    """Generic storage for app data using JSON fields."""

    __tablename__ = "app_data"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    app_name = Column(String(50), nullable=False, index=True)
    data_type = Column(String(50), nullable=False)
    data_id = Column(String(100), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    data = Column(JSON, nullable=False)

    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_app_data_lookup", "app_name", "data_type", "data_id"),
        Index("idx_app_data_user", "app_name", "user_id"),
        Index("idx_app_data_active", "app_name", "data_type", "is_active"),
    )


class ProceduralWorkflow(Base):
    """Procedural workflows."""

    __tablename__ = "procedural_workflows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    pattern = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# =============================================================================
# AUDIT LOG
# =============================================================================


class AuditLogEntry(Base):
    """Audit log entries."""

    __tablename__ = "audit_log_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(100), nullable=False, index=True)
    actor_id = Column(String(100), nullable=True, index=True)
    target_type = Column(String(100), nullable=True)
    target_id = Column(String(100), nullable=True)
    action = Column(String(100), nullable=False)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    tenant_id = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("idx_audit_actor_time", "actor_id", "created_at"),
        Index("idx_audit_event_time", "event_type", "created_at"),
        {"comment": "SHARDED BY (id) -- High-write table"},
    )


# =============================================================================
# PRIVACY: GDPR COMPLIANCE
# =============================================================================


class UserConsent(Base):
    """User consent tracking for GDPR compliance."""

    __tablename__ = "user_consents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    consent_type = Column(String(50), nullable=False)  # cookie, analytics, marketing
    granted = Column(Boolean, nullable=False, default=False)
    granted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (Index("idx_user_consents_user_type", "user_id", "consent_type"),)


class PrivacyAuditLog(Base):
    """Audit log for privacy-sensitive operations (GDPR)."""

    __tablename__ = "privacy_audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action = Column(String(50), nullable=False)  # access, modify, delete, export
    resource = Column(String(200), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    ip_address = Column(String(45), nullable=True)  # IPv6 support
    user_agent = Column(Text, nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_privacy_audit_user_ts", "user_id", "timestamp"),
        Index("idx_privacy_audit_action", "action", "timestamp"),
    )


# =============================================================================
# IDENTITY & BIOMETRICS
# =============================================================================


class Identity(Base):
    """Identity record for household members and known people.

    Stores face/voice embeddings for real-time recognition.
    Connected to presence system for "Who is home?" queries.

    Biometric data is encrypted at rest via JSONB with application-level encryption.
    """

    __tablename__ = "identities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identity_id = Column(String(50), unique=True, nullable=False, index=True)

    # Basic info
    name = Column(String(255), nullable=True)
    status = Column(
        String(32), nullable=False, default="auto_detected", index=True
    )  # auto_detected, confirmed, merged

    # User link (if this identity is a household member)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Embeddings (stored as JSONB arrays for portability)
    # Face: 512-dim InsightFace embedding
    face_embedding = Column(JSON, nullable=True)
    face_embedding_quality = Column(Float, nullable=True)

    # Voice: 192-dim SpeechBrain embedding
    voice_embedding = Column(JSON, nullable=True)
    voice_embedding_quality = Column(Float, nullable=True)

    # ReID: 2048-dim TorchReID embedding
    reid_embedding = Column(JSON, nullable=True)

    # Confidence thresholds (per-identity tuning)
    face_threshold = Column(Float, default=0.6)
    voice_threshold = Column(Float, default=0.7)

    # Statistics
    observation_count = Column(Integer, default=0)
    total_duration_seconds = Column(Float, default=0.0)

    # Source tracking
    source_videos = Column(JSON, default=list)  # List of source video paths

    # Presence link
    presence_registered = Column(Boolean, default=False, index=True)
    last_seen_location = Column(String(100), nullable=True)
    last_seen_at = Column(DateTime, nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User")
    observations = relationship(
        "IdentityObservation", back_populates="identity", cascade="all, delete-orphan"
    )
    embeddings = relationship(
        "IdentityEmbedding", back_populates="identity", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_identity_status", "status"),
        Index("idx_identity_presence", "presence_registered", "last_seen_at"),
        Index("idx_identity_user", "user_id"),
    )


class IdentityObservation(Base):
    """Record of identity observation from camera or voice.

    Each time an identity is detected, an observation is recorded.
    Observations are cryptographically signed for mesh propagation.
    """

    __tablename__ = "identity_observations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identity_id = Column(
        UUID(as_uuid=True), ForeignKey("identities.id"), nullable=False, index=True
    )

    # Detection source
    source_type = Column(String(32), nullable=False, index=True)  # camera, voice, manual
    source_id = Column(String(100), nullable=False)  # camera_id or hub_id
    location = Column(String(100), nullable=True)  # Room/zone name

    # Detection quality
    confidence = Column(Float, nullable=False)
    embedding_quality = Column(Float, nullable=True)

    # Cryptographic signature (Ed25519)
    # Signs: identity_id + source_id + timestamp + confidence
    signature = Column(String(128), nullable=True)  # Base64 encoded
    signer_hub_id = Column(String(100), nullable=True)  # Hub that signed

    # Frame/audio reference (for debugging)
    frame_path = Column(String(512), nullable=True)
    audio_path = Column(String(512), nullable=True)

    # Timestamps
    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    identity = relationship("Identity", back_populates="observations")

    __table_args__ = (
        Index("idx_observation_identity_time", "identity_id", "detected_at"),
        Index("idx_observation_source", "source_type", "source_id"),
        Index("idx_observation_location", "location", "detected_at"),
    )


class IdentityEmbedding(Base):
    """Additional embeddings for an identity.

    Stores multiple embeddings per type for ensemble matching.
    Higher quality embeddings can replace lower quality ones.
    """

    __tablename__ = "identity_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identity_id = Column(
        UUID(as_uuid=True), ForeignKey("identities.id"), nullable=False, index=True
    )

    # Embedding type
    embedding_type = Column(String(32), nullable=False, index=True)  # face, voice, reid

    # Embedding vector (JSONB array)
    embedding_vector = Column(JSON, nullable=False)
    embedding_dim = Column(Integer, nullable=False)

    # Quality metrics
    quality_score = Column(Float, nullable=False, default=0.0)
    sharpness = Column(Float, nullable=True)
    frontality = Column(Float, nullable=True)  # For face embeddings

    # Source tracking
    source_video = Column(String(512), nullable=True)
    source_timestamp = Column(Float, nullable=True)  # Seconds into video
    source_frame = Column(Integer, nullable=True)

    # Status
    is_primary = Column(Boolean, default=False, index=True)  # Best embedding for type

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    identity = relationship("Identity", back_populates="embeddings")

    __table_args__ = (
        Index("idx_embedding_identity_type", "identity_id", "embedding_type"),
        Index("idx_embedding_primary", "identity_id", "embedding_type", "is_primary"),
        Index("idx_embedding_quality", "embedding_type", "quality_score"),
    )


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    "APIKey",
    # Generic
    "AppData",
    "AuditLogEntry",
    "CalibrationPoint",
    # Colony
    "ColonyState",
    "ExpectedFreeEnergy",
    # Goals
    "Goal",
    "IdempotencyKey",
    # Identity & Biometrics
    "Identity",
    "IdentityEmbedding",
    "IdentityObservation",
    "IntegrationMeasurement",
    "MarketplacePayout",
    "MarketplacePurchase",
    "Plan",
    "PlanTask",
    "PrivacyAuditLog",
    "ProceduralWorkflow",
    # Receipts
    "Receipt",
    # Learning
    "RewardSignal",
    # Safety
    "SafetyStateSnapshot",
    "Session",
    "SettlementRecord",
    "TICRecord",
    # Billing
    "TenantPlan",
    "TenantUsage",
    "ThreatClassification",
    # Training
    "TrainingCheckpoint",
    "TrainingRun",
    # Core
    "User",
    # Privacy
    "UserConsent",
    "UserSettings",
    "VerificationToken",
    "WorldModelPrediction",
    # Utilities (re-exported from kagami.core.utils.ids)
    "generate_uuid",
]
