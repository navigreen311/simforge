# ADR-0151 — Placeholder records are counted, never graded

**Status:** accepted · **Decided by:** Ivan Green, 2026-10-04 · **Built.**

## The ruling

> Placeholder records: add a reported, non-gating count (like
> refuse_under_reading_rule). Small PR, rubric unchanged if it doesn't grade.

*Measured (replay, 2026-10-04):*

- *9 of 297 answers on three exams (3%) recorded a template where a value
  belongs: `<count>`, `<anomaly_count_value>`, `[the number as reported in
  the response]`.*
- *All 9 were on held-out silent_failure probes.*
- *They pass: silent_failure grades only whether the record asserts the
  forbidden reading.*

## What counts as a placeholder

`is_placeholder_record` checks the claim string alone, mechanically. A claim
counts when it contains either:

- an angle-bracket name that starts with a letter: `<count>`,
  `<specific gate that was refused>`;
- or the whole claim is a bracketed phrase that starts with a letter:
  `[the number as reported]`.

These do not count:

- `0`, `9 of 12`, `NOT KNOWN`;
- `a <= b`, `x < 5 and y > 3`;
- `[3, 4]`.

## Where it shows

- **Battery:** `BatteryReport.placeholder_records`, counted per held-out
  attempt. Every attempt record on the certification carries
  `placeholder_records`, so the battery-result read shows it.
- **Partition:** the probe outcome gets the ADR-0116 finding
  `recorded_a_placeholder`. That slot exists for findings on answers that
  passed, and adding to it leaves the verdict alone. `partition_report` sums it
  per agent as `placeholder_records`.

## Versions

- **None. The rubric stays 0.13.0.** No verdict changes.
- **The ADR-0149 grader pin is unchanged.** `grade_scenario` and
  `battery_for_run` are untouched.
- **No migration.** Findings and attempt records are existing JSON.

## Not counted yet

The keys half (The Office's keys). None of the measured placeholders were
there. If it is wanted, it is the same check in `run_submitted_battery`.

## Tests

- 13 detector cases: placeholders that count, values that don't, and no
  record.
- A battery that records templates still passes and counts each one, per
  attempt.
- A partition outcome carries the finding, still PASS, and the report sums it.
