"""The examiner check: is the model about to sit this exam the one production runs?

THE RULING (Ivan Green, 17 September 2026)
==========================================

    The examiner is the production model. Certification runs on phi4, the model Village agents
    run on, pinned by digest, never a moving tag.

Two claims, and they fail in different ways, so they are checked separately and refused
separately.

**"the model Village agents run on"** is a comparison between two systems. The Village declares a
TAG in its own `config.yaml` (`village.model_config`); SimForge declares the tag it will ask for.
If those differ, the exam is about a different model than production and the certification would
be about nobody.

**"pinned by digest, never a moving tag"** is a comparison between a name and a file. `phi4:latest`
is a moving name — re-pull it over different weights and the string does not change. The pin is
the digest, and the check is that the tag still resolves to it.

WHY EVERY FAILURE IS A REFUSAL AND NOT A WARNING
================================================

A battery that runs anyway produces a certification asserting it was earned on the production
model. That assertion would be false and nothing downstream could tell — which is exactly the
empty-pass shape ruling 2 names for agents, one level up. So each check returns a REASON and the
battery skips; a skip posts no outcome, and `BatterySkipped` has said so since it was written.

WHY AN UNREADABLE VILLAGE CONFIG ALSO REFUSES
=============================================

The tempting alternative is to enforce the pin and skip the comparison when the Village config is
absent. That is worse than it looks: the resulting certification still says it was earned on the
production model, and the only thing that changed is that nobody checked. **"I could not see
production" is not "it matched."** Setting `VILLAGE_CONFIG_PATH` is one line; asserting a match
nobody made is permanent.

CI is unaffected: no battery runs there (ADR-0050 — there is no endpoint), so nothing in the test
suite reaches this check by accident.

WHAT IS DELIBERATELY *NOT* REFUSED
==================================

**A settings difference.** The Village runs its agents at temperature 0.7; the battery examines at
0.0, because an exam whose answers move between runs is not a certification. Those are genuinely
different requirements and the ruling does not resolve them, so this module SURFACES the difference
on the check result and refuses nothing. Recording it was ADR-0060's job and it is done; deciding
it is Ivan's, and a silent refusal here would decide it by implication.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.config import settings
from src.services.agent_runtime.model_identity import ModelIdentity
from src.services.village.model_config import VillageConfigError, read_village_agent_model

#: Why an examiner was refused. Each names a DIFFERENT fix, which is the whole reason there are
#: five of them rather than one `examiner_not_acceptable`.
EXAMINER_NOT_PINNED = "no_exam_model_digest_is_pinned"
EXAMINER_UNREACHABLE = "the_exam_model_could_not_be_described"
EXAMINER_TAG_MOVED = "the_pinned_digest_is_not_what_the_tag_serves_now"
EXAMINER_NOT_PRODUCTION_MODEL = "the_exam_model_is_not_the_model_the_village_runs"
EXAMINER_PRODUCTION_UNKNOWN = "simforge_cannot_read_which_model_the_village_runs"


@dataclass(frozen=True, slots=True)
class ExaminerCheck:
    """The outcome of the check. `reason` is None exactly when the battery may proceed."""

    reason: str | None
    detail: str
    #: Present when the Village's declaration was readable, whatever the verdict.
    village_tag: str | None = None
    #: Settings the Village declares that the exam does not use. Reported, never a refusal.
    settings_divergence: dict | None = None

    @property
    def ok(self) -> bool:
        return self.reason is None


def _settings_divergence(village_settings: dict, exam_settings: dict) -> dict | None:
    """Which declared settings the exam does not match. `None` when there is nothing to say."""
    out = {
        key: {"village": value, "exam": exam_settings.get(key)}
        for key, value in village_settings.items()
        if exam_settings.get(key) != value
    }
    return out or None


def check_examiner(identity: ModelIdentity | None) -> ExaminerCheck:
    """Whether `identity` may sit an exam. One reason at a time, most specific first.

    Ordered so the message names the thing to fix rather than the first thing that happened to be
    wrong: an unpinned digest is a configuration gap, an unreachable model is a deployment fact,
    and a moved tag is a real drift event. Reporting "not the production model" for a deployment
    that simply has no pin would send somebody to the wrong file.
    """
    pinned_tag = settings.exam_model_tag
    pinned_digest = (settings.exam_model_digest or "").strip()

    if not pinned_digest:
        return ExaminerCheck(
            EXAMINER_NOT_PINNED,
            f"EXAM_MODEL_DIGEST is empty. The examiner is pinned by digest, never by tag: "
            f"{pinned_tag!r} can be re-pulled over different weights without the name changing. "
            f"Read the digest from GET {settings.ollama_base_url}/api/tags and set it.",
        )

    if identity is None:
        return ExaminerCheck(
            EXAMINER_UNREACHABLE,
            f"the provider could not describe {pinned_tag!r}. Either it is not pulled on this "
            f"host, or {settings.ollama_base_url} is not answering. A model that cannot be "
            "described cannot be pinned, and an unpinned exam certifies nothing.",
        )

    live_digest = (identity.file_digest or "").strip()
    if live_digest != pinned_digest:
        return ExaminerCheck(
            EXAMINER_TAG_MOVED,
            f"{identity.model!r} now serves {live_digest or '<no digest>'}, and the pin is "
            f"{pinned_digest}. The tag moved. Either the model was re-pulled - in which case "
            "every certification earned under the old pin is against a model that no longer "
            "exists here and the pin is the decision to make deliberately - or the wrong model "
            "is configured.",
        )

    # Only now is it worth reading another system's file: the local pin holds.
    try:
        village = read_village_agent_model()
    except VillageConfigError as exc:
        return ExaminerCheck(
            EXAMINER_PRODUCTION_UNKNOWN,
            f"{exc} Not being able to see production is not the same as matching it.",
        )

    if village.tag != identity.model:
        return ExaminerCheck(
            EXAMINER_NOT_PRODUCTION_MODEL,
            f"the Village runs {village.tag!r} for agent-mode calls "
            f"(`{village.route}` in {village.source_path}) and the examiner is "
            f"{identity.model!r}. A certification earned on a different model is not a "
            "certification of the agent that runs in production.",
            village_tag=village.tag,
        )

    return ExaminerCheck(
        None,
        f"examiner {identity.model} pinned at {pinned_digest[:19]}..., matching the Village's "
        f"declared agent model in {village.source_path}",
        village_tag=village.tag,
        settings_divergence=_settings_divergence(village.settings, identity.settings),
    )


__all__ = [
    "EXAMINER_NOT_PINNED",
    "EXAMINER_NOT_PRODUCTION_MODEL",
    "EXAMINER_PRODUCTION_UNKNOWN",
    "EXAMINER_TAG_MOVED",
    "EXAMINER_UNREACHABLE",
    "ExaminerCheck",
    "check_examiner",
]
