"""PEP SDK — TTL decision cache + invalidation + graceful degradation (ADR-0024)."""

from __future__ import annotations

from src.services.governance.pdp import AuthDecision, AuthRequest
from src.services.pep.pep import Pep
from src.services.pep.subscriber import apply_revocation_event

ACTION = "cre-forge.call_center.outbound"


class _Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, s: float) -> None:
        self.t += s


class _Source:
    def __init__(self, decision: AuthDecision | None = None, raises: bool = False) -> None:
        self.decision = decision
        self.raises = raises
        self.calls = 0

    async def __call__(self, req: AuthRequest) -> AuthDecision:
        self.calls += 1
        if self.raises:
            raise ConnectionError("pdp unreachable")
        assert self.decision is not None
        return self.decision


def _allow(ttl: int = 60) -> AuthDecision:
    return AuthDecision("allow", "autonomy_sufficient", "ok", ttl_seconds=ttl)


def _req() -> AuthRequest:
    return AuthRequest(subject_agent_id="agent_x", action=ACTION)


async def test_cache_hit_avoids_second_pdp_call() -> None:
    src = _Source(_allow())
    pep = Pep(src, clock=_Clock())
    assert (await pep.authorize(_req())).decision == "allow"
    assert (await pep.authorize(_req())).decision == "allow"
    assert src.calls == 1  # second served from cache
    assert pep.cache_hit_ratio() == 0.5


async def test_ttl_expiry_refetches() -> None:
    clock = _Clock()
    src = _Source(_allow(ttl=60))
    pep = Pep(src, clock=clock)
    await pep.authorize(_req())
    clock.advance(61)
    await pep.authorize(_req())
    assert src.calls == 2


async def test_ttl_is_capped() -> None:
    clock = _Clock()
    src = _Source(_allow(ttl=99999))
    pep = Pep(src, max_ttl_seconds=300, clock=clock)
    await pep.authorize(_req())
    clock.advance(301)  # past the cap, before the raw ttl
    await pep.authorize(_req())
    assert src.calls == 2


async def test_invalidate_drops_entry() -> None:
    src = _Source(_allow())
    pep = Pep(src, clock=_Clock())
    await pep.authorize(_req())
    assert pep.invalidate("agent_x", ACTION) == 1
    await pep.authorize(_req())
    assert src.calls == 2  # re-fetched after invalidation


async def test_degrade_serves_last_known() -> None:
    clock = _Clock()
    src = _Source(_allow(ttl=60))
    pep = Pep(src, clock=clock)
    await pep.authorize(_req())  # caches allow
    clock.advance(61)  # expire it
    src.raises = True  # PDP now down
    d = await pep.authorize(_req())
    assert d.decision == "allow" and d.reason_code == "degraded_last_known"


async def test_degrade_downgrades_after_24h() -> None:
    clock = _Clock()
    src = _Source(_allow(ttl=60))
    pep = Pep(src, clock=clock)
    await pep.authorize(_req())
    clock.advance(61)
    src.raises = True
    await pep.authorize(_req())  # outage begins here
    clock.advance(24 * 3600)
    d = await pep.authorize(_req())
    assert d.decision == "step_up_approval_required" and d.reason_code == "degraded_downgrade"
    assert d.required_approver == "human_supervisor"


async def test_degrade_no_cache_fails_closed() -> None:
    src = _Source(raises=True)
    pep = Pep(src, clock=_Clock())
    d = await pep.authorize(_req())  # never had a cached decision
    assert d.decision == "deny" and d.reason_code == "degraded_fail_closed"


async def test_recovery_clears_outage() -> None:
    clock = _Clock()
    src = _Source(_allow(ttl=60))
    pep = Pep(src, clock=clock)
    await pep.authorize(_req())
    clock.advance(61)
    src.raises = True
    await pep.authorize(_req())
    assert pep.stats()["pdp_outage"] is True
    src.raises = False
    clock.advance(1)
    await pep.authorize(_req())
    assert pep.stats()["pdp_outage"] is False


async def test_apply_revocation_event() -> None:
    src = _Source(_allow())
    pep = Pep(src, clock=_Clock())
    await pep.authorize(_req())
    evt = '{"agent_id": "agent_x", "forge_cap": "cre-forge.call_center.outbound", "event": "x"}'
    n = apply_revocation_event(pep, evt)
    assert n == 1
    assert apply_revocation_event(pep, "not json") == 0
    assert apply_revocation_event(pep, '{"missing": "fields"}') == 0
