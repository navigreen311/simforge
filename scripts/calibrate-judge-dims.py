#!/usr/bin/env python3
"""Calibrate the LLM-judge dims (P7/C1/C2) — the Week-2 tool for tuning Constitution
thresholds (ADR-0008).

Runs the canonical scenarios N times each with the configured judge, reports mean/stddev/
min/max per (scenario, dim), flags any dim with stddev > 0.1, and writes a markdown report
to docs/calibration/.

Usage (repo root, api venv active):
  python scripts/calibrate-judge-dims.py --provider ollama --scenarios 6 --runs-per 3
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from _judge_scenarios import build_ctx, load_scenarios, score_all  # noqa: E402

from src.config import settings  # noqa: E402
from src.services.agent_runtime.llm_client import get_judge_llm  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
DIMS = ("p7_cx", "c1_breath", "c2_soul")


async def _main(provider: str, n_scenarios: int, runs_per: int, stamp: str) -> int:
    settings.llm_judge_provider = provider
    settings.llm_cache_mode = "off"  # calibration needs live variance, not cached values
    judge = get_judge_llm()

    scenarios = load_scenarios()[:n_scenarios]
    rows: list[dict] = []
    flagged: list[str] = []

    for scn in scenarios:
        samples: dict[str, list[float]] = {d: [] for d in DIMS}
        for _ in range(runs_per):
            scores = await score_all(build_ctx(scn), judge)
            for d in DIMS:
                if scores[d] is not None:
                    samples[d].append(scores[d])
        for d in DIMS:
            vals = samples[d]
            if not vals:
                continue
            std = statistics.pstdev(vals) if len(vals) > 1 else 0.0
            rows.append({
                "scenario": scn["id"], "dim": d, "mean": statistics.fmean(vals),
                "std": std, "min": min(vals), "max": max(vals),
            })
            if std > 0.1:
                flagged.append(f"{scn['id']}/{d} (std={std:.3f})")

    out_dir = REPO_ROOT / "docs" / "calibration"
    out_dir.mkdir(parents=True, exist_ok=True)
    report = out_dir / f"calibration-{stamp}.md"
    lines = [
        f"# Judge calibration — {stamp}",
        f"\nProvider: **{provider}** · scenarios: {len(scenarios)} · runs/scenario: {runs_per}\n",
        "| Scenario | Dim | Mean | Stddev | Min | Max |",
        "|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {r['scenario']} | {r['dim']} | {r['mean']:.3f} | {r['std']:.3f} | "
        f"{r['min']:.3f} | {r['max']:.3f} |"
        for r in rows
    ]
    lines.append("\n## Flags (stddev > 0.1 — prompt may need refinement)")
    lines += [f"- {f}" for f in flagged] or ["- none"]
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {report} ({len(rows)} rows, {len(flagged)} flagged).")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="stub", choices=["stub", "ollama", "anthropic"])
    ap.add_argument("--scenarios", type=int, default=6)
    ap.add_argument("--runs-per", type=int, default=3)
    ap.add_argument("--stamp", default="latest", help="timestamp label (avoids nondeterministic now)")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(_main(args.provider, args.scenarios, args.runs_per, args.stamp)))
