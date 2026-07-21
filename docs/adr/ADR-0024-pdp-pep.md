# ADR-0024 — PDP / PEP (runtime authorization from certs)

**Status:** Accepted (2026-07-21). Supersedes the §F.6 "v1.1" placeholder.

## Context
SimForge *issues* signed certs and tracks an autonomy ladder, but nothing *consumed* them at
runtime — the platform was advisory. The blueprint (§F.6) specifies a **Policy Decision Point** (a
central "may agent X do action Y now?" engine) and **Policy Enforcement Points** (client-side SDKs
that call the PDP and cache decisions), with real-time revocation propagation (§F.4). This ADR
covers the PDP decision engine + API + metrics; the Redis revocation channel and the PEP SDK follow
in sibling PRs behind the same design.

## Decision
- **PDP engine** (`services/governance/pdp.py`) — `PDP.decide(session, AuthRequest) -> AuthDecision`.
  `AuthRequest(subject_agent_id, action, resource?, context)`; `AuthDecision(decision, reason_code,
  reason_detail, ttl_seconds, required_approver?, fail_policy)`. Decisions are the blueprint's four:
  `allow | deny | step_up_approval_required | downgrade_and_retry`.
- **Decision model** — derived from the agent's cert for the action + its autonomy level + safe-mode:
  - safe-mode active → **step_up_approval_required** (everything needs a human).
  - no / suspended / revoked / expired cert → **deny** (with a specific reason code).
  - active cert, mapped by autonomy ladder: **L4/L5 → allow**, **L3 → step_up_approval_required**
    (exec + approval), **L2 → downgrade_and_retry** (draft only), **L1 → deny** (observe only).
  - `ttl_seconds` per decision (allow 60, step-up/downgrade 30, expired 15, safe-mode 10) tells the
    PEP how long to cache.
- **Fail-open/closed** (§F.6) — `fail_policy_for(action)` annotates each decision with what a PEP
  should do if it *can't reach* the PDP. Default **fail-closed** for all compliance-adjacent Forges
  (every current Forge). This is the PEP's outage behavior, not a normal deny.
- **API** `/api/pdp` — `POST /decide` (the endpoint PEPs call; read-only) and
  `GET /agent/{id}/effective` (a decision per cert the agent holds, for dashboards/audit).
- **Metrics** — `simforge_pdp_decision_latency_seconds{decision}` + `simforge_pdp_decisions_total{
  decision, reason_code}` (and a `simforge_pdp_cache_hit_ratio` gauge the PEP will set).

## Consequences
- Certs are now **enforceable**: a revoked/suspended/expired cert immediately flips the PDP decision
  to deny; autonomy changes flow through (drift-suspend + demote → deny). The governance layer moves
  from advisory to operational.
- Read-only and sandbox-safe — the PDP only *reads* cert/agent state; it performs no writes and does
  not touch the Village. Decisions are pure functions of persisted governance state.
- Follow-ups (sibling PRs): Redis `simforge:revocations` publisher for real-time invalidation, and
  the PEP SDK (in-process TTL cache + subscriber + 24h graceful-degradation downgrade).

## Status of the series (complete)
Delivered across four PRs: (1) PDP engine + API + metrics; (2) Redis `simforge:revocations`
publisher hooked into the cert lifecycle; (3) the PEP SDK (TTL cache + subscriber + graceful
degradation); (4) runbook R-003 + `docs/pdp-pep.md` + `scripts/pdp-pep-demo.py`. The §F.6 spec is
fully implemented: PDP `decide`, the four decisions, PEP caching + real-time invalidation,
fail-open/closed (default fail-closed), 24h graceful degradation, and both metrics. Verified live
end-to-end (enforce → revoke → real-time invalidation → deny) against Postgres + Memurai.

## Cross-references
Blueprint §F.6 (PDP/PEP), §F.4 (revocation propagation), §F.3 (autonomy ladder), §H.2 (metrics),
§J.6 (graceful degradation), ADR-0017 (drift → suspend, which the PDP now enforces), ADR-0020
(reinstate → allow again), `docs/pdp-pep.md`.
