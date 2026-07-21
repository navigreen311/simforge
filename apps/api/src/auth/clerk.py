"""Clerk JWT verification (blueprint §G.1).

Staging/prod set `AUTH_MODE=clerk`; requests carry a Clerk-issued RS256 JWT. This module verifies
the token's signature against Clerk's JWKS, checks `iss`/`exp`/`nbf` (+ optional `aud`), and maps
claims → `Principal` roles. Dev keeps `AUTH_MODE=dev-bypass` (see auth/dev.py).

Key resolution (in priority):
  1. `CLERK_JWKS_JSON` — a static JWKS document (offline/test; no network), or
  2. `CLERK_JWKS_URL` — Clerk's live JWKS endpoint (fetched + cached by PyJWKClient).
"""

from __future__ import annotations

import json

import jwt
from fastapi import HTTPException, status
from jwt import PyJWKClient
from jwt.algorithms import RSAAlgorithm

from src.auth.dev import Principal
from src.auth.roles import roles_from_claims
from src.config import settings

_jwks_client: PyJWKClient | None = None


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise _unauthorized("Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized("Authorization must be a Bearer token")
    return token


def _signing_key(token: str):
    """Resolve the RSA public key that signed this token (static JWKS, else live JWKS URL)."""
    if settings.clerk_jwks_json:
        try:
            kid = jwt.get_unverified_header(token).get("kid")
            jwks = json.loads(settings.clerk_jwks_json)
        except (jwt.InvalidTokenError, json.JSONDecodeError) as exc:
            raise _unauthorized(f"Malformed token or JWKS: {type(exc).__name__}") from exc
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                return RSAAlgorithm.from_jwk(json.dumps(key))
        raise _unauthorized("No matching JWKS key for token kid")

    if settings.clerk_jwks_url:
        global _jwks_client
        if _jwks_client is None:
            _jwks_client = PyJWKClient(settings.clerk_jwks_url)
        try:
            return _jwks_client.get_signing_key_from_jwt(token).key
        except jwt.PyJWKClientError as exc:
            raise _unauthorized(f"JWKS lookup failed: {exc}") from exc

    raise _unauthorized("Clerk not configured (set CLERK_JWKS_URL or CLERK_JWKS_JSON)")


async def verify_clerk_token(authorization: str | None) -> Principal:
    """Verify a Clerk bearer token and resolve its Principal (subject + roles)."""
    token = _bearer_token(authorization)
    key = _signing_key(token)

    options = {"require": ["exp", "iat"], "verify_aud": bool(settings.clerk_audience)}
    decode_kwargs: dict = {"algorithms": ["RS256"], "options": options}
    if settings.clerk_issuer:
        decode_kwargs["issuer"] = settings.clerk_issuer
    if settings.clerk_audience:
        decode_kwargs["audience"] = settings.clerk_audience

    try:
        claims = jwt.decode(token, key=key, **decode_kwargs)
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise _unauthorized(f"Invalid token: {type(exc).__name__}") from exc

    subject = claims.get("sub")
    if not subject:
        raise _unauthorized("Token missing subject (sub)")
    return Principal(subject=subject, roles=roles_from_claims(claims))
