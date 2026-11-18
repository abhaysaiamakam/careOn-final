"""
CareOn — Milestone 2 Identity, RBAC & Multi-Tenancy Test Suite
==============================================================
Validates:
  - Standard RFC 7519 JWT access tokens (PyJWT, HS256, claims, expiry, issuer, audience)
  - Refresh token rotation, hashing, revocation, and family-based reuse detection (theft protection)
  - RBAC roles (CITIZEN, DISPATCHER, RESPONDER, HOSPITAL_STAFF, ORG_ADMIN, SUPER_ADMIN)
  - Fine-grained permissions & deny-by-default behavior
  - Multi-organization tenant isolation and boundary checks
  - User profile management & session tracking
  - Privilege escalation prevention
  - Regression for M0 and M1 controls

Requirements:
  PostgreSQL 17 running on careon_test
  Redis running on localhost:6379

Run:
  CAREON_TESTING=true DATABASE_URL=postgresql+psycopg:///careon_test \\
    REDIS_URL=redis://localhost:6379/0 \\
    PYTHONPATH=. pytest tests/test_milestone2_identity.py -v
"""
import os
import time
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect as sa_inspect, text
from sqlalchemy.orm import sessionmaker

# Require PostgreSQL for integration tests
_PG_URL = os.getenv("DATABASE_URL", "postgresql+psycopg:///careon_test")
pytestmark = pytest.mark.skipif(
    "postgresql" not in _PG_URL,
    reason="M2 tests require PostgreSQL test database",
)

from app.database import Base, get_db, normalize_database_url
from app.main import app
from app import crud
from app.models import (
    User,
    Organization,
    OrganizationMembership,
    RefreshToken,
    UserSession,
    AuditLog,
    Assignment,
    Resource,
    Incident,
)
from app.auth import hash_password, create_access_token, decode_access_token
from app.identity.jwt_handler import (
    create_access_token as jwt_create_token,
    decode_access_token as jwt_decode_token,
    ALGORITHM,
    ISSUER,
    AUDIENCE,
)
from app.identity.refresh_tokens import (
    generate_refresh_token,
    create_refresh_token_record,
    rotate_refresh_token,
    revoke_refresh_token,
    revoke_all_user_tokens,
    _sha256_hex,
)
from app.rbac.roles import (
    UserRole,
    Permission,
    get_permissions,
    has_permission,
    ROLE_MIGRATION_MAP,
)
from app.rbac.dependencies import get_current_user_flexible

PG_URL = normalize_database_url(_PG_URL)
engine = create_engine(PG_URL, pool_size=5, max_overflow=10, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module", autouse=True)
def setup_m2_database():
    """Ensure database schema is clean and seeded for the test module."""
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(scope="function")
def db():
    """Yield a database session and clean up created test entities after each test."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        try:
            session.query(OrganizationMembership).delete()
            session.query(Organization).delete()
            session.query(Assignment).filter(Assignment.assigned_by == "Coordinator").delete()
            session.query(User).filter(User.email.like("%attacker%")).delete()
            session.commit()
        except Exception:
            session.rollback()
        session.close()


@pytest.fixture(scope="function")
def client(db):
    """FastAPI TestClient wired to the test database session."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_users(db):
    """Create a standardized set of test users across multiple roles."""
    # Clean up any leftover test users
    db.query(User).filter(User.email.like("m2_%@careon.org")).delete(synchronize_session=False)
    db.query(User).filter(User.email.like("%attacker%")).delete(synchronize_session=False)
    db.commit()

    users = {
        "citizen": User(
            name="M2 Citizen",
            email="m2_citizen@careon.org",
            phone="+91 90000 00001",
            hashed_password=hash_password("citizen123"),
            role="citizen",
            is_active=True,
        ),
        "dispatcher": User(
            name="M2 Dispatcher",
            email="m2_dispatcher@careon.org",
            phone="+91 90000 00002",
            hashed_password=hash_password("dispatcher123"),
            role="dispatcher",
            is_active=True,
        ),
        "responder": User(
            name="M2 Responder",
            email="m2_responder@careon.org",
            phone="+91 90000 00003",
            hashed_password=hash_password("responder123"),
            role="responder",
            is_active=True,
        ),
        "hospital": User(
            name="M2 Hospital Staff",
            email="m2_hospital@careon.org",
            phone="+91 90000 00004",
            hashed_password=hash_password("hospital123"),
            role="hospital_staff",
            is_active=True,
        ),
        "org_admin": User(
            name="M2 Org Admin",
            email="m2_orgadmin@careon.org",
            phone="+91 90000 00005",
            hashed_password=hash_password("orgadmin123"),
            role="org_admin",
            is_active=True,
        ),
        "super_admin": User(
            name="M2 Super Admin",
            email="m2_superadmin@careon.org",
            phone="+91 90000 00006",
            hashed_password=hash_password("superadmin123"),
            role="super_admin",
            is_active=True,
        ),
        "inactive": User(
            name="M2 Inactive User",
            email="m2_inactive@careon.org",
            phone="+91 90000 00007",
            hashed_password=hash_password("inactive123"),
            role="citizen",
            is_active=False,
        ),
    }

    for u in users.values():
        db.add(u)
    db.commit()
    for u in users.values():
        db.refresh(u)
    return users


# ==============================================================================
# 1. JWT Standard Compliance Tests (M2-B)
# ==============================================================================
class TestJWTStandardCompliance:
    def test_jwt_structure_and_claims(self):
        """Tokens must be standard RFC 7519 3-segment HS256 JWTs with required claims."""
        token = jwt_create_token(
            user_id=101,
            email="test@careon.org",
            role="citizen",
            org_ids=[1, 2],
        )
        parts = token.split(".")
        assert len(parts) == 3, "JWT must consist of exactly three dot-separated segments"

        payload = jwt_decode_token(token)
        assert payload is not None
        assert payload["sub"] == "101"
        assert payload["email"] == "test@careon.org"
        assert payload["role"] == "citizen"
        assert payload["org_ids"] == [1, 2]
        assert payload["iss"] == ISSUER
        assert payload["aud"] == AUDIENCE
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_jwt_rejects_expired_token(self):
        """Expired JWTs must be strictly rejected and return None."""
        now = datetime.now(timezone.utc) - timedelta(minutes=60)
        token = jwt_create_token(
            user_id=101,
            email="test@careon.org",
            role="citizen",
            extra_claims={"iat": now, "exp": now + timedelta(minutes=10)},
        )
        payload = jwt_decode_token(token)
        assert payload is None, "Expired JWT must decode to None"

    def test_jwt_rejects_tampered_signature(self):
        """Tampered tokens must be rejected."""
        token = jwt_create_token(user_id=101, email="test@careon.org", role="citizen")
        parts = token.split(".")
        tampered = f"{parts[0]}.{parts[1]}.bad_signature_here"
        assert jwt_decode_token(tampered) is None

    def test_jwt_rejects_invalid_issuer_or_audience(self):
        """Tokens with spoofed issuer or audience must be rejected."""
        bad_iss = jwt_create_token(
            user_id=101, email="test@careon.org", role="citizen",
            extra_claims={"iss": "untrusted-issuer"},
        )
        assert jwt_decode_token(bad_iss) is None

        bad_aud = jwt_create_token(
            user_id=101, email="test@careon.org", role="citizen",
            extra_claims={"aud": "untrusted-client"},
        )
        assert jwt_decode_token(bad_aud) is None

    def test_no_sensitive_pii_in_jwt(self):
        """Access token claims must not leak phone numbers or password hashes."""
        token = jwt_create_token(user_id=101, email="test@careon.org", role="citizen")
        payload = jwt_decode_token(token)
        assert "phone" not in payload
        assert "password" not in payload
        assert "hashed_password" not in payload


# ==============================================================================
# 2. Refresh Token Lifecycle & Theft Protection Tests (M2-B)
# ==============================================================================
class TestRefreshTokenLifecycle:
    def test_raw_token_is_never_stored_in_db(self, db, test_users):
        """The database must only store the SHA-256 hash of the refresh token, never the raw token."""
        user = test_users["citizen"]
        raw_token, record = create_refresh_token_record(db, user_id=user.id, session_id="sess_123")
        db.commit()

        assert raw_token != record.token_hash
        assert len(record.token_hash) == 64  # SHA-256 hex is 64 characters
        assert _sha256_hex(raw_token) == record.token_hash

        # Verify raw token is not found in database text fields
        db_record = db.query(RefreshToken).filter(RefreshToken.id == record.id).first()
        assert db_record.token_hash == record.token_hash
        assert raw_token not in str(db_record.__dict__)

    def test_refresh_token_rotation_success(self, db, test_users):
        """Rotating a valid refresh token issues a new access token and a new refresh token in the same family."""
        user = test_users["citizen"]
        raw_token, old_record = create_refresh_token_record(db, user_id=user.id, session_id="sess_rot")
        db.commit()

        old_family_id = old_record.family_id

        # Rotate token
        result = rotate_refresh_token(db, raw_token, device_hint="iPhone 15")
        db.commit()

        assert result is not None
        new_raw_token, new_access_token, new_record = result

        assert new_raw_token != raw_token
        assert new_record.family_id == old_family_id, "New token must belong to the same family"
        assert new_record.is_revoked is False

        # Old record must be marked revoked
        db.refresh(old_record)
        assert old_record.is_revoked is True
        assert old_record.revoked_reason == "rotated"

    def test_theft_protection_reuse_detection_revokes_entire_family(self, db, test_users):
        """
        CRITICAL SECURITY REQUIREMENT:
        If a previously rotated refresh token is reused, CareOn must detect the theft,
        immediately revoke ALL tokens in that family, and log a security audit event.
        """
        user = test_users["citizen"]
        # Step 1: Issue token 1
        raw_token_1, record_1 = create_refresh_token_record(db, user_id=user.id, session_id="sess_steal")
        db.commit()

        # Step 2: Legitimate rotation -> Token 2
        rot_result = rotate_refresh_token(db, raw_token_1)
        db.commit()
        raw_token_2, _, record_2 = rot_result

        # Step 3: Attacker tries to reuse Token 1 (already rotated)
        reused_result = rotate_refresh_token(db, raw_token_1)
        db.commit()

        assert reused_result is None, "Reuse of revoked token must be rejected"

        # Step 4: Verify Token 2 was automatically revoked due to theft detection
        db.refresh(record_2)
        assert record_2.is_revoked is True, "All tokens in the family must be revoked upon reuse detection"
        assert record_2.revoked_reason == "reuse_detected"

        # Step 5: Verify security audit log exists
        audit = (
            db.query(AuditLog)
            .filter(AuditLog.action == "refresh_token_reuse_detected")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert audit is not None
        assert str(user.id) in audit.details or str(user.id) in audit.entity_id

    def test_logout_revokes_token(self, db, test_users):
        """Logging out must revoke the refresh token."""
        user = test_users["citizen"]
        raw_token, record = create_refresh_token_record(db, user_id=user.id, session_id="sess_logout")
        db.commit()

        revoked = revoke_refresh_token(db, raw_token)
        db.commit()
        assert revoked is True

        db.refresh(record)
        assert record.is_revoked is True
        assert record.revoked_reason == "logout"


# ==============================================================================
# 3. RBAC Roles & Permissions Tests (M2-D)
# ==============================================================================
class TestRBACPermissions:
    def test_citizen_permissions(self):
        """Citizen role has strictly bounded self-service permissions."""
        assert has_permission(UserRole.CITIZEN, Permission.INCIDENT_CREATE) is True
        assert has_permission(UserRole.CITIZEN, Permission.INCIDENT_READ_OWN) is True
        assert has_permission(UserRole.CITIZEN, Permission.INCIDENT_CANCEL_OWN) is True
        # Must NOT have operational or management permissions
        assert has_permission(UserRole.CITIZEN, Permission.INCIDENT_ASSIGN) is False
        assert has_permission(UserRole.CITIZEN, Permission.RESOURCE_MANAGE) is False
        assert has_permission(UserRole.CITIZEN, Permission.INCIDENT_READ_OPERATIONAL) is False
        assert has_permission(UserRole.CITIZEN, Permission.ORG_MANAGE) is False

    def test_dispatcher_permissions(self):
        """Dispatcher role can view operational incidents, assign resources, and verify emergencies."""
        assert has_permission(UserRole.DISPATCHER, Permission.INCIDENT_READ_OPERATIONAL) is True
        assert has_permission(UserRole.DISPATCHER, Permission.INCIDENT_ASSIGN) is True
        assert has_permission(UserRole.DISPATCHER, Permission.INCIDENT_VERIFY) is True
        assert has_permission(UserRole.DISPATCHER, Permission.RESOURCE_MANAGE) is True
        assert has_permission(UserRole.DISPATCHER, Permission.ORG_MANAGE) is False

    def test_responder_permissions(self):
        """Responder role can read operational incidents and update their mission status."""
        assert has_permission(UserRole.RESPONDER, Permission.INCIDENT_READ_OPERATIONAL) is True
        assert has_permission(UserRole.RESPONDER, Permission.RESPONDER_MISSION_UPDATE) is True
        assert has_permission(UserRole.RESPONDER, Permission.RESOURCE_MANAGE) is False

    def test_hospital_staff_permissions(self):
        """Hospital staff can update hospital readiness and acknowledge patient handover."""
        assert has_permission(UserRole.HOSPITAL_STAFF, Permission.HOSPITAL_READINESS_UPDATE) is True
        assert has_permission(UserRole.HOSPITAL_STAFF, Permission.HANDOVER_ACKNOWLEDGE) is True
        assert has_permission(UserRole.HOSPITAL_STAFF, Permission.INCIDENT_ASSIGN) is False

    def test_organization_admin_permissions(self):
        """Organization Admin has dispatcher capabilities plus tenant organization management."""
        assert has_permission(UserRole.ORGANIZATION_ADMIN, Permission.INCIDENT_ASSIGN) is True
        assert has_permission(UserRole.ORGANIZATION_ADMIN, Permission.ORG_MANAGE) is True
        assert has_permission(UserRole.ORGANIZATION_ADMIN, Permission.USERS_MANAGE) is True

    def test_super_admin_has_all_permissions(self):
        """Super Admin carries all permissions defined in the platform."""
        perms = get_permissions(UserRole.SUPER_ADMIN)
        assert len(perms) == len(list(Permission))

    def test_legacy_role_mapping(self):
        """Legacy 'user' and 'admin' strings map seamlessly to modern roles."""
        assert ROLE_MIGRATION_MAP["user"] == UserRole.CITIZEN
        assert ROLE_MIGRATION_MAP["admin"] == UserRole.SUPER_ADMIN
        assert has_permission("user", Permission.INCIDENT_CREATE) is True
        assert has_permission("user", Permission.INCIDENT_ASSIGN) is False
        assert has_permission("admin", Permission.PLATFORM_CONFIGURE) is True


# ==============================================================================
# 4. Authentication Endpoints Integration Tests (M2-A, M2-B, M2-C)
# ==============================================================================
class TestAuthEndpoints:
    def test_login_returns_jwt_and_refresh_token(self, client, test_users):
        """Login must return a valid RFC 7519 JWT access token and a refresh token."""
        res = client.post(
            "/api/auth/login",
            json={"email": "m2_citizen@careon.org", "password": "citizen123"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "Bearer"

        # Verify access token is a 3-part JWT
        assert len(data["access_token"].split(".")) == 3
        assert data["user"]["email"] == "m2_citizen@careon.org"

    def test_login_invalid_password_returns_401(self, client, test_users):
        """Invalid credentials return 401 Unauthorized without disclosing account existence."""
        res = client.post(
            "/api/auth/login",
            json={"email": "m2_citizen@careon.org", "password": "wrong_password"},
        )
        assert res.status_code == 401

    def test_deactivated_user_cannot_login(self, client, test_users):
        """Deactivated accounts are denied login."""
        res = client.post(
            "/api/auth/login",
            json={"email": "m2_inactive@careon.org", "password": "inactive123"},
        )
        assert res.status_code == 401

    def test_refresh_endpoint_rotates_tokens(self, client, test_users):
        """POST /api/auth/refresh rotates the refresh token."""
        login_res = client.post(
            "/api/auth/login",
            json={"email": "m2_citizen@careon.org", "password": "citizen123"},
        )
        initial_refresh = login_res.json()["refresh_token"]

        ref_res = client.post(
            "/api/auth/refresh",
            json={"refresh_token": initial_refresh},
        )
        assert ref_res.status_code == 200
        ref_data = ref_res.json()
        assert "access_token" in ref_data
        assert "refresh_token" in ref_data
        assert ref_data["refresh_token"] != initial_refresh

    def test_logout_endpoint_invalidates_session(self, client, test_users):
        """POST /api/auth/logout invalidates refresh tokens."""
        login_res = client.post(
            "/api/auth/login",
            json={"email": "m2_citizen@careon.org", "password": "citizen123"},
        )
        token = login_res.json()["access_token"]
        refresh = login_res.json()["refresh_token"]

        logout_res = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
            json={"refresh_token": refresh},
        )
        assert logout_res.status_code == 200

        # Attempting to refresh with the logged-out token must fail
        ref_fail = client.post("/api/auth/refresh", json={"refresh_token": refresh})
        assert ref_fail.status_code == 401

    def test_change_password_and_invalidates_sessions(self, client, test_users):
        """Changing password updates the password and revokes all active refresh tokens."""
        login_res = client.post(
            "/api/auth/login",
            json={"email": "m2_citizen@careon.org", "password": "citizen123"},
        )
        token = login_res.json()["access_token"]
        refresh = login_res.json()["refresh_token"]

        # Change password
        ch_res = client.post(
            "/api/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "citizen123",
                "new_password": "new_citizen_pwd_456",
                "confirm_password": "new_citizen_pwd_456",
            },
        )
        assert ch_res.status_code == 200

        # Old refresh token is revoked
        ref_fail = client.post("/api/auth/refresh", json={"refresh_token": refresh})
        assert ref_fail.status_code == 401

        # Old password cannot login
        login_old = client.post(
            "/api/auth/login",
            json={"email": "m2_citizen@careon.org", "password": "citizen123"},
        )
        assert login_old.status_code == 401

        # New password succeeds
        login_new = client.post(
            "/api/auth/login",
            json={"email": "m2_citizen@careon.org", "password": "new_citizen_pwd_456"},
        )
        assert login_new.status_code == 200


# ==============================================================================
# 5. Multi-Organization & Tenant Isolation Tests (M2-E)
# ==============================================================================
class TestMultiTenancy:
    def test_create_organization_requires_super_admin(self, client, test_users):
        """Only Super Admin can create organizations. Ordinary users get 403 Forbidden."""
        citizen_token = create_access_token({"sub": test_users["citizen"].id, "email": "m2_citizen@careon.org", "role": "citizen"})
        super_token = create_access_token({"sub": test_users["super_admin"].id, "email": "m2_superadmin@careon.org", "role": "super_admin"})

        org_name = f"Mysuru Fire Services {int(time.time()*1000)}"
        org_payload = {
            "name": org_name,
            "org_type": "fire",
            "contact_phone": "+91 821 241 0101",
            "location_name": "Saraswathipuram, Mysuru",
        }

        # Citizen attempt -> 403
        cit_res = client.post(
            "/api/organizations",
            headers={"Authorization": f"Bearer {citizen_token}"},
            json=org_payload,
        )
        assert cit_res.status_code == 403

        # Super Admin attempt -> 201
        admin_res = client.post(
            "/api/organizations",
            headers={"Authorization": f"Bearer {super_token}"},
            json=org_payload,
        )
        assert admin_res.status_code == 201
        assert admin_res.json()["name"] == org_name

    def test_tenant_isolation_member_list(self, client, test_users, db):
        """A user from Org A cannot access private member rosters of Org B."""
        ts = int(time.time() * 1000)
        org1 = Organization(name=f"Org Alpha {ts}", org_type="ambulance_service", is_active=True)
        org2 = Organization(name=f"Org Beta {ts}", org_type="hospital", is_active=True)
        db.add_all([org1, org2])
        db.commit()

        # Add citizen to Org 1 only
        mem1 = OrganizationMembership(
            organization_id=org1.id,
            user_id=test_users["citizen"].id,
            membership_role="member",
            status="active",
        )
        db.add(mem1)
        db.commit()

        citizen_token = create_access_token({
            "sub": test_users["citizen"].id,
            "email": test_users["citizen"].email,
            "role": "citizen",
        })

        # Accessing own Org 1 members -> Allowed
        res_own = client.get(
            f"/api/organizations/{org1.id}/members",
            headers={"Authorization": f"Bearer {citizen_token}"},
        )
        assert res_own.status_code == 200

        # Accessing Org 2 members -> Forbidden (Tenant Isolation)
        res_other = client.get(
            f"/api/organizations/{org2.id}/members",
            headers={"Authorization": f"Bearer {citizen_token}"},
        )
        assert res_other.status_code == 403


# ==============================================================================
# 6. Privilege Escalation Prevention Tests (M2-D)
# ==============================================================================
class TestPrivilegeEscalationPrevention:
    def test_public_registration_cannot_set_admin_role(self, client):
        """Public registration attempting to pass role='super_admin' or 'admin' is forced to 'user'/'citizen'."""
        email = f"attacker_{int(time.time()*1000)}@careon.org"
        res = client.post(
            "/api/auth/register",
            json={
                "name": "Attacker",
                "email": email,
                "phone": "+91 99999 88888",
                "password": "password123",
                "role": "super_admin",  # Escalation attempt
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["user"]["role"] in ("user", "citizen")
        assert data["user"]["role"] not in ("admin", "super_admin")

    def test_profile_update_cannot_change_role_or_email(self, client, test_users):
        """Updating personal profile cannot elevate role or change verified email."""
        citizen_token = create_access_token({
            "sub": test_users["citizen"].id,
            "email": test_users["citizen"].email,
            "role": "citizen",
        })

        res = client.patch(
            "/api/users/me/profile",
            headers={"Authorization": f"Bearer {citizen_token}"},
            json={
                "name": "Updated Citizen Name",
                "role": "super_admin",  # should be ignored
                "email": "hacked@careon.org",  # should be ignored
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "Updated Citizen Name"
        assert data["role"] == "citizen"
        assert data["email"] == test_users["citizen"].email


# ==============================================================================
# 7. Regression Tests: M0 and M1 Controls on PostgreSQL (M2-J)
# ==============================================================================
class TestMilestoneRegression:
    def test_legacy_hmac_token_is_still_accepted(self, client, test_users):
        """Zero-downtime transition: older 2-segment HMAC tokens continue to authenticate seamlessly."""
        import base64, json, hmac, hashlib
        from app.auth import get_secret_key

        payload = {"sub": test_users["citizen"].id, "email": test_users["citizen"].email, "role": "citizen", "exp": int(time.time()) + 3600}
        enc = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        sig = hmac.new(get_secret_key().encode(), enc.encode(), hashlib.sha256).hexdigest()
        legacy_token = f"{enc}.{sig}"

        res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {legacy_token}"})
        assert res.status_code == 200
        assert res.json()["email"] == test_users["citizen"].email

    def test_concurrent_assignment_partial_unique_index(self, db, test_users):
        """M0 partial unique index (uq_active_assignment_resource) must prevent dual active assignments."""
        from app.models import Resource, Incident, Assignment
        from sqlalchemy.exc import IntegrityError

        res = db.query(Resource).filter(Resource.status == "Available").first()
        inc = db.query(Incident).filter(Incident.status.notin_(["Resolved", "Cancelled"])).first()
        if not res or not inc:
            pytest.skip("Requires available resource and active incident from seed data")

        # Clear any existing assignments on this resource before testing
        db.query(Assignment).filter(Assignment.resource_id == res.id).delete()
        db.commit()

        a1 = Assignment(incident_id=inc.id, resource_id=res.id, assigned_by="Coordinator", status="Active")
        db.add(a1)
        db.commit()

        a2 = Assignment(incident_id=inc.id, resource_id=res.id, assigned_by="Coordinator", status="Active")
        db.add(a2)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_simulation_reset_strictly_admin_only(self, client, test_users):
        """M0 SEC-001: simulation reset cannot be accessed without administrator authentication."""
        cit_token = create_access_token({"sub": test_users["citizen"].id, "email": "m2_citizen@careon.org", "role": "citizen"})
        res = client.post("/api/simulation/reset", headers={"Authorization": f"Bearer {cit_token}"})
        assert res.status_code == 403
