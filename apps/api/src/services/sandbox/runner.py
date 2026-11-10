"""The sandbox runner: one run from start to stop (ADR-0166 stage 7).

For one run it:

1. checks every start rule (`rules.check_start`) and refuses with every reason that applies;
2. picks a seed (the next after the last one run, unless named) and that seed's tasks;
3. loads the seed's world into the sandbox CRE Forge with `--replace` (the Forge's own loader);
4. starts a fresh sandbox Office (a new `office_sandbox` database), sets up Greenstone and serves
   it on 127.0.0.1:9212 (9213 for a throwaway);
5. sets up the sandbox Village operator, pointed at that Office's broker;
6. as the starter, with their own sandbox token, starts the Office's run and files up to N
   tasks; a filing the Office refuses is skipped and named;
7. opens the `SandboxRun` on the tasks filed, then ticks the operator one step at a time,
   asks `sandbox-approver` to approve each proposal, and records every step the Office wrote
   (`office_sync`) as a `SandboxStep`; it pauses inside a sweep or while a SimForge exam is
   open, and stops at its tick or wall-clock budget, or when told to;
8. finishes the Office's run, closes the `SandboxRun`, writes its page;
9. stops everything it started.

`Stack` is everything outside SimForge; `ProcessStack` is the real one. The loop (`drive`) is
the same for both, and is tested against a fake.

Practice, never evidence (ADR-0166 rulings 1 and 5). The runner writes `SandboxRun` and
`SandboxStep` through `record` and nothing else in SimForge. It reads `OperationRun` only to
refuse or pause while an exam is open.
"""

from __future__ import annotations

import contextlib
import ctypes
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.operation_run import OperationRun
from src.models.sandbox_run import SandboxRun, SandboxStep
from src.services.forges.deal_desk_world import (
    READ_MODULES,
    Task,
    export_json,
    generate_tasks,
    generate_world,
    world_name,
)
from src.services.sandbox import office_sync, record, rules
from src.services.sandbox.page import load_run, render_run_page

VENTURE = "greenstone"
TERMINAL = frozenset({"answered", "refused", "declined", "escalated", "failed"})
OLLAMA = "http://127.0.0.1:11434"
PHI4 = "phi4:latest"
#: The sandbox Office's broker: 9212 is the runner's, 9213 a throwaway's. The operator
#: (village-os `sandbox.BROKER_URLS`) and the Office (`broker/sandbox/guards.py`) accept these.
RUNNER_OFFICE_PORT = 9212
THROWAWAY_OFFICE_PORT = 9213

# --- the runner's own directory ------------------------------------------------------------------


def home() -> Path:
    """Where the runner keeps its config, schedule, lock and each run's files. Never synced."""
    return Path(os.environ.get("SIMFORGE_SANDBOX_HOME") or Path.home() / ".simforge-sandbox")


def synced(path: Path) -> str | None:
    """A path under OneDrive, which would copy tokens to the cloud (secrets never there)."""
    resolved = str(path.resolve()).lower()
    for key in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        root = os.environ.get(key)
        if root and resolved.startswith(str(Path(root).resolve()).lower()):
            return f"{path} is under {key}"
    if "onedrive" in resolved:
        return f"{path} is under a OneDrive folder"
    return None


def read_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip() and not raw.lstrip().startswith("#") and "=" in raw:
            k, _, v = raw.partition("=")
            out[k.strip()] = v.strip()
    return out


def write_env(path: Path, values: Mapping[str, str], note: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = f"# {note}\n" + "".join(f"{k}={v}\n" for k, v in values.items())
    path.write_text(body, encoding="ascii")


# --- the targets: the shared sandbox, or a throwaway copy ----------------------------------------

CONFIG_KEYS = (
    "SANDBOX_FORGE_CHECKOUT",  # medlink-wholesale main, with the loader's --replace (#110)
    "SANDBOX_OFFICE_CHECKOUT",  # theoffice with broker/sandbox (#521)
    "SANDBOX_OFFICE_PYTHON",
    "SANDBOX_OPERATOR_CHECKOUT",  # village-os with sandbox_operator.py (#25)
    "SANDBOX_OPERATOR_PYTHON",
)


@dataclass(frozen=True)
class Targets:
    throwaway: bool
    forge_checkout: Path
    office_checkout: Path
    office_python: Path
    operator_checkout: Path
    operator_python: Path
    state: Path
    forge_project: str
    forge_port: int
    forge_compose: tuple[Path, ...]
    forge_env: Path
    office_project: str
    office_port: int
    office_pg_port: int
    office_env: Path
    live_office_env: Path

    @property
    def forge_backend(self) -> str:
        return f"{self.forge_project}-backend"

    @property
    def office_db(self) -> str:
        return f"{self.office_project}-db"

    @property
    def broker_url(self) -> str:
        """The sandbox Office this run serves, and the only one its operator may talk to."""
        return f"http://127.0.0.1:{self.office_port}"

    @property
    def forge_url(self) -> str:
        return f"http://127.0.0.1:{self.forge_port}/forge"

    @classmethod
    def from_config(cls, config: Mapping[str, str], *, throwaway: bool, state: Path) -> Targets:
        forge = Path(config["SANDBOX_FORGE_CHECKOUT"])
        here = Path(__file__).resolve().parents[3] / "scripts" / "sandbox_runner"
        common = dict(
            forge_checkout=forge,
            office_checkout=Path(config["SANDBOX_OFFICE_CHECKOUT"]),
            office_python=Path(config["SANDBOX_OFFICE_PYTHON"]),
            operator_checkout=Path(config["SANDBOX_OPERATOR_CHECKOUT"]),
            operator_python=Path(config["SANDBOX_OPERATOR_PYTHON"]),
            live_office_env=Path(
                config.get("SANDBOX_LIVE_OFFICE_ENV") or Path.home() / "Projects/theoffice/.env"
            ),
        )
        if throwaway:
            tw = state / "throwaway"
            return cls(
                throwaway=True,
                state=tw,
                forge_project="sf-runner-forge",
                forge_port=8013,
                forge_compose=(forge / "docker-compose.sandbox.yml", here / "forge-throwaway.yaml"),
                forge_env=tw / "forge.env",
                office_project="sf-runner-office",
                office_port=THROWAWAY_OFFICE_PORT,
                office_pg_port=55443,
                office_env=tw / "office.env",
                **common,  # type: ignore[arg-type]
            )
        return cls(
            throwaway=False,
            state=state,
            forge_project="creforge-sandbox",
            forge_port=8012,
            forge_compose=(forge / "docker-compose.sandbox.yml",),
            forge_env=forge / ".sandbox" / "sandbox.env",
            office_project="office-sandbox",
            office_port=RUNNER_OFFICE_PORT,
            office_pg_port=55442,
            office_env=state / "office.env",
            **common,  # type: ignore[arg-type]
        )

    def missing(self) -> list[str]:
        """Files the run needs that are not there. Read only."""
        out = []
        checks = {
            "the CRE Forge's sandbox compose": self.forge_checkout / "docker-compose.sandbox.yml",
            "the Office's sandbox broker": self.office_checkout / "broker" / "sandbox" / "runs.py",
            "the Office's sandbox compose": self.office_checkout / "compose.sandbox.yaml",
            "the Office's python": self.office_python,
            "the sandbox operator": self.operator_checkout / "sandbox_operator.py",
            "the operator's python": self.operator_python,
            "the live Office's .env (the simulation check reads it)": self.live_office_env,
        }
        if not self.throwaway:
            checks["the sandbox CRE Forge's env (.sandbox/sandbox.env)"] = self.forge_env
        for what, path in checks.items():
            if not path.exists():
                out.append(f"{what}: {path}")
        loader = self.forge_checkout / "backend" / "app" / "sandbox" / "loader.py"
        if not loader.is_file() or "--replace" not in loader.read_text(encoding="utf-8"):
            out.append(f"a CRE Forge loader with --replace (medlink-wholesale #110): {loader}")
        return out

    def ports(self) -> tuple[int, ...]:
        """Ports that must be free before the run starts its own processes."""
        return (
            (self.office_port, self.forge_port, self.office_pg_port)
            if self.throwaway
            else (self.office_port,)
        )


# --- the world beyond SimForge -------------------------------------------------------------------


class Stack(Protocol):
    def load_world(self, seed: int, path: Path) -> str: ...
    def office_up(self, run_dir: Path) -> Path: ...
    def operator_up(self, run_dir: Path, tokens: Path) -> None: ...
    def office(self, method: str, path: str, token: str, body: Any = None) -> tuple[int, Any]: ...
    def snapshot(self, office_run_id: str) -> list[dict[str, Any]]: ...
    def tick(self) -> list[str]: ...
    def stop(self) -> list[str]: ...


def port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=3) as r:  # noqa: S310 - loopback only
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def clean_env(values: Mapping[str, str] | None = None) -> dict[str, str]:
    """The OS basics and the values given, nothing inherited (the sandboxes' own rule)."""
    keep = (
        "SYSTEMROOT",
        "PATH",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "HOMEDRIVE",
        "HOMEPATH",
        "HOME",
        "COMSPEC",
        "SYSTEMDRIVE",
        "WINDIR",
        "LOCALAPPDATA",
        "APPDATA",
    )
    env = {k: os.environ[k] for k in keep if k in os.environ}
    return {**env, **(values or {}), "PYTHONIOENCODING": "utf-8"}


class ProcessStack:
    """The real stack: docker compose for the Forge and the Office's Postgres, the Office's
    broker and the operator as processes. Every secret is read from its env file and passed
    in a child's environment; none is printed or put on a command line."""

    def __init__(self, targets: Targets, log: Callable[[str], None]) -> None:
        self.t = targets
        self.log = log
        self.started_forge = False
        self.started_office_db = False
        self.broker: subprocess.Popen[str] | None = None
        self.run_dir: Path | None = None
        self.operator_config: Path | None = None

    # -- helpers
    def _run(
        self,
        args: Sequence[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        stdin: bytes | None = None,
        timeout: int = 900,
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            list(args),
            cwd=cwd,
            env=dict(env) if env is not None else None,
            input=stdin,
            capture_output=True,
            timeout=timeout,
            check=False,
        )

    def _compose_forge(self) -> list[str]:
        files = [x for f in self.t.forge_compose for x in ("-f", str(f))]
        return [
            "docker",
            "compose",
            "-p",
            self.t.forge_project,
            *files,
            "--env-file",
            str(self.t.forge_env),
        ]

    def _compose_office(self) -> list[str]:
        return [
            "docker",
            "compose",
            "-f",
            str(self.t.office_checkout / "compose.sandbox.yaml"),
            "--env-file",
            str(self.t.office_env),
        ]

    def _running(self, container: str) -> bool:
        done = self._run(["docker", "inspect", "-f", "{{.State.Running}}", container])
        return done.returncode == 0 and done.stdout.strip() == b"true"

    def _psql(self, sql: str, db: str = "office_sandbox") -> str:
        done = self._run(
            [
                "docker",
                "exec",
                "-i",
                self.t.office_db,
                "psql",
                "-U",
                "postgres",
                "-d",
                db,
                "-v",
                "ON_ERROR_STOP=1",
                "-tA",
            ],
            stdin=sql.encode("utf-8"),
        )
        if done.returncode:
            raise RuntimeError(done.stderr.decode("utf-8", "replace").strip()[-500:])
        return done.stdout.decode("utf-8")

    def forge_token(self) -> str:
        return read_env(self.t.forge_env)["SANDBOX_TENANT_TOKEN"]

    # -- the CRE Forge
    def _forge_env(self) -> None:
        if self.t.throwaway and not self.t.forge_env.is_file():
            write_env(
                self.t.forge_env,
                {
                    "SANDBOX_TENANT_TOKEN": secrets.token_urlsafe(32),
                    "SANDBOX_DB_PASSWORD": secrets.token_urlsafe(24),
                    "SANDBOX_JWT_SECRET": secrets.token_urlsafe(32),
                    "SANDBOX_PORT": str(self.t.forge_port),
                },
                "A throwaway sandbox CRE Forge for the SimForge runner's tests. Generated.",
            )

    def load_world(self, seed: int, path: Path) -> str:
        self._forge_env()
        if not self._running(self.t.forge_backend):
            self.log(f"   the sandbox CRE Forge ({self.t.forge_project}) is down: starting it")
            up = self._run([*self._compose_forge(), "up", "-d", "--build"], timeout=1800)
            if up.returncode:
                raise RuntimeError(
                    "the sandbox CRE Forge did not come up: "
                    + up.stderr.decode("utf-8", "replace")[-1500:]
                )
            self.started_forge = True
        for _ in range(120):
            if http_ok(f"http://127.0.0.1:{self.t.forge_port}/ready"):
                break
            time.sleep(2)
        else:
            raise RuntimeError(f"the sandbox CRE Forge is not ready on :{self.t.forge_port}")
        load = self._run(
            [
                "docker",
                "exec",
                "-i",
                self.t.forge_backend,
                "python",
                "-m",
                "app.sandbox.loader",
                "-",
                "--replace",
            ],
            stdin=path.read_bytes(),
        )
        out = (load.stdout + load.stderr).decode("utf-8", "replace").strip()
        if load.returncode:
            raise RuntimeError(f"the Forge's loader refused {path.name}: {out[-1500:]}")
        said = [x for x in out.splitlines() if x.startswith("world ")]
        return (said or out.splitlines() or ["loaded"])[-1]

    # -- the Office
    def _office_values(self) -> dict[str, str]:
        if self.t.office_env.is_file():
            values = read_env(self.t.office_env)
        else:
            pw = {k: secrets.token_hex(24) for k in ("pg", "owner", "app", "reader")}
            port = self.t.office_pg_port
            values = {
                "OFFICE_SANDBOX": "1",
                "OFFICE_SANDBOX_PROJECT": self.t.office_project,
                "OFFICE_SANDBOX_PG_PORT": str(port),
                "OFFICE_SANDBOX_PG_PASSWORD": pw["pg"],
                "OFFICE_OWNER_PASSWORD": pw["owner"],
                "OFFICE_APP_PASSWORD": pw["app"],
                "OFFICE_READER_PASSWORD": pw["reader"],
                "OFFICE_SANDBOX_SUPERUSER_DSN": f"postgresql://postgres:{pw['pg']}@127.0.0.1:{port}/office_sandbox",
                "OFFICE_ADMIN_DSN": f"postgresql://office_owner:{pw['owner']}@127.0.0.1:{port}/office_sandbox",
                "OFFICE_APP_DSN": f"postgresql://office_app:{pw['app']}@127.0.0.1:{port}/office_sandbox",
                "SANDBOX_CRE_FORGE_URL": self.t.forge_url,
            }
            write_env(
                self.t.office_env,
                values,
                "The sandbox Office's generated values (SimForge sandbox runner). Never printed.",
            )
        tag_digest = ollama_digest(PHI4)
        return {
            **values,
            # Always the targets' port, never a stored one: an office.env written before the
            # throwaway moved to 9213 still says 9212.
            "OFFICE_SANDBOX_PORT": str(self.t.office_port),
            "SANDBOX_AGENT_MODEL_TAG": PHI4,
            "SANDBOX_AGENT_MODEL_DIGEST": tag_digest,
            "SANDBOX_AGENT_MODEL_TEMPERATURE": "0.0",
            "SANDBOX_AGENT_MODEL_MAX_TOKENS": "4000",
        }

    def _broker(
        self, args: Sequence[str], env: Mapping[str, str], timeout: int = 900
    ) -> subprocess.CompletedProcess[bytes]:
        return self._run(
            [str(self.t.office_python), "-m", "broker.sandbox", *args],
            cwd=self.t.office_checkout,
            env=env,
            timeout=timeout,
        )

    def _simulation_dsn(self, values: Mapping[str, str]) -> str:
        if self.t.throwaway:
            # A stand-in for the live declaration (Greenstone, 22 September), as The Office's
            # own demo does with --simulation-standin. Never the live Office in a test.
            self._psql("DROP DATABASE IF EXISTS standin_declared WITH (FORCE)", "postgres")
            self._psql("CREATE DATABASE standin_declared", "postgres")
            self._psql(
                "CREATE TABLE venture_simulation (simulation_id uuid PRIMARY KEY, venture_id "
                "text NOT NULL, declared_at timestamptz NOT NULL, left_at timestamptz);"
                "INSERT INTO venture_simulation VALUES (gen_random_uuid(), 'greenstone', "
                "'2026-09-22', NULL);",
                "standin_declared",
            )
            return (
                f"postgresql://postgres:{values['OFFICE_SANDBOX_PG_PASSWORD']}@127.0.0.1:"
                f"{self.t.office_pg_port}/standin_declared"
            )
        dsn = read_env(self.t.live_office_env).get("OFFICE_READ_DSN", "")
        if not dsn:
            raise RuntimeError(
                f"no OFFICE_READ_DSN in {self.t.live_office_env}: the "
                "simulation check reads the live declaration there"
            )
        return dsn

    def office_up(self, run_dir: Path) -> Path:
        values = self._office_values()
        env = clean_env({**values, "SANDBOX_CRE_FORGE_TOKEN": self.forge_token()})
        if not self._running(self.t.office_db):
            up = self._run([*self._compose_office(), "up", "-d", "--wait"], timeout=600)
            if up.returncode:
                raise RuntimeError(
                    "the sandbox Office's Postgres did not come up: "
                    + up.stderr.decode("utf-8", "replace")[-1500:]
                )
            self.started_office_db = True
        self._psql("DROP DATABASE IF EXISTS office_sandbox WITH (FORCE)", "postgres")
        self._psql("CREATE DATABASE office_sandbox", "postgres")
        self.log("   a fresh office_sandbox database")
        done = self._broker(["migrate"], env)
        if done.returncode:
            raise RuntimeError(
                "the sandbox Office's migrate refused or failed (exit "
                f"{done.returncode}): " + _tail(done)
            )
        tokens = run_dir / "tokens.env"
        done = self._broker(
            ["setup", "--venture", VENTURE, "--secrets", str(tokens)],
            {**env, "OFFICE_SANDBOX_SIMULATION_DSN": self._simulation_dsn(values)},
        )
        if done.returncode:
            raise RuntimeError(
                f"the sandbox Office's setup refused (exit {done.returncode}): " + _tail(done)
            )
        summary = done.stdout.decode("utf-8", "replace")
        grants = json.loads(summary[summary.index("{") :]).get("grants", [])
        self.log("   set up Greenstone: " + "; ".join(grants))
        log_file = (run_dir / "office-broker.log").open("w", encoding="utf-8")
        self.broker = subprocess.Popen(  # noqa: S603
            [str(self.t.office_python), "-m", "broker.sandbox", "serve"],
            cwd=self.t.office_checkout,
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for _ in range(90):
            if http_ok(f"{self.t.broker_url}/api/live"):
                break
            if self.broker.poll() is not None:
                raise RuntimeError(
                    f"the sandbox Office exited (code {self.broker.returncode}); "
                    f"see {run_dir / 'office-broker.log'}"
                )
            time.sleep(1)
        else:
            raise RuntimeError(f"the sandbox Office is not live on {self.t.broker_url}")
        return tokens

    def office(self, method: str, path: str, token: str, body: Any = None) -> tuple[int, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(  # noqa: S310 - loopback only
            f"{self.t.broker_url}{path}",
            data=data,
            method=method,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                return exc.code, json.loads(raw or b"null")
            except ValueError:
                return exc.code, {"text": raw.decode("utf-8", "replace")[:500]}

    def snapshot(self, office_run_id: str) -> list[dict[str, Any]]:
        sql = office_sync.OFFICE_TASK_SQL.format(run_id=office_run_id.replace("'", ""))
        return [json.loads(line) for line in self._psql(sql).splitlines() if line.strip()]

    # -- the operator
    def operator_setup_args(self, run_dir: Path, tokens: Path) -> list[str]:
        """`sandbox_operator.py setup`, pointed at the broker this stack serves."""
        return [
            str(self.t.operator_python),
            "sandbox_operator.py",
            "setup",
            "--office-tokens",
            str(tokens),
            "--dir",
            str(run_dir / "operator"),
            "--broker-url",
            self.t.broker_url,
        ]

    def operator_run_args(self) -> list[str]:
        """`sandbox_operator.py run --once` on the config `setup` wrote."""
        assert self.operator_config is not None
        return [
            str(self.t.operator_python),
            "sandbox_operator.py",
            "run",
            "--once",
            "--config",
            str(self.operator_config),
        ]

    def operator_up(self, run_dir: Path, tokens: Path) -> None:
        done = self._run(
            self.operator_setup_args(run_dir, tokens),
            cwd=self.t.operator_checkout,
            env=clean_env(),
        )
        if done.returncode:
            raise RuntimeError(
                f"the sandbox operator's setup refused (exit {done.returncode}): " + _tail(done)
            )
        self.operator_config = run_dir / "operator" / "operator.env"

    def tick(self) -> list[str]:
        done = self._run(
            self.operator_run_args(),
            cwd=self.t.operator_checkout,
            env=clean_env(),
            timeout=1800,
        )
        lines = [
            x
            for x in (done.stdout + done.stderr).decode("utf-8", "replace").splitlines()
            if "[SANDBOX]" in x or "REFUSED" in x or "rror" in x
        ]
        if done.returncode:
            raise RuntimeError(
                f"the sandbox operator exited {done.returncode}: " + " | ".join(lines[-5:])
            )
        return [x.split(" ", 2)[-1] for x in lines]

    def stop(self) -> list[str]:
        said = []
        if self.broker is not None and self.broker.poll() is None:
            self.broker.terminate()
            try:
                self.broker.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.broker.kill()
            said.append(f"stopped the sandbox Office broker on {self.t.broker_url}")
        verb = ["down", "-v"] if self.t.throwaway else ["stop"]
        if self.t.throwaway or self.started_office_db:
            self._run([*self._compose_office(), *verb], timeout=300)
            said.append(f"{' '.join(verb)}: {self.t.office_project}")
        if self.t.throwaway or self.started_forge:
            self._run([*self._compose_forge(), *verb], timeout=300)
            said.append(f"{' '.join(verb)}: {self.t.forge_project}")
        elif not self.started_forge:
            said.append(f"left {self.t.forge_project} as it was found (up)")
        return said


def _tail(done: subprocess.CompletedProcess[bytes]) -> str:
    lines = [
        x for x in (done.stdout + done.stderr).decode("utf-8", "replace").splitlines() if x.strip()
    ]
    return " | ".join(lines[-8:])


# --- measuring the machine -----------------------------------------------------------------------


def free_gb() -> float:
    if sys.platform == "win32":

        class Status(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        s = Status()
        s.dwLength = ctypes.sizeof(Status)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))  # type: ignore[attr-defined]
        return s.ullAvailPhys / 2**30
    with open("/proc/meminfo", encoding="ascii") as f:
        info = dict(line.split(":", 1) for line in f)
    return int(info["MemAvailable"].split()[0]) / 2**20


def _ollama(path: str, body: Mapping[str, Any] | None = None) -> Any:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"{OLLAMA}{path}",
        data=data,  # noqa: S310 - loopback only
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
        return json.loads(r.read() or b"null")


def phi4_loaded() -> bool:
    try:
        return any(m.get("name") == PHI4 for m in _ollama("/api/ps").get("models") or [])
    except Exception:  # noqa: BLE001 - no Ollama means nothing loaded
        return False


def stop_phi4() -> None:
    """`ollama stop phi4`, through the API: unload it now."""
    _ollama("/api/generate", {"model": PHI4, "keep_alive": 0})


def ollama_digest(tag: str) -> str:
    for m in _ollama("/api/tags").get("models") or []:
        if m.get("name") == tag or m.get("model") == tag:
            # The live form, sha256:<hex>: what the Village sends and the Office compares.
            digest = str(m["digest"])
            return digest if digest.startswith("sha256:") else f"sha256:{digest}"
    raise RuntimeError(f"Ollama has no {tag}; the sandbox certifications name it")


def pid_alive(pid: int) -> bool:
    """Whether a process exists. Never `os.kill(pid, 0)`: on Windows that terminates it."""
    if sys.platform == "win32":
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # type: ignore[attr-defined]
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))  # type: ignore[attr-defined]
        ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


class Lock:
    """One run at a time on this machine."""

    def __init__(self, state: Path) -> None:
        self.path = state / "run.lock"

    def holder(self) -> str | None:
        if not self.path.is_file():
            return None
        try:
            held = json.loads(self.path.read_text(encoding="utf-8"))
        except ValueError:
            return "an unreadable lock file"
        if not pid_alive(int(held.get("pid", 0))):
            return None  # its process is gone: a stale lock
        return f"pid {held['pid']}, since {held.get('since')}"

    def take(self, what: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "since": datetime.now().isoformat(timespec="seconds"),
                    "what": what,
                }
            ),
            encoding="utf-8",
        )

    def release(self) -> None:
        with contextlib.suppress(FileNotFoundError):
            self.path.unlink()


# --- SimForge's side ----------------------------------------------------------------------------


async def exam_open(db: AsyncSession) -> bool:
    stmt = (
        select(func.count())
        .select_from(OperationRun)
        .where(
            OperationRun.endedAt.is_(None),
            OperationRun.verdict.is_(None),
            OperationRun.timedOutAt.is_(None),
        )
    )
    return bool((await db.execute(stmt)).scalar_one())


async def sandbox_tables_exist(db: AsyncSession) -> bool:
    try:
        await db.execute(text('SELECT 1 FROM "SandboxRun" WHERE 1 = 0'))
        await db.execute(text('SELECT 1 FROM "SandboxStep" WHERE 1 = 0'))
        return True
    except Exception:  # noqa: BLE001 - the migration is not applied
        await db.rollback()
        return False


async def next_seed(db: AsyncSession) -> int:
    top = (await db.execute(select(func.max(SandboxRun.seed)))).scalar_one()
    return 0 if top is None else int(top) + 1


async def scheduled_today(db: AsyncSession, now: datetime) -> list[datetime]:
    """Local start times of the scheduled runs that started on `now`'s local day."""
    rows = (
        await db.execute(select(SandboxRun.startedAt).where(SandboxRun.scheduleOwner.is_not(None)))
    ).scalars()
    out = []
    for started in rows:
        # The record stores naive UTC; the business day is the local one.
        local = started.replace(tzinfo=UTC).astimezone().replace(tzinfo=None)
        if local.date() == now.date():
            out.append(local)
    return out


def choose_tasks(seed: int) -> list[Task]:
    """The seed's tasks, one module at a time in turn, so a short run still sees all three."""
    tasks = generate_tasks(generate_world(seed))
    queues = {m: [t for t in tasks if t.module_id == m] for m in READ_MODULES}
    out: list[Task] = []
    while any(queues.values()):
        for m in READ_MODULES:
            if queues[m]:
                out.append(queues[m].pop(0))
    return out


def office_facts(task: Task) -> dict[str, Any]:
    """What the starter files: the Forge payload, and the person's words as `instruction`
    (B113: a read whose facts carry a person's words keeps Turn A, which the record grades)."""
    return {**task.request, "instruction": task.facts}


# --- one run -------------------------------------------------------------------------------------


@dataclass
class Budget:
    max_ticks: int
    max_minutes: float
    poll_seconds: float = 30.0
    #: Ticks in a row that record nothing before the run stops: an agent that cannot answer
    #: (a refused model, an operator error) spends no more of the budget.
    idle_ticks: int = 8
    idle_seconds: float = 5.0


@dataclass
class Outcome:
    run_ref: str | None = None
    office_run_id: str | None = None
    seed: int | None = None
    page: Path | None = None
    refused_at_filing: list[dict[str, str]] = field(default_factory=list)
    record_refusals: list[dict[str, str]] = field(default_factory=list)
    office_status: dict[str, str] = field(default_factory=dict)
    pauses: list[dict[str, str]] = field(default_factory=list)
    ticks: int = 0
    stopped_because: str = ""
    stopped: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {**self.__dict__, "page": str(self.page) if self.page else None}


@dataclass
class Clock:
    now: Callable[[], datetime] = datetime.now
    sleep: Callable[[float], None] = time.sleep
    monotonic: Callable[[], float] = time.monotonic


async def drive(
    db: AsyncSession,
    stack: Stack,
    *,
    starter: str,
    seed: int,
    tasks: Sequence[Task],
    want: int,
    run_dir: Path,
    budget: Budget,
    log: Callable[[str], None],
    schedule_owner: str | None = None,
    stop_requested: Callable[[], str | None] = lambda: None,
    clock: Clock | None = None,
) -> Outcome:
    """Steps 3 to 8: world, Office, operator, filing, the recorded loop, close and page.

    The caller has checked the start rules and holds the lock; it stops the stack after.
    """
    clock = clock or Clock()
    out = Outcome(seed=seed)
    world_file = run_dir / f"{world_name(seed)}.json"
    world_file.write_bytes(export_json(seed).encode("utf-8"))
    log(f"3. world {world_name(seed)} into the sandbox CRE Forge, --replace")
    log("   " + stack.load_world(seed, world_file))

    log("4. a fresh sandbox Office, set up for Greenstone")
    tokens_file = stack.office_up(run_dir)
    token = _person_token(tokens_file, starter)

    log("5. the sandbox operator")
    stack.operator_up(run_dir, tokens_file)

    log(f"6. {starter} starts the Office's run and files up to {want} tasks")
    purpose = (
        f"ADR-0166 stage 7: SimForge sandbox run on {world_name(seed)}, {want} tasks, "
        f"started by {starter}" + (f" on {schedule_owner}'s schedule" if schedule_owner else "")
    )
    status, body = stack.office(
        "POST", "/api/sandbox/runs", token, {"venture_id": VENTURE, "purpose": purpose}
    )
    if status >= 300:
        raise RuntimeError(f"the sandbox Office refused to start the run ({status}): {body}")
    office_run = str(body["sandbox_run_id"])
    out.office_run_id = office_run
    filed: list[Task] = []
    for task in tasks:
        if len(filed) == want:
            break
        status, body = stack.office(
            "POST",
            f"/api/sandbox/runs/{office_run}/tasks",
            token,
            {
                "module_id": task.module_id,
                "facts": office_facts(task),
                "record_subject": task.turn_b.record_subject,
            },
        )
        if status >= 300:
            # The Office answers a refusal as {"error", "message"} (OfficeError) or {"detail"}.
            why = (
                (body.get("message") or body.get("detail") or body)
                if isinstance(body, dict)
                else body
            )
            out.refused_at_filing.append(
                {"task": task.task_id, "status": str(status), "why": str(why)[:300]}
            )
            log(f"   {task.task_id} refused at filing ({status}): {str(why)[:160]}")
            continue
        filed.append(task)
    if not filed:
        raise RuntimeError("the sandbox Office refused every filing")
    log(f"   filed {len(filed)}; refused at filing {len(out.refused_at_filing)}")

    run = await record.open_run(
        db,
        venture=VENTURE,
        seed=seed,
        started_by=starter,
        task_ids=[t.task_id for t in filed],
        schedule_owner=schedule_owner,
        refused_at_filing=out.refused_at_filing,
    )
    out.run_ref = run.runRef
    log(f"7. SandboxRun {run.runRef}: ticking the operator, approving, recording")
    by_office: dict[str, str] = {}  # office task id -> SimForge task id, in filing order
    stuck: set[str] = set()
    approved: set[str] = set()
    started = clock.monotonic()
    paused_since: str | None = None

    async def sync() -> tuple[list[dict[str, Any]], int]:
        """Record every step the Office has written since; how many were new."""
        rows = stack.snapshot(office_run)
        new_steps = 0
        steps = (
            (
                await db.execute(
                    select(SandboxStep)
                    .where(SandboxStep.sandboxRunId == run.id)
                    .order_by(SandboxStep.seq)
                )
            )
            .scalars()
            .all()
        )
        done: dict[str, list[str]] = {}
        for s in steps:
            done.setdefault(s.taskId, []).append(s.step)
        for row in rows:
            # The Office numbers a run's filings 1, 2, ... in its source_ref, `<run>:<n>`.
            n = int(str(row["source_ref"]).rsplit(":", 1)[1])
            task_id = by_office.setdefault(row["task_id"], filed[n - 1].task_id)
            out.office_status[task_id] = office_sync.office_status(row)
            if task_id in stuck:
                continue
            for new in office_sync.steps_to_record(
                row, done.get(task_id, []), starter=starter, run_ref=office_run
            ):
                try:
                    await record.record_step(
                        db,
                        run,
                        task_id=task_id,
                        step=new.step,
                        at=new.at,
                        actor=new.actor,
                        payload=new.payload,
                        sandbox_ids=new.sandbox_ids,
                        agent_id=new.agent_id,
                    )
                    new_steps += 1
                except record.SandboxRefused as exc:
                    stuck.add(task_id)
                    out.record_refusals.append(
                        {"task": task_id, "step": new.step, "code": exc.code, "detail": str(exc)}
                    )
                    log(f"   {task_id}: the record refused {new.step} ({exc})")
                    break
        return rows, new_steps

    rows, _ = await sync()
    idle = 0
    while True:
        if all(r["status"] in TERMINAL for r in rows):
            out.stopped_because = "every task finished"
            break
        why = stop_requested()
        if why:
            out.stopped_because = f"stopped: {why}"
            break
        if idle >= budget.idle_ticks:
            out.stopped_because = f"no step recorded in {idle} ticks in a row"
            break
        if out.ticks >= budget.max_ticks:
            out.stopped_because = f"tick budget spent ({budget.max_ticks})"
            break
        if (clock.monotonic() - started) / 60 > budget.max_minutes:
            out.stopped_because = f"wall-clock budget spent ({budget.max_minutes:g} min)"
            break
        reason = rules.pause_reason(now=clock.now(), exam_open=await exam_open(db))
        if reason:
            if paused_since is None:
                paused_since = clock.now().isoformat(timespec="seconds")
                out.pauses.append({"at": paused_since, "why": reason})
                log(f"   paused: {reason}")
            clock.sleep(budget.poll_seconds)
            continue
        if paused_since is not None:
            out.pauses[-1]["resumed"] = clock.now().isoformat(timespec="seconds")
            log("   resumed")
            paused_since = None
        out.ticks += 1
        for line in stack.tick():
            log(f"   tick {out.ticks}: {line}")
        for row in stack.snapshot(office_run):
            pid = row.get("proposal_id")
            if pid and row.get("proposal_status") == "pending" and pid not in approved:
                status, body = stack.office("POST", f"/api/sandbox/proposals/{pid}/approve", token)
                approved.add(pid)
                log(f"   asked sandbox-approver to approve {pid[:8]} -> {status}")
        rows, new_steps = await sync()
        idle = 0 if new_steps else idle + 1
        if idle:
            clock.sleep(budget.idle_seconds)

    log(f"8. {out.stopped_because}; finishing and closing")
    stack.office("POST", f"/api/sandbox/runs/{office_run}/finish", token)
    run = await record.close_run(db, run)
    loaded, steps = await load_run(db, run.runRef)
    page = run_dir / f"sandbox-run-{run.runRef}.html"
    page.write_bytes(render_run_page(loaded, steps).encode("utf-8"))
    out.page = page
    log(f"   page: {page}")
    return out


def _person_token(tokens_file: Path, starter: str) -> str:
    key = f"PERSON_{starter.split()[0].upper()}"
    token = read_env(tokens_file).get(key, "")
    if not token:
        raise RuntimeError(f"the sandbox Office's setup wrote no {key}")
    return token


def by_module(tasks: Iterable[Task]) -> dict[str, int]:
    out: dict[str, int] = {}
    for t in tasks:
        out[t.module_id] = out.get(t.module_id, 0) + 1
    return out
