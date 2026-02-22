"""Add jobs table.

Revision ID: 0002_jobs
Revises: 0001_initial
Create Date: 2026-02-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_jobs"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_job_user_id", "job", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_job_user_id", table_name="job")
    op.drop_table("job")
