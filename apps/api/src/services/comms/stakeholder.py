"""Stakeholder Communication layer (v1.2).

Translates the platform's technical state into a plain-language executive brief: headline status,
the numbers that matter (certs, open gaps by severity, venture readiness, forge-parity concerns),
a short narrative, and recommended actions. Every sentence is generated from live counts — no
fabricated confidence. (An LLM polish pass is a seam; the substance here is deterministic.)
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.cert import AgentCert
from src.models.gap import SoftwareGap, VillageOSGap
from src.services.forge.parity import parity_summary
from src.services.playbook.cold_start import all_playbooks


async def _count(session: AsyncSession, model, *where) -> int:  # noqa: ANN001
    stmt = select(func.count()).select_from(model)
    for w in where:
        stmt = stmt.where(w)
    return (await session.execute(stmt)).scalar_one()


async def portfolio_brief(session: AsyncSession) -> dict:
    active_certs = await _count(session, AgentCert, AgentCert.status == "active")
    total_certs = await _count(session, AgentCert)

    open_by_sev: dict[str, int] = {}
    for sev in ("P0", "P1", "P2"):
        n = await _count(
            session, SoftwareGap, SoftwareGap.status == "open", SoftwareGap.severity == sev
        )
        n += await _count(
            session, VillageOSGap, VillageOSGap.status == "open", VillageOSGap.severity == sev
        )
        open_by_sev[sev] = n
    open_total = sum(open_by_sev.values())

    playbooks = await all_playbooks(session)
    ventures_ready = sum(1 for p in playbooks if p["ready"])
    ventures_total = len(playbooks)
    sla_breached = [p["venture"] for p in playbooks if p["sla_status"] == "breached"]

    parity = await parity_summary(session)
    unsafe_forges = [p["forge_cap"] for p in parity if p["unsafe_to_certify"]]

    # Headline: red on any P0 gap or unsafe forge; amber on P1/SLA breach; else green.
    if open_by_sev["P0"] > 0 or unsafe_forges:
        headline = "Attention needed"
        tone = "red"
    elif open_by_sev["P1"] > 0 or sla_breached:
        headline = "On track with risks"
        tone = "amber"
    else:
        headline = "On track"
        tone = "green"

    narrative = (
        f"{active_certs} active certification(s) across {ventures_total} venture(s); "
        f"{ventures_ready} venture(s) have a certifiable v1 pack. "
        f"{open_total} open gap(s) ({open_by_sev['P0']} P0, {open_by_sev['P1']} P1). "
    )
    if unsafe_forges:
        narrative += (
            f"{len(unsafe_forges)} forge(s) are below the parity SLA and unsafe to certify. "
        )
    if sla_breached:
        narrative += f"{len(sla_breached)} venture(s) have breached the cold-start SLA. "
    if tone == "green":
        narrative += "No P0 gaps and all measured forges within parity SLA."

    actions: list[str] = []
    if open_by_sev["P0"] > 0:
        actions.append(f"Resolve {open_by_sev['P0']} P0 gap(s) before further certification.")
    if unsafe_forges:
        actions.append(f"Restore sandbox-vs-production parity for: {', '.join(unsafe_forges)}.")
    if sla_breached:
        actions.append(f"Escalate cold-start for: {', '.join(sla_breached)}.")
    if not actions:
        actions.append("Maintain cadence; no blocking risks surfaced.")

    return {
        "headline": headline,
        "tone": tone,
        "narrative": narrative.strip(),
        "metrics": {
            "active_certs": active_certs,
            "total_certs": total_certs,
            "open_gaps": open_by_sev,
            "open_gaps_total": open_total,
            "ventures_ready": ventures_ready,
            "ventures_total": ventures_total,
            "unsafe_forges": unsafe_forges,
            "sla_breached_ventures": sla_breached,
        },
        "recommended_actions": actions,
    }
