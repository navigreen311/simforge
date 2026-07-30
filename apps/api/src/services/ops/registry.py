"""Human Operating Model — queue ownership matrix + SLAs (§11.8).

The single source of truth for SimForge's human-facing output queues: each has a named owner, a
backup, the role whose triage inbox it lands in, and an SLA (in hours). The ops report (service.py)
reads live entities into these queues and computes per-item SLA status.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OpsQueue:
    name: str
    description: str
    owner: str
    backup: str
    role: str  # the triage-inbox role this queue belongs to
    sla_hours: float
    source: str  # which live entity feeds it


# Queue ownership matrix + SLA engine inputs (§11.8; SLAs: P0 4h / P1 24h / P2 72h / cert 48h).
QUEUES: tuple[OpsQueue, ...] = (
    OpsQueue(
        "gaps_p0",
        "P0 gaps blocking readiness",
        "ivan",
        "sre_oncall",
        "sre",
        4,
        "software+village_os gaps (severity P0, open)",
    ),
    OpsQueue(
        "gaps_p1",
        "P1 gaps",
        "sre_oncall",
        "sre_backup",
        "sre",
        24,
        "software+village_os gaps (severity P1, open)",
    ),
    OpsQueue(
        "gaps_p2",
        "P2 gaps",
        "sre_backup",
        "sre_oncall",
        "sre",
        72,
        "software+village_os gaps (severity P2, open)",
    ),
    OpsQueue(
        "cert_reviews",
        "Cert issue/revoke approvals awaiting sign-off",
        "ivan",
        "compliance_lead",
        "compliance_analyst",
        48,
        "pending cert_issuance/cert_revocation approval requests",
    ),
    OpsQueue(
        "appeal_cases",
        "Open cert-decision appeals",
        "compliance_lead",
        "ivan",
        "compliance_analyst",
        48,
        "open/under_review appeals",
    ),
    OpsQueue(
        "regression_alerts",
        "Training proposals from weak/regressed runs",
        "prompt_eng_lead",
        "prompt_eng_backup",
        "prompt_engineer",
        24,
        "proposed training proposals",
    ),
)

QUEUES_BY_NAME: dict[str, OpsQueue] = {q.name: q for q in QUEUES}
ROLES: tuple[str, ...] = tuple(dict.fromkeys(q.role for q in QUEUES))
