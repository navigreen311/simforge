"""Jurisdiction registry + coverage (blueprint §H — Jurisdiction Engine).

The single source of truth for which compliance flags a pack must declare, given the jurisdictions
it operates in. US-FED is the federal baseline that applies everywhere; each state layers its
regulator + required flags on top. Lives in the validator package (not the API) so pack validation
can enforce coverage in CI; the API imports this module so the two never drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Jurisdiction:
    code: str  # e.g. "US-FED", "US-NV"
    name: str
    level: str  # "federal" | "state"
    regulators: tuple[str, ...]
    required_flags: tuple[str, ...]  # flags a pack in this jurisdiction must declare
    phi_flags: tuple[str, ...] = field(default_factory=tuple)  # required only when handling PHI
    # Compliance-evidence metadata (P0-B audit): a matrix without an as-of date is a liability.
    effective_date: str | None = None
    source_citation: str | None = None


_FEDERAL = Jurisdiction(
    code="US-FED",
    name="United States (Federal)",
    level="federal",
    regulators=("OIG", "SAM.gov", "USCIS", "HHS-OCR"),
    # The federal exclusion/eligibility/privacy checks (OIG+SAM, I-9, HIPAA) are healthcare-staffing
    # requirements — gated behind PHI so non-healthcare ventures (e.g. real-estate) aren't forced to
    # declare them. `phi_required=true` is the marker for a healthcare-staffing (PHI) pack.
    required_flags=(),
    phi_flags=("oig_sam", "i9", "hipaa"),
    effective_date="2024-01-01",
    source_citation="42 CFR §1001 (OIG); 8 USC §1324a (I-9); 45 CFR §160 (HIPAA)",
)

_STATES = (
    Jurisdiction(
        "US-NV",
        "Nevada",
        "state",
        ("HCQC",),
        ("hcqc_nv",),
        effective_date="2024-01-01",
        source_citation="NRS 449 (Health Care Facilities)",
    ),
    Jurisdiction(
        "US-CA",
        "California",
        "state",
        ("CDPH", "CPPA"),
        ("cdph_ca", "ccpa"),
        effective_date="2023-01-01",
        source_citation="Cal. Civ. Code §1798.100 (CCPA); H&S §1200",
    ),
    Jurisdiction("US-TX", "Texas", "state", ("HHSC",), ("hhsc_tx",)),
    Jurisdiction("US-FL", "Florida", "state", ("AHCA",), ("ahca_fl",)),
    Jurisdiction("US-AZ", "Arizona", "state", ("ADHS",), ("adhs_az",)),
    Jurisdiction("US-NY", "New York", "state", ("NYSDOH",), ("nysdoh_ny",)),
    # Greenstone Phase-1 target geographies. Real-estate wholesaling is non-PHI, so no required
    # flags — added for coverage visibility; real regulatory reqs are a v2 workstream.
    Jurisdiction("US-UT", "Utah", "state", ("UTREC",), ()),
    Jurisdiction("US-ID", "Idaho", "state", ("IREC",), ()),
)

JURISDICTIONS: dict[str, Jurisdiction] = {j.code: j for j in (_FEDERAL, *_STATES)}
FEDERAL_CODE = _FEDERAL.code

_FLAG_TO_JURISDICTION: dict[str, str] = {}
for _j in JURISDICTIONS.values():
    for _flag in (*_j.required_flags, *_j.phi_flags):
        _FLAG_TO_JURISDICTION.setdefault(_flag, _j.code)


class UnknownJurisdictionError(Exception):
    """Raised when a jurisdiction code is not in the registry."""


def jurisdiction_for_flag(flag: str) -> str | None:
    return _FLAG_TO_JURISDICTION.get(flag)


def _normalize(codes: list[str]) -> list[str]:
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
