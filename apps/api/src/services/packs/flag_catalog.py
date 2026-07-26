"""Plain-language labels for pack compliance flags (Part A: make chips self-explaining).

Deterministic catalog — no LLM, no storage — mirroring the gaps fault-catalog and capability-label
pattern: a governance console needs identical, auditable text every time. Every flag that can appear
on a pack chip gets a plain tooltip; unknown flags fall back to a readable humanized label so a chip
is never unexplained.

The compliance flags map to the Jurisdiction engine where the engine knows them
(`jurisdiction_for_flag`), so the labels here stay consistent with what jurisdictions require.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.services.jurisdiction.registry import jurisdiction_for_flag


@dataclass(frozen=True)
class FlagInfo:
    label: str
    tooltip: str
    phi: bool = False  # a PHI/health-privacy flag → rendered red


# Keyed by the raw flag string stored on Pack.complianceFlags.
FLAG_CATALOG: dict[str, FlagInfo] = {
    "hipaa": FlagInfo(
        "HIPAA",
        "HIPAA — the U.S. health-privacy law governing Protected Health Information.",
        phi=True,
    ),
    "oig_sam": FlagInfo(
        "OIG / SAM",
        "OIG exclusion + SAM.gov check — confirms the person or entity isn't federally barred "
        "from healthcare or government contracting.",
    ),
    "i9": FlagInfo(
        "I-9",
        "Form I-9 — verifies the worker is legally eligible for employment in the U.S.",
    ),
    "hcqc_nv": FlagInfo(
        "HCQC (NV)",
        "Nevada Health Care Quality & Compliance — state licensing and oversight for Nevada "
        "health-care work.",
        phi=True,
    ),
    "cdph_ca": FlagInfo(
        "CDPH (CA)",
        "California Department of Public Health — state health-care oversight in California.",
        phi=True,
    ),
    "ccpa": FlagInfo(
        "CCPA",
        "California Consumer Privacy Act — California's consumer data-privacy rules.",
    ),
    "hhsc_tx": FlagInfo(
        "HHSC (TX)",
        "Texas Health & Human Services Commission — state health-care oversight in Texas.",
        phi=True,
    ),
    "ahca_fl": FlagInfo(
        "AHCA (FL)",
        "Florida Agency for Health Care Administration — state health-care oversight in Florida.",
        phi=True,
    ),
    "adhs_az": FlagInfo(
        "ADHS (AZ)",
        "Arizona Department of Health Services — state health-care oversight in Arizona.",
        phi=True,
    ),
    "nysdoh_ny": FlagInfo(
        "NYSDOH (NY)",
        "New York State Department of Health — state health-care oversight in New York.",
        phi=True,
    ),
    "tcpa": FlagInfo(
        "TCPA",
        "Telephone Consumer Protection Act — federal rules governing calls and texts to consumers.",
    ),
    "state_wholesaling": FlagInfo(
        "State wholesaling",
        "State real-estate wholesaling rules — disclosure and licensing for assigning purchase "
        "contracts.",
    ),
}

# Legend copy for the non-flag chips shown on a pack card (venture / PHI / execution mode).
LEGEND = {
    "venture": "The venture this Pack certifies agents for.",
    "phi": "This Pack involves Protected Health Information — HIPAA and health-privacy rules apply.",  # noqa: E501
    "sandbox": "Scenarios run against mock Forge APIs — no real systems are touched.",
    "integrated": "Scenarios may execute against real, write-enabled systems (integrated mode).",
    "signed": "An owner has ratified this Pack version.",
    "golden": "A golden benchmark scenario — its expected result is pinned for regression testing.",
}


def _humanize(flag: str) -> str:
    return flag.replace("_", " ").replace("-", " ").title()


def describe_flag(flag: str) -> dict:
    """Return {label, tooltip, phi, jurisdiction} for a flag, with a readable fallback."""
    info = FLAG_CATALOG.get(flag)
    jur = jurisdiction_for_flag(flag)
    if info is None:
        return {
            "label": _humanize(flag),
            "tooltip": f"Compliance flag '{flag}'. No plain-language description is on file yet.",
            "phi": False,
            "jurisdiction": jur,
        }
    return {"label": info.label, "tooltip": info.tooltip, "phi": info.phi, "jurisdiction": jur}
