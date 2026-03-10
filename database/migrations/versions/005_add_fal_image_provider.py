"""Add fal to imageprovider enum.

Revision ID: 005
Revises: 004
"""
from alembic import op

revision = "005"
down_revision = "004"


def upgrade() -> None:
    op.execute("ALTER TYPE imageprovider ADD VALUE IF NOT EXISTS 'fal'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values
    pass
