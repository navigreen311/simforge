"""Map Clerk JWT claims → SimForge roles (blueprint §G.1).

Clerk can carry roles in several shapes depending on how the instance is configured; we accept
them in priority order and keep only roles SimForge recognizes:
  1. a top-level ``roles`` claim (list[str] or space/comma-separated str),
  2. ``public_metadata.roles`` (same shapes),
  3. an ``org_role`` claim (Clerk B2B), mapped ``org:admin``/``admin`` → ``admin`` etc.
"""

from __future__ import annotations

from src.auth.dev import ALL_ROLES


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        return [p for p in value.replace(",", " ").split() if p]
    return []


def roles_from_claims(claims: dict) -> frozenset[str]:
    raw: list[str] = []
    raw += _as_list(claims.get("roles"))
    meta = claims.get("public_metadata")
    if isinstance(meta, dict):
        raw += _as_list(meta.get("roles"))
    org_role = claims.get("org_role")
    if isinstance(org_role, str) and org_role:
        raw.append(org_role.split(":", 1)[-1])  # "org:admin" → "admin"

    # Keep only roles SimForge knows about (normalize hyphen/space to underscore).
    recognized = {r.strip().lower().replace("-", "_").replace(" ", "_") for r in raw}
    return frozenset(recognized & ALL_ROLES)
