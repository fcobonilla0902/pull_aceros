"""Conserva la restricción de cantidades después de recrear la tabla en SQLite."""
from alembic import op
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None
def upgrade():
    with op.batch_alter_table('request_items') as batch:
        batch.create_check_constraint('ck_item_quantity_positive','quantity > 0')
def downgrade():
    with op.batch_alter_table('request_items') as batch:
        batch.drop_constraint('ck_item_quantity_positive',type_='check')
