"""Operator CLI: void the certificates issued from practice runs (ADR-0158).

    apps/api/.venv/Scripts/python.exe -m scripts.void_practice_certs
    apps/api/.venv/Scripts/python.exe -m scripts.void_practice_certs --apply --actor "<name>"

Without `--apply` it is a dry run: it reads, prints the plan, and writes nothing. With `--apply` it
re-plans, refuses if any target has moved since the ruling, and writes. Append-only; see
`services/cert/practice_void.py`.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import text

from src.db import SessionLocal
from src.services.cert import practice_void


def _print(the_plan: practice_void.Plan, *, applied: bool) -> None:
    print("APPLIED" if applied else "DRY RUN - nothing written")
    print(f"reason: {practice_void.REASON}")
    for s in the_plan.steps:
        print(f"  {s.kind:<15} {s.target:<27} {s.label:<48} {s.before} -> {s.after}  +{s.appends}")
    for line in the_plan.skipped:
        print(f"  skipped: {line}")


async def _main(apply: bool, actor: str) -> int:
    async with SessionLocal() as session:
        try:
            if apply:
                _print(await practice_void.apply(session, actor=actor), applied=True)
            else:
                await session.execute(text("SET TRANSACTION READ ONLY"))
                _print(await practice_void.plan(session), applied=False)
                await session.rollback()
        except practice_void.VoidRefused as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 2
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="write; default is a dry run")
    parser.add_argument("--actor", default="", help="who is applying it (required with --apply)")
    args = parser.parse_args()
    if args.apply and not args.actor.strip():
        parser.error("--apply needs --actor")
    return asyncio.run(_main(args.apply, args.actor))


if __name__ == "__main__":
    sys.exit(main())
