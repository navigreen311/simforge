"""Watch the operation-cert data and regenerate the static export whenever it changes.

Leave this running in a terminal; it polls a cheap fingerprint of the operation-cert data
(certifications + declared instruction sets + the P0 incident count that feeds the board) and
re-renders docs/operation-certs.html the moment anything moves — so however you seed (a script, the
API, or a manual insert), the openable export is always current. Ctrl+C to stop.

Run from the repo root:
  apps/api/.venv/Scripts/python.exe scripts/watch_operation_certs.py [--interval SECONDS]

Requires the api venv + a reachable dev database. It refreshes the local file only; commit the
export when you want to persist a snapshot.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import time

# export_operation_certs puts apps/api on sys.path at import time.
from export_operation_certs import OUTPUT, build, write_export  # noqa: E402


async def _fingerprint() -> tuple:
    """A cheap signature of everything the export depends on. Changes → re-render."""
    from sqlalchemy import func, select

    from src.db import SessionLocal
    from src.models.cert import AgentCert
    from src.models.forge_instruction_set import ForgeInstructionSet
    from src.models.gap import SoftwareGap
    from src.models.operation_cert import OperationCertification

    async with SessionLocal() as s:

        async def sig(model, ts_col) -> tuple:
            n = (await s.execute(select(func.count()).select_from(model))).scalar_one()
            latest = (await s.execute(select(func.max(ts_col)))).scalar_one()
            return (n, str(latest))

        op = await sig(OperationCertification, OperationCertification.createdAt)
        dom = await sig(AgentCert, AgentCert.issuedAt)  # domain pairing shown beside operation
        iset = await sig(ForgeInstructionSet, ForgeInstructionSet.authoredAt)  # declared hashes
        p0 = (
            await s.execute(
                select(func.count()).select_from(SoftwareGap).where(SoftwareGap.severity == "P0")
            )
        ).scalar_one()
        return (op, dom, iset, p0)


async def _render() -> int:
    data = await build()
    return write_export(data)


def _now() -> str:
    return time.strftime("%H:%M:%S")


async def watch(interval: float) -> None:
    print(f"[watch] operation-cert export → {OUTPUT}")
    n = await _render()
    last = await _fingerprint()
    print(f"[watch] {_now()} initial render ({n:,} bytes). Watching every {interval:g}s — Ctrl+C to stop.")
    while True:
        await asyncio.sleep(interval)
        try:
            fp = await _fingerprint()
        except Exception as exc:  # DB hiccup — keep watching, don't die
            print(f"[watch] {_now()} db check failed: {exc}")
            continue
        if fp != last:
            last = fp
            n = await _render()
            print(f"[watch] {_now()} data changed → re-rendered ({n:,} bytes)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--interval", type=float, default=3.0, help="poll seconds (default 3)")
    args = ap.parse_args()
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(watch(args.interval))
    print("\n[watch] stopped.")


if __name__ == "__main__":
    main()
