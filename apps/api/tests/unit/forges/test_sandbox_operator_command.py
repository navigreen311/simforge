"""The runner's operator commands fit the operator's command line (village-os).

The first real run (10 November) stopped at stage 5: `setup` requires `--broker-url` since
village-os #25 (a3d0879), and the runner did not pass it. These tests build the commands the
real `ProcessStack` runs and check them against the operator's usage: a copy pinned here, and,
when `SANDBOX_OPERATOR_CHECKOUT` and `SANDBOX_OPERATOR_PYTHON` are set, the checkout's own.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from src.services.sandbox import runner

#: `sandbox_operator.py <command> --help` at village-os a3d0879 (#25), the usage lines only.
PINNED_USAGE = {
    "setup": "usage: sandbox_operator.py setup [-h] --office-tokens OFFICE_TOKENS --dir DIR\n"
    "                                 --broker-url\n"
    "                                 {http://127.0.0.1:9212,http://127.0.0.1:9213}\n",
    "run": "usage: sandbox_operator.py run [-h] --config CONFIG [--once]\n",
}

_OPTION = re.compile(r"(\[)?(--[\w-]+)(?:\s+(\{[^}]*\}|[A-Z_]+))?\]?")


@dataclass(frozen=True)
class Option:
    required: bool
    takes_value: bool
    choices: tuple[str, ...] | None


def parse_usage(text: str) -> dict[str, Option]:
    """The options in an argparse usage block: which are required, take a value, or choose."""
    usage = []
    for line in text.splitlines():
        if usage and not line.startswith(" "):
            break
        if line.startswith("usage:") or usage:
            usage.append(line.strip())
    out = {}
    for m in _OPTION.finditer(" ".join(usage)):
        bracket, name, value = m.groups()
        choices = tuple(value[1:-1].split(",")) if value and value.startswith("{") else None
        out[name] = Option(required=bracket is None, takes_value=bool(value), choices=choices)
    return out


def mismatches(command: list[str], usage: dict[str, Option]) -> list[str]:
    """Every way `command` (the args after the subcommand) would fail the operator's argparse."""
    found = []
    given: dict[str, str | None] = {}
    i = 0
    while i < len(command):
        name = command[i]
        if name not in usage:
            found.append(f"{name} is not an operator option")
            i += 1
            continue
        if usage[name].takes_value:
            given[name] = command[i + 1] if i + 1 < len(command) else None
            i += 2
        else:
            given[name] = None
            i += 1
    for name, opt in usage.items():
        if opt.required and name not in given:
            found.append(f"{name} is required and not passed")
        if opt.choices and name in given and given[name] not in opt.choices:
            found.append(f"{name} {given[name]} is not one of {', '.join(opt.choices)}")
    return found


def targets(tmp_path: Path, *, throwaway: bool) -> runner.Targets:
    config = {
        k: str(tmp_path / k.lower())
        for k in (
            "SANDBOX_FORGE_CHECKOUT",
            "SANDBOX_OFFICE_CHECKOUT",
            "SANDBOX_OFFICE_PYTHON",
            "SANDBOX_OPERATOR_CHECKOUT",
            "SANDBOX_OPERATOR_PYTHON",
        )
    }
    return runner.Targets.from_config(config, throwaway=throwaway, state=tmp_path / "state")


class Recorded(runner.ProcessStack):
    """The real stack with its subprocess calls recorded and answered `ok`."""

    def __init__(self, t: runner.Targets) -> None:
        super().__init__(t, log=lambda _m: None)
        self.calls: list[list[str]] = []

    def _run(self, args: Any, **_kw: Any) -> subprocess.CompletedProcess[bytes]:
        self.calls.append(list(args))
        return subprocess.CompletedProcess(list(args), 0, b"", b"")


def operator_commands(stack: Recorded, tmp_path: Path) -> dict[str, list[str]]:
    """What stage 5 and one tick of stage 7 run, as {subcommand: args after it}."""
    stack.operator_up(tmp_path / "run", tmp_path / "run" / "tokens.env")
    stack.tick()
    out = {}
    for call in stack.calls:
        assert call[1] == "sandbox_operator.py"
        out[call[2]] = call[3:]
    return out


def test_the_real_stacks_operator_setup_names_the_runners_broker(tmp_path: Path) -> None:
    stack = Recorded(targets(tmp_path, throwaway=False))
    setup = operator_commands(stack, tmp_path)["setup"]
    assert setup[setup.index("--broker-url") + 1] == "http://127.0.0.1:9212"


def test_a_throwaway_stacks_operator_setup_names_the_throwaway_broker(tmp_path: Path) -> None:
    stack = Recorded(targets(tmp_path, throwaway=True))
    setup = operator_commands(stack, tmp_path)["setup"]
    assert setup[setup.index("--broker-url") + 1] == "http://127.0.0.1:9213"


@pytest.mark.parametrize("throwaway", [False, True])
def test_the_broker_and_the_operator_share_one_port(tmp_path: Path, throwaway: bool) -> None:
    """The port the broker is served on, checked free, and talked to is the operator's."""
    t = targets(tmp_path, throwaway=throwaway)
    t.state.mkdir(parents=True)
    # An office.env from before the throwaway moved to 9213 must not win.
    runner.write_env(t.office_env, {"OFFICE_SANDBOX_PORT": "9212"}, "old")
    stack = Recorded(t)
    original = runner.ollama_digest
    runner.ollama_digest = lambda _tag: "sha256:" + "0" * 64  # type: ignore[assignment]
    try:
        served = stack._office_values()["OFFICE_SANDBOX_PORT"]
    finally:
        runner.ollama_digest = original  # type: ignore[assignment]
    setup = operator_commands(stack, tmp_path)["setup"]
    assert setup[setup.index("--broker-url") + 1] == f"http://127.0.0.1:{served}"
    assert int(served) == t.office_port
    assert t.office_port in t.ports()


@pytest.mark.parametrize("throwaway", [False, True])
def test_every_operator_command_fits_the_pinned_usage(tmp_path: Path, throwaway: bool) -> None:
    built = operator_commands(Recorded(targets(tmp_path, throwaway=throwaway)), tmp_path)
    assert set(built) == set(PINNED_USAGE)
    for command, args in built.items():
        assert mismatches(args, parse_usage(PINNED_USAGE[command])) == [], command


def test_the_usage_check_catches_the_10_november_failure() -> None:
    old_setup = ["--office-tokens", "t.env", "--dir", "d"]
    assert mismatches(old_setup, parse_usage(PINNED_USAGE["setup"])) == [
        "--broker-url is required and not passed"
    ]
    wrong = [*old_setup, "--broker-url", "http://127.0.0.1:9200"]
    assert mismatches(wrong, parse_usage(PINNED_USAGE["setup"]))


@pytest.mark.skipif(
    not (os.environ.get("SANDBOX_OPERATOR_CHECKOUT") and os.environ.get("SANDBOX_OPERATOR_PYTHON")),
    reason="set SANDBOX_OPERATOR_CHECKOUT and SANDBOX_OPERATOR_PYTHON to check a real checkout",
)
@pytest.mark.parametrize("throwaway", [False, True])
def test_every_operator_command_fits_the_checkouts_usage(tmp_path: Path, throwaway: bool) -> None:
    checkout = Path(os.environ["SANDBOX_OPERATOR_CHECKOUT"])
    python = os.environ["SANDBOX_OPERATOR_PYTHON"]
    built = operator_commands(Recorded(targets(tmp_path, throwaway=throwaway)), tmp_path)
    for command, args in built.items():
        done = subprocess.run(
            [python, "sandbox_operator.py", command, "--help"],
            cwd=checkout,
            capture_output=True,
            text=True,
            check=True,
            env=runner.clean_env(),
        )
        assert mismatches(args, parse_usage(done.stdout)) == [], command
