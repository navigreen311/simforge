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
