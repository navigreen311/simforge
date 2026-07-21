"""SQLAlchemy models (mapped to Prisma tables). Import all so metadata is complete."""

from src.models.agent import Agent
from src.models.base import Base
from src.models.ccb import CCB
from src.models.cert import (
    AgentCert,
    AutonomyEvent,
    CertLifecycleEvent,
    CertSnapshot,
    DeptCert,
)
from src.models.department import Department
from src.models.gap import SoftwareGap, VillageOSGap
from src.models.governance import Constitution, ConstitutionalAmendment
from src.models.pack import Pack, ReadinessGate, Scenario
from src.models.registry import LineageEdge, ObjectRegistryEntry
from src.models.run import Run, TraceEvent
from src.models.scorecard import Scorecard
from src.models.training import TrainingProposal
from src.models.village_fingerprint import VillageFingerprint

__all__ = [
    "Base",
    "Agent",
    "Department",
    "CCB",
    "VillageFingerprint",
    "Pack",
    "Scenario",
    "ReadinessGate",
    "Run",
    "TraceEvent",
    "Scorecard",
    "TrainingProposal",
    "SoftwareGap",
    "VillageOSGap",
    "AgentCert",
    "DeptCert",
    "CertSnapshot",
    "CertLifecycleEvent",
    "AutonomyEvent",
    "Constitution",
    "ConstitutionalAmendment",
    "ObjectRegistryEntry",
    "LineageEdge",
]
