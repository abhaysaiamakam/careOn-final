from datetime import datetime, timezone
from typing import Tuple, Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Date,
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
    facilities = relationship("HospitalFacility", back_populates="organization", cascade="all, delete-orphan")


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
    device_identifier = Column(String(64), unique=True, index=True, nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    is_revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    revoked_reason = Column(String(255), nullable=True)
    last_sync_at = Column(DateTime, nullable=True)
    sync_cursor = Column(String(64), nullable=False, default="0")
    last_seen_at = Column(DateTime, default=utc_now, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User")
    organization = relationship("Organization")
    sync_batches = relationship("SyncBatchReceipt", back_populates="device", cascade="all, delete-orphan")
    action_receipts = relationship("SyncActionReceipt", back_populates="device", cascade="all, delete-orphan")
    conflicts = relationship("SyncConflict", back_populates="device", cascade="all, delete-orphan")


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


# ==============================================================================
# Milestone 7 — Hospital Facilities, Dynamic Capacity & Coordination Models
# ==============================================================================
class HospitalFacility(Base):
    """
    Physical hospital facility profile under an Organization.
    Tracks precise geospatial coordinates, trauma/ICU capabilities, operating status,
    and emergency intake configurations.
    """
    __tablename__ = "hospital_facilities"
    __table_args__ = (
        Index("idx_hospital_facilities_geom", "geom", postgresql_using="gist"),
        Index("ix_hospital_facilities_org", "organization_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    facility_code = Column(String(30), unique=True, index=True, nullable=False)
    name = Column(String(120), nullable=False)
    facility_type = Column(String(50), nullable=False, default="General Hospital")
    location_name = Column(String(200), nullable=False)
    latitude = Column(Float, nullable=False, default=12.3052)
    longitude = Column(Float, nullable=False, default=76.6552)
    geom = Column(SpatialPoint, nullable=True)
    trauma_level = Column(String(30), nullable=False, default="Level 2")  # Level 1, Level 2, Level 3, None
    capabilities = Column(String(255), nullable=False, default="emergency,trauma,icu,ct_scan,blood_bank,ambulance_bay")
    specialist_services = Column(String(255), nullable=True, default="trauma_surgeon,cardiologist,neurologist,anesthesiologist")
    medical_equipment = Column(String(255), nullable=True, default="ct_scanner,mri,ventilators,defibrillators,dialysis")
    ambulance_bays = Column(Integer, nullable=False, default=4)
    operating_status = Column(String(30), nullable=False, default="operational")  # operational, limited, closed, diversion
    emergency_phone = Column(String(30), nullable=True)
    escalation_contact = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    last_verified_at = Column(DateTime, default=utc_now, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    organization = relationship("Organization", back_populates="facilities")
    capacities = relationship("HospitalCapacity", back_populates="facility", cascade="all, delete-orphan")
    reservations = relationship("HospitalCapacityReservation", back_populates="facility", cascade="all, delete-orphan")
    incoming_requests = relationship("IncomingPatientRequest", back_populates="facility", cascade="all, delete-orphan")
    diversion_logs = relationship("HospitalDiversionLog", back_populates="facility", cascade="all, delete-orphan")


class HospitalCapacity(Base):
    """
    Granular, independently tracked hospital capacity per category (ER beds, Trauma bays, ICU, etc.).
    Maintains total, occupied, reserved, and temporarily unavailable counts with freshness status.
    """
    __tablename__ = "hospital_capacities"
    __table_args__ = (
        UniqueConstraint("facility_id", "category", name="uq_facility_capacity_category"),
        Index("ix_hospital_capacities_facility", "facility_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    facility_id = Column(Integer, ForeignKey("hospital_facilities.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(50), nullable=False)  # er_beds, trauma_bays, icu_beds, critical_care_beds, ventilators, oxygen_beds, specialists
    total_capacity = Column(Integer, nullable=False, default=0)
    occupied_capacity = Column(Integer, nullable=False, default=0)
    reserved_capacity = Column(Integer, nullable=False, default=0)
    unavailable_capacity = Column(Integer, nullable=False, default=0)
    reporting_source = Column(String(50), nullable=False, default="staff_manual")  # staff_manual, hmis_integration, automated_sensor
    verification_status = Column(String(30), nullable=False, default="verified_current")  # verified_current, reported_unverified, aging, stale, unknown
    notes = Column(Text, nullable=True)
    last_updated = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    facility = relationship("HospitalFacility", back_populates="capacities")
    updated_by_user = relationship("User", foreign_keys=[updated_by_user_id])

    @property
    def available_capacity(self) -> int:
        return max(0, self.total_capacity - self.occupied_capacity - self.reserved_capacity - self.unavailable_capacity)


class HospitalCapacityReservation(Base):
    """
    Atomic capacity reservation linked to an incoming emergency patient / assignment.
    Prevents overbooking and ensures database-level concurrency protection.
    """
    __tablename__ = "hospital_capacity_reservations"
    __table_args__ = (
        Index("ix_hospital_reservations_facility_status", "facility_id", "status"),
        Index("ix_hospital_reservations_incident", "incident_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    reservation_token = Column(String(36), unique=True, index=True, nullable=False)
    facility_id = Column(Integer, ForeignKey("hospital_facilities.id", ondelete="CASCADE"), nullable=False, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True, index=True)
    category = Column(String(50), nullable=False, default="er_beds")
    quantity = Column(Integer, nullable=False, default=1)
    status = Column(String(30), default="active", nullable=False)  # active, fulfilled, released, expired, cancelled
    expires_at = Column(DateTime, nullable=False)
    released_at = Column(DateTime, nullable=True)
    release_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    facility = relationship("HospitalFacility", back_populates="reservations")
    incident = relationship("Incident")
    assignment = relationship("Assignment")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])


class IncomingPatientRequest(Base):
    """
    Hospital pre-arrival coordination request lifecycle.
    Tracks dispatcher destination selection, hospital review/acknowledgement/acceptance/decline,
    and capacity reservation linking.
    """
    __tablename__ = "incoming_patient_requests"
    __table_args__ = (
        Index("ix_incoming_requests_facility_status", "facility_id", "status"),
        Index("ix_incoming_requests_incident", "incident_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    request_token = Column(String(36), unique=True, index=True, nullable=False)
    facility_id = Column(Integer, ForeignKey("hospital_facilities.id", ondelete="CASCADE"), nullable=False, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=True, index=True)
    dispatcher_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(30), default="pending", nullable=False)  # pending, acknowledged, accepted, declined, needs_clarification, expired, cancelled
    emergency_severity = Column(String(30), nullable=False, default="High")  # Critical, High, Medium, Low
    patient_condition_summary = Column(String(255), nullable=True)  # Strictly non-PII operational summary
    eta_minutes = Column(Float, nullable=True)
    eta_source = Column(String(50), nullable=True)
    hospital_response_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    hospital_response_reason = Column(Text, nullable=True)
    clarification_notes = Column(Text, nullable=True)
    capacity_snapshot_json = Column(Text, nullable=True)
    acknowledgement_deadline = Column(DateTime, nullable=False)
    responded_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    facility = relationship("HospitalFacility", back_populates="incoming_requests")
    incident = relationship("Incident")
    assignment = relationship("Assignment")
    dispatcher = relationship("User", foreign_keys=[dispatcher_id])
    hospital_response_user = relationship("User", foreign_keys=[hospital_response_user_id])


class HospitalDiversionLog(Base):
    """
    Immutable audit history of hospital diversion state transitions.
    Supports full diversion, partial diversion, capability-specific restrictions, and closures.
    """
    __tablename__ = "hospital_diversion_logs"
    __table_args__ = (
        Index("ix_diversion_logs_facility", "facility_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    facility_id = Column(Integer, ForeignKey("hospital_facilities.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)  # open, partial_diversion, full_diversion, closed, emergency_only
    diversion_type = Column(String(50), nullable=True)  # trauma, pediatric, ct_down, ed_saturation, staffing
    reason = Column(Text, nullable=False)
    effective_from = Column(DateTime, default=utc_now, nullable=False)
    effective_until = Column(DateTime, nullable=True)
    authorized_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    facility = relationship("HospitalFacility", back_populates="diversion_logs")
    authorized_by_user = relationship("User", foreign_keys=[authorized_by_user_id])


# ==============================================================================
# Milestone 8 — Patient Identity, Encounters & Pre-Hospital Clinical Models
# ==============================================================================
class Patient(Base):
    """
    Patient identity entity.
    Supports unknown/unidentified patients, provisional IDs, verified identity,
    and distinct history verification states.
    """
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    patient_identifier = Column(String(40), unique=True, index=True, nullable=False)
    full_name = Column(String(120), nullable=True)
    identity_status = Column(String(30), default="unknown", nullable=False)  # unknown, provisional, verified
    date_of_birth = Column(Date, nullable=True)
    estimated_age = Column(Integer, nullable=True)
    gender = Column(String(20), default="unknown", nullable=False)  # male, female, non_binary, unknown
    contact_phone = Column(String(30), nullable=True)
    emergency_contact_name = Column(String(100), nullable=True)
    emergency_contact_phone = Column(String(30), nullable=True)
    blood_group = Column(String(10), nullable=True)
    known_allergies = Column(Text, nullable=True)
    known_medical_conditions = Column(Text, nullable=True)
    current_medications = Column(Text, nullable=True)
    history_verification_status = Column(String(30), default="unknown", nullable=False)  # patient_reported, family_reported, clinical_verified, unknown
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    encounters = relationship("EmergencyEncounter", back_populates="patient", cascade="all, delete-orphan")


class EmergencyEncounter(Base):
    """
    An emergency healthcare care episode linking an Incident, Patient, Mission Assignment,
    and Receiving Hospital Facility.
    """
    __tablename__ = "emergency_encounters"
    __table_args__ = (
        Index("ix_encounters_incident", "incident_id"),
        Index("ix_encounters_patient", "patient_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    encounter_code = Column(String(40), unique=True, index=True, nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_responder_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    receiving_facility_id = Column(Integer, ForeignKey("hospital_facilities.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(30), default="active", nullable=False)  # active, in_transport, handed_over, completed, cancelled
    chief_complaint = Column(String(255), nullable=False)
    initial_acuity = Column(String(30), default="High", nullable=False)  # Critical, High, Medium, Low
    started_at = Column(DateTime, default=utc_now, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    patient = relationship("Patient", back_populates="encounters")
    incident = relationship("Incident")
    assignment = relationship("Assignment")
    assigned_responder = relationship("User", foreign_keys=[assigned_responder_id])
    receiving_facility = relationship("HospitalFacility", foreign_keys=[receiving_facility_id])

    assessments = relationship("ClinicalAssessment", back_populates="encounter", cascade="all, delete-orphan")
    vitals = relationship("VitalSignObservation", back_populates="encounter", cascade="all, delete-orphan")
    interventions = relationship("PreHospitalIntervention", back_populates="encounter", cascade="all, delete-orphan")
    medications = relationship("MedicationAdministration", back_populates="encounter", cascade="all, delete-orphan")
    timeline_events = relationship("ClinicalTimelineEvent", back_populates="encounter", cascade="all, delete-orphan")
    handovers = relationship("DigitalHandoverRecord", back_populates="encounter", cascade="all, delete-orphan")
    attachments = relationship("HandoverAttachment", back_populates="encounter", cascade="all, delete-orphan")


class ClinicalAssessment(Base):
    """
    Structured physical & neurological assessment performed by field responders.
    """
    __tablename__ = "clinical_assessments"

    id = Column(Integer, primary_key=True, index=True)
    encounter_id = Column(Integer, ForeignKey("emergency_encounters.id", ondelete="CASCADE"), nullable=False, index=True)
    responder_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assessed_at = Column(DateTime, default=utc_now, nullable=False)
    consciousness_level = Column(String(30), default="Alert", nullable=False)  # Alert, Voice, Pain, Unresponsive
    airway_status = Column(String(50), default="clear", nullable=False)
    breathing_status = Column(String(50), default="normal", nullable=False)
    circulation_status = Column(String(50), default="normal_pulses", nullable=False)
    presenting_complaints = Column(Text, nullable=True)
    observed_injuries = Column(Text, nullable=True)
    symptoms = Column(Text, nullable=True)
    clinical_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    encounter = relationship("EmergencyEncounter", back_populates="assessments")
    responder = relationship("User", foreign_keys=[responder_id])


class VitalSignObservation(Base):
    """
    Periodic or continuous physiological vital sign observations.
    """
    __tablename__ = "vital_sign_observations"
    __table_args__ = (
        Index("ix_vitals_encounter_time", "encounter_id", "observed_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    encounter_id = Column(Integer, ForeignKey("emergency_encounters.id", ondelete="CASCADE"), nullable=False, index=True)
    recorded_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    observed_at = Column(DateTime, default=utc_now, nullable=False)
    heart_rate = Column(Integer, nullable=True)
    systolic_bp = Column(Integer, nullable=True)
    diastolic_bp = Column(Integer, nullable=True)
    respiratory_rate = Column(Integer, nullable=True)
    oxygen_saturation = Column(Float, nullable=True)
    body_temperature = Column(Float, nullable=True)
    blood_glucose = Column(Float, nullable=True)
    gcs_eye = Column(Integer, nullable=True)
    gcs_verbal = Column(Integer, nullable=True)
    gcs_motor = Column(Integer, nullable=True)
    gcs_total = Column(Integer, nullable=True)
    measurement_source = Column(String(50), default="manual", nullable=False)  # manual, monitor_automated, patient_reported
    data_quality = Column(String(30), default="verified", nullable=False)  # verified, provisional, artifact_flagged
    created_at = Column(DateTime, default=utc_now, nullable=False)

    encounter = relationship("EmergencyEncounter", back_populates="vitals")
    recorded_by = relationship("User", foreign_keys=[recorded_by_user_id])


class PreHospitalIntervention(Base):
    """
    Life-saving or supportive clinical interventions performed pre-hospital.
    """
    __tablename__ = "prehospital_interventions"

    id = Column(Integer, primary_key=True, index=True)
    encounter_id = Column(Integer, ForeignKey("emergency_encounters.id", ondelete="CASCADE"), nullable=False, index=True)
    performer_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    intervention_type = Column(String(60), nullable=False)  # oxygen_therapy, cpr, defibrillation, bleeding_control, immobilization, iv_access
    parameters_json = Column(Text, nullable=True)
    patient_response = Column(String(50), default="unchanged", nullable=False)  # improved, unchanged, deteriorated, successful
    notes = Column(Text, nullable=True)
    performed_at = Column(DateTime, default=utc_now, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    encounter = relationship("EmergencyEncounter", back_populates="interventions")
    performer = relationship("User", foreign_keys=[performer_id])


class MedicationAdministration(Base):
    """
    Field medication administration audit record.
    """
    __tablename__ = "medication_administrations"

    id = Column(Integer, primary_key=True, index=True)
    encounter_id = Column(Integer, ForeignKey("emergency_encounters.id", ondelete="CASCADE"), nullable=False, index=True)
    administering_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    medication_name = Column(String(100), nullable=False)
    dose = Column(Float, nullable=False)
    unit = Column(String(30), nullable=False)  # mg, mcg, mL, L
    route = Column(String(50), nullable=False)  # IV, IM, IN, PO, Sublingual, Nebulized
    response_notes = Column(Text, nullable=True)
    verification_status = Column(String(30), default="administered", nullable=False)  # administered, cosigned, standing_order
    administered_at = Column(DateTime, default=utc_now, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    encounter = relationship("EmergencyEncounter", back_populates="medications")
    administering_user = relationship("User", foreign_keys=[administering_user_id])


class ClinicalTimelineEvent(Base):
    """
    Immutable chronological timeline recording all operational and clinical events.
    Distinguishes client device timestamp from server receipt timestamp.
    """
    __tablename__ = "clinical_timeline_events"
    __table_args__ = (
        Index("ix_timeline_encounter_time", "encounter_id", "event_timestamp"),
    )

    id = Column(Integer, primary_key=True, index=True)
    event_token = Column(String(36), unique=True, index=True, nullable=False)
    encounter_id = Column(Integer, ForeignKey("emergency_encounters.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(60), nullable=False)
    event_timestamp = Column(DateTime, default=utc_now, nullable=False)
    server_receipt_timestamp = Column(DateTime, default=utc_now, nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_role = Column(String(30), nullable=False)
    structured_data_json = Column(Text, nullable=True)
    source_application = Column(String(40), default="responder_mobile", nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    encounter = relationship("EmergencyEncounter", back_populates="timeline_events")
    actor = relationship("User", foreign_keys=[actor_id])


class DigitalHandoverRecord(Base):
    """
    Formal digital handover document and clinical transfer of care agreement.
    Supports state machine progression, versioning, amendments, and dual-party confirmation.
    """
    __tablename__ = "digital_handover_records"
    __table_args__ = (
        Index("ix_handover_encounter_version", "encounter_id", "version"),
        Index("ix_handover_facility_status", "facility_id", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    handover_token = Column(String(36), unique=True, index=True, nullable=False)
    encounter_id = Column(Integer, ForeignKey("emergency_encounters.id", ondelete="CASCADE"), nullable=False, index=True)
    facility_id = Column(Integer, ForeignKey("hospital_facilities.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, default=1, nullable=False)
    previous_version_id = Column(Integer, ForeignKey("digital_handover_records.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(40), default="draft", nullable=False)  # draft, ready_for_handover, submitted, received, acknowledged, clarification_requested, correction_required, completed, cancelled
    sending_responder_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    receiving_staff_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    receiving_department = Column(String(100), nullable=True)
    received_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    clarification_notes = Column(Text, nullable=True)
    correction_reason = Column(Text, nullable=True)
    clinical_summary_json = Column(Text, nullable=True)
    outstanding_clinical_concerns = Column(Text, nullable=True)
    is_final = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    encounter = relationship("EmergencyEncounter", back_populates="handovers")
    facility = relationship("HospitalFacility")
    sending_responder = relationship("User", foreign_keys=[sending_responder_id])
    receiving_staff = relationship("User", foreign_keys=[receiving_staff_id])
    previous_version = relationship("DigitalHandoverRecord", remote_side=[id])
    attachments = relationship("HandoverAttachment", back_populates="handover")


class HandoverAttachment(Base):
    """
    Secure attachment associated with an emergency clinical encounter or handover document.
    """
    __tablename__ = "handover_attachments"

    id = Column(Integer, primary_key=True, index=True)
    attachment_token = Column(String(36), unique=True, index=True, nullable=False)
    encounter_id = Column(Integer, ForeignKey("emergency_encounters.id", ondelete="CASCADE"), nullable=False, index=True)
    handover_id = Column(Integer, ForeignKey("digital_handover_records.id", ondelete="SET NULL"), nullable=True, index=True)
    file_name = Column(String(150), nullable=False)
    file_type = Column(String(50), nullable=False)  # ecg_strip, injury_photo, prior_medical_record, transfer_form
    mime_type = Column(String(100), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    storage_path = Column(String(255), nullable=False)
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_confidential = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    encounter = relationship("EmergencyEncounter", back_populates="attachments")
    handover = relationship("DigitalHandoverRecord", back_populates="attachments")
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_user_id])


# ==============================================================================
# Milestone 9 — Offline-First Synchronization & Resilient Field Operations
# ==============================================================================


class SyncBatchReceipt(Base):
    """
    Tracks a submitted batch of queued offline synchronization actions.
    Records overall batch metrics and processing duration.
    """
    __tablename__ = "sync_batch_receipts"

    id = Column(Integer, primary_key=True, index=True)
    batch_uuid = Column(String(64), unique=True, nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("device_registrations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    total_actions = Column(Integer, nullable=False, default=0)
    accepted_actions = Column(Integer, nullable=False, default=0)
    failed_actions = Column(Integer, nullable=False, default=0)
    conflict_actions = Column(Integer, nullable=False, default=0)
    server_receipt_timestamp = Column(DateTime, default=utc_now, nullable=False)
    processing_time_ms = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    device = relationship("DeviceRegistration", back_populates="sync_batches")
    user = relationship("User", foreign_keys=[user_id])
    actions = relationship("SyncActionReceipt", back_populates="batch")


class SyncActionReceipt(Base):
    """
    Individual idempotent receipt for an action processed via sync upload.
    Enforces client_action_id deduplication and stores the authoritative result.
    """
    __tablename__ = "sync_action_receipts"

    id = Column(Integer, primary_key=True, index=True)
    action_uuid = Column(String(64), unique=True, nullable=False, index=True)
    batch_id = Column(Integer, ForeignKey("sync_batch_receipts.id", ondelete="SET NULL"), nullable=True, index=True)
    device_id = Column(Integer, ForeignKey("device_registrations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String(60), nullable=False)
    mission_id = Column(Integer, nullable=True, index=True)
    encounter_id = Column(Integer, nullable=True, index=True)
    client_timestamp = Column(DateTime, nullable=False)
    server_receipt_timestamp = Column(DateTime, default=utc_now, nullable=False)
    status = Column(String(40), nullable=False)  # ACKNOWLEDGED, PERMANENT_FAILURE, RETRYABLE_FAILURE, CONFLICT
    server_ack_id = Column(String(64), unique=True, nullable=False, index=True)
    payload_hash = Column(String(64), nullable=False)
    response_payload_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    device = relationship("DeviceRegistration", back_populates="action_receipts")
    user = relationship("User", foreign_keys=[user_id])
    batch = relationship("SyncBatchReceipt", back_populates="actions")


class SyncConflict(Base):
    """
    Records a state conflict between device-side action and authoritative server state.
    Provides structured data for operational review or automatic resolution.
    """
    __tablename__ = "sync_conflicts"

    id = Column(Integer, primary_key=True, index=True)
    conflict_token = Column(String(64), unique=True, nullable=False, index=True)
    action_uuid = Column(String(64), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("device_registrations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    mission_id = Column(Integer, nullable=True, index=True)
    encounter_id = Column(Integer, nullable=True, index=True)
    conflict_category = Column(String(40), nullable=False)  # MISSION_STATE, CLINICAL, ASSIGNMENT, TELEMETRY, DESTINATION
    reason = Column(Text, nullable=False)
    client_state_json = Column(Text, nullable=False)
    server_state_json = Column(Text, nullable=False)
    resolution_status = Column(String(30), nullable=False, default="PENDING")  # PENDING, RESOLVED_SERVER, RESOLVED_CLIENT, DISCARDED
    resolution_notes = Column(Text, nullable=True)
    resolved_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    device = relationship("DeviceRegistration", back_populates="conflicts")
    user = relationship("User", foreign_keys=[user_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_user_id])


class SyncAuditEvent(Base):
    """
    Immutable audit trail for synchronization events, security anomalies, and device revocations.
    """
    __tablename__ = "sync_audit_events"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("device_registrations.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(60), nullable=False)  # DEVICE_REGISTERED, DEVICE_REVOKED, BATCH_UPLOADED, CONFLICT_DETECTED, CONFLICT_RESOLVED, CURSOR_ADVANCED, ANOMALY_DETECTED
    details_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    device = relationship("DeviceRegistration", foreign_keys=[device_id])
    user = relationship("User", foreign_keys=[user_id])






