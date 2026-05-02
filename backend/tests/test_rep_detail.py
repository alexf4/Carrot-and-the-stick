"""Tests for GET /reps/browse and GET /reps/{bioguide_id} endpoints."""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.base import Base
from app.models.bills import Bill
from app.models.enums import Chamber
from app.models.pledges import Pledge
from app.models.representatives import Representative
from app.models.votes import Vote, VoteOutcomeRow

# ---------------------------------------------------------------------------
# DB fixture — SQLite in-memory
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


@pytest.fixture()
def client(sqlite_db):
    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: sqlite_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _rep(session: Session, bioguide_id: str, **kwargs) -> Representative:
    defaults = {
        "id": uuid.uuid4(),
        "name": f"Rep {bioguide_id}",
        "party": "D",
        "chamber": Chamber.house,
        "state": "VA",
        "district": 1,
        "is_active": True,
    }
    defaults.update(kwargs)
    r = Representative(bioguide_id=bioguide_id, **defaults)
    session.add(r)
    session.commit()
    return r


def _bill(session: Session) -> Bill:
    b = Bill(
        id=uuid.uuid4(),
        congress_bill_id=f"hr{uuid.uuid4().hex[:6]}-119",
        title="A Test Bill",
    )
    session.add(b)
    session.commit()
    return b


def _vote(session: Session, bill: Bill, resolved: bool = True) -> Vote:
    now = datetime(2025, 3, 1, 12, 0, tzinfo=timezone.utc)
    v = Vote(
        id=uuid.uuid4(),
        bill_id=bill.id,
        scheduled_at=now,
        resolved_at=now if resolved else None,
        congress_vote_id=f"119/house/1/{uuid.uuid4().hex[:4]}" if resolved else None,
    )
    session.add(v)
    session.commit()
    return v


def _outcome(session: Session, vote: Vote, rep: Representative, outcome: str = "yes") -> VoteOutcomeRow:
    row = VoteOutcomeRow(
        id=uuid.uuid4(),
        vote_id=vote.id,
        representative_id=rep.id,
        outcome=outcome,
    )
    session.add(row)
    session.commit()
    return row


def _pledge(
    session: Session,
    vote: Vote,
    rep: Representative,
    direction: str,
    amount_cents: int,
    status: str = "held",
) -> Pledge:
    from app.models.users import User

    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4().hex[:8]}@test.com")
    session.add(user)
    session.flush()
    p = Pledge(
        id=uuid.uuid4(),
        user_id=user.id,
        vote_id=vote.id,
        representative_id=rep.id,
        direction=direction,
        amount_cents=amount_cents,
        status=status,
    )
    session.add(p)
    session.commit()
    return p


# ---------------------------------------------------------------------------
# GET /reps/browse tests
# ---------------------------------------------------------------------------


def test_browse_returns_all_active_reps(client, sqlite_db):
    _rep(sqlite_db, "H000001", state="VA", chamber=Chamber.house, party="D")
    _rep(sqlite_db, "S000001", state="VA", chamber=Chamber.senate, party="R")
    response = client.get("/reps/browse")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["reps"]) == 2


def test_browse_excludes_inactive_reps(client, sqlite_db):
    _rep(sqlite_db, "H000001", is_active=True)
    _rep(sqlite_db, "H000002", is_active=False)
    response = client.get("/reps/browse")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["reps"][0]["bioguide_id"] == "H000001"


def test_browse_filters_by_state(client, sqlite_db):
    _rep(sqlite_db, "H000001", state="VA")
    _rep(sqlite_db, "H000002", state="CA")
    response = client.get("/reps/browse?state=VA")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["reps"][0]["state"] == "VA"


def test_browse_filters_by_chamber(client, sqlite_db):
    _rep(sqlite_db, "H000001", chamber=Chamber.house)
    _rep(sqlite_db, "S000001", chamber=Chamber.senate)
    response = client.get("/reps/browse?chamber=senate")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["reps"][0]["chamber"] == "senate"


def test_browse_filters_by_party(client, sqlite_db):
    _rep(sqlite_db, "H000001", party="D")
    _rep(sqlite_db, "H000002", party="R")
    response = client.get("/reps/browse?party=R")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["reps"][0]["party"] == "R"


def test_browse_total_matches_reps_length(client, sqlite_db):
    _rep(sqlite_db, "H000001")
    _rep(sqlite_db, "H000002")
    _rep(sqlite_db, "H000003")
    response = client.get("/reps/browse")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == len(data["reps"])


# ---------------------------------------------------------------------------
# GET /reps/{bioguide_id} tests
# ---------------------------------------------------------------------------


def test_rep_detail_404_for_unknown_bioguide(client):
    response = client.get("/reps/UNKNOWN999")
    assert response.status_code == 404


def test_rep_detail_returns_bio_fields(client, sqlite_db):
    _rep(sqlite_db, "H000001", name="Jane Smith", party="D", state="VA", district=5, chamber=Chamber.house)
    response = client.get("/reps/H000001")
    assert response.status_code == 200
    data = response.json()
    assert data["bioguide_id"] == "H000001"
    assert data["name"] == "Jane Smith"
    assert data["party"] == "D"
    assert data["state"] == "VA"
    assert data["district"] == 5
    assert data["chamber"] == "house"


def test_rep_detail_empty_vote_history_when_no_outcomes(client, sqlite_db):
    _rep(sqlite_db, "H000001")
    response = client.get("/reps/H000001")
    assert response.status_code == 200
    assert response.json()["vote_history"] == []


def test_rep_detail_pledge_aggregate_zeros_with_no_pledges(client, sqlite_db):
    _rep(sqlite_db, "H000001")
    response = client.get("/reps/H000001")
    assert response.status_code == 200
    agg = response.json()["pledge_aggregate"]
    assert agg["total_carrot_cents"] == 0
    assert agg["total_stick_cents"] == 0


def test_rep_detail_vote_history_shows_rep_outcome(client, sqlite_db):
    rep = _rep(sqlite_db, "H000001")
    bill = _bill(sqlite_db)
    vote = _vote(sqlite_db, bill)
    _outcome(sqlite_db, vote, rep, outcome="yes")
    response = client.get("/reps/H000001")
    assert response.status_code == 200
    history = response.json()["vote_history"]
    assert len(history) == 1
    assert history[0]["rep_outcome"] == "yes"
    assert history[0]["bill_title"] == "A Test Bill"


def test_rep_detail_vote_history_per_vote_pledge_pools(client, sqlite_db):
    rep = _rep(sqlite_db, "H000001")
    bill = _bill(sqlite_db)
    vote = _vote(sqlite_db, bill)
    _outcome(sqlite_db, vote, rep)
    _pledge(sqlite_db, vote, rep, direction="yes", amount_cents=500)
    _pledge(sqlite_db, vote, rep, direction="yes", amount_cents=300)
    _pledge(sqlite_db, vote, rep, direction="no", amount_cents=200)
    response = client.get("/reps/H000001")
    assert response.status_code == 200
    pledges = response.json()["vote_history"][0]["pledges"]
    assert pledges["yes_pool_cents"] == 800
    assert pledges["no_pool_cents"] == 200


def test_rep_detail_pledge_aggregate_counts_only_disbursed(client, sqlite_db):
    rep = _rep(sqlite_db, "H000001")
    bill = _bill(sqlite_db)
    vote = _vote(sqlite_db, bill)
    _outcome(sqlite_db, vote, rep)
    _pledge(sqlite_db, vote, rep, direction="yes", amount_cents=1000, status="disbursed_carrot")
    _pledge(sqlite_db, vote, rep, direction="no", amount_cents=500, status="disbursed_stick")
    _pledge(sqlite_db, vote, rep, direction="yes", amount_cents=9999, status="held")
    response = client.get("/reps/H000001")
    assert response.status_code == 200
    agg = response.json()["pledge_aggregate"]
    assert agg["total_carrot_cents"] == 1000
    assert agg["total_stick_cents"] == 500


def test_rep_detail_vote_history_zero_pools_when_no_pledges(client, sqlite_db):
    rep = _rep(sqlite_db, "H000001")
    bill = _bill(sqlite_db)
    vote = _vote(sqlite_db, bill)
    _outcome(sqlite_db, vote, rep)
    response = client.get("/reps/H000001")
    assert response.status_code == 200
    pledges = response.json()["vote_history"][0]["pledges"]
    assert pledges["yes_pool_cents"] == 0
    assert pledges["no_pool_cents"] == 0
