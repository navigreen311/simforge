"""Locale registry router — supported languages + rubric-prompt coverage (ADR-0041)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.deps import require_role
from src.services.evaluation.prompts import available_locales

router = APIRouter()

# The judge prompts that carry translations (the localizable rubric surface).
_JUDGE_PROMPTS = ("p7_cx", "c1_breath", "c2_soul")


@router.get("/", dependencies=[Depends(require_role("viewer"))])
async def list_locales() -> dict:
    """Supported locales and which rubric prompts are translated into each."""
    coverage = {name: available_locales(name) for name in _JUDGE_PROMPTS}
    locales = sorted({loc for locs in coverage.values() for loc in locs})
    return {"locales": locales, "default": "en", "prompt_coverage": coverage}
