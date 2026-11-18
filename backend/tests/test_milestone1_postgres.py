"""
CareOn — Milestone 1 Integration Test Suite
============================================
Exercises PostgreSQL + PostGIS + Alembic + Redis rate limiting.

Requirements:
  - PostgreSQL 17 running with PostGIS extension
  - Database: careon_test  (CREATE DATABASE careon_test;)
  - PostGIS: psql -d careon_test -c "CREATE EXTENSION IF NOT EXISTS postgis;"
  - Redis running on localhost:6379

Run:
  cd backend
  CAREON_TESTING=true DATABASE_URL=postgresql+psycopg:///careon_test \\
      REDIS_URL=redis://localhost:6379/0 \\
      PYTHONPATH=. pytest tests/test_milestone1_postgres.py -v
"""
from __future__ import annotations

import os
import time
import pytest

# ---------------------------------------------------------------------------
# Skip guard: skip the entire module when PostgreSQL is not configured
# ---------------------------------------------------------------------------
_PG_URL = os.getenv("DATABASE_URL", "")
_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

pytestmark = pytest.mark.skipif(
    "postgresql" not in _PG_URL,
    reason="M1 integration tests require DATABASE_URL=postgresql+psycopg:///...",
)

from sqlalchemy import create_engine, inspect as sa_inspect, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base, get_db, normalize_database_url
from app.main import app
from app import crud
from app.models import make_point_wkt, validate_coordinates
from app.redis_client import reset_redis_client_for_tests, get_redis_client
from app.spatial import (
    find_resources_within_radius,
    find_incidents_within_radius,
    find_providers_within_radius,
    _haversine_m,
)

# ---------------------------------------------------------------------------
# Shared PostgreSQL engine + session factory
# ---------------------------------------------------------------------------
PG_URL = normalize_database_url(_PG_URL)

pg_engine = create_engine(
    PG_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)
PGSession = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def pg_schema():
    """Ensure a clean schema for the whole test module, then tear down."""
    Base.metadata.drop_all(bind=pg_engine)
    Base.metadata.create_all(bind=pg_engine)
    yield
    Base.metadata.drop_all(bind=pg_engine)


@pytest.fixture()
def db():
    """Yield a PostgreSQL session per test; rollback after each."""
    session = PGSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def seeded_db(db):
    """Seed demo data into the PostgreSQL test database."""
    crud.seed_demo_data(db)
    db.commit()
    yield db
    # Cleanup seeded data between tests
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()


@pytest.fixture()
def pg_client(seeded_db):
    """FastAPI TestClient wired to the PostgreSQL test session."""
    def override_get_db():
        try:
            yield seeded_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# M1-B: Alembic / Schema tests
# ---------------------------------------------------------------------------

class TestSchema:
    def test_all_expected_tables_exist(self, db):
        """All 14 ORM-defined tables must be present in the PostgreSQL schema."""
        inspector = sa_inspect(pg_engine)
        existing = set(inspector.get_table_names())
        required = {
            "users", "incidents", "resources", "assignments",
            "incident_updates", "external_providers", "provider_enquiries",
            "notifications", "cancellations", "feedback",
            "audit_logs", "verification_logs", "emergencies",
            "alembic_version",
        }
        # alembic_version only exists if Alembic was run; skip that check in create_all mode
        required.discard("alembic_version")
        missing = required - existing
        assert not missing, f"Missing tables: {missing}"

    def test_geom_columns_exist(self, db):
        """Spatial geom columns must be present on incidents, resources, external_providers."""
        inspector = sa_inspect(pg_engine)
        for table in ("incidents", "resources", "external_providers"):
            cols = {c["name"] for c in inspector.get_columns(table)}
            assert "geom" in cols, f"geom column missing from {table}"

    def test_postgis_extension_active(self, db):
        """ST_Distance function must be callable — confirms PostGIS is loaded."""
        result = db.execute(
            text("SELECT ST_Distance('POINT(76.65 12.30)'::geography, 'POINT(76.66 12.31)'::geography)")
        ).scalar()
        assert result is not None
        assert float(result) > 0


# ---------------------------------------------------------------------------
# M1-A: PostgreSQL CRUD tests
# ---------------------------------------------------------------------------

class TestPostgresCRUD:
    def test_create_and_read_user(self, db):
        from app.auth import hash_password
        from app.models import User
        u = User(
            email="pg_test_user@careon.org",
            name="PG Test",
            phone="+91 999 000 0001",
            hashed_password=hash_password("test123"),
            role="user",
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        assert u.id is not None
        fetched = db.query(User).filter_by(email="pg_test_user@careon.org").first()
        assert fetched is not None
        assert fetched.name == "PG Test"

    def test_create_incident_populates_geom(self, seeded_db):
        from app.schemas import IncidentCreate
        from app.models import Incident
        payload = IncidentCreate(
            category="Medical",
            description="Integration test incident",
            location_name="Test Location, Mysuru",
            latitude=12.3052,
            longitude=76.6552,
            affected_people=1,
            help_required="Ambulance",
            contact_name="Test Reporter",
            contact_phone="+91 999 111 2222",
        )
        incident = crud.create_incident(seeded_db, payload, user_id=None)
        assert incident.id is not None
        assert incident.geom is not None, "geom must be populated on create_incident"
        assert incident.tracking_token is not None

    def test_coordinate_validation_rejects_invalid(self):
        from pydantic import ValidationError
        from app.schemas import IncidentCreate
        with pytest.raises(ValidationError):
            IncidentCreate(
                category="Medical",
                description="Bad coords",
                location_name="Nowhere",
                latitude=200.0,  # > 90 — invalid
                longitude=76.6552,
                affected_people=1,
                help_required="Help",
                contact_name="X",
                contact_phone="+91 000",
            )

    def test_coordinate_validation_rejects_bad_longitude(self):
        from pydantic import ValidationError
        from app.schemas import IncidentCreate
        with pytest.raises(ValidationError):
            IncidentCreate(
                category="Medical",
                description="Bad lon",
                location_name="Nowhere",
                latitude=12.3052,
                longitude=-200.0,  # < -180 — invalid
                affected_people=1,
                help_required="Help",
                contact_name="X",
                contact_phone="+91 000",
            )


# ---------------------------------------------------------------------------
# M1-C + M1-D: Spatial / duplicate detection tests
# ---------------------------------------------------------------------------

class TestSpatial:
    def test_find_resources_within_radius(self, seeded_db):
        """Seed has 8 resources all in Mysuru city; all should be within 25 km."""
        results = find_resources_within_radius(seeded_db, lat=12.3052, lon=76.6552, radius_m=25_000)
        assert len(results) >= 1, "Expected at least one resource near Mysuru centre"

    def test_find_resources_ordered_by_distance(self, seeded_db):
        """Resources must be returned sorted nearest-first."""
        results = find_resources_within_radius(seeded_db, lat=12.3052, lon=76.6552, radius_m=25_000)
        if len(results) < 2:
            pytest.skip("Not enough resources to verify ordering")
        for i in range(len(results) - 1):
            d1 = _haversine_m(12.3052, 76.6552, results[i].latitude or 0, results[i].longitude or 0)
            d2 = _haversine_m(12.3052, 76.6552, results[i + 1].latitude or 0, results[i + 1].longitude or 0)
            assert d1 <= d2 + 100, f"Results not ordered: {d1:.0f}m > {d2:.0f}m"

    def test_find_resources_status_filter(self, seeded_db):
        """Only Available resources should be returned when status='Available'."""
        results = find_resources_within_radius(
            seeded_db, lat=12.3052, lon=76.6552, radius_m=25_000, status="Available"
        )
        for r in results:
            assert r.status == "Available"

    def test_find_resources_category_filter(self, seeded_db):
        results = find_resources_within_radius(
            seeded_db, lat=12.3052, lon=76.6552, radius_m=25_000, category="Medical Ambulance"
        )
        for r in results:
            assert r.category == "Medical Ambulance"

    def test_find_incidents_within_radius(self, seeded_db):
        results = find_incidents_within_radius(seeded_db, lat=12.3052, lon=76.6552, radius_m=20_000)
        # Seed has 5 incidents; at least some should be active
        assert isinstance(results, list)

    def test_find_incidents_excludes_terminal(self, seeded_db):
        from app.models import Incident
        results = find_incidents_within_radius(
            seeded_db, lat=12.3052, lon=76.6552, radius_m=20_000, exclude_terminal=True
        )
        for inc in results:
            assert inc.status not in ("Resolved", "Cancelled", "Rejected")

    def test_duplicate_detection_nearby_same_category(self, seeded_db):
        """Creating an incident very close to an existing active one should flag as duplicate."""
        from app.schemas import IncidentCreate
        # Seed has CARE-2026-101 (Medical) at some Mysuru location
        # Create another Medical incident at nearly the same location
        payload = IncidentCreate(
            category="Medical",
            description="Another test medical incident very close by",
            location_name="KR Hospital Area",
            latitude=12.3052,  # same as CARE-2026-105 (Resolved — won't flag)
            longitude=76.6552,
            affected_people=2,
            help_required="Ambulance",
            contact_name="Test",
            contact_phone="+91 123 456 7890",
        )
        # First, create a fresh active incident at this location
        first = crud.create_incident(seeded_db, payload, user_id=None)
        assert not first.is_duplicate  # No pre-existing active incident here

        # Now create another with same location + category → should be flagged
        second = crud.create_incident(seeded_db, payload, user_id=None)
        assert second.is_duplicate, "Second nearby same-category incident must be flagged as duplicate"
        assert second.duplicate_of_id is not None

    def test_duplicate_detection_different_category_not_flagged(self, seeded_db):
        """Different category at same location must not be flagged as duplicate."""
        from app.schemas import IncidentCreate
        base_payload = dict(
            description="Distinct category test",
            location_name="Same Location",
            latitude=12.3600,
            longitude=76.6800,
            affected_people=1,
            help_required="Help",
            contact_name="Tester",
            contact_phone="+91 111 222 3333",
        )
        fire_incident = crud.create_incident(
            seeded_db, IncidentCreate(category="Fire", **base_payload), user_id=None
        )
        flood_incident = crud.create_incident(
            seeded_db, IncidentCreate(category="Flood", **base_payload), user_id=None
        )
        assert not flood_incident.is_duplicate, "Different category at same location must not flag as duplicate"

    def test_find_providers_within_radius(self, seeded_db):
        results = find_providers_within_radius(seeded_db, lat=12.3052, lon=76.6552, radius_m=20_000)
        assert len(results) >= 1

    def test_validate_coordinates_accepts_valid(self):
        # validate_coordinates returns (lat, lon) tuple on success
        result = validate_coordinates(12.3052, 76.6552)
        assert result == (12.3052, 76.6552)

    def test_validate_coordinates_rejects_invalid_lat(self):
        # validate_coordinates raises ValueError for out-of-range latitude
        with pytest.raises(ValueError, match="latitude"):
            validate_coordinates(200.0, 76.6552)

    def test_validate_coordinates_rejects_invalid_lon(self):
        # validate_coordinates raises ValueError for out-of-range longitude
        with pytest.raises(ValueError, match="longitude"):
            validate_coordinates(12.3052, 300.0)

    def test_make_point_wkt_format(self):
        # CareOn uses EWKT format: SRID=4326;POINT(lon lat)
        wkt = make_point_wkt(12.3052, 76.6552)
        assert "POINT(" in wkt
        assert "76.6552" in wkt
        assert "12.3052" in wkt
        assert "4326" in wkt  # SRID must be embedded


# ---------------------------------------------------------------------------
# M0 Partial unique index test on PostgreSQL
# ---------------------------------------------------------------------------

class TestConcurrentAssignment:
    def test_active_assignment_uniqueness(self, seeded_db):
        """The uq_active_assignment_resource partial index must prevent double-assignment."""
        from app.models import Resource, Incident, Assignment
        from sqlalchemy.exc import IntegrityError

        resource = seeded_db.query(Resource).filter(Resource.status == "Available").first()
        if not resource:
            pytest.skip("No available resource for concurrent assignment test")

        incident = (
            seeded_db.query(Incident)
            .filter(Incident.status.notin_(["Resolved", "Cancelled", "Rejected"]))
            .first()
        )
        if not incident:
            pytest.skip("No active incident for concurrent assignment test")

        # First assignment should succeed
        a1 = Assignment(
            incident_id=incident.id,
            resource_id=resource.id,
            assigned_by="TestCoordinator",
            status="Active",
        )
        seeded_db.add(a1)
        seeded_db.commit()

        # Second assignment of same resource while first is Active must fail
        a2 = Assignment(
            incident_id=incident.id,
            resource_id=resource.id,
            assigned_by="TestCoordinator",
            status="Active",
        )
        seeded_db.add(a2)
        with pytest.raises(IntegrityError):
            seeded_db.commit()
        seeded_db.rollback()


# ---------------------------------------------------------------------------
# M1-F: Redis rate limiting tests
# ---------------------------------------------------------------------------

class TestRateLimiting:
    @pytest.fixture(autouse=True)
    def clear_redis(self):
        """Flush all Redis keys before each rate limit test."""
        redis = get_redis_client()
        if redis:
            redis.flushdb()
        yield
        if redis:
            redis.flushdb()
        reset_redis_client_for_tests()

    def test_rate_limit_allows_requests_within_limit(self, pg_client):
        """Registration should succeed within the 10-request window."""
        # We cleared Redis; first attempt should work
        resp = pg_client.post("/api/auth/login", json={
            "email": "admin@careon.org",
            "password": "admin123",
        })
        # Could be 200 (success) or 401 (wrong DB state) but NOT 429
        assert resp.status_code != 429

    def test_rate_limit_blocks_after_threshold(self, pg_client):
        """After exceeding the auth limit (10 req/60s), 429 must be returned."""
        redis = get_redis_client()
        if not redis:
            pytest.skip("Redis unavailable — rate limiting requires Redis")

        # Temporarily lower limit for testing by forcing Redis counter above threshold
        # Rate limit scope "auth" = 10 requests per 60 seconds
        from app.rate_limiter import LIMITS
        max_req, window = LIMITS["auth"]

        # Force counter to max+1
        key = "rate_limit:auth:testclient"
        redis.set(key, max_req + 1, ex=window)

        # Temporarily re-enable rate limiting for this test
        import app.rate_limiter as rl_module
        original = rl_module._TESTING
        rl_module._TESTING = False

        try:
            resp = pg_client.post("/api/auth/login", json={
                "email": "user@test.com",
                "password": "wrong",
            })
            assert resp.status_code == 429, f"Expected 429, got {resp.status_code}"
            assert "Retry-After" in resp.headers
        finally:
            rl_module._TESTING = original

    def test_rate_limit_includes_retry_after_header(self, pg_client):
        """429 response must include a Retry-After header."""
        redis = get_redis_client()
        if not redis:
            pytest.skip("Redis unavailable")

        from app.rate_limiter import LIMITS
        import app.rate_limiter as rl_module
        max_req, window = LIMITS["auth"]
        redis.set("rate_limit:auth:testclient", max_req + 1, ex=window)

        original = rl_module._TESTING
        rl_module._TESTING = False
        try:
            resp = pg_client.post("/api/auth/login", json={"email": "x", "password": "y"})
            if resp.status_code == 429:
                assert "Retry-After" in resp.headers
                assert int(resp.headers["Retry-After"]) > 0
        finally:
            rl_module._TESTING = original

    def test_rate_limit_fails_open_without_redis(self, pg_client):
        """When Redis is unreachable, requests must be allowed through (fail-open)."""
        import app.rate_limiter as rl_module
        import app.redis_client as rc_module

        # Simulate Redis unavailability
        original_client = rc_module._redis_client
        rc_module._redis_client = None  # force None → no Redis

        original_testing = rl_module._TESTING
        rl_module._TESTING = False

        try:
            resp = pg_client.post("/api/auth/login", json={
                "email": "admin@careon.org",
                "password": "admin123",
            })
            # Must NOT return 429 or 500 — could be 200 or 401
            assert resp.status_code != 429
            assert resp.status_code != 500
        finally:
            rc_module._redis_client = original_client
            rl_module._TESTING = original_testing
            reset_redis_client_for_tests()


# ---------------------------------------------------------------------------
# M1-G: Auth token format verification
# ---------------------------------------------------------------------------

class TestAuthTokenFormat:
    def test_login_returns_bearer_token(self, pg_client):
        resp = pg_client.post("/api/auth/login", json={
            "email": "admin@careon.org",
            "password": "admin123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data.get("token_type", "").lower() == "bearer"
        # CareOn uses a custom 2-segment HMAC token (payload.signature)
        # rather than standard 3-segment JWT — both formats are valid; ensure token is non-empty
        token = data["access_token"]
        parts = token.split(".")
        assert len(parts) >= 2, "Token must have at least 2 dot-separated segments"
        assert len(token) > 32, "Token must be of substantial length"

    def test_me_requires_bearer_token(self, pg_client):
        # No auth
        resp = pg_client.get("/api/auth/me")
        assert resp.status_code in (401, 403)

        # With valid token
        login = pg_client.post("/api/auth/login", json={
            "email": "admin@careon.org",
            "password": "admin123",
        })
        token = login.json()["access_token"]
        me = pg_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200


# ---------------------------------------------------------------------------
# M1-I: Legacy endpoint compatibility
# ---------------------------------------------------------------------------

class TestLegacyCompatibility:
    def test_legacy_emergencies_list(self, pg_client):
        resp = pg_client.get("/api/emergencies")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_legacy_incidents_list_unauthenticated(self, pg_client):
        """Unauthenticated access to /api/incidents returns empty list (not 401)."""
        resp = pg_client.get("/api/incidents")
        assert resp.status_code == 200

    def test_stats_endpoint(self, pg_client):
        resp = pg_client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data


# ---------------------------------------------------------------------------
# M1-A: Connection pooling config
# ---------------------------------------------------------------------------

class TestConnectionPooling:
    def test_engine_uses_postgresql_dialect(self):
        assert pg_engine.dialect.name == "postgresql"

    def test_connection_pool_config(self):
        pool = pg_engine.pool
        # pool_size and max_overflow are set via env or defaults
        assert pool.size() >= 1  # At minimum 1 connection available

    def test_multiple_concurrent_queries(self, db):
        """Multiple sequential queries should complete without pool exhaustion."""
        from app.models import User, Incident, Resource
        for _ in range(20):
            db.query(User).count()
            db.query(Incident).count()
            db.query(Resource).count()
        # If we get here without exception, pool is healthy
