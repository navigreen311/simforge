"""Unit tests for the Village reader, CCB composer, and fingerprint."""

from __future__ import annotations

from src.services.village.ccb_composer import FRAMEWORKS, CCBComposer
from src.services.village.reader import VillageReader, VillageReaderError


def test_reader_breath_has_all_components(village_reader: VillageReader) -> None:
    breath = village_reader.get_agent_breath("taylor_zhang")
    assert set(breath.keys()) == {
        "beliefs",
        "rituals",
        "ethics",
        "attachments",
        "traditions",
        "habits",
    }
    assert "beliefs_core" in breath["beliefs"]


def test_reader_frameworks(village_reader: VillageReader) -> None:
    assert village_reader.get_agent_fot("taylor_zhang")["tier"] == "stable"
    assert village_reader.get_agent_arc("gardner")["current_phase"] == "expansion"
    assert village_reader.get_agent_soul("taylor_zhang")["ledger"]["current"]["valence"] == 0.62
    assert village_reader.get_agent_episodes("taylor_zhang")[0]["id"] == "ep_0001"


def test_reader_unknown_agent_raises(village_reader: VillageReader) -> None:
    try:
        village_reader.get_agent_breath("does_not_exist")
    except VillageReaderError:
        return
    raise AssertionError("expected VillageReaderError")


def test_fingerprint_is_deterministic(village_reader: VillageReader) -> None:
    fp1 = village_reader.get_village_schema_fingerprint()
    fp2 = village_reader.get_village_schema_fingerprint()
    assert fp1 == fp2
    assert len(fp1) == 64  # sha256 hex


def test_verify_fingerprint_mismatch(village_reader: VillageReader) -> None:
    from src.services.village.reader import VillageSchemaFingerprintMismatch

    try:
        village_reader.verify_fingerprint("not-the-real-fingerprint")
    except VillageSchemaFingerprintMismatch:
        return
    raise AssertionError("expected fingerprint mismatch")


def test_ccb_composer_completeness_and_determinism(village_reader: VillageReader) -> None:
    composer = CCBComposer(village_reader)
    ccb1 = composer.compose("taylor_zhang", "pre")
    ccb2 = composer.compose("taylor_zhang", "pre")

    # All 10 frameworks present
    assert set(ccb1.frameworks.keys()) == set(FRAMEWORKS)
    # Content hash is deterministic across composes of unchanged state
    assert ccb1.content_hash == ccb2.content_hash
    # But snapshot ids differ (unique per capture)
    assert ccb1.snapshot_id != ccb2.snapshot_id


def test_ccb_content_hash_changes_with_agent(village_reader: VillageReader) -> None:
    composer = CCBComposer(village_reader)
    a = composer.compose("taylor_zhang", "pre")
    b = composer.compose("gardner", "pre")
    assert a.content_hash != b.content_hash
