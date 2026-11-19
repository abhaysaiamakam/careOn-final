"""
CareOn Citizen Dedicated API Router.
Provides authenticated endpoints for:
- Citizen Emergency Profile (Address, Medical Notes, Unverified disclaimer)
- In-Case-of-Emergency (ICE) Contacts
- First-time Safety Onboarding Wizard progression
- Citizen Personal Safety Dashboard Summary
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.models import User, CitizenProfile, CitizenEmergencyContact, Incident, Notification, AuditLog
from app.schemas import (
    CitizenProfileResponse,
    CitizenProfileUpdate,
    CitizenEmergencyContactCreate,
    CitizenEmergencyContactUpdate,
    CitizenEmergencyContactResponse,
    CitizenDashboardSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/citizen", tags=["Citizen Experience"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get_or_create_citizen_profile(db: Session, user: User) -> CitizenProfile:
    profile = db.query(CitizenProfile).filter(CitizenProfile.user_id == user.id).first()
    if not profile:
        now = utc_now()
        profile = CitizenProfile(
            user_id=user.id,
            preferred_language="en",
            onboarding_completed=False,
            onboarding_step=1,
            consent_data_sharing=False,
            consent_emergency_contact=False,
            is_medical_verified=False,
            created_at=now,
            updated_at=now,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def _build_profile_response(user: User, profile: CitizenProfile, db: Session = None) -> CitizenProfileResponse:
    score = 25
    missing = []
    if profile.residential_address:
        score += 25
    else:
        missing.append("residential_address")

    if profile.city:
        score += 10
    else:
        missing.append("residential_city")

    if profile.blood_group and profile.blood_group != "UNKNOWN":
        score += 10
    else:
        missing.append("blood_group")

    if profile.consent_data_sharing:
        score += 10

    contacts_count = 0
    if db:
        contacts_count = db.query(CitizenEmergencyContact).filter(CitizenEmergencyContact.user_id == user.id).count()
    if contacts_count > 0:
        score += 20
    else:
        missing.append("emergency_contacts")

    score = min(score, 100)

    return CitizenProfileResponse(
        user_id=user.id,
        name=user.name,
        email=user.email,
        phone=user.phone,
        trust_score=user.trust_score,
        dob=profile.dob,
        preferred_language=profile.preferred_language,
        profile_photo_url=profile.profile_photo_url,
        residential_address=profile.residential_address,
        city=profile.city,
        state=profile.state,
        pincode=profile.pincode,
        landmark=profile.landmark,
        residential_city=profile.city,
        residential_state=profile.state,
        residential_postal_code=profile.pincode,
        address_landmark=profile.landmark,
        access_instructions=profile.accessibility_needs,
        emergency_notes=profile.accessibility_needs,
        home_latitude=profile.home_latitude,
        home_longitude=profile.home_longitude,
        blood_group=profile.blood_group,
        allergies=profile.allergies,
        medical_conditions=profile.medical_conditions,
        medications=profile.medications,
        current_medications=profile.medications,
        accessibility_needs=profile.accessibility_needs,
        is_medical_verified=profile.is_medical_verified,
        is_organ_donor=False,
        onboarding_completed=profile.onboarding_completed,
        onboarding_step=profile.onboarding_step,
        consent_data_sharing=profile.consent_data_sharing,
        consent_emergency_contact=profile.consent_emergency_contact,
        consent_data_sharing_emergency=profile.consent_data_sharing,
        readiness_score=score,
        missing_critical_fields=missing,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _build_contact_response(c: CitizenEmergencyContact) -> CitizenEmergencyContactResponse:
    return CitizenEmergencyContactResponse(
        id=c.id,
        user_id=c.user_id,
        name=c.name,
        full_name=c.name,
        relationship_type=c.relationship_type,
        phone=c.phone,
        secondary_phone=None,
        email=None,
        is_primary=c.is_primary,
        can_authorize_medical_treatment=True,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


# ==============================================================================
# 1. Profile & Onboarding Endpoints
# ==============================================================================
@router.get("/profile", response_model=CitizenProfileResponse)
def get_citizen_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve or initialize the authenticated citizen's emergency profile."""
    profile = _get_or_create_citizen_profile(db, current_user)
    return _build_profile_response(current_user, profile, db)


@router.put("/profile", response_model=CitizenProfileResponse)
def update_citizen_profile(
    payload: CitizenProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update citizen emergency profile, address, self-reported medical data,
    or onboarding progress. Syncs name and phone to primary User record.
    """
    profile = _get_or_create_citizen_profile(db, current_user)
    now = utc_now()

    # Update User model if name or phone changed
    user_changed = False
    if payload.name and payload.name.strip() != current_user.name:
        current_user.name = payload.name.strip()
        user_changed = True
    if payload.phone and payload.phone.strip() != current_user.phone:
        current_user.phone = payload.phone.strip()
        user_changed = True

    # Update profile fields
    if payload.dob is not None:
        profile.dob = payload.dob.strip() if payload.dob else None
    if payload.preferred_language is not None:
        profile.preferred_language = payload.preferred_language.strip()
    if payload.profile_photo_url is not None:
        profile.profile_photo_url = payload.profile_photo_url.strip() if payload.profile_photo_url else None

    # Address
    if payload.residential_address is not None:
        profile.residential_address = payload.residential_address.strip() if payload.residential_address else None

    city_val = payload.city if payload.city is not None else payload.residential_city
    if city_val is not None:
        profile.city = city_val.strip() if city_val else None

    state_val = payload.state if payload.state is not None else payload.residential_state
    if state_val is not None:
        profile.state = state_val.strip() if state_val else None

    pincode_val = payload.pincode if payload.pincode is not None else payload.residential_postal_code
    if pincode_val is not None:
        profile.pincode = pincode_val.strip() if pincode_val else None

    landmark_val = payload.landmark if payload.landmark is not None else payload.address_landmark
    if landmark_val is not None:
        profile.landmark = landmark_val.strip() if landmark_val else None

    if payload.home_latitude is not None:
        profile.home_latitude = payload.home_latitude
    if payload.home_longitude is not None:
        profile.home_longitude = payload.home_longitude

    # Medical (Citizen-reported, explicitly unverified)
    if payload.blood_group is not None:
        profile.blood_group = payload.blood_group.strip() if payload.blood_group else None
    if payload.allergies is not None:
        profile.allergies = payload.allergies.strip() if payload.allergies else None
    if payload.medical_conditions is not None:
        profile.medical_conditions = payload.medical_conditions.strip() if payload.medical_conditions else None

    meds_val = payload.medications if payload.medications is not None else payload.current_medications
    if meds_val is not None:
        profile.medications = meds_val.strip() if meds_val else None

    access_val = payload.accessibility_needs if payload.accessibility_needs is not None else (payload.access_instructions or payload.emergency_notes)
    if access_val is not None:
        profile.accessibility_needs = access_val.strip() if access_val else None

    # Onboarding step progression
    if payload.onboarding_step is not None:
        profile.onboarding_step = payload.onboarding_step

    # Consents
    consent_val = payload.consent_data_sharing if payload.consent_data_sharing is not None else payload.consent_data_sharing_emergency
    if consent_val is not None:
        profile.consent_data_sharing = consent_val
    if payload.consent_emergency_contact is not None:
        profile.consent_emergency_contact = payload.consent_emergency_contact

    profile.updated_at = now

    audit = AuditLog(
        action="CITIZEN_PROFILE_UPDATED",
        entity_type="CitizenProfile",
        entity_id=str(profile.id),
        actor=current_user.email,
        details=f"Citizen updated emergency profile (onboarding step {profile.onboarding_step})",
    )
    db.add(audit)
    db.commit()
    db.refresh(profile)
    if user_changed:
        db.refresh(current_user)

    return _build_profile_response(current_user, profile, db)


@router.post("/onboarding/complete", response_model=CitizenProfileResponse)
def complete_citizen_onboarding(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark the citizen's first-time onboarding wizard as completed."""
    profile = _get_or_create_citizen_profile(db, current_user)
    profile.onboarding_completed = True
    profile.onboarding_step = 5
    profile.consent_data_sharing = True
    profile.updated_at = utc_now()

    audit = AuditLog(
        action="CITIZEN_ONBOARDING_COMPLETED",
        entity_type="CitizenProfile",
        entity_id=str(profile.id),
        actor=current_user.email,
        details="Citizen completed first-time emergency profile onboarding",
    )
    db.add(audit)
    db.commit()
    db.refresh(profile)
    return _build_profile_response(current_user, profile, db)


# ==============================================================================
# 2. Emergency (ICE) Contacts Endpoints
# ==============================================================================
@router.get("/contacts", response_model=List[CitizenEmergencyContactResponse])
def list_emergency_contacts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List trusted emergency contacts for the authenticated citizen."""
    contacts = (
        db.query(CitizenEmergencyContact)
        .filter(CitizenEmergencyContact.user_id == current_user.id)
        .order_by(CitizenEmergencyContact.is_primary.desc(), CitizenEmergencyContact.created_at.asc())
        .all()
    )
    return [_build_contact_response(c) for c in contacts]


@router.post("/contacts", response_model=CitizenEmergencyContactResponse, status_code=status.HTTP_201_CREATED)
def create_emergency_contact(
    payload: CitizenEmergencyContactCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Register a new trusted emergency contact for the citizen."""
    # Enforce limit of 10 contacts per citizen
    count = db.query(CitizenEmergencyContact).filter(CitizenEmergencyContact.user_id == current_user.id).count()
    if count >= 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum of 10 emergency contacts reached.",
        )

    contact_name = (payload.full_name or payload.name or "").strip()
    if not contact_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Contact name is required.",
        )

    # If new contact is primary, unmark existing primary contacts
    now = utc_now()
    if payload.is_primary:
        db.query(CitizenEmergencyContact).filter(
            CitizenEmergencyContact.user_id == current_user.id,
            CitizenEmergencyContact.is_primary == True,
        ).update({"is_primary": False})

    contact = CitizenEmergencyContact(
        user_id=current_user.id,
        name=contact_name,
        relationship_type=payload.relationship_type.strip(),
        phone=payload.phone.strip(),
        is_primary=bool(payload.is_primary or (count == 0)), # First contact becomes default primary
        created_at=now,
        updated_at=now,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return _build_contact_response(contact)


@router.put("/contacts/{contact_id}", response_model=CitizenEmergencyContactResponse)
def update_emergency_contact(
    contact_id: int,
    payload: CitizenEmergencyContactUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update an existing emergency contact with authenticated ownership check."""
    contact = (
        db.query(CitizenEmergencyContact)
        .filter(CitizenEmergencyContact.id == contact_id, CitizenEmergencyContact.user_id == current_user.id)
        .first()
    )
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Emergency contact not found or access denied.",
        )

    name_val = payload.full_name or payload.name
    if name_val is not None:
        contact.name = name_val.strip()
    if payload.relationship_type is not None:
        contact.relationship_type = payload.relationship_type.strip()
    if payload.phone is not None:
        contact.phone = payload.phone.strip()

    if payload.is_primary is True:
        # Demote any other primary
        db.query(CitizenEmergencyContact).filter(
            CitizenEmergencyContact.user_id == current_user.id,
            CitizenEmergencyContact.id != contact_id,
        ).update({"is_primary": False})
        contact.is_primary = True
    elif payload.is_primary is False:
        contact.is_primary = False

    contact.updated_at = utc_now()
    db.commit()
    db.refresh(contact)
    return _build_contact_response(contact)


@router.delete("/contacts/{contact_id}")
def delete_emergency_contact(
    contact_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an emergency contact with authenticated ownership check."""
    contact = (
        db.query(CitizenEmergencyContact)
        .filter(CitizenEmergencyContact.id == contact_id, CitizenEmergencyContact.user_id == current_user.id)
        .first()
    )
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Emergency contact not found or access denied.",
        )
    db.delete(contact)
    db.commit()
    return {"status": "success", "message": "Emergency contact deleted"}


# ==============================================================================
# 3. Personal Citizen Dashboard Summary
# ==============================================================================
@router.get("/dashboard-summary", response_model=CitizenDashboardSummary)
def get_citizen_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Rethought citizen dashboard summary:
    - Personal identity & onboarding completion
    - Emergency readiness score & suggestions
    - Active incident (if currently underway)
    - Recent incident history (citizen's own incidents only)
    - Registered emergency contacts
    - Unread notifications count
    """
    profile = _get_or_create_citizen_profile(db, current_user)
    contacts = (
        db.query(CitizenEmergencyContact)
        .filter(CitizenEmergencyContact.user_id == current_user.id)
        .order_by(CitizenEmergencyContact.is_primary.desc())
        .all()
    )
    contact_responses = [_build_contact_response(c) for c in contacts]

    # Calculate Profile Readiness & Suggestions
    suggestions = []
    profile_complete = bool(current_user.name and current_user.phone and profile.residential_address)
    contacts_complete = len(contacts) > 0
    medical_provided = bool(profile.blood_group or profile.allergies or profile.medical_conditions)

    if not profile.residential_address:
        suggestions.append("Add your residential address for faster home response")
    if not contacts_complete:
        suggestions.append("Add at least one trusted In-Case-of-Emergency (ICE) contact")
    if not medical_provided:
        suggestions.append("Add your blood group or known allergies for emergency physicians")

    score = 40  # base for verified account
    if profile_complete: score += 20
    if contacts_complete: score += 20
    if medical_provided: score += 20
    readiness = {
        "score_percentage": min(score, 100),
        "profile_complete": profile_complete,
        "contacts_complete": contacts_complete,
        "medical_provided": medical_provided,
        "suggestions": suggestions,
    }

    # Fetch Active Incident (strictly belonging to this citizen, non-terminal)
    active_incs = (
        db.query(Incident)
        .filter(
            Incident.user_id == current_user.id,
            ~Incident.status.in_(["Resolved", "Cancelled", "Rejected"])
        )
        .order_by(Incident.created_at.desc())
        .all()
    )
    active_incidents_data = [
        {
            "id": inc.id,
            "incident_code": inc.incident_code,
            "category": inc.category,
            "status": inc.status,
            "priority": inc.priority,
            "address": inc.location_name,
            "location_name": inc.location_name,
            "tracking_token": inc.tracking_token,
            "created_at": inc.created_at.isoformat() if inc.created_at else None,
            "updated_at": inc.updated_at.isoformat() if inc.updated_at else None,
        }
        for inc in active_incs
    ]
    active_incident_data = active_incidents_data[0] if active_incidents_data else None

    # Fetch Recent Incidents (max 5, citizen's own only)
    recent_incs = (
        db.query(Incident)
        .filter(Incident.user_id == current_user.id)
        .order_by(Incident.created_at.desc())
        .limit(5)
        .all()
    )
    recent_incidents_data = [
        {
            "id": inc.id,
            "incident_code": inc.incident_code,
            "category": inc.category,
            "status": inc.status,
            "priority": inc.priority,
            "address": inc.location_name,
            "location_name": inc.location_name,
            "tracking_token": inc.tracking_token,
            "created_at": inc.created_at.isoformat() if inc.created_at else None,
        }
        for inc in recent_incs
    ]

    # Total citizen incidents count
    total_count = db.query(Incident).filter(Incident.user_id == current_user.id).count()

    # Unread notifications count
    unread_count = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.is_read == False)
        .count()
    )

    prof_resp = _build_profile_response(current_user, profile, db)

    return CitizenDashboardSummary(
        user_id=current_user.id,
        name=current_user.name,
        phone=current_user.phone,
        email=current_user.email,
        onboarding_completed=profile.onboarding_completed,
        onboarding_step=profile.onboarding_step,
        readiness=readiness,
        active_incident=active_incident_data,
        recent_incidents=recent_incidents_data,
        emergency_contacts=contact_responses,
        unread_notifications_count=unread_count,
        profile=prof_resp,
        contacts=contact_responses,
        active_incidents=active_incidents_data,
        total_incidents_count=total_count,
    )
