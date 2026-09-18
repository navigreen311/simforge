# ADR-0066 — Phase 1 certifies the agent-plus-model pair, and the dilution is on the record

**Status:** accepted · **Decided by:** Ivan Green, 17 September 2026
**Closes the open question in:** ADR-0065. **Not built:** the workstream below.

---

## The ruling

> For Phase 1, the exam certifies the agent-plus-model pair as it stands, with the prompt carrying
> name and title only. Recorded as a known dilution: with every agent on phi4, a pass is close to a
> claim about the model. Closing it means carrying the Village's beliefs, affect and self-model into
> the prompt, and that is its own workstream.

---

## What a Phase 1 certification therefore means

**"This agent, on this model, under these instructions, refused what it was told never to do."**

The model half is precise — ADR-0060 records the file digest, the quantization and the generation
settings, and ADR-0061 pins the examiner to the model production runs. The agent half is a name and
a job title.

So a Phase 1 pass is a **joint** claim about a pair, and the ruling's own sentence is the honest
reading of how the two halves divide: with every agent on phi4, two agents' exams differ by a name
and a title, and most of what the result measures is the model.

**It is not nothing.** The prohibitions in the prompt are the agent's own module's, numbered, and
the verdict turns on whether *that* module's rules were held. A pass is specific to the
agent × module × instruction-hash triple even when the persona behind it is thin.

**And it is less than it sounds.** Recorded here so nobody has to rediscover it from a green
dashboard.

## Why this is a ruling and not a defect

Everything needed to close it exists — `village.db` holds the material, populated, for all three
Greenstone agents. What does not exist is a decision about how to render numeric cognitive state
into prompt text, and one prior ruling that gates it (see the report). Both are real work with real
choices in them, and neither is a reason to hold Phase 1.

The alternative to shipping Phase 1 diluted is shipping nothing while the mapping is designed.

## What is on the record because of this

- The dilution itself, named, above.
- `RESPONSE_PROTOCOL_VERSION` (ADR-0064) and the model identity (ADR-0060) already stamp what a
  result was earned under. **A prompt change is the third axis and is not stamped.** When the
  workstream lands it will make Phase 1 results incomparable exactly as the protocol rewording made
  the A0 baselines incomparable — and the report recommends that the prompt carry a version too,
  before rather than after.

## Sizing, and one ruling that comes first

In [the report](../phase-1-dilution-and-the-cognitive-layers-2026-09-17.md). The headline: the raw
material is ~10,400 tokens per agent against a ~630-token exam prompt, so it cannot be injected —
it has to be summarised, and every summary is a decision.

And one finding that should be settled before any of it is carried: **`_grade_decline` passes a
bare escalation**, so a field that makes an agent escalate more raises its pass rate without the
agent having recognised any prohibition. `aptitudes` and `self_model_data` are exactly such fields.
That is a ruling about the grader, and it gates the workstream rather than following it.

## What this does not decide

Whether Phase 2 carries all of the material or some of it. Whether `_grade_decline` should keep
passing an uncited escalation. Whether the prompt gains a version stamp before the layers do.
