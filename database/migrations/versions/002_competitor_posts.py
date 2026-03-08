"""Add competitor_posts table.

Revision ID: 002
Revises: 001
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"


def upgrade():
    op.create_table(
        "competitor_posts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("competitor_handle", sa.String(100), nullable=False, index=True),
        sa.Column("platform_media_id", sa.String(100), unique=True, nullable=False),
        sa.Column("media_type", sa.String(20), nullable=False),
        sa.Column("caption", sa.Text),
        sa.Column("hashtags", sa.JSON, server_default="[]"),
        sa.Column("posted_at", sa.DateTime),
        sa.Column("permalink", sa.String(2000)),
        sa.Column("scraped_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_comp_posts_handle_date", "competitor_posts", ["competitor_handle", "posted_at"])


def downgrade():
    op.drop_table("competitor_posts")
