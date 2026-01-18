"""Test fixtures for database layer tests.

Created: December 28, 2025
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from kagami.core.database.base import Base
from kagami.core.database.models import (
    ColonyState,
    TrainingCheckpoint,
    TrainingRun,
    User,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine():
    """Create in-memory SQLite database engine for testing."""
    # Use SQLite in-memory for fast tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for testing."""
    async_session = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def sample_user(db_session: AsyncSession) -> User:
    """Create a sample user for testing."""
    user = User(
        id=uuid.uuid4(),
        username="testuser",
        email="test@example.com",
        hashed_password="$2b$12$dummy_hash",
        roles=["user"],
        is_active=True,
        is_verified=True,
        tenant_id="test-tenant",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def sample_colony_state(db_session: AsyncSession) -> ColonyState:
    """Create a sample colony state for testing."""
    state = ColonyState(
        id=uuid.uuid4(),
        colony_id="spark",
        instance_id="spark-001",
        node_id="node-001",
        z_state={"latent": [0.0] * 64},
        z_dim=64,
        timestamp=datetime.utcnow().timestamp(),
        vector_clock={"node-001": 1},
        action_history=["init"],
        last_action="init",
        fano_neighbors=["forge", "flow"],
        is_active=True,
        last_heartbeat_at=datetime.utcnow(),
        state_metadata={"version": "1.0.0"},
    )
    db_session.add(state)
    await db_session.commit()
    await db_session.refresh(state)
    return state


@pytest_asyncio.fixture
async def sample_training_run(db_session: AsyncSession, sample_user: User) -> TrainingRun:
    """Create a sample training run for testing."""
    run = TrainingRun(
        id=uuid.uuid4(),
        run_id="test-run-001",
        name="Test Training Run",
        run_type="pretrain",
        user_id=sample_user.id,
        tenant_id="test-tenant",
        config={"learning_rate": 0.001, "batch_size": 32},
        model_architecture="transformer",
        dataset_name="test-dataset",
        status="pending",
        progress=0.0,
        metrics={},
        current_epoch=0,
        total_epochs=10,
        current_step=0,
        total_steps=1000,
        gpu_hours=0.0,
        total_tokens_processed=0,
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    return run


@pytest_asyncio.fixture
async def sample_training_checkpoint(
    db_session: AsyncSession, sample_training_run: TrainingRun
) -> TrainingCheckpoint:
    """Create a sample training checkpoint for testing."""
    checkpoint = TrainingCheckpoint(
        id=uuid.uuid4(),
        run_id=sample_training_run.run_id,
        checkpoint_id="checkpoint-001",
        epoch=1,
        step=100,
        loss=0.5,
        accuracy=0.8,
        file_path="/tmp/checkpoints/checkpoint-001.pt",
        file_size_bytes=1024 * 1024,
        storage_backend="local",
        metrics={"val_loss": 0.45, "val_accuracy": 0.85},
        is_best=True,
    )
    db_session.add(checkpoint)
    await db_session.commit()
    await db_session.refresh(checkpoint)
    return checkpoint


@pytest.fixture
def mock_redis_client():
    """Create mock Redis client for testing."""
    from unittest.mock import AsyncMock, MagicMock

    mock = MagicMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=True)
    mock.exists = AsyncMock(return_value=False)
    return mock


@pytest.fixture
def mock_etcd_client():
    """Create mock etcd client for testing."""
    from unittest.mock import AsyncMock, MagicMock

    mock = MagicMock()
    mock.put = AsyncMock(return_value=True)
    mock.get = AsyncMock(return_value=None)
    mock.delete = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def sample_colony_state_data() -> dict:
    """Sample colony state data for testing."""
    return {
        "colony_id": "forge",
        "instance_id": "forge-001",
        "node_id": "node-forge-001",
        "z_state": {"latent": [0.1] * 64},
        "z_dim": 64,
        "timestamp": datetime.utcnow().timestamp(),
        "vector_clock": {"node-forge-001": 1},
        "action_history": ["create_artifact"],
        "last_action": "create_artifact",
        "fano_neighbors": ["spark", "nexus"],
        "is_active": True,
        "last_heartbeat_at": datetime.utcnow(),
        "state_metadata": {"version": "1.0.0", "environment": "test"},
    }


@pytest.fixture
def sample_training_run_data(sample_user: User) -> dict:
    """Sample training run data for testing."""
    return {
        "run_id": "test-run-002",
        "name": "Test Fine-tune Run",
        "run_type": "finetune",
        "user_id": sample_user.id,
        "tenant_id": "test-tenant",
        "config": {
            "learning_rate": 0.0001,
            "batch_size": 16,
            "warmup_steps": 100,
        },
        "model_architecture": "gpt2",
        "dataset_name": "custom-dataset",
        "status": "pending",
        "progress": 0.0,
        "metrics": {},
        "total_epochs": 5,
        "total_steps": 500,
    }
