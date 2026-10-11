# ADR-0156 — A lost operator credential is reset, witnessed

**Status:** accepted · **Decided by:** Ivan Green, 2026-10-11 · **Built.**
Extends ADR-0154. The recovery path at the end is proposed, not built.

## Why

Ivan Green's partition-operator credential is lost. The audit holds two
`author` refusals on 2026-10-11, both `credential_did_not_match`. ADR-0154
has no reset: an enrolled name cannot enrol again (`already_enrolled`),
and nothing else writes `credentialHash`. Ivan cannot author a partition.

## The ruling

> Build a witnessed reset. Ira authenticates as witness with his own
> credential; Ivan sets a new one at a hidden prompt (twice, 12+ chars).
> Refuse self-witness; audit every step and refusal. The old credential
> stops working; history (Greenstone 01M4HTKQ authored by Ivan) stays
> intact. Propose, don't build, a recovery path if both founders lose
> credentials.

## What changes

**A reset replaces the hash in place.** `reset_credential` writes a new
scrypt hash to the operator's existing row. The operator keeps their id.
`HeldOutPartition.authoredByOperatorId`, `sealedByOperatorId` and every
`PartitionOperatorEvent.operatorId` name that id, so none of them is
touched, and none needs to be. The old hash is gone; the old credential
matches nothing.

**A witness is required.** Another enrolled operator authenticates with
their own credential. The person being reset does not authenticate:
they lost the thing they would authenticate with.

**Refused, each with an audit row:**

| code | when |
|---|---|
| `not_enrolled` | the name being reset is not enrolled |
| `witness_required` | no witness, or no witness credential |
| `witness_is_the_operator` | the witness is the person being reset, by name or by id |
| `witness_did_not_authenticate` | the witness is unknown, or their credential is wrong |
| `entries_differ` | the two entries of the new credential differ |
| `credential_too_short` | the new credential is under 12 characters |

So a reset needs at least two enrolled operators. With one, no witness
can exist.

**Two audited steps.** `act = 'reset'`:

1. `witnessed`: the witness authenticated. Committed on its own,
   before the new credential is checked. A reset refused after this
   step still shows who vouched.
2. `done`, or `refused` with the code above.

Both carry the operator id and the witness id. Neither carries a
credential.

**The checks are in the service.** The CLI cannot skip them. The
mismatch check (`entries_differ`) is in the service too, so it is
audited. Enrolment's mismatch check stays in the CLI, unaudited, as
ADR-0154 built it.

**The CLI** asks the witness first, then the new credential twice, all
at hidden prompts (`getpass`). No flag or variable carries a
credential.

    python -m scripts.author_partition --reset "<name>" --witness "<name>"

## What it does not prove

The witness authenticates; the person being reset does not. Nothing
proves Ivan was at the keyboard. One operator alone could reset the
other, then author as them and seal as themselves. That defeats the
two-person rule (ADR-0113) with one person.

This is the same kind of weakness as ADR-0154's "one person who controls
enrolment can enrol a second identity". The audit shows it: a `reset`
witnessed by X, then a partition authored by the reset operator and
sealed by X. Nothing refuses it. A rule that refused it would stop every
seal for a two-operator venture after any reset. The MFA tie on the
backlog is the real fix.

## Migration

`20261011000000_operator_credential_reset` widens two CHECKs on
`PartitionOperatorEvent`: act gains `'reset'`, outcome gains
`'witnessed'`. No column and no data change. Idempotent.

## Versions

None. Grading unchanged.

---

## Proposed, not built: when both founders lose their credentials

**Today.** Two operators are enrolled: Ivan Green and Ira Green. If both
lose their credentials, there is no witness left. A reset is refused.
Enrolment is refused too: it needs a witness once anyone is enrolled.
No partition can be authored or sealed. Sealed partitions still grade;
operators gate authoring and sealing only.

**Recommended, in this order:**

1. **Prevention: enrol a third operator now.** A trusted person who will
   never author (counsel, for example), witnessed by Ivan or Ira. One
   lost credential is then recoverable by the other two. No code.
   It also means a single person no longer controls every reset.

2. **Break-glass, audited.** A separate script, `operator_break_glass`,
   that runs only with the database **owner** role, not the API's role.
   It:
   - refuses unless every enrolled operator is named on the command
     line, so it cannot be used to replace only one;
   - writes a `reset` event per operator with outcome `done`, witness
     null, and a new `reason` column reading `break_glass` plus a
     decisions entry number that must already exist;
   - clears every `credentialHash`, then lets the first re-enrolment run
     witness-free, as the bootstrap does (ADR-0154), keeping each id.

   This does not lower the bar. Anyone with the owner credentials can
   already write any row (ADR-0154, "What it does not prove"). It turns
   a silent rewrite into a recorded one.

3. **Optional: per-operator recovery codes.** At enrolment, print one
   recovery code once, store only its hash, and let it stand in for a
   witness exactly once. It must be kept offline. A code kept beside the
   credential is lost with it; this only helps if they are kept apart.

**Not proposed:** recovering an old credential. It was never stored, so
it cannot be recovered, only replaced.

**Open for Ivan:** who the third operator is; whether break-glass needs
both founders present or names the two in a decisions entry; whether
recovery codes are wanted at all.
