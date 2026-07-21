"""Persist and retrieve CCB snapshots (bridges CCBComposer ↔ the CCB table)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ccb import CCB as CCBModel
from src.services.village.ccb_composer import CCBComposer, CCBData, Phase
from src.services.village.reader import VillageReader


def _to_model(data: CCBData) -> CCBModel:
    fw = data.frameworks
    return CCBModel(
        snapshotId=data.snapshot_id,
        agentVillageId=data.agent_village_id,
        phase=data.phase,
        takenAt=data.taken_at,
        contentHash=data.content_hash,
        villageSchemaFingerprint=data.village_schema_fingerprint,
        game=fw.get("game", {}),
        mate=fw.get("mate", {}),
        soul=fw.get("soul", {}),
        breath=fw.get("breath", {}),
        fot=fw.get("fot", {}),
        hfm=fw.get("hfm", {}),
        arc=fw.get("arc", {}),
        echo=fw.get("echo", {}),
        drift=fw.get("drift", {}),
        ame=fw.get("ame", {}),
    )


def model_to_response_dict(row: CCBModel) -> dict:
    return {
        "snapshot_id": row.snapshotId,
        "agent_village_id": row.agentVillageId,
        "phase": row.phase,
        "taken_at": row.takenAt,
        "content_hash": row.contentHash,
        "village_schema_fingerprint": row.villageSchemaFingerprint,
        "frameworks": {
            "game": row.game,
            "mate": row.mate,
            "soul": row.soul,
            "breath": row.breath,
            "fot": row.fot,
            "hfm": row.hfm,
            "arc": row.arc,
            "echo": row.echo,
            "drift": row.drift,
            "ame": row.ame,
        },
    }


async def capture_ccb(
    session: AsyncSession,
    reader: VillageReader,
    agent_village_id: str,
    phase: Phase = "pre",
) -> CCBModel:
    """Compose a CCB from Village fs and persist it."""
    composer = CCBComposer(reader)
    data = composer.compose(agent_village_id, phase)
    row = _to_model(data)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def get_latest_ccb(
    session: AsyncSession, agent_village_id: str, phase: str | None = None
) -> CCBModel | None:
    stmt = select(CCBModel).where(CCBModel.agentVillageId == agent_village_id)
    if phase is not None:
        stmt = stmt.where(CCBModel.phase == phase)
    stmt = stmt.order_by(CCBModel.takenAt.desc()).limit(1)
    return (await session.execute(stmt)).scalar_one_or_none()
