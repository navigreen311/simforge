"""PEP core — TTL decision cache + graceful degradation (blueprint §F.6, §J.6; ADR-0024).

The PEP asks the PDP once, caches the `AuthDecision` for its `ttl_seconds`, and serves the cache
until it expires or a revocation event invalidates it. If the PDP is unreachable it degrades
gracefully: serve the last-known decision (so a Village keeps operating at its last-certified
level), and after a sustained outage (default 24h, §J.6) downgrade any cached `allow` to
`step_up_approval_required` — forcing human oversight. With no cached decision, apply the action's
fail policy (default fail-closed → deny).
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace

from src.services.governance.pdp import AuthDecision, AuthRequest, fail_policy_for
from src.telemetry.metrics import PDP_CACHE_HIT_RATIO

DecisionSource = Callable[[AuthRequest], Awaitable[AuthDecision]]
_DEGRADE_DOWNGRADE_AFTER_S = 24 * 3600  # §J.6: after 24h outage, downgrade L5→L4-equivalent


@dataclass
class _Entry:
    decision: AuthDecision
    expires_at: float
    stored_at: float


class Pep:
    def __init__(
        self,
        source: DecisionSource,
        *,
        max_ttl_seconds: int = 300,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._source = source
        self._cache: dict[tuple[str, str, str | None], _Entry] = {}
        self._max_ttl = max_ttl_seconds
        self._clock = clock
        self._hits = 0
        self._misses = 0
        self._outage_started: float | None = None

    def _key(self, req: AuthRequest) -> tuple[str, str, str | None]:
        return (req.subject_agent_id, req.action, req.resource)

    def _update_gauge(self) -> None:
        total = self._hits + self._misses
        PDP_CACHE_HIT_RATIO.set(self._hits / total if total else 0.0)

    async def authorize(self, req: AuthRequest) -> AuthDecision:
        key = self._key(req)
        now = self._clock()
        entry = self._cache.get(key)
        if entry is not None and entry.expires_at > now:
            self._hits += 1
            self._update_gauge()
            return entry.decision

        self._misses += 1
        self._update_gauge()
        try:
            decision = await self._source(req)
        except Exception:  # noqa: BLE001 — PDP unreachable → graceful degradation
            return self._degrade(req, entry, now)

        self._outage_started = None
        ttl = max(1, min(decision.ttl_seconds, self._max_ttl))
        self._cache[key] = _Entry(decision, now + ttl, now)
        return decision

    def _degrade(self, req: AuthRequest, entry: _Entry | None, now: float) -> AuthDecision:
        if self._outage_started is None:
            self._outage_started = now
        outage = now - self._outage_started

        if entry is not None:
            dec = entry.decision
            if outage >= _DEGRADE_DOWNGRADE_AFTER_S and dec.decision == "allow":
                return replace(
                    dec,
                    decision="step_up_approval_required",
                    reason_code="degraded_downgrade",
                    reason_detail="PDP outage >24h: autonomy downgraded, human approval required",
                    required_approver="human_supervisor",
                )
            return replace(
                dec,
                reason_code="degraded_last_known",
                reason_detail="PDP unreachable; serving last-known decision",
            )

        # No cached decision → the action's fail policy decides.
        if fail_policy_for(req.action) == "fail_open":
            return AuthDecision(
                "allow", "degraded_fail_open", "PDP unreachable, no cache, action is fail-open", 10
            )
        return AuthDecision(
            "deny", "degraded_fail_closed", "PDP unreachable, no cache, action is fail-closed", 10
        )

    def invalidate(self, agent_id: str, forge_cap: str) -> int:
        """Drop cached decisions for (agent, action). Called on a `simforge:revocations` event."""
        keys = [k for k in self._cache if k[0] == agent_id and k[1] == forge_cap]
        for k in keys:
            del self._cache[k]
        return len(keys)

    def cache_hit_ratio(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total else 0.0

    def stats(self) -> dict:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_ratio": self.cache_hit_ratio(),
            "entries": len(self._cache),
            "pdp_outage": self._outage_started is not None,
        }
