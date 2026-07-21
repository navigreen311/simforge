"""Software Gap detector (blueprint §C.11).

A Software Gap is a defect in a Forge (the software under test) surfaced by a run.
v1 heuristic (documented): real detection reads Forge sandbox error traces; here we derive
candidate gaps from run outcome + tier against the scenario's tested Forge capabilities.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from src.models.pack import Scenario
from src.models.run import Run

_KNOWN_FORGES = {
    "voiceforge",
    "vaf",
    "medlink-pro",
    "cre-forge",
    "funnelforge",
    "capitalforge",
}


@dataclass
class GapCandidate:
    forge: str
    module: str
    severity: str
    summary: str
    detail: str
    proposed_fix: str


def _parse_cap(cap: str) -> tuple[str, str]:
    parts = cap.split(".")
    forge = parts[0] if parts else "unknown"
    module = parts[1] if len(parts) > 1 else "core"
    return forge, module


def ticket_id(prefix: str, dedup_key: str) -> str:
    n = int(hashlib.sha256(dedup_key.encode()).hexdigest()[:6], 16) % 10000
    return f"{prefix}-{n:04d}"


def detect_forge_fault_gaps(fault_events: list[dict]) -> list[GapCandidate]:
    """Real Software Gaps from `forge_fault` trace events (Forge sandbox faults hit at runtime)."""
    gaps: list[GapCandidate] = []
    for payload in fault_events:
        forge = payload.get("forge", "unknown")
        module = payload.get("module", "core")
        reason = payload.get("reason", "fault")
        gaps.append(
            GapCandidate(
                forge,
                module,
                payload.get("severity", "P1"),
                f"{forge}.{module} returned a '{reason}' fault during the run",
                payload.get("detail", f"{forge}.{module} fault: {reason}"),
                f"Verify {module} handling for the '{reason}' path in {forge}.",
            )
        )
    return gaps


def detect_software_gaps(run: Run, scenario: Scenario) -> list[GapCandidate]:
    gaps: list[GapCandidate] = []
    for cap in scenario.testedForgeCaps or []:
        forge, module = _parse_cap(cap)
        if forge not in _KNOWN_FORGES:
            continue

        if run.outcome in ("slo_exceeded", "errored"):
            gaps.append(
                GapCandidate(
                    forge,
                    module,
                    "P0",
                    f"{forge}.{module} did not complete within SLO",
                    f"Run {run.runId} on {scenario.scenarioId} ended '{run.outcome}' "
                    f"exercising {cap}.",
                    f"Investigate {module} latency/timeout handling in {forge} sandbox.",
                )
            )
        elif scenario.tier == "advanced_crisis":
            gaps.append(
                GapCandidate(
                    forge,
                    module,
                    "P1",
                    f"{forge}.{module} degrades under crisis load",
                    f"Advanced-crisis scenario {scenario.scenarioId} stressed {cap}; "
                    f"agent had to compensate for {module} friction.",
                    f"Harden {module} error surfaces and retry semantics in {forge}.",
                )
            )
    return gaps
