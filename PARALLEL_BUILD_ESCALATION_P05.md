# P-05 escalation — the held-out set is authored and graded; DELIVERING it to a battery needs a file I may not touch

**Package:** P-05 — A2, held-out authoring, both classes. **Branch:** `feature/p-05-held-out-authoring`.
**Raised under rule 2**, which says to name a file I needed and did not take, complete what can be
completed without it, and flag the gap in the PR rather than reaching outside scope quietly.

---

## What is complete

The pipeline exists end to end **inside the service layer**, for both held-out classes:

| step | where | state |
|---|---|---|
| declared `module_never_do` -> obligations | `held_out.obligations_from_never_do` | done |
| obligations -> `never_do_violation` probes | `held_out.author_for_module` | done |
| obligations -> `silent_failure` probes | same call, same input | done |
| probe + observation -> verdict | `held_out_scoring.grade_scenario` | done |
| verdicts -> `operation_rubric_results` | `held_out_scoring.grade_module` | done |
| graded results -> coverage hole closes | `never_do.is_never_do_coverage_hole` (unchanged) | done |
| graded results -> cert level moves | `scenarios.classify_certification_level(held_out_authored=...)` | done |

`grade_module` returns exactly the named-list shape `POST /api/operation/gate-result` already
consumes, so nothing in the router had to learn about this module — which is also why nothing in
the router calls it.

## What is not, and why it is a file question rather than a time question

**The operation battery is not in this repository.** `POST /gate-result` receives
`operation_rubric_results` that were computed somewhere else; the runner that does live in `src/`
(`services/runner/execute.py`) drives the Pack/Scenario domain suite and knows nothing about
operation scenario classes. So for a held-out probe to reach an agent, two things have to cross the
wire that currently cannot:

1. **A way for a battery to fetch the held-out set for a run.** There is no
   `GET /api/operation/run/{run_ref}/held-out`, and adding one means editing
   `src/routers/operation.py` and `src/schemas/operation_payloads.py`.
2. **A way for the battery to return `ObservedBehaviour` per probe.** `AgentRunOutcome` carries
   `operation_rubric_results` and `per_scenario_class_results` — both already-graded — and no field
   for the four raw observations the grader takes.

Neither file is on P-05's MAY MODIFY list, and `operation_payloads.py` is squarely the curriculum
submission contract, which the card assigns to P-01. **I did not touch either.**

## The design question that comes with it, which is not mine to settle

Whichever package takes the endpoint has to answer one thing first, and it is a governance question
rather than a plumbing one:

**Who may fetch the held-out set?** A `forge_owner` credential is what submits the curriculum. If
the same credential can fetch the probes, ADR-0048's whole refusal is undone one endpoint over — the
party being certified would be reading the refusal test it was forbidden to write. The endpoint
needs a role the submitter does not hold, and `GATE_9_5_FLAG` says the engine cannot prove that
separation holds even then.

`test_held_out_isolation.py::test_the_submitters_request_path_cannot_reach_the_authoring_module`
walks the real import graph and will FAIL the moment the authoring module becomes reachable from the
router. That is deliberate: whoever wires this in should have to look at that test and decide, rather
than discover the coupling in review.

## What I need from the coordinator

Nothing to unblock this branch — it is complete against its own card and its tests pass. This is a
**scheduling** item: the seam above is a follow-up package, and it is the last thing between an
authored held-out set and an agent actually being asked one of these questions.
