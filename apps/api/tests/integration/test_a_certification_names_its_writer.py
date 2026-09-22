"""ADR-0104 — a certification records the process that wrote it, and a restart preserves evidence.

**Measured, and that is why these rulings exist.** The six certifications of 19 September 2026 name
no process, no commit and no host. When the question came — which process wrote them — nothing on
the row could answer it. `forgeApiVersion` is a declared string, `agentModelIdentity` describes the
*examinee*, and no column named the writer. The attribution closed unattributed.

And the restart of 21 September truncated `simforge-api-8110.log` with
`Start-Process -RedirectStandardOutput`, destroying the prior launch's entire record while that
same question was being asked — then captured PID and command line for the processes it killed, and
not their `CreationDate`.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.build_info import PROCESS_IDENTITY, process_identity
from src.models.operation_cert import OperationCertification
from src.services.operation.battery import BatterySkipped, submit_battery_result
from tests.integration.test_operation_battery_run import (
    AGENT,
    _examiner_pinned,  # noqa: F401  - autouse fixture
    _runtime,
    _seed,
)
from tests.unit.test_operation_battery import ScriptedProvider, _compliant

REPO = Path(__file__).resolve().parents[4]
RESTART_SCRIPT = REPO / "scripts" / "restart-api.ps1"

_FIELDS = {"started_commit", "pid", "host", "process_started_at", "process_start_source"}


# =================================================================================================
# Ruling 1 - a certification records the process that wrote it
# =================================================================================================


def test_the_identity_carries_the_four_facts_the_attribution_needed() -> None:
    identity = process_identity()

    assert set(identity) == _FIELDS
    assert isinstance(identity["pid"], int) and identity["pid"] > 0
    assert identity["host"]
    assert identity["started_commit"]


def test_the_start_time_says_where_it_came_from() -> None:
    """**`kernel` and `import` are not the same measurement.** Import time is later than creation
    by however long the interpreter took to start, and a reader comparing a log line against a
    process must know which of the two they hold. Reporting both under one name would be this
    ADR's own defect, one layer down."""
    identity = process_identity()

    assert identity["process_start_source"] in {"kernel", "import"}
    started = datetime.fromisoformat(str(identity["process_started_at"]))
    now = datetime.now(tz=UTC)
    assert started <= now, "a process cannot have started after the moment it is asked"
    assert started > now - timedelta(days=30), "and not a month ago either"


def test_each_call_returns_its_own_dict() -> None:
    """A column default returning one shared dict would hang a single mutable object off every
    certification in the session."""
    first, second = process_identity(), process_identity()

    assert first == second
    assert first is not second
    assert first is not PROCESS_IDENTITY


async def test_a_certification_written_by_the_battery_names_its_writer(
    db_session: AsyncSession,
) -> None:
    """Through `submit_battery_result`, which is the path that wrote the six unattributed rows."""
    await _seed(db_session, run_ref="op-run-0104")

    result = await submit_battery_result(
        db_session, "op-run-0104", runtime=_runtime(ScriptedProvider(_compliant))
    )
    assert not isinstance(result, BatterySkipped)

    cert = (
        (
            await db_session.execute(
                select(OperationCertification).where(OperationCertification.agentId == AGENT)
            )
        )
        .scalars()
        .one()
    )
    assert cert.writtenBy is not None
    assert set(cert.writtenBy) == _FIELDS
    assert cert.writtenBy["pid"] == process_identity()["pid"]


def test_it_is_a_column_default_so_a_write_site_cannot_forget() -> None:
    """**Three write sites today, and the next one will not remember.** A keyword argument at each
    one is a rule enforced by whoever is reading; a default cannot be omitted."""
    column = OperationCertification.__table__.c.writtenBy

    assert column.default is not None
    assert column.default.is_callable, "a fresh value per row, not one frozen at class definition"
    # SQLAlchemy adapts a zero-argument callable, so the identity check is on what it PRODUCES.
    assert set(column.default.arg(None)) == _FIELDS
    assert column.nullable, "rows written before this existed carry NULL, never a backfilled guess"


# =================================================================================================
# Rulings 2 and 3 - a restart preserves logs and records both CreationDates
# =================================================================================================


def test_the_restart_script_exists_and_is_ascii() -> None:
    """ASCII because a `.ps1` with a BOM or a stray dash fails to parse on Windows PowerShell,
    and a restart script that will not run is the same as no restart script."""
    assert RESTART_SCRIPT.exists()
    raw = RESTART_SCRIPT.read_bytes()

    assert not raw.startswith(b"\xef\xbb\xbf"), "a BOM breaks .ps1 parsing"
    assert all(byte < 128 for byte in raw)


def test_the_restart_rotates_the_logs_and_never_truncates() -> None:
    """`Start-Process -RedirectStandardOutput` TRUNCATES. The script may still use it — it is the
    only way to redirect a detached process — but only after the existing file has been moved
    aside, so the bytes survive under another name."""
    text = RESTART_SCRIPT.read_text(encoding="ascii")

    # COMMENTS STRIPPED FIRST. The header explains the defect by naming the cmdlet, and an
    # ordering check that reads prose would pass or fail on where the explanation sits.
    code = "|".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )

    assert "Move-Item" in code, "rotation is a rename, so a partial rotation leaves the file whole"
    rotate_at = code.index("Move-Item")
    redirect_at = code.index("-RedirectStandardOutput")
    assert rotate_at < redirect_at, "the rotation must happen BEFORE anything can truncate"

    # AND AFTER THE STOP, which the first version of this script got wrong: the child holds both
    # log files open, so `Move-Item` on a live process fails with "being used by another process"
    # and the restart dies half done. Stopping first is still safe - the only thing that truncates
    # is `Start-Process`, and that is downstream of the rename either way.
    assert code.index("Stop-Process") < rotate_at

    # A rotation that cannot complete must not be followed by a start. Truncating a log to keep
    # the service up is the trade this whole script refuses.
    assert "throw" in code

    # `>` and `Out-File` without -Append are the other two ways to destroy a log here.
    assert not re.search(r"Out-File(?![^|]*-Append)", code)


def test_the_restart_records_creation_date_for_both_launcher_and_child() -> None:
    """**The field the 21 September restart did not capture.** And both halves, because
    `.venv\\Scripts\\python.exe` is a launcher that spawns the base interpreter — one uvicorn
    launch is always two processes, and reading that pair as two launches cost an investigation."""
    text = RESTART_SCRIPT.read_text(encoding="ascii")

    assert "CreationDate" in text
    assert "'launcher'" in text and "'child'" in text
    # Recorded BEFORE the kill: after it there is nothing left to ask.
    assert text.index("CreationDate") < text.index("Stop-Process")


def test_the_restart_ledger_is_appended_not_rotated() -> None:
    """One line per restart, in a file nothing rotates. It is what survives after the logs have
    rolled and the processes are gone — which is the state the 19 September question arrived in."""
    text = RESTART_SCRIPT.read_text(encoding="ascii")

    assert "restarts.jsonl" in text
    assert "AppendAllText" in text, "append, and without the BOM Add-Content would write"
    for field in ("stopped", "started", "checkout_commit", "restarted_at"):
        assert f"{field} " in text or f"{field}=" in text or f'"{field}"' in text


def test_the_ledger_record_is_json_one_line_per_restart() -> None:
    """Compressed JSON, one line, so the file stays greppable as it grows."""
    text = RESTART_SCRIPT.read_text(encoding="ascii")

    assert "ConvertTo-Json" in text and "-Compress" in text
    assert json.dumps  # the reader on the other end is an ordinary JSONL reader
