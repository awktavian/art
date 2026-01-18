#!/usr/bin/env python3
"""Database seeding script for test data.

Usage:
    python scripts/db/seed.py [--env ENV]

Examples:
    # Seed development data
    python scripts/db/seed.py --env dev

    # Seed test data
    python scripts/db/seed.py --env test

    # Seed production sample data
    python scripts/db/seed.py --env prod

Environment Variables:
    DATABASE_URL: PostgreSQL connection string (required)
"""

import argparse
import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from kagami.core.database.models import (
    ColonyState,
    Goal,
    Plan,
    PlanTask,
    Receipt,
    TrainingRun,
    User,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_db_session() -> AsyncSession:
    """Get database session.

    Returns:
        Async database session
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable must be set")

    # Convert postgresql:// to postgresql+asyncpg://
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return async_session()


async def seed_users(session: AsyncSession, env: str) -> list[User]:
    """Seed user data.

    Args:
        session: Database session
        env: Environment (dev, test, prod)

    Returns:
        List of created users
    """
    logger.info("Seeding users...")
    users = []

    if env in ["dev", "test"]:
        # Test users
        test_users = [
            User(
                id=uuid.uuid4(),
                username="admin",
                email="admin@kagami.ai",
                hashed_password="$2b$12$dummy_hash_for_testing",
                roles=["admin", "user"],
                is_active=True,
                is_superuser=True,
                is_verified=True,
                tenant_id="kagami-internal",
            ),
            User(
                id=uuid.uuid4(),
                username="testuser",
                email="test@example.com",
                hashed_password="$2b$12$dummy_hash_for_testing",
                roles=["user"],
                is_active=True,
                is_verified=True,
                tenant_id="test-tenant",
            ),
        ]
        users.extend(test_users)

    for user in users:
        session.add(user)

    await session.commit()
    logger.info(f"Created {len(users)} users")
    return users


async def seed_colony_states(session: AsyncSession, env: str) -> None:
    """Seed colony state data.

    Args:
        session: Database session
        env: Environment (dev, test, prod)
    """
    logger.info("Seeding colony states...")
    colonies = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]
    states = []

    for colony in colonies:
        state = ColonyState(
            id=uuid.uuid4(),
            colony_id=colony,
            instance_id=f"{colony}-001",
            node_id=f"node-{colony}-001",
            z_state={"latent": [0.0] * 64},
            z_dim=64,
            timestamp=datetime.utcnow().timestamp(),
            vector_clock={},
            action_history=[],
            fano_neighbors=[],
            is_active=True,
            last_heartbeat_at=datetime.utcnow(),
            state_metadata={"version": "1.0.0"},
        )
        states.append(state)
        session.add(state)

    await session.commit()
    logger.info(f"Created {len(states)} colony states")


async def seed_training_runs(session: AsyncSession, users: list[User], env: str) -> None:
    """Seed training run data.

    Args:
        session: Database session
        users: List of users
        env: Environment (dev, test, prod)
    """
    logger.info("Seeding training runs...")
    runs = []

    if env in ["dev", "test"] and users:
        user = users[0]

        # Completed run
        run1 = TrainingRun(
            id=uuid.uuid4(),
            run_id=f"run-{uuid.uuid4().hex[:8]}",
            name="RSSM Pretraining - Complete",
            run_type="pretrain",
            user_id=user.id,
            tenant_id=user.tenant_id,
            config={"batch_size": 32, "learning_rate": 0.001},
            model_architecture="RSSM",
            dataset_name="synthetic",
            status="completed",
            progress=1.0,
            metrics={"loss": [1.5, 1.2, 1.0, 0.9], "accuracy": [0.5, 0.6, 0.7, 0.8]},
            best_loss=0.9,
            best_accuracy=0.8,
            final_loss=0.9,
            current_epoch=10,
            total_epochs=10,
            current_step=1000,
            total_steps=1000,
            gpu_hours=2.5,
            started_at=datetime.utcnow() - timedelta(hours=3),
            completed_at=datetime.utcnow() - timedelta(hours=1),
        )
        runs.append(run1)

        # Running run
        run2 = TrainingRun(
            id=uuid.uuid4(),
            run_id=f"run-{uuid.uuid4().hex[:8]}",
            name="EFE Fine-tuning - In Progress",
            run_type="finetune",
            user_id=user.id,
            tenant_id=user.tenant_id,
            config={"batch_size": 16, "learning_rate": 0.0001},
            model_architecture="EFE",
            dataset_name="custom",
            status="running",
            progress=0.45,
            metrics={"loss": [0.8, 0.75], "accuracy": [0.82, 0.84]},
            best_loss=0.75,
            best_accuracy=0.84,
            current_epoch=4,
            total_epochs=10,
            current_step=450,
            total_steps=1000,
            gpu_hours=1.2,
            started_at=datetime.utcnow() - timedelta(minutes=45),
        )
        runs.append(run2)

    for run in runs:
        session.add(run)

    await session.commit()
    logger.info(f"Created {len(runs)} training runs")


async def seed_receipts(session: AsyncSession, users: list[User], env: str) -> None:
    """Seed receipt data.

    Args:
        session: Database session
        users: List of users
        env: Environment (dev, test, prod)
    """
    logger.info("Seeding receipts...")
    receipts = []

    if env in ["dev", "test"] and users:
        user = users[0]
        correlation_id = f"corr-{uuid.uuid4().hex[:8]}"

        # PLAN receipt
        plan_receipt = Receipt(
            id=uuid.uuid4(),
            correlation_id=correlation_id,
            parent_receipt_id=None,
            phase="PLAN",
            action="generate_character",
            app="forge",
            status="success",
            user_id=user.id,
            tenant_id=user.tenant_id,
            intent={"goal": "create warrior character"},
            event={"phase": "planning"},
            data={"concept": "warrior"},
            metrics={"planning_time_ms": 50},
            duration_ms=50,
            ts=datetime.utcnow() - timedelta(seconds=10),
        )
        receipts.append(plan_receipt)

        # EXECUTE receipt
        exec_receipt = Receipt(
            id=uuid.uuid4(),
            correlation_id=correlation_id,
            parent_receipt_id=correlation_id,
            phase="EXECUTE",
            action="generate_character",
            app="forge",
            status="success",
            user_id=user.id,
            tenant_id=user.tenant_id,
            intent={"goal": "create warrior character"},
            event={"phase": "execution"},
            data={"character_id": "char-001"},
            metrics={"generation_time_ms": 500},
            duration_ms=500,
            ts=datetime.utcnow() - timedelta(seconds=5),
        )
        receipts.append(exec_receipt)

        # VERIFY receipt
        verify_receipt = Receipt(
            id=uuid.uuid4(),
            correlation_id=correlation_id,
            parent_receipt_id=correlation_id,
            phase="VERIFY",
            action="generate_character",
            app="forge",
            status="success",
            user_id=user.id,
            tenant_id=user.tenant_id,
            intent={"goal": "create warrior character"},
            event={"phase": "verification"},
            data={"verification_passed": True},
            metrics={"verification_time_ms": 25},
            duration_ms=25,
            ts=datetime.utcnow(),
        )
        receipts.append(verify_receipt)

    for receipt in receipts:
        session.add(receipt)

    await session.commit()
    logger.info(f"Created {len(receipts)} receipts")


async def seed_plans_and_goals(session: AsyncSession, users: list[User], env: str) -> None:
    """Seed plans and goals.

    Args:
        session: Database session
        users: List of users
        env: Environment (dev, test, prod)
    """
    logger.info("Seeding plans and goals...")

    if env in ["dev", "test"] and users:
        user = users[0]

        # Create goal
        goal = Goal(
            id=uuid.uuid4(),
            goal_id=f"goal-{uuid.uuid4().hex[:8]}",
            description="Build AI character generation system",
            success_criteria={"criteria": ["working API", "test coverage"]},
            priority=8,
            status="active",
            completion_percentage=0.6,
            estimated_steps=10,
            completed_steps=6,
        )
        session.add(goal)

        # Create plan
        plan = Plan(
            id=uuid.uuid4(),
            plan_id=f"plan-{uuid.uuid4().hex[:8]}",
            user_id=user.id,
            name="Q4 2025 - Character Generation",
            description="Implement full character generation pipeline",
            type="project",
            status="active",
            progress=60,
            target_date=datetime.utcnow() + timedelta(days=30),
            visibility="public",
        )
        session.add(plan)
        await session.flush()

        # Create tasks
        tasks = [
            PlanTask(
                id=uuid.uuid4(),
                task_id=f"task-{uuid.uuid4().hex[:8]}",
                plan_id=plan.plan_id,
                title="Implement 3D model generation",
                description="Use Genesis for 3D character models",
                status="completed",
                priority="high",
            ),
            PlanTask(
                id=uuid.uuid4(),
                task_id=f"task-{uuid.uuid4().hex[:8]}",
                plan_id=plan.plan_id,
                title="Add animation system",
                description="Facial and gesture animations",
                status="in_progress",
                priority="high",
            ),
            PlanTask(
                id=uuid.uuid4(),
                task_id=f"task-{uuid.uuid4().hex[:8]}",
                plan_id=plan.plan_id,
                title="Build export pipeline",
                description="Export to FBX, GLTF formats",
                status="pending",
                priority="medium",
            ),
        ]

        for task in tasks:
            session.add(task)

    await session.commit()
    logger.info("Created plans and goals")


async def seed_database(env: str) -> None:
    """Seed database with test data.

    Args:
        env: Environment (dev, test, prod)
    """
    logger.info(f"Seeding database for environment: {env}")

    session = await get_db_session()

    try:
        users = await seed_users(session, env)
        await seed_colony_states(session, env)
        await seed_training_runs(session, users, env)
        await seed_receipts(session, users, env)
        await seed_plans_and_goals(session, users, env)

        logger.info("Database seeding complete!")
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        await session.rollback()
        raise
    finally:
        await session.close()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Database seeding tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--env",
        "-e",
        choices=["dev", "test", "prod"],
        default="dev",
        help="Environment to seed (default: dev)",
    )

    args = parser.parse_args()

    try:
        asyncio.run(seed_database(args.env))
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
