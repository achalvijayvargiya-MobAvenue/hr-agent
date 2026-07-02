"""add cross-encoder rerank score to match_results

Revision ID: 011
Revises: 010
Create Date: 2026-07-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("match_results", sa.Column("rerank_score", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("match_results", "rerank_score")
