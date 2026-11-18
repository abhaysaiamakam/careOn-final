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
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    user: UserResponse


# ==============================================================================
# Incident Schemas
# ==============================================================================
class IncidentCreate(BaseModel):
    category: str = Field(..., description="Medical, Road accident, Fire, Rescue, Safety / Other, Disaster / Multiple affected people")
    description: str = Field(..., min_length=5)
    location_name: str = Field(..., min_length=2)
    latitude: Optional[float] = 12.3052
    longitude: Optional[float] = 76.6552
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
    latitude: float = 12.3052
    longitude: float = 76.6552
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
    latitude: float = 12.3052
    longitude: float = 76.6552
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
