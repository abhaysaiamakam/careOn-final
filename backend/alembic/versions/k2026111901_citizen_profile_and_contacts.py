"""citizen_profile_and_contacts

Revision ID: k2026111901_citizen
Revises: j2026111811_m11
Create Date: 2026-11-19 21:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'k2026111901_citizen'
down_revision: Union[str, Sequence[str], None] = 'j2026111811_m11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create citizen_profiles table
    op.create_table(
        'citizen_profiles',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('dob', sa.String(length=20), nullable=True),
        sa.Column('preferred_language', sa.String(length=10), server_default='en', nullable=False),
        sa.Column('profile_photo_url', sa.String(length=255), nullable=True),
        # Residential
        sa.Column('residential_address', sa.Text(), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('pincode', sa.String(length=20), nullable=True),
        sa.Column('landmark', sa.String(length=255), nullable=True),
        sa.Column('home_latitude', sa.Float(), nullable=True),
        sa.Column('home_longitude', sa.Float(), nullable=True),
        # Medical
        sa.Column('blood_group', sa.String(length=10), nullable=True),
        sa.Column('allergies', sa.Text(), nullable=True),
        sa.Column('medical_conditions', sa.Text(), nullable=True),
        sa.Column('medications', sa.Text(), nullable=True),
        sa.Column('accessibility_needs', sa.Text(), nullable=True),
        sa.Column('is_medical_verified', sa.Boolean(), server_default='false', nullable=False),
        # Onboarding progress
        sa.Column('onboarding_completed', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('onboarding_step', sa.Integer(), server_default='1', nullable=False),
        sa.Column('consent_data_sharing', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('consent_emergency_contact', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_citizen_profiles_id', 'citizen_profiles', ['id'])
    op.create_index('ix_citizen_profiles_user_id', 'citizen_profiles', ['user_id'], unique=True)

    # 2. Create citizen_emergency_contacts table
    op.create_table(
        'citizen_emergency_contacts',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('relationship_type', sa.String(length=50), nullable=False),
        sa.Column('phone', sa.String(length=30), nullable=False),
        sa.Column('is_primary', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_citizen_emergency_contacts_id', 'citizen_emergency_contacts', ['id'])
    op.create_index('ix_citizen_emergency_contacts_user_id', 'citizen_emergency_contacts', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_citizen_emergency_contacts_user_id', table_name='citizen_emergency_contacts')
    op.drop_index('ix_citizen_emergency_contacts_id', table_name='citizen_emergency_contacts')
    op.drop_table('citizen_emergency_contacts')

    op.drop_index('ix_citizen_profiles_user_id', table_name='citizen_profiles')
    op.drop_index('ix_citizen_profiles_id', table_name='citizen_profiles')
    op.drop_table('citizen_profiles')
