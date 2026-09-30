# ADR-0132 — The battery sweep selects Unit A runs only

**Status:** accepted · **Decided by:** Ivan Green, 2026-09-30 · **Built.**

## The ruling

> Longer term: exclude Unit B from battery selection like the protocol fix.

*Measured: `battery_for_run` skips every department run
(`SKIP_NOT_UNIT_A`), yet `unscored_runs` selected them, so each took one of
the sweep's 10 slots every hour until it timed out. Run 7f09c779 opened 13
new Unit A and 3 Unit B exams with one start time, so the order within a pass
was arbitrary.*

## Built

`unscored_runs` adds `unit = 'A'` to its filter, beside ADR-0131's protocol
filter. Department runs still close by timeout (`run_timeout_sweep`), as
before. The docstring already said "Open Unit-A runs"; the query now agrees.

## Not changed

Nothing scores a department run. That gap is unchanged and separate.

## Tests

`test_a_department_run_takes_no_slot`: three older Unit B runs do not
displace two Unit A runs at limit 2. Removing the filter fails it.
