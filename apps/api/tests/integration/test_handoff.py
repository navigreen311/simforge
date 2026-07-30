"""Multi-agent handoff integrity testing (v1.1): completeness, continuity, consent."""

from __future__ import annotations

from httpx import AsyncClient

from src.services.handoff.integrity import evaluate


def test_clean_chain_passes() -> None:
    res = evaluate(
        [
            {
                "from": "outreach",
                "to": "underwriting",
                "provides": ["applicant", "income", "consent"],
                "required": ["applicant", "income"],
                "consent": True,
            },
            {
                "from": "underwriting",
                "to": "servicing",
                "provides": ["decision"],
                "required": ["decision"],
                "consent": True,
            },
        ]
    )
    assert res["passed"] is True
    assert res["integrity_score"] == 1.0


def test_incomplete_handoff_flagged() -> None:
    res = evaluate(
        [
            {
                "from": "outreach",
                "to": "underwriting",
                "provides": ["applicant"],
                "required": ["applicant", "income"],
                "consent": True,
            }
        ]
    )
    assert res["passed"] is False
    assert res["summary"]["incomplete"] == 1
    assert "income" in res["findings"][0]["detail"]


def test_missing_consent_flagged() -> None:
    res = evaluate(
        [{"from": "a", "to": "b", "provides": ["x"], "required": ["x"], "consent": False}]
    )
    assert res["summary"]["missing_consent"] == 1


def test_broken_continuity_flagged() -> None:
    res = evaluate(
        [
            {"from": "a", "to": "b", "provides": [], "required": [], "consent": True},
            {"from": "c", "to": "d", "provides": [], "required": [], "consent": True},
        ]
    )
    assert res["summary"]["broken_continuity"] == 1


async def test_evaluate_endpoint(client: AsyncClient) -> None:
    body = {
        "name": "outreach→underwriting",
        "chain": [
            {
                "from_agent": "outreach",
                "to_agent": "underwriting",
                "provides": ["lead"],
                "required": ["lead"],
                "consent": True,
            }
        ],
    }
    res = (await client.post("/api/handoff/evaluate", json=body)).json()
    assert res["passed"] is True


async def test_store_and_evaluate_stored(client: AsyncClient) -> None:
    created = (
        await client.post(
            "/api/handoff/",
            json={
                "name": "drill",
                "chain": [
                    {
                        "from_agent": "a",
                        "to_agent": "b",
                        "provides": [],
                        "required": ["ssn"],
                        "consent": False,
                    }
                ],
            },
        )
    ).json()
    tid = created["id"]
    listed = (await client.get("/api/handoff/")).json()
    assert any(t["id"] == tid for t in listed["handoff_tests"])

    res = (await client.post(f"/api/handoff/{tid}/evaluate")).json()
    assert res["passed"] is False  # missing required ssn + missing consent

    missing = await client.post("/api/handoff/nope/evaluate")
    assert missing.status_code == 404
