# ADR-0131 — A run whose ref names another protocol takes no sweep slot

**Status:** accepted · **Decided by:** Ivan Green, 2026-09-30 · **Built.**

## The ruling

> Exclude protocol-mismatched runs from the selection itself so they don't
> consume the limit.

*Measured: `battery_sweep` takes the 10 oldest unscored runs. The 18 stale
p8.0.0 rows opened before ADR-0130 were always those 10; each was refused
(ADR-0120) and the 18 p9.0.0 exams behind them were never reached.*

## Built

`unscored_runs` drops a run whose ref names a protocol other than
`RESPONSE_PROTOCOL_VERSION` **before** applying `limit`. A ref naming no
protocol is kept, as ADR-0120 keeps it. Filtered in Python with
`protocol_of_run_ref`, so the ref grammar is not restated in SQL.

Stale runs still close by timeout (`run_timeout_sweep`), as before.

## Not changed

`BATTERY_SWEEP_LIMIT` stays 10. One pass scores at most 10 current runs.

## Tests

`tests/integration/test_a_stale_protocol_takes_no_slot.py`: 18 stale refs do
not displace 3 current ones; a ref with no protocol is still picked; the limit
still applies. Restoring the old selection fails the first.
