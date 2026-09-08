# ADR-0048 — the never-do rule has no correct submission

**Status:** **Resolved 2026-09-08 — path B, plus the rejection of its mirror image.**
~~Open — a defect, recorded before it is fixed~~
**Date:** 2026-09-07 · **Resolved:** 2026-09-08
**Resolved by:** P-03, parallel build Wave 2. The second half was ruled by Ivan.
**Resolution:** see *Decision* at the end — the analysis above is left exactly as written
**Concerns:** `services/operation/scenarios.py` · `routers/operation.py` · ADR-0047
**Raised by:** The Office, while building the Gate 8 hand-over against this validator

## Context

`validate_curriculum_submission` rejects a submission whose declared `module_never_do`
carries an entry with no matching `never_do_violation` scenario, or one that does not
prove the agent declines:

```python
for entry in nd_entries:
    matches = [s for s in nd_scenarios if s.get("never_do_entry") == entry]
    if not matches:
        violations.append(
            f"module {mod}: never-do entry {entry!r} has no never_do_violation scenario"
        )
```

And `never_do_violation` is held out:

```python
# SimForge authors these classes as the HELD-OUT set (not exposed to The Office).
HELD_OUT_CLASSES: frozenset[str] = frozenset(
    {ScenarioClass.NEVER_DO_VIOLATION, ScenarioClass.SILENT_FAILURE}
)
```

## The defect

**There is no correct submission that declares a never-do list.**

A submitter that declares `module_never_do` honestly is rejected for not supplying
`never_do_violation` scenarios — a class it is structurally forbidden to author, because
SimForge owns it as held-out content. The rejection names work the submitter is not
allowed to do.

A submitter that omits the list passes. And `ForgeInstructionSet.neverDo` is then empty,
which defeats the reason that column was added:

```python
neverDo=never_do,  # so an n/a can be told from a coverage hole (FIX 2)
```

**The honest path is refused and the passing path erases the distinction the field was
added to keep.** Those are the only two paths.

## Why it was not caught

The rule is correct in isolation: a declared prohibition with nothing testing it *is* a
coverage hole, and saying so is right. What is wrong is *who* the rule asks. It was
written against a submitter that authors every class, and the held-out split — added for
a different and good reason — made two of the nine unauthorable by the only submitter
there is.

**Two controls, each sound, that cannot both be satisfied.** Neither review would catch
it, because each is correct where it is written. It surfaces only when something actually
submits a curriculum with a never-do list, which nothing had until now.

## The fix is on this side

> **Chosen 2026-09-08: B, plus a rejection this section did not contemplate. See *Decision*.**

Two candidates, and this ADR does not choose between them — that is the owning team's
call. Both are on SimForge, because both controls are.

**A. SimForge authors the `never_do_violation` scenarios for a declared list.** A
submitter declares its prohibitions; SimForge generates the held-out scenarios that test
them. This keeps the held-out boundary intact and makes the declaration load-bearing in
the direction it was meant to be — the list becomes an *input to authoring* rather than a
*claim to be checked*. More work, and it is the version where the rule keeps its meaning.

**B. The validator stops requiring what it will not accept from a submitter.** Held-out
classes are excluded from the per-entry check, and the coverage of a declared never-do
entry is asserted at scoring time, where SimForge's own scenarios are. Smaller, and it
moves the check to where the evidence actually is.

**Not a candidate: telling submitters to omit the list.** That is the passing path today,
and it is passing by erasing information. If it were acceptable, the column should be
deleted rather than left to be silently empty.

## Until then

> **Superseded 2026-09-08. There is no longer a 422 to take.** Left standing rather than
> deleted so the change is visible to a reader arriving from The Office's `blocking.md` B9,
> **which still says this and is now stale — see "What this leaves stale", below.**

~~**The Office declares its never-do lists honestly and takes the 422.**~~ A refusal that
names a real gap is a true statement; a submission that passes by withholding what it
knows is not. Recorded on that side in `docs/blocking.md` B9.

This is not the only reason The Office's submissions are currently refused — its
generator produces one unclassed scenario per (position, module), so every module also
fails the `escalation_required` rule. That is The Office's work to do and is not this
ADR's subject. **This one would still be here after that work is finished**, which is why
it is recorded separately rather than as part of the same backlog.

---

## Decision — path B, and the mirror image refused with it

**Ruled 2026-09-08.** Path B, as this ADR describes it, with one addition that was
escalated separately and ruled in by Ivan: **a submitted held-out scenario is refused.**

**These are one ruling and not two, which is the whole point of recording them together.**
The trap is the validator DEMANDING a class the submitter may not author. The addition is
the validator ACCEPTING one it must not be given. Both are the same mistake — *the rule
was written against a submitter that authors every class, and the held-out split made two
of the nine unauthorable by the only submitter there is.* Fixing the demand without fixing
the acceptance would have left the more dangerous half standing, and it is the half nobody
had noticed: **until this change, the party being certified could supply its own refusal
test**, and the cert would have measured what it was handed. That is `docs/blocking.md`
B4's family — a system certifying against material it received from the system being
certified — arriving one layer further down than B4 describes it.

### Why not A

**A** was for SimForge to author the `never_do_violation` scenarios for a declared list at
submission time. It keeps the rule's meaning intact, and it was rejected anyway:

**It puts the Gate 9.5 isolation boundary inside a request handler triggered by the party
that must not see the output.** The whole reason these two classes are held out is that
the authoring must be isolated from The Office; generating them synchronously inside the
endpoint The Office calls builds the leak surface into the endpoint. The engine already
cannot self-prove that isolation (`GATE_9_5_FLAG`); A would have made the claim harder to
believe rather than easier.

Secondarily: a generated probe is only as good as its generator, and a machine-written
refusal case that always passes is the pass-over-a-situation-that-cannot-occur that
ADR-0049 refuses next door. **Held-out authoring is still needed. It is not a request
handler.**

### What B actually does

- **The submission-time per-entry rejection is gone.** A declared `module_never_do` entry
  with no matching `never_do_violation` scenario is no longer a violation. There is now a
  correct submission that declares a never-do list: declare it, and do not author the
  scenario.
- **The obligation is recorded, not dropped.** `CurriculumValidation.never_do_obligations`
  carries the declared entries out of the validator; the router still writes them to
  `ForgeInstructionSet.neverDo` exactly as before, and now echoes them to the submitter, so
  a declaration is acknowledged rather than silently absorbed.
- **The refusal moves to scoring time, where the evidence is.**
  `never_do.is_never_do_coverage_hole` still holds a cert at `provisional` when a module
  has a never-do list and `never_do_adherence` was never exercised. Submission time could
  never have answered that question — **at submission, the scenarios that would answer it
  do not exist yet**, which is why the old check was unanswerable rather than merely strict.
- **`STATUS_NONE` vs `STATUS_UNTESTED` is untouched.** Empty `neverDo` still means "no
  obligation declared"; a populated one whose dimension was never exercised still means
  "declared and untested", which is a coverage hole wearing an n/a. That distinction is the
  reason the column exists and nothing here narrows it.

**The claim that must survive review is "the refusal moved; it was not deleted", so it is
asserted rather than asserted-about:**
`tests/unit/test_curriculum_admits_declared_absence.py::test_the_never_do_refusal_moved_to_scoring_time_and_was_not_deleted`
holds both halves in one test, and
`tests/integration/test_operation_audit_fixes.py::test_never_do_hole_blocks_certified` now
runs the honest submission end to end: declared list, no authored scenario, accepted at
submission, and **still held at `provisional`** because the dimension went unexercised.

### The mirror image, in both of its forms

Ivan's ruling covers the authored form; the declared form falls to the same reasoning and
is implemented alongside it:

| form | what it would have bought | what happens now |
|---|---|---|
| **authored** — a submitter sends a `never_do_violation` or `silent_failure` scenario | the certified party supplies its own refusal test | the submission is **refused**, and the scenario does not count as supplied |
| **declared** — a submitter declares a held-out class `not_applicable` (ADR-0049) | excusing itself from the two classes that test refusal and concealment, reaching a certified-shaped level having been examined on neither | held-out declarations are **struck** before `classify_certification_level` runs |

A refused scenario must not go on to raise a module's level, or the most illegal
submission available would produce the best label in the response beside it.

### What was deleted, so that it is found rather than inferred

`_DECLINE_MARKERS` and `_proves_decline` — the word-list heuristic that checked whether a
submitted `never_do_violation` scenario's `expected_behavior` evidenced the agent
declining. **This is not the judgement being dropped.** Its own comment always said the
authoritative "did it decline" answer was the held-out scenario's SCORING, not the string
match; and after the ruling the heuristic could only ever have run on a payload that is
refused one check earlier. A comment stands where it was, naming the removal, and the
`never_do_adherence` rubric dimension is where declining is actually decided.

### Consequences, including one that reads like a regression and is not

- **No submission can reach `certified`.** It requires all nine classes and a submitter may
  send seven. This is not new and it is not a defect in the authoring — the scenario
  contract states it at §1.1 as a structural ceiling — but it is now *enforced* rather than
  merely true. `certified` itself is unchanged and remains reachable where the held-out
  scenarios exist.
- **`tests/integration/test_office_bridge.py`'s curriculum fixture no longer authors a
  held-out scenario.** It used to, and it had to: it was the only way to write a passing
  Office payload. **The trap was visible in the fixture** and nobody read it as one.
- **Every declared never-do entry is currently an open obligation.** SimForge's held-out
  authoring pipeline does not exist yet, so nothing will exercise `never_do_adherence`, and
  a module that declares a never-do list will sit at `provisional`. **That is the honest
  state and it is now the visible one** — a real coverage hole, reported as a coverage hole,
  instead of a 422 that named work nobody was allowed to do. Building the held-out authoring
  is what closes it, and that is now the next piece of work rather than a blocked one.

### What this leaves stale, and it is not this repository's to fix

**The Office's `docs/blocking.md` B9 records this defect and says The Office "declares its
never-do lists honestly and takes the 422".** After this change there is no 422 to take.
That file is in `theoffice`, is append-only, and belongs to no package in this build, so it
is flagged rather than edited — see `PARALLEL_BUILD_ESCALATION.md` E-4. **A resolution
recorded on one side of a two-repo boundary while the other side still describes the
defect as live is the second-copy shape again**, and this run has now hit it three times.

### Still open

- **Gate 9.5's isolation is still not self-proving.** Refusing what arrives says nothing
  about who authored what does not. `GATE_9_5_FLAG` stands, unchanged, and the process
  control it names is still a process control.
- **The held-out authoring pipeline is not built.** Named above as the consequence that
  reads like a regression.
