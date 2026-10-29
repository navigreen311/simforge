"""Operator CLI: author a venture's held-out partition, seal one, or enrol an operator.

    apps/api/.venv/Scripts/python.exe -m scripts.author_partition \\
        --venture <venture_id> --forge <forge_id> --by "<author's name>" \\
        [--modules a,b] [--roster <The Office's roster statement, a JSON file>]

    apps/api/.venv/Scripts/python.exe -m scripts.author_partition \\
        --seal-id <partition_id> --sealed-by "<sealer's name>"

    apps/api/.venv/Scripts/python.exe -m scripts.author_partition \\
        --enrol "<name>" [--witness "<enrolled operator>"]

    apps/api/.venv/Scripts/python.exe -m scripts.author_partition \\
        --reset "<name>" --witness "<another enrolled operator>"

Two commands, two people (ADR-0113): the sealer is a named human and
never the author, so one invocation cannot do both.

Each named person types their own credential at a hidden prompt
(ADR-0154). It is never taken from the command line or the environment,
and never printed. Enrolment asks for the new credential twice; every
enrolment after the first also asks the witness for theirs.

A lost credential is reset, never recovered (ADR-0156): the witness types
theirs first, then the operator sets a new one, twice. The operator keeps
their id, so what they authored stays theirs.

`--roster` is The Office's statement of its live grants on the venture and
forge (docs/contracts/partition-roster.md). Its grants on the partition's
modules are recorded, and they alone sit it (ADR-0162). Without it the
partition keeps the run-history roster (ADR-0152).

It prints the partition id, the scenario count, the number of rostered
agents when a roster was recorded, and, once sealed, the content digest.
It never prints a scenario. ADR-0109.

Not a route, by design: no HTTP path authors or reads a partition.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import sys
from collections.abc import Callable

from src.db import SessionLocal
from src.models.held_out_partition import HeldOutPartition
from src.services.operation.held_out_partition import (
    PartitionRefused,
    author_partition,
    scenario_count,
    seal_partition,
)
from src.services.operation.partition_operators import (
    OperatorRefused,
    enrol_operator,
    reset_credential,
)

Prompt = Callable[[str], str]


def _read_roster(path: str) -> dict:
    """The Office's roster statement. Not validated here: `author_partition` does that."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as exc:
        raise PartitionRefused(f"the roster file could not be read as JSON: {exc}") from exc


def _credential_for(prompt: Prompt, name: str) -> str:
    return prompt(f"Credential for {name}: ")


async def _run(args: argparse.Namespace, prompt: Prompt) -> dict:
    async with SessionLocal() as session:
        if getattr(args, "reset", None):
            witness_credential = _credential_for(prompt, args.witness)
            operator_id = await reset_credential(
                session,
                args.reset,
                prompt(f"New credential for {args.reset}: "),
                prompt(f"Repeat the credential for {args.reset}: "),
                witness_name=args.witness,
                witness_credential=witness_credential,
            )
            return {"operator_id": operator_id, "reset": args.reset, "witness": args.witness}
        if args.enrol:
            credential = prompt(f"New credential for {args.enrol}: ")
            if prompt(f"Repeat the credential for {args.enrol}: ") != credential:
                raise OperatorRefused("the two entries did not match.", "entries_differ")
            witness_credential = _credential_for(prompt, args.witness) if args.witness else None
            operator_id = await enrol_operator(
                session,
                args.enrol,
                credential,
                witness_name=args.witness,
                witness_credential=witness_credential,
            )
            return {"operator_id": operator_id, "enrolled": args.enrol}
        if args.seal_id:
            pid = args.seal_id
            digest = await seal_partition(
                session,
                pid,
                args.sealed_by,
                credential=_credential_for(prompt, args.sealed_by),
            )
            return {
                "partition_id": pid,
                "scenarios": await scenario_count(session, pid),
                "content_digest": digest,
                "status": "sealed",
            }
        raw = getattr(args, "modules", None)
        modules = raw.split(",") if raw else None
        roster = _read_roster(args.roster) if getattr(args, "roster", None) else None
        pid = await author_partition(
            session,
            args.venture,
            args.forge,
            args.by,
            modules,
            credential=_credential_for(prompt, args.by),
            roster=roster,
        )
        out = {
            "partition_id": pid,
            "scenarios": await scenario_count(session, pid),
            "status": "authoring",
        }
        if roster is not None:
            recorded = (await session.get(HeldOutPartition, pid)).roster
            out["rostered_agents"] = len({g["agent_id"] for g in recorded["grants"]})
        return out


def main(argv: list[str] | None = None, prompt: Prompt = getpass.getpass) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--venture")
    p.add_argument("--forge")
    p.add_argument("--by", help="the author: an enrolled named human, never The Office")
    p.add_argument(
        "--modules",
        help="comma-separated: scope to the modules the venture operates (ADR-0129)",
    )
    p.add_argument(
        "--roster",
        help="The Office's roster statement, a JSON file: who sits the partition (ADR-0162)",
    )
    p.add_argument("--seal-id", help="seal an existing authoring partition")
    p.add_argument("--sealed-by", help="the sealer: an enrolled named human, not the author")
    p.add_argument("--enrol", help="enrol a named human as a partition operator (ADR-0154)")
    p.add_argument(
        "--reset", help="replace a lost credential, witnessed by another operator (ADR-0156)"
    )
    p.add_argument("--witness", help="the enrolled operator vouching for --enrol or --reset")
    args = p.parse_args(argv)
    if args.reset:
        if args.enrol or args.seal_id or args.by:
            p.error("--reset is its own command")
        if not args.witness:
            p.error("--reset needs --witness")
    elif args.enrol:
        if args.seal_id or args.by:
            p.error("--enrol is its own command")
    elif args.seal_id:
        if not args.sealed_by:
            p.error("--seal-id needs --sealed-by")
    elif not (args.venture and args.forge and args.by):
        p.error("--venture, --forge and --by are required to author")
    try:
        print(json.dumps(asyncio.run(_run(args, prompt)), indent=2))
    except (PartitionRefused, OperatorRefused) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
