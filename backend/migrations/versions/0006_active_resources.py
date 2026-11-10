"""A physical resource cannot serve two open movements, regardless of client races."""
from alembic import op
import sqlalchemy as sa
revision='0006'
down_revision='0005'
branch_labels=None
depends_on=None

def upgrade():
    for field in ['operator_id','forklift_id']:
        condition=sa.text(f"{field} IS NOT NULL AND state NOT IN ('Entregado','Cancelado')")
        op.create_index('uq_requests_active_'+field,'requests',[field],unique=True,postgresql_where=condition,sqlite_where=condition)

def downgrade():
    for field in ['operator_id','forklift_id']:op.drop_index('uq_requests_active_'+field,table_name='requests')
