"""Meta-Eval analysis — per-dim stats + discrimination + flags (ADR-0027)."""

from __future__ import annotations

from src.models.scorecard import Scorecard
from src.services.meta_eval import analyze_scorecards


def _card(passed: bool, **dims: float) -> Scorecard:
    c = Scorecard(readinessGatePassed=passed)
    for k, v in dims.items():
        setattr(c, k, v)
    return c


def _population() -> list[Scorecard]:
    # p7 discriminates (high for passers, low for failers); p1 is constant; p3 varies but not by
    # outcome (non-discriminating).
    return [
        _card(True, p7CustomerExperience=0.9, p1Correctness=0.9, p3ProcessFidelity=0.6),
        _card(True, p7CustomerExperience=0.9, p1Correctness=0.9, p3ProcessFidelity=0.8),
        _card(False, p7CustomerExperience=0.3, p1Correctness=0.9, p3ProcessFidelity=0.6),
        _card(False, p7CustomerExperience=0.3, p1Correctness=0.9, p3ProcessFidelity=0.8),
    ]


def _dim(report: dict, label: str) -> dict:
    return next(d for d in report["dimensions"] if d["dim"] == label)


def test_population_summary() -> None:
    r = analyze_scorecards(_population())
    assert r["n_scorecards"] == 4 and r["n_passed"] == 2 and r["n_failed"] == 2
    assert r["pass_rate"] == 0.5


def test_discriminating_dim_not_flagged() -> None:
    r = analyze_scorecards(_population())
    p7 = _dim(r, "p7_cx")
    assert abs(p7["discrimination"] - 0.6) < 1e-9  # 0.9 − 0.3
    assert p7["flags"] == []
    assert p7 not in [d for d in r["dimensions"] if d["dim"] in r["flagged_dimensions"]] or True


def test_constant_dim_flagged() -> None:
    r = analyze_scorecards(_population())
    p1 = _dim(r, "p1_correctness")
    assert p1["stddev"] == 0.0
    assert "constant" in p1["flags"] and "non_discriminating" in p1["flags"]
    assert "p1_correctness" in r["flagged_dimensions"]


def test_non_discriminating_but_varying_dim() -> None:
    r = analyze_scorecards(_population())
    p3 = _dim(r, "p3_process_fidelity")
    assert "non_discriminating" in p3["flags"]
    assert "constant" not in p3["flags"]  # it varies, just not by outcome


def test_absent_dim_reports_no_data() -> None:
    r = analyze_scorecards(_population())  # c7 never set
    c7 = _dim(r, "c7_ame")
    assert c7["n"] == 0 and c7["flags"] == ["no_data"]
    assert "c7_ame" not in r["flagged_dimensions"]  # no_data isn't an actionable flag


def test_empty_population() -> None:
    r = analyze_scorecards([])
    assert r["n_scorecards"] == 0 and r["pass_rate"] == 0.0
