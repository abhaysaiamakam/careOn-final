"""m10_predictive_intelligence_and_resource_positioning

Revision ID: i2026111810_m10
Revises: h2026111809_m9
Create Date: 2026-11-18 23:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry


# revision identifiers, used by Alembic.
revision: str = 'i2026111810_m10'
down_revision: Union[str, Sequence[str], None] = 'h2026111809_m9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create demand_forecast_records table
    op.create_table(
        'demand_forecast_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('forecast_uuid', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('zone_or_region', sa.String(length=100), nullable=False),
        sa.Column('horizon_hours', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('expected_incidents', sa.Float(), nullable=False),
        sa.Column('confidence_lower', sa.Float(), nullable=False),
        sa.Column('confidence_upper', sa.Float(), nullable=False),
        sa.Column('confidence_level', sa.String(length=30), server_default='MEDIUM', nullable=False),
        sa.Column('category_breakdown_json', sa.Text(), nullable=True),
        sa.Column('model_id', sa.String(length=64), nullable=False),
        sa.Column('model_version', sa.String(length=32), nullable=False),
        sa.Column('historical_sample_size', sa.Integer(), server_default='0', nullable=False),
        sa.Column('data_freshness_seconds', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('contributing_factors_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_forecast_uuid', 'demand_forecast_records', ['forecast_uuid'], unique=True)
    op.create_index('ix_forecast_org_id', 'demand_forecast_records', ['organization_id'])
    op.create_index('ix_forecast_zone', 'demand_forecast_records', ['zone_or_region'])
    op.create_index('ix_forecast_zone_time', 'demand_forecast_records', ['zone_or_region', 'start_time', 'end_time'])

    # 2. Create predictive_model_registry table
    op.create_table(
        'predictive_model_registry',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.String(length=64), nullable=False),
        sa.Column('model_name', sa.String(length=120), nullable=False),
        sa.Column('model_type', sa.String(length=50), nullable=False),
        sa.Column('version', sa.String(length=32), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('feature_schema_version', sa.String(length=20), server_default='v1.0', nullable=False),
        sa.Column('training_start', sa.DateTime(), nullable=True),
        sa.Column('training_end', sa.DateTime(), nullable=True),
        sa.Column('sample_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('mae', sa.Float(), nullable=True),
        sa.Column('rmse', sa.Float(), nullable=True),
        sa.Column('forecast_bias', sa.Float(), nullable=True),
        sa.Column('poisson_deviance', sa.Float(), nullable=True),
        sa.Column('parameters_json', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='CANDIDATE', nullable=False),
        sa.Column('last_evaluated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_predictive_model_registry_model_id', 'predictive_model_registry', ['model_id'], unique=True)

    # 3. Create model_evaluation_logs table
    op.create_table(
        'model_evaluation_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('log_uuid', sa.String(length=36), nullable=False),
        sa.Column('model_id', sa.String(length=64), nullable=False),
        sa.Column('model_version', sa.String(length=32), nullable=False),
        sa.Column('evaluation_dataset_start', sa.DateTime(), nullable=True),
        sa.Column('evaluation_dataset_end', sa.DateTime(), nullable=True),
        sa.Column('sample_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('mae', sa.Float(), nullable=False),
        sa.Column('rmse', sa.Float(), nullable=False),
        sa.Column('forecast_bias', sa.Float(), nullable=False),
        sa.Column('poisson_deviance', sa.Float(), nullable=True),
        sa.Column('baseline_mae', sa.Float(), nullable=False),
        sa.Column('baseline_rmse', sa.Float(), nullable=False),
        sa.Column('outperformed_baseline', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_model_evaluation_logs_uuid', 'model_evaluation_logs', ['log_uuid'], unique=True)
    op.create_index('ix_model_evaluation_logs_model_id', 'model_evaluation_logs', ['model_id'])

    # 4. Create positioning_recommendations table
    op.create_table(
        'positioning_recommendations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recommendation_uuid', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('target_area', sa.String(length=120), nullable=False),
        sa.Column('target_latitude', sa.Float(), nullable=False),
        sa.Column('target_longitude', sa.Float(), nullable=False),
        sa.Column('target_geom', Geometry(geometry_type='POINT', srid=4326, spatial_index=False), nullable=True),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('current_latitude', sa.Float(), nullable=False),
        sa.Column('current_longitude', sa.Float(), nullable=False),
        sa.Column('proposed_latitude', sa.Float(), nullable=False),
        sa.Column('proposed_longitude', sa.Float(), nullable=False),
        sa.Column('proposed_staging_geom', Geometry(geometry_type='POINT', srid=4326, spatial_index=False), nullable=True),
        sa.Column('proposed_staging_name', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=40), server_default='PENDING_REVIEW', nullable=False),
        sa.Column('expected_coverage_improvement', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('estimated_travel_time_minutes', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('demand_forecast_summary_json', sa.Text(), nullable=True),
        sa.Column('alternative_resource_ids_json', sa.Text(), nullable=True),
        sa.Column('confidence_level', sa.String(length=20), server_default='MEDIUM', nullable=False),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('reviewed_by_user_id', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('modification_notes', sa.Text(), nullable=True),
        sa.Column('execution_requested_at', sa.DateTime(), nullable=True),
        sa.Column('execution_status', sa.String(length=40), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('model_id', sa.String(length=64), nullable=True),
        sa.Column('model_version', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_positioning_recommendations_uuid', 'positioning_recommendations', ['recommendation_uuid'], unique=True)
    op.create_index('ix_positioning_recommendations_org_id', 'positioning_recommendations', ['organization_id'])
    op.create_index('ix_positioning_recommendations_resource_id', 'positioning_recommendations', ['resource_id'])
    op.create_index('ix_positioning_recommendations_status', 'positioning_recommendations', ['status'])
    op.create_index('ix_positioning_recommendations_expires', 'positioning_recommendations', ['expires_at'])
    op.create_index('ix_recommendation_status_expires', 'positioning_recommendations', ['status', 'expires_at'])

    # 5. Create positioning_audit_logs table
    op.create_table(
        'positioning_audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('log_uuid', sa.String(length=36), nullable=False),
        sa.Column('recommendation_id', sa.Integer(), nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('previous_status', sa.String(length=40), nullable=True),
        sa.Column('new_status', sa.String(length=40), nullable=False),
        sa.Column('details_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['recommendation_id'], ['positioning_recommendations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_positioning_audit_logs_uuid', 'positioning_audit_logs', ['log_uuid'], unique=True)
    op.create_index('ix_positioning_audit_logs_rec_id', 'positioning_audit_logs', ['recommendation_id'])

    # 6. Create scenario_simulation_records table
    op.create_table(
        'scenario_simulation_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('simulation_uuid', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('scenario_type', sa.String(length=60), nullable=False),
        sa.Column('scenario_name', sa.String(length=150), nullable=False),
        sa.Column('parameters_json', sa.Text(), nullable=False),
        sa.Column('results_summary_json', sa.Text(), nullable=False),
        sa.Column('coverage_impact_json', sa.Text(), nullable=False),
        sa.Column('bottleneck_alerts_json', sa.Text(), nullable=False),
        sa.Column('simulated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['simulated_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scenario_simulation_records_uuid', 'scenario_simulation_records', ['simulation_uuid'], unique=True)
    op.create_index('ix_scenario_simulation_records_org_id', 'scenario_simulation_records', ['organization_id'])

    # 7. Create coverage_snapshot_records table
    op.create_table(
        'coverage_snapshot_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('snapshot_uuid', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('zone_or_region', sa.String(length=100), nullable=False),
        sa.Column('operational_resources_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('available_resources_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('forecasted_demand', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('coverage_ratio', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('avg_travel_time_minutes', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('is_gap', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('threshold_travel_time_minutes', sa.Float(), server_default='15.0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_coverage_snapshot_records_uuid', 'coverage_snapshot_records', ['snapshot_uuid'], unique=True)
    op.create_index('ix_coverage_snapshot_records_org_id', 'coverage_snapshot_records', ['organization_id'])
    op.create_index('ix_coverage_snapshot_records_zone', 'coverage_snapshot_records', ['zone_or_region'])
    op.create_index('ix_coverage_zone_created', 'coverage_snapshot_records', ['zone_or_region', 'created_at'])


def downgrade() -> None:
    op.drop_table('coverage_snapshot_records')
    op.drop_table('scenario_simulation_records')
    op.drop_table('positioning_audit_logs')
    op.drop_table('positioning_recommendations')
    op.drop_table('model_evaluation_logs')
    op.drop_table('predictive_model_registry')
    op.drop_table('demand_forecast_records')
