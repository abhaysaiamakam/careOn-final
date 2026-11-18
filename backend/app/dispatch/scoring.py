"""
CareOn Milestone 5 — Explainable Candidate Scoring Engine.

Features:
- Configurable scoring weights
- Hard eligibility constraints enforced before scoring
- Capability match prioritised over proximity
- Transparent, deterministic mathematical scoring formula (0..100)
- Detailed per-candidate explanation comparing ranks
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models import Resource, Incident
from app.dispatch.assessment import IncidentAssessment
from app.dispatch.eligibility import check_resource_eligibility, parse_csv_set, EligibilityResult
from app.dispatch.routing import routing_engine, RoutingResult


@dataclass
class ScoringWeights:
    eta_weight: float = 0.45             # 45% of score from travel time
    capability_weight: float = 0.25      # 25% of score from capability alignment
    equipment_weight: float = 0.15       # 15% of score from equipment completeness
    freshness_weight: float = 0.15       # 15% of score from GPS telemetry freshness
    version: str = "v1.0"


@dataclass
class CandidateScore:
    resource_id: int
    resource_code: str
    resource_name: str
    category: str
    eligibility_status: str              # "eligible" or "ineligible"
    overall_score: float                 # 0.0 to 100.0
    eta_minutes: float
    eta_source: str                      # "osrm_road_network", "cache_osrm", "haversine_fallback"
    distance_km: float
    is_fallback_routing: bool
    capability_match: Dict[str, Any]
    equipment_match: Dict[str, Any]
    location_freshness_seconds: float
    conflicts_or_warnings: List[str]
    ineligibility_reasons: List[str]
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "resource_code": self.resource_code,
            "resource_name": self.resource_name,
            "category": self.category,
            "eligibility_status": self.eligibility_status,
            "overall_score": self.overall_score,
            "eta_minutes": self.eta_minutes,
            "eta_source": self.eta_source,
            "distance_km": self.distance_km,
            "is_fallback_routing": self.is_fallback_routing,
            "capability_match": self.capability_match,
            "equipment_match": self.equipment_match,
            "location_freshness_seconds": self.location_freshness_seconds,
            "conflicts_or_warnings": self.conflicts_or_warnings,
            "ineligibility_reasons": self.ineligibility_reasons,
            "explanation": self.explanation,
        }


def score_resource_candidate(
    resource: Resource,
    assessment: IncidentAssessment,
    incident: Incident,
    eligibility: EligibilityResult,
    routing: RoutingResult,
    weights: ScoringWeights = ScoringWeights(),
) -> CandidateScore:
    """
    Compute a deterministic, explainable score for a single resource candidate.
    """
    # If resource is ineligible, overall score is zeroed out
    if not eligibility.is_eligible:
        return CandidateScore(
            resource_id=resource.id,
            resource_code=resource.resource_code,
            resource_name=resource.name,
            category=resource.category,
            eligibility_status="ineligible",
            overall_score=0.0,
            eta_minutes=routing.eta_minutes,
            eta_source=routing.source,
            distance_km=routing.distance_km,
            is_fallback_routing=routing.is_fallback,
            capability_match={
                "missing": eligibility.missing_capabilities,
            },
            equipment_match={
                "missing": eligibility.missing_equipment,
            },
            location_freshness_seconds=0.0,
            conflicts_or_warnings=eligibility.warnings,
            ineligibility_reasons=eligibility.reasons,
            explanation=f"Ineligible candidate: {'; '.join(eligibility.reasons)}",
        )

    # 1. ETA Component (0..100): 1 min = 100, 30+ mins = 0
    # Formula: max(0, 100 - (eta_minutes - 1) * 3.4)
    eta_score = max(0.0, min(100.0, 100.0 - (routing.eta_minutes - 1.0) * 3.4))

    # 2. Capability Component (0..100)
    res_caps = parse_csv_set(resource.capabilities)
    req_caps = [c.lower() for c in assessment.required_capabilities]
    matched_caps = [c for c in req_caps if c in res_caps]
    cap_ratio = len(matched_caps) / max(1, len(req_caps))
    cap_score = cap_ratio * 100.0

    # 3. Equipment Component (0..100)
    res_equip = parse_csv_set(getattr(resource, "equipment", None)).union(res_caps)
    req_equip = [e.lower() for e in assessment.required_equipment]
    matched_equip = [e for e in req_equip if e in res_equip]
    equip_ratio = len(matched_equip) / max(1, len(req_equip))
    equip_score = equip_ratio * 100.0

    # 4. GPS Freshness Component (0..100)
    freshness_seconds = 0.0
    freshness_score = 100.0
    if resource.last_updated:
        now_dt = datetime.now(timezone.utc)
        up_dt = resource.last_updated
        if up_dt.tzinfo is None:
            up_dt = up_dt.replace(tzinfo=timezone.utc)
        freshness_seconds = max(0.0, (now_dt - up_dt).total_seconds())
        # Decay: 0s -> 100, 1800s (30m) -> 50, 3600s (60m) -> 0
        freshness_score = max(0.0, min(100.0, 100.0 - (freshness_seconds / 36.0)))

    # Weighted Overall Score
    raw_score = (
        (eta_score * weights.eta_weight)
        + (cap_score * weights.capability_weight)
        + (equip_score * weights.equipment_weight)
        + (freshness_score * weights.freshness_weight)
    )
    overall_score = round(max(0.0, min(100.0, raw_score)), 1)

    explanation = (
        f"Score {overall_score}/100: ETA ~{routing.eta_minutes}m ({routing.distance_km}km via {routing.source}) "
        f"[ETA score {eta_score:.1f}]; Capabilities matched {len(matched_caps)}/{len(req_caps)}; "
        f"Equipment matched {len(matched_equip)}/{len(req_equip)}; "
        f"GPS freshness {int(freshness_seconds)}s ago."
    )

    return CandidateScore(
        resource_id=resource.id,
        resource_code=resource.resource_code,
        resource_name=resource.name,
        category=resource.category,
        eligibility_status="eligible",
        overall_score=overall_score,
        eta_minutes=routing.eta_minutes,
        eta_source=routing.source,
        distance_km=routing.distance_km,
        is_fallback_routing=routing.is_fallback,
        capability_match={
            "required": assessment.required_capabilities,
            "matched": matched_caps,
            "missing": eligibility.missing_capabilities,
        },
        equipment_match={
            "required": assessment.required_equipment,
            "matched": matched_equip,
            "missing": eligibility.missing_equipment,
        },
        location_freshness_seconds=round(freshness_seconds, 1),
        conflicts_or_warnings=eligibility.warnings,
        ineligibility_reasons=[],
        explanation=explanation,
    )


def rank_candidates_for_incident(
    incident: Incident,
    assessment: IncidentAssessment,
    resources: List[Resource],
    db: Session,
    weights: ScoringWeights = ScoringWeights(),
) -> List[CandidateScore]:
    """
    Score and rank all candidate resources for an incident.
    Returns sorted list from highest scoring eligible candidate to lowest.
    Ineligible resources appear at the bottom with score 0.0 and clear reasons.
    """
    scored: List[CandidateScore] = []

    for res in resources:
        eligibility = check_resource_eligibility(res, assessment, db)
        routing = routing_engine.calculate_eta(
            from_lat=res.latitude,
            from_lon=res.longitude,
            to_lat=incident.latitude,
            to_lon=incident.longitude,
        )
        candidate = score_resource_candidate(
            resource=res,
            assessment=assessment,
            incident=incident,
            eligibility=eligibility,
            routing=routing,
            weights=weights,
        )
        scored.append(candidate)

    # Sort: Eligible first by overall_score descending, then ETA ascending
    scored.sort(
        key=lambda c: (
            1 if c.eligibility_status == "eligible" else 0,
            c.overall_score,
            -c.eta_minutes,
        ),
        reverse=True,
    )

    # Enhance explanations with comparative ranking reasoning
    for idx, c in enumerate(scored):
        if c.eligibility_status == "eligible":
            if idx == 0:
                c.explanation = f"🏆 Top Recommendation (Rank 1): {c.explanation}"
            else:
                better = scored[idx - 1]
                diff_reason = []
                if c.overall_score < better.overall_score:
                    if c.eta_minutes > better.eta_minutes:
                        diff_reason.append(f"+{round(c.eta_minutes - better.eta_minutes, 1)}m longer ETA")
                    if len(c.capability_match.get("missing", [])) > len(better.capability_match.get("missing", [])):
                        diff_reason.append("fewer matching capabilities")
                rationale = f" (ranked below {better.resource_name} due to {', '.join(diff_reason)})" if diff_reason else ""
                c.explanation = f"Rank {idx + 1}: {c.explanation}{rationale}"

    return scored
