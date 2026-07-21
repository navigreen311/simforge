"""Meta-Eval analysis (blueprint §L.4; ADR-0027).

Asks "is the rubric any good?" over a population of scorecards. For each numeric dim it reports
mean/stddev/range and — crucially — **discrimination**: does the dim separate gate-*passed* from
gate-*failed* runs? A dim that is constant (no variance) or that scores passers and failers the same
provides no signal and is flagged for review. Read-only; no writes.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.pack import Pack, Scenario
from src.models.run import Run
from src.models.scorecard import Scorecard

# Numeric dims (label → Scorecard attribute). p2 (bool) + c4 (categorical) are handled elsewhere.
_NUMERIC_DIMS: dict[str, str] = {
    "p1_correctness": "p1Correctness",
    "p3_process_fidelity": "p3ProcessFidelity",
    "p4_time_to_resolution": "p4TimeToResolution",
    "p5_escalation": "p5Escalation",
    "p6_doc_quality": "p6DocQuality",
    "p7_cx": "p7CustomerExperience",
    "p8_cost_discipline": "p8CostDiscipline",
    "c1_breath": "c1BreathCoherence",
    "c2_soul": "c2SoulStability",
    "c3_fot": "c3FotPressureManagement",
    "c5_echo": "c5EchoRegretLoad",
    "c6_hfm": "c6HfmDriveBalance",
    "c7_ame": "c7AmeReputationTrajectory",
    "cognitive_aggregate": "cognitiveAggregate",
}

_CONSTANT_EPS = 0.01  # stddev below this = no variance → no signal
_DISCRIMINATION_MIN = 0.05  # |mean_passed − mean_failed| below this = doesn't separate outcomes


@dataclass
class DimStats:
    dim: str
    n: int
    mean: float | None
    stddev: float | None
    min: float | None
    max: float | None
    mean_passed: float | None
    mean_failed: float | None
    discrimination: float | None
    flags: list[str]

    def as_dict(self) -> dict:
        return self.__dict__


def analyze_scorecards(cards: list[Scorecard]) -> dict:
    """Per-dim stats + discrimination + flags over a list of scorecards."""
    n_cards = len(cards)
    passed = [c for c in cards if c.readinessGatePassed]
    failed = [c for c in cards if not c.readinessGatePassed]

    dims: list[DimStats] = []
    for label, attr in _NUMERIC_DIMS.items():
        vals = [v for c in cards if (v := getattr(c, attr, None)) is not None]
        pv = [v for c in passed if (v := getattr(c, attr, None)) is not None]
        fv = [v for c in failed if (v := getattr(c, attr, None)) is not None]
        flags: list[str] = []

        if not vals:
            dims.append(DimStats(label, 0, None, None, None, None, None, None, None, ["no_data"]))
            continue

        std = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        mean_p = statistics.fmean(pv) if pv else None
        mean_f = statistics.fmean(fv) if fv else None
        disc = (mean_p - mean_f) if (mean_p is not None and mean_f is not None) else None

        if len(vals) < 2:
            flags.append("insufficient_data")
        elif std < _CONSTANT_EPS:
            flags.append("constant")  # no variance → dim carries no signal
        if disc is not None and abs(disc) < _DISCRIMINATION_MIN:
            flags.append("non_discriminating")  # passers & failers score the same

        dims.append(
            DimStats(
                dim=label,
                n=len(vals),
                mean=statistics.fmean(vals),
                stddev=std,
                min=min(vals),
                max=max(vals),
                mean_passed=mean_p,
                mean_failed=mean_f,
                discrimination=disc,
                flags=flags,
            )
        )

    # Only actionable flags (a dim that carries no signal) count as "flagged" — not data gaps.
    _ACTIONABLE = {"constant", "non_discriminating"}
    flagged = [d.dim for d in dims if _ACTIONABLE & set(d.flags)]
    return {
        "n_scorecards": n_cards,
        "n_passed": len(passed),
        "n_failed": len(failed),
        "pass_rate": (len(passed) / n_cards) if n_cards else 0.0,
        "dimensions": [d.as_dict() for d in dims],
        "flagged_dimensions": flagged,
    }


async def meta_eval_report(session: AsyncSession, *, pack_id: str | None = None) -> dict:
    """Run the meta-eval over all scorecards (optionally scoped to one pack)."""
    stmt = select(Scorecard)
    if pack_id:
        stmt = (
            select(Scorecard)
            .join(Run, Scorecard.runId == Run.id)
            .join(Scenario, Run.scenarioId == Scenario.id)
            .join(Pack, Scenario.packId == Pack.id)
            .where(Pack.packId == pack_id)
        )
    cards = (await session.execute(stmt)).scalars().all()
    report = analyze_scorecards(list(cards))
    report["pack_id"] = pack_id
    return report
