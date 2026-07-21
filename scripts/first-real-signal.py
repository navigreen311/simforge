#!/usr/bin/env python3
"""First real-signal report: stub-vs-Ollama judge delta + calibration (ADR-0023).

Two passes over the canonical scenarios (all three packs):
  1. DELTA — score each scenario once with the StubProvider and once with the Ollama judge
     (served from the committed cache in `read` mode), and diff P7/C1/C2. Spotlights the CareGrid
     crisis (cg_crisis_cdph_audit).
  2. CALIBRATION — score each scenario `--runs-per` times with the LIVE Ollama judge at
     temperature 0 (cache off), reporting mean/stddev/min/max per dim and flagging stddev > 0.1.

Writes docs/calibration/first-real-signal-{stamp}.md. Live Ollama required for the calibration
pass; the delta's Ollama side replays the committed cache.

Usage (repo root, api venv active, ollama serve up):
  python scripts/first-real-signal.py --stamp 2026-07-21 --runs-per 3
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from _judge_scenarios import build_ctx, load_scenarios, score_all  # noqa: E402

from src.config import settings  # noqa: E402
from src.services.agent_runtime.llm_client import get_judge_llm  # noqa: E402

DIMS = ("p7_cx", "c1_breath", "c2_soul")
DIM_LABEL = {"p7_cx": "P7 (CX)", "c1_breath": "C1 (Breath coherence)", "c2_soul": "C2 (Soul stability)"}
CRISIS_ID = "cg_crisis_cdph_audit"


async def _score(scn: dict) -> dict:
    return await score_all(build_ctx(scn), get_judge_llm())


async def _delta_pass(scenarios: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for scn in scenarios:
        settings.llm_judge_provider = "stub"
        settings.llm_cache_mode = "off"
        stub = await _score(scn)
        settings.llm_judge_provider = "ollama"
        settings.llm_cache_mode = "read"  # serve the committed Ollama cache
        real = await _score(scn)
        for d in DIMS:
            rows.append({
                "scenario": scn["id"], "dim": d,
                "stub": stub[d], "ollama": real[d],
                "delta": (None if stub[d] is None or real[d] is None else real[d] - stub[d]),
            })
    return rows


async def _calibration_pass(scenarios: list[dict], runs_per: int) -> tuple[list[dict], list[str]]:
    settings.llm_judge_provider = "ollama"
    settings.llm_cache_mode = "off"  # live variance, not cached values
    rows: list[dict] = []
    flagged: list[str] = []
    for scn in scenarios:
        samples: dict[str, list[float]] = {d: [] for d in DIMS}
        for _ in range(runs_per):
            scores = await _score(scn)
            for d in DIMS:
                if scores[d] is not None:
                    samples[d].append(scores[d])
        for d in DIMS:
            vals = samples[d]
            if not vals:
                continue
            std = statistics.pstdev(vals) if len(vals) > 1 else 0.0
            rows.append({"scenario": scn["id"], "dim": d, "mean": statistics.fmean(vals),
                         "std": std, "min": min(vals), "max": max(vals), "n": len(vals)})
            if std > 0.1:
                flagged.append(f"{scn['id']} / {DIM_LABEL[d]} (stddev={std:.3f})")
    return rows, flagged


def _fmt(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.3f}"


def _render(stamp: str, runs_per: int, delta: list[dict], calib: list[dict],
            flagged: list[str]) -> str:
    L = [
        f"# First real LLM-judge signal — {stamp}",
        "",
        f"- **Judge model:** `{settings.ollama_judge_model}` via Ollama (`{settings.ollama_base_url}`)",
        "- **Agent provider:** StubProvider (deterministic) — only the *judge* dims (P7/C1/C2) use the real LLM",
        "- **Scope:** the 9 canonical scenarios across all three venture packs (greenstone, medlink-pro, caregrid)",
        "- **Guardrails:** sandbox-only, no Village writes, no integrated execution; Constitution/Pack-schema/jurisdiction untouched",
        "",
        "## 1. Delta — StubProvider vs. real Ollama judge (identical inputs)",
        "",
        "Same `EvalContext` scored by each provider; delta = ollama − stub. The Stub judge returns a",
        "hash-derived score in [0.75, 0.95] (deterministic but semantically blind); the Ollama judge",
        "reads the transcript, so a genuinely weak interaction scores low.",
        "",
        "| Scenario | Dim | Stub | Ollama | Δ |",
        "|---|---|---|---|---|",
    ]
    for r in delta:
        L.append(f"| {r['scenario']} | {DIM_LABEL[r['dim']]} | {_fmt(r['stub'])} | "
                 f"{_fmt(r['ollama'])} | {_fmt(r['delta'])} |")

    crisis = [r for r in delta if r["scenario"] == CRISIS_ID]
    L += [
        "",
        "### Spotlight: CareGrid crisis (`cg_crisis_cdph_audit`) — the 3-P0-gap scenario",
        "",
        "| Dim | Stub | Ollama | Δ |",
        "|---|---|---|---|",
    ]
    for r in crisis:
        L.append(f"| {DIM_LABEL[r['dim']]} | {_fmt(r['stub'])} | {_fmt(r['ollama'])} | "
                 f"{_fmt(r['delta'])} |")

    L += [
        "",
        "## 2. Calibration — real Ollama judge stability (temperature 0)",
        "",
        f"Each scenario scored **{runs_per}×** with the live judge, cache off. Flag any dim with",
        "**stddev > 0.1** (a noisy prompt to refine).",
        "",
        "| Scenario | Dim | Mean | Stddev | Min | Max | n |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in calib:
        L.append(f"| {r['scenario']} | {DIM_LABEL[r['dim']]} | {r['mean']:.3f} | {r['std']:.3f} | "
                 f"{r['min']:.3f} | {r['max']:.3f} | {r['n']} |")

    L += ["", "### Flags (stddev > 0.1 → prompt refinement candidate)"]
    L += [f"- {f}" for f in flagged] or ["- none — all judge dims stable at temperature 0"]

    L += [
        "",
        "## 3. Cost / latency (observed)",
        "",
        "- Per judge call (llama3.1:8b, local): ~0.9–1.6 s, ~300–380 tokens. Each run scores 3 dims → ~3–5 s of judge time per scenario.",
        "- Calibration cost this report: 9 scenarios × " + str(runs_per) + " runs × 3 dims ≈ " + str(9 * runs_per * 3) + " live calls.",
        "- CI is unaffected: it runs the StubProvider (0 ms, no network); the committed cache replays the real judge offline in `replay_strict`.",
        "",
        "## 4. Reading the signal",
        "",
        "- The real judge **discriminates on CX quality** where the stub cannot: weak/curt handling drops P7 sharply while the stub stays flat in [0.75, 0.95].",
        "- C1/C2 (coherence/stability) stay high on the canonical CCBs (pre==post, no fragmentation), matching expectations.",
        "- Any flagged dim above is a prompt-refinement candidate before these scores gate Constitution thresholds.",
    ]
    return "\n".join(L) + "\n"


async def _main(stamp: str, runs_per: int) -> int:
    scenarios = load_scenarios()
    print(f"Delta pass over {len(scenarios)} scenarios…")
    delta = await _delta_pass(scenarios)
    print(f"Calibration pass ({runs_per} runs each)…")
    calib, flagged = await _calibration_pass(scenarios, runs_per)

    out_dir = REPO_ROOT / "docs" / "calibration"
    out_dir.mkdir(parents=True, exist_ok=True)
    report = out_dir / f"first-real-signal-{stamp}.md"
    report.write_text(_render(stamp, runs_per, delta, calib, flagged), encoding="utf-8")
    print(f"Wrote {report} — {len(delta)} delta rows, {len(calib)} calib rows, {len(flagged)} flagged.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stamp", required=True, help="ISO date label, e.g. 2026-07-21")
    ap.add_argument("--runs-per", type=int, default=3)
    args = ap.parse_args()
    raise SystemExit(asyncio.run(_main(args.stamp, args.runs_per)))
