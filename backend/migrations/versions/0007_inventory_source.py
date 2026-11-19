"""Conserva las columnas del archivo de inventario en cada rollo importado."""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('rolls', sa.Column('source_data', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('rolls', 'source_data')
