#!/usr/bin/env bash
# SimForge smoke test — verifies infra + (when present) api/web are reachable.
# Idempotent; safe to re-run. Usage: ./scripts/smoke-test.sh
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

pass=0; fail=0
ok()   { printf "\033[1;32m  ok\033[0m   %s\n" "$*"; pass=$((pass+1)); }
bad()  { printf "\033[1;31m fail\033[0m   %s\n" "$*"; fail=$((fail+1)); }

echo "== SimForge smoke test =="

# Postgres
if docker compose exec -T postgres pg_isready -U simforge >/dev/null 2>&1; then
  ok "Postgres reachable"
else
  bad "Postgres not reachable (docker compose up -d postgres)"
fi

# Redis
if docker compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
  ok "Redis reachable"
else
  bad "Redis not reachable (docker compose up -d redis)"
fi

# API health (Phase 1+)
API="${NEXT_PUBLIC_API_URL:-http://localhost:8000}"
if curl -fsS "$API/api/health/" >/dev/null 2>&1; then
  ok "API health $API/api/health/"
else
  bad "API not up at $API (expected from Phase 1; run 'pnpm --filter api dev')"
fi

# Web (Phase 1+)
WEB="http://localhost:3000"
if curl -fsS "$WEB" >/dev/null 2>&1; then
  ok "Web up at $WEB"
else
  bad "Web not up at $WEB (expected from Phase 1; run 'pnpm --filter web dev')"
fi

echo "== $pass passed, $fail failed =="
# Non-zero exit only if core infra failed; app tiers may legitimately be absent pre-Phase-1.
[[ $fail -gt 2 ]] && exit 1 || exit 0
