"""Deterministic in-process Deal Desk engine (blueprint §E.5 CRE Forge).

Seeds synthetic commercial-real-estate deals, leads, and buyers, injects deal faults, and
"processes" a deal — surfacing any injected fault (a title defect, an undisclosed lien, a
blocked assignment, a stale deal, …). No external service, no randomness. This is the CRE Forge
sandbox for dev/CI; a real CRE Forge sits behind the same adapter over HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.services.forges.base import Fault, FaultType, SandboxTenant
from src.utils.time import utcnow

DEAL_TYPES = ("assignment", "wholesale", "double_close", "novation")

# Deal fault → severity (blueprint §E.5; deal-blocking faults are critical).
_FAULT_SEVERITY = {
    FaultType.TITLE_DEFECT: "P0",
    FaultType.LIEN_UNDISCLOSED: "P0",
    FaultType.ASSIGNMENT_BLOCKED: "P0",
    FaultType.DEAL_STALE: "P1",
    FaultType.BUYER_UNRESPONSIVE: "P1",
    FaultType.SEQUENCE_STALL: "P1",
    FaultType.DUPLICATE_LEAD: "P2",
}


@dataclass
class _Deal:
    deal_id: str
    deal_type: str
    fields: dict
    fault: Fault | None = None


@dataclass
class _Tenant:
    tenant: SandboxTenant
    deals: dict[str, _Deal] = field(default_factory=dict)
    audit: list[dict] = field(default_factory=list)


class DealDeskEngine:
    def __init__(self) -> None:
        self._tenants: dict[str, _Tenant] = {}
        self._seq = 0

    def _next_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}_{self._seq:06d}"

    def provision(self, run_id: str) -> SandboxTenant:
        tid = self._next_id("cre_tenant")
        tenant = SandboxTenant(tenant_id=tid, forge="cre-forge", run_id=run_id, created_at=utcnow())
        self._tenants[tid] = _Tenant(tenant=tenant)
        self._log(tid, "provision", {"run_id": run_id})
        return tenant

    def teardown(self, tenant_id: str) -> None:
        self._tenants.pop(tenant_id, None)

    def create_deal(self, tenant_id: str, deal_type: str) -> _Deal:
        t = self._require(tenant_id)
        deal = _Deal(
            deal_id=self._next_id("cre_deal"),
            deal_type=deal_type if deal_type in DEAL_TYPES else "assignment",
            fields={"buyer": "SYNTHETIC BUYER", "seller": "SYNTHETIC SELLER", "state": "NV"},
        )
        t.deals[deal.deal_id] = deal
        self._log(tenant_id, "create_deal", {"deal_id": deal.deal_id, "type": deal.deal_type})
        return deal

    def inject_fault(self, tenant_id: str, deal_id: str, fault_type: str) -> None:
        t = self._require(tenant_id)
        deal = t.deals[deal_id]
        sev = _FAULT_SEVERITY.get(fault_type, "P1")
        deal.fault = Fault(
            fault_type, sev, f"{fault_type} on {deal.deal_type} deal", deal.deal_type
        )
        self._log(tenant_id, "inject_fault", {"deal_id": deal_id, "type": fault_type})

    def process_deal(self, tenant_id: str, deal_id: str) -> dict:
        """Process the deal; surface any injected fault (the 'detection')."""
        t = self._require(tenant_id)
        deal = t.deals[deal_id]
        result: dict[str, object] = {
            "deal_id": deal_id,
            "deal_type": deal.deal_type,
            "fields": deal.fields,
            "outcome": "clear",
        }
        if deal.fault is not None:
            result["outcome"] = "fault_detected"
            result["fault"] = {
                "type": deal.fault.fault_type,
                "severity": deal.fault.severity,
                "detail": deal.fault.detail,
                "module": deal.fault.module,
            }
        self._log(tenant_id, "process_deal", {"deal_id": deal_id, "outcome": result["outcome"]})
        return result

    def inject_fault_on_deal(self, tenant_id: str, deal_type: str, fault_type: str) -> dict:
        """Convenience: create a deal, inject a fault, process it."""
        deal = self.create_deal(tenant_id, deal_type)
        self.inject_fault(tenant_id, deal.deal_id, fault_type)
        return self.process_deal(tenant_id, deal.deal_id)

    def audit_log(self, tenant_id: str) -> list[dict]:
        return list(self._require(tenant_id).audit)

    def world_state(self, tenant_id: str) -> dict:
        """Rich domain snapshot: every deal on the desk with its type and fault status."""
        t = self._require(tenant_id)
        deals = [
            {
                "deal_id": d.deal_id,
                "deal_type": d.deal_type,
                "status": "faulted" if d.fault else "clear",
                "fault_type": d.fault.fault_type if d.fault else None,
            }
            for d in t.deals.values()
        ]
        by_type: dict[str, int] = {}
        for d in t.deals.values():
            by_type[d.deal_type] = by_type.get(d.deal_type, 0) + 1
        return {
            "deal_count": len(deals),
            "deals": deals,
            "deals_by_type": by_type,
            "faulted_deals": sum(1 for d in t.deals.values() if d.fault),
        }

    def _require(self, tenant_id: str) -> _Tenant:
        if tenant_id not in self._tenants:
            raise KeyError(f"Unknown CRE Forge tenant: {tenant_id}")
        return self._tenants[tenant_id]

    def _log(self, tenant_id: str, action: str, payload: dict) -> None:
        self._tenants[tenant_id].audit.append(
            {"ts": utcnow().isoformat(), "action": action, "payload": payload}
        )


# Process-wide engine (the dev CRE Forge sandbox).
deal_desk = DealDeskEngine()
