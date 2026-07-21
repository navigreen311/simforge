"""Shared FastAPI dependencies (DI)."""

from __future__ import annotations

from src.auth.dev import Principal, get_current_principal, require_role
from src.db import get_session

__all__ = ["get_session", "get_current_principal", "require_role", "Principal"]
