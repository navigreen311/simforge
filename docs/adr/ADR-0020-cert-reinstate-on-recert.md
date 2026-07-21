# ADR-0020 — Reinstate a suspended cert by re-certification

**Status:** Accepted (2026-07-21).

## Context
ADR-0017 (Drift Canary) and the governance amendment flow both **suspend** certs, but there was no
way back: the `AgentCert` table has `UNIQUE(agentId, forgeCap)`, so a suspended cert permanently
occupies its pair — `issue` can't create a replacement, and nothing flipped it active again. A
drift-suspended cert was therefore a dead end (the recovery gap ADR-0017 left open).

## Decision
- **`reinstate_agent_cert(session, cert_id, battery_run_ids, approver_id)`** — recovers a
  **suspended** cert by re-certifying against the *current* version matrix: validate a fresh passing
  battery, build + sign a **new** CertSnapshot pinning the now-current Forge (and constitution)
  versions, update the existing cert row in place (`status="active"`, new `certSnapshotId`, fresh
  validity window, clear revocation fields), log a `reinstated` lifecycle event, and restore one
  autonomy level (the inverse of the defensive demote on suspension). Updating in place respects the
  `UNIQUE(agentId, forgeCap)` constraint — which is exactly why suspended certs must be reinstated,
  not re-issued.
- **Shared `_create_snapshot` helper** — `issue` and `reinstate` now build + sign the snapshot
  through one code path, so both produce byte-identical canonical/signed payloads (ADR-0007).
- **Deterministic re-issue rejection** — `issue_agent_cert` now rejects when an **active or
  suspended** cert already occupies the pair (was: active only), with a message pointing to
  reinstate/revoke. This makes the guard deterministic on SQLite (hermetic tests) and Postgres alike,
  rather than relying on a DB `IntegrityError` that only the Prisma-migrated Postgres schema enforces.
- **Router** `POST /api/certs/agent/{cert_id}/reinstate` (admin) → same `IssueCertResponse` shape as
  issue (cert + signed snapshot + autonomy transition).

## Consequences
- The drift lifecycle is now complete: drift → suspend + demote → **reinstate** (fresh battery) →
  active + autonomy restored, with a new snapshot pinning the current versions. The same path
  recovers amendment-suspended certs.
- Verified live (Postgres 17): a suspended cert reinstates to active, restores L1→L2, and the new
  snapshot's Ed25519 signature verifies (the ADR-0007 round-trip holds through reinstate). Re-issuing
  over a suspended pair returns a 400 telling the caller to reinstate.

## Cross-references
ADR-0017 (Drift Canary — the suspension this recovers), ADR-0007 (cert snapshot signing round-trip),
governance amendment auto-suspend (also recovered by reinstate), blueprint §F.4 (lifecycle).
