"""Comprehensive tests for database models.

Tests all ORM models, relationships, validators, and CRDT operations.

Created: December 28, 2025
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kagami.core.database.models import (
    APIKey,
    ColonyState,
    Goal,
    IdempotencyKey,
    Plan,
    PlanTask,
    Receipt,
    Session,
    TICRecord,
    TrainingCheckpoint,
    TrainingRun,
    User,
    VerificationToken,
)

pytestmark = pytest.mark.tier_integration


# =============================================================================
# User Model Tests
# =============================================================================


@pytest.mark.asyncio
async def test_user_model_creation(db_session: AsyncSession):
    """Test user model creation with all fields."""
    user = User(
        id=uuid.uuid4(),
        username="john_doe",
        email="john@example.com",
        hashed_password="$2b$12$hashed",
        roles=["user", "admin"],
        is_active=True,
        is_superuser=False,
        is_verified=True,
        tenant_id="tenant-001",
        sso_provider="google",
        sso_user_id="google-123",
        stripe_customer_id="cus_123",
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.id is not None
    assert user.username == "john_doe"
    assert user.email == "john@example.com"
    assert user.roles == ["user", "admin"]
    assert user.is_active is True
    assert user.tenant_id == "tenant-001"
    assert user.created_at is not None
    assert user.updated_at is not None


@pytest.mark.asyncio
async def test_user_unique_constraints(db_session: AsyncSession):
    """Test user unique constraints."""
    user1 = User(
        id=uuid.uuid4(),
        username="test_user",
        email="test@example.com",
        hashed_password="hash",
    )
    db_session.add(user1)
    await db_session.commit()

    # Try to create duplicate username
    user2 = User(
        id=uuid.uuid4(),
        username="test_user",
        email="other@example.com",
        hashed_password="hash",
    )
    db_session.add(user2)

    with pytest.raises(Exception):  # IntegrityError
        await db_session.commit()


@pytest.mark.asyncio
async def test_user_relationships(db_session: AsyncSession, sample_user: User):
    """Test user relationships with API keys and sessions."""
    # Create API key
    api_key = APIKey(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        key="sk_test_123",
        name="Test Key",
        scopes=["read", "write"],
        is_active=True,
    )
    db_session.add(api_key)

    # Create session
    session = Session(
        id=uuid.uuid4(),
        session_id="sess_123",
        user_id=sample_user.id,
        ip_address="127.0.0.1",
        is_active=True,
        expires_at=datetime.utcnow() + timedelta(days=1),
    )
    db_session.add(session)
    await db_session.commit()

    # Refresh and check relationships
    await db_session.refresh(sample_user)
    assert len(sample_user.api_keys) == 1
    assert len(sample_user.sessions) == 1
    assert sample_user.api_keys[0].key == "sk_test_123"


# =============================================================================
# ColonyState Model Tests
# =============================================================================


@pytest.mark.asyncio
async def test_colony_state_creation(db_session: AsyncSession):
    """Test colony state model creation."""
    state = ColonyState(
        id=uuid.uuid4(),
        colony_id="spark",
        instance_id="spark-001",
        node_id="node-001",
        z_state={"latent": [0.5] * 64},
        z_dim=64,
        timestamp=datetime.utcnow().timestamp(),
        vector_clock={"node-001": 5},
        action_history=["init", "process", "complete"],
        last_action="complete",
        fano_neighbors=["forge", "flow"],
        is_active=True,
        last_heartbeat_at=datetime.utcnow(),
        state_metadata={"version": "2.0.0"},
    )

    db_session.add(state)
    await db_session.commit()
    await db_session.refresh(state)

    assert state.id is not None
    assert state.colony_id == "spark"
    assert state.instance_id == "spark-001"
    assert state.z_dim == 64
    assert len(state.z_state["latent"]) == 64
    assert state.vector_clock["node-001"] == 5
    assert len(state.action_history) == 3
    assert state.is_active is True


@pytest.mark.asyncio
async def test_colony_state_unique_constraint(db_session: AsyncSession):
    """Test colony_id + instance_id unique constraint."""
    state1 = ColonyState(
        id=uuid.uuid4(),
        colony_id="forge",
        instance_id="forge-001",
        node_id="node-001",
        z_state={"latent": [0.0] * 64},
        z_dim=64,
        timestamp=datetime.utcnow().timestamp(),
    )
    db_session.add(state1)
    await db_session.commit()

    # Try to create duplicate colony_id + instance_id
    state2 = ColonyState(
        id=uuid.uuid4(),
        colony_id="forge",
        instance_id="forge-001",
        node_id="node-002",
        z_state={"latent": [0.1] * 64},
        z_dim=64,
        timestamp=datetime.utcnow().timestamp(),
    )
    db_session.add(state2)

    with pytest.raises(Exception):  # IntegrityError
        await db_session.commit()


@pytest.mark.asyncio
async def test_colony_state_vector_clock_merge(db_session: AsyncSession):
    """Test CRDT vector clock operations."""
    # Create initial state
    state = ColonyState(
        id=uuid.uuid4(),
        colony_id="nexus",
        instance_id="nexus-001",
        node_id="node-001",
        z_state={"latent": [0.0] * 64},
        z_dim=64,
        timestamp=datetime.utcnow().timestamp(),
        vector_clock={"node-001": 1, "node-002": 0},
    )
    db_session.add(state)
    await db_session.commit()

    # Update vector clock (CRDT merge)
    await db_session.refresh(state)
    state.vector_clock["node-001"] += 1
    state.vector_clock["node-002"] = max(
        state.vector_clock.get("node-002", 0), 3
    )
    await db_session.commit()

    # Verify merge
    await db_session.refresh(state)
    assert state.vector_clock["node-001"] == 2
    assert state.vector_clock["node-002"] == 3


@pytest.mark.asyncio
async def test_colony_state_action_history_gset(db_session: AsyncSession):
    """Test action history as grow-only set (GSet)."""
    state = ColonyState(
        id=uuid.uuid4(),
        colony_id="crystal",
        instance_id="crystal-001",
        node_id="node-001",
        z_state={"latent": [0.0] * 64},
        z_dim=64,
        timestamp=datetime.utcnow().timestamp(),
        action_history=["init"],
    )
    db_session.add(state)
    await db_session.commit()

    # Add actions (GSet - grow-only)
    await db_session.refresh(state)
    state.action_history.append("test")
    state.action_history.append("verify")
    state.last_action = "verify"
    await db_session.commit()

    # Verify
    await db_session.refresh(state)
    assert len(state.action_history) == 3
    assert "test" in state.action_history
    assert state.last_action == "verify"


# =============================================================================
# TrainingRun Model Tests
# =============================================================================


@pytest.mark.asyncio
async def test_training_run_creation(
    db_session: AsyncSession, sample_user: User
):
    """Test training run model creation."""
    run = TrainingRun(
        id=uuid.uuid4(),
        run_id="run-001",
        name="GPT-2 Pretraining",
        run_type="pretrain",
        user_id=sample_user.id,
        tenant_id="tenant-001",
        config={"lr": 0.001, "batch_size": 64},
        model_architecture="gpt2",
        dataset_name="openwebtext",
        status="pending",
        progress=0.0,
        total_epochs=10,
        total_steps=10000,
    )

    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)

    assert run.id is not None
    assert run.run_id == "run-001"
    assert run.name == "GPT-2 Pretraining"
    assert run.run_type == "pretrain"
    assert run.status == "pending"
    assert run.progress == 0.0
    assert run.created_at is not None


@pytest.mark.asyncio
async def test_training_run_status_transitions(
    db_session: AsyncSession, sample_training_run: TrainingRun
):
    """Test training run status transitions."""
    # pending -> running
    sample_training_run.status = "running"
    sample_training_run.started_at = datetime.utcnow()
    await db_session.commit()

    await db_session.refresh(sample_training_run)
    assert sample_training_run.status == "running"
    assert sample_training_run.started_at is not None

    # running -> completed
    sample_training_run.status = "completed"
    sample_training_run.completed_at = datetime.utcnow()
    sample_training_run.progress = 1.0
    await db_session.commit()

    await db_session.refresh(sample_training_run)
    assert sample_training_run.status == "completed"
    assert sample_training_run.completed_at is not None
    assert sample_training_run.progress == 1.0


@pytest.mark.asyncio
async def test_training_run_metrics_update(
    db_session: AsyncSession, sample_training_run: TrainingRun
):
    """Test training run metrics updates."""
    # Update metrics
    sample_training_run.metrics = {
        "train_loss": [1.5, 1.2, 1.0],
        "val_loss": [1.6, 1.3, 1.1],
    }
    sample_training_run.best_loss = 1.0
    sample_training_run.best_accuracy = 0.85
    sample_training_run.current_step = 300
    sample_training_run.progress = 0.3

    await db_session.commit()
    await db_session.refresh(sample_training_run)

    assert len(sample_training_run.metrics["train_loss"]) == 3
    assert sample_training_run.best_loss == 1.0
    assert sample_training_run.current_step == 300


@pytest.mark.asyncio
async def test_training_run_error_tracking(
    db_session: AsyncSession, sample_training_run: TrainingRun
):
    """Test training run error tracking."""
    sample_training_run.status = "failed"
    sample_training_run.error_message = "CUDA out of memory"
    sample_training_run.error_traceback = "Traceback (most recent call last):\n..."
    sample_training_run.completed_at = datetime.utcnow()

    await db_session.commit()
    await db_session.refresh(sample_training_run)

    assert sample_training_run.status == "failed"
    assert sample_training_run.error_message is not None
    assert "CUDA" in sample_training_run.error_message


# =============================================================================
# TrainingCheckpoint Model Tests
# =============================================================================


@pytest.mark.asyncio
async def test_training_checkpoint_creation(
    db_session: AsyncSession, sample_training_run: TrainingRun
):
    """Test training checkpoint model creation."""
    checkpoint = TrainingCheckpoint(
        id=uuid.uuid4(),
        run_id=sample_training_run.run_id,
        checkpoint_id="ckpt-001",
        epoch=5,
        step=500,
        loss=0.35,
        accuracy=0.92,
        file_path="/data/checkpoints/ckpt-001.pt",
        file_size_bytes=50 * 1024 * 1024,
        storage_backend="s3",
        metrics={"perplexity": 10.5},
        is_best=True,
    )

    db_session.add(checkpoint)
    await db_session.commit()
    await db_session.refresh(checkpoint)

    assert checkpoint.id is not None
    assert checkpoint.run_id == sample_training_run.run_id
    assert checkpoint.epoch == 5
    assert checkpoint.loss == 0.35
    assert checkpoint.is_best is True


@pytest.mark.asyncio
async def test_training_checkpoint_best_tracking(
    db_session: AsyncSession, sample_training_run: TrainingRun
):
    """Test tracking best checkpoint."""
    # Create multiple checkpoints
    checkpoints = []
    for i, loss in enumerate([0.5, 0.3, 0.4, 0.2]):
        ckpt = TrainingCheckpoint(
            id=uuid.uuid4(),
            run_id=sample_training_run.run_id,
            checkpoint_id=f"ckpt-{i:03d}",
            epoch=i,
            step=i * 100,
            loss=loss,
            file_path=f"/tmp/ckpt-{i:03d}.pt",
            is_best=(loss == 0.2),  # Last one is best
        )
        checkpoints.append(ckpt)
        db_session.add(ckpt)

    await db_session.commit()

    # Query best checkpoint
    stmt = select(TrainingCheckpoint).where(
        TrainingCheckpoint.run_id == sample_training_run.run_id,
        TrainingCheckpoint.is_best == True,  # noqa: E712
    )
    result = await db_session.execute(stmt)
    best = result.scalar_one_or_none()

    assert best is not None
    assert best.loss == 0.2
    assert best.checkpoint_id == "ckpt-003"


@pytest.mark.asyncio
async def test_training_checkpoint_cascade_delete(
    db_session: AsyncSession, sample_training_run: TrainingRun
):
    """Test cascade delete of checkpoints when run is deleted."""
    # Create checkpoint
    checkpoint = TrainingCheckpoint(
        id=uuid.uuid4(),
        run_id=sample_training_run.run_id,
        checkpoint_id="ckpt-cascade",
        epoch=1,
        step=100,
        loss=0.5,
        file_path="/tmp/ckpt-cascade.pt",
    )
    db_session.add(checkpoint)
    await db_session.commit()

    # Delete training run
    await db_session.delete(sample_training_run)
    await db_session.commit()

    # Verify checkpoint is deleted (cascade)
    stmt = select(TrainingCheckpoint).where(
        TrainingCheckpoint.checkpoint_id == "ckpt-cascade"
    )
    result = await db_session.execute(stmt)
    deleted_checkpoint = result.scalar_one_or_none()

    assert deleted_checkpoint is None


# =============================================================================
# Receipt and TIC Model Tests
# =============================================================================


@pytest.mark.asyncio
async def test_receipt_creation(db_session: AsyncSession, sample_user: User):
    """Test receipt model creation."""
    receipt = Receipt(
        id=uuid.uuid4(),
        correlation_id="corr-001",
        parent_receipt_id=None,
        phase="PLAN",
        action="generate_code",
        app="forge",
        status="success",
        user_id=sample_user.id,
        tenant_id="test-tenant",
        intent={"goal": "Create REST API"},
        event={"type": "plan_created"},
        data={"code": "def hello(): pass"},
        metrics={"duration_ms": 150},
        duration_ms=150,
    )

    db_session.add(receipt)
    await db_session.commit()
    await db_session.refresh(receipt)

    assert receipt.id is not None
    assert receipt.correlation_id == "corr-001"
    assert receipt.phase == "PLAN"
    assert receipt.action == "generate_code"
    assert receipt.duration_ms == 150


@pytest.mark.asyncio
async def test_receipt_parent_child_relationship(db_session: AsyncSession):
    """Test receipt parent-child relationships."""
    # Create parent receipt
    parent = Receipt(
        id=uuid.uuid4(),
        correlation_id="parent-001",
        parent_receipt_id=None,
        phase="PLAN",
        action="plan_task",
        status="success",
        intent={"goal": "Parent task"},
        duration_ms=100,
    )
    db_session.add(parent)
    await db_session.commit()

    # Create child receipt
    child = Receipt(
        id=uuid.uuid4(),
        correlation_id="child-001",
        parent_receipt_id="parent-001",
        phase="EXECUTE",
        action="execute_step",
        status="success",
        intent={"goal": "Child task"},
        duration_ms=50,
    )
    db_session.add(child)
    await db_session.commit()

    # Query children
    stmt = select(Receipt).where(Receipt.parent_receipt_id == "parent-001")
    result = await db_session.execute(stmt)
    children = list(result.scalars().all())

    assert len(children) == 1
    assert children[0].correlation_id == "child-001"


@pytest.mark.asyncio
async def test_tic_record_creation(db_session: AsyncSession):
    """Test TIC record model creation."""
    tic = TICRecord(
        id=uuid.uuid4(),
        correlation_id="tic-001",
        operation="safe_execute",
        operation_type="code_generation",
        effects=["create_file", "modify_state"],
        preconditions={"file_writable": True, "disk_space": True},
        postconditions={"file_exists": True, "content_valid": True},
        invariants=["h(x) >= 0", "energy > 0"],
        termination_type="bounded_fuel",
        fuel_limit=1000,
        evidence_type="pco",
        evidence_verified=True,
        evidence_content={"proof": "formal_verification"},
        barrier_value=0.8,
    )

    db_session.add(tic)
    await db_session.commit()
    await db_session.refresh(tic)

    assert tic.id is not None
    assert tic.operation == "safe_execute"
    assert len(tic.effects) == 2
    assert tic.preconditions["file_writable"] is True
    assert tic.postconditions["file_exists"] is True
    assert "h(x) >= 0" in tic.invariants
    assert tic.barrier_value == 0.8


# =============================================================================
# Goal and Plan Model Tests
# =============================================================================


@pytest.mark.asyncio
async def test_goal_creation(db_session: AsyncSession):
    """Test goal model creation."""
    goal = Goal(
        id=uuid.uuid4(),
        goal_id="goal-001",
        description="Implement user authentication",
        success_criteria={"tests_pass": True, "coverage": ">80%"},
        priority=8,
        deadline=datetime.utcnow() + timedelta(days=7),
        status="active",
        completion_percentage=0.0,
        estimated_steps=5,
        completed_steps=0,
    )

    db_session.add(goal)
    await db_session.commit()
    await db_session.refresh(goal)

    assert goal.id is not None
    assert goal.goal_id == "goal-001"
    assert goal.priority == 8
    assert goal.status == "active"


@pytest.mark.asyncio
async def test_plan_with_tasks_relationship(
    db_session: AsyncSession, sample_user: User
):
    """Test plan and task relationships."""
    # Create plan
    plan = Plan(
        id=uuid.uuid4(),
        plan_id="plan-001",
        user_id=sample_user.id,
        name="API Development Plan",
        description="Build REST API",
        type="project",
        status="active",
        progress=0,
    )
    db_session.add(plan)
    await db_session.commit()

    # Create tasks
    task1 = PlanTask(
        id=uuid.uuid4(),
        task_id="task-001",
        plan_id=plan.plan_id,
        title="Setup project",
        status="completed",
        priority="high",
    )
    task2 = PlanTask(
        id=uuid.uuid4(),
        task_id="task-002",
        plan_id=plan.plan_id,
        title="Implement endpoints",
        status="in_progress",
        priority="high",
    )
    db_session.add_all([task1, task2])
    await db_session.commit()

    # Refresh and check relationship
    await db_session.refresh(plan)
    assert len(plan.tasks) == 2
    assert plan.tasks[0].title in ["Setup project", "Implement endpoints"]


# =============================================================================
# Additional Model Tests
# =============================================================================


@pytest.mark.asyncio
async def test_idempotency_key(db_session: AsyncSession, sample_user: User):
    """Test idempotency key model."""
    key = IdempotencyKey(
        id=uuid.uuid4(),
        key="idem-key-001",
        path="/api/v1/payments",
        user_id=sample_user.id,
        tenant_id="test-tenant",
        status_code=200,
        response_hash="abc123",
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )

    db_session.add(key)
    await db_session.commit()
    await db_session.refresh(key)

    assert key.id is not None
    assert key.key == "idem-key-001"
    assert key.status_code == 200


@pytest.mark.asyncio
async def test_verification_token(db_session: AsyncSession, sample_user: User):
    """Test verification token model."""
    token = VerificationToken(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        token="verify-token-123",
        token_type="email_verification",
        expires_at=datetime.utcnow() + timedelta(days=1),
    )

    db_session.add(token)
    await db_session.commit()
    await db_session.refresh(token)

    assert token.id is not None
    assert token.token_type == "email_verification"
    assert token.consumed_at is None

    # Mark as consumed
    token.consumed_at = datetime.utcnow()
    await db_session.commit()

    await db_session.refresh(token)
    assert token.consumed_at is not None
