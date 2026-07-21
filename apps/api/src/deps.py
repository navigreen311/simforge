"""Shared FastAPI dependencies (DI)."""

from __future__ import annotations

from fastapi import HTTPException, status

from src.auth.dev import Principal, get_current_principal, require_role
from src.db import get_session
from src.services.village.reader import VillageReader, VillageReaderError

__all__ = [
    "get_session",
    "get_current_principal",
    "require_role",
    "Principal",
    "get_village_reader",
]


def get_village_reader() -> VillageReader:
    """Provide a read-only Village reader, or 503 if VILLAGE_DATA_PATH is unavailable."""
    try:
        return VillageReader.from_settings()
    except VillageReaderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Village data unavailable: {exc}",
        ) from exc
