"""Production FileEd25519Signer — key from an injected PEM, no auto-generation."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.config import settings
from src.services.cert.signer import (
    FileEd25519Signer,
    SignerConfigError,
    get_signer,
    reset_signer_cache,
)


def _pem() -> str:
    return (
        Ed25519PrivateKey.generate()
        .private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        .decode()
    )


def test_file_signer_signs_and_verifies_from_injected_pem() -> None:
    signer = FileEd25519Signer(pem=_pem())
    sig = signer.sign(b"hello")
    assert signer.verify(b"hello", sig) is True
    assert signer.verify(b"tampered", sig) is False
    assert "BEGIN PUBLIC KEY" in signer.public_key_pem()
    assert signer.key_id().startswith(settings.simforge_root_key_id)


def test_file_signer_requires_existing_key() -> None:
    # No PEM and a non-existent path → loud failure, never a silently-generated key.
    with pytest.raises(SignerConfigError):
        FileEd25519Signer(pem="", private_key_path="/does/not/exist.pem")


def test_get_signer_dispatches_to_file_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "hsm_provider", "file")
    monkeypatch.setattr(settings, "simforge_signing_private_key_pem", _pem())
    reset_signer_cache()
    try:
        signer = get_signer()
        assert isinstance(signer, FileEd25519Signer)
        # A real end-to-end sign/verify round-trip through the configured provider.
        sig = signer.sign(b"payload")
        assert signer.verify(b"payload", sig) is True
    finally:
        reset_signer_cache()


def test_unknown_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "hsm_provider", "cloudhsm")
    reset_signer_cache()
    try:
        with pytest.raises(NotImplementedError):
            get_signer()
    finally:
        reset_signer_cache()
