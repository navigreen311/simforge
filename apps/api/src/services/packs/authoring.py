"""Create / edit a Pack from committed Scenario-Bank scenarios (Part B).

A Pack is a curated bundle of EXISTING committed scenarios plus venture + compliance metadata. This
service is the ONLY way to author a pack from a form; it upholds the guardrails:

  * Only COMMITTED bank scenarios may enter a pack (draft/AI-drafted are rejected) — a pack is a
    certification instrument, built from reviewed material only.
  * Creating a pack does NOT certify anyone and does NOT run anything — it defines the library.
  * Editing creates a NEW version (pack.{venture}.v{n+1}) that supersedes the old; the old version
    is preserved untouched, so certs pinned to it keep resolving.

Mechanism: the form is materialized to `pack.yml` + `scenarios/*.yml` under packs_root, then run
through the SAME validator + `ingest_pack` path as a hand-authored pack — so the created pack passes
jurisdiction-coverage / PHI validation, gets a real yamlHash (which certs pin to), and flows into
Runs / Certifications / Lineage indistinguishably from an existing pack. The bank scenario provides
the CONTENT (title, tier, situation→cold_open, expectedBehaviors→compliance_checks); the pack build
provides the certification binding the bank does not carry (tested agent, SLO, forge caps, golden).
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.bank_scenario import BankScenario
from src.models.pack import Pack, Scenario
from src.schemas.pack import PackCreateRequest, PackScenarioInput
from src.services.packs.ingestion import ingest_pack

_PACK_ID_RE = re.compile(r"^pack\.([a-z0-9_-]+)\.v(\d+)$")
_VENTURE_RE = re.compile(r"^[a-z0-9_-]+$")


class AuthoringError(Exception):
    """A pack could not be authored (bad input or a guardrail violation)."""


@dataclass
class AuthoringResult:
    ok: bool
    pack_id: str
    scenario_count: int
    issues: list[dict]
    error: str | None = None


def _slug(venture: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", venture.strip().lower()).strip("-")


def pack_id_for(venture: str, major: int) -> str:
    return f"pack.{_slug(venture)}.v{major}"


def _pack_dir(pack_id: str) -> Path:
    m = _PACK_ID_RE.match(pack_id)
    if not m:
        raise AuthoringError(f"Invalid pack id '{pack_id}' (must match pack.<venture>.v<n>).")
    venture, major = m.group(1), m.group(2)
    # Absolute so ingest_pack (which resolves relative dirs against packs_root) won't double-prefix.
    return (Path(settings.packs_root) / venture / f"v{major}").resolve()


async def _committed_bank_scenarios(
    session: AsyncSession, scenario_ids: list[str]
) -> dict[str, BankScenario]:
    """Return {scenarioId: BankScenario} for committed ids; raise if any is not committed."""
    rows = (
        (
            await session.execute(
                select(BankScenario).where(BankScenario.scenarioId.in_(scenario_ids))
            )
        )
        .scalars()
        .all()
    )
    by_id = {r.scenarioId: r for r in rows if r.scenarioId}
    problems = []
    for sid in scenario_ids:
        row = by_id.get(sid)
        if row is None:
            problems.append(f"{sid} (not found in the Scenario Bank)")
        elif row.status != "committed":
            problems.append(f"{sid} (status '{row.status}', not committed)")
    if problems:
        raise AuthoringError(
            "Only committed scenarios can enter a pack. Rejected: " + "; ".join(problems)
        )
    return by_id


def _scenario_dict(bank: BankScenario, inp: PackScenarioInput) -> dict:
    """Map a committed bank scenario + its pack-build binding into a ScenarioSpec dict."""
    return {
        "scenario_id": bank.scenarioId,
        "title": bank.title,
        "tier": bank.tier,
        "tested_agent_village_id": inp.testedAgentVillageId,
        "tested_forge_caps": list(inp.testedForgeCaps),
        "training_domains": list(inp.trainingDomains),
        "seed": inp.seed,
        "slo_seconds": inp.sloSeconds,
        # expectedBehaviors are the checks a passing agent must satisfy.
        "compliance_checks": list(bank.expectedBehaviors),
        # the bank's situation is the scenario the agent faces.
        "cold_open": bank.situation,
        "is_golden": inp.isGolden,
    }


def _pack_dict(req: PackCreateRequest, pack_id: str, owner_human: str) -> dict:
    return {
        "pack_id": pack_id,
        "name": req.title.strip(),
        "version": req.version,
        "owner_venture": _slug(req.ownerVenture),
        "owner_human": owner_human,
        "phi_required": req.phiRequired,
        "compliance_flags": list(req.complianceFlags),
        "integrated_runs_allowed": False,
        "execution_mode_default": req.executionModeDefault,
        "narrative_mode_default": "protected",
        "locale": "en",
        "rubric_profile": req.rubricProfile,
        "readiness_gate": {
            "tier_thresholds": {"F": 0.70, "I": 0.80, "AC": 0.85},
            "cognitive_aggregate_min": 0.75,
            "blind_mode_pct": 0.25,
            "arc_fragmentation_auto_fail": True,
            "compliance_require_pass": True,
        },
    }


def _write_pack_files(pack_dir: Path, pack_dict: dict, scenario_dicts: list[dict]) -> None:
    (pack_dir / "scenarios").mkdir(parents=True, exist_ok=True)
    with (pack_dir / "pack.yml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(pack_dict, f, sort_keys=False, allow_unicode=True)
    for sd in scenario_dicts:
        with (pack_dir / "scenarios" / f"{sd['scenario_id']}.yml").open("w", encoding="utf-8") as f:
            yaml.safe_dump(sd, f, sort_keys=False, allow_unicode=True)


async def _materialize(
    session: AsyncSession,
    req: PackCreateRequest,
    pack_id: str,
    owner_human: str,
    supersedes_pack_id: str | None,
) -> AuthoringResult:
    if not req.scenarios:
        raise AuthoringError("A pack needs at least one scenario.")

    scenario_ids = [s.scenarioId for s in req.scenarios]
    if len(set(scenario_ids)) != len(scenario_ids):
        raise AuthoringError("The same scenario was added more than once.")

    # Guardrail: committed scenarios only.
    bank = await _committed_bank_scenarios(session, scenario_ids)

    # A scenario id is globally unique in the runtime Scenario table → a committed scenario can be
    # materialized into at most one pack. Reject collisions with a clear message up front.
    taken = (
        await session.execute(
            select(Scenario.scenarioId, Pack.packId)
            .join(Pack, Scenario.packId == Pack.id)
            .where(Scenario.scenarioId.in_(scenario_ids))
        )
    ).all()
    if taken:
        detail = "; ".join(f"{sid} (already in {pid})" for sid, pid in taken)
        raise AuthoringError(f"These scenarios are already used in another pack: {detail}")

    pack_dir = _pack_dir(pack_id)
    pack_dict = _pack_dict(req, pack_id, owner_human)
    scenario_dicts = [_scenario_dict(bank[s.scenarioId], s) for s in req.scenarios]

    _write_pack_files(pack_dir, pack_dict, scenario_dicts)
    try:
        result = await ingest_pack(session, str(pack_dir))
    except Exception:
        shutil.rmtree(pack_dir, ignore_errors=True)  # don't leave invalid YAML behind
        raise

    if not result.ok:
        # Validation failed → no Pack row was written; remove the generated files.
        shutil.rmtree(pack_dir, ignore_errors=True)
        return AuthoringResult(False, pack_id, len(req.scenarios), result.issues)

    if supersedes_pack_id:
        pack = (
            await session.execute(select(Pack).where(Pack.packId == pack_id))
        ).scalar_one_or_none()
        if pack is not None:
            pack.supersedesPackId = supersedes_pack_id
            await session.commit()

    return AuthoringResult(True, pack_id, result.scenario_count, result.issues)


async def create_pack(
    session: AsyncSession, req: PackCreateRequest, owner_human: str
) -> AuthoringResult:
    """Create a brand-new pack (pack.{venture}.v1 unless a higher version is requested)."""
    m = _VENTURE_RE.match(_slug(req.ownerVenture))
    if not m:
        raise AuthoringError("Venture must be lowercase letters, numbers, hyphens or underscores.")
    major = 1
    vm = re.match(r"^(\d+)", req.version)
    if vm:
        major = int(vm.group(1))
    pack_id = pack_id_for(req.ownerVenture, major)

    existing = (
        await session.execute(select(Pack).where(Pack.packId == pack_id))
    ).scalar_one_or_none()
    if existing is not None:
        raise AuthoringError(
            f"Pack '{pack_id}' already exists. Edit it to create a new version instead."
        )
    return await _materialize(session, req, pack_id, owner_human, supersedes_pack_id=None)


async def new_version(
    session: AsyncSession, base_pack_id: str, req: PackCreateRequest, owner_human: str
) -> AuthoringResult:
    """Author the next version of an existing pack; the old version is preserved and superseded."""
    m = _PACK_ID_RE.match(base_pack_id)
    if not m:
        raise AuthoringError(f"Invalid base pack id '{base_pack_id}'.")
    base = (
        await session.execute(select(Pack).where(Pack.packId == base_pack_id))
    ).scalar_one_or_none()
    if base is None:
        raise AuthoringError(f"Base pack '{base_pack_id}' not found.")

    venture, old_major = m.group(1), int(m.group(2))
    new_major = old_major + 1
    new_pack_id = f"pack.{venture}.v{new_major}"
    req.version = f"{new_major}.0.0"
    req.ownerVenture = venture
    return await _materialize(
        session, req, new_pack_id, owner_human, supersedes_pack_id=base_pack_id
    )
