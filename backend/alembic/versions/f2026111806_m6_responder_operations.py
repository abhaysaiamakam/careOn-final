"""m6_responder_operations_and_notifications

Revision ID: f2026111806_m6
Revises: e2026111805_m5
Create Date: 2026-11-18 21:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2026111806_m6'
down_revision: Union[str, Sequence[str], None] = 'e2026111805_m5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extend assignments table with acknowledgement tracking
    op.add_column(
        'assignments',
        sa.Column('acknowledgement_status', sa.String(length=30), server_default='pending', nullable=False)
    )
    op.add_column(
        'assignments',
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True)
    )
    op.add_column(
        'assignments',
        sa.Column('acknowledgement_deadline', sa.DateTime(), nullable=True)
    )
    op.add_column(
        'assignments',
        sa.Column('rejection_reason', sa.Text(), nullable=True)
    )

    # 2. Create mission_event_logs table
    op.create_table(
        'mission_event_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=True),
        sa.Column('actor_role', sa.String(length=30), nullable=False),
        sa.Column('previous_status', sa.String(length=40), nullable=True),
        sa.Column('new_status', sa.String(length=40), nullable=False),
        sa.Column('client_action_id', sa.String(length=64), nullable=True),
        sa.Column('client_timestamp', sa.DateTime(), nullable=True),
        sa.Column('server_timestamp', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('hospital_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assignment_id'], ['assignments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['hospital_id'], ['organizations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_mission_event_logs_id'), 'mission_event_logs', ['id'], unique=False)
    op.create_index(op.f('ix_mission_event_logs_assignment_id'), 'mission_event_logs', ['assignment_id'], unique=False)
    op.create_index(op.f('ix_mission_event_logs_incident_id'), 'mission_event_logs', ['incident_id'], unique=False)
    op.create_index(op.f('ix_mission_event_logs_resource_id'), 'mission_event_logs', ['resource_id'], unique=False)
    op.create_index(op.f('ix_mission_event_logs_client_action_id'), 'mission_event_logs', ['client_action_id'], unique=False)
    op.create_index('ix_mission_events_assignment', 'mission_event_logs', ['assignment_id', 'server_timestamp'], unique=False)
    op.create_index('ix_mission_events_incident', 'mission_event_logs', ['incident_id', 'server_timestamp'], unique=False)

    # 3. Create device_registrations table
    op.create_table(
        'device_registrations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('device_token', sa.String(length=255), nullable=False),
        sa.Column('platform', sa.String(length=30), nullable=False),
        sa.Column('device_model', sa.String(length=100), nullable=True),
        sa.Column('app_version', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_device_registrations_id'), 'device_registrations', ['id'], unique=False)
    op.create_index(op.f('ix_device_registrations_user_id'), 'device_registrations', ['user_id'], unique=False)
    op.create_index(op.f('ix_device_registrations_device_token'), 'device_registrations', ['device_token'], unique=True)

    # 4. Create notification_delivery_logs table
    op.create_table(
        'notification_delivery_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('notification_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('device_token', sa.String(length=255), nullable=True),
        sa.Column('platform', sa.String(length=30), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=150), nullable=False),
        sa.Column('body', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=30), server_default='queued', nullable=False),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('idempotency_key', sa.String(length=64), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_notification_delivery_logs_id'), 'notification_delivery_logs', ['id'], unique=False)
    op.create_index(op.f('ix_notification_delivery_logs_notification_id'), 'notification_delivery_logs', ['notification_id'], unique=True)
    op.create_index(op.f('ix_notification_delivery_logs_user_id'), 'notification_delivery_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_notification_delivery_logs_idempotency_key'), 'notification_delivery_logs', ['idempotency_key'], unique=False)
    op.create_index('ix_notification_logs_user', 'notification_delivery_logs', ['user_id', 'created_at'], unique=False)

    # 5. Create responder_telemetry_logs table
    op.create_table(
        'responder_telemetry_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('speed', sa.Float(), nullable=True),
        sa.Column('heading', sa.Float(), nullable=True),
        sa.Column('accuracy', sa.Float(), nullable=True),
        sa.Column('battery_level', sa.Float(), nullable=True),
        sa.Column('network_type', sa.String(length=30), nullable=True),
        sa.Column('freshness_status', sa.String(length=30), server_default='verified_live', nullable=False),
        sa.Column('is_buffered', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('client_action_id', sa.String(length=64), nullable=True),
        sa.Column('client_timestamp', sa.DateTime(), nullable=True),
        sa.Column('server_timestamp', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_responder_telemetry_logs_id'), 'responder_telemetry_logs', ['id'], unique=False)
    op.create_index(op.f('ix_responder_telemetry_logs_resource_id'), 'responder_telemetry_logs', ['resource_id'], unique=False)
    op.create_index(op.f('ix_responder_telemetry_logs_client_action_id'), 'responder_telemetry_logs', ['client_action_id'], unique=False)
    op.create_index('ix_telemetry_resource_time', 'responder_telemetry_logs', ['resource_id', 'server_timestamp'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_telemetry_resource_time', table_name='responder_telemetry_logs')
    op.drop_index(op.f('ix_responder_telemetry_logs_client_action_id'), table_name='responder_telemetry_logs')
    op.drop_index(op.f('ix_responder_telemetry_logs_resource_id'), table_name='responder_telemetry_logs')
    op.drop_index(op.f('ix_responder_telemetry_logs_id'), table_name='responder_telemetry_logs')
    op.drop_table('responder_telemetry_logs')

    op.drop_index('ix_notification_logs_user', table_name='notification_delivery_logs')
    op.drop_index(op.f('ix_notification_delivery_logs_idempotency_key'), table_name='notification_delivery_logs')
    op.drop_index(op.f('ix_notification_delivery_logs_user_id'), table_name='notification_delivery_logs')
    op.drop_index(op.f('ix_notification_delivery_logs_notification_id'), table_name='notification_delivery_logs')
    op.drop_index(op.f('ix_notification_delivery_logs_id'), table_name='notification_delivery_logs')
    op.drop_table('notification_delivery_logs')

    op.drop_index(op.f('ix_device_registrations_device_token'), table_name='device_registrations')
    op.drop_index(op.f('ix_device_registrations_user_id'), table_name='device_registrations')
    op.drop_index(op.f('ix_device_registrations_id'), table_name='device_registrations')
    op.drop_table('device_registrations')

    op.drop_index('ix_mission_events_incident', table_name='mission_event_logs')
    op.drop_index('ix_mission_events_assignment', table_name='mission_event_logs')
    op.drop_index(op.f('ix_mission_event_logs_client_action_id'), table_name='mission_event_logs')
    op.drop_index(op.f('ix_mission_event_logs_resource_id'), table_name='mission_event_logs')
    op.drop_index(op.f('ix_mission_event_logs_incident_id'), table_name='mission_event_logs')
    op.drop_index(op.f('ix_mission_event_logs_assignment_id'), table_name='mission_event_logs')
    op.drop_index(op.f('ix_mission_event_logs_id'), table_name='mission_event_logs')
    op.drop_table('mission_event_logs')

    op.drop_column('assignments', 'rejection_reason')
    op.drop_column('assignments', 'acknowledgement_deadline')
    op.drop_column('assignments', 'acknowledged_at')
    op.drop_column('assignments', 'acknowledgement_status')
