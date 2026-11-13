"""Esquema operativo inicial normalizado."""
from alembic import op
import sqlalchemy as sa
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    from migrations.initial_schema import Base
    Base.metadata.create_all(bind=op.get_bind())
def downgrade():
    from migrations.initial_schema import Base
    Base.metadata.drop_all(bind=op.get_bind())
