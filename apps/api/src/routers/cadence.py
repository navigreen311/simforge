"""Cadence/scheduler router (Part 16) — inspect the schedule + trigger a job on demand.

Not every registered job is triggerable from here. `CadenceJob.triggerable` is checked before
`run`, because ADR-0050's consequence — no endpoint triggers a battery — is about this router and
is invisible to the guard test that walks out of `src.routers.operation`.

**The role dependency is not what holds that line.** ADR-0050 read `Principal.has_role` out of the
code and found `return role in self.roles or "admin" in self.roles` — any check answers True once
`admin` is present. So `require_role("admin")` below is the weakest gate in the file, and a
battery must be excluded by name rather than by role.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.deps import require_role
from src.services.cadence import JOBS, JOBS_BY_NAME

router = APIRouter()


@router.get("/status", dependencies=[Depends(require_role("viewer"))])
async def scheduler_status() -> dict:
    """The configured cadence (jobs + schedule) and whether the scheduler is running."""
    from src.config import settings
    from src.scheduler import scheduler_running

    return {
        "enabled": settings.scheduler_enabled,
        "running": scheduler_running(),
        "jobs": [
            {"name": j.name, "schedule": j.schedule, "description": j.description} for j in JOBS
        ],
    }


@router.post("/run/{job_name}", dependencies=[Depends(require_role("admin"))])
async def run_job(job_name: str, session: AsyncSession = Depends(get_session)) -> dict:
    """Trigger a cadence job immediately (does not require the scheduler to be running)."""
    job = JOBS_BY_NAME.get(job_name)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown job '{job_name}'. Known: {sorted(JOBS_BY_NAME)}",
        )
    if not job.triggerable:
        # 403 and not 404: the job exists, is scheduled, and is listed by /status. Pretending it
        # were unknown would hide a running job from an operator to enforce a rule about who may
        # START it - two different questions. See CadenceJob.triggerable and ADR-0050.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Job '{job_name}' is scheduler-only and cannot be triggered by request. "
                "See ADR-0050: no endpoint triggers a battery."
            ),
        )
    return await job.run(session=session)
