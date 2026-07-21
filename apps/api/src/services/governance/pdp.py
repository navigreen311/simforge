"""Policy Decision Point — the centralized authorization engine (blueprint §F.6; ADR-0024).

The PDP answers one question: *may agent X perform action Y right now?* — turning the certs SimForge
issues into runtime enforcement. A decision is derived from the agent's **active cert** for the
action (a Forge capability), its **autonomy level** on the ladder, cert lifecycle state
(active/suspended/revoked/expired), and emergency **safe-mode**. PEPs (blueprint §F.6) call this and
cache the result for `ttl_seconds`.

Decision × cause:
  - allow                        — active cert, autonomy L4 (spot-check) or L5 (full)
  - step_up_approval_required    — active cert, autonomy L3 (exec + approval), or safe-mode
  - downgrade_and_retry          — active cert, autonomy L2 (draft only) — execute as a draft
  - deny                         — no/suspended/revoked/expired cert, or autonomy L1 (observe only)

Fail-open/closed (§F.6) is what a PEP does when it *can't reach* the PDP; the PDP annotates each
action with its fail policy (default **fail-closed** for compliance-adjacent Forges).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.cert import AgentCert
from src.services.cert.autonomy_ladder import LEVELS
from src.services.governance.safe_mode import safe_mode
from src.utils.time import utcnow

Decision = Literal["allow", "deny", "step_up_approval_required", "downgrade_and_retry"]

# Forges whose actions are compliance-adjacent → fail-closed when the PDP is unreachable.
# (All current Forges touch regulated workflows, so every action defaults fail-closed.)
_FAIL_OPEN_FORGES: frozenset[str] = frozenset()  # none in v1 — everything fails closed


@dataclass
class AuthRequest:
    subject_agent_id: str
    action: str  # a Forge capability, e.g. "cre-forge.call_center.outbound"
    resource: str | None = None
    context: dict = field(default_factory=dict)  # jurisdiction, time_of_day, caseload, approver…


@dataclass
class AuthDecision:
    decision: Decision
    reason_code: str
    reason_detail: str
    ttl_seconds: int
    required_approver: str | None = None
    fail_policy: str = "fail_closed"  # what a PEP does if it can't reach the PDP

    def as_dict(self) -> dict:
        return {
            "decision": self.decision,
            "reason_code": self.reason_code,
            "reason_detail": self.reason_detail,
            "ttl_seconds": self.ttl_seconds,
            "required_approver": self.required_approver,
            "fail_policy": self.fail_policy,
        }


def fail_policy_for(action: str) -> str:
    """Fail-open vs fail-closed for an action class (§F.6). Default fail-closed."""
    forge = action.split(".", 1)[0]
    return "fail_open" if forge in _FAIL_OPEN_FORGES else "fail_closed"


class PDP:
    """Stateless decision engine. One `decide` per authorization query."""

    def _approver(self, req: AuthRequest) -> str:
        return str(req.context.get("approver") or "human_supervisor")

    async def decide(self, session: AsyncSession, req: AuthRequest) -> AuthDecision:
        fail = fail_policy_for(req.action)

        # Emergency safe-mode: nothing runs autonomously — everything needs a human.
        if safe_mode.active:
            return AuthDecision(
                "step_up_approval_required",
                "safe_mode_active",
                f"Safe mode active: {safe_mode.reason or 'emergency halt'}",
                ttl_seconds=10,
                required_approver=self._approver(req),
                fail_policy=fail,
            )

        agent = (
            await session.execute(select(Agent).where(Agent.villageAgentId == req.subject_agent_id))
        ).scalar_one_or_none()
        if agent is None:
            return AuthDecision(
                "deny",
                "unknown_subject",
                f"No such agent: {req.subject_agent_id}",
                60,
                fail_policy=fail,
            )

        cert = (
            await session.execute(
                select(AgentCert).where(
                    AgentCert.agentId == agent.id, AgentCert.forgeCap == req.action
                )
            )
        ).scalar_one_or_none()
        if cert is None:
            return AuthDecision(
                "deny",
                "no_certification",
                f"{req.subject_agent_id} holds no cert for {req.action}",
                60,
                fail_policy=fail,
            )
        if cert.status == "revoked":
            return AuthDecision(
                "deny", "cert_revoked", "Certification revoked", 60, fail_policy=fail
            )
        if cert.status == "suspended":
            return AuthDecision(
                "deny",
                "cert_suspended",
                "Certification suspended pending re-certification",
                60,
                fail_policy=fail,
            )
        if cert.status == "expired" or cert.expiresAt < utcnow():
            return AuthDecision(
                "deny", "cert_expired", "Certification expired", 15, fail_policy=fail
            )

        # Active cert → map the autonomy ladder to a decision.
        level = agent.currentAutonomyLevel
        idx = LEVELS.index(level) if level in LEVELS else 0  # L1..L5 → 0..4
        if idx >= 3:  # L4 spot-check, L5 full
            return AuthDecision(
                "allow",
                "autonomy_sufficient",
                f"Active cert + autonomy {level}",
                60,
                fail_policy=fail,
            )
        if idx == 2:  # L3 exec + approval
            return AuthDecision(
                "step_up_approval_required",
                "approval_required_l3",
                f"Autonomy {level}: execution requires human approval",
                30,
                required_approver=self._approver(req),
                fail_policy=fail,
            )
        if idx == 1:  # L2 draft
            return AuthDecision(
                "downgrade_and_retry",
                "draft_only_l2",
                f"Autonomy {level}: produce a draft for review, not a live action",
                30,
                fail_policy=fail,
            )
        return AuthDecision(
            "deny",
            "observe_only_l1",
            f"Autonomy {level}: observe only — not cleared to act",
            60,
            fail_policy=fail,
        )


# Process-wide engine.
pdp = PDP()
