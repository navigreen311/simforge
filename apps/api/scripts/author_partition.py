"""Operator CLI: author a venture's held-out partition, or seal one.

    apps/api/.venv/Scripts/python.exe -m scripts.author_partition \\
        --venture <venture_id> --forge <forge_id> --by "<author's name>"

    apps/api/.venv/Scripts/python.exe -m scripts.author_partition \\
        --seal-id <partition_id> --sealed-by "<sealer's name>"

Two commands, two people (ADR-0113): the sealer is a named human and
never the author, so one invocation cannot do both.

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
            digest = await seal_partition(session, pid, args.sealed_by)
            return {
                "partition_id": pid,
                "scenarios": await scenario_count(session, pid),
                "content_digest": digest,
                "status": "sealed",
            }
        pid = await author_partition(session, args.venture, args.forge, args.by)
        return {
            "partition_id": pid,
            "scenarios": await scenario_count(session, pid),
            "status": "authoring",
        }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--venture")
    p.add_argument("--forge")
    p.add_argument("--by", help="the author: a named human, never The Office")
    p.add_argument("--seal-id", help="seal an existing authoring partition")
    p.add_argument("--sealed-by", help="the sealer: a named human, not the author")
    args = p.parse_args(argv)
    if args.seal_id:
        if not args.sealed_by:
            p.error("--seal-id needs --sealed-by")
    elif not (args.venture and args.forge and args.by):
        p.error("--venture, --forge and --by are required to author")
    try:
        print(json.dumps(asyncio.run(_run(args)), indent=2))
    except PartitionRefused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
