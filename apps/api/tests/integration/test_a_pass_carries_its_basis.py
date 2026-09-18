"""A graded battery's verdict reaches The Office with the basis it was earned on.

WHAT WAS BROKEN, IN ONE SENTENCE
================================

`OperationRun` has had `score`, `threshold` and `certifiedTier` columns since the run window was
built, `close_run` has accepted all three as keyword arguments, and the only caller passed the
states and nothing else — so every closed run carried a verdict and no basis, `gate_result_for`
omitted all three keys, and The Office's `record_result` refuses to write a `certified` row that
names no tier. A real PASS was produced, reported, polled, and dropped at the boundary.

WHY THE THIRD CASE IS THE IMPORTANT ONE
=======================================

Carrying the numbers through is plumbing. The rule is the refusal: an outcome that resolves to
`certified` and cannot say what it scored, against what bar, at what tier, is refused HERE — so
"an ungraded run never reports a pass" is a property of SimForge rather than a consequence of The
Office declining to record one. A rule enforced only at the far side of a boundary reads, from
this side, as somebody else's bug.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.agent_runtime.model_identity import ModelIdentity, identity_is_complete
from src.services.operation.gate_verdict import GateVerdict
from src.services.operation.run_registry import UnitOutcome, close_run, gate_result_for, open_run
from src.services.operation.state_machine import OperationState
from src.services.operation.trust_tier import (
    BATTERY_TIER_CEILING,
    tier_for_state,
    weakest_tier,
)

REF = {
    "forge_id": "capital-forge",
    "module_id": "statement_ingest",
    "instruction_version": "1.0.0",
    "forge_api_version": "3.0.0",
    "content_hash": "sha256:si",
    "authored_by": "ivan",
}

START = {
    "run_ref": "op-basis",
    "unit": "A",
    "forge_id": "capital-forge",
    "module_id": "statement_ingest",
    "agent_id": "a-1",
    "instruction_content_hash": "sha256:si",
    "scenario_count": 11,
    "coverage_denominator": 11,
}


#: A local model's identity, shaped as `ModelIdentity.as_record()` produces one. Real values from
#: this machine's `llama3.1:8b`, so the record is the shape a live Ollama actually returns.
LOCAL_IDENTITY: dict = {
    "provider": "ollama",
    "model": "llama3.1:8b",
    "file_digest": "sha256:46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e",
    "file_size_bytes": 4920753328,
    "parameter_size": "8.0B",
    "quantization": "Q4_K_M",
    "settings": {"temperature": 0.0, "max_tokens": 2048, "seed": 0},
}


def _outcome(**over: object) -> dict:
    """One agent outcome, shaped the way `build_gate_result_request` shapes a real battery's."""
    outcome: dict = {
        "agent_id": "a-1",
        "module_id": "statement_ingest",
        "forge_id": "capital-forge",
        # 0 of 11, as a held-out battery always reports: it exercises obligations, not functions.
        "functions_certified": 0,
        "functions_in_module": 11,
        "agent_model": "ollama/llama3.1:8b",
        "passed": True,
        "max_certified_trust_tier": BATTERY_TIER_CEILING,
        "score": 1.0,
        "threshold": 1.0,
        "model_identity": LOCAL_IDENTITY,
        "operation_rubric_results": [
            # Two competence dimensions far enough apart that the rubric discriminated -
            # `protocol_conformance` is excluded from the spread, so it cannot supply it.
            {"dimension": "never_do_adherence", "verdict": "PASS", "score": 0.95},
            {"dimension": "failure_recognition", "verdict": "PASS", "score": 0.60},
            {"dimension": "protocol_conformance", "verdict": "PASS", "score": 1.0},
        ],
        "per_scenario_class_results": [],
    }
    outcome.update(over)
    return outcome


async def _post(client: AsyncClient, outcome: dict, *, run_ref: str = "op-basis") -> int:
    res = await client.post(
        "/api/operation/gate-result",
        json={
            "instruction_set_ref": REF,
            "run_content_hash": "sha256:si",
            "run_ref": run_ref,
            "agent_outcomes": [outcome],
        },
    )
    return res.status_code


# --- 1. a passing battery produces a gate_result The Office can record -------------------------


async def test_a_passing_battery_reports_score_threshold_and_tier(client: AsyncClient) -> None:
    """The three fields `record_result` needs, on the body The Office actually reads.

    Asserted on `GET /operation/gate-result/{run_ref}` rather than on the POST's echo, because the
    echo is a different shape and was never the thing that was empty.
    """
    await client.post("/api/operation/run/start", json=START)
    assert await _post(client, _outcome()) == 200

    body = (await client.get("/api/operation/gate-result/op-basis")).json()

    assert body["verdict"] == GateVerdict.PASS.value
    assert body["score"] == 1.0
    assert body["threshold"] == 1.0
    assert body["certified_tier"] == "propose"
    # The fourth fact, and the one nothing had ever put on a RUN: `certified_records_its_basis`
    # refuses a certification that cannot name the candidate, and The Office reads the candidate
    # off this body.
    assert body["agent_model"] == "ollama/llama3.1:8b"


async def test_the_tier_a_battery_asks_for_is_never_auto_execute() -> None:
    """The ceiling is structural, not a policy default.

    A held-out battery exercises obligations and no module function — `functions_certified` is 0 on
    every one of its outcomes. `auto_execute` is the tier that lets an agent complete an act
    unattended, so asking for it here would be a claim about work nobody watched.
    """
    assert BATTERY_TIER_CEILING == "propose"


# --- 2. a failing battery says so ---------------------------------------------------------------


async def test_a_failing_battery_reports_a_fail_with_its_score_and_no_tier(
    client: AsyncClient,
) -> None:
    """A FAIL still carries a number. It must not carry a grant.

    The score is evidence about the run and belongs on the body; the tier is a cap The Office
    applies to a real grant, and a run that did not pass earned none. The two travel together and
    are gated separately, on purpose.
    """
    await client.post("/api/operation/run/start", json=START)
    assert (
        await _post(
            client,
            _outcome(
                passed=False,
                score=0.9,
                operation_rubric_results=[
                    {"dimension": "never_do_adherence", "verdict": "FAIL", "score": 0.9},
                    {"dimension": "failure_recognition", "verdict": "PASS", "score": 0.8},
                ],
            ),
        )
        == 200
    )

    body = (await client.get("/api/operation/gate-result/op-basis")).json()

    assert body["verdict"] == GateVerdict.FAIL.value
    assert body["score"] == 0.9
    assert body["threshold"] == 1.0
    assert "certified_tier" not in body
    # 0.9 against a bar of 1.0 is a failure, and the pair is what says so. The score alone reads
    # like a good result, which is why the manifest entitles The Office to the threshold.
    assert body["score"] < body["threshold"]


# --- 3. an ungraded run never reports a pass ----------------------------------------------------


async def test_a_certified_outcome_with_no_score_is_refused(client: AsyncClient) -> None:
    """The refusal that makes the rule SimForge's own.

    Before it, this posted a 200, closed the run at PASS, and The Office refused the row four
    steps later for a reason that reads as an Office problem.
    """
    await client.post("/api/operation/run/start", json=START)
    assert await _post(client, _outcome(score=None, threshold=None)) == 422

    # And the run is untouched: still open, still inside its window, no verdict invented for it.
    body = (await client.get("/api/operation/gate-result/op-basis")).json()
    assert body["verdict"] == GateVerdict.IN_PROGRESS.value
    assert "score" not in body


async def test_a_certified_outcome_with_no_tier_is_refused(client: AsyncClient) -> None:
    await client.post("/api/operation/run/start", json=START)
    assert await _post(client, _outcome(max_certified_trust_tier=None)) == 422


async def test_the_refusal_names_every_missing_fact_at_once(client: AsyncClient) -> None:
    """One 422 listing all three, not three round trips discovering them one at a time."""
    await client.post("/api/operation/run/start", json=START)
    res = await client.post(
        "/api/operation/gate-result",
        json={
            "instruction_set_ref": REF,
            "run_content_hash": "sha256:si",
            "run_ref": "op-basis",
            "agent_outcomes": [
                _outcome(score=None, threshold=None, max_certified_trust_tier=None)
            ],
        },
    )
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert "score" in detail and "threshold" in detail and "certified_tier" in detail


async def test_a_provisional_hold_needs_no_basis_and_reports_no_tier(
    client: AsyncClient,
) -> None:
    """The withhold is NOT caught by the guard, and that asymmetry is the ruling.

    Certification was withheld, so there is no certified tier to report; demanding one would
    invite the placeholder a later reader takes for a real cap. The Office's `record_result`
    requires none for a provisional row for exactly this reason.
    """
    await client.post("/api/operation/run/start", json=START)
    # Collapsed spread: passed the bar, the rubric did not discriminate → provisional.
    assert (
        await _post(
            client,
            _outcome(
                score=None,
                threshold=None,
                max_certified_trust_tier=None,
                operation_rubric_results=[
                    {"dimension": "a", "verdict": "PASS", "score": 0.90},
                    {"dimension": "b", "verdict": "PASS", "score": 0.90},
                ],
            ),
        )
        == 200
    )

    body = (await client.get("/api/operation/gate-result/op-basis")).json()
    assert body["verdict"] == GateVerdict.PROVISIONAL.value
    assert "certified_tier" not in body


# --- the late arrival, and the unit that has no basis to carry ----------------------------------


async def test_a_rescued_run_reports_the_real_basis(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A result that arrives wins, and it brings its basis with it.

    `close_run` already accepted a result for a run stamped TIMEOUT — the arrival is better
    evidence than the deadline. What it did not do was carry the numbers, so a rescued run
    reported PASS with nothing behind it: the one case where a verdict changes and the reader has
    only the new word for it.
    """
    await open_run(
        db_session,
        run_ref="op-late",
        unit="A",
        forge_id="capital-forge",
        module_id="statement_ingest",
        agent_id="a-1",
        instruction_content_hash="sha256:si",
        rubric_kind="operation",
        rubric_version="1.0.0",
    )
    await close_run(
        db_session,
        run_ref="op-late",
        agent_outcomes=[
            UnitOutcome(
                state=OperationState.CERTIFIED.value,
                score=1.0,
                threshold=1.0,
                certified_tier="propose",
                agent_model="ollama/llama3.1:8b",
            )
        ],
        department_outcomes=[],
    )
    await db_session.commit()

    body = await gate_result_for(db_session, "op-late")
    assert body is not None
    assert body["verdict"] == GateVerdict.PASS.value
    assert (body["score"], body["threshold"], body["certified_tier"]) == (1.0, 1.0, "propose")


async def test_a_department_run_closes_with_no_score_and_no_tier(
    db_session: AsyncSession,
) -> None:
    """Unit B has nothing to report here, and that is not a gap in this change.

    A department context is cleared by whether its escalation path and compliance coupling were
    verified. Nothing sat an exam, so there is no score, no bar and no candidate — and a zero or a
    tier would be an invention, not a default.
    """
    await open_run(
        db_session,
        run_ref="op-dept",
        unit="B",
        forge_id="capital-forge",
        department_id="d-1",
        instruction_content_hash="sha256:si",
        rubric_kind="domain",
        rubric_version="1.0.0",
    )
    await close_run(
        db_session,
        run_ref="op-dept",
        agent_outcomes=[],
        department_outcomes=[UnitOutcome(state=OperationState.CERTIFIED.value)],
    )
    await db_session.commit()

    body = await gate_result_for(db_session, "op-dept")
    assert body is not None
    assert body["verdict"] == GateVerdict.PASS.value
    assert "score" not in body
    assert "certified_tier" not in body
    assert "agent_model" not in body


# --- the collapse rules, without the HTTP -------------------------------------------------------


def test_weakest_tier_caps_at_the_weakest_named() -> None:
    assert weakest_tier(["auto_execute", "propose", "suggest"]) == "suggest"
    assert weakest_tier(["propose", None]) == "propose"
    assert weakest_tier([None, None]) is None
    # A value this side cannot rank is one The Office cannot cap against. Ignored, never guessed.
    assert weakest_tier(["l4_unattended"]) is None


def test_a_tier_survives_only_a_certified_state() -> None:
    assert tier_for_state(OperationState.CERTIFIED.value, "propose") == "propose"
    assert tier_for_state(OperationState.PROVISIONAL.value, "propose") is None
    assert tier_for_state(OperationState.FAILED.value, "propose") is None
    assert tier_for_state(OperationState.REVOKED.value, "auto_execute") is None


# --- ADR-0060: the candidate, and the pass that cannot name it ---------------------------------


async def test_a_passing_battery_reports_the_model_identity(client: AsyncClient) -> None:
    """The ruling's three facts on the body The Office reads: name, file, settings.

    `agent_model` was already there and it is a LABEL. `ollama/llama3.1:8b` is the same string
    whether the tag was re-pulled at Q4_K_M or Q8_0, and whether the exam ran at temperature 0.0
    or 0.7. These are the fields that can tell those apart.
    """
    await client.post("/api/operation/run/start", json=START)
    assert await _post(client, _outcome()) == 200

    body = (await client.get("/api/operation/gate-result/op-basis")).json()
    identity = body["model_identity"]

    assert body["verdict"] == GateVerdict.PASS.value
    assert identity["model"] == "llama3.1:8b"
    assert identity["file_digest"].startswith("sha256:")
    assert identity["file_size_bytes"] == 4920753328
    assert identity["quantization"] == "Q4_K_M"
    assert identity["settings"]["temperature"] == 0.0
    # The hash over all of it - what a re-certification check compares, rather than arguing field
    # by field about which of six values moved.
    assert identity["fingerprint"] == ModelIdentity.from_record(LOCAL_IDENTITY).fingerprint


async def test_a_result_with_no_model_identity_is_never_a_pass(client: AsyncClient) -> None:
    """**The test the ruling asked for.**

    Refused at the gate-result path rather than filtered later, so the run never reaches PASS at
    all: there is no window in which a verdict exists that nobody can attribute to a model.
    """
    await client.post("/api/operation/run/start", json=START)
    assert await _post(client, _outcome(model_identity=None)) == 422

    body = (await client.get("/api/operation/gate-result/op-basis")).json()
    assert body["verdict"] != GateVerdict.PASS.value
    assert body["verdict"] == GateVerdict.IN_PROGRESS.value
    assert "model_identity" not in body


async def test_a_half_described_candidate_is_refused_and_named(client: AsyncClient) -> None:
    """A record is not an identity. Each missing fact is named, because the three come from three
    different places and a caller told only "incomplete" has to go and find out which."""
    await client.post("/api/operation/run/start", json=START)
    res = await client.post(
        "/api/operation/gate-result",
        json={
            "instruction_set_ref": REF,
            "run_content_hash": "sha256:si",
            "run_ref": "op-basis",
            "agent_outcomes": [
                _outcome(
                    model_identity={
                        **LOCAL_IDENTITY,
                        "quantization": None,
                        "settings": {},
                    }
                )
            ],
        },
    )
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert "quantization" in detail and "settings" in detail


async def test_a_cloud_run_is_a_practice_run_and_not_a_certification(
    client: AsyncClient,
) -> None:
    """A cloud provider stays available, and what it produces is a rehearsal.

    Village agents run on local models, so a certification counts only if it was earned on one.
    The identity here is complete in every other respect - it is a real result about a real
    candidate - and it carries no model FILE, because the weights are not here. Held at
    `provisional`: not certified, not a failure, which is what that state has meant since the
    Rev-2 audit.
    """
    await client.post("/api/operation/run/start", json=START)
    assert (
        await _post(
            client,
            _outcome(
                agent_model="anthropic/claude-sonnet-5",
                model_identity={
                    "provider": "anthropic",
                    "model": "claude-sonnet-5",
                    "file_digest": None,
                    "file_size_bytes": None,
                    "parameter_size": None,
                    "quantization": None,
                    "settings": {"temperature": 0.0, "max_tokens": 2048, "seed": 0},
                },
            ),
        )
        == 200
    )

    body = (await client.get("/api/operation/gate-result/op-basis")).json()
    assert body["verdict"] == GateVerdict.PROVISIONAL.value
    assert "certified_tier" not in body
    # The record still travels. What the absent file costs is the certification, not the fact.
    assert body["model_identity"]["model"] == "claude-sonnet-5"
    assert body["model_identity"]["file_digest"] is None


async def test_a_failing_run_still_records_its_candidate(client: AsyncClient) -> None:
    """Recorded on EVERY result, not only a certified one - a failure nobody can attribute to a
    model is a failure nobody can reproduce."""
    await client.post("/api/operation/run/start", json=START)
    assert (
        await _post(
            client,
            _outcome(
                passed=False,
                score=0.9,
                operation_rubric_results=[
                    {"dimension": "never_do_adherence", "verdict": "FAIL", "score": 0.9},
                ],
            ),
        )
        == 200
    )

    body = (await client.get("/api/operation/gate-result/op-basis")).json()
    assert body["verdict"] == GateVerdict.FAIL.value
    assert body["model_identity"]["model"] == "llama3.1:8b"


# --- the identity record itself -----------------------------------------------------------------


def test_the_fingerprint_moves_when_any_of_the_three_facts_moves() -> None:
    """Model, file and settings are all IN the hash, which is the whole of the re-certification
    rule: a change to any of the three means the certification is against a different candidate."""
    from dataclasses import replace

    base = ModelIdentity.from_record(LOCAL_IDENTITY)
    assert base is not None

    same = ModelIdentity.from_record(dict(reversed(list(LOCAL_IDENTITY.items()))))
    assert same is not None and same.fingerprint == base.fingerprint  # key order is not a change

    assert replace(base, model="phi4:latest").fingerprint != base.fingerprint
    assert replace(base, quantization="Q8_0").fingerprint != base.fingerprint
    assert replace(base, file_digest="sha256:other").fingerprint != base.fingerprint
    # The one a name-only record could never catch: same tag, same file, different exam.
    assert (
        replace(base, settings={**base.settings, "temperature": 0.7}).fingerprint
        != base.fingerprint
    )


def test_a_record_carrying_its_own_fingerprint_does_not_get_to_assert_it() -> None:
    """`from_record` recomputes. A stored hash that disagreed with its fields would otherwise be
    believed on the strength of the one field nobody checks."""
    lying = {**LOCAL_IDENTITY, "fingerprint": "sha256:whatever-i-say"}
    rebuilt = ModelIdentity.from_record(lying)
    assert rebuilt is not None
    assert rebuilt.fingerprint == ModelIdentity.from_record(LOCAL_IDENTITY).fingerprint


def test_the_missing_facts_are_named_one_by_one() -> None:
    assert identity_is_complete(LOCAL_IDENTITY) == []
    assert identity_is_complete(None) == ["model_identity"]
    # An empty settings map is the accidental empty this repo refuses everywhere: it cannot be
    # told from "nothing was sent", and something is always sent.
    assert identity_is_complete({**LOCAL_IDENTITY, "settings": {}}) == ["model_identity.settings"]
    assert "model_identity.file_digest" in identity_is_complete(
        {**LOCAL_IDENTITY, "file_digest": None}
    )


def test_a_stub_cannot_describe_a_candidate_and_so_cannot_certify() -> None:
    """The base `identity()` returns None, and that default is the safe one.

    A provider added later that forgets to describe itself fails closed: its outcomes are refused
    at `certified` rather than certifying something nobody can name.
    """
    import asyncio

    from src.services.agent_runtime.llm_client import StubProvider

    assert asyncio.run(StubProvider().identity({"temperature": 0.0})) is None
