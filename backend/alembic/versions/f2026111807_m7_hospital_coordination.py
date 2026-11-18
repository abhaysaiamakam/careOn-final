"""m7_hospital_readiness_capacity_and_coordination

Revision ID: f2026111807_m7
Revises: f2026111806_m6
Create Date: 2026-11-18 22:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2026111807_m7'
down_revision: Union[str, Sequence[str], None] = 'f2026111806_m6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create hospital_facilities table
    op.create_table(
        'hospital_facilities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('facility_code', sa.String(length=30), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('facility_type', sa.String(length=50), server_default='General Hospital', nullable=False),
        sa.Column('location_name', sa.String(length=200), nullable=False),
        sa.Column('latitude', sa.Float(), server_default='12.3052', nullable=False),
        sa.Column('longitude', sa.Float(), server_default='76.6552', nullable=False),
        sa.Column('trauma_level', sa.String(length=30), server_default='Level 2', nullable=False),
        sa.Column('capabilities', sa.String(length=255), server_default='emergency,trauma,icu,ct_scan,blood_bank,ambulance_bay', nullable=False),
        sa.Column('specialist_services', sa.String(length=255), server_default='trauma_surgeon,cardiologist,neurologist,anesthesiologist', nullable=True),
        sa.Column('medical_equipment', sa.String(length=255), server_default='ct_scanner,mri,ventilators,defibrillators,dialysis', nullable=True),
        sa.Column('ambulance_bays', sa.Integer(), server_default='4', nullable=False),
        sa.Column('operating_status', sa.String(length=30), server_default='operational', nullable=False),
        sa.Column('emergency_phone', sa.String(length=30), nullable=True),
        sa.Column('escalation_contact', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('last_verified_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_hospital_facilities_facility_code', 'hospital_facilities', ['facility_code'], unique=True)
    op.create_index('ix_hospital_facilities_org', 'hospital_facilities', ['organization_id'])

    # 2. Create hospital_capacities table
    op.create_table(
        'hospital_capacities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('facility_id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('total_capacity', sa.Integer(), server_default='0', nullable=False),
        sa.Column('occupied_capacity', sa.Integer(), server_default='0', nullable=False),
        sa.Column('reserved_capacity', sa.Integer(), server_default='0', nullable=False),
        sa.Column('unavailable_capacity', sa.Integer(), server_default='0', nullable=False),
        sa.Column('reporting_source', sa.String(length=50), server_default='staff_manual', nullable=False),
        sa.Column('verification_status', sa.String(length=30), server_default='verified_current', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['facility_id'], ['hospital_facilities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('facility_id', 'category', name='uq_facility_capacity_category')
    )
    op.create_index('ix_hospital_capacities_facility', 'hospital_capacities', ['facility_id'])

    # 3. Create hospital_capacity_reservations table
    op.create_table(
        'hospital_capacity_reservations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reservation_token', sa.String(length=36), nullable=False),
        sa.Column('facility_id', sa.Integer(), nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=True),
        sa.Column('category', sa.String(length=50), server_default='er_beds', nullable=False),
        sa.Column('quantity', sa.Integer(), server_default='1', nullable=False),
        sa.Column('status', sa.String(length=30), server_default='active', nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('released_at', sa.DateTime(), nullable=True),
        sa.Column('release_reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['assignment_id'], ['assignments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['facility_id'], ['hospital_facilities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_hospital_reservations_token', 'hospital_capacity_reservations', ['reservation_token'], unique=True)
    op.create_index('ix_hospital_reservations_facility_status', 'hospital_capacity_reservations', ['facility_id', 'status'])
    op.create_index('ix_hospital_reservations_incident', 'hospital_capacity_reservations', ['incident_id'])

    # 4. Create incoming_patient_requests table
    op.create_table(
        'incoming_patient_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_token', sa.String(length=36), nullable=False),
        sa.Column('facility_id', sa.Integer(), nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=True),
        sa.Column('dispatcher_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='pending', nullable=False),
        sa.Column('emergency_severity', sa.String(length=30), server_default='High', nullable=False),
        sa.Column('patient_condition_summary', sa.String(length=255), nullable=True),
        sa.Column('eta_minutes', sa.Float(), nullable=True),
        sa.Column('eta_source', sa.String(length=50), nullable=True),
        sa.Column('hospital_response_user_id', sa.Integer(), nullable=True),
        sa.Column('hospital_response_reason', sa.Text(), nullable=True),
        sa.Column('clarification_notes', sa.Text(), nullable=True),
        sa.Column('capacity_snapshot_json', sa.Text(), nullable=True),
        sa.Column('acknowledgement_deadline', sa.DateTime(), nullable=False),
        sa.Column('responded_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['assignment_id'], ['assignments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['dispatcher_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['facility_id'], ['hospital_facilities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['hospital_response_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_incoming_requests_token', 'incoming_patient_requests', ['request_token'], unique=True)
    op.create_index('ix_incoming_requests_facility_status', 'incoming_patient_requests', ['facility_id', 'status'])
    op.create_index('ix_incoming_requests_incident', 'incoming_patient_requests', ['incident_id'])

    # 5. Create hospital_diversion_logs table
    op.create_table(
        'hospital_diversion_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('facility_id', sa.Integer(), nullable=False),
        sa.Column('previous_status', sa.String(length=50), nullable=True),
        sa.Column('new_status', sa.String(length=50), nullable=False),
        sa.Column('diversion_type', sa.String(length=50), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('effective_from', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('effective_until', sa.DateTime(), nullable=True),
        sa.Column('authorized_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['authorized_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['facility_id'], ['hospital_facilities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_diversion_logs_facility', 'hospital_diversion_logs', ['facility_id', 'created_at'])


def downgrade() -> None:
    op.drop_table('hospital_diversion_logs')
    op.drop_table('incoming_patient_requests')
    op.drop_table('hospital_capacity_reservations')
    op.drop_table('hospital_capacities')
    op.drop_table('hospital_facilities')
