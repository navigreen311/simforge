# ADR-0017 — Drift Canary (Forge version drift → auto-suspend)

**Status:** Accepted (2026-07-21).

## Context
A CertSnapshot pins the exact version matrix its battery ran against, including
`pinnedVersions.forge_versions` (blueprint §C.4). But issuance hard-coded `{forge: "sandbox.dev"}`,
so the pin was meaningless — and nothing ever checked whether a Forge later changed. If a Forge
sandbox is upgraded after certification, the certified behavior may no longer hold, yet the cert
(and the autonomy it unlocks) stayed active. The Drift Canary is a blueprint §L.4 deferral; it is
now buildable because every Forge (Local or HTTP, ADR-0016) reports a real `get_current_version()`.

## Decision
1. **Pin the real Forge version at issuance.** `issue_agent_cert` now resolves the tested Forge's
   adapter and pins `forge_versions={forge: await get_current_version()}` (falling back to
   `"{forge}.unknown"` if the lookup errors — issuance never fails on a Forge hiccup). The pin now
   means something: "this cert's evidence was gathered against Forge version X."
2. **Drift Canary** (`services/drift/canary.py`) — `scan_forge_drift(session, actor, *, suspend)`:
   for each **active** `AgentCert`, load its snapshot, and for each pinned `(forge, version)`
   compare against the Forge's current version. On mismatch → **drift**; when `suspend=True`, set
   the cert `status="suspended"`, record a `suspended` `CertLifecycleEvent`, and defensively demote
   the agent one autonomy level (as on revocation) — mirroring the constitution-amendment
   auto-suspend. Current versions are cached so each Forge is hit once per scan.
3. **Unreachable ≠ drift.** A Forge whose `get_current_version()` raises (e.g. an HTTP sandbox
   that's down) is reported as `unreachable` but **never** suspended — a transient outage must not
   knock out certs.
4. **Router** `/api/drift` — `GET /status` (viewer, dry run: report drift without acting) +
   `POST /scan` (admin: scan and auto-suspend). Read-only against the Village; sandbox-isolated.

## Consequences
- Certs are now bound to the real Forge version, and a Forge upgrade is detected: `GET
  /api/drift/status` surfaces pending drift; `POST /api/drift/scan` (or a scheduled call) suspends
  drifted certs pending re-certification, and the agent's autonomy drops accordingly.
- Suspension is reversible by re-certifying against the new Forge version (a fresh battery → new
  snapshot pinning the current version), consistent with the existing suspend/reinstate lifecycle.
- The canary composes with ADR-0016: pointing a forge at a real HTTP sandbox means drift is
  detected against the **live** sandbox's version.

## Cross-references
Blueprint §C.4 (pinned versions), §L.4 (Drift Canary deferral), ADR-0007 (cert snapshots),
ADR-0016 (`get_current_version` over HTTP), governance amendment auto-suspend (the mirrored pattern).
