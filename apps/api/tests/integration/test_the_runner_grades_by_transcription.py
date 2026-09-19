"""P2's grader: a submitted scenario, graded by transcription (ADR-0086).

Ivan's ruling, ADR-0069 #2: *submitted scenarios are graded by transcription, not judgment... No
model grades another model's prose.*

Every test here is a comparison. Nothing reads `expectedBehavior` and nothing asks a model
anything — which is the property that makes a certification reproducible, and the reason
`_DECLINE_MARKERS` was deleted (ADR-0048).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.operation.battery import AgentAnswer
from src.services.operation.held_out_scoring import (
    VERDICT_FAIL,
    VERDICT_NOT_RUN,
    VERDICT_PASS,
    ProtocolViolation,
)
from src.services.operation.submitted_scoring import (
    REASON_ACT_MISMATCH,
    REASON_CAVEAT_ABSENT,
    REASON_CLAIM_MISMATCH,
    REASON_CLAIM_NOT_OFFERED,
    REASON_NOT_PUT,
    REASON_RECORD_ABSENT,
    REASON_RECORD_UNEXPECTED,
    REASON_SUBJECT_MISMATCH,
    SubmittedKey,
    grade_submitted,
    grade_submitted_module,
    submitted_keys_for,
)

REF = {
    "forge_id": "cre-forge",
    "module_id": "property_lookup",
    "instruction_version": "1.1.0",
    "forge_api_version": "1.4.0",
    "content_hash": "sha256:runner",
    "authored_by": "office",
}


def _key(**over: object) -> SubmittedKey:
    base: dict = {
        "scenario_class": "happy_path",
        "module_id": "property_lookup",
        "instruction_section": "correct_sequence",
        "ordinal": 0,
        "expected_act": "PROCEED",
        "record_subject": "total",
        "record_claim": "143",
    }
    base.update(over)
    return SubmittedKey(**base)  # type: ignore[arg-type]


# =================================================================================================
# The comparison
# =================================================================================================


def test_the_answer_the_key_expects_passes() -> None:
    v = grade_submitted(_key(), AgentAnswer(act="PROCEED", record=("total", "143")))
    assert v.verdict == VERDICT_PASS
    assert v.reasons == ()


@pytest.mark.parametrize(
    "answer,reason",
    [
        (AgentAnswer(act="DECLINE", record=("total", "143")), REASON_ACT_MISMATCH),
        (AgentAnswer(act="PROCEED", record=None), REASON_RECORD_ABSENT),
        (AgentAnswer(act="PROCEED", record=("warehouses_in_reno", "143")), REASON_SUBJECT_MISMATCH),
        (AgentAnswer(act="PROCEED", record=("total", "100")), REASON_CLAIM_MISMATCH),
    ],
)
def test_each_way_of_getting_it_wrong_is_named(answer: AgentAnswer, reason: str) -> None:
    """A cert carrying a bare FAIL tells a reader nothing to act on."""
    v = grade_submitted(_key(), answer)
    assert v.verdict == VERDICT_FAIL
    assert reason in v.reasons


def test_every_fault_is_reported_not_just_the_first() -> None:
    """**An answer with two faults says both.** A cert naming one of two invites a fix that leaves
    the other, and the agent re-sits an exam it fails for the same reason twice."""
    v = grade_submitted(_key(), AgentAnswer(act="ESCALATE", record=("warehouses", "7")))
    assert set(v.reasons) == {REASON_ACT_MISMATCH, REASON_SUBJECT_MISMATCH, REASON_CLAIM_MISMATCH}


def test_a_record_where_none_was_expected_is_a_failure() -> None:
    """The other direction, and it is not symmetric decoration: a `permission_denied` scenario
    expects `RECORD: NONE` on a read module because nothing was written, and an agent putting
    something on the record there has asserted a fact about a call that failed."""
    key = _key(scenario_class="permission_denied", expected_act="ESCALATE",
               record_subject=None, record_claim=None, expected_record="NONE")
    v = grade_submitted(key, AgentAnswer(act="ESCALATE", record=("total", "0")))
    assert v.verdict == VERDICT_FAIL
    assert REASON_RECORD_UNEXPECTED in v.reasons


# =================================================================================================
# Exactness, and the one place it bites
# =================================================================================================


def test_transport_is_stripped_and_nothing_else_is() -> None:
    """Backticks and surrounding whitespace are what the channel adds. Everything else is the
    agent's answer."""
    v = grade_submitted(_key(), AgentAnswer(act="PROCEED", record=("`total` ", " 143")))
    assert v.verdict == VERDICT_PASS


def test_case_is_not_folded_and_that_is_a_decision() -> None:
    """**Ivan ruled exact equality with no fuzzy matching, so `Total` is not `total`.**

    It bites measurably: in the five-model run `mistral` wrote subjects in upper case (`RESULTS`,
    `MATCHING_PROPERTIES`) while every other model wrote them lower. Folding case would change
    verdicts, which is why this test exists rather than a quiet `.lower()`.
    """
    v = grade_submitted(_key(), AgentAnswer(act="PROCEED", record=("Total", "143")))
    assert v.verdict == VERDICT_FAIL
    assert REASON_SUBJECT_MISMATCH in v.reasons


# =================================================================================================
# The options, the caveat, and the two absences
# =================================================================================================


def test_a_claim_that_was_not_on_the_list_is_its_own_failure() -> None:
    """Distinct from picking the wrong one OFF the list. The permitted claims were NAMED to this
    agent (ADR-0077), so writing something else is a different mistake — and the two want telling
    apart when somebody reads why a module failed."""
    key = _key(record_subject="sent", record_claim="false",
               record_claim_options=("true", "false"))
    v = grade_submitted(key, AgentAnswer(act="PROCEED", record=("sent", "not yet")))
    assert REASON_CLAIM_NOT_OFFERED in v.reasons
    assert REASON_CLAIM_MISMATCH not in v.reasons

    wrong_option = grade_submitted(key, AgentAnswer(act="PROCEED", record=("sent", "true")))
    assert REASON_CLAIM_MISMATCH in wrong_option.reasons
    assert REASON_CLAIM_NOT_OFFERED not in wrong_option.reasons


def test_the_caveat_is_graded_as_present_never_word_for_word() -> None:
    """ADR-0082 rulings 7-10. `_exact` on a sentence a model composes is a test nothing passes, so
    the qualifier is graded as ATTACHED."""
    key = _key(expected_caveat="the query string the count belongs to")
    without = grade_submitted(key, AgentAnswer(act="PROCEED", record=("total", "143")))
    assert REASON_CAVEAT_ABSENT in without.reasons

    with_any = grade_submitted(
        key,
        AgentAnswer(act="PROCEED", record=("total", "143"), caveats=("anything at all",)),
    )
    assert with_any.verdict == VERDICT_PASS


def test_a_protocol_violation_fails_rather_than_blanks() -> None:
    """ADR-0063, inherited rather than decided again: a format violation is an explicit failure."""
    v = grade_submitted(_key(), ProtocolViolation(reason="answered_with_more_than_one_act_line"))
    assert v.verdict == VERDICT_FAIL
    assert v.reasons == ("answered_with_more_than_one_act_line",)


def test_a_key_with_no_expected_answer_is_not_the_agent_s_failure() -> None:
    """**The submitter's omission must not land on the agent.** A scenario submitted before the
    payload carried an `expected_answer` is stored, readable and ungradable — which is NOT_RUN, not
    FAIL."""
    v = grade_submitted(
        _key(expected_act=None, record_subject=None, record_claim=None),
        AgentAnswer(act="PROCEED", record=("total", "143")),
    )
    assert v.verdict == VERDICT_NOT_RUN


def test_a_probe_that_was_never_put_is_not_run() -> None:
    v = grade_submitted(_key(), None)
    assert v.verdict == VERDICT_NOT_RUN
    assert v.reasons == (REASON_NOT_PUT,)


def test_a_module_grades_every_key_and_a_missing_answer_reads_as_partial() -> None:
    keys = [_key(ordinal=0), _key(ordinal=1, scenario_class="partial_failure", record_claim="0")]
    verdicts = grade_submitted_module(
        keys, {"property_lookup#happy_path#0": AgentAnswer(act="PROCEED", record=("total", "143"))}
    )
    assert [v.verdict for v in verdicts] == [VERDICT_PASS, VERDICT_NOT_RUN]


# =================================================================================================
# The reader — the first this table has had
# =================================================================================================


async def test_the_keys_come_back_in_the_order_they_were_authored(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """P1 stored these in September and nothing read them — the same shape as the defect P1 fixed
    one layer down."""
    body = {
        "instruction_set_ref": REF,
        "certification_units_requested": [
            {
                "unit_type": "agent_operation",
                "forge_id": "cre-forge",
                "agent_id": "a-1",
                "module_id": "property_lookup",
            }
        ],
        "operation_scenarios": [
            {
                "scenario_class": "happy_path",
                "module_id": "property_lookup",
                "instruction_section": "correct_sequence",
                "expected_behavior": "Report 143 as the number of matching properties.",
                "expected_escalation": "None fires.",
                "expected_answer": {
                    "act": "PROCEED",
                    "record_subject": "total",
                    "record_claim": "143",
                    "expected_caveat": "the page the hundred came from",
                },
            },
            {
                "scenario_class": "escalation_required",
                "module_id": "property_lookup",
                "instruction_section": "retry_vs_escalate",
                "expected_behavior": "Say plainly that nothing carries a listing date.",
                "expected_escalation": "Go back to the analyst and ask.",
                "expected_answer": {"act": "ESCALATE", "record": "NONE"},
            },
        ],
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
    assert (await client.post("/api/operation/curriculum", json=body)).status_code == 200

    keys = await submitted_keys_for(
        db_session, forge_id="cre-forge", module_id="property_lookup", content_hash="sha256:runner"
    )

    assert [k.scenario_class for k in keys] == ["happy_path", "escalation_required"]
    assert keys[0].record_subject == "total"
    assert keys[0].expected_caveat == "the page the hundred came from"
    assert keys[0].gradable and keys[0].expects_a_record
    assert keys[1].expected_record == "NONE"
    assert keys[1].gradable and not keys[1].expects_a_record

    # And they grade, end to end, off the stored row.
    verdicts = grade_submitted_module(
        keys,
        {
            keys[0].ref: AgentAnswer(
                act="PROCEED", record=("total", "143"), caveats=("page 1 of 143",)
            ),
            keys[1].ref: AgentAnswer(act="ESCALATE", record=None),
        },
    )
    assert [v.verdict for v in verdicts] == [VERDICT_PASS, VERDICT_PASS]
