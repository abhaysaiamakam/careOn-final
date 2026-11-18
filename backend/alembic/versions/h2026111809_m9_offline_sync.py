"""m9_offline_sync_and_resilient_field_operations

Revision ID: h2026111809_m9
Revises: g2026111808_m8
Create Date: 2026-11-18 22:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h2026111809_m9'
down_revision: Union[str, Sequence[str], None] = 'g2026111808_m8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enhance existing device_registrations table with M9 offline sync columns
    op.add_column('device_registrations', sa.Column('device_identifier', sa.String(length=64), nullable=True))
    op.add_column('device_registrations', sa.Column('organization_id', sa.Integer(), nullable=True))
    op.add_column('device_registrations', sa.Column('is_revoked', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('device_registrations', sa.Column('revoked_at', sa.DateTime(), nullable=True))
    op.add_column('device_registrations', sa.Column('revoked_reason', sa.String(length=255), nullable=True))
    op.add_column('device_registrations', sa.Column('last_sync_at', sa.DateTime(), nullable=True))
    op.add_column('device_registrations', sa.Column('sync_cursor', sa.String(length=64), server_default='0', nullable=False))
    op.add_column('device_registrations', sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False))
    
    op.create_index('ix_device_registrations_identifier', 'device_registrations', ['device_identifier'], unique=True)
    op.create_index('ix_device_registrations_org_id', 'device_registrations', ['organization_id'])
    op.create_foreign_key('fk_device_registrations_org_id', 'device_registrations', 'organizations', ['organization_id'], ['id'], ondelete='SET NULL')

    # 2. Create sync_batch_receipts table
    op.create_table(
        'sync_batch_receipts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_uuid', sa.String(length=64), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('total_actions', sa.Integer(), server_default='0', nullable=False),
        sa.Column('accepted_actions', sa.Integer(), server_default='0', nullable=False),
        sa.Column('failed_actions', sa.Integer(), server_default='0', nullable=False),
        sa.Column('conflict_actions', sa.Integer(), server_default='0', nullable=False),
        sa.Column('server_receipt_timestamp', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('processing_time_ms', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['device_id'], ['device_registrations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sync_batch_receipts_uuid', 'sync_batch_receipts', ['batch_uuid'], unique=True)
    op.create_index('ix_sync_batch_receipts_device_id', 'sync_batch_receipts', ['device_id'])
    op.create_index('ix_sync_batch_receipts_user_id', 'sync_batch_receipts', ['user_id'])

    # 3. Create sync_action_receipts table
    op.create_table(
        'sync_action_receipts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('action_uuid', sa.String(length=64), nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=True),
        sa.Column('device_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('action_type', sa.String(length=60), nullable=False),
        sa.Column('mission_id', sa.Integer(), nullable=True),
        sa.Column('encounter_id', sa.Integer(), nullable=True),
        sa.Column('client_timestamp', sa.DateTime(), nullable=False),
        sa.Column('server_receipt_timestamp', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('status', sa.String(length=40), nullable=False),
        sa.Column('server_ack_id', sa.String(length=64), nullable=False),
        sa.Column('payload_hash', sa.String(length=64), nullable=False),
        sa.Column('response_payload_json', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['batch_id'], ['sync_batch_receipts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['device_id'], ['device_registrations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sync_action_receipts_uuid', 'sync_action_receipts', ['action_uuid'], unique=True)
    op.create_index('ix_sync_action_receipts_ack_id', 'sync_action_receipts', ['server_ack_id'], unique=True)
    op.create_index('ix_sync_action_receipts_device_id', 'sync_action_receipts', ['device_id'])
    op.create_index('ix_sync_action_receipts_user_id', 'sync_action_receipts', ['user_id'])
    op.create_index('ix_sync_action_receipts_mission_id', 'sync_action_receipts', ['mission_id'])

    # 4. Create sync_conflicts table
    op.create_table(
        'sync_conflicts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conflict_token', sa.String(length=64), nullable=False),
        sa.Column('action_uuid', sa.String(length=64), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('mission_id', sa.Integer(), nullable=True),
        sa.Column('encounter_id', sa.Integer(), nullable=True),
        sa.Column('conflict_category', sa.String(length=40), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('client_state_json', sa.Text(), nullable=False),
        sa.Column('server_state_json', sa.Text(), nullable=False),
        sa.Column('resolution_status', sa.String(length=30), server_default='PENDING', nullable=False),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('resolved_by_user_id', sa.Integer(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['device_id'], ['device_registrations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resolved_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sync_conflicts_token', 'sync_conflicts', ['conflict_token'], unique=True)
    op.create_index('ix_sync_conflicts_action_uuid', 'sync_conflicts', ['action_uuid'])
    op.create_index('ix_sync_conflicts_device_id', 'sync_conflicts', ['device_id'])
    op.create_index('ix_sync_conflicts_status', 'sync_conflicts', ['resolution_status'])

    # 5. Create sync_audit_events table
    op.create_table(
        'sync_audit_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('device_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=60), nullable=False),
        sa.Column('details_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['device_id'], ['device_registrations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sync_audit_events_device_id', 'sync_audit_events', ['device_id'])
    op.create_index('ix_sync_audit_events_user_id', 'sync_audit_events', ['user_id'])
    op.create_index('ix_sync_audit_events_type', 'sync_audit_events', ['event_type'])


def downgrade() -> None:
    op.drop_table('sync_audit_events')
    op.drop_table('sync_conflicts')
    op.drop_table('sync_action_receipts')
    op.drop_table('sync_batch_receipts')
    op.drop_constraint('fk_device_registrations_org_id', 'device_registrations', type_='foreignkey')
    op.drop_index('ix_device_registrations_org_id', table_name='device_registrations')
    op.drop_index('ix_device_registrations_identifier', table_name='device_registrations')
    op.drop_column('device_registrations', 'updated_at')
    op.drop_column('device_registrations', 'sync_cursor')
    op.drop_column('device_registrations', 'last_sync_at')
    op.drop_column('device_registrations', 'revoked_reason')
    op.drop_column('device_registrations', 'revoked_at')
    op.drop_column('device_registrations', 'is_revoked')
    op.drop_column('device_registrations', 'organization_id')
    op.drop_column('device_registrations', 'device_identifier')
