"""Jurisdiction Engine — multi-state + federal compliance requirements (ADR-0019)."""

from src.services.jurisdiction.engine import (
    CoverageReport,
    coverage_for_flags,
    infer_jurisdictions,
    resolve_requirements,
)
from src.services.jurisdiction.registry import JURISDICTIONS, Jurisdiction

__all__ = [
    "JURISDICTIONS",
    "Jurisdiction",
    "CoverageReport",
    "coverage_for_flags",
    "infer_jurisdictions",
    "resolve_requirements",
]
