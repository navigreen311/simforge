"""The examiner's settings as one value: what an exam ref names, and what a verdict must match.

THE RULING (Ivan Green, 26 November 2026, The Office decisions entry 355)
=========================================================================

    A changed setting must make a new exam; an unchanged one must still carry over as today.

The Office mints the run ref, and `open_run` is idempotent on it (ADR-0091's run identity is the
ref and nothing else). The ref named the venture, Forge, module, agent, instruction, answer key,
sections shown, protocol and rubric - and not the model. So once the window moved from 8192 to
16384 with the manuals unchanged, The Office would mint the 8192 exam's ref, `open_run` would hand
back the graded 8192 run, and its verdict would be read as a 16384 certification. The Office's
grant hold (its #568) would then refuse the grant forever, because nothing could re-sit it.

So the ref names the examiner too: an `m` segment, the first 12 hex characters of
`settings_digest` over the five facts below. The Office reads the digest from
`GET /api/health/examiner-settings` and puts it in the ref; SimForge checks it before grading
(`battery.SKIP_EXAMINER_SETTINGS_MISMATCH`) and when counting a held-out sitting (Gate 9.5).

WHICH FACTS, AND WHY THESE FIVE
===============================

    model         the tag. The Office's `check_model` compares it, so it is here.
    file_digest   the weights. A re-pull over different weights is a different examiner.
    temperature   per Forge (B136). `check_model` compares it.
    max_tokens    the output cap (entry 354, `agent_tasks.max_tokens`). Compared since phase 2a.
    num_ctx       the window (B131; 16384 since entry 353). Compared from The Office's #568.

**Exactly what The Office's `check_model` compares, and no more.** A setting it compares and the
ref does not name is a setting whose change holds every grant with no exam that can lift the hold.
A fact it does not compare (quantization, file size) is decided by the digest already, and adding
it would only make two records of one fact that can disagree.

The seed is not here, for `model_identity`'s reason: it belongs to an attempt, not to the exam.

WHY THE STATED VALUES ARE THE PIN AND THE DECLARATION, NOT A MODEL CALL
=======================================================================

`settings_now` says what an exam WOULD run at, and The Office asks it before any exam exists. So
it reads the pin (`EXAM_MODEL_DIGEST`, `EXAM_MODEL_TAG`), the Village's declaration for the Forge
and `EXAM_NUM_CTX` - the same values the battery builds its runtime from - and calls nothing.
`check_examiner` refuses any exam whose live digest is not the pin, so a graded exam's identity
and this agree whenever the battery was allowed to run at all.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from src.config import settings
from src.services.agent_runtime.model_identity import ModelIdentity
from src.services.agent_runtime.runtime import exam_settings_from
from src.services.village.model_config import VillageConfigError, read_village_agent_model

#: The five facts, in the order they are named above.
SETTINGS_KEYS: tuple[str, ...] = ("model", "file_digest", "temperature", "max_tokens", "num_ctx")

#: `...:s<12>:m<12>:p6.0.0:r0.5.0` - the segment The Office's `mint_run_ref` writes.
_REF_SETTINGS = re.compile(r":m([0-9a-f]{12})(?=:|$)")


class ExaminerSettingsUnknown(Exception):
    """What an exam would run at cannot be stated. Never a default in its place."""


def _canonical(model: Any, file_digest: Any, generation: dict) -> dict | None:
    """The five facts with one type each, or None when any is missing.

    Typed here so two writers produce the same bytes: a temperature of `0` and of `0.0` are one
    setting, and a JSON digest over them must not be two.
    """
    temperature = generation.get("temperature")
    max_tokens = generation.get("max_tokens")
    num_ctx = generation.get("num_ctx")
    if not model or not file_digest:
        return None
    if isinstance(temperature, bool) or not isinstance(temperature, int | float):
        return None
    if not _whole(max_tokens) or not _whole(num_ctx):
        return None
    return {
        "model": str(model),
        "file_digest": str(file_digest),
        "temperature": float(temperature),
        "max_tokens": max_tokens,
        "num_ctx": num_ctx,
    }


def _whole(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def settings_of(identity: ModelIdentity | dict | None) -> dict | None:
    """The five facts a recorded model identity names, or None when it cannot name all five.

    None is the answer for a record older than the window (B131 added `num_ctx`, 17 October) or
    than ADR-0167's examiner record on a held-out sitting. A record that cannot say what it ran
    at is not evidence that it ran at anything in particular, so it matches nothing.
    """
    if isinstance(identity, dict):
        identity = ModelIdentity.from_record(identity)
    if identity is None:
        return None
    return _canonical(identity.model, identity.file_digest, dict(identity.settings or {}))


def settings_now(forge_id: str) -> dict:
    """The five facts an exam on `forge_id` would run at now. Raises rather than guessing."""
    digest = (settings.exam_model_digest or "").strip()
    if not digest:
        raise ExaminerSettingsUnknown(
            "EXAM_MODEL_DIGEST is empty, so no exam can run and none can be named."
        )
    try:
        declared = read_village_agent_model(forge_id=forge_id).settings
    except VillageConfigError as exc:
        raise ExaminerSettingsUnknown(str(exc)) from exc
    found = _canonical(settings.exam_model_tag, digest, exam_settings_from(declared))
    if found is None:
        raise ExaminerSettingsUnknown(
            f"the exam's settings for {forge_id!r} do not name all of {', '.join(SETTINGS_KEYS)}."
        )
    return found


def settings_digest(facts: dict) -> str:
    """`sha256:<hex>` over the five facts, sorted keys and compact separators."""
    payload = json.dumps(
        {k: facts[k] for k in SETTINGS_KEYS}, sort_keys=True, separators=(",", ":")
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def ref_segment(digest: str) -> str:
    """The 12 hex characters a run ref carries after `m`."""
    return digest.removeprefix("sha256:")[:12]


def settings_of_run_ref(run_ref: str) -> str | None:
    """The settings segment a run ref names, or None when it names none.

    A ref with no segment predates the segment, or is one The Office carried over because its
    certification already stands at these settings (entry 355); either way there is nothing to
    compare, so it is not refused on this ground - `protocol_of_run_ref`'s rule.
    """
    found = _REF_SETTINGS.findall(run_ref or "")
    return found[-1] if found else None


def same_settings(identity: ModelIdentity | dict | None, now: dict | None) -> bool:
    """Whether a recorded identity names exactly the five facts in `now`."""
    recorded = settings_of(identity)
    return recorded is not None and now is not None and recorded == now


__all__ = [
    "SETTINGS_KEYS",
    "ExaminerSettingsUnknown",
    "ref_segment",
    "same_settings",
    "settings_digest",
    "settings_now",
    "settings_of",
    "settings_of_run_ref",
]
