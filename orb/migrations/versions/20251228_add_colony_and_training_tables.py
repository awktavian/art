"""Add colony state and training run tables

Revision ID: 20251228_add_colony_training
Revises: add_privacy_tables
Create Date: 2025-12-28 17:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20251228_add_colony_training"
down_revision = "add_privacy_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create colony state and training tables."""
    # Colony states table
    op.create_table(
        "colony_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("colony_id", sa.String(50), nullable=False),
        sa.Column("instance_id", sa.String(100), nullable=False),
        sa.Column("node_id", sa.String(100), nullable=False),
        sa.Column("z_state", postgresql.JSON, nullable=False),
        sa.Column("z_dim", sa.Integer, nullable=False, server_default="64"),
        sa.Column("timestamp", sa.Float, nullable=False),
        sa.Column("vector_clock", postgresql.JSON, server_default="{}"),
        sa.Column("action_history", postgresql.JSON, server_default="[]"),
        sa.Column("last_action", sa.String(255), nullable=True),
        sa.Column("fano_neighbors", postgresql.JSON, server_default="[]"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_heartbeat_at", sa.DateTime, nullable=True),
        sa.Column("state_metadata", postgresql.JSON, server_default="{}"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
    )

    # Colony state indexes
    op.create_index(
        "idx_colony_state_colony_instance",
        "colony_states",
        ["colony_id", "instance_id"],
        unique=True,
    )
    op.create_index(
        "idx_colony_state_active", "colony_states", ["is_active", "colony_id"]
    )
    op.create_index(
        "idx_colony_state_timestamp", "colony_states", ["colony_id", "timestamp"]
    )
    op.create_index("idx_colony_state_colony_id", "colony_states", ["colony_id"])
    op.create_index("idx_colony_state_instance_id", "colony_states", ["instance_id"])

    # Training runs table
    op.create_table(
        "training_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("run_type", sa.String(50), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("tenant_id", sa.String(100), nullable=True),
        sa.Column("config", postgresql.JSON, nullable=False),
        sa.Column("model_architecture", sa.String(100), nullable=True),
        sa.Column("dataset_name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("progress", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("metrics", postgresql.JSON, server_default="{}"),
        sa.Column("best_loss", sa.Float, nullable=True),
        sa.Column("best_accuracy", sa.Float, nullable=True),
        sa.Column("final_loss", sa.Float, nullable=True),
        sa.Column("current_epoch", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_epochs", sa.Integer, nullable=True),
        sa.Column("current_step", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_steps", sa.Integer, nullable=True),
        sa.Column("gpu_hours", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("total_tokens_processed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("checkpoint_path", sa.String(512), nullable=True),
        sa.Column("model_path", sa.String(512), nullable=True),
        sa.Column("log_path", sa.String(512), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("error_traceback", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
    )

    # Training runs indexes
    op.create_index("idx_training_run_run_id", "training_runs", ["run_id"])
    op.create_index("idx_training_run_name", "training_runs", ["name"])
    op.create_index("idx_training_run_run_type", "training_runs", ["run_type"])
    op.create_index("idx_training_run_tenant_id", "training_runs", ["tenant_id"])
    op.create_index(
        "idx_training_run_status", "training_runs", ["status", "started_at"]
    )
    op.create_index(
        "idx_training_run_user_status", "training_runs", ["user_id", "status"]
    )
    op.create_index(
        "idx_training_run_type", "training_runs", ["run_type", "status"]
    )
    op.create_index("idx_training_run_started_at", "training_runs", ["started_at"])
    op.create_index("idx_training_run_completed_at", "training_runs", ["completed_at"])

    # Training checkpoints table
    op.create_table(
        "training_checkpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(100),
            sa.ForeignKey("training_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("checkpoint_id", sa.String(100), nullable=False, unique=True),
        sa.Column("epoch", sa.Integer, nullable=False),
        sa.Column("step", sa.Integer, nullable=False),
        sa.Column("loss", sa.Float, nullable=True),
        sa.Column("accuracy", sa.Float, nullable=True),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("storage_backend", sa.String(50), nullable=False, server_default="local"),
        sa.Column("metrics", postgresql.JSON, server_default="{}"),
        sa.Column("is_best", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
    )

    # Training checkpoints indexes
    op.create_index(
        "idx_checkpoint_run_id", "training_checkpoints", ["run_id"]
    )
    op.create_index(
        "idx_checkpoint_checkpoint_id", "training_checkpoints", ["checkpoint_id"]
    )
    op.create_index(
        "idx_checkpoint_run_step", "training_checkpoints", ["run_id", "step"]
    )
    op.create_index(
        "idx_checkpoint_run_best", "training_checkpoints", ["run_id", "is_best"]
    )
    op.create_index(
        "idx_checkpoint_created_at", "training_checkpoints", ["created_at"]
    )


def downgrade() -> None:
    """Drop colony state and training tables."""
    op.drop_table("training_checkpoints")
    op.drop_table("training_runs")
    op.drop_table("colony_states")
