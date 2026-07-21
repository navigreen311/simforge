"""HSM-backed Ed25519 signer — shared logic (fake backend) + provider dispatch/guards.

Real YubiHSM/CloudHSM hardware isn't available here, so the vendor connection code can't run; the
backend-agnostic signer logic that every HSM shares IS fully exercised via a fake backend, and the
`get_signer` dispatch + "SDK not installed" guards are tested for both providers.
"""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key

from src.config import settings
from src.services.cert.hsm_signer import HsmEd25519Signer
from src.services.cert.signer import SignerConfigError, get_signer, reset_signer_cache


class _FakeHsmBackend:
    """An in-process stand-in for an HSM: signs on-'device' with a local Ed25519 key."""

    def __init__(self, key: Ed25519PrivateKey | None = None) -> None:
        self._key = key or Ed25519PrivateKey.generate()

    def sign(self, payload: bytes) -> bytes:
        return self._key.sign(payload)

    def public_key_der(self) -> bytes:
        return self._key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )


class _RsaBackend:
    """A backend holding a non-Ed25519 key — the signer must reject it."""

    def __init__(self) -> None:
        self._key = generate_private_key(public_exponent=65537, key_size=2048)

    def sign(self, payload: bytes) -> bytes:  # pragma: no cover - never reached
        return b""

    def public_key_der(self) -> bytes:
        return self._key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )


def test_hsm_signer_sign_verify_round_trip() -> None:
    signer = HsmEd25519Signer(_FakeHsmBackend(), label="test")
    sig = signer.sign(b"cert-payload")
    assert signer.verify(b"cert-payload", sig) is True
    assert signer.verify(b"tampered", sig) is False


def test_hsm_signer_public_key_and_key_id() -> None:
    signer = HsmEd25519Signer(_FakeHsmBackend(), label="yubihsm")
    assert "BEGIN PUBLIC KEY" in signer.public_key_pem()
    kid = signer.key_id()
    assert kid.startswith(settings.simforge_root_key_id) and ":yubihsm:" in kid


def test_hsm_signer_verify_matches_cryptography() -> None:
    key = Ed25519PrivateKey.generate()
    signer = HsmEd25519Signer(_FakeHsmBackend(key), label="t")
    sig = signer.sign(b"data")
    # An independent public-key verify agrees with the signer.
    pub: Ed25519PublicKey = key.public_key()
    pub.verify(sig, b"data")  # raises if invalid


def test_hsm_signer_rejects_non_ed25519_key() -> None:
    signer = HsmEd25519Signer(_RsaBackend(), label="t")
    with pytest.raises(SignerConfigError):
        signer.public_key_pem()


@pytest.mark.parametrize(("provider", "sdk_hint"), [("yubihsm", "yubihsm"), ("cloudhsm", "pkcs11")])
def test_get_signer_hsm_provider_without_sdk_raises_clear_error(
    provider: str, sdk_hint: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The vendor SDKs aren't installed here → a clear SignerConfigError, not a crash.
    monkeypatch.setattr(settings, "hsm_provider", provider)
    reset_signer_cache()
    try:
        with pytest.raises(SignerConfigError) as ei:
            get_signer()
        assert sdk_hint in str(ei.value).lower()
    finally:
        reset_signer_cache()
