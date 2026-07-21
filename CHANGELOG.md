# Changelog

All notable changes to SimForge. Format: [Keep a Changelog](https://keepachangelog.com/); this project uses SemVer.

## [Unreleased]

### Added
- **Phase 0 — Foundation.** Monorepo skeleton (pnpm + Turborepo), git repo + `navigreen311/simforge` remote.
- `CLAUDE.md` (persona, recipe, quality gates, SimForge context) and 5 Claude commands (`impl-feature`, `test-suite`, `deploy-prod`, `code-review`, `api-test`).
- Complete Prisma schema — 17 entities (`packages/db/schema.prisma`) + dev seed skeleton (13 departments, 8 agents).
- `docker-compose.yml` (Postgres 15 + Redis 7 + optional Ollama), `.env.example`, `.gitattributes` (LF normalization).
- Docs: `SIMFORGE.md`, `BLUEPRINT.md`, `SPEC.md` pointer, `ROADMAP.md`, `DECISIONS.md` (ADR-0001…0005), `CONTRIBUTING.md`, `CONSTITUTION_v1.0.0.yml`.
- `scripts/bootstrap.sh`, `scripts/smoke-test.sh`.
