"""PEP revocation subscriber — invalidate cached decisions on `simforge:revocations` (ADR-0024).

Runs as a background task inside a PEP host. Each event `{agent_id, forge_cap, event, ts}` drops the
matching cached decisions so a revoke/suspend takes effect in ~real time, not at TTL expiry. If
Redis is unreachable the PEP still works — it just falls back to TTL-based expiry.
"""

from __future__ import annotations

import json

import structlog

from src.config import settings
from src.services.governance.revocation import REVOCATION_CHANNEL
from src.services.pep.pep import Pep

log = structlog.get_logger(__name__)


def apply_revocation_event(pep: Pep, raw: str) -> int:
    """Parse one channel message and invalidate the PEP's matching cache entries. Returns count."""
    try:
        event = json.loads(raw)
        agent_id = event["agent_id"]
        forge_cap = event["forge_cap"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return 0
    return pep.invalidate(agent_id, forge_cap)


async def listen_for_revocations(pep: Pep, *, redis_url: str | None = None) -> None:
    """Subscribe to `simforge:revocations`, invalidating `pep` on each event (until cancelled).

    Best-effort: a Redis error is logged and ends the loop; the caller may retry with backoff."""
    import redis.asyncio as aioredis

    client = aioredis.from_url(redis_url or settings.redis_url)
    pubsub = client.pubsub()
    try:
        await pubsub.subscribe(REVOCATION_CHANNEL)
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            data = message["data"]
            if isinstance(data, bytes):
                data = data.decode()
            n = apply_revocation_event(pep, data)
            if n:
                log.info("pep_cache_invalidated", entries=n)
    except Exception as exc:  # noqa: BLE001 — never crash the host on a Redis hiccup
        log.warning("pep_subscriber_stopped", error=type(exc).__name__)
    finally:
        await pubsub.aclose()
        await client.aclose()
