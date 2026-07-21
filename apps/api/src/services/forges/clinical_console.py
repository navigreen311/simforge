"""Deterministic in-process Clinical Console engine (blueprint §E.4 medlink-pro).

Seeds a PHI-**synthetic** healthcare-staffing tenant (scheduler / compliance / clinician state),
injects UI + staffing faults, and "runs" a console task — surfacing any injected fault (an
unflagged expired credential, a double-booked shift, PHI over-exposure, a blocking UI modal, …).
No external service, no randomness, and **never real PHI**. This is the medlink-pro sandbox for
dev/CI; a real medlink-pro sits behind the same adapter over HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.services.forges.base import Fault, FaultType, SandboxTenant
from src.utils.time import utcnow

MODULES = ("scheduler", "compliance", "clinician")

# Console fault → severity (blueprint §E.4; compliance/safety faults are critical).
_FAULT_SEVERITY = {
    FaultType.CREDENTIAL_EXPIRED_UNFLAGGED: "P0",
    FaultType.SHIFT_DOUBLE_BOOKED: "P0",
    FaultType.PHI_OVEREXPOSURE: "P0",
    FaultType.UI_BLOCKING_MODAL: "P1",
    FaultType.STALE_ROSTER: "P1",
    FaultType.TIMECARD_MISSING: "P1",
    FaultType.MSA_TERMS_STALE: "P1",
}


@dataclass
class _Task:
    task_id: str
    module: str
    fields: dict
    fault: Fault | None = None


@dataclass
class _Tenant:
    tenant: SandboxTenant
    seed_params: dict = field(default_factory=dict)
    tasks: dict[str, _Task] = field(default_factory=dict)
    audit: list[dict] = field(default_factory=list)


class ClinicalConsoleEngine:
    def __init__(self) -> None:
        self._tenants: dict[str, _Tenant] = {}
        self._seq = 0

    def _next_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}_{self._seq:06d}"

    def provision(self, run_id: str) -> SandboxTenant:
        tid = self._next_id("mlp_tenant")
        tenant = SandboxTenant(
            tenant_id=tid, forge="medlink-pro", run_id=run_id, created_at=utcnow()
        )
        self._tenants[tid] = _Tenant(tenant=tenant)
        self._log(tid, "provision", {"run_id": run_id})
        return tenant

    def teardown(self, tenant_id: str) -> None:
        self._tenants.pop(tenant_id, None)

    def seed_state(self, tenant_id: str, params: dict) -> None:
        """Seed scheduler/compliance/clinician state (creds expiring, timecards, shifts, …)."""
        t = self._require(tenant_id)
        t.seed_params.update(params)
        self._log(tenant_id, "seed_state", {"keys": sorted(params.keys())})

    def start_task(self, tenant_id: str, module: str) -> _Task:
        t = self._require(tenant_id)
        task = _Task(
            task_id=self._next_id("mlp_task"),
            module=module if module in MODULES else "scheduler",
            fields={"clinician": "SYNTHETIC CLINICIAN", "facility": "SYNTHETIC FACILITY"},
        )
        t.tasks[task.task_id] = task
        self._log(tenant_id, "start_task", {"task_id": task.task_id, "module": task.module})
        return task

    def inject_fault(self, tenant_id: str, task_id: str, fault_type: str) -> None:
        t = self._require(tenant_id)
        task = t.tasks[task_id]
        sev = _FAULT_SEVERITY.get(fault_type, "P1")
        task.fault = Fault(fault_type, sev, f"{fault_type} in {task.module}", task.module)
        self._log(tenant_id, "inject_fault", {"task_id": task_id, "type": fault_type})

    def run_task(self, tenant_id: str, task_id: str) -> dict:
        """Run the console task; surface any injected fault (the 'detection')."""
        t = self._require(tenant_id)
        task = t.tasks[task_id]
        result: dict[str, object] = {
            "task_id": task_id,
            "module": task.module,
            "fields": task.fields,
            "outcome": "ok",
        }
        if task.fault is not None:
            result["outcome"] = "fault_detected"
            result["fault"] = {
                "type": task.fault.fault_type,
                "severity": task.fault.severity,
                "detail": task.fault.detail,
                "module": task.fault.module,
            }
        self._log(tenant_id, "run_task", {"task_id": task_id, "outcome": result["outcome"]})
        return result

    def inject_fault_on_task(self, tenant_id: str, module: str, fault_type: str) -> dict:
        """Convenience: start a task, inject a fault, run it."""
        task = self.start_task(tenant_id, module)
        self.inject_fault(tenant_id, task.task_id, fault_type)
        return self.run_task(tenant_id, task.task_id)

    def audit_log(self, tenant_id: str) -> list[dict]:
        return list(self._require(tenant_id).audit)

    def _require(self, tenant_id: str) -> _Tenant:
        if tenant_id not in self._tenants:
            raise KeyError(f"Unknown medlink-pro tenant: {tenant_id}")
        return self._tenants[tenant_id]

    def _log(self, tenant_id: str, action: str, payload: dict) -> None:
        self._tenants[tenant_id].audit.append(
            {"ts": utcnow().isoformat(), "action": action, "payload": payload}
        )


# Process-wide engine (the dev medlink-pro sandbox).
clinical_console = ClinicalConsoleEngine()
