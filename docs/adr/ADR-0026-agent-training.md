# ADR-0026 — Agent training loop (approval-gated)

**Status:** Accepted (2026-07-21).

## Context
The platform *certifies* agents but never *improved* them — the loop was open. The blueprint (§L.4)
lists agent training as a deferral: use eval feedback to make agents better. Done naively this is
dangerous (an auto-tuning agent could drift its behavior past what was certified), so the design
must keep the human and the certification layer in the loop. This is the companion to integrated
execution (ADR-0025): together they close the certifier → *improver* loop.

## Decision
- **Weakness → proposal, never auto-apply.** `analyze_run_for_training(session, run_id)` reads a
  run's scorecard; if an **LLM-judge** dimension (P7 CX, C1 breath-coherence, C2 soul-stability — the
  ones a prompt can actually move) is below 0.60, it generates a **`TrainingProposal`**: the weak
  dims, a targeted prompt refinement (addendum), and a bumped prompt version. `autoApplied` is
  always false. Heuristic dims (P1–P6, P8, C3–C7) are out of scope — a prompt tweak shouldn't be
  proposed for a latency or process-fidelity miss.
- **Approval promotes + re-certifies.** `approve_proposal(id, approver)` sets the proposal approved,
  promotes the agent's prompt version, and **suspends every active cert pinned to the old prompt
  version** — exactly the drift/amendment auto-suspend mechanism (ADR-0017). Those certs must be
  **reinstated** (re-certified, ADR-0020) against the improved prompt before the agent can act on
  them again; the PDP (ADR-0024) denies them until then, and a `simforge:revocations` event
  invalidates PEP caches. An improvement therefore *cannot* silently bypass governance.
- **Reject** closes a proposal without effect. Approve/reject are terminal (a reviewed proposal
  can't be re-actioned).
- **API** `/api/training` — `POST /proposals/from-run/{run}` (generate; null if the run scored
  well), `GET /proposals` (list, filter by agent/status), `POST /proposals/{id}/approve` (admin),
  `POST /proposals/{id}/reject` (admin).

## Consequences
- The loop is closed and *safe*: run → eval → (weak?) proposal → human approval → prompt promoted →
  old certs suspended → re-certify. Better agents, but only through the same governance gate.
- New table `TrainingProposal` (Prisma schema + SQLAlchemy runtime, ADR-0003). It carries the
  proposal + its review state; approval effects live in the existing cert lifecycle, so no other
  schema changed.
- The refinement text is a deterministic heuristic addendum in v1 (auditable, offline). Swapping in
  an LLM-authored refinement is a drop-in behind `analyze_run_for_training` — and it would use the
  same provider factory (ADR-0008/0023), so CI stays hermetic.

## Cross-references
Blueprint §L.4 (agent training), ADR-0025 (integrated execution — its companion), ADR-0017
(drift-suspend, the reuse), ADR-0020 (reinstate — how a promoted-prompt cert comes back), ADR-0024
(PDP enforces the suspension), ADR-0023 (the LLM-judge signal that flags weakness).
