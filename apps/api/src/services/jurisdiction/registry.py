"""Jurisdiction registry (blueprint §H — Jurisdiction Engine; v1 was NV-only).

A jurisdiction is a compliance authority whose rules a venture must satisfy. US-FED is the federal
baseline that applies everywhere; each state layers its own regulator + required compliance flags on
top. Packs declare compliance flags (`hcqc_nv`, `hipaa`, …); the engine (engine.py) maps those to
jurisdictions and reports coverage gaps. Extending to a new state = one entry here.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Jurisdiction:
    code: str  # e.g. "US-FED", "US-NV"
    name: str
    level: str  # "federal" | "state"
    regulators: tuple[str, ...]
    required_flags: tuple[str, ...]  # compliance flags a pack in this jurisdiction must declare
    phi_flags: tuple[str, ...] = field(default_factory=tuple)  # required only when PHI is handled


# Federal baseline — applies to every pack regardless of state.
_FEDERAL = Jurisdiction(
    code="US-FED",
    name="United States (Federal)",
    level="federal",
    regulators=("OIG", "SAM.gov", "USCIS", "HHS-OCR"),
    required_flags=("oig_sam", "i9"),
    phi_flags=("hipaa",),  # HIPAA required when the pack handles PHI
)

# States (healthcare-staffing regulators + any state privacy regime). Add a state by adding a row.
_STATES = (
    Jurisdiction("US-NV", "Nevada", "state", ("HCQC",), ("hcqc_nv",)),
    Jurisdiction("US-CA", "California", "state", ("CDPH", "CPPA"), ("cdph_ca", "ccpa")),
    Jurisdiction("US-TX", "Texas", "state", ("HHSC",), ("hhsc_tx",)),
    Jurisdiction("US-FL", "Florida", "state", ("AHCA",), ("ahca_fl",)),
    Jurisdiction("US-AZ", "Arizona", "state", ("ADHS",), ("adhs_az",)),
    Jurisdiction("US-NY", "New York", "state", ("NYSDOH",), ("nysdoh_ny",)),
)

JURISDICTIONS: dict[str, Jurisdiction] = {j.code: j for j in (_FEDERAL, *_STATES)}
FEDERAL_CODE = _FEDERAL.code

# Reverse index: a required flag → the jurisdiction that requires it (for inference from flags).
_FLAG_TO_JURISDICTION: dict[str, str] = {}
for _j in JURISDICTIONS.values():
    for _flag in (*_j.required_flags, *_j.phi_flags):
        _FLAG_TO_JURISDICTION.setdefault(_flag, _j.code)


def jurisdiction_for_flag(flag: str) -> str | None:
    return _FLAG_TO_JURISDICTION.get(flag)
