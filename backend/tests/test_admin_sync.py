"""Tests for POST /admin/sync endpoint."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.base import Base
from app.services.congress_client import RecentVote, VoteDetail


@pytest.fixture()
def sqlite_db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)


class FakeCongressClient:
    def get_recent_votes(self, chamber: str) -> list[RecentVote]:
        return [
            RecentVote(
                congress_vote_id=f"119/{chamber}/1/1",
                congress=119, chamber=chamber, session=1, roll_call=1,
                date="2025-03-15", time="14:30:00",
                congress_bill_id=f"hr1-119-{chamber}",
                bill_title="Test bill",
                result="Passed",
            )
        ]

    def get_vote_detail(self, congress: int, chamber: str, session: int, roll_call: int) -> VoteDetail:
        return VoteDetail(
            congress_vote_id=f"119/{chamber}/1/1",
            positions=[],
        )


@pytest.fixture()
def client(sqlite_db: Session, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from app.database import get_db
    from app.routers.admin import get_congress_client_dep

    monkeypatch.setenv("ADMIN_API_KEY", "test-secret")
    app.dependency_overrides[get_db] = lambda: sqlite_db
    app.dependency_overrides[get_congress_client_dep] = lambda: FakeCongressClient()
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def test_missing_admin_key_returns_403(client: TestClient) -> None:
    response = client.post("/admin/sync")
    assert response.status_code == 403


def test_wrong_admin_key_returns_403(client: TestClient) -> None:
    response = client.post("/admin/sync", headers={"X-Admin-Key": "wrong-key"})
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_correct_admin_key_returns_200(client: TestClient) -> None:
    response = client.post("/admin/sync", headers={"X-Admin-Key": "test-secret"})
    assert response.status_code == 200


def test_sync_response_schema(client: TestClient) -> None:
    response = client.post("/admin/sync", headers={"X-Admin-Key": "test-secret"})
    body = response.json()
    assert "house" in body
    assert "senate" in body
    for chamber_key in ("house", "senate"):
        assert "bills_upserted" in body[chamber_key]
        assert "votes_upserted" in body[chamber_key]
        assert "outcomes_upserted" in body[chamber_key]


def test_sync_upserts_bills_and_votes(client: TestClient) -> None:
    response = client.post("/admin/sync", headers={"X-Admin-Key": "test-secret"})
    body = response.json()
    assert body["house"]["bills_upserted"] == 1
    assert body["house"]["votes_upserted"] == 1
    assert body["senate"]["bills_upserted"] == 1
    assert body["senate"]["votes_upserted"] == 1
