"""Operator CLI: author, and optionally seal, a venture's held-out partition.

    apps/api/.venv/Scripts/python.exe -m scripts.author_partition \\
        --venture <venture_id> --forge <forge_id> --by <operator> [--seal]

    apps/api/.venv/Scripts/python.exe -m scripts.author_partition \\
        --seal-id <partition_id>

It prints the partition id, the scenario count and, once sealed, the
content digest. It never prints a scenario. ADR-0109.

Not a route, by design: no HTTP path authors or reads a partition.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from src.db import SessionLocal
from src.services.operation.held_out_partition import (
    PartitionRefused,
    author_partition,
    scenario_count,
    seal_partition,
)


async def _run(args: argparse.Namespace) -> dict:
    async with SessionLocal() as session:
        if args.seal_id:
            pid = args.seal_id
        else:
            pid = await author_partition(
                session, args.venture, args.forge, args.by
            )
        out: dict = {
            "partition_id": pid,
            "scenarios": await scenario_count(session, pid),
        }
        if args.seal or args.seal_id:
            out["content_digest"] = await seal_partition(session, pid)
            out["status"] = "sealed"
        else:
            out["status"] = "authoring"
        return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--venture")
    p.add_argument("--forge")
    p.add_argument("--by", help="who triggers it (never The Office)")
    p.add_argument("--seal", action="store_true", help="seal after authoring")
    p.add_argument("--seal-id", help="seal an existing authoring partition")
    args = p.parse_args(argv)
    if not args.seal_id and not (args.venture and args.forge and args.by):
        p.error("--venture, --forge and --by are required unless --seal-id")
    try:
        print(json.dumps(asyncio.run(_run(args)), indent=2))
    except PartitionRefused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
