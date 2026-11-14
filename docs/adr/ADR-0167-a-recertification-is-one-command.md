# ADR-0167 — A re-certification is one command, and the only stops are the humans'

**Status:** accepted · **Decided by:** Ivan Green, 2026-11-14 (asked 2026-11-13) · **Not built.**
 Builds on [ADR-0050](ADR-0050-no-credential-fetches-the-held-out-set.md) (no request puts a held-out probe, so the sweeps are scheduler-only),
[ADR-0154](ADR-0154-author-and-sealer-authenticate.md),
[ADR-0162](ADR-0162-a-partition-records-its-roster.md),
[ADR-0163](ADR-0163-one-sealed-partition-per-venture-and-forge.md) and
[ADR-0166](ADR-0166-an-autonomous-sandbox-run.md); and on The Office's decisions entries 204,
228, 300, 316, 332, 333 and 340 to 342.

## The question

> Re-certifying after a manual change takes 2+ hours of hand-run founder blocks and waiting for
> sweeps. Make it short: one runner command that does every non-human step in order, and stops
> only for Ivan approving any changed exam key, Ivan's Gate 4 review, Ira sealing the partition
> and Ira signing Gate 10. On-demand grading instead of waiting for :20 and :50. One review that
> holds. Unchanged modules carry over, and the command says up front which exams re-sit. No
> Greenstone task filed while a re-certification is open. (Ivan Green, 13 November 2026)

## What it takes today, measured

The last cycle, manuals 1.11.12 on Greenstone (entry 342), took eight founder blocks (152 to 159).
Run 740aff34 alone took 1 h 39 min, and blocks 152 (abort) and 153 (merge, move, restart, load)
came before it:

| time (12 Nov) | step | waiting on |
|---|---|---|
| 12:56:47 | block 154: run started, Gate 4 reviewed at 12:56:54 (artifacts 08b6d4f8) | Ivan |
| 12:57:30 | block 155: Gate 8 hands SimForge the curriculum; Gate 9 blocks seconds later | — |
| 13:20 → 13:28 | the :20 battery sweep grades comp_analysis; Victor Serath certified | **22 min of clock** |
| 13:25, 13:30 | block 156: Ivan authors the partition; block 157: Ira seals it | Ivan, Ira |
| 13:50 | the :50 partition sweep: 9 of 9 | **20 min of clock** |
| 14:15:53 | block 155 again: Gates 9 and 9.5 pass; Gate 10 reads the review as not bound | Claude's confirmation, Ivan |
| 14:27:32 | block 159: Ivan reviews the regenerated artifacts 03e8fd84 again | Ivan |
| 14:34:03 | block 158: Ira signs | Ira |
| 14:35:32 | block 155 again: Gates 11 and 12; complete | Ivan |

Most of the time was spent waiting for a clock, a confirmation, or a review the run had already
voided. Very little of it was human judgment.

## The ruling (Ivan Green, 14 November 2026)

> Ivan approves ADR-0167, including stage 3: at Gate 4 he reviews both the current artifacts
> and the artifacts as they'll look if the exams land as planned; Gate 10 binds only if the full
> current hash equals one of the two; anything else falls back to block 159's re-review.

So stage 3 is ruled as worded in section 3 and needs no further ruling before it is built. Stage 1
starts now. Stages 2 to 5 wait, and the 1.11.13 re-certification runs the old way, by founder
blocks.

## The decision

### 1. One command: `python -m scripts.recertify`

The command is built in **The Office** (`scripts/recertify.py`, run from wt-main's venv). Most of
its steps are The Office's, and its blocks already pin everything they touch. It calls SimForge's
own CLIs as subprocesses in SimForge's venv, as blocks 156 and 157 do today. It runs in the
foreground and waits in the foreground: no background process, no scheduled task.

```
recertify plan   --venture greenstone --pr 528 --pin <40-hex head>   # dry run, read-only
recertify run    --venture greenstone --pr 528 --pin <40-hex head>   # Ivan, his own token
recertify seal   --venture greenstone                                # Ira, his own credential
recertify sign   --venture greenstone                                # Ira, his own token
```

`plan` prints everything `run` would do, and changes nothing. `run` refuses unless a `plan` with
the same arguments ran within the last hour and nothing it read has moved since (the live hashes,
the PR's head, the open runs, the tasks in flight).

**The steps, in order.** Each step is one of the existing blocks, with that block's refusals
intact. Each one skips itself when it is already done, so every step can be re-run safely.

| # | step | today's block | typed word | refusals kept |
|---|---|---|---|---|
| 0 | **freeze** the venture's filing, and pause its active grants | 44 / B123 | `freeze` | a task or proposal in flight; inside a sweep |
| 1 | **abort** the stale run | 152 | `abort` | not exactly one open run; not blocked; older than the floor |
| 2 | stop for **key approval** if the PR changes any visible key | — | per module, `approve <module>` | see "The four stops" below |
| 3 | **merge** the PR at its pin | 153 stage 1 | `merge` | head ≠ pin; fewer than 7 checks, or any not passing; a `## NEXT.` entry; entry not main's last + 1; `broker/` or `db/` changed |
| 4 | **move** wt-main to the merge | 153 stage 2 | — (part of `merge`) | anything in flight; local changes; not an ancestor |
| 5 | **restart** the broker on wt-main's commit | 153 stage 3 | `restart` | a migration in between; schema not equal on every side; nothing on :9200; anything in flight |
| 6 | **load** the manuals | 153 stage 4 | `load` | the modules that move are not exactly the ones the plan named; a hash is not the one computed before the merge |
| 7 | **start** the run and advance it to Gate 4 | 154 | `start` | broker not on wt-main; SimForge rubric or checkout differs; temperature not 0.0 at both ends; live Pack not the expected one |
| 8 | stop for **Ivan's Gate 4 review** | 154 | `review` | see section 3 |
| 9 | **advance** through Gate 8; Gate 9 blocks on the exams | 155 | `advance` | the run is not the one step 7 started; hashes moved |
| 10 | **author** the partition with the roster | 156 | `author` (Ivan's partition credential at SimForge's hidden prompt) | roster not as planned; SimForge's current hashes are not the new ones; not blocked at 9 or 9.5 |
| 11 | stop for **Ira's seal** | 157 | Ira: `seal` | see "The four stops" |
| 12 | **grade now**: each re-sat Unit A exam, then the partition | — (section 2) | — | the model is busy; a sandbox run is active; the digest is off |
| 13 | **advance** through Gates 9 and 9.5 | 155 | — | the partition is not bound to the new hashes; not graded PASS |
| 14 | stop for **Ira's Gate 10 signature** | 158 | Ira: `sign` | not Ira's token; artifacts not the ones the review covers |
| 15 | **advance** through Gates 11 and 12, and lift the freeze | 155 | — | Gate 12 below plan (assignable count) |

Steps 13 and 15 have no typed word. They change only the run's own gate state, and each one is the
consequence of a human step just before it (a seal or a signature). Every other step that changes
something is behind its own word. There is never a single "yes" for everything.

**What every step prints and refuses, as the blocks do:**
- It refuses inside SimForge's sweep windows (:17 to :24, :47 to :54), checked again just before
  each typed word.
- It reads first through the read-only DSN, and prints hashes, ids and counts only. It never
  prints a scenario, an answer or held-out content.
- Its first line on any refusal says what was not done. A refusal whose cause is unexpected ends
  with "tell Claude".

**The four stops, and what each one says.** A stop prints the exact command, where to run it, and
the word to type. It then waits in the foreground, checking every 15 s for the human's action to
land in the database. A stop that waits more than 4 hours exits; running it again resumes.

1. **A changed exam key** (step 2). If the PR changes `scenarios/<module>.yaml` for any module the
   venture operates, the command prints the visible key's diff. These are visible classes only:
   the file holds no held-out class. It names the `approved_by`, `approved_on` and
   `approved_content_hash` the PR carries, and asks Ivan to type `approve <module>` for each.
   - It refuses if the header does not name Ivan Green, or if the hash does not match the file.
     `load_module` already refuses both (entry 300).
   - A changed key mints a new `k` segment in the exam's ref, so that module always re-sits.
2. **Ivan's Gate 4 review** (step 8): "Open run <id> in the console, read the artifacts below,
   then type `review`." The suggested note names the artifacts hashes and the five instruction
   hashes (B122, entry 317).
3. **Ira's seal** (step 11): "Ira: in a terminal of your own, in `~\Projects\wt-main`,
   run `python -m scripts.recertify seal --venture greenstone`, then type `seal`."
   - `seal` does what block 157 does. It shows the partition id, its author, its rostered agents,
     its bound hashes and what the seal retires, and refuses unless they are as planned.
   - It asks for Ira's partition credential at SimForge's own hidden prompt (ADR-0154). The
     sealer is never the author. SimForge refuses that, and `seal` refuses first if the author
     is Ira.
4. **Ira's Gate 10 signature** (step 14): "Ira: run `python -m scripts.recertify sign --venture
   greenstone` and type `sign`."
   - `sign` does what block 158 does. It reads `/api/me` and refuses any token but Ira Green's.
   - It shows the artifacts hash it signs, and the review that covers it (section 3).
   - The reason for the signature is still Ira's to write. The server still refuses an empty one.

**Resuming.** The command keeps a journal in `%USERPROFILE%\.theoffice-recert\<venture>.json`,
never under OneDrive. It holds the PR, the pin, the run id, the partition id and each step's
outcome; it holds no token.
- The journal is only a place to resume from. Each step re-derives its state from the systems
  themselves: the PR, wt-main's HEAD, `/api/version`, the live hashes, the run, the partition. A
  step that is already done says so and moves on, as block 153's stages do today. So an
  interruption at any point, in any step, is safe to re-run.
- Ivan's Office token is asked once per sitting at a hidden prompt and held only in the process.
  Resuming asks for it again. Ira's token and credential never pass through Ivan's process.

### 2. On-demand grading

**Built in SimForge:** `python -m scripts.grade_now --run-ref <ref>` and
`python -m scripts.grade_now --partition <id>`. These are process-side scripts, as
`resit_partition.py` is today, never an endpoint. ADR-0050 is unchanged: no request puts a
held-out probe, both sweeps stay `triggerable=False`, and the partition sweep still refuses a
request path.

`grade_now` grades as soon as the exam or partition is ready, and only if all of these hold:
- **The model is free.** A new shared advisory lock, `exam:model`, is taken by the :20 battery
  sweep, the :50 partition sweep, `resit_partition` and `grade_now` alike. Today the two sweeps
  take different locks and can overlap, so this closes that gap too.
- **No sandbox run is active.** It checks every runner home's lock file and the runner's own
  record of an active run, and finds no Ollama model loaded by anyone but itself.
- **It is outside the sweep windows,** so the sweeps keep their slots.
- **The examiner checks pass:** `check_examiner` (the digest pin, `EXAM_MODEL_TAG` and
  `EXAM_MODEL_DIGEST`) and at least 8 GB free.

If any of these fails, `grade_now` refuses with its reason and grades nothing. The `recertify`
command then waits and tries again at the next quiet minute. If it is still refused, it falls back
to the next sweep, which grades the exam as it does today.

**What it calls.** `grade_now` calls exactly what the sweeps call: `submit_battery_result` for a
Unit A ref, and `grade_partition` for a partition. It runs on the examiner runtime from
`get_exam_llm()`, with its clean-cache rule. (This also fixes `run_battery_sweep.py`, which builds
a provider without that rule.)

**What it changes for isolation and determinism, and why it is safe:**
- **The verdict does not depend on when grading happens.** It depends on the scenarios, the
  seeds (three attempts; partition seeds 0 to 2), the temperature (0.0 for cre-forge, from the
  Village's `config.yaml`, read the same way), the model digest (pinned and checked before
  grading), the protocol and the rubric. None of these reads the clock. On-demand grading
  changes when a verdict is computed, not what goes into it.
- **Isolation is enforced by the call, not by the schedule.** Every exam call starts from an
  unloaded model, and a warm load (under 1000 ms) is thrown away; three in a row raise
  `ColdStartFailed` (B135). So another phi4 user during grading (a sandbox run, Village speech)
  makes the exam refuse. It never makes it pass or fail. The `exam:model` lock and the sandbox
  check keep that refusal rare; they are not what makes grading correct.
- **The sandbox must see on-demand grading.** Today the runner's `exam_open` pause counts only
  open `OperationRun` rows, and a partition being graded writes none. `grade_now`, and the
  partition sweep, will hold the `exam:model` lock, and the runner's `pause_reason` will read it.
  So the sandbox pauses for partition grading too. Until now only the :47 to :54 window protected
  partition grading from the sandbox.
- **Partition verdicts gain the model identity.** `HeldOutPartitionVerdict` will record
  `examiner.as_record()`, as a battery-graded run does. A verdict graded outside the sweep can
  then be checked against the pin afterwards, not only before.
- **What is unchanged:** the sweeps, their slots, their limits and their order; who may author,
  seal or read; what a verdict means. A verdict from `grade_now` and one from a sweep are the
  same rows, and neither says which produced it except in the audit line.

### 3. One review that holds

**Why the review goes stale.** The Gate 4 artifacts include certification state:
- `certified`, `certified_tiers`, `certified_modules` and `requires_certification` on each
  appointed agent;
- `capacity.certified_and_free`, and the shortfall escalation and its advisory;
- `trust_tier` on each planned grant;
- the approval projection.

Gate 4 always comes before Gate 8's exams, so a run whose exams land in between reaches Gate 10
with the review void. That is block 159's nine fields on 12 November, all from one certification.

**What was weighed and rejected again.** One option was to take certification state out of what
Gate 4 reviews, or to bind the review to a second "content" hash that leaves it out. Entry 333
rejected this on 2 November, and the reason still holds. Gate 10 signs the full artifacts. A split
would have Ira sign appointment changes that no reviewer read: who is certified, at which tier,
whether a shortfall clears. And certification can change more than labels. Seat ordering puts
certified candidates first, so a certification can change who is appointed and which grants are
planned. Keeping some fields out of the review weakens "a signature over the reviewed artifacts".
This ADR does not do it.

**The decision: Ivan reviews both documents in one sitting, the artifacts now and the artifacts
the exams should produce.**
- **Building the projection.** At step 8, The Office regenerates the artifacts twice. First as
  they are now. Then as they will be if every exam that re-sits lands as the plan expects. For
  each (agent, module) that re-sits, the plan states the expected result, which is the result
  its carried-over peers hold today (for Greenstone: certified, tier propose).
  - The projection uses the same generators as the real artifacts
    (`generators.pipeline`), with those certifications supplied in place of the database's.
  - It writes nothing. Both snapshots are kept (migration 0117's table).
- **What Ivan reads.** The console's Gate 4 panel shows the current artifacts, and the diff to
  the projected ones. The diff is the same kind block 159 printed. For 12 November it would have
  been exactly block 159's nine fields, read at 12:57 instead of 14:27.
- **What the review records.** It records both hashes: the artifacts as they are at review time,
  and the projected ones. The note names both (B122).
- **How Gate 10 binds.** `review_binding` reads a review as bound when the run's current full
  artifacts hash is one of the hashes that review recorded. Today it must be the one hash.
  Nothing else changes:
  - the signature is over the full current artifacts, and the server still regenerates them and
    refuses a mismatch;
  - `distinct_humans` (entry 204) is enforced where it is;
  - entry 228's void and unbound states keep their meanings.
- **Why it is safe.** Ira signs a document whose every byte Ivan has read, because its hash is one
  Ivan's review recorded. The review does not cover a class of fields. It covers one exact
  document, which is entry 333's own test. Nothing is predicted into the record: the projection is
  only a document Ivan reviewed. If the exams land differently, the hashes differ and the review
  is void, as today. That covers any of these:
  - a lower tier, a FAIL that Gate 9 still lets through, a staleness flag;
  - a revocation in between, a re-ordered seat, a changed advisory.
- **When the projection does not hold.** Gate 10 reads the review as void, and the command stops
  for **block 159's re-review** as a fifth stop. It shows the diff from the nearer of the two
  reviewed snapshots and asks Ivan to type `review`. This is a correct outcome, not a failure: a
  document nobody has read waits for a reader. A plan can also say that it cannot project a module
  (for example, if its last result was a FAIL). Then the command says so at step 8 and tells Ivan
  the re-review stop will come.

### 4. Unchanged modules carry over, and the command says which exams re-sit

This already happens; the command only makes it visible. An exam's `run_ref` holds no provisioning
run id. It is built from the venture, Forge, module, agent, instruction hash, key hash, sections
hash, protocol and rubric (`broker/simforge.py`, `mint_run_ref`). So a module whose inputs did not
move lands on its graded exam at Gate 8, and Gate 9 counts it (entries 332 and 341).

**Built in The Office:** a read-only `provisioning.plan_recertification(venture, merge_commit)`.
- **What it computes.** For every live grant, it computes the ref Gate 8 would mint from the
  merge commit's manuals and keys. It then asks SimForge for that ref's verdict
  (`GET /api/operation/gate-result/{ref}`, which already exists).
- **What `plan` prints, before anything changes:**

  ```
  re-sits     Victor Serath   comp_analysis    instruction d9a14ba9 -> <new>   (manual moved)
  carries     Victor Serath   property_lookup  run 1eb42420's exam, certified propose
  carries     Ronan Valek     buyer_match      run 1eb42420's exam, PASS
  carries     Seraphine Valek buyer_match      run 1eb42420's exam, PASS
  department  <department>    re-sits (a member operates comp_analysis)
  partition   new, all 3 modules, 3 agents x 3 seeds (a hash moved: 01M78TE8 stops serving)
  ```

- **Why a carried line can still fail.** A carried line is a carry only if SimForge still
  publishes that ref's protocol and rubric, and its verdict is graded, not open. Otherwise the
  line reads `re-sits` and gives the reason.
- **The partition always re-sits** after a manual change. A partition is read NOT_RUN once any
  hash it was authored on stops being live. There is one sealed partition per venture and Forge
  (ADR-0163), so the new one covers every module, not just the one that moved.

### 5. No Greenstone task while a re-certification is open

**Why filing is still possible today.** Nothing ties filing to a re-certification.
`agent_tasks.file` never reads `provisioning_run`. It refuses only when no activated grant
exists, and even that holds only because the blocks paused the grants first. Once a load moves a
manual, a grant that is still active would serve a task under text nobody has certified. Its own
grant cannot be changed while active (Gate 5, `ActiveGrantWouldChangeError`). It is stranded until
Gate 11 reactivates it.

**Built in The Office:**
- **Opening the freeze.** Step 0 records a `venture_recertification` row: venture, opened by,
  PR, pin, opened at. Then it pauses the venture's active grants, as block 44 did; entry 316
  keeps the agent tokens alive across the pause.
- **What the freeze refuses.** While the row is open, `agent_tasks.file` refuses every task for
  the venture with **409 `recertification_open`**, naming who opened it and when, whatever any
  grant's state. `claim_next` hands out nothing for the venture.
- **Starting it.** The command refuses to open the freeze while a task or proposal is in flight,
  as blocks 152 and 153 refuse today. It names them, and the filer resolves them first.
- **Closing it.** The row is closed by step 15, after Gate 12, or by
  `recertify abandon --venture greenstone` (typed word `abandon`). Abandoning aborts the open run
  and leaves the grants paused. Re-activating them is a run's Gate 11, never the abandon. Closing
  is an append, not an edit: the log keeps both rows.

### 6. What stays exactly as it is

- **Two distinct humans.** Ivan reviews. Ira seals and signs, each with his own token or
  credential, typed in his own process. `distinct_humans` and ADR-0154 are enforced by the servers
  as now; the command only refuses earlier.
- **Nothing held-out is readable by anyone.** The command, `plan`, `seal` and `grade_now` print
  ids, hashes, counts and verdicts by class. No path prints a held-out probe, situation or answer.
- **Sealed partitions:** one per venture and Forge, roster-bound, retired by the next seal.
- **The append-only log.** Every step writes the audit rows its endpoint writes today. The freeze,
  the projection and `grade_now` add their own rows and edit none.
- **The 1.11.13 batch's process.** It goes through founder blocks as drafted. This command is
  first used on the cycle after it, and only after the rehearsal in stage 5.

## Expected time

Assume one module's manual changes, no key changes, and both humans at hand. The grading times are
estimates. Only the Unit A one is measured.

| span | today (12 Nov) | with this ADR |
|---|---|---|
| abort, merge, move, restart, load | blocks 152 and 153, by hand | ~3 min, machine |
| start → Gate 4 review | seconds + Ivan | ~5 to 10 min, Ivan (both documents) |
| Gate 8 | 36 s | 36 s |
| author → seal | 13:25 → 13:30 | ~3 min (Ivan's credential, then Ira) |
| Unit A grading | waited 22 min for :20, graded by 13:28 | ~8 min per re-sat exam, at once |
| partition grading | waited for :50 | at once; **not measured** (9 sittings); estimate 15 to 25 min; stage 1 measures it |
| Gates 9 and 9.5 | 14:15:53, after Claude's confirmation | seconds, machine |
| Gate 10 | re-review 12 min, then signature | Ira's signature, ~2 min |
| Gates 11 and 12 | by hand | seconds |
| **end to end** | **1 h 39 min for the run, plus blocks 152 and 153 (2 h+)** | **~40 to 55 min** |

**Per human:**
- **Ivan:** about 15 min, in one sitting at the start: `plan`, the run's typed words, the Gate 4
  review of both documents, and his partition credential. Add about 5 min per changed key, and
  5 min if the projection does not hold (section 3's fallback).
- **Ira:** about 5 min, in two short sittings: the seal at roughly 15 min in, and the signature
  at roughly 40 to 55 min.
- **Claude:** no confirmation steps. The gates and the command read the verdicts themselves; Gate
  9 and 9.5's refusals already state the class-level reasons.

The longest wait is grading on one model. Several re-sat exams grade one after another (~8 min
each), so a cycle that moves three modules adds roughly 16 min.

## What is built where

**SimForge:**
- `scripts/grade_now.py`, for a Unit A ref or a partition.
- The shared `exam:model` advisory lock, taken by both sweeps, `resit_partition` and `grade_now`.
- The sandbox's `pause_reason` reads that lock.
- `HeldOutPartitionVerdict.agentModelIdentity`, a migration.
- `run_battery_sweep.py` moves to the examiner runtime.

**The Office:**
- `scripts/recertify.py`, with `plan`, `run`, `seal`, `sign` and `abandon`.
- `provisioning.plan_recertification`.
- The `venture_recertification` table and the `recertification_open` refusal in
  `agent_tasks.file` and `claim_next` (a migration).
- The projected artifacts at Gate 4, a review recording more than one hash, and `review_binding`
  accepting any of a review's recorded hashes (a migration, for the review's hash list).
- The console's Gate 4 panel showing the projection's diff.

**Founder blocks:** none new. Blocks 152 to 159 stay as the record of how 1.11.12 was done.

## Risks

- **One command performs several irreversible acts:** a merge, a broker restart, a load, a
  freeze, an abort. Each act still has its own typed word, dry-run read and refusals. `run`
  refuses without a fresh `plan`, and the merge is pinned to a head.
- **The projection is wrong.** Then the review is void at Gate 10 and the re-review stop runs:
  safe, and about 5 min slower. It is never wrong in the unsafe direction, because the binding
  compares exact hashes.
- **A long foreground wait gets interrupted.** Resuming re-derives every step from the systems.
  Only the token prompt repeats.
- **Holding Ivan's token for longer.** The blocks held it for minutes; a sitting holds it for up
  to about 15 min. It stays in memory only, and is asked again after any stop longer than 15 min.
- **`grade_now` collides with Village speech or a sandbox run.** The clean-cache rule makes the
  exam refuse rather than grade wrongly. The command falls back to the next sweep: slower, never
  wrong.
- **The freeze strands work.** Greenstone files nothing for 40 to 55 min instead of 2 h or more.
  The refusal names who opened the freeze and when.
- **A wider blast radius.** One script now touches the broker, the database and SimForge. The
  rehearsal (stage 5) runs it end to end on a scratch Office database and throwaway stacks before
  it is ever run live.

## Stages

1. **SimForge: grading.** `grade_now`, the `exam:model` lock, the sandbox reading it, and the
   partition verdict's model identity. Measure Unit A and partition grading times on a scratch
   database.
2. **The Office: the plan and the freeze.** `plan_recertification`, `venture_recertification` and
   `recertification_open`, with tests. `plan` works alone and read-only from this stage.
3. **The Office: one review that holds.** Projected artifacts, the review's hash list,
   `review_binding`, and the console panel. This amends entries 228 and 333's binding. Ivan Green
   ruled it as worded here on 14 November.
4. **The Office: `scripts.recertify`.** `run`, `seal`, `sign` and `abandon`, each step a port of
   its block with that block's refusals, plus the journal and the dry run.
5. **Rehearsal.** End to end on a scratch Office database and throwaway SimForge and Forge stacks,
   with a manual-only PR, a key-change PR, an interruption at every step, and a projection made to
   miss. Never into 8012 or the live databases.
6. **First live use** on the first cycle after the 1.11.13 batch. Ivan runs it, and Ira runs his
   two steps.

## Not decided here

- Whether `grade_now` may run inside a sweep window if the sweep has nothing to grade. It does
  not: the windows stay.
- Whether the projection may assume a result other than the carried-over peers' result, such as
  a module with no certified peer. It does not; such a module goes to the re-review stop.
- Department (Unit B) exams. They are closed by The Office's `department_outcome` or by the :35
  timeout (ADR-0161, ADR-0165), not graded by a sweep. The command waits for them as Gate 9 does
  today.
