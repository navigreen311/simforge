"""Revocation publisher — best-effort Redis pub/sub for real-time PEP invalidation (ADR-0024)."""

from __future__ import annotations

import asyncio
import json

import pytest

from src.config import settings
from src.services.governance import revocation
from src.services.governance.revocation import (
    REVOCATION_CHANNEL,
    event_payload,
    publish_cert_event,
)


def test_event_payload_shape() -> None:
    payload = json.loads(event_payload("david_kim", "cre-forge.deals.title", "revoked"))
    assert payload["agent_id"] == "david_kim"
    assert payload["forge_cap"] == "cre-forge.deals.title"
    assert payload["event"] == "revoked"
    assert "ts" in payload


async def test_publish_success(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[tuple[str, str]] = []

    async def _capture(channel: str, message: str) -> None:
        sent.append((channel, message))

    monkeypatch.setattr(revocation, "_redis_publish", _capture)
    ok = await publish_cert_event("agent_x", "vaf.doc.retrieve", "suspended")
    assert ok is True
    assert len(sent) == 1
    channel, message = sent[0]
    assert channel == REVOCATION_CHANNEL
    assert json.loads(message)["event"] == "suspended"


async def test_publish_swallows_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _boom(channel: str, message: str) -> None:
        raise ConnectionError("redis down")

    monkeypatch.setattr(revocation, "_redis_publish", _boom)
    # A down Redis must never raise — it returns False and the cert op continues.
    ok = await publish_cert_event("agent_x", "vaf.doc.retrieve", "revoked")
    assert ok is False


async def _redis_reachable() -> bool:
    try:
        import redis.asyncio as aioredis

        c = aioredis.from_url(settings.redis_url, socket_connect_timeout=2.0)
        try:
            await c.ping()
            return True
        finally:
            await c.aclose()
    except Exception:  # noqa: BLE001
        return False


async def test_real_redis_roundtrip() -> None:
    """Real pub/sub against a live Redis/Memurai — subscriber receives the published event.

    Skips when Redis is unreachable (e.g. CI has no Redis service), so it never gates CI.
    """
    if not await _redis_reachable():
        pytest.skip("Redis/Memurai not reachable")

    import redis.asyncio as aioredis

    client = aioredis.from_url(settings.redis_url)
    pubsub = client.pubsub()
    await pubsub.subscribe(REVOCATION_CHANNEL)
    # Drain the subscribe confirmation.
    await pubsub.get_message(timeout=1.0)

    assert await publish_cert_event("round_trip_agent", "cre-forge.deals.title", "revoked") is True

    received = None
    for _ in range(10):
        msg = await pubsub.get_message(timeout=1.0)
        if msg and msg.get("type") == "message":
            received = json.loads(msg["data"])
            break
        await asyncio.sleep(0.05)

    await pubsub.unsubscribe(REVOCATION_CHANNEL)
    await pubsub.aclose()
    await client.aclose()

    assert received is not None and received["agent_id"] == "round_trip_agent"
    assert received["event"] == "revoked"
