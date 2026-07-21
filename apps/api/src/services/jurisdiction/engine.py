"""Jurisdiction Engine — resolve requirements + report coverage (ADR-0019).

Given a set of jurisdiction codes (or a pack's declared compliance flags), compute the required
compliance flags (federal baseline + PHI + each state) and report which are satisfied vs missing.
This generalizes the old NV-only assumption to any mix of states.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.services.jurisdiction.registry import (
    FEDERAL_CODE,
    JURISDICTIONS,
    jurisdiction_for_flag,
)


class UnknownJurisdictionError(Exception):
    """Raised when a jurisdiction code is not in the registry."""


@dataclass
class CoverageReport:
    jurisdictions: list[str]
    phi_required: bool
    required_flags: list[str]
    present_flags: list[str]
    missing_flags: list[str]
    extra_flags: list[str] = field(default_factory=list)

    @property
    def satisfied(self) -> bool:
        return not self.missing_flags

    def as_dict(self) -> dict:
        return {
            "jurisdictions": self.jurisdictions,
            "phi_required": self.phi_required,
            "required_flags": self.required_flags,
            "present_flags": self.present_flags,
            "missing_flags": self.missing_flags,
            "extra_flags": self.extra_flags,
            "satisfied": self.satisfied,
        }


def _normalize(codes: list[str]) -> list[str]:
    """Always include the federal baseline; de-dup; preserve order (federal first)."""
    ordered: list[str] = [FEDERAL_CODE]
    for code in codes:
        code = code.strip().upper()
        if code and code != FEDERAL_CODE and code not in ordered:
            if code not in JURISDICTIONS:
                raise UnknownJurisdictionError(code)
            ordered.append(code)
    return ordered


def resolve_requirements(codes: list[str], *, phi_required: bool) -> list[str]:
    """Full set of required compliance flags for these jurisdictions (federal always included)."""
    required: list[str] = []
    for code in _normalize(codes):
        j = JURISDICTIONS[code]
        for flag in j.required_flags:
            if flag not in required:
                required.append(flag)
        if phi_required:
            for flag in j.phi_flags:
                if flag not in required:
                    required.append(flag)
    return required


def infer_jurisdictions(flags: list[str]) -> list[str]:
    """Reverse-map declared compliance flags → jurisdiction codes (federal always included)."""
    codes: list[str] = [FEDERAL_CODE]
    for flag in flags:
        code = jurisdiction_for_flag(flag)
        if code and code not in codes:
            codes.append(code)
    return codes


def coverage_for_flags(
    declared_flags: list[str], *, phi_required: bool, jurisdictions: list[str] | None = None
) -> CoverageReport:
    """Coverage report. Jurisdictions are inferred from the declared flags unless given."""
    codes = jurisdictions if jurisdictions is not None else infer_jurisdictions(declared_flags)
    codes = _normalize(codes)
    required = resolve_requirements(codes, phi_required=phi_required)
    declared_set = set(declared_flags)
    present = [f for f in required if f in declared_set]
    missing = [f for f in required if f not in declared_set]
    extra = [f for f in declared_flags if f not in required]
    return CoverageReport(
        jurisdictions=codes,
        phi_required=phi_required,
        required_flags=required,
        present_flags=present,
        missing_flags=missing,
        extra_flags=extra,
    )
