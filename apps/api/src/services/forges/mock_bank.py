"""Deterministic in-process Mock Bank engine (blueprint §E.7 CapitalForge).

No external service, no randomness — outcomes derive from inputs + injected faults. This is
the CapitalForge sandbox for dev/CI. A real CapitalForge sandbox would sit behind the same
adapter over HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.services.forges.base import Fault, FaultType, SandboxTenant
from src.utils.time import utcnow

_OPENING_BALANCE = 250_000.0
_VELOCITY_THRESHOLD = 3  # wires within a tenant before the velocity signal trips


@dataclass
class _Tenant:
    tenant: SandboxTenant
    balance: float = _OPENING_BALANCE
    faults: dict[str, Fault] = field(default_factory=dict)  # fault_type -> Fault
    audit: list[dict] = field(default_factory=list)
    ledger: list[dict] = field(default_factory=list)  # running transaction history
    wire_count: int = 0  # velocity signal


class MockBankEngine:
    def __init__(self) -> None:
        self._tenants: dict[str, _Tenant] = {}
        self._seq = 0

    def _next_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}_{self._seq:06d}"

    # -- lifecycle --------------------------------------------------------

    def provision(self, run_id: str) -> SandboxTenant:
        tid = self._next_id("cf_tenant")
        tenant = SandboxTenant(
            tenant_id=tid, forge="capitalforge", run_id=run_id, created_at=utcnow()
        )
        self._tenants[tid] = _Tenant(tenant=tenant)
        self._log(tid, "provision", {"run_id": run_id})
        return tenant

    def teardown(self, tenant_id: str) -> None:
        self._tenants.pop(tenant_id, None)

    def seed_state(self, tenant_id: str, fixtures: dict) -> None:
        t = self._require(tenant_id)
        if "balance" in fixtures:
            t.balance = float(fixtures["balance"])
        t.tenant.state.update(fixtures)
        self._log(tenant_id, "seed_state", fixtures)

    def inject_fault(self, tenant_id: str, fault: Fault) -> None:
        t = self._require(tenant_id)
        t.faults[fault.fault_type] = fault
        self._log(tenant_id, "inject_fault", {"type": fault.fault_type, "severity": fault.severity})

    def audit_log(self, tenant_id: str) -> list[dict]:
        return list(self._require(tenant_id).audit)

    # -- bank operations --------------------------------------------------

    def apply(self, tenant_id: str, amount: float, applicant: str = "buyer") -> dict:
        t = self._require(tenant_id)
        for kind in (FaultType.OFAC, FaultType.FRAUD_FLAG, FaultType.DECLINATION):
            if kind in t.faults:
                return self._result(
                    tenant_id, "apply", "declined", amount, reason=kind, fault=t.faults[kind]
                )
        return self._result(
            tenant_id,
            "apply",
            "approved",
            amount,
            reference=self._next_id("cf_app"),
            decision=self._decision(amount, t.balance),
        )

    def wire(self, tenant_id: str, amount: float, to: str = "escrow") -> dict:
        t = self._require(tenant_id)
        if FaultType.OFAC in t.faults:
            return self._result(
                tenant_id, "wire", "blocked", amount, reason="ofac", fault=t.faults[FaultType.OFAC]
            )
        if FaultType.NSF in t.faults or amount > t.balance:
            return self._result(
                tenant_id, "wire", "failed", amount, reason="nsf", fault=t.faults.get(FaultType.NSF)
            )
        if FaultType.VELOCITY in t.faults:
            return self._result(
                tenant_id,
                "wire",
                "held",
                amount,
                reason="velocity",
                fault=t.faults[FaultType.VELOCITY],
            )
        t.balance -= amount
        t.wire_count += 1
        return self._result(tenant_id, "wire", "sent", amount, reference=self._next_id("cf_wire"))

    def emd_release(self, tenant_id: str, amount: float) -> dict:
        t = self._require(tenant_id)
        if FaultType.FRAUD_FLAG in t.faults:
            return self._result(
                tenant_id,
                "emd_release",
                "held",
                amount,
                reason="fraud_flag",
                fault=t.faults[FaultType.FRAUD_FLAG],
            )
        return self._result(
            tenant_id, "emd_release", "released", amount, reference=self._next_id("cf_emd")
        )

    def account(self, tenant_id: str) -> dict:
        t = self._require(tenant_id)
        return {
            "tenant_id": tenant_id,
            "balance": t.balance,
            "opening_balance": _OPENING_BALANCE,
            "wire_count": t.wire_count,
            "active_faults": list(t.faults),
            "ledger_entries": len(t.ledger),
        }

    def ledger(self, tenant_id: str) -> list[dict]:
        return list(self._require(tenant_id).ledger)

    def world_state(self, tenant_id: str) -> dict:
        """Rich domain snapshot: balance movement, the full ledger, and velocity."""
        t = self._require(tenant_id)
        settled = sum(e["amount"] for e in t.ledger if e["op"] == "wire" and e["outcome"] == "sent")
        return {
            "balance": t.balance,
            "opening_balance": _OPENING_BALANCE,
            "settled_out": settled,
            "wire_count": t.wire_count,
            "velocity_flag": t.wire_count >= _VELOCITY_THRESHOLD,
            "active_faults": list(t.faults),
            "ledger": t.ledger,
        }

    # -- helpers ----------------------------------------------------------

    def _decision(self, amount: float, balance: float) -> dict:
        """A deterministic credit-decision tier so approvals carry a reason, not just 'yes'."""
        if amount <= 50_000:
            return {"tier": "auto_approve", "reason": "within auto-approval limit"}
        if amount <= balance:
            return {"tier": "standard", "reason": "covered by available balance"}
        return {"tier": "manual_review", "reason": "exceeds available balance — review advised"}

    def _require(self, tenant_id: str) -> _Tenant:
        if tenant_id not in self._tenants:
            raise KeyError(f"Unknown Mock Bank tenant: {tenant_id}")
        return self._tenants[tenant_id]

    def _log(self, tenant_id: str, action: str, payload: dict) -> None:
        self._tenants[tenant_id].audit.append(
            {"ts": utcnow().isoformat(), "action": action, "payload": payload}
        )

    def _result(
        self,
        tenant_id,
        op,
        outcome,
        amount,
        *,
        reason=None,
        reference=None,
        fault: Fault | None = None,
        decision: dict | None = None,
    ) -> dict:
        res = {
            "op": op,
            "outcome": outcome,
            "amount": amount,
            "reason": reason,
            "reference": reference,
        }
        if decision is not None:
            res["decision"] = decision
        self._log(tenant_id, op, {"outcome": outcome, "amount": amount, "reason": reason})
        t = self._tenants[tenant_id]
        t.ledger.append(
            {
                "seq": len(t.ledger) + 1,
                "op": op,
                "outcome": outcome,
                "amount": amount,
                "reason": reason,
                "reference": reference,
                "balance_after": t.balance,
                "ts": utcnow().isoformat(),
            }
        )
        if fault is not None:
            res["fault"] = {
                "type": fault.fault_type,
                "severity": fault.severity,
                "detail": fault.detail,
                "module": fault.module,
            }
        return res


# Process-wide engine (the dev CapitalForge sandbox).
mock_bank = MockBankEngine()
