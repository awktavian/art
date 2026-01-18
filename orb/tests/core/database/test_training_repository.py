"""Comprehensive tests for TrainingRunRepository and TrainingCheckpointRepository.

Tests training run lifecycle, status transitions, metrics updates, checkpoint
tracking, best checkpoint selection, and read-through caching.

Created: December 28, 2025
"""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kagami.core.database.models import TrainingCheckpoint, TrainingRun, User
from kagami.core.storage.training_repository import (
    TrainingCheckpointRepository,
    TrainingRunRepository,
)

pytestmark = pytest.mark.tier_integration


# =============================================================================
# TrainingRunRepository - Initialization Tests
# =============================================================================


@pytest.mark.asyncio
async def test_training_run_repository_initialization(db_session: AsyncSession):
    """Test training run repository initialization."""
    repo = TrainingRunRepository(db_session=db_session)

    assert repo.db_session is db_session
    assert repo._cache_strategy.value == "read"  # READ_THROUGH


@pytest.mark.asyncio
async def test_training_run_repository_with_redis(
    db_session: AsyncSession, mock_redis_client
):
    """Test repository initialization with Redis."""
    repo = TrainingRunRepository(
        db_session=db_session, redis_client=mock_redis_client
    )

    assert repo._redis_client is mock_redis_client


# =============================================================================
# TrainingRunRepository - CRUD Operations Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_by_id_uuid(
    db_session: AsyncSession, sample_training_run: TrainingRun
):
    """Test get training run by UUID."""
    repo = TrainingRunRepository(db_session=db_session)

    run = await repo.get_by_id(sample_training_run.id)
    assert run is not None
    assert run.id == sample_training_run.id
    assert run.run_id == "test-run-001"


@pytest.mark.asyncio
async def test_get_by_id_run_id_string(
    db_session: AsyncSession, sample_training_run: TrainingRun
):
    """Test get training run by run_id string."""
    repo = TrainingRunRepository(db_session=db_session)

    # Get by run_id string
    run = await repo.get_by_id("test-run-001")
    assert run is not None
    assert run.run_id == "test-run-001"


@pytest.mark.asyncio
async def test_get_by_id_not_found(db_session: AsyncSession):
    """Test get by ID returns None for non-existent run."""
    repo = TrainingRunRepository(db_session=db_session)

    run = await repo.get_by_id(uuid.uuid4())
    assert run is None


@pytest.mark.asyncio
async def test_get_by_run_id(
    db_session: AsyncSession, sample_training_run: TrainingRun
):
    """Test get training run by run_id string."""
    repo = TrainingRunRepository(db_session=db_session)

    run = await repo.get_by_run_id("test-run-001")
    assert run is not None
    assert run.run_id == "test-run-001"


@pytest.mark.asyncio
async def test_create_run(db_session: AsyncSession, sample_user: User):
    """Test create new training run."""
    repo = TrainingRunRepository(db_session=db_session)

    run = TrainingRun(
        id=uuid.uuid4(),
        run_id="new-run-001",
        name="New Training Run",
        run_type="finetune",
        user_id=sample_user.id,
        tenant_id="test-tenant",
        config={"lr": 0.0001},
        status="pending",
        progress=0.0,
        total_steps=500,
    )

    created_run = await repo.create_run(run)
    assert created_run.id is not None
    assert created_run.run_id == "new-run-001"

    # Verify in database
    stmt = select(TrainingRun).where(TrainingRun.run_id == "new-run-001")
    result = await db_session.execute(stmt)
    db_run = result.scalar_one_or_none()
    assert db_run is not None


@pytest.mark.asyncio
async def test_update_run(
    db_session: AsyncSession, sample_training_run: TrainingRun
):
    """Test update training run."""
    repo = TrainingRunRepository(db_session=db_session)

    # Update fields
    sample_training_run.status = "running"
    sample_training_run.current_step = 100
    sample_training_run.progress = 0.1

    updated_run = await repo.update_run(sample_training_run)
    assert updated_run.status == "running"
    assert updated_run.current_step == 100

    # Verify in database
    run = await repo.get_by_run_id("test-run-001")
    assert run.status == "running"
    assert run.current_step == 100


# =============================================================================
# TrainingRunRepository - List and Filter Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_runs_no_filters(db_session: AsyncSession, sample_user: User):
    """Test list training runs without filters."""
    # Create multiple runs
    for i in range(3):
        run = TrainingRun(
            id=uuid.uuid4(),
            run_id=f"run-{i}",
            name=f"Run {i}",
            run_type="pretrain",
            user_id=sample_user.id,
            config={},
            status="pending",
            progress=0.0,
        )
        db_session.add(run)
    await db_session.commit()

    repo = TrainingRunRepository(db_session=db_session)

    runs = await repo.list_runs()
    assert len(runs) >= 3


@pytest.mark.asyncio
async def test_list_runs_filter_by_user(
    db_session: AsyncSession, sample_user: User
):
    """Test list runs filtered by user."""
    # Create runs for different users
    other_user = User(
        id=uuid.uuid4(),
        username="other",
        email="other@test.com",
        hashed_password="hash",
    )
    db_session.add(other_user)
    await db_session.commit()

    for i in range(2):
        run = TrainingRun(
            id=uuid.uuid4(),
            run_id=f"user-run-{i}",
            name=f"User Run {i}",
            run_type="pretrain",
            user_id=sample_user.id,
            config={},
            status="pending",
        )
        db_session.add(run)

    run = TrainingRun(
        id=uuid.uuid4(),
        run_id="other-run",
        name="Other Run",
        run_type="pretrain",
        user_id=other_user.id,
        config={},
        status="pending",
    )
    db_session.add(run)
    await db_session.commit()

    repo = TrainingRunRepository(db_session=db_session)

    user_runs = await repo.list_runs(user_id=sample_user.id)
    assert len(user_runs) >= 2
    assert all(r.user_id == sample_user.id for r in user_runs)


@pytest.mark.asyncio
async def test_list_runs_filter_by_status(
    db_session: AsyncSession, sample_user: User
):
    """Test list runs filtered by status."""
    # Create runs with different statuses
    for i, status in enumerate(["pending", "running", "completed"]):
        run = TrainingRun(
            id=uuid.uuid4(),
            run_id=f"status-run-{i}",
            name=f"Run {status}",
            run_type="pretrain",
            user_id=sample_user.id,
            config={},
            status=status,
        )
        db_session.add(run)
    await db_session.commit()

    repo = TrainingRunRepository(db_session=db_session)

    running_runs = await repo.list_runs(status="running")
    assert all(r.status == "running" for r in running_runs)


@pytest.mark.asyncio
async def test_list_runs_filter_by_type(
    db_session: AsyncSession, sample_user: User
):
    """Test list runs filtered by run type."""
    # Create runs with different types
    for i, run_type in enumerate(["pretrain", "finetune", "rl"]):
        run = TrainingRun(
            id=uuid.uuid4(),
            run_id=f"type-run-{i}",
            name=f"Run {run_type}",
            run_type=run_type,
            user_id=sample_user.id,
            config={},
            status="pending",
        )
        db_session.add(run)
    await db_session.commit()

    repo = TrainingRunRepository(db_session=db_session)

    finetune_runs = await repo.list_runs(run_type="finetune")
    assert all(r.run_type == "finetune" for r in finetune_runs)


@pytest.mark.asyncio
async def test_list_runs_with_limit(db_session: AsyncSession, sample_user: User):
    """Test list runs with limit."""
    # Create many runs
    for i in range(10):
        run = TrainingRun(
            id=uuid.uuid4(),
            run_id=f"limit-run-{i}",
            name=f"Run {i}",
            run_type="pretrain",
            user_id=sample_user.id,
            config={},
            status="pending",
        )
        db_session.add(run)
    await db_session.commit()

    repo = TrainingRunRepository(db_session=db_session)

    runs = await repo.list_runs(user_id=sample_user.id, limit=5)
    assert len(runs) <= 5


@pytest.mark.asyncio
async def test_get_active_runs(db_session: AsyncSession, sample_user: User):
    """Test get currently running training runs."""
    # Create runs with different statuses
    for i, status in enumerate(["pending", "running", "running", "completed"]):
        run = TrainingRun(
            id=uuid.uuid4(),
            run_id=f"active-run-{i}",
            name=f"Run {i}",
            run_type="pretrain",
            user_id=sample_user.id,
            config={},
            status=status,
            started_at=datetime.utcnow() if status == "running" else None,
        )
        db_session.add(run)
    await db_session.commit()

    repo = TrainingRunRepository(db_session=db_session)

    active_runs = await repo.get_active_runs()
    assert len(active_runs) == 2
    assert all(r.status == "running" for r in active_runs)


# =============================================================================
# TrainingRunRepository - Progress and Status Tests
# =============================================================================


@pytest.mark.asyncio
async def test_update_progress(
    db_session: AsyncSession, sample_training_run: TrainingRun
):
    """Test update training progress."""
    repo = TrainingRunRepository(db_session=db_session)

    # Update progress
    result = await repo.update_progress(
        run_id="test-run-001",
        current_step=500,
        current_epoch=5,
        metrics={"loss": 0.5, "accuracy": 0.85},
    )
    assert result is True

    # Verify updates
    run = await repo.get_by_run_id("test-run-001")
    assert run.current_step == 500
    assert run.current_epoch == 5
    assert run.metrics["loss"] == 0.5
    assert run.progress == 0.5  # 500/1000 steps


@pytest.mark.asyncio
async def test_update_progress_not_found(db_session: AsyncSession):
    """Test update progress returns False when run not found."""
    repo = TrainingRunRepository(db_session=db_session)

    result = await repo.update_progress(
        run_id="nonexistent-run", current_step=100
    )
    assert result is False


@pytest.mark.asyncio
async def test_update_progress_calculates_percentage(
    db_session: AsyncSession, sample_training_run: TrainingRun
):
    """Test progress percentage calculation."""
    repo = TrainingRunRepository(db_session=db_session)

    # Update to 75% completion
    await repo.update_progress(run_id="test-run-001", current_step=750)

    run = await repo.get_by_run_id("test-run-001")
    assert run.progress == 0.75


@pytest.mark.asyncio
async def test_mark_completed(
    db_session: AsyncSession, sample_training_run: TrainingRun
):
    """Test mark training run as completed."""
    repo = TrainingRunRepository(db_session=db_session)

    result = await repo.mark_completed(
        run_id="test-run-001",
        final_metrics={"loss": 0.25, "accuracy": 0.95},
    )
    assert result is True

    # Verify completed
    run = await repo.get_by_run_id("test-run-001")
    assert run.status == "completed"
    assert run.progress == 1.0
    assert run.completed_at is not None
    assert run.final_loss == 0.25
    assert run.best_accuracy == 0.95


@pytest.mark.asyncio
async def test_mark_completed_not_found(db_session: AsyncSession):
    """Test mark completed returns False when run not found."""
    repo = TrainingRunRepository(db_session=db_session)

    result = await repo.mark_completed(run_id="nonexistent-run")
    assert result is False


@pytest.mark.asyncio
async def test_mark_failed(
    db_session: AsyncSession, sample_training_run: TrainingRun
):
    """Test mark training run as failed."""
    repo = TrainingRunRepository(db_session=db_session)

    result = await repo.mark_failed(
        run_id="test-run-001",
        error_message="Out of memory",
        error_traceback="Traceback...",
    )
    assert result is True

    # Verify failed
    run = await repo.get_by_run_id("test-run-001")
    assert run.status == "failed"
    assert run.error_message == "Out of memory"
    assert run.error_traceback == "Traceback..."
    assert run.completed_at is not None


@pytest.mark.asyncio
async def test_mark_failed_not_found(db_session: AsyncSession):
    """Test mark failed returns False when run not found."""
    repo = TrainingRunRepository(db_session=db_session)

    result = await repo.mark_failed(
        run_id="nonexistent-run", error_message="Error"
    )
    assert result is False


# =============================================================================
# TrainingRunRepository - Caching Tests
# =============================================================================


@pytest.mark.asyncio
async def test_read_through_cache(
    db_session: AsyncSession, sample_training_run: TrainingRun
):
    """Test read-through cache strategy."""
    repo = TrainingRunRepository(db_session=db_session)

    # First read - cache miss, load from DB
    run1 = await repo.get_by_id(sample_training_run.id)
    assert run1 is not None

    # Second read - cache hit (L1)
    run2 = await repo.get_by_id(sample_training_run.id)
    assert run2 is not None
    assert run2.id == run1.id


# =============================================================================
# TrainingCheckpointRepository - Initialization Tests
# =============================================================================


@pytest.mark.asyncio
async def test_checkpoint_repository_initialization(db_session: AsyncSession):
    """Test checkpoint repository initialization."""
    repo = TrainingCheckpointRepository(db_session=db_session)

    assert repo.db_session is db_session
    assert repo._cache_strategy.value == "read"  # READ_THROUGH


# =============================================================================
# TrainingCheckpointRepository - CRUD Operations Tests
# =============================================================================


@pytest.mark.asyncio
async def test_create_checkpoint(
    db_session: AsyncSession, sample_training_run: TrainingRun
):
    """Test create new checkpoint."""
    repo = TrainingCheckpointRepository(db_session=db_session)

    checkpoint = TrainingCheckpoint(
        id=uuid.uuid4(),
        run_id=sample_training_run.run_id,
        checkpoint_id="ckpt-new",
        epoch=3,
        step=300,
        loss=0.4,
        accuracy=0.88,
        file_path="/tmp/ckpt-new.pt",
        metrics={"val_loss": 0.35},
    )

    created = await repo.create_checkpoint(checkpoint)
    assert created.id is not None
    assert created.checkpoint_id == "ckpt-new"


@pytest.mark.asyncio
async def test_get_checkpoints_for_run(
    db_session: AsyncSession, sample_training_run: TrainingRun
):
    """Test get checkpoints for a training run."""
    # Create multiple checkpoints
    for i in range(5):
        checkpoint = TrainingCheckpoint(
            id=uuid.uuid4(),
            run_id=sample_training_run.run_id,
            checkpoint_id=f"ckpt-{i}",
            epoch=i,
            step=i * 100,
            loss=0.5 - i * 0.05,
            file_path=f"/tmp/ckpt-{i}.pt",
        )
        db_session.add(checkpoint)
    await db_session.commit()

    repo = TrainingCheckpointRepository(db_session=db_session)

    checkpoints = await repo.get_checkpoints_for_run("test-run-001")
    assert len(checkpoints) == 6  # 5 new + 1 from fixture
    # Should be ordered by step desc
    assert checkpoints[0].step >= checkpoints[1].step


@pytest.mark.asyncio
async def test_get_checkpoints_with_limit(
    db_session: AsyncSession, sample_training_run: TrainingRun
):
    """Test get checkpoints with limit."""
    # Create many checkpoints
    for i in range(10):
        checkpoint = TrainingCheckpoint(
            id=uuid.uuid4(),
            run_id=sample_training_run.run_id,
            checkpoint_id=f"ckpt-limit-{i}",
            epoch=i,
            step=i * 100,
            loss=0.5,
            file_path=f"/tmp/ckpt-{i}.pt",
        )
        db_session.add(checkpoint)
    await db_session.commit()

    repo = TrainingCheckpointRepository(db_session=db_session)

    checkpoints = await repo.get_checkpoints_for_run("test-run-001", limit=5)
    assert len(checkpoints) <= 5


@pytest.mark.asyncio
async def test_get_best_checkpoint(
    db_session: AsyncSession, sample_training_run: TrainingRun
):
    """Test get best checkpoint for a training run."""
    # Create checkpoints with different quality
    for i, is_best in enumerate([False, False, True, False]):
        checkpoint = TrainingCheckpoint(
            id=uuid.uuid4(),
            run_id=sample_training_run.run_id,
            checkpoint_id=f"ckpt-best-{i}",
            epoch=i,
            step=i * 100,
            loss=0.5 - i * 0.1,
            file_path=f"/tmp/ckpt-{i}.pt",
            is_best=is_best,
        )
        db_session.add(checkpoint)
    await db_session.commit()

    repo = TrainingCheckpointRepository(db_session=db_session)

    best = await repo.get_best_checkpoint("test-run-001")
    assert best is not None
    assert best.checkpoint_id == "ckpt-best-2"
    assert best.is_best is True


@pytest.mark.asyncio
async def test_get_best_checkpoint_not_found(db_session: AsyncSession):
    """Test get best checkpoint returns None when not found."""
    repo = TrainingCheckpointRepository(db_session=db_session)

    best = await repo.get_best_checkpoint("nonexistent-run")
    assert best is None


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.asyncio
async def test_training_run_fetch_error_handling(db_session: AsyncSession):
    """Test error handling in training run fetch."""
    repo = TrainingRunRepository(db_session=db_session)

    with patch.object(
        repo, "_fetch_from_storage", side_effect=Exception("DB error")
    ):
        result = await repo.get_by_id(uuid.uuid4())
        assert result is None


@pytest.mark.asyncio
async def test_training_run_write_rollback_on_error(db_session: AsyncSession):
    """Test transaction rollback on write error."""
    repo = TrainingRunRepository(db_session=db_session)

    run = TrainingRun(
        id=uuid.uuid4(),
        run_id="error-run",
        name="Error Run",
        run_type="pretrain",
        config={},
        status="pending",
    )

    with patch.object(db_session, "commit", side_effect=Exception("Commit failed")):
        with pytest.raises(Exception):
            await repo.create_run(run)


# =============================================================================
# Performance Tests
# =============================================================================


@pytest.mark.asyncio
async def test_bulk_checkpoint_query_performance(
    db_session: AsyncSession, sample_user: User
):
    """Test performance of bulk checkpoint queries."""
    import time

    # Create run with many checkpoints
    run = TrainingRun(
        id=uuid.uuid4(),
        run_id="perf-run",
        name="Performance Test",
        run_type="pretrain",
        user_id=sample_user.id,
        config={},
        status="running",
    )
    db_session.add(run)
    await db_session.commit()

    # Create 100 checkpoints
    for i in range(100):
        checkpoint = TrainingCheckpoint(
            id=uuid.uuid4(),
            run_id="perf-run",
            checkpoint_id=f"perf-ckpt-{i}",
            epoch=i,
            step=i * 10,
            loss=0.5,
            file_path=f"/tmp/ckpt-{i}.pt",
        )
        db_session.add(checkpoint)
    await db_session.commit()

    repo = TrainingCheckpointRepository(db_session=db_session)

    # Time query
    start = time.time()
    checkpoints = await repo.get_checkpoints_for_run("perf-run")
    elapsed = time.time() - start

    assert len(checkpoints) == 100
    # Should complete quickly (< 1 second)
    assert elapsed < 1.0
