"""Tests for ProPublicaCongressClient — fixture parsing and retry logic."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.congress_client import (
    CongressAPIError,
    ProPublicaCongressClient,
    RecentVote,
    VoteDetail,
    get_congress_client,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _make_client(responses: list[httpx.Response]) -> ProPublicaCongressClient:
    """Build a client with a fake httpx.Client that returns responses in order."""
    call_count = 0

    def fake_get(url: str, **kwargs: object) -> httpx.Response:
        nonlocal call_count
        resp = responses[call_count]
        call_count += 1
        return resp

    fake_http = MagicMock(spec=httpx.Client)
    fake_http.get.side_effect = fake_get
    return ProPublicaCongressClient(api_key="test-key", http_client=fake_http)


_DUMMY_REQUEST = httpx.Request("GET", "https://api.propublica.org/test")


def _json_response(data: dict) -> httpx.Response:
    return httpx.Response(200, json=data, request=_DUMMY_REQUEST)


def _status_response(status_code: int, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(status_code, headers=headers or {}, content=b"", request=_DUMMY_REQUEST)


# ---------------------------------------------------------------------------
# Fixture parsing — recent votes
# ---------------------------------------------------------------------------

def test_get_recent_votes_parses_fixture() -> None:
    fixture = json.loads((FIXTURES / "recent_votes_house.json").read_text())
    client = _make_client([_json_response(fixture)])
    votes = client.get_recent_votes("house")

    assert len(votes) == 2
    assert isinstance(votes[0], RecentVote)


def test_get_recent_votes_first_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = json.loads((FIXTURES / "recent_votes_house.json").read_text())
    client = _make_client([_json_response(fixture)])
    first = client.get_recent_votes("house")[0]

    assert first.congress_vote_id == "119/house/1/142"
    assert first.congress_bill_id == "hr1234-119"
    assert first.bill_title == "A bill to do something important"
    assert first.result == "Passed"
    assert first.congress == 119
    assert first.chamber == "house"
    assert first.session == 1
    assert first.roll_call == 142
    assert first.date == "2025-03-15"
    assert first.time == "14:30:00"


def test_get_recent_votes_null_bill_entry() -> None:
    fixture = json.loads((FIXTURES / "recent_votes_house.json").read_text())
    client = _make_client([_json_response(fixture)])
    second = client.get_recent_votes("house")[1]

    assert second.congress_bill_id is None
    assert second.bill_title is None
    assert second.congress_vote_id == "119/house/1/143"


# ---------------------------------------------------------------------------
# Fixture parsing — vote detail
# ---------------------------------------------------------------------------

def test_get_vote_detail_parses_fixture() -> None:
    fixture = json.loads((FIXTURES / "vote_detail_house.json").read_text())
    client = _make_client([_json_response(fixture)])
    detail = client.get_vote_detail(congress=119, chamber="house", session=1, roll_call=142)

    assert isinstance(detail, VoteDetail)
    assert detail.congress_vote_id == "119/house/1/142"
    assert len(detail.positions) == 4


def test_get_vote_detail_all_position_values() -> None:
    fixture = json.loads((FIXTURES / "vote_detail_house.json").read_text())
    client = _make_client([_json_response(fixture)])
    detail = client.get_vote_detail(congress=119, chamber="house", session=1, roll_call=142)

    position_map = {p.member_id: p.vote_position for p in detail.positions}
    assert position_map["A000001"] == "Yes"
    assert position_map["B000002"] == "No"
    assert position_map["C000003"] == "Not Voting"
    assert position_map["D000004"] == "Present"


# ---------------------------------------------------------------------------
# Retry logic — 429 handling
# ---------------------------------------------------------------------------

def test_retries_on_429_and_succeeds() -> None:
    fixture = json.loads((FIXTURES / "recent_votes_house.json").read_text())
    responses = [
        _status_response(429, headers={"Retry-After": "1"}),
        _json_response(fixture),
    ]
    client = _make_client(responses)

    with patch("app.services.congress_client.time.sleep") as mock_sleep:
        votes = client.get_recent_votes("house")

    assert len(votes) == 2
    mock_sleep.assert_called_once_with(1)


def test_exhausted_retries_raise_congress_api_error() -> None:
    responses = [_status_response(429, headers={"Retry-After": "1"})] * 4
    client = _make_client(responses)

    with patch("app.services.congress_client.time.sleep"):
        with pytest.raises(CongressAPIError):
            client.get_recent_votes("house")


# ---------------------------------------------------------------------------
# Dependency factory
# ---------------------------------------------------------------------------

def test_get_congress_client_returns_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONGRESS_API_KEY", "test-key-123")
    result = get_congress_client()
    assert isinstance(result, ProPublicaCongressClient)
