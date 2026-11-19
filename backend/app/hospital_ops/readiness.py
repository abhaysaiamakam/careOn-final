"""
CareOn Milestone 7 — Hospital Readiness Assessment & Destination Scoring Engine.

Evaluates:
- Facility operating status & diversion state
- Emergency department & ICU capacity
- Trauma capabilities matching incident severity
- Equipment & specialist availability
- Capacity freshness / confidence classification
- Current incoming patient workload
- Travel distance and OSRM road-network ETA
- Pre-arrival confirmation status

Produces explainable suitability classifications:
- SUITABLE_CONFIRMED
- SUITABLE_RECENT
- POTENTIALLY_SUITABLE_UNCONFIRMED
- CAPACITY_UNAVAILABLE
- CAPABILITY_UNAVAILABLE
- DIVERTED
- UNKNOWN_INSUFFICIENT_INFO
"""

import os
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models import (
    HospitalFacility,
    HospitalCapacity,
    IncomingPatientRequest,
    Incident,
    utc_now,
)
from app.dispatch.routing import routing_engine, RoutingResult
from app.hospital_ops.capacity import (
    CapacityCategory,
    CapacityFreshnessStatus,
    calculate_capacity_freshness,
    get_facility_capacity_summary,
)
from app.hospital_ops.diversion import (
    DiversionStatus,
    get_facility_diversion_status,
)

logger = logging.getLogger("careon.hospital_ops.readiness")


class ReadinessClassification:
    SUITABLE_CONFIRMED = "suitable_confirmed"
    SUITABLE_RECENT = "suitable_recent"
    POTENTIALLY_SUITABLE_UNCONFIRMED = "potentially_suitable_unconfirmed"
    CAPACITY_UNAVAILABLE = "capacity_unavailable"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    DIVERTED = "diverted"
    UNKNOWN_INSUFFICIENT_INFO = "unknown_insufficient_info"


@dataclass
class FacilityReadinessAssessment:
    facility_id: int
    facility_code: str
    facility_name: str
    organization_id: int
    latitude: float
    longitude: float
    distance_km: float
    eta_minutes: float
    eta_source: str
    operating_status: str
    classification: str
    score: float
    er_beds_available: int
    trauma_bays_available: int
    icu_beds_available: int
    incoming_patients_count: int
    capacity_freshness: str
    has_confirmed: bool
    matched_capabilities: List[str]
    missing_capabilities: List[str]
    explanations: List[str]
    is_designated: bool = False
    requires_override: bool = False
    routing_warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "facility_id": self.facility_id,
            "facility_code": self.facility_code,
            "facility_name": self.facility_name,
            "organization_id": self.organization_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "distance_km": round(self.distance_km, 2),
            "eta_minutes": round(self.eta_minutes, 1),
            "eta_source": self.eta_source,
            "operating_status": self.operating_status,
            "classification": self.classification,
            "score": round(self.score, 2),
            "er_beds_available": self.er_beds_available,
            "trauma_bays_available": self.trauma_bays_available,
            "icu_beds_available": self.icu_beds_available,
            "incoming_patients_count": self.incoming_patients_count,
            "capacity_freshness": self.capacity_freshness,
            "has_confirmed": self.has_confirmed,
            "matched_capabilities": self.matched_capabilities,
            "missing_capabilities": self.missing_capabilities,
            "explanations": self.explanations,
            "is_designated": self.is_designated,
            "requires_override": self.requires_override,
            "routing_warning": self.routing_warning,
        }


def get_designated_facility(db: Session) -> Optional[HospitalFacility]:
    """
    Resolves the single configured designated receiving hospital facility.
    In the initial CareOn deployment, all emergency requests target this facility
    unless marked diverted, inactive, or manually overridden.
    Uses CAREON_DESIGNATED_FACILITY_CODE as the authoritative configuration reference.
    Fails closed (returns None) if the configured facility cannot be resolved in the database.
    Does NOT assume Facility ID 1 exists or fall back to arbitrary facilities.
    """
    code = os.getenv("CAREON_DESIGNATED_FACILITY_CODE", "VRH-TRAUMA-01")
    if not code or not code.strip():
        logger.warning("CAREON_DESIGNATED_FACILITY_CODE is not configured. Failing closed.")
        return None

    fac = db.query(HospitalFacility).filter(HospitalFacility.facility_code == code.strip()).first()
    if not fac:
        logger.error(f"Designated facility code '{code}' could not be resolved in the database. Failing closed.")
        return None

    if not fac.organization_id:
        logger.error(f"Designated facility '{code}' is not associated with an authorized hospital organization. Failing closed.")
        return None

    return fac


def assess_facility_readiness(
    db: Session,
    facility: HospitalFacility,
    incident: Incident,
    required_capabilities: Optional[List[str]] = None,
    assignment_id: Optional[int] = None,
) -> FacilityReadinessAssessment:
    """
    Evaluates a hospital facility against an emergency incident's requirements.
    Calculates ETA, capability match, capacity freshness, incoming load, and classification.
    """
    explanations: List[str] = []
    matched_capabilities: List[str] = []
    missing_capabilities: List[str] = []

    # 1. Routing & Travel Time
    inc_lat = incident.latitude or 12.3052
    inc_lon = incident.longitude or 76.6552
    fac_lat = facility.latitude or 12.3052
    fac_lon = facility.longitude or 76.6552

    routing: RoutingResult = routing_engine.calculate_eta(inc_lat, inc_lon, fac_lat, fac_lon)

    # 2. Operating & Diversion Status
    div_status = get_facility_diversion_status(facility.id, db)
    operating_status = div_status.get("operating_status", facility.operating_status)
    is_diverted = div_status.get("is_diverted", False)
    diversion_reason = div_status.get("reason")

    # 3. Capacity Summary & Freshness
    cap_summary = get_facility_capacity_summary(db, facility.id)
    overall_freshness = cap_summary["overall_freshness"]
    cats = cap_summary["categories"]

    er_available = cats.get(CapacityCategory.ER_BEDS, {}).get("available", 0)
    trauma_available = cats.get(CapacityCategory.TRAUMA_BAYS, {}).get("available", 0)
    icu_available = cats.get(CapacityCategory.ICU_BEDS, {}).get("available", 0)

    # 4. Incoming patient workload (active pending/accepted requests)
    now = utc_now()
    active_incoming = (
        db.query(IncomingPatientRequest)
        .filter(
            IncomingPatientRequest.facility_id == facility.id,
            IncomingPatientRequest.status.in_(["pending", "acknowledged", "accepted"]),
        )
        .count()
    )

    # 5. Check if this specific incident/assignment has an accepted request
    has_confirmed = False
    if assignment_id:
        existing_accepted = (
            db.query(IncomingPatientRequest)
            .filter(
                IncomingPatientRequest.facility_id == facility.id,
                IncomingPatientRequest.assignment_id == assignment_id,
                IncomingPatientRequest.status == "accepted",
            )
            .first()
        )
        if existing_accepted:
            has_confirmed = True

    # 6. Capabilities Matching
    fac_caps = set(c.strip().lower() for c in (facility.capabilities or "").split(",") if c.strip())
    fac_equipment = set(e.strip().lower() for e in (facility.medical_equipment or "").split(",") if e.strip())
    fac_specialists = set(s.strip().lower() for s in (facility.specialist_services or "").split(",") if s.strip())
    all_fac_features = fac_caps.union(fac_equipment).union(fac_specialists)

    req_caps = required_capabilities or []
    # Infer required capabilities from incident severity and category if not passed
    if not req_caps:
        if incident.priority in ("Critical", "1", "High") or (incident.category or "").lower() in ("road accident", "traffic_accident", "trauma"):
            req_caps.append("trauma")
            req_caps.append("emergency")
        if (incident.category or "").lower() == "medical" and incident.priority == "Critical":
            req_caps.append("icu")
            req_caps.append("emergency")

    for req in req_caps:
        if req.lower() in all_fac_features:
            matched_capabilities.append(req)
        else:
            missing_capabilities.append(req)

    # 7. Determine Classification & Score
    score = 100.0

    # Distance/ETA penalty: -1 point per minute of ETA
    score -= min(40.0, routing.eta_minutes * 1.0)

    # Incoming workload penalty: -3 points per active incoming patient
    score -= min(15.0, active_incoming * 3.0)

    # Freshness penalty
    if overall_freshness == CapacityFreshnessStatus.VERIFIED_CURRENT:
        score += 5.0
        explanations.append("Capacity verified within past 15 minutes.")
    elif overall_freshness == CapacityFreshnessStatus.REPORTED_UNVERIFIED:
        score -= 5.0
        explanations.append("Capacity reported within past hour; requires operational confirmation.")
    elif overall_freshness == CapacityFreshnessStatus.AGING:
        score -= 15.0
        explanations.append("Capacity data is aging (1-3 hours old); verification required.")
    elif overall_freshness == CapacityFreshnessStatus.STALE:
        score -= 25.0
        explanations.append("Capacity data is stale (>3 hours old); cannot guarantee availability.")
    else:
        score -= 35.0
        explanations.append("Capacity data is unknown; treat as unconfirmed.")

    # Classification assignment logic
    if is_diverted or operating_status in (DiversionStatus.FULL_DIVERSION, DiversionStatus.CLOSED):
        classification = ReadinessClassification.DIVERTED
        score = max(0.0, score - 50.0)
        explanations.append(f"Facility is currently DIVERTED: {diversion_reason or 'No reason provided'}.")

    elif operating_status == DiversionStatus.PARTIAL_DIVERSION:
        # Check if partial diversion affects this incident's requirements
        div_type = div_status.get("diversion_type", "")
        if div_type and any(div_type.lower() in req.lower() for req in req_caps):
            classification = ReadinessClassification.DIVERTED
            score = max(0.0, score - 40.0)
            explanations.append(f"Facility has partial diversion matching emergency need: {div_type}.")
        else:
            classification = ReadinessClassification.POTENTIALLY_SUITABLE_UNCONFIRMED
            score -= 15.0
            explanations.append(f"Facility on partial diversion ({div_type}); non-diverted services active.")

    elif missing_capabilities:
        classification = ReadinessClassification.CAPABILITY_UNAVAILABLE
        score = max(0.0, score - 30.0)
        explanations.append(f"Missing required clinical capabilities: {', '.join(missing_capabilities)}.")

    elif er_available <= 0:
        classification = ReadinessClassification.CAPACITY_UNAVAILABLE
        score = max(0.0, score - 25.0)
        explanations.append("No emergency department beds currently available.")

    elif overall_freshness in (CapacityFreshnessStatus.UNKNOWN, CapacityFreshnessStatus.STALE):
        classification = ReadinessClassification.UNKNOWN_INSUFFICIENT_INFO
        explanations.append("Insufficient or stale capacity reporting prevents guaranteed readiness.")

    elif has_confirmed:
        classification = ReadinessClassification.SUITABLE_CONFIRMED
        score += 20.0
        explanations.append("Facility has explicitly accepted incoming emergency patient.")

    elif overall_freshness == CapacityFreshnessStatus.VERIFIED_CURRENT and er_available > 0:
        classification = ReadinessClassification.SUITABLE_RECENT
        explanations.append("Facility is suitable based on verified current bed availability.")

    else:
        classification = ReadinessClassification.POTENTIALLY_SUITABLE_UNCONFIRMED
        explanations.append("Facility is potentially suitable; awaiting hospital staff confirmation.")

    # 8. Check CareOn Designated Facility Configuration & Routing Overrides
    desig = get_designated_facility(db)
    is_designated = (desig is not None and desig.id == facility.id)
    requires_override = False
    routing_warning: Optional[str] = None

    if is_designated:
        if not facility.is_active:
            requires_override = True
            routing_warning = "Designated facility is INACTIVE. Manual dispatcher override required to route."
            explanations.append(routing_warning)
        elif operating_status in (DiversionStatus.FULL_DIVERSION, DiversionStatus.CLOSED) or is_diverted:
            requires_override = True
            routing_warning = f"Designated facility is DIVERTED/CLOSED ({diversion_reason or operating_status}). Manual dispatcher override required to route."
            explanations.append(routing_warning)
        elif overall_freshness in (CapacityFreshnessStatus.STALE, CapacityFreshnessStatus.UNKNOWN):
            requires_override = True
            routing_warning = f"Designated facility capacity data is {overall_freshness.upper()}. Verification required before routing."
            explanations.append(routing_warning)
        else:
            explanations.append("Primary CareOn designated facility for acute emergency intake.")

    return FacilityReadinessAssessment(
        facility_id=facility.id,
        facility_code=facility.facility_code,
        facility_name=facility.name,
        organization_id=facility.organization_id,
        latitude=fac_lat,
        longitude=fac_lon,
        distance_km=routing.distance_km,
        eta_minutes=routing.eta_minutes,
        eta_source=routing.source,
        operating_status=operating_status,
        classification=classification,
        score=max(0.0, score),
        er_beds_available=er_available,
        trauma_bays_available=trauma_available,
        icu_beds_available=icu_available,
        incoming_patients_count=active_incoming,
        capacity_freshness=overall_freshness,
        has_confirmed=has_confirmed,
        matched_capabilities=matched_capabilities,
        missing_capabilities=missing_capabilities,
        explanations=explanations,
        is_designated=is_designated,
        requires_override=requires_override,
        routing_warning=routing_warning,
    )


def rank_hospital_destinations(
    db: Session,
    incident: Incident,
    required_capabilities: Optional[List[str]] = None,
    assignment_id: Optional[int] = None,
    max_candidates: int = 10,
) -> List[FacilityReadinessAssessment]:
    """
    Ranks all active hospital facilities by readiness classification, score, and travel time.
    Separates confirmed/suitable hospitals from diverted or incapable facilities.
    Prioritizes designated facility when eligible without override flags.
    """
    facilities = db.query(HospitalFacility).filter(HospitalFacility.is_active == True).all()
    assessments: List[FacilityReadinessAssessment] = []

    for fac in facilities:
        assessment = assess_facility_readiness(
            db=db,
            facility=fac,
            incident=incident,
            required_capabilities=required_capabilities,
            assignment_id=assignment_id,
        )
        assessments.append(assessment)

    # Sort hierarchy:
    # 0. Designated facility first (if not requiring override)
    # 1. Non-diverted / capable first
    # 2. Confirmed & recent suitable first
    # 3. Descending readiness score
    # 4. Ascending ETA
    def sort_key(a: FacilityReadinessAssessment):
        tier_weight = {
            ReadinessClassification.SUITABLE_CONFIRMED: 0,
            ReadinessClassification.SUITABLE_RECENT: 1,
            ReadinessClassification.POTENTIALLY_SUITABLE_UNCONFIRMED: 2,
            ReadinessClassification.UNKNOWN_INSUFFICIENT_INFO: 3,
            ReadinessClassification.CAPACITY_UNAVAILABLE: 4,
            ReadinessClassification.CAPABILITY_UNAVAILABLE: 5,
            ReadinessClassification.DIVERTED: 6,
        }.get(a.classification, 7)
        desig_priority = 0 if (a.is_designated and not a.requires_override) else 1
        return (desig_priority, tier_weight, -a.score, a.eta_minutes)

    assessments.sort(key=sort_key)
    return assessments[:max_candidates]
