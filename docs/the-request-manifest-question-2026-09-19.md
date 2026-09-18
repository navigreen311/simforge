# Would a request manifest be worth having?

Read-only. Companion to [ADR-0083](adr/ADR-0083-a-boundary-that-ignores-is-not-a-boundary.md).

---

## What the response manifest actually is

`theoffice/broker/simforge_response_manifest.json` is not a schema. It is **a file of reasons**:
every field SimForge may return, each with a sentence saying why The Office is entitled to it.

```
"module_levels": "module_id -> certified | certified_with_declared_absence | demonstrated.
                  THE FIELD WORTH HAVING: the per-module certification level, which is what
                  the certification run needs and what the old contract discarded by
                  returning only a ref."
```

And its README says what the machinery is for:

> *Rule of thumb: The Office is entitled to learn WHETHER an agent passed and by how much against
> what threshold. It is not entitled to learn WHY, because a rich enough explanation of a failure
> reconstructs the scenario that produced it.*

`tests/golden/test_no_read_path.py` fails their build when a response carries a field the file does
not name. **Adding a field is a reviewable act**, and the review is about a specific hazard: the
held-out set leaking back to the party being examined.

## So the question is not "should requests be checked too"

`extra="forbid"` already checks them, and as of ADR-0083 it does. The question is **whether the
request direction has a hazard worth a file of reasons.**

### The response direction's hazard

**Leakage.** Every field is a channel out of the examiner's private corpus, and the manifest is
a standing invitation to ask *"can this field carry scenario content?"* before it ships. That is a
real question with a wrong answer.

### The request direction's hazards, and they are different

| | |
|---|---|
| **An undeclared field is dropped** | what ADR-0083 just fixed. `extra="forbid"` is the whole remedy; a file of reasons adds nothing |
| **A declared field is unused** | `certification_units_requested` carries `agent_id` and SimForge consumes only `module_id`. The Office's own comment says so: *"SimForge consumes only `module_id` from this list, so this is a declaration rather than an instruction"* |
| **A declared field is misused** | `agent_id` is sent as an Office uuid and consumed as a Village ref. **Nine months of this repository's worst defect, and neither a schema nor a manifest would have caught it** — the field was declared, populated and well-typed |

**The third is the interesting one.** It is the defect ADR-0083's `village_agent_ref` fixes, and a
manifest would not have prevented it, because a manifest records *what may be sent*, not *what the
receiver does with it.*

## What a request manifest would actually buy

One thing the type system cannot express, and it is the second row above: **which declared fields
are read, and which are decoration.**

```
"certification_units_requested[].agent_id":
    "SENT AND NOT READ. SimForge consumes only module_id from this list. Kept because the
     declaration is true and worth being true; nothing here acts on it."
"instruction_set_ref.authored_by":
    "Nullable; defaulted to `office`. The Office sends null on purpose - it authors under a
     human's id and will not put a person's uuid in another system."
```

That is a real category. This week alone produced two findings of exactly that shape — the venture
arriving twice per call and stored nowhere, and `agent_id` being read as something it is not.

## What it would take

| | |
|---|---|
| **The file** | ~40 fields across `ForgeOperationCurriculum`, `OperationRunStartRequest` and `GateResultRequest`, each with a sentence. **Half a day of writing, and the writing is the value** — the sentences are where "sent and not read" gets noticed |
| **The test** | mirror `test_no_read_path.py`: walk the Pydantic models, assert every field is named. ~30 lines. **In SimForge**, because SimForge owns the request schemas |
| **The upkeep** | one line per new field, forever |
| **Whose** | SimForge's entirely. The response manifest lives with the party that *receives*, so the request one lives with the party that receives requests |

## The honest case against

**`extra="forbid"` already closes the hazard the ruling named.** A manifest adds a second artefact
that must agree with the schemas, and two descriptions of one thing drift — this repository has
recorded that pattern under its own heading more than once. The response manifest earns its keep
because it encodes a *policy* (no read path) that no type can express. A request manifest would
encode mostly what `operation_payloads.py` already says, plus one column of prose about usage.

**A narrower version gets most of the value:** not a manifest, but a required `#:` comment on every
request-model field saying who reads it — enforced by the same kind of test, living in the file it
describes, with no second artefact to drift.

## Not recommended, and not built

The measured facts: the hazard the response manifest exists for has no counterpart in this
direction; the hazard that *does* exist here is fields that are declared and unread; and neither
`extra="forbid"` nor a manifest catches a field that is read as the wrong thing, which is the defect
that actually cost this repository six hand-corrected rows.
