"""Golden Benchmark suite (ADR-0033).

A curated set of scenarios (``Scenario.isGolden = true``) with a **committed expected baseline**
(`apps/api/golden/baseline.json`): each golden scenario's outcome, readiness gate, and every rubric
dimension. Re-running the suite and comparing against the baseline is a **regression guard on the
evaluator itself** — if a scorer or gate threshold shifts a golden dimension beyond tolerance, the
suite reports a regression (and the CI golden test fails). Golden runs are seed- and
stub-deterministic, so the baseline is exact (content dims) with a coarse tolerance on
wall-clock-derived timing dims.

Regenerate the baseline **only when a change to golden behavior is intended**, via
``scripts/golden-baseline.py`` — that is the moment to review what moved and why.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.pack import Scenario
from src.models.scorecard import Scorecard
from src.services.evaluation import evaluate_run
from src.services.runner import run_scenario
from src.services.village.reader import VillageReader

# apps/api/golden/baseline.json (this file is apps/api/src/services/golden/suite.py).
DEFAULT_BASELINE_PATH = Path(__file__).resolve().parents[3] / "golden" / "baseline.json"

# (scorecard attribute, wire label) for every dimension recorded/compared.
_DIMS: list[tuple[str, str]] = [
    ("p1Correctness", "p1_correctness"),
    ("p2Compliance", "p2_compliance"),
    ("p3ProcessFidelity", "p3_process_fidelity"),
    ("p4TimeToResolution", "p4_time_to_resolution"),
    ("p5Escalation", "p5_escalation"),
    ("p6DocQuality", "p6_doc_quality"),
    ("p7CustomerExperience", "p7_customer_experience"),
    ("p8CostDiscipline", "p8_cost_discipline"),
    ("c1BreathCoherence", "c1_breath_coherence"),
    ("c2SoulStability", "c2_soul_stability"),
    ("c3FotPressureManagement", "c3_fot_pressure_management"),
    ("c4ArcNarrativeCoherence", "c4_arc_narrative_coherence"),
    ("c5EchoRegretLoad", "c5_echo_regret_load"),
    ("c6HfmDriveBalance", "c6_hfm_drive_balance"),
    ("c7AmeReputationTrajectory", "c7_ame_reputation_trajectory"),
    ("cognitiveAggregate", "cognitive_aggregate"),
]

_EPS = 1e-6
_TIMING_EPS = 1e-2
_TIMING_DIMS = {"p4_time_to_resolution"}  # wall-clock-derived → jitters run-to-run


def load_baseline(path: Path | None = None) -> dict:
    p = path or DEFAULT_BASELINE_PATH
    if not p.exists():
        return {"scenarios": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def _dim_changed(label: str, expected: object, actual: object) -> bool:
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        eps = _TIMING_EPS if label in _TIMING_DIMS else _EPS
        return abs(float(expected) - float(actual)) > eps
    return expected != actual


async def compute_golden(session: AsyncSession, reader: VillageReader) -> dict:
    """Run every golden scenario and capture its outcome/gate/dims (the baseline shape)."""
    scenarios = (
        (await session.execute(select(Scenario).where(Scenario.isGolden.is_(True)))).scalars().all()
    )
    out: dict[str, dict] = {}
    for scenario in sorted(scenarios, key=lambda s: s.scenarioId):
        run = await run_scenario(session, scenario.scenarioId, reader)
        card: Scorecard | None = (
            await evaluate_run(session, run.id) if run.status != "errored" else None
        )
        dims = {label: getattr(card, attr) for attr, label in _DIMS} if card else {}
        out[scenario.scenarioId] = {
            "outcome": run.outcome,
            "gate_passed": bool(card.readinessGatePassed) if card else None,
            "dims": dims,
        }
    return out


async def run_golden_suite(
    session: AsyncSession,
    reader: VillageReader,
    baseline: dict | None = None,
    *,
    baseline_path: Path | None = None,
) -> dict:
    """Run the golden suite and compare against the committed baseline → a regression report."""
    if baseline is None:
        baseline = load_baseline(baseline_path).get("scenarios", {})

    current = await compute_golden(session, reader)
    results: list[dict] = []
    regressions = 0

    for scenario_id in sorted(current):
        actual = current[scenario_id]
        expected = baseline.get(scenario_id)
        if expected is None:
            results.append({"scenario_id": scenario_id, "status": "no_baseline", "diffs": []})
            continue

        diffs: list[dict] = []
        if actual["outcome"] != expected.get("outcome"):
            diffs.append(
                {"dim": "outcome", "expected": expected.get("outcome"), "actual": actual["outcome"]}
            )
        if actual["gate_passed"] != expected.get("gate_passed"):
            diffs.append(
                {
                    "dim": "gate_passed",
                    "expected": expected.get("gate_passed"),
                    "actual": actual["gate_passed"],
                }
            )
        exp_dims = expected.get("dims", {})
        for label, actual_val in actual["dims"].items():
            if _dim_changed(label, exp_dims.get(label), actual_val):
                diffs.append({"dim": label, "expected": exp_dims.get(label), "actual": actual_val})

        status = "regression" if diffs else "match"
        if diffs:
            regressions += 1
        results.append({"scenario_id": scenario_id, "status": status, "diffs": diffs})

    # A golden scenario in the baseline that produced no current run at all.
    for scenario_id in sorted(set(baseline) - set(current)):
        results.append({"scenario_id": scenario_id, "status": "missing", "diffs": []})

    return {
        "total": len(current),
        "matched": sum(1 for r in results if r["status"] == "match"),
        "regressions": regressions,
        "passed": regressions == 0 and all(r["status"] != "missing" for r in results),
        "results": results,
    }
