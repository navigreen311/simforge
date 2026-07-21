#!/usr/bin/env python3
"""End-to-end PDP/PEP demo: enforce → revoke → real-time invalidation (ADR-0024).

Drives the whole loop against a running SimForge API + Redis:
  1. issue a cert (fresh cap) for david_kim,
  2. a PEP (HTTP source) authorizes the action and caches the decision,
  3. the cert is revoked → the API publishes to `simforge:revocations`,
  4. the PEP's subscriber invalidates its cache → the next authorize flips to deny.

Usage (repo root, api venv, server + Redis up):
  # Windows: use 127.0.0.1 (localhost → IPv6 ::1 breaks async redis vs IPv4 Memurai)
  REDIS_URL=redis://127.0.0.1:6379/0 uvicorn src.main:app --port 8120   # terminal 1
  REDIS_URL=redis://127.0.0.1:6379/0 python scripts/pdp-pep-demo.py --base-url http://127.0.0.1:8120
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

import httpx  # noqa: E402

from src.services.governance.pdp import AuthRequest  # noqa: E402
from src.services.pep import HttpDecisionSource, Pep  # noqa: E402
from src.services.pep.subscriber import listen_for_revocations  # noqa: E402

# A unique cap per run so re-runs never collide with a prior (revoked) cert on the same pair.
CAP = f"capitalforge.demo.pdp_pep_{uuid.uuid4().hex[:8]}"
AGENT = "david_kim"


async def _issue_cert(base_url: str) -> str:
    async with httpx.AsyncClient(base_url=base_url, timeout=30) as c:
        rid = (await c.post("/api/scenarios/scn.gs.src.001/run")).json()["run_id"]
        r = await c.post("/api/certs/agent/issue", json={
            "agent_village_id": AGENT, "forge_cap": CAP, "tier": "foundational",
            "battery_run_ids": [rid], "approver_id": "ivan", "pack_id": "pack.greenstone.v1",
        })
        r.raise_for_status()
        return r.json()["cert"]["id"]


async def _revoke(base_url: str, cert_id: str) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=30) as c:
        (await c.post(f"/api/certs/agent/{cert_id}/revoke", json={"reason": "demo"})).raise_for_status()


async def _main(base_url: str) -> int:
    print(f"1. Issuing cert for {AGENT} / {CAP} …")
    cert_id = await _issue_cert(base_url)

    pep = Pep(HttpDecisionSource(base_url))
    sub = asyncio.create_task(listen_for_revocations(pep))
    await asyncio.sleep(0.5)  # let the subscriber attach

    req = AuthRequest(subject_agent_id=AGENT, action=CAP)
    d1 = await pep.authorize(req)
    print(f"2. PEP authorize (cached): {d1.decision} / {d1.reason_code}")
    d1b = await pep.authorize(req)
    print(f"   PEP authorize again (cache hit={pep.cache_hit_ratio():.2f}): {d1b.decision}")

    print("3. Revoking the cert (API publishes to simforge:revocations) …")
    await _revoke(base_url, cert_id)

    # Give the pub/sub a moment to invalidate the PEP cache.
    for _ in range(20):
        await asyncio.sleep(0.1)
        if pep.stats()["entries"] == 0:
            break
    print(f"4. PEP cache after revoke: entries={pep.stats()['entries']} (0 = invalidated in real time)")

    d2 = await pep.authorize(req)
    print(f"5. PEP authorize post-revoke: {d2.decision} / {d2.reason_code}")

    sub.cancel()
    ok = d1.decision != "deny" and d2.decision == "deny" and pep.stats()["misses"] >= 2
    print(f"\n{'PASS' if ok else 'FAIL'}: enforce -> revoke -> real-time invalidation -> deny")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8120")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(_main(args.base_url)))
