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

from src.db import SessionLocal
from src.services.agent_runtime.exam_model_lock import SKIP_MODEL_HELD, exam_model_lock
from src.services.agent_runtime.runtime import build_exam_runtime
from src.services.village.reader import VillageReader
from src.workers.battery_sweep import battery_sweep_lock, sweep_unscored_runs


async def main_async(limit: int, seed: int) -> int:
    # The EXAMINER (ADR-0061, ADR-0167), as the scheduled sweep builds it: `get_exam_llm()` names
    # its own pinned model and starts every call from a clean cache (B135). This script used to
    # build its provider from LLM_PROVIDER, which skipped the clean-cache unload.
    runtime = build_exam_runtime(VillageReader.from_settings())

    # The locks on their OWN session, as `jobs.battery_sweep` holds them: a failed run's
    # rollback hands the swept session's connection back, and the unlock needs it.
    async with SessionLocal() as session, SessionLocal() as lock_session:
        async with battery_sweep_lock(lock_session) as acquired:
            if not acquired:
                print(json.dumps({"skipped": "another battery sweep holds the lock"}))
                return 0
            async with exam_model_lock(lock_session) as model_free:
                if not model_free:
                    print(json.dumps({"skipped": SKIP_MODEL_HELD}))
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
