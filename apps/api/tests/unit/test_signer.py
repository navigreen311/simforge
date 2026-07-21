"""Unit tests for the Ed25519 StubSigner and snapshot verification."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.services.cert.signer import StubSigner, decode_signature, encode_signature
from src.services.cert.snapshot import CertSnapshotPayload, PinnedVersions


def test_sign_verify_roundtrip(tmp_path: Path) -> None:
    signer = StubSigner(str(tmp_path / "k.pem"))
    payload = b"hello certsnapshot"
    sig = signer.sign(payload)
    assert signer.verify(payload, sig) is True
    assert signer.verify(b"tampered", sig) is False


def test_key_persists_across_instances(tmp_path: Path) -> None:
    p = str(tmp_path / "k.pem")
    a = StubSigner(p)
    b = StubSigner(p)
    assert a.public_key_pem() == b.public_key_pem()
    assert a.key_id() == b.key_id()
    # A signature from one verifies with the other (same key on disk).
    sig = a.sign(b"x")
    assert b.verify(b"x", sig) is True


def test_signature_base64_roundtrip(tmp_path: Path) -> None:
    signer = StubSigner(str(tmp_path / "k.pem"))
    sig = signer.sign(b"data")
    assert decode_signature(encode_signature(sig)) == sig


def test_payload_canonical_is_stable() -> None:
    now = datetime(2026, 7, 21, tzinfo=UTC)
    pv = PinnedVersions(pack="pack.x.v1", scenario_library_hash="abc").as_dict()
    p1 = CertSnapshotPayload(
        "agent_forge_cap",
        "a",
        "foundational",
        now,
        now + timedelta(days=90),
        pv,
        "file://e",
        forge_cap="f.x",
    )
    p2 = CertSnapshotPayload(
        "agent_forge_cap",
        "a",
        "foundational",
        now,
        now + timedelta(days=90),
        pv,
        "file://e",
        forge_cap="f.x",
    )
    assert p1.to_canonical() == p2.to_canonical()
    assert p1.content_hash() == p2.content_hash()
