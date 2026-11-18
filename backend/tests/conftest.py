import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Disable rate limiting in all tests to prevent cross-test Redis state from
# interfering with authentication and emergency reporting endpoints.
os.environ.setdefault("CAREON_TESTING", "true")

from app.database import Base, get_db
from app.main import app
from app import crud

# SQLite in-memory database with StaticPool ensures all connections share the same memory DB
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    """Create fresh tables, seed initial demo data, and yield session."""
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    crud.seed_demo_data(session)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Provide a FastAPI TestClient with the test database session overridden."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
