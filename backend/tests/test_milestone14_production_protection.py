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
from app.database import normalize_database_url, get_engine_args
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


class TestDatabaseSupabaseCompatibility:
    def test_url_normalization_variations(self):
        assert normalize_database_url("postgres://user:pass@host/db") == "postgresql+psycopg://user:pass@host/db"
        assert normalize_database_url("postgresql://user:pass@host/db") == "postgresql+psycopg://user:pass@host/db"
        assert normalize_database_url("postgresql+psycopg2://user:pass@host/db") == "postgresql+psycopg://user:pass@host/db"
        assert normalize_database_url("postgresql+psycopg://user:pass@host/db") == "postgresql+psycopg://user:pass@host/db"
        assert normalize_database_url("sqlite:///data.db") == "sqlite:///data.db"

    def test_search_path_connect_args(self):
        args = get_engine_args("postgresql+psycopg://user:pass@host/db")
        assert "connect_args" in args
        assert args["connect_args"]["options"] == "-c search_path=public,extensions"

    def test_pgbouncer_transaction_pooler_disables_prepared_statements(self):
        url_6543 = "postgresql+psycopg://postgres.ref:pass@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
        args = get_engine_args(url_6543)
        assert args["connect_args"]["prepare_threshold"] is None

    def test_direct_connection_keeps_default_prepare_threshold(self):
        url_5432 = "postgresql+psycopg://postgres:pass@db.ref.supabase.co:5432/postgres"
        args = get_engine_args(url_5432)
        assert "prepare_threshold" not in args["connect_args"]

    def test_sslmode_passthrough(self):
        with patch.dict(os.environ, {"DB_SSLMODE": "require"}):
            args = get_engine_args("postgresql+psycopg://user:pass@host/db")
            assert args["connect_args"]["sslmode"] == "require"

    def test_alembic_config_interpolation_safety_with_special_characters(self):
        """
        Verify that URL-encoded passwords with %, @, #, $, : do not crash
        Alembic's ConfigParser when escaped as %%.
        Uses purely fake/mock credentials.
        """
        from alembic.config import Config
        cfg = Config("backend/alembic.ini")
        fake_encoded_url = "postgresql+psycopg://mock_user:p%40ss%23word%25123%24@mock-host:5432/mock_db"
        # Escaping % -> %% preserves configparser integrity
        escaped_url = fake_encoded_url.replace("%", "%%")
        cfg.set_main_option("sqlalchemy.url", escaped_url)
        retrieved_url = cfg.get_main_option("sqlalchemy.url")
        assert retrieved_url == fake_encoded_url


class TestOutboxRelayConcurrencyAndResilience:
    def test_concurrent_workers_skip_locked(self):
        """
        Integration test verifying PostgreSQL row locking via SKIP LOCKED:
        Two concurrent worker sessions on careon_test must not claim the same outbox events.
        """
        import uuid
        import os
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.database import normalize_database_url, get_engine_args
        from app.models import OutboxEvent, utc_now

        pg_url = normalize_database_url(os.getenv("DATABASE_URL", "postgresql+psycopg:///careon_test"))
        if not pg_url.startswith("postgresql"):
            pytest.skip("Test requires PostgreSQL (careon_test)")

        engine = create_engine(pg_url, **get_engine_args(pg_url))
        SessionFactory = sessionmaker(bind=engine)

        setup_db = SessionFactory()
        worker1_session = SessionFactory()
        worker2_session = SessionFactory()

        event1_id = str(uuid.uuid4())
        event2_id = str(uuid.uuid4())

        try:
            # 1. Seed two test outbox events in careon_test
            ev1 = OutboxEvent(
                event_id=event1_id,
                event_type="test.concurrent.1",
                channel="careon:events:test",
                payload_json="{}",
                is_published=False,
                retry_count=0,
                occurred_at=utc_now(),
            )
            ev2 = OutboxEvent(
                event_id=event2_id,
                event_type="test.concurrent.2",
                channel="careon:events:test",
                payload_json="{}",
                is_published=False,
                retry_count=0,
                occurred_at=utc_now(),
            )
            setup_db.add_all([ev1, ev2])
            setup_db.commit()

            # 2. Worker 1 opens transaction and locks event 1 with SKIP LOCKED
            w1_events = (
                worker1_session.query(OutboxEvent)
                .filter(OutboxEvent.event_id.in_([event1_id, event2_id]), OutboxEvent.is_published == False)
                .order_by(OutboxEvent.created_at.asc())
                .with_for_update(skip_locked=True)
                .limit(1)
                .all()
            )
            assert len(w1_events) == 1
            locked_event_id = w1_events[0].event_id

            # 3. Worker 2 queries concurrently with SKIP LOCKED
            w2_events = (
                worker2_session.query(OutboxEvent)
                .filter(OutboxEvent.event_id.in_([event1_id, event2_id]), OutboxEvent.is_published == False)
                .order_by(OutboxEvent.created_at.asc())
                .with_for_update(skip_locked=True)
                .limit(2)
                .all()
            )

            # Worker 2 must NOT claim the event locked by Worker 1
            w2_ids = [e.event_id for e in w2_events]
            assert locked_event_id not in w2_ids
            assert len(w2_events) == 1
            assert w2_ids[0] != locked_event_id

            # 4. Simulate Worker 1 crash after Redis publish (rollback before DB commit)
            # This demonstrates at-least-once delivery with stable UUID:
            worker1_session.rollback()

            # Now Worker 1's lock is released, and the event remains is_published=False
            setup_db.expire_all()
            rechecked = setup_db.query(OutboxEvent).filter(OutboxEvent.event_id == locked_event_id).first()
            assert rechecked is not None
            assert rechecked.is_published is False
            assert rechecked.event_id == locked_event_id

            worker2_session.commit()
        finally:
            setup_db.query(OutboxEvent).filter(OutboxEvent.event_id.in_([event1_id, event2_id])).delete()
            setup_db.commit()
            setup_db.close()
            worker1_session.close()
            worker2_session.close()
            engine.dispose()

    def test_relay_redis_failure_increments_retry_count(self, db_session):
        """
        Verify that a Redis publish failure records retry_count and last_error
        without losing the event record or marking it published.
        """
        import uuid
        from app.models import OutboxEvent, utc_now
        from app.realtime.event_publisher import relay_pending_outbox_events

        event_id = str(uuid.uuid4())
        test_event = OutboxEvent(
            event_id=event_id,
            event_type="test.retry.failure",
            channel="careon:events:test",
            payload_json="{}",
            is_published=False,
            retry_count=0,
            occurred_at=utc_now(),
        )
        db_session.add(test_event)
        db_session.commit()

        mock_redis = MagicMock()
        mock_redis.publish.side_effect = RuntimeError("Simulated Redis Connection Timeout")

        try:
            with patch("app.realtime.event_publisher.get_redis_client", return_value=mock_redis):
                relayed = relay_pending_outbox_events(db_session, limit=10)
                # Success count should be 0 because publish failed
                assert relayed == 0

            db_session.expire_all()
            updated_event = db_session.query(OutboxEvent).filter(OutboxEvent.event_id == event_id).first()
            assert updated_event is not None
            assert updated_event.is_published is False
            assert updated_event.retry_count == 1
            assert "Simulated Redis Connection Timeout" in (updated_event.last_error or "")
        finally:
            db_session.query(OutboxEvent).filter(OutboxEvent.event_id == event_id).delete()
            db_session.commit()
