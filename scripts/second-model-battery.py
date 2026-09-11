"""P-01 / A0 — put the SAME eight held-out probes to a SECOND model.

STATUS: **WRITTEN BUT NEVER EXECUTED.** No run behind it, no numbers from it. It is committed
for the guards it encodes, not for a result it produced. See
`docs/calibration/first-battery-run-2026-09-10.md` (entry 3) for why it did not run.

Why the guards below exist, rather than as a matter of taste: the 10 September run was retracted
TWICE, and the second retraction was an instrument that sent the empty string on all eight probes
and returned a confident, plausible, wrong number. A default is how an instrument keeps running
while measuring the wrong thing. So:

  * Nothing is read with `getattr(x, "name", fallback)`. Fields come off the dataclass by name;
    a rename must raise `AttributeError` and stop the run, which is the behaviour that caught the
    second error in the first place.
  * Every probe is asserted non-empty BEFORE the first call, not after and not in a comment.
  * The provider that will actually answer is resolved and printed BEFORE the first call, and the
    run aborts unless it is the second model. `LLM_PROVIDER=auto` resolves to
    ollama-if-reachable-else-stub and NEVER to anthropic (`llm_client.resolve_provider`), so on a
    box with Ollama up, `auto` would quietly re-measure `llama3.1:8b` — the FIRST model — and
    produce a plausible "second model" number. That is the same family of error as the two
    retractions, and this guard is the whole reason the script exists.

Run it as:
    LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-ant-...         python scripts/second-model-battery.py <forge_id> <module_id>
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from src.config import settings  # noqa: E402
from src.services.agent_runtime.llm_client import (  # noqa: E402
    provider_label,
    resolve_provider,
)

EXPECTED_PROVIDER = "anthropic"
#: The comparison is only meaningful against the same eight probes as the 10 September run.
EXPECTED_PROBE_COUNT = 8
EXPECTED_BY_CLASS = {"silent_failure": 3, "never_do_violation": 5}


def _abort(why: str) -> None:
    print(f"ABORT: {why}", file=sys.stderr)
    raise SystemExit(2)


def check_provider_before_any_call() -> str:
    """Resolve what will actually answer, and refuse to run if it is not the second model."""
    resolved = resolve_provider(settings.llm_provider)
    print(f"configured LLM_PROVIDER = {settings.llm_provider!r}  ->  resolves to {resolved!r}")
    if resolved != EXPECTED_PROVIDER:
        _abort(
            f"resolved provider is {resolved!r}, not {EXPECTED_PROVIDER!r}. "
            "`auto` resolves to ollama-if-reachable-else-stub and never to anthropic; running "
            "now would re-measure the FIRST model and report it as the second. "
            "Set LLM_PROVIDER=anthropic explicitly."
        )

    # The agent provider is wrapped in CachedLLMProvider. A replaying cache would serve fixtures
    # instead of calling the model, and the run would still print numbers.
    if settings.llm_cache_mode not in ("off", "record"):
        _abort(
            f"LLM_CACHE_MODE={settings.llm_cache_mode!r} would replay cached answers instead of "
            "putting the probes to the model. Set LLM_CACHE_MODE=off."
        )

    key = settings.anthropic_api_key
    if not key:
        _abort("ANTHROPIC_API_KEY is unset. Refusing to substitute a provider.")
    if not key.startswith("sk-ant-"):
        _abort(
            f"ANTHROPIC_API_KEY is present but does not look like a key "
            f"(length {len(key)}, prefix {key[:7]!r}). A placeholder is not a credential: "
            "`AnthropicProvider.health_check` reports ok for ANY non-empty string."
        )
    return resolved


def assert_every_probe_is_non_empty(scenarios) -> int:
    """Mandatory. Returns the shortest probe length, which the caller must print."""
    if not scenarios:
        _abort("no probes were authored at all")

    lengths = []
    for index, scenario in enumerate(scenarios):
        # Read the field. No default. A rename must raise here.
        probe = scenario.probe
        if not isinstance(probe, str) or not probe.strip():
            _abort(
                f"probe {index} ({scenario.scenario_class}) is empty or blank. "
                "This is the exact failure that produced the second retraction."
            )
        lengths.append(len(probe))

    by_class: dict[str, int] = defaultdict(int)
    for scenario in scenarios:
        by_class[scenario.scenario_class] += 1
    print(f"probes authored: {len(scenarios)} -> {dict(by_class)}")
    if len(scenarios) != EXPECTED_PROBE_COUNT or dict(by_class) != EXPECTED_BY_CLASS:
        _abort(
            f"probe set is {dict(by_class)}, expected {EXPECTED_BY_CLASS}. "
            "A different probe set makes the comparison against 10 September meaningless."
        )
    return min(lengths)


async def main() -> None:
    if len(sys.argv) < 3:
        _abort("usage: second-model-battery.py <forge_id> <module_id>")
    forge_id, module_id = sys.argv[1], sys.argv[2]

    # 1. Refuse to run against the wrong model, BEFORE touching the DB or spending a call.
    check_provider_before_any_call()

    # Imports deferred so the provider guard fires even if the DB layer is unavailable.
    from src.db import SessionLocal
    from src.services.agent_runtime import get_llm_provider
    from src.services.agent_runtime.runtime import AgentRuntime
    from src.services.operation.battery import run_module_battery
    from src.services.operation.held_out import (
        author_held_out_scenarios,
        obligations_from_never_do,
    )
    from src.services.operation.rubric import VERDICT_NOT_RUN
    from src.services.operation.never_do import module_never_do_list
    from src.services.village.reader import VillageReader

    async with SessionLocal() as session:
        never_do = await module_never_do_list(session, forge_id, module_id)
    if not never_do:
        _abort(f"module {module_id!r} has no declared never-do list; there is nothing to probe")

    # 2. Author the probes and assert every one is non-empty BEFORE the first call.
    scenarios = author_held_out_scenarios(obligations_from_never_do(module_id, never_do))
    shortest = assert_every_probe_is_non_empty(scenarios)

    runtime = AgentRuntime(
        village_reader=VillageReader.from_settings(), provider=get_llm_provider()
    )

    # 3. Print the provider label and the shortest probe length before the first call.
    print(f"answering model : {provider_label(runtime.provider)}")
    print(f"shortest probe  : {shortest} chars")
    print("-" * 60)

    report = await run_module_battery(
        module_id=module_id,
        agent_id=f"p01-second-model-{module_id}",
        never_do=never_do,
        runtime=runtime,
        seed=0,
    )

    # 4. Report BY CLASS. A single rate hides the entire finding.
    # A probe whose answer could not be parsed as the grammar is NOT_RUN (ADR-0051): an
    # unreadable answer is neither a pass nor a fail. So "readable in the grammar" is exactly
    # "did not land on NOT_RUN".
    readable: dict[str, int] = defaultdict(int)
    total: dict[str, int] = defaultdict(int)
    for verdict in report.grading.verdicts:
        total[verdict.scenario_class] += 1
        if verdict.verdict != VERDICT_NOT_RUN:
            readable[verdict.scenario_class] += 1

    print(f"answering model : {provider_label(runtime.provider)}")
    print(f"probes put      : {report.probes_put}")
    print(f"unreadable      : {report.unreadable_answers}")
    for cls in sorted(total):
        print(f"  {cls:22s} readable in the grammar: {readable[cls]} / {total[cls]}")


if __name__ == "__main__":
    asyncio.run(main())
