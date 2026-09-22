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
import socket
import subprocess
from datetime import UTC, datetime, timedelta
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


# =================================================================================================
# WHICH PROCESS, not only which code (ADR-0104 ruling 1).
#
# The six certifications of 19 September 2026 name no process, no commit and no host. When the
# question came - which process wrote them - the only handle was `started_commit` on a LIVE
# process, and every process alive that day had been restarted several times since. The attribution
# closed unattributed, and the rows themselves could not help: `forgeApiVersion` is a declared
# string, `agentModelIdentity` describes the examinee, and nothing anywhere named the writer.
#
# So a certification carries its writer. Four facts, frozen at import because none of them can
# change while the process lives.
# =================================================================================================



def _process_started_at() -> tuple[str, str]:
    """When this process was created, and **where the answer came from**.

    Two sources and a fallback, and the third value is reported rather than hidden:

    * `kernel` - Windows `GetProcessTimes`, or `/proc/self` on Linux. The real creation time.
    * `import` - the instant this module was imported, used where neither is available.

    The source travels with the value because they are not the same measurement. Import time is
    later than creation by however long the interpreter took to start, and a reader comparing a
    log line against a process must know which of the two they hold. Reporting them under one name
    would be the defect this whole ADR is about, one layer down.
    """
    try:  # Windows: the kernel's own answer, no dependency.
        import ctypes  # noqa: PLC0415
        import ctypes.wintypes  # noqa: PLC0415
        from ctypes import wintypes  # noqa: PLC0415

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        # ARGTYPES AND RESTYPES DECLARED, and they are not decoration. Without them
        # `GetCurrentProcess` returns its pseudo-handle (-1) as a C int, the call fails with 0,
        # and this function falls back to `import` while looking like it measured something.
        # That is the shape of defect this ADR exists about, so it is spelled out here.
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        pointer = ctypes.POINTER(wintypes.FILETIME)
        kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [pointer] * 4
        kernel32.GetProcessTimes.restype = wintypes.BOOL

        creation = wintypes.FILETIME()
        other = [wintypes.FILETIME() for _ in range(3)]
        ok = kernel32.GetProcessTimes(
            kernel32.GetCurrentProcess(),
            ctypes.byref(creation),
            *(ctypes.byref(f) for f in other),
        )
        if ok:
            # FILETIME is 100-nanosecond ticks since 1601-01-01 UTC.
            #
            # Added as a timedelta rather than through `.timestamp()`: on Windows,
            # `datetime(1601, 1, 1).timestamp()` raises OSError because the platform cannot
            # convert a pre-1970 instant - which is exactly how this silently fell back to
            # `import` the first time it ran.
            ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
            started = datetime(1601, 1, 1, tzinfo=UTC) + timedelta(
                microseconds=ticks // 10
            )
            return (started.isoformat(), "kernel")
    except Exception:
        pass
    try:  # Linux: /proc/self is created when the process is.
        stat = Path("/proc/self").stat()
        return (
            datetime.fromtimestamp(stat.st_ctime, tz=UTC).isoformat(),
            "kernel",
        )
    except Exception:
        pass
    return (datetime.now(tz=UTC).isoformat(), "import")


_STARTED_AT, _STARTED_AT_SOURCE = _process_started_at()

#: This process, as a row can record it. **Frozen at import**, for the reason `STARTED_COMMIT` is:
#: none of these can change while the process lives, and a value that moved under a caller would
#: describe some later moment as the one that wrote the row.
PROCESS_IDENTITY: dict[str, object] = {
    "started_commit": STARTED_COMMIT,
    "pid": os.getpid(),
    "host": socket.gethostname(),
    "process_started_at": _STARTED_AT,
    "process_start_source": _STARTED_AT_SOURCE,
}


def process_identity() -> dict[str, object]:
    """A COPY, because this is used as a column default and a shared dict would be one object
    hung off every row in the session - mutate it once and every certification changes."""
    return dict(PROCESS_IDENTITY)
