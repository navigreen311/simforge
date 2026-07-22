# ADR-0040 — Incident Command dashboard

**Status:** Accepted (2026-07-21).

## Context
The blueprint's operations section lists an **Incident Command** view (v1.2) for the on-call: active
incidents, safe-mode status, and blast radius. The underlying signals all existed — emergency safe
mode, governance-invalidated certs, open high-severity software gaps, the cost caps (ADR-0039) — but
there was no single place that answered "what is wrong right now, and how big is the blast radius?"

## Decision
- **`incident_report` derives incidents from live signals — it does not add an incident store.**
  Current incidents are computed on read from what the platform already records:
  - emergency **safe mode** → one `critical` incident (blast radius = its domains);
  - **revoked** certs → `high`, **suspended** certs → `medium`, each with a blast radius of the
    affected agents, forge caps, and departments;
  - open **P0** software gaps → `high`, **P1** → `medium` (blast radius = the affected forges);
  - a **breached cost cap** (either mode) → `high`.
- Incidents are sorted worst-first; the report carries per-severity counts, the month's budget, and an
  overall `status` (`ok` / `degraded` / `critical`).
- Surface: `GET /api/incident/status`; an **Incident Command** dashboard page (status banner, safe-mode
  banner, budget bars, incident cards with blast-radius chips).

## Consequences
- Zero drift risk: because incidents are derived, they can never disagree with the source of truth —
  clear a suspension, fix a gap, or deactivate safe mode and the incident disappears on the next read.
- No new writes, table, or worker — the view is a pure aggregation, so it's cheap and always current.
- Composes the earlier work: safe mode (ADR-0028-era governance), the CRL-adjacent cert statuses,
  gaps (ADR-P6), and budget (ADR-0039) all surface in one operational pane.
- Verified: clean state → `status: ok`, 0 incidents; safe mode → `critical` with domain blast radius;
  revoke a cert → `degraded` with the agent, cap, and department correctly in the blast radius.

## Cross-references
Blueprint §H (operations / incident command). `src/services/incident/`, ADR-0039 (budget), ADR-0038
(CRL / cert statuses), the safe-mode + software-gap subsystems.
