"""create vacancies table

Revision ID: 20260703_0001
Revises:
Create Date: 2026-07-03 00:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260703_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vacancies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column(
            "company",
            sa.String(length=512),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "salary",
            sa.String(length=128),
            nullable=False,
            server_default="Не указана",
        ),
        sa.Column("city", sa.String(length=128), nullable=False, server_default=""),
        sa.Column(
            "remote",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("requirements", sa.Text(), nullable=False, server_default=""),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "source",
            sa.String(length=64),
            nullable=False,
            server_default="hh.ru",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="new",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url", name="uq_vacancy_url"),
    )
    op.create_index(
        op.f("ix_vacancies_external_id"),
        "vacancies",
        ["external_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_vacancies_external_id"), table_name="vacancies")
    op.drop_table("vacancies")
