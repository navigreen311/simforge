"""Cadence/scheduler router (Part 16) — inspect the schedule + trigger a job on demand."""

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
    return await job.run(session=session)
