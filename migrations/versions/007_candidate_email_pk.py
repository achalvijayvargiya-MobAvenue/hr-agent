"""Use email as candidate primary key and add candidate_imports table.

Revision ID: 007
Revises: 006
"""
import sqlalchemy as sa
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Staging table for imports / conflicts ────────────────────────────────
    op.create_table(
        "candidate_imports",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("source_name", sa.String(), nullable=False, server_default="local_kb"),
        sa.Column("status", sa.String(), nullable=False, server_default="PROCESSING"),
        sa.Column("proposed_email", sa.String(), nullable=True),
        sa.Column("existing_email", sa.String(), nullable=True),
        sa.Column("extracted_data", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── Add email column and back-fill from legacy id ──────────────────────────
    op.add_column("candidates", sa.Column("email", sa.String(), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id FROM candidates")).fetchall()
    for (legacy_id,) in rows:
        placeholder = f"{legacy_id}@legacy.local"
        conn.execute(
            sa.text("UPDATE candidates SET email = :email WHERE id = :id"),
            {"email": placeholder, "id": legacy_id},
        )

    op.alter_column("candidates", "email", nullable=False)

    # ── Re-point foreign keys from candidates.id → candidates.email ──────────
    op.drop_constraint("match_results_candidate_id_fkey", "match_results", type_="foreignkey")

    conn.execute(
        sa.text(
            """
            UPDATE match_results AS mr
            SET candidate_id = c.email
            FROM candidates AS c
            WHERE mr.candidate_id = c.id
            """
        )
    )

    conn.execute(
        sa.text(
            """
            UPDATE embeddings AS e
            SET entity_id = c.email
            FROM candidates AS c
            WHERE e.entity_type = 'candidate' AND e.entity_id = c.id
            """
        )
    )

    conn.execute(
        sa.text(
            """
            UPDATE processing_logs AS pl
            SET entity_id = c.email
            FROM candidates AS c
            WHERE pl.entity_type = 'candidate' AND pl.entity_id = c.id
            """
        )
    )

    op.drop_constraint("candidates_pkey", "candidates", type_="primary")
    op.drop_column("candidates", "id")
    op.create_primary_key("candidates_pkey", "candidates", ["email"])

    op.create_foreign_key(
        "match_results_candidate_id_fkey",
        "match_results",
        "candidates",
        ["candidate_id"],
        ["email"],
    )


def downgrade() -> None:
    op.drop_constraint("match_results_candidate_id_fkey", "match_results", type_="foreignkey")

    op.add_column("candidates", sa.Column("id", sa.String(), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT email FROM candidates")).fetchall()
    for (email,) in rows:
        legacy_id = email.split("@")[0] if "@" in email else email
        conn.execute(
            sa.text("UPDATE candidates SET id = :id WHERE email = :email"),
            {"id": legacy_id, "email": email},
        )

    conn.execute(
        sa.text(
            """
            UPDATE match_results AS mr
            SET candidate_id = split_part(c.email, '@', 1)
            FROM candidates AS c
            WHERE mr.candidate_id = c.email
            """
        )
    )

    conn.execute(
        sa.text(
            """
            UPDATE embeddings AS e
            SET entity_id = split_part(c.email, '@', 1)
            FROM candidates AS c
            WHERE e.entity_type = 'candidate' AND e.entity_id = c.email
            """
        )
    )

    conn.execute(
        sa.text(
            """
            UPDATE processing_logs AS pl
            SET entity_id = split_part(c.email, '@', 1)
            FROM candidates AS c
            WHERE pl.entity_type = 'candidate' AND pl.entity_id = c.email
            """
        )
    )

    op.drop_constraint("candidates_pkey", "candidates", type_="primary")
    op.drop_column("candidates", "email")
    op.alter_column("candidates", "id", nullable=False)
    op.create_primary_key("candidates_pkey", "candidates", ["id"])

    op.create_foreign_key(
        "match_results_candidate_id_fkey",
        "match_results",
        "candidates",
        ["candidate_id"],
        ["id"],
    )

    op.drop_table("candidate_imports")
