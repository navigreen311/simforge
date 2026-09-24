"""Gate 9.5 over the bridge: The Office learns whether, never why (ADR-0111).

The shape is `docs/contracts/gate-9-5-verdict.md`. These tests hold three
claims against the real endpoint, not against the service:

1. Nothing about the partition leaves. Planted strings stay home.
2. The key set never varies, so the shape itself says nothing.
3. The answer is the rows now, not a report cached from before.
"""

from __future__ import annotations

import ast
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db import get_session
from src.main import create_app
from src.models.base import _new_id
from src.models.held_out_partition import (
    HeldOutPartition,
    HeldOutPartitionScenario,
    HeldOutPartitionVerdict,
)
from src.services.operation.partition_verdict import venture_verdict
from tests.integration.scheduler_path import fresh_session

TOKEN = "office-tenant-token-for-tests"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
KEYS = {"venture_id", "partition_exists", "verdict", "decided_at"}
URL = "/office/gate_9_5_verdict"

# Planted. None of these may appear in any response body.
SECRET_SITUATION = "A SECRET SITUATION NOBODY MAY READ"
SECRET_MODULE = "secret_module_zq7"
SECRET_CLASS = "silent_failure"
SECRET_SCENARIO_ID = "scn-secret-0x5eed"
SECRET_SCENARIO_DIGEST = "sha256:scenario-digest-nobody-may-read"
SECRET_PARTITION_DIGEST = "sha256:partition-digest-nobody-may-read"
SECRET_PARTITION_ID = "part-secret-0xbeef"
SECRET_FORGE = "forge-secret-qq"
SECRET_AGENT = "agent-secret-kk"
SECRET_AUTHOR = "author-secret-ivan"

T0 = datetime(2026, 9, 23, 12, 0, 0)


@pytest_asyncio.fixture
async def bridged(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[AsyncClient, None]:
    monkeypatch.setattr(settings, "office_tenant_token", TOKEN)
    app = create_app()

    async def _override() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def _partition(
    venture: str,
    *,
    status: str = "sealed",
    digest: str | None = "sha256:p",
    pid: str | None = None,
    sealed_at: datetime | None = T0,
) -> HeldOutPartition:
    row = HeldOutPartition(
        ventureId=venture,
        forgeId="forge-a",
        status=status,
        authoredBy="ivan",
        contentDigest=digest,
        sealedAt=sealed_at if status != "authoring" else None,
        sealedBy="Grace Hopper" if status != "authoring" else None,
    )
    # Set now, not at flush, so a verdict can name it in the same batch.
    row.id = pid or _new_id()
    return row


def _verdict(
    p: HeldOutPartition,
    agent: str,
    verdict: str,
    *,
    at: datetime = T0,
    digest: str | None = None,
) -> HeldOutPartitionVerdict:
    return HeldOutPartitionVerdict(
        partitionId=p.id,
        ventureId=p.ventureId,
        agentId=agent,
        verdict=verdict,
        partitionDigest=digest if digest is not None else p.contentDigest,
        decidedAt=at,
    )


async def _add(session: AsyncSession, *rows: object) -> None:
    for row in rows:
        session.add(row)
        await session.flush()
    await session.commit()


async def _ask(client: AsyncClient, venture: str) -> dict:
    res = await client.post(URL, json={"venture_id": venture}, headers=AUTH)
    assert res.status_code == 200, res.text
    return res.json()


# --- 1. whether, never why ------------------------------------------------------------------


async def test_nothing_about_the_partition_leaves(
    bridged: AsyncClient, db_session: AsyncSession
) -> None:
    """ADR-0050's care, applied to Gate 9.5. Plant everything; find none of it."""
    p = _partition("v-secret", digest=SECRET_PARTITION_DIGEST, pid=SECRET_PARTITION_ID)
    p.forgeId = SECRET_FORGE
    p.authoredBy = SECRET_AUTHOR
    await _add(db_session, p)
    scenario = HeldOutPartitionScenario(
        partitionId=p.id,
        moduleId=SECRET_MODULE,
        scenarioClass=SECRET_CLASS,
        body={"scenario_id": SECRET_SCENARIO_ID, "situation": SECRET_SITUATION},
        digest=SECRET_SCENARIO_DIGEST,
    )
    scenario.id = SECRET_SCENARIO_ID
    await _add(db_session, scenario, _verdict(p, SECRET_AGENT, "FAIL"))

    res = await bridged.post(URL, json={"venture_id": "v-secret"}, headers=AUTH)
    assert res.status_code == 200
    raw = res.text

    for planted in (
        SECRET_SITUATION,
        "SECRET",
        SECRET_MODULE,
        SECRET_CLASS,
        SECRET_SCENARIO_ID,
        SECRET_SCENARIO_DIGEST,
        SECRET_PARTITION_DIGEST,
        SECRET_PARTITION_ID,
        SECRET_FORGE,
        SECRET_AGENT,
        SECRET_AUTHOR,
    ):
        assert planted not in raw, f"{planted!r} leaked"
    # Headers carry nothing either, bar the request id.
    assert SECRET_PARTITION_ID not in str(res.headers)

    assert '"FAIL"' in raw, "positive control: the verdict IS published"
    assert set(res.json()) == KEYS


async def test_no_key_names_a_forbidden_fragment(bridged: AsyncClient) -> None:
    body = await _ask(bridged, "v-none")
    for key in body:
        for fragment in ("held_out", "heldout", "prompt", "scenarios"):
            assert fragment not in key.lower()


# --- 2. the shape never varies --------------------------------------------------------------


async def test_the_key_set_is_the_same_in_every_state(
    bridged: AsyncClient, db_session: AsyncSession
) -> None:
    authoring = _partition("v-authoring", status="authoring", digest=None)
    ungraded = _partition("v-ungraded")
    passed = _partition("v-pass")
    failed = _partition("v-fail")
    timed = _partition("v-timeout")
    stale = _partition("v-stale")
    await _add(db_session, authoring, ungraded, passed, failed, timed, stale)
    await _add(
        db_session,
        _verdict(passed, "a1", "PASS"),
        _verdict(failed, "a1", "FAIL"),
        _verdict(timed, "a1", "TIMEOUT"),
        _verdict(stale, "a1", "FAIL", digest="sha256:an-older-seal"),
    )

    expected = {
        "v-unknown": (False, None),
        "v-authoring": (False, None),
        "v-ungraded": (True, "NOT_RUN"),
        "v-pass": (True, "PASS"),
        "v-fail": (True, "FAIL"),
        "v-timeout": (True, "TIMEOUT"),
        # A verdict on another seal describes another partition.
        "v-stale": (True, "NOT_RUN"),
    }
    for venture, (exists, verdict) in expected.items():
        body = await _ask(bridged, venture)
        assert set(body) == KEYS, venture
        assert list(body) == [
            "venture_id",
            "partition_exists",
            "verdict",
            "decided_at",
        ]
        assert body["venture_id"] == venture
        assert body["partition_exists"] is exists, venture
        assert body["verdict"] == verdict, venture
        if verdict in (None, "NOT_RUN"):
            assert body["decided_at"] is None, venture
        else:
            assert body["decided_at"] == "2026-09-23T12:00:00+00:00"


async def test_an_unknown_venture_reads_as_an_absent_partition(
    bridged: AsyncClient, db_session: AsyncSession
) -> None:
    """Otherwise the call is an oracle for which ventures exist."""
    retired = _partition("v-retired", status="retired")
    await _add(db_session, retired, _verdict(retired, "a1", "PASS"))

    unknown = await _ask(bridged, "v-never-heard-of")
    absent = await _ask(bridged, "v-retired")
    unknown.pop("venture_id")
    absent.pop("venture_id")
    assert (
        unknown
        == absent
        == {
            "partition_exists": False,
            "verdict": None,
            "decided_at": None,
        }
    )


async def test_weakest_agent_wins_at_its_latest_verdict(
    bridged: AsyncClient, db_session: AsyncSession
) -> None:
    p = _partition("v-agents")
    await _add(db_session, p)
    await _add(
        db_session,
        # a1 failed, then passed: its latest is PASS.
        _verdict(p, "a1", "FAIL", at=T0),
        _verdict(p, "a1", "PASS", at=T0 + timedelta(hours=1)),
        # a2 is still in progress.
        _verdict(p, "a2", "IN_PROGRESS", at=T0 + timedelta(minutes=30)),
        # a3 not run.
        _verdict(p, "a3", "NOT_RUN", at=T0 + timedelta(hours=2)),
    )
    body = await _ask(bridged, "v-agents")
    assert body["verdict"] == "IN_PROGRESS"
    assert body["decided_at"] == "2026-09-23T12:30:00+00:00"

    await _add(db_session, _verdict(p, "a3", "TIMEOUT", at=T0 + timedelta(hours=3)))
    assert (await _ask(bridged, "v-agents"))["verdict"] == "TIMEOUT"


async def test_only_the_current_seal_counts(bridged: AsyncClient, db_session: AsyncSession) -> None:
    old = _partition("v-reseal", status="retired", digest="sha256:old")
    new = _partition("v-reseal", digest="sha256:new", sealed_at=T0 + timedelta(days=1))
    await _add(db_session, old, new)
    await _add(db_session, _verdict(old, "a1", "PASS"))
    assert (await _ask(bridged, "v-reseal"))["verdict"] == "NOT_RUN"

    await _add(db_session, _verdict(new, "a1", "PASS"))
    assert (await _ask(bridged, "v-reseal"))["verdict"] == "PASS"


# --- 3. effect, not report ------------------------------------------------------------------


async def test_the_answer_is_the_committed_rows_now(
    bridged: AsyncClient, db_session: AsyncSession
) -> None:
    """Rows written and committed, then read back through a fresh session
    and the endpoint. A newer row later changes the answer: no cache."""
    p = _partition("v-live")
    await _add(db_session, p)
    await _add(db_session, _verdict(p, "a1", "PASS", at=T0))

    async with fresh_session(db_session) as new:
        assert (await venture_verdict(new, "v-live"))["verdict"] == "PASS"
    assert (await _ask(bridged, "v-live"))["verdict"] == "PASS"

    await _add(db_session, _verdict(p, "a1", "FAIL", at=T0 + timedelta(minutes=5)))

    async with fresh_session(db_session) as new:
        fresh = await venture_verdict(new, "v-live")
    assert fresh["verdict"] == "FAIL"
    assert fresh["decided_at"] == "2026-09-23T12:05:00+00:00"
    assert (await _ask(bridged, "v-live")) == fresh


# --- 4. 4xx is auth or body, never the venture ----------------------------------------------


@pytest.mark.parametrize("venture", ["v-pass", "v-unknown"])
async def test_no_credential_is_refused_whatever_the_venture(
    bridged: AsyncClient, db_session: AsyncSession, venture: str
) -> None:
    p = _partition("v-pass")
    await _add(db_session, p)
    await _add(db_session, _verdict(p, "a1", "PASS"))

    payload = {"venture_id": venture}
    none = await bridged.post(URL, json=payload)
    wrong = await bridged.post(URL, json=payload, headers={"Authorization": "Bearer wrong"})
    for res in (none, wrong):
        assert res.status_code == 401
        assert "PASS" not in res.text
        assert "partition" not in res.text.lower()


@pytest.mark.parametrize(
    "payload", [{}, {"venture_id": ""}, {"venture_id": 7}, {"venture_id": "v", "x": 1}]
)
async def test_a_malformed_body_is_a_422(bridged: AsyncClient, payload: dict) -> None:
    res = await bridged.post(URL, json=payload, headers=AUTH)
    assert res.status_code == 422


# --- 5. no request path can reach content ---------------------------------------------------

SRC = Path(__file__).resolve().parents[2] / "src"
FORBIDDEN_MODULES = {
    "src.services.operation.held_out_partition",
    "src.services.operation.partition_grading",
    "src.workers.partition_sweep",
}
#: The scheduler's own router. It reaches every job through `jobs`, as it
#: reaches `battery_sweep`; what stops a request putting the partition there
#: is `triggerable=False` and the job's own refusal, asserted below.
SCHEDULER_ROUTER = "src.routers.cadence"
#: Where the scenario table is defined and registered for the mapper.
#: Reaching these is unavoidable (every model loads) and holds no rows.
SCENARIO_NAME_HOMES = {"src.models", "src.models.held_out_partition"}


def _module_path(name: str) -> Path | None:
    parts = name.split(".")[1:]
    for path in (
        SRC.joinpath(*parts).with_suffix(".py"),
        SRC.joinpath(*parts, "__init__.py"),
    ):
        if path.exists():
            return path
    return None


def _reachable(entries: list[str]) -> dict[str, ast.AST]:
    """Every `src.*` module statically imported from `entries`, with its AST."""
    seen: dict[str, ast.AST] = {}
    stack = list(entries)
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        path = _module_path(name)
        if path is None:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        seen[name] = tree
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("src."):
                    stack.append(node.module)
                    # `from src.x import y` may import a submodule y.
                    stack.extend(f"{node.module}.{a.name}" for a in node.names)
            elif isinstance(node, ast.Import):
                stack.extend(a.name for a in node.names if a.name.startswith("src."))
    return seen


def _mentions(tree: ast.AST, name: str) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == name:
            return True
        if isinstance(node, ast.Attribute) and node.attr == name:
            return True
        if isinstance(node, ast.alias) and name in (node.name, node.asname):
            return True
    return False


def test_no_router_can_reach_the_scenarios() -> None:
    routers = [
        f"src.routers.{p.stem}"
        for p in (SRC / "routers").glob("*.py")
        if p.stem != "__init__" and f"src.routers.{p.stem}" != SCHEDULER_ROUTER
    ]
    reachable = _reachable(routers)

    # Positive controls: the walk reaches the verdict service and the model.
    assert "src.services.operation.partition_verdict" in reachable
    assert "src.models.held_out_partition" in reachable

    assert not FORBIDDEN_MODULES & set(reachable), sorted(FORBIDDEN_MODULES & set(reachable))
    # ADR-0114 adds the per-probe why. It is as closed to a request as the scenarios.
    touching = sorted(
        name
        for name, tree in reachable.items()
        if name not in SCENARIO_NAME_HOMES
        and (
            _mentions(tree, "HeldOutPartitionScenario")
            or _mentions(tree, "HeldOutPartitionOutcome")
        )
    )
    assert touching == [], f"request path names the scenario table: {touching}"


def test_the_scheduler_router_cannot_start_the_grader() -> None:
    """The one router that reaches the grader, through `jobs`. It may not start it."""
    from src.services.cadence import JOBS_BY_NAME

    assert JOBS_BY_NAME["partition_sweep"].triggerable is False
    reachable = _reachable([SCHEDULER_ROUTER])
    assert "src.services.cadence.jobs" in reachable  # the path this test is about
