# R-003 — PDP latency spike / PEP degradation

**Trigger:** `simforge_pdp_decision_latency_seconds` p95 > 0.5s, or a drop in
`simforge_pdp_cache_hit_ratio`, or PEPs reporting `degraded_*` decisions.

## Context (what's involved)
- **PDP** — `POST /api/pdp/decide` (`services/governance/pdp.py`). A decision is a read of the
  agent's cert + autonomy + safe-mode; it performs **no writes**. Slowness here is almost always the
  DB read path, not the logic.
- **PEPs** — embed the `services/pep` SDK; each caches decisions in-process for `ttl_seconds` and
  invalidates on the `simforge:revocations` Redis channel. High PDP load usually means a low cache
  hit ratio (short TTLs, or invalidation churn).

## Response
1. **Check the metrics** at `/metrics`: `simforge_pdp_decision_latency_seconds{decision}` (which
   decision is slow?), `simforge_pdp_decisions_total{decision,reason_code}` (a spike in `deny/*` or
   `cert_expired`?), and `simforge_pdp_cache_hit_ratio` (are PEPs caching?).
2. **Redis / pub/sub** — confirm Redis is healthy (`GET /api/health`). If `simforge:revocations`
   is flapping, PEP caches are being invalidated constantly → every action hits the PDP. Find the
   source of the revocation storm (a drift-scan or amendment ratify suspending many certs).
3. **DB** — the decide path does two indexed reads (`Agent` by `villageAgentId`, `AgentCert` by
   `(agentId, forgeCap)`). If p95 is high, check DB connection-pool saturation and those indexes.
4. **Degradation is safe** — while the PDP is slow/unreachable, PEPs serve **last-known** decisions
   (fail-closed by default for compliance-adjacent actions), so Village agents keep operating at
   their last-certified level. After a 24h outage PEPs downgrade `allow` → `step_up_approval_required`
   (§J.6). No emergency action is required to stay safe.
5. **Fail-open** — only for action classes explicitly marked fail-open in the Constitution
   (`_FAIL_OPEN_FORGES` in `pdp.py`; empty in v1 = everything fail-closed). Do **not** widen
   fail-open for compliance-adjacent actions.

## Verify recovery
- `simforge_pdp_decision_latency_seconds` p95 back < 0.5s and `simforge_pdp_cache_hit_ratio`
  recovered.
- `python scripts/pdp-pep-demo.py --base-url <url>` prints **PASS** (enforce → revoke → real-time
  invalidation → deny).

## After-action
- If a revocation storm caused it, note whether the drift/amendment batch should throttle its
  `simforge:revocations` publishes. File a post-incident note.
