from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict


# ==============================================================================
# Auth Schemas
# ==============================================================================
class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=120)
    phone: str = Field(..., min_length=8, max_length=20)
    password: str = Field(..., min_length=6)
    confirm_password: Optional[str] = None
    role: Optional[str] = "user"


class UserLogin(BaseModel):
    email: str = Field(..., min_length=5, max_length=120)
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    role: str
    trust_score: str
    is_flagged: bool
    is_active: Optional[bool] = True
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    refresh_token: Optional[str] = None
    user: UserResponse


# ==============================================================================
# Incident Schemas
# ==============================================================================
class IncidentCreate(BaseModel):
    category: str = Field(..., description="Medical, Road accident, Fire, Rescue, Safety / Other, Disaster / Multiple affected people")
    description: str = Field(..., min_length=5)
    location_name: str = Field(..., min_length=2)
    latitude: Optional[float] = Field(default=12.3052, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=76.6552, ge=-180.0, le=180.0)
    affected_people: Optional[int] = 1
    help_required: str = Field(..., min_length=2)
    contact_name: str = Field(..., min_length=2)
    contact_phone: str = Field(..., min_length=8)
    additional_details: Optional[str] = None
    is_disaster: Optional[bool] = False
    disaster_details: Optional[str] = None


class IncidentVerify(BaseModel):
    otp: str = Field(..., min_length=4, max_length=8)


class IncidentStatusUpdate(BaseModel):
    status: str
    message: Optional[str] = None
    internal_admin_notes: Optional[str] = None


class IncidentPriorityUpdate(BaseModel):
    priority: str
    reason: str


class IncidentCancel(BaseModel):
    reason: str = Field(..., description="Emergency resolved, Help arranged independently, Request submitted by mistake, Other")
    details: Optional[str] = None


class IncidentUpdateItem(BaseModel):
    id: int
    status: str
    message: str
    actor: str
    is_public: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResourceSimple(BaseModel):
    id: int
    resource_code: str
    name: str
    category: str
    contact_phone: str
    status: str
    latitude: float
    longitude: float

    model_config = ConfigDict(from_attributes=True)


class AssignmentResponse(BaseModel):
    id: int
    incident_id: int
    resource_id: int
    assigned_by: str
    status: str
    assigned_at: datetime
    released_at: Optional[datetime] = None
    notes: Optional[str] = None
    resource: Optional[ResourceSimple] = None

    model_config = ConfigDict(from_attributes=True)


class ProviderEnquiryResponse(BaseModel):
    id: int
    incident_id: int
    provider_id: int
    status: str
    charge_quote: float
    careon_fee: float
    subsidy_amount: float
    user_consent: str
    response_time_minutes: int
    notes: Optional[str] = None
    provider_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FeedbackResponse(BaseModel):
    id: int
    rating: int
    tags: Optional[str] = None
    comments: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncidentResponse(BaseModel):
    id: int
    incident_code: str
    tracking_token: Optional[str] = None
    user_id: Optional[int] = None
    category: str
    title: str
    description: str
    location_name: str
    latitude: float
    longitude: float
    affected_people: int
    help_required: str
    contact_name: str
    contact_phone: str
    additional_details: Optional[str] = None
    priority: str
    priority_reason: Optional[str] = None
    status: str
    is_verified: bool
    verification_otp: Optional[str] = None
    is_duplicate: bool
    is_disaster: bool
    disaster_details: Optional[str] = None
    internal_admin_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncidentDetailResponse(IncidentResponse):
    updates: List[IncidentUpdateItem] = []
    assignments: List[AssignmentResponse] = []
    provider_enquiries: List[ProviderEnquiryResponse] = []
    feedback: Optional[FeedbackResponse] = None


class IncidentPublicTrackingUpdateItem(BaseModel):
    status: str
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncidentPublicTrackingResponse(BaseModel):
    """Sanitized public tracking response that never leaks PII, phone, or private medical details."""
    incident_code: str
    category: str
    status: str
    priority: str
    location_name: str
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    updates: List[IncidentPublicTrackingUpdateItem] = []

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# Resource Schemas
# ==============================================================================
class ResourceCreate(BaseModel):
    resource_code: str
    name: str
    category: str
    capabilities: str
    location_name: str
    latitude: float = Field(default=12.3052, ge=-90.0, le=90.0)
    longitude: float = Field(default=76.6552, ge=-180.0, le=180.0)
    status: Optional[str] = "Available"
    capacity: Optional[int] = 1
    contact_phone: str


class ResourceUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    capabilities: Optional[str] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: Optional[str] = None
    capacity: Optional[int] = None
    contact_phone: Optional[str] = None


class ResourceResponse(BaseModel):
    id: int
    resource_code: str
    name: str
    category: str
    capabilities: str
    location_name: str
    latitude: float
    longitude: float
    status: str
    capacity: int
    contact_phone: str
    current_assignment_id: Optional[int] = None
    last_updated: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# Allocation Schemas
# ==============================================================================
class AllocationRecommendRequest(BaseModel):
    incident_id: int


class AllocationConfirmRequest(BaseModel):
    incident_id: int
    resource_id: int
    notes: Optional[str] = None


# ==============================================================================
# Provider Schemas
# ==============================================================================
class ProviderCreate(BaseModel):
    name: str
    provider_type: str
    is_registered_partner: bool = True
    location_name: str
    latitude: float = Field(default=12.3052, ge=-90.0, le=90.0)
    longitude: float = Field(default=76.6552, ge=-180.0, le=180.0)
    contact_person: str
    phone: str
    service_capabilities: str
    estimated_base_charge: float = 0.0


class ProviderResponse(BaseModel):
    id: int
    name: str
    provider_type: str
    is_registered_partner: bool
    location_name: str
    latitude: float
    longitude: float
    contact_person: str
    phone: str
    service_capabilities: str
    estimated_base_charge: float
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ProviderEnquiryCreate(BaseModel):
    incident_id: int
    provider_id: int
    status: Optional[str] = "Contacted"
    charge_quote: Optional[float] = 0.0
    subsidy_amount: Optional[float] = 0.0
    user_consent: Optional[str] = "Pending"
    response_time_minutes: Optional[int] = 15
    notes: Optional[str] = None


class ProviderEnquiryUpdate(BaseModel):
    status: Optional[str] = None
    charge_quote: Optional[float] = None
    user_consent: Optional[str] = None
    notes: Optional[str] = None


# ==============================================================================
# Notifications & Feedback
# ==============================================================================
class NotificationResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    incident_id: Optional[int] = None
    title: str
    message: str
    type: str
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FeedbackCreate(BaseModel):
    incident_id: int
    rating: int = Field(..., ge=1, le=5)
    tags: Optional[str] = None
    comments: Optional[str] = None


# ==============================================================================
# Chatbot & Simulation
# ==============================================================================
class ChatbotMessageRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default_session"


class ChatbotMessageResponse(BaseModel):
    reply: str
    intent: str
    suggested_actions: List[Dict[str, Any]] = []


class SimulationRunRequest(BaseModel):
    scenario: Optional[str] = "resource_shortage_challenge"


# ==============================================================================
# Backward Compatibility for existing tests
# ==============================================================================
class EmergencyCreate(BaseModel):
    patient_name: str = Field(..., min_length=1, max_length=100)
    room_number: str = Field(..., min_length=1, max_length=50)
    emergency_type: str = Field(..., min_length=1, max_length=50)
    priority: str = Field(default="High", pattern="^(Critical|High|Medium|Low)$")
    description: Optional[str] = Field(default=None, max_length=500)


class EmergencyUpdateStatus(BaseModel):
    status: str = Field(..., pattern="^(Pending|Responded|Resolved)$")


class EmergencyResponse(BaseModel):
    id: int
    patient_name: str
    room_number: str
    emergency_type: str
    priority: str
    status: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StatsResponse(BaseModel):
    total: int
    pending: int
    responded: int
    resolved: int
    critical: int
    available_resources: Optional[int] = 0
    active_shortages: Optional[int] = 0


class HealthResponse(BaseModel):
    status: str
    database: str
    timestamp: str
    version: str


# ==============================================================================
# Milestone 2 — Identity, RBAC & Multi-Organization Schemas
# ==============================================================================
class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)
    confirm_password: str


class PasswordResetRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=120)


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)
    confirm_password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: int = 1800  # 30 min in seconds
    user: UserResponse


class UserProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    phone: Optional[str] = Field(default=None, min_length=8, max_length=30)


class UserStatusUpdate(BaseModel):
    is_active: bool
    reason: Optional[str] = None


class UserRoleUpdate(BaseModel):
    role: str = Field(..., description="citizen, dispatcher, responder, hospital_staff, org_admin, super_admin")


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    org_type: str = Field(..., min_length=2, max_length=50)
    description: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    location_name: Optional[str] = None


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    org_type: Optional[str] = None
    description: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    location_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None


class OrganizationResponse(BaseModel):
    id: int
    name: str
    org_type: str
    description: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    location_name: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class MembershipCreate(BaseModel):
    user_id: int
    membership_role: str = Field(default="member", pattern="^(member|dispatcher|admin)$")


class MembershipUpdate(BaseModel):
    membership_role: Optional[str] = Field(default=None, pattern="^(member|dispatcher|admin)$")
    status: Optional[str] = Field(default=None, pattern="^(active|inactive|pending)$")


class MembershipResponse(BaseModel):
    id: int
    organization_id: int
    user_id: int
    membership_role: str
    status: str
    joined_at: datetime
    user: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)


class SessionResponse(BaseModel):
    session_id: str
    device_hint: Optional[str] = None
    ip_address: Optional[str] = None
    is_active: bool
    last_seen_at: datetime
    created_at: datetime
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# Milestone 3 — Five-Application Ecosystem Schemas
# ==============================================================================

class MissionResponse(BaseModel):
    id: int  # Assignment ID
    incident_id: int
    incident_code: str
    category: str
    priority: str
    title: str
    description: str
    location_name: str
    latitude: float
    longitude: float
    affected_people: int
    help_required: str
    status: str
    incident_status: str
    assigned_at: datetime
    resource_id: int
    resource_code: str
    resource_name: str
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MissionActionRequest(BaseModel):
    reason: Optional[str] = None


class MissionStatusUpdate(BaseModel):
    status: str = Field(..., description="Accepted, En Route, On Scene, Transporting, Arrived Hospital, Cleared, Completed")
    notes: Optional[str] = None


class ResponderTelemetryUpdate(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    heading: Optional[float] = None
    speed: Optional[float] = None


class HospitalReadinessUpdate(BaseModel):
    total_er_beds: Optional[int] = Field(default=None, ge=0)
    available_er_beds: Optional[int] = Field(default=None, ge=0)
    icu_beds_total: Optional[int] = Field(default=None, ge=0)
    icu_beds_available: Optional[int] = Field(default=None, ge=0)
    trauma_bays_total: Optional[int] = Field(default=None, ge=0)
    trauma_bays_available: Optional[int] = Field(default=None, ge=0)
    operating_rooms_total: Optional[int] = Field(default=None, ge=0)
    operating_rooms_available: Optional[int] = Field(default=None, ge=0)
    divert_status: Optional[bool] = None
    divert_reason: Optional[str] = None


class HospitalReadinessResponse(BaseModel):
    id: int
    organization_id: int
    organization_name: Optional[str] = None
    total_er_beds: int
    available_er_beds: int
    icu_beds_total: int
    icu_beds_available: int
    trauma_bays_total: int
    trauma_bays_available: int
    operating_rooms_total: int
    operating_rooms_available: int
    divert_status: bool
    divert_reason: Optional[str] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncomingPatientResponse(BaseModel):
    incident_id: int
    incident_code: str
    category: str
    priority: str
    affected_people: int
    location_name: str
    transport_status: str
    resource_name: Optional[str] = None
    resource_code: Optional[str] = None
    eta_minutes: Optional[int] = None
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PatientArrivalAcknowledge(BaseModel):
    bed_type: Optional[str] = Field(default="er_bed", description="er_bed, icu_bed, trauma_bay, operating_room")
    intake_notes: Optional[str] = None


class AuditLogQueryResponse(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: str
    actor: str
    details: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SystemHealthResponse(BaseModel):
    status: str
    database_connected: bool
    postgis_available: bool
    redis_connected: bool
    active_incidents: int
    available_resources: int
    total_users: int
    total_organizations: int
    audit_log_count: int
    timestamp: datetime


# ==============================================================================
# Milestone 5 — Intelligent Dispatch & Resource Optimization Schemas
# ==============================================================================
class DispatchAssessmentResponse(BaseModel):
    incident_id: int
    incident_code: str
    reported_priority: str
    recommended_priority: str
    severity: str
    required_capabilities: List[str]
    required_equipment: List[str]
    confidence_score: float
    missing_information: List[str]
    is_geospatially_valid: bool
    is_duplicate_candidate: bool
    duplicate_of_code: Optional[str] = None
    has_active_assignment: bool
    explanation: str
    assessed_at: str


class CandidateScoreResponse(BaseModel):
    resource_id: int
    resource_code: str
    resource_name: str
    category: str
    eligibility_status: str
    overall_score: float
    eta_minutes: float
    eta_source: str
    distance_km: float
    is_fallback_routing: bool
    capability_match: Dict[str, Any]
    equipment_match: Dict[str, Any]
    location_freshness_seconds: float
    conflicts_or_warnings: List[str]
    ineligibility_reasons: List[str]
    explanation: str


class DispatchRecommendationResponse(BaseModel):
    incident_id: int
    incident_code: str
    assessment: DispatchAssessmentResponse
    top_recommendation: Optional[CandidateScoreResponse] = None
    ranked_candidates: List[CandidateScoreResponse]
    total_candidates_evaluated: int
    eligible_count: int


class DispatchOptimizationPlanItemResponse(BaseModel):
    incident_id: int
    incident_code: str
    priority: str
    severity: str
    status: str
    recommended_resource_id: Optional[int] = None
    recommended_resource_name: Optional[str] = None
    recommended_resource_code: Optional[str] = None
    score: float
    eta_minutes: Optional[float] = None
    eta_source: Optional[str] = None
    distance_km: Optional[float] = None
    rationale: str
    bottleneck_reason: Optional[str] = None
    competing_incidents: List[str] = []


class DispatchOptimizationResponse(BaseModel):
    plan_id: str
    generated_at: str
    algorithm_version: str
    total_incidents_evaluated: int
    assigned_count: int
    unassigned_count: int
    allocations: List[DispatchOptimizationPlanItemResponse]
    fleet_utilization_percent: float
    systemic_rationale: str


class DispatchApproveRequest(BaseModel):
    incident_id: int
    resource_id: int
    notes: Optional[str] = None


class DispatchOverrideRequest(BaseModel):
    incident_id: int
    resource_id: int
    override_reason: str = Field(..., min_length=5, description="Mandatory reason for overriding algorithm recommendation")
    notes: Optional[str] = None


class DispatchDecisionResponse(BaseModel):
    id: int
    decision_id: str
    incident_id: int
    recommendation_version: int
    selected_resource_id: int
    dispatcher_name: str
    decision_type: str
    override_reason: Optional[str] = None
    eta_minutes: Optional[float] = None
    eta_source: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HospitalDiversionUpdateRequest(BaseModel):
    divert_status: bool
    divert_reason: Optional[str] = None


class HospitalDiversionResponse(BaseModel):
    organization_id: int
    divert_status: bool
    divert_reason: Optional[str] = None
    updated_at: str


class HospitalRecommendationResponse(BaseModel):
    organization_id: int
    hospital_name: str
    location_name: str
    distance_km: float
    eta_minutes: float
    eta_source: str
    divert_status: bool
    divert_reason: Optional[str] = None
    available_er_beds: int
    trauma_bays_available: int
    recommendation_tier: str
    rationale: str


class ResourceCapabilityUpdateRequest(BaseModel):
    capabilities: Optional[str] = None
    equipment: Optional[str] = None
    capacity: Optional[int] = None
    status: Optional[str] = None


# ==============================================================================
# Milestone 6 — Responder Operations, Mobile Reliability & Notification Schemas
# ==============================================================================

class DeviceRegistrationCreate(BaseModel):
    device_token: str = Field(..., min_length=4, max_length=255)
    platform: str = Field(..., description="fcm, apns, or web_push")
    device_model: Optional[str] = Field(None, max_length=100)
    app_version: Optional[str] = Field(None, max_length=50)


class DeviceRegistrationResponse(BaseModel):
    id: int
    user_id: int
    device_token: str
    platform: str
    device_model: Optional[str] = None
    app_version: Optional[str] = None
    is_active: bool
    last_seen_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MissionAcknowledgementRequest(BaseModel):
    action: str = Field(..., description="'accept' or 'reject'")
    rejection_reason: Optional[str] = Field(None, description="Mandatory when action is 'reject'")
    client_action_id: Optional[str] = None


class MissionTransitionRequest(BaseModel):
    target_status: str = Field(..., description="e.g. en_route_incident, arrived_scene, patient_contact, patient_picked_up, en_route_hospital, arrived_hospital, handover_initiated, handover_completed, completed, cancelled")
    client_action_id: Optional[str] = None
    client_timestamp: Optional[datetime] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    hospital_id: Optional[int] = None
    notes: Optional[str] = None
    rejection_reason: Optional[str] = None


class MissionTransitionResponse(BaseModel):
    assignment_id: int
    incident_id: int
    resource_id: int
    previous_status: Optional[str]
    current_status: str
    is_duplicate_replay: bool
    server_timestamp: datetime


class MissionEventLogResponse(BaseModel):
    id: int
    assignment_id: int
    incident_id: int
    resource_id: int
    actor_id: Optional[int] = None
    actor_role: str
    previous_status: Optional[str] = None
    new_status: str
    client_action_id: Optional[str] = None
    client_timestamp: Optional[datetime] = None
    server_timestamp: datetime
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    hospital_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class TelemetryPointSchema(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    speed: Optional[float] = Field(None, ge=0.0)
    heading: Optional[float] = Field(None, ge=0.0, le=360.0)
    accuracy: Optional[float] = Field(None, ge=0.0)
    battery_level: Optional[float] = Field(None, ge=0.0, le=100.0)
    network_type: Optional[str] = Field(None, max_length=30)
    is_buffered: bool = False
    client_action_id: Optional[str] = None
    client_timestamp: Optional[datetime] = None


class TelemetryBatchRequest(BaseModel):
    resource_id: int
    points: List[TelemetryPointSchema]


class NotificationDeliveryResponse(BaseModel):
    notification_id: str
    user_id: int
    device_token: Optional[str] = None
    platform: str
    category: str
    title: str
    body: str
    status: str
    retry_count: int
    error_message: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)




