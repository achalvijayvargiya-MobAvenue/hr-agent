"""Allow nullable raw_text on candidate_imports and purge stored failed CV payloads.

Revision ID: 008
Revises: 007
"""
import sqlalchemy as sa
from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("candidate_imports", "raw_text", existing_type=sa.Text(), nullable=True)

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE candidate_imports
            SET raw_text = NULL, extracted_data = NULL
            WHERE status = 'FAILED'
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE candidate_imports
            SET raw_text = ''
            WHERE raw_text IS NULL
            """
        )
    )
    op.alter_column("candidate_imports", "raw_text", existing_type=sa.Text(), nullable=False)
