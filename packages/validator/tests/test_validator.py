"""Tests for the Pack/Scenario validator, including the PHI guard."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from validator import load_pack, validate_pack
from validator.pack_schema import PackSpec

REPO_ROOT = Path(__file__).resolve().parents[3]
GREENSTONE = REPO_ROOT / "packs" / "greenstone" / "v1"
MEDLINK = REPO_ROOT / "packs" / "medlink-pro" / "v1"
CAREGRID = REPO_ROOT / "packs" / "caregrid" / "v1"


def test_greenstone_pack_loads_and_validates() -> None:
    loaded = load_pack(GREENSTONE)
    assert loaded.spec.pack_id == "pack.greenstone.v1"
    # Full-scale corpus (Wave 5): assert the floor + that the golden seed still loads.
    assert len(loaded.scenarios) >= 3
    assert any(s.spec.scenario_id == "scn.gs.src.001" for s in loaded.scenarios)
    result = validate_pack(loaded)
    assert result.ok, [i.message for i in result.errors]


def test_medlink_pack_is_phi_required_and_valid() -> None:
    loaded = load_pack(MEDLINK)
    assert loaded.spec.phi_required is True
    result = validate_pack(loaded)
    assert result.ok, [i.message for i in result.errors]


def test_caregrid_pack_multi_state_ca_validates() -> None:
    loaded = load_pack(CAREGRID)
    assert loaded.spec.owner_venture == "caregrid"
    assert loaded.spec.phi_required is True
    assert "cdph_ca" in loaded.spec.compliance_flags  # California jurisdiction
    assert len(loaded.scenarios) >= 3
    result = validate_pack(loaded)
    assert result.ok, [i.message for i in result.errors]


def test_pack_id_pattern_rejected() -> None:
    with pytest.raises(ValidationError):
        PackSpec.model_validate(
            {
                "pack_id": "not-valid",
                "name": "x",
                "version": "1",
                "owner_venture": "v",
                "owner_human": "h",
                "rubric_profile": "r",
            }
        )


def _min_pack(**overrides: object) -> dict:
    base = {
        "pack_id": "pack.test.v1",
        "name": "x",
        "version": "1",
        "owner_venture": "v",
        "owner_human": "h",
        "rubric_profile": "r",
    }
    base.update(overrides)
    return base


def test_locale_defaults_to_en_and_accepts_supported() -> None:
    assert PackSpec.model_validate(_min_pack()).locale == "en"
    assert PackSpec.model_validate(_min_pack(locale="es")).locale == "es"


def test_unsupported_locale_rejected() -> None:
    with pytest.raises(ValidationError):
        PackSpec.model_validate(_min_pack(locale="fr"))


def test_phi_guard_flags_ssn(tmp_path: Path) -> None:
    pack_dir = tmp_path / "badpack"
    (pack_dir / "scenarios").mkdir(parents=True)
    (pack_dir / "pack.yml").write_text(
        "pack_id: pack.test.v1\nname: T\nversion: '1'\nowner_venture: t\n"
        "owner_human: h\nrubric_profile: r\n",
        encoding="utf-8",
    )
    (pack_dir / "scenarios" / "s.yml").write_text(
        "scenario_id: scn.t.001\ntitle: T\ntier: foundational\n"
        "tested_agent_village_id: a\nslo_seconds: 60\n"
        "cold_open: 'Patient SSN is 123-45-6789 for the record.'\n",
        encoding="utf-8",
    )
    loaded = load_pack(pack_dir)
    result = validate_pack(loaded)
    assert result.ok is False
    assert any(i.code == "phi_ssn" for i in result.errors)


# A spec-complete readiness_gate block (all 5 fields — §6.3 rule readiness_gate_complete).
_FULL_GATE = (
    "readiness_gate:\n  tier_thresholds:\n    F: 0.7\n    I: 0.8\n    AC: 0.85\n"
    "  cognitive_aggregate_min: 0.75\n  blind_mode_pct: 0.25\n"
    "  arc_fragmentation_auto_fail: true\n  compliance_require_pass: true\n"
)


def _write_pack(pack_dir: Path, pack_yaml: str) -> None:
    (pack_dir / "scenarios").mkdir(parents=True)
    (pack_dir / "pack.yml").write_text(pack_yaml, encoding="utf-8")
    (pack_dir / "scenarios" / "s.yml").write_text(
        "scenario_id: scn.t.001\ntitle: T\ntier: foundational\n"
        "tested_agent_village_id: a\nslo_seconds: 60\ncold_open: 'x'\n",
        encoding="utf-8",
    )


def test_jurisdiction_under_declared_phi_pack_flagged(tmp_path: Path) -> None:
    # A PHI (healthcare-staffing) pack in Nevada that omits the required federal flags.
    _write_pack(
        tmp_path / "under",
        "pack_id: pack.test.v1\nname: T\nversion: '1'\nowner_venture: t\nowner_human: h\n"
        "rubric_profile: r\nphi_required: true\ncompliance_flags:\n  - hcqc_nv\n"
        "readiness_gate:\n  tier_thresholds:\n    F: 0.7\n",
    )
    result = validate_pack(load_pack(tmp_path / "under"))
    assert result.ok is False
    issue = next(i for i in result.errors if i.code == "jurisdiction_under_declared")
    assert "oig_sam" in issue.message and "i9" in issue.message and "hipaa" in issue.message


def test_jurisdiction_fully_declared_phi_pack_passes(tmp_path: Path) -> None:
    _write_pack(
        tmp_path / "full",
        "pack_id: pack.test.v1\nname: T\nversion: '1'\nowner_venture: t\nowner_human: h\n"
        "rubric_profile: r\nphi_required: true\ncompliance_flags:\n"
        "  - hcqc_nv\n  - hipaa\n  - oig_sam\n  - i9\n" + _FULL_GATE,
    )
    result = validate_pack(load_pack(tmp_path / "full"))
    assert result.ok, [i.message for i in result.errors]


def test_non_phi_pack_not_forced_to_declare_federal_flags(tmp_path: Path) -> None:
    # A non-healthcare venture (phi false) with venture-specific flags is not under-declared.
    _write_pack(
        tmp_path / "re",
        "pack_id: pack.test.v1\nname: T\nversion: '1'\nowner_venture: t\nowner_human: h\n"
        "rubric_profile: r\nphi_required: false\ncompliance_flags:\n"
        "  - tcpa\n  - state_wholesaling\n" + _FULL_GATE,
    )
    result = validate_pack(load_pack(tmp_path / "re"))
    assert result.ok, [i.message for i in result.errors]


def test_missing_threshold_flagged(tmp_path: Path) -> None:
    pack_dir = tmp_path / "gappack"
    (pack_dir / "scenarios").mkdir(parents=True)
    # readiness gate omits the AC threshold but an advanced_crisis scenario is present
    (pack_dir / "pack.yml").write_text(
        "pack_id: pack.test.v1\nname: T\nversion: '1'\nowner_venture: t\nowner_human: h\n"
        "rubric_profile: r\nreadiness_gate:\n  tier_thresholds:\n    F: 0.7\n",
        encoding="utf-8",
    )
    (pack_dir / "scenarios" / "s.yml").write_text(
        "scenario_id: scn.t.001\ntitle: T\ntier: advanced_crisis\n"
        "tested_agent_village_id: a\nslo_seconds: 60\ncold_open: 'x'\n",
        encoding="utf-8",
    )
    loaded = load_pack(pack_dir)
    result = validate_pack(loaded)
    assert result.ok is False
    assert any(i.code == "missing_threshold" for i in result.errors)


# --- spec §6.3 rules 1–9 (new) ---


def test_full_scenario_schema_parses(tmp_path: Path) -> None:
    """§6.2 fields (setup/complications/expected_outcome/cognitive_expectations/handoff) load."""
    pack_dir = tmp_path / "rich"
    _write_pack(
        pack_dir,
        "pack_id: pack.test.v1\nname: T\nversion: '1'\nowner_venture: t\n"
        "owner_human: h\nrubric_profile: r\n" + _FULL_GATE,
    )
    (pack_dir / "scenarios" / "rich.yml").write_text(
        "scenario_id: scn.t.002\ntitle: Rich\ntier: intermediate\n"
        "tested_agent_village_id: a\nslo_seconds: 120\ncold_open: 'go'\nstage: sourcing\n"
        "setup:\n  personas:\n    - ref: persona.seller.001\n"
        "complications:\n  - id: c1\n    trigger: 'turn >= 2'\n    effect: 'mood := hostile'\n"
        "expected_outcome:\n  state_changes:\n    - 'lead.status == booked'\n"
        "  forbidden_state_changes:\n    - 'contract.sent == true'\n"
        "cognitive_expectations:\n  breath_coherence_min: 0.8\n  arc_no_fragmentation: true\n"
        "handoff_chain:\n  - underwriting\nexpected_escalation: none\n",
        encoding="utf-8",
    )
    loaded = load_pack(pack_dir)
    rich = next(s for s in loaded.scenarios if s.spec.scenario_id == "scn.t.002")
    assert rich.spec.stage == "sourcing"
    assert rich.spec.complications[0].id == "c1"
    assert rich.spec.expected_outcome.forbidden_state_changes == ["contract.sent == true"]
    assert rich.spec.cognitive_expectations.breath_coherence_min == 0.8
    assert rich.spec.persona_refs == ["persona.seller.001"]


def test_persona_namespace_violation_flagged(tmp_path: Path) -> None:
    pack_dir = tmp_path / "persona_bad"
    _write_pack(
        pack_dir,
        "pack_id: pack.test.v1\nname: T\nversion: '1'\nowner_venture: t\n"
        "owner_human: h\nrubric_profile: r\n" + _FULL_GATE,
    )
    (pack_dir / "scenarios" / "s.yml").write_text(
        "scenario_id: scn.t.001\ntitle: T\ntier: foundational\n"
        "tested_agent_village_id: diana_foster\nslo_seconds: 60\ncold_open: 'x'\n"
        "setup:\n  personas:\n    - ref: diana_foster\n",  # not persona.-namespaced + = agent id
        encoding="utf-8",
    )
    result = validate_pack(load_pack(pack_dir))
    assert result.ok is False
    codes = {i.code for i in result.errors}
    assert "persona_namespace" in codes and "persona_is_village_agent" in codes


def test_fixture_ref_unresolved_flagged(tmp_path: Path) -> None:
    pack_dir = tmp_path / "fix_bad"
    _write_pack(
        pack_dir,
        "pack_id: pack.test.v1\nname: T\nversion: '1'\nowner_venture: t\n"
        "owner_human: h\nrubric_profile: r\n" + _FULL_GATE,
    )
    (pack_dir / "scenarios" / "s.yml").write_text(
        "scenario_id: scn.t.001\ntitle: T\ntier: foundational\n"
        "tested_agent_village_id: a\nslo_seconds: 60\ncold_open: 'x'\n"
        "setup:\n  personas:\n    - ref: persona.ghost.999\n",  # no fixtures dir → unresolved
        encoding="utf-8",
    )
    result = validate_pack(load_pack(pack_dir))
    assert any(i.code == "fixture_ref_unresolved" for i in result.errors)


def test_readiness_gate_incomplete_flagged(tmp_path: Path) -> None:
    pack_dir = tmp_path / "gate_bad"
    _write_pack(
        pack_dir,
        "pack_id: pack.test.v1\nname: T\nversion: '1'\nowner_venture: t\nowner_human: h\n"
        "rubric_profile: r\nreadiness_gate:\n  tier_thresholds:\n    F: 0.7\n",  # partial
    )
    result = validate_pack(load_pack(pack_dir))
    assert any(i.code == "readiness_gate_incomplete" for i in result.errors)


def test_corpus_rules_warn_by_default_error_under_strict(tmp_path: Path) -> None:
    """tier distribution + non-canonical domains + no-stage warn by default; error under strict."""
    pack_dir = tmp_path / "thin"
    _write_pack(
        pack_dir,
        "pack_id: pack.test.v1\nname: T\nversion: '1'\nowner_venture: t\n"
        "owner_human: h\nrubric_profile: r\n" + _FULL_GATE,
    )
    (pack_dir / "scenarios" / "s.yml").write_text(
        "scenario_id: scn.t.001\ntitle: T\ntier: intermediate\n"  # 0% foundational
        "tested_agent_village_id: a\nslo_seconds: 60\ncold_open: 'x'\n"
        "training_domains:\n  - not_canonical_domain\n",
        encoding="utf-8",
    )
    loaded = load_pack(pack_dir)
    lenient = validate_pack(loaded, strict=False)
    assert lenient.ok is True
    warn_codes = {i.code for i in lenient.warnings}
    assert "tier_distribution_foundational" in warn_codes
    assert "training_domains_noncanonical" in warn_codes
    assert "role_stage_taxonomy_absent" in warn_codes

    strict = validate_pack(loaded, strict=True)
    assert strict.ok is False
    err_codes = {i.code for i in strict.errors}
    assert "tier_distribution_foundational" in err_codes
    assert "training_domains_noncanonical" in err_codes


def test_forge_version_floor_missing_when_tenant_required(tmp_path: Path) -> None:
    pack_dir = tmp_path / "forge"
    _write_pack(
        pack_dir,
        "pack_id: pack.test.v1\nname: T\nversion: '1'\nowner_venture: t\nowner_human: h\n"
        "rubric_profile: r\nforge_tools:\n  - forge: cre-forge\n    sandbox_tenant_required: true\n"
        + _FULL_GATE,
    )
    strict = validate_pack(load_pack(pack_dir), strict=True)
    assert any(i.code == "forge_version_floor_missing" for i in strict.errors)


def test_real_packs_pass_strict_except_corpus_scale(tmp_path: Path) -> None:
    """The 3 real packs have 0 errors in lenient mode (corpus rules are warnings)."""
    for p in (GREENSTONE, MEDLINK, CAREGRID):
        result = validate_pack(load_pack(p))
        assert result.ok, [i.message for i in result.errors]
