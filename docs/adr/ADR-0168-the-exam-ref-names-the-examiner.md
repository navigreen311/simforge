# ADR-0168 — The exam ref names the examiner, and Gate 9.5 counts only sittings at it

**Status:** accepted · **Decided by:** Ivan Green, 2026-11-26 (The Office decisions entry 355) ·
**Built, not merged.** Builds on [ADR-0060](ADR-0060-a-certification-names-the-model-file.md),
[ADR-0062](ADR-0062-production-settings-and-three-attempts.md),
[ADR-0120](ADR-0120-a-run-is-graded-under-its-protocol.md),
[ADR-0122](ADR-0122-the-gate-reads-the-current-protocol.md) and
[ADR-0167](ADR-0167-a-recertification-is-one-command.md); stacked on B131's 16384 window and the
task cap of 1,000 (this repo's #289).

## The ruling

> Add the examiner's model settings (num_ctx and the output cap at least, and say whether
> temperature and digest belong too) as a segment of the Unit A exam ref The Office builds, and
> the same check on the partition at Gate 9.5. A changed setting must make a new exam; an
> unchanged one must still carry over as today. (Ivan Green, 26 November 2026)

## What was wrong, measured

The Office's run ref named the venture, Forge, module, agent, instruction, answer key, sections
shown, protocol and rubric. It named nothing about the model. `open_run` is idempotent on the
ref, so with the manuals unchanged a move from 8192 to 16384 would mint the 8192 exam's ref and
hand back its graded run. The Office's grant hold (its #568) then refuses that grant at 16384
for good, because no exam can lift it.

Gate 9.5 had the same hole. It counted a sitting by partition digest, protocol and rubric. Live,
on 26 November: Burkham-Wickmont's sealed partition holds 36 sittings from 4 November that record
no examiner at all (they predate ADR-0167's record), and Greenstone's 18 record `num_ctx` 8192.

## The decision

**Five facts, exactly the ones The Office's `check_model` compares:** the tag, the pinned digest,
the Forge's temperature, the output cap and the window. If `check_model` compares a setting the
ref doesn't name, that setting's change holds every grant and no exam can lift the hold. The
quantization and file size are left out because the digest already decides them. The seed is
left out because it belongs to an attempt, not to the exam (ADR-0060).

`examiner_settings.settings_now(forge)` states the five from the pin, the Village's declaration
and `EXAM_NUM_CTX`, the same values the battery builds its runtime from. It makes no model call.
`settings_digest` hashes them, and a ref carries the first 12 hex characters as `m<12>`.

1. `GET /api/health/examiner-settings?forge_id=` states the five facts, the digest and the
   segment. It is public and read-only, like `/exam-model`, and always answers 200: when the
   settings can't be stated it says `readable: false` and gives the reason.
2. The battery refuses a ref whose segment isn't its examiner's
   (`the_run_ref_names_different_examiner_settings`) before any probe is put. ADR-0120 does the
   same for the protocol. A ref with no segment is not refused on this ground.
3. Gate 9.5 counts a sitting only if its `agentModelIdentity` names the five facts of now. A
   record that can't name all five matches nothing.
4. The grader treats a sitting at other settings as due again, as for a protocol or rubric
   (ADR-0123, ADR-0137). It puts nothing when its own examiner isn't at the stated five
   (`the_examiner_is_not_at_the_settings_gate_9_5_counts`), because a sitting written then would
   never count.

## What carries over

On the exam side, The Office decides which ref to use (`broker.simforge.exam_ref`). An exam
already certified at the settings now keeps its ref, with or without the segment, so unchanged
manuals at unchanged settings land on the certified run as today. Anything else opens under the
segmented ref.

On the partition side, a sitting at the settings now still counts, as today. A sitting that
records no examiner can't show it ran at these settings, so it doesn't count; at 16384 nothing
recorded before the switch does either. In practice:

- Greenstone's 18 sittings at 8192 stop counting at 16384.
- Burkham-Wickmont's 36 sittings stop counting the day this deploys, even before the window
  moves.
- The grader re-sits both on the next partition sweep, against the partitions already sealed,
  unless the instructions have moved.

So this deploys with the 16384 window, never ahead of it.
