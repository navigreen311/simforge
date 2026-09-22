# The 19 September certifications — closed, unattributed

**Recorded 21 September 2026.** Ruling: ADR-0104. Read-only investigation; nothing was changed to
produce it.

---

## The question

Six certifications were written on 19 September 2026 by a process nobody had identified. It had
imported SimForge's modules before 09:44:25 and was alive at 09:48. Which process was it?

## The verdict

**Closed, unattributed.** Most consistent with the long-lived process last seen at `3628c23`. Not
provable now.

---

## The rows

`createdAt` in the naive-UTC column ADR-0101 repaired; local times are PDT.

| UTC | local | module | state | rubric |
|---|---|---|---|---|
| 16:48:52.011 | 09:48:52 | `assign_contract` | failed | 0.2.0 |
| 16:49:31.798 | 09:49:31 | `assign_contract` | failed | 0.2.0 |
| 16:50:26.090 | 09:50:26 | `buyer_match` | revoked | 0.2.0 |
| 16:51:19.479 | 09:51:19 | `buyer_match` | revoked | 0.2.0 |
| 16:51:56.876 | 09:51:56 | `comp_analysis` | revoked | 0.2.0 |
| 16:52:50.170 | 09:52:50 | `property_lookup` | revoked | 0.2.0 |

Every row: `forgeApiVersion='1.4.0'`, `instructionVersion='1.1.0'`,
`agentModel='ollama/phi4:latest'`, digest `sha256:ac896e5b8b34…`.

**None of that names a process.** `forgeApiVersion` is a declared string. `agentModelIdentity`
describes the examinee. `operationRubricVersion` dates the rules. Thirty-five columns and not one
writer.

---

## What the checkout was doing

From the reflog:

```
3628c23   18 Sep 23:26:49 PDT     <- HEAD through the whole morning of the 19th
ab11851   19 Sep 12:28:02 PDT     <- first pull of that day
```

A process that imported before 09:44:25 on the 19th read `3628c23` as HEAD. `STARTED_COMMIT` is
resolved once at import and never re-read, so that is the value it would report for as long as it
lived — and `3628c23` is the SHA later observed on a process that was still running two days after
the checkout had moved past it.

**That is the candidate, and it is the only one the evidence points at.**

---

## The pre-restart pair is ruled out

Before the restart of 21 September, two python processes carried the uvicorn command line for port
8110. They are not the 19 September process:

- The listener reported `started_commit = 93eac59`.
- The reflog puts main at `93eac59` from **21 Sep 10:54:41** to **15:20:23 PDT**.
- `STARTED_COMMIT` cannot move upward within a process's life.

So it imported on 21 September, two days after the certifications were written.

**And they were not two processes in any meaningful sense.** `.venv\Scripts\python.exe` is a
launcher that spawns the base interpreter. One uvicorn launch is always a pair: the launcher, and a
child holding the socket whose `ExecutablePath` is the system Python. The restart reproduced it
exactly —

```
19248  ...\apps\api\.venv\Scripts\python.exe  -m uvicorn ... --port 8110
17040  ...\Programs\Python\Python312\python.exe  -m uvicorn ... --port 8110   (parent 19248)
```

— same command line, same creation timestamp, child owns the socket. The same shape appears on
Village OS (19620 → 3528) and The Office (16900 → 19704). The system Python's `site-packages`
holds pip and nothing else; it could not have run SimForge on its own.

**Reading that pair as two independent launches sent this investigation down an hour of the wrong
path**, and is why ADR-0104's restart script labels the roles rather than leaving them to be
inferred from a path.

---

## What cannot be established, and why

| | |
|---|---|
| Start time, parent, working directory of the pre-restart pair | Died with the processes. PID and command line were captured; `CreationDate` was not. |
| Windows 4688 process-creation records | `auditpol` needs admin and the Security log is unreadable without it. **Inconclusive, not absent.** |
| Prefetch run history | The directory exists and holds **zero files**. Prefetch is off. |
| The prior launch's stdout | `simforge-api-8110.log` begins at the new PID. `Start-Process` truncates, so **the restart destroyed it** — a limit introduced during the investigation, not one it found. |
| A writer on the row | No column carried one. |

---

## What was built because of it

ADR-0104, all three rulings:

1. **`writtenBy` on every certification** — `started_commit`, `pid`, `host`,
   `process_started_at` and the source that time came from. A column default, so no write site can
   omit it.
2. **`scripts/restart-api.ps1` rotates rather than truncates**, by renaming both log files aside
   before starting anything.
3. **It records `CreationDate` for launcher and child before the kill**, and appends the pair to
   `simforge-api-8110.restarts.jsonl`, a ledger nothing rotates.

None of it recovers 19 September. All of it makes the next one a lookup.
