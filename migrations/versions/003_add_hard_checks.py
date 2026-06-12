"""Add hard_checks column to jobs table.

Stores per-JD user-configured hard filter criteria as a JSON object.
Keys are field names; values are either a list of required items (for
list fields such as must_have_skills) or a string (for scalar fields
such as seniority_level).

Revision ID: 003
Revises: 002
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("hard_checks", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_column("hard_checks")
