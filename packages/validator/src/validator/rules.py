"""Pack/Scenario validation rules — the spec §6.3 CI gate (9 rules) + PHI guard (§G.3).

No real PHI/PII may enter a Pack. Beyond that, the §6.3 rules gate coverage, canonical vocab,
fixture resolution, forge-version floor, tier distribution, gate completeness, and the persona ≠
village-agent namespace rule (B9). Corpus-scale rules (coverage / tier distribution / canonical
domains) emit WARNINGS by default and become ERRORS under `strict=True` — an honest seam so the thin
v1 corpus (3 scenarios/pack) validates today and the full gate switches on with the real corpus.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from validator.jurisdiction import coverage_for_flags
from validator.loader import LoadedPack
from validator.scenario_schema import CANONICAL_TRAINING_DOMAINS

# spec §6.3 rule 7: tier distribution floors.
_MIN_FOUNDATIONAL_PCT = 0.50
_MIN_ADVANCED_PCT = 0.10
# spec §6.3 rule 1: minimum scenarios per (role × stage) cell.
_MIN_PER_ROLE_STAGE = 3

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


def _jurisdiction_coverage(loaded: LoadedPack, issues: list[ValidationIssue]) -> None:
    """A pack must declare all compliance flags required by the jurisdictions it operates in.

    Jurisdictions are inferred from the declared flags (e.g. `hcqc_nv` → Nevada); the federal
    baseline (`oig_sam`, `i9`, plus `hipaa` under PHI) always applies. A pack that names a state or
    handles PHI but omits a required flag is under-declared → validation error. A pack with no
    compliance flags at all is left to the `phi_no_flags` warning above (nothing to infer from)."""
    flags = list(loaded.spec.compliance_flags)
    if not flags:
        return
    report = coverage_for_flags(flags, phi_required=loaded.spec.phi_required)
    if not report.satisfied:
        issues.append(
            ValidationIssue(
                "error",
                "jurisdiction_under_declared",
                f"Pack operates in {report.jurisdictions} but is missing required compliance "
                f"flags {report.missing_flags} (declared: {flags}).",
                loaded.pack_yaml_path,
            )
        )


def _sev(strict: bool) -> str:
    """Corpus-scale rules: warning by default, error under strict (full-corpus CI gate)."""
    return "error" if strict else "warning"


def _required_fields_present(loaded: LoadedPack, issues: list[ValidationIssue]) -> None:
    """§6.3 rule 3. Pydantic enforces required fields at load; this names the rule and confirms
    each scenario carries the load-critical fields (a loadable pack always passes)."""
    for scen in loaded.scenarios:
        s = scen.spec
        if not (s.scenario_id and s.title and s.tier and s.tested_agent_village_id and s.cold_open):
            issues.append(
                ValidationIssue(
                    "error",
                    "required_fields_missing",
                    "Scenario missing a required field (id/title/tier/agent/cold_open).",
                    scen.yaml_path,
                )
            )


def _training_domains_canonical(
    loaded: LoadedPack, issues: list[ValidationIssue], strict: bool
) -> None:
    """§6.3 rule 2. Non-canonical training-domain values (warn by default; error under strict)."""
    for scen in loaded.scenarios:
        bad = [d for d in scen.spec.training_domains if d not in CANONICAL_TRAINING_DOMAINS]
        if bad:
            issues.append(
                ValidationIssue(
                    _sev(strict),
                    "training_domains_noncanonical",
                    f"Non-canonical training_domains {bad}; canonical set is "
                    f"{list(CANONICAL_TRAINING_DOMAINS)}.",
                    scen.yaml_path,
                )
            )


def _fixture_refs_resolve(loaded: LoadedPack, issues: list[ValidationIssue]) -> None:
    """§6.3 rule 4. Every persona/doc/property ref a scenario declares must resolve to a fixture
    file under the pack's fixtures/personas dirs. Scenarios that declare no setup are skipped."""
    from pathlib import Path

    pack_dir = Path(loaded.pack_yaml_path).parent
    # Known fixture ids from fixtures/*.yml + personas/*.yml (best-effort text scan).
    fixture_blob = ""
    for sub in ("fixtures", "personas"):
        d = pack_dir / sub
        if d.exists():
            for f in list(d.glob("*.yml")) + list(d.glob("*.yaml")):
                fixture_blob += f.read_text(encoding="utf-8")
    for scen in loaded.scenarios:
        for kind, ref in scen.spec.fixture_refs():
            if ref and ref not in fixture_blob:
                issues.append(
                    ValidationIssue(
                        "error",
                        "fixture_ref_unresolved",
                        f"{kind} ref '{ref}' does not resolve to any pack fixture.",
                        scen.yaml_path,
                    )
                )


def _forge_version_floor(loaded: LoadedPack, issues: list[ValidationIssue], strict: bool) -> None:
    """§6.3 rule 5. A pack's declared forge min_version should be ≥ the deployed sandbox floor.

    Without a live version map (validator is standalone), this validates min_version is well-formed
    and present; the ≥-deployed comparison is enforced at ingestion where the version map exists."""
    for tool in loaded.spec.forge_tools:
        if tool.sandbox_tenant_required and not tool.min_version:
            issues.append(
                ValidationIssue(
                    _sev(strict),
                    "forge_version_floor_missing",
                    f"forge '{tool.forge}' requires a sandbox tenant but declares no min_version.",
                    loaded.pack_yaml_path,
                )
            )


def _tier_distribution(loaded: LoadedPack, issues: list[ValidationIssue], strict: bool) -> None:
    """§6.3 rule 7. ≥50% foundational and ≥10% advanced_crisis across the pack."""
    if not loaded.scenarios:
        return
    total = len(loaded.scenarios)
    counts = {"foundational": 0, "intermediate": 0, "advanced_crisis": 0}
    for s in loaded.scenarios:
        counts[s.spec.tier] = counts.get(s.spec.tier, 0) + 1
    if counts["foundational"] / total < _MIN_FOUNDATIONAL_PCT:
        issues.append(
            ValidationIssue(
                _sev(strict),
                "tier_distribution_foundational",
                f"Foundational tier is {counts['foundational']}/{total} "
                f"(<{int(_MIN_FOUNDATIONAL_PCT * 100)}% required).",
                loaded.pack_yaml_path,
            )
        )
    if counts["advanced_crisis"] / total < _MIN_ADVANCED_PCT:
        issues.append(
            ValidationIssue(
                _sev(strict),
                "tier_distribution_advanced",
                f"Advanced-crisis tier is {counts['advanced_crisis']}/{total} "
                f"(<{int(_MIN_ADVANCED_PCT * 100)}% required).",
                loaded.pack_yaml_path,
            )
        )


def _readiness_gate_complete(loaded: LoadedPack, issues: list[ValidationIssue]) -> None:
    """§6.3 rule 8. All 5 readiness_gate fields must be declared in the pack YAML."""
    from pathlib import Path

    import yaml

    raw = yaml.safe_load(Path(loaded.pack_yaml_path).read_text(encoding="utf-8")) or {}
    rg = raw.get("readiness_gate") or {}
    required = (
        "tier_thresholds",
        "cognitive_aggregate_min",
        "blind_mode_pct",
        "arc_fragmentation_auto_fail",
        "compliance_require_pass",
    )
    missing = [k for k in required if k not in rg]
    if missing:
        issues.append(
            ValidationIssue(
                "error",
                "readiness_gate_incomplete",
                f"readiness_gate is missing fields {missing}.",
                loaded.pack_yaml_path,
            )
        )


def _persona_not_village_agent(loaded: LoadedPack, issues: list[ValidationIssue]) -> None:
    """§6.3 rule 9 / B9. Every persona ref must be namespaced `persona.` (never a village agent id),
    and must not equal the scenario's tested agent id."""
    for scen in loaded.scenarios:
        for ref in scen.spec.persona_refs:
            if ref and not ref.startswith("persona."):
                issues.append(
                    ValidationIssue(
                        "error",
                        "persona_namespace",
                        f"Persona ref '{ref}' is not namespaced 'persona.' (B9).",
                        scen.yaml_path,
                    )
                )
            if ref and ref == scen.spec.tested_agent_village_id:
                issues.append(
                    ValidationIssue(
                        "error",
                        "persona_is_village_agent",
                        f"Persona ref '{ref}' collides with the tested village agent id (B9).",
                        scen.yaml_path,
                    )
                )


def _role_stage_coverage(loaded: LoadedPack, issues: list[ValidationIssue], strict: bool) -> None:
    """§6.3 rule 1. Each (tested_agent × stage) cell needs ≥3 scenarios. When no scenario declares a
    stage, the pack has no stage taxonomy yet → a single advisory warning (not per-cell)."""
    staged = [s for s in loaded.scenarios if s.spec.stage]
    if not staged:
        if loaded.scenarios:
            issues.append(
                ValidationIssue(
                    _sev(strict),
                    "role_stage_taxonomy_absent",
                    "No scenarios declare a `stage`; role×stage coverage cannot be checked.",
                    loaded.pack_yaml_path,
                )
            )
        return
    cells: dict[tuple[str, str], int] = {}
    for s in staged:
        key = (s.spec.tested_agent_village_id, str(s.spec.stage))
        cells[key] = cells.get(key, 0) + 1
    for (agent, stage), n in sorted(cells.items()):
        if n < _MIN_PER_ROLE_STAGE:
            issues.append(
                ValidationIssue(
                    _sev(strict),
                    "role_stage_coverage_low",
                    f"(role={agent} × stage={stage}) has {n} scenarios (<{_MIN_PER_ROLE_STAGE}).",
                    loaded.pack_yaml_path,
                )
            )


def validate_pack(loaded: LoadedPack, strict: bool = False) -> ValidationResult:
    """Run the full §6.3 CI gate. `strict=True` promotes corpus-scale rules to errors (full-corpus
    gate); default keeps them as warnings so the thin v1 corpus validates."""
    issues: list[ValidationIssue] = []
    _phi_guard(loaded, issues)
    _referential(loaded, issues)
    _jurisdiction_coverage(loaded, issues)
    _required_fields_present(loaded, issues)
    _training_domains_canonical(loaded, issues, strict)
    _fixture_refs_resolve(loaded, issues)
    _forge_version_floor(loaded, issues, strict)
    _tier_distribution(loaded, issues, strict)
    _readiness_gate_complete(loaded, issues)
    _persona_not_village_agent(loaded, issues)
    _role_stage_coverage(loaded, issues, strict)
    ok = not any(i.severity == "error" for i in issues)
    return ValidationResult(ok=ok, issues=issues)
