# Changelog

All notable changes to SimForge. Format: [Keep a Changelog](https://keepachangelog.com/); this project uses SemVer.

## [Unreleased]

### Added — First real Forge: CapitalForge (Mock Bank) (post-v1)
- **`ForgeAdapter` contract** (`services/forges/base.py`) — provision/teardown sandbox tenant, seed state, inject fault, audit log, version; `SandboxTenant`/`Fault`/`FaultType`; `NullForgeAdapter` for unwired Forges.
- **CapitalForge = Mock Bank** — deterministic in-process engine (`mock_bank.py`) + `LocalCapitalForgeAdapter`: tenants, accounts, apply/wire/emd_release, fault injection (declination/fraud/nsf/ofac/velocity), audit log. Registry/factory `get_forge_adapter`.
- **Runner wiring** — capitalforge scenarios provision a sandbox tenant, run the tested op, and record `forge_action`/`forge_fault` trace events (sandbox-isolated; deterministic fault on even seed). **Real Software Gaps** now derive from `forge_fault` events (`detect_forge_fault_gaps`), merged with heuristics.
- **Router** `/api/forges` — list/health + CapitalForge demo flow.
- **Tests:** 15 new (100 api + 5 validator) — Mock Bank engine, adapter **contract test** (§I.3), Null adapter, Forge router, and the fault→gap integration. ruff clean.
- **Verified live:** `scn.gs.buy.002` → `emd/fraud_flag` fault → Software Gap `capitalforge/emd`. ADR-0010.

### Added — Real Ollama LLM provider (post-v1)
- **`OllamaProvider`** — real `POST /api/chat` (non-streaming, seeded) against a local Ollama; transcript roles mapped (agent→assistant, scenario/world→user); token accounting from `prompt_eval_count`+`eval_count`.
- **Provider selection** via `LLM_PROVIDER` (`stub` default · `ollama` · `auto` = Ollama-if-reachable-else-stub · `openai`); `OLLAMA_MODEL` (default `llama3.1:8b`). StubProvider stays default so tests/CI remain deterministic (ADR-0008).
- **Script:** `scripts/run-scenario-ollama.py` — drive a scenario with a real model and print the transcript.
- **Tests:** 4 new (74 api total) — role mapping, provider selection, and mocked-HTTP `complete()` request/response parsing. ruff clean.

### Added — Phase 9 (Observability, security & deploy) — **v1 feature-complete**
- **Metrics** (`telemetry/metrics.py`) — real Prometheus collectors (`simforge_runs_total`, `_readiness_gate_total`, `_certs_issued_total`, `_tokens_used_total`, `_run_duration_seconds`, …) exposed at **`/metrics`**; wired into the run + cert flows.
- **Dashboard aggregates** (`/api/dashboard/*`) — `summary`, `throughput` (runs by status + tokens + cost), `readiness-matrix`.
- **Security** — role-based authz already enforced on every endpoint; Clerk JWT verification **seam** (`auth/clerk.py`, gated by `AUTH_MODE`); `docs/security.md` (keys, PHI, secrets, audit).
- **Deploy scaffolding** — Terraform (`infra/terraform/`: rds/redis/s3/ecs/iam), CI (`contract-tests.yml`, `deploy-staging.yml`, `deploy-prod.yml`), `docs/deploy.md`, **7 incident runbooks** (R-001…R-007) + `DR.md` + `KEY_CEREMONY.md`.
- **Tests:** 4 new (70 api + 5 validator) — `/metrics` exposition + dashboard summary/throughput/readiness. ruff clean.

### Added — Phase 8 (Governance & Object Registry / Lineage)
- **Governance** (`services/governance`) — constitution lifecycle + **amendment workflow** (propose → cooling period → ratify/withdraw/veto); ratification bumps the version, supersedes the prior, and **auto-suspends certs pinned to the old constitution**; impact analysis (affected-cert count); in-process **safe-mode** flag.
- **Object Registry + Lineage** (`services/registry`) — URN scheme (`urn:gc:village:<kind>:<id>`), register/resolve/tombstone, directed lineage edges + BFS path + neighborhood subgraph. Cert issuance now **emits lineage** (`produced_by`/`derived_from`/`pinned_to`/`evidenced_by`).
- **Models:** Constitution, ConstitutionalAmendment, ObjectRegistryEntry, LineageEdge.
- **Endpoints:** `/api/constitution/*` (current/version/history/amendments/safe-mode), `/api/registry/*` (urn/kind/register/tombstone), `/api/lineage/*` (from/to/path/subgraph).
- **Frontend:** Constitution + amendments page, Lineage explorer; sidebar enabled. **Script:** `scripts/seed-constitution.py`.
- **Tests:** 7 new (66 api + 5 validator) — URN/lineage path+subgraph, constitution ratify/current, amendment cooling→ratify→supersede, cert-issuance-emits-lineage. ruff clean.
- **Verified live:** amendment ratified → v1.0.0→v1.0.1, 2 dependent certs auto-suspended.

### Added — Phase 7 (Certification, signing & autonomy ladder)
- **Signing** (`services/cert/signer.py`) — `Signer` ABC + Ed25519 **StubSigner** (dev; generates/persists a keypair); HSM providers drop in behind the ABC.
- **CertSnapshot** (`snapshot.py`) — version-pinned payload with a stable canonical encoding; `content_hash` + signature.
- **Registry** (`registry.py`) — `issue_agent_cert` (validates a passing-gate battery, no active duplicate), signs a CertSnapshot, writes an evidence bundle, advances the **Autonomy Ladder** L1→L2; `revoke_agent_cert` (audited, demotes one level).
- **Verifier** (`verifier.py`) — recomputes canonical + checks hash & signature. **Autonomy ladder** state machine (`autonomy_ladder.py`). **Evidence** bundle storage (local FS in dev).
- **Models:** AgentCert, DeptCert, CertSnapshot, CertLifecycleEvent, AutonomyEvent. **Workers:** `cert_lifecycle_worker` (expiry sweep).
- **Endpoints:** `/api/certs/agent/*` (issue/list/detail/revoke), `/api/snapshots/{id}` + `/verify`, `/api/attest/cert/{id}` + `/public-keys`, agent autonomy promote/downgrade/history.
- **Frontend:** Cert Registry + **Readiness Gate Matrix** (agent × Forge-cap grid); sidebar enabled.
- **Tests:** 12 new (59 api + 5 validator) — signer roundtrip/tamper, full issue→verify→autonomy flow, duplicate/failing-battery rejection, revoke-demotes. ruff clean.
- **Verified live:** passing run → signed cert issued, autonomy L1→L2, **signature verifies True against Postgres**, external attestation valid, revoke demotes L2→L1.
- **ADR-0007:** persisted timestamps are **naive UTC truncated to ms** (Prisma `timestamp(3)`); fixed a signature-verification bug where microsecond/tz round-tripping broke the signed hash.

### Added — Phase 6 (Triple Reporter + Gaps)
- **Software Gap detector** (`services/reporter/software_gap.py`) — surfaces Forge defects from run outcome + tier against tested Forge caps (v1 heuristic; real detection reads Forge sandbox error traces).
- **Village-OS Gap detector** (`services/reporter/village_os_gap.py`) — principled CCB-threshold anomalies per framework (ARC fragmentation, high regret, drive imbalance, drift, low valence); healthy agents → no gaps.
- **Reporter service** — dedup-persists gaps (deterministic `SF-GAP-`/`SF-VG-` ticket ids, occurrence counting) + no-op **Linear client** (dev); `reporter_worker` RQ entrypoint; runs auto-emit reports on completion.
- **Models:** `SoftwareGap`, `VillageOSGap`. **Endpoints:** `/api/gaps/software`, `/api/gaps/village-os`, gap detail, status update, `top-10/forge/{forge}`, `top-10/village-os`.
- **Frontend:** Software + Village-OS gap tables (severity pills, occurrence counts) + Top-gaps widget on the overview; sidebar Gaps enabled.
- **Tests:** 12 new (51 api + 5 validator) — detectors (crisis→P1, slo→P0, anomalous CCB→framework gaps, healthy→none), dedup, endpoints. ruff clean.
- **Verified live:** crisis run surfaced 2 P1 software gaps (cre-forge, voiceforge); healthy run → 0 Village-OS gaps.

### Added — Phase 5 (Evaluation engine + Readiness Gate)
- **15-dimension rubric** (`services/evaluation`) — 8 performance (P1–P8) + 7 cognitive (C1–C7) deterministic heuristic scorers over the transcript + CCB pre/post diff + scenario metadata (`dimensions/performance.py`, `dimensions/cognitive.py`); LLM-judge dims (P7/C1/C2) swap in behind the same signatures later.
- **Readiness Gate** (`gate.py`) — hard auto-fails on P2 compliance violation and C4 ARC fragmentation (sudden_shift/regression/fragmentation); otherwise all perf dims must clear the per-tier threshold and the cognitive aggregate its minimum.
- **Regression detector** (`regression.py`) — flags an agent that previously passed a scenario now failing (for Phase 7 revocation + Phase 9 nightly worker).
- **Scorecard model** + `evaluate_run` orchestration (persists 15 dims + gate + turn annotations + remediation recs); runs auto-evaluate on completion; `eval_worker` RQ entrypoint.
- **Endpoint:** `GET /api/runs/{id}/scorecard`.
- **Frontend:** `FifteenDimChart` (perf + cognitive bars, gate badge, C4/compliance callouts, remediation list) on the run detail page.
- **Tests:** 8 new (37 api + 5 validator) — all 15 dims scored, clean run passes, compliance + ARC auto-fails, missing-CCB handling, scorecard endpoint. ruff clean.
- **Verified live:** David Kim's `scn.gs.src.001` run → scorecard persisted, **GATE PASSED** (cognitive aggregate 0.878); a compliance/ARC violation auto-fails (unit-tested).
- Calibrated P7 so a professional stub response clears the bar (coarse under the stub; discriminating with a real LLM-judge).

### Added — Phase 4 (Scenario runner spine)
- **Agent runtime** (`services/agent_runtime`) — 9-layer system-prompt assembly from Village state (resilient to agents missing from the dev tree) + a **deterministic offline `StubProvider`** LLM (ADR-0001 philosophy; Ollama/OpenAI drop in behind the same interface).
- **Scenario engine** (`services/scenario_engine`) — `RunState` + `Phase` state machine (setup→cold_open→turn↔complication→resolution→wrap), `ComplicationInjector`, deterministic via `seed`.
- **Mock world** (`services/mock_world`) — in-process deterministic counter-party persona + Forge action recorder.
- **Runner orchestration** (`services/runner`) — resolves scenario/pack/agent → creates Run → captures CCB pre → runs → persists transcript + TraceEvents + CCB post → sets status; `runner_worker` RQ entrypoint.
- **Models:** `Run`, `TraceEvent` (Prisma-mapped).
- **Endpoints:** `POST /api/scenarios/{id}/run` (inline exec, deterministic) + `/api/runs` (list/detail/transcript/trace).
- **Frontend:** Runs list + Run detail (transcript bubbles with complication highlight + trace timeline) + a client "Run" button on Pack scenarios; sidebar Runs enabled.
- **Fixtures:** Village generator extended to all 8 seeded agents.
- **Tests:** 7 new (30 api + 5 validator) — runner determinism/completion/complication; run endpoint end-to-end, unregistered-agent + missing-scenario 404s. ruff clean.
- **Verified live:** David Kim ran `scn.gs.src.001` → `passed`/`resolved`, complication injected, transcript + trace + CCB pre/post persisted to Postgres.

### Added — Phase 3 (Pack + Scenario ingestion & validation)
- **Validator package** (`packages/validator`) — typed Pack/Scenario YAML schemas, referential + readiness-gate rules, and a **PHI regex guard** (rejects SSN/DOB-shaped tokens). CLI `simforge-validate`. Single source of truth reused by the backend.
- **Sample Packs:** `packs/greenstone/v1` and `packs/medlink-pro/v1` (PHI-required), 3 scenarios each across foundational/intermediate/advanced-crisis tiers.
- **Backend:** Pack/Scenario/ReadinessGate models (`StrArray` = Postgres text[] with SQLite JSON fallback), ingestion service (load → validate → idempotent upsert), routers `/api/packs` (list/detail/ingest/validate/sign) and `/api/scenarios` (list/detail).
- **Frontend:** Packs list + Pack detail pages (scenarios table with tier pills + golden marker); sidebar Packs enabled.
- **CI:** `ci.yml` (validator + api + web jobs) and `pack-validator.yml` (validates `packs/` on PR).
- **Automation:** `scripts/ingest-scenario-library.py` (idempotent bulk ingest).
- **Tests:** 9 new (23 api + 5 validator) — validator happy-path + PHI guard + missing-threshold; ingestion idempotency; packs/scenarios endpoints. All green; ruff clean both packages.
- **Verified live:** both Packs ingested via API into Postgres (2 packs, 6 scenarios, 2 gates); tier filter + detail confirmed.

### Added — Phase 2 (Village reader + CCB)
- **Village reader** (`services/village/reader.py`) — read-only getters for all 10 frameworks (game, mate, soul, breath, fot, hfm, arc, echo, drift, ame) + episodes + identity, plus a structural **schema fingerprint** with drift detection (`verify_fingerprint`).
- **CCB composer** (`services/village/ccb_composer.py`) — assembles the 10 frameworks into a snapshot with a deterministic SHA-256 content hash; persistence via `ccb_store.py`.
- **Fingerprint capture** (`services/village/fingerprint.py`) + `fingerprint_worker` (RQ) + self-contained CLI `scripts/check-village-fingerprint.py`.
- **Models:** `CCB`, `VillageFingerprint` (mapped to Prisma tables; JSON framework columns).
- **Endpoints:** `POST /api/agents/{id}/ccb/capture`, `GET /api/agents/{id}/ccb/latest`; `GET /api/health/village-fingerprint` now uses the live reader.
- **Fixtures:** `scripts/make-village-fixture.py` generates a synthetic VillageData tree (2 agents); committed test fixture under `apps/api/tests/fixtures/village/`.
- **Tests:** 10 new (19 total) — reader completeness, fingerprint determinism/mismatch, CCB composer determinism, capture→latest endpoints, fingerprint capture. ruff clean.
- **Verified live:** CCB captured for `taylor_zhang` → persisted to Postgres; fingerprint `9fa4eecd…` served.
- **Decision:** ADR-0006 (Village path conventions are dev conventions pending reconciliation) + Windows dev-server kill-by-port gotcha.

### Added — Phase 1 (runnable skeleton)
- **Backend (`apps/api`):** FastAPI app factory + `config.py` (typed settings) + async SQLAlchemy engine (ADR-0003). Routers: `/api/health` (`/`, `/ready`, `/village-fingerprint`), `/api/agents` (list+filter+detail), `/api/departments`. Dev-bypass auth with role dependencies (`require_role`). Telemetry stubs. SQLAlchemy models (Agent, Department) mapped to Prisma tables. 9 pytest passing.
- **Frontend (`apps/web`):** Next.js 14 App Router shell (sidebar + live-status header), gold-on-ink design tokens (Tailwind), typed API client, marketing landing (`/`) + overview dashboard (`/dashboard`) rendering live agents/departments from the API. Typecheck + build + lint clean.
- **DB:** first Prisma migration (`init`) applied to native Postgres 17; dev seed run (13 departments, 8 agents).
- **Verified:** full-stack demo — `/dashboard` renders seeded agents live from FastAPI→Postgres; `/api/health/ready` reports database + redis ok.
- **Decisions:** ADR-0003 (SQLAlchemy async runtime; Prisma = schema/migrations/TS-types), fixed dashboard routing to a real `dashboard/` segment (blueprint §D.2 URLs).

### Added — Phase 0 (foundation)
- **Phase 0 — Foundation.** Monorepo skeleton (pnpm + Turborepo), git repo + `navigreen311/simforge` remote.
- `CLAUDE.md` (persona, recipe, quality gates, SimForge context) and 5 Claude commands (`impl-feature`, `test-suite`, `deploy-prod`, `code-review`, `api-test`).
- Complete Prisma schema — 17 entities (`packages/db/schema.prisma`) + dev seed skeleton (13 departments, 8 agents).
- `docker-compose.yml` (Postgres 15 + Redis 7 + optional Ollama), `.env.example`, `.gitattributes` (LF normalization).
- Docs: `SIMFORGE.md`, `BLUEPRINT.md`, `SPEC.md` pointer, `ROADMAP.md`, `DECISIONS.md` (ADR-0001…0005), `CONTRIBUTING.md`, `CONSTITUTION_v1.0.0.yml`.
- `scripts/bootstrap.sh`, `scripts/smoke-test.sh`.
