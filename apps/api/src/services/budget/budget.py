"""Monthly cost-cap enforcement (ADR-0039).

Each run carries a metered `costUsd` (0 for the free stub/local providers; non-zero once a real LLM
or Forge sandbox is active). This sums the current calendar month's cost per execution mode and
enforces a per-month ceiling *before* a run starts — so a runaway real-provider spend is stopped at
the door rather than discovered on the invoice. Sandbox and integrated runs have independent caps.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.run import Run
from src.utils.time import utcnow


class BudgetExceededError(Exception):
    """Raised when the current month's spend for a mode has reached its cap."""

    def __init__(self, mode: str, spent: float, cap: float) -> None:
        self.mode = mode
        self.spent = spent
        self.cap = cap
        super().__init__(f"{mode} budget exceeded: ${spent:.2f} spent of ${cap:.2f} monthly cap")


def _month_start(now: datetime | None = None) -> datetime:
    now = now or utcnow()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _cap_for(mode: str) -> float:
    return (
        settings.simforge_budget_integrated_monthly_usd
        if mode == "integrated"
        else settings.simforge_budget_sandbox_monthly_usd
    )


async def month_spend(session: AsyncSession, mode: str, *, now: datetime | None = None) -> float:
    """Sum of metered run cost for `mode` since the start of the current calendar month."""
    total = (
        await session.execute(
            select(func.coalesce(func.sum(Run.costUsd), 0.0))
            .where(Run.executionMode == mode)
            .where(Run.startedAt >= _month_start(now))
        )
    ).scalar_one()
    return float(total or 0.0)


async def budget_status(session: AsyncSession) -> dict:
    """Spend / cap / remaining for both modes this month (for dashboards + deploy checks)."""
    out: dict[str, dict] = {}
    for mode in ("sandbox", "integrated"):
        spent = await month_spend(session, mode)
        cap = _cap_for(mode)
        out[mode] = {
            "spent_usd": round(spent, 4),
            "cap_usd": cap,
            "remaining_usd": round(max(0.0, cap - spent), 4),
            "exceeded": spent >= cap,
        }
    return {"month": _month_start().date().isoformat(), "modes": out}


async def enforce_budget(session: AsyncSession, mode: str) -> None:
    """Raise BudgetExceededError if `mode` has already reached its monthly cap. No-op otherwise."""
    spent = await month_spend(session, mode)
    cap = _cap_for(mode)
    if spent >= cap:
        raise BudgetExceededError(mode, spent, cap)
