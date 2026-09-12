"""A0 baseline - the eleven probes put to one named model, once.

WHAT THIS MEASURES
==================

Whether a model holds the response protocol. **Nothing else.** See `a0_probes` for what A0 is not:
not A2, not a held-out corpus, and no evidence about any agent's competence.

THE THREE RULES THIS RUN IS BUILT AROUND, EACH FROM A RUN THAT WENT WRONG
=========================================================================

1. **The provider is named in code, never resolved.** `OllamaProvider` is constructed directly with
   an explicit model string. `resolve_provider` is not called and `settings.llm_provider` is not
   read, because `auto` resolves to whichever of Ollama or the stub answered a ping - which is how
   a scoreboard of the stub was once published as a measurement of a model. The server on :8110 is
   on `auto` right now; this process does not inherit that.

2. **Every probe is asserted non-empty before anything is measured.** A previous run sent the empty
   string to all eight probes and produced a full scoreboard, because the probe text was reached for
   with `getattr(probe, "prompt", None) or getattr(probe, "situation", "")` - a chain that cannot
   raise. Nothing here is reached for with a default: attributes are accessed directly so a wrong
   name is an `AttributeError` at the first probe rather than a plausible number at the twelfth.

3. **The model is recorded as ANSWERED, not as configured.** `LLMResponse.model` and
   `.provider` are read off each response and cross-checked against what was requested. A
   configured value is an intention; the response is the fact, and the two differ exactly when it
   matters.

WHAT IT DOES NOT PUT TO THE MODEL
=================================

The real runner reaches the model through `AgentRuntime.turn`, which assembles a Village agent's
BREATH/FOT/SOUL layers and appends the battery context. This calls the provider directly with
`battery_system_context` as the whole system prompt. **That is a deliberate isolation and it is a
difference worth naming**: this measures a model against the operating context alone, with no
Village identity in front of it. For "can a model hold this grammar" that is the cleaner question;
it is not a measurement of a certified Village agent.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime

from scripts.a0_probes import (
    CONTENT_HASH,
    DERIVATIONS,
    FORGE_ID,
    MODULE_ID,
    PROBES,
    live_never_do,
)
from src.config import get_settings
from src.services.agent_runtime.llm_client import OllamaProvider
from src.services.operation.battery import (
    battery_system_context,
    observe_answer,
    parse_answer,
)
from src.services.operation.held_out import obligations_from_never_do
from src.services.operation.held_out_scoring import run_held_out_battery_async

#: P-12 is excluded from this run. It is the forced `verified [Y/N]` box for prohibition #7, and it
#: cannot be probed as written: the honest answer is to decline a binary, but the probe asks the
#: agent to FILL IN a box, which is a request to act, while the probe is graded on the RECORD
#: channel as a concealment case. The two channels disagree about what the answer even is, so
#: whatever came back could not be read as evidence either way.
#:
#: **A prohibition that cannot be probed is a coverage gap, not an absent rule.** #7 is still in
#: force and the agent is still shown it, numbered, in its operating context - it is simply not
#: measured by the excluded probe. Recorded so that the eleven are never read as the whole list.
EXCLUDED = {12: "the forced-binary probe asks for an act and is graded as a claim"}

DEFAULT_MODEL = "llama3.1:8b"


def _selected() -> tuple[tuple[int, object, str], ...]:
    """The probes this run puts, numbered as they are in `a0_probes`, minus the exclusions."""
    return tuple(
        (n, probe, note)
        for n, (probe, note) in enumerate(zip(PROBES, DERIVATIONS, strict=True), 1)
        if n not in EXCLUDED
    )


def _preflight(context: str, selected: tuple[tuple[int, object, str], ...]) -> None:
    """Every probe non-empty, and the context too, BEFORE a single call is made.

    Rule 2. This is the check whose absence let an entire run measure the empty string. It is
    cheap, it runs first, and it raises rather than warning.
    """
    if not context.strip():
        raise SystemExit("battery_system_context is empty - nothing would be asked")
    if len(selected) != len(PROBES) - len(EXCLUDED):
        raise SystemExit("selection arithmetic is wrong; refusing to run")
    for n, probe, _ in selected:
        text = probe.probe  # direct attribute access; no default, no fallback chain
        if not isinstance(text, str) or not text.strip():
            raise SystemExit(f"probe {n} is empty or not a string - refusing to measure")
        if len(text.strip()) < 40:
            raise SystemExit(f"probe {n} is {len(text.strip())} chars - implausibly short")
    print(f"preflight OK: {len(selected)} probes, all non-empty; "
          f"context {len(context)} chars; shortest probe "
          f"{min(len(p.probe) for _, p, _ in selected)} chars")


async def run(model: str, base_url: str, timeout: float) -> dict:
    never_do = live_never_do()
    context = battery_system_context(MODULE_ID, never_do)
    declared_refs = tuple(o.ref for o in obligations_from_never_do(MODULE_ID, never_do))
    selected = _selected()
    _preflight(context, selected)

    provider = OllamaProvider(base_url, model, timeout, 1)
    print(f"provider constructed by name: {provider.name}/{provider.model} at {provider.base_url}")
    print()

    scenarios = tuple(probe for _, probe, _ in selected)
    numbers = [n for n, _, _ in selected]
    in_order = iter(range(len(scenarios)))
    records: list[dict] = []

    async def ask(probe):
        i = next(in_order)
        scenario = scenarios[i]
        number = numbers[i]
        if probe.prompt != scenario.probe:
            raise SystemExit(f"probe {number} delivered out of order - refusing to grade")

        started = time.monotonic()
        response = await provider.complete(
            system=context,
            messages=[{"role": "scenario", "content": probe.prompt}],
            temperature=0.0,
            max_tokens=512,
        )
        elapsed = int((time.monotonic() - started) * 1000)

        raw = response.content  # direct; `.text` is what the broken run reached for
        answer = parse_answer(raw)
        rec = {
            "probe": number,
            "scenario_class": scenario.scenario_class,
            "obligation_ref": scenario.obligation_ref,
            "answered_model": response.model,
            "answered_provider": response.provider,
            "latency_ms": elapsed,
            "tokens_out": response.tokens_output,
            "raw": raw,
            "readable": answer is not None,
            "act": answer.act if answer is not None else None,
            "cited_rule": answer.cited_rule if answer is not None else None,
            "record": list(answer.record) if answer is not None and answer.record else None,
            "caveats": list(answer.caveats) if answer is not None else [],
        }
        records.append(rec)
        shape = (
            f"{rec['act']}" + (f" {rec['cited_rule']}" if rec["cited_rule"] else "")
            if answer is not None
            else "UNREADABLE"
        )
        print(f"  probe {number:2}  [{scenario.scenario_class:18}] {shape:14} "
              f"{elapsed:6}ms  {response.tokens_output:4} tok")
        if answer is None:
            return None
        return observe_answer(
            answer, probed_ref=scenario.obligation_ref, declared_refs=declared_refs
        )

    print(f"putting {len(scenarios)} probes to {model}...")
    grading = await run_held_out_battery_async(MODULE_ID, scenarios, ask)
    return {"grading": grading, "records": records, "context_chars": len(context)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL, help="named explicitly; never resolved")
    ap.add_argument("--out", default=None, help="write the full transcript here as JSON")
    args = ap.parse_args()

    settings = get_settings()
    result = asyncio.run(run(args.model, settings.ollama_base_url, 180.0))
    records = result["records"]
    grading = result["grading"]

    answered = {(r["answered_provider"], r["answered_model"]) for r in records}
    readable = [r for r in records if r["readable"]]
    unreadable = [r for r in records if not r["readable"]]

    print()
    print("=" * 78)
    print(f"A0 BASELINE - {FORGE_ID}/{MODULE_ID}")
    print(f"  instruction content_hash  {CONTENT_HASH}")
    print(f"  requested model           {args.model}")
    print(f"  ANSWERED (provider/model) {sorted(f'{p}/{m}' for p, m in answered)}")
    if len(answered) != 1:
        print("  ** more than one answering identity in one run - the run is not one measurement")
    print(f"  run at                    {datetime.now(UTC).isoformat()}")
    print(f"  probes put                {len(records)} of {len(PROBES)}"
          f"   (excluded: {sorted(EXCLUDED)})")
    print()

    print(f"PROTOCOL CONFORMANCE  {len(readable)}/{len(records)} readable")
    for cls in ("silent_failure", "never_do_violation"):
        rows = [r for r in records if r["scenario_class"] == cls]
        ok = [r for r in rows if r["readable"]]
        print(f"  {cls:20} {len(ok)}/{len(rows)}")
    if unreadable:
        print(f"  unreadable probes: {[r['probe'] for r in unreadable]}")
    print()

    acts = {}
    for r in readable:
        acts[r["act"]] = acts.get(r["act"], 0) + 1
    print(f"ACTS (readable only)  {acts}")
    print()

    verdicts = {}
    for v in grading.verdicts:
        verdicts[v.verdict] = verdicts.get(v.verdict, 0) + 1
    print(f"GRADED VERDICTS  {verdicts}")
    for v in grading.verdicts:
        print(f"  {v.scenario_class:20} {v.verdict:8} {list(v.reasons)}")
    print()

    # P-11, called out whatever it did. Declining without narrating is the right answer here and a
    # CAVEAT line is the most likely way a right answer arrives in the wrong shape.
    p11 = next((r for r in records if r["probe"] == 11), None)
    print("=" * 78)
    print("P-11 - flagged by instruction, whatever it did")
    if p11 is None:
        print("  NOT PUT - probe 11 was not in this run")
    else:
        print(f"  readable: {p11['readable']}   act: {p11['act']}   "
              f"cited: {p11['cited_rule']}")
        print(f"  record:   {p11['record']}")
        print(f"  caveats:  {p11['caveats']}")
        print("  raw answer:")
        for line in p11["raw"].splitlines():
            print(f"    | {line}")
    print("=" * 78)

    if args.out:
        payload = {
            "forge_id": FORGE_ID,
            "module_id": MODULE_ID,
            "instruction_content_hash": CONTENT_HASH,
            "requested_model": args.model,
            "answered": sorted(f"{p}/{m}" for p, m in answered),
            "run_at": datetime.now(UTC).isoformat(),
            "excluded": {str(k): v for k, v in EXCLUDED.items()},
            "records": records,
        }
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        print(f"transcript -> {args.out}")


if __name__ == "__main__":
    main()
