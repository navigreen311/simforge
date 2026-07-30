"""Cold-Start Playbook (v1.2).

The path a new venture walks from "workflow signed off" to a certifiable v1 Pack, tracked against
an SLA. Every milestone is derived from live state — no manual checkboxes — so the playbook can't
drift from reality: the pack either has scenarios or it doesn't, is signed or isn't, passed a dress
rehearsal or hasn't. The blocking step is the first unmet milestone; the SLA compares elapsed days
since venture registration against the target.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.dress_rehearsal import DressRehearsal
from src.models.pack import Pack, Scenario
from src.models.scenario_truth_review import ScenarioTruthReview
from src.models.venture import Venture
from src.utils.time import utcnow

MIN_SCENARIOS = 3

# Ordered milestones from signoff → v1-pack-ready. Each is a (key, label) pair.
MILESTONES = (
    ("venture_registered", "Venture registered"),
    ("pack_created", "Pack created"),
    ("scenarios_authored", f"Scenarios authored (>= {MIN_SCENARIOS})"),
    ("truth_reviewed", "Scenarios truth-reviewed"),
    ("pack_signed", "Pack signed"),
    ("dress_rehearsal_signed", "Dress rehearsal signed off"),
)


async def _venture_pack(session: AsyncSession, slug: str) -> Pack | None:
    return (
        await session.execute(
            select(Pack).where(Pack.ownerVenture == slug).order_by(Pack.createdAt.desc()).limit(1)
        )
    ).scalar_one_or_none()


async def venture_playbook(session: AsyncSession, venture: Venture) -> dict:
    pack = await _venture_pack(session, venture.slug)

    scenario_count = 0
    truth_ok = False
    pack_signed = False
    rehearsal_signed = False
    if pack is not None:
        scenario_count = (
            await session.execute(
                select(func.count()).select_from(Scenario).where(Scenario.packId == pack.id)
            )
        ).scalar_one()
        pack_signed = pack.signedBy is not None
        # Every authored scenario in the pack has an approved truth review (and there is >=1).
        sids = (
            (await session.execute(select(Scenario.scenarioId).where(Scenario.packId == pack.id)))
            .scalars()
            .all()
        )
        if sids:
            approved = (
                (
                    await session.execute(
                        select(ScenarioTruthReview.scenarioId).where(
                            ScenarioTruthReview.scenarioId.in_(sids),
                            ScenarioTruthReview.status == "approved",
                        )
                    )
                )
                .scalars()
                .all()
            )
            truth_ok = len(set(approved)) == len(set(sids))
        rehearsal_signed = (
            await session.execute(
                select(func.count())
                .select_from(DressRehearsal)
                .where(DressRehearsal.packId == pack.packId, DressRehearsal.status == "signed")
            )
        ).scalar_one() > 0

    states = {
        "venture_registered": True,
        "pack_created": pack is not None,
        "scenarios_authored": scenario_count >= MIN_SCENARIOS,
        "truth_reviewed": truth_ok,
        "pack_signed": pack_signed,
        "dress_rehearsal_signed": rehearsal_signed,
    }

    milestones = [{"key": k, "label": label, "done": states[k]} for k, label in MILESTONES]
    done_count = sum(1 for m in milestones if m["done"])
    blocking = next((m["key"] for m in milestones if not m["done"]), None)
    ready = blocking is None

    elapsed_days = None
    if venture.createdAt is not None:
        elapsed_days = (utcnow() - venture.createdAt).days
    target = settings.cold_start_sla_days
    if ready:
        sla_status = "met"
    elif elapsed_days is None:
        sla_status = "unknown"
    elif elapsed_days > target:
        sla_status = "breached"
    elif elapsed_days >= 0.75 * target:
        sla_status = "at_risk"
    else:
        sla_status = "within"

    return {
        "venture": venture.slug,
        "name": venture.name,
        "pack": pack.packId if pack else None,
        "ready": ready,
        "progress": f"{done_count}/{len(MILESTONES)}",
        "blocking_step": blocking,
        "milestones": milestones,
        "elapsed_days": elapsed_days,
        "sla_target_days": target,
        "sla_status": sla_status,
    }


async def all_playbooks(session: AsyncSession) -> list[dict]:
    ventures = (await session.execute(select(Venture))).scalars().all()
    return [await venture_playbook(session, v) for v in ventures]
