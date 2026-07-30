"""Cross-Pack Learning Transfer (v1.2).

Ventures don't start from zero. When one pack has invested in testing a forge capability and another
pack exercises the same capability but only thinly, the first pack's scenarios are transfer
candidates — adapt them instead of authoring from scratch. This derives those opportunities purely
from existing scenario coverage: for each forge capability, the best-covered pack is the donor and
any pack that touches the capability but sits below the minimum is a recipient.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.pack import Pack, Scenario

DEFAULT_MIN = 3


async def transfer_opportunities(
    session: AsyncSession, *, min_scenarios: int = DEFAULT_MIN
) -> dict:
    packs = {p.id: p for p in (await session.execute(select(Pack))).scalars().all()}
    scenarios = (await session.execute(select(Scenario))).scalars().all()

    # forgeCap -> packId -> scenario count (a scenario can exercise several caps).
    cap_counts: dict[str, dict[str, int]] = {}
    for s in scenarios:
        for cap in s.testedForgeCaps or []:
            cap_counts.setdefault(cap, {}).setdefault(s.packId, 0)
            cap_counts[cap][s.packId] += 1

    transfers: list[dict] = []
    for cap, by_pack in cap_counts.items():
        if len(by_pack) < 2:
            continue  # a cap only one pack touches has nowhere to transfer to
        donor_id = max(by_pack, key=lambda pid: by_pack[pid])
        donor_count = by_pack[donor_id]
        if donor_count < min_scenarios:
            continue  # donor itself isn't well-covered enough to be a source of truth
        for pid, count in by_pack.items():
            if pid == donor_id or count >= min_scenarios:
                continue
            donor = packs.get(donor_id)
            recipient = packs.get(pid)
            transfers.append(
                {
                    "forge_cap": cap,
                    "donor_pack": donor.packId if donor else donor_id,
                    "donor_scenarios": donor_count,
                    "recipient_pack": recipient.packId if recipient else pid,
                    "recipient_scenarios": count,
                    "cross_venture": bool(
                        donor and recipient and donor.ownerVenture != recipient.ownerVenture
                    ),
                    "suggested_transfer": min_scenarios - count,
                    "rationale": (
                        f"{cap}: {donor.packId if donor else donor_id} has {donor_count}; "
                        f"{recipient.packId if recipient else pid} has only {count}. "
                        f"Adapt {min_scenarios - count} to close the gap."
                    ),
                }
            )

    transfers.sort(key=lambda t: (-t["suggested_transfer"], t["forge_cap"]))
    return {
        "min_scenarios": min_scenarios,
        "total_opportunities": len(transfers),
        "transfers": transfers,
    }
