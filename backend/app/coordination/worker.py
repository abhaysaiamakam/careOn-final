"""
Coordination Background Maintenance Worker.
Handles automated expiry sweeps for invitations and mutual aid requests,
as well as overdue task notifications.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.models import (
    IncidentAgencyCollaboration,
    AgencyResourceRequest,
    AgencyOperationalTask,
    utc_now,
)

logger = logging.getLogger("careon.coordination.worker")


def sweep_coordination_expiries(db: Session) -> Dict[str, int]:
    """
    Perform a periodic sweep of expired inter-agency collaborations and resource requests.
    """
    now = utc_now()
    stats = {
        "expired_collaborations": 0,
        "expired_resource_requests": 0,
        "overdue_tasks": 0,
    }

    # 1. Sweep expired collaborations
    expired_collabs = (
        db.query(IncidentAgencyCollaboration)
        .filter(
            IncidentAgencyCollaboration.expires_at <= now,
            IncidentAgencyCollaboration.collaboration_status.in_(["INVITED", "ACCEPTED", "ACTIVE"]),
        )
        .all()
    )
    for c in expired_collabs:
        c.collaboration_status = "REVOKED"
        c.revoked_at = now
        c.revoked_reason = "Expired automatically by system policy"
        stats["expired_collaborations"] += 1

    # 2. Sweep expired resource requests
    expired_requests = (
        db.query(AgencyResourceRequest)
        .filter(
            AgencyResourceRequest.expires_at <= now,
            AgencyResourceRequest.status.in_(["REQUESTED", "ACKNOWLEDGED"]),
        )
        .all()
    )
    for r in expired_requests:
        r.status = "EXPIRED"
        r.decision_notes = "Expired without timely response"
        r.updated_at = now
        stats["expired_resource_requests"] += 1

    # 3. Check overdue tasks
    overdue_tasks = (
        db.query(AgencyOperationalTask)
        .filter(
            AgencyOperationalTask.deadline <= now,
            AgencyOperationalTask.status.in_(["REQUESTED", "ACKNOWLEDGED", "IN_PROGRESS"]),
        )
        .all()
    )
    stats["overdue_tasks"] = len(overdue_tasks)

    if stats["expired_collaborations"] > 0 or stats["expired_resource_requests"] > 0:
        db.commit()

    return stats
