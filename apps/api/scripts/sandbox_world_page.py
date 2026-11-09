"""Write the sandbox world page for one or more seeds (ADR-0166 stage 2).

    cd apps/api && python -m scripts.sandbox_world_page --seed 0 --seed 1 --seed 2 --out <dir>

Reads nothing and writes one `world-seed-<n>.html` per seed. The same seed gives the same bytes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.services.forges.deal_desk_world import render_page


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    for seed in args.seed:
        path = args.out / f"world-seed-{seed}.html"
        path.write_bytes(render_page(seed).encode("utf-8"))
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
