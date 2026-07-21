#!/usr/bin/env python3
"""Run one scenario with a REAL Ollama model and print the transcript.

Bypasses the HTTP server — drives the scenario engine directly with an OllamaProvider,
so you can see a real LLM play the agent. Requires: Ollama running + model pulled, the
Pack ingested, the agent seeded, and the Village fixture present.

Usage (repo root, api venv active, DATABASE_URL set):
  # one-time: ollama serve ; ollama pull llama3.1:8b
  python scripts/ingest-scenario-library.py
  python scripts/run-scenario-ollama.py scn.gs.src.001
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from src.config import settings  # noqa: E402
from src.db import SessionLocal, dispose_engine  # noqa: E402
from src.services.agent_runtime.llm_client import OllamaProvider  # noqa: E402
from src.services.runner import RunnerError, run_scenario  # noqa: E402
from src.services.village.reader import VillageReader  # noqa: E402


async def _main(scenario_id: str) -> int:
    provider = OllamaProvider(
        settings.ollama_base_url, settings.ollama_agent_model, settings.llm_request_timeout_seconds
    )
    health = await provider.health_check()
    if not health.get("ok"):
        print(f"Ollama not reachable at {settings.ollama_base_url}. Run `ollama serve`.")
        return 2
    reader = VillageReader.from_settings()
    print(f"Running {scenario_id} with Ollama model '{settings.ollama_agent_model}'…\n")

    async with SessionLocal() as session:
        try:
            run = await run_scenario(session, scenario_id, reader, provider)
        except RunnerError as exc:
            print(f"ERROR: {exc}")
            return 1
        for turn in run.transcript or []:
            print(f"[{turn['role']:8}] {turn['content']}\n")
        print(f"--- status={run.status} outcome={run.outcome} tokens={run.tokensUsed} ---")

    await dispose_engine()
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python scripts/run-scenario-ollama.py <scenario_id>")
        raise SystemExit(1)
    raise SystemExit(asyncio.run(_main(sys.argv[1])))
