# Runbook — activating real external systems (seam activation)

Every SimForge integration is a **seam** that ships in stub/local mode and activates on config
(ADR-0030). This runbook is how you flip each one to a real system and confirm it. Verify at any time
with:

```bash
cd apps/api && python scripts/verify-seams.py        # table; exit 1 iff an activated seam is broken
python scripts/verify-seams.py --json                # machine-readable
```

`verify-seams` reports each seam as `ok` (activated + reachable), `stub` (not activated — not an
error), or `FAIL` (activated but broken). It is hermetic by default: an all-stub deployment exits 0.
Cross-check the modes (no secrets) at runtime with `GET /api/health/config`.

| Seam | Flip | Verify |
|---|---|---|
| **Auth (Clerk)** | `AUTH_MODE=clerk` + `CLERK_JWKS_URL` (or `CLERK_JWKS_JSON` offline) + `CLERK_ISSUER`/`CLERK_AUDIENCE` | `verify-seams` fetches the JWKS; a request with a real Clerk JWT resolves a Principal |
| **Signing (HSM)** | `HSM_PROVIDER=file` (+ `SIMFORGE_SIGNING_PRIVATE_KEY_PEM`) or `yubihsm`/`cloudhsm` (+ vendor SDK from `pip install 'simforge-api[hsm]'` + device creds) | `verify-seams` loads the signer key; issue a cert and verify the signature |
| **Forges (HTTP)** | `FORGE_MODE=http` + `FORGE_SANDBOX_URLS="name=url,…"` | `verify-seams` hits each `/health`; runs then traverse real HTTP (see below) |
| **LLM** | `LLM_PROVIDER` / `LLM_JUDGE_PROVIDER = ollama\|anthropic\|auto` (+ `OLLAMA_BASE_URL` or `ANTHROPIC_API_KEY`) | `verify-seams` probes the daemon / key; `auto` degrades to stub if unreachable (not a failure) |
| **Gap tickets (Linear)** | `LINEAR_API_KEY` + `LINEAR_TEAM_ID` | `verify-seams` confirms config; a gap emits a real Linear issue (best-effort) |
| **Revocation push (Redis)** | `REDIS_URL` to a real Redis | `verify-seams` pings; revoke a cert → PEP invalidates in real time |
| **Tracing (Tempo)** | `OTEL_EXPORTER_OTLP_ENDPOINT` to a collector | `verify-seams` checks reachability; traces appear in Grafana/Tempo |
| **Integrated exec** | `INTEGRATED_EXECUTION_ENABLED=true` (+ pack opt-in + per-run request) | a run's action ledger shows `applied` entries (PDP-gated) |

## Activating the HTTP Forge seam locally (fully runnable here)

The one external seam with a **runnable reference provider** — no third party needed:

```bash
# terminal 1 — the reference sandbox for all six forges (:8850)
cd apps/api && python scripts/run-forge-sandbox.py

# terminal 2 — the API in http mode, one URL per forge
FORGE_MODE=http \
FORGE_SANDBOX_URLS="capitalforge=http://127.0.0.1:8850/capitalforge,vaf=http://127.0.0.1:8850/vaf,voiceforge=http://127.0.0.1:8850/voiceforge,cre-forge=http://127.0.0.1:8850/cre-forge,medlink-pro=http://127.0.0.1:8850/medlink-pro,funnelforge=http://127.0.0.1:8850/funnelforge" \
uvicorn src.main:app

python scripts/verify-seams.py    # forges → ok, all six reachable
```

`GET /api/health/config` then shows `forge_mode: http`, and a run's forge side-effects traverse real
HTTP (a crisis scenario emits `forge_fault` trace events resolved via the sandbox). A production Forge
implements the same contract — pinned by the Pact tests (ADR-0036), so swapping the reference server
for a vendor sandbox needs no code change.

## What still needs a real third party
`verify-seams` tells you what's live. The seams whose *providers* can't run on a dev box —
a live Clerk tenant, real HSM hardware, a production Forge sandbox, a Grafana/Tempo collector, a
Linear workspace, the real Village OS, and the cloud `terraform apply` — activate the same way (flip
the env, run `verify-seams`, confirm `ok`). The wiring, health checks, and contracts are all in place;
only the credentials/endpoints are supplied at deploy time.

## Cross-references
ADR-0030 (seams + `/api/health/config`), ADR-0037 (this tooling), ADR-0016 (HTTP Forge adapter),
ADR-0036 (the Forge contract), `docs/deploy.md` (the seam matrix).
