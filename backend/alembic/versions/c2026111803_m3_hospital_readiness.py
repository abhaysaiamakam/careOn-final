"""m3_hospital_readiness_and_responder_assignment

Revision ID: c2026111803_m3
Revises: b2026111802_m2
Create Date: 2026-11-18 20:48:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2026111803_m3'
down_revision: Union[str, Sequence[str], None] = 'b2026111802_m2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add assigned_user_id column to resources table
    op.add_column('resources', sa.Column('assigned_user_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_resources_assigned_user_id',
        'resources',
        'users',
        ['assigned_user_id'],
        ['id'],
    )

    # 2. Create hospital_readiness table
    op.create_table(
        'hospital_readiness',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('total_er_beds', sa.Integer(), server_default='20', nullable=False),
        sa.Column('available_er_beds', sa.Integer(), server_default='15', nullable=False),
        sa.Column('icu_beds_total', sa.Integer(), server_default='8', nullable=False),
        sa.Column('icu_beds_available', sa.Integer(), server_default='4', nullable=False),
        sa.Column('trauma_bays_total', sa.Integer(), server_default='4', nullable=False),
        sa.Column('trauma_bays_available', sa.Integer(), server_default='2', nullable=False),
        sa.Column('operating_rooms_total', sa.Integer(), server_default='3', nullable=False),
        sa.Column('operating_rooms_available', sa.Integer(), server_default='1', nullable=False),
        sa.Column('divert_status', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('divert_reason', sa.String(length=255), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', name='uq_hospital_readiness_org')
    )
    op.create_index(op.f('ix_hospital_readiness_id'), 'hospital_readiness', ['id'], unique=False)
    op.create_index(op.f('ix_hospital_readiness_organization_id'), 'hospital_readiness', ['organization_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_hospital_readiness_organization_id'), table_name='hospital_readiness')
    op.drop_index(op.f('ix_hospital_readiness_id'), table_name='hospital_readiness')
    op.drop_table('hospital_readiness')
    op.drop_constraint('fk_resources_assigned_user_id', 'resources', type_='foreignkey')
    op.drop_column('resources', 'assigned_user_id')
