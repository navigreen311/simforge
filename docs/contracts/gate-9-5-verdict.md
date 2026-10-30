# Gate 9.5 verdict — the response shape

SimForge names this. The Office records it, in that order.
Decided in ADR-0108. Implemented in ADR-0111. Per forge: ADR-0163.
Nothing on The Office's side may guess past this page.

## Why a page and not a guess

A guess about another system's response reads as that system's silence.
It once cost two days. So the key and payload are fixed here first.

## The call

The Office bridge module `gate_9_5_verdict`.

    POST /office/gate_9_5_verdict
    Authorization: Bearer <tenant credential>

    { "venture_id": "<str>" }

Or, contract v2 (ADR-0163), naming the forge:

    { "venture_id": "<str>", "forge_id": "<str>" }

Any other key is a 422.

## The answer

Always 200. Always these four keys. Never any other.

    {
      "venture_id":       "<str, echoed>",
      "partition_exists": true | false,
      "verdict":          "PASS" | "FAIL" | "NOT_RUN" | "IN_PROGRESS" | "TIMEOUT" | null,
      "decided_at":       "<ISO-8601 UTC>" | null
    }

| State | partition_exists | verdict | decided_at |
|---|---|---|---|
| unknown venture | false | null | null |
| no sealed partition | false | null | null |
| sealed, never graded | true | NOT_RUN | null |
| graded | true | weakest agent verdict | that row's decidedAt |

- `verdict` is null if and only if `partition_exists` is false.
- An unknown venture is indistinguishable from an absent partition.
- Only a currently sealed partition counts.
  A verdict whose `partitionDigest` differs from it is ignored.
- A venture holds one sealed partition per forge (ADR-0163). Asked without a
  forge, the answer is the weakest across all of them, by the order below:
  another forge's FAIL is never hidden. Where a venture holds one, that is
  exactly its answer.
- Weakest wins across agents, each at its latest verdict:
  FAIL < TIMEOUT < IN_PROGRESS < NOT_RUN < PASS.
  Any non-PASS blocks, so the order only chooses which non-PASS is named.

## v2: asked for a forge

Sent only when the request names `forge_id`. Always these six keys:

    {
      "venture_id":       "<str, echoed>",
      "forge_id":         "<str, echoed>",
      "partition_exists": true | false,
      "partition_id":     "<str>" | null,
      "verdict":          "PASS" | "FAIL" | "NOT_RUN" | "IN_PROGRESS" | "TIMEOUT" | null,
      "decided_at":       "<ISO-8601 UTC>" | null
    }

- The answer is that forge's sealed partition only. Another forge's verdict
  is not read.
- `partition_id` is the sealed partition the verdict is about. It is null if
  and only if `partition_exists` is false, like `verdict`.
- The state table above holds per forge. An unknown forge reads as one with
  no sealed partition.
- `forge_id` and `partition_id` are identifiers. Nothing about what the
  partition holds travels, here or in v1.
- A v1 request never gets these keys, so a caller that refuses a fifth key
  reads exactly what it always read.

The Office asks once per Forge a run binds. It records `forge_id` and
`partition_id` in its evidence and refuses an answer about a Forge the run
does not bind.

## Whether, not why

The answer carries nothing about the partition.
No counts, classes, modules, scenario ids, digests, reasons or scores.
A rich enough explanation of a failure reconstructs the scenario.

No key contains `held_out`, `heldout`, `prompt` or `scenarios`.
Those are The Office's forbidden name fragments.

A 4xx is auth or a malformed body only. It never depends on the venture.

## The Office's adapter (later, not here)

    partition_exists == false  ->  None   (Gate 9.5: at ceiling)
    otherwise                  ->  verdict verbatim  (only "PASS" passes)

A venture in simulation gets the same answer.
SimForge is blind to simulation. The Office's gate decides (ADR-0108 Q3).

## Not in office-simforge-contract.json

That file is versioned on both sides.
Changing it here without The Office fails The Office's build.
This shape joins it when the adapter lands, as one reviewable act.
