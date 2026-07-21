"""Tests for the deterministic Doc Vault engine (VisionAudioForge sandbox)."""

from __future__ import annotations

import pytest

from src.services.forges.base import FaultType
from src.services.forges.doc_vault import DocVaultEngine


def _engine() -> DocVaultEngine:
    return DocVaultEngine()


def test_generate_and_extract_clean() -> None:
    e = _engine()
    t = e.provision("run-1")
    doc = e.generate_doc(t.tenant_id, "nursing_license")
    res = e.ocr_extract(t.tenant_id, doc.doc_id)
    assert res["outcome"] == "clean" and "fault" not in res
    # synthetic only — never real PHI
    assert res["fields"]["name"] == "SYNTHETIC PERSON"


def test_unknown_doc_type_falls_back_generic() -> None:
    e = _engine()
    t = e.provision("run-1")
    doc = e.generate_doc(t.tenant_id, "not_a_real_type")
    assert doc.doc_type == "generic"


@pytest.mark.parametrize(
    ("fault_type", "severity"),
    [
        (FaultType.FORGED_SIGNATURE, "P0"),
        (FaultType.REVOKED_LICENSE, "P0"),
        (FaultType.OIG_MATCH, "P0"),
        (FaultType.EXPIRED_DATE, "P1"),
        (FaultType.NAME_DOB_MISMATCH, "P1"),
        (FaultType.ALTERED_AMOUNT, "P1"),
        (FaultType.MISSING_PAGES, "P2"),
    ],
)
def test_injected_fault_surfaces_with_severity(fault_type: str, severity: str) -> None:
    e = _engine()
    t = e.provision("run-1")
    res = e.inject_fault_on_generated(t.tenant_id, "nursing_license", fault_type)
    assert res["outcome"] == "fault_detected"
    assert res["fault"]["type"] == fault_type
    assert res["fault"]["severity"] == severity


def test_prosody_score_deterministic() -> None:
    e = _engine()
    t = e.provision("run-1")
    assert e.prosody_score(t.tenant_id)["prosody_score"] == 0.82


def test_audit_log_and_teardown() -> None:
    e = _engine()
    t = e.provision("run-1")
    e.generate_doc(t.tenant_id, "i9")
    assert len(e.audit_log(t.tenant_id)) >= 2  # provision + generate_doc
    e.teardown(t.tenant_id)
    with pytest.raises(KeyError):
        e.audit_log(t.tenant_id)
