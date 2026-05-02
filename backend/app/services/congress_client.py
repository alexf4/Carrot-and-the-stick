"""ProPublica Congress API client."""
import os
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

_BASE = "https://api.propublica.org/congress/v1"
_MAX_RETRIES = 3


class CongressAPIError(Exception):
    pass


@dataclass(frozen=True)
class RecentVote:
    congress_vote_id: str  # "{congress}/{chamber}/{session}/{roll_call}"
    congress: int
    chamber: str  # "house" | "senate"
    session: int
    roll_call: int
    date: str  # "YYYY-MM-DD"
    time: str  # "HH:MM:SS"
    congress_bill_id: str | None
    bill_title: str | None
    result: str


@dataclass(frozen=True)
class VotePosition:
    member_id: str  # bioguide_id
    vote_position: str  # "Yes" | "No" | "Not Voting" | "Present"


@dataclass(frozen=True)
class VoteDetail:
    congress_vote_id: str
    positions: list[VotePosition]


class CongressClient(Protocol):
    def get_recent_votes(self, chamber: str) -> list[RecentVote]: ...
    def get_vote_detail(self, congress: int, chamber: str, session: int, roll_call: int) -> VoteDetail: ...


class ProPublicaCongressClient:
    def __init__(self, api_key: str, http_client: httpx.Client | None = None) -> None:
        self._api_key = api_key
        self._http = http_client or httpx.Client()

    def get_recent_votes(self, chamber: str) -> list[RecentVote]:
        data = self._request_with_backoff(f"{_BASE}/{chamber.lower()}/votes/recent.json")
        votes_raw: list[dict[str, Any]] = data["results"]["votes"]
        return [self._parse_recent_vote(v) for v in votes_raw]

    def get_vote_detail(self, congress: int, chamber: str, session: int, roll_call: int) -> VoteDetail:
        url = f"{_BASE}/{congress}/{chamber.lower()}/sessions/{session}/votes/{roll_call}.json"
        data = self._request_with_backoff(url)
        vote_raw = data["results"]["votes"]
        congress_vote_id = (
            f"{vote_raw['congress']}/{vote_raw['chamber'].lower()}"
            f"/{vote_raw['session']}/{vote_raw['roll_call']}"
        )
        positions = [
            VotePosition(member_id=p["member_id"], vote_position=p["vote_position"])
            for p in vote_raw.get("positions", [])
        ]
        return VoteDetail(congress_vote_id=congress_vote_id, positions=positions)

    def _request_with_backoff(self, url: str) -> dict[str, Any]:
        delay = 1
        for attempt in range(_MAX_RETRIES + 1):
            resp = self._http.get(url, headers={"X-API-Key": self._api_key})
            if resp.status_code == 429:
                if attempt == _MAX_RETRIES:
                    raise CongressAPIError(f"Rate limit exceeded after {_MAX_RETRIES} retries: {url}")
                retry_after = int(resp.headers.get("Retry-After", delay))
                time.sleep(retry_after)
                delay *= 2
                continue
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]
        raise CongressAPIError(f"Request failed after {_MAX_RETRIES} retries: {url}")

    @staticmethod
    def _parse_recent_vote(raw: dict[str, Any]) -> RecentVote:
        chamber = str(raw["chamber"]).lower()
        congress_vote_id = f"{raw['congress']}/{chamber}/{raw['session']}/{raw['roll_call']}"
        bill = raw.get("bill") or {}
        return RecentVote(
            congress_vote_id=congress_vote_id,
            congress=int(raw["congress"]),
            chamber=chamber,
            session=int(raw["session"]),
            roll_call=int(raw["roll_call"]),
            date=raw["date"],
            time=raw["time"],
            congress_bill_id=bill.get("bill_id") or None,
            bill_title=bill.get("title") or None,
            result=raw.get("result", ""),
        )


def get_congress_client() -> CongressClient:
    return ProPublicaCongressClient(api_key=os.environ["CONGRESS_API_KEY"])
