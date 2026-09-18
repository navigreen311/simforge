"""What model the Village actually runs its agents on, read from the Village's own config.

WHY SIMFORGE READS THIS AT ALL
==============================

Ivan's ruling, 17 September 2026: *the examiner is the production model.* That is a statement
about two systems, and only one of them can check it — SimForge holds the exam, so SimForge is the
side that has to compare. The alternative is a declaration on the curriculum, which The Office
would have to make about a system it does not run, and a declaration nobody can check is the shape
`ADR-0059` refused.

WHERE THE VALUE COMES FROM, EXACTLY
===================================

`mate.ollama_model_routes.agent` in the Village's `config.yaml`. That key can hold either of two
things, and **the live deployment uses the one the code's defaults do not**:

    agent: phi4:latest     <- a TAG, directly. This is what the live config.yaml says.
    agent: default_llm     <- a model TYPE, resolved through `mate.models.default_llm.model_id`.
                              This is what `modules/frameworks/mate.py` defaults to in code.

Both are read. Assuming only the second would have raised on the real file; assuming only the
first would break a deployment that uses the indirection. Measured before it was written: the live
`config.yaml` names `phi4:latest` in the route.

THE SETTINGS ARE SOMEWHERE ELSE, AND THAT IS THE TRAP
=====================================================

`temperature` and `max_tokens` live in `mate.models.<type>` whichever form the route takes — so a
config that short-circuits the route still declares its settings under a type. Reading them only
on the indirect path reports `{}` for the live file and makes "no divergence" mean "did not look",
which is the false-negative this whole module exists to avoid. So the settings are found by
matching `model_id` against the resolved tag, and the route form does not change the answer.

They are REPORTED and not enforced — see `VillageAgentModel.settings`.

A TAG IS NOT A PIN, AND THIS FILE CANNOT FIX THAT
=================================================

The Village declares `phi4:latest`. That is a moving name: the same tag re-pulled over different
weights is a different model and the string does not change. So what crosses from here is the TAG,
and the digest is resolved from the Ollama instance that serves both sides. Ruling 1 says the pin
is a digest; this module supplies the half the Village actually states, and `examiner.py` supplies
the other half and refuses when they do not line up.

READ AT CHECK TIME, NOT CACHED
==============================

A production model change should be visible on the next battery, not on the next restart. The file
is small and the read is once per battery, against a battery that costs a minute of GPU.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.config import settings


class VillageConfigError(Exception):
    """The Village's model declaration could not be read. Never a battery's fault, and never
    silently a match either."""


@dataclass(frozen=True, slots=True)
class VillageAgentModel:
    """What the Village declares its agents run on."""

    tag: str
    #: The full key path that produced the tag - `mate.ollama_model_routes.agent` when the route
    #: named it directly, `mate.models.<type>.model_id` when it went through the indirection. Kept
    #: whole rather than as a bare name so a refusal can say WHICH declaration it read; the two
    #: forms live in different places and "default_llm" alone would not say which.
    route: str
    source_path: str
    #: Generation settings the Village declares. Reported, not enforced: SimForge examines at
    #: temperature 0.0 for determinism, and an exam whose answers move between runs is not a
    #: certification. That difference is a real one and it is ADR-0061's open question, not a
    #: silent divergence — `examiner.py` surfaces it and does not refuse on it.
    settings: dict = field(default_factory=dict)


def read_village_agent_model(path: str | Path | None = None) -> VillageAgentModel:
    """The model the Village declares for `agent`-mode calls. Raises rather than defaulting.

    Every failure here is a refusal to guess: an unreadable config, a missing route, a route
    pointing at a model block that is not there. A default would make SimForge assert a match
    against a value it invented, which is the one outcome ruling 1 exists to prevent.
    """
    configured = str(path) if path is not None else settings.village_config_path
    if not configured:
        raise VillageConfigError(
            "VILLAGE_CONFIG_PATH is not set, so SimForge cannot see which model the Village runs "
            "its agents on. The examiner is the production model (ADR-0061), and a battery that "
            "cannot check that is a battery whose certification claims something nobody verified. "
            "Point it at the Village's config.yaml."
        )
    config_path = Path(configured)
    if not config_path.exists():
        raise VillageConfigError(f"VILLAGE_CONFIG_PATH does not exist: {config_path}")

    try:
        with open(config_path, encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise VillageConfigError(f"could not read {config_path}: {exc}") from exc

    mate = raw.get("mate") or {}
    routes = mate.get("ollama_model_routes") or {}
    route = routes.get("agent")
    if not route:
        raise VillageConfigError(
            f"{config_path} declares no `mate.ollama_model_routes.agent`. That is the route "
            "agent-mode calls take, and without it there is no production model to match."
        )

    models = mate.get("models") or {}
    block = models.get(route)

    if block is not None:
        tag = block.get("model_id")
        if not tag:
            raise VillageConfigError(
                f"{config_path}: `mate.models.{route}` carries no `model_id`."
            )
        resolved_via = f"mate.models.{route}.model_id"
    elif ":" in str(route):
        # The route names the tag directly. The live config.yaml does exactly this.
        tag = str(route)
        resolved_via = "mate.ollama_model_routes.agent"
    else:
        raise VillageConfigError(
            f"{config_path}: `mate.ollama_model_routes.agent` is {route!r} and "
            f"`mate.models.{route}` does not exist. The route resolves to nothing."
        )

    return VillageAgentModel(
        tag=str(tag),
        route=resolved_via,
        source_path=str(config_path),
        settings=_settings_for_tag(models, str(tag), preferred=block),
    )


def _settings_for_tag(models: dict, tag: str, *, preferred: dict | None) -> dict:
    """The generation settings declared for `tag`, wherever they are written.

    `preferred` is the block the route named, when it named one. Otherwise the tag is matched
    against every `models.*` entry's `model_id` — which is the only way to find the settings for a
    config whose route short-circuits the indirection, and the live file is one of those.

    Several blocks can name the same tag (`reasoning_llm` and `code_llm` both point at
    `deepseek-r1:32b` in the live file, at different temperatures). With no route to disambiguate,
    returning one of them arbitrarily would be an invention, so the ambiguity is reported as an
    absence: nothing is claimed rather than the wrong thing.
    """
    def _pick(block: dict) -> dict:
        return {k: block[k] for k in ("temperature", "max_tokens") if k in block}

    if preferred is not None:
        return _pick(preferred)

    matches = [b for b in models.values() if isinstance(b, dict) and b.get("model_id") == tag]
    return _pick(matches[0]) if len(matches) == 1 else {}


__all__ = ["VillageAgentModel", "VillageConfigError", "read_village_agent_model"]
