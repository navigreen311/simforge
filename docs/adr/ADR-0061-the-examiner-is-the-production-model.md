# ADR-0061 — The examiner is the production model, and an agent nobody can name is not examined

**Status:** accepted · **Decided by:** Ivan Green, 17 September 2026 · **Built by:** the coordinator
**Extends:** ADR-0054 (the examiner is named), ADR-0060 (a certification names the model file).

---

## The rulings

**1. The examiner is the production model. Certification runs on phi4, the model Village agents run
on, pinned by digest, never a moving tag.**

**2. SimForge refuses to run a battery for an agent it cannot identify. Certifying an agent with no
name, role or identity is an empty pass.**

Two rulings, one shape: a certification has to be about something. Ruling 1 is about the model
asking the questions; ruling 2 is about the agent answering them.

---

## Ruling 1 — the examiner

### What was wrong

`LLM_PROVIDER=auto`, and `auto` resolves to ollama-if-reachable-else-stub. `OLLAMA_AGENT_MODEL`
defaults to `llama3.1:8b`. So the examiner was whatever those two settings — turned for scenario
runs and demos — happened to be, and the Village's own model was never consulted.

ADR-0060 made the candidate recordable. This makes it **checkable**, which is a different thing:
recording `ollama/llama3.1:8b` faithfully is no help when production runs `phi4:latest`.

### Where the Village's value is read from

`mate.ollama_model_routes.agent` in the Village's `config.yaml`, at `VILLAGE_CONFIG_PATH`.

**That key holds a tag in the live deployment and a model type in the code's defaults**, so both
are read:

    agent: phi4:latest     <- the live config.yaml. The tag, directly.
    agent: default_llm     <- mate.py's in-code default, resolved via mate.models.default_llm.model_id

This was measured before it was written. Assuming only the indirection — which is what
`modules/frameworks/mate.py` does — would have raised on the real file.

**The settings are somewhere else and that is the trap.** `temperature` and `max_tokens` live under
`mate.models.<type>` whichever form the route takes. A first version read them only on the indirect
path, reported `{}` against the live file, and made "no divergence" mean "did not look" — caught by
running the check against the real config before it was finished. They are now found by matching
`model_id` against the resolved tag, and an ambiguous tag (the live file points `reasoning_llm` and
`code_llm` at one model at different temperatures) reports nothing rather than picking.

Read at check time, not cached: a production model change should be visible on the next battery.

### What happens if the two disagree — five refusals, five fixes

Every one is a `BatterySkipped`, which posts no outcome. A battery that ran anyway would produce a
certification asserting it was earned on the production model, and nothing downstream could tell.

| reason | what it means | the fix |
|---|---|---|
| `no_exam_model_digest_is_pinned` | `EXAM_MODEL_DIGEST` is empty | read it from `/api/tags` and set it |
| `the_exam_model_could_not_be_described` | the provider has no file to name | pull the model, or start Ollama |
| `the_pinned_digest_is_not_what_the_tag_serves_now` | **the tag moved** | re-pin deliberately, or fix the config |
| `the_exam_model_is_not_the_model_the_village_runs` | SimForge asks for X, production runs Y | make them the same |
| `simforge_cannot_read_which_model_the_village_runs` | `VILLAGE_CONFIG_PATH` unset or unreadable | point it at `config.yaml` |

They are named separately because they send you to five different files. One
`examiner_not_acceptable` would be a refusal that starts an investigation.

**The last row is the one worth arguing about.** The tempting alternative is to enforce the local
pin and skip the comparison when the Village config is absent. That is worse than it looks: the
certification still says it was earned on the production model, and the only thing that changed is
that nobody checked. **"I could not see production" is not "it matched."**

### What is deliberately NOT refused

**A settings difference.** The Village runs its agents at temperature 0.7 with a 4000-token cap;
the battery examines at 0.0 and 2048, because an exam whose answers move between runs is not a
certification. Measured live: the check reports
`{'temperature': {'village': 0.7, 'exam': 0.0}, 'max_tokens': {'village': 4000, 'exam': 2048}}`
and proceeds.

Those are genuinely different requirements and this ADR does not resolve them. Refusing here would
resolve it by implication; recording it was ADR-0060's job and it is done. **It is the open
question this ruling leaves behind**, and it is stated rather than buried.

### The exam has its own runtime

`build_exam_runtime` / `get_exam_llm` ask for `EXAM_MODEL_TAG` over Ollama, and do **not** route
through `LLM_PROVIDER`. That setting answers "what should a scenario run use", and its `anthropic`
branch is a cloud model — none of which is a decision a certification should inherit from a setting
turned for a demo. The cloud provider remains reachable through the ordinary agent runtime, and
ADR-0060 already holds anything it produces short of a certification.

---

## Ruling 2 — the agent

### What made this reachable, and why nothing failed

`AgentRuntime.assemble_system_prompt` is deliberately forgiving: every Village read goes through
`_safe`, which swallows `VillageReaderError`, and the name falls back to the id itself. That is
right for the scenario runner and wrong for a certification, because the fallback produces a real
prompt — *"You are e27fc174-01ac-4090-8127-f4f0cec91bf9, a Village agent"* — that a model answers,
a grader grades, and a certification records.

**Nothing raised. Nothing was NOT_RUN. The pass looked exactly like a real one.** It was a pass
about nobody, which is the failure Ivan named.

The leniency is not changed: it is correct where it lives. The battery is what must not rely on it,
so the check happens first, before the examiner check and before the never-do list — it is the
cheapest of the three and the only one that fails silently.

### Two reasons, not one

    the_agent_is_not_in_the_village_tree        the id resolves to no agent directory
    the_agent_identity_carries_no_name_or_role  the directory exists and says nothing

Different fixes — a missing agent or a wrong id, against an identity file nobody filled in — so a
single `unidentified` would send somebody looking in the wrong place.

**Logged at WARNING, not info.** Every other skip is a run the battery has nothing to say about;
this one is a run that was handed over *for certification* against an agent the examiner cannot
name. Somebody needs to see it.

### What is NOT checked here

Whether the id is the right *shape*. The Office sends its own `office_agent_id` (a uuid); the
Village keys agents by a ref like `victor_serath`; the mapping exists in The Office's
`office_agent_identity.village_agent_ref` and does not cross the boundary. That is a seam to build,
not a string to validate — and the three Greenstone agents are absent from both Village trees
anyway. The report sizes it.

---

## What this costs

Six existing battery tests pointed at `no-such-village` on purpose and now point at the committed
fixture, because a test that examined a blank would be testing the thing ruling 2 forbids. The old
path survives in `test_a_battery_refuses_an_agent_it_cannot_identify`.

One test changed shape rather than meaning: `StubProvider` can no longer reach the battery through
`battery_for_run` (it cannot be pinned), so its grading behaviour is asserted through the runner and
its refusal is asserted separately.

## What this does not decide

Whether the exam should run at production's temperature or its own. Whether the Village ref should
travel on the run, be looked up, or be declared. Whether the three Greenstone agents should exist in
the Village at all.
