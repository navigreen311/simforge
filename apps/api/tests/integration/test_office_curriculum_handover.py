"""P-01 / T-004 - does a REAL Office curriculum submission get accepted?

Gate 8 submitted six curricula on 2026-09-07 and got six 422s: `scenario_class` and
`instruction_section` were required by `OperationScenarioSubmission` and The Office was not
sending either, so Pydantic refused every submission before `validate_curriculum_submission`
ever ran. Both fields are on the wire now. **Nobody had run Gate 8 since**, so the fix was
unexercised and no `curriculum_submission` row has ever carried a `simforge_run_ref`.

This file is the observation. It is deliberately NOT a fixture exercise:

    THE PAYLOADS ARE REAL AND THEY ARE NOT WRITTEN HERE.

`tests/fixtures/office_curriculum/*.json` were produced by The Office's own code -
`generators.pipeline.run_all` against the live Office database, then
`broker.provisioning._curriculum_payload` called verbatim on the resulting scenarios and on
the live `broker.instructions.live` instruction set. Sixteen module payloads, exactly the
ones Gate 8 puts on the wire, captured at theoffice `7ba5efc`. Each file's `_provenance`
block records how. A hand-built payload would prove only that this test file agrees with
itself.

WHAT THE OBSERVATION IS, IN ONE LINE
====================================
**SimForge accepts a real, authored curriculum - and the hand-over still does not complete,
for a NEW reason.** `test_an_accepted_submission_carries_nothing_the_office_can_record`
below is that second half, and it is the finding P-02 and P-03 are waiting on. It is a
CHARACTERIZATION test: it asserts what is true today so the gap cannot be mistaken for
working, and it is expected to be rewritten by whoever closes the gap - not deleted quietly.

WHY EVERY ACCEPTED MODULE IS `demonstrated` AND NOT `certified`
==============================================================
`never_do_violation` and `silent_failure` are HELD_OUT_CLASSES: a submitter may not send
them (ADR-0048) and `classify_certification_level` subtracts them from the declared set, so
no submission - however complete - can reach `certified` or
`certified_with_declared_absence` on its own. That ceiling is SimForge's held-out authoring
to lift and is P-05's package, not a defect in the submission. Asserted here so the level is
read as a ceiling rather than as an incomplete curriculum.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_session
from src.main import create_app
from src.services.operation.scenarios import HELD_OUT_CLASSES, LEVEL_DEMONSTRATED

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "office_curriculum"

#: The token value is irrelevant; that the bridge demands one is not. The real client signs
#: `submit_curriculum` with The Office's tenant credential, so the real route is the brokered
#: one and that is the route exercised here.
TOKEN = "office-tenant-token-for-tests"
AUTH = {"Authorization": f"Bearer {TOKEN}"}

#: `broker/simforge_response_manifest.json` at theoffice `7ba5efc`. The Office refuses any
#: response field it has not enumerated - `validate_response` raises on the unexpected
#: direction only - so this set is what a body may contain and still be readable by the
#: caller. Copied rather than imported: the two repos share no code, which is the whole
#: reason the drift asserted below went unnoticed.
OFFICE_DECLARED_RESPONSE_FIELDS = frozenset(
    {"run_ref", "accepted", "scenario_count", "coverage_denominator", "rejected_reason"}
)


def _load(name: str) -> dict[str, dict[str, Any]]:
    doc = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    payloads: dict[str, dict[str, Any]] = doc["payloads"]
    # An empty capture compares equal to anything, and two empty greps have already read as a
    # pass once in this project. Refuse the empty file rather than iterating it zero times.
    assert payloads, f"{name}.json carries no payloads"
    return payloads


@pytest_asyncio.fixture
async def bridged(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[AsyncClient, None]:
    """SimForge with The Office bridge mounted. The router is bound at app creation, so the
    credential has to be set before `create_app()`."""
    monkeypatch.setattr(settings, "office_tenant_token", TOKEN)
    app = create_app()

    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# --- the question the package exists to answer --------------------------------------------------


async def test_one_real_office_curriculum_is_accepted(bridged: AsyncClient) -> None:
    """ONE real submission, accepted, asserted ON THE BODY.

    A 200 is not the assertion. `submit_curriculum` answers a refusal with 422 today, but a
    handler that started answering `{"accepted": false, ...}` with a 200 would be exactly the
    failure this package was written to catch, and a status-code assertion would sail past it.
    """
    payload = _load("burkham_wickmont")["submit_application"]
    res = await bridged.post("/office/submit_curriculum", json=payload, headers=AUTH)

    body = res.json()
    # The body, first and on its own terms.
    assert body.get("accepted") is True, body
    assert "violations" not in body, body
    assert body.get("module_levels") == {"submit_application": LEVEL_DEMONSTRATED}, body
    # Then the status, so a 200-with-a-refusing-body cannot pass either.
    assert res.status_code == 200, body


async def test_every_authored_burkham_module_is_accepted(bridged: AsyncClient) -> None:
    """All ten, because one module accepted proves one module, and Gate 8 submits per module.

    Every one of these carries authored `expected_behavior` / `expected_escalation` prose and
    declares, with a reason, each class the module cannot have. That is the difference between
    this venture and Greenstone below, and it is the only difference that matters here.
    """
    payloads = _load("burkham_wickmont")
    assert len(payloads) == 10, sorted(payloads)

    refused: dict[str, Any] = {}
    levels: dict[str, str] = {}
    for module_id, payload in sorted(payloads.items()):
        res = await bridged.post("/office/submit_curriculum", json=payload, headers=AUTH)
        body = res.json()
        if body.get("accepted") is not True:
            refused[module_id] = body
            continue
        levels[module_id] = body["module_levels"][module_id]

    assert refused == {}, refused
    assert sorted(levels) == sorted(payloads)
    # The ceiling, not a shortfall - see the module docstring.
    assert set(levels.values()) == {LEVEL_DEMONSTRATED}, levels


async def test_a_declared_never_do_list_comes_back_as_an_outstanding_obligation(
    bridged: AsyncClient,
) -> None:
    """The Office declares its never-do lists honestly and is not refused for it (ADR-0048).

    `record_consent` carries thirteen entries. None of them is exercised by this submission and
    none of them could be: `never_do_violation` is held out and the submitter may not author it.
    The obligation comes back RECORDED, which is what replaced the refusal that used to make a
    truthful submission impossible.
    """
    payload = _load("burkham_wickmont")["record_consent"]
    res = await bridged.post("/office/submit_curriculum", json=payload, headers=AUTH)

    body = res.json()
    assert body["accepted"] is True, body
    obligations = body["never_do_obligations"]["record_consent"]
    assert len(obligations) == 13, obligations
    # Declared, and unexercised - the submission supplies no held-out class.
    supplied = {s["scenario_class"] for s in payload["operation_scenarios"]}
    assert supplied.isdisjoint(HELD_OUT_CLASSES), supplied


# --- the six that 422'd, and why they still do --------------------------------------------------


async def test_the_six_greenstone_curricula_are_still_refused_but_not_for_the_old_reason(
    bridged: AsyncClient,
) -> None:
    """THE SIX FROM THE CARD. Still 422 - and the old cause is gone.

    These are the six `curriculum_submission` rows written 2026-09-07 with a NULL
    `simforge_run_ref`. `scenario_class` and `instruction_section` now arrive and are accepted:
    no violation names either, and the refusal has moved from Pydantic to the validator, which
    is where P-05's change was supposed to move it.

    What refuses them now is true and is nobody's bug here: no content file exists for any
    cre-forge or voiceforge module, so `expected_behavior` and `expected_escalation` come across
    as empty strings, and no `recovery_after_failure` scenario is supplied or declared. **That
    is a report about where the authorship is, not a defect in the hand-over.**
    """
    payloads = _load("greenstone")
    assert len(payloads) == 6, sorted(payloads)

    for module_id, payload in sorted(payloads.items()):
        res = await bridged.post("/office/submit_curriculum", json=payload, headers=AUTH)
        assert res.status_code == 422, (module_id, res.json())
        detail = res.json()["detail"]
        assert detail["error"] == "curriculum_rejected", (module_id, detail)
        violations = " | ".join(str(v) for v in detail["violations"])

        # The old cause, gone. Both fields are present on every scenario and neither is named.
        assert "scenario_class" not in violations, (module_id, violations)
        assert "instruction_section" not in violations, (module_id, violations)
        for scenario in payload["operation_scenarios"]:
            assert scenario["scenario_class"], scenario
            assert scenario["instruction_section"], scenario

        # The new cause, named.
        assert "missing expected_behavior, expected_escalation" in violations, (
            module_id,
            violations,
        )
        assert "recovery_after_failure" in violations, (module_id, violations)


# --- the finding --------------------------------------------------------------------------------


async def test_an_accepted_submission_carries_nothing_the_office_can_record(
    bridged: AsyncClient,
) -> None:
    """CHARACTERIZATION, NOT AN ENDORSEMENT. Acceptance here does not complete the hand-over.

    The Office's `SimForgeClient.submit_curriculum` does two things with this body before it
    believes anything, and today both refuse it:

      1. `validate_response("submit_curriculum", body)` refuses any field not enumerated in
         `broker/simforge_response_manifest.json`. Five of the six fields here are not in it.
      2. It then requires a non-empty string `run_ref`, because
         `curriculum_submission.simforge_run_ref` is what correlates a verdict back and what
         `overdue_submissions` sweeps. There is no `run_ref` in this body at all.

    So the row still lands with a NULL `simforge_run_ref` - `blocking.md` B8's exact condition -
    and P-03's sweep still has nothing to ingest. **The 422 is fixed and the hand-over is not.**

    Whoever closes this rewrites this test to assert the ref. Do not delete it quietly: an
    absent assertion is how this gap went unseen while six rows were written against it.
    """
    payload = _load("burkham_wickmont")["submit_application"]
    body = (await bridged.post("/office/submit_curriculum", json=payload, headers=AUTH)).json()

    assert body["accepted"] is True, body

    # (2) - no correlation handle of any name. Checked before the manifest diff because it is
    # the one that makes the accepted submission unusable rather than merely unreadable.
    assert "run_ref" not in body, (
        "SimForge now returns a run_ref for an accepted curriculum. That is the fix this test "
        "was written against - rewrite it to assert the ref, and tell P-02/P-03 that B8 can "
        "close."
    )

    # (1) - every field The Office would refuse, named, so the diff is the report.
    undeclared = sorted(set(body) - OFFICE_DECLARED_RESPONSE_FIELDS)
    assert undeclared == [
        "coverage_declaration",
        "gate_9_5_flag",
        "module_declared_absences",
        "module_levels",
        "never_do_obligations",
    ], undeclared
