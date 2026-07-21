# SimForge — Complete Engineering Blueprint

**Document version:** 1.0.0
**Relationship to spec:** Implementation layer on top of `SIMFORGE_COMPLETE_SPECIFICATION.md`
**Audience:** Engineering team, Claude Code, external contractors
**Status:** Builder-ready

> **How to use this document:** The spec defines *what* SimForge is and *why*. This blueprint defines *how* to build it. When these conflict, the spec wins (philosophy > implementation detail). Conflicts should be reported as spec-blueprint reconciliation issues.

---

## TABLE OF CONTENTS

**PART A — SYSTEM ORIENTATION**
- A.1 Blueprint purpose and reading guide
- A.2 Architecture stack (physical + logical)
- A.3 Deployment topology
- A.4 Technology choices with rationale
- A.5 Repository structure (complete)
- A.6 Environment matrix

**PART B — DATA LAYER**
- B.1 Complete Prisma schema (all 17 entities)
- B.2 Entity relationship diagram
- B.3 Index & query patterns
- B.4 Migration strategy
- B.5 Seed data strategy
- B.6 Archival & retention policies

**PART C — BACKEND SERVICES**
- C.1 FastAPI application topology
- C.2 Service modules
- C.3 Router endpoints (complete)
- C.4 Pydantic schemas
- C.5 Background workers
- C.6 Village reader module
- C.7 CCB composer
- C.8 SimForge-internal agent runtime
- C.9 Scenario runner state machine
- C.10 Evaluation engine
- C.11 Triple reporter
- C.12 Signing & attestation service

**PART D — FRONTEND**
- D.1 Next.js app structure
- D.2 Page tree
- D.3 Component library
- D.4 Design system tokens
- D.5 API client
- D.6 State management

**PART E — FORGE INTEGRATIONS**
- E.1 Integration contract (common)
- E.2 VoiceForge adapter
- E.3 VisionAudioForge adapter
- E.4 medlink-pro adapter
- E.5 CRE Forge adapter
- E.6 FunnelForge adapter
- E.7 CapitalForge (Mock Bank) adapter

**PART F — GOVERNANCE IMPLEMENTATION**
- F.1 Certification Registry
- F.2 CertSnapshot signing flow
- F.3 Autonomy Ladder state machine
- F.4 Revocation Engine
- F.5 Constitution & amendment workflow
- F.6 PDP/PEP (v1.1 implementation)

**PART G — SECURITY**
- G.1 Authentication & authorization
- G.2 Key management (HSM, rotation, CRL)
- G.3 PHI / PII handling
- G.4 Audit logging
- G.5 Secret management

**PART H — OBSERVABILITY**
- H.1 Structured logging
- H.2 Metrics (Prometheus)
- H.3 Distributed tracing (OpenTelemetry)
- H.4 Dashboards (Grafana)
- H.5 Alerting

**PART I — TESTING**
- I.1 Unit testing
- I.2 Integration testing
- I.3 Contract testing (village_bridge, Forge adapters)
- I.4 E2E testing
- I.5 Chaos & load testing

**PART J — DEPLOYMENT & OPERATIONS**
- J.1 Local dev environment
- J.2 Staging environment
- J.3 Production topology
- J.4 CI/CD pipeline
- J.5 Database backups & PITR
- J.6 Disaster recovery
- J.7 Incident runbooks

**PART K — COST MODEL**
- K.1 Per-run cost breakdown
- K.2 Budget controls
- K.3 Scaling projections

**PART L — APPENDICES**
- L.1 Extended glossary
- L.2 API reference index
- L.3 File-by-file index
- L.4 Known limitations
- L.5 Blueprint changelog

---

# PART A — SYSTEM ORIENTATION

## A.1 Blueprint Purpose

This blueprint takes the architectural decisions in the spec and translates them into implementation artifacts that can be code-reviewed, written, tested, deployed, and operated. Every section answers one of:
- "What file/module/table/endpoint?"
- "What signatures/shapes/protocols?"
- "What state machines/lifecycles?"
- "What failure modes + mitigations?"
- "What runbooks + SLOs?"

## A.2 Architecture Stack

### A.2.1 Physical stack

```
┌──────────────────────────────────────────────────────────┐
│   Cloudflare (CDN / WAF / DDoS)                         │
└──────────────────────────────────────────────────────────┘
                          │
┌──────────────────────────────────────────────────────────┐
│   Load Balancer (AWS ALB or Fly.io proxy)                │
└──────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌────────────────────┐        ┌─────────────────────┐
│  Next.js Frontend  │        │  FastAPI Backend    │
│  (Vercel or Fly)   │        │  (Fly.io / AWS ECS) │
│  Port 3000         │        │  Port 8000          │
└────────────────────┘        └─────────────────────┘
         │                              │
         └──────────┬───────────────────┘
                    │
                    ▼
      ┌───────────────────────────────┐
      │  PostgreSQL 15 (primary)      │
      │  + streaming replica          │
      │  Point-in-time recovery       │
      └───────────────────────────────┘
                    │
      ┌─────────────┴──────────────┐
      ▼                            ▼
┌───────────────┐         ┌────────────────┐
│  Redis        │         │  S3 (Evidence) │
│  (BullMQ +    │         │  + signed URLs │
│   PDP cache)  │         │  + tiered tier │
└───────────────┘         └────────────────┘

         External dependencies:
┌─────────────────────────────────────────┐
│  Ollama (local LLM — Village routes)    │
│  OpenAI / Anthropic (cloud LLM)         │
│  HSM (CertSnapshot signing)             │
│  Linear API (gap tickets)               │
│  Forge sandbox tenants (6)              │
│  Village OS VillageData/ (read-only fs) │
└─────────────────────────────────────────┘
```

### A.2.2 Logical stack

| Layer | Technology | Version |
|---|---|---|
| Frontend framework | Next.js App Router | 14.x |
| Frontend language | TypeScript | 5.x |
| Frontend UI kit | Tailwind + shadcn/ui | latest |
| Frontend state | Zustand for global, TanStack Query for server | latest |
| Backend framework | FastAPI | ≥ 0.110 |
| Backend language | Python | 3.11 |
| ORM | Prisma (schema) + Prisma Client Python | ≥ 0.13 |
| DB | PostgreSQL | 15 |
| Cache / queue | Redis | 7.x |
| Workers | BullMQ (node) + RQ (Python, for scenario runs) | latest |
| Object storage | S3-compatible (AWS S3 / Cloudflare R2) | — |
| Auth | Clerk or WorkOS | — |
| Signing | AWS CloudHSM or YubiHSM 2 | — |
| Observability | OpenTelemetry → Grafana Cloud (Loki + Tempo + Prometheus) | — |
| Error tracking | Sentry | — |
| CI/CD | GitHub Actions | — |
| IaC | Terraform (prod), docker-compose (dev) | — |

## A.3 Deployment Topology

### A.3.1 Dev (developer laptop)

- `docker-compose up` brings PostgreSQL + Redis + optional Ollama.
- Frontend at `localhost:3000`.
- Backend at `localhost:8000`.
- `VILLAGE_DATA_PATH` points to local Village repo or shared mount.
- Signing uses dev HSM stub (not real HSM).
- Evidence storage is local filesystem.

### A.3.2 Staging

- Fly.io (multi-region) or AWS Fargate.
- Staging Postgres (single-region, daily snapshots).
- Staging Redis.
- Staging S3 bucket with 30-day lifecycle.
- Connects to Forge staging sandbox tenants.
- Signing via YubiHSM 2 (dev root key, not prod root).
- Full observability enabled.

### A.3.3 Production

- Fly.io (multi-region, active-active) or AWS (ECS Fargate, multi-AZ).
- Postgres primary + streaming replica in second AZ; daily snapshots + 7-day PITR.
- Redis cluster with persistence.
- S3 with tiered lifecycle (hot → warm → cold per §12.3 of spec).
- Connects to Forge production sandbox tenants (read + fault-injection only).
- Signing via AWS CloudHSM (prod root in FIPS 140-2 Level 3 device).
- Full observability + 24/7 on-call.
- Daily automated DR drills.

## A.4 Technology Choices (Rationale)

| Choice | Alternative | Rationale |
|---|---|---|
| Next.js App Router | Remix, SvelteKit | Team familiarity; matches ChamberForge/CapitalForge stack |
| FastAPI | Django, Flask | Async-native, Pydantic-native, OpenAPI-native, better ergonomics for long-running scenario runs |
| Prisma (schema) | Raw SQLAlchemy | Single source of truth for TS + Python; migrations + types generated |
| Prisma Client Python | Pure SQLAlchemy in Python | Same schema definition drives both; reduces drift; acceptable maturity for v1 |
| PostgreSQL | MongoDB, DynamoDB | ACID guarantees for registries + lineage + certs; JSONB for CCB flexibility |
| Redis + BullMQ/RQ | SQS, Kafka | Lower ops burden for v1; scale decision deferred to v1.2 |
| S3 for evidence | Local FS, Postgres LargeObject | Durability, lifecycle policies, signed URLs |
| Fly.io | AWS ECS, k8s | Faster iteration for small team; migrate to ECS if scale demands |
| Clerk | WorkOS, Auth0 | Best DX; SOC2 ready; easy to swap if SSO-driven enterprise needs emerge |
| AWS CloudHSM (prod) | KMS | FIPS Level 3 required for external auditor acceptance of CertSnapshots |
| Linear | Jira, GitHub Issues | Team preference per B5; good API for gap routing |

## A.5 Complete Repository Structure

```
simforge/
├── apps/
│   ├── web/                                    # Next.js frontend
│   │   ├── src/
│   │   │   ├── app/
│   │   │   │   ├── (auth)/
│   │   │   │   │   ├── login/page.tsx
│   │   │   │   │   └── callback/page.tsx
│   │   │   │   ├── (dashboard)/
│   │   │   │   │   ├── layout.tsx             # sidebar + header shell
│   │   │   │   │   ├── page.tsx               # overview dashboard
│   │   │   │   │   ├── readiness/
│   │   │   │   │   │   ├── page.tsx           # Readiness Gate Matrix
│   │   │   │   │   │   └── [certId]/page.tsx  # cert detail
│   │   │   │   │   ├── runs/
│   │   │   │   │   │   ├── page.tsx           # run list
│   │   │   │   │   │   └── [runId]/page.tsx   # run detail + scorecard
│   │   │   │   │   ├── packs/
│   │   │   │   │   │   ├── page.tsx
│   │   │   │   │   │   ├── [packId]/page.tsx
│   │   │   │   │   │   └── [packId]/scenarios/[scenarioId]/page.tsx
│   │   │   │   │   ├── gaps/
│   │   │   │   │   │   ├── software/page.tsx
│   │   │   │   │   │   └── village-os/page.tsx
│   │   │   │   │   ├── agents/
│   │   │   │   │   │   ├── page.tsx           # Village agent directory
│   │   │   │   │   │   └── [agentId]/page.tsx # agent profile + certs
│   │   │   │   │   ├── departments/
│   │   │   │   │   │   ├── page.tsx
│   │   │   │   │   │   └── [deptId]/page.tsx
│   │   │   │   │   ├── certs/
│   │   │   │   │   │   ├── page.tsx           # Certification Registry
│   │   │   │   │   │   └── [certId]/page.tsx
│   │   │   │   │   ├── constitution/
│   │   │   │   │   │   ├── page.tsx
│   │   │   │   │   │   └── amendments/[amendmentId]/page.tsx
│   │   │   │   │   ├── registry/              # Object Registry UI (v1.1)
│   │   │   │   │   │   └── page.tsx
│   │   │   │   │   └── lineage/               # Lineage Graph explorer
│   │   │   │   │       └── page.tsx
│   │   │   │   ├── api/
│   │   │   │   │   └── proxy/[...slug]/route.ts  # proxy to FastAPI
│   │   │   │   ├── layout.tsx
│   │   │   │   ├── globals.css                # design tokens
│   │   │   │   └── page.tsx                   # marketing landing
│   │   │   ├── components/
│   │   │   │   ├── ui/                        # shadcn primitives
│   │   │   │   ├── shell/
│   │   │   │   │   ├── Sidebar.tsx
│   │   │   │   │   ├── Header.tsx
│   │   │   │   │   └── CommandK.tsx
│   │   │   │   ├── readiness/
│   │   │   │   │   ├── ReadinessGateMatrix.tsx
│   │   │   │   │   └── CertCell.tsx
│   │   │   │   ├── runs/
│   │   │   │   │   ├── RunTimeline.tsx
│   │   │   │   │   ├── ScorecardCard.tsx
│   │   │   │   │   ├── FifteenDimChart.tsx
│   │   │   │   │   ├── CCBDiffViewer.tsx
│   │   │   │   │   └── TurnAnnotationList.tsx
│   │   │   │   ├── packs/
│   │   │   │   │   ├── PackOverview.tsx
│   │   │   │   │   ├── CoverageHeatmap.tsx
│   │   │   │   │   └── ScenarioCard.tsx
│   │   │   │   ├── gaps/
│   │   │   │   │   ├── GapTable.tsx
│   │   │   │   │   └── Top10GapsWidget.tsx
│   │   │   │   ├── agents/
│   │   │   │   │   ├── AgentCard.tsx
│   │   │   │   │   ├── CognitiveStateBadges.tsx
│   │   │   │   │   └── AutonomyLadderIndicator.tsx
│   │   │   │   ├── charts/
│   │   │   │   │   ├── TrendLine.tsx
│   │   │   │   │   ├── CohortHeatmap.tsx
│   │   │   │   │   └── LineageGraph.tsx
│   │   │   │   └── common/
│   │   │   │       ├── GoldBadge.tsx
│   │   │   │       ├── TierPill.tsx
│   │   │   │       ├── SimulationTag.tsx
│   │   │   │       └── StatusDot.tsx
│   │   │   ├── lib/
│   │   │   │   ├── api/
│   │   │   │   │   ├── client.ts              # typed API client
│   │   │   │   │   ├── queries.ts             # TanStack Query hooks
│   │   │   │   │   └── mutations.ts
│   │   │   │   ├── auth.ts                    # Clerk helpers
│   │   │   │   ├── formatters.ts
│   │   │   │   ├── stores/
│   │   │   │   │   ├── ui.ts                  # sidebar, command-k state
│   │   │   │   │   └── filters.ts             # dashboard filter state
│   │   │   │   └── utils.ts
│   │   │   ├── styles/
│   │   │   │   └── tokens.css
│   │   │   └── middleware.ts                  # Clerk middleware
│   │   ├── public/
│   │   ├── tailwind.config.ts
│   │   ├── tsconfig.json
│   │   ├── next.config.js
│   │   └── package.json
│   │
│   └── api/                                    # FastAPI backend
│       ├── src/
│       │   ├── main.py                        # app factory
│       │   ├── config.py                      # Pydantic settings
│       │   ├── deps.py                        # DI
│       │   ├── db.py                          # async SQLAlchemy engine
│       │   ├── prisma_client/                 # generated
│       │   ├── models/                        # Prisma models (generated + Python wrappers)
│       │   │   └── __init__.py
│       │   ├── schemas/                       # Pydantic request/response
│       │   │   ├── __init__.py
│       │   │   ├── agent.py
│       │   │   ├── pack.py
│       │   │   ├── scenario.py
│       │   │   ├── run.py
│       │   │   ├── ccb.py
│       │   │   ├── scorecard.py
│       │   │   ├── gap.py
│       │   │   ├── cert.py
│       │   │   ├── snapshot.py
│       │   │   ├── readiness_gate.py
│       │   │   ├── registry.py
│       │   │   ├── lineage.py
│       │   │   └── constitution.py
│       │   ├── routers/
│       │   │   ├── __init__.py
│       │   │   ├── health.py
│       │   │   ├── agents.py
│       │   │   ├── departments.py
│       │   │   ├── packs.py
│       │   │   ├── scenarios.py
│       │   │   ├── runs.py
│       │   │   ├── certs.py
│       │   │   ├── snapshots.py
│       │   │   ├── gaps.py
│       │   │   ├── dashboard.py
│       │   │   ├── registry.py
│       │   │   ├── lineage.py
│       │   │   ├── constitution.py
│       │   │   └── attest.py                  # external verification endpoint
│       │   ├── services/
│       │   │   ├── __init__.py
│       │   │   ├── village/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── reader.py              # read-only filesystem reader
│       │   │   │   ├── ccb_composer.py
│       │   │   │   ├── fingerprint.py
│       │   │   │   └── prompt_assembler.py    # replicates 9-layer assembly
│       │   │   ├── scenario_engine/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── types.py
│       │   │   │   ├── runner.py              # main scenario loop
│       │   │   │   ├── state.py               # RunState dataclass
│       │   │   │   ├── branch.py              # branching logic
│       │   │   │   ├── complications.py       # complication injector
│       │   │   │   └── persona_cast.py
│       │   │   ├── agent_runtime/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── runtime.py             # SimForge internal agent
│       │   │   │   ├── llm_client.py          # Ollama + OpenAI wrapper
│       │   │   │   └── tool_executor.py       # tool-call handling
│       │   │   ├── mock_world/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── bank.py                # proxies CapitalForge sandbox
│       │   │   │   ├── telephony.py           # proxies VoiceForge
│       │   │   │   ├── doc_vault.py           # proxies VAF
│       │   │   │   ├── crm.py                 # proxies FunnelForge
│       │   │   │   ├── portals/
│       │   │   │   │   ├── clinician.py
│       │   │   │   │   ├── facility.py
│       │   │   │   │   └── greenstone.py
│       │   │   │   ├── personas.py
│       │   │   │   └── regulator.py
│       │   │   ├── evaluation/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── rubric.py              # 15-dim orchestrator
│       │   │   │   ├── dimensions/
│       │   │   │   │   ├── p1_correctness.py
│       │   │   │   │   ├── p2_compliance.py   # rules engine
│       │   │   │   │   ├── p3_process_fidelity.py
│       │   │   │   │   ├── p4_time_to_resolution.py
│       │   │   │   │   ├── p5_escalation.py
│       │   │   │   │   ├── p6_doc_quality.py
│       │   │   │   │   ├── p7_cx.py           # LLM-judge
│       │   │   │   │   ├── p8_cost.py
│       │   │   │   │   ├── c1_breath_coherence.py
│       │   │   │   │   ├── c2_soul_stability.py
│       │   │   │   │   ├── c3_fot_management.py
│       │   │   │   │   ├── c4_arc_coherence.py
│       │   │   │   │   ├── c5_echo_regret.py
│       │   │   │   │   ├── c6_hfm_drive.py
│       │   │   │   │   └── c7_ame_trajectory.py
│       │   │   │   ├── readiness_gate.py      # aggregator
│       │   │   │   └── regression.py          # regression detector
│       │   │   ├── reporter/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── scorecard.py
│       │   │   │   ├── software_gap.py
│       │   │   │   ├── village_os_gap.py
│       │   │   │   ├── linear_client.py
│       │   │   │   └── remediation.py
│       │   │   ├── cert/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── registry.py
│       │   │   │   ├── snapshot.py
│       │   │   │   ├── signer.py              # HSM integration
│       │   │   │   ├── verifier.py
│       │   │   │   ├── revocation.py
│       │   │   │   └── autonomy_ladder.py     # state machine
│       │   │   ├── governance/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── constitution.py
│       │   │   │   ├── amendment.py
│       │   │   │   ├── approval_workflow.py
│       │   │   │   └── safe_mode.py
│       │   │   ├── registry/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── object_registry.py
│       │   │   │   ├── lineage.py
│       │   │   │   └── urn.py
│       │   │   ├── forges/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── base.py                # ForgeAdapter ABC
│       │   │   │   ├── voiceforge.py
│       │   │   │   ├── visionaudioforge.py
│       │   │   │   ├── medlink_pro.py
│       │   │   │   ├── cre_forge.py
│       │   │   │   ├── funnelforge.py
│       │   │   │   └── capitalforge.py
│       │   │   ├── evidence/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── bundle.py
│       │   │   │   ├── storage.py             # S3 client
│       │   │   │   └── lifecycle.py
│       │   │   └── compliance/
│       │   │       ├── __init__.py
│       │   │       ├── rules_engine.py
│       │   │       └── jurisdictions/
│       │   │           ├── hipaa.py
│       │   │           ├── hcqc_nv.py
│       │   │           ├── oig_sam.py
│       │   │           ├── i9.py
│       │   │           ├── tcpa.py
│       │   │           ├── wage_hour.py
│       │   │           └── state_wholesaling.py
│       │   ├── workers/
│       │   │   ├── __init__.py
│       │   │   ├── runner_worker.py           # RQ worker for scenario runs
│       │   │   ├── eval_worker.py
│       │   │   ├── reporter_worker.py
│       │   │   ├── regression_worker.py       # nightly regression battery
│       │   │   ├── cert_lifecycle_worker.py   # expiration / renewal nudges
│       │   │   └── fingerprint_worker.py      # nightly Village fingerprint check
│       │   ├── telemetry/
│       │   │   ├── __init__.py
│       │   │   ├── logging.py
│       │   │   ├── metrics.py                 # Prometheus
│       │   │   └── tracing.py                 # OpenTelemetry
│       │   ├── auth/
│       │   │   ├── __init__.py
│       │   │   └── clerk.py
│       │   ├── utils/
│       │   │   ├── ulid_gen.py
│       │   │   ├── hashing.py
│       │   │   └── time.py
│       │   └── alembic/                       # migrations
│       │       └── versions/
│       ├── tests/                             # mirrors src structure
│       │   ├── unit/
│       │   ├── integration/
│       │   ├── contract/
│       │   └── e2e/
│       ├── pyproject.toml
│       ├── alembic.ini
│       └── Dockerfile
│
├── packages/
│   ├── db/
│   │   ├── schema.prisma
│   │   ├── seed.ts                            # seed script for sample agents/packs
│   │   └── package.json
│   ├── validator/                             # Pack + Scenario YAML validator (Python CLI)
│   │   ├── src/
│   │   │   ├── main.py
│   │   │   ├── pack_schema.py
│   │   │   ├── scenario_schema.py
│   │   │   └── rules.py
│   │   ├── tests/
│   │   └── pyproject.toml
│   └── shared-types/                          # TS types generated from Prisma
│       └── index.ts
│
├── packs/
│   ├── greenstone/v1/
│   │   ├── pack.yml
│   │   ├── scenarios/
│   │   ├── personas/
│   │   ├── documents/
│   │   └── fixtures/
│   └── medlink-pro/v1/
│       ├── pack.yml
│       ├── scenarios/
│       ├── personas/
│       ├── documents/
│       └── fixtures/
│
├── docs/
│   ├── SIMFORGE.md                            # architecture overview
│   ├── SPEC.md                                # link to canonical spec
│   ├── BLUEPRINT.md                           # this file
│   ├── RUBRIC.md
│   ├── DECISIONS.md
│   ├── CONSTITUTION_v1.0.0.yml
│   ├── RUNBOOKS/
│   │   ├── R-001_eval_engine_down.md
│   │   ├── R-002_sandbox_tenant_down.md
│   │   ├── R-003_pdp_latency_spike.md
│   │   ├── R-004_mass_regression.md
│   │   ├── R-005_hsm_unavailable.md
│   │   ├── R-006_village_fingerprint_drift.md
│   │   └── R-007_linear_webhook_failure.md
│   ├── CONTRIBUTING.md
│   └── ONBOARDING.md
│
├── infra/
│   ├── terraform/                             # prod IaC
│   │   ├── main.tf
│   │   ├── rds.tf
│   │   ├── redis.tf
│   │   ├── s3.tf
│   │   ├── ecs.tf
│   │   └── iam.tf
│   ├── k8s/                                   # optional k8s manifests (future)
│   └── dashboards/                            # Grafana dashboard JSON
│
├── scripts/
│   ├── bootstrap.sh
│   ├── smoke-test.sh
│   ├── seed-constitution.py
│   ├── check-village-fingerprint.py
│   ├── ingest-scenario-library.py             # one-time Greenstone/MedLink library import
│   └── run-dress-rehearsal.py
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── pack-validator.yml
│       ├── contract-tests.yml
│       ├── deploy-staging.yml
│       └── deploy-prod.yml
│
├── docker-compose.yml                         # dev environment
├── docker-compose.staging.yml
├── .env.example
├── .gitignore
├── README.md
├── pnpm-workspace.yaml
└── turbo.json
```

Total file count at v1: ~250 code files + ~30 doc/config files.

## A.6 Environment Matrix

| Variable | Dev | Staging | Prod | Purpose |
|---|---|---|---|---|
| `DATABASE_URL` | local pg | staging RDS | prod RDS | Postgres connection |
| `REDIS_URL` | local redis | staging elasticache | prod elasticache | Queue + PDP cache |
| `S3_BUCKET` | local filesystem | `simforge-staging-evidence` | `simforge-prod-evidence` | Evidence storage |
| `S3_REGION` | — | `us-west-2` | `us-west-2` + replica in `us-east-1` | — |
| `VILLAGE_DATA_PATH` | local path | shared mount | shared mount | Read-only Village fs |
| `VILLAGE_DB_PATH` | local path | shared mount | shared mount | Read-only village.db |
| `VILLAGE_OS_VERSION_FINGERPRINT` | dev fingerprint | staging fingerprint | prod fingerprint | Drift detection |
| `OLLAMA_BASE_URL` | `localhost:11434` | staging ollama | prod ollama cluster | LLM for internal agent |
| `OPENAI_API_KEY` | dev key | staging key | prod key | OpenAI fallback |
| `ANTHROPIC_API_KEY` | dev key | staging key | prod key | Claude fallback |
| `CLERK_PUBLISHABLE_KEY` | dev | staging | prod | Frontend auth |
| `CLERK_SECRET_KEY` | dev | staging | prod | Backend auth verification |
| `HSM_PROVIDER` | `stub` | `yubihsm` | `aws-cloudhsm` | Signing provider |
| `SIMFORGE_ROOT_KEY_ID` | `dev-root` | `staging-root` | `prod-root-2026` | Root key handle |
| `LINEAR_API_KEY` | — (skip posting) | staging workspace | prod workspace | Gap ticket routing |
| `SENTRY_DSN` | — | staging DSN | prod DSN | Error tracking |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | grafana cloud staging | grafana cloud prod | Telemetry |
| `FORGE_*_SANDBOX_URL` | local stubs | staging sandboxes | prod sandboxes | 6 Forge URLs each |
| `SIMFORGE_BUDGET_SANDBOX_MONTHLY_USD` | 50 | 500 | 5000 | Token budget cap |

---

# PART B — DATA LAYER

## B.1 Complete Prisma Schema

```prisma
generator client {
  provider = "prisma-client-js"
  output   = "../../apps/web/src/lib/db/generated"
}

generator pyclient {
  provider = "prisma-client-py"
  interface = "asyncio"
  recursive_type_depth = 5
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

// ═══════════════════════════════════════════════════════════════
// AGENT / ORGANIZATION
// ═══════════════════════════════════════════════════════════════

model Agent {
  id              String    @id @default(cuid())
  villageAgentId  String    @unique                          // "taylor_zhang"
  name            String
  role            String
  departmentId    String
  department      Department @relation(fields: [departmentId], references: [id])
  gardnerFlag     Boolean   @default(false)
  level10Enabled  Boolean   @default(false)                  // perception + host cognition + phone
  currentAutonomyLevel String @default("L1")                 // L1-L5
  
  agentCerts      AgentCert[]
  runs            Run[]
  cognitiveSnapshots CognitiveSnapshot[]
  autonomyEvents  AutonomyEvent[]
  
  createdAt       DateTime  @default(now())
  updatedAt       DateTime  @updatedAt
  
  @@index([villageAgentId])
  @@index([departmentId])
  @@index([currentAutonomyLevel])
}

model Department {
  id              String    @id @default(cuid())
  villageKey      String    @unique                          // "Engineering"
  name            String
  totalAgents     Int
  
  agents          Agent[]
  deptCerts       DeptCert[]
  
  createdAt       DateTime  @default(now())
  updatedAt       DateTime  @updatedAt
}

// ═══════════════════════════════════════════════════════════════
// PACK & SCENARIO
// ═══════════════════════════════════════════════════════════════

model Pack {
  id                    String    @id @default(cuid())
  packId                String    @unique                    // "pack.greenstone.v1"
  name                  String
  version               String
  ownerVenture          String
  ownerHuman            String
  phiRequired           Boolean   @default(false)
  complianceFlags       String[]
  integratedRunsAllowed Boolean   @default(false)
  executionModeDefault  String    @default("sandbox")
  narrativeModeDefault  String    @default("protected")
  rubricProfile         String
  yamlPath              String
  yamlHash              String
  signedBy              String?                              // owner_human who ratified
  signedAt              DateTime?
  
  scenarios             Scenario[]
  runs                  Run[]
  readinessGate         ReadinessGate?
  
  createdAt             DateTime  @default(now())
  updatedAt             DateTime  @updatedAt
  
  @@unique([packId, version])
  @@index([ownerVenture])
}

model Scenario {
  id                  String    @id @default(cuid())
  scenarioId          String    @unique                      // "scn.gs.src.001"
  packId              String
  pack                Pack      @relation(fields: [packId], references: [id])
  title               String
  tier                String                                  // "foundational" | "intermediate" | "advanced_crisis"
  testedAgentVillageId String
  testedForgeCaps     String[]
  trainingDomains     String[]
  seed                Int
  yamlPath            String
  yamlHash            String
  sloSeconds          Int
  complianceChecks    String[]
  isGolden            Boolean   @default(false)              // Golden Benchmark (v1.2)
  
  runs                Run[]
  
  createdAt           DateTime  @default(now())
  updatedAt           DateTime  @updatedAt
  
  @@index([packId])
  @@index([testedAgentVillageId])
  @@index([tier])
  @@index([isGolden])
}

model ReadinessGate {
  id                      String    @id @default(cuid())
  packId                  String    @unique
  pack                    Pack      @relation(fields: [packId], references: [id])
  tierThresholds          Json                                // {F: 0.70, I: 0.80, AC: 0.85}
  cognitiveAggregateMin   Float     @default(0.75)
  blindModePct            Float     @default(0.25)
  arcFragmentationAutoFail Boolean  @default(true)
  complianceRequirePass   Boolean   @default(true)
  updatedAt               DateTime  @updatedAt
}

// ═══════════════════════════════════════════════════════════════
// RUN & EXECUTION
// ═══════════════════════════════════════════════════════════════

model Run {
  id                String    @id @default(cuid())
  runId             String    @unique                        // ULID
  scenarioId        String
  scenario          Scenario  @relation(fields: [scenarioId], references: [id])
  packId            String
  pack              Pack      @relation(fields: [packId], references: [id])
  agentId           String
  agent             Agent     @relation(fields: [agentId], references: [id])
  
  executionMode     String                                    // "sandbox" | "integrated"
  narrativeMode     String                                    // "protected" | "integrated"
  blindMode         Boolean   @default(false)
  
  status            String                                    // "pending" | "running" | "passed" | "failed" | "errored" | "cancelled"
  startedAt         DateTime
  endedAt           DateTime?
  outcome           String?
  latencyMs         Int?
  tokensUsed        Int?
  costUsd           Float?
  
  ccbPreId          String?
  ccbPostId         String?
  ccbPre            CCB?      @relation("RunCCBPre",  fields: [ccbPreId],  references: [id])
  ccbPost           CCB?      @relation("RunCCBPost", fields: [ccbPostId], references: [id])
  
  transcript        Json?                                     // turn-by-turn
  evidenceBundleRef String?                                   // S3 URI
  
  scorecard         Scorecard?
  softwareGaps      SoftwareGap[]
  villageOSGaps     VillageOSGap[]
  traceEvents       TraceEvent[]
  
  createdAt         DateTime  @default(now())
  updatedAt         DateTime  @updatedAt
  
  @@index([scenarioId])
  @@index([agentId])
  @@index([status])
  @@index([startedAt])
}

model TraceEvent {
  id                String    @id @default(cuid())
  runId             String
  run               Run       @relation(fields: [runId], references: [id])
  timestamp         DateTime
  eventType         String                                    // "turn_start" | "tool_call" | "framework_read" | ...
  phase             String                                    // "setup" | "cold_open" | "turn" | "complication" | "resolution" | "wrap"
  turnNumber        Int?
  payload           Json
  
  createdAt         DateTime  @default(now())
  
  @@index([runId])
  @@index([timestamp])
}

// ═══════════════════════════════════════════════════════════════
// COGNITIVE CONTEXT BUNDLE (CCB)
// ═══════════════════════════════════════════════════════════════

model CCB {
  id                String    @id @default(cuid())
  snapshotId        String    @unique                        // ULID
  agentVillageId    String
  phase             String                                    // "pre" | "post"
  takenAt           DateTime
  contentHash       String                                    // sha256
  
  game              Json
  mate              Json
  soul              Json
  breath            Json
  fot               Json
  hfm               Json
  arc               Json
  echo              Json
  drift             Json
  ame               Json
  
  villageSchemaFingerprint String                            // fingerprint at capture time
  
  runsPre           Run[]     @relation("RunCCBPre")
  runsPost          Run[]     @relation("RunCCBPost")
  
  createdAt         DateTime  @default(now())
  
  @@index([agentVillageId, phase])
  @@index([takenAt])
}

// Daily canary snapshot for drift detection (v1.2)
model CognitiveSnapshot {
  id                String    @id @default(cuid())
  agentId           String
  agent             Agent     @relation(fields: [agentId], references: [id])
  date              DateTime                                  // truncated to day
  ccbSnapshotId     String
  deltas            Json                                      // vs. baseline
  
  createdAt         DateTime  @default(now())
  
  @@unique([agentId, date])
  @@index([agentId])
}

// ═══════════════════════════════════════════════════════════════
// EVALUATION
// ═══════════════════════════════════════════════════════════════

model Scorecard {
  id                        String    @id @default(cuid())
  runId                     String    @unique
  run                       Run       @relation(fields: [runId], references: [id])
  
  // Performance dimensions
  p1Correctness             Float?
  p2Compliance              Boolean?
  p3ProcessFidelity         Float?
  p4TimeToResolution        Float?
  p5Escalation              Float?
  p6DocQuality              Float?
  p7CustomerExperience      Float?
  p8CostDiscipline          Float?
  
  // Cognitive dimensions
  c1BreathCoherence         Float?
  c2SoulStability           Float?
  c3FotPressureManagement   Float?
  c4ArcNarrativeCoherence   String?                         // "gradual_drift" | "sudden_shift" | ...
  c5EchoRegretLoad          Float?
  c6HfmDriveBalance         Float?
  c7AmeReputationTrajectory Float?
  
  cognitiveAggregate        Float?
  
  // Gate
  readinessGatePassed       Boolean   @default(false)
  autoFailReason            String?                         // "arc_fragmentation" | "compliance_violation" | ...
  
  turnAnnotations           Json                              // [{turn, tag, detail}]
  remediationRecs           Json?                             // [{rec, priority}]
  cohortComparison          Json?                             // {role, agent_rank, cohort_size, percentile}
  
  createdAt                 DateTime  @default(now())
  
  @@index([readinessGatePassed])
}

// ═══════════════════════════════════════════════════════════════
// GAPS
// ═══════════════════════════════════════════════════════════════

model SoftwareGap {
  id            String    @id @default(cuid())
  ticketId      String    @unique                             // "SF-GAP-4821"
  runId         String
  run           Run       @relation(fields: [runId], references: [id])
  forge         String                                         // "voiceforge" | "vaf" | "medlink-pro" | "cre-forge" | "funnelforge" | "capitalforge"
  module        String
  severity      String                                         // "P0" | "P1" | "P2"
  summary       String
  detail        String
  proposedFix   String?
  linearUrl     String?
  linearId      String?
  status        String    @default("open")                    // "open" | "triaged" | "in_progress" | "fixed" | "wontfix"
  firstSeenRunId String
  lastSeenRunId  String
  occurrenceCount Int      @default(1)
  
  createdAt     DateTime  @default(now())
  updatedAt     DateTime  @updatedAt
  
  @@index([forge, severity, status])
  @@index([ticketId])
}

model VillageOSGap {
  id            String    @id @default(cuid())
  ticketId      String    @unique                             // "SF-VG-0142"
  runId         String
  run           Run       @relation(fields: [runId], references: [id])
  framework     String                                         // "soul" | "fot" | "arc" | "echo" | "hfm" | "ame" | "breath" | "game" | "mate" | "drift"
  severity      String
  summary       String
  detail        String
  proposedFix   String?
  linearUrl     String?
  linearId      String?
  status        String    @default("open")
  occurrenceCount Int     @default(1)
  
  createdAt     DateTime  @default(now())
  updatedAt     DateTime  @updatedAt
  
  @@index([framework, severity, status])
}

// ═══════════════════════════════════════════════════════════════
// CERTIFICATION
// ═══════════════════════════════════════════════════════════════

model AgentCert {
  id                String    @id @default(cuid())
  agentId           String
  agent             Agent     @relation(fields: [agentId], references: [id])
  forgeCap          String                                     // "cre-forge.call_center.outbound_seller_outreach"
  tier              String                                     // "foundational" | "intermediate" | "advanced_crisis"
  status            String                                     // "active" | "expired" | "revoked" | "suspended"
  issuedAt          DateTime
  expiresAt         DateTime
  revokedAt         DateTime?
  revocationReason  String?
  certSnapshotId    String    @unique
  certSnapshot      CertSnapshot @relation(fields: [certSnapshotId], references: [id])
  
  lifecycleEvents   CertLifecycleEvent[]
  
  createdAt         DateTime  @default(now())
  updatedAt         DateTime  @updatedAt
  
  @@unique([agentId, forgeCap])
  @@index([status])
  @@index([expiresAt])
}

model DeptCert {
  id                     String    @id @default(cuid())
  departmentId           String
  department             Department @relation(fields: [departmentId], references: [id])
  forgeContext           String
  tier                   String
  status                 String
  issuedAt               DateTime
  expiresAt              DateTime
  revokedAt              DateTime?
  revocationReason       String?
  certSnapshotId         String    @unique
  certSnapshot           CertSnapshot @relation(fields: [certSnapshotId], references: [id])
  prerequisiteAgentCertIds String[]
  
  lifecycleEvents        CertLifecycleEvent[]
  
  createdAt              DateTime  @default(now())
  updatedAt              DateTime  @updatedAt
  
  @@unique([departmentId, forgeContext])
  @@index([status])
}

model CertLifecycleEvent {
  id                String    @id @default(cuid())
  agentCertId       String?
  agentCert         AgentCert? @relation(fields: [agentCertId], references: [id])
  deptCertId        String?
  deptCert          DeptCert? @relation(fields: [deptCertId], references: [id])
  event             String                                     // "issued" | "renewed" | "revoked" | "suspended" | "reinstated" | "expired"
  timestamp         DateTime
  actor             String                                     // user who triggered
  reason            String?
  snapshotIdAtEvent String?
  
  createdAt         DateTime  @default(now())
  
  @@index([agentCertId])
  @@index([deptCertId])
  @@index([event])
}

model CertSnapshot {
  id                String    @id @default(cuid())
  snapshotId        String    @unique                         // "certsnap:7f3a...e9"
  certType          String                                     // "agent_forge_cap" | "dept_forge_context"
  subject           String
  forgeCap          String?
  forgeContext      String?
  tier              String
  issuedAt          DateTime
  expiresAt         DateTime
  
  pinnedVersions    Json                                       // full version matrix
  evidenceBundleRef String                                     // S3 URI
  signingKeyId      String
  signature         String                                     // base64
  contentHash       String
  
  agentCert         AgentCert?
  deptCert          DeptCert?
  
  createdAt         DateTime  @default(now())
  
  @@index([signingKeyId])
}

// ═══════════════════════════════════════════════════════════════
// AUTONOMY LADDER
// ═══════════════════════════════════════════════════════════════

model AutonomyEvent {
  id            String    @id @default(cuid())
  agentId       String
  agent         Agent     @relation(fields: [agentId], references: [id])
  fromLevel     String
  toLevel       String
  reason        String                                         // "initial" | "time_based_promotion" | "compliance_violation_demotion" | "regression_demotion" | "manual_override"
  triggeredBy   String?                                        // user or "system"
  runIdContext  String?                                        // run that triggered this
  approvalId    String?                                        // if manual
  
  createdAt     DateTime  @default(now())
  
  @@index([agentId])
  @@index([createdAt])
}

// ═══════════════════════════════════════════════════════════════
// OBJECT REGISTRY & LINEAGE
// ═══════════════════════════════════════════════════════════════

model ObjectRegistryEntry {
  id            String    @id @default(cuid())
  urn           String    @unique                             // "urn:gc:village:agent:jennifer_adams"
  kind          String                                         // "agent" | "department" | "forge_cap" | ...
  canonicalId   String
  metadata      Json
  tombstoned    Boolean   @default(false)
  tombstonedAt  DateTime?
  tombstonedBy  String?
  tombstonedReason String?
  
  createdAt     DateTime  @default(now())
  updatedAt     DateTime  @updatedAt
  
  @@index([kind])
  @@index([tombstoned])
  @@index([canonicalId])
}

model LineageEdge {
  id            String    @id @default(cuid())
  fromUrn       String
  toUrn         String
  relationType  String                                         // "produced_by" | "derived_from" | "pinned_to" | "evidenced_by" | "revoked_by" | "amends"
  metadata      Json?
  
  createdAt     DateTime  @default(now())
  
  @@index([fromUrn])
  @@index([toUrn])
  @@index([relationType])
  @@index([fromUrn, toUrn, relationType])
}

// ═══════════════════════════════════════════════════════════════
// CONSTITUTION & GOVERNANCE
// ═══════════════════════════════════════════════════════════════

model Constitution {
  id                  String    @id @default(cuid())
  version             String    @unique                        // "v1.0.0"
  ratifiedAt          DateTime
  ratifiedBy          String
  yamlContent         String    @db.Text
  contentHash         String
  supersededByVersion String?
  supersededAt        DateTime?
  
  amendments          ConstitutionalAmendment[]
  
  createdAt           DateTime  @default(now())
  
  @@index([version])
}

model ConstitutionalAmendment {
  id                    String    @id @default(cuid())
  amendmentId           String    @unique
  baseConstitutionId    String
  baseConstitution      Constitution @relation(fields: [baseConstitutionId], references: [id])
  proposedAt            DateTime
  proposedBy            String
  coolingPeriodEndsAt   DateTime
  ratifiedAt            DateTime?
  ratifiedBy            String?
  diffYaml              String    @db.Text
  impactAnalysis        Json?                                   // affected certs etc.
  status                String                                  // "proposed" | "in_cooling" | "ratified" | "withdrawn" | "vetoed"
  
  createdAt             DateTime  @default(now())
  updatedAt             DateTime  @updatedAt
  
  @@index([status])
}

// ═══════════════════════════════════════════════════════════════
// SCHEMA FINGERPRINT (Village drift detection)
// ═══════════════════════════════════════════════════════════════

model VillageFingerprint {
  id            String    @id @default(cuid())
  fingerprint   String    @unique
  capturedAt    DateTime
  paths         Json                                           // which structural paths contributed
  isCurrent     Boolean   @default(false)
  flaggedByUser Boolean   @default(false)
  
  @@index([isCurrent])
}
```

## B.2 Entity Relationship Diagram (ASCII)

```
Department 1─────* Agent
                    │
                    │ 1                       1
                    ├──* AgentCert ────1 CertSnapshot
                    │                        │
                    │                        │ 1
                    │                        └──── (signed bundle in S3)
                    │
                    ├──* Run ─────1 Scenario ──── 1 Pack
                    │     │                          │
                    │     │                          └─ 1 ReadinessGate
                    │     │
                    │     ├──* TraceEvent
                    │     ├──1 Scorecard
                    │     ├──* SoftwareGap
                    │     ├──* VillageOSGap
                    │     ├──1 CCB (pre)
                    │     └──1 CCB (post)
                    │
                    ├──* AutonomyEvent
                    └──* CognitiveSnapshot (daily canary — v1.2)

Department 1─────* DeptCert ────1 CertSnapshot
                        │
                        └──* CertLifecycleEvent

Constitution 1──* ConstitutionalAmendment

ObjectRegistryEntry (urn) ─── (referenced by URN in all lineage)

LineageEdge * → * (URN → URN via relationType)
```

## B.3 Index & Query Patterns

**Hot query paths:**
1. Readiness Gate Matrix: `SELECT agent × forge_cap WHERE status='active'` — use composite index on `AgentCert(agentId, forgeCap, status)`.
2. Recent runs for agent: `Run WHERE agentId=? ORDER BY startedAt DESC LIMIT 20` — uses `Run(agentId, startedAt)` index.
3. Gap dashboards: `SoftwareGap WHERE forge=? AND severity=? AND status='open'` — uses `SoftwareGap(forge, severity, status)` composite.
4. Lineage queries: both directions covered by `LineageEdge(fromUrn)` and `LineageEdge(toUrn)` indexes.
5. CCB retrieval: `CCB WHERE agentVillageId=? AND phase=?` — composite index.
6. Cert expiration sweep (nightly worker): `AgentCert WHERE expiresAt < now() + interval '7 days' AND status='active'` — uses `AgentCert(expiresAt)` index.

**Cold queries (accept full scans):**
- Historical evidence retrieval (S3 side, not Postgres).
- Lineage path-finding more than 5 hops (use recursive CTEs; limit depth).

## B.4 Migration Strategy

- Prisma drives schema; `prisma migrate dev` in dev, `prisma migrate deploy` in staging/prod.
- Every migration reviewed by 2 engineers before merge.
- Destructive migrations (column drops, type changes on populated columns) require: staging soak ≥ 7 days + explicit Ivan sign-off.
- Rollback plan required in migration PR description.
- Large-table migrations (Run, TraceEvent, CCB) require concurrent-index creation and zero-downtime patterns.

## B.5 Seed Data Strategy

**Dev seed (`packages/db/seed.ts`):**
- 13 departments from Village org chart.
- ~20 agents (subset of 106, those referenced in sample scenarios).
- 1 Pack per venture (Greenstone, MedLink Pro).
- 3 scenarios per Pack (~6 total).
- 1 Constitution v1.0.0 record.
- Sample ObjectRegistryEntry for each agent/department.

**Staging seed:** Full 106 agents + 13 depts; full Packs (after Week 4 ingestion); empty cert registry.

**Prod seed:** Identical to staging minus dev fixtures.

## B.6 Archival & Retention

| Data | Retention | Storage Tier | Post-retention |
|---|---|---|---|
| Run (metadata row) | Indefinite | PG hot | Partitioned by month after 12mo |
| TraceEvent | 12 months | PG hot → warm (PG partitioned) | Summarized into Run.summary after 12mo |
| CCB | 36 months | PG hot → S3 cold after 12mo | Referenced, still retrievable |
| Scorecard | Indefinite | PG hot | Partitioned by year after 36mo |
| SoftwareGap / VillageOSGap | Indefinite (with status lifecycle) | PG hot | Closed tickets archived after 24mo |
| AgentCert / DeptCert | Indefinite | PG hot | — |
| CertSnapshot | Indefinite | PG hot (metadata) + S3 (bundle) | Never purged (legal/audit) |
| Evidence bundles | 7 years (HIPAA-adjacent) | S3 tiered (hot 30d → warm 1y → cold Glacier) | Purged per lifecycle + legal hold check |
| AutonomyEvent | 36 months | PG | Summarized |
| LineageEdge | Indefinite | PG | Skeleton survives evidence purge |
| Constitution | Indefinite | PG | — |
| TraceEvent older than 12mo | — | — | Archived to S3 Parquet for analytics |

---

# PART C — BACKEND SERVICES

## C.1 FastAPI Application Topology

```python
# apps/api/src/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from src.config import settings
from src.db import engine, dispose_engine
from src.telemetry.logging import configure_logging
from src.telemetry.tracing import configure_tracing
from src.telemetry.metrics import configure_metrics
from src.routers import (
    health, agents, departments, packs, scenarios, runs,
    certs, snapshots, gaps, dashboard, registry, lineage,
    constitution, attest
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    configure_tracing()
    configure_metrics()
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(
        title="SimForge API",
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    FastAPIInstrumentor.instrument_app(app)

    # Routers
    app.include_router(health.router,         prefix="/api/health")
    app.include_router(agents.router,         prefix="/api/agents",         tags=["agents"])
    app.include_router(departments.router,    prefix="/api/departments",    tags=["departments"])
    app.include_router(packs.router,          prefix="/api/packs",          tags=["packs"])
    app.include_router(scenarios.router,      prefix="/api/scenarios",      tags=["scenarios"])
    app.include_router(runs.router,           prefix="/api/runs",           tags=["runs"])
    app.include_router(certs.router,          prefix="/api/certs",          tags=["certs"])
    app.include_router(snapshots.router,      prefix="/api/snapshots",      tags=["snapshots"])
    app.include_router(gaps.router,           prefix="/api/gaps",           tags=["gaps"])
    app.include_router(dashboard.router,      prefix="/api/dashboard",      tags=["dashboard"])
    app.include_router(registry.router,       prefix="/api/registry",       tags=["registry"])
    app.include_router(lineage.router,        prefix="/api/lineage",        tags=["lineage"])
    app.include_router(constitution.router,   prefix="/api/constitution",   tags=["constitution"])
    app.include_router(attest.router,         prefix="/api/attest",         tags=["attestation"])

    return app


app = create_app()
```

## C.2 Service Modules (Overview)

| Module | Role | LOC estimate |
|---|---|---|
| `services/village/` | Read-only coupling to Village | 600 |
| `services/scenario_engine/` | Scenario runner + branching | 900 |
| `services/agent_runtime/` | SimForge internal agent + LLM client | 500 |
| `services/mock_world/` | Forge proxies + personas | 1200 |
| `services/evaluation/` | 15-dim rubric + gate | 1500 |
| `services/reporter/` | Triple-report generation + routing | 400 |
| `services/cert/` | Registry + snapshot + signer + autonomy | 800 |
| `services/governance/` | Constitution + amendments + approvals | 500 |
| `services/registry/` | Object Registry + Lineage | 400 |
| `services/forges/` | 6 Forge adapters | 900 |
| `services/evidence/` | S3 bundle + lifecycle | 300 |
| `services/compliance/` | Rules engine + jurisdiction packs | 700 |
| **Total services LOC** | | **~8,700** |

## C.3 Router Endpoints (Complete)

### C.3.1 `/api/health`

| Method | Path | Purpose | Response |
|---|---|---|---|
| GET | `/` | Liveness | `{status: "ok"}` |
| GET | `/ready` | Readiness (DB + Redis + Village fs + Forge sandboxes) | `{status, checks: {...}}` |
| GET | `/village-fingerprint` | Current Village schema fingerprint | `{fingerprint, captured_at, drift_detected}` |

### C.3.2 `/api/agents`

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | List Village agents (paginated, filterable by department/autonomy level) |
| GET | `/{village_agent_id}` | Agent detail + current certs + recent runs |
| GET | `/{village_agent_id}/ccb/latest` | Latest CCB snapshot |
| GET | `/{village_agent_id}/autonomy-history` | Autonomy ladder event log |
| GET | `/{village_agent_id}/cognitive-trends` | Trends across 7 cognitive dims over N days |
| POST | `/{village_agent_id}/autonomy/downgrade` | Manual downgrade (Ivan only, audited) |
| POST | `/{village_agent_id}/autonomy/promote` | Manual promotion (Ivan only, audited) |

### C.3.3 `/api/departments`

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | All departments with agent counts |
| GET | `/{village_key}` | Department detail + agents + dept certs |
| GET | `/{village_key}/coverage` | Coverage matrix across Forge-contexts |

### C.3.4 `/api/packs`

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | List Packs |
| GET | `/{pack_id}` | Pack detail + scenarios |
| GET | `/{pack_id}/coverage` | Coverage heatmap data |
| POST | `/` | Register a Pack (ingests YAML, validates, creates entity) |
| POST | `/{pack_id}/validate` | Re-run validator |
| POST | `/{pack_id}/sign` | Owner-human signature (ratification) |
| POST | `/{pack_id}/deprecate` | Soft-deprecate (no new certs, existing stand) |

### C.3.5 `/api/scenarios`

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | List scenarios (filterable) |
| GET | `/{scenario_id}` | Detail + history of runs |
| POST | `/{scenario_id}/run` | Enqueue a run (sandbox default) |
| POST | `/{scenario_id}/run-battery` | Enqueue cert battery (blind subset applied) |

### C.3.6 `/api/runs`

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | List runs (filters: agent, scenario, status, date range) |
| GET | `/{run_id}` | Run detail (metadata only) |
| GET | `/{run_id}/transcript` | Full transcript |
| GET | `/{run_id}/trace` | TraceEvent list |
| GET | `/{run_id}/scorecard` | Scorecard |
| GET | `/{run_id}/evidence` | Signed URL to S3 bundle |
| POST | `/{run_id}/cancel` | Cancel running scenario |
| POST | `/{run_id}/replay` | Time-travel replay (v1.1+) |

### C.3.7 `/api/certs`

| Method | Path | Purpose |
|---|---|---|
| GET | `/agent` | List AgentCerts (filterable) |
| GET | `/dept` | List DeptCerts |
| GET | `/agent/{cert_id}` | AgentCert detail + CertSnapshot + history |
| GET | `/dept/{cert_id}` | DeptCert detail |
| POST | `/agent/issue` | Issue AgentCert (Ivan-approved) |
| POST | `/dept/issue` | Issue DeptCert (Ivan-approved, preconditions checked) |
| POST | `/agent/{cert_id}/renew` | Renew before expiration |
| POST | `/agent/{cert_id}/revoke` | Manual revocation (audited) |
| POST | `/agent/{cert_id}/suspend` | Suspend pending review |
| POST | `/dept/{cert_id}/revoke` | Manual dept revocation |

### C.3.8 `/api/snapshots`

| Method | Path | Purpose |
|---|---|---|
| GET | `/{snapshot_id}` | CertSnapshot detail (metadata + pinned versions) |
| GET | `/{snapshot_id}/verify` | Verify signature against public keys |
| GET | `/{snapshot_id}/evidence` | Redacted evidence export (external auditor mode) |

### C.3.9 `/api/gaps`

| Method | Path | Purpose |
|---|---|---|
| GET | `/software` | List SoftwareGaps (paginated, filterable) |
| GET | `/village-os` | List VillageOSGaps |
| GET | `/software/{ticket_id}` | Gap detail |
| POST | `/software/{ticket_id}/update-status` | Update from Linear webhook |
| GET | `/top-10/forge/{forge}` | Top-10 gaps per Forge |
| GET | `/top-10/village-os` | Top-10 Village OS gaps |

### C.3.10 `/api/dashboard`

| Method | Path | Purpose |
|---|---|---|
| GET | `/readiness-matrix` | Agent × Forge-cap + Dept × Forge-context grids |
| GET | `/coverage-heatmap/{pack_id}` | (role × stage) coverage |
| GET | `/cognitive-trends` | Village-wide cognitive state trends |
| GET | `/throughput` | Runs/day, parallelism, cost |
| GET | `/cohort-analytics/{department}` | Department-level cognitive drift (v1.1) |

### C.3.11 `/api/registry`

| Method | Path | Purpose |
|---|---|---|
| GET | `/urn/{urn}` | Resolve URN to entity |
| GET | `/kind/{kind}` | List entries by kind |
| POST | `/` | Register new entity |
| POST | `/{urn}/tombstone` | Soft-delete with audit |
| POST | `/{urn}/merge` | Merge two entities (audited) |

### C.3.12 `/api/lineage`

| Method | Path | Purpose |
|---|---|---|
| GET | `/from/{urn}` | Forward edges |
| GET | `/to/{urn}` | Backward edges |
| GET | `/path?from={urn}&to={urn}&max_depth=5` | Path search |
| GET | `/subgraph/{urn}?hops=2` | Neighborhood |

### C.3.13 `/api/constitution`

| Method | Path | Purpose |
|---|---|---|
| GET | `/current` | Current active version |
| GET | `/{version}` | Specific version |
| GET | `/history` | Amendment history |
| POST | `/amendments` | Propose amendment (starts cooling period) |
| POST | `/amendments/{id}/withdraw` | Withdraw before cooling ends |
| POST | `/amendments/{id}/ratify` | Ratify (Ivan + quorum) |
| POST | `/amendments/{id}/veto` | Founder veto |

### C.3.14 `/api/attest` (external verifier)

| Method | Path | Purpose |
|---|---|---|
| GET | `/cert/{cert_id}` | Signed attestation of certification status |
| GET | `/cert/{cert_id}/evidence` | Redacted evidence (with bearer token) |
| GET | `/public-keys` | Active signing public keys + CRL |

## C.4 Pydantic Schemas (Exemplar)

```python
# apps/api/src/schemas/cert.py

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Literal, Optional


class PinnedVersions(BaseModel):
    pack: str
    scenario_library_hash: str
    policy_snapshot_id: str
    rubric_version: str
    constitution_version: str
    agent_prompt_version: str
    agent_model: str
    forge_versions: dict[str, str]
    village_os_version: str
    village_schema_fingerprint: str


class CertSnapshotResponse(BaseModel):
    snapshot_id: str
    cert_type: Literal["agent_forge_cap", "dept_forge_context"]
    subject: str
    forge_cap: Optional[str] = None
    forge_context: Optional[str] = None
    tier: Literal["foundational", "intermediate", "advanced_crisis"]
    issued_at: datetime
    expires_at: datetime
    pinned_versions: PinnedVersions
    evidence_bundle_ref: str
    signing_key_id: str
    content_hash: str


class AgentCertDetail(BaseModel):
    cert_id: str
    agent_village_id: str
    forge_cap: str
    tier: Literal["foundational", "intermediate", "advanced_crisis"]
    status: Literal["active", "expired", "revoked", "suspended"]
    issued_at: datetime
    expires_at: datetime
    cert_snapshot: CertSnapshotResponse
    lifecycle_events: list["CertLifecycleEventResponse"]


class IssueAgentCertRequest(BaseModel):
    agent_village_id: str
    forge_cap: str
    tier: str
    battery_run_ids: list[str] = Field(..., min_items=18,
                                       description="Minimum 18-scenario battery required")
    approver_id: str
    pack_id: str
```

Repeat for every router — ~50 Pydantic schemas total.

## C.5 Background Workers

**Worker queues (Redis / RQ):**

| Worker | Queue | Trigger | SLA |
|---|---|---|---|
| `runner_worker` | `runs` | `POST /scenarios/{id}/run` | Per-run SLO in scenario |
| `eval_worker` | `eval` | Run completes → enqueued | < 30s per run |
| `reporter_worker` | `reports` | Scorecard saved → enqueued | < 60s per run |
| `cert_lifecycle_worker` | `cert-lifecycle` | Nightly at 02:00 UTC | < 5 min |
| `regression_worker` | `regression` | Nightly at 03:00 UTC (after lifecycle) | < 60 min for full battery |
| `fingerprint_worker` | `fingerprint` | Nightly at 01:00 UTC | < 1 min |
| `evidence_archival_worker` | `evidence` | Hourly | Ongoing |
| `pack_validator_worker` | `validation` | On Pack PR | < 30s per Pack |

Worker process: `rq worker runs eval reports cert-lifecycle regression fingerprint evidence validation` in staging/prod.

## C.6 Village Reader Module (Detailed)

```python
# apps/api/src/services/village/reader.py

from pathlib import Path
import json
import hashlib
from dataclasses import dataclass
from typing import Optional

from src.config import settings


class VillageReaderError(Exception):
    pass


class VillageSchemaFingerprintMismatch(VillageReaderError):
    pass


@dataclass(frozen=True)
class VillageReader:
    village_data_path: Path
    
    @classmethod
    def from_settings(cls) -> "VillageReader":
        path = Path(settings.village_data_path)
        if not path.exists():
            raise VillageReaderError(f"VILLAGE_DATA_PATH does not exist: {path}")
        if not path.is_dir():
            raise VillageReaderError(f"VILLAGE_DATA_PATH is not a directory: {path}")
        return cls(village_data_path=path)
    
    def agent_root(self, agent_village_id: str) -> Path:
        p = self.village_data_path / "agents" / agent_village_id
        if not p.exists():
            raise VillageReaderError(f"Agent not found: {agent_village_id}")
        return p
    
    # ---- BREATH ----
    
    def get_agent_breath(self, agent_village_id: str) -> dict:
        knowledge = self.agent_root(agent_village_id) / "knowledge"
        breath = {}
        for component in ["beliefs", "rituals", "ethics", "attachments", "traditions", "habits"]:
            comp_dir = knowledge / component
            if not comp_dir.exists():
                breath[component] = {}
                continue
            breath[component] = {}
            for json_file in comp_dir.glob("*.json"):
                with open(json_file, "r") as f:
                    breath[component][json_file.stem] = json.load(f)
        return breath
    
    # ---- FOT ----
    
    def get_agent_fot(self, agent_village_id: str) -> dict:
        fot_path = self.agent_root(agent_village_id) / "knowledge" / "fot" / "fot_index.json"
        if not fot_path.exists():
            return {}
        with open(fot_path, "r") as f:
            return json.load(f)
    
    # ---- SOUL ----
    
    def get_agent_soul(self, agent_village_id: str) -> dict:
        ledger_dir = self.agent_root(agent_village_id) / "emotional_ledger"
        if not ledger_dir.exists():
            return {"ledger": {}, "current_state": {}}
        soul = {"ledger": {}}
        for ledger_file in ledger_dir.glob("*.json"):
            with open(ledger_file, "r") as f:
                soul["ledger"][ledger_file.stem] = json.load(f)
        return soul
    
    # ---- Episodes ----
    
    def get_agent_episodes(self, agent_village_id: str, limit: int = 10) -> list[dict]:
        episodes_dir = self.agent_root(agent_village_id) / "knowledge" / "learned" / "episodes"
        if not episodes_dir.exists():
            return []
        episodes = []
        for ep_file in sorted(episodes_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
            with open(ep_file, "r") as f:
                episodes.append(json.load(f))
        return episodes
    
    # ---- ARC ----
    
    def get_agent_arc(self, agent_village_id: str) -> dict:
        # ARC state lives in memory/ or is derived; v1 reads persisted form
        arc_path = self.agent_root(agent_village_id) / "memory" / "arc_state.json"
        if not arc_path.exists():
            return {"current_phase": "unknown", "dominant_themes": [], "identity_dimensions": {}}
        with open(arc_path, "r") as f:
            return json.load(f)
    
    # ---- ECHO / HFM / DRIFT / AME / GAME / MATE ----
    # Similar pattern — each has its own persistence path per Village OS doc
    # (methods elided for brevity; see apps/api/src/services/village/reader.py full)
    
    # ---- Department roster ----
    
    def get_department_roster(self, dept_village_key: str) -> list[dict]:
        roster_path = self.village_data_path.parent / "config" / "agentsrole.yaml"
        # Parse YAML, return agents for the department
        import yaml
        with open(roster_path, "r") as f:
            data = yaml.safe_load(f)
        return data.get("departments", {}).get(dept_village_key, {}).get("agents", [])
    
    # ---- Schema fingerprint ----
    
    def get_village_schema_fingerprint(self) -> str:
        """Hash of the structural paths of VillageData — detects drift."""
        hasher = hashlib.sha256()
        # Hash sorted list of structural paths (directory shape + well-known files)
        structural_paths = []
        for agent_dir in sorted((self.village_data_path / "agents").iterdir()):
            if agent_dir.is_dir():
                structural_paths.append(agent_dir.name)
                for subdir in ["knowledge", "emotional_ledger", "memory", "tasks"]:
                    subdir_path = agent_dir / subdir
                    if subdir_path.exists():
                        structural_paths.append(f"{agent_dir.name}/{subdir}")
        hasher.update("\n".join(sorted(structural_paths)).encode())
        return hasher.hexdigest()
    
    def verify_fingerprint(self, expected: str) -> None:
        actual = self.get_village_schema_fingerprint()
        if actual != expected:
            raise VillageSchemaFingerprintMismatch(
                f"Village schema drifted. Expected: {expected[:12]}..., Got: {actual[:12]}..."
            )
```

## C.7 CCB Composer

```python
# apps/api/src/services/village/ccb_composer.py

import hashlib
import json
from datetime import datetime, timezone
from typing import Literal
from ulid import ULID

from src.services.village.reader import VillageReader
from src.schemas.ccb import CCB


class CCBComposer:
    def __init__(self, reader: VillageReader):
        self.reader = reader
    
    def compose(
        self,
        agent_village_id: str,
        phase: Literal["pre", "post"],
        village_schema_fingerprint: str,
    ) -> CCB:
        game    = self._read_game(agent_village_id)
        mate    = self._read_mate(agent_village_id)
        soul    = self.reader.get_agent_soul(agent_village_id)
        breath  = self.reader.get_agent_breath(agent_village_id)
        fot     = self.reader.get_agent_fot(agent_village_id)
        hfm     = self._read_hfm(agent_village_id)
        arc     = self.reader.get_agent_arc(agent_village_id)
        echo    = self._read_echo(agent_village_id)
        drift   = self._read_drift(agent_village_id)
        ame     = self._read_ame(agent_village_id)
        
        payload = {
            "game": game, "mate": mate, "soul": soul, "breath": breath,
            "fot": fot, "hfm": hfm, "arc": arc, "echo": echo,
            "drift": drift, "ame": ame,
        }
        content_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()
        
        return CCB(
            snapshot_id=str(ULID()),
            agent_village_id=agent_village_id,
            phase=phase,
            taken_at=datetime.now(timezone.utc),
            content_hash=content_hash,
            village_schema_fingerprint=village_schema_fingerprint,
            **payload,
        )
    
    def _read_game(self, agent_id: str) -> dict:
        # Reads memory events + active goals from VillageData + village.db
        # (implementation details — queries village.db for agent's goals,
        #  reads memory/ for last N events)
        return {}  # scaffolded
    
    # ... similar stubs for _read_mate, _read_hfm, _read_echo, _read_drift, _read_ame
```

## C.8 SimForge-Internal Agent Runtime

**Purpose:** Replicates the Village's 9-layer system-prompt assembly so SimForge can exercise the agent without touching the Village's orchestrator.

```python
# apps/api/src/services/agent_runtime/runtime.py

from dataclasses import dataclass
from src.services.village.reader import VillageReader
from src.services.agent_runtime.llm_client import LLMClient


@dataclass
class AgentRuntime:
    village_reader: VillageReader
    llm_client: LLMClient
    
    def assemble_system_prompt(self, agent_village_id: str) -> str:
        """Replicates Village AgentOrchestrator._build_system_prompt() — 9 layers."""
        parts = []
        
        # Layer 1: Base identity
        agent = self._load_agent_identity(agent_village_id)
        parts.append(f"You are {agent['name']}, a {agent['role']}.")
        if agent.get("backstory"):
            parts.append(f"Backstory: {agent['backstory']}")
        if agent.get("personality_traits"):
            parts.append(f"Personality traits: {', '.join(agent['personality_traits'])}")
        
        # Layer 2: BREATH
        breath = self.village_reader.get_agent_breath(agent_village_id)
        parts.append(self._format_breath(breath))
        
        # Layer 3: FOT + Social-FOT + behavioral modifiers
        fot = self.village_reader.get_agent_fot(agent_village_id)
        parts.append(self._format_fot(fot))
        
        # Layer 4: SOUL current emotional state
        soul = self.village_reader.get_agent_soul(agent_village_id)
        parts.append(self._format_soul_state(soul))
        
        # Layer 5: Communication style (Level 7 placeholder in v1)
        # Layer 6: Meta-cognition hints (Level 7 placeholder in v1)
        # Layer 7: Level 9 org context (placeholder in v1)
        # Layer 8: Level 10 (Gardner only — skipped in v1 for non-Gardner)
        # Layer 9: Memory + RAG
        episodes = self.village_reader.get_agent_episodes(agent_village_id, limit=5)
        parts.append(self._format_recent_memory(episodes))
        
        parts.append("\nRespond in character, naturally and engagingly.")
        return "\n\n".join(parts)
    
    async def turn(
        self,
        agent_village_id: str,
        scenario_context: str,
        conversation_history: list[dict],
    ) -> dict:
        system_prompt = self.assemble_system_prompt(agent_village_id)
        response = await self.llm_client.complete(
            system=system_prompt,
            messages=conversation_history,
            route=self._select_route(agent_village_id),
        )
        return response
```

## C.9 Scenario Runner State Machine

```
               ┌──────────────────────────────────────────┐
               │                                          │
               ▼                                          │
┌─────────────────┐     ┌─────────────┐     ┌────────────┴────┐
│   PENDING       │────▶│   SETUP     │────▶│  COLD_OPEN      │
│ (enqueued)      │     │ (fixtures,  │     │ (scenario       │
│                 │     │  CCB pre)   │     │  presented)     │
└─────────────────┘     └─────────────┘     └────────┬────────┘
                                                     │
                            ┌────────────────────────┘
                            ▼
                    ┌───────────────┐     complication trigger
                    │   TURN        │────▶──────────────┐
                    │ (agent turn + │                   ▼
                    │  world resp)  │           ┌──────────────┐
                    └───────┬───────┘           │ COMPLICATION │
                            │                   │  (injected)  │
                            │  slo exceeded     └──────┬───────┘
                            │  or outcome met          │
                            ▼                          │
                    ┌───────────────┐◀─────────────────┘
                    │  RESOLUTION   │
                    └───────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
      ┌──────────┐   ┌──────────┐   ┌──────────┐
      │  PASSED  │   │  FAILED  │   │ ERRORED  │
      └────┬─────┘   └────┬─────┘   └────┬─────┘
           │              │              │
           └──────────────┼──────────────┘
                          ▼
                  ┌──────────────┐
                  │    WRAP      │
                  │ (CCB post,   │
                  │  transcript, │
                  │  evidence)   │
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
                  │ eval queue   │
                  └──────────────┘
```

Implementation sketch:

```python
# apps/api/src/services/scenario_engine/runner.py

from enum import Enum
from src.services.scenario_engine.state import RunState
from src.services.scenario_engine.complications import ComplicationInjector
from src.services.agent_runtime.runtime import AgentRuntime


class Phase(Enum):
    PENDING = "pending"
    SETUP = "setup"
    COLD_OPEN = "cold_open"
    TURN = "turn"
    COMPLICATION = "complication"
    RESOLUTION = "resolution"
    WRAP = "wrap"


class ScenarioRunner:
    def __init__(
        self,
        scenario: dict,
        agent_runtime: AgentRuntime,
        mock_world,
        complication_injector: ComplicationInjector,
        random_seed: int,
    ):
        self.scenario = scenario
        self.agent_runtime = agent_runtime
        self.mock_world = mock_world
        self.complication_injector = complication_injector
        self.random_seed = random_seed
    
    async def run(self, run_id: str, agent_village_id: str) -> RunState:
        state = RunState(run_id=run_id, agent_village_id=agent_village_id, phase=Phase.PENDING)
        
        state.phase = Phase.SETUP
        await self._setup(state)
        
        state.phase = Phase.COLD_OPEN
        state.transcript.append({"role": "scenario", "content": self.scenario["cold_open"]})
        
        while not self._is_terminal(state):
            state.phase = Phase.TURN
            agent_response = await self.agent_runtime.turn(
                agent_village_id, self.scenario["cold_open"], state.transcript
            )
            state.transcript.append({"role": "agent", "content": agent_response["content"]})
            state.turn_count += 1
            
            # World responds (mock persona or Forge action)
            world_response = await self.mock_world.respond(state, agent_response)
            state.transcript.append({"role": "world", "content": world_response})
            
            # Check for complications
            if self.complication_injector.should_inject(state):
                state.phase = Phase.COMPLICATION
                await self.complication_injector.inject(state)
            
            # SLO check
            if state.elapsed_seconds > self.scenario["slo_seconds"] * 1.5:
                state.outcome = "slo_exceeded"
                break
        
        state.phase = Phase.RESOLUTION
        self._classify_outcome(state)
        
        state.phase = Phase.WRAP
        await self._wrap(state)
        
        return state
```

## C.10 Evaluation Engine

**Orchestrator (`evaluation/rubric.py`)**

```python
# apps/api/src/services/evaluation/rubric.py

import asyncio
from src.services.evaluation.dimensions import (
    p1_correctness, p2_compliance, p3_process_fidelity,
    p4_time_to_resolution, p5_escalation, p6_doc_quality,
    p7_cx, p8_cost,
    c1_breath_coherence, c2_soul_stability, c3_fot_management,
    c4_arc_coherence, c5_echo_regret, c6_hfm_drive, c7_ame_trajectory,
)


class RubricEvaluator:
    """Runs all 15 dimension scorers in parallel against a completed run."""
    
    async def evaluate(self, run, ccb_pre, ccb_post, scenario, pack):
        # Performance dims
        perf_coros = [
            p1_correctness.score(run, scenario),
            p2_compliance.score(run, scenario, pack),
            p3_process_fidelity.score(run, scenario),
            p4_time_to_resolution.score(run, scenario),
            p5_escalation.score(run, scenario),
            p6_doc_quality.score(run, scenario),
            p7_cx.score(run, scenario),
            p8_cost.score(run, scenario),
        ]
        # Cognitive dims
        cog_coros = [
            c1_breath_coherence.score(run, ccb_pre, ccb_post),
            c2_soul_stability.score(run, ccb_pre, ccb_post),
            c3_fot_management.score(run, ccb_pre, ccb_post),
            c4_arc_coherence.score(run, ccb_pre, ccb_post),
            c5_echo_regret.score(run, ccb_pre, ccb_post),
            c6_hfm_drive.score(run, ccb_pre, ccb_post),
            c7_ame_trajectory.score(run, ccb_pre, ccb_post),
        ]
        
        results = await asyncio.gather(*perf_coros, *cog_coros)
        return self._assemble_scorecard(results, scenario, pack)
```

**Readiness Gate (`evaluation/readiness_gate.py`)**

```python
class ReadinessGate:
    def check(self, scorecard, pack) -> dict:
        rg = pack.readiness_gate
        failures = []
        
        # P2 Compliance — auto-fail
        if scorecard.p2_compliance is not True:
            return {"passed": False, "auto_fail_reason": "compliance_violation"}
        
        # C4 ARC fragmentation — auto-fail
        if scorecard.c4_arc_narrative_coherence in ("sudden_shift", "regression", "fragmentation"):
            return {"passed": False, "auto_fail_reason": "arc_" + scorecard.c4_arc_narrative_coherence}
        
        # Performance dim thresholds
        tier = scorecard.run.scenario.tier
        perf_threshold = rg.tier_thresholds[tier]
        for dim in ("p1_correctness", "p3_process_fidelity", "p4_time_to_resolution",
                    "p5_escalation", "p6_doc_quality", "p7_customer_experience", "p8_cost_discipline"):
            if getattr(scorecard, dim, 0) < perf_threshold:
                failures.append(f"{dim} below {perf_threshold}")
        
        # Cognitive aggregate
        cog_dims = ["c1_breath_coherence", "c2_soul_stability", "c3_fot_pressure_management",
                    "c5_echo_regret_load", "c6_hfm_drive_balance", "c7_ame_reputation_trajectory"]
        cog_values = [getattr(scorecard, d, 0) for d in cog_dims]
        cog_agg = sum(cog_values) / len(cog_values)
        if cog_agg < rg.cognitive_aggregate_min:
            failures.append(f"cognitive_aggregate {cog_agg:.2f} < {rg.cognitive_aggregate_min}")
        
        if failures:
            return {"passed": False, "auto_fail_reason": None, "failures": failures}
        return {"passed": True, "auto_fail_reason": None}
```

## C.11 Triple Reporter

```python
# apps/api/src/services/reporter/__init__.py

from src.services.reporter.scorecard import ScorecardBuilder
from src.services.reporter.software_gap import SoftwareGapDetector
from src.services.reporter.village_os_gap import VillageOSGapDetector
from src.services.reporter.linear_client import LinearClient


class Reporter:
    def __init__(self, linear: LinearClient):
        self.scorecard_builder = ScorecardBuilder()
        self.software_gap_detector = SoftwareGapDetector()
        self.village_os_gap_detector = VillageOSGapDetector()
        self.linear = linear
    
    async def emit(self, run, ccb_pre, ccb_post, rubric_result, gate_result):
        # 1. Agent Scorecard
        scorecard = self.scorecard_builder.build(run, ccb_pre, ccb_post, rubric_result, gate_result)
        await scorecard.persist()
        
        # 2. Software Gap Report (per Forge traces)
        software_gaps = self.software_gap_detector.detect(run)
        for gap in software_gaps:
            await gap.persist()
            await self.linear.create_ticket(
                project=f"{gap.forge}-gaps",
                title=f"[{gap.severity}] {gap.summary}",
                description=gap.detail,
                metadata={"simforge_ticket_id": gap.ticket_id, "run_id": run.run_id},
            )
        
        # 3. Village OS Gap Report (per framework anomalies in CCB diff)
        vos_gaps = self.village_os_gap_detector.detect(run, ccb_pre, ccb_post)
        for gap in vos_gaps:
            await gap.persist()
            await self.linear.create_ticket(
                project="village-os-gaps",
                title=f"[{gap.severity}] {gap.framework}: {gap.summary}",
                description=gap.detail,
                metadata={"simforge_ticket_id": gap.ticket_id, "run_id": run.run_id},
            )
        
        return {"scorecard": scorecard, "software_gaps": software_gaps, "vos_gaps": vos_gaps}
```

## C.12 Signing & Attestation Service

```python
# apps/api/src/services/cert/signer.py

from abc import ABC, abstractmethod
from src.services.cert.snapshot import CertSnapshotPayload


class Signer(ABC):
    @abstractmethod
    async def sign(self, payload: bytes) -> bytes: ...
    
    @abstractmethod
    def get_public_key(self) -> bytes: ...
    
    @abstractmethod
    def get_key_id(self) -> str: ...


class AwsCloudHsmSigner(Signer):
    """Production signer — FIPS 140-2 Level 3."""
    def __init__(self, key_handle: str): ...
    async def sign(self, payload: bytes) -> bytes: ...
    def get_public_key(self) -> bytes: ...
    def get_key_id(self) -> str: ...


class YubiHsmSigner(Signer):
    """Staging signer — YubiHSM 2."""
    def __init__(self, slot_id: int): ...
    async def sign(self, payload: bytes) -> bytes: ...


class StubSigner(Signer):
    """Dev-only. Uses local Ed25519 key. NEVER use in prod."""
    def __init__(self, private_key_pem_path: str): ...
    async def sign(self, payload: bytes) -> bytes: ...


def get_signer() -> Signer:
    provider = settings.hsm_provider
    if provider == "aws-cloudhsm":
        return AwsCloudHsmSigner(settings.simforge_root_key_id)
    elif provider == "yubihsm":
        return YubiHsmSigner(int(settings.simforge_root_key_id))
    elif provider == "stub":
        return StubSigner(settings.simforge_signing_private_key_path)
    raise ValueError(f"Unknown HSM provider: {provider}")


class CertSnapshotIssuer:
    def __init__(self, signer: Signer):
        self.signer = signer
    
    async def issue(self, payload: CertSnapshotPayload) -> "CertSnapshot":
        canonical = payload.canonical_json()
        content_hash = hashlib.sha256(canonical.encode()).hexdigest()
        signature = await self.signer.sign(canonical.encode())
        return CertSnapshot(
            snapshot_id=f"certsnap:{content_hash[:16]}",
            content_hash=content_hash,
            signature=base64.b64encode(signature).decode(),
            signing_key_id=self.signer.get_key_id(),
            **payload.dict(),
        )
```

---

# PART D — FRONTEND

## D.1 Next.js App Structure

See §A.5 for the full page tree. Key patterns:

- **App Router + RSC** for data-heavy read pages (Readiness Matrix, Run detail).
- **Client components** only where interactivity demands (filters, real-time updates).
- **Streaming SSR** for heavy dashboards.
- **Server actions** for mutations that don't need full API round-trip.

## D.2 Page Tree (Key Routes)

| Route | Purpose | Data load pattern |
|---|---|---|
| `/` | Marketing landing | Static |
| `/login` | Clerk login | Client |
| `/dashboard` | Overview dashboard | RSC with TanStack query hydration |
| `/dashboard/readiness` | Readiness Gate Matrix | RSC + streaming |
| `/dashboard/runs` | Run list | Paginated, filterable, RSC |
| `/dashboard/runs/[runId]` | Run detail + scorecard + transcript + CCB diff | RSC |
| `/dashboard/packs` | Pack list | RSC |
| `/dashboard/packs/[packId]` | Pack detail + coverage heatmap + scenarios | RSC |
| `/dashboard/packs/[packId]/scenarios/[id]` | Scenario detail + run history | RSC |
| `/dashboard/gaps/software` | Software gap table | RSC + client filters |
| `/dashboard/gaps/village-os` | Village OS gap table | RSC + client filters |
| `/dashboard/agents` | Agent directory | RSC |
| `/dashboard/agents/[agentId]` | Agent profile + certs + cognitive trends | RSC |
| `/dashboard/departments` | Department list | RSC |
| `/dashboard/departments/[deptId]` | Department detail + dept certs | RSC |
| `/dashboard/certs` | Certification Registry | RSC |
| `/dashboard/certs/[certId]` | Cert detail + snapshot + lifecycle | RSC |
| `/dashboard/constitution` | Current constitution + amendments | RSC |
| `/dashboard/registry` | Object Registry browser (v1.1) | Client-heavy |
| `/dashboard/lineage` | Lineage graph explorer (v1.1) | Client-heavy |

## D.3 Component Library

Built on shadcn/ui primitives. Custom components:

| Component | Responsibility | Used in |
|---|---|---|
| `<ReadinessGateMatrix />` | Agent × Forge-cap grid with status cells | `/dashboard/readiness` |
| `<CertCell status tier expires />` | Individual matrix cell with status dot + tier pill | `<ReadinessGateMatrix />` |
| `<ScorecardCard />` | Compact 15-dim radar chart + gate status | Run detail, cert detail |
| `<FifteenDimChart />` | Full radar/bar view of 15 dims | Run detail |
| `<CCBDiffViewer ccbPre ccbPost />` | Side-by-side framework state diff | Run detail |
| `<TurnAnnotationList />` | Chronological turn annotations with tags | Run detail |
| `<RunTimeline />` | Horizontal scrub UI across run phases | Run detail |
| `<CoverageHeatmap pack />` | (role × stage) heatmap | Pack detail |
| `<CohortHeatmap cohort dim />` | Cognitive drift across department | Cohort dashboard (v1.1) |
| `<GapTable forge />` | Filterable gap list | Gaps pages |
| `<Top10GapsWidget />` | Sidebar widget | Dashboard overview |
| `<AgentCard agent />` | Agent card with FOT tier + autonomy indicator | Agents directory |
| `<CognitiveStateBadges ccb />` | Inline mini-badges showing BREATH/SOUL/FOT at glance | Agent card, run detail |
| `<AutonomyLadderIndicator level />` | L1–L5 visual indicator | Agent card |
| `<TierPill tier />` | Foundational / Intermediate / Advanced-Crisis pill | Ubiquitous |
| `<StatusDot status />` | active / expired / revoked / suspended colored dot | Ubiquitous |
| `<GoldBadge />` | Golden Benchmark marker | Scenario |
| `<SimulationTag />` | Episode carries simulation flag (v1.1+) | Run detail, episode view |
| `<LineageGraph urn />` | Interactive lineage subgraph (v1.1) | Lineage explorer |
| `<CommandK />` | Cmd+K quick navigator | Global |

## D.4 Design System Tokens

```css
/* apps/web/src/app/globals.css */

:root {
  /* Gold scale */
  --gold-50:  #FDF8E8;
  --gold-100: #FBF0C4;
  --gold-200: #F6E190;
  --gold-300: #EFCD5B;
  --gold-400: #E5B93C;
  --gold-500: #D4AF37;  /* primary gold */
  --gold-600: #B38F1F;
  --gold-700: #8E6F17;
  --gold-800: #6A5310;
  --gold-900: #48370A;
  
  /* Ink scale (dark backgrounds) */
  --ink-50:   #E8E8EA;
  --ink-100:  #C4C4C8;
  --ink-200:  #97979E;
  --ink-300:  #6A6A74;
  --ink-400:  #4A4A54;
  --ink-500:  #2D2D36;
  --ink-600:  #1E1E26;
  --ink-700:  #161620;  /* app background */
  --ink-800:  #10101A;
  --ink-900:  #08080F;
  
  /* Semantic */
  --success:  #3FB950;
  --warning:  #D29922;
  --danger:   #F85149;
  --info:     #58A6FF;
  
  /* Typography */
  --font-sans:    'Inter', ui-sans-serif, system-ui, sans-serif;
  --font-display: 'Playfair Display', serif;
  --font-mono:    'JetBrains Mono', ui-monospace, monospace;
}

body {
  background: var(--ink-700);
  color: var(--ink-50);
  font-family: var(--font-sans);
}

h1, h2, h3 {
  font-family: var(--font-display);
  color: var(--gold-500);
}
```

## D.5 API Client (Typed)

```typescript
// apps/web/src/lib/api/client.ts

import { createTRPCClient, httpBatchLink } from '@trpc/client'
// Note: we expose FastAPI endpoints via OpenAPI-generated typed client
// instead of tRPC, because backend is Python. Using `openapi-typescript-codegen`.

import { OpenAPI, RunsService, CertsService, PacksService, GapsService } from './generated'

OpenAPI.BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
OpenAPI.TOKEN = async () => {
  const clerkToken = await getClerkToken()
  return clerkToken
}

export { RunsService, CertsService, PacksService, GapsService }
```

## D.6 State Management

- **Zustand** for cross-page UI state (sidebar collapse, command-K open, filter presets).
- **TanStack Query** for all server state with optimistic updates.
- **URL state** for filters via `nuqs` library (bookmarkable dashboards).

---

# PART E — FORGE INTEGRATIONS

## E.1 Integration Contract (Common)

Every Forge adapter implements:

```python
# apps/api/src/services/forges/base.py

from abc import ABC, abstractmethod


class ForgeAdapter(ABC):
    forge_name: str
    
    @abstractmethod
    async def health_check(self) -> dict: ...
    
    @abstractmethod
    async def provision_sandbox_tenant(self, run_id: str) -> str: ...
    
    @abstractmethod
    async def teardown_sandbox_tenant(self, tenant_id: str) -> None: ...
    
    @abstractmethod
    async def seed_state(self, tenant_id: str, fixtures: dict) -> None: ...
    
    @abstractmethod
    async def get_audit_log(self, tenant_id: str, since: datetime) -> list[dict]: ...
    
    @abstractmethod
    async def get_current_version(self) -> str: ...
    
    @abstractmethod
    async def inject_fault(self, tenant_id: str, fault: dict) -> None: ...
```

## E.2 VoiceForge Adapter

**Endpoints used:**
- `POST /voiceforge/api/v1/sandbox/tenants` — provision
- `DELETE /voiceforge/api/v1/sandbox/tenants/{id}` — teardown
- `POST /voiceforge/api/v1/sandbox/tenants/{id}/personas/inject` — persona injection
- `POST /voiceforge/api/v1/sandbox/tenants/{id}/line-quality` — line quality control
- WebSocket `/voiceforge/api/v1/sandbox/tenants/{id}/events` — call events
- `GET /voiceforge/api/v1/sandbox/tenants/{id}/audit-log?since=<ts>` — audit log

**Persona catalog preload:** angry DON, confused clinician, hostile seller, eager buyer, skeptical broker, wholesaler competitor, lender underwriter, facility admin, DOL auditor, HCQC inspector, patient family, fraud-attempting applicant.

## E.3 VisionAudioForge Adapter

**Endpoints used:**
- `POST /vaf/api/v1/sandbox/tenants` — provision
- `POST /vaf/api/v1/sandbox/docs/generate` — synthetic doc generation (30+ types)
- `POST /vaf/api/v1/sandbox/docs/{id}/inject-fault` — fault injection
- `POST /vaf/api/v1/ocr/extract` — OCR (same as prod)
- `POST /vaf/api/v1/prosody/score` — call-quality scoring

**Doc types (v1):** nursing license (RN/LPN/CNA), CNA cert, I-9, W4, direct deposit, drug screen, background check, HIPAA attestation, offer letter, per-diem agreement, MSA, rate sheet, COI, BAA, facility order, timecard, incident report, invoice, payroll register, 1099, W9, bank statement, LOI, PSA, assignment agreement, EMD receipt, title report, rent roll, comps report, proof of funds, buyer info statement.

**Fault menu:** forged_signature, expired_date, name_dob_mismatch, redacted_over_critical, scanned_at_angle, low_resolution, wrong_state, revoked_license, oig_match, mismatched_npi_tin, altered_amount, missing_pages, duplicate_submission, watermark_removed.

## E.4 medlink-pro Adapter

**Endpoints used:**
- `POST /medlink-pro/api/v1/sandbox/tenants` — provision with PHI-synthetic seed
- `POST /medlink-pro/api/v1/sandbox/tenants/{id}/seed-state` — scheduler / compliance / clinician state
- `POST /medlink-pro/api/v1/sandbox/tenants/{id}/ui-fault` — UI fault injection
- `GET /medlink-pro/api/v1/sandbox/tenants/{id}/audit-log` — audit log

**Seed parameters:**
- Credentials expiring in N days
- Outstanding timecards count
- Active shifts with unfilled roles
- Facility MSA status mix
- Recent incident reports

## E.5 CRE Forge Adapter

**Endpoints used:**
- Sandbox tenant API
- Lead / deal / buyer state seeding
- Sequence trigger subscription
- Audit log export

## E.6 FunnelForge Adapter

**Endpoints used:**
- Sandbox tenant API
- Lead/segment/campaign/sequence seeding
- Webhook subscription for `lead.created`, `sequence.step_executed`, `campaign.replied`
- Audit log export

## E.7 CapitalForge (Mock Bank) Adapter

Implements Mock Bank API over CapitalForge's Issuer Rules Engine.

**Endpoints used:**
- `POST /capitalforge/api/v1/sandbox/bank/apply` — credit application
- `POST /capitalforge/api/v1/sandbox/bank/wire` — wire transfer
- `POST /capitalforge/api/v1/sandbox/bank/emd/release` — EMD release
- `POST /capitalforge/api/v1/sandbox/bank/payroll/draw` — payroll float
- `POST /capitalforge/api/v1/sandbox/bank/ar/factor` — AR factoring
- `GET /capitalforge/api/v1/sandbox/bank/account/{id}` — account state
- `POST /capitalforge/api/v1/sandbox/bank/_sim/declination` — fault: declination
- `POST /capitalforge/api/v1/sandbox/bank/_sim/fraud-flag` — fault: fraud
- `POST /capitalforge/api/v1/sandbox/bank/_sim/nsf` — fault: NSF
- `POST /capitalforge/api/v1/sandbox/bank/_sim/ofac` — fault: OFAC hit
- `POST /capitalforge/api/v1/sandbox/bank/_sim/velocity` — fault: velocity trigger

**CU integrations exposed:** Navy Federal, Alliant, PenFed, BECU, First Tech FCU, Lake Michigan CU (DCU).

---

# PART F — GOVERNANCE IMPLEMENTATION

## F.1 Certification Registry

Append-only log. Every AgentCert and DeptCert has a full lifecycle event chain. Queries:
- Current active certs for agent / department.
- Cert history for a subject.
- Certs pinned to a specific Pack version / Constitution version.
- Certs expiring in next N days.
- Certs revoked in last N days with reason.

## F.2 CertSnapshot Signing Flow

```
┌──────────────────────────────────────────────────────────┐
│  1. Readiness Gate PASSED                                │
└──────────────────────┬───────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────┐
│  2. Assemble CertSnapshotPayload                         │
│     - cert metadata                                      │
│     - pinned versions (pack/scenarios/policy/rubric/     │
│       constitution/prompt/model/forges/village)          │
│     - evidence bundle ref (S3 URI)                       │
└──────────────────────┬───────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────┐
│  3. Canonical JSON (sorted keys, stable encoding)        │
└──────────────────────┬───────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────┐
│  4. Content hash = sha256(canonical)                     │
└──────────────────────┬───────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────┐
│  5. signer.sign(canonical) → signature bytes             │
│     (HSM operation — prod = CloudHSM, staging = YubiHSM) │
└──────────────────────┬───────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────┐
│  6. Persist CertSnapshot row                             │
│     (snapshot_id = "certsnap:{content_hash[:16]}")       │
└──────────────────────┬───────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────┐
│  7. Persist AgentCert / DeptCert row linking snapshot    │
└──────────────────────┬───────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────┐
│  8. Emit lineage edges                                   │
│     cert.urn --derived_from--> pack.urn                  │
│     cert.urn --pinned_to-->    constitution.urn          │
│     cert.urn --evidenced_by--> evidence_bundle.urn       │
└──────────────────────┬───────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────┐
│  9. Write CertLifecycleEvent{event: "issued"}           │
└──────────────────────────────────────────────────────────┘
```

## F.3 Autonomy Ladder State Machine

```
           manual promotion
     ┌────────────────────────────┐
     │                            │
     ▼                            │
  ┌─────┐      ┌─────┐      ┌─────┴──┐    ┌─────┐    ┌─────┐
  │ L1  │─────▶│ L2  │─────▶│   L3   │───▶│ L4  │───▶│ L5  │
  │Obs  │      │Draft│      │Exec+App│    │Spot │    │Full │
  │Only │      │Only │      │        │    │Check│    │     │
  └─────┘      └─────┘      └────────┘    └─────┘    └─────┘
     ▲           ▲              ▲             ▲          │
     │           │              │             │          │
     │           │              │             │          │
     └───────────┴──────────────┴─────────────┴──────────┘
          auto-downgrade triggers:
          - compliance violation       → L2
          - regression detected        → −1 level
          - cognitive alert (FOT crit, │
            ARC fragmentation, runaway │
            regret)                    → L3
          - upstream version change    │
            (model/Forge/prompt) no    │
            re-cert                    → L3
```

**Promotion criteria:**
- L1 → L2: First AgentCert issued.
- L2 → L3: 7 days of clean operation + 1st regression battery passed.
- L3 → L4: 30 days + 5 regression batteries passed + Advanced-Crisis tier certification for at least one Forge-cap.
- L4 → L5: 90 days + consecutive passes + Ivan approval + dept cert coverage.

## F.4 Revocation Engine

Triggers:
1. **Compliance violation in production** (monitored by Village runtime, reported to SimForge via webhook).
2. **Regression on previously-passing scenario** (detected by nightly regression worker).
3. **Prerequisite dependency fails** (DeptCert's AgentCerts drop below minimum).
4. **Expiration without renewal** (cert_lifecycle_worker).
5. **Constitutional amendment** invalidates rubric → affected certs auto-suspend (governance event).
6. **Village OS framework change** invalidates prior CCB (fingerprint drift) → affected certs auto-suspend.

**Propagation:**
- v1: nightly PDP cache invalidation via database read + Redis publish.
- v1.1: real-time PDP push via Redis pub/sub channel `simforge:revocations`.

## F.5 Constitution & Amendment Workflow

```
┌──────────────────────────────────────────────────────────┐
│  1. Amendment proposed                                   │
│     POST /api/constitution/amendments                    │
│     {base_version, diff_yaml, proposer_id}               │
└──────────────────────┬───────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────┐
│  2. Cooling period begins (default 7 days)               │
│     Status: "in_cooling"                                 │
│     Impact analysis auto-computed:                       │
│       - affected certs if amendment ratified             │
│       - blast radius                                     │
└──────────────────────┬───────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────┐
│  3. During cooling:                                      │
│     - public comment from designated amenders            │
│     - proposer can withdraw                              │
│     - Ivan can veto                                      │
└──────────────────────┬───────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────┐
│  4. After cooling period:                                │
│     - Ratification requires:                             │
│       · Ivan explicit approval                           │
│       · Quorum of named approvers per article           │
│       · All in-flight certs re-evaluated                 │
└──────────────────────┬───────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────┐
│  5. On ratification:                                     │
│     - New Constitution row created                       │
│     - Previous version marked supersededBy               │
│     - Affected certs auto-suspend pending re-cert        │
│     - Lineage edges: new_constitution --amends-->        │
│       previous_constitution                              │
└──────────────────────────────────────────────────────────┘
```

## F.6 PDP / PEP (v1.1)

**PDP service** (`services/governance/pdp.py`): centralized decision engine. Query protocol:

```python
@dataclass
class AuthRequest:
    subject_agent_id: str
    action: str              # "cre-forge.call_center.outbound"
    resource: Optional[str]
    context: dict            # jurisdiction, time_of_day, caseload, etc.


@dataclass
class AuthDecision:
    decision: Literal["allow", "deny", "step_up_approval_required", "downgrade_and_retry"]
    reason_code: str
    reason_detail: str
    ttl_seconds: int         # cache lifetime on PEP
    required_approver: Optional[str] = None


class PDP:
    async def decide(self, req: AuthRequest) -> AuthDecision: ...
```

**PEP SDKs:**
- Python PEP for Village runtime (v1.1 concurrent with village_bridge).
- Python PEP for each Forge's internal service layer (inserted as middleware).

**Caching:** Each PEP caches decisions in-process with bounded TTL (default 60s). Revocation events published to Redis invalidate caches fleet-wide.

**Fail-open/closed:** Configured per action class in Constitution. Default fail-closed for all compliance-adjacent actions.

---

# PART G — SECURITY

## G.1 Authentication & Authorization

- **User auth:** Clerk. JWT bearer tokens on API calls.
- **Service-to-service:** Mutual TLS + short-lived service-account tokens.
- **Roles:** `admin` (Ivan, full access), `founder` (Ivan-level), `pack_owner` (ratify Pack), `compliance_analyst` (review gaps, appeals), `prompt_engineer` (read agent scorecards), `forge_owner` (receive Software Gap tickets), `viewer` (read-only dashboards), `external_auditor` (redacted evidence export only).
- **Permission checks:** FastAPI dependencies (`Depends(require_role("admin"))`) on every endpoint.

## G.2 Key Management

- **Root signing key (prod):** AWS CloudHSM, FIPS 140-2 Level 3, Ivan-held HSM credential.
- **Intermediate signing keys:** derived from root quarterly; used for day-to-day CertSnapshot signing; stored in HSM.
- **Rotation:**
  - Quarterly automated for intermediates.
  - Emergency rotation on compromise (triggered by incident runbook R-005).
- **CRL:** Published at `/api/attest/public-keys` and mirrored to external verifier endpoint. Updated on every rotation.
- **Key ceremony:** Two-person integrity (Ivan + witness) for all root operations. Documented in `docs/RUNBOOKS/KEY_CEREMONY.md`.

## G.3 PHI / PII Handling

- **PHI-synthetic only** in all SimForge fixtures for MedLink Pack — no real patient data ever.
- **PHI regex guard** in Pack validator rejects any scenario containing real SSN / DOB patterns.
- **Evidence redaction classes:** PHI-synthetic / financial / PII / standard — external-auditor exports apply appropriate redaction before signing.
- **Data residency:** US-only for v1 (all S3 + RDS in US regions).
- **PHI access audit:** Every access to MedLink evidence bundles logged with accessor identity + reason + timestamp.

## G.4 Audit Logging

Every governance-relevant action logged to `AuditLog` table (not shown in schema above but added for v1):
- Cert issue / revoke / suspend / renew
- Autonomy level change
- Constitutional amendment proposal / ratification / veto
- Pack ratification
- Emergency safe-mode activation
- Evidence access
- Signing ceremony events

Logs are append-only and anchored to Lineage Graph for cross-reference.

## G.5 Secret Management

- **Dev:** `.env` files, git-ignored.
- **Staging / Prod:** AWS Secrets Manager. Secrets rotated per AWS policy. Application reads via IAM role.
- **Never committed:** API keys, signing private keys, database passwords, HSM credentials, OAuth client secrets.

---

# PART H — OBSERVABILITY

## H.1 Structured Logging

- `structlog` with JSON output.
- Every log line carries: `run_id`, `agent_village_id`, `scenario_id`, `phase`, `component`.
- Shipped via OpenTelemetry → Grafana Loki.
- Log levels: INFO (default), WARN, ERROR, CRITICAL.

## H.2 Metrics

**Prometheus metrics exposed at `/metrics`:**

| Metric | Type | Labels |
|---|---|---|
| `simforge_runs_total` | counter | status, execution_mode, narrative_mode |
| `simforge_run_duration_seconds` | histogram | tier, pack_id |
| `simforge_tokens_used_total` | counter | budget_bucket, provider |
| `simforge_rubric_dim_score` | histogram | dim, tier |
| `simforge_readiness_gate_passed_total` | counter | pack_id, tier |
| `simforge_certs_active` | gauge | type, tier |
| `simforge_gaps_open` | gauge | forge, severity |
| `simforge_eval_latency_ms` | histogram | dim |
| `simforge_forge_adapter_errors_total` | counter | forge, operation |
| `simforge_hsm_sign_duration_ms` | histogram | key_id |
| `simforge_pdp_decision_latency_ms` | histogram | decision |
| `simforge_pdp_cache_hit_ratio` | gauge | — |
| `simforge_village_fingerprint_mismatch_total` | counter | — |

## H.3 Distributed Tracing

- OpenTelemetry auto-instrumentation on FastAPI + SQLAlchemy + httpx.
- Custom spans for: scenario run, CCB capture, each rubric dim, signing ceremony, PDP decision.
- Shipped to Grafana Tempo.

## H.4 Dashboards

| Dashboard | Audience | Panels |
|---|---|---|
| **SRE Overview** | SRE | P50/P95/P99 latencies, error rates, queue depths, Redis health, DB health |
| **Eval Engine** | Prompt engineers | Rubric dim distributions, readiness gate pass rate, auto-fail reasons |
| **Budget & Cost** | Finance | Token burn by bucket, cost per run, budget remaining, Pareto frontier |
| **Cert Registry** | Ivan + compliance | Certs issued/revoked/expiring, cohort readiness |
| **Gap Triage** | Forge owners | Top-10 gaps per forge, age-of-gap distribution, status flow |
| **Village Integration** | Village OS maintainers | Fingerprint drift alerts, read-error rates, framework-specific anomalies |
| **Incident Command** (v1.2) | Ivan + on-call | Active incidents, safe mode status, blast radius |

## H.5 Alerting

**PagerDuty integration. Alert levels:**

| Severity | Examples | Response time |
|---|---|---|
| **P0** | DB down, HSM unavailable, Village fingerprint drift, mass-regression event (>10 scenarios flipped in 1h), compliance violation in prod | 15 min |
| **P1** | Eval engine error rate > 5%, Forge sandbox down, PDP latency > 500ms p95, cert expiration wave imminent | 1 hour |
| **P2** | Elevated gap ticket volume, scorecard LLM-judge anomalies, scenario drift | Next business day |

---

# PART I — TESTING

## I.1 Unit Testing

- pytest (backend) + vitest (frontend).
- Target coverage: 80% on core services (evaluation, scenario_engine, cert, village), 60% elsewhere.
- Fixtures: mock VillageData filesystem, mock Forge adapters, in-memory test DB.

## I.2 Integration Testing

- End-to-end scenario runs against mock Forge adapters + stub Village filesystem.
- Full rubric scoring against seeded CCBs.
- CertSnapshot signing with StubSigner verifying signature.

## I.3 Contract Testing

**village_bridge contracts (v1.1+):** Pact-style consumer-driven tests proving:
- Sandbox isolation (no disk writes, no DB writes, no episode, no FOT tick).
- Integrated + Protected writes are tagged.
- Integrated + Integrated requires pre-commit Archive entry.

**Forge adapter contracts:** Each Forge adapter has a contract test verifying the sandbox tenant API conforms to the agreed schema. Forge side runs a parallel verify test. Breaking change in any Forge → contract test fails in SimForge CI → Forge release blocked.

## I.4 E2E Testing

- Playwright tests for frontend (login, dashboard load, cert detail, run replay).
- Full scenario execution E2E: docker-compose brings up Postgres + mock Forges + stub Village fs + run a scenario to completion.
- Dress Rehearsal replay: takes a known-good run, replays, verifies identical scorecard.

## I.5 Chaos & Load Testing

- **Load:** k6 scripts simulating 100 concurrent scenario runs, target SLO ≤ 95th percentile.
- **Chaos:** ChaosMesh-style injection — kill workers mid-run, drop Forge sandbox, HSM latency spike — verify graceful handling.
- **Soak:** 24-hour continuous-run test in staging weekly.

---

# PART J — DEPLOYMENT & OPERATIONS

## J.1 Local Dev Environment

```bash
./scripts/bootstrap.sh
# → docker compose up -d postgres redis ollama
# → pnpm install
# → cd packages/db && npx prisma migrate deploy
# → cd apps/api && pip install -e . && alembic upgrade head
# → cd apps/web && pnpm dev & pnpm --filter api dev
```

## J.2 Staging Environment

- Fly.io apps: `simforge-web-staging`, `simforge-api-staging`, `simforge-workers-staging`.
- Shared Postgres via Supabase or Fly Postgres.
- Redis via Upstash.
- Deploys on every merge to `main` via GitHub Actions.

## J.3 Production Topology

- AWS ECS Fargate (multi-AZ).
- RDS Postgres with Multi-AZ + read replica.
- ElastiCache Redis cluster.
- S3 with cross-region replication.
- CloudHSM cluster.
- CloudFront CDN in front of frontend.

## J.4 CI/CD Pipeline

```
git push
  │
  ├─ GitHub Actions: CI
  │   ├─ Pack validator on any changed Pack
  │   ├─ Unit tests (backend + frontend)
  │   ├─ Integration tests
  │   ├─ Contract tests (village_bridge + Forge adapters)
  │   ├─ Lint + type check + Prisma validate
  │   └─ Build Docker images → push to ECR
  │
  ├─ On merge to main:
  │   ├─ Deploy to staging (auto)
  │   ├─ Run smoke tests against staging
  │   ├─ Post-deploy contract verification
  │   └─ Request prod deploy approval (Slack + GitHub)
  │
  └─ On manual prod approval:
      ├─ Alembic migration (zero-downtime patterns)
      ├─ Deploy backend (blue/green)
      ├─ Deploy frontend
      ├─ Post-deploy verification
      └─ Gradual traffic shift (0% → 10% → 100%)
```

## J.5 Database Backups & PITR

- Daily automated snapshots (retained 30 days).
- Continuous WAL archiving (7-day PITR window).
- Weekly snapshot cross-region copy (us-east-1 backup of us-west-2 primary).
- Quarterly recovery drill: restore a prod snapshot to isolated env + run smoke tests.

## J.6 Disaster Recovery

- **RPO:** 1 hour (maximum acceptable data loss).
- **RTO:** 4 hours (time to restore service).
- **Tier-1 SimForge infrastructure** means the governance layer has its own SLA — outage blocks certifications, which blocks Village autonomy expansion.
- **Graceful degradation policy:** During SimForge outage, Village agents operate at their last-known-certified autonomy level (cached in PEPs). After 24h outage → auto-downgrade all L5 to L4, etc.
- **DR runbook:** `docs/RUNBOOKS/DR.md`.

## J.7 Incident Runbooks

| Runbook | Trigger | Summary |
|---|---|---|
| R-001 | Eval engine error rate > 5% | Check rubric dim failures; roll back recent rubric change if suspect |
| R-002 | Sandbox tenant down | Failover to next-available Forge staging tenant; throttle affected Packs |
| R-003 | PDP latency spike > 500ms p95 | Check Redis health; enable PEP fail-open for non-compliance actions temporarily |
| R-004 | Mass regression (>10 scenarios flipped in 1h) | Auto-safe-mode affected domain; investigate shared cause (Forge release? model change?) |
| R-005 | HSM unavailable | Pause all new CertSnapshot issuance; existing certs continue functioning; emergency signing via YubiHSM backup |
| R-006 | Village fingerprint drift | Block all new cert issuance; alert Ivan + Village OS maintainer; require manual review before resume |
| R-007 | Linear webhook failure | Gaps queued locally; retry with exponential backoff; page after 15min continued failure |

---

# PART K — COST MODEL

## K.1 Per-Run Cost Breakdown

Assuming Foundational tier scenario, typical 15-turn run:

| Line item | Typical | High |
|---|---|---|
| LLM tokens (agent runtime, Ollama local): ~5k input / 2k output × 15 turns | $0.00 | $0.00 |
| LLM tokens (evaluator LLM-judge dims P7, C1, C2): ~10k input / 2k output | $0.08 | $0.15 |
| Forge sandbox API calls (~50 calls): | $0.02 | $0.05 |
| Postgres I/O: | $0.01 | $0.02 |
| S3 evidence storage (~5MB): | $0.00 | $0.00 |
| HSM sign operation: | $0.001 | $0.002 |
| Compute (worker CPU, 10–30s): | $0.01 | $0.03 |
| **Per run total** | **~$0.12** | **~$0.25** |

At ~500 runs/day for active certification batteries: **$60–$125/day = $1,800–$3,750/month**.

## K.2 Budget Controls

Per §11.4 MATE budget segregation:
- `simforge_sandbox` monthly cap (default $5,000 prod).
- `simforge_integrated_protected` monthly cap (default $2,000, enabled v1.1).
- `simforge_integrated_integrated` monthly cap (default $500, enabled v1.2).
- Per-Pack sub-caps.
- Automatic throttling at 80% cap; halt at 100% + Ivan alert.

## K.3 Scaling Projections

| Scenario | Runs/day | Monthly cost |
|---|---|---|
| v1.0 launch (2 Packs, 1 agent per Pack in active battery) | 50 | $180 |
| v1.0 full (all agents in continuous regression) | 300 | $1,100 |
| v1.1 full + integrated-protected training | 800 | $3,000 |
| v1.2 full + adversarial + multi-agent | 2,000 | $7,500 |
| Per new venture add | +400 runs/day | +$1,500/mo |

---

# PART L — APPENDICES

## L.1 Extended Glossary

See spec §Appendix A. Additions:

- **Alembic** — Python SQL migration tool, used for incremental schema changes alongside Prisma.
- **Blue/Green Deployment** — deployment pattern with two identical environments; traffic switches between them for zero downtime.
- **CRL** — Certificate Revocation List; published list of revoked signing keys.
- **HSM** — Hardware Security Module; FIPS-validated device for cryptographic key storage.
- **PITR** — Point-in-Time Recovery for databases.
- **RTO / RPO** — Recovery Time Objective / Recovery Point Objective (DR parameters).
- **URN** — Uniform Resource Name (canonical identity scheme).

## L.2 API Reference Index

Full OpenAPI spec auto-generated at `/docs` (FastAPI interactive) and `/openapi.json`. Routes summarized in §C.3.

## L.3 File-by-File Index

See §A.5 (repository structure). Every file has:
- Purpose comment at top.
- Type hints on all functions.
- Docstrings on public API.
- `# WEEK N:` markers on Week-deferred stubs.

## L.4 Known Limitations

| Limitation | Status | Plan |
|---|---|---|
| v1 cannot train agents (sandbox only) | By design | v1.1 integrated execution |
| No Village narrative effects in v1 | By design | v1.2 integrated narrative |
| Only Gardner has phone capability in Village | Village constraint | v1.1 may expand via VoiceForge abstraction |
| v1 Object Registry is stub | By design | v1.1 full |
| Lineage Graph has skeleton only in v1 | By design | v1.1 full edges |
| Drift Canary not in v1 | By design | v1.2 |
| Jurisdiction Engine limited to NV at v1 | Scope decision | v1.2 full Rule Packs |
| Locale layer English-only at v1 | Scope decision | v1.2 locale Packs |
| Meta-Eval not in v1 | Scope decision | v1.2 |
| Adversarial layer human-only at v1 | Scope decision | v1.1 automated |

## L.5 Blueprint Changelog

| Version | Date | Changes |
|---|---|---|
| 1.0.0 | 2026-04-21 | Initial blueprint corresponding to spec v1.0.0 |

---

**END OF BLUEPRINT — SimForge v1.0.0 Engineering Implementation Guide**
