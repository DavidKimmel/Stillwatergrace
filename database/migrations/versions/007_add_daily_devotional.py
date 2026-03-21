"""Add daily_devotional content type

Revision ID: 007
Revises: 006
Create Date: 2026-03-20
"""
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE contenttype ADD VALUE IF NOT EXISTS 'daily_devotional'")
    op.execute("ALTER TYPE imageformat ADD VALUE IF NOT EXISTS 'reel_9x16'")


def downgrade():
    pass  # Cannot remove enum values in PostgreSQL
