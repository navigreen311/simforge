"""Linear gap-ticket client — no-op when unconfigured, real GraphQL when keyed, best-effort."""

from __future__ import annotations

import json

import httpx
import pytest

from src.config import settings
from src.services.reporter.linear_client import LinearClient


@pytest.fixture
def _configured(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "linear_api_key", "lin_test_key")
    monkeypatch.setattr(settings, "linear_team_id", "team_123")


async def test_disabled_is_noop() -> None:
    # No key/team → no post, empty ticket (dev default).
    client = LinearClient()
    ticket = await client.create_ticket("capitalforge", "gap", "desc", {})
    assert ticket.linear_id is None and ticket.linear_url is None


async def test_creates_issue_when_configured(_configured) -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "data": {
                    "issueCreate": {
                        "success": True,
                        "issue": {
                            "id": "iss_1",
                            "identifier": "SIM-1",
                            "url": "https://linear.app/team/issue/SIM-1",
                        },
                    }
                }
            },
        )

    client = LinearClient(transport=httpx.MockTransport(handler))
    ticket = await client.create_ticket(
        "capitalforge", "emd fault", "desc", {"severity": "P0", "forge": "capitalforge"}
    )
    assert ticket.linear_id == "iss_1"
    assert ticket.linear_url == "https://linear.app/team/issue/SIM-1"
    # It hit the GraphQL endpoint with the API key and the team id + a namespaced title.
    assert seen["auth"] == "lin_test_key"
    inp = seen["body"]["variables"]["input"]
    assert inp["teamId"] == "team_123" and inp["title"] == "[capitalforge] emd fault"
    assert "severity" in inp["description"]  # metadata folded into the body


async def test_unsuccessful_response_is_noop(_configured) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"issueCreate": {"success": False}}})

    client = LinearClient(transport=httpx.MockTransport(handler))
    ticket = await client.create_ticket("f", "t", "d", {})
    assert ticket.linear_id is None


async def test_transport_error_is_swallowed(_configured) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("linear down", request=request)

    client = LinearClient(transport=httpx.MockTransport(handler))
    # A Linear outage must never break gap emission → empty ticket, no raise.
    ticket = await client.create_ticket("f", "t", "d", {})
    assert ticket.linear_id is None
