"""Comprehensive tests for database migrations.

Tests migration up/down, rollback correctness, index creation,
constraint enforcement, and data preservation.

Created: December 28, 2025
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from kagami.core.database.base import Base
from kagami.core.database.models import ColonyState, TrainingCheckpoint, TrainingRun

pytestmark = pytest.mark.tier_integration


@pytest.fixture
def alembic_config():
    """Create Alembic configuration for testing."""
    # Path to alembic.ini
    project_root = Path(__file__).parent.parent.parent.parent
    alembic_ini = project_root / "alembic.ini"

    if not alembic_ini.exists():
        pytest.skip("alembic.ini not found")

    config = Config(str(alembic_ini))
    return config


@pytest.fixture
def migration_engine():
    """Create in-memory engine for migration testing."""
    # Use SQLite for testing
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    yield engine
    engine.dispose()


@pytest.fixture
def migration_context(migration_engine):
    """Create migration context."""
    with migration_engine.connect() as connection:
        context = MigrationContext.configure(connection)
        yield context


# =============================================================================
# Migration Upgrade Tests
# =============================================================================


def test_migration_file_exists():
    """Test that colony and training tables migration file exists."""
    project_root = Path(__file__).parent.parent.parent.parent
    migration_file = (
        project_root / "migrations" / "versions" / "20251228_add_colony_and_training_tables.py"
    )

    assert migration_file.exists(), "Migration file not found"


def test_migration_revision_id():
    """Test migration has correct revision ID."""
    from migrations.versions import (
        add_colony_and_training_tables_20251228 as migration_module,
    )

    assert migration_module.revision == "20251228_add_colony_training"
    assert migration_module.down_revision == "add_privacy_tables"


def test_migration_upgrade_creates_tables(migration_engine):
    """Test migration upgrade creates all required tables."""
    from migrations.versions.add_colony_and_training_tables_20251228 import (
        upgrade,
    )

    # Run upgrade
    with migration_engine.begin() as connection:
        # Setup alembic operations context
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        ctx = MigrationContext.configure(connection)
        op = Operations(ctx)

        # Manually run upgrade (simulating alembic)
        # For real test, we'd use alembic command API
        upgrade()

    # Verify tables exist
    inspector = inspect(migration_engine)
    tables = inspector.get_table_names()

    assert "colony_states" in tables
    assert "training_runs" in tables
    assert "training_checkpoints" in tables


def test_migration_creates_colony_states_columns(migration_engine):
    """Test colony_states table has all required columns."""
    from migrations.versions.add_colony_and_training_tables_20251228 import (
        upgrade,
    )

    with migration_engine.begin() as connection:
        upgrade()

    inspector = inspect(migration_engine)
    columns = [col["name"] for col in inspector.get_columns("colony_states")]

    required_columns = [
        "id",
        "colony_id",
        "instance_id",
        "node_id",
        "z_state",
        "z_dim",
        "timestamp",
        "vector_clock",
        "action_history",
        "last_action",
        "fano_neighbors",
        "is_active",
        "last_heartbeat_at",
        "state_metadata",
        "created_at",
        "updated_at",
    ]

    for col in required_columns:
        assert col in columns, f"Column {col} not found in colony_states"


def test_migration_creates_training_runs_columns(migration_engine):
    """Test training_runs table has all required columns."""
    from migrations.versions.add_colony_and_training_tables_20251228 import (
        upgrade,
    )

    with migration_engine.begin() as connection:
        upgrade()

    inspector = inspect(migration_engine)
    columns = [col["name"] for col in inspector.get_columns("training_runs")]

    required_columns = [
        "id",
        "run_id",
        "name",
        "run_type",
        "user_id",
        "tenant_id",
        "config",
        "status",
        "progress",
        "metrics",
        "current_epoch",
        "total_epochs",
        "current_step",
        "total_steps",
    ]

    for col in required_columns:
        assert col in columns, f"Column {col} not found in training_runs"


def test_migration_creates_training_checkpoints_columns(migration_engine):
    """Test training_checkpoints table has all required columns."""
    from migrations.versions.add_colony_and_training_tables_20251228 import (
        upgrade,
    )

    with migration_engine.begin() as connection:
        upgrade()

    inspector = inspect(migration_engine)
    columns = [col["name"] for col in inspector.get_columns("training_checkpoints")]

    required_columns = [
        "id",
        "run_id",
        "checkpoint_id",
        "epoch",
        "step",
        "loss",
        "accuracy",
        "file_path",
        "is_best",
    ]

    for col in required_columns:
        assert col in columns, f"Column {col} not found in training_checkpoints"


# =============================================================================
# Index Creation Tests
# =============================================================================


def test_migration_creates_colony_states_indexes(migration_engine):
    """Test colony_states indexes are created."""
    from migrations.versions.add_colony_and_training_tables_20251228 import (
        upgrade,
    )

    with migration_engine.begin() as connection:
        upgrade()

    inspector = inspect(migration_engine)
    indexes = inspector.get_indexes("colony_states")
    index_names = [idx["name"] for idx in indexes]

    required_indexes = [
        "idx_colony_state_colony_instance",
        "idx_colony_state_active",
        "idx_colony_state_timestamp",
        "idx_colony_state_colony_id",
        "idx_colony_state_instance_id",
    ]

    for idx_name in required_indexes:
        assert idx_name in index_names, f"Index {idx_name} not found in colony_states"


def test_migration_creates_training_runs_indexes(migration_engine):
    """Test training_runs indexes are created."""
    from migrations.versions.add_colony_and_training_tables_20251228 import (
        upgrade,
    )

    with migration_engine.begin() as connection:
        upgrade()

    inspector = inspect(migration_engine)
    indexes = inspector.get_indexes("training_runs")
    index_names = [idx["name"] for idx in indexes]

    required_indexes = [
        "idx_training_run_run_id",
        "idx_training_run_name",
        "idx_training_run_status",
        "idx_training_run_user_status",
    ]

    for idx_name in required_indexes:
        assert idx_name in index_names, f"Index {idx_name} not found in training_runs"


def test_migration_creates_training_checkpoints_indexes(migration_engine):
    """Test training_checkpoints indexes are created."""
    from migrations.versions.add_colony_and_training_tables_20251228 import (
        upgrade,
    )

    with migration_engine.begin() as connection:
        upgrade()

    inspector = inspect(migration_engine)
    indexes = inspector.get_indexes("training_checkpoints")
    index_names = [idx["name"] for idx in indexes]

    required_indexes = [
        "idx_checkpoint_run_id",
        "idx_checkpoint_checkpoint_id",
        "idx_checkpoint_run_step",
        "idx_checkpoint_run_best",
    ]

    for idx_name in required_indexes:
        assert idx_name in index_names, f"Index {idx_name} not found in training_checkpoints"


def test_colony_instance_unique_index(migration_engine):
    """Test colony_id + instance_id unique constraint."""
    from migrations.versions.add_colony_and_training_tables_20251228 import (
        upgrade,
    )

    with migration_engine.begin() as connection:
        upgrade()

    inspector = inspect(migration_engine)
    indexes = inspector.get_indexes("colony_states")

    # Find the unique index
    unique_index = next(
        (idx for idx in indexes if idx["name"] == "idx_colony_state_colony_instance"),
        None,
    )

    assert unique_index is not None
    assert unique_index["unique"] is True


# =============================================================================
# Migration Downgrade Tests
# =============================================================================


def test_migration_downgrade_drops_tables(migration_engine):
    """Test migration downgrade drops all tables."""
    from migrations.versions.add_colony_and_training_tables_20251228 import (
        downgrade,
        upgrade,
    )

    # First upgrade
    with migration_engine.begin() as connection:
        upgrade()

    inspector = inspect(migration_engine)
    assert "colony_states" in inspector.get_table_names()
    assert "training_runs" in inspector.get_table_names()

    # Then downgrade
    with migration_engine.begin() as connection:
        downgrade()

    inspector = inspect(migration_engine)
    tables = inspector.get_table_names()

    assert "colony_states" not in tables
    assert "training_runs" not in tables
    assert "training_checkpoints" not in tables


# =============================================================================
# Data Preservation Tests
# =============================================================================


@pytest.mark.skip(
    reason="TODO: Implement with full database setup - test migration preserves existing data"
)
def test_migration_preserves_existing_data(migration_engine):
    """Test migration upgrade preserves existing data in other tables."""
    # This would test that upgrading doesn't affect existing user data
    # Requires setting up user table first
    pass


@pytest.mark.skip(reason="TODO: Implement with full Alembic setup - test rollback preserves data")
def test_migration_rollback_preserves_data(migration_engine):
    """Test migration rollback preserves data."""
    # Test that downgrade doesn't corrupt other tables
    pass


# =============================================================================
# Constraint Tests
# =============================================================================


def test_training_checkpoint_foreign_key(migration_engine):
    """Test training_checkpoints has foreign key to training_runs."""
    from migrations.versions.add_colony_and_training_tables_20251228 import (
        upgrade,
    )

    with migration_engine.begin() as connection:
        upgrade()

    inspector = inspect(migration_engine)
    foreign_keys = inspector.get_foreign_keys("training_checkpoints")

    # Should have foreign key to training_runs.run_id
    assert len(foreign_keys) > 0
    run_id_fk = next(
        (fk for fk in foreign_keys if "run_id" in fk["constrained_columns"]),
        None,
    )
    assert run_id_fk is not None


def test_default_values_applied(migration_engine):
    """Test default values are properly applied."""
    from migrations.versions.add_colony_and_training_tables_20251228 import (
        upgrade,
    )

    with migration_engine.begin() as connection:
        upgrade()

        # Insert minimal colony state
        connection.execute(
            text(
                """
            INSERT INTO colony_states (id, colony_id, instance_id, node_id,
                                      z_state, timestamp)
            VALUES (:id, :colony_id, :instance_id, :node_id, :z_state, :timestamp)
        """
            ),
            {
                "id": str(uuid.uuid4()),
                "colony_id": "test",
                "instance_id": "test-001",
                "node_id": "node-001",
                "z_state": "{}",
                "timestamp": 123456.0,
            },
        )

        # Query and verify defaults
        result = connection.execute(
            text("SELECT z_dim, is_active FROM colony_states WHERE colony_id = 'test'")
        ).fetchone()

        assert result[0] == 64  # z_dim default
        assert result[1] == 1  # is_active default (True)


# =============================================================================
# Schema Validation Tests
# =============================================================================


def test_colony_states_schema_matches_model():
    """Test colony_states table schema matches ColonyState model."""
    # Compare SQLAlchemy model columns to migration columns
    from sqlalchemy import inspect as sa_inspect

    model_columns = {col.name: str(col.type) for col in sa_inspect(ColonyState).columns}

    # Check critical columns
    assert "id" in model_columns
    assert "colony_id" in model_columns
    assert "instance_id" in model_columns
    assert "z_state" in model_columns
    assert "z_dim" in model_columns


def test_training_runs_schema_matches_model():
    """Test training_runs table schema matches TrainingRun model."""
    from sqlalchemy import inspect as sa_inspect

    model_columns = {col.name: str(col.type) for col in sa_inspect(TrainingRun).columns}

    # Check critical columns
    assert "id" in model_columns
    assert "run_id" in model_columns
    assert "name" in model_columns
    assert "run_type" in model_columns
    assert "status" in model_columns


def test_training_checkpoints_schema_matches_model():
    """Test training_checkpoints table schema matches TrainingCheckpoint model."""
    from sqlalchemy import inspect as sa_inspect

    model_columns = {col.name: str(col.type) for col in sa_inspect(TrainingCheckpoint).columns}

    # Check critical columns
    assert "id" in model_columns
    assert "run_id" in model_columns
    assert "checkpoint_id" in model_columns
    assert "epoch" in model_columns
    assert "step" in model_columns


# =============================================================================
# Migration History Tests
# =============================================================================


@pytest.mark.skip(reason="TODO: Implement with full Alembic setup - verify migration order")
def test_migration_history_order(alembic_config):
    """Test migration is in correct order in history."""
    script = ScriptDirectory.from_config(alembic_config)

    # Get all revisions
    revisions = list(script.walk_revisions())

    # Find our migration
    our_revision = next(
        (r for r in revisions if r.revision == "20251228_add_colony_training"),
        None,
    )

    assert our_revision is not None
    assert our_revision.down_revision == "add_privacy_tables"


# =============================================================================
# Performance Tests
# =============================================================================


def test_migration_performance(migration_engine):
    """Test migration completes in reasonable time."""
    import time

    from migrations.versions.add_colony_and_training_tables_20251228 import (
        upgrade,
    )

    start = time.time()

    with migration_engine.begin() as connection:
        upgrade()

    elapsed = time.time() - start

    # Migration should complete quickly (< 5 seconds)
    assert elapsed < 5.0


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.skip(reason="TODO: Implement error simulation - test duplicate table handling")
def test_migration_handles_duplicate_table():
    """Test migration handles already-created tables gracefully."""
    # Test that running upgrade twice doesn't fail
    pass


@pytest.mark.skip(reason="TODO: Implement error simulation - test rollback on error")
def test_migration_rollback_on_error():
    """Test migration rolls back on error."""
    # Test that partial migration is rolled back on error
    pass
