# The exam-model signal: when the Village must leave phi4 alone

**ADR-0167, Ivan Green's ruling of 14 November 2026: prevent and detect.** On one machine, the
Village and SimForge's examiner share one Ollama and one phi4. On 14 November a second phi4 caller
during an exam changed 33 of its 57 answers. Every exam call still loaded the model cold, so the
clean-cache rule (B135) did not see it. Since then:

- **Detect (SimForge, built):** every grading watches Ollama's own request log from its first model
  call to its last. Graded here means the :20 battery sweep, the :50 partition sweep, `grade_now`
  and `resit_partition`. A model request the exam did not send makes the grading **NOT RUN**, with
  the reason *"another phi4 caller during the exam"*:
  - nothing is posted;
  - a Unit A run stays open and the next pass re-sits it;
  - a partition seed records NOT_RUN and is due again.

  This guarantee holds whatever the Village does.
- **Prevent (the Village, to build):** before each phi4 call, the Village asks SimForge whether an
  exam holds the model, and waits while one does. Otherwise its call voids the exam, and the exam
  has to be graded again.

## The signal

```
GET http://127.0.0.1:8110/api/health/exam-model
```

```json
{"held": true, "lock": "exam:model", "checked_at": "2026-11-14T18:05:01+00:00"}
```

- **What `held` means:** true while any grader holds `exam:model`, the one advisory lock every
  grader takes for its whole pass. The graders are the :20 sweep, the :50 sweep, `grade_now`,
  `resit_partition` and `run_battery_sweep`.
- **How it's computed:** read from Postgres' `pg_locks` on SimForge's own database. The lock is
  never taken, nothing is written, and it costs one indexed system-view query.
- **Access:** public, like the rest of `/api/health`. The response carries no exam, ref, agent or
  secret, only whether.
- **When it goes false:** as soon as the grader releases the lock. If a grader's process dies, the
  lock goes with its database session, so no stale state needs cleaning up.

## What the Village change does (village-os)

Wherever the Village calls phi4: speech, chatter, the operator's agent turns, anything that
posts to Ollama's `/api/chat`, `/api/generate` or `/api/embed`.

1. Read the signal immediately before the call, with a short timeout (1 s).
2. `held: true`: don't call. Wait and read again every 15 s.
   - Speech and chatter can drop the turn instead. Nothing in them is owed to anyone.
   - The operator's agent turns wait. A task is not lost by waiting: its Turn A or Turn B is made
     once the exam ends.
3. `held: false`: call.
4. **Unreachable or an error** (SimForge down): call. While SimForge's API is down no sweep runs,
   and if a `grade_now` from the command line is grading, detection voids the exam rather than
   counting it. The cost of guessing wrong is one exam re-sat, never a wrong verdict.

An exam takes about 8 minutes on phi4: three attempts, every call from an unloaded model. A
partition seed takes a few minutes. The sweeps run at :20 and :50, and `grade_now` runs outside
:17–:24 and :47–:54.

There is a window between the check and the call: a call that read `held: false` a second before
an exam started overlaps it. That is the race detection exists for. The exam is voided and
re-sat, never graded.

## How SimForge decides an exam was alone

The source is the request log Ollama itself writes: `server.log`, by default
`%LOCALAPPDATA%\Ollama\server.log`, overridable with `OLLAMA_REQUEST_LOG`.

**Why the request log, out of Ollama's own evidence:**
- It records one `[GIN]` line per request served, from every caller. It's the only source that
  records the other callers' requests themselves.
- `/api/ps` shows what is loaded and until when. The exam unloads before every call, so a
  co-caller between two exam calls leaves no trace there.
- Ollama keeps no request counter.

**How it counts:**
- The exam counts what it sent: each unload (`POST /api/generate`, keep-alive 0) and each call
  (`POST /api/chat`).
- It counts the model requests the log gained since its first call: `/api/chat`, `/api/generate`,
  `/api/embed` and `/api/embeddings`. `/api/ps`, `/api/tags` and `/api/show` don't count.
- **More logged than sent means another caller.** The log lines carry no model name, so a request
  for any model counts. On one GPU, any other generation shares the exam's hardware.

**Requests still running:**
- A line is written when its request ends, and the check runs after every exam call. So a request
  that overlapped an earlier call is caught at a later one.
- At the end of a grading, SimForge unloads the model and waits for `/api/ps` to empty. Ollama
  unloads only once no request holds the model, so everything that overlapped has ended and been
  logged. Then it reads the log one last time.

**A log that can't be read is not alone.** If the log is missing, or is no longer the file the
exam began on (it shrank, or its identity or first bytes changed because Ollama started a new
one), whether the exam was alone can't be told. That is NOT RUN too.
