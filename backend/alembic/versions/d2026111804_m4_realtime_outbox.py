"""m4_realtime_transactional_outbox

Revision ID: d2026111804_m4
Revises: c2026111803_m3
Create Date: 2026-11-18 21:07:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2026111804_m4'
down_revision: Union[str, Sequence[str], None] = 'c2026111803_m3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'outbox_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.String(length=36), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('event_version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('occurred_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('incident_id', sa.Integer(), nullable=True),
        sa.Column('actor_id', sa.Integer(), nullable=True),
        sa.Column('channel', sa.String(length=100), server_default='careon:events:global', nullable=False),
        sa.Column('payload_json', sa.Text(), nullable=False),
        sa.Column('is_published', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_outbox_events_id'), 'outbox_events', ['id'], unique=False)
    op.create_index(op.f('ix_outbox_events_event_id'), 'outbox_events', ['event_id'], unique=True)
    op.create_index(op.f('ix_outbox_events_event_type'), 'outbox_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_outbox_events_organization_id'), 'outbox_events', ['organization_id'], unique=False)
    op.create_index(op.f('ix_outbox_events_incident_id'), 'outbox_events', ['incident_id'], unique=False)
    op.create_index(op.f('ix_outbox_events_actor_id'), 'outbox_events', ['actor_id'], unique=False)
    op.create_index(op.f('ix_outbox_events_channel'), 'outbox_events', ['channel'], unique=False)
    op.create_index(op.f('ix_outbox_events_is_published'), 'outbox_events', ['is_published'], unique=False)
    op.create_index('ix_outbox_events_unpub', 'outbox_events', ['is_published', 'created_at'], unique=False)
    op.create_index('ix_outbox_events_channel_created', 'outbox_events', ['channel', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_outbox_events_channel_created', table_name='outbox_events')
    op.drop_index('ix_outbox_events_unpub', table_name='outbox_events')
    op.drop_index(op.f('ix_outbox_events_is_published'), table_name='outbox_events')
    op.drop_index(op.f('ix_outbox_events_channel'), table_name='outbox_events')
    op.drop_index(op.f('ix_outbox_events_actor_id'), table_name='outbox_events')
    op.drop_index(op.f('ix_outbox_events_incident_id'), table_name='outbox_events')
    op.drop_index(op.f('ix_outbox_events_organization_id'), table_name='outbox_events')
    op.drop_index(op.f('ix_outbox_events_event_type'), table_name='outbox_events')
    op.drop_index(op.f('ix_outbox_events_event_id'), table_name='outbox_events')
    op.drop_index(op.f('ix_outbox_events_id'), table_name='outbox_events')
    op.drop_table('outbox_events')
