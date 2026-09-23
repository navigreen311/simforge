# ADR-0111 — The Office asks Gate 9.5 and learns whether, never why

**Status:** accepted · **Decided by:** Ivan Green, 2026-09-23
**Implements:** ADR-0108 R4, R5 · **Constrained by:** ADR-0050

---

## The problem

The Office's port is `HeldOutSource.verdict(venture_id) -> str | None`.
It had nothing to call. ADR-0108 fixed the answer's shape on a page
(`docs/contracts/gate-9-5-verdict.md`) before anything answered it.
This ADR builds the thing that answers, and nothing more.

## The ruling

> **R1.** Office bridge module `gate_9_5_verdict`, behind the tenant
> credential, like `gate_result`. `is_mutating=False`,
> `idempotency_support="natural"`. The read-only check in `call_module`
> holds it to that.

> **R2.** The answer is the page's four keys, always, in this order:
> `venture_id`, `partition_exists`, `verdict`, `decided_at`.
> **This shape is the thing The Office will record.** It is validated on
> the way out (`Gate95VerdictResponse`, `extra="forbid"`), so a fifth
> key is a 500 here, not a surprise there.

> **R3.** The rules are the page's table, verbatim:
> only the currently sealed partition counts; per agent, only the latest
> verdict whose `partitionDigest` equals its `contentDigest`; weakest
> wins, FAIL < TIMEOUT < IN_PROGRESS < NOT_RUN < PASS; sealed and never
> graded is NOT_RUN with `decided_at` null. `decided_at` is the chosen
> row's `decidedAt`, ISO-8601 with an explicit `+00:00`.

> **R4.** An unknown venture answers exactly like a venture with no
> sealed partition. A 4xx is auth or a malformed body. Never the venture.

> **R5.** `partition_verdict.py` reads `HeldOutPartition` and
> `HeldOutPartitionVerdict` only. It never holds a scenario, and it
> imports neither the authoring nor the grading service. A handler that
> never held content cannot leak it, whatever is later written in it.

## The adapter mapping (The Office's side, not built here)

    partition_exists == false  ->  None             (Gate 9.5: at ceiling)
    otherwise                  ->  verdict verbatim (only "PASS" passes)

No other translation. NOT_RUN, IN_PROGRESS and TIMEOUT are not
failures and not passes; The Office blocks on them by name.

## Why the answer says so little

A rich enough explanation of a failure reconstructs the scenario.
So no counts, classes, modules, scenario ids, digests, reasons or scores.
The shape is also constant: the key set is identical in every state,
so its presence or absence says nothing either.

## Tests

- `tests/integration/test_gate_9_5_verdict.py`: planted secrets never
  appear in the body (FAIL does); one key set across unknown, absent,
  authoring, NOT_RUN, PASS, FAIL, TIMEOUT and stale-digest; unknown ==
  absent; committed rows read through a fresh session, and a newer row
  changes the answer; 401 regardless of venture; no router reaches
  the scenario table or the authoring or grading services.
- `tests/contract/test_gate_9_5_verdict_contract.py`: keys, verdicts
  and weakness order are read from the page and matched to the code.

## What this does not do

- It does not build The Office's adapter.
- It does not change `office-simforge-contract.json`. The shape joins
  that file when the adapter lands, as one reviewable act.
- It does not author, seal or grade anything (ADR-0109, ADR-0110).
- It does not know about simulation. The Office's gate decides.
