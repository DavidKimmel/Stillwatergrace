"""Add quote_id to generated_content and christian_quote enum value.

Revision ID: 004
Revises: 003
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"


def upgrade() -> None:
    # Add christian_quote to contenttype enum
    op.execute("ALTER TYPE contenttype ADD VALUE IF NOT EXISTS 'christian_quote'")

    # Add quote_id foreign key to generated_content
    op.add_column(
        "generated_content",
        sa.Column("quote_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_generated_content_quote_id",
        "generated_content",
        "christian_quotes",
        ["quote_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_generated_content_quote_id",
        "generated_content",
        type_="foreignkey",
    )
    op.drop_column("generated_content", "quote_id")
    # Note: PostgreSQL does not support removing enum values
