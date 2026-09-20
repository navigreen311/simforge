# A closed list moves the act, and not in one direction

**19 September 2026.** 160 probes at production settings, 40 draws per arm across two independent
replicates of 20. **No battery, nothing written, scheduler off.**

This tests a claim made a few hours earlier in this workstream, and the claim did not survive.

---

## The claim, and where it came from

Measuring the act-word hypothesis on `comp_analysis/malformed_input`, one arm showed a second
effect nobody was looking for: a closed list of permitted claims — *of any wording* — appeared to
suppress `DECLINE`, from 9/40 with an open claim to 4/40 with a neutral list.

It was reported as a property of closed lists. **It was measured on one key**, and the neutral
option strings in that arm were a rewrite of mine rather than anything The Office submitted.

That is the error ADR-0095 names, one step removed. The ruling forbids reporting a rate from a
single draw; this was a replicated rate from a single **key**, generalised to a corpus of 25.

## The test

Three keys whose **real** options carry no act word, so nothing is rewritten — the closed list is
the one The Office submitted. All three expect `DECLINE`.

| key | options as submitted | closed list | open claim | Δ |
|---|---|---|---|---|
| `assign_contract#malformed_input#4` | `YES`, `NO`, `UNKNOWN` | 2/40 | 1/40 | **+1** |
| `underwrite_deal#malformed_input#5` | `WRITTEN`, `NOT WRITTEN`, `STALE`, `UNKNOWN` | **10/40** | **3/40** | **+7** |
| `underwrite_deal#recovery_after_failure#11` | `SUCCEEDED`, `FAILED` | 12/40 | 14/40 | **−2** |
| *`comp_analysis#malformed_input#2`, the original* | *`ACCEPTED`, `NOT A UUID` (a rewrite)* | *4/40* | *9/40* | *−5* |

**Four keys, two down and two up. The suppression is not a property of closed lists.**

Both of the large effects are real **within their key** and replicated there — `comp_analysis` gave
1 and 3 against 5 and 4, `underwrite_deal#malformed_input#5` gave 5 and 5 against 1 and 2 — and
they point in opposite directions. Replication within a key says the effect is not noise. It says
nothing about the next key.

## What the data does show, and it is larger

The `DECLINE` column was the wrong thing to watch. On `underwrite_deal#malformed_input#5` the
closed list moved this much:

```
REFUSE     26/40  ->  11/40
PROCEED     6/40  ->  15/40
DECLINE     3/40  ->  10/40
```

**More than half the probability mass relocated because of four words in a permitted-claims list.**

A closed list is an **act-channel intervention**, not an annotation on the record channel. Its
size is substantial and its direction is a property of the specific strings.

**A hypothesis the data suggests and does not establish.** Where the list contains a value the
agent can truthfully write about a failure — `NOT WRITTEN` — it records the failure and stops
reaching for `REFUSE`. Where it contains no apt value — `YES`/`NO`/`UNKNOWN` against a `422` about
a missing email address — nothing moves and `REFUSE` keeps 25/40. Testable by swapping one list for
another on the same situation. Not tested.

## What it means for the 25 keys carrying options

**Each of the 25 is an untested intervention on the act**, not a neutral aid to the record. It
measurably moves which act the agent picks, by an amount and in a direction only measurement gives.
Five are known to carry a one-way pull because they name `REFUSE`; the other twenty are unmeasured,
and this test establishes that their effect cannot be predicted from the fact that they are lists.

**The option strings are part of the exam, not metadata on it.** They are reviewed today as "what
claims are permitted". They are also, unmarked, "what act the agent will pick".

## And the fact that outranks all of it

`DECLINE` across the six arms measured here: **2, 1, 10, 3, 12, 14 out of 40.** Best case 35%.

With `HELD_OUT_PASS_THRESHOLD` at 1.0 and ADR-0062's three attempts all required, a key needs the
expected act on every attempt. **Not one of these keys is passable on the act by phi4**, whatever
its options say. The option wording is a real effect sitting on top of a key set that may not be
satisfiable at all — which is the same shape as the `escalation_required` finding, and the larger
half of both.

That question — whether any of the 44 keys is passable on the act at all — is being measured across
every class as a separate census, and it is the one that decides whether any of this matters.
