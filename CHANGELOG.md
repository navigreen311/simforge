# Changelog

All notable changes to SimForge. Format: [Keep a Changelog](https://keepachangelog.com/); this project uses SemVer.

## [Unreleased]

### Added — Fifth real Forge: medlink-pro (Clinical Console) (post-v1)
- **medlink-pro Clinical Console** — deterministic in-process engine (`services/forges/clinical_console.py`) + `LocalMedLinkProAdapter` (`medlink_pro.py`, version `medlink-pro.console.v1`): tenants, **PHI-synthetic** staffing state (scheduler/compliance/clinician), UI + staffing fault injection + task run. Fault menu: compliance/safety (credential_expired_unflagged/shift_double_booked/phi_overexposure → **P0**), UI/state (ui_blocking_modal/stale_roster/timecard_missing/msa_terms_stale → **P1**). Fixtures synthetic only ("SYNTHETIC CLINICIAN"/"SYNTHETIC FACILITY") — never real PHI. Registry now resolves `medlink-pro` → real adapter.
- **Runner** — `_run_medlink_pro` added to the per-forge dispatch with a per-module fault map (`_CONSOLE_FAULT`: scheduler→shift_double_booked, compliance/clinician→credential_expired_unflagged, else ui_blocking_modal). Reporter is forge-agnostic, so medlink-pro faults become real Software Gaps with no reporter change. Sandbox-isolated (no Village writes).
- **`pack.medlink-pro.v1`** staffing scenarios (e.g. `scn.ml.place.002`) now surface real console faults → Software Gaps.
- **Router** `POST /api/forges/medlink-pro/demo`.
- **Tests:** +14 (155 api + 5 validator) — Clinical Console engine (all 7 fault severities + seed-state), medlink-pro adapter **contract test** (§I.3), registry resolution, demo, and the medlink-pro fault→gap integration on `scn.ml.place.002`. ruff + mypy clean on touched files.
- **Verified live:** `scn.ml.place.002` → `medlink-pro/scheduler` shift_double_booked P0 fault → Software Gap `medlink-pro/scheduler`. ADR-0014. **5 of 6 Forges now real** (only funnelforge remains Null).

### Added — Fourth real Forge: CRE Forge (Deal Desk) (post-v1)
- **CRE Forge Deal Desk** — deterministic in-process engine (`services/forges/deal_desk.py`) + `LocalCREForgeAdapter` (`cre_forge.py`, version `cre-forge.dealdesk.v1`): tenants, synthetic CRE deals (assignment/wholesale/double_close/novation, never real party data), deal-fault injection + processing. Fault menu spans deal (title_defect/lien_undisclosed/assignment_blocked/deal_stale), buyer (buyer_unresponsive), lead/sequence (sequence_stall/duplicate_lead). Severities: title_defect/lien_undisclosed/assignment_blocked → **P0**, deal_stale/buyer_unresponsive/sequence_stall → **P1**, duplicate_lead → **P2**. Registry now resolves `cre-forge` → real adapter.
- **Runner** — `_run_cre_forge` added to the per-forge dispatch; injects `title_defect` (P0) on fault — the crisis scenario's premise. Reporter is forge-agnostic, so CRE Forge faults become real Software Gaps with no reporter change. Sandbox-isolated (no Village writes).
- **`scn.gs.crisis.003`** now surfaces **all three** of its declared forge faults in one run — a CRE `title_defect`, a VAF `forged_signature`, and a VoiceForge `dropped_call`.
- **Router** `POST /api/forges/cre-forge/demo`.
- **Tests:** +13 (141 api + 5 validator) — Deal Desk engine (all 7 fault severities), CRE Forge adapter **contract test** (§I.3), registry resolution, demo, and the CRE Forge fault→gap integration. ruff + mypy clean on touched files.
- **Verified live:** `scn.gs.crisis.003` → `cre-forge/deals` title_defect P0 fault → Software Gap `cre-forge/deals`. ADR-0013. **4 of 6 Forges now real.**

### Added — Third real Forge: VoiceForge (Call Center) (post-v1)
- **VoiceForge Call Center** — deterministic in-process engine (`services/forges/call_center.py`) + `LocalVoiceForgeAdapter` (`voiceforge.py`, version `voiceforge.callcenter.v1`): tenants, synthetic calls against a persona catalog (§E.2 preload), call-fault injection + handling. Fault menu spans line-quality (dropped_call/dead_air/line_noise), call-flow (misroute/hold_timeout/escalation_failure), and compliance (disclosure_missing). Severities: dropped_call/escalation_failure/disclosure_missing → **P0**, rest → **P1**. Registry now resolves `voiceforge` → real adapter.
- **Runner** — `_run_voiceforge` added to the per-forge dispatch; cap's 3rd segment selects call direction (`voiceforge.call_center.inbound` → inbound). Reporter is forge-agnostic, so VoiceForge faults become real Software Gaps with no reporter change. Sandbox-isolated (no Village writes).
- **`scn.gs.crisis.003`** now surfaces **both** a VAF document fault and a VoiceForge call fault in one run (it already declared `voiceforge.call_center.inbound`).
- **Router** `POST /api/forges/voiceforge/demo`.
- **Tests:** +14 (128 api + 5 validator) — Call Center engine (all 7 fault severities), VoiceForge adapter **contract test** (§I.3), registry resolution, demo, and the VoiceForge fault→gap integration. ruff + mypy clean on touched files.
- **Verified live:** `scn.gs.crisis.003` → `voiceforge/call_center` dropped_call P0 fault → Software Gap `voiceforge/call_center`. ADR-0012. **3 of 6 Forges now real.**

### Added — Second real Forge: VisionAudioForge (VAF) Doc Vault (post-v1)
- **VAF Doc Vault** — deterministic in-process engine (`services/forges/doc_vault.py`) + `LocalVAFAdapter` (`visionaudioforge.py`, version `vaf.docvault.v1`): tenants, **synthetic** document generation (never real PHI), document-fault injection + OCR extraction. Fault menu (§E.3) with severities — forged_signature/revoked_license/oig_match → **P0**, expired_date/name_dob_mismatch/altered_amount → **P1**, missing_pages → **P2**. Registry now resolves `vaf` → real adapter.
- **Runner generalized** — `_run_capitalforge_side_effects` → `_run_forge_side_effects`, dispatching per-forge (CapitalForge + VAF). Fault trigger widened to **`tier == "advanced_crisis"` OR even `seed`**. The reporter's `detect_forge_fault_gaps` is forge-agnostic, so **VAF faults become real Software Gaps** with no reporter change. Sandbox-isolated (no Village writes).
- **Scenario** `scn.gs.crisis.003` gains `vaf.doc_vault.retrieve` — the seeded `david_kim` crisis run surfaces a forged-signature fault on the title document.
- **Router** `POST /api/forges/vaf/demo` — mirrors the CapitalForge demo.
- **Tests:** 9 new (114 api + 5 validator) — Doc Vault engine (all 7 fault severities), VAF adapter **contract test** (§I.3), registry resolution, VAF demo, and the VAF fault→gap integration on `scn.gs.crisis.003`. ruff + mypy clean on touched files.
- **Verified live:** `scn.gs.crisis.003` → `vaf/doc_vault` forged_signature fault → Software Gap `vaf/doc_vault`. ADR-0011.

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
