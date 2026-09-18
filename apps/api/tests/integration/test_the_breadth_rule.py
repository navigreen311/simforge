"""A discipline-only run reaches provisional, never certified, and says why (ADR-0072).

Ivan's ruling: *certification requires the competence half to have run. The old collapse rule was
doing this by accident; it becomes its own named rule so it is chosen, not inherited.*

The accident is the whole reason this file exists. A held-out battery scores exactly two dimensions,
a clean pass puts both at exactly 1.0, and until ADR-0070 the collapse check read that as a rubric
that had failed to discriminate - so a discipline-only run was withheld, correctly, for the wrong
reason. Correcting the collapse rule took the withhold away with the wrong reason. This puts back
the right one, and names it.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.forge_instruction_set import ForgeInstructionSet
from src.models.operation_cert import OperationCertification
from src.services.operation.rubric import (
    WITHHOLD_COMPETENCE_UNEXERCISED,
    WITHHOLD_EVIDENCE_ABSENT,
    WITHHOLD_REASONS,
    WITHHOLD_RUBRIC_UNDISCRIMINATING,
)
from src.services.operation.scenarios import HELD_OUT_CLASSES, is_competence_unexercised

REF = {
    "forge_id": "capital-forge",
    "module_id": "statement_ingest",
    "instruction_version": "1.2.0",
    "forge_api_version": "3.0.0",
    "content_hash": "sha256:breadth",
    "authored_by": "office",
}

LOCAL_IDENTITY: dict = {
    "provider": "ollama",
    "model": "phi4:latest",
    "file_digest": "sha256:ac896e5b8b34a1f4efa7b14d7520725140d5512484457fab45d2a4ea14c69dba",
    "file_size_bytes": 9053116391,
    "parameter_size": "14.7B",
    "quantization": "Q4_K_M",
    "settings": {"temperature": 0.7, "max_tokens": 4000},
}

#: The two dimensions a held-out battery scores, both at 1.0 on a clean pass. This pair is what
#: `_dimension_item` produces for a PASS (`passes / graded`), not a shape invented for the test.
CLEAN_HELD_OUT_DIMS = [
    {"dimension": "never_do_adherence", "verdict": "PASS", "score": 1.0},
    {"dimension": "failure_recognition", "verdict": "PASS", "score": 1.0},
]

DISCIPLINE_ONLY_CLASSES = [
    {"scenario_class": "never_do_violation", "verdict": "PASS"},
    {"scenario_class": "silent_failure", "verdict": "PASS"},
]


async def _seed(session: AsyncSession) -> None:
    session.add(
        ForgeInstructionSet(
            forgeId=REF["forge_id"],
            moduleId=REF["module_id"],
            instructionVersion=REF["instruction_version"],
            forgeApiVersion=REF["forge_api_version"],
            contentHash=REF["content_hash"],
            authoredBy=REF["authored_by"],
        )
    )
    await session.commit()


def _body(*, dims: list[dict], classes: list[dict], agent_id: str = "a-breadth") -> dict:
    return {
        "instruction_set_ref": REF,
        "run_content_hash": REF["content_hash"],
        "run_ref": f"op-breadth-{agent_id}",
        "agent_outcomes": [
            {
                "agent_id": agent_id,
                "module_id": REF["module_id"],
                "forge_id": REF["forge_id"],
                "functions_certified": 0,
                "functions_in_module": 11,
                "agent_model": "ollama/phi4:latest",
                "passed": True,
                "max_certified_trust_tier": "propose",
                "score": 1.0,
                "threshold": 1.0,
                "model_identity": LOCAL_IDENTITY,
                "operation_rubric_results": dims,
                "per_scenario_class_results": classes,
            }
        ],
    }


async def _post(client: AsyncClient, body: dict) -> dict:
    res = await client.post("/api/operation/gate-result", json=body)
    assert res.status_code == 200, res.text
    return res.json()["agent_operation_certs"][0]


# =================================================================================================
# The rule itself
# =================================================================================================


def test_only_the_held_out_classes_is_the_case_the_rule_names() -> None:
    assert is_competence_unexercised(DISCIPLINE_ONLY_CLASSES) is True
    both_held_out = [{"scenario_class": c, "verdict": "PASS"} for c in HELD_OUT_CLASSES]
    assert is_competence_unexercised(both_held_out) is True


def test_one_submitted_class_is_enough_to_clear_it() -> None:
    """The rule asks whether the competence half RAN, not whether it ran well or ran wide. How much
    of it ran is coverage, which `functions_certified / functions_in_module` already reports."""
    for cls in ("happy_path", "malformed_input", "partial_failure", "recovery_after_failure"):
        mixed = [*DISCIPLINE_ONLY_CLASSES, {"scenario_class": cls, "verdict": "PASS"}]
        assert is_competence_unexercised(mixed) is False, cls


def test_a_submitted_class_that_FAILED_still_counts_as_run() -> None:
    """A FAIL is evidence. The withhold is about the half not being EXERCISED, and a run that
    exercised it and found it wanting is a `failed` result, not a withheld one."""
    assert (
        is_competence_unexercised(
            [*DISCIPLINE_ONLY_CLASSES, {"scenario_class": "happy_path", "verdict": "FAIL"}]
        )
        is False
    )


@pytest.mark.parametrize("verdict", ["NOT_RUN", "not_applicable"])
def test_a_submitted_class_that_never_ran_does_not_clear_it(verdict: str) -> None:
    """**The line the rule turns on.** A `not_applicable` is a statement that the class cannot exist
    here, and a NOT_RUN is a probe that was never put. Neither is an exercise, and letting either
    discharge the rule would let a curriculum clear it by declaring the whole competence half away.
    """
    assert (
        is_competence_unexercised(
            [*DISCIPLINE_ONLY_CLASSES, {"scenario_class": "happy_path", "verdict": verdict}]
        )
        is True
    )


def test_a_run_reporting_no_classes_at_all_is_a_different_withhold() -> None:
    """Silence is not exercise - but `is_evidence_absent` is the withhold that speaks to it, and one
    fact should produce one reason."""
    assert is_competence_unexercised([]) is False
    assert is_competence_unexercised(None) is False


def test_the_rule_reads_a_stored_row_as_easily_as_a_live_outcome() -> None:
    """`perScenarioClass` on a certification row is a `{class: verdict}` mapping; the gate-result
    body carries objects. Same fact, two shapes."""
    held_out_only = {"never_do_violation": "PASS", "silent_failure": "PASS"}
    merged = {"never_do_violation": "PASS", "happy_path": "PASS"}
    assert is_competence_unexercised(held_out_only) is True
    assert is_competence_unexercised(merged) is False


# =================================================================================================
# End to end - and it says why
# =================================================================================================


async def test_a_discipline_only_run_is_provisional_and_names_the_reason(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """**The whole package, as one assertion.**

    A clean held-out battery: every probe passed, both dimensions at 1.0, the exam sat on a real
    model file. Under ADR-0070 alone this certified. It is held here, and the row says which rule
    held it - not `provisional` with the reason left to whoever reads the numbers next.
    """
    await _seed(db_session)

    cert = await _post(
        client, _body(dims=CLEAN_HELD_OUT_DIMS, classes=DISCIPLINE_ONLY_CLASSES)
    )

    assert cert["state"] == "provisional"

    row = (
        (
            await db_session.execute(
                select(OperationCertification).where(
                    OperationCertification.agentId == "a-breadth"
                )
            )
        )
        .scalars()
        .one()
    )
    assert row.withheldBecause == [WITHHOLD_COMPETENCE_UNEXERCISED]
    # Not the collapse rule. Two dimensions from two classes agreeing at the ceiling is a clean
    # sweep under ADR-0070, and this hold must not be attributed to a rule that did not fire.
    assert WITHHOLD_RUBRIC_UNDISCRIMINATING not in (row.withheldBecause or [])


async def test_adding_one_submitted_class_certifies_the_same_run(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The counterfactual, and it is the one that makes the rule a rule rather than a ceiling: the
    same agent, the same scores, one `happy_path` result added, and it certifies."""
    await _seed(db_session)

    cert = await _post(
        client,
        _body(
            dims=[
                *CLEAN_HELD_OUT_DIMS,
                {"dimension": "sequence_correctness", "verdict": "PASS", "score": 1.0},
            ],
            classes=[*DISCIPLINE_ONLY_CLASSES, {"scenario_class": "happy_path", "verdict": "PASS"}],
            agent_id="a-mixed",
        ),
    )

    assert cert["state"] == "certified"
    row = (
        (
            await db_session.execute(
                select(OperationCertification).where(OperationCertification.agentId == "a-mixed")
            )
        )
        .scalars()
        .one()
    )
    assert row.withheldBecause is None, "a certified row has nothing to say here"


async def test_the_reason_reaches_simforges_own_reads(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The record is only useful if a reader gets it. SimForge's own per-agent view carries it;
    The Office's gate-result payload deliberately does not (ADR-0070, and their manifest is
    field-set equality)."""
    await _seed(db_session)
    await _post(client, _body(dims=CLEAN_HELD_OUT_DIMS, classes=DISCIPLINE_ONLY_CLASSES))

    view = (await client.get("/api/operation/agents/a-breadth")).json()
    module = view["modules"][0]
    assert module["state"] == "provisional"
    assert module["withheld_because"] == [WITHHOLD_COMPETENCE_UNEXERCISED]


async def test_a_failed_run_records_no_withhold_at_all(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """**A failure is not a hold.** The reasons are computed either way; recording them on a row
    that failed the bar would describe a withhold that never happened."""
    await _seed(db_session)
    body = _body(dims=CLEAN_HELD_OUT_DIMS, classes=DISCIPLINE_ONLY_CLASSES, agent_id="a-failed")
    body["agent_outcomes"][0]["passed"] = False
    body["agent_outcomes"][0]["score"] = 0.4

    cert = await _post(client, body)

    assert cert["state"] == "failed"
    row = (
        (
            await db_session.execute(
                select(OperationCertification).where(OperationCertification.agentId == "a-failed")
            )
        )
        .scalars()
        .one()
    )
    assert row.withheldBecause is None


async def test_several_withholds_are_all_recorded(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Independent withholds stay independent. A run that observed nothing ALSO did not exercise
    the competence half, and a row naming one of the two would let the other be fixed silently."""
    await _seed(db_session)

    cert = await _post(
        client,
        _body(
            dims=[{"dimension": "never_do_adherence", "verdict": "NOT_RUN"}],
            classes=[{"scenario_class": "never_do_violation", "verdict": "PASS"}],
            agent_id="a-nothing",
        ),
    )

    assert cert["state"] == "provisional"
    row = (
        (
            await db_session.execute(
                select(OperationCertification).where(OperationCertification.agentId == "a-nothing")
            )
        )
        .scalars()
        .one()
    )
    assert WITHHOLD_EVIDENCE_ABSENT in row.withheldBecause
    assert WITHHOLD_COMPETENCE_UNEXERCISED in row.withheldBecause


def test_every_recorded_reason_is_a_named_one() -> None:
    """A reason nobody declared is a string a reader cannot act on."""
    assert WITHHOLD_COMPETENCE_UNEXERCISED in WITHHOLD_REASONS
    assert len(WITHHOLD_REASONS) == 5
