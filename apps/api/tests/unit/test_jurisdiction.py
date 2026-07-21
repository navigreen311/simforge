"""Jurisdiction Engine — multi-state requirement resolution + coverage (ADR-0019)."""

from __future__ import annotations

import pytest

from src.services.jurisdiction import (
    coverage_for_flags,
    infer_jurisdictions,
    resolve_requirements,
)
from src.services.jurisdiction.engine import UnknownJurisdictionError


def test_federal_baseline_always_included() -> None:
    # Even with no state, the federal flags are required.
    assert resolve_requirements([], phi_required=False) == ["oig_sam", "i9"]
    assert infer_jurisdictions([]) == ["US-FED"]


def test_nevada_requirements_with_phi() -> None:
    req = resolve_requirements(["US-NV"], phi_required=True)
    assert req == ["oig_sam", "i9", "hipaa", "hcqc_nv"]  # federal first, then PHI, then state


def test_phi_flag_only_required_when_phi() -> None:
    assert "hipaa" not in resolve_requirements(["US-NV"], phi_required=False)
    assert "hipaa" in resolve_requirements(["US-NV"], phi_required=True)


def test_infer_jurisdictions_from_flags() -> None:
    assert infer_jurisdictions(["hcqc_nv", "hipaa"]) == ["US-FED", "US-NV"]
    assert infer_jurisdictions(["cdph_ca"]) == ["US-FED", "US-CA"]


def test_coverage_satisfied() -> None:
    report = coverage_for_flags(["hcqc_nv", "hipaa", "oig_sam", "i9"], phi_required=True)
    assert report.satisfied is True
    assert report.missing_flags == []
    assert set(report.jurisdictions) == {"US-FED", "US-NV"}


def test_coverage_missing_federal_flags() -> None:
    report = coverage_for_flags(["hcqc_nv", "hipaa"], phi_required=True)
    assert report.satisfied is False
    assert set(report.missing_flags) == {"oig_sam", "i9"}


def test_multi_state_explicit_jurisdictions() -> None:
    # A pack operating in both NV and CA must satisfy both states + federal.
    report = coverage_for_flags(
        ["hcqc_nv", "cdph_ca", "hipaa", "oig_sam", "i9"],
        phi_required=True,
        jurisdictions=["US-NV", "US-CA"],
    )
    assert "ccpa" in report.missing_flags  # California privacy still required
    report2 = coverage_for_flags(
        ["hcqc_nv", "cdph_ca", "ccpa", "hipaa", "oig_sam", "i9"],
        phi_required=True,
        jurisdictions=["US-NV", "US-CA"],
    )
    assert report2.satisfied is True


def test_extra_flags_reported_not_penalized() -> None:
    report = coverage_for_flags(["oig_sam", "i9", "honor_do_not_call"], phi_required=False)
    assert report.satisfied is True
    assert "honor_do_not_call" in report.extra_flags


def test_unknown_jurisdiction_raises() -> None:
    with pytest.raises(UnknownJurisdictionError):
        resolve_requirements(["US-ZZ"], phi_required=False)
