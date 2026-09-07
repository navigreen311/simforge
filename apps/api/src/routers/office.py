"""The Office bridge — what SimForge dispatches, and the one brokered call it serves.

Ported from `medlink-wholesale/backend/app/api/forge.py` (CRE Forge), which
`theoffice/docs/forge-adapter.md` names as the template. The parts that look like
boilerplate are the parts that were learned by making real calls fail silently; they are
copied rather than re-derived.

WHY THE CREDENTIAL IS CHECKED HERE AND NOT BY `AUTH_MODE`
=========================================================

    This surface authenticates a *tenant*, not a user. SimForge's `AUTH_MODE` offers
    `dev-bypass` — which returns a fixed principal holding every role and never looks at
    the Authorization header — and `clerk`, which verifies a user's RS256 JWT. Neither is
    a machine credential, and the first is actively dangerous here: an adapter that
    deferred to `require_role` would, on the local default, serve the agent-facing surface
    of this Forge to any caller at all.

    So the check is `hmac.compare_digest` against `OFFICE_TENANT_TOKEN`, and it is
    performed on both endpoints. `/_modules` is not public: it names the agent-facing
    surface of the Forge, which is not something to hand to an unauthenticated caller.

WHAT `/_modules` IS FOR, AND THE ONE THING IT CANNOT DO
=======================================================

    The Office's `forge_module_registry` rows are rows a human wrote and a Pack's
    `modules_expected` is a list a human wrote. Comparing those two compares two claims.
    This endpoint is different in exactly one way: `sorted(MODULES)` is *derived* by
    iterating the dispatch map, so a name is in the answer if and only if a handler is
    bound to it. You cannot add the name without adding the function.

    **It proves a handler is bound. It proves nothing about what the handler does.** A
    module returning a plausible 200 for work that never happened appears in this list
    exactly like one that does its job. That is why `run_scenario_pack` is NOT bound
    here — see below.

WHY `run_scenario_pack` IS ABSENT
=================================

    The Burkham Pack declares `modules_expected: [run_scenario_pack, gate_result]`.
    `gate_result` is bound and `run_scenario_pack` is deliberately not, so V32 FAILs on
    that name. `submit_curriculum` and `run_start` are bound alongside them and are not
    on the Pack at all — a module the Forge dispatches and the registry has not heard of
    is reported by `verify_forge_modules` as DRIFT, and it is reported so somebody
    decides, because a Forge does not get to enlarge its own agent-facing surface by
    answering.

    SimForge has no pack-level unit of execution. `run_scenario` takes ONE
    `scenario_id`; a Pack is a filter on runs or a scenario's parent, and nothing
    iterates a Pack's scenarios into runs. The only handler that could be written today
    would run one scenario and report having run a pack — a plausible 200, invisible to
    the check above, and the same failure that took `lender_match` and `build_packet` off
    that Pack.

    A true FAIL naming the gap beats a green check over a handler that overclaims. The
    reasoning is `theoffice/docs/decisions.md`, entry 5; ADR-0044 is the run window this
    module reads from.
"""

from __future__ import annotations

import hmac
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import ValidationError
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_session
from src.routers.operation import start_operation_run, submit_curriculum
from src.schemas.operation_payloads import (
    ForgeOperationCurriculum,
    OperationRunStartRequest,
)
from src.services.operation.run_registry import gate_result_for

logger = logging.getLogger(__name__)

router = APIRouter()

# --- The contract, copied from `theoffice/broker/executor.py` -------------------------------
#
# Copied, not inferred. The first adapter built against this read `X-Office-Trace-Id`;
# FastAPI bound it to None on every request, the call returned 200, the ledger row was
# written, and the correlation id that joins The Office's ledger to this Forge's logs was
# silently absent. A header read under the wrong name does not fail — it reads as absent.

HEADER_AGENT = "X-Office-Agent-Id"
HEADER_VENTURE = "X-Office-Venture"
HEADER_TRACE = "X-Office-Trace"  # NOT -Trace-Id
HEADER_API_VERSION = "X-Office-Forge-Api-Version"
HEADER_IDEMPOTENCY = "Idempotency-Key"

#: Written on every response. The Office stores it as `agent_call_ledger.forge_side_ref`,
#: and that pair is what makes a call traceable from either end. Both sides return 200
#: without it, so it is asserted in the tests rather than assumed.
HEADER_REQUEST_ID = "X-Forge-Request-Id"

#: The API version this adapter speaks, pinned (`forge_registry` rejects 'latest').
#: This is the ADAPTER's contract version and is SimForge's own — distinct from the
#: `forge_api_version` in the operation payloads, which is the version of whichever Forge
#: is being *certified*. Matches `pyproject.version` / `APP_VERSION`.
API_VERSION = "1.0.0"

#: The three values `forge_module_registry.idempotency_support` accepts.
IdempotencySupport = Literal["key", "natural", "at_most_once"]

Handler = Callable[[AsyncSession, dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ModuleSpec:
    """A bound module and the two things The Office decides on.

    `module_id` is derived — it is this dict's key. `is_mutating` and
    `idempotency_support` are *declared* at the binding site: you cannot bind without
    stating them, and they live beside the handler rather than in another system's table,
    but they are still somebody's word. `is_mutating` is checked at runtime by
    `call_module`, which is the only moment its truth is observable.
    """

    handler: Handler
    is_mutating: bool
    idempotency_support: IdempotencySupport


# --- Handlers -------------------------------------------------------------------------------


async def _gate_result(session: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    """The verdict of a certification run, by `run_ref`.

    A pure read. It returns exactly the fields The Office's
    `broker/simforge_response_manifest.json` declares for `get_gate_result`, because
    `validate_response` refuses a response carrying a field nobody enumerated — a check
    that exists so a new field cannot arrive unreviewed. Adding a key here without adding
    it there breaks the call on arrival.

    A run still open past its window answers TIMEOUT rather than IN_PROGRESS even if the
    sweep has not stamped it: the answer must not depend on how recently a background job
    ran. See ADR-0044.
    """
    run_ref = payload.get("run_ref")
    if not isinstance(run_ref, str) or not run_ref:
        raise HTTPException(
            status_code=422,  # unprocessable content
            detail="gate_result requires a non-empty string 'run_ref' in the payload",
        )

    body = await gate_result_for(session, run_ref)
    if body is None:
        # Not a NOT_RUN body: that shape needs a `unit` and a `rubric_version` SimForge
        # does not have for a run it never received, and a shape-valid answer built out
        # of guesses is worse than an honest refusal.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SimForge has no record of run_ref {run_ref!r}",
        )
    return body


def _validated(model: type, payload: dict[str, Any], module_id: str):
    """Parse a brokered payload into the model the endpoint already declares.

    The endpoint's own signature is the schema. Re-stating it here would be a second
    declaration of the same shape, and the two would disagree the first time one changed —
    the defect `forge_module_registry` rows have twice, one table over.
    """
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,  # unprocessable content
            detail={
                "error": f"{module_id}_payload_invalid",
                # Pydantic's own errors, which name the field and the rule. A summary
                # would be a worse message that somebody has to maintain.
                "violations": exc.errors(include_url=False),
            },
        ) from exc


async def _submit_curriculum(session: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    """The Office hands over a curriculum. `POST /api/operation/curriculum`.

    REACHED WITH THE TENANT CREDENTIAL, NOT AN AGENT GRANT
    ======================================================

        Every other module on this adapter answers a question about one agent. This one
        does not: **The Office submits a curriculum on behalf of a VENTURE**, before any
        agent is certified to do anything, and often before the agents exist. There is no
        `office_agent_id` whose grant could authorize it, and inventing one would put a
        fictional agent in the ledger for an act a human and a venture performed.

        So the credential that reaches it is the tenant credential — which is what
        authenticates this whole surface anyway. `X-Office-Venture` is the identity that
        matters for this call, and it is recorded in the log line like every other header.

        The consequence worth stating: **an agent grant is not what gates this.** The
        Office decides who may submit a curriculum on its own side; SimForge checks that
        the caller holds the tenant credential and then validates the curriculum itself,
        which is the check that actually protects anything here (Batch-3 rules, 422 on
        any violation).

    Calls the endpoint function rather than re-implementing it, for the same reason CRE
    Forge's adapter calls its service layer: a second implementation of the validation
    and the instruction-set upsert is a second thing to keep correct.
    """
    body = _validated(ForgeOperationCurriculum, payload, "submit_curriculum")
    return await submit_curriculum(body=body, session=session)


async def _run_start(session: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
    """A battery is starting. `POST /api/operation/run/start`.

    Without this reaching The Office, the run window is unreachable from the outside: the
    row that makes a hung battery observable is written here, and ADR-0044 exists because
    there was no such row. Binding `gate_result` and not this one would have left The
    Office able to ask for a verdict on a run it had no way to open.
    """
    body = _validated(OperationRunStartRequest, payload, "run_start")
    started = await start_operation_run(body=body, session=session)
    # `mode="json"` because `started_at` is a datetime and the response crosses HTTP.
    return started.model_dump(mode="json")


#: module_id -> spec. A dict rather than a chain of ifs because The Office's registry is
#: also a table: a module SimForge does not implement should 404 with the module named,
#: not fall through to something that half works.
#:
#: `run_scenario_pack` is deliberately absent. See the module docstring.
MODULES: dict[str, ModuleSpec] = {
    "gate_result": ModuleSpec(
        _gate_result,
        # A read. The run row is written by `POST /api/operation/run/start` and closed by
        # `POST /api/operation/gate-result`; this only reports what they recorded.
        is_mutating=False,
        # The same run_ref returns the same verdict, so a retry lands on the same answer
        # without a key. `natural`, not `key`.
        idempotency_support="natural",
    ),
    "submit_curriculum": ModuleSpec(
        _submit_curriculum,
        # Writes: upserts the bound `ForgeInstructionSet`.
        is_mutating=True,
        # `natural`, and it is earned rather than defaulted. The upsert is keyed on
        # (forgeId, moduleId, contentHash), so re-posting the same curriculum lands on the
        # same row and does not accumulate a second instruction set. A different
        # content_hash is a different instruction set and SHOULD produce a new row — that
        # is not a retry, it is a new submission.
        idempotency_support="natural",
    ),
    "run_start": ModuleSpec(
        _run_start,
        # Writes: opens the `OperationRun` row.
        is_mutating=True,
        # `natural`, and this one is the clearest case on the adapter. `open_run` is
        # idempotent on `run_ref` and returns the existing row with its clock UNTOUCHED —
        # a re-post answers `already_open: true` rather than restarting the window. That
        # refusal is what makes `natural` honest here: an at-most-once module would need a
        # key precisely because a second call would do damage, and a second call here
        # cannot, by construction. Extending the window of a run that is already hanging is
        # the one thing that would hide a timeout, and `open_run` exists partly to refuse
        # it (ADR-0044).
        idempotency_support="natural",
    ),
}

# A module id is a path segment in `{base_url}/{module_id}`, so the `_` prefix is reserved
# for the adapter's own endpoints. Asserted at import rather than documented, because a
# module named `_modules` would shadow the manifest and the first symptom would be a
# conformance check reporting the wrong thing.
assert not any(name.startswith("_") for name in MODULES), (
    "module ids must not start with '_': that prefix is reserved for adapter endpoints"
)


# --- The tenant credential ------------------------------------------------------------------


def _require_tenant_credential(authorization: str | None) -> None:
    """Refuse anyone who cannot present the tenant credential. The only thing this
    adapter refuses.

    Not configured is a 503, not an open door. A Forge holding no tenant credential is a
    Forge that has not been onboarded, and treating that as "allow everything" is how an
    unauthenticated surface reaches production.
    """
    expected = settings.office_tenant_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OFFICE_TENANT_TOKEN is not configured; this Forge is not onboarded",
        )

    presented = ""
    if authorization and authorization.lower().startswith("bearer "):
        presented = authorization[7:]

    # Constant-time: a token compared with `==` leaks its prefix to anyone willing to time
    # the responses.
    if not hmac.compare_digest(presented, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing tenant credential",
        )


# --- Endpoints ------------------------------------------------------------------------------


@router.get("/_modules")
async def list_modules(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """What this adapter dispatches. The Office resolves a Pack against this.

    **Never replace `sorted(MODULES.items())` with a literal list.** A list maintained
    beside the dict is a third declaration, and a worse one than the two that already
    exist, because it would drift silently while carrying the authority of having come
    from the Forge. `test_manifest_is_derived_from_the_dispatch_map` fails the build if
    it does.

    These keys are the naming authority for this Forge. The Office's registry rows, a
    Pack's `modules_expected` and `broker.module_exclusions` must spell a module the way
    it is spelled here or they do not resolve against it — and an exclusion that does not
    resolve is an endpoint that quietly becomes grantable under a second name.
    """
    _require_tenant_credential(authorization)
    return {
        "forge": "simforge",
        "api_version": API_VERSION,
        "modules": [
            {
                "module_id": module_id,
                "is_mutating": spec.is_mutating,
                "idempotency_support": spec.idempotency_support,
            }
            for module_id, spec in sorted(MODULES.items())
        ],
    }


@router.post("/{module_id}")
async def call_module(
    module_id: str,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
    x_office_agent_id: str | None = Header(default=None),
    x_office_venture: str | None = Header(default=None),
    x_office_trace: str | None = Header(default=None),
    x_office_forge_api_version: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None),
) -> dict[str, Any]:
    """One brokered call from The Office."""
    _require_tenant_credential(authorization)

    spec = MODULES.get(module_id)
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"SimForge dispatches no module {module_id!r}. "
                "GET /_modules lists what it does."
            ),
        )

    request_id = str(uuid.uuid4())
    origin = {
        "forge_request_id": request_id,
        "module_id": module_id,
        "office_agent_id": x_office_agent_id,
        "office_venture": x_office_venture,
        "office_trace": x_office_trace,
        # Recorded beside the adapter's own version rather than compared against it. The
        # Office's `forge_registry.api_version` is what reaches us; a disagreement is a
        # fact worth having in both logs, not a reason to refuse a call.
        "office_api_version": x_office_forge_api_version,
        "adapter_api_version": API_VERSION,
        "idempotency_key": idempotency_key,
    }

    try:
        payload = await request.json()
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    logger.info("office.call.received %s", origin)

    # A module declared read-only that wrote is refused, and the write is rolled back
    # rather than left for the next commit to pick up.
    #
    # `is_mutating` is the field The Office's V31 keys on when it decides whether an
    # unattended agent may hold this module at auto_execute. A declaration nothing checks
    # is the same shape as the registry row this replaced, so it is checked here, at the
    # only moment the truth is observable.
    #
    # DIVERGENCE FROM THE CRE TEMPLATE, ON PURPOSE. That version inspects
    # `session.new/dirty/deleted` after the handler returns, which catches a handler that
    # called `session.add()` and nothing else. **It does not catch a handler that
    # flushed** — a flush moves objects out of `new` and leaves those collections empty,
    # so the check reads clean on a write that has already reached the database and is one
    # commit away from being permanent. `open_run` and most of this codebase's service
    # functions flush, so the template's check would have passed every one of them.
    # `test_a_read_declared_module_that_writes_is_refused` fails against the template.
    flushed = False

    def _on_flush(*_: Any) -> None:
        # SQLAlchemy skips the flush entirely when there is nothing to write, so this
        # firing at all is the signal.
        nonlocal flushed
        flushed = True

    listening = not spec.is_mutating
    if listening:
        event.listen(session.sync_session, "after_flush", _on_flush)
    try:
        result = await spec.handler(session, payload)
    finally:
        if listening:
            event.remove(session.sync_session, "after_flush", _on_flush)

    if not spec.is_mutating and (
        flushed or session.new or session.dirty or session.deleted
    ):
        pending = len(session.new) + len(session.dirty) + len(session.deleted)
        await session.rollback()
        logger.error(
            "office.call.contract_violation %s pending=%d flushed=%s", origin, pending, flushed
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                f"module {module_id!r} is declared is_mutating=False and wrote to its "
                f"session (pending={pending}, flushed={flushed}). The write was rolled "
                "back. Fix the handler or correct the declaration — The Office grants "
                "unattended access on the strength of that field."
            ),
        )

    logger.info("office.call.completed %s", origin)

    # The Office stores this against the ledger row as `forge_side_ref`, which is what
    # makes a call traceable from either end.
    response.headers[HEADER_REQUEST_ID] = request_id
    return result
