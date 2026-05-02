"""Tests for congress sync engine — migration constraints, upsert logic, events."""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.bills import Bill
from app.models.enums import Chamber
from app.models.representatives import Representative
from app.models.votes import Vote, VoteOutcomeRow


# ---------------------------------------------------------------------------
# Shared SQLite fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bill(db: Session, congress_bill_id: str = "hr1234-119") -> Bill:
    b = Bill(congress_bill_id=congress_bill_id, title="A test bill")
    db.add(b)
    db.commit()
    return b


def _vote(db: Session, bill: Bill, congress_vote_id: str | None = "119/house/1/142") -> Vote:
    v = Vote(
        bill_id=bill.id,
        scheduled_at=datetime(2025, 3, 15, 14, 30, tzinfo=timezone.utc),
        congress_vote_id=congress_vote_id,
    )
    db.add(v)
    db.commit()
    return v


def _rep(db: Session, bioguide_id: str, chamber: Chamber = Chamber.house) -> Representative:
    r = Representative(
        bioguide_id=bioguide_id, name=f"Rep {bioguide_id}", party="D",
        chamber=chamber, state="VA", district=1, is_active=True,
    )
    db.add(r)
    db.commit()
    return r


# ---------------------------------------------------------------------------
# Phase 1 — Model unique constraints
# ---------------------------------------------------------------------------

def test_vote_congress_vote_id_must_be_unique(db: Session) -> None:
    """Two votes with the same non-null congress_vote_id must raise IntegrityError."""
    bill = _bill(db)
    _vote(db, bill, congress_vote_id="119/house/1/142")
    with pytest.raises(IntegrityError):
        _vote(db, bill, congress_vote_id="119/house/1/142")


def test_vote_null_congress_vote_id_does_not_conflict(db: Session) -> None:
    """Multiple votes with NULL congress_vote_id should not conflict."""
    bill = _bill(db)
    _vote(db, bill, congress_vote_id=None)
    _vote(db, bill, congress_vote_id=None)  # should not raise
    assert db.query(Vote).count() == 2


def test_vote_outcome_vote_rep_must_be_unique(db: Session) -> None:
    """Same (vote_id, representative_id) pair must raise IntegrityError."""
    bill = _bill(db)
    vote = _vote(db, bill)
    rep = _rep(db, "A000001")
    db.add(VoteOutcomeRow(vote_id=vote.id, representative_id=rep.id, outcome="yes"))
    db.commit()
    with pytest.raises(IntegrityError):
        db.add(VoteOutcomeRow(vote_id=vote.id, representative_id=rep.id, outcome="no"))
        db.commit()


# ---------------------------------------------------------------------------
# Phase 3 — Sync engine (FakeCongressClient + SQLite)
# ---------------------------------------------------------------------------

# Imported here so the test file fails fast if the module doesn't exist yet
from app.services.congress_client import RecentVote, VoteDetail, VotePosition  # noqa: E402
from app.services.congress_sync import sync_chamber  # noqa: E402


class FakeCongressClient:
    """Returns deterministic fixture data; never makes HTTP calls."""

    RECENT_VOTES_HOUSE: list[RecentVote] = [
        RecentVote(
            congress_vote_id="119/house/1/142",
            congress=119, chamber="house", session=1, roll_call=142,
            date="2025-03-15", time="14:30:00",
            congress_bill_id="hr1234-119",
            bill_title="A bill to do something",
            result="Passed",
        ),
        # procedural — no bill, should be skipped
        RecentVote(
            congress_vote_id="119/house/1/143",
            congress=119, chamber="house", session=1, roll_call=143,
            date="2025-03-15", time="15:00:00",
            congress_bill_id=None,
            bill_title=None,
            result="Agreed to",
        ),
    ]

    VOTE_DETAIL: VoteDetail = VoteDetail(
        congress_vote_id="119/house/1/142",
        positions=[
            VotePosition(member_id="A000001", vote_position="Yes"),
            VotePosition(member_id="B000002", vote_position="No"),
            VotePosition(member_id="C000003", vote_position="Not Voting"),
            VotePosition(member_id="D000004", vote_position="Present"),
        ],
    )

    def get_recent_votes(self, chamber: str) -> list[RecentVote]:
        return self.RECENT_VOTES_HOUSE

    def get_vote_detail(self, congress: int, chamber: str, session: int, roll_call: int) -> VoteDetail:
        return self.VOTE_DETAIL


@pytest.fixture()
def fake_client() -> FakeCongressClient:
    return FakeCongressClient()


# --- Bill upsert ---

def test_sync_chamber_inserts_bill(db: Session, fake_client: FakeCongressClient) -> None:
    result = sync_chamber(db, fake_client, "house")
    assert db.query(Bill).count() == 1
    assert db.query(Bill).first().congress_bill_id == "hr1234-119"
    assert result.bills_upserted == 1


def test_sync_chamber_bill_upsert_is_idempotent(db: Session, fake_client: FakeCongressClient) -> None:
    sync_chamber(db, fake_client, "house")
    sync_chamber(db, fake_client, "house")
    assert db.query(Bill).count() == 1


def test_sync_chamber_skips_procedural_vote(db: Session, fake_client: FakeCongressClient) -> None:
    """The second RecentVote has congress_bill_id=None and must be skipped."""
    result = sync_chamber(db, fake_client, "house")
    assert result.votes_upserted == 1  # only the vote with a bill
    assert db.query(Vote).count() == 1


# --- Vote upsert ---

def test_sync_chamber_inserts_vote(db: Session, fake_client: FakeCongressClient) -> None:
    sync_chamber(db, fake_client, "house")
    vote = db.query(Vote).first()
    assert vote is not None
    assert vote.congress_vote_id == "119/house/1/142"
    assert vote.resolved_at is not None


def test_sync_chamber_vote_upsert_is_idempotent(db: Session, fake_client: FakeCongressClient) -> None:
    sync_chamber(db, fake_client, "house")
    sync_chamber(db, fake_client, "house")
    assert db.query(Vote).count() == 1


# --- Vote outcomes ---

def test_sync_chamber_inserts_outcomes_for_known_reps(db: Session, fake_client: FakeCongressClient) -> None:
    """3 of 4 reps seeded — D000004 absent from DB, should be skipped."""
    _rep(db, "A000001")
    _rep(db, "B000002")
    _rep(db, "C000003")
    result = sync_chamber(db, fake_client, "house")
    assert db.query(VoteOutcomeRow).count() == 3
    assert result.outcomes_upserted == 3


def test_sync_chamber_not_voting_maps_to_absent(db: Session, fake_client: FakeCongressClient) -> None:
    _rep(db, "A000001")
    _rep(db, "B000002")
    _rep(db, "C000003")
    sync_chamber(db, fake_client, "house")
    c_rep = db.query(Representative).filter_by(bioguide_id="C000003").one()
    outcome = db.query(VoteOutcomeRow).filter_by(representative_id=c_rep.id).one()
    assert outcome.outcome == "absent"


def test_sync_chamber_outcomes_idempotent(db: Session, fake_client: FakeCongressClient) -> None:
    _rep(db, "A000001")
    _rep(db, "B000002")
    _rep(db, "C000003")
    sync_chamber(db, fake_client, "house")
    sync_chamber(db, fake_client, "house")
    assert db.query(VoteOutcomeRow).count() == 3


# --- Events ---

def test_sync_chamber_fires_event_for_resolved_vote(db: Session, fake_client: FakeCongressClient) -> None:
    fired: list[uuid.UUID] = []
    sync_chamber(db, fake_client, "house", event_handlers=[fired.append])
    assert len(fired) == 1
    assert fired[0] == db.query(Vote).first().id


def test_sync_chamber_fires_event_only_once(db: Session, fake_client: FakeCongressClient) -> None:
    """Second sync: vote already resolved, no new event."""
    fired: list[uuid.UUID] = []
    sync_chamber(db, fake_client, "house", event_handlers=[fired.append])
    sync_chamber(db, fake_client, "house", event_handlers=[fired.append])
    assert len(fired) == 1
