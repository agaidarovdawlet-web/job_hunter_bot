"""add semantic score cache

Revision ID: 20260704_0003
Revises: 20260704_0002
Create Date: 2026-07-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260704_0003"
down_revision = "20260704_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vacancies", sa.Column("semantic_score_cached", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("vacancies", "semantic_score_cached")
