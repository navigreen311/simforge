"""HSM-backed Ed25519 signers (blueprint §C.12 — staging YubiHSM, prod AWS CloudHSM; ADR-0022).

The private key never leaves the HSM: signing happens on-device, and SimForge only ever holds the
public key. All HSMs share one backend-agnostic signer (`HsmEd25519Signer`) — the concrete backends
are thin wrappers over each vendor SDK, lazily imported so the SDK is only required when that
provider is actually selected. The shared signer logic is fully unit-tested with a fake backend; the
vendor connection code activates the moment the SDK + a reachable HSM + credentials are present.
"""

from __future__ import annotations

import hashlib
from typing import Protocol, runtime_checkable

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from src.config import settings
from src.services.cert.signer import Signer, SignerConfigError


@runtime_checkable
class HsmBackend(Protocol):
    """The minimal on-device interface every HSM backend provides."""

    def sign(self, payload: bytes) -> bytes: ...

    def public_key_der(self) -> bytes:
        """The Ed25519 public key as SubjectPublicKeyInfo DER."""
        ...


class HsmEd25519Signer(Signer):
    """Signer whose private key lives in an HSM; only `sign` crosses the device boundary.

    Backend-agnostic — YubiHSM, PKCS#11/CloudHSM, or a test fake all satisfy `HsmBackend`."""

    def __init__(self, backend: HsmBackend, *, label: str = "hsm") -> None:
        self._backend = backend
        self._label = label
        self._public: Ed25519PublicKey | None = None

    def _public_key(self) -> Ed25519PublicKey:
        if self._public is None:
            key = serialization.load_der_public_key(self._backend.public_key_der())
            if not isinstance(key, Ed25519PublicKey):
                raise SignerConfigError("HSM signing key must be Ed25519")
            self._public = key
        return self._public

    def sign(self, payload: bytes) -> bytes:
        return self._backend.sign(payload)

    def verify(self, payload: bytes, signature: bytes) -> bool:
        from cryptography.exceptions import InvalidSignature

        try:
            self._public_key().verify(signature, payload)
            return True
        except InvalidSignature:
            return False

    def public_key_pem(self) -> str:
        return (
            self._public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )

    def key_id(self) -> str:
        digest = hashlib.sha256(self.public_key_pem().encode()).hexdigest()[:16]
        return f"{settings.simforge_root_key_id}:{self._label}:{digest}"


# --- concrete vendor backends (lazy SDK import; raise a clear error when unavailable) --------


class _YubiHsmBackend:
    """YubiHSM 2 backend via the `yubihsm` SDK. The key is an on-device Ed25519 asymmetric key."""

    def __init__(self) -> None:
        try:
            from yubihsm import YubiHsm  # type: ignore[import-untyped]
            from yubihsm.defs import OBJECT  # type: ignore[import-untyped]
        except ImportError as exc:
            raise SignerConfigError(
                "HSM_PROVIDER=yubihsm requires the 'yubihsm' SDK (pip install 'yubihsm[http]')"
            ) from exc
        if not (settings.yubihsm_connector_url and settings.yubihsm_signing_key_id):
            raise SignerConfigError(
                "YubiHSM needs YUBIHSM_CONNECTOR_URL + YUBIHSM_SIGNING_KEY_ID (+ auth key/password)"
            )
        hsm = YubiHsm.connect(settings.yubihsm_connector_url)
        session = hsm.create_session_derived(
            settings.yubihsm_auth_key_id, settings.yubihsm_password
        )
        self._key = session.get_object(settings.yubihsm_signing_key_id, OBJECT.ASYMMETRIC_KEY)

    def sign(self, payload: bytes) -> bytes:
        return self._key.sign_eddsa(payload)

    def public_key_der(self) -> bytes:
        pub = self._key.get_public_key()  # a cryptography Ed25519PublicKey
        return pub.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )


class _Pkcs11Backend:
    """AWS CloudHSM (or any PKCS#11 HSM) backend via the `pkcs11` SDK + the vendor .so library."""

    def __init__(self) -> None:
        try:
            import pkcs11  # type: ignore[import-untyped]
        except ImportError as exc:
            raise SignerConfigError(
                "HSM_PROVIDER=cloudhsm requires the 'pkcs11' SDK (pip install python-pkcs11)"
            ) from exc
        if not (
            settings.pkcs11_lib_path and settings.pkcs11_token_label and settings.pkcs11_key_label
        ):
            raise SignerConfigError(
                "CloudHSM needs PKCS11_LIB_PATH + PKCS11_TOKEN_LABEL + PKCS11_KEY_LABEL (+ PIN)"
            )
        lib = pkcs11.lib(settings.pkcs11_lib_path)
        token = lib.get_token(token_label=settings.pkcs11_token_label)
        self._session = token.open(user_pin=settings.pkcs11_pin)
        self._priv = self._session.get_key(
            label=settings.pkcs11_key_label, object_class=pkcs11.ObjectClass.PRIVATE_KEY
        )
        self._pub = self._session.get_key(
            label=settings.pkcs11_key_label, object_class=pkcs11.ObjectClass.PUBLIC_KEY
        )
        self._mechanism = pkcs11.Mechanism.EDDSA

    def sign(self, payload: bytes) -> bytes:
        return bytes(self._priv.sign(payload, mechanism=self._mechanism))

    def public_key_der(self) -> bytes:
        # PKCS#11 exposes the raw 32-byte Ed25519 public point; wrap it as SubjectPublicKeyInfo.
        import pkcs11  # already importable at this point

        raw = bytes(self._pub[pkcs11.Attribute.EC_POINT])
        return Ed25519PublicKey.from_public_bytes(raw).public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )


def build_yubihsm_signer() -> HsmEd25519Signer:
    return HsmEd25519Signer(_YubiHsmBackend(), label="yubihsm")


def build_cloudhsm_signer() -> HsmEd25519Signer:
    return HsmEd25519Signer(_Pkcs11Backend(), label="cloudhsm")
