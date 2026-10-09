"""The agent's answers to The Office's own probes: kept, and read back by The Office (ADR-0153).

WHY
===

    A failed submitted probe used to leave only reason codes - `act_mismatch`,
    `claim_mismatch` - and the answer itself was discarded after parsing. The
    Office could see THAT its probe failed and had to infer what the agent said.
    The probe is The Office's own text, so the answer to it can be shown.

WHAT THIS MODULE MAY HOLD
=========================

    Plain values and the two `submitted_answer` models. It imports nothing that
    holds a held-out probe, its key or its grader: the request path reaches it,
    and `test_no_router_can_reach_the_scenarios` walks that path. The writer takes
    strings rather than a `SubmittedKey` for the same reason - importing the
    grader would put held-out scoring one import away from a router.

WHO MAY READ
============

    The Office, with its tenant credential, for a run it minted, under the
    venture that run names. Every read is recorded, including refusals. A
    refusal is one answer on the wire whatever its cause, so the call cannot
    probe which runs exist.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.operation_run import OperationRun
from src.models.submitted_answer import (
    NEVER_STORED_CLASSES,
    SubmittedAnswerRead,
    SubmittedProbeAnswer,
)
from src.services.operation.partition_roster import venture_of_run_ref

#: Refusal codes, recorded on the audit row and never sent.
REFUSED_NOT_OFFICE_MINTED = "run_ref_not_minted_by_the_office"
REFUSED_NO_VENTURE = "no_office_venture_header"
REFUSED_ANOTHER_VENTURE = "run_belongs_to_another_venture"
REFUSED_UNKNOWN_RUN = "no_such_run"

#: The keys of one returned answer, in order. Nothing else is sent.
ANSWER_KEYS: tuple[str, ...] = (
    "scenario_ref",
    "scenario_class",
    "ordinal",
    "attempt",
    "seed",
    "verdict",
    "reasons",
    "answer_text",
)


class HeldOutAnswerRefused(ValueError):
    """An answer to a held-out probe reached the writer. Nothing was stored."""


def record_submitted_answer(
    session: AsyncSession,
    *,
    run_ref: str,
    forge_id: str,
    module_id: str,
    instruction_content_hash: str,
    scenario_ref: str,
    scenario_class: str,
    ordinal: int,
    attempt: int,
    seed: int,
    verdict: str,
    reasons: Sequence[str],
    answer_text: str,
) -> None:
    """Add one answer row to the session. The caller's commit makes it permanent.

    Refuses a held-out class before the insert; the CHECK refuses it again at the database.
    """
    if scenario_class in NEVER_STORED_CLASSES:
        raise HeldOutAnswerRefused(
            f"{scenario_ref}: an answer to a {scenario_class} probe is never stored (ADR-0153)."
        )
    session.add(
        SubmittedProbeAnswer(
            runRef=run_ref,
            forgeId=forge_id,
            moduleId=module_id,
            instructionContentHash=instruction_content_hash,
            scenarioRef=scenario_ref,
            scenarioClass=scenario_class,
            ordinal=ordinal,
            attempt=attempt,
            seed=seed,
            verdict=verdict,
            reasons=list(reasons),
            answerText=answer_text,
        )
    )


@dataclass(frozen=True, slots=True)
class OfficeRead:
    """The outcome of one read. `answers` is None when it was refused."""

    run_ref: str
    answers: list[dict[str, Any]] | None
    refusal: str | None


async def _refusal(session: AsyncSession, run_ref: str, office_venture: str | None) -> str | None:
    venture = venture_of_run_ref(run_ref)
    if venture is None:
        return REFUSED_NOT_OFFICE_MINTED
    if not office_venture or not office_venture.strip():
        return REFUSED_NO_VENTURE
    if venture != office_venture.strip():
        return REFUSED_ANOTHER_VENTURE
    exists = (
        await session.execute(select(OperationRun.id).where(OperationRun.runRef == run_ref))
    ).first()
    return None if exists is not None else REFUSED_UNKNOWN_RUN


async def read_for_office(
    session: AsyncSession,
    *,
    run_ref: str,
    office_venture: str | None,
    office_agent_id: str | None,
    office_trace: str | None,
    forge_request_id: str,
) -> OfficeRead:
    """The run's stored answers for The Office, or a refusal. Audited and committed either way."""
    refusal = await _refusal(session, run_ref, office_venture)
    answers: list[dict[str, Any]] | None = None
    if refusal is None:
        rows = (
            (
                await session.execute(
                    select(SubmittedProbeAnswer)
                    .where(SubmittedProbeAnswer.runRef == run_ref)
                    .order_by(
                        SubmittedProbeAnswer.moduleId,
                        SubmittedProbeAnswer.scenarioClass,
                        SubmittedProbeAnswer.ordinal,
                        SubmittedProbeAnswer.attempt,
                    )
                )
            )
            .scalars()
            .all()
        )
        answers = [
            dict(
                zip(
                    ANSWER_KEYS,
                    (
                        r.scenarioRef,
                        r.scenarioClass,
                        r.ordinal,
                        r.attempt,
                        r.seed,
                        r.verdict,
                        list(r.reasons or []),
                        r.answerText,
                    ),
                    strict=True,
                )
            )
            for r in rows
        ]
    session.add(
        SubmittedAnswerRead(
            runRef=run_ref,
            officeVenture=office_venture,
            officeAgentId=office_agent_id,
            officeTrace=office_trace,
            forgeRequestId=forge_request_id,
            outcome="refused" if refusal else "returned",
            refusal=refusal,
            answersReturned=len(answers or []),
        )
    )
    await session.commit()
    return OfficeRead(run_ref=run_ref, answers=answers, refusal=refusal)


__all__ = [
    "ANSWER_KEYS",
    "HeldOutAnswerRefused",
    "OfficeRead",
    "REFUSED_ANOTHER_VENTURE",
    "REFUSED_NOT_OFFICE_MINTED",
    "REFUSED_NO_VENTURE",
    "REFUSED_UNKNOWN_RUN",
    "read_for_office",
    "record_submitted_answer",
]
