"""Add foreign key constraints.

Revision ID: 0003_add_foreign_keys
Revises: 0002_jobs
Create Date: 2026-02-17
"""

from __future__ import annotations

from alembic import op


revision = "0003_add_foreign_keys"
down_revision = "0002_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("summary") as batch_op:
        batch_op.create_foreign_key(
            "fk_summary_user_id",
            "user",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("job") as batch_op:
        batch_op.create_foreign_key(
            "fk_job_user_id",
            "user",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("summaryevidence") as batch_op:
        batch_op.drop_constraint("fk_summaryevidence_summary_id", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_summaryevidence_summary_id",
            "summary",
            ["summary_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("summaryevidence") as batch_op:
        batch_op.drop_constraint("fk_summaryevidence_summary_id", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_summaryevidence_summary_id",
            "summary",
            ["summary_id"],
            ["id"],
        )

    with op.batch_alter_table("job") as batch_op:
        batch_op.drop_constraint("fk_job_user_id", type_="foreignkey")

    with op.batch_alter_table("summary") as batch_op:
        batch_op.drop_constraint("fk_summary_user_id", type_="foreignkey")
