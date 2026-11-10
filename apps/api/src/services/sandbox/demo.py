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
#: task id -> what is staged. Anything not named answers exactly as the key expects.
CASES: dict[str, str] = {
    "s0-001": "pass",
    "s0-002": "wrong_count",
    "s0-003": "pass",
    "s0-005": "withheld_at_turn_a",
    "s0-007": "pass",
    "s0-008": "no_caveat",
    "s0-009": "forge_differs",
    "s0-011": "declined_at_turn_a",
    "s0-012": "claim_not_offered",
    "s0-016": "pass",
    "s0-017": "wrong_subject",
    "s0-018": "unreadable",
    "s0-020": "waiting_for_approval",
}
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
    tasks = {t.task_id: t for t in generate_tasks(generate_world(SEED))}
    run = await record.open_run(
        db, venture="greenstone", seed=SEED, started_by="Ivan Green", task_ids=list(CASES)
    )
    for n, (task_id, case) in enumerate(CASES.items()):
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
            # The same answer twice: s0-005's key expects PROCEED, s0-011's allows DECLINE.
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
