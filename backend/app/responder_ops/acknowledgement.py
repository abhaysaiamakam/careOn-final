"""
CareOn Milestone 6 — Assignment Acknowledgement & Timeout Manager.

Features:
- Configurable responder acknowledgement deadlines (default 180 seconds / 3 minutes)
- Detection and audit recording of unacknowledged mission assignments
- Real-time notification and alerts for commanding dispatchers on timeout
- Strict safety invariant: Never silently reassigns resources on timeout;
  requires explicit dispatcher authorization.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models import Assignment, Incident, Resource, Notification, utc_now
from app.realtime.event_models import EventTypes, get_global_channel, get_incident_channel
from app.realtime.event_publisher import record_and_publish_event

logger = logging.getLogger("careon.responder_ops.acknowledgement")

DEFAULT_ACK_TIMEOUT_SECONDS = 180  # 3 minutes


def initiate_assignment_acknowledgement(
    db: Session,
    assignment: Assignment,
    timeout_seconds: int = DEFAULT_ACK_TIMEOUT_SECONDS,
) -> Assignment:
    """Initialize acknowledgement tracking and deadline for a newly created assignment."""
    assignment.acknowledgement_status = "pending"
    assignment.acknowledgement_deadline = utc_now() + timedelta(seconds=timeout_seconds)
    db.commit()
    return assignment


def check_and_process_acknowledgement_timeouts(db: Session) -> List[Dict[str, Any]]:
    """
    Periodic or triggered sweep for assignments that exceeded their acknowledgement deadline.
    Alerts dispatchers without silently reassigning resources.
    """
    now = utc_now()
    timed_out_assignments = (
        db.query(Assignment)
        .filter(
            Assignment.acknowledgement_status == "pending",
            Assignment.status == "Active",
            Assignment.acknowledgement_deadline <= now,
        )
        .all()
    )

    results: List[Dict[str, Any]] = []

    for assignment in timed_out_assignments:
        assignment.acknowledgement_status = "timeout"
        incident = assignment.incident
        resource = assignment.resource

        # Create alert notification for dispatchers
        db.add(Notification(
            user_id=None,  # Broadcast / dispatch alert
            incident_id=incident.id,
            title=f"⚠️ Responder Acknowledgement Timeout ({incident.incident_code})",
            message=(
                f"Assigned unit {resource.name} did not acknowledge emergency dispatch within deadline. "
                f"Dispatcher action required."
            ),
            type="alert",
        ))

        # Publish M4 Event: responder.assignment_timeout
        record_and_publish_event(
            db=db,
            event_type="responder.assignment_timeout",
            payload={
                "assignment_id": assignment.id,
                "incident_id": incident.id,
                "incident_code": incident.incident_code,
                "resource_id": resource.id,
                "resource_name": resource.name,
                "deadline": assignment.acknowledgement_deadline.isoformat() if assignment.acknowledgement_deadline else None,
                "timeout_at": now.isoformat(),
            },
            incident_id=incident.id,
            channel=get_global_channel(),
        )

        results.append({
            "assignment_id": assignment.id,
            "incident_code": incident.incident_code,
            "resource_name": resource.name,
            "status": "timeout_processed",
        })

    if timed_out_assignments:
        db.commit()
        logger.warning(f"Processed {len(timed_out_assignments)} responder assignment acknowledgement timeouts")

    return results
