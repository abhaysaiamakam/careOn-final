"""
CareOn Milestone 4 — Real-Time Event Models and Contracts.

Defines the standard event envelope, typed categories, and channel routing helpers.
Enforces validation and serialization for multi-instance Redis Pub/Sub and WebSocket delivery.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import uuid
from pydantic import BaseModel, Field, ConfigDict


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventCategory(str, Enum):
    INCIDENT = "incident"
    DISPATCH = "dispatch"
    RESPONDER = "responder"
    RESOURCE = "resource"
    HOSPITAL = "hospital"


class EventTypes:
    # Incident lifecycle
    INCIDENT_CREATED = "incident.created"
    INCIDENT_UPDATED = "incident.updated"
    INCIDENT_PRIORITY_CHANGED = "incident.priority_changed"
    INCIDENT_VERIFIED = "incident.verified"
    INCIDENT_CANCELLED = "incident.cancelled"
    INCIDENT_RESOLVED = "incident.resolved"

    # Dispatch & Allocation
    DISPATCH_RECOMMENDATION_CREATED = "dispatch.recommendation_created"
    DISPATCH_ASSIGNMENT_APPROVED = "dispatch.assignment_approved"
    DISPATCH_ASSIGNMENT_CANCELLED = "dispatch.assignment_cancelled"
    DISPATCH_RESOURCE_CONFLICT = "dispatch.resource_conflict"

    # Responder field operations
    RESPONDER_MISSION_ASSIGNED = "responder.mission_assigned"
    RESPONDER_MISSION_ACCEPTED = "responder.mission_accepted"
    RESPONDER_MISSION_REJECTED = "responder.mission_rejected"
    RESPONDER_STATUS_CHANGED = "responder.status_changed"
    RESPONDER_LOCATION_UPDATED = "responder.location_updated"
    RESPONDER_ARRIVED_AT_INCIDENT = "responder.arrived_at_incident"
    RESPONDER_PATIENT_PICKED_UP = "responder.patient_picked_up"
    RESPONDER_ARRIVED_AT_HOSPITAL = "responder.arrived_at_hospital"

    # Resource fleet
    RESOURCE_AVAILABLE = "resource.available"
    RESOURCE_ASSIGNED = "resource.assigned"
    RESOURCE_RELEASED = "resource.released"
    RESOURCE_UNAVAILABLE = "resource.unavailable"

    # Hospital intake & capacity
    HOSPITAL_READINESS_CHANGED = "hospital.readiness_changed"
    HOSPITAL_INCOMING_PATIENT = "hospital.incoming_patient"
    HOSPITAL_PATIENT_ARRIVAL_CONFIRMED = "hospital.patient_arrival_confirmed"


# ---------------------------------------------------------------------------
# Channel Naming Conventions
# ---------------------------------------------------------------------------
def get_global_channel() -> str:
    """Platform-wide operational channel for dispatchers and super admins."""
    return "careon:events:global"


def get_org_channel(org_id: int) -> str:
    """Tenant organization-scoped channel (e.g. hospital, ambulance service)."""
    return f"careon:events:org:{org_id}"


def get_incident_channel(incident_id: int) -> str:
    """Incident-specific coordination channel for caller, dispatcher & assigned unit."""
    return f"careon:events:incident:{incident_id}"


def get_responder_channel(responder_id: int) -> str:
    """Private mission alert channel for an individual responder."""
    return f"careon:events:responder:{responder_id}"


def get_gps_cache_key(resource_id: int) -> str:
    """Redis key for latest high-frequency GPS coordinate cache."""
    return f"careon:responder:geo:{resource_id}"


# ---------------------------------------------------------------------------
# Standard Event Envelope
# ---------------------------------------------------------------------------
class RealtimeEvent(BaseModel):
    """
    Standard envelope for all CareOn operational events.
    Serialized to JSON for Redis Pub/Sub distribution and WebSocket delivery.
    """
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(..., description="e.g. incident.created, responder.status_changed")
    event_version: int = 1
    occurred_at: datetime = Field(default_factory=utc_now)
    organization_id: Optional[int] = None
    incident_id: Optional[int] = None
    actor_id: Optional[int] = None
    channel: str = Field(default_factory=get_global_channel)
    payload: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)

    def to_broadcast_dict(self) -> Dict[str, Any]:
        """Convert to dict with ISO 8601 timestamps for wire transmission."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "event_version": self.event_version,
            "occurred_at": self.occurred_at.isoformat(),
            "organization_id": self.organization_id,
            "incident_id": self.incident_id,
            "actor_id": self.actor_id,
            "channel": self.channel,
            "payload": self.payload,
        }
