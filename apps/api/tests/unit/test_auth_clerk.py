"""Real Clerk JWT verification, hermetic — self-issued RS256 token + generated JWKS (no network)."""

from __future__ import annotations

import json

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from jwt.algorithms import RSAAlgorithm

from src.auth.clerk import verify_clerk_token
from src.auth.roles import roles_from_claims
from src.config import settings

_KID = "test-kid-1"
_ISSUER = "https://clerk.test.example"


@pytest.fixture
def clerk_key(monkeypatch: pytest.MonkeyPatch):
    """Generate an RSA keypair, publish its JWK, and configure Clerk to trust it."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(RSAAlgorithm.to_jwk(private.public_key()))
    jwk["kid"] = _KID
    monkeypatch.setattr(settings, "clerk_jwks_json", json.dumps({"keys": [jwk]}))
    monkeypatch.setattr(settings, "clerk_jwks_url", "")
    monkeypatch.setattr(settings, "clerk_issuer", _ISSUER)
    monkeypatch.setattr(settings, "clerk_audience", "")
    return private


def _token(private, claims: dict) -> str:
    base = {"sub": "user_123", "iss": _ISSUER, "iat": 1_600_000_000, "exp": 4_100_000_000}
    return jwt.encode({**base, **claims}, private, algorithm="RS256", headers={"kid": _KID})


async def test_valid_token_resolves_principal_with_roles(clerk_key) -> None:
    token = _token(clerk_key, {"roles": ["admin", "viewer"]})
    principal = await verify_clerk_token(f"Bearer {token}")
    assert principal.subject == "user_123"
    assert principal.has_role("admin") and principal.has_role("viewer")


async def test_expired_token_rejected(clerk_key) -> None:
    token = _token(clerk_key, {"exp": 1_600_000_100, "roles": ["viewer"]})
    with pytest.raises(HTTPException) as ei:
        await verify_clerk_token(f"Bearer {token}")
    assert ei.value.status_code == 401 and "expired" in ei.value.detail.lower()


async def test_wrong_issuer_rejected(clerk_key) -> None:
    token = _token(clerk_key, {"iss": "https://evil.example", "roles": ["admin"]})
    with pytest.raises(HTTPException) as ei:
        await verify_clerk_token(f"Bearer {token}")
    assert ei.value.status_code == 401


async def test_signature_from_unknown_key_rejected(clerk_key) -> None:
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _token(other, {"roles": ["admin"]})  # signed by a key not in the JWKS
    with pytest.raises(HTTPException) as ei:
        await verify_clerk_token(f"Bearer {token}")
    assert ei.value.status_code == 401


async def test_missing_and_malformed_authorization_rejected(clerk_key) -> None:
    for header in (None, "", "Token abc", "Bearer "):
        with pytest.raises(HTTPException) as ei:
            await verify_clerk_token(header)
        assert ei.value.status_code == 401


def test_roles_from_claims_shapes() -> None:
    # list, space-separated string, public_metadata, and org_role all map; unknown roles dropped.
    assert roles_from_claims({"roles": ["admin", "not_a_role"]}) == frozenset({"admin"})
    assert roles_from_claims({"roles": "viewer forge_owner"}) == frozenset(
        {"viewer", "forge_owner"}
    )
    assert roles_from_claims({"public_metadata": {"roles": ["compliance_analyst"]}}) == frozenset(
        {"compliance_analyst"}
    )
    assert roles_from_claims({"org_role": "org:admin"}) == frozenset({"admin"})
    assert roles_from_claims({}) == frozenset()
