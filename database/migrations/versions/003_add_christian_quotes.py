"""Add christian_quotes table.

Revision ID: 003
Revises: 002
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"


def upgrade():
    op.create_table(
        "christian_quotes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("author", sa.String(200), nullable=False),
        sa.Column("quote_text", sa.Text, nullable=False),
        sa.Column("text_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("source", sa.String(500)),
        sa.Column("tags", sa.JSON, server_default="[]"),
        sa.Column("scraped_from", sa.String(2000)),
        sa.Column("scraped_at", sa.DateTime),
        sa.Column("approved", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_christian_quotes_author", "christian_quotes", ["author"])
    op.create_index("ix_quotes_author_approved", "christian_quotes", ["author", "approved"])


def downgrade():
    op.drop_table("christian_quotes")
