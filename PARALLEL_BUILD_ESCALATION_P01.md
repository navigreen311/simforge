# P-01 escalation — A0 is blocked on a credential, and running anyway would have measured the first model again

**Package:** P-01 — A0, the same eight probes against a second model.
**Branch:** `feature/p-01-second-model-measurement`.
**Raised under the package card's own hard stop:** *"If `ANTHROPIC_API_KEY` is absent from the
environment, STOP and report that rather than substituting a provider. Report exactly which
variable is missing."*

Filed as `..._P01.md` so it does not clobber the existing `PARALLEL_BUILD_ESCALATION.md` or
`..._P05.md`. `PARALLEL_BUILD.md` was not touched.

---

## The missing variable, exactly

**`ANTHROPIC_API_KEY`.**

| where | state |
|---|---|
| process environment | **unset** |
| `.env` in the worktree | present, value is the placeholder `YOUR_AN…` (27 chars, no `sk-ant-` prefix) |

Nothing else is missing. `ANTHROPIC_AGENT_MODEL` already defaults to `claude-3-5-sonnet-20241022`
in `apps/api/src/config.py`, exactly as the card said. The ruled model needed only a key.

**I did not substitute a provider, and I did not fabricate the split.** There is no number in this
package's output. `.env` was not modified.

## Why this was not a near-miss

`.env` also carries `LLM_PROVIDER=auto`, and Ollama is up on this box serving `llama3.1:8b` — the
**first** model. `llm_client.resolve_provider` expands `auto` to `ollama`-if-reachable-else-`stub`
and **never** to `anthropic`. So "just run it and see" would not have errored on the placeholder
key. It would have put the eight probes to the first model again and produced a plausible split to
write in the second model's column.

Recorded as entry 3 of `docs/calibration/first-battery-run-2026-09-10.md`, because it is the same
family as the two retractions already in that file and it is the one the PR #139 protection does
not catch.

## Second blocker, softer but real

**The 10 September probes cannot currently be re-derived.** The script that ran them was never
committed (PR #140 is the doc alone), and the document does not name the `forge_id` / `module_id`
whose never-do list authored the eight. The simforge database is also not running
(`docker ps` shows no simforge Postgres; `DATABASE_URL` points at `localhost:5432`).

"The same eight probes" needs to resolve to something before the comparison can mean anything.

## What unblocks A0

1. A real `ANTHROPIC_API_KEY`, and **`LLM_PROVIDER=anthropic` set explicitly** — not `auto`.
2. The simforge Postgres up, and the `forge_id` + `module_id` used on 10 September.
3. Then: `python scripts/second-model-battery.py <forge_id> <module_id>`, which refuses to run if
   any of (1) or (2) is wrong rather than producing a number.

Eight probes is a handful of calls. This is minutes of work once the key exists.

## What this blocks downstream

**P-02 is waiting on this number and should be told it is not coming from this package.** Per the
card, P-01 does not schedule anything and does not draft the ADR-0051 amendment — that amendment is
Ivan's to rule on, and it is moot until there is a second-model number to rule on.

**ADR-0053 was reserved for P-01 and is left UNUSED.** The finding here is an instrument hazard and
a blocked run, not a decision. Spending a ledger number on "the run did not happen" would put a
decision in the record where there is none. The reservation is free for whoever completes A0.
