"""What the sandbox Office did with each task, as the steps the record takes (ADR-0166 stage 7).

The runner reads each of its tasks from the sandbox Office's own database (`OFFICE_TASK_SQL`,
SELECT only) and asks `steps_to_record` which steps are new. Each step is one the Office
already wrote, with the Office's own time:

| step | from the sandbox Office |
|---|---|
| filed | `agent_task.filed_at`, by the run's starter; the facts as filed |
| claimed | `agent_task.claimed_at`, by the claiming agent |
| turn_a | the `agent_turn_a_answered` entry: its act; its caveats read off `turn_a_raw` |
| proposed | `proposal.created_at` |
| approved | `proposal.decided_at`, by `sandbox-approver` (`office_human.origin`) |
| forge_answer | `agent_task.forge_status` and `forge_body`, at the call's `ts_end` |
| turn_b | the `agent_turn_b_answered` entry: act and record; caveats off `turn_b_raw` |

An answer that broke the grammar on its last attempt is `{"unreadable": <rule>}`, the rule
the Office's `agent_answer_malformed` entry named. A step the Office has not written yet stops
the list: the record takes steps in order, so nothing after a gap is guessed.

The act and record are the ones the Office parsed (with SimForge's own parser, vendored). The
caveats are counted by the Office (`caveat_lines` on its log); their text is read off the raw
answer only to show it, and the count wins if the two disagree.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from src.models.sandbox_run import STEPS
from src.services.sandbox.record import SANDBOX_APPROVER

FORGE_ACTOR = "cre-forge-sandbox"
APPROVER_ORIGIN = "sandbox_approver"

#: One row per task of the run, as JSON, from the sandbox Office's database. SELECT only.
OFFICE_TASK_SQL = """
SELECT row_to_json(x) FROM (
  SELECT t.task_id::text, t.status, t.facts, t.filed_at, t.claimed_at,
         a.agent_name, t.turn_a_act, t.turn_a_raw, t.turn_a_attempts,
         t.turn_b_act, t.turn_b_record, t.turn_b_raw, t.turn_b_attempts,
         t.forge_status, t.forge_body, t.last_error, t.source_ref,
         p.proposal_id::text AS proposal_id, p.created_at AS proposal_at,
         p.status AS proposal_status, p.decided_at, h.origin AS decided_by_origin,
         h.display_name AS decided_by_name,
         (SELECT max(l.ts_end) FROM agent_call_ledger l WHERE l.call_id = t.call_id)
           AS call_at,
         (SELECT row_to_json(e) FROM (
            SELECT ts, subject->'caveat_lines' AS caveat_lines FROM audit_log
             WHERE event_type = 'agent_turn_a_answered' AND subject->>'task_id' = t.task_id::text
             ORDER BY audit_id DESC LIMIT 1) e) AS turn_a_entry,
         (SELECT row_to_json(e) FROM (
            SELECT ts, subject->'caveat_lines' AS caveat_lines FROM audit_log
             WHERE event_type = 'agent_turn_b_answered' AND subject->>'task_id' = t.task_id::text
             ORDER BY audit_id DESC LIMIT 1) e) AS turn_b_entry,
         (SELECT json_agg(e ORDER BY e.audit_id) FROM (
            SELECT audit_id, ts, subject->>'turn' AS turn, subject->>'reason' AS reason,
                   (subject->>'attempt')::int AS attempt
              FROM audit_log WHERE event_type = 'agent_answer_malformed'
               AND subject->>'task_id' = t.task_id::text) e) AS malformed,
         EXISTS (SELECT 1 FROM audit_log WHERE event_type = 'agent_turn_a_skipped'
                  AND subject->>'task_id' = t.task_id::text) AS turn_a_skipped
    FROM agent_task t
    LEFT JOIN office_agent_identity a ON a.office_agent_id = t.claimed_by
    LEFT JOIN proposal p ON p.proposal_id = t.proposal_id
    LEFT JOIN office_human h ON h.human_id = p.decided_by
   WHERE t.sandbox_run_id = '{run_id}'
   ORDER BY t.filed_at
) x
"""

#: Format failures the Office allows before it escalates (`agent_tasks.FORMAT_ATTEMPTS`).
FORMAT_ATTEMPTS = 2
_CAVEAT = re.compile(r"^[\s*_`>#-]*CAVEAT[\s*_`]*:[\s*_`]*(.*?)[\s*_`]*$", re.IGNORECASE)


@dataclass(frozen=True)
class NewStep:
    step: str
    at: datetime
    actor: str
    payload: dict[str, Any]
    sandbox_ids: dict[str, str] = field(default_factory=dict)
    agent_id: str | None = None


def rows(out: str) -> list[dict[str, Any]]:
    """`OFFICE_TASK_SQL`'s rows from psql's output, one JSON value after another. Not one per
    line: Postgres's json_agg puts a newline between array elements, so a task with two or more
    malformed answers spans lines (the runner's "intermittent" JSONDecodeError)."""
    found: list[dict[str, Any]] = []
    decoder = json.JSONDecoder()
    at = 0
    while True:
        while at < len(out) and out[at].isspace():
            at += 1
        if at == len(out):
            return found
        value, at = decoder.raw_decode(out, at)
        found.append(value)


def when(value: Any) -> datetime:
    """A Postgres timestamptz from row_to_json, as naive UTC (how the record stores time)."""
    if isinstance(value, datetime):
        moment = value
    else:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC).replace(tzinfo=None)
    return moment


def caveats(raw: str | None, counted: Any) -> list[str]:
    """The CAVEAT lines of an answer. The Office's count decides how many there are."""
    found = [m.group(1) for line in (raw or "").splitlines() if (m := _CAVEAT.match(line))]
    try:
        n = int(counted)
    except (TypeError, ValueError):
        return found
    if len(found) == n:
        return found
    return [f"(caveat {i + 1} of {n}, as the Office counted it)" for i in range(n)]


def _final_malformed(row: Mapping[str, Any], turn: str) -> Mapping[str, Any] | None:
    """The malformed entry that ended a turn: the last attempt broke the grammar too."""
    tries = [m for m in row.get("malformed") or () if (m.get("turn") or "").upper() == turn]
    if tries and int(tries[-1].get("attempt") or 0) >= FORMAT_ATTEMPTS:
        return tries[-1]
    return None


def _turn_a(row: Mapping[str, Any]) -> tuple[datetime, dict[str, Any]] | None:
    entry = row.get("turn_a_entry")
    if entry and row.get("turn_a_act"):
        return when(entry["ts"]), {
            "act": row["turn_a_act"],
            "record": None,
            "caveats": caveats(row.get("turn_a_raw"), entry.get("caveat_lines")),
        }
    bad = _final_malformed(row, "A")
    if bad:
        return when(bad["ts"]), {"unreadable": bad["reason"]}
    return None


def _turn_b(row: Mapping[str, Any]) -> tuple[datetime, dict[str, Any]] | None:
    entry = row.get("turn_b_entry")
    if entry and row.get("turn_b_act"):
        record = row.get("turn_b_record")
        return when(entry["ts"]), {
            "act": row["turn_b_act"],
            "record": (
                {"subject": record.get("subject"), "claim": record.get("claim")}
                if isinstance(record, Mapping)
                else None
            ),
            "caveats": caveats(row.get("turn_b_raw"), entry.get("caveat_lines")),
        }
    bad = _final_malformed(row, "B")
    if bad:
        return when(bad["ts"]), {"unreadable": bad["reason"]}
    return None


def available(row: Mapping[str, Any], *, starter: str, run_ref: str) -> list[NewStep]:
    """Every step the Office has written for this task, in order, up to the first gap."""
    ids = {"office_task": row["task_id"], "office_run": run_ref}
    agent = row.get("agent_name")
    out: list[NewStep] = []
    facts = dict(row.get("facts") or {})
    request = {k: v for k, v in facts.items() if k != "instruction"}
    out.append(
        NewStep(
            "filed",
            when(row["filed_at"]),
            starter,
            {"facts": facts.get("instruction"), "request": request},
            ids,
        )
    )
    if not row.get("claimed_at") or not agent:
        return out
    out.append(NewStep("claimed", when(row["claimed_at"]), agent, {}, ids, agent))
    turn_a = _turn_a(row)
    if turn_a is None:
        return out
    out.append(NewStep("turn_a", turn_a[0], agent, turn_a[1], ids))
    if turn_a[1].get("act") != "PROCEED" or not row.get("proposal_at"):
        return out
    proposal = {**ids, "proposal": row["proposal_id"]}
    out.append(NewStep("proposed", when(row["proposal_at"]), agent, {"request": request}, proposal))
    if row.get("proposal_status") not in ("approved", "executed") or not row.get("decided_at"):
        return out
    approver = (
        SANDBOX_APPROVER
        if row.get("decided_by_origin") == APPROVER_ORIGIN
        else str(row.get("decided_by_name"))
    )
    out.append(NewStep("approved", when(row["decided_at"]), approver, {}, proposal))
    if row.get("forge_status") is None:
        return out
    body = row.get("forge_body")
    answer = {
        "status": row["forge_status"],
        **(body if isinstance(body, Mapping) else {"body": body}),
    }
    at = when(row.get("call_at") or row["decided_at"])
    out.append(NewStep("forge_answer", at, FORGE_ACTOR, answer, proposal))
    turn_b = _turn_b(row)
    if turn_b is None:
        return out
    out.append(NewStep("turn_b", turn_b[0], agent, turn_b[1], ids))
    return out


def steps_to_record(
    row: Mapping[str, Any], recorded: Sequence[str], *, starter: str, run_ref: str
) -> list[NewStep]:
    """The steps not yet recorded for this task. `recorded` is the step names already in the
    record for it, which are always a prefix of `STEPS`."""
    assert list(recorded) == list(STEPS[: len(recorded)]), recorded
    return available(row, starter=starter, run_ref=run_ref)[len(recorded) :]


def office_status(row: Mapping[str, Any]) -> str:
    """The Office's own status for a task, with its last error, for the run's summary."""
    status = str(row.get("status"))
    if row.get("turn_a_skipped"):
        status += " (the Office skipped Turn A)"
    return status + (f": {row['last_error']}" if row.get("last_error") else "")
