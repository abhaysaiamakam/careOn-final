import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from app import __version__
from app.database import engine, Base, get_db, is_postgres, check_db_connection
from app.models import User, Incident, Resource, Assignment, ExternalProvider, ProviderEnquiry, Notification, Feedback
from app.auth import (
    get_current_user,
    get_current_admin,
    get_optional_user,
    create_access_token,
    validate_and_get_secret_key,
)
from app.schemas import (
    # Auth
    UserRegister,
    UserLogin,
    UserResponse,
    TokenResponse,
    # Incidents
    IncidentCreate,
    IncidentVerify,
    IncidentStatusUpdate,
    IncidentPriorityUpdate,
    IncidentCancel,
    IncidentResponse,
    IncidentDetailResponse,
    IncidentPublicTrackingResponse,
    IncidentPublicTrackingUpdateItem,
    # Resources
    ResourceCreate,
    ResourceUpdate,
    ResourceResponse,
    # Allocation
    AllocationRecommendRequest,
    AllocationConfirmRequest,
    # Providers
    ProviderCreate,
    ProviderResponse,
    ProviderEnquiryCreate,
    ProviderEnquiryUpdate,
    ProviderEnquiryResponse,
    # Notifications & Feedback
    NotificationResponse,
    FeedbackCreate,
    FeedbackResponse,
    # Chatbot & Simulation
    ChatbotMessageRequest,
    ChatbotMessageResponse,
    SimulationRunRequest,
    # Legacy Schemas
    EmergencyCreate,
    EmergencyUpdateStatus,
    EmergencyResponse,
    StatsResponse,
    HealthResponse,
)
from app import crud
from app.algorithms.allocation import evaluate_allocation_for_incident, compute_multi_incident_allocations
from app.algorithms.shortage import get_current_shortages
from app.algorithms.prediction import predict_resource_shortage_risk
from app.chatbot.sahara import process_sahara_message
from app.rate_limiter import rate_limit
from app.models import make_point_wkt
from app.routers.auth import router as auth_router
from app.routers.identity import router as identity_router
from app.routers.organizations import router as organizations_router
from app.routers.responder import router as responder_router
from app.routers.hospital import router as hospital_router
from app.routers.super_admin import router as super_admin_router
from app.realtime import realtime_router, redis_subscriber
from app.routers.dispatch import router as dispatch_router
from app.routers.responder_ops import router as responder_ops_router
from app.routers.hospital_coordination import router as hospital_coordination_router
from app.routers.clinical_handover import router as clinical_handover_router
from app.routers.sync import router as sync_router
from app.routers.intelligence import router as intelligence_router
from app.routers.coordination import router as coordination_router
from app.routers.citizen import router as citizen_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging as _logging
    _startup_log = _logging.getLogger("careon.startup")
    # Validate secret key configuration at server startup
    validate_and_get_secret_key()
    # Check database connectivity; warn but do not crash if DB is temporarily unavailable.
    if not check_db_connection():
        _startup_log.warning(
            "Database unreachable at startup — application may be degraded. "
            "Ensure PostgreSQL is running and DATABASE_URL is correctly configured."
        )
    # Schema initialisation strategy:
    #   SQLite  → always use create_all (dev / unit tests)
    #   PostgreSQL (production) → rely on Alembic migrations; create_all only when
    #     tables are absent (e.g. fresh integration-test DB or first-run without
    #     Alembic having been executed yet).
    if is_postgres():
        from sqlalchemy import inspect as sa_inspect
        try:
            insp = sa_inspect(engine)
            if "users" not in insp.get_table_names():
                _startup_log.info("PostgreSQL: no tables found — running create_all for initial setup.")
                Base.metadata.create_all(bind=engine)
            else:
                _startup_log.info("PostgreSQL: tables already exist — skipping create_all (use Alembic for migrations).")
        except Exception as exc:
            _startup_log.warning(f"PostgreSQL table inspection failed: {exc} — attempting create_all.")
            Base.metadata.create_all(bind=engine)
    else:
        Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        crud.seed_demo_data(db)
    except Exception as exc:
        _startup_log.warning(f"Demo data seeding skipped or partial: {exc}")
    finally:
        db.close()

    # Milestone 4: Start background Redis Pub/Sub subscriber
    try:
        redis_subscriber.start()
    except Exception as exc:
        _startup_log.warning(f"Failed to start Redis subscriber at startup: {exc}")

    yield

    # Milestone 4: Shutdown Redis Pub/Sub subscriber
    try:
        await redis_subscriber.stop()
    except Exception as exc:
        _startup_log.warning(f"Error stopping Redis subscriber: {exc}")


app = FastAPI(
    title="CareOn - Intelligent Emergency Resource Coordination Platform",
    description="Backend decision-support API for emergency coordination, resource allocation, and multi-device access.",
    version=__version__,
    lifespan=lifespan,
)

# CORS configuration: strict in production, multi-device permissive in development
ALLOWED_ORIGINS_ENV = os.getenv("ALLOWED_ORIGINS")
if ALLOWED_ORIGINS_ENV:
    cors_origins = [orig.strip() for orig in ALLOWED_ORIGINS_ENV.split(",") if orig.strip()]
elif os.getenv("CAREON_ENV", os.getenv("ENVIRONMENT", "development")).lower() in ("production", "prod"):
    cors_origins = ["https://careon.org", "https://app.careon.org"]
else:
    cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Milestone 2 Routers: Extended Auth, Identity/Sessions, and Multi-Organizations
app.include_router(auth_router)
app.include_router(identity_router)
app.include_router(organizations_router)

# Milestone 3 Routers: Five-Application Ecosystem (Responder, Hospital, Super Admin)
app.include_router(responder_router)
app.include_router(hospital_router)
app.include_router(super_admin_router)

# Milestone 4 Router: Real-time coordination engine (WebSockets, GPS telemetry, Outbox recovery)
app.include_router(realtime_router)

# Milestone 5 Router: Intelligent Dispatch & Resource Optimization Engine
app.include_router(dispatch_router)

# Milestone 6 Router: Responder Operations, Lifecycle State Machine & Push Notifications
app.include_router(responder_ops_router)

# Milestone 7 Router: Hospital Readiness, Dynamic Capacity & Emergency Coordination
app.include_router(hospital_coordination_router)

# Milestone 8 Router: Digital Patient Handover & Clinical Information Continuity
app.include_router(clinical_handover_router)

# Milestone 9 Router: Offline-First Synchronization & Resilient Field Operations
app.include_router(sync_router)

# Milestone 10 Router: Predictive Emergency Intelligence & Resource Positioning
app.include_router(intelligence_router)

# Milestone 11 Router: Multi-Agency Emergency Coordination & Unified Incident Command
app.include_router(coordination_router)

# Citizen Operations Router: Emergency Profile, Onboarding & Personal Dashboard
app.include_router(citizen_router)


# ==============================================================================
# System & Health
# ==============================================================================
@app.get("/", tags=["System"])
def root():
    return {
        "service": "CareOn Emergency Dispatch API",
        "product": "CareOn - Intelligent Emergency Resource Coordination Platform",
        "tagline": "Help is closer than you think.",
        "status": "online",
        "version": __version__,
        "docs": "/docs",
    }


@app.get("/api/health", response_model=HealthResponse, tags=["System"])
def health_check(db: Session = Depends(get_db)):
    """Healthcheck endpoint for Docker Compose, CI, and orchestrators."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "degraded", "database": "database connection unavailable"},
        )

    return HealthResponse(
        status="healthy",
        database=db_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        version=__version__,
    )


# ==============================================================================
# Auth Routes
# ==============================================================================
@app.post("/api/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED, tags=["Auth"])
def register(payload: UserRegister, db: Session = Depends(get_db), _rl: None = Depends(rate_limit("auth"))):
    if payload.confirm_password and payload.password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match.",
        )
    existing = crud.get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )
    # Security Rule: Public registration MUST NEVER create an admin account. Role is forced to 'user'.
    user = crud.create_user(
        db=db,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        password=payload.password,
        role="user",
    )
    token = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
    raw_refresh = None
    try:
        from app.identity.refresh_tokens import create_refresh_token_record
        raw_refresh, _ = create_refresh_token_record(db, user_id=user.id, session_id=None, device_hint="web")
        db.commit()
    except Exception:
        pass
    return TokenResponse(access_token=token, token_type="Bearer", refresh_token=raw_refresh, user=UserResponse.model_validate(user))


@app.post("/api/auth/login", response_model=TokenResponse, tags=["Auth"])
def login(payload: UserLogin, db: Session = Depends(get_db), _rl: None = Depends(rate_limit("auth"))):
    user = crud.authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    if hasattr(user, "is_active") and not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated.",
        )
    token = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
    raw_refresh = None
    try:
        from app.identity.refresh_tokens import create_refresh_token_record
        raw_refresh, _ = create_refresh_token_record(db, user_id=user.id, session_id=None, device_hint="web")
        db.commit()
    except Exception:
        pass
    return TokenResponse(access_token=token, token_type="Bearer", refresh_token=raw_refresh, user=UserResponse.model_validate(user))


@app.get("/api/auth/me", response_model=UserResponse, tags=["Auth"])
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


# ==============================================================================
# Incident Routes
# ==============================================================================
@app.post("/api/incidents", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED, tags=["Incidents"])
def report_incident(
    payload: IncidentCreate,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
    _rl: None = Depends(rate_limit("emergency")),
):
    """Public / user emergency reporting endpoint."""
    user_id = current_user.id if current_user else None
    return crud.create_incident(db, payload, user_id=user_id)


@app.get("/api/incidents", response_model=List[IncidentResponse], tags=["Incidents"])
def list_incidents(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority_filter: Optional[str] = Query(None, alias="priority"),
    category_filter: Optional[str] = Query(None, alias="category"),
    search: Optional[str] = Query(None),
    my_requests_only: bool = Query(False),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    List incidents with role-based privacy:
    - If user is logged in as a normal user, only their own incidents are returned.
    - Admins see all incidents across the platform.
    """
    user_id = None
    if current_user and current_user.role != "admin":
        user_id = current_user.id
    elif my_requests_only and current_user:
        user_id = current_user.id

    return crud.get_incidents(
        db,
        status_filter=status_filter,
        priority_filter=priority_filter,
        category_filter=category_filter,
        user_id=user_id,
        search=search,
    )


@app.get("/api/incidents/track/{tracking_token}", response_model=IncidentPublicTrackingResponse, tags=["Incidents"])
def track_incident_public(
    tracking_token: str,
    db: Session = Depends(get_db),
    _rl: None = Depends(rate_limit("tracking")),
):
    """
    Public restricted tracking endpoint for citizens using a cryptographically unguessable tracking credential.
    Exposes only status and sanitized updates without leaking personal patient data, contact details, or internal notes.
    """
    incident = crud.get_incident_by_tracking_token(db, tracking_token)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident tracking record not found for the provided credential.",
        )
    public_updates = [
        IncidentPublicTrackingUpdateItem(
            status=u.status,
            message=u.message,
            created_at=u.created_at,
        )
        for u in (incident.updates or [])
        if u.is_public
    ]
    return IncidentPublicTrackingResponse(
        incident_code=incident.incident_code,
        category=incident.category,
        status=incident.status,
        priority=incident.priority,
        location_name=incident.location_name,
        is_verified=incident.is_verified,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        updates=public_updates,
    )


@app.get("/api/incidents/{identifier}", response_model=IncidentDetailResponse, tags=["Incidents"])
def get_incident_details(
    identifier: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve full incident details by numeric ID or incident code with strict authorization."""
    item = crud.get_incident_by_id_or_code(db, identifier)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{identifier}' not found.",
        )
    # Authorization check:
    # Admins and dispatchers can access any incident.
    # Regular users can only access incidents they reported.
    if current_user.role not in ("admin", "super_admin", "dispatcher"):
        if item.user_id is None or item.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You cannot view another user's private emergency incident.",
            )
    return item


@app.post("/api/incidents/{incident_id}/verify", response_model=IncidentResponse, tags=["Incidents"])
def verify_incident_otp(
    incident_id: int,
    payload: IncidentVerify,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Verify phone contact via demo OTP."""
    actor = current_user.name if current_user else "Reporter"
    updated = crud.verify_incident(db, incident_id, payload.otp, verified_by=actor)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP code. Use demo code '123456'.",
        )
    return updated


@app.patch("/api/incidents/{incident_id}/status", response_model=IncidentResponse, tags=["Incidents"])
def update_status(
    incident_id: int,
    payload: IncidentStatusUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Admin-only: update incident lifecycle status."""
    updated = crud.update_incident_status(
        db,
        incident_id=incident_id,
        new_status=payload.status,
        actor=admin.name,
        message=payload.message,
        internal_notes=payload.internal_admin_notes,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident #{incident_id} not found.",
        )
    return updated


@app.patch("/api/incidents/{incident_id}/priority", response_model=IncidentResponse, tags=["Incidents"])
def update_priority(
    incident_id: int,
    payload: IncidentPriorityUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Admin-only: manually override incident priority with recorded reason."""
    updated = crud.update_incident_priority(
        db,
        incident_id=incident_id,
        new_priority=payload.priority,
        reason=payload.reason,
        actor=admin.name,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident #{incident_id} not found.",
        )
    return updated


@app.post("/api/incidents/{incident_id}/cancel", response_model=IncidentResponse, tags=["Incidents"])
def cancel_incident_endpoint(
    incident_id: int,
    payload: IncidentCancel,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    User-initiated or admin cancellation with reason.
    Strictly verifies authentication and incident ownership.
    """
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident #{incident_id} not found.",
        )

    # Ownership check: Ordinary users may only cancel their own incidents
    if current_user.role != "admin":
        if incident.user_id is None or incident.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only cancel incidents you reported.",
            )

    # Check terminal status
    if incident.status in ("Resolved", "Cancelled", "Rejected"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel incident that is already {incident.status}.",
        )

    actor_role = "admin" if current_user.role == "admin" else "user"
    actor_name = current_user.name
    cancelled = crud.cancel_incident(
        db=db,
        incident_id=incident_id,
        reason=payload.reason,
        cancelled_by=actor_role,
        details=payload.details,
        actor_name=actor_name,
    )
    return cancelled


@app.post("/api/incidents/{incident_id}/acknowledge-cancellation", response_model=IncidentResponse, tags=["Incidents"])
def acknowledge_cancellation_endpoint(
    incident_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Admin acknowledges user cancellation and safely releases assigned resources."""
    updated = crud.acknowledge_cancellation_and_release(db, incident_id, actor=admin.name)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident #{incident_id} not found.",
        )
    return updated


@app.post("/api/incidents/{incident_id}/resolve", response_model=IncidentResponse, tags=["Incidents"])
def resolve_incident_endpoint(
    incident_id: int,
    notes: Optional[str] = Query(None),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Admin marks incident resolved and releases active resources."""
    updated = crud.resolve_incident(db, incident_id, actor=admin.name, notes=notes)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident #{incident_id} not found.",
        )
    return updated


# ==============================================================================
# Resource Routes
# ==============================================================================
@app.get("/api/resources", response_model=List[ResourceResponse], tags=["Resources"])
def list_resources(
    status_filter: Optional[str] = Query(None, alias="status"),
    category_filter: Optional[str] = Query(None, alias="category"),
    db: Session = Depends(get_db),
):
    return crud.get_resources(db, status_filter=status_filter, category_filter=category_filter)


@app.post("/api/resources", response_model=ResourceResponse, status_code=status.HTTP_201_CREATED, tags=["Resources"])
def create_resource(
    payload: ResourceCreate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    res = Resource(
        resource_code=payload.resource_code,
        name=payload.name,
        category=payload.category,
        capabilities=payload.capabilities,
        location_name=payload.location_name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        status=payload.status or "Available",
        capacity=payload.capacity or 1,
        contact_phone=payload.contact_phone,
        geom=make_point_wkt(payload.latitude, payload.longitude) if payload.latitude and payload.longitude else None,
    )
    db.add(res)
    db.commit()
    db.refresh(res)
    return res


@app.get("/api/resources/{resource_id}", response_model=ResourceResponse, tags=["Resources"])
def get_resource(resource_id: int, db: Session = Depends(get_db)):
    res = crud.get_resource_by_id(db, resource_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resource #{resource_id} not found.",
        )
    return res


@app.patch("/api/resources/{resource_id}", response_model=ResourceResponse, tags=["Resources"])
def update_resource_endpoint(
    resource_id: int,
    payload: ResourceUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    res = crud.update_resource(db, resource_id, payload.model_dump(exclude_unset=True))
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resource #{resource_id} not found.",
        )
    return res


# ==============================================================================
# Smart Allocation & Shortage Routes
# ==============================================================================
@app.post("/api/allocations/recommend", tags=["Allocation"])
def recommend_allocation(
    payload: AllocationRecommendRequest,
    db: Session = Depends(get_db),
):
    """Evaluate suitable resource for a specific incident."""
    incident = db.query(Incident).filter(Incident.id == payload.incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found.")

    available = db.query(Resource).filter(Resource.status == "Available").all()
    recommendation = evaluate_allocation_for_incident(incident, available, db)
    return recommendation


@app.post("/api/allocations/multi-recommend", tags=["Allocation"])
def multi_recommend_allocation(
    db: Session = Depends(get_db),
):
    """Evaluate and recommend allocations across all active unassigned incidents."""
    assigned_inc_ids = {a.incident_id for a in db.query(Assignment).filter(Assignment.status == "Active").all()}
    active_incidents = (
        db.query(Incident)
        .filter(Incident.status.notin_(["Resolved", "Cancelled", "Rejected"]), ~Incident.id.in_(assigned_inc_ids))
        .all()
    )
    return compute_multi_incident_allocations(active_incidents, db)


@app.post("/api/allocations/confirm", tags=["Allocation"])
def confirm_allocation_endpoint(
    payload: AllocationConfirmRequest,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Coordinator confirms assignment of a resource to an incident.
    Enforces strict conflict prevention.
    """
    try:
        assignment = crud.confirm_assignment(
            db=db,
            incident_id=payload.incident_id,
            resource_id=payload.resource_id,
            assigned_by=admin.name,
            notes=payload.notes,
        )
        return {
            "status": "success",
            "message": f"Resource assigned successfully to incident.",
            "assignment_id": assignment.id,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@app.post("/api/allocations/{assignment_id}/release", tags=["Allocation"])
def release_assignment_endpoint(
    assignment_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    released = crud.release_assignment(db, assignment_id, actor=admin.name)
    if not released:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    return {"status": "success", "message": "Resource safely released back to fleet."}


@app.get("/api/allocations/shortages", tags=["Allocation"])
def list_current_shortages(db: Session = Depends(get_db)):
    """Retrieve all current resource shortages and suggested external alternatives."""
    return get_current_shortages(db)


# ==============================================================================
# External Providers Routes
# ==============================================================================
@app.get("/api/providers", response_model=List[ProviderResponse], tags=["Providers"])
def list_providers(db: Session = Depends(get_db)):
    return crud.get_providers(db)


@app.post("/api/providers", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED, tags=["Providers"])
def create_provider(
    payload: ProviderCreate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    provider = ExternalProvider(
        name=payload.name,
        provider_type=payload.provider_type,
        is_registered_partner=payload.is_registered_partner,
        location_name=payload.location_name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        contact_person=payload.contact_person,
        phone=payload.phone,
        service_capabilities=payload.service_capabilities,
        estimated_base_charge=payload.estimated_base_charge,
        is_active=True,
        geom=make_point_wkt(payload.latitude, payload.longitude) if payload.latitude and payload.longitude else None,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider


@app.post("/api/providers/enquiries", response_model=ProviderEnquiryResponse, status_code=status.HTTP_201_CREATED, tags=["Providers"])
def create_enquiry(
    payload: ProviderEnquiryCreate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Record simulated coordinator enquiry with external hospital/ambulance partner."""
    enquiry = crud.create_provider_enquiry(
        db=db,
        incident_id=payload.incident_id,
        provider_id=payload.provider_id,
        charge_quote=payload.charge_quote or 0.0,
        subsidy_amount=payload.subsidy_amount or 0.0,
        user_consent=payload.user_consent or "Pending",
        response_time_minutes=payload.response_time_minutes or 15,
        notes=payload.notes,
    )
    return enquiry


@app.patch("/api/providers/enquiries/{enquiry_id}", response_model=ProviderEnquiryResponse, tags=["Providers"])
def update_enquiry_consent(
    enquiry_id: int,
    payload: ProviderEnquiryUpdate,
    db: Session = Depends(get_db),
):
    """Update external enquiry status, recorded quote, or user consent."""
    updated = crud.update_provider_enquiry(
        db=db,
        enquiry_id=enquiry_id,
        status_val=payload.status,
        user_consent=payload.user_consent,
        charge_quote=payload.charge_quote,
        notes=payload.notes,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Provider enquiry record not found.")
    return updated


# ==============================================================================
# Notifications & Feedback Routes
# ==============================================================================
@app.get("/api/notifications", response_model=List[NotificationResponse], tags=["Notifications"])
def get_notifications(
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id if current_user else None
    return crud.get_user_notifications(db, user_id=user_id)


@app.patch("/api/notifications/{notification_id}/read", tags=["Notifications"])
def mark_read(notification_id: int, db: Session = Depends(get_db)):
    success = crud.mark_notification_read(db, notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return {"status": "success"}


@app.post("/api/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED, tags=["Feedback"])
def submit_incident_feedback(
    payload: FeedbackCreate,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Submit post-resolution rating and tags."""
    try:
        user_id = current_user.id if current_user else None
        return crud.submit_feedback(
            db=db,
            incident_id=payload.incident_id,
            rating=payload.rating,
            tags=payload.tags,
            comments=payload.comments,
            user_id=user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/feedback", response_model=List[FeedbackResponse], tags=["Feedback"])
def list_feedback(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return crud.get_feedback_list(db)


# ==============================================================================
# Chatbot & Simulation Routes
# ==============================================================================
@app.post("/api/chatbot/message", response_model=ChatbotMessageResponse, tags=["Chatbot"])
def chat_with_sahara(payload: ChatbotMessageRequest, db: Session = Depends(get_db)):
    """Communicate with Sahara, the caring emergency support companion."""
    session_id = payload.session_id or "default_session"
    result = process_sahara_message(payload.message, session_id, db)
    return ChatbotMessageResponse(**result)


@app.get("/api/admin/analytics", tags=["Analytics"])
def get_analytics(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Command centre metrics and KPIs."""
    return crud.get_platform_analytics(db)


@app.get("/api/admin/predictions", tags=["Analytics"])
def get_shortage_predictions(
    zone: Optional[str] = Query(None),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Predict resource shortage risk by geographic zone."""
    return predict_resource_shortage_risk(db, zone_name=zone)


@app.post("/api/simulation/reset", tags=["Simulation"])
def reset_simulation(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Reset the database to clean demo state for repeatable presentation.
    Strictly restricted to authenticated administrators in development/testing environments.
    Disabled in production.
    """
    env = os.getenv("CAREON_ENV", os.getenv("ENVIRONMENT", "development")).lower()
    if env in ("production", "prod"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Simulation reset is disabled in production environments.",
        )
    # Delete all records and reseed
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    crud.seed_demo_data(db)
    return {"status": "success", "message": "Demo data successfully reset to clean state."}


# ==============================================================================
# Legacy Compatibility Routes (Ensures all existing tests pass 100%)
# ==============================================================================
@app.get("/api/stats", response_model=StatsResponse, tags=["Analytics"])
def get_dashboard_stats(db: Session = Depends(get_db)):
    return crud.get_stats(db)


@app.get("/api/emergencies", response_model=List[EmergencyResponse], tags=["Emergencies"])
def list_emergencies(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority_filter: Optional[str] = Query(None, alias="priority"),
    db: Session = Depends(get_db),
):
    return crud.get_emergencies(db, status=status_filter, priority=priority_filter)


@app.get("/api/emergencies/{emergency_id}", response_model=EmergencyResponse, tags=["Emergencies"])
def get_emergency(emergency_id: int, db: Session = Depends(get_db)):
    item = crud.get_emergency_by_id(db, emergency_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emergency with ID {emergency_id} not found.",
        )
    return item


@app.post("/api/emergencies", response_model=EmergencyResponse, status_code=status.HTTP_201_CREATED, tags=["Emergencies"])
def create_emergency(payload: EmergencyCreate, db: Session = Depends(get_db)):
    return crud.create_emergency(db, payload)


@app.patch("/api/emergencies/{emergency_id}/status", response_model=EmergencyResponse, tags=["Emergencies"])
def update_emergency_status(
    emergency_id: int, payload: EmergencyUpdateStatus, db: Session = Depends(get_db)
):
    updated = crud.update_emergency_status(db, emergency_id, payload.status)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emergency with ID {emergency_id} not found.",
        )
    return updated


@app.delete(
    "/api/emergencies/{emergency_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Legacy Emergencies (Deprecated)"],
    deprecated=True,
)
def delete_emergency(
    emergency_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    [DEPRECATED] Delete an emergency record from the legacy hospital-room system.
    Requires administrator authorization.
    """
    success = crud.delete_emergency(db, emergency_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emergency with ID {emergency_id} not found.",
        )
    return None
