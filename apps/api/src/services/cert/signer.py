"""Signing providers (blueprint §C.12).

- ``stub`` — dev: local Ed25519 that **auto-generates** a keypair on first use (NEVER in prod).
- ``file`` — production Ed25519 that **requires an existing key** (never auto-generates), taken
  from a secret-manager-injected PEM (`SIMFORGE_SIGNING_PRIVATE_KEY_PEM`) or a file path. This is
  the deployable hardening: prod must not silently mint a signing key.
- ``yubihsm`` / ``cloudhsm`` — real HSMs; drop in behind the same `Signer` ABC once the vendor SDK
  + credentials are available (raise until then).
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


class SignerConfigError(Exception):
    """Raised when a production signer is misconfigured (missing key material)."""


class FileEd25519Signer(Signer):
    """Production Ed25519 signer. Loads an EXISTING key (never generates one) from an injected
    PEM secret or a file path — so a misconfigured prod deploy fails loudly instead of silently
    minting an untrusted key."""

    def __init__(self, *, pem: str = "", private_key_path: str = "") -> None:
        self._private = self._load(pem, private_key_path)
        self._public: Ed25519PublicKey = self._private.public_key()

    @staticmethod
    def _load(pem: str, private_key_path: str) -> Ed25519PrivateKey:
        source: bytes | None = None
        if pem.strip():
            source = pem.encode()
        elif private_key_path and Path(private_key_path).exists():
            source = Path(private_key_path).read_bytes()
        if source is None:
            raise SignerConfigError(
                "HSM_PROVIDER=file requires an existing key: set "
                "SIMFORGE_SIGNING_PRIVATE_KEY_PEM or a valid SIMFORGE_SIGNING_PRIVATE_KEY_PATH"
            )
        key = serialization.load_pem_private_key(source, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise SignerConfigError("Signing key must be Ed25519")
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
    """Return the configured signer (cached), dispatched on HSM_PROVIDER."""
    global _signer_singleton
    if _signer_singleton is not None:
        return _signer_singleton

    provider = settings.hsm_provider
    if provider == "stub":
        _signer_singleton = StubSigner(settings.simforge_signing_private_key_path)
    elif provider == "file":
        _signer_singleton = FileEd25519Signer(
            pem=settings.simforge_signing_private_key_pem,
            private_key_path=settings.simforge_signing_private_key_path,
        )
    else:
        # yubihsm / cloudhsm: drop in behind the same Signer ABC with the vendor SDK + creds.
        raise NotImplementedError(f"HSM provider '{provider}' not enabled in this environment")
    return _signer_singleton


def reset_signer_cache() -> None:
    """Clear the cached signer (tests that switch HSM_PROVIDER / key material)."""
    global _signer_singleton
    _signer_singleton = None
