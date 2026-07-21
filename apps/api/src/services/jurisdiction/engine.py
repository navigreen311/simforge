"""Jurisdiction Engine — re-exported from the validator package (single source of truth).

The engine (requirement resolution + coverage) lives in `validator.jurisdiction` so pack validation
and the API share one implementation (blueprint §H; ADR-0019).
"""

from __future__ import annotations

from validator.jurisdiction import (
    CoverageReport,
    UnknownJurisdictionError,
    coverage_for_flags,
    infer_jurisdictions,
    resolve_requirements,
)

__all__ = [
    "CoverageReport",
    "UnknownJurisdictionError",
    "coverage_for_flags",
    "infer_jurisdictions",
    "resolve_requirements",
]
