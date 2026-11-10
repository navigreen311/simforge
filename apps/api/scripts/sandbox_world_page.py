"""Write the sandbox world page, and the world for CRE Forge's loader, per seed (ADR-0166).

    cd apps/api && python -m scripts.sandbox_world_page --seed 0 --seed 1 --out <dir> [--export]

Reads nothing. Writes one `world-seed-<n>.html` per seed and, with `--export`, the world as
CRE Forge's sandbox loader reads it, `simforge-<version>-seed-<n>.json` (stage 5). The same seed
gives the same bytes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.services.forges.deal_desk_world import export_json, render_page, world_name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--export", action="store_true", help="also write the loader's world file")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    for seed in args.seed:
        path = args.out / f"world-seed-{seed}.html"
        path.write_bytes(render_page(seed).encode("utf-8"))
        print(path)
        if args.export:
            path = args.out / f"{world_name(seed)}.json"
            path.write_bytes(export_json(seed).encode("utf-8"))
            print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
