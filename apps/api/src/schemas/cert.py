"""Certification schemas (blueprint §C.4, §C.3.7/8/14)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IssueAgentCertRequest(BaseModel):
    agent_village_id: str
    forge_cap: str
    tier: str
    battery_run_ids: list[str] = Field(..., min_length=1)
    approver_id: str
    pack_id: str


class RevokeCertRequest(BaseModel):
    reason: str


class ReinstateCertRequest(BaseModel):
    battery_run_ids: list[str] = Field(..., min_length=1)
    approver_id: str


class CertSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    snapshotId: str
    certType: str
    subject: str
    forgeCap: str | None = None
    tier: str
    issuedAt: datetime
    expiresAt: datetime
    pinnedVersions: dict
    evidenceBundleRef: str
    signingKeyId: str
    signature: str
    contentHash: str


class AgentCertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agentId: str
    forgeCap: str
    tier: str
    status: str
    issuedAt: datetime
    expiresAt: datetime
    revokedAt: datetime | None = None
    revocationReason: str | None = None
    certSnapshotId: str
    # Derived (presentation only) from the capability catalog — the same source of truth the
    # Readiness Matrix uses. Not stored; computed per response.
    capabilityLabel: str = ""
    capabilityForge: str = ""
    capabilityDescription: str = ""


class IssueCertResponse(BaseModel):
    cert: AgentCertOut
    snapshot: CertSnapshotOut
    autonomy_from: str
    autonomy_to: str


class AgentCertList(BaseModel):
    items: list[AgentCertOut]
    total: int


class IssueDeptCertRequest(BaseModel):
    department_key: str
    forge_context: str
    tier: str = "intermediate"
    dept_battery_run_ids: list[str]
    approver_id: str
    pack_id: str
    required_forge_caps: list[str] = []
    prerequisite_min: int | None = None


class DeptCertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    departmentId: str
    forgeContext: str
    tier: str
    status: str
    issuedAt: datetime
    expiresAt: datetime
    revokedAt: datetime | None = None
    revocationReason: str | None = None
    certSnapshotId: str
    prerequisiteAgentCertIds: list[str] = []
    departmentKey: str = ""  # derived (presentation)


class DeptCertList(BaseModel):
    items: list[DeptCertOut]
    total: int


class IssueDeptCertResponse(BaseModel):
    cert: DeptCertOut
    snapshot: CertSnapshotOut


class DeptPrereqStatusOut(BaseModel):
    department_key: str
    required_min: int
    required_forge_caps: list[str]
    covering_agents: list[str]
    covering_count: int
    satisfied: bool


class VerifyResponse(BaseModel):
    snapshot_id: str
    valid: bool
    key_id: str
    reason: str


class AttestResponse(BaseModel):
    cert_id: str
    subject: str
    forge_cap: str
    tier: str
    status: str
    expires_at: datetime
    snapshot_id: str
    signature_valid: bool


class PublicKeyOut(BaseModel):
    key_id: str
    public_key_pem: str


class PublicKeysResponse(BaseModel):
    keys: list[PublicKeyOut]
    crl: list[str]
