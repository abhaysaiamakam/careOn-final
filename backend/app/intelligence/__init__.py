"""
CareOn Milestone 10 — Predictive Emergency Intelligence & Resource Positioning Engine.
"""

from app.intelligence.demand_analytics import (
    analyze_historical_demand,
    get_clean_historical_incidents_query,
)
from app.intelligence.hotspot_engine import (
    analyze_geospatial_hotspots,
)
from app.intelligence.forecasting_engine import (
    generate_demand_forecast,
    evaluate_model_chronologically,
    calculate_poisson_uncertainty_interval,
    calculate_empirical_interval_coverage,
    RollingAverageBaseline,
    SeasonalBaselineModel,
    PoissonRegressionModel,
    MODELS,
)
from app.intelligence.coverage_engine import (
    analyze_regional_coverage,
    get_available_operational_ambulances,
    is_resource_telemetry_fresh,
    DEFAULT_OPERATIONAL_ZONES,
)
from app.intelligence.positioning_optimizer import (
    generate_positioning_recommendations,
)
from app.intelligence.governance import (
    approve_positioning_recommendation,
    reject_positioning_recommendation,
    modify_positioning_recommendation,
    execute_positioning_recommendation,
    verify_resource_eligibility_for_positioning,
)
from app.intelligence.scenario_simulator import (
    simulate_operational_scenario,
)
from app.intelligence.model_registry import (
    get_model_registry_list,
    check_intelligence_model_health,
    seed_default_model_registry,
)
from app.intelligence.worker import (
    execute_intelligence_maintenance_cycle,
)

__all__ = [
    "analyze_historical_demand",
    "get_clean_historical_incidents_query",
    "analyze_geospatial_hotspots",
    "generate_demand_forecast",
    "evaluate_model_chronologically",
    "RollingAverageBaseline",
    "SeasonalBaselineModel",
    "PoissonRegressionModel",
    "MODELS",
    "analyze_regional_coverage",
    "get_available_operational_ambulances",
    "is_resource_telemetry_fresh",
    "DEFAULT_OPERATIONAL_ZONES",
    "generate_positioning_recommendations",
    "approve_positioning_recommendation",
    "reject_positioning_recommendation",
    "modify_positioning_recommendation",
    "execute_positioning_recommendation",
    "simulate_operational_scenario",
    "get_model_registry_list",
    "check_intelligence_model_health",
    "seed_default_model_registry",
    "execute_intelligence_maintenance_cycle",
]
