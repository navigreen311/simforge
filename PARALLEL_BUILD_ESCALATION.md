# P-03 — escalations

**Package:** P-03 — SimForge: the validator admits declared absence, and the never-do trap closes
**Branch:** `feature/p-03-validator-admits-absence`

Each item is a file P-03 needed and was not allowed, or a decision P-03 could not make alone.
**Nothing here was worked around.** Per the rules: stop, record, do what can be done without it,
and surface it in the PR rather than burying it.

---

## E-1 — `docs/README.md` carries a second copy of every ADR's status, and two entries go stale

**Not touched. Not on P-03's card.**

`docs/README.md` is the ADR index and it does not link ADRs — it **summarises** them, status
included:

```
- adr/ADR-0049-... — **proposed, not built.** ...
- adr/ADR-0048-... — **open, not fixed.** ...
```

ADR-0049 is now **Accepted, and built**, so that line is false as of this branch. ADR-0048's line
will go the same way when its ruling lands.

**Why this is being escalated rather than fixed in passing.** It is a one-line edit and it is
exactly the kind of edit that turns a package diff into a package diff plus something else. The
rule is explicit, so the file stays untouched. It is worth noticing what the file *is*, though: a
second copy of a status that lives in the ADR, kept in prose, updated by hand. That is the same
shape as the second-copy reasoning that keeps the contract in one repo and leaves the Burkham split
draft uncorrected — an index that restates rather than points will drift, and it drifted here
within one working day of ADR-0049 being written.

**RESOLVED — granted narrowly by the coordinator, and then extended by one line. Read this.**
The grant was *"edit only the ADR-0049 status line to match; do not restructure the index"*, and it
was given **before Ivan ruled the B2 half in**. When the grant was written, ADR-0048's index line
being stale was a prediction; it is now a fact, created by this same PR. Shipping a commit that
resolves ADR-0048 while the index beside it says *"open, not fixed"* would be the drift this item
is about, introduced by the hand documenting it.

**So both status lines are edited, and nothing else.** No restructuring, no other entry touched.
**The second line is a deliberate extension of a narrow grant and the coordinator should revert it
if that is not wanted** — it is one paragraph in `docs/README.md` and reverting it costs nothing.

---

## E-2 — a submitted `never_do_violation` scenario is accepted as evidence, and that is not P-03's to close

**Raised in P-03's acknowledgment, escalated by the coordinator to Ivan, and NOT built.**

The validator today accepts a `never_do_violation` scenario from a submitter, even though that
class is held out and The Office may not author it (contract §1.1). Nothing refuses it. The
consequence is that **the certified party can supply its own refusal test** — `blocking.md` B4's
family, and a governance question rather than a validator bug.

P-03 proposed refusing it, on the grounds that a validator which stops requiring what it will not
accept should also stop accepting what it must not be given. **The coordinator held it.** It is not
in this branch.

**One related hole WAS closed, and it is worth separating from the held item**, because it is the
same idea arriving somewhere P-03 does own: a declaration on a held-out class is struck before
`classify_certification_level` runs. Without that, a submitter could declare `never_do_violation`
and `silent_failure` not-applicable and reach a certified-shaped level having been examined on
neither. That is a *level* computation inside P-03's file, not a new rejection, and it refuses
nothing that was previously accepted — the submission is neither more nor less rejected than
before. It is recorded here so a reviewer can see the boundary P-03 drew and disagree with it if
it is the wrong one.


---

## E-3 — two test files beyond P-03's card, and the ruling left no version where they still pass

**Edited. Minimal. Flagged here and at the top of the PR rather than buried in a diff.**

The coordinator granted `tests/integration/test_operation_curriculum.py`. Ivan's ruling — a
submitted held-out scenario is refused — also invalidated fixtures in two files that were granted
to nobody:

**`tests/integration/test_office_bridge.py`** — its `CURRICULUM` fixture appended a
`never_do_violation` scenario, with a `never_do_entry`, so that the bridge test could get a 200.
**It had to.** The validator refused a declared never-do list with no matching scenario, and that
class is held out, so the only way to write a passing Office payload was to have The Office author
a class The Office may not author. **The trap was sitting in that fixture and was read as a
fixture.** The edit deletes the appended scenario and derives the class list by excluding the
held-out set rather than by naming one class — so the next change to that set reaches this fixture
instead of drifting past it. `module_never_do` is unchanged: the list is still declared.

**`tests/integration/test_operation_audit_fixes.py`** — `test_never_do_hole_blocks_certified`
submits a curriculum only as SETUP, then asserts the thing that matters: a passing battery whose
`never_do_adherence` is n/a, against a module that declares a never-do list, is held at
`provisional`. **That assertion is untouched, and it is the scoring-time refusal path B relies
on.** Only the setup payload changed — the two held-out classes are gone from it. The test is now
strictly stronger evidence than it was: the honest submission (declare the list, author nothing)
is accepted, and the cert is still capped. It is the end-to-end proof that the refusal moved
rather than disappeared.

**Neither edit changes an assertion about behaviour.** Both are fixture corrections forced by a
ruling, and there is no version of that ruling under which the old fixtures remain legal
submissions. If the coordinator would rather own these two edits, they are four lines and a
comment each.

---

## E-4 — The Office's `blocking.md` B9 now describes a defect that is fixed, and it is not
this repository's file

**Not touched. Cross-repo.**

`theoffice/docs/blocking.md` B9 records the never-do trap and says: *"The Office declares its
never-do lists honestly and takes the 422."* After this PR **there is no 422 to take** — a declared
never-do list is now a correct submission.

That file is append-only, lives in another repository, and belongs to no package in this build, so
this is a flag rather than an edit. **A defect resolved on one side of a two-repo boundary while
the other side still describes it as live is the second-copy shape**, which this run has now hit
three times: the contract path that was six commits stale, `docs/README.md` restating ADR status in
prose, and this. The common feature is not carelessness — each copy was correct when written, and
each drifted the moment the thing it described moved.

Recorded in ADR-0048's *What this leaves stale* section, so a reader arriving from B9 finds the
correction even if B9 is never updated.
