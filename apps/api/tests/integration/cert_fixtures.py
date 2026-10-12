"""Stand up an AgentCert for a test, now that no route can issue one (ADR-0158).

Issuance and reinstatement from a `Run` battery are refused: every `Run` is a practice run, and a
certificate issued from practice runs is not a certification. Certs issued before ADR-0158 still
exist, and the features that read certs (PDP, PEP, drift, CRL, incidents, training, waivers) still
have to work on them. These helpers stand one up through the retained machinery
(`registry._issue_from_runs`), so the row, its signed snapshot, evidence and lineage are what
issuance produced, not a hand-built imitation.

They are a test's way to say "this cert exists". They are not a path production can take.

The return value has the shape `POST /api/certs/agent/issue` returned, so a test that read the
response reads this the same way.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.cert import AgentCertOut, CertSnapshotOut, IssueCertResponse
from src.services.cert.registry import IssuedCert, _issue_from_runs, _reinstate_from_runs


def _as_response(issued: IssuedCert) -> dict:
    return IssueCertResponse(
        cert=AgentCertOut.model_validate(issued.agent_cert),
        snapshot=CertSnapshotOut.model_validate(issued.snapshot),
        autonomy_from=issued.autonomy_from,
        autonomy_to=issued.autonomy_to,
    ).model_dump(mode="json")


async def stand_up_cert(
    session: AsyncSession,
    *,
    agent_village_id: str,
    forge_cap: str,
    tier: str,
    battery_run_ids: list[str],
    approver_id: str = "ivan",
    pack_id: str = "pack.greenstone.v1",
) -> dict:
    """An existing cert, as issuance made it before ADR-0158. Raises CertIssuanceError as it did."""
    issued = await _issue_from_runs(
        session,
        agent_village_id=agent_village_id,
        forge_cap=forge_cap,
        tier=tier,
        battery_run_ids=battery_run_ids,
        approver_id=approver_id,
        pack_id=pack_id,
    )
    return _as_response(issued)


async def stand_up_reinstatement(
    session: AsyncSession, cert_id: str, battery_run_ids: list[str], approver_id: str = "ivan"
) -> dict:
    """A reinstatement as it was made before ADR-0158."""
    return _as_response(await _reinstate_from_runs(session, cert_id, battery_run_ids, approver_id))
