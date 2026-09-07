# ADR-0048 — the never-do rule has no correct submission

**Status:** Open — a defect, recorded before it is fixed
**Date:** 2026-09-07
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

**The Office declares its never-do lists honestly and takes the 422.** A refusal that
names a real gap is a true statement; a submission that passes by withholding what it
knows is not. Recorded on that side in `docs/blocking.md` B9.

This is not the only reason The Office's submissions are currently refused — its
generator produces one unclassed scenario per (position, module), so every module also
fails the `escalation_required` rule. That is The Office's work to do and is not this
ADR's subject. **This one would still be here after that work is finished**, which is why
it is recorded separately rather than as part of the same backlog.
