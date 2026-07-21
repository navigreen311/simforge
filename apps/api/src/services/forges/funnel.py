"""Deterministic in-process Funnel engine (blueprint §E.6 FunnelForge).

Seeds synthetic leads/segments/campaigns/sequences, injects flow faults, and "runs" a flow —
surfacing any injected fault (a dropped webhook, a message to an unsubscribed lead, a sequence
misfire, a stale segment, …). No external service, no randomness. This is the FunnelForge sandbox
for dev/CI; a real FunnelForge sits behind the same adapter over HTTP + webhooks.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.services.forges.base import Fault, FaultType, SandboxTenant
from src.utils.time import utcnow

MODULES = ("leads", "segments", "campaigns", "sequences")

# Flow fault → severity (blueprint §E.6; delivery/compliance faults are critical).
_FAULT_SEVERITY = {
    FaultType.WEBHOOK_DROPPED: "P0",
    FaultType.CAMPAIGN_TO_UNSUBSCRIBED: "P0",
    FaultType.SEQUENCE_MISFIRE: "P1",
    FaultType.SEGMENT_STALE: "P1",
    FaultType.BOUNCE_UNHANDLED: "P1",
    FaultType.LEAD_MISATTRIBUTED: "P1",
    FaultType.DUPLICATE_ENROLLMENT: "P2",
}


@dataclass
class _Flow:
    flow_id: str
    module: str
    fields: dict
    fault: Fault | None = None


@dataclass
class _Tenant:
    tenant: SandboxTenant
    seed_params: dict = field(default_factory=dict)
    flows: dict[str, _Flow] = field(default_factory=dict)
    audit: list[dict] = field(default_factory=list)


class FunnelEngine:
    def __init__(self) -> None:
        self._tenants: dict[str, _Tenant] = {}
        self._seq = 0

    def _next_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}_{self._seq:06d}"

    def provision(self, run_id: str) -> SandboxTenant:
        tid = self._next_id("ff_tenant")
        tenant = SandboxTenant(
            tenant_id=tid, forge="funnelforge", run_id=run_id, created_at=utcnow()
        )
        self._tenants[tid] = _Tenant(tenant=tenant)
        self._log(tid, "provision", {"run_id": run_id})
        return tenant

    def teardown(self, tenant_id: str) -> None:
        self._tenants.pop(tenant_id, None)

    def seed_state(self, tenant_id: str, params: dict) -> None:
        """Seed lead/segment/campaign/sequence state."""
        t = self._require(tenant_id)
        t.seed_params.update(params)
        self._log(tenant_id, "seed_state", {"keys": sorted(params.keys())})

    def start_flow(self, tenant_id: str, module: str) -> _Flow:
        t = self._require(tenant_id)
        flow = _Flow(
            flow_id=self._next_id("ff_flow"),
            module=module if module in MODULES else "sequences",
            fields={"lead": "SYNTHETIC LEAD", "campaign": "SYNTHETIC CAMPAIGN"},
        )
        t.flows[flow.flow_id] = flow
        self._log(tenant_id, "start_flow", {"flow_id": flow.flow_id, "module": flow.module})
        return flow

    def inject_fault(self, tenant_id: str, flow_id: str, fault_type: str) -> None:
        t = self._require(tenant_id)
        flow = t.flows[flow_id]
        sev = _FAULT_SEVERITY.get(fault_type, "P1")
        flow.fault = Fault(fault_type, sev, f"{fault_type} in {flow.module}", flow.module)
        self._log(tenant_id, "inject_fault", {"flow_id": flow_id, "type": fault_type})

    def run_flow(self, tenant_id: str, flow_id: str) -> dict:
        """Run the flow; surface any injected fault (the 'detection')."""
        t = self._require(tenant_id)
        flow = t.flows[flow_id]
        result: dict[str, object] = {
            "flow_id": flow_id,
            "module": flow.module,
            "fields": flow.fields,
            "outcome": "ok",
        }
        if flow.fault is not None:
            result["outcome"] = "fault_detected"
            result["fault"] = {
                "type": flow.fault.fault_type,
                "severity": flow.fault.severity,
                "detail": flow.fault.detail,
                "module": flow.fault.module,
            }
        self._log(tenant_id, "run_flow", {"flow_id": flow_id, "outcome": result["outcome"]})
        return result

    def inject_fault_on_flow(self, tenant_id: str, module: str, fault_type: str) -> dict:
        """Convenience: start a flow, inject a fault, run it."""
        flow = self.start_flow(tenant_id, module)
        self.inject_fault(tenant_id, flow.flow_id, fault_type)
        return self.run_flow(tenant_id, flow.flow_id)

    def audit_log(self, tenant_id: str) -> list[dict]:
        return list(self._require(tenant_id).audit)

    def _require(self, tenant_id: str) -> _Tenant:
        if tenant_id not in self._tenants:
            raise KeyError(f"Unknown FunnelForge tenant: {tenant_id}")
        return self._tenants[tenant_id]

    def _log(self, tenant_id: str, action: str, payload: dict) -> None:
        self._tenants[tenant_id].audit.append(
            {"ts": utcnow().isoformat(), "action": action, "payload": payload}
        )


# Process-wide engine (the dev FunnelForge sandbox).
funnel = FunnelEngine()
