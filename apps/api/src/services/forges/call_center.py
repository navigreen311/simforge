"""Deterministic in-process Call Center engine (blueprint §E.2 VoiceForge).

Places synthetic calls against a persona catalog, controls line quality, injects call faults,
and "handles" a call — surfacing any injected fault (a dropped call, dead air, a misroute, a
missing compliance disclosure, …). No telephony, no randomness. This is the VoiceForge sandbox
for dev/CI; a real VoiceForge sits behind the same adapter over a WebSocket/HTTP surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.services.forges.base import Fault, FaultType, SandboxTenant
from src.utils.time import utcnow

# Persona catalog (blueprint §E.2 preload).
PERSONAS = (
    "angry_don",
    "confused_clinician",
    "hostile_seller",
    "eager_buyer",
    "skeptical_broker",
    "wholesaler_competitor",
    "lender_underwriter",
    "facility_admin",
    "dol_auditor",
    "hcqc_inspector",
    "patient_family",
    "fraud_attempting_applicant",
)

# Call fault → severity (line-quality + call-flow + compliance; critical faults block).
_FAULT_SEVERITY = {
    FaultType.DROPPED_CALL: "P0",
    FaultType.ESCALATION_FAILURE: "P0",
    FaultType.DISCLOSURE_MISSING: "P0",
    FaultType.DEAD_AIR: "P1",
    FaultType.LINE_NOISE: "P1",
    FaultType.MISROUTE: "P1",
    FaultType.HOLD_TIMEOUT: "P1",
}


@dataclass
class _Call:
    call_id: str
    direction: str
    persona: str
    fault: Fault | None = None


@dataclass
class _Tenant:
    tenant: SandboxTenant
    calls: dict[str, _Call] = field(default_factory=dict)
    audit: list[dict] = field(default_factory=list)


class CallCenterEngine:
    def __init__(self) -> None:
        self._tenants: dict[str, _Tenant] = {}
        self._seq = 0

    def _next_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}_{self._seq:06d}"

    def provision(self, run_id: str) -> SandboxTenant:
        tid = self._next_id("vf_tenant")
        tenant = SandboxTenant(
            tenant_id=tid, forge="voiceforge", run_id=run_id, created_at=utcnow()
        )
        self._tenants[tid] = _Tenant(tenant=tenant)
        self._log(tid, "provision", {"run_id": run_id})
        return tenant

    def teardown(self, tenant_id: str) -> None:
        self._tenants.pop(tenant_id, None)

    def place_call(self, tenant_id: str, direction: str, persona: str | None = None) -> _Call:
        t = self._require(tenant_id)
        call = _Call(
            call_id=self._next_id("vf_call"),
            direction=direction if direction in ("inbound", "outbound") else "inbound",
            persona=persona if persona in PERSONAS else "facility_admin",
        )
        t.calls[call.call_id] = call
        self._log(
            tenant_id,
            "place_call",
            {"call_id": call.call_id, "direction": call.direction, "persona": call.persona},
        )
        return call

    def inject_fault(self, tenant_id: str, call_id: str, fault_type: str) -> None:
        t = self._require(tenant_id)
        call = t.calls[call_id]
        sev = _FAULT_SEVERITY.get(fault_type, "P1")
        call.fault = Fault(fault_type, sev, f"{fault_type} on {call.direction} call", "call_center")
        self._log(tenant_id, "inject_fault", {"call_id": call_id, "type": fault_type})

    def handle_call(self, tenant_id: str, call_id: str) -> dict:
        """Handle the call; surface any injected fault (the 'detection')."""
        t = self._require(tenant_id)
        call = t.calls[call_id]
        result: dict[str, object] = {
            "call_id": call_id,
            "direction": call.direction,
            "persona": call.persona,
            "outcome": "handled",
        }
        if call.fault is not None:
            result["outcome"] = "fault_detected"
            result["fault"] = {
                "type": call.fault.fault_type,
                "severity": call.fault.severity,
                "detail": call.fault.detail,
                "module": call.fault.module,
            }
        self._log(tenant_id, "handle_call", {"call_id": call_id, "outcome": result["outcome"]})
        return result

    def inject_fault_on_call(
        self, tenant_id: str, direction: str, fault_type: str, persona: str | None = None
    ) -> dict:
        """Convenience: place a call, inject a fault, handle it."""
        call = self.place_call(tenant_id, direction, persona)
        self.inject_fault(tenant_id, call.call_id, fault_type)
        return self.handle_call(tenant_id, call.call_id)

    def prosody_score(self, tenant_id: str) -> dict:
        # Call-quality score (deterministic placeholder; real VoiceForge scores live audio).
        return {"prosody_score": 0.79, "notes": "synthetic"}

    def audit_log(self, tenant_id: str) -> list[dict]:
        return list(self._require(tenant_id).audit)

    def _require(self, tenant_id: str) -> _Tenant:
        if tenant_id not in self._tenants:
            raise KeyError(f"Unknown VoiceForge tenant: {tenant_id}")
        return self._tenants[tenant_id]

    def _log(self, tenant_id: str, action: str, payload: dict) -> None:
        self._tenants[tenant_id].audit.append(
            {"ts": utcnow().isoformat(), "action": action, "payload": payload}
        )


# Process-wide engine (the dev VoiceForge sandbox).
call_center = CallCenterEngine()
