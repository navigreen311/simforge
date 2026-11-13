"""When a sandbox run may start, and when it pauses (ADR-0166 stage 7).

Pure functions of what the runner measured: the clock, free memory, whether phi4 is loaded,
whether a SimForge exam is open, the schedule and the runs already recorded. The runner
measures; this module decides. Every refusal is a code and a sentence, and every reason that
applies is reported, not just the first.

The rulings (Ivan Green, 8 and 9 November 2026):

- **Who.** Ivan Green or Ira Green start a run by hand, or a schedule one of them set. The
  schedule is recorded with its owner, and the owner can stop it.
- **When.**
  - Never inside SimForge's sweeps, :17-:24 and :47-:54. A hand-started run is refused there;
    a scheduled one waits for the window to close. A run in progress pauses there and resumes
    after.
  - Not with a SimForge exam open (an `OperationRun` with no end, verdict or timeout). A run
    in progress pauses while one is open.
  - Not with under 8 GB of free memory. The phi4 rule (standing, 4 November): if phi4 is
    loaded, no SimForge exam is open and it is outside the sweeps, `ollama stop phi4` first,
    then measure again.
- **How much.** At most 60 tasks per run; at most one scheduled run per business day.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from src.services.sandbox.record import MAX_TASKS, STARTERS

#: SimForge's sweeps, by minute of the hour, both ends inside.
SWEEPS: tuple[tuple[int, int], ...] = ((17, 24), (47, 54))
MIN_FREE_GB = 8.0
#: The first seed a schedule uses: seeds 0 to 3 were run by hand on generator 1.2.0.
FIRST_SCHEDULED_SEED = 4
#: Monday to Friday. No holiday calendar: a holiday is a business day here (not ruled).
BUSINESS_DAYS = frozenset({0, 1, 2, 3, 4})


@dataclass(frozen=True)
class Refusal:
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


def in_sweep(now: datetime) -> tuple[int, int] | None:
    """The sweep `now` is inside, or None."""
    for start, end in SWEEPS:
        if start <= now.minute <= end:
            return start, end
    return None


def sweep_ends(now: datetime) -> datetime:
    """The first minute after the sweep `now` is in (or `now` if it is in none)."""
    window = in_sweep(now)
    if window is None:
        return now
    return now.replace(minute=window[1], second=0, microsecond=0) + timedelta(minutes=1)


def is_business_day(day: date) -> bool:
    return day.weekday() in BUSINESS_DAYS


def stop_phi4_first(*, free_gb: float, phi4_loaded: bool, exam_open: bool, now: datetime) -> bool:
    """The phi4 rule: unload phi4 before measuring, if and only if it may be unloaded."""
    return free_gb < MIN_FREE_GB and phi4_loaded and not exam_open and in_sweep(now) is None


@dataclass
class Schedule:
    """A schedule one of the starters set. Kept in the runner's own directory, not a table:
    every run it starts records its owner on `SandboxRun.scheduleOwner`."""

    owner: str
    at: str  # "HH:MM", local time; the OS scheduler fires it, the runner checks it
    tasks: int | None  # None: all of the seed's tasks, at most MAX_TASKS
    set_at: str
    enabled: bool = True
    stopped_at: str | None = None
    stopped_by: str | None = None
    #: The first seed it may use. Each run takes the next seed no run has used, never below it
    #: (`first_seed`); None (a schedule set before generator 1.3.0) is `FIRST_SCHEDULED_SEED`.
    seed: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Schedule:
        return cls(**data)


def first_seed(schedule: Schedule | None) -> int:
    """The lowest seed a scheduled run may take."""
    if schedule is None or schedule.seed is None:
        return FIRST_SCHEDULED_SEED
    return schedule.seed


def scheduled_seed(schedule: Schedule | None, next_unused: int) -> int:
    """The seed a scheduled run takes: the next one no run has used (`next_unused`, one more than
    the highest recorded), and never one below the schedule's first."""
    return max(first_seed(schedule), next_unused)


def all_tasks(seed_tasks: int) -> int:
    """What a run files when no task count is given: every task of its seed, at most
    MAX_TASKS. A seed's last task is never left out by a default (11 November)."""
    return min(seed_tasks, MAX_TASKS)


def check_schedule(schedule: Schedule) -> list[Refusal]:
    found = []
    if schedule.owner not in STARTERS:
        found.append(Refusal("not_a_schedule_owner", f"{schedule.owner} is not Ivan or Ira"))
    try:
        hh, mm = (int(x) for x in schedule.at.split(":"))
        if not (0 <= hh < 24 and 0 <= mm < 60):
            raise ValueError
        if in_sweep(datetime(2026, 1, 1, hh, mm)) is not None:
            found.append(
                Refusal("schedule_in_a_sweep", f"{schedule.at} is inside :17-:24 or :47-:54")
            )
    except ValueError:
        found.append(Refusal("schedule_time_unreadable", f"{schedule.at!r} is not HH:MM"))
    if schedule.tasks is not None and not 1 <= schedule.tasks <= MAX_TASKS:
        found.append(Refusal("over_task_cap", f"{schedule.tasks} tasks; 1 to {MAX_TASKS}"))
    return found


@dataclass(frozen=True)
class Measured:
    """What the runner found just before starting."""

    now: datetime
    free_gb: float
    exam_open: bool
    lock_held_by: str | None = None
    busy_ports: tuple[int, ...] = ()
    missing: tuple[str, ...] = ()  # config, checkouts, the sandbox tables
    #: (port, who holds it, whether that is another runner home's throwaway stack), per busy port
    port_holders: tuple[tuple[int, str, bool], ...] = ()
    #: a throwaway only: who holds the machine's one throwaway slot, if another run does
    throwaway_held_by: str | None = None


@dataclass(frozen=True)
class StartRequest:
    starter: str
    tasks: int
    seed_tasks: int
    scheduled: bool = False
    schedule: Schedule | None = None
    #: local start times of runs this schedule's owner's schedule already started today
    scheduled_today: Sequence[datetime] = field(default_factory=tuple)


def check_start(request: StartRequest, measured: Measured) -> list[Refusal]:
    """Every reason this run may not start now. Empty means it may."""
    found: list[Refusal] = []
    if request.starter not in STARTERS:
        found.append(Refusal("not_a_starter", f"{request.starter} is not Ivan or Ira"))
    if not 1 <= request.tasks <= MAX_TASKS:
        found.append(Refusal("over_task_cap", f"{request.tasks} tasks; 1 to {MAX_TASKS}"))
    if request.tasks > request.seed_tasks:
        found.append(
            Refusal(
                "more_tasks_than_the_seed",
                f"{request.tasks} asked, the seed has {request.seed_tasks}",
            )
        )
    if request.scheduled:
        if request.schedule is None:
            found.append(Refusal("no_schedule", "no schedule is set"))
        else:
            found += check_schedule(request.schedule)
            if not request.schedule.enabled:
                found.append(
                    Refusal(
                        "schedule_stopped",
                        f"stopped by {request.schedule.stopped_by} at "
                        f"{request.schedule.stopped_at}",
                    )
                )
            if request.starter != request.schedule.owner:
                found.append(Refusal("not_the_schedule_owner", request.starter))
        if not is_business_day(measured.now.date()):
            found.append(Refusal("not_a_business_day", measured.now.strftime("%A")))
        if request.scheduled_today:
            first = min(request.scheduled_today)
            found.append(Refusal("scheduled_run_already_today", f"one started at {first:%H:%M}"))
    window = in_sweep(measured.now)
    if window is not None:
        found.append(
            Refusal("inside_a_sweep", f"{measured.now:%H:%M} is inside :{window[0]}-:{window[1]}")
        )
    if measured.exam_open:
        found.append(Refusal("exam_open", "a SimForge exam (OperationRun) is open"))
    if measured.free_gb < MIN_FREE_GB:
        found.append(
            Refusal("memory", f"{measured.free_gb:.1f} GB free, under {MIN_FREE_GB:.0f} GB")
        )
    if measured.lock_held_by:
        found.append(
            Refusal("another_run", f"a sandbox run is in progress ({measured.lock_held_by})")
        )
    if measured.throwaway_held_by:
        found.append(
            Refusal(
                "throwaway_held",
                f"another throwaway run holds the throwaway stacks ({measured.throwaway_held_by})",
            )
        )
    holders = {port: (who, other) for port, who, other in measured.port_holders}
    for port in measured.busy_ports:
        who, other = holders.get(port, ("", False))
        if other:
            found.append(
                Refusal(
                    "throwaway_held",
                    f"127.0.0.1:{port} is held by another runner home's throwaway stack: {who}",
                )
            )
        else:
            held = f", held by {who}" if who else ""
            found.append(Refusal("port_in_use", f"127.0.0.1:{port} is already listening{held}"))
    for what in measured.missing:
        found.append(Refusal("missing", what))
    return found


def pause_reason(*, now: datetime, exam_open: bool) -> str | None:
    """Why a run in progress waits now, or None. It resumes when this is None again."""
    window = in_sweep(now)
    if window is not None:
        return f"inside the :{window[0]}-:{window[1]} sweep"
    if exam_open:
        return "a SimForge exam is open"
    return None
