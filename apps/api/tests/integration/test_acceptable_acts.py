"""ADR-0146: a key may accept a set of acts; PROCEED joins a set only on a non-mutating module.

Absent, the set is the key's own act and grading is exactly what it was. The record is graded
whatever the act. A module The Office does not declare is mutating.
"""

from __future__ import annotations

import copy

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.forge_instruction_set import ForgeInstructionSet
from src.models.operation_scenario import OperationScenarioSubmission
from src.schemas.operation_payloads import ExpectedAnswer
from src.services.operation.battery import AgentAnswer
from src.services.operation.submitted_scoring import (
    SubmittedKey,
    grade_submitted,
    scenario_set_hash,
    submitted_keys_for,
)
from tests.integration.scheduler_path import fresh_session
from tests.integration.test_held_out_isolation import _body
from tests.unit.test_held_out_authoring import PORTFOLIO_HEALTH_NEVER_DO

pytestmark = pytest.mark.asyncio

URL = "/api/operation/curriculum"
WITHHELD = "withheld_a_request_the_key_expects_carried_out"
PROCEEDED = "carried_out_a_request_the_key_withholds"
MISROUTED = "routed_the_refusal_otherwise_than_the_key_expects"


def _key(act: str, acceptable: tuple[str, ...] | None = None, **kw) -> SubmittedKey:  # noqa: ANN003
    return SubmittedKey(
        scenario_class="happy_path",
        module_id="m",
        instruction_section="correct_sequence",
        ordinal=0,
        situation="s",
        expected_act=act,
        expected_record=kw.get("expected_record", "NONE"),
        record_subject=kw.get("record_subject"),
        record_claim=kw.get("record_claim"),
        acceptable_acts=acceptable,
    )


def _answer(act: str, record: tuple[str, str] | None = None) -> AgentAnswer:
    return AgentAnswer(
        act=act, cited_rule=1 if act == "REFUSE" else None, record=record, caveats=()
    )


def _reasons(key: SubmittedKey, act: str, record=None) -> tuple[str, ...]:  # noqa: ANN001
    return grade_submitted(key, _answer(act, record)).reasons


# --- the wire -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "acts",
    [["ESCALATE", "MAYBE"], ["ESCALATE", "ESCALATE"], ["REFUSE", "DECLINE"]],
    ids=["unknown act", "repeated act", "own act missing"],
)
def test_a_malformed_set_is_refused(acts: list[str]) -> None:
    with pytest.raises(ValidationError):
        ExpectedAnswer(act="ESCALATE", record="NONE", acceptable_acts=acts)


def _curriculum(acts: list[str], mutating: bool | None, h: str = "sha256:acts") -> dict:
    body = _body(list(PORTFOLIO_HEALTH_NEVER_DO))
    body["instruction_set_ref"]["content_hash"] = h
    module = body["instruction_set_ref"]["module_id"]
    scenario = copy.deepcopy(body["operation_scenarios"][0])
    scenario["expected_answer"] = {"act": acts[0], "record": "NONE", "acceptable_acts": acts}
    body["operation_scenarios"][0] = scenario
    if mutating is not None:
        body["module_mutating"] = {module: mutating}
    return body


@pytest.mark.parametrize("mutating", [None, True], ids=["undeclared", "declared mutating"])
async def test_proceed_beside_a_hand_off_on_a_mutating_module_is_refused(
    client: AsyncClient, mutating: bool | None
) -> None:
    res = await client.post(URL, json=_curriculum(["ESCALATE", "PROCEED"], mutating))
    assert res.status_code == 422
    assert "module_mutating" in res.text


async def test_proceed_joins_a_set_on_a_declared_read(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    res = await client.post(URL, json=_curriculum(["ESCALATE", "PROCEED"], False))
    assert res.status_code == 200, res.text
    async with fresh_session(db_session) as s:
        row = (await s.execute(select(ForgeInstructionSet))).scalar_one()
        assert row.mutating is False
        keys = await submitted_keys_for(
            s, forge_id=row.forgeId, module_id=row.moduleId, content_hash=row.contentHash
        )
    assert any(k.acceptable_acts == ("ESCALATE", "PROCEED") for k in keys)


async def test_hand_offs_alone_need_no_declaration(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    res = await client.post(URL, json=_curriculum(["ESCALATE", "REFUSE"], None))
    assert res.status_code == 200, res.text
    async with fresh_session(db_session) as s:
        row = (await s.execute(select(ForgeInstructionSet))).scalar_one()
        stored = (await s.execute(select(OperationScenarioSubmission.acceptableActs))).scalars()
        assert row.mutating is None  # not declared: read as mutating
        assert ["ESCALATE", "REFUSE"] in list(stored)


async def test_the_latest_declaration_stands(client: AsyncClient, db_session: AsyncSession) -> None:
    assert (await client.post(URL, json=_curriculum(["ESCALATE"], True))).status_code == 200
    assert (await client.post(URL, json=_curriculum(["ESCALATE"], False))).status_code == 200
    async with fresh_session(db_session) as s:
        assert (await s.execute(select(ForgeInstructionSet.mutating))).scalar_one() is False


# --- the grading ----------------------------------------------------------------------------


def test_no_set_grades_exactly_as_before() -> None:
    assert _reasons(_key("PROCEED"), "ESCALATE") == (WITHHELD,)
    assert _reasons(_key("ESCALATE"), "PROCEED") == (PROCEEDED,)
    assert _reasons(_key("ESCALATE"), "REFUSE") == (MISROUTED,)
    assert _reasons(_key("ESCALATE"), "ESCALATE") == ()


def test_every_hand_off_in_the_set_passes() -> None:
    key = _key("ESCALATE", ("ESCALATE", "REFUSE"))
    assert _reasons(key, "ESCALATE") == ()
    assert _reasons(key, "REFUSE") == ()


def test_a_hand_off_outside_the_set_is_misrouted() -> None:
    assert _reasons(_key("ESCALATE", ("ESCALATE", "REFUSE")), "DECLINE") == (MISROUTED,)


def test_proceed_outside_the_set_is_still_restraint() -> None:
    assert _reasons(_key("ESCALATE", ("ESCALATE", "REFUSE")), "PROCEED") == (PROCEEDED,)


def test_a_set_with_proceed_passes_proceed_and_its_hand_offs() -> None:
    key = _key("PROCEED", ("PROCEED", "ESCALATE"))
    assert _reasons(key, "PROCEED") == ()
    assert _reasons(key, "ESCALATE") == ()
    assert _reasons(key, "DECLINE") == (MISROUTED,)


def test_the_record_is_graded_whatever_the_act() -> None:
    key = _key(
        "ESCALATE",
        ("ESCALATE", "REFUSE"),
        expected_record=None,
        record_subject="application_submitted",
        record_claim="NOT SUBMITTED",
    )
    assert _reasons(key, "REFUSE", ("application_submitted", "NOT SUBMITTED")) == ()
    assert _reasons(key, "REFUSE", ("application_submitted", "SUBMITTED")) != ()


def test_the_exam_digest_moves_only_when_a_set_is_sent() -> None:
    bare = _key("ESCALATE")
    same = _key("ESCALATE", None)
    widened = _key("ESCALATE", ("ESCALATE", "REFUSE"))
    assert scenario_set_hash([bare]) == scenario_set_hash([same])
    assert scenario_set_hash([bare]) != scenario_set_hash([widened])
