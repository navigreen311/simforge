"""CCB schemas (blueprint §C.7)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CCBResponse(BaseModel):
    snapshot_id: str
    agent_village_id: str
    phase: str
    taken_at: datetime
    content_hash: str
    village_schema_fingerprint: str
    frameworks: dict[str, object]


class CCBCaptureRequest(BaseModel):
    phase: str = "pre"
