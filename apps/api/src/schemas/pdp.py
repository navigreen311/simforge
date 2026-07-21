"""PDP request/response schemas (blueprint §F.6)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AuthRequestBody(BaseModel):
    subject_agent_id: str
    action: str  # a Forge capability, e.g. "cre-forge.call_center.outbound"
    resource: str | None = None
    context: dict = Field(default_factory=dict)


class AuthDecisionOut(BaseModel):
    decision: str
    reason_code: str
    reason_detail: str
    ttl_seconds: int
    required_approver: str | None = None
    fail_policy: str


class EffectivePermission(BaseModel):
    action: str
    tier: str
    cert_status: str
    decision: str
    reason_code: str


class EffectivePermissionsOut(BaseModel):
    subject_agent_id: str
    autonomy_level: str
    permissions: list[EffectivePermission]
