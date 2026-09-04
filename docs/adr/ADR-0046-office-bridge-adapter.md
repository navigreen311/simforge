# ADR-0046 — The Office bridge adapter: one module bound, one deliberately not

**Status:** Accepted
**Date:** 2026-09-04
**Related:** ADR-0044 (the run window this adapter reads from) · `theoffice/docs/forge-adapter.md`
(the contract) · `theoffice/docs/decisions.md` entry 5 (the unbound module)

## Context

The Office brokers every agent call to a Forge. Until now SimForge answered nothing it
sent: no `_modules` manifest, no dispatch map, no tenant credential. Its V32 rule — which
resolves a Pack's `modules_expected` against `GET {base_url}/_modules` — reported NOT_RUN
with `simforge: tenant credential unavailable`, and `forge_registry.base_url` held
`https://example.invalid`.

`medlink-wholesale/backend/app/api/forge.py` (CRE Forge) is the named template. This is
that port.

## Decisions

### 1. `gate_result` is bound. `run_scenario_pack` is not.

The Burkham Pack declares both at `criticality: hard`. Only `gate_result` has anything
real behind it — `run_registry.gate_result_for`, the read added in ADR-0044.

**SimForge has no pack-level unit of execution.** `run_scenario` takes one `scenario_id`;
a Pack is a filter on runs (`routers/runs.py`) or a scenario's parent
(`services/runner/execute.py`), and nothing anywhere iterates a Pack's scenarios into runs.
The only handler writable today would run one scenario and report having run a pack.

That is a plausible 200 for work that never happened, and `GET /_modules` is
**structurally unable to detect it** — a handler that overclaims is bound to its name
exactly like one that does its job. Binding the name would convert a check that reports
the gap into one that reports success.

So V32 will FAIL on `run_scenario_pack` once SimForge is reachable. **That is the check
working.** A true FAIL naming a real gap beats a green tick over a fake handler. The full
reasoning, including why this differs from the removal of `lender_match` and
`build_packet`, is `theoffice/docs/decisions.md` entry 5.

### 2. The tenant credential is checked here, not by `AUTH_MODE`

`AUTH_MODE=dev-bypass` — the local default — returns a fixed principal holding every role
and never reads the Authorization header. `AUTH_MODE=clerk` verifies a *user's* RS256 JWT.
Neither is a machine credential, and the first is actively dangerous on this surface: an
adapter deferring to `require_role` would serve the agent-facing surface of this Forge to
any caller at all on every developer's machine.

`OFFICE_TENANT_TOKEN` is compared with `hmac.compare_digest` on **both** endpoints.
`/_modules` is not public — it names the agent-facing surface, which is not something to
hand to an unauthenticated caller. An unconfigured token is a 503, never an open door.

### 3. Absent configuration means absent surface

The `/office` router is mounted only when `OFFICE_TENANT_TOKEN` is set. An adapter that
answered `_modules` while holding no credential to check would tell The Office that
SimForge is bridged when it is not, and Gate 0 would pass on a Forge nobody can
authenticate to. The Office reads the resulting 404 as "adapter serves no manifest", which
is the truth. Copied from CapitalForge's `officeBridgeConfigured()`.

It mounts at `/office`, with **no `/api` prefix**: The Office builds a module URL as
`{base_url}/{module_id}` with nothing in between, so `base_url` points at the mount.

### 4. `API_VERSION = "1.0.0"`, and what it is not

Three values were in play and two of them are unrelated:

| value | what it is | authority |
|---|---|---|
| `forge_registry.api_version` for `simforge` | what The Office sends on `X-Office-Forge-Api-Version` | **The Office's row. The only one on the wire.** |
| this adapter's `API_VERSION` | the contract version SimForge speaks, returned in `/_modules` | this file |
| the Pack's `api_version: 3.2.0` | a binding declaration | checked only by V7 (pinned, not `latest`) — reconciled against nothing |

A fourth value looked relevant and is not: `forge_api_version` in SimForge's operation
payloads is the version of **whichever Forge is being certified** (the fixtures carry
`3.0.0` beside `forge_id: capital-forge`). It has never described SimForge.

`1.0.0` matches `pyproject.version` and `APP_VERSION`, and follows CapitalForge, whose
adapter also pins `1.0.0`. The Pack's `3.2.0` describes nothing that exists.

A disagreement between the header and this constant is **recorded, not refused** — both
values go in the log line. Refusing would make editing a registry row an outage.

### 5. The `is_mutating` check is stronger than the template's

The CRE template inspects `session.new / dirty / deleted` after the handler returns. That
catches a handler that called `session.add()` and nothing else.

**It does not catch a handler that flushed.** A flush moves objects out of `new` and leaves
those collections empty, so the check reads clean on a write that has already reached the
database and is one commit from permanent. `open_run` and most of this codebase's service
functions flush — the template's check would have passed every one of them.

This port adds an `after_flush` listener for the duration of a read-declared handler.
SQLAlchemy skips the flush entirely when there is nothing to write, so the event firing at
all is the signal. `test_a_read_declared_module_that_writes_is_refused` fails against the
template's version.

This matters because `is_mutating` is the field The Office's V31 keys on when deciding
whether an unattended agent may hold a module at `auto_execute`.

## Consequences

- SimForge can be asked what it dispatches. V32 moves from NOT_RUN to a real answer:
  PASS on `gate_result`, FAIL on `run_scenario_pack`.
- **Gate 2 does not clear.** It requires no failures, and there will now be one. That is
  the intended state, not a regression — see entry 5.
- Additive. Nothing existing changes; with `OFFICE_TENANT_TOKEN` unset the app is byte-for-byte
  the app it was.
- Still outstanding before a real call: `SIMFORGE_TOKEN` in `theoffice/.env`, a
  `forge_registry.base_url` that is not `example.invalid`, and a running instance. Local
  first, per the CapitalForge order.
