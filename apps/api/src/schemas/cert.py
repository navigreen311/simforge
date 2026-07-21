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


class IssueCertResponse(BaseModel):
    cert: AgentCertOut
    snapshot: CertSnapshotOut
    autonomy_from: str
    autonomy_to: str


class AgentCertList(BaseModel):
    items: list[AgentCertOut]
    total: int


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
