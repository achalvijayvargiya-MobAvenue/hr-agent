"""Add open-position fields to jobs table.

Revision ID: 005
Revises: 004
"""
import sqlalchemy as sa
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("candidates_required", sa.Integer(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column(
            "position_status",
            sa.String(),
            nullable=False,
            server_default="DRAFT",
        ),
    )
    op.add_column("jobs", sa.Column("created_by", sa.String(), nullable=True))
    op.create_foreign_key(
        "fk_jobs_created_by", "jobs", "users", ["created_by"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_jobs_created_by", "jobs", type_="foreignkey")
    op.drop_column("jobs", "created_by")
    op.drop_column("jobs", "position_status")
    op.drop_column("jobs", "candidates_required")
