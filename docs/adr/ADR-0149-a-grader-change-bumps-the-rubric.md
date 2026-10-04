# ADR-0149 — A grader change bumps the rubric; a key change does not

**Status:** accepted · **Decided by:** Ivan Green, 2026-10-04 · **Built.**

## The ruling

> Approved: bump OPERATION_RUBRIC_VERSION to 0.12.0 for ADR-0147 (it changed
> the grader). Record the rule: a change to grade_scenario or battery_for_run
> bumps the rubric; a change confined to one key does not. Partition 01M42C8D
> re-sits automatically, as expected.

## Why

ADR-0147 changed how an exam's attempts become a verdict, and left the rubric
at 0.11.0. So two certifications reading `0.11.0` could have been decided by
two different rules: one with the tolerance, one without. Saying which rule
decided a row is the job of a rubric version (ADR-0100).

## The rule

- **Bumps the rubric:** any change to `grade_scenario`, which grades one probe,
  or to `battery_for_run`, which turns an exam's attempts into a verdict.
- **Does not bump the rubric:** a change confined to one key's content, such as
  `acceptable_acts` (ADR-0146) or an edited claim. The key travels on the
  certification as `scenario_set_hash` (ADR-0092), and that names it.

## Enforced, not just recorded

`tests/unit/test_a_grader_change_bumps_the_rubric.py` pins both functions to
the rubric version. It hashes their syntax trees with docstrings removed:

- a comment or docstring edit does not change the hash;
- any change to what the functions do does change it;
- the test then fails until `OPERATION_RUBRIC_VERSION` moves and the new
  digest is pinned.

This is the same pattern as ADR-0103 (the protocol block) and ADR-0127 (the
probe builders).

The pin covers only these two functions. A grading change elsewhere is still
caught only by review and ADR-0100.

## Versions

- **`OPERATION_RUBRIC_VERSION` 0.12.0.**
- **Partition 01M42C8D** re-sits automatically on the next sweep (ADR-0137).
  It is the same partition, with no re-seal.
- **Battery refs move to `r0.12.0`.** Current certifications need a new Gate 8.
- **Both protocols are unchanged.** The agent reads nothing new.
- **ADR-0147's "rubric stays 0.11.0" is superseded by this ADR.**

## Tests

- The grader is pinned to 0.12.0.
- A comment or docstring does not move the digest.
- The four rubric pins are moved to 0.12.0.
