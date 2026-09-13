"""Cadence job registry (Part 16). Single source for what runs, when, and how — read by both the
APScheduler wiring (src/scheduler.py) and the /api/scheduler status + trigger endpoints."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from src.services.cadence import jobs


@dataclass(frozen=True)
class CadenceJob:
    name: str
    schedule: str  # human-readable cadence
    cron: dict  # APScheduler cron kwargs
    description: str
    # Accepts an optional session (request path passes one; scheduler passes none).
    run: Callable[..., Awaitable[dict]]
    #: May `POST /api/scheduler/run/<name>` fire this job?
    #:
    #: **False exists for ADR-0050 and for nothing else yet.** That ADR's rule is not only "no
    #: credential fetches the held-out set" but the consequence stated in its guard test: *"there
    #: is NO endpoint that triggers a battery: it is reached from a process-side caller."* The
    #: guard walks the import graph from `src.routers.operation`, so it cannot see this router -
    #: registering a battery job here would have satisfied the test while defeating the rule,
    #: which is the exact shape ADR-0050 warns about: routing around a refusal "is worse, because
    #: it looks compliant."
    #:
    #: A non-triggerable job is still scheduled, still listed by `/status`, and still inspectable.
    #: Only the on-demand HTTP verb is withheld.
    triggerable: bool = True


# Part 16.1 (daily) + 16.3-adjacent nightly maintenance. Cron times are UTC.
JOBS: tuple[CadenceJob, ...] = (
    CadenceJob(
        "daily_regression",
        "daily 02:00 UTC",
        {"hour": 2, "minute": 0},
        "Regression battery: detect scenario flips and auto-suspend affected certs (§9.2).",
        jobs.daily_regression,
    ),
    CadenceJob(
        "nightly_cert_lifecycle",
        "daily 02:15 UTC",
        {"hour": 2, "minute": 15},
        "Expire past-due certs; count certs expiring soon (§16.1).",
        jobs.nightly_cert_lifecycle,
    ),
    CadenceJob(
        "daily_snapshot",
        "daily 01:30 UTC",
        {"hour": 1, "minute": 30},
        "Capture each agent's cognitive snapshot (drift baseline; §16.1).",
        jobs.daily_snapshot,
    ),
    CadenceJob(
        "daily_fingerprint",
        "daily 01:00 UTC",
        {"hour": 1, "minute": 0},
        "Check the Village schema fingerprint for drift (§16.1).",
        jobs.daily_fingerprint,
    ),
    CadenceJob(
        "hourly_approval_escalation",
        "hourly",
        {"minute": 5},
        "Expire approval requests past their TTL — time-bound auto-escalation (§11.5).",
        jobs.hourly_approval_escalation,
    ),
    CadenceJob(
        "safe_mode_auto_trigger",
        "every 15 min",
        {"minute": "*/15"},
        "Auto-raise scoped safe mode when compliance failures spike (§11.7).",
        jobs.safe_mode_auto_trigger,
    ),
    CadenceJob(
        "evidence_purge",
        "daily 03:00 UTC",
        {"hour": 3, "minute": 0},
        "Purge evidence past retention unless on legal hold (§12.3).",
        jobs.evidence_purge,
    ),
    CadenceJob(
        "battery_sweep",
        "hourly",
        {"minute": 20},
        "Score unscored Unit-A runs with an operation battery (ADR-0050 - scheduler only).",
        jobs.battery_sweep,
        triggerable=False,
    ),
    CadenceJob(
        "expire_waivers",
        "hourly",
        {"minute": 10},
        "Expire waivers past their TTL (§11.5).",
        jobs.expire_waivers_job,
    ),
)

JOBS_BY_NAME: dict[str, CadenceJob] = {j.name: j for j in JOBS}
