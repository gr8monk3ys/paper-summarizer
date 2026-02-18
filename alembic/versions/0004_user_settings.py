"""Add user settings table.

Revision ID: 0004_user_settings
Revises: 0003_add_foreign_keys
Create Date: 2026-02-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_user_settings"
down_revision = "0003_add_foreign_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usersettings",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("default_model", sa.String(), nullable=False),
        sa.Column("summary_length", sa.Integer(), nullable=False),
        sa.Column("citation_handling", sa.String(), nullable=False),
        sa.Column("auto_save", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("usersettings")
