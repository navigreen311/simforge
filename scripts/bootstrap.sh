#!/usr/bin/env bash
# SimForge local bootstrap — idempotent. Brings up infra, installs deps, migrates, seeds.
# Usage: ./scripts/bootstrap.sh [--with-llm]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

log() { printf "\033[1;33m[bootstrap]\033[0m %s\n" "$*"; }

# 0. .env
if [[ ! -f .env ]]; then
  log "Creating .env from .env.example (fill in placeholders after)."
  cp .env.example .env
fi

# 1. Infra
COMPOSE_SVCS="postgres redis"
if [[ "${1:-}" == "--with-llm" ]]; then
  log "Starting Postgres + Redis + Ollama…"
  docker compose --profile llm up -d $COMPOSE_SVCS ollama
else
  log "Starting Postgres + Redis…"
  docker compose up -d $COMPOSE_SVCS
fi

# 2. Wait for Postgres
log "Waiting for Postgres…"
until docker compose exec -T postgres pg_isready -U simforge >/dev/null 2>&1; do
  sleep 1
done
log "Postgres is ready."

# 3. JS deps
if command -v pnpm >/dev/null 2>&1; then
  log "Installing JS workspace deps (pnpm)…"
  pnpm install
else
  log "pnpm not found — skipping JS install. Install pnpm >= 9."
fi

# 4. Prisma generate + migrate
if command -v pnpm >/dev/null 2>&1; then
  log "Generating Prisma clients + applying migrations…"
  pnpm --filter @simforge/db generate || log "prisma generate skipped (deps not installed yet)"
  pnpm --filter @simforge/db migrate:deploy || \
    log "No migrations yet — run 'pnpm --filter @simforge/db migrate' to create the first one."
fi

# 5. Python api deps (Phase 1+)
if [[ -f apps/api/pyproject.toml ]]; then
  log "Installing api Python deps…"
  ( cd apps/api && python -m venv .venv && . .venv/Scripts/activate 2>/dev/null || . .venv/bin/activate; \
    pip install -q -e . && ( alembic upgrade head 2>/dev/null || true ) )
else
  log "apps/api/pyproject.toml not present yet (arrives in Phase 1) — skipping."
fi

# 6. Seed
if command -v pnpm >/dev/null 2>&1; then
  log "Seeding dev data…"
  pnpm --filter @simforge/db seed || log "Seed skipped (needs migrations first)."
fi

log "Bootstrap complete. Next: 'pnpm dev' (web :3000, api :8000)."
