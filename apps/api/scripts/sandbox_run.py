"""Start, schedule and stop a sandbox run (ADR-0166 stage 7).

    cd apps/api
    python -m scripts.sandbox_run check    --as "Ivan Green" [--tasks N] [--seed S]
    python -m scripts.sandbox_run start    --as "Ivan Green" [--tasks N] [--seed S]
    python -m scripts.sandbox_run stop     --as "Ivan Green"
    python -m scripts.sandbox_run schedule set  --as "Ira Green" --at 10:05 --tasks 40 [--register]
    python -m scripts.sandbox_run schedule show
    python -m scripts.sandbox_run schedule stop --as "Ira Green"
    python -m scripts.sandbox_run scheduled      # what the OS scheduler runs

`start` runs one run from start to stop (`src.services.sandbox.runner`) and prints its page.
`check` runs every start rule and starts nothing. Exit codes: 0 ok; 3 a rule refused and
nothing was started; 1 any other failure (everything started is stopped).

The runner's own directory is `%USERPROFILE%\\.simforge-sandbox` (`SIMFORGE_SANDBOX_HOME`
overrides; never under OneDrive). It holds `runner.env` (the three checkouts and their pythons,
written by hand), the generated `office.env`, `schedule.json`, the lock, and `runs/<when>/`
with each run's world file, tokens, logs, `summary.json` and page.

`--tasks` defaults to all of the seed's tasks, at most 60.

`--throwaway` runs the same code on a throwaway copy of every stack (CRE Forge on 8013, the
Office's Postgres on 55443, both removed after), under compose projects of its runner home's
own, and one throwaway at a time on the machine. It requires `--simforge-db-file`, a file
holding the URL of a throwaway SimForge database (so no password is on a command line): a
throwaway run never writes to SimForge's own database. It still reads the live one, read-only,
for the exam check: phi4 is shared, so a throwaway never runs while a real exam is open.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


def _throwaway_database_first() -> None:
    """`--throwaway` names its own SimForge database. It is set before any SimForge module is
    imported, because importing them reads the settings once."""
    argv = sys.argv[1:]
    if "--throwaway" in argv and "--simforge-db-file" in argv:
        path = Path(argv[argv.index("--simforge-db-file") + 1])
        if path.is_file():
            # The exam check still reads the live database (`runner.live_database_url`).
            os.environ.setdefault(
                "SIMFORGE_SANDBOX_DATABASE_URL_BEFORE_THROWAWAY", os.environ.get("DATABASE_URL", "")
            )
            os.environ["DATABASE_URL"] = path.read_text(encoding="utf-8").strip()


_throwaway_database_first()

from src.services.sandbox import rules  # noqa: E402
from src.services.sandbox.record import STARTERS  # noqa: E402

REFUSED = 3
TASK_NAME = "SimForge sandbox run"
lines: list[str] = []


def log(message: str) -> None:
    stamp = f"{datetime.now():%H:%M:%S} {message}"
    lines.append(stamp)
    print(stamp, flush=True)


def _schedule_path() -> Path:
    from src.services.sandbox.runner import home

    return home() / "schedule.json"


def read_schedule() -> rules.Schedule | None:
    path = _schedule_path()
    if not path.is_file():
        return None
    return rules.Schedule.from_dict(json.loads(path.read_text(encoding="utf-8")))


def write_schedule(schedule: rules.Schedule) -> None:
    path = _schedule_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(schedule.as_dict(), indent=2) + "\n", encoding="utf-8")


def _stop_file() -> Path:
    from src.services.sandbox.runner import home

    return home() / "STOP"


def stop_requested() -> str | None:
    path = _stop_file()
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8").strip() or "asked"


async def _measure_and_check(
    args: argparse.Namespace, *, scheduled: bool
) -> tuple[list[rules.Refusal], dict[str, Any]]:
    """Every start rule. The phi4 rule may unload phi4 (the standing permission)."""
    from src.db import SessionLocal
    from src.services.forges.deal_desk_world import generate_tasks, generate_world
    from src.services.sandbox import runner

    state = runner.home()
    found: list[rules.Refusal] = []
    sync = runner.synced(state)
    if sync:
        found.append(rules.Refusal("synced_folder", sync))
    config = runner.read_env(state / "runner.env")
    missing = [f"{k} in {state / 'runner.env'}" for k in runner.CONFIG_KEYS if not config.get(k)]
    targets = None
    if not missing:
        targets = runner.Targets.from_config(config, throwaway=args.throwaway, state=state)
        missing += targets.missing()
    schedule = read_schedule() if scheduled else None
    starter = schedule.owner if scheduled and schedule else args.as_
    async with SessionLocal() as db:
        tables = await runner.sandbox_tables_exist(db)
        if not tables:
            missing.append(
                "SimForge's SandboxRun and SandboxStep tables (migration "
                "20261109000000 is not applied)"
            )
        seed = args.seed
        if seed is None:
            seed = (
                schedule.seed
                if schedule and schedule.seed is not None
                else (await runner.next_seed(db) if tables else 0)
            )
        today = await runner.scheduled_today(db, datetime.now()) if scheduled and tables else []
    exam = await runner.live_exam_open()
    now = datetime.now()
    free = runner.free_gb()
    loaded = runner.phi4_loaded()
    if rules.stop_phi4_first(free_gb=free, phi4_loaded=loaded, exam_open=exam, now=now):
        log(
            f"   the phi4 rule: {free:.1f} GB free with phi4 loaded, no exam open, outside the "
            "sweeps: unloading phi4 (ollama stop phi4)"
        )
        runner.stop_phi4()
        time.sleep(5)
        free = runner.free_gb()
    seed_tasks = len(generate_tasks(generate_world(seed)))
    want = schedule.tasks if scheduled and schedule else args.tasks
    if want is None:
        want = rules.all_tasks(seed_tasks)
    request = rules.StartRequest(
        starter=starter or "",
        tasks=want,
        seed_tasks=seed_tasks,
        scheduled=scheduled,
        schedule=schedule,
        scheduled_today=today,
    )
    busy = tuple(p for p in (targets.ports() if targets else ()) if runner.port_busy(p))
    holders = tuple((p, *runner.port_holder(p, targets)) for p in busy)
    throwaway = targets is not None and targets.throwaway
    measured = rules.Measured(
        now=now,
        free_gb=free,
        exam_open=exam,
        lock_held_by=runner.Lock(state).holder(),
        busy_ports=busy,
        missing=tuple(missing),
        port_holders=holders,
        throwaway_held_by=runner.throwaway_lock().holder() if throwaway else None,
    )
    found += rules.check_start(request, measured)
    return found, {
        "starter": starter,
        "seed": seed,
        "tasks": want,
        "targets": targets,
        "schedule": schedule,
        "free_gb": free,
        "state": state,
    }


def _report(found: list[rules.Refusal]) -> int:
    for r in found:
        log(f"REFUSED {r}")
    return REFUSED


async def _start(args: argparse.Namespace, *, scheduled: bool) -> int:
    from src.db import SessionLocal
    from src.services.sandbox import runner

    if scheduled:
        schedule = read_schedule()
        now = datetime.now()
        if rules.in_sweep(now):
            until = rules.sweep_ends(now)
            log(f"scheduled at {now:%H:%M}, inside a sweep: waiting until {until:%H:%M}")
            time.sleep(max(0.0, (until - now).total_seconds()))
        args.as_ = schedule.owner if schedule else None
    log("1. the start rules")
    found, facts = await _measure_and_check(args, scheduled=scheduled)
    if found:
        return _report(found)
    log(
        f"   all pass: {facts['starter']}, seed {facts['seed']}, {facts['tasks']} tasks, "
        f"{facts['free_gb']:.1f} GB free" + (" (THROWAWAY stacks)" if args.throwaway else "")
    )
    state: Path = facts["state"]
    targets: runner.Targets = facts["targets"]
    lock = runner.Lock(state)
    lock.take(f"seed {facts['seed']} by {facts['starter']}")
    # One throwaway per machine: its ports are every home's (released in `finally` below).
    slot = runner.throwaway_lock() if targets.throwaway else None
    if slot is not None:
        slot.take(f"seed {facts['seed']} by {facts['starter']}", home=state)
    run_dir = state / "runs" / f"{datetime.now():%Y%m%d-%H%M%S}-seed-{facts['seed']}"
    run_dir.mkdir(parents=True, exist_ok=True)
    stack = runner.ProcessStack(targets, log)
    outcome: runner.Outcome | None = None
    code = 0
    try:
        tasks = runner.choose_tasks(facts["seed"])
        log(f"2. seed {facts['seed']}: {len(tasks)} tasks; filing up to {facts['tasks']}")
        budget = runner.Budget(
            max_ticks=args.max_ticks or 4 * facts["tasks"] + 10, max_minutes=args.max_minutes
        )
        async with SessionLocal() as db:
            outcome = await runner.drive(
                db,
                stack,
                starter=facts["starter"],
                seed=facts["seed"],
                tasks=tasks,
                want=facts["tasks"],
                run_dir=run_dir,
                budget=budget,
                log=log,
                schedule_owner=facts["starter"] if scheduled else None,
                exam_is_open=runner.live_exam_open,
                stop_requested=stop_requested,
            )
    except Exception as exc:  # noqa: BLE001 - report it, then stop everything
        log(f"FAILED: {type(exc).__name__}: {exc}")
        code = 1
    finally:
        log("9. stopping everything this run started")
        for said in stack.stop():
            log(f"   {said}")
        exam = await runner.live_exam_open()
        if runner.phi4_loaded() and not exam and rules.in_sweep(datetime.now()) is None:
            runner.stop_phi4()
            log("   the phi4 rule: unloaded phi4 (no exam open, outside the sweeps)")
        lock.release()
        if slot is not None:
            slot.release()
        _stop_file().unlink(missing_ok=True)
        summary = {
            "outcome": outcome.as_dict() if outcome else None,
            "exit": code,
            "throwaway": args.throwaway,
            "log": lines,
        }
        (run_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, default=str), encoding="utf-8"
        )
        (run_dir / "run.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if outcome and outcome.page:
        log(f"page: {outcome.page}")
        log(f"summary: {run_dir / 'summary.json'}")
    return code


def _schedule(args: argparse.Namespace) -> int:
    from src.services.sandbox.runner import home

    current = read_schedule()
    if args.action == "show":
        print(json.dumps(current.as_dict() if current else None, indent=2))
        return 0
    if args.as_ not in STARTERS:
        return _report([rules.Refusal("not_a_starter", f"{args.as_} is not Ivan or Ira")])
    if args.action == "stop":
        if current is None or not current.enabled:
            log("no schedule is running")
            return 0
        if args.as_ != current.owner:
            return _report(
                [
                    rules.Refusal(
                        "not_the_schedule_owner",
                        f"the schedule is {current.owner}'s; only they stop it",
                    )
                ]
            )
        current.enabled = False
        current.stopped_at = datetime.now().isoformat(timespec="seconds")
        current.stopped_by = args.as_
        write_schedule(current)
        _register(current, enable=False, registered=args.register)
        log(f"schedule stopped by {args.as_}")
        return 0
    schedule = rules.Schedule(
        owner=args.as_,
        at=args.at,
        tasks=args.tasks,
        set_at=datetime.now().isoformat(timespec="seconds"),
        seed=args.seed,
    )
    found = rules.check_schedule(schedule)
    if found:
        return _report(found)
    if current and current.enabled and current.owner != args.as_:
        return _report(
            [
                rules.Refusal(
                    "not_the_schedule_owner",
                    f"{current.owner}'s schedule is running; they stop it first",
                )
            ]
        )
    write_schedule(schedule)
    many = "all of the seed's" if args.tasks is None else str(args.tasks)
    log(
        f"schedule set by {args.as_}: business days at {args.at}, {many} tasks "
        f"({home() / 'schedule.json'})"
    )
    _register(schedule, enable=True, registered=args.register)
    return 0


def _register(schedule: rules.Schedule, *, enable: bool, registered: bool) -> None:
    """The Windows scheduled task that runs `scheduled` on business days. Only with --register."""
    from src.services.sandbox.runner import home

    cmd = home() / "scheduled-run.cmd"
    api = Path(__file__).resolve().parents[1]
    line = f'cd /d "{api}" && "{sys.executable}" -m scripts.sandbox_run scheduled'
    cmd.write_text(
        f'@echo off\r\n{line} >> "{home() / "scheduled.log"}" 2>&1\r\n', encoding="ascii"
    )
    create = [
        "schtasks",
        "/Create",
        "/TN",
        TASK_NAME,
        "/SC",
        "WEEKLY",
        "/D",
        "MON,TUE,WED,THU,FRI",
        "/ST",
        schedule.at,
        "/TR",
        f'"{cmd}"',
        "/F",
    ]
    change = ["schtasks", "/Change", "/TN", TASK_NAME, "/ENABLE" if enable else "/DISABLE"]
    if not registered:
        log(
            "not registered with Windows (pass --register); it would run: "
            + " ".join(create if enable else change)
        )
        return
    done = subprocess.run(create if enable else change, capture_output=True, text=True, check=False)
    log(
        f"   {' '.join((create if enable else change)[:3])} -> exit {done.returncode} "
        f"{done.stdout.strip()[:200]}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "start"):
        p = sub.add_parser(name)
        p.add_argument("--as", dest="as_", required=True, choices=STARTERS)
        p.add_argument("--tasks", type=int, help="default: all of the seed's tasks, at most 60")
        p.add_argument("--seed", type=int)
    for p in (sub.choices["check"], sub.choices["start"], sub.add_parser("scheduled")):
        p.add_argument("--throwaway", action="store_true")
        p.add_argument("--simforge-db-file", type=Path, help="a file holding the URL")
        p.add_argument("--max-ticks", type=int)
        p.add_argument("--max-minutes", type=float, default=240.0)
    stop = sub.add_parser("stop")
    stop.add_argument("--as", dest="as_", required=True, choices=STARTERS)
    sch = sub.add_parser("schedule")
    sch.add_argument("action", choices=("set", "show", "stop"))
    sch.add_argument("--as", dest="as_")
    sch.add_argument("--at", default="10:05")
    sch.add_argument("--tasks", type=int, help="default: all of the seed's tasks, at most 60")
    sch.add_argument("--seed", type=int)
    sch.add_argument("--register", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "stop":
        path = _stop_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{args.as_} at {datetime.now():%H:%M}", encoding="utf-8")
        log(f"asked the run in progress to stop ({path}); it stops after its current tick")
        return 0
    if args.command == "schedule":
        return _schedule(args)
    if getattr(args, "throwaway", False):
        if not args.simforge_db_file or not args.simforge_db_file.is_file():
            why = "--throwaway writes only to the database whose URL is in --simforge-db-file"
            return _report([rules.Refusal("throwaway_needs_a_database", why)])
        wanted = urlsplit(args.simforge_db_file.read_text(encoding="utf-8").strip())
        from src.db import engine

        if (engine.url.host, engine.url.port) != (wanted.hostname, wanted.port):
            why = "SimForge's settings were read before the throwaway database was set"
            return _report([rules.Refusal("throwaway_database_not_in_use", why)])
    for name, default in (("seed", None), ("tasks", None), ("as_", None)):
        if not hasattr(args, name):
            setattr(args, name, default)
    if args.command == "check":
        found, facts = asyncio.run(_measure_and_check(args, scheduled=False))
        if found:
            return _report(found)
        log(
            f"all start rules pass: {facts['starter']}, seed {facts['seed']}, {facts['tasks']} "
            f"tasks, {facts['free_gb']:.1f} GB free"
        )
        return 0
    return asyncio.run(_start(args, scheduled=args.command == "scheduled"))


if __name__ == "__main__":
    sys.exit(main())
