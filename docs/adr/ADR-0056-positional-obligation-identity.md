# ADR-0056 — An obligation's identity is its position, and rationale stays out of the grading key

**Status:** accepted · **Decided by:** Ivan, 13 September 2026
**Amends:** `Obligation.ref` and `parse_obligation` (ADR-0051's authoring path)
**Supersedes nothing.**

---

## Two defects, one cause

`parse_obligation` was written for terse one-liners. The live never-do entries carry their
reasoning in the same sentence, and two things followed:

1. **Rationale entered the grading key.** `\bas\b` and `\bwithout\b` split and then consumed to the
   END of the entry, so `forbidden_readings` absorbed the author's reasoning.
2. **The ref carried a digest of the whole sentence**, making an obligation's identity depend on
   prose that includes that reasoning.

Both are the same unstated assumption: **that a prohibition is one clause.**

## The splicing, and that it failed OPEN

    before   readings ['zero', 'grade F. It means nothing was assessed. Shared rule 1: an
                       absence of clients is a fact about the records']
    after    readings ['zero', 'grade F']

`_grade_over_read` compares the agent's recorded value to these by normalised equality. A reading
carrying a rationale clause **can never equal what a model says**, so the check could not catch the
violation it named. Measured against the live seven prohibitions:

| agent asserts | before | after |
|---|---|---|
| `grade F` | missed | **caught** |
| `a forecast` | missed | **caught** |
| `verified` | missed | **caught** |
| `zero`, `money` | caught | caught |
| `42%` | missed | still missed - #2 has no readings (ADR-0055's narrowing) |
| `flat` | missed | still missed - reading is `'a flat trend'`; ADR-0051's documented exact-match gap |

**Violations caught: 2 of 7 -> 5 of 7.** The two remaining are previously recorded defects, not
splicing.

**Note the direction.** `must_disclose` (ADR-0055) failed CLOSED - no correct answer could pass.
This failed OPEN - most incorrect answers did. Opposite failures from the same assumption.

## The ruling: positional identity

    before   {module_id}#{index}:{sha256(text)[:12]}
    after    {module_id}#{index}

**What this rests on, and it is not a caveat.** The digest protected against grading a stale
obligation, and that is already closed upstream:

- a never-do edit changes `forge_operating_instruction.content`;
- a **database trigger** recomputes `content_hash` (`instruction_hash(NEW.content)`) - it is not
  accepted from a caller;
- `recompute_staleness` marks every certification bound to the old hash `stale_instructions`;
- SimForge's `is_content_hash_void` VOIDs a run whose text moved - *"Not 'questionable' - VOID."*

**A stale index cannot be graded against a live certification.** The ref does not need to carry the
sensitivity a second time.

### Correction: the index was never discarded

The ruling was argued partly on the premise that `parse_obligation` discarded `enumerate`'s index
for a derived value that collided. **It did not.** The index has always been in the ref, and
rationale-only differences have never collided: two such entries get different indices *and*
different digests, yielding four probes with four distinct keys. That was true before this change
and is asserted as a regression guard, not as evidence of a fix.

The `(obligation_ref, scenario_class)` collision remains reachable only when one obligation yields
two probes of the same class - which the generator cannot do, and which only the hand-authored A0
set ever did. Dropping the digest neither causes nor cures it.

### What positional identity gives up

Two properties, not one, and the second was not named when the ruling was made:

- a **reworded** entry keeps its ref, where it used to get a new one - intended;
- a **reordered** list is now **invisible at the ref level**. `{m#0, m#1}` before and after, and
  `m#0` names whichever prohibition sits first, which may be a different prohibition.

Both are covered by the same chain. But the ref previously carried half this distinction and now
carries none of it, and that is the trade. `test_the_ref_is_positional_and_what_that_gives_up`
asserts it rather than leaving it implicit; it replaces
`test_an_obligation_ref_survives_reordering_and_not_rewording`, which asserted the sensitivity this
ADR removes.

## The two things this ruling rests on

**The invalidation is a sweep, not a constraint.** Between an edit and the next `run_all`,
certifications still read `certified` against the old hash. That is a property of the staleness
model, not of identity: **positional refs are no worse in that window than content-derived ones**,
because the certification is the thing that is stale, not the ref. The sweep also carries the
snapshot-dependent `checked` denominator recorded in calibration Entry 9.

**`obligation_ref` and `content_hash` are not interchangeable evidence.** One is SimForge's, over a
single entry as SimForge received it; the other is The Office's, over all eight instruction
sections. They agree because SimForge upserts what The Office sends, and **nothing asserts they
move together** - a change to a non-`never_do` section moves one and not the other. Neither may be
read as a proxy for the other.

## Scope

`obligation_ref` is **in-memory only** - it is never persisted, so there is no migration and no
stored ref to reinterpret. Verified by grep before the change.

## Still open, unchanged

`_grade_over_read` matches by normalised string equality, so an agent asserting a forbidden reading
in different words is still uncaught - ADR-0051 records this as fail-open in the concealment
direction. And a concealment probe whose prohibition names no forbidden reading still cannot fail
(ADR-0055).
