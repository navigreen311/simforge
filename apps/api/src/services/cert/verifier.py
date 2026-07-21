"""CertSnapshot verification (blueprint §C.3.8).

Recomputes the canonical payload from the persisted snapshot fields, checks the content
hash, and verifies the signature against the signer's public key.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.models.cert import CertSnapshot
from src.services.cert.signer import decode_signature, get_signer
from src.services.cert.snapshot import CertSnapshotPayload


@dataclass
class VerifyResult:
    valid: bool
    key_id: str
    reason: str


def verify_snapshot(snapshot: CertSnapshot) -> VerifyResult:
    payload = CertSnapshotPayload(
        cert_type=snapshot.certType,
        subject=snapshot.subject,
        tier=snapshot.tier,
        issued_at=snapshot.issuedAt,
        expires_at=snapshot.expiresAt,
        pinned_versions=snapshot.pinnedVersions,
        evidence_bundle_ref=snapshot.evidenceBundleRef,
        forge_cap=snapshot.forgeCap,
        forge_context=snapshot.forgeContext,
    )
    canonical = payload.to_canonical().encode()

    if payload.content_hash() != snapshot.contentHash:
        return VerifyResult(False, snapshot.signingKeyId, "content hash mismatch")

    signer = get_signer()
    ok = signer.verify(canonical, decode_signature(snapshot.signature))
    return VerifyResult(ok, snapshot.signingKeyId, "signature valid" if ok else "signature invalid")
