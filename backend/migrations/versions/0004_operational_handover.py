"""Recepción de la responsabilidad del turno e incidentes de producción estructurados."""
from alembic import op
import sqlalchemy as sa
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('requests', sa.Column('destination', sa.String(200), nullable=False, server_default=''))
    op.add_column('requests', sa.Column('risk', sa.String(30), nullable=False, server_default='Sin riesgo'))
    op.add_column('incidents', sa.Column('cause', sa.String(40), nullable=False, server_default='Otro'))
    op.add_column('incidents', sa.Column('production_stopped', sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table('handovers') as batch:
        batch.add_column(sa.Column('receiving_user_id', sa.Integer()))
        batch.add_column(sa.Column('accepted_by_id', sa.Integer()))
        batch.add_column(sa.Column('accepted_at', sa.DateTime()))
        batch.add_column(sa.Column('acceptance_notes', sa.Text()))
        batch.create_foreign_key('fk_handover_recipient','users',['receiving_user_id'],['id'])
        batch.create_foreign_key('fk_handover_acceptor','users',['accepted_by_id'],['id'])
        batch.create_index('ix_handovers_receiving_user_id',['receiving_user_id'])
        batch.create_index('ix_handovers_accepted_by_id',['accepted_by_id'])
    op.create_table('handover_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('handover_id', sa.Integer(), sa.ForeignKey('handovers.id'), nullable=False),
        sa.Column('request_id', sa.Integer(), sa.ForeignKey('requests.id'), nullable=False),
        sa.Column('snapshot', sa.Text(), nullable=False),
        sa.UniqueConstraint('handover_id','request_id'))
    op.create_index('ix_handover_items_handover_id','handover_items',['handover_id'])
    op.create_index('ix_handover_items_request_id','handover_items',['request_id'])

def downgrade():
    op.drop_table('handover_items')
    with op.batch_alter_table('handovers') as batch:
        batch.drop_index('ix_handovers_receiving_user_id')
        batch.drop_index('ix_handovers_accepted_by_id')
        batch.drop_constraint('fk_handover_recipient',type_='foreignkey')
        batch.drop_constraint('fk_handover_acceptor',type_='foreignkey')
        for name in ['receiving_user_id','accepted_by_id','accepted_at','acceptance_notes']: batch.drop_column(name)
    with op.batch_alter_table('incidents') as batch:
        batch.drop_column('cause'); batch.drop_column('production_stopped')
    with op.batch_alter_table('requests') as batch:
        batch.drop_column('destination'); batch.drop_column('risk')
