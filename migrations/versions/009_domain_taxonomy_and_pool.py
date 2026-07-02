"""add domain taxonomy and job candidate pool

Revision ID: 009
Revises: 7be0a4d35442
Create Date: 2026-07-01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "7be0a4d35442"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── jobs: domain fields ───────────────────────────────────────────────────
    op.add_column("jobs", sa.Column("domain_code", sa.String(), nullable=True))
    op.add_column("jobs", sa.Column("domain_label", sa.String(), nullable=True))
    op.add_column("jobs", sa.Column("subdomain_codes", sa.JSON(), nullable=True))
    op.add_column("jobs", sa.Column("subdomain_labels", sa.JSON(), nullable=True))
    op.add_column("jobs", sa.Column("domain_confidence", sa.Float(), nullable=True))
    op.add_column("jobs", sa.Column("domain_source", sa.String(), nullable=True))
    op.add_column("jobs", sa.Column("domain_evidence", sa.JSON(), nullable=True))

    # ── candidates: domain fields ───────────────────────────────────────────
    op.add_column("candidates", sa.Column("domain_code", sa.String(), nullable=True))
    op.add_column("candidates", sa.Column("domain_label", sa.String(), nullable=True))
    op.add_column("candidates", sa.Column("subdomain_codes", sa.JSON(), nullable=True))
    op.add_column("candidates", sa.Column("subdomain_labels", sa.JSON(), nullable=True))
    op.add_column("candidates", sa.Column("domain_confidence", sa.Float(), nullable=True))
    op.add_column("candidates", sa.Column("domain_source", sa.String(), nullable=True))
    op.add_column("candidates", sa.Column("domain_evidence", sa.JSON(), nullable=True))

    # ── job candidate pools ───────────────────────────────────────────────────
    op.create_table(
        "job_candidate_pools",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("candidate_id", sa.String(), nullable=False),
        sa.Column("pool_status", sa.String(), nullable=False),
        sa.Column("domain_match_score", sa.Float(), nullable=False),
        sa.Column("subdomain_match_score", sa.Float(), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("match_reason", sa.Text(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.email"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "candidate_id", name="uq_job_pool_candidate"),
    )
    op.create_index("ix_job_candidate_pools_job", "job_candidate_pools", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_job_candidate_pools_job", table_name="job_candidate_pools")
    op.drop_table("job_candidate_pools")

    op.drop_column("candidates", "domain_evidence")
    op.drop_column("candidates", "domain_source")
    op.drop_column("candidates", "domain_confidence")
    op.drop_column("candidates", "subdomain_labels")
    op.drop_column("candidates", "subdomain_codes")
    op.drop_column("candidates", "domain_label")
    op.drop_column("candidates", "domain_code")

    op.drop_column("jobs", "domain_evidence")
    op.drop_column("jobs", "domain_source")
    op.drop_column("jobs", "domain_confidence")
    op.drop_column("jobs", "subdomain_labels")
    op.drop_column("jobs", "subdomain_codes")
    op.drop_column("jobs", "domain_label")
    op.drop_column("jobs", "domain_code")
