"""Scenario Bank schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BankScenarioOut(BaseModel):
    """List-row view."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    publicId: str
    scenarioId: str | None = None
    title: str
    pack: str
    family: str
    tier: str
    situation: str  # included so free-text search covers it (kept short in practice)
    status: str
    aiDrafted: bool
    sourceType: str
    createdBy: str
    createdAt: datetime


class BankScenarioDetail(BankScenarioOut):
    """Full detail view (situation, behaviors, provenance, review state)."""

    expectedBehaviors: list[str]
    adversarialTactics: list[str]
    jurisdictionFlags: list[str]
    sourceRef: str | None = None
    sourceExcerpt: str | None = None
    reviewedBy: str | None = None
    reviewedAt: datetime | None = None
    version: int
    supersedesId: str | None = None
    updatedAt: datetime


class BankScenarioList(BaseModel):
    items: list[BankScenarioOut]
    total: int
