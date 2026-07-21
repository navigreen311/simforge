"""Ingest a Pack directory: load → validate → upsert Pack + Scenarios + ReadinessGate.

Uses the shared `validator` package as the single source of truth for Pack/Scenario
schemas and rules (blueprint §A.5, §C.3.4).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from validator import load_pack, validate_pack
from validator.loader import LoadedPack, PackLoadError

from src.config import settings
from src.models.pack import Pack, ReadinessGate, Scenario


class IngestionError(Exception):
    """Raised when a Pack cannot be located or fails hard validation."""


@dataclass
class IngestResult:
    ok: bool
    pack_id: str
    scenario_count: int
    issues: list[dict]


def _resolve_pack_dir(pack_dir: str) -> Path:
    p = Path(pack_dir)
    if p.is_absolute():
        return p
    return Path(settings.packs_root) / p


def _apply_spec(pack: Pack, loaded: LoadedPack) -> None:
    spec = loaded.spec
    pack.packId = spec.pack_id
    pack.name = spec.name
    pack.version = spec.version
    pack.ownerVenture = spec.owner_venture
    pack.ownerHuman = spec.owner_human
    pack.phiRequired = spec.phi_required
    pack.complianceFlags = list(spec.compliance_flags)
    pack.integratedRunsAllowed = spec.integrated_runs_allowed
    pack.executionModeDefault = spec.execution_mode_default
    pack.narrativeModeDefault = spec.narrative_mode_default
    pack.rubricProfile = spec.rubric_profile
    pack.yamlPath = loaded.pack_yaml_path
    pack.yamlHash = loaded.pack_yaml_hash


def _build_scenarios(loaded: LoadedPack) -> list[Scenario]:
    scenarios: list[Scenario] = []
    for ls in loaded.scenarios:
        s = ls.spec
        scenarios.append(
            Scenario(
                scenarioId=s.scenario_id,
                title=s.title,
                tier=s.tier,
                testedAgentVillageId=s.tested_agent_village_id,
                testedForgeCaps=list(s.tested_forge_caps),
                trainingDomains=list(s.training_domains),
                seed=s.seed,
                yamlPath=ls.yaml_path,
                yamlHash=ls.yaml_hash,
                sloSeconds=s.slo_seconds,
                complianceChecks=list(s.compliance_checks),
                isGolden=s.is_golden,
            )
        )
    return scenarios


def _build_gate(loaded: LoadedPack) -> ReadinessGate:
    rg = loaded.spec.readiness_gate
    return ReadinessGate(
        tierThresholds=rg.tier_thresholds,
        cognitiveAggregateMin=rg.cognitive_aggregate_min,
        blindModePct=rg.blind_mode_pct,
        arcFragmentationAutoFail=rg.arc_fragmentation_auto_fail,
        complianceRequirePass=rg.compliance_require_pass,
    )


async def ingest_pack(session: AsyncSession, pack_dir: str) -> IngestResult:
    path = _resolve_pack_dir(pack_dir)
    try:
        loaded = load_pack(path)
    except PackLoadError as exc:
        raise IngestionError(str(exc)) from exc

    result = validate_pack(loaded)
    issues = [
        {"severity": i.severity, "code": i.code, "message": i.message, "location": i.location}
        for i in result.issues
    ]
    if not result.ok:
        return IngestResult(False, loaded.spec.pack_id, len(loaded.scenarios), issues)

    existing = (
        await session.execute(
            select(Pack)
            .where(Pack.packId == loaded.spec.pack_id)
            .options(selectinload(Pack.scenarios), selectinload(Pack.readinessGate))
        )
    ).scalar_one_or_none()

    if existing is None:
        pack = Pack()
        _apply_spec(pack, loaded)
        pack.scenarios = _build_scenarios(loaded)
        pack.readinessGate = _build_gate(loaded)
        session.add(pack)
    else:
        _apply_spec(existing, loaded)
        # Delete old children and flush before inserting new ones, so unique keys
        # (scenarioId, ReadinessGate.packId) don't collide mid-transaction.
        for scen in list(existing.scenarios):
            await session.delete(scen)
        if existing.readinessGate is not None:
            await session.delete(existing.readinessGate)
        await session.flush()
        existing.scenarios = _build_scenarios(loaded)
        existing.readinessGate = _build_gate(loaded)

    await session.commit()
    return IngestResult(True, loaded.spec.pack_id, len(loaded.scenarios), issues)
