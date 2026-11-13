"""Permite que producción solicite un rollo físico específico."""
from alembic import op
import sqlalchemy as sa
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None
def upgrade():
    with op.batch_alter_table('request_items') as batch:
        batch.add_column(sa.Column('preferred_roll_id',sa.Integer(),nullable=True))
        batch.create_foreign_key('fk_request_item_preferred_roll','rolls',['preferred_roll_id'],['id'])
def downgrade():
    with op.batch_alter_table('request_items') as batch:
        batch.drop_constraint('fk_request_item_preferred_roll',type_='foreignkey')
        batch.drop_column('preferred_roll_id')
