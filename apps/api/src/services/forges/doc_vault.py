"""Deterministic in-process Doc Vault engine (blueprint §E.3 VisionAudioForge).

Generates synthetic documents, injects document faults, and "OCR-extracts" fields — surfacing
any injected fault (a forged signature, expired/revoked license, OIG match, …). No external
service, no randomness. This is the VAF sandbox for dev/CI; a real VAF sits behind the same
adapter over HTTP. Fixtures are synthetic only — never real PHI.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.services.forges.base import Fault, FaultType, SandboxTenant
from src.utils.time import utcnow

DOC_TYPES = (
    "nursing_license",
    "cna_cert",
    "i9",
    "w4",
    "drug_screen",
    "background_check",
    "hipaa_attestation",
    "offer_letter",
    "title_report",
    "proof_of_funds",
)

# Doc fault → severity (blueprint §E.3 fault menu; critical faults block).
_FAULT_SEVERITY = {
    FaultType.FORGED_SIGNATURE: "P0",
    FaultType.REVOKED_LICENSE: "P0",
    FaultType.OIG_MATCH: "P0",
    FaultType.EXPIRED_DATE: "P1",
    FaultType.NAME_DOB_MISMATCH: "P1",
    FaultType.ALTERED_AMOUNT: "P1",
    FaultType.MISSING_PAGES: "P2",
}


@dataclass
class _Doc:
    doc_id: str
    doc_type: str
    fields: dict
    fault: Fault | None = None


@dataclass
class _Tenant:
    tenant: SandboxTenant
    docs: dict[str, _Doc] = field(default_factory=dict)
    audit: list[dict] = field(default_factory=list)


class DocVaultEngine:
    def __init__(self) -> None:
        self._tenants: dict[str, _Tenant] = {}
        self._seq = 0

    def _next_id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}_{self._seq:06d}"

    def provision(self, run_id: str) -> SandboxTenant:
        tid = self._next_id("vaf_tenant")
        tenant = SandboxTenant(tenant_id=tid, forge="vaf", run_id=run_id, created_at=utcnow())
        self._tenants[tid] = _Tenant(tenant=tenant)
        self._log(tid, "provision", {"run_id": run_id})
        return tenant

    def teardown(self, tenant_id: str) -> None:
        self._tenants.pop(tenant_id, None)

    def generate_doc(self, tenant_id: str, doc_type: str) -> _Doc:
        t = self._require(tenant_id)
        doc = _Doc(
            doc_id=self._next_id("vaf_doc"),
            doc_type=doc_type if doc_type in DOC_TYPES else "generic",
            fields={"name": "SYNTHETIC PERSON", "issued": "2025-01-01", "state": "NV"},
        )
        t.docs[doc.doc_id] = doc
        self._log(tenant_id, "generate_doc", {"doc_id": doc.doc_id, "type": doc.doc_type})
        return doc

    def inject_fault(self, tenant_id: str, doc_id: str, fault_type: str) -> None:
        t = self._require(tenant_id)
        doc = t.docs[doc_id]
        sev = _FAULT_SEVERITY.get(fault_type, "P1")
        doc.fault = Fault(fault_type, sev, f"{fault_type} on {doc.doc_type}", doc.doc_type)
        self._log(tenant_id, "inject_fault", {"doc_id": doc_id, "type": fault_type})

    def ocr_extract(self, tenant_id: str, doc_id: str) -> dict:
        """Extract fields; surface any injected fault (the 'detection')."""
        t = self._require(tenant_id)
        doc = t.docs[doc_id]
        result = {
            "doc_id": doc_id,
            "doc_type": doc.doc_type,
            "fields": doc.fields,
            "outcome": "clean",
        }
        if doc.fault is not None:
            result["outcome"] = "fault_detected"
            result["fault"] = {
                "type": doc.fault.fault_type,
                "severity": doc.fault.severity,
                "detail": doc.fault.detail,
                "module": doc.fault.module,
            }
        self._log(tenant_id, "ocr_extract", {"doc_id": doc_id, "outcome": result["outcome"]})
        return result

    def prosody_score(self, tenant_id: str) -> dict:
        # Call-quality score (deterministic placeholder; real VAF scores audio).
        return {"prosody_score": 0.82, "notes": "synthetic"}

    def inject_fault_on_generated(self, tenant_id: str, doc_type: str, fault_type: str) -> dict:
        """Convenience: generate a doc, inject a fault, OCR-extract it."""
        doc = self.generate_doc(tenant_id, doc_type)
        self.inject_fault(tenant_id, doc.doc_id, fault_type)
        return self.ocr_extract(tenant_id, doc.doc_id)

    def audit_log(self, tenant_id: str) -> list[dict]:
        return list(self._require(tenant_id).audit)

    def _require(self, tenant_id: str) -> _Tenant:
        if tenant_id not in self._tenants:
            raise KeyError(f"Unknown VAF tenant: {tenant_id}")
        return self._tenants[tenant_id]

    def _log(self, tenant_id: str, action: str, payload: dict) -> None:
        self._tenants[tenant_id].audit.append(
            {"ts": utcnow().isoformat(), "action": action, "payload": payload}
        )


# Process-wide engine (the dev VAF sandbox).
doc_vault = DocVaultEngine()
