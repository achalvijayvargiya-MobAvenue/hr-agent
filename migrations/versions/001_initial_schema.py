"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("normalized_role", sa.String(), nullable=True),
        sa.Column("experience_min", sa.Integer(), nullable=True),
        sa.Column("experience_max", sa.Integer(), nullable=True),
        sa.Column("must_have_skills", sa.JSON(), nullable=True),
        sa.Column("good_to_have_skills", sa.JSON(), nullable=True),
        sa.Column("department", sa.String(), nullable=True),
        sa.Column("industry", sa.String(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "candidates",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("normalized_role", sa.String(), nullable=True),
        sa.Column("years_experience", sa.Float(), nullable=True),
        sa.Column("skills", sa.JSON(), nullable=True),
        sa.Column("education", sa.JSON(), nullable=True),
        sa.Column("industries", sa.JSON(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "embeddings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=False),
        sa.Column("vector_blob", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "match_results",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("candidate_id", sa.String(), nullable=False),
        sa.Column("is_filtered", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("filter_reason", sa.Text(), nullable=True),
        sa.Column("rule_score", sa.Float(), nullable=True),
        sa.Column("vector_score", sa.Float(), nullable=True),
        sa.Column("llm_score", sa.Float(), nullable=True),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "processing_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Indexes for common query patterns
    op.create_index("ix_embeddings_lookup", "embeddings", ["entity_type", "entity_id", "model_name"])
    op.create_index("ix_match_results_job", "match_results", ["job_id"])
    op.create_index("ix_processing_logs_entity", "processing_logs", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_index("ix_processing_logs_entity", table_name="processing_logs")
    op.drop_index("ix_match_results_job", table_name="match_results")
    op.drop_index("ix_embeddings_lookup", table_name="embeddings")
    op.drop_table("processing_logs")
    op.drop_table("match_results")
    op.drop_table("embeddings")
    op.drop_table("candidates")
    op.drop_table("jobs")
