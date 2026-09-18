"""A boundary that ignores is not a boundary (ADR-0083).

Ivan's ruling: *request payloads declare their fields and refuse unknown ones, as responses already
do. Silently dropping a field both sides believe was delivered is worse than a refusal.*

Two fields were being dropped that way. `expected_answer` is the transcribable half of an answer
key - the thing SimForge would grade an agent against - and `village_agent_ref` is who is sitting
the exam. Pydantic's default is to IGNORE an undeclared field, so a submitter could send either and
get a `200` back with nothing kept.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.operation_run import OperationRun
from src.models.operation_scenario import OperationScenarioSubmission

REF = {
    "forge_id": "cre-forge",
    "module_id": "property_lookup",
    "instruction_version": "1.1.0",
    "forge_api_version": "1.4.0",
    "content_hash": "sha256:boundary",
    "authored_by": "office",
}


def _scenario(**over: object) -> dict:
    out: dict = {
        "scenario_class": "escalation_required",
        "module_id": "property_lookup",
        "instruction_section": "retry_vs_escalate",
        "expected_behavior": "Answer the half that was answered and name the half that was not.",
        "expected_escalation": "Go back to the analyst with the missing half and ask.",
    }
    out.update(over)
    return out


def _curriculum(*scenarios: dict) -> dict:
    return {
        "instruction_set_ref": REF,
        "certification_units_requested": [
            {
                "unit_type": "agent_operation",
                "forge_id": "cre-forge",
                "agent_id": "a-1",
                "module_id": "property_lookup",
            }
        ],
        "operation_scenarios": list(scenarios),
        "coverage_declaration": {
            "modules_in_forge": 4,
            "modules_covered": 1,
            "modules_uncovered": [],
            "functions_in_module": 5,
            "functions_covered": 0,
        },
        "module_never_do": {"property_lookup": ["never report result order as ranking"]},
        "module_not_applicable": {
            "property_lookup": {
                c: f"{c} cannot occur on a pure read"
                for c in ("rate_limited", "recovery_after_failure")
            }
        },
    }


def _run_start(**over: object) -> dict:
    out: dict = {
        "run_ref": "op-boundary-1",
        "unit": "A",
        "forge_id": "cre-forge",
        "instruction_content_hash": "sha256:boundary",
        "module_id": "property_lookup",
        "agent_id": "3f1c9a2e-0000-4000-8000-000000000001",
    }
    out.update(over)
    return out


# =================================================================================================
# The refusal
# =================================================================================================


async def test_an_undeclared_field_on_a_scenario_is_refused(client: AsyncClient) -> None:
    """**The ruling, as one assertion.** Before this the submission returned `200` and the field
    was gone - both sides believing an answer key had been delivered when none had."""
    body = _curriculum(_scenario(expected_anwser={"act": "ESCALATE", "record": "NONE"}))

    res = await client.post("/api/operation/curriculum", json=body)

    assert res.status_code == 422
    assert "expected_anwser" in res.text


async def test_an_undeclared_field_on_run_start_is_refused(client: AsyncClient) -> None:
    res = await client.post("/api/operation/run/start", json=_run_start(village_agent="victor"))

    assert res.status_code == 422
    assert "village_agent" in res.text


async def test_a_typo_in_the_expected_answer_is_refused_too(client: AsyncClient) -> None:
    """The nested model forbids extras as well, and it is the one that matters most: a misspelled
    `record_subject` would leave the scenario storable, ungradable, and looking complete."""
    body = _curriculum(
        _scenario(
            expected_answer={"act": "PROCEED", "record_subjekt": "total", "record_claim": "7"}
        )
    )

    res = await client.post("/api/operation/curriculum", json=body)

    assert res.status_code == 422
    assert "record_subjekt" in res.text


# =================================================================================================
# What the key now carries
# =================================================================================================


async def test_an_expected_answer_is_stored_in_full(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # `escalation_required` is mandatory per module unless declared absent, so the curriculum
    # carries one beside the scenario under test. That rule predates this change.
    body = _curriculum(
        _scenario(),
        _scenario(
            scenario_class="happy_path",
            expected_answer={
                "act": "PROCEED",
                "record_subject": "arv_basis",
                "record_claim": "ASKING PRICE RESTATED",
                "record_claim_options": ["ASKING PRICE RESTATED", "DEFAULT CONSTANT"],
                "expected_caveat": "the confidence the figure was returned with",
            },
        )
    )

    assert (await client.post("/api/operation/curriculum", json=body)).status_code == 200

    row = (
        (
            await db_session.execute(
                select(OperationScenarioSubmission).where(
                    OperationScenarioSubmission.scenarioClass == "happy_path"
                )
            )
        )
        .scalars()
        .one()
    )
    assert row.expectedAct == "PROCEED"
    assert row.recordSubject == "arv_basis"
    assert row.recordClaim == "ASKING PRICE RESTATED"
    assert row.recordClaimOptions == ["ASKING PRICE RESTATED", "DEFAULT CONSTANT"]
    assert row.expectedCaveat == "the confidence the figure was returned with"
    assert row.expectedRecord is None


async def test_a_scenario_without_an_expected_answer_is_still_accepted(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """**The 44 split keys are drafts and nothing is submitting them yet.** A required
    `expected_answer` would refuse every curriculum The Office sends today, which is a boundary
    that is not a boundary in the other direction."""
    assert (
        await client.post("/api/operation/curriculum", json=_curriculum(_scenario()))
    ).status_code == 200

    row = (await db_session.execute(select(OperationScenarioSubmission))).scalars().one()
    assert row.expectedAct is None
    assert row.recordSubject is None


@pytest.mark.parametrize(
    "answer,because",
    [
        ({"act": "SHRUG", "record": "NONE"}, "an act the protocol does not offer"),
        (
            {"act": "PROCEED", "record": "NONE", "record_subject": "total"},
            "both record forms at once",
        ),
        ({"act": "PROCEED"}, "neither record form"),
        ({"act": "PROCEED", "record_subject": "total"}, "a subject with no claim"),
        (
            {
                "act": "PROCEED",
                "record_subject": "total",
                "record_claim": "7",
                "record_claim_options": ["0", "143"],
            },
            "a right answer that is not on its own option list",
        ),
    ],
)
async def test_an_unsatisfiable_key_is_refused(
    client: AsyncClient, answer: dict, because: str
) -> None:
    """Each of these would store cleanly and grade nothing - or worse, grade every agent as
    failing, which reads as a finding about the agent."""
    res = await client.post(
        "/api/operation/curriculum", json=_curriculum(_scenario(expected_answer=answer))
    )

    assert res.status_code == 422, because


# =================================================================================================
# Who is sitting the exam
# =================================================================================================


async def test_the_village_ref_is_stored_on_the_run(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """**The September defect, closed at the boundary instead of by hand.**

    `agentId` is consumed as a Village ref and The Office sends its own uuid there, so six rows
    were corrected by hand after every exam refused on identity. Both ids now travel, and each
    side gets the one it uses.
    """
    res = await client.post(
        "/api/operation/run/start", json=_run_start(village_agent_ref="victor_serath")
    )
    assert res.status_code == 200

    run = (
        (
            await db_session.execute(
                select(OperationRun).where(OperationRun.runRef == "op-boundary-1")
            )
        )
        .scalars()
        .one()
    )
    assert run.villageAgentRef == "victor_serath"
    # The Office's key is untouched: its certifications are written against this one.
    assert run.agentId == "3f1c9a2e-0000-4000-8000-000000000001"


async def test_a_run_without_a_village_ref_is_still_opened(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The Office does not send it yet. An optional field is the difference between a boundary that
    refuses what it cannot use and one that refuses what nobody has sent yet."""
    assert (await client.post("/api/operation/run/start", json=_run_start())).status_code == 200

    run = (
        (
            await db_session.execute(
                select(OperationRun).where(OperationRun.runRef == "op-boundary-1")
            )
        )
        .scalars()
        .one()
    )
    assert run.villageAgentRef is None
