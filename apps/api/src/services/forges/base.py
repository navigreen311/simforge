"""Forge adapter contract (blueprint §E.1).

Every Forge (VoiceForge, VAF, medlink-pro, CRE-Forge, FunnelForge, CapitalForge) implements
this ABC so the scenario runner can provision an isolated sandbox tenant, seed state, inject
faults, and read an audit log — without touching production or the Village.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


class FaultType:
    """Canonical Forge fault kinds."""

    # CapitalForge / Mock Bank (blueprint §E.7)
    DECLINATION = "declination"
    FRAUD_FLAG = "fraud_flag"
    NSF = "nsf"
    OFAC = "ofac"
    VELOCITY = "velocity"

    # VisionAudioForge / Doc Vault (blueprint §E.3 fault menu)
    FORGED_SIGNATURE = "forged_signature"
    EXPIRED_DATE = "expired_date"
    NAME_DOB_MISMATCH = "name_dob_mismatch"
    REVOKED_LICENSE = "revoked_license"
    OIG_MATCH = "oig_match"
    MISSING_PAGES = "missing_pages"
    ALTERED_AMOUNT = "altered_amount"

    # VoiceForge / Call Center (blueprint §E.2 — line-quality + call-flow + compliance)
    DROPPED_CALL = "dropped_call"
    DEAD_AIR = "dead_air"
    LINE_NOISE = "line_noise"
    MISROUTE = "misroute"
    HOLD_TIMEOUT = "hold_timeout"
    ESCALATION_FAILURE = "escalation_failure"
    DISCLOSURE_MISSING = "disclosure_missing"

    # CRE Forge / Deal Desk (blueprint §E.5 — lead/deal/buyer)
    TITLE_DEFECT = "title_defect"
    LIEN_UNDISCLOSED = "lien_undisclosed"
    ASSIGNMENT_BLOCKED = "assignment_blocked"
    DEAL_STALE = "deal_stale"
    BUYER_UNRESPONSIVE = "buyer_unresponsive"
    SEQUENCE_STALL = "sequence_stall"
    DUPLICATE_LEAD = "duplicate_lead"

    # medlink-pro / Clinical Console (blueprint §E.4 — UI-fault + staffing/compliance)
    CREDENTIAL_EXPIRED_UNFLAGGED = "credential_expired_unflagged"
    SHIFT_DOUBLE_BOOKED = "shift_double_booked"
    PHI_OVEREXPOSURE = "phi_overexposure"
    UI_BLOCKING_MODAL = "ui_blocking_modal"
    STALE_ROSTER = "stale_roster"
    TIMECARD_MISSING = "timecard_missing"
    MSA_TERMS_STALE = "msa_terms_stale"

    # FunnelForge / Flows (blueprint §E.6 — lead/segment/campaign/sequence + webhooks)
    WEBHOOK_DROPPED = "webhook_dropped"
    CAMPAIGN_TO_UNSUBSCRIBED = "campaign_to_unsubscribed"
    SEQUENCE_MISFIRE = "sequence_misfire"
    SEGMENT_STALE = "segment_stale"
    BOUNCE_UNHANDLED = "bounce_unhandled"
    LEAD_MISATTRIBUTED = "lead_misattributed"
    DUPLICATE_ENROLLMENT = "duplicate_enrollment"


@dataclass
class Fault:
    fault_type: str
    severity: str  # "P0" | "P1" | "P2"
    detail: str
    module: str


@dataclass
class SandboxTenant:
    tenant_id: str
    forge: str
    run_id: str
    created_at: datetime
    state: dict = field(default_factory=dict)


class ForgeAdapter(ABC):
    forge_name: str = "abstract"

    @abstractmethod
    async def health_check(self) -> dict: ...

    @abstractmethod
    async def provision_sandbox_tenant(self, run_id: str) -> SandboxTenant: ...

    @abstractmethod
    async def teardown_sandbox_tenant(self, tenant_id: str) -> None: ...

    @abstractmethod
    async def seed_state(self, tenant_id: str, fixtures: dict) -> None: ...

    @abstractmethod
    async def get_audit_log(self, tenant_id: str, since: datetime | None = None) -> list[dict]: ...

    @abstractmethod
    async def get_current_version(self) -> str: ...

    @abstractmethod
    async def inject_fault(self, tenant_id: str, fault: Fault) -> None: ...

    @abstractmethod
    async def exercise(self, tenant_id: str, cap: str, fault_type: str | None) -> dict:
        """Exercise a tested capability (optionally injecting a fault) and return a result dict
        ``{"outcome": ..., "fault"?: {...}}``. This is the single uniform op the scenario runner
        drives — the same call works whether the adapter is Local (in-process engine) or HTTP
        (real sandbox), so the runner is forge-agnostic and mode-agnostic. `cap` is the full
        capability string (e.g. ``"capitalforge.emd.release"``); each adapter reads the segments
        it needs."""
        ...


class NullForgeAdapter(ForgeAdapter):
    """Placeholder for Forges not yet wired — reports unhealthy, refuses provisioning."""

    def __init__(self, forge_name: str) -> None:
        self.forge_name = forge_name

    async def health_check(self) -> dict:
        return {"forge": self.forge_name, "ok": False, "reason": "adapter not implemented (v1.1)"}

    async def provision_sandbox_tenant(self, run_id: str) -> SandboxTenant:
        raise NotImplementedError(f"{self.forge_name} adapter not implemented")

    async def teardown_sandbox_tenant(self, tenant_id: str) -> None:
        return None

    async def seed_state(self, tenant_id: str, fixtures: dict) -> None:
        return None

    async def get_audit_log(self, tenant_id: str, since: datetime | None = None) -> list[dict]:
        return []

    async def get_current_version(self) -> str:
        return f"{self.forge_name}.unimplemented"

    async def inject_fault(self, tenant_id: str, fault: Fault) -> None:
        return None

    async def exercise(self, tenant_id: str, cap: str, fault_type: str | None) -> dict:
        return {"outcome": "skipped", "reason": f"{self.forge_name} adapter not implemented"}
