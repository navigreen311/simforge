# ADR-0104 — A certification names its writer, and a restart preserves the evidence

**Status:** accepted · **Decided by:** Ivan Green, 21 September 2026 · **Built.**

---

## The rulings

> **1. A certification records the process that wrote it:** `started_commit`, `pid`, `host`,
> process start time. *Measured: the six 19 September rows name no process, commit or host, and
> attribution failed for that reason.*
>
> **2. A restart preserves logs:** append or rotate, never truncate. *Measured: the 21 September
> restart truncated `simforge-api-8110.log` and destroyed the prior launch's record.*
>
> **3. A restart records `CreationDate` for both launcher and child.**

All three come out of one failed investigation, and each names the thing that was missing when it
was asked for.

---

## 1 · The row names its writer

### What the six rows could not say

```
16:48:52  assign_contract   forgeApiVersion='1.4.0'  agentModel='ollama/phi4:latest'
16:49:31  assign_contract   forgeApiVersion='1.4.0'  agentModel='ollama/phi4:latest'
16:50:26  buyer_match       forgeApiVersion='1.4.0'  agentModel='ollama/phi4:latest'
16:51:19  buyer_match       forgeApiVersion='1.4.0'  agentModel='ollama/phi4:latest'
16:51:56  comp_analysis     forgeApiVersion='1.4.0'  agentModel='ollama/phi4:latest'
16:52:50  property_lookup   forgeApiVersion='1.4.0'  agentModel='ollama/phi4:latest'
```

`forgeApiVersion` is a **declared string**, not a build. `agentModelIdentity` describes the
**examinee**. `operationRubricVersion` dates the rules, not the process. Thirty-five columns, and
not one of them names the writer.

The only handle left was `started_commit` on a **live** process — and every process from that day
had been restarted several times since. The attribution closed unattributed.

### Built

`writtenBy`, a JSONB column:

```json
{
  "started_commit": "9b0d0d7290083a55dcf7831d7131ed1139602a69",
  "pid": 17040,
  "host": "DESKTOP-3PVA34B",
  "process_started_at": "2026-09-22T01:27:04.679869+00:00",
  "process_start_source": "kernel"
}
```

**Five fields, not four.** `process_start_source` says where the time came from — `kernel`
(Windows `GetProcessTimes`, or `/proc/self` on Linux) or `import` (the instant `build_info` was
imported, where neither is available). They are not the same measurement: import time is later
than creation by however long the interpreter took to start, and a reader comparing a log line
against a process must know which they hold. Reporting both under one name would be this ADR's own
defect, one layer down.

Writing the kernel path surfaced two traps worth recording, because each one fails **silently into
the fallback**:

* `datetime(1601, 1, 1).timestamp()` raises `OSError` on Windows — the platform cannot convert a
  pre-1970 instant. Added as a `timedelta` instead.
* Without declared `argtypes`/`restype`, `GetCurrentProcess` returns its pseudo-handle as a C int,
  `GetProcessTimes` returns 0, and the function reports `import` while looking like it measured
  something.

**A column default, not a keyword at each write site.** There are three sites today
(`routers/operation.py` twice, `recert.py` once) and the next one will not remember. A default
cannot be omitted. The callable returns a fresh dict per row, because a shared one would hang a
single mutable object off every certification in the session.

**Frozen at import**, for the reason `STARTED_COMMIT` is: none of these can change while the
process lives, and a value that moved under a caller would describe some later moment as the one
that wrote the row.

**NULL for existing rows.** A backfill would have to guess, and a guessed writer is worse than a
blank one — it reads as a record.

---

## 2 and 3 · The restart

`scripts/restart-api.ps1`. It exists because the restart that was done by hand on 21 September did
two things wrong while a forensic question was open.

### Rotate, never truncate

`Start-Process -RedirectStandardOutput` **truncates**. The previous launch's entire record — its
startup line, its scheduler registration, every sweep it had run — was destroyed by the act of
replacing it, and the question being asked that evening lost its only remaining source.

The script moves both files aside first, to `simforge-api-8110.<stampZ>.log`. **A rename, not a
copy:** the old bytes are never rewritten, so a rotation that fails part way leaves the original
whole rather than half of it.

### Record both halves of the pair, before the kill

The same restart captured PID and command line for the two processes it stopped — and **not their
`CreationDate`**. Once they were gone there was nothing left to ask, and the process had to be
dated from `started_commit` on an endpoint that was already dead.

The script writes both processes down before stopping anything, each tagged `launcher` or `child`.

**`.venv\Scripts\python.exe` is a launcher that spawns the base interpreter**, so one uvicorn
launch is always two processes: the launcher, and a child holding the socket whose
`ExecutablePath` is the **system** Python. That pair is not two launches and not a stray process.
Reading it as one cost an investigation an hour, and it is why the roles are labelled rather than
left to be inferred from a path.

### A ledger that is never rotated

`simforge-api-8110.restarts.jsonl` — one compressed JSON line per restart, appended, holding both
pairs, the checkout commit and the rotation stamp. It is the file that survives after the logs have
rolled and the processes are gone, which is exactly the state the 19 September question arrived in.

Appended with `[IO.File]::AppendAllText` and a BOM-less UTF-8 encoder, because
`Add-Content -Encoding UTF8` on Windows PowerShell writes a BOM and a BOM in the middle of a JSONL
file is a parse error for the next reader.

---

## The 19 September incident — closed, unattributed

Recorded in full at `docs/the-19-september-attribution-2026-09-21.md`.

**Most consistent with the long-lived process last seen at `3628c23`.** The checkout sat at that
commit from 18 September 23:26:49 until the first pull of 19 September at 12:28:02, which brackets
a process that had imported before 09:44:25 and was alive at 09:48.

**The pre-restart pair is ruled out.** It reported `started_commit = 93eac59`, which was not HEAD
until 21 September 10:54:41 — two days later — and `STARTED_COMMIT` is resolved once at import and
never re-read.

**Not provable now.** Prefetch is disabled, the Security log is unreadable without admin so 4688
records can be neither confirmed nor excluded, the processes are gone with their creation times,
and the log that might have held the startup line was truncated by the restart.

Everything built here is so that the next one of these is a lookup.

---

## Tested

`test_a_certification_names_its_writer.py`, ten tests. The identity carries all five fields; the
start time says where it came from and is not in the future; each call returns its own dict; a
certification written **through `submit_battery_result`** — the path that produced the six
unattributed rows — names its writer; and the default is callable and the column nullable.

Then the script: ASCII with no BOM (a `.ps1` that will not parse is the same as no script), the
rotation happens before anything that can truncate, `Out-File` never appears without `-Append`,
`CreationDate` is captured before `Stop-Process`, both roles are labelled, and the ledger is
appended rather than rotated.

The ordering checks strip comment lines first — the header explains the defect by naming the
cmdlet, and a check that reads prose would pass or fail on where the explanation sits.
