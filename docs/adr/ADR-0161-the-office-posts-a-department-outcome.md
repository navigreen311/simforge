# ADR-0161 — The Office posts a department outcome through the bridge

**Status:** accepted · **Decided by:** Ivan Green, 2026-10-23 · **Built.**
Follows ADR-0062 (Unit B, option A) and ADR-0153 (an audited bridge module).

## The rulings

> - A Unit B attestation's unverified flag is PROVISIONAL (ADR-0062 option
>   A); FAILED only when the attester records a defect.
> - Attestations may be posted while a venture is in simulation.
>
> Build a mutating /office module `department_outcome`, the first write
> The Office makes through the bridge. Contract doc in docs/contracts/.

## What was wrong

No Unit B run has ever closed with a verdict. Since 1 October:
capitalforge 31, cre-forge 27, funnelforge 3 runs, every one TIMEOUT.
SimForge has written no `department_context` certification for any of them.

Nothing measures a department; `DEPARTMENT_HANDOVER_TEST` is False and
stays so. Option A was meant to carry Unit B until option B exists: a named
founder attests the two flags, and Gate 8 posts them as
`department_outcomes`. The post never arrived:

- Gate 8 posted to `{base}/gate_result`. On this bridge that is a pure read
  (`is_mutating=False`). It ignored the outcome and answered the run's
  status.
- The Office checked that answer against its `post_gate_result` manifest,
  which declares `run_ref`, `accepted`, `recorded` and `status`. No
  SimForge endpoint returns that shape. The check raised, Gate 8 recorded
  `posted: false`, and that error is non-fatal.
- The writer that would have recorded it, `POST /api/operation/gate-result`,
  is not on the bridge.

Run `01M5MTA4QF6S7BV7P4474R9WXW` (greenstone, operations, 23 October) shows
it. Its attestation was in force, the post failed on the manifest check, and
the :35 sweep stamped TIMEOUT at 20:35Z.

## What is built

**`department_outcome`**, a bridge module (`routers/office.py`), the service
`services/operation/department_outcome.py`, and the contract
`docs/contracts/department-outcome.md`.

- `is_mutating: true`, `idempotency_support: key`. The first keyed module:
  nothing in the payload makes two posts the same post by construction.
- The payload is `DepartmentOutcomeRequest` (`extra: forbid`): the run ref,
  the two versions the certification requires, and at least one department
  outcome. A non-empty `agent_outcomes` is refused by name. A Unit A verdict
  is earned by the battery and is never posted.
- Checked in order:
  1. the key;
  2. the payload;
  3. the ADR-0153 lookup (Office-minted ref, venture header present and
     equal to the ref's, run exists), one 404 whatever the cause;
  4. a retry with the same key and payload, answered from the first call's
     row;
  5. the run itself: Unit B, the outcome names its department and forge, no
     verdict yet. TIMEOUT does not count as a verdict: a late outcome is
     recorded, as `close_run` already holds.
- The state is not decided here. The module builds a `GateResultRequest`
  from the run (its forge, its content hash on both sides, its sitting) and
  calls `routers.operation.gate_result`, the writer every gate result goes
  through, the way `submit_battery_result` calls it.
- The reply is `DepartmentOutcomeReply`: four keys, validated on the way out.
  The verdict travels back through `gate_result` like every other.

**Audit.** `DepartmentOutcomePost`, one row per call with the credential,
refusals included, in the shape of `SubmittedAnswerRead`. It also carries
the idempotency key and a payload digest. A recorded row is added before the
writer commits, so the certification and its audit row become permanent
together. A partial unique index allows one recorded row per key. A
concurrent duplicate that loses it is answered as the retry it is.

## The rulings, where they land

- **Unverified is provisional.** The writer already maps `passed: true` with
  a flag false to `provisional`, and `passed: false` to `failed`. That
  matches the ruling only if `passed: false` means a recorded defect.
  The Office decides what it sends, and today it sends `passed` = both flags
  verified. That would post today's attestations (escalation path true,
  compliance coupling false) as FAILED. **The Office's change, not this
  one's:** send `passed: true` unless the attester recorded a defect.
- **Simulation.** SimForge does not read whether a venture is in simulation,
  and this module adds no check for it. The ruling is satisfied here; any
  gate on The Office's side is The Office's to lift.

## What The Office must change

1. Post to `department_outcome`, not `gate_result`, with an
   `Idempotency-Key`.
2. Send `instruction_version` and `forge_api_version` as strings. Gate 8
   sends None today; the certification requires both.
3. Send `passed` per the ruling above.
4. Its manifest entry `post_gate_result` already names the reply's four
   keys. Rename it to the module if it wishes; the keys do not change.

## Versions

- No protocol bump: nothing the agent sees or answers changed.
- No rubric bump: no grader changed, and the state mapping is ADR-0062's.
- Migration `20261023000000_department_outcome_post` adds the audit table and
  its partial unique index.

## Tests

`tests/integration/test_department_outcome.py`:

- a post writes the `department_context` certification and closes the run
  PASS, including after a TIMEOUT;
- the reply is exactly the four keys, with no verdict;
- agent outcomes, a Unit A run, another department, and a missing key are
  refused, and nothing is written but the audit row;
- a retry with the same key replays with no second certification; the same
  key with another payload is 409; a new key on a closed run is 409;
- each flag not verified gives `provisional` (run `PROVISIONAL`); a recorded
  defect gives `failed`;
- every lookup refusal is the same 404 and is audited; a retry under
  another venture is refused before it can replay.

`test_office_bridge.py` now lists six modules.
