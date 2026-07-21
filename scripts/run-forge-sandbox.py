#!/usr/bin/env python3
"""Serve a reference Forge sandbox over HTTP (ADR-0016).

Stands up the generic sandbox API for one forge, backed by its in-process Local engine, so you
can exercise the real HTTP path end-to-end. Point SimForge at it with:

  # terminal 1 — a reference CapitalForge sandbox on :9101
  python scripts/run-forge-sandbox.py capitalforge --port 9101

  # terminal 2 — run SimForge with FORGE_MODE=http against it
  export FORGE_MODE=http
  export FORGE_SANDBOX_URLS="capitalforge=http://localhost:9101"
  uvicorn src.main:app   # /api/forges/capitalforge/health now crosses HTTP to the sandbox

A production Forge implements the same contract for real; this is the dev/reference stand-in.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

import uvicorn  # noqa: E402

from src.services.forges.reference_sandbox import create_reference_sandbox  # noqa: E402
from src.services.forges.registry import KNOWN_FORGES  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve a reference Forge sandbox over HTTP.")
    parser.add_argument("forge", choices=sorted(KNOWN_FORGES), help="which forge to serve")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9101)
    args = parser.parse_args()

    app = create_reference_sandbox(args.forge)
    print(f"Reference {args.forge} sandbox -> http://{args.host}:{args.port}")
    print(f'  FORGE_MODE=http FORGE_SANDBOX_URLS="{args.forge}=http://{args.host}:{args.port}"')
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
