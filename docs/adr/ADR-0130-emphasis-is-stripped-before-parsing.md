# ADR-0130 — Emphasis markers are stripped before a never-do entry is parsed

**Status:** accepted · **Decided by:** Ivan Green, 2026-09-30 · **Built.**

---

## The ruling

> Fix (a): strip emphasis markers (`**`, `__`) before parsing, protocol bump
> per ADR-0127. Tests.

*Measured: 62 of CapitalForge's 77 live entries open `**Never ... .**`. The
parser strips a plain leading "Never" only, so the decline request asked the
agent "to **Never act on an absence.** The single ..." - the opposite act,
remedy attached (the ADR-0126 cut could not see the sentence end behind
`**`). Claims were read as acts: 74 acts, 0 claims, 0 beliefs.*

## Built

- `strip_emphasis(text)` in `held_out.py` removes `**` and `__`. Inside
  backticks a marker is literal (`__init__` stays). Nothing is split,
  reworded or dropped.
- Used where an entry is **read**: `parse_obligation` (kind, act, readings)
  and `prohibition_sentence` (the ADR-0126 cut), so the battery's decline
  probe and the partition's three framings both get it.
- `Obligation.text` keeps the entry **as sent**.

On the live CapitalForge lists: 35 acts, 39 claims, 3 beliefs; 74 held-out
scenarios; no request carries markup, a leading "Never", or trailing text.

## The bump: 9.0.0

What a probe asks changed for any bold-led entry, so ADR-0127 applies.

**8.0.0 results are not comparable with 9.0.0.** That includes Greenstone's
Gate 9.5 sittings, although cre-forge has no bold entries and its probes did
not change: the version belongs to the exam, not the forge.

After deploy:
- 8.0.0 refs are refused (ADR-0120); The Office mints `:p9.0.0`.
- Every 8.0.0 partition is refused (ADR-0128), including Greenstone's
  `…C3BANS`. Greenstone's Gate 9.5 reads `NOT_RUN` until a 9.0.0 partition is
  authored, sealed and sat (ADR-0122).

Pins: the block's ADR-0103 hash carries over unchanged. The ADR-0127 probe pin
gained bold-led fixtures and a 9.0.0 digest.

## Tests

`tests/unit/test_emphasis_is_stripped_before_parsing.py`: markers go and
backticked ones stay; a bold entry parses as its plain twin; the obligation
keeps the entry as sent; the request asks for the act; the cut finds the end
behind markers; no battery or partition probe carries markup; a claim gets its
over-read probe. Removing the strip fails 6 of 9.
