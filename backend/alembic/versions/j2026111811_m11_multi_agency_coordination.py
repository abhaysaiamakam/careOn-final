"""m11_multi_agency_coordination_and_unified_command

Revision ID: j2026111811_m11
Revises: i2026111810_m10
Create Date: 2026-11-18 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'j2026111811_m11'
down_revision: Union[str, Sequence[str], None] = 'i2026111810_m10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create agency_classifications table
    op.create_table(
        'agency_classifications',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('agency_type', sa.String(length=50), nullable=False),
        sa.Column('jurisdiction', sa.String(length=200), nullable=True),
        sa.Column('dispatch_hotline', sa.String(length=40), nullable=True),
        sa.Column('radio_channel', sa.String(length=40), nullable=True),
        sa.Column('capabilities_json', sa.Text(), nullable=True),
        sa.Column('is_mutual_aid_signatory', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_agency_classifications_org_id', 'agency_classifications', ['organization_id'])

    # 2. Create incident_agency_collaborations table
    op.create_table(
        'incident_agency_collaborations',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('collaboration_uuid', sa.String(length=36), unique=True, nullable=False),
        sa.Column('incident_id', sa.Integer(), sa.ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('collaboration_status', sa.String(length=30), server_default='INVITED', nullable=False),
        sa.Column('inviting_organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('inviting_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('accepted_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.Column('collaboration_purpose', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('incident_id', 'organization_id', name='uq_incident_agency_collab')
    )
    op.create_index('ix_incident_agency_collab_uuid', 'incident_agency_collaborations', ['collaboration_uuid'])
    op.create_index('ix_incident_agency_collab_inc_id', 'incident_agency_collaborations', ['incident_id'])
    op.create_index('ix_incident_agency_collab_org_id', 'incident_agency_collaborations', ['organization_id'])
    op.create_index('ix_incident_agency_collab_status', 'incident_agency_collaborations', ['collaboration_status'])

    # 3. Create incident_information_grants table
    op.create_table(
        'incident_information_grants',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('grant_uuid', sa.String(length=36), unique=True, nullable=False),
        sa.Column('collaboration_id', sa.Integer(), sa.ForeignKey('incident_agency_collaborations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('scope', sa.String(length=60), nullable=False),
        sa.Column('is_granted', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('granted_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('granted_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('collaboration_id', 'scope', name='uq_collab_scope_grant')
    )
    op.create_index('ix_incident_info_grants_uuid', 'incident_information_grants', ['grant_uuid'])
    op.create_index('ix_incident_info_grants_collab_id', 'incident_information_grants', ['collaboration_id'])

    # 4. Create incident_command_structures table
    op.create_table(
        'incident_command_structures',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('command_uuid', sa.String(length=36), unique=True, nullable=False),
        sa.Column('incident_id', sa.Integer(), sa.ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('structure_type', sa.String(length=40), server_default='SINGLE_COMMAND', nullable=False),
        sa.Column('lead_agency_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('activation_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_incident_cmd_structures_uuid', 'incident_command_structures', ['command_uuid'])
    op.create_index('ix_incident_cmd_structures_inc_id', 'incident_command_structures', ['incident_id'])

    # 5. Create incident_command_assignments table
    op.create_table(
        'incident_command_assignments',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('assignment_uuid', sa.String(length=36), unique=True, nullable=False),
        sa.Column('command_structure_id', sa.Integer(), sa.ForeignKey('incident_command_structures.id', ondelete='CASCADE'), nullable=False),
        sa.Column('command_role', sa.String(length=50), nullable=False),
        sa.Column('assigned_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assigned_organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('radio_callsign', sa.String(length=50), nullable=True),
        sa.Column('contact_number', sa.String(length=40), nullable=True),
        sa.Column('assigned_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('relieved_at', sa.DateTime(), nullable=True),
        sa.Column('relieved_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('ix_incident_cmd_assignments_uuid', 'incident_command_assignments', ['assignment_uuid'])
    op.create_index('ix_incident_cmd_assignments_cmd_id', 'incident_command_assignments', ['command_structure_id'])
    op.create_index('ix_incident_cmd_assignments_user_id', 'incident_command_assignments', ['assigned_user_id'])
    op.create_index('ix_incident_cmd_assignments_org_id', 'incident_command_assignments', ['assigned_organization_id'])
    op.create_index('ix_cmd_active_role', 'incident_command_assignments', ['command_structure_id', 'command_role', 'is_active'])

    # 6. Create incident_command_histories table
    op.create_table(
        'incident_command_histories',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('history_uuid', sa.String(length=36), unique=True, nullable=False),
        sa.Column('command_structure_id', sa.Integer(), sa.ForeignKey('incident_command_structures.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('previous_commander_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('new_commander_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('authorizing_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('briefing_summary', sa.Text(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_incident_cmd_histories_uuid', 'incident_command_histories', ['history_uuid'])
    op.create_index('ix_incident_cmd_histories_cmd_id', 'incident_command_histories', ['command_structure_id'])

    # 7. Create agency_operational_tasks table
    op.create_table(
        'agency_operational_tasks',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('task_uuid', sa.String(length=36), unique=True, nullable=False),
        sa.Column('incident_id', sa.Integer(), sa.ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('command_structure_id', sa.Integer(), sa.ForeignKey('incident_command_structures.id', ondelete='SET NULL'), nullable=True),
        sa.Column('assigning_organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assigned_organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('priority', sa.String(length=20), server_default='MEDIUM', nullable=False),
        sa.Column('status', sa.String(length=30), server_default='REQUESTED', nullable=False),
        sa.Column('assigned_unit_name', sa.String(length=100), nullable=True),
        sa.Column('deadline', sa.DateTime(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('acknowledged_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('completed_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('status_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_agency_tasks_uuid', 'agency_operational_tasks', ['task_uuid'])
    op.create_index('ix_agency_tasks_incident_id', 'agency_operational_tasks', ['incident_id'])
    op.create_index('ix_agency_tasks_assigning_org', 'agency_operational_tasks', ['assigning_organization_id'])
    op.create_index('ix_agency_tasks_assigned_org', 'agency_operational_tasks', ['assigned_organization_id'])
    op.create_index('ix_agency_tasks_status', 'agency_operational_tasks', ['status'])

    # 8. Create agency_resource_requests table
    op.create_table(
        'agency_resource_requests',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('request_uuid', sa.String(length=36), unique=True, nullable=False),
        sa.Column('incident_id', sa.Integer(), sa.ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('requesting_organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('requested_organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('requested_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('quantity', sa.Integer(), server_default='1', nullable=False),
        sa.Column('urgency', sa.String(length=20), server_default='ROUTINE', nullable=False),
        sa.Column('status', sa.String(length=30), server_default='REQUESTED', nullable=False),
        sa.Column('operational_justification', sa.Text(), nullable=False),
        sa.Column('staging_location_name', sa.String(length=200), nullable=True),
        sa.Column('staging_latitude', sa.Float(), nullable=True),
        sa.Column('staging_longitude', sa.Float(), nullable=True),
        sa.Column('decision_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('decision_at', sa.DateTime(), nullable=True),
        sa.Column('decision_notes', sa.Text(), nullable=True),
        sa.Column('assigned_resource_ids_json', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_agency_resource_req_uuid', 'agency_resource_requests', ['request_uuid'])
    op.create_index('ix_agency_resource_req_inc_id', 'agency_resource_requests', ['incident_id'])
    op.create_index('ix_agency_resource_req_req_org', 'agency_resource_requests', ['requesting_organization_id'])
    op.create_index('ix_agency_resource_req_rec_org', 'agency_resource_requests', ['requested_organization_id'])
    op.create_index('ix_agency_resource_req_status', 'agency_resource_requests', ['status'])

    # 9. Create incident_operational_zones table
    op.create_table(
        'incident_operational_zones',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('zone_uuid', sa.String(length=36), unique=True, nullable=False),
        sa.Column('incident_id', sa.Integer(), sa.ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by_organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('zone_type', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('center_latitude', sa.Float(), nullable=True),
        sa.Column('center_longitude', sa.Float(), nullable=True),
        sa.Column('radius_meters', sa.Float(), nullable=True),
        sa.Column('polygon_geojson', sa.Text(), nullable=True),
        sa.Column('hazard_type', sa.String(length=100), nullable=True),
        sa.Column('access_restrictions', sa.String(length=200), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_incident_zones_uuid', 'incident_operational_zones', ['zone_uuid'])
    op.create_index('ix_incident_zones_inc_id', 'incident_operational_zones', ['incident_id'])

    # 10. Create inter_agency_audit_logs table
    op.create_table(
        'inter_agency_audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('audit_uuid', sa.String(length=36), unique=True, nullable=False),
        sa.Column('incident_id', sa.Integer(), sa.ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('acting_organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('acting_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action_type', sa.String(length=60), nullable=False),
        sa.Column('target_agency_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('target_resource_type', sa.String(length=50), nullable=True),
        sa.Column('target_resource_id', sa.String(length=100), nullable=True),
        sa.Column('details_json', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_inter_agency_audit_uuid', 'inter_agency_audit_logs', ['audit_uuid'])
    op.create_index('ix_inter_agency_audit_incident_id', 'inter_agency_audit_logs', ['incident_id'])
    op.create_index('ix_inter_agency_audit_acting_org', 'inter_agency_audit_logs', ['acting_organization_id'])
    op.create_index('ix_inter_agency_audit_action_type', 'inter_agency_audit_logs', ['action_type'])
    op.create_index('ix_inter_agency_audit_created_at', 'inter_agency_audit_logs', ['created_at'])


def downgrade() -> None:
    op.drop_table('inter_agency_audit_logs')
    op.drop_table('incident_operational_zones')
    op.drop_table('agency_resource_requests')
    op.drop_table('agency_operational_tasks')
    op.drop_table('incident_command_histories')
    op.drop_table('incident_command_assignments')
    op.drop_table('incident_command_structures')
    op.drop_table('incident_information_grants')
    op.drop_table('incident_agency_collaborations')
    op.drop_table('agency_classifications')
