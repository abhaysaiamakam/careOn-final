"""
CareOn Milestone 7 — Mass-Casualty Incident (MCI) Coordination & Distribution Engine.

Addresses the critical disaster-response failure mode: "All ambulances rushing to the nearest hospital."
Provides:
- Multi-patient, multi-hospital capacity coordination
- Aggregate incoming patient load visibility
- Contention analysis and facility saturation warnings
- Capability-aware distribution recommendation (Critical/Trauma -> Level 1/2 Trauma Centers; Minor -> Community Hospitals)
- Dispatcher-controlled balanced allocation
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models import (
    HospitalFacility,
    Incident,
    IncomingPatientRequest,
    utc_now,
)
from app.hospital_ops.capacity import (
    CapacityCategory,
    get_facility_capacity_summary,
)
from app.hospital_ops.diversion import (
    DiversionStatus,
    get_facility_diversion_status,
)
from app.dispatch.routing import routing_engine, RoutingResult

logger = logging.getLogger("careon.hospital_ops.mci")


@dataclass
class MCIPatientAllocation:
    patient_index: int
    severity: str  # Critical, High, Medium, Low
    allocated_facility_id: int
    allocated_facility_name: str
    eta_minutes: float
    rationale: str


@dataclass
class MCIHospitalLoadOverview:
    facility_id: int
    facility_name: str
    trauma_level: str
    operating_status: str
    available_er_beds: int
    available_trauma_bays: int
    active_incoming_count: int
    mci_allocated_count: int
    total_projected_load: int
    is_saturated: bool
    saturation_warning: Optional[str]


def plan_mci_distribution(
    db: Session,
    incident_id: int,
    patient_severities: List[str],  # e.g. ["Critical", "Critical", "High", "Medium", "Low", "Low"]
) -> Dict[str, Any]:
    """
    Computes an optimal, balanced distribution of multiple MCI casualties across available hospitals.
    Prevents single-facility saturation by balancing trauma capabilities and travel time.
    """
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise ValueError(f"Incident {incident_id} not found")

    facilities = db.query(HospitalFacility).filter(HospitalFacility.is_active == True).all()
    if not facilities:
        raise ValueError("No active hospital facilities available for MCI distribution")

    inc_lat = incident.latitude or 12.3052
    inc_lon = incident.longitude or 76.6552

    # 1. Profile each facility
    facility_stats: Dict[int, Dict[str, Any]] = {}
    for fac in facilities:
        div = get_facility_diversion_status(fac.id, db)
        if div["is_diverted"] or div["operating_status"] in (DiversionStatus.FULL_DIVERSION, DiversionStatus.CLOSED):
            continue  # Exclude completely diverted hospitals from MCI intake

        cap = get_facility_capacity_summary(db, fac.id)
        er_avail = cap["categories"].get(CapacityCategory.ER_BEDS, {}).get("available", 0)
        trauma_avail = cap["categories"].get(CapacityCategory.TRAUMA_BAYS, {}).get("available", 0)

        routing: RoutingResult = routing_engine.calculate_eta(inc_lat, inc_lon, fac.latitude, fac.longitude)

        active_incoming = (
            db.query(IncomingPatientRequest)
            .filter(
                IncomingPatientRequest.facility_id == fac.id,
                IncomingPatientRequest.status.in_(["pending", "acknowledged", "accepted"]),
            )
            .count()
        )

        facility_stats[fac.id] = {
            "facility": fac,
            "er_available": er_avail,
            "trauma_available": trauma_avail,
            "active_incoming": active_incoming,
            "mci_allocated": 0,
            "trauma_level": fac.trauma_level,
            "eta_minutes": routing.eta_minutes,
            "distance_km": routing.distance_km,
        }

    if not facility_stats:
        raise ValueError("All regional hospital facilities are currently diverted or closed")

    # 2. Allocate patients sorted by severity (Critical first)
    # Priority sorting: Critical -> High -> Medium -> Low
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    indexed_patients = list(enumerate(patient_severities))
    indexed_patients.sort(key=lambda item: severity_order.get(item[1].lower(), 4))

    allocations: List[MCIPatientAllocation] = []

    for patient_idx, severity in indexed_patients:
        sev_lower = severity.lower()
        best_fac_id: Optional[int] = None
        best_score = -999999.0
        best_rationale = ""

        for fac_id, stat in facility_stats.items():
            fac: HospitalFacility = stat["facility"]
            remaining_er = stat["er_available"] - stat["mci_allocated"]
            remaining_trauma = stat["trauma_available"] - (stat["mci_allocated"] if sev_lower in ("critical", "high") else 0)

            # Score this hospital for this patient
            score = 100.0

            # Trauma center match for critical patients
            if sev_lower in ("critical", "high"):
                if "level 1" in stat["trauma_level"].lower():
                    score += 40.0
                elif "level 2" in stat["trauma_level"].lower():
                    score += 25.0
                else:
                    score -= 30.0  # Community hospital without trauma center penalized for critical

                if remaining_trauma <= 0:
                    score -= 35.0  # Depleted trauma bays
            else:
                # Mild/Moderate patients can go to community or lower-acuity hospitals to preserve trauma bays
                if "level 1" in stat["trauma_level"].lower():
                    score -= 10.0  # Preserve Level 1 for critical

            # Remaining capacity bonus / penalty
            if remaining_er <= 0:
                score -= 60.0  # Over-capacity penalty
            else:
                score += min(20.0, remaining_er * 2.0)

            # ETA penalty
            score -= min(30.0, stat["eta_minutes"] * 1.5)

            # Load spreading penalty
            score -= (stat["mci_allocated"] * 8.0)

            if score > best_score:
                best_score = score
                best_fac_id = fac_id
                best_rationale = (
                    f"Selected {fac.name} ({stat['trauma_level']}, ETA {stat['eta_minutes']:.1f}m): "
                    f"{remaining_er} ER beds available, currently allocated {stat['mci_allocated']} MCI patients."
                )

        if best_fac_id is not None:
            facility_stats[best_fac_id]["mci_allocated"] += 1
            allocations.append(
                MCIPatientAllocation(
                    patient_index=patient_idx + 1,
                    severity=severity,
                    allocated_facility_id=best_fac_id,
                    allocated_facility_name=facility_stats[best_fac_id]["facility"].name,
                    eta_minutes=facility_stats[best_fac_id]["eta_minutes"],
                    rationale=best_rationale,
                )
            )

    # Sort allocations back to original patient order
    allocations.sort(key=lambda a: a.patient_index)

    # 3. Compile facility load overview and warnings
    facility_overviews: List[MCIHospitalLoadOverview] = []
    warnings: List[str] = []

    for fac_id, stat in facility_stats.items():
        total_projected = stat["active_incoming"] + stat["mci_allocated"]
        is_saturated = total_projected > stat["er_available"]
        sat_warn = None
        if is_saturated:
            sat_warn = (
                f"Facility '{stat['facility'].name}' is projected to exceed capacity! "
                f"Projected load: {total_projected}, Available ER beds: {stat['er_available']}."
            )
            warnings.append(sat_warn)

        facility_overviews.append(
            MCIHospitalLoadOverview(
                facility_id=fac_id,
                facility_name=stat["facility"].name,
                trauma_level=stat["trauma_level"],
                operating_status=stat["facility"].operating_status,
                available_er_beds=stat["er_available"],
                available_trauma_bays=stat["trauma_available"],
                active_incoming_count=stat["active_incoming"],
                mci_allocated_count=stat["mci_allocated"],
                total_projected_load=total_projected,
                is_saturated=is_saturated,
                saturation_warning=sat_warn,
            )
        )

    return {
        "incident_id": incident.id,
        "total_patients": len(patient_severities),
        "allocations": [
            {
                "patient_index": a.patient_index,
                "severity": a.severity,
                "facility_id": a.allocated_facility_id,
                "facility_name": a.allocated_facility_name,
                "eta_minutes": round(a.eta_minutes, 1),
                "rationale": a.rationale,
            }
            for a in allocations
        ],
        "facility_overviews": [
            {
                "facility_id": fo.facility_id,
                "facility_name": fo.facility_name,
                "trauma_level": fo.trauma_level,
                "available_er_beds": fo.available_er_beds,
                "available_trauma_bays": fo.available_trauma_bays,
                "active_incoming": fo.active_incoming_count,
                "mci_allocated": fo.mci_allocated_count,
                "total_projected_load": fo.total_projected_load,
                "is_saturated": fo.is_saturated,
                "saturation_warning": fo.saturation_warning,
            }
            for fo in facility_overviews
        ],
        "warnings": warnings,
    }
