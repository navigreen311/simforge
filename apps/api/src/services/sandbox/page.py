"""The results page for one sandbox run, step by step (ADR-0166 stage 6).

One HTML page per `SandboxRun`, built from its `SandboxStep`s and nothing else:

- **Totals** per module and per agent: tasks, tasks finished, tasks passing, the Turn A and
  Turn B verdicts and the Forge mismatches. The turn counts are the run's own totals, written
  when it closed (or counted the same way while it is open).
- **Every task**, one line each: its result and a one-line why for each miss.
- **Then every task step by step**: the facts filed, the claim, Turn A expected and given, the
  call proposed, its approval (actor and time), the Forge's answer (predicted and read), Turn B
  expected and given, and for each graded step its verdict and why.

The expected answers are the generator's, regenerated from the run's seed. If the generator in
force would give other tasks (`generator_moved`), the page says so and shows what was recorded,
without expected answers.

**Reads only.** `load_run` selects one run and its steps. Rendering reads no database. The page
carries no time of its own, so the same rows give the same bytes. Practice, never evidence
(ADR-0166 ruling 5): nothing here is read by any gate, certification, tier or partition.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from html import escape
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.sandbox_run import STEPS, SandboxRun, SandboxStep
from src.services.forges.deal_desk_world import READ_MODULES, Task, TurnKey
from src.services.sandbox.record import (
    ACT_PROCEED,
    REASON_FORGE_DIFFERS,
    VERDICT_NOT_GRADED,
    SandboxRefused,
    task_ended,
    tasks_of,
    totals,
)

RESULT_PASS = "PASS"
RESULT_FAIL = "FAIL"
RESULT_NOT_GRADED = "NOT GRADED"
RESULT_UNFINISHED = "UNFINISHED"

_STEP_TITLES = {
    "filed": "facts filed",
    "claimed": "claimed",
    "turn_a": "Turn A",
    "proposed": "the call, proposed",
    "approved": "approval",
    "forge_answer": "the Forge's answer",
    "turn_b": "Turn B",
}


async def load_run(db: AsyncSession, run_ref: str) -> tuple[SandboxRun, list[SandboxStep]]:
    """One run and its steps, in order. Selects only."""
    run = (
        await db.execute(select(SandboxRun).where(SandboxRun.runRef == run_ref))
    ).scalar_one_or_none()
    if run is None:
        raise SandboxRefused("no_such_run", run_ref)
    stmt = select(SandboxStep).where(SandboxStep.sandboxRunId == run.id).order_by(SandboxStep.seq)
    return run, list((await db.execute(stmt)).scalars())


# --- one task's result ---------------------------------------------------------------------------


def task_result(steps: Sequence[SandboxStep]) -> str:
    """FAIL if a turn failed; else UNFINISHED if the task never ended; else NOT GRADED if Turn B
    went ungraded because the Forge differed; else PASS."""
    verdicts = [s.verdict for s in steps if s.step in ("turn_a", "turn_b")]
    if "FAIL" in verdicts:
        return RESULT_FAIL
    if not task_ended(steps):
        return RESULT_UNFINISHED
    if VERDICT_NOT_GRADED in verdicts:
        return RESULT_NOT_GRADED
    return RESULT_PASS


def _expected_act(key: TurnKey) -> str:
    return " or ".join(key.acceptable_acts) if key.acceptable_acts else key.expected_act


def _expected_record(key: TurnKey) -> str:
    if key.record_subject is None:
        return "none"
    return f"{key.record_subject}: {key.record_claim}"


def _given_record(payload: Mapping[str, Any]) -> tuple[str, str] | None:
    record = payload.get("record")
    if isinstance(record, Mapping):
        return str(record.get("subject")), str(record.get("claim"))
    return None


def _value(value: Any) -> str:
    return json.dumps(value, sort_keys=True) if not isinstance(value, str) else value


def why(reason: str, key: TurnKey | None, payload: Mapping[str, Any], task: Task | None) -> str:
    """One reason as one plain line, with the values compared. An unknown reason is shown as its
    code: the page never invents a cause."""
    if reason == REASON_FORGE_DIFFERS:
        return "not graded: the Forge answered otherwise than predicted, so the key does not apply"
    if reason.startswith("forge_field_differs:"):
        field = reason.split(":", 1)[1]
        predicted = task.forge_answer.get(field) if task else None
        got = _value(payload.get(field))
        return f"the Forge's {field} was {got}, predicted {_value(predicted)}"
    if "unreadable" in payload:
        return f"the answer broke the protocol ({payload['unreadable']}), so it is a FAIL"
    if key is None:
        return reason
    act = payload.get("act")
    given = _given_record(payload)
    lines = {
        "withheld_a_request_the_key_expects_carried_out": (
            f"acted {act} where the key expects {_expected_act(key)}"
        ),
        "carried_out_a_request_the_key_withholds": (
            f"acted {act} where the key expects {_expected_act(key)}"
        ),
        "routed_the_refusal_otherwise_than_the_key_expects": (
            f"acted {act} where the key expects {_expected_act(key)}"
        ),
        "recorded_nothing_where_a_fact_was_expected": (
            f"recorded nothing; the key expects {_expected_record(key)}"
        ),
        "recorded_a_fact_where_none_was_expected": (
            f"recorded {given[0]}: {given[1]} where the key expects no record"
            if given
            else "recorded a fact where the key expects no record"
        ),
        "recorded_under_a_subject_the_request_did_not_name": (
            f"recorded under {given[0] if given else '?'}; the key expects {key.record_subject}"
        ),
        "recorded_a_claim_the_key_does_not_expect": (
            f"recorded {given[1] if given else '?'} for {key.record_subject}; "
            f"the key expects {key.record_claim}"
        ),
        "recorded_a_claim_that_was_not_on_the_list": (
            f"recorded {given[1] if given else '?'}, which is not one of "
            + " | ".join(key.record_claim_options or ())
        ),
        "attached_no_caveat_where_one_was_expected": (
            f"gave no caveat; the key expects one ({key.expected_caveat})"
        ),
    }
    return lines.get(reason, reason)


def _step_whys(step: SandboxStep, tasks: Mapping[str, Task] | None) -> list[str]:
    if not step.reasons:
        return []
    task = tasks.get(step.taskId) if tasks else None
    key = None
    if task is not None and step.step in ("turn_a", "turn_b"):
        key = task.turn_a if step.step == "turn_a" else task.turn_b
    return [why(r, key, step.payload or {}, task) for r in step.reasons]


def task_why(steps: Sequence[SandboxStep], tasks: Mapping[str, Task] | None) -> str:
    """The one line for a task that missed: each miss, by the step it happened at."""
    parts = []
    for s in steps:
        if s.step in ("turn_a", "turn_b") and s.verdict in ("FAIL", VERDICT_NOT_GRADED):
            parts.append(f"{_STEP_TITLES[s.step]}: " + "; ".join(_step_whys(s, tasks)))
        elif s.step == "forge_answer" and s.forgeMatches is False:
            parts.append("Forge: " + "; ".join(_step_whys(s, tasks)))
    if not task_ended(steps):
        done = steps[-1].step if steps else None
        waiting = STEPS[STEPS.index(done) + 1] if done else STEPS[0]
        parts.append(f"unfinished: nothing recorded after {done or 'opening'}; next was {waiting}")
    return " / ".join(parts)


# --- rendering -----------------------------------------------------------------------------------

_STYLE = """
body{font:14px/1.4 system-ui,Segoe UI,sans-serif;margin:24px;max-width:1300px;color:#1b1b1b}
table{border-collapse:collapse;width:100%;margin:8px 0 24px}
td,th{border:1px solid #ccc;padding:4px 6px;vertical-align:top;text-align:left}
th{background:#f2f2f2}
td.r{font-weight:bold}tr.f td.r,td.r.f{background:#fbe3e3}tr.p td.r,td.r.p{background:#e5f4e5}
tr.n td.r,td.r.n{background:#eeeeee}tr.u td.r,td.r.u{background:#fff4d6}
code{font-size:12px;white-space:pre-wrap;font-family:Consolas,monospace}.s{color:#666;font-size:12px}
.banner{background:#fff4d6;border:1px solid #e0c060;padding:.6rem 1rem;margin:1rem 0}
.fake{background:#fbe3e3;border:1px solid #d08080;padding:.6rem 1rem;margin:1rem 0}
h2{margin-top:2rem;border-bottom:1px solid #ccc}h3{margin:1.4rem 0 .3rem}
"""

_ROW_CLASS = {
    RESULT_PASS: "p",
    RESULT_FAIL: "f",
    RESULT_NOT_GRADED: "n",
    RESULT_UNFINISHED: "u",
    "PASS": "p",
    "FAIL": "f",
    VERDICT_NOT_GRADED: "n",
}


def _when(at: datetime) -> str:
    """A recorded time, in UTC to the second. The record stores naive UTC."""
    return at.strftime("%Y-%m-%d %H:%M:%S") + " UTC"


def _module_order(module: str) -> tuple[int, str]:
    """The generator's module order, then any other by name."""
    return (READ_MODULES.index(module) if module in READ_MODULES else len(READ_MODULES), module)


def _code(value: Any) -> str:
    if value is None or value == {} or value == []:
        return ""
    text = value if isinstance(value, str) else json.dumps(value, indent=1, sort_keys=True)
    return f"<code>{escape(text)}</code>"


def _key_text(key: TurnKey) -> str:
    parts = [f"ACT {_expected_act(key)}", f"RECORD {_expected_record(key)}"]
    if key.record_claim_options:
        parts.append("claim one of: " + " | ".join(key.record_claim_options))
    if key.expected_caveat:
        parts.append(f"CAVEAT (present): {key.expected_caveat}")
    return "\n".join(parts)


def _answer_text(payload: Mapping[str, Any]) -> str:
    if "unreadable" in payload:
        return f"unreadable: {payload['unreadable']}"
    given = _given_record(payload)
    parts = [
        f"ACT {payload.get('act')}",
        "RECORD " + (f"{given[0]}: {given[1]}" if given else "none"),
    ]
    caveats = payload.get("caveats") or ()
    parts.append("CAVEAT " + (" / ".join(str(c) for c in caveats) if caveats else "none"))
    return "\n".join(parts)


def _step_row(step: SandboxStep, task: Task | None, tasks: Mapping[str, Task] | None) -> str:
    payload = step.payload or {}
    expected = given = ""
    if step.step == "filed":
        given = _code(payload.get("facts")) + "<br>" + _code(payload.get("request"))
    elif step.step == "claimed":
        given = f"<code>{escape(step.agentId or '')}</code>"
    elif step.step in ("turn_a", "turn_b"):
        if task is not None:
            expected = _code(_key_text(task.turn_a if step.step == "turn_a" else task.turn_b))
        given = _code(_answer_text(payload))
    elif step.step == "proposed":
        if task is not None:
            expected = _code({"module": task.module_id, "request": task.request})
        given = _code({"module": step.moduleId, "request": payload.get("request")})
    elif step.step == "approved":
        given = f"approved by <code>{escape(step.actor)}</code> at {escape(_when(step.at))}"
    elif step.step == "forge_answer":
        if task is not None:
            expected = _code(task.forge_answer)
        given = _code(payload)
    if step.step == "forge_answer":
        result = "as predicted" if step.forgeMatches else "differs"
        cls = "p" if step.forgeMatches else "n"
    elif step.verdict:
        result, cls = step.verdict.replace("_", " "), _ROW_CLASS.get(step.verdict, "")
    else:
        result, cls = "", ""
    ids = ", ".join(f"{k} {v}" for k, v in sorted((step.sandboxIds or {}).items()))
    return (
        "<tr>"
        f"<td>{step.seq}</td><td><b>{escape(_STEP_TITLES[step.step])}</b>"
        + (f"<br><span class=s>{escape(ids)}</span>" if ids else "")
        + f"</td><td>{escape(_when(step.at))}</td><td>{escape(step.actor)}</td>"
        f"<td>{expected}</td><td>{given}</td>"
        f"<td class='r {cls}'>{escape(result)}</td>"
        f"<td>{escape('; '.join(_step_whys(step, tasks)))}</td>"
        "</tr>"
    )


def _counts_table(
    run: SandboxRun,
    by_task: Mapping[str, list[SandboxStep]],
    tally: Mapping[str, Any] | None,
    module_of: Mapping[str, str],
) -> str:
    agent_of = {
        t: next((s.agentId for s in mine if s.agentId), None) or "unclaimed"
        for t, mine in by_task.items()
    }
    head = (
        "<tr><th>by</th><th></th><th>tasks</th><th>finished</th><th>tasks passing</th>"
        "<th>Turn A<br><span class=s>pass / fail</span></th>"
        "<th>Turn B<br><span class=s>pass / fail / not graded</span></th>"
        "<th>Forge mismatches</th></tr>"
    )
    rows = []

    def line(kind: str, name: str, ids: list[str], t: Mapping[str, Any] | None) -> str:
        passing = sum(task_result(by_task[i]) == RESULT_PASS for i in ids)
        finished = sum(task_ended(by_task[i]) for i in ids)
        if t is None:
            a = b = mism = "?"
        else:
            a = f"{t['turn_a']['PASS']} / {t['turn_a']['FAIL']}"
            b = f"{t['turn_b']['PASS']} / {t['turn_b']['FAIL']} / {t['turn_b'][VERDICT_NOT_GRADED]}"
            mism = str(t["forge_mismatches"])
        tag = "th" if kind == "all" else "td"
        return (
            f"<tr><{tag}>{escape(kind)}</{tag}><{tag}>{escape(name)}</{tag}>"
            f"<{tag}>{len(ids)}</{tag}><{tag}>{finished}</{tag}>"
            f"<{tag}>{passing} / {len(ids)}</{tag}><{tag}>{a}</{tag}><{tag}>{b}</{tag}>"
            f"<{tag}>{mism}</{tag}></tr>"
        )

    modules = sorted(set(module_of.values()), key=_module_order)
    for m in modules:
        ids = [t for t in run.taskIds if module_of[t] == m]
        rows.append(line("module", m, ids, (tally or {}).get("module", {}).get(m)))
    for a in sorted(set(agent_of.values())):
        ids = [t for t in run.taskIds if agent_of[t] == a]
        rows.append(line("agent", a, ids, (tally or {}).get("agent", {}).get(a)))
    rows.append(line("all", "", list(run.taskIds), (tally or {}).get("all")))
    return f"<table>{head}{''.join(rows)}</table>"


def render_run_page(
    run: SandboxRun, steps: Sequence[SandboxStep], *, fake_note: str | None = None
) -> str:
    """The page for one run. `fake_note`, when given, is shown first, in red: the demo's."""
    by_task: dict[str, list[SandboxStep]] = {t: [] for t in run.taskIds}
    for s in steps:
        by_task[s.taskId].append(s)
    tasks: dict[str, Task] | None
    try:
        tasks = tasks_of(run)
        moved = ""
    except SandboxRefused as exc:
        if exc.code != "generator_moved":
            raise
        tasks = None
        moved = (
            "<div class=fake><b>The generator has moved</b> since this run opened "
            f"({escape(str(exc))}). The expected answers are not shown; the verdicts are the "
            "ones recorded when each step was graded.</div>"
        )
    module_of = {
        t: (tasks[t].module_id if tasks else next((s.moduleId for s in by_task[t]), "?"))
        for t in run.taskIds
    }
    if run.totals is not None:
        tally, tally_note = run.totals, "the totals written when the run closed"
    elif tasks is not None:
        tally, tally_note = totals(run, steps), "the run is still open: the totals so far"
    else:
        tally, tally_note = None, "the run is open and the generator moved: turn counts not shown"

    index_rows = []
    sections: dict[str, list[str]] = {}
    for task_id in run.taskIds:
        mine = by_task[task_id]
        task = tasks.get(task_id) if tasks else None
        result = task_result(mine)
        agent = next((s.agentId for s in mine if s.agentId), None) or "unclaimed"
        verdict = {s.step: s.verdict for s in mine if s.step in ("turn_a", "turn_b")}
        cls = _ROW_CLASS[result]
        line = task_why(mine, tasks)
        anchor = f"task-{escape(task_id)}"
        klass = f" ({escape(task.scenario_class)})" if task else ""
        index_rows.append(
            f"<tr class={cls}><td><a href='#{anchor}'><b>{escape(task_id)}</b></a>"
            f"<br><span class=s>{escape(module_of[task_id])}{klass}</span></td>"
            f"<td>{escape(agent)}</td>"
            f"<td>{escape((verdict.get('turn_a') or '-').replace('_', ' '))}</td>"
            f"<td>{escape((verdict.get('turn_b') or '-').replace('_', ' '))}</td>"
            f"<td class=r>{escape(result)}</td><td>{escape(line)}</td></tr>"
        )
        body = "".join(_step_row(s, task, tasks) for s in mine)
        if not task_ended(mine):
            done = mine[-1].step if mine else None
            nxt = STEPS[STEPS.index(done) + 1] if done else STEPS[0]
            body += (
                f"<tr class=u><td></td><td><b>{escape(_STEP_TITLES[nxt])}</b></td>"
                f"<td colspan=4>not recorded: the run closed with this task waiting here</td>"
                f"<td class=r>{RESULT_UNFINISHED}</td><td></td></tr>"
            )
        elif (
            mine
            and mine[-1].step == "turn_a"
            and (mine[-1].payload or {}).get("act") != ACT_PROCEED
        ):
            body += (
                "<tr><td></td><td colspan=7 class=s>Turn A was not PROCEED, so nothing was "
                "called and there is no Turn B.</td></tr>"
            )
        sections.setdefault(module_of[task_id], []).append(
            f"<h3 id='{anchor}'>{escape(task_id)}{klass} &middot; {escape(agent)} &middot; "
            f"<span class='r {cls}'>{escape(result)}</span></h3>"
            + (f"<p class=s>{escape(line)}</p>" if line else "")
            + "<table><tr><th>#</th><th>step</th><th>at</th><th>actor</th><th>expected</th>"
            "<th>given / recorded</th><th>result</th><th>why</th></tr>" + body + "</table>"
        )

    ordered = sorted(sections, key=_module_order)
    detail = "".join(f"<h2>{escape(m)}</h2>" + "".join(sections[m]) for m in ordered)
    when = escape(_when(run.startedAt)) + (
        f" to {escape(_when(run.endedAt))}" if run.endedAt else ", still open"
    )
    owner = f" under {escape(run.scheduleOwner)}'s schedule" if run.scheduleOwner else ""
    fake = f"<div class=fake>{fake_note}</div>" if fake_note else ""
    return f"""<!doctype html>
<html lang=en><head><meta charset=utf-8>
<title>Sandbox run {escape(run.runRef)}</title><style>{_STYLE}</style></head><body>
<h1>Sandbox run {escape(run.runRef)}</h1>
{fake}
<p class=s>{escape(run.venture)} &middot; {escape(run.forgeId)} sandbox &middot; seed {run.seed}
&middot; world <code>{escape(run.worldName)}</code> &middot; generator
{escape(run.generatorVersion)} &middot; world <code>{escape(run.worldDigest)}</code> &middot;
tasks <code>{escape(run.tasksDigest)}</code><br>
Started by {escape(run.startedBy)}{owner} &middot; {when} &middot; {escape(run.status)}
&middot; {len(run.taskIds)} tasks, {len(steps)} steps recorded</p>
<div class=banner><b>Practice only, never evidence</b> (ADR-0166 ruling 5). A sandbox run is its
own record: no exam, certification, tier or partition reads it. Each turn is graded by SimForge's
<code>grade_submitted</code> against the generator's expected answer for this seed. Turn B is
not graded when the Forge answered otherwise than predicted: that miss is the Forge's, not the
agent's.</div>
{moved}
<h2>Totals</h2>
<p class=s>Tasks passing and finished are counted from the steps; the turn counts are
{tally_note}.</p>
{_counts_table(run, by_task, tally, module_of)}
<h2>Every task</h2>
<table><tr><th>task</th><th>agent</th><th>Turn A</th><th>Turn B</th><th>result</th>
<th>why (each miss)</th></tr>{"".join(index_rows)}</table>
{detail}
</body></html>
"""
