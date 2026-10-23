# Department outcome — the call and its reply

SimForge names this. Decided and built in ADR-0161. The first write The
Office makes through the bridge.

The Office's `broker/simforge_response_manifest.json` already declares the
reply under `post_gate_result`: `run_ref`, `accepted`, `recorded`, `status`.
`validate_response` refuses any other key, so the reply carries those four
and nothing else.

## The call

The Office bridge module `department_outcome`.

    POST /office/department_outcome
    Authorization: Bearer <tenant credential>
    X-Office-Venture: <venture id>          required
    Idempotency-Key: <str>                  required

    {
      "run_ref":             "<the Unit B ref The Office minted>",
      "instruction_version": "<str, non-empty>",
      "forge_api_version":   "<str, non-empty>",
      "department_outcomes": [
        {
          "department_id":                "<the run's department>",
          "forge_id":                     "<the run's forge>",
          "passed":                       <bool>,
          "escalation_path_verified":     <bool>,
          "compliance_coupling_verified": <bool>
        }
      ],
      "agent_outcomes": []                  optional; must be empty
    }

Any other key is refused (`extra: forbid`). The forge, department and
content hash are the run's own: the run that Gate 8 opened holds them, and
an outcome naming a different department or forge is refused.

## What the state is

Decided by the gate-result writer, as for every gate result (ADR-0062
option A; Ivan Green's ruling of 23 October 2026):

| `passed` | both flags `true` | state         | run verdict   |
|----------|-------------------|---------------|---------------|
| `true`   | yes               | `certified`   | `PASS`        |
| `true`   | no                | `provisional` | `PROVISIONAL` |
| `false`  | either            | `failed`      | `FAIL`        |

`passed: false` means the attester recorded a defect. A flag that is merely
not verified is `provisional`, never `failed`: send `passed: true` with the
flag `false`.

The verdict is not in the reply. Read it back through `gate_result`, the
path every other verdict travels.

## The reply

200, four keys:

    {
      "run_ref":  "<str, echoed>",
      "accepted": true,
      "recorded": <int, outcomes written>,
      "status":   "recorded" | "replayed"
    }

`replayed` answers a retry: the same `Idempotency-Key` with the same
payload. It writes no second certification and repeats the first call's
`recorded`.

## Refusals

A refusal is never a 200. Each carries `{"detail": {"error": "<code>"}}`,
except the 404.

| status | code | when |
|--------|------|------|
| 401 | — | no tenant credential |
| 404 | — | the ref was not minted by The Office; `X-Office-Venture` is missing or names another venture; no such run. One message whatever the cause. |
| 422 | `no_idempotency_key` | `Idempotency-Key` missing or blank |
| 422 | `payload_invalid` | the body breaks the shape above, including any `agent_outcomes`; `violations` names the rule |
| 422 | `not_a_department_run` | the run is Unit A |
| 422 | `outcome_names_another_department_or_forge` | an outcome's department or forge is not the run's |
| 409 | `idempotency_key_reused_with_another_payload` | the key already recorded a different payload |
| 409 | `run_already_has_a_verdict` | the run is closed. A run closed by TIMEOUT is not: a late outcome is recorded. |

## Audit

Every call with the credential writes one `DepartmentOutcomePost` row:
run ref, venture, agent id, trace, `X-Forge-Request-Id`, idempotency key,
payload digest, outcome (`recorded` | `replayed` | `refused`), refusal code,
and the number of outcomes recorded. Append-only. A recorded row commits in
the same transaction as the certification it wrote.

## Binding

`is_mutating: true`: it writes a certification and closes a run.
`idempotency_support: key`: the only keyed module on the adapter.
