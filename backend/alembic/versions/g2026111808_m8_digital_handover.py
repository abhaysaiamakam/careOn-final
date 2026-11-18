"""m8_digital_patient_handover_and_clinical_continuity

Revision ID: g2026111808_m8
Revises: f2026111807_m7
Create Date: 2026-11-18 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g2026111808_m8'
down_revision: Union[str, Sequence[str], None] = 'f2026111807_m7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create patients table
    op.create_table(
        'patients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_identifier', sa.String(length=40), nullable=False),
        sa.Column('full_name', sa.String(length=120), nullable=True),
        sa.Column('identity_status', sa.String(length=30), server_default='unknown', nullable=False),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('estimated_age', sa.Integer(), nullable=True),
        sa.Column('gender', sa.String(length=20), server_default='unknown', nullable=False),
        sa.Column('contact_phone', sa.String(length=30), nullable=True),
        sa.Column('emergency_contact_name', sa.String(length=100), nullable=True),
        sa.Column('emergency_contact_phone', sa.String(length=30), nullable=True),
        sa.Column('blood_group', sa.String(length=10), nullable=True),
        sa.Column('known_allergies', sa.Text(), nullable=True),
        sa.Column('known_medical_conditions', sa.Text(), nullable=True),
        sa.Column('current_medications', sa.Text(), nullable=True),
        sa.Column('history_verification_status', sa.String(length=30), server_default='unknown', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_patients_identifier', 'patients', ['patient_identifier'], unique=True)

    # 2. Create emergency_encounters table
    op.create_table(
        'emergency_encounters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('encounter_code', sa.String(length=40), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=True),
        sa.Column('assigned_responder_id', sa.Integer(), nullable=True),
        sa.Column('receiving_facility_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='active', nullable=False),
        sa.Column('chief_complaint', sa.String(length=255), nullable=False),
        sa.Column('initial_acuity', sa.String(length=30), server_default='High', nullable=False),
        sa.Column('started_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['assignment_id'], ['assignments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assigned_responder_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['receiving_facility_id'], ['hospital_facilities.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_encounters_code', 'emergency_encounters', ['encounter_code'], unique=True)
    op.create_index('ix_encounters_incident', 'emergency_encounters', ['incident_id'])
    op.create_index('ix_encounters_patient', 'emergency_encounters', ['patient_id'])

    # 3. Create clinical_assessments table
    op.create_table(
        'clinical_assessments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('encounter_id', sa.Integer(), nullable=False),
        sa.Column('responder_id', sa.Integer(), nullable=True),
        sa.Column('assessed_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('consciousness_level', sa.String(length=30), server_default='Alert', nullable=False),
        sa.Column('airway_status', sa.String(length=50), server_default='clear', nullable=False),
        sa.Column('breathing_status', sa.String(length=50), server_default='normal', nullable=False),
        sa.Column('circulation_status', sa.String(length=50), server_default='normal_pulses', nullable=False),
        sa.Column('presenting_complaints', sa.Text(), nullable=True),
        sa.Column('observed_injuries', sa.Text(), nullable=True),
        sa.Column('symptoms', sa.Text(), nullable=True),
        sa.Column('clinical_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['encounter_id'], ['emergency_encounters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['responder_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_assessments_encounter', 'clinical_assessments', ['encounter_id'])

    # 4. Create vital_sign_observations table
    op.create_table(
        'vital_sign_observations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('encounter_id', sa.Integer(), nullable=False),
        sa.Column('recorded_by_user_id', sa.Integer(), nullable=True),
        sa.Column('observed_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('heart_rate', sa.Integer(), nullable=True),
        sa.Column('systolic_bp', sa.Integer(), nullable=True),
        sa.Column('diastolic_bp', sa.Integer(), nullable=True),
        sa.Column('respiratory_rate', sa.Integer(), nullable=True),
        sa.Column('oxygen_saturation', sa.Float(), nullable=True),
        sa.Column('body_temperature', sa.Float(), nullable=True),
        sa.Column('blood_glucose', sa.Float(), nullable=True),
        sa.Column('gcs_eye', sa.Integer(), nullable=True),
        sa.Column('gcs_verbal', sa.Integer(), nullable=True),
        sa.Column('gcs_motor', sa.Integer(), nullable=True),
        sa.Column('gcs_total', sa.Integer(), nullable=True),
        sa.Column('measurement_source', sa.String(length=50), server_default='manual', nullable=False),
        sa.Column('data_quality', sa.String(length=30), server_default='verified', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['encounter_id'], ['emergency_encounters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recorded_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_vitals_encounter_time', 'vital_sign_observations', ['encounter_id', 'observed_at'])

    # 5. Create prehospital_interventions table
    op.create_table(
        'prehospital_interventions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('encounter_id', sa.Integer(), nullable=False),
        sa.Column('performer_id', sa.Integer(), nullable=True),
        sa.Column('intervention_type', sa.String(length=60), nullable=False),
        sa.Column('parameters_json', sa.Text(), nullable=True),
        sa.Column('patient_response', sa.String(length=50), server_default='unchanged', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('performed_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['encounter_id'], ['emergency_encounters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['performer_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_interventions_encounter', 'prehospital_interventions', ['encounter_id'])

    # 6. Create medication_administrations table
    op.create_table(
        'medication_administrations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('encounter_id', sa.Integer(), nullable=False),
        sa.Column('administering_user_id', sa.Integer(), nullable=True),
        sa.Column('medication_name', sa.String(length=100), nullable=False),
        sa.Column('dose', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=30), nullable=False),
        sa.Column('route', sa.String(length=50), nullable=False),
        sa.Column('response_notes', sa.Text(), nullable=True),
        sa.Column('verification_status', sa.String(length=30), server_default='administered', nullable=False),
        sa.Column('administered_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['administering_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['encounter_id'], ['emergency_encounters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_medications_encounter', 'medication_administrations', ['encounter_id'])

    # 7. Create clinical_timeline_events table
    op.create_table(
        'clinical_timeline_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_token', sa.String(length=36), nullable=False),
        sa.Column('encounter_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=60), nullable=False),
        sa.Column('event_timestamp', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('server_receipt_timestamp', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=True),
        sa.Column('actor_role', sa.String(length=30), nullable=False),
        sa.Column('structured_data_json', sa.Text(), nullable=True),
        sa.Column('source_application', sa.String(length=40), server_default='responder_mobile', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['encounter_id'], ['emergency_encounters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_timeline_event_token', 'clinical_timeline_events', ['event_token'], unique=True)
    op.create_index('ix_timeline_encounter_time', 'clinical_timeline_events', ['encounter_id', 'event_timestamp'])

    # 8. Create digital_handover_records table
    op.create_table(
        'digital_handover_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('handover_token', sa.String(length=36), nullable=False),
        sa.Column('encounter_id', sa.Integer(), nullable=False),
        sa.Column('facility_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('previous_version_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=40), server_default='draft', nullable=False),
        sa.Column('sending_responder_id', sa.Integer(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('receiving_staff_id', sa.Integer(), nullable=True),
        sa.Column('receiving_department', sa.String(length=100), nullable=True),
        sa.Column('received_at', sa.DateTime(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('clarification_notes', sa.Text(), nullable=True),
        sa.Column('correction_reason', sa.Text(), nullable=True),
        sa.Column('clinical_summary_json', sa.Text(), nullable=True),
        sa.Column('outstanding_clinical_concerns', sa.Text(), nullable=True),
        sa.Column('is_final', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['encounter_id'], ['emergency_encounters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['facility_id'], ['hospital_facilities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['previous_version_id'], ['digital_handover_records.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['receiving_staff_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['sending_responder_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_handover_token', 'digital_handover_records', ['handover_token'], unique=True)
    op.create_index('ix_handover_encounter_version', 'digital_handover_records', ['encounter_id', 'version'])
    op.create_index('ix_handover_facility_status', 'digital_handover_records', ['facility_id', 'status'])

    # 9. Create handover_attachments table
    op.create_table(
        'handover_attachments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('attachment_token', sa.String(length=36), nullable=False),
        sa.Column('encounter_id', sa.Integer(), nullable=False),
        sa.Column('handover_id', sa.Integer(), nullable=True),
        sa.Column('file_name', sa.String(length=150), nullable=False),
        sa.Column('file_type', sa.String(length=50), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False),
        sa.Column('storage_path', sa.String(length=255), nullable=False),
        sa.Column('uploaded_by_user_id', sa.Integer(), nullable=True),
        sa.Column('is_confidential', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['encounter_id'], ['emergency_encounters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['handover_id'], ['digital_handover_records.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['uploaded_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_attachments_token', 'handover_attachments', ['attachment_token'], unique=True)
    op.create_index('ix_attachments_encounter', 'handover_attachments', ['encounter_id'])


def downgrade() -> None:
    op.drop_table('handover_attachments')
    op.drop_table('digital_handover_records')
    op.drop_table('clinical_timeline_events')
    op.drop_table('medication_administrations')
    op.drop_table('prehospital_interventions')
    op.drop_table('vital_sign_observations')
    op.drop_table('clinical_assessments')
    op.drop_table('emergency_encounters')
    op.drop_table('patients')
