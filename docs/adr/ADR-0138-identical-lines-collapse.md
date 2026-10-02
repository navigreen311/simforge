# ADR-0138 — Identical repeated ACT and RECORD lines collapse to one

**Status:** accepted · **Decided by:** Ivan Green, 2026-10-02 · **Built.**

## The ruling

> Identical repeated ACT (and RECORD) lines collapse to one; any difference
> still fails. Rubric 0.8.0.

*Measured on partition `…3CP8JX` (rubric 0.7.0): 68 unparseable answers, 60 of
them two ACT lines, up from 15. Replayed: phi4 writes a clean ACT / RECORD /
CAVEAT block, then a bulleted explanation that restates it -
`- **ACT: DECLINE** is chosen because ...`. ADR-0136's unwrapping read the
restatement as a second ACT line. In every replayed case the restated act
was identical. The regression was ADR-0136's.*

## Built

In `parse_answer`, before counting: if every ACT body is the same - compared
whole, ignoring spacing and case - they are one ACT line. The same for RECORD
lines. Anything else is left as it was and fails as before, unread:
`REFUSE 5` beside `REFUSE 6`, `DECLINE` beside `PROCEED`, or two different
records. Nothing is chosen between differing lines (ADR-0063).

## Version

Rubric 0.8.0: the verdict rule changed (ADR-0100). Protocol stays 10.0.0.
Partition sittings graded at 0.7.0 are not current (ADR-0137): `…3CP8JX` is
re-sat at the next partition sweep under 0.8.0.

## Tests

`tests/unit/test_identical_lines_collapse.py`: a restated answer is one
answer; a restated refusal keeps its number; spacing and case of the act word
do not differ; two different acts, two different refusal numbers and two
different records still fail. Three existing fixtures that used an identical
duplicate as "two lines" now use two that differ. Removing the collapse fails
3 of 6.
