# Submitted answers — the response shape

SimForge names this. Decided and built in ADR-0153.
The Office must declare the module and these keys in its response
manifest before calling it: `validate_response` refuses an undeclared field.

## The call

The Office bridge module `submitted_answers`.

    POST /office/submitted_answers
    Authorization: Bearer <tenant credential>
    X-Office-Venture: <venture id>          required

    { "run_ref": "<str>" }

## The answer

200, two keys:

    {
      "run_ref": "<str, echoed>",
      "answers": [
        {
          "scenario_ref":   "<module>#<class>#<ordinal>",
          "scenario_class": "<one of The Office's submittable classes>",
          "ordinal":        <int>,
          "attempt":        <int, 0-based>,
          "seed":           <int>,
          "verdict":        "PASS" | "FAIL" | "NOT_RUN",
          "reasons":        ["<reason code>", ...],
          "answer_text":    "<the agent's answer, verbatim>"
        }
      ]
    }

One entry per submitted probe per exam attempt, ordered by module,
class, ordinal, attempt. `verdict` is that attempt's, not the merged one.
An empty list means the run was found and nothing has been examined yet.

## What is never in it

An answer to a held-out probe (`never_do_violation`, `silent_failure`)
or to a partition go-ahead probe (`permitted_request`). None is stored.

## Refusals

404, one message, whatever the cause:

- the run ref was not minted by The Office;
- `X-Office-Venture` is missing;
- it names a venture other than the run ref's;
- no such run.

401 without the tenant credential. 422 when `run_ref` is missing or not
a non-empty string.

## Audit

Every call with the credential writes one `SubmittedAnswerRead` row:
run ref, venture, agent id, trace, `X-Forge-Request-Id`, outcome,
refusal code and the number of answers returned. Refusals included.

## Binding

`is_mutating: true` — the audit row is a write.
`idempotency_support: natural` — a retry returns the same answers and
records its own read.
