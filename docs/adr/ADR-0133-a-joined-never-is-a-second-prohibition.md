# ADR-0133 — A "never" joined into the same sentence is a second prohibition

**Status:** accepted · **Decided by:** Ivan Green, 2026-09-30 · **Built.**

## The ruling

> Widen the #220 check to count "never" after ", and", "; " and em-dash, with
> tests. Don't change anything that affects this partition's grading.

*Measured: ADR-0129 counted a "never" only where a statement starts. Four of
CapitalForge's live entries join two prohibitions in one sentence ("Never
retry, and never assemble a second export"), so they passed the hand-over and
were authored into partition `…GJXJ61` as one obligation each.*

## Built

`prohibitions_in` also counts a "never" that follows `, and`, `;` (optionally
`; and`) or an em dash (optionally `— and`). A "never" inside a clause
("a duplicate will never be caught") is still not counted.

Over every live list SimForge holds: **9** CapitalForge entries now count 2 -
client_read 2, client_read_pii 3, portfolio_health 5, regulator_dossier_export
1, restack_recommend 2 and 5, scan_communication 6, statement_pull 1 and 4.
87 count one. cre-forge and voiceforge: none.

## What it does and does not touch

- **Hand-over only.** The next submission of those 9 modules is refused with
  `a_never_do_entry_holds_more_than_one_prohibition (2 found)` until The Office
  splits them. Nothing stored is re-validated.
- **Grading is untouched.** No parser, probe or grader changed, so the
  protocol does not move (ADR-0127), and sealed partition `…GJXJ61` grades
  exactly as authored.

## Tests

Six added to `test_one_prohibition_per_entry.py`: `, and`, `;`/`; and`,
em dash with and without `and`, emphasis before the join, a "never" inside a
clause not counted, and the validator refusing a joined entry. Removing the
widening fails 5.
