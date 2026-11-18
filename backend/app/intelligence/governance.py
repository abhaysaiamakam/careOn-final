"""
CareOn Milestone 10 — Positioning Governance & Human Approval Workflow.

Enforces human operational control over all predictive recommendations:
- State machine: GENERATED -> PENDING_REVIEW -> APPROVED / REJECTED / MODIFIED / EXPIRED -> EXECUTION_REQUESTED -> EXECUTED / FAILED / CANCELLED
- Strict dispatcher review and approval audit logging
- Rejection reason tracking
- Modification audit history
- OutboxEvent integration for real-time WebSocket notifications
"""

import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import (
    PositioningRecommendation,
    PositioningAuditLog,
    OutboxEvent,
    Resource,
    Assignment,
    User,
    make_point_wkt,
    utc_now,
)
from app.intelligence.coverage_engine import is_resource_telemetry_fresh
from app.schemas import (
    PositioningRecommendationReviewRequest,
    PositioningRecommendationRejectRequest,
    PositioningRecommendationModifyRequest,
    PositioningExecutionRequest,
)

logger = logging.getLogger("careon.intelligence.governance")


def verify_resource_eligibility_for_positioning(db: Session, resource_id: int) -> Tuple[bool, str]:
    """
    Re-evaluate operational availability and location freshness before approval or execution.
    Guarantees that an ambulance that became occupied or stale after recommendation generation
    cannot be dispatched into staging.
    """
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource:
        return False, f"Resource {resource_id} no longer exists."

    if resource.status in ["Unavailable", "Under Maintenance"]:
        return False, f"Resource {resource.resource_code} is currently {resource.status}."

    # Check active assignments
    active_assignment = (
        db.query(Assignment)
        .filter(Assignment.resource_id == resource.id, Assignment.status == "Active")
        .first()
    )
    if active_assignment or resource.status in ["Assigned", "Busy"]:
        return False, f"Resource {resource.resource_code} has become occupied on an active incident."

    # Check telemetry freshness
    is_fresh, _, _ = is_resource_telemetry_fresh(db, resource)
    if not is_fresh:
        return False, f"Resource {resource.resource_code} GPS telemetry is stale (>15 minutes old)."

    return True, ""


def approve_positioning_recommendation(
    db: Session,
    recommendation_id: int,
    user: User,
    request: PositioningRecommendationReviewRequest,
) -> PositioningRecommendation:
    """
    Dispatcher approval of an ambulance positioning recommendation.
    Emits an OutboxEvent for real-time WebSocket distribution.
    """
    now = utc_now()
    rec = (
        db.query(PositioningRecommendation)
        .filter(PositioningRecommendation.id == recommendation_id)
        .first()
    )
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Positioning recommendation {recommendation_id} not found.",
        )

    # Check expiration
    if rec.expires_at:
        exp = rec.expires_at if rec.expires_at.tzinfo else rec.expires_at.replace(tzinfo=timezone.utc)
        if exp < now:
            rec.status = "EXPIRED"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Recommendation has expired and cannot be approved.",
            )

    if rec.status not in ["PENDING_REVIEW", "MODIFIED", "GENERATED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve recommendation in status '{rec.status}'. Must be PENDING_REVIEW or MODIFIED.",
        )

    # Re-verify resource operational availability and location freshness at approval time
    is_eligible, ineligibility_reason = verify_resource_eligibility_for_positioning(db, rec.resource_id)
    if not is_eligible:
        prev_status = rec.status
        rec.status = "FAILED"
        rec.updated_at = now
        audit = PositioningAuditLog(
            log_uuid=str(uuid.uuid4()),
            recommendation_id=rec.id,
            actor_id=user.id,
            action="INVALIDATED",
            previous_status=prev_status,
            new_status="FAILED",
            details_json=json.dumps({"reason": ineligibility_reason}),
            created_at=now,
        )
        db.add(audit)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Approval rejected: {ineligibility_reason}",
        )

    prev_status = rec.status
    rec.status = "APPROVED"
    rec.reviewed_by_user_id = user.id
    rec.reviewed_at = now
    rec.updated_at = now

    # Audit log
    audit = PositioningAuditLog(
        log_uuid=str(uuid.uuid4()),
        recommendation_id=rec.id,
        actor_id=user.id,
        action="APPROVED",
        previous_status=prev_status,
        new_status="APPROVED",
        details_json=json.dumps({"notes": request.notes or "Approved by dispatcher"}),
        created_at=now,
    )
    db.add(audit)

    # Outbox event for M4 real-time WebSocket broadcast
    outbox = OutboxEvent(
        event_id=str(uuid.uuid4()),
        event_type="INTELLIGENCE_RECOMMENDATION_APPROVED",
        event_version=1,
        occurred_at=now,
        organization_id=rec.organization_id,
        actor_id=user.id,
        channel="careon:events:dispatch",
        payload_json=json.dumps({
            "recommendation_id": rec.id,
            "recommendation_uuid": rec.recommendation_uuid,
            "target_area": rec.target_area,
            "resource_id": rec.resource_id,
            "proposed_staging_name": rec.proposed_staging_name,
            "approved_by": user.email,
        }),
    )
    db.add(outbox)

    db.commit()
    db.refresh(rec)
    return rec


def reject_positioning_recommendation(
    db: Session,
    recommendation_id: int,
    user: User,
    request: PositioningRecommendationRejectRequest,
) -> PositioningRecommendation:
    """
    Dispatcher rejection of an ambulance positioning recommendation with mandatory reason.
    """
    now = utc_now()
    rec = (
        db.query(PositioningRecommendation)
        .filter(PositioningRecommendation.id == recommendation_id)
        .first()
    )
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Positioning recommendation {recommendation_id} not found.",
        )

    if rec.status in ["EXECUTED", "REJECTED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject recommendation in terminal status '{rec.status}'.",
        )

    prev_status = rec.status
    rec.status = "REJECTED"
    rec.reviewed_by_user_id = user.id
    rec.reviewed_at = now
    rec.rejection_reason = request.reason
    rec.updated_at = now

    audit = PositioningAuditLog(
        log_uuid=str(uuid.uuid4()),
        recommendation_id=rec.id,
        actor_id=user.id,
        action="REJECTED",
        previous_status=prev_status,
        new_status="REJECTED",
        details_json=json.dumps({"reason": request.reason}),
        created_at=now,
    )
    db.add(audit)
    db.commit()
    db.refresh(rec)
    return rec


def modify_positioning_recommendation(
    db: Session,
    recommendation_id: int,
    user: User,
    request: PositioningRecommendationModifyRequest,
) -> PositioningRecommendation:
    """
    Dispatcher modification of proposed staging coordinates, staging name, or candidate resource.
    """
    now = utc_now()
    rec = (
        db.query(PositioningRecommendation)
        .filter(PositioningRecommendation.id == recommendation_id)
        .first()
    )
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Positioning recommendation {recommendation_id} not found.",
        )

    if rec.status in ["EXECUTED", "REJECTED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot modify recommendation in status '{rec.status}'.",
        )

    prev_status = rec.status
    rec.status = "MODIFIED"
    rec.reviewed_by_user_id = user.id
    rec.reviewed_at = now
    rec.updated_at = now

    modifications: Dict[str, Any] = {}
    if request.proposed_latitude is not None and request.proposed_longitude is not None:
        rec.proposed_latitude = request.proposed_latitude
        rec.proposed_longitude = request.proposed_longitude
        rec.proposed_staging_geom = make_point_wkt(request.proposed_latitude, request.proposed_longitude)
        modifications["staging_coordinates"] = [request.proposed_latitude, request.proposed_longitude]

    if request.proposed_staging_name:
        rec.proposed_staging_name = request.proposed_staging_name
        modifications["staging_name"] = request.proposed_staging_name

    if request.resource_id:
        rec.resource_id = request.resource_id
        modifications["resource_id"] = request.resource_id

    if request.notes:
        rec.modification_notes = request.notes
        modifications["notes"] = request.notes

    audit = PositioningAuditLog(
        log_uuid=str(uuid.uuid4()),
        recommendation_id=rec.id,
        actor_id=user.id,
        action="MODIFIED",
        previous_status=prev_status,
        new_status="MODIFIED",
        details_json=json.dumps(modifications),
        created_at=now,
    )
    db.add(audit)
    db.commit()
    db.refresh(rec)
    return rec


def execute_positioning_recommendation(
    db: Session,
    recommendation_id: int,
    user: User,
    request: PositioningExecutionRequest,
) -> PositioningRecommendation:
    """
    Transition approved recommendation into execution tracking.
    """
    now = utc_now()
    rec = (
        db.query(PositioningRecommendation)
        .filter(PositioningRecommendation.id == recommendation_id)
        .first()
    )
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Positioning recommendation {recommendation_id} not found.",
        )

    if rec.status not in ["APPROVED", "MODIFIED", "EXECUTION_REQUESTED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot execute recommendation in status '{rec.status}'. Must be APPROVED.",
        )

    prev_status = rec.status
    if request.execution_action == "CANCEL":
        rec.status = "CANCELLED"
        rec.execution_status = "CANCELLED_BY_OPERATOR"
    else:
        # Re-verify resource operational availability before dispatching to staging
        is_eligible, ineligibility_reason = verify_resource_eligibility_for_positioning(db, rec.resource_id)
        if not is_eligible:
            rec.status = "FAILED"
            rec.execution_status = "EXECUTION_ABORTED_RESOURCE_UNAVAILABLE"
            rec.updated_at = now
            audit = PositioningAuditLog(
                log_uuid=str(uuid.uuid4()),
                recommendation_id=rec.id,
                actor_id=user.id,
                action="EXECUTION_FAILED",
                previous_status=prev_status,
                new_status="FAILED",
                details_json=json.dumps({"reason": ineligibility_reason}),
                created_at=now,
            )
            db.add(audit)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Execution rejected: {ineligibility_reason}",
            )

        rec.status = "EXECUTED"
        rec.execution_status = "STAGING_MISSION_DISPATCHED"
        rec.execution_requested_at = now

    rec.updated_at = now

    audit = PositioningAuditLog(
        log_uuid=str(uuid.uuid4()),
        recommendation_id=rec.id,
        actor_id=user.id,
        action=rec.status,
        previous_status=prev_status,
        new_status=rec.status,
        details_json=json.dumps({"action": request.execution_action, "notes": request.notes}),
        created_at=now,
    )
    db.add(audit)
    db.commit()
    db.refresh(rec)
    return rec
