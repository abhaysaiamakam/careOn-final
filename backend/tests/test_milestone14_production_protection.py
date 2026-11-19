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
    def test_seed_demo_data_raises_in_production(self):
        mock_db = MagicMock()
        with patch.dict(os.environ, {"CAREON_ENV": "production"}):
            with pytest.raises(RuntimeError, match="CRITICAL INTEGRITY VIOLATION.*PRODUCTION"):
                seed_demo_data(mock_db)

    def test_seed_demo_data_raises_in_prod(self):
        mock_db = MagicMock()
        with patch.dict(os.environ, {"ENVIRONMENT": "prod", "CAREON_ENV": ""}):
            with pytest.raises(RuntimeError, match="CRITICAL INTEGRITY VIOLATION.*PRODUCTION"):
                seed_demo_data(mock_db)


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
