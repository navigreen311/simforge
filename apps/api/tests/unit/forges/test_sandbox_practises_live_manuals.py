"""The sandbox practises on the live Office's manuals, or it does not run (runner step 4).

Ivan Green, 19 November 2026: "the sandbox must practise on the same manuals as live." SimForge
#286 found the daily run filing against theoffice f8d8c73 (manuals 1.11.12) while the live Office
ran 1.11.13, so property_lookup was practised on a manual nobody runs, and nothing said so.

After its setup, the sandbox Office's manuals are read back from its own database and compared
with the manuals in force in the live Office, read through OFFICE_READ_DSN in a read-only
transaction. A difference refuses the run before anything is filed, naming each module and both
hashes. A throwaway never reads the live Office and says it did not compare.

Both reads name only The Office's `forge_operating_instruction` columns; `PINNED` is that table
as The Office's migration 0007 creates it (theoffice main 7c81041), checked against the Office
checkout beside this one when there is one. SimForge's CI has neither, so nothing here skips.
"""

from __future__ import annotations

import os
import re
import sys
import types
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.sandbox_run import SandboxRun
from src.services.sandbox import runner
from tests.unit.forges.test_sandbox_runner import MANUALS, FakeStack, _drive

#: The Office's `forge_operating_instruction` as its migration 0007 creates it, the columns
#: verbatim (theoffice main 7c810410c61b3705f48cdce49520d38ca24889ca; no later migration alters
#: them).
PINNED = """
          forge_id             TEXT NOT NULL,
          module_id            TEXT NOT NULL,
          instruction_version  TEXT NOT NULL,
          forge_api_version    TEXT NOT NULL,
          content              JSONB NOT NULL,
          content_hash         TEXT NOT NULL,
          superseded_at        TIMESTAMPTZ,
"""
OLD_PL = ("1.11.12", "3b8a71b65b0e" + "1" * 52)


def _columns(sql: str) -> set[str]:
    words = set(re.findall(r"\b[a-z_]+\b", sql))
    keywords = {"select", "from", "where", "and", "any", "is", "null", "order", "by", "text"}
    return {w for w in words if w.lower() not in keywords} - {"forge_operating_instruction"}


async def test_a_run_on_the_live_manuals_files_and_names_them(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    said: list[str] = []
    stack = FakeStack()
    out = await _drive(db_session, stack, tmp_path, log=said.append)
    assert out.stopped_because == "every task finished"
    assert out.manuals["property_lookup"] == {
        "sandbox": "1.11.13 " + MANUALS["property_lookup"][1],
        "live": "1.11.13 " + MANUALS["property_lookup"][1],
    }
    assert any(x.startswith("   the same manuals as the live Office:") for x in said)


async def test_a_run_on_other_manuals_refuses_before_filing(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    stack = FakeStack(manuals={**MANUALS, "property_lookup": OLD_PL})
    with pytest.raises(runner.ManualsDiffer) as refused:
        await _drive(db_session, stack, tmp_path)
    message = str(refused.value)
    assert "property_lookup: the sandbox's 1.11.12 3b8a71b65b0e" in message
    assert "the live Office's 1.11.13 cc62a653e456" in message
    assert "comp_analysis" not in message and "buyer_match" not in message
    assert "SANDBOX_OFFICE_CHECKOUT" in message
    # Nothing filed, nothing started in the Office, no SandboxRun opened.
    assert stack.calls == [] and stack.tasks == {}
    assert (await db_session.execute(select(func.count()).select_from(SandboxRun))).scalar() == 0
    # The summary still names both sides.
    assert refused.value.outcome.manuals["property_lookup"]["sandbox"].startswith("1.11.12 ")


async def test_the_same_manual_under_another_version_is_the_same_manual(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    """The hash is made from the content; a version string alone moves nothing."""
    renamed = {m: ("1.11.12", h) for m, (_v, h) in MANUALS.items()}
    out = await _drive(db_session, FakeStack(manuals=renamed), tmp_path)
    assert out.stopped_because == "every task finished"


@pytest.mark.parametrize(
    ("sandbox", "live", "said"),
    [
        (
            {k: v for k, v in MANUALS.items() if k != "buyer_match"},
            MANUALS,
            "buyer_match: the sandbox Office set up no manual",
        ),
        (
            MANUALS,
            {k: v for k, v in MANUALS.items() if k != "comp_analysis"},
            "comp_analysis: the live Office has no manual in force",
        ),
        ({**MANUALS, "comp_analysis": ("1.11.13", "")}, MANUALS, "comp_analysis: the sandbox's"),
    ],
)
def test_a_manual_missing_on_either_side_differs(
    sandbox: dict[str, tuple[str, str]], live: dict[str, tuple[str, str]], said: str
) -> None:
    found = runner.manuals_differ(sandbox, live)
    assert len(found) == 1 and found[0].startswith(said)


def test_the_same_manuals_do_not_differ() -> None:
    assert runner.manuals_differ(MANUALS, dict(MANUALS)) == []
    # A module outside the three the sandbox practises is not compared.
    assert runner.manuals_differ({**MANUALS, "underwrite_deal": ("1", "x")}, MANUALS) == []


async def test_a_throwaway_does_not_compare_and_says_so(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    said: list[str] = []
    out = await _drive(db_session, FakeStack(live_manuals=None), tmp_path, log=said.append)
    assert out.stopped_because == "every task finished"
    assert {v["live"] for v in out.manuals.values()} == {"not compared"}
    assert "   manuals not compared with the live Office's: a throwaway never reads it" in said


def _targets(tmp_path: Path, *, throwaway: bool, live_env: Path) -> runner.Targets:
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
    config["SANDBOX_LIVE_OFFICE_ENV"] = str(live_env)
    return runner.Targets.from_config(config, throwaway=throwaway, state=tmp_path / "state")


class _Conn:
    def __init__(self, seen: dict[str, Any]) -> None:
        self.seen = seen

    def transaction(self, **kw: Any) -> Any:
        self.seen["transaction"] = kw
        seen = self.seen

        class _Tx:
            async def __aenter__(self) -> None:
                seen["in_tx"] = True

            async def __aexit__(self, *_a: Any) -> None:
                seen["in_tx"] = False

        return _Tx()

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, str]]:
        assert self.seen.get("in_tx"), "read outside the read-only transaction"
        self.seen["fetch"] = (sql, args)
        return [
            {"module_id": m, "instruction_version": v, "content_hash": h}
            for m, (v, h) in MANUALS.items()
        ]

    async def close(self) -> None:
        self.seen["closed"] = True


async def test_the_live_read_is_read_only_and_uses_the_read_dsn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    live_env = tmp_path / "live.env"
    runner.write_env(
        live_env, {"OFFICE_READ_DSN": "postgresql://reader:x@127.0.0.1:5432/theoffice"}, "test"
    )
    seen: dict[str, Any] = {}

    async def connect(dsn: str, **_kw: Any) -> _Conn:
        seen["dsn"] = dsn
        return _Conn(seen)

    monkeypatch.setitem(sys.modules, "asyncpg", types.SimpleNamespace(connect=connect))
    stack = runner.ProcessStack(_targets(tmp_path, throwaway=False, live_env=live_env), print)
    assert await stack.live_manuals() == MANUALS
    assert seen["dsn"].startswith("postgresql://reader:")
    assert seen["transaction"] == {"readonly": True} and seen["closed"]
    sql, args = seen["fetch"]
    assert sql == runner.LIVE_MANUALS_SQL
    assert args == ("cre-forge", ["property_lookup", "comp_analysis", "buyer_match"])


async def test_a_throwaway_never_reads_the_live_office(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def connect(*_a: Any, **_kw: Any) -> None:
        raise AssertionError("a throwaway read the live Office")

    monkeypatch.setitem(sys.modules, "asyncpg", types.SimpleNamespace(connect=connect))
    t = _targets(tmp_path, throwaway=True, live_env=tmp_path / "absent.env")
    assert await runner.ProcessStack(t, print).live_manuals() is None


def test_no_read_dsn_is_a_refusal_that_says_where_it_looked(tmp_path: Path) -> None:
    t = _targets(tmp_path, throwaway=False, live_env=tmp_path / "absent.env")
    with pytest.raises(RuntimeError, match="no OFFICE_READ_DSN in .*absent.env: the manuals"):
        runner.ProcessStack(t, print)._live_read_dsn("the manuals check reads it there")


def test_the_sandbox_read_parses_psqls_lines() -> None:
    out = "".join(f"{m}|{v}|{h}\n" for m, (v, h) in sorted(MANUALS.items()))
    assert runner.manuals_from_psql(out + "\n") == MANUALS


def test_both_reads_name_only_the_offices_columns() -> None:
    pinned = set(re.findall(r"^\s+([a-z_]+)\s+[A-Z]", PINNED, flags=re.M))
    for sql in (runner.LIVE_MANUALS_SQL, runner.SANDBOX_MANUALS_SQL):
        assert _columns(sql) - {"cre", "forge"} <= pinned, sql
        assert "FROM forge_operating_instruction" in sql
        assert "superseded_at IS NULL" in sql  # the manual in force, never a superseded one
    office = (
        Path(os.environ.get("THEOFFICE_CHECKOUT") or Path.home() / "Projects" / "theoffice")
        / "db"
        / "versions"
        / "0007_instructions_certification.py"
    )
    if office.is_file():  # the machine the runner runs on: the table as it is there
        text = office.read_text(encoding="utf-8")
        for line in PINNED.strip("\n").splitlines():
            assert line.strip() in text, line
