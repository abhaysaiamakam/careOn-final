"""
CareOn Milestone 10 — Predictive Emergency Intelligence & Resource Positioning Router.

Namespace: /api/intelligence/v1
Provides decision-support endpoints for:
- Historical demand intelligence and temporal pattern analytics
- Geospatial hotspot clustering with privacy aggregation
- Configurable horizon temporal demand forecasting with uncertainty intervals
- Regional resource availability and predictive coverage gap analysis
- Ambulance strategic pre-positioning recommendation engine
- Dispatcher governance workflow (approve, reject, modify, execute)
- Isolated operational scenario simulation
- Model registry, evaluation against baseline, and health degradation monitoring
"""

import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    User,
    PositioningRecommendation,
    DemandForecastRecord,
    PositioningAuditLog,
)
from app.rbac.dependencies import get_current_user_flexible
from app.schemas import (
    DemandAnalyticsResponse,
    HotspotAnalysisRequest,
    HotspotAnalysisResponse,
    ForecastGenerateRequest,
    ForecastResponse,
    CoverageAnalysisRequest,
    ZoneCoverageResponse,
    PositioningRecommendRequest,
    PositioningRecommendationResponse,
    PositioningRecommendationReviewRequest,
    PositioningRecommendationRejectRequest,
    PositioningRecommendationModifyRequest,
    PositioningExecutionRequest,
    ScenarioSimulationRequest,
    ScenarioSimulationResponse,
    ModelRegistryResponse,
    ModelEvaluationRequest,
    ModelEvaluationResponse,
    ModelHealthResponse,
)
from app.intelligence.demand_analytics import analyze_historical_demand
from app.intelligence.hotspot_engine import analyze_geospatial_hotspots
from app.intelligence.forecasting_engine import (
    generate_demand_forecast,
    evaluate_model_chronologically,
)
from app.intelligence.coverage_engine import analyze_regional_coverage
from app.intelligence.positioning_optimizer import generate_positioning_recommendations
from app.intelligence.governance import (
    approve_positioning_recommendation,
    reject_positioning_recommendation,
    modify_positioning_recommendation,
    execute_positioning_recommendation,
)
from app.intelligence.scenario_simulator import simulate_operational_scenario
from app.intelligence.model_registry import (
    get_model_registry_list,
    check_intelligence_model_health,
)

router = APIRouter(prefix="/api/intelligence/v1", tags=["Predictive Intelligence & Resource Positioning"])


def _extract_user_organization(user: User) -> Optional[int]:
    """Helper to get user's primary organization id if multi-tenant."""
    if user.organization_memberships:
        return user.organization_memberships[0].organization_id
    return None


# ==============================================================================
# Historical Demand Analytics
# ==============================================================================

@router.get("/demand/analytics", response_model=DemandAnalyticsResponse)
def get_demand_analytics_endpoint(
    days: int = Query(30, ge=1, le=365),
    category: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Retrieve historical emergency demand intelligence:
    volume frequency, time-of-day/day-of-week patterns, category/severity distributions.
    Strictly excludes duplicates, cancelled, and test incidents.
    """
    org_id = _extract_user_organization(current_user)
    return analyze_historical_demand(db, days=days, organization_id=org_id, category=category)


# ==============================================================================
# Geospatial Hotspots Intelligence
# ==============================================================================

@router.post("/hotspots/analyze", response_model=HotspotAnalysisResponse)
def analyze_hotspots_endpoint(
    payload: HotspotAnalysisRequest,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Geospatial Hotspot Analysis using PostGIS spatial binning.
    Protects privacy via spatial aggregation; labels sparse data as statistically insufficient.
    """
    org_id = _extract_user_organization(current_user)
    return analyze_geospatial_hotspots(db, payload, organization_id=org_id)


# ==============================================================================
# Temporal Demand Forecasting
# ==============================================================================

@router.post("/forecasts/generate", response_model=ForecastResponse)
def generate_forecast_endpoint(
    payload: ForecastGenerateRequest,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Generate an operational demand forecast across configurable horizons (1h, 3h, 6h, 12h, 24h).
    Returns expected incident count, Poisson confidence intervals, and contributing factors.
    """
    if payload.horizon_hours not in [1, 3, 6, 12, 24]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Horizon {payload.horizon_hours}h is invalid. Must be 1, 3, 6, 12, or 24.",
        )
    org_id = _extract_user_organization(current_user)
    return generate_demand_forecast(db, payload, organization_id=org_id)


@router.get("/forecasts/history", response_model=List[ForecastResponse])
def get_forecast_history_endpoint(
    zone_or_region: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Query persisted operational demand forecast history.
    """
    org_id = _extract_user_organization(current_user)
    query = db.query(DemandForecastRecord)
    if org_id:
        query = query.filter(DemandForecastRecord.organization_id == org_id)
    if zone_or_region:
        query = query.filter(DemandForecastRecord.zone_or_region == zone_or_region)

    records = query.order_by(DemandForecastRecord.created_at.desc()).limit(limit).all()
    results = []
    for r in records:
        cats = json.loads(r.category_breakdown_json) if r.category_breakdown_json else {}
        factors = json.loads(r.contributing_factors_json) if r.contributing_factors_json else []
        results.append(
            ForecastResponse(
                forecast_uuid=r.forecast_uuid,
                zone_or_region=r.zone_or_region,
                horizon_hours=r.horizon_hours,
                start_time=r.start_time,
                end_time=r.end_time,
                expected_incidents=r.expected_incidents,
                confidence_lower=r.confidence_lower,
                confidence_upper=r.confidence_upper,
                confidence_level=r.confidence_level,
                category_breakdown=cats,
                model_id=r.model_id,
                model_version=r.model_version,
                historical_sample_size=r.historical_sample_size,
                data_freshness_seconds=r.data_freshness_seconds,
                contributing_factors=factors,
                created_at=r.created_at,
            )
        )
    return results


# ==============================================================================
# Regional Coverage Analysis & Gap Detection
# ==============================================================================

@router.post("/coverage/analyze", response_model=List[ZoneCoverageResponse])
def analyze_coverage_endpoint(
    payload: CoverageAnalysisRequest,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Analyze regional ambulance coverage, travel times, and identify coverage gaps.
    Strictly excludes occupied ambulances and stale GPS telemetry (>15 mins).
    """
    org_id = _extract_user_organization(current_user)
    return analyze_regional_coverage(db, payload, organization_id=org_id)


# ==============================================================================
# Strategic Positioning Recommender
# ==============================================================================

def _format_rec_response(rec: PositioningRecommendation) -> PositioningRecommendationResponse:
    alts = json.loads(rec.alternative_resource_ids_json) if rec.alternative_resource_ids_json else []
    res_code = rec.resource.resource_code if rec.resource else f"Res-{rec.resource_id}"
    return PositioningRecommendationResponse(
        id=rec.id,
        recommendation_uuid=rec.recommendation_uuid,
        target_area=rec.target_area,
        target_latitude=rec.target_latitude,
        target_longitude=rec.target_longitude,
        resource_id=rec.resource_id,
        resource_code=res_code,
        current_latitude=rec.current_latitude,
        current_longitude=rec.current_longitude,
        proposed_latitude=rec.proposed_latitude,
        proposed_longitude=rec.proposed_longitude,
        proposed_staging_name=rec.proposed_staging_name,
        status=rec.status,
        expected_coverage_improvement=rec.expected_coverage_improvement,
        estimated_travel_time_minutes=rec.estimated_travel_time_minutes,
        confidence_level=rec.confidence_level,
        explanation=rec.explanation,
        alternative_resources=alts,
        expires_at=rec.expires_at,
        reviewed_by_user_id=rec.reviewed_by_user_id,
        reviewed_at=rec.reviewed_at,
        rejection_reason=rec.rejection_reason,
        modification_notes=rec.modification_notes,
        execution_status=rec.execution_status,
        model_id=rec.model_id,
        model_version=rec.model_version,
        created_at=rec.created_at,
    )


@router.post("/recommendations/generate", response_model=List[PositioningRecommendationResponse])
def generate_recommendations_endpoint(
    payload: PositioningRecommendRequest,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Generate strategic ambulance pre-positioning recommendations.
    Balancing demand coverage, travel time, and adjacent region preservation.
    """
    org_id = _extract_user_organization(current_user)
    recs = generate_positioning_recommendations(db, payload, organization_id=org_id)
    return [_format_rec_response(r) for r in recs]


@router.get("/recommendations", response_model=List[PositioningRecommendationResponse])
def list_recommendations_endpoint(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    List ambulance positioning recommendations with optional status filtering.
    """
    org_id = _extract_user_organization(current_user)
    query = db.query(PositioningRecommendation)
    if org_id:
        query = query.filter(PositioningRecommendation.organization_id == org_id)
    if status_filter:
        query = query.filter(PositioningRecommendation.status == status_filter)

    recs = query.order_by(PositioningRecommendation.created_at.desc()).limit(limit).all()
    return [_format_rec_response(r) for r in recs]


@router.get("/recommendations/{recommendation_id}", response_model=PositioningRecommendationResponse)
def get_recommendation_details_endpoint(
    recommendation_id: int,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Retrieve single recommendation details.
    """
    rec = db.query(PositioningRecommendation).filter(PositioningRecommendation.id == recommendation_id).first()
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation {recommendation_id} not found.",
        )
    return _format_rec_response(rec)


# ==============================================================================
# Human Dispatcher Governance (Approve / Reject / Modify / Execute)
# ==============================================================================

@router.post("/recommendations/{recommendation_id}/approve", response_model=PositioningRecommendationResponse)
def approve_recommendation_endpoint(
    recommendation_id: int,
    payload: PositioningRecommendationReviewRequest,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Dispatcher approval of an ambulance positioning recommendation.
    Emits an OutboxEvent for real-time WebSocket notification.
    """
    rec = approve_positioning_recommendation(db, recommendation_id, current_user, payload)
    return _format_rec_response(rec)


@router.post("/recommendations/{recommendation_id}/reject", response_model=PositioningRecommendationResponse)
def reject_recommendation_endpoint(
    recommendation_id: int,
    payload: PositioningRecommendationRejectRequest,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Dispatcher rejection of an ambulance positioning recommendation with mandatory reason.
    """
    rec = reject_positioning_recommendation(db, recommendation_id, current_user, payload)
    return _format_rec_response(rec)


@router.post("/recommendations/{recommendation_id}/modify", response_model=PositioningRecommendationResponse)
def modify_recommendation_endpoint(
    recommendation_id: int,
    payload: PositioningRecommendationModifyRequest,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Dispatcher modification of proposed staging coordinates, staging name, or resource.
    """
    rec = modify_positioning_recommendation(db, recommendation_id, current_user, payload)
    return _format_rec_response(rec)


@router.post("/recommendations/{recommendation_id}/execute", response_model=PositioningRecommendationResponse)
def execute_recommendation_endpoint(
    recommendation_id: int,
    payload: PositioningExecutionRequest,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Transition approved recommendation into execution tracking.
    """
    rec = execute_positioning_recommendation(db, recommendation_id, current_user, payload)
    return _format_rec_response(rec)


# ==============================================================================
# Operational Scenario Simulation
# ==============================================================================

@router.post("/scenarios/simulate", response_model=ScenarioSimulationResponse)
def simulate_scenario_endpoint(
    payload: ScenarioSimulationRequest,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Execute an isolated operational scenario simulation (Surge, Shortage, MCI, Diversion).
    STRICT INVARIANT: Never mutates live missions, assignments, reservations, or clinical data.
    """
    org_id = _extract_user_organization(current_user)
    return simulate_operational_scenario(db, payload, user=current_user, organization_id=org_id)


# ==============================================================================
# Model Catalog, Evaluation & Monitoring
# ==============================================================================

@router.get("/models", response_model=List[ModelRegistryResponse])
def get_models_endpoint(
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Retrieve model catalog, active model, candidate versions, and baseline metrics.
    """
    return get_model_registry_list(db)


@router.post("/models/evaluate", response_model=ModelEvaluationResponse)
def evaluate_model_endpoint(
    payload: ModelEvaluationRequest,
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Evaluate candidate model performance against the seasonal baseline using chronological splitting.
    """
    log = evaluate_model_chronologically(db, payload.candidate_model_id, payload.validation_days)
    rec_text = (
        "Model successfully outperformed baseline; eligible for activation."
        if log.outperformed_baseline
        else "Model did not beat seasonal baseline; retain production baseline."
    )
    return ModelEvaluationResponse(
        model_id=log.model_id,
        model_version=log.model_version,
        sample_count=log.sample_count,
        mae=log.mae,
        rmse=log.rmse,
        forecast_bias=log.forecast_bias,
        poisson_deviance=log.poisson_deviance,
        baseline_mae=log.baseline_mae,
        baseline_rmse=log.baseline_rmse,
        outperformed_baseline=log.outperformed_baseline,
        can_activate=log.outperformed_baseline,
        recommendation=rec_text,
    )


@router.get("/models/health", response_model=ModelHealthResponse)
def get_model_health_endpoint(
    current_user: User = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    Monitor intelligence model health, data freshness, and degradation status.
    """
    return check_intelligence_model_health(db)
