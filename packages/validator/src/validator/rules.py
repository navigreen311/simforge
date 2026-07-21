"""Pack/Scenario validation rules — incl. the PHI regex guard (blueprint §G.3).

No real PHI/PII may enter a Pack: the guard rejects real-looking SSN and DOB patterns
so fixtures stay synthetic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from validator.loader import LoadedPack

# Real SSN (AAA-GG-SSSS) excluding obviously-synthetic 000/666/9xx area numbers is complex;
# for a guard we flag ANY SSN-shaped token — Packs must never contain them.
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
# ISO or US date-of-birth-shaped tokens near a 'dob'/'date of birth' cue.
_DOB_RE = re.compile(r"(?i)\b(dob|date[_ ]of[_ ]birth)\b\s*[:=]?\s*\d{1,4}[-/]\d{1,2}[-/]\d{1,4}")


@dataclass
class ValidationIssue:
    severity: str  # "error" | "warning"
    code: str
    message: str
    location: str = ""


@dataclass
class ValidationResult:
    ok: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]


def _phi_guard(loaded: LoadedPack, issues: list[ValidationIssue]) -> None:
    for scen in loaded.scenarios:
        if _SSN_RE.search(scen.raw_text):
            issues.append(
                ValidationIssue(
                    "error",
                    "phi_ssn",
                    "Scenario contains an SSN-shaped token; fixtures must be synthetic.",
                    scen.yaml_path,
                )
            )
        if _DOB_RE.search(scen.raw_text):
            issues.append(
                ValidationIssue(
                    "error",
                    "phi_dob",
                    "Scenario contains a date-of-birth pattern; fixtures must be synthetic.",
                    scen.yaml_path,
                )
            )


def _referential(loaded: LoadedPack, issues: list[ValidationIssue]) -> None:
    if not loaded.scenarios:
        issues.append(
            ValidationIssue(
                "warning", "no_scenarios", "Pack has no scenarios.", loaded.pack_yaml_path
            )
        )

    seen: set[str] = set()
    for scen in loaded.scenarios:
        sid = scen.spec.scenario_id
        if sid in seen:
            issues.append(
                ValidationIssue(
                    "error", "dup_scenario_id", f"Duplicate scenario_id: {sid}", scen.yaml_path
                )
            )
        seen.add(sid)

    # PHI-required packs should declare at least one compliance flag.
    if loaded.spec.phi_required and not loaded.spec.compliance_flags:
        issues.append(
            ValidationIssue(
                "warning",
                "phi_no_flags",
                "phi_required is true but no compliance_flags are declared.",
                loaded.pack_yaml_path,
            )
        )

    # Readiness gate must define thresholds for the tiers in use.
    tiers_used = {s.spec.tier for s in loaded.scenarios}
    tier_key = {"foundational": "F", "intermediate": "I", "advanced_crisis": "AC"}
    for tier in tiers_used:
        key = tier_key[tier]
        if key not in loaded.spec.readiness_gate.tier_thresholds:
            issues.append(
                ValidationIssue(
                    "error",
                    "missing_threshold",
                    f"tier_thresholds missing key '{key}' for tier '{tier}'.",
                    loaded.pack_yaml_path,
                )
            )


def validate_pack(loaded: LoadedPack) -> ValidationResult:
    issues: list[ValidationIssue] = []
    _phi_guard(loaded, issues)
    _referential(loaded, issues)
    ok = not any(i.severity == "error" for i in issues)
    return ValidationResult(ok=ok, issues=issues)
