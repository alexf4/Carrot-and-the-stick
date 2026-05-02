"""Congress sync engine — upserts bills, votes, and vote outcomes from ProPublica."""
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.bills import Bill
from app.models.representatives import Representative
from app.models.votes import Vote, VoteOutcomeRow
from app.services.congress_client import CongressClient, RecentVote

logger = logging.getLogger(__name__)

_POSITION_MAP: dict[str, str] = {
    "Yes": "yes",
    "No": "no",
    "Not Voting": "absent",
    "Present": "present",
}


@dataclass
class SyncResult:
    bills_upserted: int
    votes_upserted: int
    outcomes_upserted: int


def sync_chamber(
    db: Session,
    client: CongressClient,
    chamber: str,
    event_handlers: list[Callable[[uuid.UUID], None]] | None = None,
) -> SyncResult:
    handlers = event_handlers or []
    result = SyncResult(bills_upserted=0, votes_upserted=0, outcomes_upserted=0)

    recent_votes = client.get_recent_votes(chamber)

    for rv in recent_votes:
        if rv.congress_bill_id is None:
            continue

        bill = _upsert_bill(db, rv)
        result.bills_upserted += 1

        was_resolved, vote = _upsert_vote(db, rv, bill)
        result.votes_upserted += 1

        if was_resolved:
            for handler in handlers:
                handler(vote.id)

        if vote.resolved_at is not None:
            detail = client.get_vote_detail(rv.congress, rv.chamber, rv.session, rv.roll_call)
            for pos in detail.positions:
                if _upsert_outcome(db, vote, pos):
                    result.outcomes_upserted += 1

    return result


def _upsert_bill(db: Session, rv: RecentVote) -> Bill:
    bill = db.query(Bill).filter_by(congress_bill_id=rv.congress_bill_id).first()
    if bill is None:
        bill = Bill(
            congress_bill_id=rv.congress_bill_id,
            title=rv.bill_title or "",
        )
        db.add(bill)
        db.commit()
    return bill


def _upsert_vote(db: Session, rv: RecentVote, bill: Bill) -> tuple[bool, Vote]:
    """Returns (newly_resolved, vote). newly_resolved=True when resolved_at just became set."""
    resolved_at = _parse_datetime(rv.date, rv.time) if rv.result else None

    vote = db.query(Vote).filter_by(congress_vote_id=rv.congress_vote_id).first()
    if vote is None:
        vote = Vote(
            bill_id=bill.id,
            scheduled_at=resolved_at or _parse_datetime(rv.date, rv.time),
            resolved_at=resolved_at,
            congress_vote_id=rv.congress_vote_id,
        )
        db.add(vote)
        db.commit()
        return resolved_at is not None, vote

    # Vote already exists — check if resolved_at is transitioning None → set
    newly_resolved = vote.resolved_at is None and resolved_at is not None
    if newly_resolved:
        vote.resolved_at = resolved_at
        db.commit()
    return newly_resolved, vote


def _upsert_outcome(db: Session, vote: Vote, pos: object) -> bool:
    """Insert outcome if not present. Returns True if a new row was created."""
    from app.services.congress_client import VotePosition

    p: VotePosition = pos  # type: ignore[assignment]
    rep = db.query(Representative).filter_by(bioguide_id=p.member_id).first()
    if rep is None:
        return False

    outcome_val = _POSITION_MAP.get(p.vote_position)
    if outcome_val is None:
        logger.warning("Unknown vote_position %r for member %s — skipping", p.vote_position, p.member_id)
        return False

    existing = db.query(VoteOutcomeRow).filter_by(vote_id=vote.id, representative_id=rep.id).first()
    if existing is not None:
        return False

    db.add(VoteOutcomeRow(vote_id=vote.id, representative_id=rep.id, outcome=outcome_val))
    db.commit()
    return True


def _parse_datetime(date: str, time_str: str) -> datetime:
    return datetime.strptime(f"{date} {time_str}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
