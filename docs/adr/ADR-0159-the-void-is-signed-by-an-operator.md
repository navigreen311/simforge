# ADR-0159 — The void is signed by an enrolled operator

**Status:** accepted · **Decided by:** Ivan Green, 2026-10-12 · **Built.**
Extends ADR-0158 and ADR-0154.

## The ruling

> Before applying: the void must be signed by an enrolled operator's
> credential (#245), not a typed --actor name. Prompt for the operator
> credential, like author_partition.

## What changes

`practice_void.apply` takes `operator_name` and `credential` and calls
ADR-0154's `authenticate` before reading anything. The actor on every
event it writes is the operator as enrolled: `"<name> (operator <id>)"`.

`scripts/void_practice_certs.py --apply --operator "<name>"` asks for
the credential at a hidden prompt (`getpass`). There is no flag for
it: it is never taken from the command line or the environment, and
never printed. A dry run takes no `--operator` and asks for nothing.

**Every attempt is a `PartitionOperatorEvent` with act `void`**
(migration `20261012010000_operator_signs_the_void` adds the act):

| outcome | refusal | when |
|---|---|---|
| `refused` | `not_enrolled` | the name is not an enrolled operator |
| `refused` | `credential_did_not_match` | wrong credential |
| `refused` | `void_plan_refused` | authenticated, but a target moved or a certification would survive |
| `done` | | the void was written |

A refusal is committed on its own and nothing else is written.

## Also: `restart-api.ps1` path defaults

Launched as `powershell -File` with `[CmdletBinding()]`, Windows
PowerShell 5.1 left `$PSScriptRoot` empty inside `param()` defaults.
`"$PSScriptRoot\..\apps\api"` resolved to `C:\apps\api` and the restart
refused before stopping anything (2026-10-12). The defaults are now
computed in the script body, where `$PSScriptRoot` is set. Verified
with `-File` (relative and absolute) and `&`.

## What it does not prove

The same as ADR-0154: that the operator is a person, not one person
with two enrolments. It turns "typed a name" into "knew that
operator's credential".
