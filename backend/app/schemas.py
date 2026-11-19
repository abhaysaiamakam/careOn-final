from datetime import datetime, date
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


# ==============================================================================
# Milestone 7 — Hospital Readiness, Capacity & Coordination Schemas
# ==============================================================================

class HospitalFacilityCreate(BaseModel):
    organization_id: int
    facility_code: str = Field(..., min_length=3, max_length=30)
    name: str = Field(..., min_length=2, max_length=120)
    facility_type: str = Field("General Hospital", max_length=50)
    location_name: str = Field(..., max_length=200)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    trauma_level: str = Field("Level 2", max_length=30)
    capabilities: str = Field("emergency,trauma,icu,ct_scan,blood_bank,ambulance_bay")
    specialist_services: Optional[str] = Field("trauma_surgeon,cardiologist,neurologist,anesthesiologist")
    medical_equipment: Optional[str] = Field("ct_scanner,mri,ventilators,defibrillators,dialysis")
    ambulance_bays: int = Field(4, ge=0)
    operating_status: str = Field("operational", max_length=30)
    emergency_phone: Optional[str] = Field(None, max_length=30)
    escalation_contact: Optional[str] = Field(None, max_length=100)


class HospitalFacilityUpdate(BaseModel):
    name: Optional[str] = None
    facility_type: Optional[str] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    trauma_level: Optional[str] = None
    capabilities: Optional[str] = None
    specialist_services: Optional[str] = None
    medical_equipment: Optional[str] = None
    ambulance_bays: Optional[int] = Field(None, ge=0)
    operating_status: Optional[str] = None
    emergency_phone: Optional[str] = None
    escalation_contact: Optional[str] = None
    is_active: Optional[bool] = None


class HospitalFacilityResponse(BaseModel):
    id: int
    organization_id: int
    facility_code: str
    name: str
    facility_type: str
    location_name: str
    latitude: float
    longitude: float
    trauma_level: str
    capabilities: str
    specialist_services: Optional[str] = None
    medical_equipment: Optional[str] = None
    ambulance_bays: int
    operating_status: str
    emergency_phone: Optional[str] = None
    escalation_contact: Optional[str] = None
    is_active: bool
    last_verified_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HospitalCapacityUpdateRequest(BaseModel):
    category: str = Field(..., description="er_beds, trauma_bays, icu_beds, ventilators, etc.")
    total: int = Field(..., ge=0)
    occupied: int = Field(..., ge=0)
    unavailable: int = Field(0, ge=0)
    reporting_source: str = Field("staff_manual", max_length=50)
    notes: Optional[str] = None


class HospitalCapacityResponse(BaseModel):
    id: int
    facility_id: int
    category: str
    total_capacity: int
    occupied_capacity: int
    reserved_capacity: int
    unavailable_capacity: int
    available_capacity: int
    reporting_source: str
    verification_status: str
    notes: Optional[str] = None
    last_updated: datetime

    model_config = ConfigDict(from_attributes=True)


class HospitalCapacityReservationRequest(BaseModel):
    facility_id: int
    incident_id: int
    assignment_id: Optional[int] = None
    category: str = Field("er_beds", max_length=50)
    quantity: int = Field(1, ge=1)
    expires_in_seconds: int = Field(1800, ge=60, le=86400)


class HospitalCapacityReservationResponse(BaseModel):
    id: int
    reservation_token: str
    facility_id: int
    incident_id: int
    assignment_id: Optional[int] = None
    category: str
    quantity: int
    status: str
    expires_at: datetime
    released_at: Optional[datetime] = None
    release_reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FacilityDiversionUpdateRequest(BaseModel):
    new_status: str = Field(..., description="open, partial_diversion, full_diversion, closed, emergency_only")
    reason: str = Field(..., min_length=3)
    diversion_type: Optional[str] = Field(None, description="trauma, pediatric, ct_down, ed_saturation, staffing")
    effective_until: Optional[datetime] = None


class IncomingPatientCreateRequest(BaseModel):
    facility_id: int
    incident_id: int
    assignment_id: Optional[int] = None
    emergency_severity: str = Field("High", max_length=30)
    patient_condition_summary: Optional[str] = Field(None, max_length=255)
    eta_minutes: Optional[float] = None
    eta_source: Optional[str] = None
    deadline_seconds: int = Field(600, ge=60, le=3600)


class IncomingPatientResponseAction(BaseModel):
    action: str = Field(..., description="'acknowledge', 'accept', 'decline', or 'clarify'")
    reason: Optional[str] = Field(None, description="Mandatory when action is 'decline'")
    clarification_notes: Optional[str] = Field(None, description="Mandatory when action is 'clarify'")
    reserve_er_bed: bool = True
    reserve_trauma_bay: bool = False
    reserve_icu_bed: bool = False


class IncomingPatientRequestResponse(BaseModel):
    id: int
    request_token: str
    facility_id: int
    incident_id: int
    assignment_id: Optional[int] = None
    dispatcher_id: Optional[int] = None
    status: str
    emergency_severity: str
    patient_condition_summary: Optional[str] = None
    eta_minutes: Optional[float] = None
    eta_source: Optional[str] = None
    hospital_response_user_id: Optional[int] = None
    hospital_response_reason: Optional[str] = None
    clarification_notes: Optional[str] = None
    acknowledgement_deadline: datetime
    responded_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FacilityReadinessAssessmentResponse(BaseModel):
    facility_id: int
    facility_code: str
    facility_name: str
    organization_id: int
    latitude: float
    longitude: float
    distance_km: float
    eta_minutes: float
    eta_source: str
    operating_status: str
    classification: str
    score: float
    er_beds_available: int
    trauma_bays_available: int
    icu_beds_available: int
    incoming_patients_count: int
    capacity_freshness: str
    has_confirmed: bool
    matched_capabilities: List[str]
    missing_capabilities: List[str]
    explanations: List[str]


class MCIDistributionRequest(BaseModel):
    incident_id: int
    patient_severities: List[str] = Field(..., min_length=1)


# ==============================================================================
# Milestone 8 — Digital Handover & Clinical Information Continuity Schemas
# ==============================================================================

class PatientCreate(BaseModel):
    full_name: Optional[str] = None
    identity_status: str = Field("unknown", description="unknown, provisional, verified")
    date_of_birth: Optional[date] = None
    estimated_age: Optional[int] = Field(None, ge=0, le=150)
    gender: str = Field("unknown", description="male, female, non_binary, unknown")
    contact_phone: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    blood_group: Optional[str] = None
    known_allergies: Optional[str] = None
    known_medical_conditions: Optional[str] = None
    current_medications: Optional[str] = None
    history_verification_status: str = Field("unknown", description="patient_reported, family_reported, clinical_verified, unknown")


class PatientUpdate(BaseModel):
    full_name: Optional[str] = None
    identity_status: Optional[str] = None
    date_of_birth: Optional[date] = None
    estimated_age: Optional[int] = None
    gender: Optional[str] = None
    contact_phone: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    blood_group: Optional[str] = None
    known_allergies: Optional[str] = None
    known_medical_conditions: Optional[str] = None
    current_medications: Optional[str] = None
    history_verification_status: Optional[str] = None


class PatientResponse(BaseModel):
    id: int
    patient_identifier: str
    full_name: Optional[str] = None
    identity_status: str
    date_of_birth: Optional[date] = None
    estimated_age: Optional[int] = None
    gender: str
    contact_phone: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    blood_group: Optional[str] = None
    known_allergies: Optional[str] = None
    known_medical_conditions: Optional[str] = None
    current_medications: Optional[str] = None
    history_verification_status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmergencyEncounterCreate(BaseModel):
    incident_id: int
    chief_complaint: str = Field(..., min_length=2, max_length=255)
    patient_id: Optional[int] = None
    assignment_id: Optional[int] = None
    receiving_facility_id: Optional[int] = None
    initial_acuity: str = Field("High", description="Critical, High, Medium, Low")


class EmergencyEncounterResponse(BaseModel):
    id: int
    encounter_code: str
    patient_id: int
    incident_id: int
    assignment_id: Optional[int] = None
    assigned_responder_id: Optional[int] = None
    receiving_facility_id: Optional[int] = None
    status: str
    chief_complaint: str
    initial_acuity: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClinicalAssessmentCreate(BaseModel):
    consciousness_level: str = Field("Alert", description="Alert, Voice, Pain, Unresponsive")
    airway_status: str = Field("clear", max_length=50)
    breathing_status: str = Field("normal", max_length=50)
    circulation_status: str = Field("normal_pulses", max_length=50)
    presenting_complaints: Optional[str] = None
    observed_injuries: Optional[str] = None
    symptoms: Optional[str] = None
    clinical_notes: Optional[str] = None
    assessed_at: Optional[datetime] = None


class ClinicalAssessmentResponse(BaseModel):
    id: int
    encounter_id: int
    responder_id: Optional[int] = None
    assessed_at: datetime
    consciousness_level: str
    airway_status: str
    breathing_status: str
    circulation_status: str
    presenting_complaints: Optional[str] = None
    observed_injuries: Optional[str] = None
    symptoms: Optional[str] = None
    clinical_notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VitalSignObservationCreate(BaseModel):
    heart_rate: Optional[int] = Field(None, ge=0, le=300)
    systolic_bp: Optional[int] = Field(None, ge=0, le=300)
    diastolic_bp: Optional[int] = Field(None, ge=0, le=200)
    respiratory_rate: Optional[int] = Field(None, ge=0, le=100)
    oxygen_saturation: Optional[float] = Field(None, ge=0.0, le=100.0)
    body_temperature: Optional[float] = Field(None, ge=20.0, le=45.0)
    blood_glucose: Optional[float] = Field(None, ge=0.0, le=1500.0)
    gcs_eye: Optional[int] = Field(None, ge=1, le=4)
    gcs_verbal: Optional[int] = Field(None, ge=1, le=5)
    gcs_motor: Optional[int] = Field(None, ge=1, le=6)
    measurement_source: str = Field("manual", max_length=50)
    observed_at: Optional[datetime] = None


class VitalSignObservationResponse(BaseModel):
    id: int
    encounter_id: int
    recorded_by_user_id: Optional[int] = None
    observed_at: datetime
    heart_rate: Optional[int] = None
    systolic_bp: Optional[int] = None
    diastolic_bp: Optional[int] = None
    respiratory_rate: Optional[int] = None
    oxygen_saturation: Optional[float] = None
    body_temperature: Optional[float] = None
    blood_glucose: Optional[float] = None
    gcs_total: Optional[int] = None
    measurement_source: str
    data_quality: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PreHospitalInterventionCreate(BaseModel):
    intervention_type: str = Field(..., max_length=60)
    parameters_json: Optional[Dict[str, Any]] = None
    patient_response: str = Field("unchanged", max_length=50)
    notes: Optional[str] = None
    performed_at: Optional[datetime] = None


class PreHospitalInterventionResponse(BaseModel):
    id: int
    encounter_id: int
    performer_id: Optional[int] = None
    intervention_type: str
    parameters_json: Optional[str] = None
    patient_response: str
    notes: Optional[str] = None
    performed_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MedicationAdministrationCreate(BaseModel):
    medication_name: str = Field(..., min_length=2, max_length=100)
    dose: float = Field(..., gt=0.0)
    unit: str = Field(..., max_length=30)
    route: str = Field(..., max_length=50)
    response_notes: Optional[str] = None
    administered_at: Optional[datetime] = None


class MedicationAdministrationResponse(BaseModel):
    id: int
    encounter_id: int
    administering_user_id: Optional[int] = None
    medication_name: str
    dose: float
    unit: str
    route: str
    response_notes: Optional[str] = None
    verification_status: str
    administered_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DigitalHandoverCreate(BaseModel):
    encounter_id: int
    facility_id: int
    receiving_department: Optional[str] = "Emergency Department"
    outstanding_clinical_concerns: Optional[str] = None


class DigitalHandoverSubmit(BaseModel):
    receiving_department: Optional[str] = None
    outstanding_clinical_concerns: Optional[str] = None


class DigitalHandoverActionRequest(BaseModel):
    action: str = Field(..., description="'receive', 'acknowledge', 'complete', 'clarify', 'correct'")
    clarification_notes: Optional[str] = None
    correction_reason: Optional[str] = None
    outstanding_clinical_concerns: Optional[str] = None


class DigitalHandoverRecordResponse(BaseModel):
    id: int
    handover_token: str
    encounter_id: int
    facility_id: int
    version: int
    previous_version_id: Optional[int] = None
    status: str
    sending_responder_id: Optional[int] = None
    submitted_at: Optional[datetime] = None
    receiving_staff_id: Optional[int] = None
    receiving_department: Optional[str] = None
    received_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    clarification_notes: Optional[str] = None
    correction_reason: Optional[str] = None
    clinical_summary_json: Optional[str] = None
    outstanding_clinical_concerns: Optional[str] = None
    is_final: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HandoverAttachmentCreate(BaseModel):
    file_name: str = Field(..., max_length=150)
    file_type: str = Field(..., max_length=50)
    mime_type: str = Field(..., max_length=100)
    file_size_bytes: int = Field(..., gt=0)
    storage_path: str = Field(..., max_length=255)
    handover_id: Optional[int] = None
    is_confidential: bool = True


class HandoverAttachmentResponse(BaseModel):
    id: int
    attachment_token: str
    encounter_id: int
    handover_id: Optional[int] = None
    file_name: str
    file_type: str
    mime_type: str
    file_size_bytes: int
    is_confidential: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClinicalTimelineEventResponse(BaseModel):
    id: int
    event_token: str
    encounter_id: int
    event_type: str
    event_timestamp: datetime
    server_receipt_timestamp: datetime
    actor_id: Optional[int] = None
    actor_role: str
    structured_data_json: Optional[str] = None
    source_application: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# Milestone 9 — Offline-First Synchronization & Resilient Field Operations
# ==============================================================================

class DeviceSyncRegisterRequest(BaseModel):
    device_identifier: str = Field(..., min_length=4, max_length=64)
    platform: str = Field("mobile", max_length=30)
    app_version: str = Field("1.0.0", max_length=50)
    device_model: Optional[str] = Field(None, max_length=100)
    push_token: Optional[str] = Field(None, max_length=255)
    organization_id: Optional[int] = None


class DeviceSyncResponse(BaseModel):
    id: int
    device_identifier: Optional[str] = None
    user_id: int
    organization_id: Optional[int] = None
    platform: str
    app_version: Optional[str] = None
    device_model: Optional[str] = None
    is_active: bool
    is_revoked: bool
    revoked_at: Optional[datetime] = None
    revoked_reason: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    sync_cursor: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeviceRevokeRequest(BaseModel):
    reason: Optional[str] = Field("Device decommissioned or revoked", max_length=255)


class SyncActionItem(BaseModel):
    action_uuid: str = Field(..., min_length=8, max_length=64)
    action_type: str = Field(..., max_length=60)
    mission_id: Optional[int] = None
    encounter_id: Optional[int] = None
    client_timestamp: datetime
    device_sequence_number: Optional[int] = 1
    payload: Dict[str, Any]


class SyncUploadBatchRequest(BaseModel):
    device_id: str = Field(..., min_length=4, max_length=64)
    client_batch_id: str = Field(..., min_length=8, max_length=64)
    actions: List[SyncActionItem] = Field(...)


class SyncActionReceiptResponse(BaseModel):
    action_uuid: str
    status: str  # ACKNOWLEDGED, PERMANENT_FAILURE, RETRYABLE_FAILURE, CONFLICT
    server_ack_id: str
    action_type: str
    client_timestamp: datetime
    server_receipt_timestamp: datetime
    response_payload: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    conflict_details: Optional[Dict[str, Any]] = None


class SyncUploadBatchResponse(BaseModel):
    batch_uuid: str
    device_id: str
    total_actions: int
    accepted_actions: int
    failed_actions: int
    conflict_actions: int
    server_receipt_timestamp: datetime
    processing_time_ms: float
    results: List[SyncActionReceiptResponse]


class SyncDownloadRequest(BaseModel):
    device_id: str = Field(..., min_length=4, max_length=64)
    since_cursor: Optional[str] = "0"
    limit: Optional[int] = Field(50, ge=1, le=200)


class SyncDownloadChangeItem(BaseModel):
    change_id: str
    entity_type: str
    entity_id: int
    operation: str
    timestamp: datetime
    data: Dict[str, Any]


class SyncDownloadResponse(BaseModel):
    device_id: str
    previous_cursor: str
    next_cursor: str
    has_more: bool
    changes_count: int
    changes: List[SyncDownloadChangeItem]
    server_time: datetime


class SyncAckRequest(BaseModel):
    device_id: str = Field(..., min_length=4, max_length=64)
    acknowledged_cursor: str
    acknowledged_action_uuids: Optional[List[str]] = []


class SyncAckResponse(BaseModel):
    device_id: str
    acknowledged_cursor: str
    status: str = "success"
    updated_at: datetime


class SyncConflictResponse(BaseModel):
    id: int
    conflict_token: str
    action_uuid: str
    device_id: int
    user_id: int
    mission_id: Optional[int] = None
    encounter_id: Optional[int] = None
    conflict_category: str
    reason: str
    client_state: Dict[str, Any]
    server_state: Dict[str, Any]
    resolution_status: str
    resolution_notes: Optional[str] = None
    resolved_by_user_id: Optional[int] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime


class SyncConflictReconcileRequest(BaseModel):
    resolution: str = Field(..., description="RESOLVED_SERVER, RESOLVED_CLIENT, DISCARDED")
    notes: Optional[str] = None


# ==============================================================================
# Milestone 10 — Predictive Emergency Intelligence & Resource Positioning Schemas
# ==============================================================================

class HourlyDemandPattern(BaseModel):
    hour: int = Field(..., ge=0, le=23)
    incident_count: int
    incident_share_pct: float


class WeekdayDemandPattern(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6)
    day_name: str
    incident_count: int
    incident_share_pct: float


class CategoryBreakdownItem(BaseModel):
    category: str
    count: int
    percentage: float


class SeverityBreakdownItem(BaseModel):
    priority: str
    count: int
    percentage: float


class DemandAnalyticsResponse(BaseModel):
    total_valid_incidents: int
    excluded_incidents_count: int
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    hourly_patterns: List[HourlyDemandPattern]
    weekday_patterns: List[WeekdayDemandPattern]
    category_breakdown: List[CategoryBreakdownItem]
    severity_breakdown: List[SeverityBreakdownItem]
    monthly_trend: List[Dict[str, Any]]
    data_freshness_seconds: float


class HotspotAnalysisRequest(BaseModel):
    days: int = Field(30, ge=1, le=365)
    grid_size_km: float = Field(1.0, ge=0.1, le=20.0)
    min_incidents: int = Field(2, ge=1)


class HotspotCluster(BaseModel):
    cluster_id: int
    centroid_latitude: float
    centroid_longitude: float
    incident_count: int
    incident_density_per_sq_km: float
    average_response_time_minutes: float
    is_coverage_gap: bool
    risk_tier: str  # LOW, MODERATE, HIGH, CRITICAL, STATISTICALLY_INSUFFICIENT


class HotspotAnalysisResponse(BaseModel):
    analyzed_incidents: int
    clusters: List[HotspotCluster]
    underserved_areas: List[str]
    grid_resolution_km: float
    generated_at: datetime


class ForecastGenerateRequest(BaseModel):
    zone_or_region: str = Field(..., min_length=2, max_length=100)
    horizon_hours: int = Field(3, description="1, 3, 6, 12, or 24 hours")
    model_id: Optional[str] = None


class ForecastResponse(BaseModel):
    forecast_uuid: str
    zone_or_region: str
    horizon_hours: int
    start_time: datetime
    end_time: datetime
    expected_incidents: float
    confidence_lower: float
    confidence_upper: float
    confidence_level: str  # HIGH, MEDIUM, LOW, INSUFFICIENT_DATA
    category_breakdown: Dict[str, float]
    model_id: str
    model_version: str
    historical_sample_size: int
    data_freshness_seconds: float
    contributing_factors: List[str]
    created_at: datetime


class CoverageAnalysisRequest(BaseModel):
    zone_or_region: Optional[str] = None
    response_threshold_minutes: float = Field(15.0, ge=1.0, le=60.0)


class ZoneCoverageResponse(BaseModel):
    zone_or_region: str
    operational_resources_count: int
    available_resources_count: int
    occupied_resources_count: int
    stale_gps_resources_count: int
    forecasted_demand_next_3h: float
    coverage_ratio: float
    avg_travel_time_minutes: float
    is_coverage_gap: bool
    nearest_available_resource_code: Optional[str] = None
    nearest_travel_time_minutes: Optional[float] = None
    routing_source: str


class PositioningRecommendRequest(BaseModel):
    target_area: Optional[str] = None
    max_recommendations: int = Field(3, ge=1, le=10)


class PositioningRecommendationResponse(BaseModel):
    id: int
    recommendation_uuid: str
    target_area: str
    target_latitude: float
    target_longitude: float
    resource_id: int
    resource_code: Optional[str] = None
    current_latitude: float
    current_longitude: float
    proposed_latitude: float
    proposed_longitude: float
    proposed_staging_name: str
    status: str
    expected_coverage_improvement: float
    estimated_travel_time_minutes: float
    confidence_level: str
    explanation: str
    alternative_resources: List[Dict[str, Any]]
    expires_at: datetime
    reviewed_by_user_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    modification_notes: Optional[str] = None
    execution_status: Optional[str] = None
    model_id: Optional[str] = None
    model_version: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PositioningRecommendationReviewRequest(BaseModel):
    notes: Optional[str] = None


class PositioningRecommendationRejectRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class PositioningRecommendationModifyRequest(BaseModel):
    proposed_latitude: Optional[float] = None
    proposed_longitude: Optional[float] = None
    proposed_staging_name: Optional[str] = None
    resource_id: Optional[int] = None
    notes: Optional[str] = None


class PositioningExecutionRequest(BaseModel):
    execution_action: str = Field("DISPATCH_RELOCATION", description="DISPATCH_RELOCATION or CANCEL")
    notes: Optional[str] = None


class ScenarioSimulationRequest(BaseModel):
    scenario_type: str = Field(..., description="BASELINE_NORMAL, REGIONAL_DEMAND_SURGE, MASS_CASUALTY_EVENT, RESOURCE_SHORTAGE, HOSPITAL_DIVERSION")
    scenario_name: Optional[str] = None
    target_zone: Optional[str] = None
    surge_factor: Optional[float] = Field(1.0, ge=0.1, le=10.0)
    unavailable_resource_ids: Optional[List[int]] = []
    diverted_hospital_ids: Optional[List[int]] = []


class ScenarioSimulationResponse(BaseModel):
    simulation_uuid: str
    scenario_type: str
    scenario_name: str
    baseline_expected_demand: float
    simulated_demand: float
    operational_resources_count: int
    available_resources_count: int
    response_time_impact_minutes: float
    coverage_gaps_identified: List[str]
    bottleneck_alerts: List[str]
    recommended_positioning_actions: List[Dict[str, Any]]
    created_at: datetime


class ModelRegistryResponse(BaseModel):
    model_id: str
    model_name: str
    model_type: str
    version: str
    is_active: bool
    status: str
    sample_count: int
    mae: Optional[float] = None
    rmse: Optional[float] = None
    forecast_bias: Optional[float] = None
    poisson_deviance: Optional[float] = None
    last_evaluated_at: Optional[datetime] = None


class ModelEvaluationRequest(BaseModel):
    candidate_model_id: str
    validation_days: int = Field(14, ge=1, le=180)


class ModelEvaluationResponse(BaseModel):
    model_id: str
    model_version: str
    sample_count: int
    mae: float
    rmse: float
    forecast_bias: float
    poisson_deviance: Optional[float] = None
    baseline_mae: float
    baseline_rmse: float
    outperformed_baseline: bool
    can_activate: bool
    recommendation: str


class ModelHealthResponse(BaseModel):
    active_model_id: str
    active_model_version: str
    status: str
    is_degraded: bool
    data_freshness_seconds: float
    historical_sample_count: int
    fallback_active: bool
    alerts: List[str]


# ==============================================================================
# Milestone 11 — Multi-Agency Coordination & Unified Incident Command Schemas
# ==============================================================================

class AgencyClassificationCreate(BaseModel):
    agency_type: str = Field(..., description="EMS, POLICE, FIRE_RESCUE, DISASTER_RESPONSE, HOSPITAL, EMERGENCY_COMMAND, OTHER")
    jurisdiction: Optional[str] = None
    dispatch_hotline: Optional[str] = None
    radio_channel: Optional[str] = None
    capabilities_json: Optional[str] = None
    is_mutual_aid_signatory: bool = True


class AgencyClassificationUpdate(BaseModel):
    agency_type: Optional[str] = None
    jurisdiction: Optional[str] = None
    dispatch_hotline: Optional[str] = None
    radio_channel: Optional[str] = None
    capabilities_json: Optional[str] = None
    is_mutual_aid_signatory: Optional[bool] = None


class AgencyClassificationResponse(BaseModel):
    id: int
    organization_id: int
    agency_type: str
    jurisdiction: Optional[str] = None
    dispatch_hotline: Optional[str] = None
    radio_channel: Optional[str] = None
    capabilities_json: Optional[str] = None
    is_mutual_aid_signatory: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncidentCollaborationInviteRequest(BaseModel):
    target_organization_id: int
    collaboration_purpose: str = Field(..., min_length=3)
    initial_scopes: List[str] = Field(default_factory=lambda: ["INCIDENT_SUMMARY", "OPERATIONAL_LOCATION"])
    expires_hours: Optional[int] = Field(24, ge=1, le=168)


class IncidentCollaborationActionRequest(BaseModel):
    status: str = Field(..., description="ACCEPTED, SUSPENDED, REVOKED, COMPLETED")
    reason: Optional[str] = None


class IncidentCollaborationResponse(BaseModel):
    id: int
    collaboration_uuid: str
    incident_id: int
    organization_id: int
    organization_name: Optional[str] = None
    organization_type: Optional[str] = None
    collaboration_status: str
    collaboration_purpose: str
    inviting_organization_id: Optional[int] = None
    inviting_organization_name: Optional[str] = None
    accepted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_reason: Optional[str] = None
    active_scopes: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InformationGrantRequest(BaseModel):
    scopes_to_grant: List[str] = Field(default_factory=list)
    scopes_to_revoke: List[str] = Field(default_factory=list)


class InformationGrantResponse(BaseModel):
    grant_uuid: str
    collaboration_id: int
    scope: str
    is_granted: bool
    granted_at: datetime
    revoked_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class IncidentCommandCreateRequest(BaseModel):
    structure_type: str = Field("SINGLE_COMMAND", description="SINGLE_COMMAND or UNIFIED_COMMAND")
    lead_agency_id: int
    activation_notes: Optional[str] = None
    initial_commander_user_id: int
    radio_callsign: Optional[str] = None
    contact_number: Optional[str] = None


class IncidentCommandTransferRequest(BaseModel):
    new_commander_user_id: int
    new_commander_org_id: int
    briefing_summary: str = Field(..., min_length=5)
    radio_callsign: Optional[str] = None
    contact_number: Optional[str] = None


class IncidentCommandSuccessionRequest(BaseModel):
    new_commander_user_id: int
    new_commander_org_id: int
    reason: str = Field(..., min_length=5)
    briefing_summary: Optional[str] = None


class IncidentCommandAssignRoleRequest(BaseModel):
    command_role: str = Field(..., description="DEPUTY_COMMANDER, SAFETY_OFFICER, LIAISON_OFFICER, OPERATIONS_CHIEF, PLANNING_CHIEF, LOGISTICS_CHIEF, FINANCE_CHIEF, EMS_BRANCH_DIRECTOR, etc.")
    assigned_user_id: int
    assigned_org_id: int
    radio_callsign: Optional[str] = None
    contact_number: Optional[str] = None


class IncidentCommandAssignmentResponse(BaseModel):
    assignment_uuid: str
    command_structure_id: int
    command_role: str
    assigned_user_id: int
    assigned_user_name: Optional[str] = None
    assigned_organization_id: int
    assigned_organization_name: Optional[str] = None
    is_active: bool
    radio_callsign: Optional[str] = None
    contact_number: Optional[str] = None
    assigned_at: datetime
    relieved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class IncidentCommandHistoryResponse(BaseModel):
    history_uuid: str
    event_type: str
    previous_commander_id: Optional[int] = None
    new_commander_id: Optional[int] = None
    authorizing_user_id: Optional[int] = None
    briefing_summary: Optional[str] = None
    reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncidentCommandStructureResponse(BaseModel):
    command_uuid: str
    incident_id: int
    structure_type: str
    lead_agency_id: int
    lead_agency_name: Optional[str] = None
    is_active: bool
    activation_notes: Optional[str] = None
    active_commander: Optional[IncidentCommandAssignmentResponse] = None
    assignments: List[IncidentCommandAssignmentResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgencyTaskCreateRequest(BaseModel):
    assigned_organization_id: int
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=5)
    priority: str = Field("MEDIUM", description="LOW, MEDIUM, HIGH, CRITICAL")
    assigned_unit_name: Optional[str] = None
    deadline: Optional[datetime] = None


class AgencyTaskUpdateRequest(BaseModel):
    status: Optional[str] = Field(None, description="ACKNOWLEDGED, IN_PROGRESS, BLOCKED, COMPLETED, REJECTED, CANCELLED")
    assigned_unit_name: Optional[str] = None
    rejection_reason: Optional[str] = None
    status_notes: Optional[str] = None


class AgencyTaskResponse(BaseModel):
    id: int
    task_uuid: str
    incident_id: int
    command_structure_id: Optional[int] = None
    assigning_organization_id: int
    assigning_organization_name: Optional[str] = None
    assigned_organization_id: int
    assigned_organization_name: Optional[str] = None
    created_by_user_id: int
    created_by_name: Optional[str] = None
    title: str
    description: str
    priority: str
    status: str
    assigned_unit_name: Optional[str] = None
    deadline: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    status_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgencyResourceRequestCreate(BaseModel):
    requested_organization_id: int
    resource_type: str = Field(..., description="AMBULANCE, FIRE_TRUCK, HAZMAT_UNIT, POLICE_PATROL, RESCUE_SQUAD, HELICOPTER, WATER_TANKER, OTHER")
    quantity: int = Field(1, ge=1, le=50)
    urgency: str = Field("ROUTINE", description="ROUTINE, URGENT, EMERGENCY, LIFE_THREATENING")
    operational_justification: str = Field(..., min_length=5)
    staging_location_name: Optional[str] = None
    staging_latitude: Optional[float] = None
    staging_longitude: Optional[float] = None
    expires_hours: Optional[int] = Field(6, ge=1, le=72)


class AgencyResourceRequestAction(BaseModel):
    action: str = Field(..., description="ACKNOWLEDGE, ACCEPT, DECLINE, FULFILL, CANCEL")
    decision_notes: Optional[str] = None
    assigned_resource_ids: Optional[List[str]] = None


class AgencyResourceRequestResponse(BaseModel):
    id: int
    request_uuid: str
    incident_id: int
    requesting_organization_id: int
    requesting_organization_name: Optional[str] = None
    requested_organization_id: int
    requested_organization_name: Optional[str] = None
    resource_type: str
    quantity: int
    urgency: str
    status: str
    operational_justification: str
    staging_location_name: Optional[str] = None
    staging_latitude: Optional[float] = None
    staging_longitude: Optional[float] = None
    decision_notes: Optional[str] = None
    assigned_resource_ids: List[str] = Field(default_factory=list)
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncidentOperationalZoneCreate(BaseModel):
    zone_type: str = Field(..., description="INCIDENT_PERIMETER, HOT_ZONE, WARM_ZONE, COLD_ZONE, STAGING_AREA, EVACUATION_ZONE, ACCESS_RESTRICTED_ZONE, HAZARD_ZONE, SAFE_ASSEMBLY_AREA")
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    center_latitude: Optional[float] = None
    center_longitude: Optional[float] = None
    radius_meters: Optional[float] = None
    polygon_geojson: Optional[str] = None
    hazard_type: Optional[str] = None
    access_restrictions: Optional[str] = None


class IncidentOperationalZoneResponse(BaseModel):
    zone_uuid: str
    incident_id: int
    created_by_organization_id: int
    created_by_organization_name: Optional[str] = None
    zone_type: str
    name: str
    description: Optional[str] = None
    center_latitude: Optional[float] = None
    center_longitude: Optional[float] = None
    radius_meters: Optional[float] = None
    polygon_geojson: Optional[str] = None
    hazard_type: Optional[str] = None
    access_restrictions: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OperationalPictureResponse(BaseModel):
    incident_id: int
    requesting_agency_id: int
    granted_scopes: List[str]
    summary: Optional[Dict[str, Any]] = None
    location: Optional[Dict[str, Any]] = None
    hazard_information: Optional[List[Dict[str, Any]]] = None
    participating_agencies: List[Dict[str, Any]] = Field(default_factory=list)
    resource_status: Optional[List[Dict[str, Any]]] = None
    agency_tasks: Optional[List[Dict[str, Any]]] = None
    casualty_counts: Optional[Dict[str, Any]] = None
    hospital_destinations: Optional[List[Dict[str, Any]]] = None
    clinical_handover_reference: Optional[Dict[str, Any]] = None
    command_information: Optional[Dict[str, Any]] = None
    operational_zones: Optional[List[Dict[str, Any]]] = None


class InterAgencyAuditResponse(BaseModel):
    audit_uuid: str
    incident_id: int
    acting_organization_id: int
    acting_organization_name: Optional[str] = None
    acting_user_id: int
    acting_user_name: Optional[str] = None
    action_type: str
    target_agency_id: Optional[int] = None
    target_agency_name: Optional[str] = None
    target_resource_type: Optional[str] = None
    target_resource_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# Citizen Emergency Profile & Onboarding Schemas
# ==============================================================================
class CitizenProfileResponse(BaseModel):
    user_id: int
    name: str
    email: str
    phone: str
    trust_score: str
    dob: Optional[str] = None
    preferred_language: str = "en"
    profile_photo_url: Optional[str] = None
    residential_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    landmark: Optional[str] = None
    residential_city: Optional[str] = None
    residential_state: Optional[str] = None
    residential_postal_code: Optional[str] = None
    address_landmark: Optional[str] = None
    access_instructions: Optional[str] = None
    emergency_notes: Optional[str] = None
    home_latitude: Optional[float] = None
    home_longitude: Optional[float] = None
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    medical_conditions: Optional[str] = None
    medications: Optional[str] = None
    current_medications: Optional[str] = None
    accessibility_needs: Optional[str] = None
    is_medical_verified: bool = False
    is_organ_donor: bool = False
    onboarding_completed: bool = False
    onboarding_step: int = 1
    consent_data_sharing: bool = False
    consent_emergency_contact: bool = False
    consent_data_sharing_emergency: bool = True
    readiness_score: int = 50
    missing_critical_fields: List[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CitizenProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    phone: Optional[str] = Field(default=None, min_length=8, max_length=30)
    dob: Optional[str] = None
    preferred_language: Optional[str] = None
    profile_photo_url: Optional[str] = None
    residential_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    landmark: Optional[str] = None
    residential_city: Optional[str] = None
    residential_state: Optional[str] = None
    residential_postal_code: Optional[str] = None
    address_landmark: Optional[str] = None
    access_instructions: Optional[str] = None
    emergency_notes: Optional[str] = None
    home_latitude: Optional[float] = None
    home_longitude: Optional[float] = None
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    medical_conditions: Optional[str] = None
    medications: Optional[str] = None
    current_medications: Optional[str] = None
    accessibility_needs: Optional[str] = None
    is_organ_donor: Optional[bool] = None
    onboarding_step: Optional[int] = None
    consent_data_sharing: Optional[bool] = None
    consent_emergency_contact: Optional[bool] = None
    consent_data_sharing_emergency: Optional[bool] = None


class CitizenEmergencyContactCreate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    full_name: Optional[str] = Field(default=None, max_length=100)
    relationship_type: str = Field(..., min_length=2, max_length=50)
    phone: str = Field(..., min_length=8, max_length=30)
    secondary_phone: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=100)
    is_primary: Optional[bool] = False
    can_authorize_medical_treatment: Optional[bool] = False


class CitizenEmergencyContactUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    full_name: Optional[str] = Field(default=None, max_length=100)
    relationship_type: Optional[str] = Field(default=None, max_length=50)
    phone: Optional[str] = Field(default=None, max_length=30)
    secondary_phone: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=100)
    is_primary: Optional[bool] = None
    can_authorize_medical_treatment: Optional[bool] = None


class CitizenEmergencyContactResponse(BaseModel):
    id: int
    user_id: int
    name: str
    full_name: Optional[str] = None
    relationship_type: str
    phone: str
    secondary_phone: Optional[str] = None
    email: Optional[str] = None
    is_primary: bool
    can_authorize_medical_treatment: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CitizenDashboardSummary(BaseModel):
    user_id: int
    name: str
    phone: str
    email: str
    onboarding_completed: bool
    onboarding_step: int
    readiness: Dict[str, Any]
    active_incident: Optional[Dict[str, Any]] = None
    recent_incidents: List[Dict[str, Any]] = []
    emergency_contacts: List[CitizenEmergencyContactResponse] = []
    unread_notifications_count: int = 0
    # Additional enriched fields
    profile: Optional[CitizenProfileResponse] = None
    contacts: List[CitizenEmergencyContactResponse] = []
    active_incidents: List[Dict[str, Any]] = []
    total_incidents_count: int = 0










