"""`/api/version` — a live process is not an up-to-date one (ADR-0084).

On 19 September the API had served `f13d7b1` for two days while the checkout sat sixteen commits
ahead at `0b2fb9e`, so a curriculum's `expected_answer` met a schema written before P1 and was
discarded on arrival. Every check passed: the port answered, health said ok, and
`openapi.info.version` reported a SHA.

**The SHA was not evidence.** It is `settings.app_version`, which is `APP_VERSION` from the
environment with a default of "1.0.0" - a label the launcher wrote on the box. On the first restart
that day it read "1.0.0" while running correct code, which is the same failure pointing the other
way.
"""

from __future__ import annotations

from httpx import AsyncClient

from src import build_info
from src.build_info import UNKNOWN, commits_differ


async def test_it_reports_both_commits_and_whether_they_differ(client: AsyncClient) -> None:
    """**The whole route.** One number can only say what it was told; the comparison is the
    evidence."""
    body = (await client.get("/api/version")).json()

    assert set(body) >= {"started_commit", "checkout_commit", "differs", "launch_environment"}
    assert body["differs"] in (True, False, None)
    # In this checkout the two agree, which is the state a restart is supposed to produce.
    if body["started_commit"] != UNKNOWN and body["checkout_commit"] != UNKNOWN:
        assert body["differs"] is (body["started_commit"] != body["checkout_commit"])


def test_an_unknown_commit_is_never_reported_as_up_to_date() -> None:
    """**The care in the whole module.** `False` would tell a process that cannot say what it is
    running that it is current - the one reassurance it must not be given."""
    assert commits_differ(UNKNOWN, "0b2fb9e") is None
    assert commits_differ("0b2fb9e", UNKNOWN) is None
    assert commits_differ(UNKNOWN, UNKNOWN) is None
    assert commits_differ("0b2fb9e", "0b2fb9e") is False
    assert commits_differ("0b2fb9e", "f13d7b1") is True


async def test_the_started_commit_is_frozen_and_the_checkout_is_not(
    client: AsyncClient, monkeypatch
) -> None:
    """The distinction the route exists for: one number is about the PROCESS and cannot move while
    it lives; the other is about the TREE and moves under it. A `started_commit` re-read per
    request would report the checkout's commit as the process's own, which is exactly the
    confusion being ended."""
    monkeypatch.setattr(build_info, "checkout_commit", lambda: "deadbee" * 5 + "f")
    monkeypatch.setattr("src.routers.version.checkout_commit", lambda: "deadbee" * 5 + "f")

    body = (await client.get("/api/version")).json()

    assert body["checkout_commit"] == "deadbee" * 5 + "f"
    assert body["started_commit"] != body["checkout_commit"]
    assert body["differs"] is True


async def test_the_launch_environment_reports_the_modes_that_decide_behaviour(
    client: AsyncClient,
) -> None:
    """`SCHEDULER_ENABLED` vanished on the 19 September restart and nothing said so - it lived only
    in the old process's environment, and the batteries an operator believed were running were
    not."""
    modes = (await client.get("/api/version")).json()["launch_environment"]["modes"]

    assert "scheduler_enabled" in modes
    assert "llm_provider" in modes
    assert "exam_model_tag" in modes
    assert "auth_mode" in modes


async def test_no_credential_is_reported_by_value(client: AsyncClient) -> None:
    """**The reason this reads `settings` and never `os.environ`.** A dump would put
    `DATABASE_URL`'s password, the Clerk secret and The Office's tenant token into an
    unauthenticated response.

    Presence answers "was it exported" without answering "what is it", which is the whole question
    an operator has.
    """
    body = (await client.get("/api/version")).json()
    configured = body["launch_environment"]["configured"]

    assert set(configured) >= {"database_url", "office_tenant_token", "clerk_secret_key"}
    for name, value in configured.items():
        assert isinstance(value, bool), f"{name} is reported by value, not presence"

    raw = (await client.get("/api/version")).text
    for secret in ("password", "postgresql://", "sk-", "Bearer "):
        assert secret not in raw


async def test_it_never_raises_when_git_cannot_be_read(client: AsyncClient, monkeypatch) -> None:
    """A version endpoint that can fail is a health check reporting the health of itself."""
    monkeypatch.setattr("src.routers.version.checkout_commit", lambda: UNKNOWN)

    body = (await client.get("/api/version")).json()

    assert body["checkout_commit"] == UNKNOWN
    assert body["differs"] is None
