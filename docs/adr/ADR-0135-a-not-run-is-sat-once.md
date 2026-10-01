# ADR-0135 — A NOT_RUN sitting at a given seed is sat once

**Status:** accepted · **Decided by:** Ivan Green, 2026-10-01 · **Built.**

## The ruling

> A NOT_RUN sitting at a given seed is sat once, and not re-sat while the
> partition, instructions and protocol are unchanged.

*Measured: on partition `…F0M1SD`, gianna_horven's seed 1 came back NOT_RUN
(an unreadable answer, ADR-0117). NOT_RUN was DUE, so every hourly sweep put
all three seeds again from 2026-09-30 20:50 PT: 42 sittings against every
other agent's 3. phi4 at a fixed seed answers the same way, so it could never
resolve.*

## Built

In `grade_partition`, a latest sitting whose result is NOT_RUN is skipped when
**every seed has a final row from probes actually put** (it carries the
instruction digest it was put under).

The three conditions of the ruling are the existing guards:

- partition: DUE reads only this partition's sittings at its digest;
- instructions: a sitting under a non-live digest is not current and is
  re-sat (ADR-0125), and a moved partition is refused outright;
- protocol: a sitting under another protocol is not current and is re-sat
  (ADR-0123), and a partition built under another is refused (ADR-0128).

## Not changed

- **The cheap NOT_RUN** (no module in scope, an agent the Village cannot name)
  has no seed and no digest and stays due, so it is put once the cause is gone.
- **The operator re-sit** (`resit=True`, `scripts/resit_partition.py`) still
  puts it. That is the path for a NOT_RUN caused by a provider outage, which
  this rule would otherwise also settle.
- The gate still reads NOT_RUN as NOT_RUN (ADR-0121).

## Tests

`tests/integration/test_a_not_run_is_sat_once.py`: an unreadable sitting is
not put again over two more sweeps, and no rows are added; an operator re-sit
still puts it. Removing the rule fails the first.
