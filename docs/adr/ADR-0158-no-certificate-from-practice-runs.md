# ADR-0158 — No certificate from practice runs

**Status:** accepted · **Decided by:** Ivan Green, 2026-10-12 · **Built.**
The void is built and dry-run. It is not applied by this ADR.
Extends ADR-0157.

## Why

ADR-0157 ruling 1 stopped practice runs from changing certification
through four hooks. Three paths still turned practice runs into
certification:

- `issue_agent_cert` issued an AgentCert from a battery of `Run` ids.
- `reinstate_agent_cert` reinstated one the same way.
- `run_regression_sweep` (nightly worker) re-ran scenarios for fresh
  evidence. Every `Run` is a practice run, so it produced nothing that
  counts.

Nine certificates already exist on that basis.

## The ruling

> A certificate issued from practice runs is not a certification
> (ADR-0157 ruling 1), whatever model ran. Void all 7 of David Kim's
> certs and the 2 voiceforge rows, append-only, reason citing this
> ruling. Dry run first. No stacked demotions: add the skip-demotion
> flag, and set David's level once, explicitly. Refuse cert issuance
> and reinstatement from Run batteries. Pause run_regression_sweep.

"Whatever model ran" settles ADR-0157's open question on ruling 2. No
proof of a stub is needed: a practice basis is enough.

## What changes

**Issuance and reinstatement refuse, before any lookup.**
`issue_agent_cert` and `reinstate_agent_cert` raise
`PRACTICE_BATTERY_REFUSED`; both routes return 400 with it. No route
can issue an AgentCert now. Certification comes from key-graded exams
(`OperationCertification`).

The machinery is kept, unreachable from any route, as
`_issue_from_runs` and `_reinstate_from_runs`. Rebasing issuance on
exams (BACKLOG) would reuse its snapshot, signing, evidence and
lineage. Tests use it, through `tests/integration/cert_fixtures.py`,
to stand up a cert that already exists, as the pre-ADR-0158 certs do.

**`revoke_agent_cert(..., skip_demotion=True)`** skips the one-level
demotion. The default still demotes. Without the flag, voiding David's
seven certs would drop him one level per cert, from L4 to the L1
floor.

**An OperationCertification revocation is recorded.** New table
`OperationCertificationEvent` (migration
`20261012000000_operation_certification_events`): the prior state, the
actor, the reason. A trigger refuses UPDATE and DELETE on it.
`services/operation/void.py` writes the event, then sets `state` to
`revoked`.

The state is set in place, as every existing revoke path does. A
superseding row would not work: `coverage`, `capacity` and
`module_has_any_certified_agent` count every row, not only the latest,
and would still see the original as certified. The older revoke paths
in `recert.py` still overwrite without an event.

**The nightly regression re-run is paused.** `regression_worker._run`
returns `{"paused": true, ...}` before opening a session. Nothing
schedules it today; the pause holds if something does. Un-pausing is
a ruling.

## The void

`services/cert/practice_void.py`, run by
`scripts/void_practice_certs.py`. Without `--apply` it is a dry run in
a read-only transaction. With `--apply --actor "<name>"` it re-plans
and refuses if any target has moved since the ruling.

The nine targets are listed by id, with the state each held when the
ruling was given:

| target | before |
|---|---|
| AgentCert `01M03QY8…` david_kim `cre-forge.deals.title` | active |
| 6 AgentCerts, david_kim | suspended |
| OperationCertification `01M128NV…` Unit A sara_lopez × voiceforge/call_flow | certified |
| OperationCertification `01M0KHDK…` Unit B voiceforge dept (medlink-pro) | certified |

Each becomes `revoked`, with one appended event carrying the reason:

> VOID - ruling of Ivan Green, 2026-10-12 (ADR-0157 ruling 1,
> ADR-0158): issued from practice runs. A certificate issued from
> practice runs is not a certification, whatever model ran.

**The level for an agent with no valid certification is L1**
(Observe only). `autonomy_ladder.FLOOR` is where new agents start
and earn higher levels from. The PDP denies every action at L1 anyway.
After the void, David holds no active AgentCert and no certified
OperationCertification, so he is set from L4 to L1 once, with one
`AutonomyEvent`. If any certification survived, the void would refuse
rather than apply the floor.

**Dry run against the live database, 2026-10-12:** 7 AgentCerts and
2 OperationCertifications to `revoked`, David L4 to L1. Nothing
written.

## Not covered

- The older `recert.py` revoke paths still overwrite `state` without
  an `OperationCertificationEvent`.
- No route issues an AgentCert. Rebasing AgentCert on key-graded exams
  is open in BACKLOG.
- The void needs the migration applied first: the dev database has no
  `OperationCertificationEvent` table until it is.
