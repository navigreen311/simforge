"""Unit tests for the gap detectors."""

from __future__ import annotations

from types import SimpleNamespace

from src.services.reporter.software_gap import detect_software_gaps, ticket_id
from src.services.reporter.village_os_gap import detect_village_os_gaps


def _scenario(tier: str, caps: list[str]):
    return SimpleNamespace(scenarioId="scn.x.001", tier=tier, testedForgeCaps=caps)


def _run(outcome: str):
    return SimpleNamespace(runId="run-x", outcome=outcome)


def test_ticket_id_is_deterministic() -> None:
    a = ticket_id("SF-GAP", "cre-forge:deals:P1:x")
    b = ticket_id("SF-GAP", "cre-forge:deals:P1:x")
    assert a == b and a.startswith("SF-GAP-")


def test_crisis_scenario_yields_p1_software_gap() -> None:
    gaps = detect_software_gaps(
        _run("resolved"), _scenario("advanced_crisis", ["cre-forge.deals.title"])
    )
    assert len(gaps) == 1
    assert gaps[0].forge == "cre-forge" and gaps[0].severity == "P1"


def test_slo_exceeded_yields_p0_software_gap() -> None:
    gaps = detect_software_gaps(
        _run("slo_exceeded"), _scenario("foundational", ["voiceforge.call_center.outbound"])
    )
    assert gaps and gaps[0].severity == "P0"


def test_clean_foundational_run_has_no_software_gaps() -> None:
    gaps = detect_software_gaps(
        _run("resolved"), _scenario("foundational", ["voiceforge.call_center.outbound"])
    )
    assert gaps == []


def test_unknown_forge_ignored() -> None:
    gaps = detect_software_gaps(_run("errored"), _scenario("foundational", ["mysteryforge.x.y"]))
    assert gaps == []


def _ccb(regret=0.12, balance=0.66, valence=0.62, drift=False) -> dict:
    return {
        "echo": {"regret_load": regret},
        "hfm": {"balance": balance},
        "drift": {"flagged": drift},
        "soul": {"ledger": {"current": {"valence": valence}}},
    }


def test_healthy_agent_has_no_village_os_gaps() -> None:
    assert detect_village_os_gaps("stable", _ccb()) == []


def test_arc_fragmentation_raises_village_os_gap() -> None:
    gaps = detect_village_os_gaps("sudden_shift", _ccb())
    assert any(g.framework == "arc" and g.severity == "P1" for g in gaps)


def test_anomalous_ccb_raises_gaps() -> None:
    gaps = detect_village_os_gaps("stable", _ccb(regret=0.4, balance=0.4, valence=0.3, drift=True))
    frameworks = {g.framework for g in gaps}
    assert {"echo", "hfm", "soul", "drift"} <= frameworks


def test_no_ccb_no_gaps() -> None:
    assert detect_village_os_gaps("stable", None) == []
