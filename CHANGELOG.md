# Changelog

All notable changes to SimForge. Format: [Keep a Changelog](https://keepachangelog.com/); this project uses SemVer.

## [Unreleased]

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
