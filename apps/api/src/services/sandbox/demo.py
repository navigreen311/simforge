"""A recorded fake sandbox run, to show the results page (ADR-0166 stage 6).

**Fake.** No agent answered and no Forge was called: the answers are scripted here and the
Forge's answer is the generator's prediction, except where a mismatch is staged. It is still
*recorded*, through `record.open_run` / `record_step` / `close_run`, so every verdict on the page
is the one the real record gave, with the real grader.

It is recorded into whatever session it is given. `scripts.sandbox_run_page --demo` gives it an
in-memory SQLite database holding only the two sandbox tables, so the fake run exists nowhere
else.

The cases, on seed 0 (one agent per module, as on shift):

- a pass in each module (two in property_lookup);
- a wrong count, a missing caveat, a record under the wrong subject;
- a Turn A DECLINE where the key expects PROCEED, and one the key allows (no call, no Turn B);
- a Turn B DECLINE with a claim not on the list;
- an answer that broke the protocol;
- a Forge answer other than predicted (Turn B not graded);
- a task left waiting for its approval when the run closed.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.sandbox_run import SandboxRun
from src.services.forges.deal_desk_world import Task, generate_tasks, generate_world
from src.services.sandbox import record

SEED = 0
T0 = datetime(2026, 11, 10, 15, 0, 0)
FORGE_ACTOR = "cre-forge-sandbox (scripted)"
AGENTS = {
    "property_lookup": "fake-agent-1",
    "comp_analysis": "fake-agent-2",
    "buyer_match": "fake-agent-3",
}
_ANY: Callable[[Task], bool] = lambda t: True  # noqa: E731


def _counts(t: Task) -> bool:
    return t.turn_b.record_subject == "total"


def _proceed_only(t: Task) -> bool:
    return t.turn_a.expected_act == "PROCEED" and t.turn_a.acceptable_acts is None


#: What is staged, and on which task: the first of the seed's tasks in that module and class that
#: fits, in task order, and not staged already. Since generator 1.3.0 a seed draws its own tasks,
#: so they are found by what they are, not by number. Anything else answers as the key expects.
STAGED: tuple[tuple[str, str, str, Callable[[Task], bool]], ...] = (
    ("pass", "property_lookup", "happy_path", _ANY),
    ("wrong_count", "property_lookup", "happy_path", _counts),
    ("pass", "property_lookup", "partial_failure", _ANY),
    ("withheld_at_turn_a", "property_lookup", "partial_failure", _proceed_only),
    ("pass", "comp_analysis", "happy_path", _ANY),
    ("no_caveat", "comp_analysis", "happy_path", lambda t: bool(t.turn_b.expected_caveat)),
    ("forge_differs", "comp_analysis", "partial_failure", _ANY),
    (
        "declined_at_turn_a",
        "comp_analysis",
        "malformed_input",
        lambda t: "DECLINE" in (t.turn_a.acceptable_acts or ()),
    ),
    (
        "claim_not_offered",
        "comp_analysis",
        "malformed_input",
        lambda t: bool(t.turn_b.record_claim_options),
    ),
    ("pass", "buyer_match", "happy_path", _ANY),
    ("wrong_subject", "buyer_match", "happy_path", _counts),
    ("unreadable", "buyer_match", "partial_failure", _ANY),
    ("waiting_for_approval", "buyer_match", "malformed_input", _ANY),
)


def staged_cases(tasks: tuple[Task, ...]) -> dict[str, str]:
    """Task id -> what is staged on it, in task order."""
    chosen: dict[str, str] = {}
    for case, module, scenario_class, fits in STAGED:
        task = next(
            t
            for t in tasks
            if (t.module_id, t.scenario_class) == (module, scenario_class)
            and t.task_id not in chosen
            and fits(t)
        )
        chosen[task.task_id] = case
    return dict(sorted(chosen.items()))


FAKE_NOTE = (
    "<b>FAKE RUN, recorded for the demo.</b> No agent answered and no Forge was called: the "
    "answers are scripted (<code>src/services/sandbox/demo.py</code>) and the Forge's answer is "
    "the prediction except where a mismatch is staged. The agents are not real agents. It was "
    "recorded through the real record and graded by the real grader, into an in-memory database "
    "that held nothing else."
)


def _turn_b(task: Task, case: str) -> dict[str, Any]:
    key = task.turn_b
    record_ = (
        {"subject": key.record_subject, "claim": key.record_claim} if key.record_subject else None
    )
    caveats = ["synthetic sandbox data"] if key.expected_caveat else []
    if case == "wrong_count" and record_:
        record_["claim"] = str(int(str(record_["claim"])) + 1)
    elif case == "no_caveat":
        caveats = []
    elif case == "wrong_subject" and record_:
        record_["subject"] = "suppressed"
    elif case == "claim_not_offered" and record_:
        record_["claim"] = "TOO FAR"
    elif case == "unreadable":
        return {"unreadable": "answered_with_more_than_one_act_line"}
    return {"act": key.expected_act, "record": record_, "caveats": caveats}


async def record_demo_run(db: AsyncSession) -> SandboxRun:
    """Open, record and close the fake run. Returns the closed run."""
    every = generate_tasks(generate_world(SEED))
    tasks = {t.task_id: t for t in every}
    cases = staged_cases(every)
    run = await record.open_run(
        db, venture="greenstone", seed=SEED, started_by="Ivan Green", task_ids=list(cases)
    )
    for n, (task_id, case) in enumerate(cases.items()):
        task = tasks[task_id]
        agent = AGENTS[task.module_id]
        at = T0 + timedelta(minutes=10 * n)
        office = f"fake-task-{n + 1:02d}"

        async def step(
            name: str,
            actor: str,
            payload: dict[str, Any] | None = None,
            minute: int = 0,
            ids: dict[str, str] | None = None,
            task: Task = task,
            at: datetime = at,
            office: str = office,
            agent: str = agent,
        ) -> None:
            await record.record_step(
                db,
                run,
                task_id=task.task_id,
                step=name,
                at=at + timedelta(minutes=minute),
                actor=actor,
                payload=payload,
                sandbox_ids={"office_task": office, **(ids or {})},
                agent_id=agent if name == "claimed" else None,
            )

        await step("filed", "Ivan Green", {"facts": task.facts, "request": task.request})
        await step("claimed", agent, minute=1)
        if case in ("withheld_at_turn_a", "declined_at_turn_a"):
            # The same answer twice: one key expects PROCEED, the other allows DECLINE.
            await step("turn_a", agent, {"act": "DECLINE", "caveats": []}, minute=2)
            continue
        await step("turn_a", agent, {"act": "PROCEED", "caveats": []}, minute=2)
        proposal = {"proposal": f"fake-proposal-{n + 1:02d}"}
        await step("proposed", agent, {"request": task.request}, minute=3, ids=proposal)
        if case == "waiting_for_approval":
            continue
        await step("approved", record.SANDBOX_APPROVER, minute=4, ids=proposal)
        answer = {k: v for k, v in task.forge_answer.items()}
        if case == "forge_differs":
            answer["status"], answer["comps_available"] = 503, False
        await step("forge_answer", FORGE_ACTOR, answer, minute=5, ids=proposal)
        await step("turn_b", agent, _turn_b(task, case), minute=6)
    return await record.close_run(db, run)
