"""Representatives router — public read endpoints for the rep dashboard.

This module owns three endpoints:

``GET /reps``
    Returns the House rep and both senators for a constituent's zip code.
    Used by the pledge flow to identify which reps a user can pledge against.

``GET /reps/browse``
    Returns a filterable, paginated list of all active reps. Powers the
    public browse page where constituents discover their representatives.

``GET /reps/{bioguide_id}``
    Returns full detail for a single rep, including their vote history and
    pledge pool aggregates. Powers the individual rep dashboard page.

Architecture notes
------------------
All three endpoints are read-only and require no authentication. The rep
dashboard is intentionally public and SEO-indexed (see DESIGN.md).

The detail endpoint runs two separate queries rather than one big join:
1. Vote history: joins Vote → Bill → VoteOutcomeRow → Pledge (aggregated).
2. Pledge aggregate: a separate sum over all pledges for the rep.

The two-query approach avoids a cartesian product that would arise from
joining vote outcomes and all pledges in a single query, which would inflate
pledge totals incorrectly when a rep has votes with multiple pledge rows.

Routing order matters
---------------------
``/reps/browse`` must be registered *before* ``/reps/{bioguide_id}`` so that
FastAPI does not try to match the literal string "browse" as a bioguide_id.
The router registers routes in declaration order, so keep browse above detail.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.bills import Bill
from app.models.enums import Chamber
from app.models.pledges import Pledge
from app.models.representatives import Representative
from app.models.votes import Vote, VoteOutcomeRow
from app.services.zip_lookup import ZipLookupClient, ZipNotFoundError, get_zip_lookup

router = APIRouter()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class RepResponse(BaseModel):
    """Serialised representation of a single active Representative.

    Used as both a standalone response and as a list item in browse/detail
    responses. ``model_config = {"from_attributes": True}`` allows Pydantic
    to build this directly from a SQLAlchemy ORM instance.

    Attributes
    ----------
    id:
        Internal UUID primary key (not the ProPublica bioguide_id).
    bioguide_id:
        ProPublica / Congressional Biographical Directory identifier.
        Used as the public-facing URL slug (e.g. ``/reps/H001234``).
    name:
        Full display name as returned by ProPublica (e.g. "Jane Smith").
    party:
        Single-letter party code: ``"D"``, ``"R"``, or ``"I"``.
    chamber:
        ``"house"`` or ``"senate"``.
    state:
        Two-letter state abbreviation (e.g. ``"VA"``).
    district:
        House district number. ``None`` for senators.
    photo_url:
        ProPublica CDN URL for the official headshot. May be ``None`` if
        ProPublica does not have a photo on file for this rep.
    is_active:
        ``False`` if the rep has retired, lost a primary, or otherwise left
        office. Inactive reps are excluded from browse and zip-lookup results
        but remain in the database for historical pledge resolution.
    """

    id: uuid.UUID
    bioguide_id: str
    name: str
    party: str
    chamber: str
    state: str
    district: int | None
    photo_url: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class RepsResponse(BaseModel):
    """Response schema for ``GET /reps`` (zip-based constituent lookup).

    Attributes
    ----------
    house:
        The constituent's House rep, or ``None`` if no active rep is found
        for their district (e.g. vacancy, or zip spans district boundary).
    senators:
        Both active senators for the constituent's state. Normally two, but
        may be fewer during vacancies.
    """

    house: RepResponse | None
    senators: list[RepResponse]


class RepsBrowseResponse(BaseModel):
    """Response schema for ``GET /reps/browse``.

    Attributes
    ----------
    reps:
        Filtered list of active representatives.
    total:
        Total count of matching reps (currently equal to ``len(reps)`` since
        pagination is not yet implemented — reserved for future use).
    """

    reps: list[RepResponse]
    total: int


class VotePledgeAggregates(BaseModel):
    """Pledge pool totals for a single vote, broken down by direction.

    These are the sum of all pledge amounts for this rep on this specific
    vote, grouped by the constituent's desired direction (yes or no). They
    represent "carrot" and "stick" incentives respectively.

    Attributes
    ----------
    yes_pool_cents:
        Total pledge dollars (in cents) from constituents who pledged for
        the rep to vote YES. If the rep votes yes, these become Carrots.
    no_pool_cents:
        Total pledge dollars (in cents) from constituents who pledged for
        the rep to vote NO. If the rep votes no, these become Carrots.
    """

    yes_pool_cents: int
    no_pool_cents: int


class VoteHistoryItem(BaseModel):
    """A single vote in a rep's history, with associated pledge pools.

    Attributes
    ----------
    vote_id:
        UUID of the Vote record.
    bill_title:
        Human-readable title of the bill being voted on.
    scheduled_at:
        When the floor vote was scheduled (may be in the future for pending
        votes, or in the past for resolved ones).
    resolved_at:
        When the vote was actually recorded. ``None`` if still pending.
    rep_outcome:
        How this rep voted: ``"yes"``, ``"no"``, ``"absent"``, or
        ``"present"``. ``None`` if the vote has not yet resolved.
        Absent and present both count as Non-compliant per domain rules.
    pledges:
        Aggregated pledge pool totals for this vote/rep combination.
    """

    vote_id: uuid.UUID
    bill_title: str
    scheduled_at: datetime
    resolved_at: datetime | None
    rep_outcome: str | None
    pledges: VotePledgeAggregates


class RepAggregatePool(BaseModel):
    """Lifetime pledge pool totals for a single representative.

    These totals reflect already-disbursed pledges only (status
    ``disbursed_carrot`` or ``disbursed_stick``). Held pledges are excluded
    because they have not yet resolved — including them would overstate the
    rep's accountability record before votes are cast.

    Attributes
    ----------
    total_carrot_cents:
        Sum of all carrot disbursements (rep voted correctly) in cents.
    total_stick_cents:
        Sum of all stick disbursements (rep voted non-compliantly) in cents.
    """

    total_carrot_cents: int
    total_stick_cents: int


class RepDetailResponse(RepResponse):
    """Full detail response for a single representative.

    Extends ``RepResponse`` with vote history and lifetime pledge aggregates.
    Used exclusively by ``GET /reps/{bioguide_id}``.

    Attributes
    ----------
    vote_history:
        All votes this rep has participated in, ordered by ``scheduled_at``
        descending (most recent first).
    pledge_aggregate:
        Lifetime carrot/stick totals across all disbursed pledges.
    """

    vote_history: list[VoteHistoryItem]
    pledge_aggregate: RepAggregatePool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/reps", response_model=RepsResponse)
def get_reps(
    zip: str = Query(..., pattern=r"^\d{5}$", description="5-digit US zip code"),
    db: Session = Depends(get_db),
    zip_lookup: ZipLookupClient = Depends(get_zip_lookup),
) -> RepsResponse:
    """Return the House rep and senators for a constituent's zip code.

    Looks up the congressional district and state for the given zip, then
    queries the database for the matching active representatives.

    Parameters
    ----------
    zip:
        A 5-digit US zip code. Validated by FastAPI's Query pattern before
        reaching this handler.
    db:
        SQLAlchemy session, injected by FastAPI's dependency system.
    zip_lookup:
        Zip-to-district lookup client, injected by FastAPI's dependency
        system. Backed by a CSV lookup table in staging/test and the USPS
        API in production.

    Returns
    -------
    RepsResponse:
        House rep (or None) and list of active senators for the zip's state.

    Raises
    ------
    HTTPException(404):
        If the zip code cannot be mapped to a congressional district.
    """
    try:
        info = zip_lookup.lookup(zip)
    except ZipNotFoundError:
        raise HTTPException(status_code=404, detail=f"No congressional district found for zip {zip}")

    house_rep = (
        db.query(Representative)
        .filter(
            Representative.state == info.state,
            Representative.district == info.house_district,
            Representative.chamber == Chamber.house,
            Representative.is_active.is_(True),
        )
        .first()
    )

    senators = (
        db.query(Representative)
        .filter(
            Representative.state == info.state,
            Representative.chamber == Chamber.senate,
            Representative.is_active.is_(True),
        )
        .all()
    )

    return RepsResponse(
        house=RepResponse.model_validate(house_rep) if house_rep else None,
        senators=[RepResponse.model_validate(s) for s in senators],
    )


@router.get("/reps/browse", response_model=RepsBrowseResponse)
def browse_reps(
    state: str | None = Query(None, description="Two-letter state code, e.g. 'VA'"),
    chamber: str | None = Query(None, description="'house' or 'senate'"),
    party: str | None = Query(None, description="Party code, e.g. 'D' or 'R'"),
    db: Session = Depends(get_db),
) -> RepsBrowseResponse:
    """Return a filterable list of all active representatives.

    All filters are optional and combinable. Returns only ``is_active=True``
    reps regardless of filter combination — inactive reps are never surfaced
    on the public browse page.

    Parameters
    ----------
    state:
        Optional two-letter state filter (e.g. ``"VA"``). Case-sensitive;
        values are stored uppercase in the database.
    chamber:
        Optional chamber filter: ``"house"`` or ``"senate"``.
    party:
        Optional party filter (e.g. ``"D"``, ``"R"``, ``"I"``). Case-sensitive.
    db:
        SQLAlchemy session, injected by FastAPI's dependency system.

    Returns
    -------
    RepsBrowseResponse:
        Filtered list of reps plus a total count.
    """
    # Start with all active reps; narrow with each provided filter.
    q = db.query(Representative).filter(Representative.is_active.is_(True))
    if state:
        q = q.filter(Representative.state == state)
    if chamber:
        q = q.filter(Representative.chamber == chamber)
    if party:
        q = q.filter(Representative.party == party)
    reps = q.all()
    return RepsBrowseResponse(
        reps=[RepResponse.model_validate(r) for r in reps],
        total=len(reps),
    )


@router.get("/reps/{bioguide_id}", response_model=RepDetailResponse)
def get_rep_detail(
    bioguide_id: str,
    db: Session = Depends(get_db),
) -> RepDetailResponse:
    """Return full detail for a single rep including vote history and pledge pools.

    This endpoint powers the individual rep dashboard page. It runs two
    separate database queries (see module docstring for why).

    Query 1 — Vote history with per-vote pledge pools
    -------------------------------------------------
    Joins Vote → Bill → VoteOutcomeRow → Pledge (left outer, aggregated).
    Groups by (vote_id, scheduled_at, resolved_at, bill_title, rep_outcome)
    and sums pledge amounts into yes_pool_cents / no_pool_cents. Results are
    ordered most-recent-first.

    The VoteOutcomeRow join is an inner join: only votes where the rep has a
    recorded outcome row are included. Votes that exist in the database but
    have no VoteOutcomeRow for this rep (i.e. the sync has not yet processed
    this rep's specific vote record) are excluded rather than shown as null.

    Query 2 — Lifetime pledge aggregate
    ------------------------------------
    Sums disbursed pledge amounts across all votes for this rep. Only
    ``disbursed_carrot`` and ``disbursed_stick`` statuses are counted;
    ``held`` pledges are excluded (vote not yet resolved).

    Parameters
    ----------
    bioguide_id:
        The ProPublica bioguide identifier for the rep (e.g. ``"H001234"``).
    db:
        SQLAlchemy session, injected by FastAPI's dependency system.

    Returns
    -------
    RepDetailResponse:
        Full rep info with vote_history list and pledge_aggregate totals.

    Raises
    ------
    HTTPException(404):
        If no representative with the given bioguide_id exists in the database.
    """
    rep = db.query(Representative).filter(Representative.bioguide_id == bioguide_id).first()
    if rep is None:
        raise HTTPException(status_code=404, detail=f"Representative {bioguide_id} not found")

    # Query 1: vote history with per-vote pledge pool aggregates.
    # Uses conditional SUM (SQLAlchemy `case`) to split pledge amounts by
    # direction without a second join or subquery.
    rows = (
        db.query(
            Vote.id.label("vote_id"),
            Vote.scheduled_at,
            Vote.resolved_at,
            Bill.title.label("bill_title"),
            VoteOutcomeRow.outcome.label("rep_outcome"),
            func.coalesce(
                func.sum(case((Pledge.direction == "yes", Pledge.amount_cents), else_=0)), 0
            ).label("yes_pool_cents"),
            func.coalesce(
                func.sum(case((Pledge.direction == "no", Pledge.amount_cents), else_=0)), 0
            ).label("no_pool_cents"),
        )
        .join(Bill, Vote.bill_id == Bill.id)
        .join(
            VoteOutcomeRow,
            # Inner join: only include votes where we have this rep's outcome.
            (VoteOutcomeRow.vote_id == Vote.id) & (VoteOutcomeRow.representative_id == rep.id),
        )
        .outerjoin(
            Pledge,
            # Left outer join: votes with no pledges still appear with $0 pools.
            (Pledge.vote_id == Vote.id) & (Pledge.representative_id == rep.id),
        )
        .group_by(Vote.id, Vote.scheduled_at, Vote.resolved_at, Bill.title, VoteOutcomeRow.outcome)
        .order_by(Vote.scheduled_at.desc())
        .all()
    )

    vote_history = [
        VoteHistoryItem(
            vote_id=row.vote_id,
            bill_title=row.bill_title,
            scheduled_at=row.scheduled_at,
            resolved_at=row.resolved_at,
            rep_outcome=row.rep_outcome,
            pledges=VotePledgeAggregates(
                yes_pool_cents=row.yes_pool_cents,
                no_pool_cents=row.no_pool_cents,
            ),
        )
        for row in rows
    ]

    # Query 2: lifetime pledge aggregate (disbursed only).
    agg = (
        db.query(
            func.coalesce(
                func.sum(case((Pledge.status == "disbursed_carrot", Pledge.amount_cents), else_=0)), 0
            ).label("total_carrot_cents"),
            func.coalesce(
                func.sum(case((Pledge.status == "disbursed_stick", Pledge.amount_cents), else_=0)), 0
            ).label("total_stick_cents"),
        )
        .filter(Pledge.representative_id == rep.id)
        .first()
    )

    return RepDetailResponse(
        id=rep.id,
        bioguide_id=rep.bioguide_id,
        name=rep.name,
        party=rep.party,
        chamber=rep.chamber,
        state=rep.state,
        district=rep.district,
        photo_url=rep.photo_url,
        is_active=rep.is_active,
        vote_history=vote_history,
        pledge_aggregate=RepAggregatePool(
            total_carrot_cents=agg.total_carrot_cents,
            total_stick_cents=agg.total_stick_cents,
        ),
    )
