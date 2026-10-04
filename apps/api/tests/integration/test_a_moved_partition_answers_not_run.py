"""ADR-0148: a sealed partition whose instructions moved does not answer PASS.

Its scenarios number rules in instruction sets that are no longer live (ADR-0125), so its
verdicts describe instructions not in force. Gate 9.5 answers NOT_RUN, `decided_at` null,
until a new partition is sealed - whatever the old sittings said.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.forge_instruction_set import ForgeInstructionSet
from src.services.operation.partition_verdict import RESPONSE_KEYS, venture_verdict
from tests.integration.test_gate_9_5_verdict import (
    AUTH,
    T0,
    URL,
    _add,
    _partition,
    _verdict,
    bridged,  # noqa: F401 - fixture
)

pytestmark = pytest.mark.asyncio

AUTHORED = "sha256:authored-from"
MOVED = "sha256:moved-to"


def _set(module: str, content_hash: str, at: datetime) -> ForgeInstructionSet:
    return ForgeInstructionSet(
        forgeId="forge-a",
        moduleId=module,
        instructionVersion="1.0.0",
        forgeApiVersion="1.0.0",
        authoredBy="the-office",
        contentHash=content_hash,
        neverDo=["Never do the thing."],
        createdAt=at,
        lastSubmittedAt=at,
    )


async def _passed(db: AsyncSession, venture: str, modules=("m", "n")) -> object:  # noqa: ANN001
    """A sealed partition authored from the live sets, with every agent's sittings PASS."""
    for m in modules:
        await _add(db, _set(m, f"{AUTHORED}-{m}", T0))
    p = _partition(venture)
    p.instructionHashes = {m: f"{AUTHORED}-{m}" for m in modules}
    await _add(db, p)
    await _add(db, _verdict(p, "a1", "PASS"), _verdict(p, "a2", "PASS", at=T0 + timedelta(1)))
    return p


async def test_matching_instructions_answer_pass(db_session: AsyncSession) -> None:
    await _passed(db_session, "v-live")
    assert (await venture_verdict(db_session, "v-live"))["verdict"] == "PASS"


async def test_one_moved_module_answers_not_run(db_session: AsyncSession) -> None:
    await _passed(db_session, "v-moved")
    # The Office re-submits one module under a new hash: it is now the live set.
    await _add(db_session, _set("n", MOVED, T0 + timedelta(days=1)))
    body = await venture_verdict(db_session, "v-moved")
    assert body["verdict"] == "NOT_RUN"
    assert body["decided_at"] is None
    assert body["partition_exists"] is True
    assert tuple(body) == RESPONSE_KEYS


async def test_a_return_to_the_authored_hash_answers_again(db_session: AsyncSession) -> None:
    """Live is the most recently submitted set; going back to the authored one restores it."""
    await _passed(db_session, "v-back")
    await _add(db_session, _set("n", MOVED, T0 + timedelta(days=1)))
    assert (await venture_verdict(db_session, "v-back"))["verdict"] == "NOT_RUN"
    # A re-submission of the authored set stamps its row (ADR-0125); it is live again.
    authored = (
        await db_session.execute(
            select(ForgeInstructionSet).where(
                ForgeInstructionSet.moduleId == "n",
                ForgeInstructionSet.contentHash == f"{AUTHORED}-n",
            )
        )
    ).scalar_one()
    authored.lastSubmittedAt = T0 + timedelta(days=2)
    await db_session.commit()
    assert (await venture_verdict(db_session, "v-back"))["verdict"] == "PASS"


async def test_a_new_partition_sealed_on_the_new_hash_answers(db_session: AsyncSession) -> None:
    old = await _passed(db_session, "v-new")
    await _add(db_session, _set("n", MOVED, T0 + timedelta(days=1)))
    old.status = "retired"
    new = _partition("v-new", digest="sha256:p2", sealed_at=T0 + timedelta(days=2))
    new.instructionHashes = {"m": f"{AUTHORED}-m", "n": MOVED}
    await _add(db_session, old, new)
    await _add(db_session, _verdict(new, "a1", "PASS", at=T0 + timedelta(days=3)))
    assert (await venture_verdict(db_session, "v-new"))["verdict"] == "PASS"


async def test_the_bridge_answers_not_run_and_names_no_hash(
    bridged: AsyncClient,  # noqa: F811
    db_session: AsyncSession,
) -> None:
    await _passed(db_session, "v-wire")
    await _add(db_session, _set("n", MOVED, T0 + timedelta(days=1)))
    res = await bridged.post(URL, json={"venture_id": "v-wire"}, headers=AUTH)
    assert res.status_code == 200, res.text
    assert res.json()["verdict"] == "NOT_RUN"
    for leaked in (AUTHORED, MOVED, "instruction"):
        assert leaked not in res.text
