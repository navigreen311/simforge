# ADR-0126 — A decline probe asks for the prohibited act, not the rule's remedy

**Status:** accepted · **Decided by:** Ivan Green, 2026-09-25 · **Built.**

---

## The ruling

> A decline probe asks for the prohibited act, not the rule's remedy.
> `_decline_probe` copies the whole never-do entry into the request, so
> sentences after the prohibition ride along.
>
> *Measured: assign_contract#0's request carries the rule's own remedy, "let a
> human check the deal", so the probe asks the agent to escalate and fails it
> for escalating. Both agents, every seed, across two instruction versions.*

## Built

`prohibition_sentence(text)` in `held_out.py`: the entry's first sentence.

- `_decline_probe` builds its request from that sentence only.
- So does the partition's `_variant`, which frames the same act three ways
  (ADR-0108). It had its own copy of the whole-entry line.
- A sentence ends at `.`, `!` or `?` followed by a space and a capital or an
  opening mark. `e.g. a price` does not end one.
- A full stop inside backticks does not end one.
- **Only the request is cut.** `Obligation.text` and `obligation_text` keep
  the whole entry, so the obligation examined is unchanged.

## What it changes

- Every decline probe whose entry runs on past its prohibition asks a
  different, shorter question. Battery results on those probes move.
- **Sealed partitions are untouched.** Their scenario bodies are stored, and
  the digest is over what was stored.
- A partition authored after this carries the new probes and framings, so its digest
  differs from one authored before, for the same instructions.
- `battery_digests` uses the same builder, so partition/battery disjointness
  (ADR-0108) still compares like with like.

## What it does not do

- The over-read probe (`silent_failure`) is not touched. It already reads
  only the clause (`_first_sentence`).
- ~~No protocol change; no version bump.~~ Wrong: ADR-0127 bumps to 8.0.0.

## Tests

`tests/unit/test_a_decline_probe_asks_for_the_act.py`, on assign_contract's
live never-do list:

- the timeout probe asks for a retry and carries none of the remedy;
- no decline probe carries a sentence after its prohibition;
- the obligation keeps the whole entry;
- a one-sentence entry is unchanged;
- backticks and abbreviations do not end the prohibition;
- no partition framing of the timeout probe carries the remedy.

Mutation: restoring the whole entry in `_decline_probe` fails 2 of 7;
in `_variant`, 1 of 7.
