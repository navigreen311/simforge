"""Which code this process is running, and which code the checkout is on now (ADR-0084).

**A live process is not an up-to-date one, and until now nothing could tell them apart.** On
19 September the API had been serving `f13d7b1` for two days while the checkout sat at `0b2fb9e`,
sixteen commits ahead - so a curriculum's `expected_answer` was validated by a schema written
before P1 and discarded on arrival. Every check that could have caught it passed: the port
answered, `/api/health` said ok, and `openapi.info.version` reported a SHA.

    THE SHA WAS NOT EVIDENCE. `openapi.info.version` is `settings.app_version`, which is the
    `APP_VERSION` environment variable with a default of "1.0.0". Whoever launched the process
    exported it by hand. It reported a SHA it was TOLD, not one it READ - so it can be wrong in
    both directions, and on the first restart of that day it reported "1.0.0" while running
    correct code.

Two numbers, and the second is the one no single-value check can have.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

#: Where `.git` lives relative to this file: apps/api/src/build_info.py -> repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]

UNKNOWN = "unknown"


def _git_head(root: Path) -> str:
    """`git rev-parse HEAD` for a working tree, or `unknown`. **Never raises.**

    A version endpoint that can fail is a health check reporting the health of itself.
    """
    try:
        if not (root / ".git").exists():
            return UNKNOWN
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return out.stdout.strip() or UNKNOWN
    except Exception:
        return UNKNOWN


def _started_commit() -> str:
    """The commit this process is running, resolved ONCE at import.

    `SIMFORGE_GIT_COMMIT` first, then `APP_VERSION` when it looks like a SHA, then the working
    tree. An image has no `.git` and stamps the variable; a development checkout has no stamp and
    can be asked.

    **Read at import and never again**, because the answer cannot change while the process lives.
    A value that moved under a caller would be worse than none: it would report the checkout's
    commit as the process's own, which is precisely the confusion this module exists to end.
    """
    for name in ("SIMFORGE_GIT_COMMIT", "APP_VERSION"):
        stamped = os.environ.get(name, "").strip()
        # `APP_VERSION` also carries release strings like "1.0.0", which are not commits.
        if stamped and len(stamped) >= 7 and all(c in "0123456789abcdef" for c in stamped.lower()):
            return stamped
    return _git_head(_REPO_ROOT)


#: Frozen at import. See `_started_commit`.
STARTED_COMMIT: str = _started_commit()


def checkout_commit() -> str:
    """What the working tree is on RIGHT NOW. Read per request, because this one moves."""
    return _git_head(_REPO_ROOT)


def commits_differ(started: str, checkout: str) -> bool | None:
    """Whether the process is behind its own checkout.

    **`None` when either side is unknown, and that is the whole care in this function.** An
    unknown is not a match: returning `False` would report "up to date" for a process that cannot
    say what it is running, which is the reassurance the caller must not be given.
    """
    if started == UNKNOWN or checkout == UNKNOWN:
        return None
    return started != checkout
