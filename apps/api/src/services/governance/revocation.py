"""Real-time revocation propagation (blueprint §F.4; part of the PDP/PEP series, ADR-0024).

When a cert changes state (revoked / suspended / reinstated / expired) SimForge publishes a small
event to the Redis channel `simforge:revocations`. PEPs subscribe and invalidate their in-process
decision caches fleet-wide, so a revocation takes effect in ~real time instead of at TTL expiry.

Publishing is **best-effort**: a down/absent Redis never fails a cert operation — the event is
dropped and PEPs fall back to TTL-based expiry. Sandbox-safe: publish-only, no reads, no writes to
anything but the ephemeral pub/sub channel.
"""

from __future__ import annotations

import json

import structlog

from src.config import settings
from src.utils.time import utcnow

log = structlog.get_logger(__name__)

REVOCATION_CHANNEL = "simforge:revocations"
# Cert lifecycle events that should invalidate PEP caches.
CertEvent = str  # "revoked" | "suspended" | "reinstated" | "expired"


def event_payload(agent_village_id: str, forge_cap: str, event: CertEvent) -> str:
    return json.dumps(
        {
            "agent_id": agent_village_id,
            "forge_cap": forge_cap,
            "event": event,
            "ts": utcnow().isoformat(),
        },
        sort_keys=True,
    )


async def _redis_publish(channel: str, message: str) -> None:
    """Publish to Redis with a short connect timeout so a down Redis fails fast (never hangs)."""
    import redis.asyncio as aioredis

    client = aioredis.from_url(settings.redis_url, socket_connect_timeout=0.5, socket_timeout=0.5)
    try:
        await client.publish(channel, message)
    finally:
        await client.aclose()


async def publish_cert_event(agent_village_id: str, forge_cap: str, event: CertEvent) -> bool:
    """Best-effort publish of a cert lifecycle event. True if it reached Redis, else False."""
    try:
        await _redis_publish(REVOCATION_CHANNEL, event_payload(agent_village_id, forge_cap, event))
        return True
    except Exception as exc:  # noqa: BLE001 — publishing must never break a cert operation
        # NB: structlog reserves `event` as the message key, so name the field `cert_event`.
        log.warning(
            "revocation_publish_failed",
            cert_event=event,
            agent=agent_village_id,
            forge_cap=forge_cap,
            error=type(exc).__name__,
        )
        return False
