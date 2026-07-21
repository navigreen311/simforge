"""Decision sources — how a PEP asks the PDP for a decision (blueprint §F.6; ADR-0024).

- `HttpDecisionSource` — the canonical remote PEP: POST `/api/pdp/decide` over HTTP (an injectable
  transport makes it hermetically testable against the app).
- `local_decision_source` — an in-process source (calls the PDP engine directly with a DB session),
  for a PEP co-located with SimForge.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.governance.pdp import AuthDecision, AuthRequest, pdp


class HttpDecisionSource:
    """Calls the PDP over HTTP. `Authorization` is a bearer token in prod (service account)."""

    def __init__(
        self,
        base_url: str,
        *,
        token: str = "",
        timeout: float = 3.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._timeout = timeout
        self._transport = transport

    async def __call__(self, req: AuthRequest) -> AuthDecision:
        payload = {
            "subject_agent_id": req.subject_agent_id,
            "action": req.action,
            "resource": req.resource,
            "context": req.context,
        }
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self._timeout,
            transport=self._transport,
            headers=self._headers,
        ) as c:
            resp = await c.post("/api/pdp/decide", json=payload)
            resp.raise_for_status()
            body = resp.json()
        return AuthDecision(
            decision=body["decision"],
            reason_code=body["reason_code"],
            reason_detail=body["reason_detail"],
            ttl_seconds=body["ttl_seconds"],
            required_approver=body.get("required_approver"),
            fail_policy=body.get("fail_policy", "fail_closed"),
        )


def local_decision_source(
    session_factory: Callable[[], AsyncSession],
) -> Callable[[AuthRequest], Awaitable[AuthDecision]]:
    """An in-process decision source: run the PDP engine directly against a fresh DB session."""

    async def _source(req: AuthRequest) -> AuthDecision:
        async with session_factory() as session:
            return await pdp.decide(session, req)

    return _source
