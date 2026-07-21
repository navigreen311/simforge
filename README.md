# SimForge

> **Tier-1 governance & certification platform for Village OS agents.**
> SimForge runs Village agents through simulated, high-stakes scenarios, scores them on a 15-dimension rubric (8 performance + 7 cognitive), gates them against per-Pack readiness thresholds, and issues cryptographically-signed capability certificates that gate each agent's autonomy in production.

**Status:** v1.0.0 — **feature-complete** (Phases 0–9 shipped: full spine from scenario run → 15-dim eval → gate → gaps → signed cert → autonomy → governance → observability). See [`docs/ROADMAP.md`](docs/ROADMAP.md) and [`CHANGELOG.md`](CHANGELOG.md).
**Repo:** `navigreen311/simforge`
**Docs:** see [`docs/SIMFORGE.md`](docs/SIMFORGE.md) (architecture), [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md) (full engineering blueprint), [`docs/ROADMAP.md`](docs/ROADMAP.md) (phased build plan).

---

## What it is

| | |
|---|---|
| **Frontend** | Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui — `apps/web`, port `3000` |
| **Backend** | FastAPI (Python 3.12) — `apps/api`, port `8000` |
| **Data** | PostgreSQL 15 via Prisma (schema) + Prisma Client Python — `packages/db` |
| **Queue/Cache** | Redis 7 + RQ workers |
| **Evidence** | S3-compatible object storage (local FS in dev) |
| **Signing** | HSM (dev = local Ed25519 stub, staging = YubiHSM, prod = AWS CloudHSM) |

## Monorepo layout

```
apps/web         Next.js dashboard (Readiness Matrix, Runs, Certs, Gaps, Governance)
apps/api         FastAPI backend (routers, services, workers)
packages/db      Prisma schema — single source of truth for TS + Python types
packages/validator  Pack + Scenario YAML validator (Python CLI)
packages/shared-types  TS types generated from Prisma
packs/           Certification Packs (Greenstone, MedLink Pro) — scenarios/personas/docs
docs/            Architecture, blueprint, runbooks, decisions
infra/           Terraform (prod) + Grafana dashboards
scripts/         bootstrap, smoke-test, seed, fingerprint check
```

## Quick start (local dev)

> **Prerequisites:** Docker, Node ≥ 20 + pnpm ≥ 9, Python 3.12. See [`docs/SIMFORGE.md`](docs/SIMFORGE.md) for details.

```bash
cp .env.example .env          # fill in placeholders
./scripts/bootstrap.sh        # postgres + redis (+ optional ollama), install deps, migrate, seed
pnpm dev                      # web on :3000, api on :8000
```

Then open <http://localhost:3000>.

### Real LLM scoring (optional, ADR-0008)

By default the agent + judge LLMs are a deterministic stub. To use a real model for the
3 LLM-judge dimensions (P7/C1/C2):

```bash
# Ollama (local): ollama serve ; ollama pull llama3.1:8b
export LLM_PROVIDER=ollama LLM_JUDGE_PROVIDER=ollama OLLAMA_BASE_URL=http://localhost:11434
# or Anthropic (cloud):
export LLM_PROVIDER=anthropic LLM_JUDGE_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-ant-...

python scripts/populate-llm-cache.py --provider ollama   # first-time: record hermetic fixtures
```

## v1 local-dev note

SimForge orchestrates external systems (Village OS filesystem, 6 Forge sandbox APIs, Clerk, HSM, Linear). In local dev these run against **stubs** (see `docs/DECISIONS.md`). No real PHI/PII is ever used — all fixtures are synthetic.

## Contributing

This repo is developed with Claude Code under the conventions in [`CLAUDE.md`](CLAUDE.md). Every feature ships in an `ai-feature/<slug>` branch via the [`/impl-feature`](.claude/commands/impl-feature.md) command, with tests, docs, and a demo. See [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md).

## License

Proprietary — Greenstone PCA. All rights reserved.
