"""Three fixes to the sandbox runner (11 November).

1. `--tasks` defaults to all of the seed's tasks, at most 60: a default run never leaves out
   the seed's last task (s0-021, the widening kept).
2. A throwaway's exam check reads the live SimForge database, read-only, as the real runner
   does: phi4 is shared, so a throwaway never runs while a real exam is open.
3. A throwaway's compose projects are its runner home's own, and a start names who holds the
   throwaway ports when another home's throwaway stack does.
"""

from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts import sandbox_run
from src.config import Settings
from src.services.forges.deal_desk_world import generate_tasks, generate_world
from src.services.sandbox import rules, runner
from tests.unit.forges.test_sandbox_operator_command import targets

MARK = runner.DATABASE_URL_BEFORE_THROWAWAY
LIVE = "postgresql://simforge:live-pw@localhost:5432/simforge"
THROWAWAY = "postgresql://sf:tw-pw@127.0.0.1:55444/sf_runner_test"
OVERLAY = Path(sandbox_run.__file__).parent / "sandbox_runner" / "forge-throwaway.yaml"
MON_10 = datetime(2026, 11, 9, 10, 5)  # a Monday, outside the sweeps


# --- 1. --tasks defaults to all of the seed's tasks ---------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["start", "--as", "Ivan Green"],
        ["check", "--as", "Ira Green"],
        ["schedule", "set", "--as", "Ira Green"],
    ],
)
def test_no_task_count_means_all_of_the_seeds(argv: list[str]) -> None:
    assert sandbox_run.build_parser().parse_args(argv).tasks is None


def test_all_of_the_seeds_tasks_includes_its_last_and_stays_under_the_cap() -> None:
    tasks = generate_tasks(generate_world(0))
    want = rules.all_tasks(len(tasks))
    assert want == len(tasks) == 21
    chosen = runner.choose_tasks(0)[:want]
    assert "s0-021" in {t.task_id for t in chosen}
    assert rules.all_tasks(70) == rules.MAX_TASKS == 60


def test_a_schedule_with_no_task_count_is_accepted() -> None:
    schedule = rules.Schedule(owner="Ira Green", at="10:05", tasks=None, set_at="2026-11-11T09:00")
    assert rules.check_schedule(schedule) == []
    assert rules.Schedule.from_dict(schedule.as_dict()).tasks is None


# --- 2. the exam check reads the live database, read-only ---------------------------------------


class _Result:
    def scalar_one(self) -> int:
        return 0


class _Conn:
    def __init__(self, seen: list[str]) -> None:
        self.seen = seen

    async def __aenter__(self) -> _Conn:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def execute(self, stmt: Any) -> _Result:
        self.seen.append(str(stmt))
        return _Result()

    async def rollback(self) -> None:
        self.seen.append("ROLLBACK")


class _Engine:
    def __init__(self, seen: list[str]) -> None:
        self.seen = seen

    def connect(self) -> _Conn:
        return _Conn(self.seen)

    async def dispose(self) -> None:
        self.seen.append("DISPOSED")


@pytest.fixture
def engines(monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], list[str]]:
    """Every engine the check opens (its URL), and every statement it sends."""
    urls: list[str] = []
    seen: list[str] = []

    def fake(url: str, **_kw: Any) -> _Engine:
        urls.append(url)
        return _Engine(seen)

    monkeypatch.setattr(runner, "create_async_engine", fake)
    return urls, seen


def _as_asyncpg(url: str) -> str:
    return Settings.model_construct(database_url=url).sqlalchemy_url


def _throwaway_in_force(monkeypatch: pytest.MonkeyPatch, before: str) -> None:
    """What `--throwaway` leaves: settings on the throwaway database, the earlier value kept."""
    monkeypatch.setenv("DATABASE_URL", THROWAWAY)
    monkeypatch.setenv(MARK, before)
    monkeypatch.setattr(runner, "settings", Settings.model_construct(database_url=THROWAWAY))


async def test_a_throwaways_exam_check_reads_the_live_database_only(
    monkeypatch: pytest.MonkeyPatch, engines: tuple[list[str], list[str]]
) -> None:
    urls, seen = engines
    _throwaway_in_force(monkeypatch, before=LIVE)
    assert await runner.live_exam_open() is False
    assert urls == [_as_asyncpg(LIVE)], "the exam check read something other than the live DB"
    assert not any("55444" in u or "sf_runner_test" in u for u in urls)
    assert seen[0] == "SET TRANSACTION READ ONLY"
    assert '"OperationRun"' in seen[1]
    assert seen[2:] == ["ROLLBACK", "DISPOSED"]


async def test_the_live_database_from_the_env_files_when_the_environment_had_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, engines: tuple[list[str], list[str]]
) -> None:
    urls, _seen = engines
    other = "postgresql://simforge:pw@localhost:5432/simforge_from_dotenv"
    (tmp_path / ".env").write_text(f"DATABASE_URL={other}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    _throwaway_in_force(monkeypatch, before="")
    await runner.live_exam_open()
    assert urls == [_as_asyncpg(other)]


async def test_the_real_runner_reads_its_own_settings(
    monkeypatch: pytest.MonkeyPatch, engines: tuple[list[str], list[str]]
) -> None:
    urls, _seen = engines
    monkeypatch.delenv(MARK, raising=False)
    monkeypatch.setattr(runner, "settings", Settings.model_construct(database_url=LIVE))
    await runner.live_exam_open()
    assert urls == [_as_asyncpg(LIVE)]


def test_the_throwaway_switch_keeps_the_live_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_file = tmp_path / "db.url"
    db_file.write_text(THROWAWAY + "\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", LIVE)
    monkeypatch.delenv(MARK, raising=False)
    monkeypatch.setattr(
        "sys.argv", ["sandbox_run", "start", "--throwaway", "--simforge-db-file", str(db_file)]
    )
    sandbox_run._throwaway_database_first()
    assert runner.live_database_url() == LIVE
    assert os.environ["DATABASE_URL"] == THROWAWAY


def test_every_exam_check_the_script_makes_is_the_live_one() -> None:
    """Not one `exam_open(<session>)` left: a session there is the throwaway's database."""
    src = Path(sandbox_run.__file__).read_text(encoding="utf-8")
    assert re.findall(r"(?<!live_)exam_open\(", src) == []
    assert src.count("runner.live_exam_open()") == 2  # the start rules and the phi4 rule
    assert "exam_is_open=runner.live_exam_open" in src  # before every tick


# --- 3. compose projects per runner home, and who holds the ports -------------------------------


def test_each_runner_home_has_its_own_throwaway_projects(tmp_path: Path) -> None:
    a = targets(tmp_path / "a", throwaway=True)
    b = targets(tmp_path / "b", throwaway=True)
    assert a.forge_project != b.forge_project and a.office_project != b.office_project
    for t in (a, b):
        assert t.forge_project.startswith("sf-runner-forge-")
        assert t.office_project.startswith("sf-runner-office-")
        assert t.forge_backend == f"{t.forge_project}-backend"
    assert targets(tmp_path / "a", throwaway=True).forge_project == a.forge_project
    real = targets(tmp_path / "a", throwaway=False)
    assert (real.forge_project, real.office_project) == ("creforge-sandbox", "office-sandbox")


def test_the_overlay_names_nothing_fixed() -> None:
    overlay = yaml.safe_load(OVERLAY.read_text(encoding="utf-8"))
    assert "name" not in overlay  # the project is the runner's -p
    for service in overlay["services"].values():
        assert service["container_name"].startswith("${SF_RUNNER_FORGE_PROJECT")
        assert service["labels"][runner.HOME_LABEL].startswith("${SF_RUNNER_HOME")
    assert overlay["services"]["backend"]["image"].startswith("${SF_RUNNER_FORGE_PROJECT")


class _Recorded(runner.ProcessStack):
    def __init__(self, t: runner.Targets) -> None:
        super().__init__(t, log=lambda _m: None)
        self.calls: list[tuple[list[str], dict[str, str]]] = []

    def _run(self, args: Any, **kw: Any) -> subprocess.CompletedProcess[bytes]:
        self.calls.append((list(args), dict(kw.get("env") or {})))
        return subprocess.CompletedProcess(list(args), 0, b"", b"")


def test_a_teardown_names_only_its_own_projects(tmp_path: Path) -> None:
    t = targets(tmp_path, throwaway=True)
    stack = _Recorded(t)
    stack.stop()
    downs = [(a, env) for a, env in stack.calls if a[:2] == ["docker", "compose"]]
    assert len(downs) == 2
    for args, env in downs:
        project = args[args.index("-p") + 1]
        assert project in (t.forge_project, t.office_project)
        assert args[-2:] == ["down", "-v"]
        if project == t.office_project:
            assert env["OFFICE_SANDBOX_PROJECT"] == t.office_project
        else:
            assert env["SF_RUNNER_FORGE_PROJECT"] == t.forge_project
            assert env["SF_RUNNER_HOME"] == str(tmp_path / "state")


def test_an_older_office_env_takes_the_homes_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    t = targets(tmp_path, throwaway=True)
    runner.write_env(t.office_env, {"OFFICE_SANDBOX_PROJECT": "sf-runner-office"}, "old")
    monkeypatch.setattr(runner, "ollama_digest", lambda _tag: "sha256:x")
    values = runner.ProcessStack(t, log=lambda _m: None)._office_values()
    assert values["OFFICE_SANDBOX_PROJECT"] == t.office_project
    assert runner.read_env(t.office_env)["OFFICE_SANDBOX_PROJECT"] == t.office_project


def _docker_says(monkeypatch: pytest.MonkeyPatch, line: str) -> None:
    def fake(args: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        assert args[:2] == ["docker", "ps"]
        return subprocess.CompletedProcess(args, 0, line, "")

    monkeypatch.setattr(runner.subprocess, "run", fake)


def test_another_homes_stack_is_named_with_its_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mine = targets(tmp_path / "mine", throwaway=True)
    _docker_says(
        monkeypatch,
        "sf-runner-forge-0badc0de-gateway\tsf-runner-forge-0badc0de\tC:\\Users\\x\\other-home\n",
    )
    who, other = runner.port_holder(8013, mine)
    assert other
    assert "sf-runner-forge-0badc0de" in who and "C:\\Users\\x\\other-home" in who


@pytest.mark.parametrize(
    ("project", "other"),
    [("sf-runner-forge", True), ("sf-runner-office", True), ("funnelforge", False)],
)
def test_the_old_shared_names_are_another_homes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, project: str, other: bool
) -> None:
    _docker_says(monkeypatch, f"{project}-db\t{project}\t\n")
    who, found = runner.port_holder(55443, targets(tmp_path, throwaway=True))
    assert found is other and project in who


def test_this_homes_own_leftover_is_not_another_homes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mine = targets(tmp_path, throwaway=True)
    _docker_says(monkeypatch, f"{mine.forge_project}-gateway\t{mine.forge_project}\th\n")
    assert runner.port_holder(8013, mine)[1] is False


def test_a_process_holder_shows_no_argument_but_its_module(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(args: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        if args[0] == "docker":
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[0] == "netstat":
            return subprocess.CompletedProcess(
                args, 0, "  TCP    127.0.0.1:9213   0.0.0.0:0   LISTENING   4242\n", ""
            )
        line = r'"C:\py\python.exe" -m broker.sandbox serve --token s3cret'
        return subprocess.CompletedProcess(args, 0, line, "")

    monkeypatch.setattr(runner.subprocess, "run", fake)
    who, other = runner.port_holder(9213, None)
    assert who == "pid 4242 (python.exe -m broker.sandbox)" and other is False
    assert "s3cret" not in who


def test_a_start_refuses_and_names_another_homes_throwaway() -> None:
    who = "container sf-runner-forge-0badc0de-gateway (compose project sf-runner-forge-0badc0de, "
    who += "runner home C:\\Users\\x\\other-home)"
    measured = rules.Measured(
        now=MON_10,
        free_gb=12.0,
        exam_open=False,
        busy_ports=(8013, 9213),
        port_holders=((8013, who, True), (9213, "pid 4242 (python.exe -m broker.sandbox)", False)),
    )
    found = rules.check_start(rules.StartRequest("Ivan Green", 4, 21), measured)
    by_code = {r.code: r.detail for r in found}
    assert "other-home" in by_code["throwaway_held"]
    assert "held by pid 4242" in by_code["port_in_use"]


def test_one_throwaway_slot_per_machine_names_its_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SIMFORGE_SANDBOX_THROWAWAY_LOCK_DIR", str(tmp_path / "slot"))
    slot = runner.throwaway_lock()
    assert slot.holder() is None
    slot.take("seed 0 by Ivan Green", home=tmp_path / "other-home")
    held = runner.throwaway_lock().holder()
    assert held and "other-home" in held and "seed 0 by Ivan Green" in held
    measured = rules.Measured(now=MON_10, free_gb=12.0, exam_open=False, throwaway_held_by=held)
    found = rules.check_start(rules.StartRequest("Ivan Green", 4, 21), measured)
    assert [r.code for r in found] == ["throwaway_held"]
    slot.release()
    assert runner.throwaway_lock().holder() is None
