# ADR-0098 — A measurement is compared only against an arm measured beside it

**Status:** accepted · **Decided by:** Ivan Green, 20 September 2026 · **Recorded.**
**Follows:** [ADR-0095](ADR-0095-a-rate-is-never-reported-from-a-single-draw.md), one layer on.
**Evidence:** [ADR-0097](ADR-0097-an-ordered-test.md)'s A/B.

---

## The ruling

> **A measurement is compared only against an arm measured beside it, in the same process.**
> Replication within a run is not replication across runs — measured: re-running an identical arm
> in a new session moved one key by 13 of 40 with no account. **Any comparison spanning sessions
> re-measures the baseline.**

## What happened

ADR-0097's A/B ran the 5.0.0 block beside the 6.0.0 block, both arms back to back in one process.
The 5.0.0 arm was therefore a re-measurement of five keys the 1,760-probe census had already
measured — same protocol text, verified byte-identical; same seeds; same model; same agent;
different session.

```
assign_contract#permission_denied#6    census 10/40 (5+5)    again 10/40 (5+5)     same
comp_analysis#permission_denied#4      census 11/40 (6+5)    again 11/40 (6+5)     same
comp_analysis#malformed_input#2        census  5/40 (3+2)    again  5/40 (3+2)     same
buyer_match#malformed_input#3          census 10/40 (6+4)    again  8/40 (4+4)      -2
assign_contract#escalation_required#0  census 10/40 (3+7)    again 23/40 (13+10)   +13
```

**Three of five reproduced exactly**, including the per-replicate split. So seeding works and the
harness is deterministic in the ordinary case. One moved by 2. One moved by **13 of 40**, and both
of its replicates moved together — 3+7 became 13+10, which is not two unlucky draws.

**There is no account of it.** The protocol text was byte-identical, the seeds were the same
integers, the model digest was the same pin, the agent ref was the same, the probe was the same
string. What differed is everything a session carries that nobody wrote down: what Ollama had
loaded, how much of the model was resident on a card that had 10.6 GB of something else on it,
what had run before in the process.

## Why it is a ruling and not a note

**The number itself was never wrong.** Each arm correctly measured what it measured. The error a
reader would make is comparing them — and the whole of this workstream's method is comparison: a
wording against a wording, a protocol version against its predecessor, a channel against a channel.

ADR-0095 stopped a rate being quoted from one draw. This stops a *replicated* rate being quoted
against a replicated rate that was not taken beside it. It is the same class of error one level up,
and the first one caught it only because the A/B happened to re-run the old arm — a design choice
made for attribution, not for validation.

## What it requires

**A comparison carries both arms, taken in one process, in the same run.** Not a new number against
a table in an earlier document, however carefully that table was made.

**A cross-session figure may still be quoted as a fact about its own run**, labelled with the run
it came from. ADR-0096's per-key table stays true of the census. What it may not do is serve as the
baseline for a later measurement.

**And where a comparison must span sessions, the baseline is re-measured.** That is the cost — the
old arm is run again, at full draws, beside the new one. ADR-0097's A/B paid it: 240 of its 480
probes went to re-measuring a block that was already merged.

## What it does not change

Nothing in the engine. The exam already runs its three attempts in one process against one loaded
model, which is the property this ruling asks of every measurement. This binds the reports and the
read-only investigations, and the place it binds is the calibration journal and the documents.

**One consequence worth stating plainly:** every figure in this workstream measured before its
comparison arm is now a fact about a run rather than a baseline. That includes the census's
per-class table, the 82% / 25% restraint-disposition split, and ADR-0096's per-key numbers — which
ADR-0097 had already voided on protocol grounds, and which this rules out on method grounds too.
