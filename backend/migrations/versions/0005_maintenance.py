"""Gestión del ciclo de vida del catálogo, concurrencia optimista e importaciones de inventario revisadas."""
from alembic import op
import sqlalchemy as sa
revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None

def upgrade():
    for table in ['users','parts','locations','presses','processes','forklifts','rolls']:
        op.add_column(table,sa.Column('version',sa.Integer(),nullable=False,server_default='1'))
    for table in ['parts','locations','presses','processes','forklifts']:
        op.add_column(table,sa.Column('active',sa.Boolean(),nullable=False,server_default=sa.true()))
    op.create_table('inventory_imports',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('token_digest',sa.String(64),nullable=False,unique=True),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('filename',sa.String(200),nullable=False),
        sa.Column('payload',sa.Text(),nullable=False),
        sa.Column('update_existing',sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.Column('expires_at',sa.DateTime(),nullable=False),
        sa.Column('committed_at',sa.DateTime()))
    op.create_index('ix_inventory_imports_user_id','inventory_imports',['user_id'])
    op.create_index('ix_inventory_imports_expires_at','inventory_imports',['expires_at'])

def downgrade():
    op.drop_table('inventory_imports')
    for table in ['users','parts','locations','presses','processes','forklifts','rolls']:
        with op.batch_alter_table(table) as batch:
            batch.drop_column('version')
            if table not in ['users','rolls']:batch.drop_column('active')
