# ADR-0136 — The parser reads one ACT and one RECORD line through their wrapping

**Status:** accepted · **Decided by:** Ivan Green, 2026-10-01 · **Built.**

## The ruling

> The Office confirms production never parses the ACT/RECORD block; it's
> exam-only. The parser accepts exactly one ACT line and one RECORD line even
> when wrapped in prose, bullets, bold or code fences. Zero or two ACT lines
> still fails. Bump whatever version this requires.

*Measured on partition `…M93BCA`: 15 unreadable answers, 10 of them "no ACT
line" - phi4 wrapping the lines in a code fence, a bullet, bold, or an
"Explanation:" section. ADR-0063's strictness was protecting a parser that
production never runs.*

## Built

`unwrap_protocol_line()` in `battery.py`, applied to every line before
`parse_answer` matches it:

- leading list or quote markers go (`- `, `* `, `+ `, `> `, `1. `, `1) `);
- if a wrapper (`**`, `__`, `` ` ``, `*`, `_`) opens the line and its span is
  itself a protocol line, the span is the line and the prose after it is not
  (`- **ACT: REFUSE 5** - because ...` reads as `ACT: REFUSE 5`);
- otherwise emphasis markers are dropped (`**ACT:** ESCALATE`), and a line
  wholly in a code span is unwrapped. Backticks inside a line stay, so a
  backticked subject reads as before.

Prose lines were already skipped; fence lines (```` ``` ````) are prose.

**Unchanged:** counting. Zero ACT lines, two ACT lines, two RECORD lines,
an undefined act, or a RECORD with no `=` still fail, named, before any body
is read. A protocol line mentioned mid-sentence is not a line.

## The bump: rubric 0.6.0, not the protocol

The agent reads the same text, so `RESPONSE_PROTOCOL_VERSION` stays 10.0.0
(ADR-0103, ADR-0127 pin what the agent reads and is asked; neither moved).
What changed is how a verdict is **computed**, which is what
`OPERATION_RUBRIC_VERSION` marks (ADR-0100): an answer that was "no ACT line"
at 0.5.0 can be graded at 0.6.0.

- New Unit A certifications are stamped 0.6.0; The Office mints `:r0.6.0`
  refs from `/api/version`.
- Partition verdict rows record the protocol, not the rubric. `…M93BCA`'s
  sittings were all graded at 0.5.0 and are settled (ADR-0121, ADR-0135), so
  none is re-graded. An operator re-sit would grade at 0.6.0.

## Tests

`tests/unit/test_the_parser_reads_wrapped_lines.py`: a fenced block with
prose after it; bullets and bold; a bold span then prose on one line;
numbered, quoted and code-span lines; a backticked subject left as written;
two ACT lines still fail; no ACT line still fails; a mention inside a
sentence is not a line; a plain line is left alone. Removing the unwrap fails
4 of 9.
