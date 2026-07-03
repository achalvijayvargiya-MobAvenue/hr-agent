"""add Zoho Recruit sync tables

Revision ID: 012
Revises: 011
Create Date: 2026-07-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sync_metadata",
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("last_modified_time", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="idle"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("records_synced", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("entity_type"),
    )

    op.create_table(
        "zoho_candidates",
        sa.Column("zoho_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("modified_time", sa.String(), nullable=True),
        sa.Column("raw_profile_json", sa.JSON(), nullable=True),
        sa.Column("resume_downloaded", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("resume_attachment_id", sa.String(), nullable=True),
        sa.Column("local_candidate_email", sa.String(), nullable=True),
        sa.Column("sync_status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("sync_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["local_candidate_email"], ["candidates.email"]),
        sa.PrimaryKeyConstraint("zoho_id"),
    )
    op.create_index("ix_zoho_candidates_email", "zoho_candidates", ["email"])

    op.create_table(
        "zoho_job_openings",
        sa.Column("zoho_id", sa.String(), nullable=False),
        sa.Column("posting_title", sa.String(), nullable=True),
        sa.Column("modified_time", sa.String(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("mapped_job_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["mapped_job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("zoho_id"),
    )
    op.create_index("ix_zoho_job_openings_mapped_job_id", "zoho_job_openings", ["mapped_job_id"])

    op.create_table(
        "zoho_applications",
        sa.Column("zoho_id", sa.String(), nullable=False),
        sa.Column("zoho_candidate_id", sa.String(), nullable=False),
        sa.Column("zoho_job_opening_id", sa.String(), nullable=False),
        sa.Column("application_status", sa.String(), nullable=True),
        sa.Column("modified_time", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["zoho_candidate_id"], ["zoho_candidates.zoho_id"]),
        sa.ForeignKeyConstraint(["zoho_job_opening_id"], ["zoho_job_openings.zoho_id"]),
        sa.PrimaryKeyConstraint("zoho_id"),
    )
    op.create_index("ix_zoho_applications_zoho_candidate_id", "zoho_applications", ["zoho_candidate_id"])
    op.create_index("ix_zoho_applications_zoho_job_opening_id", "zoho_applications", ["zoho_job_opening_id"])


def downgrade() -> None:
    op.drop_index("ix_zoho_applications_zoho_job_opening_id", table_name="zoho_applications")
    op.drop_index("ix_zoho_applications_zoho_candidate_id", table_name="zoho_applications")
    op.drop_table("zoho_applications")
    op.drop_index("ix_zoho_job_openings_mapped_job_id", table_name="zoho_job_openings")
    op.drop_table("zoho_job_openings")
    op.drop_index("ix_zoho_candidates_email", table_name="zoho_candidates")
    op.drop_table("zoho_candidates")
    op.drop_table("sync_metadata")
