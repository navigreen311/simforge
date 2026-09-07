# ADR-0047 — `submit_curriculum` and `run_start` on the Office bridge

**Status:** Accepted
**Date:** 2026-09-07
**Extends:** ADR-0046 (the bridge adapter) · ADR-0044 (the run window)

## Context

ADR-0046 bound one module, `gate_result`, and it is a read. That was enough to prove the
plumbing and not enough to use it: **The Office could ask for the verdict of a run it had no
way to open, against a curriculum it had no way to submit.** Both of those acts existed as
SimForge HTTP endpoints; neither was reachable with the credential The Office holds.

    submit_curriculum  ->  POST /api/operation/curriculum
    run_start          ->  POST /api/operation/run/start

## Decision

Both are bound on `/office`, both `is_mutating=True`, both `idempotency_support="natural"`.
`GET /office/_modules` now returns three.

### 1. Why they cannot stay behind `require_role`

The Office holds a **tenant credential**. It has no Clerk account, no user JWT, and no way
to obtain one — it is a machine calling a machine.

Under `AUTH_MODE=dev-bypass`, which is the local default, `require_role` returns a fixed
principal holding every role in `ALL_ROLES` and **never reads the Authorization header**.
The adapter's own docstring has said so since ADR-0046. Deferring to it would mean the
agent-facing surface of this Forge is open to any caller on every developer's machine —
and it would look authenticated, because the dependency is right there in the signature.

So these two go through the same `hmac.compare_digest` check against `OFFICE_TENANT_TOKEN`
as `gate_result`, on the same router, which is not mounted at all when that token is unset.

### 2. `submit_curriculum` is reached with the tenant credential, not an agent grant

Worth stating plainly because it is the first module on this adapter that is not about an
agent.

Every other brokered call answers a question about one agent, and `agent_forge_grant` is
what authorizes it. **A curriculum submission is not that.** The Office submits on behalf of
a **venture**, before any agent is certified for the module in question and often before the
agents exist at all. There is no `office_agent_id` whose grant could authorize it, and
minting one would put a fictional agent in the ledger for an act a venture and a human
performed.

`X-Office-Venture` is the identity that matters for this call. It is recorded in the log
line like every other header, and it is what a reader should look for when asking who
submitted a curriculum.

**The consequence, said out loud: an agent grant is not what gates this.** The Office
decides on its own side who may submit a curriculum. SimForge checks the tenant credential
and then validates the curriculum itself — the Batch-3 rules, 422 on any violation — which
is the check that actually protects anything here.

### 3. Both are `natural`, and both earn it

`natural` is the value that says "a retry lands on the same state without a key". It is the
easy value to write and the easy one to be wrong about, so:

**`run_start`** is the clearest case on the adapter. `open_run` is idempotent on `run_ref`
and returns the existing row **with its clock untouched** — a re-post answers
`already_open: true` rather than restarting the window. That refusal is exactly what makes
`natural` honest: an `at_most_once` module needs a key because a second call would do
damage, and a second call here cannot, by construction. Extending the window of a run that
is already hanging is the one thing that would hide a timeout, and `open_run` exists partly
to refuse it (ADR-0044).

**`submit_curriculum`** upserts `ForgeInstructionSet` on `(forgeId, moduleId, contentHash)`.
Re-posting the same curriculum lands on the same row rather than accumulating a second
instruction set. A *different* `content_hash` is a different instruction set and should
produce a new row — that is not a retry, it is a new submission, and the distinction is the
whole point of binding a certification to a content hash.

### 4. The `after_flush` guard does not run for these, by design

Stated because the opposite is easy to assume. The listener from ADR-0046 is installed only
when `is_mutating=False`:

```python
listening = not spec.is_mutating
```

It exists to catch a module that **claims to be a read** and writes. A module that declared
itself a writer is allowed to write, and both of these flush and commit. The guard is not
weakened by binding writers; it simply has nothing to say about them.

`test_the_two_writers_may_write` is the assertion that keeps that honest — without it, a
guard that refused *every* write would look identical to a correct one until somebody bound
a writer, which is exactly what has now happened.

### 5. The manifest is still derived

`sorted(MODULES.items())` — unchanged, and `test_manifest_is_derived_from_the_dispatch_map`
still fails the build if it becomes a literal list. Three entries appear because three
handlers are bound, not because a number was updated.

### 6. The handlers call the endpoints, not copies of them

`_submit_curriculum` and `_run_start` call `submit_curriculum(...)` and
`start_operation_run(...)` directly. A second implementation of the Batch-3 validation, the
instruction-set upsert, or the run-window guards would be a second thing to keep correct —
the reason CRE Forge's adapter calls its service layer rather than re-querying.

The payload is parsed with the model the endpoint already declares
(`ForgeOperationCurriculum`, `OperationRunStartRequest`), so the schema has one home. A
malformed payload comes back 422 carrying Pydantic's own field-level errors rather than a
summary somebody has to maintain.

**A rejection is a 422, not a 200 carrying `accepted: false`.** The Office's executor
records a non-2xx as a real outcome that belongs in the ledger; a 200 over a rejected
curriculum would be a plausible success, which is the shape this whole adapter exists to
avoid.

## Consequences

- Two modules SimForge dispatches that no Pack declares. `verify_forge_modules` will report
  them as **DRIFT** — "dispatched by the Forge and unknown to the registry. Not added — a
  Forge does not enlarge its own agent-facing surface." That is the correct outcome:
  somebody decides whether The Office should know about them, and writes the registry rows
  from the manifest.
- `run_scenario_pack` is still unbound and V32 still FAILs on it. Unchanged by this
  (`theoffice/docs/decisions.md` entry 5).
- Additive. `gate_result` is untouched; with `OFFICE_TENANT_TOKEN` unset the router is still
  not mounted.
- 12 new tests, including the two that would catch this being got wrong in the ways above:
  the clock not restarting on a re-post, and a retry not producing a second instruction set.

## A note on how the tests were written

The first version of the curriculum fixture invented eight plausible-looking scenario class
names. The validator rejected every one, correctly. The fixture now derives them from
`ALL_SCENARIO_CLASSES` — the same reason the manifest iterates the dispatch map. A list
maintained beside the real one drifts, and this one was wrong on the day it was written.
