"""Add agents to the roster — single + bulk. Guardrail: floor autonomy, zero certs, no fabrication.

A new agent ALWAYS starts at the autonomy floor (L1) with no certs; there is no way to set autonomy
here, so "add agent" cannot be a backdoor around the certification gate. Bulk import validates each
row and never invents a missing value — an invalid row is reported and skipped, a duplicate id is
skipped ("already in roster"), never overwritten.
"""

from __future__ import annotations

import re

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.models.department import Department
from src.schemas.agent import BulkAgentRow, BulkRowResult
from src.services.cert.autonomy_ladder import FLOOR
from src.telemetry.logging import get_logger

log = get_logger("agent_admin")


class AgentAdminError(Exception):
    """A single-agent add was invalid (bad input)."""


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", name.strip().lower()).strip("_")


def parse_flags(raw: str) -> tuple[bool, bool]:
    """(gardnerFlag, level10Enabled) parsed from a free-text flags cell like 'gardner; l10'."""
    tokens = {t.strip().lower() for t in re.split(r"[,;| ]+", raw or "") if t.strip()}
    return ("gardner" in tokens, bool({"l10", "level10", "level_10"} & tokens))


async def resolve_department(session: AsyncSession, value: str) -> Department | None:
    """Match a department by id, villageKey, or name (case-insensitive) — no fuzzy guessing."""
    v = (value or "").strip()
    if not v:
        return None
    row = (
        await session.execute(
            select(Department).where(
                or_(
                    Department.id == v,
                    Department.villageKey == v,
                    Department.name == v,
                )
            )
        )
    ).scalar_one_or_none()
    if row is not None:
        return row
    # case-insensitive name/key fallback
    lower = v.lower()
    return (
        await session.execute(
            select(Department).where(
                or_(
                    Department.villageKey.ilike(lower),
                    Department.name.ilike(lower),
                )
            )
        )
    ).scalar_one_or_none()


async def _village_id_taken(session: AsyncSession, vid: str) -> bool:
    return (
        await session.execute(select(Agent.id).where(Agent.villageAgentId == vid))
    ).scalar_one_or_none() is not None


async def create_agent(
    session: AsyncSession,
    *,
    name: str,
    department_id: str,
    village_agent_id: str | None,
    role: str,
    gardner_flag: bool,
    level10_enabled: bool,
    actor: str,
) -> Agent:
    """Create one agent at the autonomy floor. Raises AgentAdminError on invalid input."""
    name = (name or "").strip()
    if not name:
        raise AgentAdminError("Name is required.")
    dept = (
        await session.execute(select(Department).where(Department.id == department_id))
    ).scalar_one_or_none()
    if dept is None:
        raise AgentAdminError(f"Unknown department '{department_id}'.")
    vid = (village_agent_id or "").strip() or slugify(name)
    if not vid:
        raise AgentAdminError("Could not derive an id from the name; provide one explicitly.")
    if await _village_id_taken(session, vid):
        raise AgentAdminError(f"Agent id '{vid}' already exists.")

    agent = Agent(
        villageAgentId=vid,
        name=name,
        role=(role or "").strip(),
        departmentId=dept.id,
        gardnerFlag=gardner_flag,
        level10Enabled=level10_enabled,
        currentAutonomyLevel=FLOOR,  # floor — earns higher levels through certification
    )
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    log.info("agent_added", agent=vid, dept=dept.villageKey, by=actor, mode="single")
    return agent


async def bulk_import(
    session: AsyncSession, rows: list[BulkAgentRow], actor: str
) -> list[BulkRowResult]:
    """Validate + import valid rows at floor autonomy. Never fabricates or overwrites."""
    results: list[BulkRowResult] = []
    seen_ids: set[str] = set()

    for i, row in enumerate(rows):
        name = (row.name or "").strip()
        if not name:
            results.append(
                BulkRowResult(index=i, name=name, status="error", reason="Missing name.")
            )
            continue

        vid = (row.id or "").strip() or slugify(name)
        if not vid:
            results.append(
                BulkRowResult(index=i, name=name, status="error", reason="Could not derive an id.")
            )
            continue

        if vid in seen_ids:
            results.append(
                BulkRowResult(
                    index=i,
                    name=name,
                    villageAgentId=vid,
                    status="skipped",
                    reason="Duplicate id within this import.",
                )
            )
            continue

        dept = await resolve_department(session, row.department)
        if dept is None:
            results.append(
                BulkRowResult(
                    index=i,
                    name=name,
                    villageAgentId=vid,
                    status="error",
                    reason=f"Unknown department '{row.department}'.",
                )
            )
            continue

        if await _village_id_taken(session, vid):
            results.append(
                BulkRowResult(
                    index=i,
                    name=name,
                    villageAgentId=vid,
                    status="skipped",
                    reason="Already in roster.",
                )
            )
            continue

        gardner, l10 = parse_flags(row.flags)
        session.add(
            Agent(
                villageAgentId=vid,
                name=name,
                role=(row.role or "").strip(),
                departmentId=dept.id,
                gardnerFlag=gardner,
                level10Enabled=l10,
                currentAutonomyLevel=FLOOR,
            )
        )
        seen_ids.add(vid)
        results.append(BulkRowResult(index=i, name=name, villageAgentId=vid, status="imported"))

    await session.commit()
    imported = sum(1 for r in results if r.status == "imported")
    log.info("agents_bulk_imported", imported=imported, total=len(rows), by=actor)
    return results
