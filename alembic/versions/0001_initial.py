"""Initial schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-02-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)

    op.create_table(
        "summary",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_value", sa.String(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("model_type", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("num_sentences", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_summary_user_id", "summary", ["user_id"], unique=False)

    op.create_table(
        "summaryevidence",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("summary_id", sa.String(), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_summaryevidence_summary_id", "summaryevidence", ["summary_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_summaryevidence_summary_id", table_name="summaryevidence")
    op.drop_table("summaryevidence")
    op.drop_index("ix_summary_user_id", table_name="summary")
    op.drop_table("summary")
    op.drop_index("ix_user_email", table_name="user")
    op.drop_table("user")
