#!/usr/bin/env python3
"""Database layer verification script.

Verifies that all database components are properly configured.

Usage:
    python scripts/db/verify.py
"""

import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_file_exists(path: Path, description: str) -> bool:
    """Check if file exists.

    Args:
        path: Path to file
        description: Description for logging

    Returns:
        True if exists
    """
    if path.exists():
        logger.info(f"✓ {description}: {path}")
        return True
    else:
        logger.error(f"✗ {description}: {path} NOT FOUND")
        return False


def check_alembic_config() -> bool:
    """Check alembic configuration.

    Returns:
        True if configured correctly
    """
    logger.info("\n=== Checking Alembic Configuration ===")

    alembic_ini = project_root / "alembic.ini"
    if not check_file_exists(alembic_ini, "Alembic config"):
        return False

    # Check script_location
    with open(alembic_ini) as f:
        content = f.read()
        if "script_location = migrations" in content:
            logger.info("✓ Alembic script_location correctly set to 'migrations'")
            return True
        else:
            logger.error("✗ Alembic script_location not set correctly")
            return False


def check_migration_files() -> bool:
    """Check migration files exist.

    Returns:
        True if all files exist
    """
    logger.info("\n=== Checking Migration Files ===")

    files = [
        (project_root / "migrations" / "env.py", "Alembic environment"),
        (project_root / "migrations" / "script.py.mako", "Migration template"),
        (
            project_root / "migrations" / "versions" / "20251228_add_colony_and_training_tables.py",
            "Colony & Training migration",
        ),
    ]

    all_exist = True
    for path, desc in files:
        if not check_file_exists(path, desc):
            all_exist = False

    return all_exist


def check_orm_models() -> bool:
    """Check ORM models are defined.

    Returns:
        True if models exist
    """
    logger.info("\n=== Checking ORM Models ===")

    try:
        from kagami.core.database.models import (
            ColonyState,
            TrainingCheckpoint,
            TrainingRun,
        )

        logger.info("✓ ColonyState model imported successfully")
        logger.info("✓ TrainingRun model imported successfully")
        logger.info("✓ TrainingCheckpoint model imported successfully")

        # Check model has expected fields
        assert hasattr(ColonyState, "colony_id")
        assert hasattr(ColonyState, "z_state")
        assert hasattr(TrainingRun, "run_id")
        assert hasattr(TrainingRun, "status")
        assert hasattr(TrainingCheckpoint, "checkpoint_id")

        logger.info("✓ All models have expected fields")
        return True

    except ImportError as e:
        logger.error(f"✗ Failed to import models: {e}")
        return False
    except AssertionError as e:
        logger.error(f"✗ Model missing expected field: {e}")
        return False


def check_repositories() -> bool:
    """Check repository implementations exist.

    Returns:
        True if repositories exist
    """
    logger.info("\n=== Checking Repositories ===")

    try:
        from kagami.core.storage.colony_repository import ColonyStateRepository
        from kagami.core.storage.training_repository import (
            TrainingCheckpointRepository,
            TrainingRunRepository,
        )

        logger.info("✓ ColonyStateRepository imported successfully")
        logger.info("✓ TrainingRunRepository imported successfully")
        logger.info("✓ TrainingCheckpointRepository imported successfully")

        # Check repositories have expected methods
        assert hasattr(ColonyStateRepository, "get_by_colony_instance")
        assert hasattr(ColonyStateRepository, "save_colony_state")
        assert hasattr(TrainingRunRepository, "get_by_run_id")
        assert hasattr(TrainingRunRepository, "update_progress")

        logger.info("✓ All repositories have expected methods")
        return True

    except ImportError as e:
        logger.error(f"✗ Failed to import repositories: {e}")
        return False
    except AssertionError as e:
        logger.error(f"✗ Repository missing expected method: {e}")
        return False


def check_automation_scripts() -> bool:
    """Check automation scripts exist.

    Returns:
        True if all scripts exist
    """
    logger.info("\n=== Checking Automation Scripts ===")

    scripts = [
        "migrate.py",
        "rollback.py",
        "seed.py",
        "backup.py",
        "restore.py",
    ]

    all_exist = True
    for script in scripts:
        path = project_root / "scripts" / "db" / script
        if not check_file_exists(path, f"Script: {script}"):
            all_exist = False
        else:
            # Check if executable
            if path.stat().st_mode & 0o111:
                logger.info(f"  ✓ {script} is executable")
            else:
                logger.warning(f"  ⚠ {script} is not executable (run: chmod +x {path})")

    return all_exist


def check_documentation() -> bool:
    """Check documentation exists.

    Returns:
        True if documentation exists
    """
    logger.info("\n=== Checking Documentation ===")

    docs = [
        (project_root / "scripts" / "db" / "README.md", "Database scripts README"),
        (project_root / "DATABASE_LAYER_COMPLETE.md", "Database layer summary"),
    ]

    all_exist = True
    for path, desc in docs:
        if not check_file_exists(path, desc):
            all_exist = False

    return all_exist


def main() -> None:
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Database Layer Verification")
    logger.info("=" * 60)

    checks = [
        ("Alembic Configuration", check_alembic_config),
        ("Migration Files", check_migration_files),
        ("ORM Models", check_orm_models),
        ("Repositories", check_repositories),
        ("Automation Scripts", check_automation_scripts),
        ("Documentation", check_documentation),
    ]

    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            logger.error(f"\n✗ {name} check failed with exception: {e}")
            results.append((name, False))

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("VERIFICATION SUMMARY")
    logger.info("=" * 60)

    all_passed = True
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {name}")
        if not result:
            all_passed = False

    logger.info("=" * 60)

    if all_passed:
        logger.info("\n✓ All checks passed! Database layer is ready.")
        sys.exit(0)
    else:
        logger.error("\n✗ Some checks failed. Please review errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
