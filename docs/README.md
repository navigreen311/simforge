# SimForge docs

Reference material for the SimForge platform. Start with the blueprint and spec; the rest is
organized by concern.

## Core

| Doc | What it covers |
|-----|----------------|
| [BLUEPRINT.md](BLUEPRINT.md) | System architecture and the module map. |
| [SPEC.md](SPEC.md) | Canonical specification. |
| [SIMFORGE.md](SIMFORGE.md) | Product overview. |
| [ROADMAP.md](ROADMAP.md) | Phasing and what ships when. |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev workflow, conventions, the PR loop. |
| [DECISIONS.md](DECISIONS.md) · [adr/](adr) | Architecture decision records. |

## Operations

| Doc | What it covers |
|-----|----------------|
| [deploy.md](deploy.md) | Deployment + the seam-activation checklist. |
| [RUNBOOKS/](RUNBOOKS) | On-call runbooks. |
| [grafana.md](grafana.md) | Dashboards-as-code. |
| [pdp-pep.md](pdp-pep.md) | Policy Decision / Enforcement Point runtime authorization. |
| [security.md](security.md) | Security posture. |
| [calibration/](calibration) | Evaluator calibration reports. |

## Forge Operation Certification

A certification unit at agent × forge × module — whether an agent can *operate the software*,
kept entirely separate from the domain rubric.

- **[operation-rubric-proposal.md](operation-rubric-proposal.md)** — the approved operation rubric
  (5 dimensions, first-class `not_applicable`, each mapped to a scenario class).
- **[adr/ADR-0044-operation-run-window.md](adr/ADR-0044-operation-run-window.md)** — the **run
  window**: how a battery that never finishes resolves. It used to resolve to nothing at all —
  no row, no verdict, no error — leaving the previous certification in place. It now resolves to
  `TIMEOUT`, which never resolves to a pass and is never recorded as a failure.
- **[adr/ADR-0046-office-bridge-adapter.md](adr/ADR-0046-office-bridge-adapter.md)** — the
  **Office bridge**: `GET /office/_modules` and `POST /office/{module_id}`. `gate_result` is
  bound; `run_scenario_pack` deliberately is not, because SimForge has no pack-level unit of
  execution and a handler that ran one scenario would be a plausible 200.
- **[adr/ADR-0047-two-more-modules-on-the-office-bridge.md](adr/ADR-0047-two-more-modules-on-the-office-bridge.md)**
  — `submit_curriculum` and `run_start` bound alongside it. Why they cannot sit behind
  `require_role` (under `dev-bypass` it holds every role and never reads the header), and why
  `submit_curriculum` is reached with the **tenant credential rather than an agent grant** —
  The Office submits on behalf of a venture, not as an agent.
- **[adr/ADR-0045-deploy-pipeline-is-a-scaffold.md](adr/ADR-0045-deploy-pipeline-is-a-scaffold.md)**
  — `deploy-staging.yml` has been green on every push to main for months while running only
  `echo`. Nothing here has ever been deployed.
- **[adr/ADR-0048-the-never-do-trap.md](adr/ADR-0048-the-never-do-trap.md)**
  — **resolved 2026-09-08 (P-03).** The validator used to reject a submission whose declared
  never-do list had no `never_do_violation` scenario — a held-out class the submitter may not
  author — so no correct submission could declare a never-do list at all. Path B: the demand is
  gone, the obligation is recorded, and its coverage is decided at scoring time, where the
  held-out scenarios are. **The refusal moved; it was not deleted.** Ruled with it: a submitted
  held-out scenario is now refused, because accepting one let the certified party supply its own
  refusal test.
- **[adr/ADR-0049-a-declared-not-applicable-for-scenario-classes.md](adr/ADR-0049-a-declared-not-applicable-for-scenario-classes.md)**
  — **accepted, and built** (P-02 the primitive, P-03 the enforcement). The curriculum
  validator asked every module for the same scenario classes, and modules differ in kind. A
  class a module genuinely cannot have is now DECLARED `not_applicable` with a required prose
  reason and admitted; a class neither supplied nor declared is still refused.
  `classify_certification_level` gains a third level rather than widening `certified`, so the
  cap stops being silent without being lifted.
- **[adr/ADR-0050-no-credential-fetches-the-held-out-set.md](adr/ADR-0050-no-credential-fetches-the-held-out-set.md)**
  — **delivery, not retrieval.** No endpoint hands out a held-out probe and none triggers a battery;
  the runner is reached process-side, and `test_no_request_handler_can_construct_a_probe` keeps the
  walk from the router closed.
- **[adr/ADR-0051-an-agent-under-certification-answers-in-a-declared-grammar.md](adr/ADR-0051-an-agent-under-certification-answers-in-a-declared-grammar.md)**
  — **accepted (P-18).** An LLM returns prose and the grader wants structure. Neither bridge is
  built — no word list over the answer, no second model judging it. The agent answers in a
  class-invariant grammar and the runner transcribes; an unreadable answer is NOT_RUN, never a FAIL.
- **[adr/ADR-0052-the-channel-is-its-own-dimension.md](adr/ADR-0052-the-channel-is-its-own-dimension.md)**
  — **accepted, and built.** The first real battery run split: the model refused all five forbidden
  acts and answered none of them in the grammar. *Did it refuse* and *can it structure the refusal*
  are orthogonal, and one NOT_RUN was carrying both. `protocol_conformance` (rubric **0.2.0**) is a
  sixth dimension mapped to every class, **excluded from the spread pool** because pooling it would
  weaken the collapse check as it grew more informative, and it **never discharges** the never-do
  coverage hole. Also closes a reachable gap it found on the way: an agent unreadable throughout, on
  a module with no never-do list, used to reach `certified`.
- **[contracts/office-simforge-contract.json](contracts/office-simforge-contract.json)** — the
  vocabulary The Office and SimForge share, asserted from both sides. The canonical copy lives in
  The Office; `contract_version` is what says the two copies are the same generation.
- **[operation-certs.html](operation-certs.html)** — a **static export of the operation-certs
  dashboard**. A single self-contained file (inlined CSS/JS, no server, no external assets): open it
  directly in a browser to see the board — agents across all states (certified / failed / stale /
  revoked-VOID), each domain cert and operation cert **side by side** with its own denominator and
  version stamp, plus coverage, capacity, Unit-B context, and incidents.

  Regenerate it against live data (same composed read-views the live page uses, so it can't drift
  from the contract):

  ```
  apps/api/.venv/Scripts/python.exe scripts/export_operation_certs.py
  ```

  Or leave a **watcher** running — it re-renders automatically whenever the operation-cert data
  changes, however you seed it (script, API, or manual insert):

  ```
  apps/api/.venv/Scripts/python.exe scripts/watch_operation_certs.py   # Ctrl+C to stop
  ```

  Template + generator + watcher live in [`scripts/`](../scripts) (`operation-certs.template.html`,
  `export_operation_certs.py`, `watch_operation_certs.py`).
