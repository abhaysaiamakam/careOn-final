"""m5_intelligent_dispatch_and_audit

Revision ID: e2026111805_m5
Revises: d2026111804_m4
Create Date: 2026-11-18 21:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2026111805_m5'
down_revision: Union[str, Sequence[str], None] = 'd2026111804_m4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add equipment and organization_id to resources table
    op.add_column(
        'resources',
        sa.Column('equipment', sa.String(length=255), server_default='oxygen,first_aid_kit', nullable=True)
    )
    op.add_column(
        'resources',
        sa.Column('organization_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_resources_organization_id',
        'resources',
        'organizations',
        ['organization_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_index(
        op.f('ix_resources_organization_id'),
        'resources',
        ['organization_id'],
        unique=False
    )

    # 2. Create dispatch_decisions table
    op.create_table(
        'dispatch_decisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('decision_id', sa.String(length=36), nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('recommendation_version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('candidates_json', sa.Text(), nullable=False),
        sa.Column('recommended_resource_id', sa.Integer(), nullable=True),
        sa.Column('selected_resource_id', sa.Integer(), nullable=False),
        sa.Column('dispatcher_id', sa.Integer(), nullable=True),
        sa.Column('dispatcher_name', sa.String(length=100), nullable=False),
        sa.Column('decision_type', sa.String(length=30), nullable=False),
        sa.Column('override_reason', sa.Text(), nullable=True),
        sa.Column('scoring_weights_version', sa.String(length=20), server_default='v1.0', nullable=False),
        sa.Column('eta_minutes', sa.Float(), nullable=True),
        sa.Column('eta_source', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['dispatcher_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recommended_resource_id'], ['resources.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['selected_resource_id'], ['resources.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_dispatch_decisions_id'), 'dispatch_decisions', ['id'], unique=False)
    op.create_index(op.f('ix_dispatch_decisions_decision_id'), 'dispatch_decisions', ['decision_id'], unique=True)
    op.create_index(op.f('ix_dispatch_decisions_incident_id'), 'dispatch_decisions', ['incident_id'], unique=False)
    op.create_index('ix_dispatch_decisions_incident', 'dispatch_decisions', ['incident_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_dispatch_decisions_incident', table_name='dispatch_decisions')
    op.drop_index(op.f('ix_dispatch_decisions_incident_id'), table_name='dispatch_decisions')
    op.drop_index(op.f('ix_dispatch_decisions_decision_id'), table_name='dispatch_decisions')
    op.drop_index(op.f('ix_dispatch_decisions_id'), table_name='dispatch_decisions')
    op.drop_table('dispatch_decisions')

    op.drop_index(op.f('ix_resources_organization_id'), table_name='resources')
    op.drop_constraint('fk_resources_organization_id', 'resources', type_='foreignkey')
    op.drop_column('resources', 'organization_id')
    op.drop_column('resources', 'equipment')
