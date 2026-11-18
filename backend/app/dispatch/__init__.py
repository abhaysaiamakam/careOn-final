"""
CareOn Milestone 5 — Intelligent Dispatch & Resource Optimization Engine Package.
"""

from app.dispatch.assessment import assess_incident, IncidentAssessment
from app.dispatch.routing import routing_engine, RoutingResult
from app.dispatch.eligibility import check_resource_eligibility, filter_eligible_resources, EligibilityResult
from app.dispatch.scoring import score_resource_candidate, rank_candidates_for_incident, CandidateScore, ScoringWeights
from app.dispatch.optimizer import optimize_multi_incident_dispatch, MultiIncidentOptimizationPlan
from app.dispatch.diversion import (
    get_hospital_diversion_status,
    set_hospital_diversion_status,
    recommend_destination_hospitals,
    HospitalDestinationCandidate,
)
from app.dispatch.approval import process_dispatch_decision

__all__ = [
    "assess_incident",
    "IncidentAssessment",
    "routing_engine",
    "RoutingResult",
    "check_resource_eligibility",
    "filter_eligible_resources",
    "EligibilityResult",
    "score_resource_candidate",
    "rank_candidates_for_incident",
    "CandidateScore",
    "ScoringWeights",
    "optimize_multi_incident_dispatch",
    "MultiIncidentOptimizationPlan",
    "get_hospital_diversion_status",
    "set_hospital_diversion_status",
    "recommend_destination_hospitals",
    "HospitalDestinationCandidate",
    "process_dispatch_decision",
]
