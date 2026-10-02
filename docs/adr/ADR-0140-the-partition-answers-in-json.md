# ADR-0140 — The partition answers in JSON; the battery stays text

**Status:** accepted · **Decided by:** Ivan Green, 2026-10-02 · **Built.**

## The ruling

> Approved: option (ii). PARTITION_PROTOCOL_VERSION 12.0.0 with JSON (a) on
> the partition path only; battery and Office keys stay at
> RESPONSE_PROTOCOL_VERSION 11.0.0 text. State in the ADR that Gate 9 and
> Gate 9.5 answer formats now differ and must not be read against each other.

## Gate 9 and Gate 9.5 are no longer comparable

**Gate 9 and Gate 9.5 now use different answer formats. Do not read one
against the other.**

- **Gate 9** covers the battery and The Office's keys. It uses the text line
  grammar under `RESPONSE_PROTOCOL_VERSION` 11.0.0.
- **Gate 9.5** covers the held-out partition. It uses a JSON object held to
  `ANSWER_SCHEMA` under `PARTITION_PROTOCOL_VERSION` 12.0.0.

An agent's Gate 9 result and its Gate 9.5 result are measured under different
formats. A gap between them is not evidence about the agent until both gates
use the same format.

## Measured

On one 114-probe partition sample, JSON (a) scored 113 PASS and 1 FAIL. The
text format on the same sample scored 80 PASS and 34 NOT_RUN.

On the 33 permission_denied answers to The Office's keys, JSON (a) scored 3
PASS. Text scored 11. That is why JSON is not used for the battery.

The step-2 rewording ("make this request succeed as put") had no effect, so it
was dropped. Step 2 is the same as in 11.0.0.

## Built

- **The block.** `PARTITION_PROTOCOL` in `battery.py` has the same ordered test
  and rules as the text block, word for word. The fields replace the line
  grammar. It has five JSON examples, which are the text block's five
  examples in JSON.
  - `record` is null by default.
  - `cited_rule` is an integer only on REFUSE.
- **The schema.** `ANSWER_SCHEMA` reaches the model this way:
  - `AgentRuntime.turn(response_schema=...)` passes it to the provider.
  - `OllamaProvider` sets `format`. Other providers ignore it.
- **The path.**
  - `partition_grading` sends the JSON block and the schema.
  - `battery_system_context(protocol=None)` returns the text block. The
    battery and The Office's keys are unchanged.
- **The parser.** In `parse_answer`, an answer that starts with `{` goes to
  `_parse_json_answer`. Any other answer goes to the line grammar.
  `_parse_json_answer` reads each field and never repairs one:

  | Answer | Result |
  |---|---|
  | Not valid JSON | `answered_with_unreadable_json` |
  | `act` is not one of the four | unknown act |
  | REFUSE without an integer `cited_rule` | unknown act |
  | `record` is neither null nor {subject, claim} | unreadable record |
  | `caveats` is not a list of text | `answered_with_unreadable_json` |

## Versions

- **`PARTITION_PROTOCOL_VERSION` 12.0.0** is new.
  - It is recorded on partitions and partition verdicts.
  - It is checked by the built-under refusal (ADR-0128) and the current-only
    gate read (ADR-0122).
  - It is shown at `/api/version` as `exam.partition_protocol_version`.
- **`RESPONSE_PROTOCOL_VERSION` stays 11.0.0.**
  - Battery run refs keep `:p11.0.0`.
  - No Gate 8 re-run is needed.
- **Rubric 0.10.0.** The partition's answers are now read in a different way
  (ADR-0100).
- **Every partition built under 11.0.0 is refused, including 60HHB4.** A new
  partition must be authored and sealed.

## Migration

None. There are no new columns and no new CHECK values.

## Tests

The new tests are in `tests/unit/test_the_partition_answers_in_json.py`:

- The versions are split.
- The JSON block's hash is pinned to 12.0.0 (ADR-0103).
- Step 2 is the same in both blocks.
- The battery context ends in the text block, and the partition context ends
  in the JSON block.
- All five JSON examples are valid and readable.
- Valid JSON answers are read field by field.
- Six malformed answers are each tied to the rule they broke.
- Text answers still go to the line grammar.
- The battery sends the text block with no schema.

Other test changes:

- `test_partition_grading`: the partition sends the JSON block, and every call
  carries `ANSWER_SCHEMA`.
- `test_a_partition_records_its_protocol`: an 11.0.0 partition is refused
  under 12.0.0.
- Partition tests were moved to `PARTITION_PROTOCOL_VERSION`.
- The rubric pins and exam-block keys were updated.
