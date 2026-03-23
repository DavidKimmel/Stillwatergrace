"""Add is_selected field to generated_content"""
from alembic import op
import sqlalchemy as sa

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('generated_content', sa.Column('is_selected', sa.Boolean(), server_default='false', nullable=False))


def downgrade():
    op.drop_column('generated_content', 'is_selected')
