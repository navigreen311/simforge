"""Auth dependencies.

Phase 1 ships a dev-bypass that yields a fixed admin principal so every endpoint can
already declare `Depends(require_role(...))`. Clerk JWT verification replaces the bypass
in staging/prod without changing call sites (blueprint §G.1, ADR-0001).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Depends, Header, HTTPException, status

from src.config import settings

# Roles per blueprint §G.1
ALL_ROLES = {
    "admin",
    "founder",
    "pack_owner",
    "compliance_analyst",
    "prompt_engineer",
    "forge_owner",
    "viewer",
    "external_auditor",
}


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: frozenset[str] = field(default_factory=frozenset)

    def has_role(self, role: str) -> bool:
        return role in self.roles or "admin" in self.roles


_DEV_PRINCIPAL = Principal(subject="dev-ivan", roles=frozenset(ALL_ROLES))


async def get_current_principal(
    authorization: str | None = Header(default=None),
) -> Principal:
    """Resolve the caller from AUTH_MODE.

    ``dev-bypass`` (local default) → a fixed full-access principal. ``clerk`` → verify the Clerk
    RS256 JWT from the Authorization header (auth/clerk.py) and map its claims to roles."""
    if settings.auth_mode == "dev-bypass":
        return _DEV_PRINCIPAL
    if settings.auth_mode == "clerk":
        from src.auth.clerk import verify_clerk_token

        return await verify_clerk_token(authorization)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Unknown AUTH_MODE: {settings.auth_mode}",
    )


def require_role(role: str):
    """Dependency factory enforcing a role on an endpoint."""

    async def _dep(principal: Principal = Depends(get_current_principal)) -> Principal:
        if not principal.has_role(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {role}",
            )
        return principal

    return _dep
