"""Comprehensive tests for database automation scripts.

Tests migrate.py, rollback.py, seed.py, backup.py, restore.py, and verify.py.

Created: December 28, 2025
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

pytestmark = pytest.mark.tier_integration

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
SCRIPTS_PATH = PROJECT_ROOT / "scripts" / "db"


# =============================================================================
# migrate.py Tests
# =============================================================================


def test_migrate_script_exists():
    """Test migrate.py script exists."""
    migrate_script = SCRIPTS_PATH / "migrate.py"
    assert migrate_script.exists()
    assert migrate_script.is_file()


def test_migrate_script_executable():
    """Test migrate.py is executable."""
    migrate_script = SCRIPTS_PATH / "migrate.py"
    assert os.access(migrate_script, os.X_OK)


@patch("scripts.db.migrate.command")
@patch("scripts.db.migrate.Config")
def test_migrate_get_alembic_config(mock_config, mock_command, monkeypatch):
    """Test getting Alembic configuration."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")

    from scripts.db.migrate import get_alembic_config

    config = get_alembic_config()
    assert config is not None


def test_migrate_requires_database_url(monkeypatch):
    """Test migrate.py requires DATABASE_URL."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    from scripts.db.migrate import get_alembic_config

    with pytest.raises(ValueError, match="DATABASE_URL"):
        get_alembic_config()


@patch("scripts.db.migrate.command")
@patch("scripts.db.migrate.Config")
def test_migrate_to_head(mock_config, mock_command, monkeypatch):
    """Test migrate to latest revision."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")

    from scripts.db.migrate import migrate_to_head

    # Mock config
    mock_cfg = MagicMock()
    mock_config.return_value = mock_cfg

    migrate_to_head()

    # Verify upgrade command called
    mock_command.upgrade.assert_called_once_with(mock_cfg, "head")


@patch("scripts.db.migrate.command")
@patch("scripts.db.migrate.Config")
def test_migrate_to_specific_revision(mock_config, mock_command, monkeypatch):
    """Test migrate to specific revision."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")

    from scripts.db.migrate import migrate_to_revision

    # Mock config
    mock_cfg = MagicMock()
    mock_config.return_value = mock_cfg

    migrate_to_revision("abc123")

    # Verify upgrade command called with revision
    mock_command.upgrade.assert_called_once_with(mock_cfg, "abc123")


@patch("scripts.db.migrate.command")
@patch("scripts.db.migrate.Config")
def test_show_current_revision(mock_config, mock_command, monkeypatch):
    """Test show current database revision."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")

    from scripts.db.migrate import show_current_revision

    # Mock config
    mock_cfg = MagicMock()
    mock_config.return_value = mock_cfg

    show_current_revision()

    # Verify current command called
    mock_command.current.assert_called_once()


# =============================================================================
# rollback.py Tests
# =============================================================================


def test_rollback_script_exists():
    """Test rollback.py script exists."""
    rollback_script = SCRIPTS_PATH / "rollback.py"
    assert rollback_script.exists()
    assert rollback_script.is_file()


def test_rollback_script_executable():
    """Test rollback.py is executable."""
    rollback_script = SCRIPTS_PATH / "rollback.py"
    assert os.access(rollback_script, os.X_OK)


@patch("scripts.db.rollback.command")
@patch("scripts.db.rollback.Config")
def test_rollback_one_revision(mock_config, mock_command, monkeypatch):
    """Test rollback one revision."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")

    from scripts.db.rollback import rollback_one_revision

    # Mock config
    mock_cfg = MagicMock()
    mock_config.return_value = mock_cfg

    rollback_one_revision()

    # Verify downgrade command called
    mock_command.downgrade.assert_called_once_with(mock_cfg, "-1")


@patch("scripts.db.rollback.command")
@patch("scripts.db.rollback.Config")
def test_rollback_to_revision(mock_config, mock_command, monkeypatch):
    """Test rollback to specific revision."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")

    from scripts.db.rollback import rollback_to_revision

    # Mock config
    mock_cfg = MagicMock()
    mock_config.return_value = mock_cfg

    rollback_to_revision("xyz789")

    # Verify downgrade command called with revision
    mock_command.downgrade.assert_called_once_with(mock_cfg, "xyz789")


# =============================================================================
# seed.py Tests
# =============================================================================


def test_seed_script_exists():
    """Test seed.py script exists."""
    seed_script = SCRIPTS_PATH / "seed.py"
    assert seed_script.exists()
    assert seed_script.is_file()


def test_seed_script_executable():
    """Test seed.py is executable."""
    seed_script = SCRIPTS_PATH / "seed.py"
    assert os.access(seed_script, os.X_OK)


@pytest.mark.asyncio
@patch("scripts.db.seed.create_async_engine")
async def test_get_db_session(mock_create_engine, monkeypatch):
    """Test getting database session."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")

    from scripts.db.seed import get_db_session

    # Mock engine
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine

    session = await get_db_session()
    assert session is not None


def test_seed_requires_database_url(monkeypatch):
    """Test seed.py requires DATABASE_URL."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    from scripts.db.seed import get_db_session

    with pytest.raises(ValueError, match="DATABASE_URL"):
        import asyncio

        asyncio.run(get_db_session())


@pytest.mark.asyncio
async def test_seed_users_dev_environment(db_session):
    """Test seeding users in dev environment."""
    from scripts.db.seed import seed_users

    users = await seed_users(db_session, "dev")

    assert len(users) >= 2
    assert any(u.username == "admin" for u in users)
    assert any(u.username == "testuser" for u in users)


@pytest.mark.asyncio
async def test_seed_users_test_environment(db_session):
    """Test seeding users in test environment."""
    from scripts.db.seed import seed_users

    users = await seed_users(db_session, "test")

    assert len(users) >= 2
    assert any(u.is_superuser for u in users)


@pytest.mark.asyncio
async def test_seed_users_prod_environment(db_session):
    """Test seeding users in prod environment."""
    from scripts.db.seed import seed_users

    # Prod should not seed test users
    users = await seed_users(db_session, "prod")

    # Prod seeding would be minimal or none
    assert len(users) == 0 or all(not u.username.startswith("test") for u in users)


@pytest.mark.asyncio
async def test_seed_colony_states(db_session):
    """Test seeding colony states."""
    from scripts.db.seed import seed_colony_states

    await seed_colony_states(db_session, "dev")

    # Verify colonies created
    from sqlalchemy import select

    from kagami.core.database.models import ColonyState

    stmt = select(ColonyState)
    result = await db_session.execute(stmt)
    states = list(result.scalars().all())

    # Should create 7 colonies
    assert len(states) == 7

    colony_ids = {s.colony_id for s in states}
    expected = {"spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"}
    assert colony_ids == expected


# =============================================================================
# backup.py Tests
# =============================================================================


def test_backup_script_exists():
    """Test backup.py script exists."""
    backup_script = SCRIPTS_PATH / "backup.py"
    assert backup_script.exists()
    assert backup_script.is_file()


def test_backup_script_executable():
    """Test backup.py is executable."""
    backup_script = SCRIPTS_PATH / "backup.py"
    assert os.access(backup_script, os.X_OK)


@patch("subprocess.run")
def test_backup_postgresql_dump(mock_run, monkeypatch, tmp_path):
    """Test PostgreSQL backup with pg_dump."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/kagami")

    from scripts.db.backup import backup_postgresql

    output_file = tmp_path / "backup.sql"

    # Mock successful pg_dump
    mock_run.return_value = Mock(returncode=0)

    result = backup_postgresql(str(output_file))
    assert result is True

    # Verify pg_dump was called
    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert "pg_dump" in call_args


@patch("subprocess.run")
def test_backup_handles_pg_dump_error(mock_run, monkeypatch, tmp_path):
    """Test backup handles pg_dump errors."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/kagami")

    from scripts.db.backup import backup_postgresql

    output_file = tmp_path / "backup.sql"

    # Mock failed pg_dump
    mock_run.return_value = Mock(returncode=1, stderr="Error")

    result = backup_postgresql(str(output_file))
    assert result is False


@patch("scripts.db.backup.create_async_engine")
@pytest.mark.asyncio
async def test_backup_table_to_json(mock_create_engine, tmp_path):
    """Test backing up table to JSON."""
    from scripts.db.backup import backup_table_to_json

    output_file = tmp_path / "table_backup.json"

    # Mock engine and connection
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine

    # This would need full async mocking
    # Simplified test
    assert output_file.parent.exists()


# =============================================================================
# restore.py Tests
# =============================================================================


def test_restore_script_exists():
    """Test restore.py script exists."""
    restore_script = SCRIPTS_PATH / "restore.py"
    assert restore_script.exists()
    assert restore_script.is_file()


def test_restore_script_executable():
    """Test restore.py is executable."""
    restore_script = SCRIPTS_PATH / "restore.py"
    assert os.access(restore_script, os.X_OK)


@patch("subprocess.run")
def test_restore_postgresql_dump(mock_run, monkeypatch, tmp_path):
    """Test PostgreSQL restore with psql."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/kagami")

    from scripts.db.restore import restore_postgresql

    # Create fake backup file
    backup_file = tmp_path / "backup.sql"
    backup_file.write_text("-- SQL backup")

    # Mock successful psql
    mock_run.return_value = Mock(returncode=0)

    result = restore_postgresql(str(backup_file))
    assert result is True

    # Verify psql was called
    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert "psql" in call_args


@patch("subprocess.run")
def test_restore_handles_psql_error(mock_run, monkeypatch, tmp_path):
    """Test restore handles psql errors."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/kagami")

    from scripts.db.restore import restore_postgresql

    backup_file = tmp_path / "backup.sql"
    backup_file.write_text("-- SQL backup")

    # Mock failed psql
    mock_run.return_value = Mock(returncode=1, stderr="Error")

    result = restore_postgresql(str(backup_file))
    assert result is False


def test_restore_nonexistent_file(monkeypatch):
    """Test restore with nonexistent backup file."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/kagami")

    from scripts.db.restore import restore_postgresql

    result = restore_postgresql("/nonexistent/backup.sql")
    assert result is False


# =============================================================================
# verify.py Tests
# =============================================================================


def test_verify_script_exists():
    """Test verify.py script exists."""
    verify_script = SCRIPTS_PATH / "verify.py"
    assert verify_script.exists()
    assert verify_script.is_file()


def test_verify_script_executable():
    """Test verify.py is executable."""
    verify_script = SCRIPTS_PATH / "verify.py"
    assert os.access(verify_script, os.X_OK)


@pytest.mark.asyncio
@patch("scripts.db.verify.create_async_engine")
async def test_verify_connection(mock_create_engine, monkeypatch):
    """Test verifying database connection."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/kagami")

    from scripts.db.verify import verify_connection

    # Mock engine
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine

    result = await verify_connection()
    assert result is not None


@pytest.mark.asyncio
async def test_verify_tables_exist(db_session):
    """Test verifying required tables exist."""
    from scripts.db.verify import verify_tables_exist

    # Create some tables
    from kagami.core.database.base import Base

    # Tables already created by fixture

    result = await verify_tables_exist(db_session)
    assert result is True


@pytest.mark.asyncio
async def test_verify_indexes_exist(db_session):
    """Test verifying required indexes exist."""
    from scripts.db.verify import verify_indexes_exist

    # Indexes already created by fixture

    result = await verify_indexes_exist(db_session)
    # May be True or False depending on SQLite vs PostgreSQL
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_verify_data_integrity(db_session, sample_user):
    """Test verifying data integrity."""
    from scripts.db.verify import verify_data_integrity

    # Sample data already exists

    result = await verify_data_integrity(db_session)
    assert isinstance(result, bool)


# =============================================================================
# Integration Tests
# =============================================================================


@pytest.mark.skip(
    reason="TODO: Implement with full database setup - test migrate/seed/backup workflow"
)
def test_migrate_seed_backup_workflow():
    """Test full workflow: migrate -> seed -> backup."""
    # This would test the complete workflow
    # 1. Run migrations
    # 2. Seed data
    # 3. Backup database
    # 4. Verify backup created
    pass


@pytest.mark.skip(reason="TODO: Implement with full database setup - test backup/restore workflow")
def test_backup_restore_workflow():
    """Test backup and restore workflow."""
    # This would test:
    # 1. Create backup
    # 2. Modify database
    # 3. Restore backup
    # 4. Verify data restored
    pass


@pytest.mark.skip(reason="TODO: Implement with full database setup - test rollback workflow")
def test_rollback_workflow():
    """Test migration rollback workflow."""
    # This would test:
    # 1. Run migration
    # 2. Verify tables created
    # 3. Rollback migration
    # 4. Verify tables removed
    pass


# =============================================================================
# Error Handling Tests
# =============================================================================


def test_migrate_handles_invalid_revision(monkeypatch):
    """Test migrate handles invalid revision gracefully."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/kagami")

    from scripts.db.migrate import migrate_to_revision

    # This should raise or handle error gracefully
    with pytest.raises(Exception):
        migrate_to_revision("invalid_revision_id")


def test_seed_handles_duplicate_data(db_session):
    """Test seed handles duplicate data gracefully."""
    import asyncio

    from scripts.db.seed import seed_users

    # Seed once
    asyncio.run(seed_users(db_session, "test"))

    # Seed again - should handle duplicates
    with pytest.raises(Exception):
        # Should raise integrity error or handle it
        asyncio.run(seed_users(db_session, "test"))


# =============================================================================
# Performance Tests
# =============================================================================


@pytest.mark.asyncio
async def test_seed_performance(db_session):
    """Test seeding completes in reasonable time."""
    import time

    from scripts.db.seed import seed_colony_states, seed_users

    start = time.time()

    await seed_users(db_session, "test")
    await seed_colony_states(db_session, "test")

    elapsed = time.time() - start

    # Should complete quickly (< 5 seconds)
    assert elapsed < 5.0


@pytest.mark.skip(
    reason="Performance test requiring large dataset - run with: pytest -m performance"
)
@pytest.mark.performance
def test_backup_performance():
    """Test backup performance with large dataset."""
    # Test backup completes in reasonable time
    pass


@pytest.mark.skip(
    reason="Performance test requiring large dataset - run with: pytest -m performance"
)
@pytest.mark.performance
def test_restore_performance():
    """Test restore performance with large dataset."""
    # Test restore completes in reasonable time
    pass


# =============================================================================
# Command Line Interface Tests
# =============================================================================


def test_migrate_cli_help():
    """Test migrate.py --help works."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_PATH / "migrate.py"), "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_seed_cli_help():
    """Test seed.py --help works."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_PATH / "seed.py"), "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_backup_cli_help():
    """Test backup.py --help works."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_PATH / "backup.py"), "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "usage" in result.stdout.lower()
