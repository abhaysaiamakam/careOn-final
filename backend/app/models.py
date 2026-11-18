from datetime import datetime, timezone
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
    text,
)
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


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
    created_at = Column(DateTime, default=utc_now)

    incidents = relationship("Incident", back_populates="user")
    notifications = relationship("Notification", back_populates="user")


class Incident(Base):
    __tablename__ = "incidents"

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

    id = Column(Integer, primary_key=True, index=True)
    resource_code = Column(String(30), unique=True, index=True, nullable=False)
    name = Column(String(120), nullable=False)
    category = Column(String(60), nullable=False)  # Ambulance, Medical Team, Fire Response, Rescue Team, First-Aid Team, Relief Vehicle, Shelter / Relief Centre
    capabilities = Column(String(255), nullable=False)  # e.g. "ALS,patient_transport,trauma_care"
    location_name = Column(String(200), nullable=False)
    latitude = Column(Float, nullable=False, default=12.3052)
    longitude = Column(Float, nullable=False, default=76.6552)
    status = Column(String(30), nullable=False, default="Available")  # Available, Assigned, Busy, Unavailable, Under Maintenance
    capacity = Column(Integer, nullable=False, default=1)
    contact_phone = Column(String(30), nullable=False)
    current_assignment_id = Column(Integer, nullable=True)
    last_updated = Column(DateTime, default=utc_now, onupdate=utc_now)

    assignments = relationship("Assignment", back_populates="resource")


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

    incident = relationship("Incident", back_populates="assignments")
    resource = relationship("Resource", back_populates="assignments")


class ExternalProvider(Base):
    __tablename__ = "external_providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    provider_type = Column(String(60), nullable=False)  # Hospital, Private Ambulance, NGO, Volunteer Organisation, Local Rescue
    is_registered_partner = Column(Boolean, default=True)  # True = Partner, False = Fallback Directory
    location_name = Column(String(200), nullable=False)
    latitude = Column(Float, nullable=False, default=12.3052)
    longitude = Column(Float, nullable=False, default=76.6552)
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
    # Not Contacted, Contacted, Awaiting Response, Available, Unavailable, Declined, Confirmed
    status = Column(String(40), nullable=False, default="Contacted")
    charge_quote = Column(Float, default=0.0)
    careon_fee = Column(Float, default=0.0)  # Always 0.0
    subsidy_amount = Column(Float, default=0.0)
    # Pending, Accepted, Declined, Not Required, Not Obtained
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
