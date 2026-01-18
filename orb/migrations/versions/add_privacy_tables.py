"""Add privacy tables

Revision ID: add_privacy_tables
Revises:
Create Date: 2025-11-23 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "add_privacy_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_consents",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("consent_type", sa.Text(), nullable=True),
        sa.Column("granted", sa.Boolean(), nullable=True),
        sa.Column("timestamp", sa.TIMESTAMP(), nullable=True),
    )

    op.create_table(
        "privacy_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resource", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.TIMESTAMP(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("privacy_audit_log")
    op.drop_table("user_consents")
