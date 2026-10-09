# ADR-0153 — The Office sees the answers to its own probes

**Status:** accepted · **Decided by:** Ivan Green, 2026-10-09 · **Built.**

## The ruling

> Store the agent's answer text for probes in The Office's own curricula
> (not held-out), so a failed probe can be shown, not inferred.
> Constraints:
> - held-out probes: never store answer text that could expose the probe;
>   the no-read-path check must still pass and cover this change
> - readable by The Office only for its own curricula; access audited
> - tests, including that held-out answer text is never stored or returned

## What was wrong

A submitted probe's answer was parsed, graded and dropped. The Office
saw reason codes on a FAIL and had to infer what the agent said. The
probe is The Office's own text, so the answer to it can be shown.

## What is stored

`SubmittedProbeAnswer`, one row per submitted probe per exam attempt:

- run ref, forge, module, instruction content hash;
- `scenarioRef` (`module#class#ordinal`), class, ordinal;
- attempt (0-based) and the seed it was put at;
- that attempt's verdict and reason codes;
- `answerText`, the provider's answer verbatim.

Written in `run_submitted_battery` only, into the battery's session. The
rows commit with the outcome they belong to, never without it.

## Why a held-out answer cannot get in

The held-out answer is never stored. An answer can quote the probe, so
this is the only safe rule. Three layers hold it:

1. **One writer.** `record_submitted_answer` is called only by
   `run_submitted_battery`, which iterates The Office's submitted keys.
   An AST test pins the single call site. Another pins that only the
   reader names `SubmittedProbeAnswer`.
2. **The writer refuses** `never_do_violation`, `silent_failure` and
   `permitted_request` before the insert.
3. **The database refuses** the same three classes (CHECK).

The test answers every held-out probe by quoting it, the worst case, and
checks that no stored row, no read response, no certification and no
gate or battery result carries it.

## Who reads

A new Office bridge module, `submitted_answers`
(`docs/contracts/submitted-answers.md`):

- the tenant credential, as for every module;
- the run ref must be Office-minted;
- `X-Office-Venture` must equal the run ref's venture segment;
- the run must exist.

Any refusal is one 404 with one message, so the call cannot probe which
runs or ventures exist. The refusal code is kept on the audit row only.

## Audit

`SubmittedAnswerRead`, one row per call with the credential, refusals
included: run ref, venture, agent id, trace, `X-Forge-Request-Id`,
outcome, refusal code, count returned. Append-only.

Handlers now receive the call's origin (the headers `call_module`
already logs) so this one can record it. The other four ignore it.

The module is declared `is_mutating: true`: the audit row is a write,
and `call_module` refuses a read-declared module that writes.

## The no-read-path check

- `test_no_router_can_reach_the_scenarios` now asserts the reader is on
  the router path, so the walk covers it, and still passes.
- The reader imports only its models and `venture_of_run_ref`. A test
  walks its imports and finds no held-out module, no grader, no battery.
- The Office router still reaches no partition content, no held-out
  scorer and no battery.

## Not done

- **The Office side.** It must declare `submitted_answers` and its keys
  in its response manifest and registry before calling it.
- **Retention.** Rows are kept indefinitely, like the outcomes table.

## Versions

None. Protocol and rubric unchanged; nothing is graded differently.
Migration `20261009000000_submitted_probe_answers` adds both tables.
