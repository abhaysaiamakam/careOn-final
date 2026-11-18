from datetime import datetime, timezone
from typing import Tuple, Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Float,
    Boolean,
    ForeignKey,
    Index,
    UniqueConstraint,
    text,
    types as sqla_types,
)
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from geoalchemy2.elements import WKTElement
import geoalchemy2.admin.dialects.sqlite as s_admin

from app.database import Base

# Protect GeoAlchemy2 SQLite after_create from missing SpatiaLite functions during SQLite testing
_orig_sqlite_after_create = s_admin.after_create


def _safe_sqlite_after_create(table, bind, **kw):
    try:
        _orig_sqlite_after_create(table, bind, **kw)
    except Exception:
        pass


s_admin.after_create = _safe_sqlite_after_create


class SpatialPoint(sqla_types.TypeDecorator):
    """
    Cross-dialect spatial Point geometry type (SRID 4326).
    Uses PostGIS Geometry(POINT, 4326) on PostgreSQL.
    Falls back gracefully to Text on SQLite for isolated unit tests without SpatiaLite.
    """
    impl = Geometry("POINT", srid=4326, spatial_index=False)
    cache_ok = True
    spatial_index = False

    def load_dialect_impl(self, dialect):
        if dialect and dialect.name == "sqlite":
            return dialect.type_descriptor(sqla_types.Text())
        if dialect:
            return dialect.type_descriptor(Geometry("POINT", srid=4326, spatial_index=False))
        return Geometry("POINT", srid=4326, spatial_index=False)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect and dialect.name == "sqlite":
            return str(value)
        if isinstance(value, str):
            return WKTElement(value, srid=4326)
        return value

    def process_result_value(self, value, dialect):
        return value


def utc_now():
    return datetime.now(timezone.utc)


def validate_coordinates(latitude: float, longitude: float) -> Tuple[float, float]:
    """
    Validate geographic coordinates.
    Latitude must be between -90 and +90 degrees.
    Longitude must be between -180 and +180 degrees.
    """
    if latitude is None or longitude is None:
        raise ValueError("Latitude and longitude coordinates cannot be null.")
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        raise ValueError("Coordinates must be valid floating point numbers.")

    if not (-90.0 <= lat <= 90.0):
        raise ValueError(f"Invalid latitude: {lat}. Latitude must be between -90.0 and 90.0 degrees.")
    if not (-180.0 <= lon <= 180.0):
        raise ValueError(f"Invalid longitude: {lon}. Longitude must be between -180.0 and 180.0 degrees.")
    return lat, lon


def make_point_wkt(latitude: float, longitude: float) -> str:
    """Return SRID 4326 Point WKT string: POINT(longitude latitude)."""
    lat, lon = validate_coordinates(latitude, longitude)
    return f"SRID=4326;POINT({lon} {lat})"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(120), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    phone = Column(String(30), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="user")  # "user" or "admin"
    trust_score = Column(String(30), nullable=False, default="Unverified")  # Unverified, Mistaken, Confirmed Genuine, Confirmed Misuse
    trust_notes = Column(Text, nullable=True)
    is_flagged = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now)

    incidents = relationship("Incident", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    organization_memberships = relationship(
        "OrganizationMembership",
        back_populates="user",
        foreign_keys="OrganizationMembership.user_id",
        cascade="all, delete-orphan",
    )


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        Index("idx_incidents_geom", "geom", postgresql_using="gist"),
    )

    id = Column(Integer, primary_key=True, index=True)
    incident_code = Column(String(40), unique=True, index=True, nullable=False)
    tracking_token = Column(String(64), unique=True, index=True, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    category = Column(String(60), nullable=False)  # Medical, Road accident, Fire, Rescue, Safety / Other, Disaster / Multiple affected people
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    location_name = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=False, default=12.3052)
    longitude = Column(Float, nullable=False, default=76.6552)
    geom = Column(SpatialPoint, nullable=True)
    affected_people = Column(Integer, nullable=False, default=1)
    help_required = Column(String(150), nullable=False)
    contact_name = Column(String(100), nullable=False)
    contact_phone = Column(String(30), nullable=False)
    additional_details = Column(Text, nullable=True)
    
    priority = Column(String(20), nullable=False, default="High")  # Critical, High, Medium, Low
    priority_reason = Column(Text, nullable=True)
    
    # Status lifecycle:
    # Received -> Verification Pending -> Verified -> Assistance Search ->
    # Provider Contacted -> Awaiting Provider Response -> Awaiting User Consent ->
    # Assignment Confirmed -> Team Dispatched -> Team Arrived -> Resolved
    # Terminal: Cancelled, Rejected
    status = Column(String(40), nullable=False, default="Received")
    
    is_verified = Column(Boolean, default=False)
    verification_otp = Column(String(10), default="123456")
    is_duplicate = Column(Boolean, default=False)
    duplicate_of_id = Column(Integer, ForeignKey("incidents.id"), nullable=True)
    
    is_disaster = Column(Boolean, default=False)
    disaster_details = Column(Text, nullable=True)  # JSON-like or comma separated relief items
    internal_admin_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="incidents")
    updates = relationship("IncidentUpdate", back_populates="incident", cascade="all, delete-orphan", order_by="IncidentUpdate.created_at.desc()")
    assignments = relationship("Assignment", back_populates="incident", cascade="all, delete-orphan")
    provider_enquiries = relationship("ProviderEnquiry", back_populates="incident", cascade="all, delete-orphan")
    cancellation = relationship("Cancellation", back_populates="incident", uselist=False, cascade="all, delete-orphan")
    feedback = relationship("Feedback", back_populates="incident", uselist=False, cascade="all, delete-orphan")
    verification_logs = relationship("VerificationLog", back_populates="incident", cascade="all, delete-orphan")


class IncidentUpdate(Base):
    __tablename__ = "incident_updates"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    status = Column(String(40), nullable=False)
    message = Column(Text, nullable=False)
    actor = Column(String(100), nullable=False, default="System")
    is_public = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)

    incident = relationship("Incident", back_populates="updates")


class Resource(Base):
    __tablename__ = "resources"
    __table_args__ = (
        Index("idx_resources_geom", "geom", postgresql_using="gist"),
    )

    id = Column(Integer, primary_key=True, index=True)
    resource_code = Column(String(30), unique=True, index=True, nullable=False)
    name = Column(String(120), nullable=False)
    category = Column(String(60), nullable=False)  # Ambulance, Medical Team, Fire Response, Rescue Team, First-Aid Team, Relief Vehicle, Shelter / Relief Centre
    capabilities = Column(String(255), nullable=False)  # e.g. "ALS,patient_transport,trauma_care"
    location_name = Column(String(200), nullable=False)
    latitude = Column(Float, nullable=False, default=12.3052)
    longitude = Column(Float, nullable=False, default=76.6552)
    geom = Column(SpatialPoint, nullable=True)
    status = Column(String(30), nullable=False, default="Available")  # Available, Assigned, Busy, Unavailable, Under Maintenance
    capacity = Column(Integer, nullable=False, default=1)
    contact_phone = Column(String(30), nullable=False)
    equipment = Column(String(255), nullable=True, default="oxygen,first_aid_kit")  # e.g. "ventilator,defibrillator,oxygen,monitor,extrication_tools"
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    current_assignment_id = Column(Integer, nullable=True)
    assigned_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    last_updated = Column(DateTime, default=utc_now, onupdate=utc_now)

    assignments = relationship("Assignment", back_populates="resource")
    assigned_user = relationship("User", foreign_keys=[assigned_user_id])
    organization = relationship("Organization", foreign_keys=[organization_id])


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        Index(
            "uq_active_assignment_resource",
            "resource_id",
            unique=True,
            sqlite_where=text("status = 'Active'"),
            postgresql_where=text("status = 'Active'"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False)
    assigned_by = Column(String(100), nullable=False, default="Coordinator Aastha Singh")
    status = Column(String(30), nullable=False, default="Active")  # Active, Completed, Released, Cancelled
    assigned_at = Column(DateTime, default=utc_now)
    released_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    acknowledgement_status = Column(String(30), nullable=False, default="pending")  # pending, acknowledged, rejected, timeout
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledgement_deadline = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    incident = relationship("Incident", back_populates="assignments")
    resource = relationship("Resource", back_populates="assignments")
    mission_events = relationship("MissionEventLog", back_populates="assignment", cascade="all, delete-orphan")


class ExternalProvider(Base):
    __tablename__ = "external_providers"
    __table_args__ = (
        Index("idx_external_providers_geom", "geom", postgresql_using="gist"),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    provider_type = Column(String(60), nullable=False)  # Hospital, Private Ambulance, NGO, Volunteer Organisation, Local Rescue
    is_registered_partner = Column(Boolean, default=True)  # True = Partner, False = Fallback Directory
    location_name = Column(String(200), nullable=False)
    latitude = Column(Float, nullable=False, default=12.3052)
    longitude = Column(Float, nullable=False, default=76.6552)
    geom = Column(SpatialPoint, nullable=True)
    contact_person = Column(String(100), nullable=False)
    phone = Column(String(30), nullable=False)
    service_capabilities = Column(String(255), nullable=False)
    estimated_base_charge = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)

    enquiries = relationship("ProviderEnquiry", back_populates="provider")


class ProviderEnquiry(Base):
    __tablename__ = "provider_enquiries"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    provider_id = Column(Integer, ForeignKey("external_providers.id"), nullable=False)
    status = Column(String(40), nullable=False, default="Contacted")
    charge_quote = Column(Float, default=0.0)
    careon_fee = Column(Float, default=0.0)  # Always 0.0
    subsidy_amount = Column(Float, default=0.0)
    user_consent = Column(String(30), default="Not Required")
    response_time_minutes = Column(Integer, default=15)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    incident = relationship("Incident", back_populates="provider_enquiries")
    provider = relationship("ExternalProvider", back_populates="enquiries")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=True)
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(30), default="info")  # info, alert, success, warning
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)

    user = relationship("User", back_populates="notifications")


class Cancellation(Base):
    __tablename__ = "cancellations"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), unique=True, nullable=False)
    reason = Column(String(100), nullable=False)  # Emergency resolved, Help arranged independently, Request submitted by mistake, Other
    details = Column(Text, nullable=True)
    cancelled_by = Column(String(30), default="user")  # "user" or "admin"
    acknowledged_by_admin = Column(Boolean, default=False)
    resources_safely_released = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)

    incident = relationship("Incident", back_populates="cancellation")


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    rating = Column(Integer, nullable=False)  # 1 to 5
    tags = Column(String(200), nullable=True)  # comma separated
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    incident = relationship("Incident", back_populates="feedback")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(80), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(50), nullable=False)
    actor = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class VerificationLog(Base):
    __tablename__ = "verification_logs"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    verified_by = Column(String(100), nullable=False)
    decision = Column(String(50), nullable=False)  # Verified, Flagged Mistake, Flagged Deliberate Misuse, Unverified
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    incident = relationship("Incident", back_populates="verification_logs")


class ChatbotLog(Base):
    __tablename__ = "chatbot_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), nullable=False)
    user_message = Column(Text, nullable=False)
    bot_response = Column(Text, nullable=False)
    intent_detected = Column(String(60), nullable=False)
    created_at = Column(DateTime, default=utc_now)


# Backward-compatibility model for existing tests
class Emergency(Base):
    __tablename__ = "emergencies"

    id = Column(Integer, primary_key=True, index=True)
    patient_name = Column(String(100), nullable=False)
    room_number = Column(String(50), nullable=False)
    emergency_type = Column(String(50), nullable=False)
    priority = Column(String(20), nullable=False, default="High")
    status = Column(String(20), nullable=False, default="Pending")
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


# ==============================================================================
# Milestone 2 — Identity, Session & Multi-Organization Models
# ==============================================================================
class RefreshToken(Base):
    """
    Stores SHA-256 hashed refresh tokens.
    Raw tokens are never persisted. Token family tracking enables immediate
    invalidation of all descended tokens when reuse (theft) is detected.
    """
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    family_id = Column(String(32), index=True, nullable=False)
    session_id = Column(String(64), index=True, nullable=True)
    device_hint = Column(String(200), nullable=True)
    is_revoked = Column(Boolean, default=False, nullable=False, index=True)
    revoked_reason = Column(String(50), nullable=True)  # rotated, logout, reuse_detected, expired
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utc_now)
    revoked_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="refresh_tokens")


class UserSession(Base):
    """
    Tracks client sessions across devices with device hints and activity timestamps.
    """
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_hint = Column(String(200), nullable=True)
    ip_address = Column(String(45), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    last_seen_at = Column(DateTime, default=utc_now)
    created_at = Column(DateTime, default=utc_now)
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="sessions")


class Organization(Base):
    """
    Emergency service organization record (e.g. Ambulance Service, Hospital, Fire, Police).
    """
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    org_type = Column(String(50), nullable=False)  # ambulance_service, hospital, fire, police, disaster_response, other
    description = Column(Text, nullable=True)
    contact_email = Column(String(120), nullable=True)
    contact_phone = Column(String(30), nullable=True)
    location_name = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    memberships = relationship("OrganizationMembership", back_populates="organization", cascade="all, delete-orphan")
    readiness = relationship("HospitalReadiness", back_populates="organization", uselist=False, cascade="all, delete-orphan")


class OrganizationMembership(Base):
    """
    User membership within an organization, supporting organization-scoped roles.
    """
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_user_membership"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    membership_role = Column(String(30), nullable=False, default="member")  # member, dispatcher, admin
    status = Column(String(20), nullable=False, default="active")  # active, inactive, pending
    joined_at = Column(DateTime, default=utc_now)
    invited_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    organization = relationship("Organization", back_populates="memberships")
    user = relationship("User", back_populates="organization_memberships", foreign_keys=[user_id])


# ==============================================================================
# Milestone 3 — Hospital Readiness & Field Capacity Model
# ==============================================================================
class HospitalReadiness(Base):
    """
    Real-time hospital capacity, emergency department status, and diversion tracking.
    Enforces M2 organization isolation: each hospital org has one readiness record.
    """
    __tablename__ = "hospital_readiness"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    total_er_beds = Column(Integer, nullable=False, default=20)
    available_er_beds = Column(Integer, nullable=False, default=15)
    icu_beds_total = Column(Integer, nullable=False, default=8)
    icu_beds_available = Column(Integer, nullable=False, default=4)
    trauma_bays_total = Column(Integer, nullable=False, default=4)
    trauma_bays_available = Column(Integer, nullable=False, default=2)
    operating_rooms_total = Column(Integer, nullable=False, default=3)
    operating_rooms_available = Column(Integer, nullable=False, default=1)
    divert_status = Column(Boolean, default=False, nullable=False)
    divert_reason = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    organization = relationship("Organization", back_populates="readiness")
    updated_by_user = relationship("User", foreign_keys=[updated_by_user_id])


# ==============================================================================
# Milestone 4 — Real-Time Transactional Outbox Model
# ==============================================================================
class OutboxEvent(Base):
    """
    Transactional Outbox pattern for guaranteed event delivery.
    Critical state mutations commit business data and an OutboxEvent in the same
    database transaction. An asynchronous or relay publisher then forwards events
    to Redis Pub/Sub for multi-instance WebSocket distribution.
    """
    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("ix_outbox_events_unpub", "is_published", "created_at"),
        Index("ix_outbox_events_channel_created", "channel", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(36), unique=True, index=True, nullable=False)  # UUID
    event_type = Column(String(64), index=True, nullable=False)
    event_version = Column(Integer, default=1, nullable=False)
    occurred_at = Column(DateTime, default=utc_now, nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    channel = Column(String(100), nullable=False, default="careon:events:global", index=True)
    payload_json = Column(Text, nullable=False)
    is_published = Column(Boolean, default=False, nullable=False, index=True)
    published_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)


# ==============================================================================
# Milestone 5 — Intelligent Dispatch Decision & Audit Log Model
# ==============================================================================
class DispatchDecision(Base):
    """
    Immutable audit record for every intelligent dispatch decision.
    Captures:
    - Incident evaluated
    - Evaluated candidates and scoring breakdown (explainability)
    - Original algorithm recommendation
    - Dispatcher decision: approval or override
    - Mandatory override reason when overriding
    - ETA and its provenance (road-network vs fallback)
    """
    __tablename__ = "dispatch_decisions"
    __table_args__ = (
        Index("ix_dispatch_decisions_incident", "incident_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    decision_id = Column(String(36), unique=True, index=True, nullable=False)
    incident_id = Column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_version = Column(Integer, default=1, nullable=False)
    candidates_json = Column(Text, nullable=False)
    recommended_resource_id = Column(Integer, ForeignKey("resources.id", ondelete="SET NULL"), nullable=True)
    selected_resource_id = Column(Integer, ForeignKey("resources.id", ondelete="SET NULL"), nullable=False)
    dispatcher_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    dispatcher_name = Column(String(100), nullable=False)
    decision_type = Column(String(30), nullable=False)  # approved, overridden
    override_reason = Column(Text, nullable=True)
    scoring_weights_version = Column(String(20), default="v1.0", nullable=False)
    eta_minutes = Column(Float, nullable=True)
    eta_source = Column(String(50), nullable=True)  # osrm_road_network, haversine_fallback, cache_osrm
    created_at = Column(DateTime, default=utc_now, nullable=False)

    incident = relationship("Incident", foreign_keys=[incident_id])
    recommended_resource = relationship("Resource", foreign_keys=[recommended_resource_id])
    selected_resource = relationship("Resource", foreign_keys=[selected_resource_id])
    dispatcher = relationship("User", foreign_keys=[dispatcher_id])


# ==============================================================================
# Milestone 6 — Responder Mission State Machine & Event Logs
# ==============================================================================
class MissionEventLog(Base):
    """
    Immutable mission event audit log tracking responder operations.
    Captures: assigned -> accepted -> en_route -> on_scene -> patient_picked_up -> hospital_arrival -> handover -> completed.
    Includes client idempotency keys, offline timestamps, and geospatial coordinates.
    """
    __tablename__ = "mission_event_logs"
    __table_args__ = (
        Index("ix_mission_events_assignment", "assignment_id", "server_timestamp"),
        Index("ix_mission_events_incident", "incident_id", "server_timestamp"),
    )

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_id = Column(Integer, ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_role = Column(String(30), nullable=False)
    previous_status = Column(String(40), nullable=True)
    new_status = Column(String(40), nullable=False)
    client_action_id = Column(String(64), nullable=True, index=True)  # Client idempotency key
    client_timestamp = Column(DateTime, nullable=True)
    server_timestamp = Column(DateTime, default=utc_now, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    hospital_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)

    assignment = relationship("Assignment", back_populates="mission_events")
    incident = relationship("Incident")
    resource = relationship("Resource")
    actor = relationship("User", foreign_keys=[actor_id])
    hospital = relationship("Organization", foreign_keys=[hospital_id])


# ==============================================================================
# Milestone 6 — Push Notification Infrastructure Models
# ==============================================================================
class DeviceRegistration(Base):
    """
    Device tokens registered by responders (PWA Web Push, Capacitor, or Native).
    Supports token replacement, platform targeting (fcm, apns, web_push), and deactivation.
    """
    __tablename__ = "device_registrations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_token = Column(String(255), unique=True, index=True, nullable=False)
    platform = Column(String(30), nullable=False)  # fcm, apns, web_push
    device_model = Column(String(100), nullable=True)
    app_version = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_seen_at = Column(DateTime, default=utc_now, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    user = relationship("User")


class NotificationDeliveryLog(Base):
    """
    Audit and delivery tracking log for emergency push notifications.
    Strict privacy: zero sensitive patient PII or internal triage records stored in payload.
    """
    __tablename__ = "notification_delivery_logs"
    __table_args__ = (
        Index("ix_notification_logs_user", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    notification_id = Column(String(36), unique=True, index=True, nullable=False)  # UUID
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_token = Column(String(255), nullable=True)
    platform = Column(String(30), nullable=False)
    category = Column(String(50), nullable=False)  # new_assignment, ack_reminder, cancellation, mission_update, critical_alert
    title = Column(String(150), nullable=False)
    body = Column(String(255), nullable=False)
    status = Column(String(30), default="queued", nullable=False)  # queued, sent, delivered, failed, expired
    retry_count = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    idempotency_key = Column(String(64), nullable=True, index=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    sent_at = Column(DateTime, nullable=True)

    user = relationship("User")


# ==============================================================================
# Milestone 6 — Responder Telemetry & Location Freshness Log
# ==============================================================================
class ResponderTelemetryLog(Base):
    """
    Continuous telemetry log supporting batch submission, offline sync buffering,
    GPS accuracy metadata, and velocity anomaly detection.
    """
    __tablename__ = "responder_telemetry_logs"
    __table_args__ = (
        Index("ix_telemetry_resource_time", "resource_id", "server_timestamp"),
    )

    id = Column(Integer, primary_key=True, index=True)
    resource_id = Column(Integer, ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    speed = Column(Float, nullable=True)
    heading = Column(Float, nullable=True)
    accuracy = Column(Float, nullable=True)
    battery_level = Column(Float, nullable=True)
    network_type = Column(String(30), nullable=True)
    freshness_status = Column(String(30), default="verified_live", nullable=False)
    is_buffered = Column(Boolean, default=False, nullable=False)
    client_action_id = Column(String(64), nullable=True, index=True)
    client_timestamp = Column(DateTime, nullable=True)
    server_timestamp = Column(DateTime, default=utc_now, nullable=False)

    resource = relationship("Resource")
    user = relationship("User")



