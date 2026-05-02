#!/usr/bin/env python3
"""
Seed the representatives table with current federal representatives.

Uses the Congress.gov API (https://api.congress.gov/v3/).
Requires CONGRESS_API_KEY env var or --api-key flag.
Requires DATABASE_URL env var.

Usage:
    python scripts/seed_reps.py
    python scripts/seed_reps.py --api-key YOUR_KEY --congress 119
"""
import argparse
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Allow running as a script from the backend/ directory
sys.path.insert(0, str(Path(__file__).parents[1]))

load_dotenv(Path(__file__).parents[2] / ".env")

from app.models.enums import Chamber  # noqa: E402
from app.models.representatives import Representative  # noqa: E402

_BASE = "https://api.congress.gov/v3"
_PARTY_MAP = {
    "Democratic": "D",
    "Republican": "R",
    "Independent": "I",
}
_STATE_ABBR = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY", "District of Columbia": "DC",
    "Puerto Rico": "PR", "Virgin Islands": "VI", "Guam": "GU",
    "American Samoa": "AS", "Northern Mariana Islands": "MP",
}


def _fetch_members(api_key: str, congress: int) -> list[dict]:
    members: list[dict] = []
    params: dict = {
        "currentMember": "true",
        "congress": str(congress),
        "limit": "250",
        "offset": "0",
        "api_key": api_key,
        "format": "json",
    }
    with httpx.Client(timeout=30) as client:
        while True:
            resp = client.get(f"{_BASE}/member", params=params)
            resp.raise_for_status()
            data = resp.json()
            batch: list[dict] = data.get("members", [])
            members.extend(batch)
            if len(batch) < int(params["limit"]):
                break
            params["offset"] = str(int(params["offset"]) + len(batch))
    return members


def _chamber_from_terms(member: dict) -> str | None:
    terms = member.get("terms", {})
    if isinstance(terms, dict):
        items = terms.get("item", [])
    else:
        items = terms
    if not items:
        return None
    latest = items[-1] if isinstance(items, list) else items
    raw = latest.get("chamber", "").lower()
    if raw == "house of representatives":
        return Chamber.house.value
    if raw == "senate":
        return Chamber.senate.value
    return None


def _upsert(session: Session, member: dict) -> None:
    bioguide_id: str = member.get("bioguideId", "")
    if not bioguide_id:
        return

    chamber = _chamber_from_terms(member)
    if chamber is None:
        return

    state_raw: str = member.get("state", "")
    state: str = _STATE_ABBR.get(state_raw, state_raw)
    district: int | None = member.get("district") if chamber == Chamber.house.value else None
    name: str = member.get("name", "")
    party_raw: str = member.get("partyName", "")
    party: str = _PARTY_MAP.get(party_raw, party_raw[:1] if party_raw else "?")

    existing = session.query(Representative).filter_by(bioguide_id=bioguide_id).first()
    if existing:
        existing.name = name
        existing.party = party
        existing.chamber = chamber
        existing.state = state
        existing.district = district
        existing.is_active = True
    else:
        session.add(Representative(
            bioguide_id=bioguide_id,
            name=name,
            party=party,
            chamber=chamber,
            state=state,
            district=district,
            is_active=True,
        ))


def seed(api_key: str, congress: int, database_url: str) -> None:
    print(f"Fetching members (Congress {congress})...")
    members = _fetch_members(api_key, congress)
    print(f"  Found {len(members)} members")

    engine = create_engine(database_url)
    with Session(engine) as session:
        for m in members:
            _upsert(session, m)
        session.commit()
    print("  Seeding complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed representatives table from Congress.gov")
    parser.add_argument("--api-key", default=os.getenv("CONGRESS_GOV_API_KEY", ""))
    parser.add_argument("--congress", type=int, default=119, help="Congress number (default: 119)")
    args = parser.parse_args()

    if not args.api_key:
        print("Error: set CONGRESS_GOV_API_KEY env var or pass --api-key", file=sys.stderr)
        sys.exit(1)

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("Error: DATABASE_URL env var is required", file=sys.stderr)
        sys.exit(1)

    seed(args.api_key, args.congress, database_url)


if __name__ == "__main__":
    main()
