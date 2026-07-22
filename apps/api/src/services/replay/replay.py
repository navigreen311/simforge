"""Time-travel run replay (ADR-0032).

Re-executes a prior run's scenario to reproduce its behavior, then diffs the replay against the
original — outcome, gate, transcript, and every rubric dimension. A run is seed-deterministic
(``scenario.seed`` drives the world + complications) and the StubProvider is offline/deterministic,
a stub replay is bit-identical: `deterministic=true` with an empty diff. Under a real LLM provider a
replay may diverge — and that divergence is itself the signal (non-reproducibility of a certified
run).

**Replay is always sandboxed.** It never re-applies integrated (write-enabled) actions — reproducing
a run must not re-commit its side effects. The replay is a fresh Run row, tagged with a `replay`
TraceEvent that points back at the original for lineage.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.run import Run, TraceEvent
from src.models.scorecard import Scorecard
from src.services.evaluation import evaluate_run
from src.services.runner import run_scenario
from src.services.village.reader import VillageReader
from src.telemetry.tracing import span
from src.utils.time import utcnow

# (scorecard attribute, wire label) for every rubric dimension compared on replay.
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

# Content-derived float dims equal within this tolerance count as unchanged (FP noise).
_EPS = 1e-6
# p4 (time-to-resolution) is derived from wall-clock run latency, so it jitters run-to-run even on
# an identical replay. It is compared with a coarse tolerance: reproducibility means the *behavior*
# is reproduced, not that two runs took the same number of microseconds. Real behavioral divergence
# (a different judge verdict under a live LLM) is orders of magnitude larger than this.
_TIMING_EPS = 1e-2
_TIMING_DIMS = {"p4TimeToResolution"}


@dataclass
class DimDiff:
    dim: str
    original: float | str | bool | None
    replay: float | str | bool | None


@dataclass
class ReplayComparison:
    original_run_id: str
    replay_run_id: str
    scenario_id: str
    deterministic: bool
    transcript_identical: bool
    original_outcome: str | None
    replay_outcome: str | None
    original_gate_passed: bool | None
    replay_gate_passed: bool | None
    scorecard_diffs: list[DimDiff]

    def as_dict(self) -> dict:
        d = asdict(self)
        d["scorecard_diffs"] = [asdict(x) for x in self.scorecard_diffs]
        return d


def _changed(attr: str, a: object, b: object) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        eps = _TIMING_EPS if attr in _TIMING_DIMS else _EPS
        return abs(float(a) - float(b)) > eps
    return a != b


async def replay_run(
    session: AsyncSession,
    run_id: str,
    reader: VillageReader,
    provider: object | None = None,
) -> ReplayComparison:
    """Replay ``run_id``'s scenario and return the original-vs-replay comparison.

    Raises ``LookupError`` if the run (or its scenario/original scorecard) can't be found.
    """
    original = (await session.execute(select(Run).where(Run.runId == run_id))).scalar_one_or_none()
    if original is None:
        raise LookupError(f"Run not found: {run_id}")

    from src.models.pack import Scenario

    scenario = (
        await session.execute(select(Scenario).where(Scenario.id == original.scenarioId))
    ).scalar_one()
    original_card = (
        await session.execute(select(Scorecard).where(Scorecard.runId == original.id))
    ).scalar_one_or_none()

    with span(
        "run.replay",
        **{"replay.original_run_id": run_id, "scenario.id": scenario.scenarioId},
    ):
        # Always sandbox: never re-commit integrated side effects (provider kwarg reserved for
        # counterfactual replays; default reuses the configured provider → faithful reproduction).
        replay = await run_scenario(
            session,
            scenario.scenarioId,
            reader,
            provider=provider,  # type: ignore[arg-type]
        )
        replay_card = await evaluate_run(session, replay.id) if replay.status != "errored" else None

    # Provenance: tag the replay run with a trace event pointing back at the original.
    session.add(
        TraceEvent(
            runId=replay.id,
            timestamp=utcnow(),
            eventType="replay",
            phase="meta",
            turnNumber=None,
            payload={"original_run_id": run_id, "scenario_id": scenario.scenarioId},
        )
    )

    diffs: list[DimDiff] = []
    if original_card is not None and replay_card is not None:
        for attr, label in _DIMS:
            ov = getattr(original_card, attr)
            rv = getattr(replay_card, attr)
            if _changed(attr, ov, rv):
                diffs.append(DimDiff(dim=label, original=ov, replay=rv))

    transcript_identical = (original.transcript or []) == (replay.transcript or [])
    orig_gate = original_card.readinessGatePassed if original_card else None
    replay_gate = replay_card.readinessGatePassed if replay_card else None
    deterministic = (
        transcript_identical
        and original.outcome == replay.outcome
        and orig_gate == replay_gate
        and not diffs
    )

    await session.commit()

    return ReplayComparison(
        original_run_id=run_id,
        replay_run_id=replay.runId,
        scenario_id=scenario.scenarioId,
        deterministic=deterministic,
        transcript_identical=transcript_identical,
        original_outcome=original.outcome,
        replay_outcome=replay.outcome,
        original_gate_passed=orig_gate,
        replay_gate_passed=replay_gate,
        scorecard_diffs=diffs,
    )
