"""Health/readiness response schemas (blueprint §C.3.1)."""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    checks: dict[str, str]


class FingerprintResponse(BaseModel):
    fingerprint: str
    captured_at: str | None
    drift_detected: bool
