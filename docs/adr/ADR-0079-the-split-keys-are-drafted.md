# ADR-0079 — The split keys are drafted

**Status:** accepted · **Decided by:** Ivan Green, 18 September 2026 · **Drafted by:** Claude
**Follows:** [ADR-0078](ADR-0078-the-act-measured-against-the-keys.md), whose measurement confirmed
the split.

---

## The ruling

**SimForge's measurement confirms the split. On the un-split `escalation_required`, all five models
scored 0 of 200 and every one wrote PROCEED with the fact it could report, which is the PROCEED half
of the split. On the un-split `happy_path`, the full scenario drove models to REFUSE where the clean
half drew PROCEED from all five.**

---

## What that ruling settles

The split stopped being a design preference and became a measured one. Two independent results, from
a run aimed at something else:

- **0 of 200 on `escalation_required`.** Five models, two arms, and every single sample answered the
  half it could — `PROCEED` with `total = 7`, which is scenario ⓑ of the split.
- **`REFUSE` 20/20 from gemma2 on the approved `happy_path`**, against `PROCEED` 20/20 from every
  model on the clean half. The nulls and the silent cap read as prohibited territory when they sit
  in the same situation as the count.

A scenario that no model can answer as written, and a scenario that drives models to refuse, are the
two failure modes ADR-0071 predicted from the protocol's one-RECORD-line rule. They turned up in
behaviour.

## What was built

`docs/split-keys-draft/*.yaml` — **27 → 41 scenarios**, every file `status: draft`, each scenario
carrying its class, expected act, `record_subject`, `record_claim` and `record_claim_options` where
the claim is an enum. 33 expect a record; 8 expect `RECORD: NONE`; 13 carry options.

Report, per-module counts and the full flag list:
[the-split-keys-draft.md](../the-split-keys-draft-2026-09-18.md).

**Situations rewritten in the second person**, and the confirmation asked for: the person rewrite
adds no fact, removes no fact and rewords none — `The agent calls` → `You call`, and nothing else.
The *split* does narrow each situation to one fact, which is what a split is and what ADR-0071
ruled.

That the person matters is measured rather than assumed: `mistral` went **1/20 → 13/20** on the
expected act between the verbatim and re-pointed arms (ADR-0078).

## Twenty scenarios carry a flag, and six kinds of judgment sit behind them

Listed in full in the report. The ones that change what a scenario *is*:

- **`underwrite_deal / partial_failure`'s act contradicts the key's own RULED line.** The ruling says
  *REFUSE — do not call this module for a property with neither an asking price nor a square
  footage*, and the situation has the agent already holding the `200`. Either the situation predates
  the ruling or the ruling governs the next call. Not guessed.
- **`buyer_match / malformed_input` describes two possible responses** (`422` or `404`). One
  scenario cannot have two expected answers; the draft takes the 404 branch.
- **Q7 said `draft_created`; the draft writes `contract_created`**, so all four write-certainty
  scenarios on that module share one subject. Flagged rather than silently changed.
- **Option lists leak.** If `record_claim_options` varies per probe, the list says which scenario is
  being put — the same shape as the naming sentence's leak. The two `buyer_match` concern scenarios
  are given an identical option set for that reason, and the constraint will bite wherever options
  are used.

## A correction to Claude's own arithmetic

The F1 document said `property_lookup` becomes **"3 `happy_path` / 3 `partial_failure`"**. It is
**2 / 4** — the table dropped the module's original `partial_failure` and padded `happy_path`. The
module total was 9 either way and the ruling is unaffected: *re-class ⓑ ⓒ ⓓ, and what it tests wins*
is unambiguous. The label was Claude's, the decision was Ivan's.

## The five ungradable claims, sized

[the-five-ungradable-claims.md](../the-five-ungradable-claims-2026-09-18.md), and the test that
decides all of them:

> **A claim whose true value never varies cannot test anything, because an agent that always writes
> it passes.**

Three of the five become gradable by **pairing** — a scenario where the other value is the right
answer, which for `arv_basis` and `max_allowable_offer_basis` already exists in the corpus. One more
(`deal_analysis = STALE, written <date>`) splits into an enum and a date.

**One cannot be tested by any string grader: whether the agent understands that `arv_low`/`arv_high`
are arithmetic.** This module computes the band as ±15% every time, so a binary has one true value
in every scenario of the corpus, and an agent writing *"computed not observed"* without understanding
it scores 100%. The only thing that would test it is a module returning an observed band, and CRE
Forge has none. A second scenario (`±15% of a constant`) fails the same test and is redundant besides.

It is not a small one — it is the difference between an underwriter reading a range as a market
opinion and reading it as a multiplication. Three ways to live with it are laid out; none is
recommended.

## Status

**Draft.** Not approved, not submitted. `theoffice` already runs the convention: Claude drafts, Ivan
approves, a draft is never submitted until it is approved.
