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


class RepResponse(BaseModel):
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
    house: RepResponse | None
    senators: list[RepResponse]


class RepsBrowseResponse(BaseModel):
    reps: list[RepResponse]
    total: int


class VotePledgeAggregates(BaseModel):
    yes_pool_cents: int
    no_pool_cents: int


class VoteHistoryItem(BaseModel):
    vote_id: uuid.UUID
    bill_title: str
    scheduled_at: datetime
    resolved_at: datetime | None
    rep_outcome: str | None
    pledges: VotePledgeAggregates


class RepAggregatePool(BaseModel):
    total_carrot_cents: int
    total_stick_cents: int


class RepDetailResponse(BaseModel):
    id: uuid.UUID
    bioguide_id: str
    name: str
    party: str
    chamber: str
    state: str
    district: int | None
    photo_url: str | None
    is_active: bool
    vote_history: list[VoteHistoryItem]
    pledge_aggregate: RepAggregatePool

    model_config = {"from_attributes": True}


@router.get("/reps", response_model=RepsResponse)
def get_reps(
    zip: str = Query(..., pattern=r"^\d{5}$", description="5-digit US zip code"),
    db: Session = Depends(get_db),
    zip_lookup: ZipLookupClient = Depends(get_zip_lookup),
) -> RepsResponse:
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
    state: str | None = Query(None),
    chamber: str | None = Query(None),
    party: str | None = Query(None),
    db: Session = Depends(get_db),
) -> RepsBrowseResponse:
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
    rep = db.query(Representative).filter(Representative.bioguide_id == bioguide_id).first()
    if rep is None:
        raise HTTPException(status_code=404, detail=f"Representative {bioguide_id} not found")

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
            (VoteOutcomeRow.vote_id == Vote.id) & (VoteOutcomeRow.representative_id == rep.id),
        )
        .outerjoin(
            Pledge,
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
