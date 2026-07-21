"""Village-OS Gap detector (blueprint §C.11).

A Village-OS Gap is an anomaly in a Village cognitive framework surfaced by a run's CCB.
v1 uses principled thresholds over the post-run CCB — healthy agents produce no gaps
(the correct, common case); anomalies (ARC fragmentation, high regret, drive imbalance,
drift) raise framework-specific tickets.
"""

from __future__ import annotations

from dataclasses import dataclass

_ARC_FRAGMENTED = {"sudden_shift", "regression", "fragmentation"}


@dataclass
class VosGapCandidate:
    framework: str
    severity: str
    summary: str
    detail: str
    proposed_fix: str


def detect_village_os_gaps(
    arc_coherence: str | None, ccb_post: dict | None
) -> list[VosGapCandidate]:
    gaps: list[VosGapCandidate] = []
    if ccb_post is None:
        return gaps

    if arc_coherence in _ARC_FRAGMENTED:
        gaps.append(
            VosGapCandidate(
                "arc",
                "P1",
                f"ARC narrative {arc_coherence} during run",
                "Agent identity arc shifted unexpectedly mid-scenario in a sandbox run.",
                "Review ARC transition guards; a sandbox run must not alter narrative phase.",
            )
        )

    regret = float((ccb_post.get("echo") or {}).get("regret_load", 0.0))
    if regret > 0.25:
        gaps.append(
            VosGapCandidate(
                "echo",
                "P2",
                f"Elevated regret load ({regret:.2f})",
                "ECHO regret load exceeds the healthy threshold.",
                "Inspect recent regret accumulation and decay in ECHO.",
            )
        )

    balance = float((ccb_post.get("hfm") or {}).get("balance", 1.0))
    if balance < 0.55:
        gaps.append(
            VosGapCandidate(
                "hfm",
                "P2",
                f"Drive imbalance ({balance:.2f})",
                "HFM drive balance is below the healthy threshold.",
                "Rebalance HFM drives; check for a dominant unmet drive.",
            )
        )

    if (ccb_post.get("drift") or {}).get("flagged") is True:
        gaps.append(
            VosGapCandidate(
                "drift",
                "P1",
                "DRIFT flagged",
                "The DRIFT framework flagged this agent.",
                "Investigate value/behavior drift signals for this agent.",
            )
        )

    valence = float(
        ((ccb_post.get("soul") or {}).get("ledger") or {}).get("current", {}).get("valence", 0.5)
    )
    if valence < 0.45:
        gaps.append(
            VosGapCandidate(
                "soul",
                "P2",
                f"Low emotional valence ({valence:.2f})",
                "SOUL current valence is low.",
                "Check emotional ledger for unresolved negative events.",
            )
        )

    return gaps
