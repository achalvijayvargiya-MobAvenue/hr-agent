"""add requirement fit fields to match_results

Revision ID: 010
Revises: 009
Create Date: 2026-07-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("match_results", sa.Column("requirement_fit_score", sa.Float(), nullable=True))
    op.add_column("match_results", sa.Column("requirement_gaps", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("match_results", "requirement_gaps")
    op.drop_column("match_results", "requirement_fit_score")
