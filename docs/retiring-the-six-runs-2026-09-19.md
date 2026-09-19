# Retiring the six exam runs — what it would take

Read-only. **Nothing retired.** Sized only.

---

## What exists

Six Unit-A runs on `cre-forge`, all closed, from 18 September:

| run | agent | module | content hash |
|---|---|---|---|
| `…assign_contract@cc49a49c` | `ronan_valek` | `assign_contract` | `cacf28ef5ba0…` |
| `…assign_contract@c8afb0e6` | `seraphine_valek` | `assign_contract` | `cacf28ef5ba0…` |
| `…buyer_match@cc49a49c` | `ronan_valek` | `buyer_match` | `648e494d6026…` |
| `…buyer_match@c8afb0e6` | `seraphine_valek` | `buyer_match` | `648e494d6026…` |
| `…comp_analysis@e27fc174` | `victor_serath` | `comp_analysis` | `d57e1d204bbb…` |
| `…property_lookup@e27fc174` | `victor_serath` | `property_lookup` | `5aab8992fefb…` |

They produced **6 `failed` and 2 `provisional`** agent-operation certifications.

## The hazard, stated precisely

A verdict earned on the **un-split** scenarios must not be matched to a submission of the **split**
ones. The risk is not that the rows are wrong — they are accurate records of what happened — but
that something reads one as current evidence about a curriculum it was never sat against.

## Why the existing machinery mostly handles it

**Every certification binds to an `instructionContentHash`.** The split keys change the scenarios,
which changes the content hash The Office submits, which means:

- `recert.py` already moves a cert to **`stale_instructions`** when the instruction set is
  re-authored under a new hash;
- `close_run`'s **content-hash VOID** already drives a cert to `revoked` when a run executes against
  a hash the submission did not declare;
- a new submission produces new runs under a **new hash**, and nothing joins an old cert to it.

So a naive "it will get matched anyway" is not the failure mode. **The failure mode is subtler:**
a reader — a dashboard, a coverage view, a person — treating six `failed` rows as *this agent
cannot do this module* when what they record is *this agent could not answer a scenario that no
longer exists.*

## What retiring them would take

### Option A — let the existing hash binding do it. **No work.**

Submit the split keys under a new content hash. The old certs stay as they are, bound to hashes
nothing will submit again. Honest, costs nothing, and leaves the ambiguity above: the rows read as
verdicts about agents rather than about withdrawn scenarios.

### Option B — mark them, without inventing a state. **Half a day.**

The seven-state machine has no `superseded` and **adding one is the expensive choice** — every
consumer of `OperationState` would need to learn it, `is_assignable` would need a rule, and the
frontend renders states by name.

Cheaper and truer: a **column, not a state.** `OperationCertification.supersededBy` (the content
hash that replaced the one it was earned under) plus `supersededAt`. Nullable, written by a small
script, read by the views that already show a cert's basis. The state stays what it was — the row
still records a `failed`, because it did fail — and the row now also says *against what, and that
the what is gone.*

- one migration, two columns
- a script that sets them for a named list of runs
- `views.py` and `battery_result.py` carry them, as they already carry `rubricSpreadMeasure`
- **no state-machine change, no `is_assignable` change**

### Option C — revoke them. **Wrong, and worth saying why.**

`revoked` means *voided* — a content-hash mismatch, drift, a misoperation incident. These six are
none of those. Revoking would make the record say the verdicts were invalid when they were
correct: phi4 genuinely failed those probes on 18 September, and ADR-0068's 8→0 RECORD result was
measured on them. **Rewriting a recorded result's basis is the thing this repository has now ruled
against three times.**

### And the piece none of the options covers

**`RESPONSE_PROTOCOL_VERSION` is already the honest marker and nothing reads it.** Those six
verdicts were taken under **3.0.0**; the protocol is at **4.0.0** and the naming design will make it
5.0.0. Every attempt record carries its version, so *"this verdict was earned under a protocol two
majors ago"* is already in the database — it is simply never surfaced.

A reader that showed the protocol version beside a verdict would retire these six by making them
self-describing, and would do the same for every future one automatically. **That is a smaller
change than Option B and it generalises**, which is the argument for preferring it.

## Recommendation

None. Sized, not chosen. The three facts worth carrying into the decision:

1. The hash binding already prevents a *mechanical* mis-match; the risk is a *reading*.
2. A new state is the expensive answer and a column is the cheap one.
3. The database already knows these are old — under `response_protocol_version` — and nothing
   asks it.
