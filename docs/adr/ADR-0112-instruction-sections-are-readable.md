# ADR-0112 — A certification's instruction_sections is readable

**Status:** accepted · **Decided by:** Ivan Green, 2026-09-23 · **Built.**

---

## The ruling

> A certification's `instruction_sections` is readable. Publish it on
> `battery_result_for`, at `GET /api/operation/battery-result/{run_ref}`,
> the route The Office actually reads. Keep `shown`, `required_by_keys`
> and `missing` distinct; don't collapse them to a boolean.
>
> Publish the section names only, never their prose. The field must pass
> `assert_no_scenario_content` unchanged, not by exemption.
>
> Assert the row, not the response.
>
> *Measured, 23 September: all six Greenstone exams recorded `missing: []`
> for the first time, and The Office's `verdict_evidence.instruction_sections`
> is None on all six. Both facts are true at once, and only the second is
> visible from where the decision gets made.*

## What let it through

ADR-0107 ruling 1 recorded the field on `OperationCertification`.
Nothing serialized it. Neither `gate_result_for` nor `battery_result_for`
returned it. The only reader was SQL against SimForge's database.

`missing` is the point of recording it. It tells a reader whether a 0.0
on a `failure_signatures` key is the agent's fault or the submitter's
omission.

## Built

`battery_result.section_names` projects the row onto exactly three lists.
Each certification in the battery-result body now carries:

    "instruction_sections": {
      "shown":            ["correct_sequence", "inputs", ...],
      "required_by_keys": ["correct_sequence", "failure_signatures", ...],
      "missing":          ["failure_signatures"]
    }

| Row | Published |
|---|---|
| NULL (pre-ADR-0107) | `null` — not `missing: []`, which would claim a check that never ran |
| a record | the three lists, names only |
| a record with a fourth key | the three lists; the fourth is dropped |

`gate_result_for` is not touched. It is a manifested contract with a
bound Pack module (see `battery_result.py`'s header).

## The Office's guard

- `validate_response` checks top-level keys only against the manifest.
  `instruction_sections` is nested in `certifications[]`, so no manifest
  change is needed for the body to be accepted.
- `assert_no_scenario_content` runs on it. No name matches a forbidden
  fragment. Values are section names, far below the prose threshold.
- Run against theoffice `9015a36`'s real guard with `echoed=None`:
  passes on a gap, a whole set, and null.

The Office's `parse_battery_result` does not yet read the field.
That is its adapter, after this.

## Tested

`tests/integration/test_instruction_sections_are_readable.py`, 7 tests.

- A certification with `missing: ["failure_signatures"]` and one with
  `missing: []`, both written by `instruction_section_record`. Each is
  read back from a fresh session, then the route must equal that row.
  The two must differ.
- Mutation check: publishing a constant empty record fails 4 of 7.
- The three fields stay distinct. NULL publishes null.
- The instruction set's prose never appears in the raw body.
- The Office's guard, copied at `9015a36`, passes with no exemption,
  with a positive control that it still catches prose.

Full suite: see the PR. `ruff` clean. No migration.

## What this does not do

- It does not change `gate_result_for` or The Office's manifest.
- It does not change The Office. `verdict_evidence.instruction_sections`
  stays None there until its parser reads the field.
- It does not put `run_ref` on the certification row. The join is still
  the natural-key lookup `battery_result.py` describes.
