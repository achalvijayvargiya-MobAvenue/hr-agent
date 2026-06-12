"""Add new extraction fields to jobs and candidates tables.

Adds columns extracted by the updated JD / CV prompts:
  jobs      — employment_type, location, education_requirements, certifications,
               responsibilities, tools_and_technologies, seniority_level
  candidates — current_title, current_company, location, tools_and_technologies,
                certifications, employment_history, experience_areas,
                responsibilities, seniority_level

Revision ID: 002
Revises: 001
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── jobs ──────────────────────────────────────────────────────────────────
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("employment_type", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("location", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("education_requirements", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("certifications", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("responsibilities", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("tools_and_technologies", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("seniority_level", sa.String(), nullable=True))

    # ── candidates ────────────────────────────────────────────────────────────
    with op.batch_alter_table("candidates") as batch_op:
        batch_op.add_column(sa.Column("current_title", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("current_company", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("location", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("tools_and_technologies", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("certifications", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("employment_history", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("experience_areas", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("responsibilities", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("seniority_level", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("candidates") as batch_op:
        for col in [
            "seniority_level", "responsibilities", "experience_areas",
            "employment_history", "certifications", "tools_and_technologies",
            "location", "current_company", "current_title",
        ]:
            batch_op.drop_column(col)

    with op.batch_alter_table("jobs") as batch_op:
        for col in [
            "seniority_level", "tools_and_technologies", "responsibilities",
            "certifications", "education_requirements", "location", "employment_type",
        ]:
            batch_op.drop_column(col)
