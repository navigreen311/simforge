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

**What the coordinator needs to do:** either grant `docs/README.md` to P-03, or make the two line
edits at merge. The 0049 line should read *accepted, built by P-02 (primitive) and P-03
(enforcement); a declared `not_applicable` with a required reason is admitted, an undeclared
absence is still refused, and `classify_certification_level` gains a third level rather than
widening `certified`.*

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
