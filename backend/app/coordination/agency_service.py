"""
Agency Classification and Directory Service.
Manages emergency services agency metadata, radio channels, jurisdiction, and mutual aid registry.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import AgencyClassification, Organization, utc_now
from app.schemas import AgencyClassificationCreate, AgencyClassificationUpdate


def get_agency_classification(db: Session, organization_id: int) -> Optional[AgencyClassification]:
    return db.query(AgencyClassification).filter(AgencyClassification.organization_id == organization_id).first()


def register_or_update_classification(
    db: Session,
    organization_id: int,
    data: AgencyClassificationCreate,
) -> AgencyClassification:
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization {organization_id} not found."
        )

    classification = get_agency_classification(db, organization_id)
    if not classification:
        classification = AgencyClassification(
            organization_id=organization_id,
            agency_type=data.agency_type.upper(),
            jurisdiction=data.jurisdiction,
            dispatch_hotline=data.dispatch_hotline,
            radio_channel=data.radio_channel,
            capabilities_json=data.capabilities_json,
            is_mutual_aid_signatory=data.is_mutual_aid_signatory,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.add(classification)
    else:
        classification.agency_type = data.agency_type.upper()
        if data.jurisdiction is not None:
            classification.jurisdiction = data.jurisdiction
        if data.dispatch_hotline is not None:
            classification.dispatch_hotline = data.dispatch_hotline
        if data.radio_channel is not None:
            classification.radio_channel = data.radio_channel
        if data.capabilities_json is not None:
            classification.capabilities_json = data.capabilities_json
        classification.is_mutual_aid_signatory = data.is_mutual_aid_signatory
        classification.updated_at = utc_now()

    db.commit()
    db.refresh(classification)
    return classification


def get_mutual_aid_partners(
    db: Session,
    current_org_id: int,
    agency_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Return all registered mutual aid partner agencies except the current organization.
    """
    query = (
        db.query(Organization, AgencyClassification)
        .join(AgencyClassification, Organization.id == AgencyClassification.organization_id)
        .filter(
            Organization.id != current_org_id,
            Organization.is_active == True,
            AgencyClassification.is_mutual_aid_signatory == True,
        )
    )
    if agency_type:
        query = query.filter(AgencyClassification.agency_type == agency_type.upper())

    results = []
    for org, classification in query.all():
        results.append({
            "organization_id": org.id,
            "organization_name": org.name,
            "agency_type": classification.agency_type,
            "jurisdiction": classification.jurisdiction,
            "dispatch_hotline": classification.dispatch_hotline,
            "radio_channel": classification.radio_channel,
            "is_mutual_aid_signatory": classification.is_mutual_aid_signatory,
        })
    return results
