"""Entry point for the battery sweep. Its own process, not a route and not in `run_all`.

    apps/api/.venv/Scripts/python.exe -m scripts.run_battery_sweep --limit 5

CADENCE
=======

Three numbers, and only two of them are load-bearing.

**Measured: 24.2 seconds** for eleven probes against `claude-sonnet-5`, the examiner ADR-0054
names - mean 2.20s per probe, slowest single probe 3.9s, from the committed transcript
`docs/calibration/a0-decline-sonnet5-2026-09-12.json`. Twelve probes is ~27s.

**Budgeted: eight minutes per battery.** That is ~18x the measured mean and it is deliberate
headroom, not a measurement - a bad network minute, a cold start, or a longer curriculum all fit
inside it. The interval is designed against this number so the sweep is never the thing that made a
pass overlap.

**Worst case: 44 minutes**, and this is what the lock is for. Eleven probes x
`llm_request_timeout_seconds` (60) x (`llm_max_retries` 3 + 1 attempts) = 44 min, because
`_with_retries` runs `max_retries + 1` attempts with exponential backoff. It is not
`MAX_SCENARIOS x timeout` - **there is no `MAX_SCENARIOS` constant in either repository.** A pass
that hits this is one where every probe timed out four times, which is a provider outage rather
than a slow battery.

So: `--limit` x 8 minutes is the budgeted pass, the advisory lock bounds the pathological one, and
a cron shorter than the budget simply finds the lock held and returns - which is the designed
behaviour, not a failure.

WHY IT IS NOT IN `run_all`
==========================

The Office's `run_all` iterates its sweeps in a **plain sequential loop**, each under a per-kind
advisory lock. The locks never contend with each other; the loop is what serialises them. So a
battery added to that tuple would stall every sweep after it in the same invocation - including the
audit chain - regardless of having its own key. Its own lock in its own database and its own
process is the only shape that does not.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from src.config import get_settings
from src.db import SessionLocal
from src.services.agent_runtime.llm_client import resolve_provider
from src.services.agent_runtime.runtime import AgentRuntime
from src.services.village.reader import VillageReader
from src.workers.battery_sweep import battery_sweep_lock, sweep_unscored_runs


def _provider_or_die(name: str):
    """The examiner is named, never resolved. ADR-0054.

    `auto` resolves to Ollama-if-reachable-else-stub and never to Anthropic, so a sweep launched on
    `auto` would certify agents against whichever local model happened to be running. It is refused
    here rather than warned about, because the resulting certifications look exactly like real ones.
    """
    if name == "auto":
        raise SystemExit(
            "LLM_PROVIDER=auto is not a valid examiner. It resolves to ollama or stub and never "
            "to anthropic. Set LLM_PROVIDER=anthropic (ADR-0054)."
        )
    if resolve_provider(name) != name:
        raise SystemExit(f"provider {name!r} does not resolve to itself; name it explicitly")
    from src.services.agent_runtime.llm_client import get_llm_provider

    return get_llm_provider()


async def main_async(limit: int, seed: int) -> int:
    settings = get_settings()
    provider = _provider_or_die(settings.llm_provider)
    runtime = AgentRuntime(
        village_reader=VillageReader(village_data_path=Path(settings.village_data_path)),
        provider=provider,
    )

    async with SessionLocal() as session:
        async with battery_sweep_lock(session) as acquired:
            if not acquired:
                print(json.dumps({"skipped": "another battery sweep holds the lock"}))
                return 0
            outcome = await sweep_unscored_runs(
                session, runtime=runtime, limit=limit, seed=seed
            )

    print(
        json.dumps(
            {
                "considered": outcome.considered,
                "scored": outcome.scored,
                "skipped": [list(s) for s in outcome.skipped],
                "failed": [list(f) for f in outcome.failed],
            },
            indent=2,
        )
    )
    # A failed run is not a failed sweep: the pass did its job by attempting every run and
    # reporting which did not score. Exit non-zero only if nothing could be attempted at all.
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=5, help="runs per pass (the blast radius)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main_async(args.limit, args.seed)))


if __name__ == "__main__":
    main()
