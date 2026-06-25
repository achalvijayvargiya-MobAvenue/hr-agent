"""
Shared pytest fixtures.

Integration tests use an isolated SQLite file per test function so they are
fast, independent, and leave no artefacts.  Legacy unit tests
(test_matching_service, test_pdf_service) need no DB fixtures at all and are
unaffected by changes here.
"""
import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hr_agent.database import Base, get_db
from hr_agent.main import app


# ── Integration DB fixture ─────────────────────────────────────────────────────

@pytest.fixture()
def test_db(tmp_path):
    """
    Create a fresh SQLite database for a single test function.
    Uses a file in pytest's tmp_path so multiple concurrent workers never collide.
    """
    db_file = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def client(test_db):
    """
    TestClient wired to the isolated test DB.
    Patches init_db so the lifespan never touches the real Postgres instance.
    """
    TestingSessionLocal = sessionmaker(
        bind=test_db, autocommit=False, autoflush=False
    )

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with patch("hr_agent.main.init_db"):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client):
    """Register a regular test user and return their Bearer authorization headers."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@test.local",
            "password": "TestPass123!",
            "full_name": "Test User",
        },
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "user@test.local", "password": "TestPass123!"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture()
def admin_headers(client, test_db):
    """
    Register a user, assign the 'admin' role directly via AuthService
    (bypassing the API auth check), then return their Bearer headers.
    """
    from sqlalchemy.orm import sessionmaker as sm
    from hr_agent.services.auth_service import AuthService

    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@test.local",
            "password": "AdminPass123!",
            "full_name": "Admin User",
        },
    )
    user_id = resp.json()["id"]

    AdminSession = sm(bind=test_db, autocommit=False, autoflush=False)
    db = AdminSession()
    try:
        svc = AuthService(db)
        svc.assign_role(user_id, "admin")
    finally:
        db.close()

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.local", "password": "AdminPass123!"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── Legacy fixtures (kept for backwards-compatibility) ─────────────────────────

@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db_session(db_engine):
    """Yield a clean session for each test, rolled back after the test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()
