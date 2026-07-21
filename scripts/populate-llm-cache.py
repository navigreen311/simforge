#!/usr/bin/env python3
"""Populate the hermetic LLM cache (tests/fixtures/llm_cache/) by scoring the canonical
scenarios once with the configured judge provider in `record` mode (ADR-0008).

Usage (repo root, api venv active):
  python scripts/populate-llm-cache.py --provider ollama    # requires ollama serve
  python scripts/populate-llm-cache.py --provider anthropic # requires ANTHROPIC_API_KEY
  python scripts/populate-llm-cache.py --provider stub      # deterministic placeholder fixtures

Commit the resulting cache files. CI replays them in replay_strict mode.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

from _judge_scenarios import build_ctx, load_scenarios, score_all  # noqa: E402
from src.config import settings  # noqa: E402
from src.services.agent_runtime.cache import LLMResponseCache  # noqa: E402
from src.services.agent_runtime.llm_client import get_judge_llm  # noqa: E402


async def _main(provider: str) -> int:
    settings.llm_judge_provider = provider
    settings.llm_cache_mode = "record"
    judge = get_judge_llm()

    health = await judge.health_check()
    if not health.get("ok") and provider != "stub":
        print(f"Judge provider '{provider}' not healthy: {health}. Aborting.")
        return 2

    scenarios = load_scenarios()
    for scn in scenarios:
        scores = await score_all(build_ctx(scn), judge)
        print(f"  recorded {scn['id']}: {scores}")

    cache = LLMResponseCache()
    count = sum(1 for _ in Path(settings.llm_cache_dir).rglob("*.json")) if Path(
        settings.llm_cache_dir
    ).exists() else 0
    print(f"\nCache dir {cache.cache_dir} now holds {count} entries. Commit them.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="stub", choices=["stub", "ollama", "anthropic"])
    args = ap.parse_args()
    raise SystemExit(asyncio.run(_main(args.provider)))
