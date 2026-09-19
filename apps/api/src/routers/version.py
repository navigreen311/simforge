"""`/api/version` — which code this process is running, and whether the checkout has moved.

ADR-0084. The Office has had the same route since a stale API 404'd a route that was in the file
and not in the process. SimForge's version differs in one way that matters: **it reports BOTH
numbers**, because a single number can only ever say what it was told.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from src.build_info import STARTED_COMMIT, checkout_commit, commits_differ
from src.config import settings

router = APIRouter()

#: Settings that decide what this process DOES, reported by value.
#:
#: Every one of these is a mode rather than a credential. The list exists because
#: `SCHEDULER_ENABLED` vanished on a restart on 19 September and nothing said so: it lived only in
#: the old process's environment, the new process defaulted it to False, and the batteries the
#: operator believed were running were not.
#:
#: **Never `os.environ`.** Dumping the environment would put `DATABASE_URL`'s password, the Clerk
#: secret and The Office's tenant token into an unauthenticated response. The credential-bearing
#: settings are reported as booleans below instead - which answers "was it exported" without
#: answering "what is it".
_REPORTED_MODES: tuple[str, ...] = (
    "scheduler_enabled",
    "auth_mode",
    "llm_provider",
    "llm_judge_provider",
    "forge_mode",
    "hsm_provider",
    "exam_model_tag",
    "exam_model_digest",
    "integrated_execution_enabled",
)

#: Credential-bearing settings, reported as PRESENT or ABSENT and never by value.
_REPORTED_PRESENCE: tuple[str, ...] = (
    "database_url",
    "office_tenant_token",
    "clerk_secret_key",
    "anthropic_api_key",
)

#: Settings that name a FILE, and the environment variable that sets each.
#:
#: **Reported by whether they RESOLVE, not by whether they have a value** (ADR-0088). For two days
#: `village_db_path` read as `configured: true` while pointing at a file that does not exist -
#: because it has a default, and a default is a value. `configured` answered "is there a string",
#: and for a path the useful question is "is there a file".
#:
#: `is_default` is the other half of that, and it is compared against the FIELD'S DEFAULT rather
#: than against `os.environ`. A value set in `.env` is not in the process environment - pydantic
#: reads the file into the settings object - so an environment check would report every configured
#: path as unconfigured, which is the same class of wrong answer in the opposite direction.
_REPORTED_PATHS: tuple[str, ...] = (
    "village_config_path",
    "village_db_path",
    "village_data_path",
)


def _launch_environment() -> dict:
    """The settings this process actually parsed, not the environment a caller hopes it had.

    Reported from `settings` rather than `os.environ` deliberately: what matters is the value the
    process is USING. A variable exported with a typo is absent from `settings` and present in the
    environment, and the first is the honest answer.
    """
    modes = {}
    for name in _REPORTED_MODES:
        value = getattr(settings, name, None)
        modes[name] = value if value not in ("", None) else None
    present = {}
    for name in _REPORTED_PRESENCE:
        value = getattr(settings, name, None)
        present[name] = bool(value)
    return {"modes": modes, "configured": present, "paths": _path_report()}


def _path_report() -> dict:
    """Each file-valued setting: set, from where, and **whether it is actually there.**

    The value itself is not reported. An absolute path carries a username and this route is
    public; `resolves` is what an operator needs and `value` is not.

    Relative paths resolve against the process's working directory, which is what the application
    itself would do - so a path that reads `resolves: false` here fails for the application too,
    rather than only for this report.
    """
    out: dict = {}
    for name in _REPORTED_PATHS:
        raw = (getattr(settings, name, None) or "").strip()
        field = type(settings).model_fields.get(name)
        default = "" if field is None or field.default is None else str(field.default)
        out[name] = {
            "value_set": bool(raw),
            "is_default": raw == default.strip(),
            "resolves": bool(raw) and Path(raw).exists(),
        }
    return out


@router.get("")
@router.get("/")
async def version() -> dict:
    """Which build is serving, which build is checked out, and whether they differ.

    **Two numbers, because one cannot catch the failure.** `openapi.info.version` reported a SHA
    for two days while serving code sixteen commits older - it was the `APP_VERSION` variable
    somebody exported at launch, not a fact about the loaded bytecode. A stamp can be stale, wrong,
    or absent; only the comparison is evidence.

    `differs: null` means at least one side could not be read, and it is never `false` in that
    case: a process that cannot say what it is running must not report itself up to date.

    **Public, and that is a divergence from The Office worth naming.** The Office authenticates
    this route and pins its unauthenticated surface to exactly two paths, on the ground that
    telling an anonymous caller which build is running is a disclosure. SimForge's health router is
    public by stated design and `/api/health/config` already returns `app_version` and the whole
    seam configuration, so authenticating this one alone would be a lock on an open door. Worth a
    ruling; not worth a private decision here.
    """
    started = STARTED_COMMIT
    checkout = checkout_commit()
    return {
        "started_commit": started,
        "checkout_commit": checkout,
        "differs": commits_differ(started, checkout),
        "app_version": settings.app_version,
        "launch_environment": _launch_environment(),
    }
