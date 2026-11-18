"""
CareOn Milestone 5 — Resource Capability & Eligibility Engine.

Evaluates:
- Availability: status == "Available" AND no active DB assignment
- Capability match: hard constraints for incident requirements
- Equipment match: hard constraints for life-support / critical equipment
- Location Freshness: max staleness threshold check (e.g. 1800s / 30m)
- Operational constraints & organizational boundaries

Only eligible resources may enter the dispatch recommendation pool.
Incompatible, committed, or stale-location resources are excluded or flagged.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from sqlalchemy.orm import Session

from app.models import Resource, Assignment, Incident
from app.dispatch.assessment import IncidentAssessment

# Maximum allowable staleness for GPS before marking ineligible (in seconds)
# Operational freshness thresholds:
# <= 300s (5m): VERIFIED_LIVE
# 300s - 900s (5-15m): AGING
# 900s - 1800s (15-30m): STALE
# > 1800s (30m): UNKNOWN_OR_EXPIRED (Ineligible for emergency dispatch)
MAX_STALE_GPS_SECONDS = 1800      # 30 minutes hard cutoff
WARNING_STALE_GPS_SECONDS = 300   # 5 minutes warning


class LocationFreshnessStatus:
    VERIFIED_LIVE = "verified_live"
    AGING = "aging"
    STALE = "stale"
    UNKNOWN_OR_EXPIRED = "unknown_or_expired"


def determine_location_freshness(last_updated: Optional[datetime]) -> Tuple[str, float]:
    """Return (freshness_status, age_in_seconds)."""
    if not last_updated:
        return LocationFreshnessStatus.UNKNOWN_OR_EXPIRED, float("inf")

    now_dt = datetime.now(timezone.utc)
    res_dt = last_updated
    if res_dt.tzinfo is None:
        res_dt = res_dt.replace(tzinfo=timezone.utc)

    age_seconds = max(0.0, (now_dt - res_dt).total_seconds())
    if age_seconds <= 300:
        return LocationFreshnessStatus.VERIFIED_LIVE, age_seconds
    elif age_seconds <= 900:
        return LocationFreshnessStatus.AGING, age_seconds
    elif age_seconds <= 1800:
        return LocationFreshnessStatus.STALE, age_seconds
    else:
        return LocationFreshnessStatus.UNKNOWN_OR_EXPIRED, age_seconds


@dataclass
class EligibilityResult:
    resource_id: int
    resource_code: str
    resource_name: str
    category: str
    is_eligible: bool
    reasons: List[str]
    missing_capabilities: List[str]
    missing_equipment: List[str]
    is_stale_gps: bool
    freshness_status: str = LocationFreshnessStatus.VERIFIED_LIVE
    warnings: List[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "resource_id": self.resource_id,
            "resource_code": self.resource_code,
            "resource_name": self.resource_name,
            "category": self.category,
            "is_eligible": self.is_eligible,
            "reasons": self.reasons,
            "missing_capabilities": self.missing_capabilities,
            "missing_equipment": self.missing_equipment,
            "is_stale_gps": self.is_stale_gps,
            "freshness_status": self.freshness_status,
            "warnings": self.warnings,
        }


def parse_csv_set(val: Optional[str]) -> Set[str]:
    """Parse comma-separated string into lowercase normalized set."""
    if not val:
        return set()
    return {item.strip().lower() for item in val.split(",") if item.strip()}


def check_resource_eligibility(
    resource: Resource,
    assessment: IncidentAssessment,
    db: Session,
    max_stale_seconds: int = MAX_STALE_GPS_SECONDS,
) -> EligibilityResult:
    """
    Evaluate if a candidate resource satisfies all hard eligibility constraints
    for a given assessed emergency.
    """
    reasons: List[str] = []
    warnings: List[str] = []
    missing_caps: List[str] = []
    missing_equip: List[str] = []
    is_eligible = True

    # 1. Availability Status Check
    if resource.status != "Available":
        is_eligible = False
        reasons.append(f"Resource status is '{resource.status}' (must be 'Available').")

    # 2. Active Assignment DB Check
    active_assignment = (
        db.query(Assignment)
        .filter(Assignment.resource_id == resource.id, Assignment.status == "Active")
        .first()
    )
    if active_assignment:
        is_eligible = False
        reasons.append(
            f"Resource is actively committed to mission on incident #{active_assignment.incident_id}."
        )

    # 3. Location Freshness Check
    freshness_status, age_seconds = determine_location_freshness(resource.last_updated)
    is_stale = freshness_status in (LocationFreshnessStatus.STALE, LocationFreshnessStatus.UNKNOWN_OR_EXPIRED)

    if freshness_status == LocationFreshnessStatus.UNKNOWN_OR_EXPIRED:
        is_eligible = False
        reasons.append(
            f"GPS telemetry is stale / expired ({int(age_seconds // 60)} mins old, cutoff {max_stale_seconds // 60} mins)."
        )
    elif freshness_status == LocationFreshnessStatus.STALE:
        warnings.append(
            f"GPS telemetry is stale ({int(age_seconds // 60)} mins old, re-verification recommended)."
        )
    elif freshness_status == LocationFreshnessStatus.AGING:
        warnings.append(
            f"GPS telemetry is aging ({int(age_seconds // 60)} mins old)."
        )

    # 4. Capability Match (Hard Constraints)
    resource_caps = parse_csv_set(resource.capabilities)
    for required_cap in assessment.required_capabilities:
        req_norm = required_cap.strip().lower()
        if req_norm not in resource_caps:
            # Check critical life-saving capabilities as hard exclusions
            if req_norm in ("als", "fire_suppression", "search_and_rescue", "extrication", "heavy_rescue"):
                is_eligible = False
                missing_caps.append(required_cap)
                reasons.append(f"Lacks mandatory capability '{required_cap}'.")
            else:
                # Soft capability deficit
                missing_caps.append(required_cap)
                warnings.append(f"Missing preferred capability '{required_cap}'.")

    # 5. Equipment Match (Hard Constraints)
    resource_equipment = parse_csv_set(getattr(resource, "equipment", None))
    # If equipment column is empty, check capabilities for equipment tags
    combined_equipment = resource_equipment.union(resource_caps)

    for required_eq in assessment.required_equipment:
        eq_norm = required_eq.strip().lower()
        if eq_norm not in combined_equipment:
            if assessment.severity == "Life-Threatening" and eq_norm in ("defibrillator", "ventilator", "als_kit"):
                is_eligible = False
                missing_equip.append(required_eq)
                reasons.append(f"Lacks life-critical equipment '{required_eq}'.")
            else:
                missing_equip.append(required_eq)
                warnings.append(f"Missing recommended equipment '{required_eq}'.")

    if is_eligible and not reasons:
        reasons.append("Resource meets all availability, capability, and operational constraints.")

    return EligibilityResult(
        resource_id=resource.id,
        resource_code=resource.resource_code,
        resource_name=resource.name,
        category=resource.category,
        is_eligible=is_eligible,
        reasons=reasons,
        missing_capabilities=missing_caps,
        missing_equipment=missing_equip,
        is_stale_gps=is_stale,
        freshness_status=freshness_status,
        warnings=warnings,
    )


def filter_eligible_resources(
    resources: List[Resource],
    assessment: IncidentAssessment,
    db: Session,
) -> Tuple[List[Resource], List[EligibilityResult]]:
    """
    Partition resources into eligible candidates and audit results for all resources.
    """
    eligible_resources: List[Resource] = []
    evaluations: List[EligibilityResult] = []

    for res in resources:
        eval_result = check_resource_eligibility(res, assessment, db)
        evaluations.append(eval_result)
        if eval_result.is_eligible:
            eligible_resources.append(res)

    return eligible_resources, evaluations
