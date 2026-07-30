"""Scenario Coverage Optimizer (v1.2).

Turns the raw coverage heatmap into a ranked worklist: which (pack × role × tier) cells are
under-tested, and how many scenarios to add to close the gap. Priority weights a deficit by tier —
an untested crisis path is worse than an untested foundational one — so the top of the list is where
new authoring effort buys the most certification confidence. Pure derived analysis, no external deps.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.pack import Pack, Scenario

# A missing crisis scenario is a bigger hole than a missing foundational one.
TIER_WEIGHT = {"advanced_crisis": 3.0, "intermediate": 2.0, "foundational": 1.0}
TIERS = ("foundational", "intermediate", "advanced_crisis")
DEFAULT_MIN_PER_CELL = 3


@dataclass
class Recommendation:
    pack: str
    role: str
    tier: str
    current: int
    target: int
    deficit: int
    priority: float
    rationale: str


@dataclass
class OptimizerReport:
    min_per_cell: int
    recommendations: list[Recommendation] = field(default_factory=list)
    total_deficit: int = 0
    fully_covered: bool = False

    def as_dict(self) -> dict:
        return {
            "min_per_cell": self.min_per_cell,
            "total_deficit": self.total_deficit,
            "fully_covered": self.fully_covered,
            "recommendations": [
                {
                    "pack": r.pack,
                    "role": r.role,
                    "tier": r.tier,
                    "current": r.current,
                    "target": r.target,
                    "deficit": r.deficit,
                    "priority": round(r.priority, 2),
                    "rationale": r.rationale,
                }
                for r in self.recommendations
            ],
        }


async def optimize(session: AsyncSession, *, min_per_cell: int = DEFAULT_MIN_PER_CELL) -> dict:
    packs = {p.id: p.packId for p in (await session.execute(select(Pack))).scalars().all()}
    scenarios = (await session.execute(select(Scenario))).scalars().all()

    # Count scenarios per (pack, role, tier), and the set of roles present per pack.
    counts: dict[tuple[str, str, str], int] = {}
    roles_by_pack: dict[str, set[str]] = {}
    for s in scenarios:
        pack = packs.get(s.packId, s.packId)
        counts[(pack, s.testedAgentVillageId, s.tier)] = (
            counts.get((pack, s.testedAgentVillageId, s.tier), 0) + 1
        )
        roles_by_pack.setdefault(pack, set()).add(s.testedAgentVillageId)

    recs: list[Recommendation] = []
    for pack, roles in roles_by_pack.items():
        for role in sorted(roles):
            for tier in TIERS:
                current = counts.get((pack, role, tier), 0)
                if current >= min_per_cell:
                    continue
                deficit = min_per_cell - current
                weight = TIER_WEIGHT.get(tier, 1.0)
                # An entirely-empty cell is worse than a merely-thin one — bump priority.
                empty_bonus = 1.5 if current == 0 else 1.0
                priority = deficit * weight * empty_bonus
                rationale = (
                    f"{'No' if current == 0 else 'Only ' + str(current)} "
                    f"{tier.replace('_', ' ')} scenario(s) for {role}; "
                    f"add {deficit} to reach the minimum of {min_per_cell}."
                )
                recs.append(
                    Recommendation(
                        pack=pack,
                        role=role,
                        tier=tier,
                        current=current,
                        target=min_per_cell,
                        deficit=deficit,
                        priority=priority,
                        rationale=rationale,
                    )
                )

    recs.sort(key=lambda r: (-r.priority, r.pack, r.role, r.tier))
    report = OptimizerReport(
        min_per_cell=min_per_cell,
        recommendations=recs,
        total_deficit=sum(r.deficit for r in recs),
        fully_covered=len(recs) == 0 and len(scenarios) > 0,
    )
    return report.as_dict()
