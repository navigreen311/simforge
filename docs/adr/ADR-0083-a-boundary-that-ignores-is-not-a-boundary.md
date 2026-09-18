# ADR-0083 — A boundary that ignores is not a boundary

**Status:** accepted · **Decided by:** Ivan Green, 19 September 2026 · **Built.**

---

## The ruling

**A boundary that ignores is not a boundary. Request payloads declare their fields and refuse
unknown ones, as responses already do. Silently dropping a field both sides believe was delivered is
worse than a refusal.**

---

## The asymmetry it closes

The **response** side has been strict since the beginning: The Office's
`broker/simforge_response_manifest.json` enumerates every field SimForge may return, and
`tests/golden/test_no_read_path.py` fails their build when a response carries one the file does not
name. *Adding a field there is a reviewable act.*

The **request** side had no equivalent. Pydantic's default is `extra="ignore"`, so a submitter could
send `expected_answer` — the transcribable half of an answer key, the thing SimForge would grade an
agent against — and get a `200` back with nothing kept. **No error on either side, and both of them
believing a key had been delivered.**

That is the same defect as P1's, one layer out. P1 fixed *validated and stored nowhere*; this fixes
*not even validated.*

## What was built

**Declared.** `ExpectedAnswer` — `act`, `record` / (`record_subject` + `record_claim`),
`record_claim_options`, `expected_caveat` — on `OperationScenarioSubmission`; `village_agent_ref`
on `OperationRunStartRequest`.

**Refused.** `extra="forbid"` on both, and on `ExpectedAnswer` itself — which is the one that
matters most, because a misspelled `record_subjekt` would leave a scenario storable, ungradable and
looking complete.

**Stored.** Six columns on P1's table plus `OperationRun.villageAgentRef`, one migration, a CHECK
that a subject and a claim travel together.

**Validated, because a key that cannot be satisfied is worse than no key.** Four refusals, each with
a reason: an act the protocol does not offer; both record forms at once or neither; a subject with
no claim; **a right answer that is not on its own option list.** Every one of those would store
cleanly and then grade every agent as failing, which reads as a finding about the agent.

## What `extra="forbid"` would start refusing

**Nothing that anything sends today, and that was checked rather than assumed.**

Reading `broker/provisioning.py` on `origin/main`, The Office's two request payloads are:

```
run/start    run_ref · unit · forge_id · instruction_content_hash · rubric_kind
             module_id · agent_id · department_id · scenario_count · coverage_denominator
curriculum   instruction_set_ref · certification_units_requested · operation_scenarios
             coverage_declaration · module_never_do · module_not_applicable
             scenarios: scenario_class · instruction_section · module_id
                        expected_behavior · expected_escalation
```

**Every key is declared.** The full suite confirms it empirically: 1,062 tests pass with the forbid
in place.

**What it would refuse in future** is the point rather than a cost: a field The Office adds and
SimForge has not accepted yet now fails at the boundary, loudly, on the first call — instead of
being dropped for however long it takes somebody to notice a column full of nulls.

**Where it was deliberately NOT applied:** the other fifteen models in `operation_payloads.py`,
including `GateResultRequest` and the outbound result shapes. The ruling named two models. Widening
it is a one-line change per model and a decision about whether an old SimForge should refuse a newer
SimForge's gate result — see below.

## `village_agent_ref`, and two identities that were one

`OperationRun.agentId` is consumed as a **Village** ref by `check_agent_identity`, and The Office
sends its **`office_agent_id`** there. Every run it opened in September refused on identity, and six
rows were corrected by hand from `office_agent_identity.village_agent_ref`.

Both ids now travel and **each side gets the one it uses**:

| | reads | why |
|---|---|---|
| the examiner's lookup | `villageAgentRef` | `assemble_system_prompt` resolves a Village ref |
| the outcome The Office receives | `agentId` | its certifications are keyed on its own uuid |

An outcome returning the Village ref would be a verdict about an agent The Office cannot find, so
`build_gate_result_request` now takes `run.agentId` for the outcome while the battery takes
`village_ref` for the prompt.

**Optional, and the fallback is unchanged.** The Office does not send it yet; when it is absent the
battery falls back to `agentId` and fails exactly as it does today — loudly, by name, never quietly.
A required field here would refuse every curriculum The Office currently sends, which is a boundary
that is not a boundary in the other direction.

## And one thing the ruling did not ask for but the schema now says

`expected_answer` is **optional**. The 44 split keys are drafts and nothing submits them yet. A
scenario stored without one is readable and not gradable by transcription, which is the honest state
of those drafts rather than a gap.

## Read-only alongside

Whether a **request manifest**, matching the response one, is worth having:
[the-request-manifest-question.md](../the-request-manifest-question-2026-09-19.md).

Verified: 1,062 pass, 2 skip; ruff clean.
