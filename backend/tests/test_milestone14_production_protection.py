"""
Unit and integration tests for Milestone 14.2:
- Production demo-seeding prevention and fail-closed security.
- Secret key validation and entropy requirements in production.
- Designated facility fail-closed resolution.
- WebSocket authentication payload schema flexibility.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from app.auth import validate_and_get_secret_key, KNOWN_INSECURE_SECRETS
from app.crud import seed_demo_data
from app.main import check_demo_seeding_safety
from app.hospital_ops.readiness import get_designated_facility
from app.models import HospitalFacility, Organization
from app.database import get_db


class TestSecretKeyProtection:
    def test_production_fails_if_secret_unset(self):
        with patch.dict(os.environ, {"CAREON_SECRET_KEY": ""}, clear=False):
            with pytest.raises(RuntimeError, match="CAREON_SECRET_KEY environment variable must be set"):
                validate_and_get_secret_key(environment="production", secret_override=None)

    def test_production_fails_on_known_insecure_secrets(self):
        for bad_secret in KNOWN_INSECURE_SECRETS:
            with pytest.raises(RuntimeError, match="known default demo secret key is strictly forbidden"):
                validate_and_get_secret_key(environment="production", secret_override=bad_secret)

    def test_production_fails_if_secret_too_short(self):
        short_secret = "short_secret_under_32_chars!"
        with pytest.raises(RuntimeError, match="must be at least 32 characters"):
            validate_and_get_secret_key(environment="production", secret_override=short_secret)

    def test_production_accepts_strong_secret(self):
        strong_secret = "a" * 64  # 64 characters
        result = validate_and_get_secret_key(environment="production", secret_override=strong_secret)
        assert result == strong_secret

    def test_development_allows_fallback(self):
        with patch.dict(os.environ, {"CAREON_SECRET_KEY": ""}, clear=False):
            result = validate_and_get_secret_key(environment="development", secret_override=None)
            assert result is not None
            assert len(result) > 0


class TestProductionDemoSeedingProtection:
    def test_production_variable_unset_is_safe(self):
        """In production, an unset ENABLE_DEMO_SEEDING must be safe (no crash, seeding skipped)."""
        should_seed = check_demo_seeding_safety(env_name="production", raw_enable_seeding=None)
        assert should_seed is False

    def test_production_false_string_does_not_fail(self):
        """In production, ENABLE_DEMO_SEEDING='false' must not cause false startup failure."""
        should_seed = check_demo_seeding_safety(env_name="production", raw_enable_seeding="false")
        assert should_seed is False

    def test_production_zero_string_does_not_fail(self):
        """In production, ENABLE_DEMO_SEEDING='0' must not cause false startup failure."""
        should_seed = check_demo_seeding_safety(env_name="production", raw_enable_seeding="0")
        assert should_seed is False

    def test_production_true_fails_startup(self):
        """In production, ENABLE_DEMO_SEEDING='true' must cause explicit startup failure."""
        with pytest.raises(RuntimeError, match="Demo data seeding cannot be enabled in a production environment"):
            check_demo_seeding_safety(env_name="production", raw_enable_seeding="true")

    def test_production_one_fails_startup(self):
        """In production, ENABLE_DEMO_SEEDING='1' must cause explicit startup failure."""
        with pytest.raises(RuntimeError, match="Demo data seeding cannot be enabled in a production environment"):
            check_demo_seeding_safety(env_name="production", raw_enable_seeding="1")

    def test_prod_alias_truthy_fails_startup(self):
        """When CAREON_ENV='prod', truthy ENABLE_DEMO_SEEDING must also fail startup."""
        with pytest.raises(RuntimeError, match="Demo data seeding cannot be enabled in a production environment"):
            check_demo_seeding_safety(env_name="prod", raw_enable_seeding="true")

    def test_development_with_seeding_enabled(self):
        """In development/test, seeding is enabled when unset or explicitly truthy."""
        assert check_demo_seeding_safety(env_name="development", raw_enable_seeding=None) is True
        assert check_demo_seeding_safety(env_name="development", raw_enable_seeding="true") is True
        assert check_demo_seeding_safety(env_name="development", raw_enable_seeding="1") is True
        assert check_demo_seeding_safety(env_name="test", raw_enable_seeding=None) is True

    def test_development_with_seeding_disabled(self):
        """In development/test, seeding is disabled when explicitly falsy ('false' or '0')."""
        assert check_demo_seeding_safety(env_name="development", raw_enable_seeding="false") is False
        assert check_demo_seeding_safety(env_name="development", raw_enable_seeding="0") is False
        assert check_demo_seeding_safety(env_name="test", raw_enable_seeding="false") is False

    def test_unknown_environment_is_failsafe(self):
        """Unknown or unconfigured environments must fail safe and never seed."""
        assert check_demo_seeding_safety(env_name="staging", raw_enable_seeding="true") is False
        assert check_demo_seeding_safety(env_name="", raw_enable_seeding="true") is False

    def test_seed_demo_data_direct_invocation_in_production(self):
        """Direct invocation of crud.seed_demo_data() in production must raise RuntimeError."""
        mock_db = MagicMock()
        with patch.dict(os.environ, {"CAREON_ENV": "production"}):
            with pytest.raises(RuntimeError, match="CRITICAL INTEGRITY VIOLATION.*PRODUCTION"):
                seed_demo_data(mock_db)

    def test_seed_demo_data_direct_invocation_in_prod(self):
        """Direct invocation of crud.seed_demo_data() with ENVIRONMENT='prod' must raise RuntimeError."""
        mock_db = MagicMock()
        with patch.dict(os.environ, {"ENVIRONMENT": "prod", "CAREON_ENV": ""}):
            with pytest.raises(RuntimeError, match="CRITICAL INTEGRITY VIOLATION.*PRODUCTION"):
                seed_demo_data(mock_db)

    @pytest.mark.anyio
    async def test_lifespan_startup_blocks_in_production_when_seeding_requested(self):
        """FastAPI lifespan startup must crash closed if ENABLE_DEMO_SEEDING is truthy in production."""
        from app.main import lifespan, app
        with patch.dict(os.environ, {"CAREON_ENV": "production", "ENABLE_DEMO_SEEDING": "true", "CAREON_SECRET_KEY": "a" * 64}):
            with pytest.raises(RuntimeError, match="Demo data seeding cannot be enabled in a production environment"):
                async with lifespan(app):
                    pass

    @pytest.mark.anyio
    async def test_lifespan_startup_succeeds_in_production_when_seeding_is_false(self):
        """FastAPI lifespan startup must succeed smoothly in production when ENABLE_DEMO_SEEDING='false'."""
        from app.main import lifespan, app
        with patch.dict(os.environ, {"CAREON_ENV": "production", "ENABLE_DEMO_SEEDING": "false", "CAREON_SECRET_KEY": "a" * 64}):
            async with lifespan(app):
                pass


class TestDesignatedFacilityFailClosed:
    def test_nonexistent_facility_code_returns_none(self, db_session):
        with patch.dict(os.environ, {"CAREON_DESIGNATED_FACILITY_CODE": "NONEXISTENT-CODE-9999"}):
            facility = get_designated_facility(db_session)
            assert facility is None

    def test_empty_facility_code_returns_none(self, db_session):
        with patch.dict(os.environ, {"CAREON_DESIGNATED_FACILITY_CODE": ""}):
            facility = get_designated_facility(db_session)
            assert facility is None

    def test_valid_facility_code_resolves_correctly(self, db_session):
        # Create an organization and hospital facility for testing
        test_org = Organization(name="Test Org Hospital", org_type="hospital", is_active=True)
        db_session.add(test_org)
        db_session.flush()

        test_fac = HospitalFacility(
            organization_id=test_org.id,
            facility_code="TEST-DESIGNATED-01",
            name="Test General Hospital",
            is_active=True,
            operating_status="normal",
            location_name="Test District",
            latitude=12.9716,
            longitude=77.5946
        )
        db_session.add(test_fac)
        db_session.commit()

        try:
            with patch.dict(os.environ, {"CAREON_DESIGNATED_FACILITY_CODE": "TEST-DESIGNATED-01"}):
                facility = get_designated_facility(db_session)
                assert facility is not None
                assert facility.facility_code == "TEST-DESIGNATED-01"
                assert facility.name == "Test General Hospital"
        finally:
            db_session.delete(test_fac)
            db_session.delete(test_org)
            db_session.commit()
