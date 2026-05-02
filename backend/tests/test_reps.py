"""Tests for GET /reps?zip= endpoint."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.base import Base
from app.models.enums import Chamber
from app.models.representatives import Representative

# ---------------------------------------------------------------------------
# DB fixture — SQLite in-memory, no live Supabase connection
# ---------------------------------------------------------------------------


@pytest.fixture()
def sqlite_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)


def _va_reps(session: Session) -> None:
    session.add_all([
        Representative(
            id=uuid.uuid4(),
            bioguide_id="H000001",
            name="House Rep VA-8",
            party="D",
            chamber=Chamber.house,
            state="VA",
            district=8,
            is_active=True,
        ),
        Representative(
            id=uuid.uuid4(),
            bioguide_id="S000001",
            name="Senator VA One",
            party="D",
            chamber=Chamber.senate,
            state="VA",
            district=None,
            is_active=True,
        ),
        Representative(
            id=uuid.uuid4(),
            bioguide_id="S000002",
            name="Senator VA Two",
            party="R",
            chamber=Chamber.senate,
            state="VA",
            district=None,
            is_active=True,
        ),
    ])
    session.commit()


def _senators_only(session: Session) -> None:
    session.add_all([
        Representative(
            id=uuid.uuid4(),
            bioguide_id="S000003",
            name="Senator OR One",
            party="D",
            chamber=Chamber.senate,
            state="OR",
            district=None,
            is_active=True,
        ),
        Representative(
            id=uuid.uuid4(),
            bioguide_id="S000004",
            name="Senator OR Two",
            party="D",
            chamber=Chamber.senate,
            state="OR",
            district=None,
            is_active=True,
        ),
    ])
    session.commit()


# ---------------------------------------------------------------------------
# Fake zip lookup
# ---------------------------------------------------------------------------


class _FakeZipLookup:
    def __init__(self, result):
        self._result = result

    def lookup(self, zip_code: str):
        if self._result is None:
            from app.services.zip_lookup import ZipNotFoundError
            raise ZipNotFoundError(zip_code)
        return self._result


# ---------------------------------------------------------------------------
# Client fixtures — override dependencies via app.dependency_overrides
# ---------------------------------------------------------------------------


@pytest.fixture()
def client_va(sqlite_db):
    from app.database import get_db
    from app.services.zip_lookup import ZipInfo, get_zip_lookup

    _va_reps(sqlite_db)
    app.dependency_overrides[get_db] = lambda: sqlite_db
    app.dependency_overrides[get_zip_lookup] = lambda: _FakeZipLookup(ZipInfo(state="VA", house_district=8))
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def client_unknown_zip(sqlite_db):
    from app.database import get_db
    from app.services.zip_lookup import get_zip_lookup

    app.dependency_overrides[get_db] = lambda: sqlite_db
    app.dependency_overrides[get_zip_lookup] = lambda: _FakeZipLookup(None)
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def client_no_house(sqlite_db):
    from app.database import get_db
    from app.services.zip_lookup import ZipInfo, get_zip_lookup

    _senators_only(sqlite_db)
    app.dependency_overrides[get_db] = lambda: sqlite_db
    app.dependency_overrides[get_zip_lookup] = lambda: _FakeZipLookup(ZipInfo(state="OR", house_district=1))
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def client(sqlite_db):
    """Bare client with SQLite DB — for tests that exercise validation before any DB/service call."""
    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: sqlite_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_get_reps_missing_zip_param(client):
    response = client.get("/reps")
    assert response.status_code == 422


def test_get_reps_invalid_zip_format(client):
    response = client.get("/reps?zip=notazip")
    assert response.status_code == 422


def test_get_reps_too_short_zip(client):
    response = client.get("/reps?zip=1234")
    assert response.status_code == 422


def test_get_reps_unknown_zip_returns_404(client_unknown_zip):
    response = client_unknown_zip.get("/reps?zip=99999")
    assert response.status_code == 404
    assert "99999" in response.json()["detail"]


def test_get_reps_returns_house_and_two_senators(client_va):
    response = client_va.get("/reps?zip=22201")
    assert response.status_code == 200
    data = response.json()
    assert data["house"]["state"] == "VA"
    assert data["house"]["district"] == 8
    assert data["house"]["chamber"] == "house"
    assert len(data["senators"]) == 2
    assert all(s["chamber"] == "senate" for s in data["senators"])
    assert all(s["state"] == "VA" for s in data["senators"])


def test_get_reps_no_house_rep_returns_null_house(client_no_house):
    response = client_no_house.get("/reps?zip=97201")
    assert response.status_code == 200
    data = response.json()
    assert data["house"] is None
    assert len(data["senators"]) == 2
