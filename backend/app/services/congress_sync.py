"""Congress sync engine — upserts bills, votes, and vote outcomes from ProPublica.

This module is the core of the Congress Sync feature (issue #6). It contains
the business logic for taking data returned by the ProPublica API client and
persisting it to the database in an idempotent way.

Responsibilities
----------------
- Fetch recent votes for a chamber via the ``CongressClient`` protocol.
- For each vote that has an associated bill, upsert the ``Bill`` row.
- Upsert the ``Vote`` row, keyed on ``congress_vote_id``.
- When a vote transitions from unresolved to resolved (``resolved_at``
  transitions from ``None`` to a timestamp), fire registered event callbacks
  and fetch + upsert per-representative ``VoteOutcomeRow`` records.
- Report counts of rows created/updated via ``SyncResult``.

Idempotency guarantees
----------------------
This module is designed to be called repeatedly without producing duplicate
data. The guarantees are enforced at two levels:

1. **Application level** — each upsert helper queries for an existing record
   before inserting. If the record already exists the insert is skipped.
2. **Database level** — migration 0002 adds:
   - A partial unique index on ``votes.congress_vote_id`` (WHERE NOT NULL)
   - A unique constraint on ``vote_outcomes(vote_id, representative_id)``
   These constraints act as a safety net if application-level logic is ever
   bypassed (e.g. a concurrent sync triggered by two simultaneous requests to
   POST /admin/sync).

Event system
------------
``sync_chamber`` accepts an optional ``event_handlers`` list. Each handler is
a callable that takes a ``uuid.UUID`` (the internal ``Vote.id``) and returns
nothing. Handlers are called synchronously, inline, immediately after the
database commit that sets ``resolved_at``. If a handler raises, the exception
propagates and the sync for that vote is aborted — so handlers should be
robust.

The event fires **exactly once per vote** — only when ``resolved_at``
transitions from ``None`` to a non-None value during a sync run. Subsequent
runs that see an already-resolved vote do not re-fire the event.

Vote outcome mapping
--------------------
ProPublica ``vote_position`` strings are mapped to our ``VoteOutcome`` enum:

    "Yes"        → "yes"
    "No"         → "no"
    "Not Voting" → "absent"
    "Present"    → "present"

The ubiquitous language defines both ``"Not Voting"`` and ``"Present"`` as
non-compliant vote outcomes (Sticks). Only ``"Yes"`` or ``"No"`` that match
the constituent's Direction produce a Carrot.

Skipped records
---------------
- Votes with no associated bill (``congress_bill_id is None``) are skipped
  entirely. These are procedural votes (motions to table, rule adoptions)
  that can never be the subject of a Pledge.
- Vote outcomes for representatives not found in our ``representatives``
  table are silently skipped. This handles the window between a rep being
  elected and the seed script being updated.
"""

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

# Maps ProPublica's raw vote_position strings to our VoteOutcome enum values.
# "Not Voting" becomes "absent" per the domain model — a rep who does not vote
# is non-compliant regardless of reason, and triggers a Stick outcome.
_POSITION_MAP: dict[str, str] = {
    "Yes": "yes",
    "No": "no",
    "Not Voting": "absent",
    "Present": "present",
}


@dataclass
class SyncResult:
    """Summary of rows created or updated during a single sync run.

    Returned by ``sync_chamber`` so the caller (scheduler job or admin
    endpoint) can log or expose meaningful counts rather than a generic
    success/failure boolean.

    All counts represent the number of rows **inserted or updated** during
    this particular call. Rows that already existed and were not changed are
    not included in the count.

    Attributes
    ----------
    bills_upserted:
        Number of ``Bill`` rows inserted or title-updated during this run.
    votes_upserted:
        Number of ``Vote`` rows inserted or resolved during this run.
    outcomes_upserted:
        Number of ``VoteOutcomeRow`` rows inserted during this run. Only
        counts new insertions — existing outcomes are never overwritten.
    """

    bills_upserted: int
    votes_upserted: int
    outcomes_upserted: int


def sync_chamber(
    db: Session,
    client: CongressClient,
    chamber: str,
    event_handlers: list[Callable[[uuid.UUID], None]] | None = None,
) -> SyncResult:
    """Sync all recent votes for one chamber into the database.

    This is the top-level entry point for the sync engine. It fetches recent
    votes from the API, then for each vote with an associated bill:

    1. Upserts the ``Bill`` record.
    2. Upserts the ``Vote`` record (including setting ``resolved_at`` if the
       vote has a non-empty result).
    3. If the vote just became resolved in this run, fires each event handler
       with the ``Vote.id``.
    4. For resolved votes, fetches per-member positions from the API and
       upserts ``VoteOutcomeRow`` records for each known representative.

    Parameters
    ----------
    db:
        SQLAlchemy session. Commits are made incrementally inside the upsert
        helpers — there is no single outer transaction for the whole sync run.
        This means a crash mid-run leaves partial data, but the idempotency
        guarantees ensure a subsequent run completes cleanly.
    client:
        Congress API client. In production this is ``ProPublicaCongressClient``;
        in tests it is a ``FakeCongressClient`` injected via the parameter.
    chamber:
        ``"house"`` or ``"senate"``. Passed directly to the API client.
    event_handlers:
        Optional list of callbacks invoked when a vote first becomes resolved.
        Each callback receives the ``Vote.id`` (UUID). Downstream services
        (notification engine, vote resolution engine) register handlers here
        at startup. If ``None``, no events are fired but the sync proceeds
        normally.

    Returns
    -------
    SyncResult:
        Counts of rows created/updated during this run.
    """
    handlers = event_handlers or []
    result = SyncResult(bills_upserted=0, votes_upserted=0, outcomes_upserted=0)

    recent_votes = client.get_recent_votes(chamber)

    for rv in recent_votes:
        # Skip procedural votes — they have no bill and can never be pledged on.
        if rv.congress_bill_id is None:
            continue

        bill = _upsert_bill(db, rv)
        result.bills_upserted += 1

        was_resolved, vote = _upsert_vote(db, rv, bill)
        result.votes_upserted += 1

        # Fire events only when the vote newly resolved during THIS run.
        if was_resolved:
            for handler in handlers:
                handler(vote.id)

        # Only fetch per-member outcomes for resolved votes. An unresolved vote
        # has no positions yet (members haven't voted), and the API returns an
        # empty positions array anyway.
        if vote.resolved_at is not None:
            detail = client.get_vote_detail(rv.congress, rv.chamber, rv.session, rv.roll_call)
            for pos in detail.positions:
                if _upsert_outcome(db, vote, pos):
                    result.outcomes_upserted += 1

    return result


def _upsert_bill(db: Session, rv: RecentVote) -> Bill:
    """Insert a Bill row if it doesn't exist, or return the existing one.

    Keyed on ``congress_bill_id`` (ProPublica's bill slug, e.g.
    ``"hr1234-119"``), which has a unique constraint in the database.

    We do not update the title on an existing bill because the AI-generated
    ``summary_ai`` may have already been populated, and overwriting bill
    metadata on every sync is unnecessary noise. A separate migration or
    manual process can update bill metadata if needed.

    Parameters
    ----------
    db:
        SQLAlchemy session.
    rv:
        The recent-vote record whose bill should be upserted. Assumed to have
        a non-None ``congress_bill_id`` (caller is responsible for that check).

    Returns
    -------
    Bill:
        The existing or newly-created Bill row.
    """
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
    """Insert a Vote row or update it if it has newly resolved.

    Keyed on ``congress_vote_id``. The return value includes a boolean flag
    indicating whether ``resolved_at`` was set for the first time during this
    call. Callers use this flag to decide whether to fire event handlers.

    ``resolved_at`` semantics
    ~~~~~~~~~~~~~~~~~~~~~~~~~
    ProPublica includes a non-empty ``result`` string (e.g. ``"Passed"``) once
    the vote is complete. We treat any non-empty ``result`` as "resolved" and
    set ``resolved_at`` to the vote's ``date`` + ``time`` parsed as UTC.

    ``scheduled_at`` semantics
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
    The ProPublica recent-votes endpoint only returns votes that have already
    occurred, so ``scheduled_at`` and ``resolved_at`` are always the same value
    for votes ingested through this sync path. If the system later supports
    pre-scheduling future votes (where ``congress_vote_id`` would be NULL and
    ``resolved_at`` would be NULL), those rows are created elsewhere and only
    updated when the sync sees them appear in ProPublica with a matching ID.

    Parameters
    ----------
    db:
        SQLAlchemy session.
    rv:
        Recent vote record from the API.
    bill:
        The already-upserted ``Bill`` row this vote belongs to.

    Returns
    -------
    tuple[bool, Vote]:
        ``(newly_resolved, vote)`` where ``newly_resolved`` is ``True`` if
        ``resolved_at`` was set during this call (either because the row is
        brand new and the vote is resolved, or because the row existed but
        ``resolved_at`` was previously ``None``).
    """
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

    # Vote already exists — check if resolved_at is transitioning None → set.
    # This handles the rare case where a vote appeared in the recent-votes list
    # before ProPublica recorded its result (network timing, recess, etc.).
    newly_resolved = vote.resolved_at is None and resolved_at is not None
    if newly_resolved:
        vote.resolved_at = resolved_at
        db.commit()
    return newly_resolved, vote


def _upsert_outcome(db: Session, vote: Vote, pos: object) -> bool:
    """Insert a VoteOutcomeRow if it doesn't already exist.

    Vote outcomes are immutable once written. We never update an existing
    outcome row — if ProPublica somehow changes a recorded position (which
    should not happen in practice), it would require a manual data correction.

    Representatives not found in our database are silently skipped. This
    handles representatives who have left office since the last seed run,
    or edge cases in the ProPublica data for non-voting delegates.

    Unknown ``vote_position`` strings (anything not in ``_POSITION_MAP``) are
    logged as warnings and skipped rather than crashing the sync. This is a
    defensive measure against ProPublica API changes.

    Parameters
    ----------
    db:
        SQLAlchemy session.
    vote:
        The ``Vote`` row these outcomes belong to.
    pos:
        A ``VotePosition`` from the API detail response. Typed as ``object``
        to avoid a circular import at the module level; it is cast internally.

    Returns
    -------
    bool:
        ``True`` if a new row was inserted, ``False`` if the outcome already
        existed or the representative was not found.
    """
    from app.services.congress_client import VotePosition

    p: VotePosition = pos  # type: ignore[assignment]
    rep = db.query(Representative).filter_by(bioguide_id=p.member_id).first()
    if rep is None:
        # Representative not in our database — most likely a non-voting
        # delegate (DC, PR, etc.) or a rep who left office after the last
        # seed run. Skip silently; the sync is still valid.
        return False

    outcome_val = _POSITION_MAP.get(p.vote_position)
    if outcome_val is None:
        logger.warning(
            "Unknown vote_position %r for member %s — skipping outcome",
            p.vote_position,
            p.member_id,
        )
        return False

    existing = db.query(VoteOutcomeRow).filter_by(
        vote_id=vote.id, representative_id=rep.id
    ).first()
    if existing is not None:
        return False

    db.add(VoteOutcomeRow(vote_id=vote.id, representative_id=rep.id, outcome=outcome_val))
    db.commit()
    return True


def _parse_datetime(date: str, time_str: str) -> datetime:
    """Parse ProPublica date and time strings into a timezone-aware UTC datetime.

    ProPublica returns dates as ``"YYYY-MM-DD"`` and times as ``"HH:MM:SS"``
    in Eastern time, but for our purposes treating them as UTC is acceptable —
    we only need day-level resolution for pledge resolution logic, not exact
    clock times.

    Parameters
    ----------
    date:
        Date string in ``"YYYY-MM-DD"`` format.
    time_str:
        Time string in ``"HH:MM:SS"`` format.

    Returns
    -------
    datetime:
        UTC-aware datetime combining the two inputs.
    """
    return datetime.strptime(f"{date} {time_str}", "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=timezone.utc
    )
