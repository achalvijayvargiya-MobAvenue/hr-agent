"""Add source_name column to candidates table.

Revision ID: 006
Revises: 005
"""
import sqlalchemy as sa
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column(
            "source_name",
            sa.String(),
            nullable=False,
            server_default="local_kb",
        ),
    )


def downgrade() -> None:
    op.drop_column("candidates", "source_name")
