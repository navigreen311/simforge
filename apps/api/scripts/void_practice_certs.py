"""Operator CLI: void the certificates issued from practice runs (ADR-0158, ADR-0159).

    apps/api/.venv/Scripts/python.exe -m scripts.void_practice_certs
    apps/api/.venv/Scripts/python.exe -m scripts.void_practice_certs --apply --operator "<name>"

Without `--apply` it is a dry run: a read-only transaction, the plan printed, nothing written, no
credential asked for.

With `--apply`, the named operator types their own credential at a hidden prompt, as for
`author_partition` (ADR-0154). It is never taken from the command line or the environment, and
never printed. An unknown name or a wrong credential is refused and audited, and nothing is
written. The void then re-plans and refuses if any target has moved since the ruling.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from collections.abc import Callable

from sqlalchemy import text

from src.db import SessionLocal
from src.services.cert import practice_void
from src.services.operation.partition_operators import OperatorRefused

Prompt = Callable[[str], str]


def _print(the_plan: practice_void.Plan, *, applied: bool) -> None:
    print("APPLIED" if applied else "DRY RUN - nothing written")
    print(f"reason: {practice_void.REASON}")
    for s in the_plan.steps:
        print(f"  {s.kind:<15} {s.target:<27} {s.label:<48} {s.before} -> {s.after}  +{s.appends}")
    for line in the_plan.skipped:
        print(f"  skipped: {line}")


async def _main(operator: str | None, prompt: Prompt) -> int:
    async with SessionLocal() as session:
        try:
            if operator is not None:
                credential = prompt(f"Credential for {operator}: ")
                applied = await practice_void.apply(
                    session, operator_name=operator, credential=credential
                )
                _print(applied, applied=True)
            else:
                await session.execute(text("SET TRANSACTION READ ONLY"))
                _print(await practice_void.plan(session), applied=False)
                await session.rollback()
        except (practice_void.VoidRefused, OperatorRefused) as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 2
    return 0


def main(argv: list[str] | None = None, prompt: Prompt = getpass.getpass) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write; default is a dry run")
    parser.add_argument(
        "--operator", help="the enrolled operator signing it (required with --apply)"
    )
    args = parser.parse_args(argv)
    if args.apply and not (args.operator or "").strip():
        parser.error("--apply needs --operator")
    if args.operator and not args.apply:
        parser.error("--operator signs an --apply; a dry run needs no credential")
    return asyncio.run(_main(args.operator if args.apply else None, prompt))


if __name__ == "__main__":
    sys.exit(main())
