"""ADR-0167 (Ivan Green, 14 November 2026): the Village can ask whether an exam holds the model.

`GET /api/health/exam-model` - public, read-only, cheap. It reads `pg_locks` for `exam:model`
and takes nothing; it names no exam, ref or agent, and carries no secret.
"""

from __future__ import annotations

import inspect

import pytest
from httpx import AsyncClient

from src.routers import health
from src.services.agent_runtime import exam_model_lock

pytestmark = pytest.mark.asyncio


async def test_it_says_whether_an_exam_holds_the_model(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    quiet = (await client.get("/api/health/exam-model")).json()
    assert quiet["held"] is False and quiet["lock"] == "exam:model"
    assert set(quiet) == {"held", "lock", "checked_at"}, "nothing but whether"

    async def held(_conn: object) -> bool:
        return True

    monkeypatch.setattr(exam_model_lock, "model_lock_held", held)
    busy = (await client.get("/api/health/exam-model")).json()
    assert busy["held"] is True


def test_it_reads_the_lock_and_never_takes_it() -> None:
    src = inspect.getsource(health.exam_model)
    assert "model_lock_held" in src and "exam_model_lock(" not in src
    assert "pg_try_advisory_lock" not in inspect.getsource(exam_model_lock.model_lock_held)
