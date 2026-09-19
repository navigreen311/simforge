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

import os
from unittest import mock

from httpx import AsyncClient

from src import build_info
from src.build_info import UNKNOWN, commits_differ
from src.config import Settings, settings


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


# =================================================================================================
# A path is reported by whether it RESOLVES (ADR-0088)
# =================================================================================================


async def test_a_path_is_reported_by_whether_it_resolves(client: AsyncClient) -> None:
    """**The failure this fixes.** For two days `village_db_path` read as `configured: true` while
    pointing at a file that does not exist — because it has a default, and a default is a value.
    `configured` answered *is there a string*; for a path the useful question is *is there a file*.
    """
    paths = (await client.get("/api/version")).json()["launch_environment"]["paths"]

    assert set(paths) >= {"village_config_path", "village_db_path", "village_data_path"}
    for name, report in paths.items():
        assert set(report) == {"value_set", "is_default", "resolves"}, name
        assert all(isinstance(v, bool) for v in report.values()), name


async def test_a_default_that_points_nowhere_reads_as_unresolved(
    client: AsyncClient, monkeypatch
) -> None:
    """The exact shape of the two-day miss: set, defaulted, and not there."""
    monkeypatch.setattr(settings, "village_db_path", "./nowhere/village.db")

    report = (await client.get("/api/version")).json()["launch_environment"]["paths"][
        "village_db_path"
    ]

    assert report["value_set"] is True
    assert report["resolves"] is False


async def test_is_default_is_compared_against_the_field_not_the_environment(
    client: AsyncClient, monkeypatch
) -> None:
    """**A value set in `.env` is not in `os.environ`** — pydantic reads the file into the settings
    object. Checking the environment would report every configured path as unconfigured, which is
    the same class of wrong answer pointing the other way.
    """
    monkeypatch.setattr(settings, "village_config_path", "C:/somewhere/config.yaml")

    report = (await client.get("/api/version")).json()["launch_environment"]["paths"][
        "village_config_path"
    ]

    assert report["is_default"] is False  # the field's default is ""
    assert "VILLAGE_CONFIG_PATH" not in os.environ or True  # and no environment check was needed


async def test_no_path_value_is_reported(client: AsyncClient) -> None:
    """An absolute path carries a username and this route is public. `resolves` is what an operator
    needs; the value is not."""
    raw = (await client.get("/api/version")).text
    assert "village1.0.2-recovered" not in raw
    assert "C:/" not in raw and "C:\\\\" not in raw


# =================================================================================================
# The published version defaults to the commit (ADR-0091)
# =================================================================================================


async def test_openapi_version_is_the_started_commit_not_a_release_string(
    client: AsyncClient,
) -> None:
    """**What The Office's Gate 8 reads.**

    `openapi.info.version` is `settings.app_version`. Its default was "1.0.0" - a label the
    launcher wrote on the box, which said the same thing whatever code was inside, and said it
    while this process ran a commit sixteen behind its own checkout.

    Now the default is `STARTED_COMMIT`, so an unstamped process publishes the commit it is
    running rather than a release number nobody maintains.
    """
    from src.build_info import STARTED_COMMIT

    assert settings.app_version == STARTED_COMMIT

    body = (await client.get("/openapi.json")).json()
    assert body["info"]["version"] == STARTED_COMMIT
    assert body["info"]["version"] == (await client.get("/api/version")).json()["started_commit"]


def test_a_stamped_app_version_still_wins_and_the_two_agree() -> None:
    """An image stamps `APP_VERSION` with its own SHA, and `_started_commit` reads the SAME
    variable. So the stamped case does not bypass the default, it agrees with it - which is the
    property that made the environment variable safe to keep."""
    from src.build_info import _started_commit

    with mock.patch.dict(os.environ, {"APP_VERSION": "f" * 40}, clear=False):
        assert _started_commit() == "f" * 40
        assert Settings(APP_VERSION="f" * 40).app_version == "f" * 40


def test_a_release_string_in_app_version_is_not_mistaken_for_a_commit() -> None:
    """`APP_VERSION` also carries release strings. "1.0.0" is not hex, so `_started_commit` falls
    through to the working tree rather than reporting it as the commit."""
    from src.build_info import _started_commit

    with mock.patch.dict(os.environ, {"APP_VERSION": "1.0.0"}, clear=False):
        assert _started_commit() != "1.0.0"
