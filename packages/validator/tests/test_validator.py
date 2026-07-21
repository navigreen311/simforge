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


def test_greenstone_pack_loads_and_validates() -> None:
    loaded = load_pack(GREENSTONE)
    assert loaded.spec.pack_id == "pack.greenstone.v1"
    assert len(loaded.scenarios) == 3
    result = validate_pack(loaded)
    assert result.ok, [i.message for i in result.errors]


def test_medlink_pack_is_phi_required_and_valid() -> None:
    loaded = load_pack(MEDLINK)
    assert loaded.spec.phi_required is True
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
