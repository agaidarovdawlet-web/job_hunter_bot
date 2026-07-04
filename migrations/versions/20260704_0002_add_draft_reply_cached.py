"""add cached draft reply column

Revision ID: 20260704_0002
Revises: 20260703_0001
Create Date: 2026-07-04 00:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260704_0002"
down_revision = "20260703_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vacancies",
        sa.Column(
            "draft_reply_cached",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    op.drop_column("vacancies", "draft_reply_cached")
