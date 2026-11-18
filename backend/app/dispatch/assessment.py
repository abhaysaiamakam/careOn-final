"""
CareOn Milestone 5 — Intelligent Incident Assessment Service.

Evaluates:
- Emergency category & reported keywords
- Reported severity & priority
- Casualty counts (affected people)
- Patient condition and special requirements
- Geospatial validity (-90..90, -180..180)
- Incident reporting age & status
- Active assignments & duplicate incident candidates

Produces:
- Recommended priority (Critical, High, Medium, Low)
- Severity classification (Life-Threatening, Severe, Moderate, Low)
- Required resource capabilities (ALS, BLS, trauma_care, etc.)
- Required equipment (oxygen, defibrillator, ventilator, etc.)
- Assessment confidence score (0.0 to 1.0)
- Missing or uncertain information checklist
- Detailed, human-readable triage explanation
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models import Incident, Assignment, validate_coordinates
from app.algorithms.classification import CRITICAL_KEYWORDS, HIGH_KEYWORDS


# Capability mapping per category
INCIDENT_CAPABILITY_REQUIREMENTS: Dict[str, List[str]] = {
    "Medical": ["BLS", "patient_transport", "first_aid"],
    "Road accident": ["BLS", "trauma_care", "patient_transport", "extrication"],
    "Fire": ["fire_suppression", "smoke_rescue"],
    "Rescue": ["search_and_rescue", "heavy_rescue", "first_aid"],
    "Safety / Other": ["first_aid", "patrol"],
    "Disaster / Multiple affected people": [
        "disaster_relief", "mass_casualty", "triage", "patient_transport"
    ],
}

# Equipment mapping per severity and category
SEVERITY_EQUIPMENT_REQUIREMENTS: Dict[str, List[str]] = {
    "Life-Threatening": ["defibrillator", "ventilator", "oxygen", "spine_board", "als_kit"],
    "Severe": ["oxygen", "first_aid_kit", "spine_board", "stretcher"],
    "Moderate": ["first_aid_kit", "stretcher"],
    "Low": ["first_aid_kit"],
}


@dataclass
class IncidentAssessment:
    incident_id: int
    incident_code: str
    reported_priority: str
    recommended_priority: str
    severity: str  # Life-Threatening, Severe, Moderate, Low
    required_capabilities: List[str]
    required_equipment: List[str]
    confidence_score: float  # 0.0 - 1.0
    missing_information: List[str]
    is_geospatially_valid: bool
    is_duplicate_candidate: bool
    duplicate_of_code: Optional[str]
    has_active_assignment: bool
    explanation: str
    assessed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "incident_code": self.incident_code,
            "reported_priority": self.reported_priority,
            "recommended_priority": self.recommended_priority,
            "severity": self.severity,
            "required_capabilities": self.required_capabilities,
            "required_equipment": self.required_equipment,
            "confidence_score": self.confidence_score,
            "missing_information": self.missing_information,
            "is_geospatially_valid": self.is_geospatially_valid,
            "is_duplicate_candidate": self.is_duplicate_candidate,
            "duplicate_of_code": self.duplicate_of_code,
            "has_active_assignment": self.has_active_assignment,
            "explanation": self.explanation,
            "assessed_at": self.assessed_at,
        }


def assess_incident(incident: Incident, db: Session) -> IncidentAssessment:
    """
    Perform deep structured assessment of an incident to derive operational requirements.
    Does not invent clinical diagnoses; clearly distinguishes reported data from recommendations.
    """
    missing_info: List[str] = []
    text_content = f"{incident.category or ''} {incident.help_required or ''} {incident.description or ''}".lower()

    # 1. Geospatial validity
    geo_valid = False
    try:
        lat = float(incident.latitude)
        lon = float(incident.longitude)
        if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
            validate_coordinates(lat, lon)
            geo_valid = True
    except (TypeError, ValueError):
        geo_valid = False

    if not geo_valid:
        missing_info.append("Valid GPS coordinates (latitude/longitude out of range)")

    # 2. Information completeness check
    if not incident.contact_phone or incident.contact_phone.strip() in ("", "+91 00000 00000"):
        missing_info.append("Verified caller contact number")
    if not incident.affected_people or incident.affected_people <= 0:
        missing_info.append("Confirmed number of affected individuals")
    if not incident.description or len(incident.description.strip()) < 15:
        missing_info.append("Detailed description of incident context and symptoms")

    # 3. Severity & Priority Assessment
    severity = "Moderate"
    recommended_priority = "Medium"
    confidence = 0.85

    # Check life-threatening markers
    critical_matches = [kw for kw in CRITICAL_KEYWORDS if re.search(r"\b" + re.escape(kw) + r"\b", text_content)]
    high_matches = [kw for kw in HIGH_KEYWORDS if re.search(r"\b" + re.escape(kw) + r"\b", text_content)]

    if critical_matches:
        severity = "Life-Threatening"
        recommended_priority = "Critical"
        reason = f"Immediate life threat identified ({', '.join(critical_matches)})."
    elif incident.is_disaster or (incident.affected_people and incident.affected_people >= 4):
        severity = "Life-Threatening" if incident.affected_people >= 5 else "Severe"
        recommended_priority = "Critical" if incident.affected_people >= 5 else "High"
        reason = f"Mass casualty / disaster event with {incident.affected_people} individuals involved."
    elif incident.category.lower() == "fire" and (incident.affected_people > 1 or "building" in text_content or "trapped" in text_content):
        severity = "Life-Threatening"
        recommended_priority = "Critical"
        reason = "Active structural fire with human endangerment."
    elif high_matches:
        severity = "Severe"
        recommended_priority = "High"
        reason = f"Acute operational urgency detected ({', '.join(high_matches)})."
    elif (not incident.affected_people or incident.affected_people <= 1) and any(w in text_content for w in ["minor", "stable", "first aid", "advice"]):
        severity = "Low"
        recommended_priority = "Low"
        reason = "Non-acute minor condition reported; patient stable."
    elif incident.category.lower() in ("medical", "road accident", "rescue"):
        severity = "Severe"
        recommended_priority = "High"
        reason = f"Standard emergency protocol for acute {incident.category.lower()} response."
    else:
        severity = "Moderate"
        recommended_priority = "Medium"
        reason = "Standard emergency triage pending on-scene responder assessment."

    # Adjust confidence based on missing info
    confidence -= len(missing_info) * 0.15
    confidence = max(0.20, min(1.0, round(confidence, 2)))

    # 4. Required capabilities and equipment
    req_caps = list(INCIDENT_CAPABILITY_REQUIREMENTS.get(incident.category, ["first_aid"]))
    if severity == "Life-Threatening":
        if "ALS" not in req_caps:
            req_caps.insert(0, "ALS")
        if "critical_care" not in req_caps:
            req_caps.append("critical_care")
    elif severity == "Severe":
        if "BLS" not in req_caps and "ALS" not in req_caps:
            req_caps.insert(0, "BLS")

    req_equipment = list(SEVERITY_EQUIPMENT_REQUIREMENTS.get(severity, ["first_aid_kit"]))
    if incident.category.lower() == "road accident" and "extrication_tools" not in req_equipment:
        req_equipment.append("extrication_tools")

    # 5. Active assignment check
    active_assignment = (
        db.query(Assignment)
        .filter(Assignment.incident_id == incident.id, Assignment.status == "Active")
        .first()
    )

    # 6. Duplicate check status
    is_dup = bool(incident.is_duplicate)
    dup_code = None
    if incident.duplicate_of_id:
        parent = db.query(Incident).filter(Incident.id == incident.duplicate_of_id).first()
        if parent:
            dup_code = parent.incident_code

    explanation = (
        f"Assessed as {severity} ({recommended_priority} priority). {reason} "
        f"Requires capabilities [{', '.join(req_caps)}] and equipment [{', '.join(req_equipment)}]."
    )
    if missing_info:
        explanation += f" Warning: Missing {', '.join(missing_info)} (Confidence: {int(confidence*100)}%)."

    return IncidentAssessment(
        incident_id=incident.id,
        incident_code=incident.incident_code,
        reported_priority=incident.priority,
        recommended_priority=recommended_priority,
        severity=severity,
        required_capabilities=req_caps,
        required_equipment=req_equipment,
        confidence_score=confidence,
        missing_information=missing_info,
        is_geospatially_valid=geo_valid,
        is_duplicate_candidate=is_dup,
        duplicate_of_code=dup_code,
        has_active_assignment=active_assignment is not None,
        explanation=explanation,
    )
