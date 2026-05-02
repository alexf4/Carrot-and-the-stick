import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import Chamber
from app.models.representatives import Representative
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
