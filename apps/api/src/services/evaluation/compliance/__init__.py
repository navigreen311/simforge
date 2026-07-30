"""Deterministic compliance rules engine — the real P2 (§5.1 P2, §9.1)."""

from src.services.evaluation.compliance.engine import (
    ComplianceReport,
    ComplianceResult,
    evaluate_compliance,
)
from src.services.evaluation.compliance.rules import RULES, ComplianceRule

__all__ = [
    "evaluate_compliance",
    "ComplianceReport",
    "ComplianceResult",
    "ComplianceRule",
    "RULES",
]
