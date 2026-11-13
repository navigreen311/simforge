# The sandbox runner

Stage 7 of [ADR-0166](adr/ADR-0166-an-autonomous-sandbox-run.md): start, schedule and stop a
sandbox run. A run drives Greenstone's agents through the sandbox Office's task loop to the
sandbox CRE Forge, on one seed's synthetic world. It records every step in SimForge
(`SandboxRun`, `SandboxStep`) and writes the run's page. Practice, never evidence.

## Start a run, and open its page

From SimForge's API checkout, with its venv:

```
cd ~/Projects/simforge/apps/api
.venv/Scripts/python -m scripts.sandbox_run check --as "Ivan Green"             # the start rules only
.venv/Scripts/python -m scripts.sandbox_run start --as "Ivan Green" --tasks 20  # one run, start to stop
```

`start` prints each stage as it goes, then the page:

```
page: C:\Users\ivann\.simforge-sandbox\runs\<when>-seed-<n>\sandbox-run-<runRef>.html
```

Open that file in a browser. Beside it are `summary.json`, `run.log`, the world file loaded,
and the Office broker's log. To write a run's page again later:

```
.venv/Scripts/python -m scripts.sandbox_run_page --run <runRef> --out <dir>
```

Options:
- `--seed N` names the seed. The default is the next seed after the last one run.
- `--tasks N` is how many tasks are filed, 1 to 60. The default is all of the seed's tasks, at
  most 60 (48 since generator 1.3.0), so a default run never leaves out the seed's last task.
  A schedule set without `--tasks` files all of each seed's tasks too.
- `--max-ticks N` is the step budget: operator ticks (default 4 per task + 10).
- `--max-minutes M` is the wall-clock budget (default 240).

Exit codes: 0 ok; 3 a start rule refused and nothing was started; 1 any other failure, after
which everything the run started is stopped.

## Stop a run

```
.venv/Scripts/python -m scripts.sandbox_run stop --as "Ira Green"
```

The run stops after its current tick. It finishes the Office's run, closes the `SandboxRun`
(tasks not finished are shown as such on the page), writes the page and stops everything.

## The schedule

```
cd ~/Projects/simforge-runner/apps/api
~/Projects/simforge/apps/api/.venv/Scripts/python -m scripts.sandbox_run schedule set --as "Ivan Green" --register
~/Projects/simforge/apps/api/.venv/Scripts/python -m scripts.sandbox_run schedule show
~/Projects/simforge/apps/api/.venv/Scripts/python -m scripts.sandbox_run schedule stop --as "Ivan Green" --register
```

Set it from the runner's own checkout (`~/Projects/simforge-runner`, never the live
`~/Projects/simforge`): `scheduled-run.cmd` runs `scripts.sandbox_run scheduled` from the
checkout and with the python that set it.

- A schedule has one owner, Ivan or Ira, a time outside the sweeps and at most 60 tasks. Only
  its owner stops it or replaces it.
- **Daily practice (generator 1.3.0).** The defaults are a run **every day, weekends included**
  (Ivan Green, 13 November), at **07:05**, at most once a day, all of the seed's tasks (48), on **the next seed no run has used**: one more than the highest seed in
  `SandboxRun`, and never below the schedule's `--seed` (default 4: seeds 0 to 3 were run by
  hand on 1.2.0). Each seed draws its own tasks from the pool, so day after day the tasks
  differ. 07:05 is outside the sweeps and before the exams: over the 45 days to 13 November,
  the hours 00:00 to 07:59 held an open exam on 8 run-hours each (one long run), 08:00 on 33,
  and 09:00 to 17:00 on 62 to 127 each. A 48-task run took 4 to 5 minutes on throwaway stacks
  (13 November), and a run waits out the :17-:24 sweep if it meets it, so it ends before 08:00.
- `schedule show` prints the schedule, Task Scheduler's next run time (`schtasks /Query`), and
  the seed the next run will take.
- Each day's run appends to `scheduled.log` in the runner's directory, and writes its page to
  `runs/<YYYYmmdd-HHMMSS>-seed-<n>/sandbox-run-<runRef>.html` there, beside `summary.json`.
- To pause it without losing it: `schtasks /Change /TN "SimForge sandbox run" /DISABLE` (and
  `/ENABLE` to resume), or `schedule stop --as <owner> --register`, which also marks the
  schedule stopped. To remove it: `schtasks /Delete /TN "SimForge sandbox run" /F`, then
  `schedule stop`. The task runs only while its owner is logged on to this machine; a run it
  fires while an exam is open, or with under 8 GB free, is refused for the day (the start rules)
  and the next day takes the same seed. Those refusals hold on a weekend as on any day: an
  exam open, under 8 GB free, inside a sweep (a scheduled run waits the sweep out).
- `--register` creates (or disables) the Windows scheduled task `SimForge sandbox run`,
  every day at that time (`schtasks /SC DAILY`), which runs `python -m scripts.sandbox_run scheduled`.
  Without `--register` it prints the `schtasks` line it would run.
- `scheduled` starts the run as the owner, with `SandboxRun.scheduleOwner` set, so the page
  names the owner. It refuses after a scheduled run already started today, when
  the schedule is stopped, or on any start rule. Fired inside a sweep, it waits for the sweep to
  close. There is no holiday calendar.

## The start rules

Every rule is checked and every reason reported. `check` runs them alone.

| refusal | when |
|---|---|
| `not_a_starter` | anyone but Ivan Green or Ira Green |
| `over_task_cap`, `more_tasks_than_the_seed` | over 60 tasks, or more than the seed has |
| `inside_a_sweep` | the minute is in :17-:24 or :47-:54 (a hand start is refused; a scheduled one waits) |
| `exam_open` | a SimForge `OperationRun` is open (no end, verdict or timeout), read from the live SimForge database in a READ ONLY transaction, a throwaway included |
| `memory` | under 8 GB free. First, the phi4 rule: if phi4 is loaded, no exam is open and it is outside the sweeps, phi4 is unloaded (`ollama stop phi4`) and memory measured again |
| `another_run` | another run holds the lock |
| `port_in_use` | 127.0.0.1:9212 already listening (a throwaway: 8013, 9213 or 55443), with who holds it |
| `throwaway_held` | a throwaway only: another runner home's throwaway stack holds 8013, 9213 or 55443, or another throwaway run holds the machine's one throwaway slot; both name the home |
| `missing` | `runner.env`, a checkout, a python, the CRE Forge's env, a loader without `--replace`, or SimForge's sandbox tables (migration 20261109000000) |
| `not_a_schedule_day` (never, with all seven days), `scheduled_run_already_today`, `schedule_stopped`, `no_schedule`, `not_the_schedule_owner` | `scheduled` only |

Each piece also has its own start-up refusals, which the runner does not repeat: the sandbox
CRE Forge's (`SANDBOX_MODE`), the sandbox Office's (`OFFICE_SANDBOX`, including the simulation
check) and the sandbox operator's. A refusal there stops the run and is shown in the log.

## What one run does

1. **The start rules**, above. Then the lock.
2. **A seed** and its tasks, one module at a time in turn, so a short run sees all three.
3. **The world.** The seed's world file is written and loaded into the shared sandbox CRE Forge
   (`creforge-sandbox`, 127.0.0.1:8012) by its own loader, with `--replace`: the world tables
   are emptied first, so the Forge holds this world only. The Forge is started if it is down.
4. **A fresh sandbox Office.** Its Postgres (`office-sandbox-db`, 55442) is started if down, the
   `office_sandbox` database is dropped and made again, migrated, and set up for Greenstone
   (`python -m broker.sandbox setup`). The simulation check reads the live Office's own
   declaration once, on its read-only DSN. The broker is served on 127.0.0.1:9212 (9213 for a throwaway).
5. **The sandbox operator** is set up from the Office's fresh tokens (`sandbox_operator.py setup`).
6. **Filing.** As the starter, with their own sandbox token, the runner starts the Office's run
   and files up to N tasks. A task's facts are its request, plus the person's words as
   `instruction`, so Turn A runs (The Office's B113). A filing the Office refuses (for example a
   radius with no `widening_reason`, B117) is skipped and the next task tried. The refusal is
   kept on the run and shown on its page as "refused at filing by The Office", counted against
   no agent (ruled 10 November).
7. **The run.** The `SandboxRun` opens on the tasks filed. Then, until every task is finished:
   - the operator takes one tick (`sandbox_operator.py run --once`): each agent one step;
   - each pending proposal is approved by `sandbox-approver`, at the starter's request;
   - every step the Office wrote since is recorded as a `SandboxStep`, with the Office's times
     (`office_sync`), and graded by the record (stage 5), with any CAVEAT flagged that states a
     count the Forge's answer contradicts (below);
   - inside a sweep, or while a SimForge exam is open, it pauses (no tick, no approval) and
     resumes after;
   - it stops at the step budget, the wall-clock budget, 8 ticks in a row that record nothing,
     or a stop.
8. **Close.** The Office's run is finished, the `SandboxRun` closed with its totals, and the page
   written.
9. **Stop everything.** The broker is stopped. The Office's Postgres and the CRE Forge are
   stopped if this run started them, and left as found otherwise (volumes kept). Then the phi4
   rule: phi4 is unloaded if no exam is open and it is outside the sweeps.

## What the grade flags

Each turn is graded by `grade_submitted`, as an exam is: the act, the record, and whether a
caveat is there. It does not read what a CAVEAT says. On the first real run
(`sandbox-01M73YAV88WWRG7F7CFFCVY2NP`, s0-001 and s0-002) the Forge answered `total: 8` and
Victor Serath's CAVEAT said the response "returned 100 properties", the `page_size` he sent.
Both passed.

So the sandbox record also reads each Turn B CAVEAT for a count: digits before a counted noun
(properties, results, rows, records, comps, sales, buyers, matches; one word between at most).
A count that is none of the Forge's counts is flagged `caveat_contradicts_forge`. The Forge's
counts are `total`, `suppressed`, each `results_with_<field>_null`, the rows of `results`, and
the rows on the page (`total` capped at `page_size`). `page_size` itself is never one: it is a
bound. Neither is a number after "up to", "at most", "top", "limit" or "page size". With no count
in the Forge's answer (a 404, a 422), nothing is flagged.

**A flag fails nothing.** The verdict, the run's totals and the exam's grading are unchanged; the
page shows the flag on the task's line and on its Turn B row, with the Forge's counts beside it.
It is a flag and not a FAIL because the check reads prose with a pattern and can misread it, and
because a sandbox verdict should mean what an exam verdict means. Failing on it would be a
change to the grade, which is the exam's to make first.

## Configuration

The runner's directory is `%USERPROFILE%\.simforge-sandbox` (`SIMFORGE_SANDBOX_HOME`
overrides). It refuses a directory under OneDrive. Write `runner.env` there by hand; it holds
paths only:

```
SANDBOX_FORGE_CHECKOUT=C:\Users\ivann\Projects\creforge-sandbox
SANDBOX_OFFICE_CHECKOUT=<a theoffice checkout with broker/sandbox, #521>
SANDBOX_OFFICE_PYTHON=<that checkout's venv python>
SANDBOX_OPERATOR_CHECKOUT=<a village-os checkout with sandbox_operator.py, #25>
SANDBOX_OPERATOR_PYTHON=<its venv python>
```

The runner writes the rest:
- `office.env`: the sandbox Office's generated passwords and DSNs. Never printed.
- `runs/<when>/tokens.env`: the Office's sandbox tokens for that run. Never printed.
- `schedule.json`, `run.lock`, `STOP`, `scheduled-run.cmd`, `scheduled.log`.

The CRE Forge's tenant token is read from the Forge checkout's `.sandbox/sandbox.env` and
passed to the Office in a child's environment only.

## Testing on throwaway stacks

```
python -m scripts.sandbox_run start --as "Ivan Green" --tasks 4 --throwaway --simforge-db-file <file>
```

`--throwaway` runs the same code against throwaway copies:
- a CRE Forge `sf-runner-forge-<home>` on 8013 (`scripts/sandbox_runner/forge-throwaway.yaml`
  over the Forge's own compose);
- the Office's Postgres `sf-runner-office-<home>` on 55443;
- a stand-in for the simulation declaration, so the live Office is not read.

`<home>` is 8 hex digits of the runner home's path (`runner.home_tag`), so two homes' stacks
never share a compose project and one run's `down -v` cannot remove another's (11 November;
both once used `sf-runner-forge` and `sf-runner-office`). The Forge's containers carry the
label `simforge.sandbox.home`. The ports are still every home's, so a machine runs one throwaway
at a time: a throwaway takes `~/.simforge-sandbox-throwaway-lock/run.lock`, naming its home, and
a start from another home is refused `throwaway_held` while it is held, or while another home's
stack (by its label, its project, or the old shared names) holds 8013, 9213 or 55443. A port
held by a process is named by pid, executable and module, never its other arguments.

**The exam check reads the live SimForge database.** phi4 is shared, so a throwaway never runs
while a real exam is open: its start rules, its pause before every tick and its phi4 rule read
the live database, read-only, as the real runner does. That is the DATABASE_URL SimForge's
settings had before `--simforge-db-file` replaced it (from the environment, else the `.env`
files, else the default). Everything else a throwaway reads and writes is the throwaway's.

Both stacks are removed with their volumes at the end. `--simforge-db-file` names a file
holding a throwaway SimForge database's URL (no password on a command line). It is required,
and the runner refuses if SimForge's settings point anywhere else. The broker is served on
127.0.0.1:9213, the operator's throwaway port, so a throwaway never takes the runner's 9212.

The operator is told which broker it talks to: stage 5 runs `sandbox_operator.py setup ...
--broker-url http://127.0.0.1:9212` (9213 for a throwaway), from the same `Targets.office_port`
the broker is served on. That needs a village-os checkout at #25 (a3d0879) or later; an older
one (aead1e5) has no `--broker-url` and refuses with `unrecognized arguments`.
`tests/unit/forges/test_sandbox_operator_command.py` checks every operator command the runner
builds against the operator's usage; set `SANDBOX_OPERATOR_CHECKOUT` and
`SANDBOX_OPERATOR_PYTHON` to check a real checkout too.

Set the throwaway SimForge database's time zone to SimForge's own
(`ALTER DATABASE ... SET timezone TO 'America/Los_Angeles'`). SimForge writes naive UTC
through columns declared with a time zone, and the stored times come out right only on a server
whose `TimeZone` is the machine's. On a UTC server they move 8 hours.

The unit tests drive the same loop against a fake Office: `tests/unit/forges/test_sandbox_runner.py`,
`test_sandbox_rules.py` and `test_sandbox_office_sync.py`.
