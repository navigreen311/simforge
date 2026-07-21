# PDP / PEP — runtime authorization (ADR-0024)

The PDP/PEP layer turns the certs SimForge issues into **runtime enforcement**: it answers "may
agent X perform action Y right now?" and keeps that answer fresh across a fleet of enforcement
points. This is what makes the governance platform *operational* rather than advisory.

```
 Village runtime / Forge service                 SimForge
 ┌───────────────────────────┐                  ┌──────────────────────────────┐
 │  PEP (services/pep)        │  POST /decide    │  PDP (governance/pdp.py)     │
 │  • in-process TTL cache    │ ───────────────► │  reads cert + autonomy +     │
 │  • authorize(req)          │ ◄─────────────── │  safe-mode → AuthDecision    │
 │  • graceful degradation    │   AuthDecision   └──────────────┬───────────────┘
 │  • subscribes ▼            │                   revoke/suspend │ publishes
 └──────────┬────────────────┘                                  ▼
            │  invalidate(agent, action)         Redis channel `simforge:revocations`
            └──────────────◄────────────────────────────────────┘
```

## PDP — the decision engine (`services/governance/pdp.py`)
`PDP.decide(session, AuthRequest) → AuthDecision`. The decision is a pure read of governance state:

| Situation | Decision |
|---|---|
| safe-mode active | `step_up_approval_required` |
| no / suspended / revoked / expired cert for the action | `deny` (specific `reason_code`) |
| active cert, autonomy **L4 / L5** | `allow` |
| active cert, autonomy **L3** (exec + approval) | `step_up_approval_required` |
| active cert, autonomy **L2** (draft) | `downgrade_and_retry` |
| active cert, autonomy **L1** (observe) | `deny` |

Each decision carries `ttl_seconds` (PEP cache lifetime) and `fail_policy` (default **fail-closed**
for all compliance-adjacent Forges — the PEP's behavior when it can't reach the PDP).

**API:** `POST /api/pdp/decide` (the PEP endpoint) and `GET /api/pdp/agent/{id}/effective` (a
decision per cert, for dashboards/audit).

## PEP — the enforcement point (`services/pep`)
Embed in a Village runtime or a Forge service:

```python
from src.services.pep import Pep, HttpDecisionSource
from src.services.pep.subscriber import listen_for_revocations
from src.services.governance.pdp import AuthRequest

pep = Pep(HttpDecisionSource("https://simforge.internal", token=SERVICE_TOKEN))
asyncio.create_task(listen_for_revocations(pep))       # real-time cache invalidation

decision = await pep.authorize(AuthRequest("david_kim", "cre-forge.call_center.outbound"))
if decision.decision == "allow":
    ...  # proceed
```

- **Cache:** decisions are cached for `ttl_seconds` (bounded by `max_ttl`, default 300s). Cache hit
  ratio is exported as `simforge_pdp_cache_hit_ratio`.
- **Invalidation:** `listen_for_revocations` drops cached entries the moment a
  `revoked`/`suspended`/`reinstated` event arrives on `simforge:revocations`, so a revocation takes
  effect in ~real time instead of at TTL expiry.
- **Graceful degradation (§J.6):** if the PDP is unreachable the PEP serves the **last-known**
  decision (a Village keeps running at its last-certified level); after a 24h outage it downgrades
  cached `allow` → `step_up_approval_required`; with no cached decision it applies the action's fail
  policy (fail-closed → `deny`).

## Real-time revocation (`services/governance/revocation.py`)
Cert lifecycle changes publish a `{agent_id, forge_cap, event, ts}` message to
`simforge:revocations` (best-effort — a down Redis never fails the cert op). Hooked into:
`revoke_agent_cert` → `revoked`, `reinstate_agent_cert` → `reinstated`, the Drift Canary and
amendment ratify → `suspended`.

## Metrics
`simforge_pdp_decision_latency_seconds{decision}`, `simforge_pdp_decisions_total{decision,
reason_code}`, `simforge_pdp_cache_hit_ratio`. Incident: **R-003** (PDP latency spike / PEP
degradation).

## Try it
```bash
# Redis + a running API; on Windows use 127.0.0.1 (localhost → IPv6 breaks async redis vs Memurai).
REDIS_URL=redis://127.0.0.1:6379/0 uvicorn src.main:app --port 8120
REDIS_URL=redis://127.0.0.1:6379/0 python scripts/pdp-pep-demo.py --base-url http://127.0.0.1:8120
# → enforce (downgrade_and_retry) → revoke → real-time invalidation (entries→0) → deny. PASS.
```

## Guardrails
Read-only and sandbox-safe throughout: the PDP only *reads* governance state; the PEP is a client
cache; the revocation channel is publish-only. No Village writes, no integrated execution.
