"""CLI: validate one or more Pack directories. Exit non-zero on any error."""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import ValidationError

from validator.loader import PackLoadError, load_pack
from validator.rules import validate_pack


def validate_path(pack_dir: Path) -> bool:
    print(f"\n== {pack_dir} ==")
    try:
        loaded = load_pack(pack_dir)
    except (PackLoadError, ValidationError) as exc:
        print(f"  ERROR loading: {exc}")
        return False

    result = validate_pack(loaded)
    print(f"  pack: {loaded.spec.pack_id}  scenarios: {len(loaded.scenarios)}")
    for issue in result.issues:
        print(f"  [{issue.severity}] {issue.code}: {issue.message}")
    print("  OK" if result.ok else "  FAILED")
    return result.ok


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("usage: simforge-validate <pack_dir> [<pack_dir> ...]")
        return 1

    targets: list[Path] = []
    for a in args:
        p = Path(a)
        # Allow passing a parent dir containing versioned packs (e.g. packs/greenstone).
        if (p / "pack.yml").exists():
            targets.append(p)
        else:
            targets.extend(sorted(d.parent for d in p.rglob("pack.yml")))

    if not targets:
        print(f"No pack.yml found under: {', '.join(args)}")
        return 1

    all_ok = all(validate_path(t) for t in targets)
    print("\nALL PACKS VALID" if all_ok else "\nVALIDATION FAILED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
