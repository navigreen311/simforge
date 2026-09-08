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
from src.services.operation.scenarios import ALL_SCENARIO_CLASSES, HELD_OUT_CLASSES
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


async def test_the_manifest_lists_three_modules(bridged: AsyncClient) -> None:
    res = await bridged.get("/office/_modules", headers=AUTH)
    assert res.status_code == 200
    body = res.json()

    assert body["forge"] == "simforge"
    shapes = {m["module_id"]: m for m in body["modules"]}
    assert sorted(shapes) == ["gate_result", "run_start", "submit_curriculum"]

    # The read.
    assert shapes["gate_result"]["is_mutating"] is False
    # The two writers, declared as writers.
    assert shapes["submit_curriculum"]["is_mutating"] is True
    assert shapes["run_start"]["is_mutating"] is True
    # All three retry onto the same state without a key.
    assert {m["idempotency_support"] for m in body["modules"]} == {"natural"}


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


# --- submit_curriculum ---------------------------------------------------------------------

#: Derived from the engine, not retyped. The first version of this fixture invented eight
#: plausible-looking class names and the validator rejected all of them - correctly, and it
#: is the same reason the manifest iterates the dispatch map: a list maintained beside the
#: real one drifts, and here it was wrong on the day it was written.
#:
#: UPDATED 2026-09-08 by ADR-0048's ruling: derived by EXCLUDING the held-out set rather than by
#: naming one class, so a change to that set reaches this fixture instead of drifting past it.
_CLASSES = tuple(c for c in ALL_SCENARIO_CLASSES if c not in HELD_OUT_CLASSES)

CURRICULUM = {
    "instruction_set_ref": {
        "forge_id": "capital-forge",
        "module_id": "statement_ingest",
        "instruction_version": "1.0.0",
        "forge_api_version": "3.0.0",
        "content_hash": "sha256:bridge-curriculum",
        "authored_by": "office",
    },
    "certification_units_requested": [
        {"unit_type": "agent_operation", "forge_id": "capital-forge",
         "agent_id": "a-1", "module_id": "statement_ingest"},
    ],
    # The Office declares the never-do list below and does NOT author the scenario that tests it.
    #
    # This fixture used to append a `never_do_violation` scenario, and it had to: the validator
    # refused a declared never-do list with no matching scenario, and that class is held out. **The
    # trap was visible right here** - the only way to write a passing Office payload was to have
    # The Office author a class it may not author. ADR-0048's ruling removes the demand and refuses
    # the scenario, so the honest payload is now the passing one.
    "operation_scenarios": [
        {"scenario_class": cls, "module_id": "statement_ingest",
         "instruction_section": "s1", "expected_behavior": "b", "expected_escalation": "e"}
        for cls in _CLASSES
    ],
    "coverage_declaration": {
        "modules_in_forge": 1, "modules_covered": 1, "modules_uncovered": [],
        "functions_in_module": 4, "functions_covered": 4,
    },
    "module_never_do": {"statement_ingest": ["never post to the ledger"]},
}


async def test_a_curriculum_can_be_submitted_over_the_bridge(bridged: AsyncClient) -> None:
    """The Office hands over a curriculum with the TENANT credential, not an agent grant.

    This module answers no question about an agent. The Office submits on behalf of a
    venture, before any agent is certified and often before the agents exist, so there is
    no `office_agent_id` whose grant could authorize it.
    """
    res = await bridged.post(
        "/office/submit_curriculum",
        json=CURRICULUM,
        headers={**AUTH, **OFFICE_HEADERS},
    )
    assert res.status_code == 200
    assert res.json()["accepted"] is True
    assert res.headers.get("X-Forge-Request-Id")


async def test_submit_curriculum_is_idempotent_on_the_content_hash(
    bridged: AsyncClient, db_session: AsyncSession
) -> None:
    """Why `natural` rather than `key`.

    The upsert is keyed on (forgeId, moduleId, contentHash), so a retry lands on the same
    instruction set rather than accumulating a second one.
    """
    from src.models.forge_instruction_set import ForgeInstructionSet

    for _ in range(3):
        res = await bridged.post("/office/submit_curriculum", json=CURRICULUM, headers=AUTH)
        assert res.status_code == 200

    rows = (
        (
            await db_session.execute(
                select(ForgeInstructionSet).where(
                    ForgeInstructionSet.contentHash == "sha256:bridge-curriculum"
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1, "a retry created a second instruction set"


async def test_a_rejected_curriculum_comes_back_as_a_422_not_a_200(
    bridged: AsyncClient,
) -> None:
    """A curriculum that fails the Batch-3 rules must not read as accepted.

    The Office's executor records a non-2xx as a real outcome in the ledger, so a
    rejection reaching it as a 422 is correct. A 200 carrying `accepted: false` would be
    a plausible success - the shape this adapter exists to avoid.
    """
    thin = {**CURRICULUM, "operation_scenarios": CURRICULUM["operation_scenarios"][:1]}
    res = await bridged.post("/office/submit_curriculum", json=thin, headers=AUTH)

    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "curriculum_rejected"


async def test_a_malformed_curriculum_names_the_field(bridged: AsyncClient) -> None:
    """The endpoint signature is the schema; the adapter does not restate it.

    A second declaration of the same shape would disagree with the first the moment one
    changed, so the payload is parsed with the model the endpoint already declares and
    Pydantic own errors are passed through.
    """
    res = await bridged.post("/office/submit_curriculum", json={"nonsense": 1}, headers=AUTH)

    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "submit_curriculum_payload_invalid"
    assert res.json()["detail"]["violations"], "no field was named"


# --- run_start ------------------------------------------------------------------------------


async def test_a_run_can_be_opened_over_the_bridge(bridged: AsyncClient) -> None:
    """Without this, the run window is unreachable from outside.

    Binding `gate_result` and not this one would leave The Office able to ask for a
    verdict on a run it had no way to open.
    """
    res = await bridged.post("/office/run_start", json=START, headers={**AUTH, **OFFICE_HEADERS})

    assert res.status_code == 200
    body = res.json()
    assert body["run_ref"] == "op-bridge-1"
    assert body["already_open"] is False
    assert body["window_minutes"] == 180


async def test_run_start_does_not_restart_the_clock_on_a_re_post(
    bridged: AsyncClient,
) -> None:
    """Why `natural` is honest here rather than a default.

    An at-most-once module needs a key precisely because a second call would do damage. A
    second call here cannot: `open_run` returns the existing row with its clock untouched.
    Extending the window of a run that is already hanging is the one thing that would hide
    a timeout, and refusing it is why this is safe to retry (ADR-0044).
    """
    first = (await bridged.post("/office/run_start", json=START, headers=AUTH)).json()
    second = (await bridged.post("/office/run_start", json=START, headers=AUTH)).json()

    assert first["already_open"] is False
    assert second["already_open"] is True
    assert second["started_at"] == first["started_at"], "the clock was restarted"


async def test_run_start_still_refuses_an_unknown_unit(bridged: AsyncClient) -> None:
    """The endpoint own guard is reached through the bridge, not bypassed by it."""
    res = await bridged.post("/office/run_start", json={**START, "unit": "C"}, headers=AUTH)

    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "unknown_unit"


async def test_the_two_writers_may_write(bridged: AsyncClient, db_session: AsyncSession) -> None:
    """The other half of the `is_mutating` guard.

    The `after_flush` listener is installed only for a module declared `is_mutating=False`
    - a declared writer is allowed to write, and these two both flush and commit. Without
    this assertion, a guard that refused every write would look identical to a correct one
    until somebody bound a writer.
    """
    assert (await bridged.post("/office/run_start", json=START, headers=AUTH)).status_code == 200
    assert (
        await bridged.post("/office/submit_curriculum", json=CURRICULUM, headers=AUTH)
    ).status_code == 200

    run = (
        await db_session.execute(select(OperationRun).where(OperationRun.runRef == "op-bridge-1"))
    ).scalar_one_or_none()
    assert run is not None, "run_start is declared a writer and its write did not survive"


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
