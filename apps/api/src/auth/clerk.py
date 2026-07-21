"""Clerk JWT verification seam (blueprint §G.1).

Staging/prod set `AUTH_MODE=clerk`; requests carry a Clerk-issued JWT. This module is the
integration point — it verifies the token against Clerk's JWKS and maps claims → Principal.
Dev keeps `AUTH_MODE=dev-bypass` (see auth/dev.py), so this raises until real keys are wired.
"""

from __future__ import annotations

from src.auth.dev import Principal
from src.config import settings


async def verify_clerk_token(authorization: str | None) -> Principal:
    """Verify a Clerk bearer token and resolve roles.

    WEEK 9 (staging): fetch Clerk JWKS (cached), verify RS256 signature + `iss`/`exp`,
    read the `org_role` / `public_metadata.roles` claim, and build the Principal.
    """
    if not settings.clerk_secret_key or not authorization:
        raise NotImplementedError("Clerk verification requires CLERK_SECRET_KEY + Authorization")
    raise NotImplementedError("Live Clerk JWT verification not enabled in this environment")
