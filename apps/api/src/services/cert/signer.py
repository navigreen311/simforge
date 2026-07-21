"""Signing providers (blueprint §C.12).

Dev = StubSigner (local Ed25519 — NEVER in prod). Staging = YubiHSM, prod = AWS CloudHSM
(both stubbed as not-enabled here). The signer boundary is a clean ABC so the HSM providers
drop in without touching the issuance flow.
"""

from __future__ import annotations

import base64
import hashlib
from abc import ABC, abstractmethod
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.config import settings


class Signer(ABC):
    @abstractmethod
    def sign(self, payload: bytes) -> bytes: ...

    @abstractmethod
    def verify(self, payload: bytes, signature: bytes) -> bool: ...

    @abstractmethod
    def public_key_pem(self) -> str: ...

    @abstractmethod
    def key_id(self) -> str: ...


class StubSigner(Signer):
    """Local Ed25519 signer for dev. Generates + persists a keypair on first use."""

    def __init__(self, private_key_path: str) -> None:
        self._path = Path(private_key_path)
        self._private = self._load_or_create()
        self._public: Ed25519PublicKey = self._private.public_key()

    def _load_or_create(self) -> Ed25519PrivateKey:
        if self._path.exists():
            return serialization.load_pem_private_key(self._path.read_bytes(), password=None)  # type: ignore[return-value]
        key = Ed25519PrivateKey.generate()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_bytes(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        return key

    def sign(self, payload: bytes) -> bytes:
        return self._private.sign(payload)

    def verify(self, payload: bytes, signature: bytes) -> bool:
        from cryptography.exceptions import InvalidSignature

        try:
            self._public.verify(signature, payload)
            return True
        except InvalidSignature:
            return False

    def public_key_pem(self) -> str:
        return self._public.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    def key_id(self) -> str:
        digest = hashlib.sha256(self.public_key_pem().encode()).hexdigest()[:16]
        return f"{settings.simforge_root_key_id}:{digest}"


def encode_signature(sig: bytes) -> str:
    return base64.b64encode(sig).decode()


def decode_signature(sig_b64: str) -> bytes:
    return base64.b64decode(sig_b64)


_signer_singleton: Signer | None = None


def get_signer() -> Signer:
    """Return the configured signer. Dev = StubSigner (cached)."""
    global _signer_singleton
    provider = settings.hsm_provider
    if provider != "stub":
        # WEEK 9: YubiHsmSigner / AwsCloudHsmSigner.
        raise NotImplementedError(f"HSM provider '{provider}' not enabled in this environment")
    if _signer_singleton is None:
        _signer_singleton = StubSigner(settings.simforge_signing_private_key_path)
    return _signer_singleton
