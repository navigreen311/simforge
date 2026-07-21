"""CertSnapshot payload assembly + canonical encoding (blueprint §C.12, §F.2).

The canonical JSON is what gets hashed and signed; verification recomputes it from the
persisted snapshot fields, so `to_canonical` must be stable and deterministic.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _canon_dt(dt: datetime) -> str:
    """Stable UTC-naive ISO encoding so signing (tz-aware) and verify (SQLite tz-naive
    or Postgres tz-aware) produce byte-identical canonical payloads."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt.isoformat()


@dataclass
class CertSnapshotPayload:
    cert_type: str
    subject: str
    tier: str
    issued_at: datetime
    expires_at: datetime
    pinned_versions: dict
    evidence_bundle_ref: str
    forge_cap: str | None = None
    forge_context: str | None = None

    def to_canonical(self) -> str:
        payload = {
            "cert_type": self.cert_type,
            "subject": self.subject,
            "forge_cap": self.forge_cap,
            "forge_context": self.forge_context,
            "tier": self.tier,
            "issued_at": _canon_dt(self.issued_at),
            "expires_at": _canon_dt(self.expires_at),
            "pinned_versions": self.pinned_versions,
            "evidence_bundle_ref": self.evidence_bundle_ref,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def content_hash(self) -> str:
        return hashlib.sha256(self.to_canonical().encode()).hexdigest()


@dataclass
class PinnedVersions:
    """The full version matrix a cert is bound to (blueprint §C.4)."""

    pack: str
    scenario_library_hash: str
    policy_snapshot_id: str = "policy.v1"
    rubric_version: str = "rubric.v1"
    constitution_version: str = "v1.0.0"
    agent_prompt_version: str = "prompt.v1"
    agent_model: str = "stub-llm"
    forge_versions: dict[str, str] = field(default_factory=dict)
    village_os_version: str = "village.dev"
    village_schema_fingerprint: str = ""

    def as_dict(self) -> dict:
        return {
            "pack": self.pack,
            "scenario_library_hash": self.scenario_library_hash,
            "policy_snapshot_id": self.policy_snapshot_id,
            "rubric_version": self.rubric_version,
            "constitution_version": self.constitution_version,
            "agent_prompt_version": self.agent_prompt_version,
            "agent_model": self.agent_model,
            "forge_versions": self.forge_versions,
            "village_os_version": self.village_os_version,
            "village_schema_fingerprint": self.village_schema_fingerprint,
        }
