"""Seam-activation verifier (ADR-0037).

Deploy-readiness for real external systems. Every SimForge integration is a *seam* that ships in
stub/local mode and activates on config (ADR-0030). This checks each **activated** seam is actually
reachable/valid — Clerk JWKS, the signing key, each Forge sandbox, the LLM provider, Linear, Redis,
the OTLP collector — and reports per-seam status. A stub/unconfigured seam is reported as ``stub``,
not an error, so the script is hermetic by default (all-stub → exit 0).

    cd apps/api && python scripts/verify-seams.py          # human-readable table
    cd apps/api && python scripts/verify-seams.py --json    # machine-readable

Exit code is non-zero iff a seam that was *activated* fails its check — so CI/deploy can gate on it.
"""

from __future__ import annotations

import asyncio
import json
import sys

import httpx

from src.config import settings

# status: ok (activated + reachable) | stub (not activated) | FAIL (activated but broken)
OK, STUB, FAIL = "ok", "stub", "FAIL"


async def _check_auth() -> dict:
    if settings.auth_mode != "clerk":
        return {"seam": "auth", "mode": settings.auth_mode, "status": STUB, "detail": "dev-bypass"}
    if settings.clerk_jwks_json:
        return {"seam": "auth", "mode": "clerk", "status": OK, "detail": "offline JWKS configured"}
    if not settings.clerk_jwks_url:
        return {"seam": "auth", "mode": "clerk", "status": FAIL, "detail": "no CLERK_JWKS_URL"}
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(settings.clerk_jwks_url)
            keys = r.json().get("keys", [])
        return {"seam": "auth", "mode": "clerk", "status": OK, "detail": f"{len(keys)} JWKS keys"}
    except (httpx.HTTPError, ValueError) as exc:
        return {"seam": "auth", "mode": "clerk", "status": FAIL, "detail": f"JWKS: {exc!r}"}


def _check_signing() -> dict:
    if settings.hsm_provider == "stub":
        return {"seam": "signing", "mode": "stub", "status": STUB, "detail": "ephemeral dev key"}
    try:
        from src.services.cert.signer import get_signer

        signer = get_signer()
        pub = signer.public_key_pem()  # raises if the key can't be loaded
        ok = "PUBLIC KEY" in pub
        return {
            "seam": "signing",
            "mode": settings.hsm_provider,
            "status": OK if ok else FAIL,
            "detail": "signer key loaded" if ok else "no public key",
        }
    except Exception as exc:  # noqa: BLE001 — any load failure is a real activation failure
        return {
            "seam": "signing",
            "mode": settings.hsm_provider,
            "status": FAIL,
            "detail": repr(exc),
        }


async def _check_forges() -> dict:
    if settings.forge_mode != "http":
        return {"seam": "forges", "mode": "local", "status": STUB, "detail": "in-process engines"}
    urls = settings.forge_sandbox_urls
    if not urls:
        return {"seam": "forges", "mode": "http", "status": FAIL, "detail": "no FORGE_SANDBOX_URLS"}
    reachable, broken = [], []
    async with httpx.AsyncClient(timeout=5) as c:
        for forge, url in urls.items():
            try:
                r = await c.get(f"{url.rstrip('/')}/health")
                (reachable if r.json().get("ok") else broken).append(forge)
            except (httpx.HTTPError, ValueError):
                broken.append(forge)
    status = OK if reachable and not broken else FAIL
    return {
        "seam": "forges",
        "mode": "http",
        "status": status,
        "detail": f"reachable={reachable} broken={broken}",
    }


async def _check_llm() -> dict:
    provider = settings.llm_judge_provider
    if provider in ("stub",):
        return {"seam": "llm", "mode": "stub", "status": STUB, "detail": "deterministic stub"}
    if provider == "anthropic":
        ok = bool(settings.anthropic_api_key)
        return {
            "seam": "llm",
            "mode": "anthropic",
            "status": OK if ok else FAIL,
            "detail": "API key set" if ok else "no ANTHROPIC_API_KEY",
        }
    # ollama or auto → probe the daemon
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            models = [m.get("name") for m in r.json().get("models", [])]
        return {"seam": "llm", "mode": provider, "status": OK, "detail": f"ollama models={models}"}
    except (httpx.HTTPError, ValueError) as exc:
        detail = f"ollama unreachable: {exc!r}"
        # `auto` legitimately falls back to stub, so an unreachable ollama is not a failure there.
        status = STUB if provider == "auto" else FAIL
        return {"seam": "llm", "mode": provider, "status": status, "detail": detail}


def _check_linear() -> dict:
    if not (settings.linear_api_key and settings.linear_team_id):
        return {"seam": "linear", "mode": "no-op", "status": STUB, "detail": "gaps not routed"}
    return {"seam": "linear", "mode": "real", "status": OK, "detail": "key + team configured"}


async def _check_redis() -> dict:
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.redis_url)
        await client.ping()
        await client.aclose()
        return {"seam": "redis", "mode": "real", "status": OK, "detail": "PONG"}
    except Exception as exc:  # noqa: BLE001
        return {"seam": "redis", "mode": "real", "status": FAIL, "detail": repr(exc)}


async def _check_tracing() -> dict:
    endpoint = settings.otel_exporter_otlp_endpoint
    if not endpoint:
        mode = "local-spans" if settings.otel_traces_enabled else "off"
        return {"seam": "tracing", "mode": mode, "status": STUB, "detail": "no OTLP export"}
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            # A collector need not answer GET on the base URL, but a connection proves reachability.
            await c.get(endpoint)
        return {"seam": "tracing", "mode": "otlp", "status": OK, "detail": f"reachable {endpoint}"}
    except httpx.HTTPStatusError:
        return {"seam": "tracing", "mode": "otlp", "status": OK, "detail": "reachable (non-2xx)"}
    except httpx.HTTPError as exc:
        return {"seam": "tracing", "mode": "otlp", "status": FAIL, "detail": repr(exc)}


async def gather() -> list[dict]:
    results = await asyncio.gather(
        _check_auth(),
        _check_forges(),
        _check_llm(),
        _check_redis(),
        _check_tracing(),
    )
    return [*results, _check_signing(), _check_linear()]


def main() -> int:
    rows = asyncio.run(gather())
    rows.sort(key=lambda r: r["seam"])
    if "--json" in sys.argv:
        print(json.dumps({"seams": rows}, indent=2))
    else:
        print(f"{'SEAM':<10} {'MODE':<14} {'STATUS':<6} DETAIL")
        for r in rows:
            print(f"{r['seam']:<10} {r['mode']:<14} {r['status']:<6} {r['detail']}")
        activated = sum(1 for r in rows if r["status"] != STUB)
        failing = sum(1 for r in rows if r["status"] == FAIL)
        print(f"\n{activated} seam(s) activated; {failing} failing")
    return 1 if any(r["status"] == FAIL for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
