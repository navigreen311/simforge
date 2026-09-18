"""The answer key The Office sends is kept (ADR-0069, P1).

Until this, `submit_curriculum` validated `operation_scenarios` and stored nothing — so nothing
could re-read what a venture said its agent should do, nothing could run the seven submittable
classes, and only the two held-out dimensions ever carried a score. Both at 1.0 on a clean run is a
collapsed spread, which is why no run could reach `certified`.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.operation_scenario import OperationScenarioSubmission

REF = {
    "forge_id": "cre-forge",
    "module_id": "property_lookup",
    "instruction_version": "1.1.0",
    "forge_api_version": "1.4.0",
    "content_hash": "sha256:pl-1",
    "authored_by": "office",
}

#: `escalation_required` is MANDATORY on every module unless declared not_applicable, so every
#: fixture below carries one. That rule predates this package and is not what it is testing.
#: The seven a submitter may send. `never_do_violation` and `silent_failure` are held out and
#: refused at validation (ADR-0048), which is why no test here sends one.
SUBMITTABLE = [
    "happy_path",
    "malformed_input",
    "partial_failure",
    "permission_denied",
    "escalation_required",
    "recovery_after_failure",
    "rate_limited",
]


def _scenario(scenario_class: str, *, module: str = "property_lookup", **over: object) -> dict:
    out = {
        "scenario_class": scenario_class,
        "module_id": module,
        "instruction_section": "correct_sequence",
        "expected_behavior": f"Report the {scenario_class} case and say what was not answered.",
        "expected_escalation": "Nothing fires; the call answered completely.",
    }
    out.update(over)
    return out


def _curriculum(*scenarios: dict, ref: dict | None = None, **over: object) -> dict:
    body = {
        "instruction_set_ref": ref or REF,
        "certification_units_requested": [
            {
                "unit_type": "agent_operation",
                "forge_id": "cre-forge",
                "agent_id": "victor_serath",
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
    body.update(over)
    return body


async def _stored(session: AsyncSession) -> list[OperationScenarioSubmission]:
    rows = (
        (
            await session.execute(
                select(OperationScenarioSubmission).order_by(
                    OperationScenarioSubmission.ordinal
                )
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def test_a_submitted_curriculum_keeps_its_scenarios(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """**The whole of P1.** Every field The Office sends is readable afterwards."""
    body = _curriculum(
        _scenario("happy_path"),
        _scenario("malformed_input", instruction_section="inputs"),
        _scenario("escalation_required", expected_escalation="Hand it to the analyst and stop."),
    )

    assert (await client.post("/api/operation/curriculum", json=body)).status_code == 200

    rows = await _stored(db_session)
    assert [r.scenarioClass for r in rows] == [
        "happy_path",
        "malformed_input",
        "escalation_required",
    ]
    first = rows[0]
    assert first.forgeId == "cre-forge"
    assert first.moduleId == "property_lookup"
    assert first.instructionContentHash == "sha256:pl-1"
    assert first.instructionSection == "correct_sequence"
    assert "Report the happy_path case" in first.expectedBehavior
    assert first.expectedEscalation
    assert first.neverDoEntry is None
    assert rows[2].expectedEscalation == "Hand it to the analyst and stop."


async def test_the_order_the_author_wrote_them_in_survives(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A set that comes back shuffled is harder to review against the file it came from."""
    ordered = [_scenario(c) for c in SUBMITTABLE[:5]]
    assert (
        await client.post("/api/operation/curriculum", json=_curriculum(*ordered))
    ).status_code == 200

    rows = await _stored(db_session)
    assert [r.ordinal for r in rows] == [0, 1, 2, 3, 4]
    assert [r.scenarioClass for r in rows] == SUBMITTABLE[:5]


async def test_resubmitting_the_same_curriculum_does_not_double_it(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A curriculum is a SET submitted whole, so the write replaces rather than accumulates."""
    body = _curriculum(
        _scenario("happy_path"),
        _scenario("malformed_input"),
        _scenario("escalation_required"),
    )

    for _ in range(3):
        assert (await client.post("/api/operation/curriculum", json=body)).status_code == 200

    assert len(await _stored(db_session)) == 3


async def test_a_changed_curriculum_replaces_the_old_scenarios(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """**The case a per-scenario upsert would have got wrong.**

    Re-posting a curriculum with FEWER scenarios must not leave last time's standing beside this
    time's — a reader would see a class the submitter had withdrawn and count it as covered.
    """
    await client.post(
        "/api/operation/curriculum",
        json=_curriculum(*[_scenario(c) for c in SUBMITTABLE[:5]]),
    )
    assert len(await _stored(db_session)) == 5

    await client.post(
        "/api/operation/curriculum", json=_curriculum(_scenario("escalation_required"))
    )

    rows = await _stored(db_session)
    assert len(rows) == 1
    assert rows[0].scenarioClass == "escalation_required"


async def test_a_different_content_hash_is_a_different_curriculum(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Not a retry - a new instruction set, whose scenarios stand beside the old ones rather than
    replacing them. The same rule `ForgeInstructionSet` follows."""
    await client.post(
        "/api/operation/curriculum", json=_curriculum(_scenario("escalation_required"))
    )
    await client.post(
        "/api/operation/curriculum",
        json=_curriculum(
            _scenario("escalation_required"),
            ref={**REF, "content_hash": "sha256:pl-2", "instruction_version": "1.2.0"},
        ),
    )

    rows = await _stored(db_session)
    assert {r.instructionContentHash for r in rows} == {"sha256:pl-1", "sha256:pl-2"}


async def test_a_rejected_curriculum_stores_nothing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """**The refusal has to hold on this side of the write too.**

    A 422 means the curriculum was not accepted, and a rejected submission that left its scenarios
    behind would put an answer key in the database that SimForge had refused.
    """
    body = _curriculum(
        _scenario("happy_path"),
        # A submitter may not author a never-do scenario (ADR-0048); this is refused.
        _scenario("never_do_violation", never_do_entry="never report order as ranking"),
    )

    res = await client.post("/api/operation/curriculum", json=body)

    assert res.status_code == 422
    assert await _stored(db_session) == []


async def test_a_curriculum_spanning_two_modules_files_each_under_its_own(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The scenario's module, not the ref's: `requested_modules` is built from exactly that, so a
    scenario filed under the wrong module would be invisible to the runner that needs it."""
    body = _curriculum(
        _scenario("escalation_required"),
        _scenario("escalation_required", module="comp_analysis"),
        module_never_do={
            "property_lookup": ["never report result order as ranking"],
            "comp_analysis": ["never average the comps into a value"],
        },
        module_not_applicable={
            m: {c: f"{c} cannot occur here" for c in ("rate_limited", "recovery_after_failure")}
            for m in ("property_lookup", "comp_analysis")
        },
    )

    assert (await client.post("/api/operation/curriculum", json=body)).status_code == 200

    rows = await _stored(db_session)
    assert {r.moduleId for r in rows} == {"property_lookup", "comp_analysis"}
