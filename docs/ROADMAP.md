# SimForge Build Roadmap

Phased plan to take SimForge from foundation to a runnable v1.0.0. Each phase ends in a **testable, committable, demoable** state (per `CLAUDE.md` §3). Phases are built as `ai-feature/<slug>` branches, largest-risk-reduction first, following a **vertical-slice** strategy so there is always a working end-to-end path.

Guiding principle: **prove the spine end-to-end early** (one scenario → run → score → gate → cert), then widen. Avoid building all 15 rubric dimensions or all 6 Forge adapters before a single run completes.

---

## Phase 0 — Foundation ✅ (this branch: `ai-feature/repo-foundation`)

- Monorepo skeleton, git repo + remote, `CLAUDE.md`, 5 Claude commands.
- Complete Prisma schema (17 entities), dev seed skeleton.
- `docker-compose` (Postgres + Redis + optional Ollama), `.env.example`.
- Docs: architecture, decisions, roadmap, contributing, constitution, blueprint copy.
- `scripts/bootstrap.sh`, `scripts/smoke-test.sh`.
- **Done when:** `docker compose up` + `prisma migrate` + `seed` succeeds and the tree is committed. (App tiers scaffolded in Phase 1.)

## Phase 1 — Runnable skeleton (fullstack hello-spine)

- `apps/api`: FastAPI app factory, `config.py` (Pydantic settings), async DB, `/api/health` (`/`, `/ready`, `/village-fingerprint`), telemetry stubs, dev-auth bypass.
- `apps/web`: Next.js App Router shell (sidebar + header), design tokens, typed API client (OpenAPI-generated), overview dashboard reading `/api/health` + agent list.
- `packages/db`: migrations generated; seed runs.
- **Demo:** `pnpm dev` → `:3000` dashboard shows seeded agents/departments from `:8000`.
- **Tests:** health + agents router (pytest); web smoke (vitest/Playwright login+dashboard).

## Phase 2 — Village reader + CCB (read-only coupling)

- `services/village/reader.py` (full BREATH/FOT/SOUL/ARC/echo/hfm/drift/ame/game/mate + fingerprint), `ccb_composer.py`, `fingerprint.py`.
- A small **synthetic VillageData fixture tree** under `village-data-local/` for dev + tests.
- `fingerprint_worker`; `/api/agents/{id}/ccb/latest`.
- **Demo:** compose a CCB for a seeded agent; fingerprint drift detection test.

## Phase 3 — Pack + Scenario ingestion & validation

- `packages/validator` (pack + scenario YAML schema + rules, PHI regex guard).
- 1 Greenstone + 1 MedLink Pack, 3 scenarios each (synthetic).
- `POST /api/packs` (ingest+validate), `/api/packs/*`, `/api/scenarios/*`; Pack pages in web.
- CI: `pack-validator.yml`.
- **Demo:** register a Pack from YAML; see it + scenarios in the UI.

## Phase 4 — Scenario runner spine (the core loop)

- `services/agent_runtime` (9-layer prompt assembly, Ollama/OpenAI client, tool executor).
- `services/scenario_engine` (state machine: pending→setup→cold_open→turn→complication→resolution→wrap).
- `services/mock_world` minimal (one persona + one Forge **stub**).
- `runner_worker` (RQ); `POST /api/scenarios/{id}/run`; run detail + transcript in web.
- **Demo:** run a Foundational scenario end-to-end against stubs; transcript + trace persisted.

## Phase 5 — Evaluation engine + Readiness Gate

- `services/evaluation` — start with a **representative subset** (P1, P2, P3, P7 + C2, C4), then fill remaining dims; `rubric.py` orchestrator (parallel), `readiness_gate.py`, `regression.py`.
- `eval_worker`; Scorecard + `<FifteenDimChart/>` + gate status in web.
- **Demo:** completed run yields a scorecard; gate auto-fails on compliance/ARC-fragmentation.

## Phase 6 — Triple reporter + Gaps

- `services/reporter` (scorecard, software_gap, village_os_gap, linear_client [dev = no-op], remediation).
- `reporter_worker`; `/api/gaps/*`; gap tables + Top-10 widget in web.
- **Demo:** a run emits scorecard + software/village-OS gaps; gaps visible in UI.

## Phase 7 — Certification + signing + autonomy ladder

- `services/cert` (registry, snapshot, `StubSigner`/`YubiHsm`/`CloudHsm`, verifier, revocation, autonomy_ladder).
- `services/evidence` (bundle + local/S3 storage + lifecycle).
- Cert issue flow (Ivan-gated), `/api/certs/*`, `/api/snapshots/*`, `/api/attest/*`; Readiness Matrix + Cert Registry in web.
- `cert_lifecycle_worker`, `regression_worker`.
- **Demo:** gate pass → signed CertSnapshot → verify signature → agent autonomy L1→L2.

## Phase 8 — Governance (constitution) + registry/lineage

- `services/governance` (constitution, amendment, approval_workflow, safe_mode).
- `services/registry` (object_registry, lineage, urn) — v1 skeleton edges.
- Constitution + amendment pages; lineage explorer (v1.1 full).

## Phase 9 — Observability, security hardening, CI/CD, deploy assets

- Structured logging, Prometheus `/metrics`, OTEL tracing; role-based authz on every endpoint (Clerk in staging).
- Full CI (`ci.yml`, `contract-tests.yml`), staging deploy (`deploy-staging.yml`), `/deploy-prod` assets (Terraform).
- Runbooks R-001…R-007, DR doc.

---

## Cross-cutting conventions

- **Stub-first for externals** (Village fixture tree, Forge stub servers, StubSigner, dev-auth, Linear no-op). Real integrations swap in behind the same ports (`docs/DECISIONS.md`).
- **Test as you go** — no phase is "done" without passing unit + integration tests and updated docs.
- **Best-of-N** where design is open (e.g. scenario-engine branching, rubric aggregation): implement 2–3 approaches on parallel branches/worktrees and compare before committing.

## Deferred to v1.1 / v1.2 (per blueprint §L.4)

Integrated execution & training, Village narrative effects, full Object Registry & Lineage, Drift Canary, full Jurisdiction Engine (v1 = NV only), locale packs, Meta-Eval, automated adversarial layer, PDP/PEP real-time push.
