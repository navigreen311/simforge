"""The Office bridge: the manifest, the credential, and one brokered call.

Every assertion here corresponds to something that failed silently on a previous adapter
and returned a plausible 200 while doing so — see `theoffice/docs/forge-adapter.md`. The
header name, the response header, and the derivation of the manifest are the three that
cannot be caught by reading.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_session
from src.main import create_app
from src.models.operation_run import OperationRun
from src.routers import office
from src.services.operation.gate_verdict import GateVerdict
from src.services.operation.run_registry import open_run
from src.utils.time import utcnow

TOKEN = "office-tenant-token-for-tests"

START = {
    "run_ref": "op-bridge-1",
    "unit": "A",
    "forge_id": "capital-forge",
    "module_id": "statement_ingest",
    "agent_id": "a-1",
    "instruction_content_hash": "sha256:si",
    "scenario_count": 9,
    "coverage_denominator": 9,
}

AUTH = {"Authorization": f"Bearer {TOKEN}"}

#: Copied from `theoffice/broker/executor.py:build_headers`, spellings included. The point
#: of the test below is that these exact strings are what the adapter reads.
OFFICE_HEADERS = {
    "X-Office-Agent-Id": "11111111-2222-3333-4444-555555555555",
    "X-Office-Venture": "burkham-wickmont",
    "X-Office-Trace": "99999999-8888-7777-6666-555555555555",
    "X-Office-Forge-Api-Version": "1.0.0",
}


@pytest_asyncio.fixture
async def bridged(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[AsyncClient, None]:
    """A SimForge with the bridge configured. The router is mounted at app creation, so
    the token has to be set before `create_app()` — which is the behaviour under test in
    `test_the_bridge_is_absent_when_no_credential_is_configured`."""
    monkeypatch.setattr(settings, "office_tenant_token", TOKEN)
    app = create_app()

    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# --- the manifest ---------------------------------------------------------------------------


async def test_the_manifest_lists_gate_result(bridged: AsyncClient) -> None:
    res = await bridged.get("/office/_modules", headers=AUTH)
    assert res.status_code == 200
    body = res.json()

    assert body["forge"] == "simforge"
    assert [m["module_id"] for m in body["modules"]] == ["gate_result"]
    assert body["modules"][0]["is_mutating"] is False
    assert body["modules"][0]["idempotency_support"] == "natural"


async def test_run_scenario_pack_is_not_dispatched(bridged: AsyncClient) -> None:
    """The Pack declares it; SimForge does not dispatch it, and says so.

    SimForge has no pack-level unit of execution — `run_scenario` takes one scenario id,
    and nothing iterates a Pack's scenarios into runs. Binding this name to a handler that
    ran one scenario would be a plausible 200 that `_modules` is structurally unable to
    detect. V32 failing on the name is the correct outcome; see
    `theoffice/docs/decisions.md` entry 5.
    """
    body = (await bridged.get("/office/_modules", headers=AUTH)).json()
    assert "run_scenario_pack" not in [m["module_id"] for m in body["modules"]]

    res = await bridged.post("/office/run_scenario_pack", json={}, headers=AUTH)
    assert res.status_code == 404
    assert "run_scenario_pack" in res.json()["detail"]


def test_manifest_is_derived_from_the_dispatch_map() -> None:
    """The one artefact in the path that is derived rather than asserted.

    A literal list maintained beside the dict would be a third declaration, worse than the
    two that already exist because it would drift silently while carrying the authority of
    having come from the Forge. This test is what stops that being written.
    """
    source = (office.__file__ or "").replace("\\", "/")
    with open(source, encoding="utf-8") as fh:
        text = fh.read()
    assert "sorted(MODULES.items())" in text, (
        "the manifest must iterate the dispatch map. A hand-maintained list is a third "
        "declaration and drifts silently."
    )


def test_no_module_id_shadows_an_adapter_endpoint() -> None:
    """`_` is reserved: a module named `_modules` would shadow the manifest, and the first
    symptom would be a conformance check reporting the wrong thing."""
    assert not any(name.startswith("_") for name in office.MODULES)


# --- the credential -------------------------------------------------------------------------


async def test_the_bridge_is_absent_when_no_credential_is_configured(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Absent configuration means absent surface.

    An adapter answering `_modules` while holding no credential to check would tell The
    Office that SimForge is bridged when it is not, and Gate 0 would pass on a Forge nobody
    can authenticate to. A 404 is read as "serves no manifest", which is the truth.
    """
    monkeypatch.setattr(settings, "office_tenant_token", "")
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        assert (await ac.get("/office/_modules")).status_code == 404
        assert (await ac.post("/office/gate_result", json={})).status_code == 404


async def test_the_manifest_is_not_public(bridged: AsyncClient) -> None:
    """It names the agent-facing surface of the Forge. Not something to hand to an
    unauthenticated caller."""
    assert (await bridged.get("/office/_modules")).status_code == 401
    assert (
        await bridged.get("/office/_modules", headers={"Authorization": "Bearer wrong"})
    ).status_code == 401


async def test_a_call_without_the_credential_is_refused(bridged: AsyncClient) -> None:
    res = await bridged.post("/office/gate_result", json={"run_ref": "op-bridge-1"})
    assert res.status_code == 401
    assert "tenant credential" in res.json()["detail"]


async def test_dev_bypass_does_not_open_the_bridge(bridged: AsyncClient) -> None:
    """The reason this surface does not use `require_role`.

    Under `AUTH_MODE=dev-bypass` — the local default — every principal is a full-access
    admin and the Authorization header is never read. An adapter that deferred to the
    app's auth would serve the agent-facing surface to any caller at all.
    """
    assert settings.auth_mode == "dev-bypass"
    assert (await bridged.post("/office/gate_result", json={})).status_code == 401


# --- one brokered call ----------------------------------------------------------------------


async def test_a_brokered_call_returns_the_verdict_and_a_forge_request_id(
    bridged: AsyncClient,
) -> None:
    """The end-to-end shape, including the half that joins the two ledgers."""
    assert (
        await bridged.post("/api/operation/run/start", json=START)
    ).status_code == 200

    res = await bridged.post(
        "/office/gate_result",
        json={"run_ref": "op-bridge-1"},
        headers={**AUTH, **OFFICE_HEADERS},
    )
    assert res.status_code == 200

    # The Office stores this as `agent_call_ledger.forge_side_ref`. Both sides return 200
    # without it, which is why it is asserted rather than assumed.
    forge_ref = res.headers.get("X-Forge-Request-Id")
    assert forge_ref, "no X-Forge-Request-Id: the ledger row would have no forge-side join"
    assert len(forge_ref) == 36  # a uuid4

    body = res.json()
    assert body["verdict"] == GateVerdict.IN_PROGRESS.value
    assert body["unit"] == "A"


async def test_the_response_carries_only_manifested_fields(bridged: AsyncClient) -> None:
    """The Office's `validate_response` refuses a response carrying a field nobody
    enumerated, so a key added here without a matching entry in
    `broker/simforge_response_manifest.json` breaks the call on arrival."""
    await bridged.post("/api/operation/run/start", json=START)
    body = (
        await bridged.post(
            "/office/gate_result", json={"run_ref": "op-bridge-1"}, headers=AUTH
        )
    ).json()

    manifested = {
        "run_ref",
        "unit",
        "verdict",
        "rubric_kind",
        "rubric_version",
        "score",
        "threshold",
        "certified_tier",
        "scenario_count",
        "coverage_denominator",
        "completed_at",
    }
    assert set(body) - manifested == set()


async def test_a_hung_run_answers_timeout_over_the_bridge(
    bridged: AsyncClient, db_session: AsyncSession
) -> None:
    """The whole point of ADR-0044, reached the way The Office will reach it."""
    await bridged.post("/api/operation/run/start", json={**START, "window_minutes": 60})
    run = (
        await db_session.execute(select(OperationRun).where(OperationRun.runRef == "op-bridge-1"))
    ).scalar_one()
    run.startedAt = utcnow() - timedelta(minutes=200)
    await db_session.commit()

    body = (
        await bridged.post(
            "/office/gate_result", json={"run_ref": "op-bridge-1"}, headers=AUTH
        )
    ).json()
    assert body["verdict"] == GateVerdict.TIMEOUT.value
    assert "score" not in body


async def test_an_unknown_run_ref_is_a_404(bridged: AsyncClient) -> None:
    res = await bridged.post(
        "/office/gate_result", json={"run_ref": "op-never-seen"}, headers=AUTH
    )
    assert res.status_code == 404


async def test_a_payload_without_a_run_ref_is_refused(bridged: AsyncClient) -> None:
    res = await bridged.post("/office/gate_result", json={}, headers=AUTH)
    assert res.status_code == 422
    assert "run_ref" in res.json()["detail"]


async def test_a_non_object_payload_does_not_crash_the_adapter(bridged: AsyncClient) -> None:
    """`broker/executor.py` sends whatever the grant carries. A list or a bare string is a
    caller error and must read as a missing `run_ref`, not a 500."""
    for payload in ([1, 2, 3], "run_ref", 7):
        res = await bridged.post("/office/gate_result", json=payload, headers=AUTH)
        assert res.status_code == 422


# --- the headers ----------------------------------------------------------------------------


async def test_the_trace_header_is_read_under_the_name_the_office_sends(
    bridged: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    """`X-Office-Trace`, not `X-Office-Trace-Id`.

    The first adapter built against this contract read the wrong name. FastAPI bound it to
    None on every request, the call returned 200, the ledger row was written, and the
    correlation id was silently absent from the Forge side. A header read under the wrong
    name does not fail — it reads as absent, which is why this asserts on the logged value
    rather than on the status code.
    """
    await bridged.post("/api/operation/run/start", json=START)

    with caplog.at_level("INFO", logger="src.routers.office"):
        await bridged.post(
            "/office/gate_result",
            json={"run_ref": "op-bridge-1"},
            headers={**AUTH, **OFFICE_HEADERS},
        )

    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert OFFICE_HEADERS["X-Office-Trace"] in logged, (
        "the trace id did not reach the adapter's log: the header is being read under the "
        "wrong name, and nothing about the call would have failed"
    )
    assert OFFICE_HEADERS["X-Office-Agent-Id"] in logged
    assert OFFICE_HEADERS["X-Office-Venture"] in logged


async def test_a_trace_id_sent_under_the_old_name_does_not_arrive(
    bridged: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    """The negative half, so the test above cannot pass by accident."""
    await bridged.post("/api/operation/run/start", json=START)

    with caplog.at_level("INFO", logger="src.routers.office"):
        await bridged.post(
            "/office/gate_result",
            json={"run_ref": "op-bridge-1"},
            headers={**AUTH, "X-Office-Trace-Id": "wrong-header-name"},
        )

    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "wrong-header-name" not in logged
    assert "'office_trace': None" in logged


# --- the is_mutating contract ---------------------------------------------------------------


async def test_a_read_declared_module_that_writes_is_refused(
    bridged: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`is_mutating` is the field The Office's V31 keys on for unattended access.

    A declaration nothing checks is the same shape as the registry row this replaced, so
    it is checked at the only moment its truth is observable: after the handler ran.
    """

    async def _writes(session: AsyncSession, payload: dict) -> dict:
        await open_run(
            session,
            run_ref="op-sneaky-write",
            unit="A",
            forge_id="capital-forge",
            instruction_content_hash="sha256:si",
            rubric_kind="operation",
            rubric_version="1.0.0",
        )
        return {"ok": True}

    monkeypatch.setitem(
        office.MODULES,
        "gate_result",
        office.ModuleSpec(_writes, is_mutating=False, idempotency_support="natural"),
    )

    res = await bridged.post("/office/gate_result", json={"run_ref": "x"}, headers=AUTH)
    assert res.status_code == 500
    assert "is_mutating=False" in res.json()["detail"]

    # Rolled back, not left for the next commit to pick up.
    assert (
        await db_session.execute(
            select(OperationRun).where(OperationRun.runRef == "op-sneaky-write")
        )
    ).scalar_one_or_none() is None


# --- the version this adapter speaks --------------------------------------------------------


async def test_the_adapter_pins_its_api_version(bridged: AsyncClient) -> None:
    """`forge_registry` rejects 'latest', so the adapter's version is pinned and reported.

    This is the ADAPTER's contract version — SimForge's own. It is not the
    `forge_api_version` carried in the operation payloads, which is the version of
    whichever Forge is being certified.
    """
    assert office.API_VERSION == "1.0.0"
    assert (await bridged.get("/office/_modules", headers=AUTH)).json()[
        "api_version"
    ] == "1.0.0"


async def test_a_version_disagreement_is_recorded_not_refused(
    bridged: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    """The Office sends `forge_registry.api_version`. If it disagrees with the adapter's
    own, both values belong in the log — refusing the call would make a registry row edit
    an outage."""
    await bridged.post("/api/operation/run/start", json=START)

    with caplog.at_level("INFO", logger="src.routers.office"):
        res = await bridged.post(
            "/office/gate_result",
            json={"run_ref": "op-bridge-1"},
            headers={**AUTH, "X-Office-Forge-Api-Version": "3.2.0"},
        )

    assert res.status_code == 200
    logged = "\n".join(r.getMessage() for r in caplog.records)
    assert "'office_api_version': '3.2.0'" in logged
    assert "'adapter_api_version': '1.0.0'" in logged
