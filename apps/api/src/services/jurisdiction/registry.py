"""Jurisdiction registry — re-exported from the validator package (single source of truth).

The registry lives in `validator.jurisdiction` so pack validation can enforce coverage in CI; the
API re-exports it here so the two never drift (blueprint §H; ADR-0019).
"""

from __future__ import annotations

from validator.jurisdiction import (
    FEDERAL_CODE,
    JURISDICTIONS,
    Jurisdiction,
    jurisdiction_for_flag,
)

__all__ = ["FEDERAL_CODE", "JURISDICTIONS", "Jurisdiction", "jurisdiction_for_flag"]
