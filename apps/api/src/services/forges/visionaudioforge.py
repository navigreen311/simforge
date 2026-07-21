"""VisionAudioForge (VAF) adapter (blueprint §E.3) — Local (in-process Doc Vault) implementation.

Default dev/CI adapter. A real VAF sandbox drops in as an HTTP-backed adapter behind the same
`ForgeAdapter` contract (settings.forge_vaf_sandbox_url).
"""

from __future__ import annotations

from datetime import datetime

from src.services.forges.base import Fault, ForgeAdapter, SandboxTenant
from src.services.forges.doc_vault import DocVaultEngine, doc_vault


class LocalVAFAdapter(ForgeAdapter):
    forge_name = "vaf"

    def __init__(self, engine: DocVaultEngine | None = None) -> None:
        self.engine = engine or doc_vault

    async def health_check(self) -> dict:
        return {
            "forge": "vaf",
            "ok": True,
            "mode": "local",
            "version": await self.get_current_version(),
        }

    async def provision_sandbox_tenant(self, run_id: str) -> SandboxTenant:
        return self.engine.provision(run_id)

    async def teardown_sandbox_tenant(self, tenant_id: str) -> None:
        self.engine.teardown(tenant_id)

    async def seed_state(self, tenant_id: str, fixtures: dict) -> None:
        for doc_type in fixtures.get("doc_types", []):
            self.engine.generate_doc(tenant_id, doc_type)

    async def get_audit_log(self, tenant_id: str, since: datetime | None = None) -> list[dict]:
        log = self.engine.audit_log(tenant_id)
        if since is not None:
            log = [e for e in log if e["ts"] >= since.isoformat()]
        return log

    async def get_current_version(self) -> str:
        return "vaf.docvault.v1"

    async def inject_fault(self, tenant_id: str, fault: Fault) -> None:
        # Generate a doc of the fault's module (doc_type) and inject onto it, then it can be OCR'd.
        doc = self.engine.generate_doc(tenant_id, fault.module)
        self.engine.inject_fault(tenant_id, doc.doc_id, fault.fault_type)

    # -- doc operations (used by the mock world) --------------------------

    async def generate_and_extract(
        self, tenant_id: str, doc_type: str, fault_type: str | None = None
    ) -> dict:
        if fault_type:
            return self.engine.inject_fault_on_generated(tenant_id, doc_type, fault_type)
        doc = self.engine.generate_doc(tenant_id, doc_type)
        return self.engine.ocr_extract(tenant_id, doc.doc_id)

    async def prosody_score(self, tenant_id: str) -> dict:
        return self.engine.prosody_score(tenant_id)
