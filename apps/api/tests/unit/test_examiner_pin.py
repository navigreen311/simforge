"""The examiner pin (ADR-0061 ruling 1): the production model, by digest, never a moving tag.

Five refusals, five different fixes. They are tested one at a time because a single
`examiner_not_acceptable` would send an operator to the wrong file — an unpinned digest is a
config gap, an unreachable model is a deployment fact, and a moved tag is a real drift event.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import settings
from src.services.agent_runtime.examiner import (
    EXAMINER_NOT_PINNED,
    EXAMINER_NOT_PRODUCTION_MODEL,
    EXAMINER_PRODUCTION_UNKNOWN,
    EXAMINER_TAG_MOVED,
    EXAMINER_UNREACHABLE,
    check_examiner,
)
from src.services.agent_runtime.model_identity import ModelIdentity
from src.services.village.model_config import VillageConfigError, read_village_agent_model

#: The real values from this machine's `phi4:latest`, so the fixture is the shape Ollama returns.
PHI4_DIGEST = "sha256:ac896e5b8b34a1f4efa7b14d7520725140d5512484457fab45d2a4ea14c69dba"


def _phi4(**over: object) -> ModelIdentity:
    fields: dict = {
        "provider": "ollama",
        "model": "phi4:latest",
        "file_digest": PHI4_DIGEST,
        "file_size_bytes": 9053116391,
        "parameter_size": "14.7B",
        "quantization": "Q4_K_M",
        "settings": {"temperature": 0.0, "max_tokens": 2048, "seed": 0},
    }
    fields.update(over)
    return ModelIdentity(**fields)  # type: ignore[arg-type]


def _village_config(tmp_path: Path, *, tag: str = "phi4:latest", temperature: float = 0.7) -> str:
    """The Village's own two-hop declaration, written the way its `config.yaml` writes it."""
    path = tmp_path / "config.yaml"
    path.write_text(
        "mate:\n"
        "  ollama_model_routes:\n"
        "    phone: phi3.5:3.8b\n"
        "    agent: default_llm\n"
        "  models:\n"
        "    default_llm:\n"
        f"      model_id: {tag}\n"
        "      max_tokens: 4000\n"
        f"      temperature: {temperature}\n",
        encoding="utf-8",
    )
    return str(path)


@pytest.fixture
def pinned(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr(settings, "exam_model_tag", "phi4:latest")
    monkeypatch.setattr(settings, "exam_model_digest", PHI4_DIGEST)
    monkeypatch.setattr(settings, "village_config_path", _village_config(tmp_path))


# --- the Village's half -------------------------------------------------------------------------


def test_the_declared_model_is_read_through_the_indirection(tmp_path: Path) -> None:
    """`agent` can name a model TYPE, and the type names the tag. Reading one hop gives the wrong
    answer: the first alone yields `default_llm`, which is not a model."""
    declared = read_village_agent_model(_village_config(tmp_path))

    assert declared.tag == "phi4:latest"
    assert declared.route == "mate.models.default_llm.model_id"
    assert declared.settings == {"temperature": 0.7, "max_tokens": 4000}


def test_the_live_shape_names_the_tag_in_the_route_and_still_finds_its_settings(
    tmp_path: Path,
) -> None:
    """**The shape the real config.yaml uses, and the one that nearly reported `{}`.**

    `mate.ollama_model_routes.agent` holds `phi4:latest` directly, while the settings still live
    under `mate.models.default_llm`. Looking for settings only on the indirect path would make
    "no divergence" mean "did not look" - which is the false negative the whole comparison exists
    to avoid. Caught by running it against the live file before the code was finished.
    """
    path = tmp_path / "config.yaml"
    path.write_text(
        "mate:\n"
        "  ollama_model_routes:\n"
        "    web: phi4:latest\n"
        "    agent: phi4:latest\n"
        "  models:\n"
        "    default_llm:\n"
        "      model_id: phi4:latest\n"
        "      max_tokens: 4000\n"
        "      temperature: 0.7\n"
        "    reasoning_llm:\n"
        "      model_id: deepseek-r1:32b\n"
        "      temperature: 0.3\n",
        encoding="utf-8",
    )

    declared = read_village_agent_model(path)

    assert declared.tag == "phi4:latest"
    assert declared.route == "mate.ollama_model_routes.agent"
    assert declared.settings == {"temperature": 0.7, "max_tokens": 4000}


def test_an_ambiguous_tag_reports_no_settings_rather_than_the_wrong_ones(
    tmp_path: Path,
) -> None:
    """Two blocks name one tag at different temperatures - the live file does this with
    `deepseek-r1:32b`. With no route to disambiguate, picking one would be an invention."""
    path = tmp_path / "config.yaml"
    path.write_text(
        "mate:\n"
        "  ollama_model_routes:\n"
        "    agent: deepseek-r1:32b\n"
        "  models:\n"
        "    reasoning_llm:\n"
        "      model_id: deepseek-r1:32b\n"
        "      temperature: 0.3\n"
        "    code_llm:\n"
        "      model_id: deepseek-r1:32b\n"
        "      temperature: 0.1\n",
        encoding="utf-8",
    )

    assert read_village_agent_model(path).settings == {}


def test_a_route_that_names_a_tag_directly_is_accepted(tmp_path: Path) -> None:
    """Some deployments skip the indirection. Refusing a legal shape would be this reader
    asserting a convention rather than reading a value."""
    path = tmp_path / "config.yaml"
    path.write_text(
        "mate:\n  ollama_model_routes:\n    agent: phi4:latest\n", encoding="utf-8"
    )
    assert read_village_agent_model(path).tag == "phi4:latest"


@pytest.mark.parametrize(
    "body",
    [
        "mate: {}\n",  # no routes at all
        "mate:\n  ollama_model_routes:\n    agent: default_llm\n  models: {}\n",  # dead route
        "mate:\n  ollama_model_routes:\n    agent: default_llm\n"
        "  models:\n    default_llm:\n      temperature: 0.7\n",  # no model_id
    ],
)
def test_every_unreadable_declaration_raises_rather_than_defaulting(
    tmp_path: Path, body: str
) -> None:
    """A default here would make SimForge assert a match against a value it invented, which is the
    one outcome the ruling exists to prevent."""
    path = tmp_path / "config.yaml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(VillageConfigError):
        read_village_agent_model(path)


# --- the five refusals --------------------------------------------------------------------------


def test_an_unpinned_examiner_is_refused(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    monkeypatch.setattr(settings, "exam_model_digest", "")
    monkeypatch.setattr(settings, "village_config_path", _village_config(tmp_path))

    verdict = check_examiner(_phi4())

    assert verdict.reason == EXAMINER_NOT_PINNED
    assert "EXAM_MODEL_DIGEST" in verdict.detail


def test_a_model_that_cannot_describe_itself_is_refused(pinned) -> None:  # noqa: ANN001
    """`None` is what a provider returns when it has no file to name — a stub, or a tag that is
    not pulled on this host. A model that cannot be described cannot be pinned."""
    verdict = check_examiner(None)

    assert verdict.reason == EXAMINER_UNREACHABLE


def test_a_tag_that_moved_under_its_pin_is_refused(pinned) -> None:  # noqa: ANN001
    """**The reason the pin is a digest and not a tag.** `phi4:latest` re-pulled over different
    weights is the same string and a different model; nothing in the name would change."""
    verdict = check_examiner(_phi4(file_digest="sha256:" + "ab" * 32))

    assert verdict.reason == EXAMINER_TAG_MOVED
    assert "re-pulled" in verdict.detail


def test_an_examiner_that_is_not_the_production_model_is_refused(
    monkeypatch, tmp_path  # noqa: ANN001
) -> None:
    """The Village runs phi4; examining on llama3.1 would certify an agent that does not exist."""
    monkeypatch.setattr(settings, "exam_model_tag", "llama3.1:8b")
    monkeypatch.setattr(settings, "exam_model_digest", "sha256:" + "46" * 32)
    monkeypatch.setattr(settings, "village_config_path", _village_config(tmp_path))

    verdict = check_examiner(
        _phi4(model="llama3.1:8b", file_digest="sha256:" + "46" * 32)
    )

    assert verdict.reason == EXAMINER_NOT_PRODUCTION_MODEL
    assert "phi4:latest" in verdict.detail and "llama3.1:8b" in verdict.detail
    assert verdict.village_tag == "phi4:latest"


def test_an_unreadable_village_config_is_refused_rather_than_assumed(
    monkeypatch,  # noqa: ANN001
) -> None:
    """**Not being able to see production is not the same as matching it.**

    The tempting alternative — enforce the local pin, skip the comparison — leaves the
    certification still asserting it was earned on the production model, with the only change
    being that nobody checked.
    """
    monkeypatch.setattr(settings, "exam_model_digest", PHI4_DIGEST)
    monkeypatch.setattr(settings, "village_config_path", "")

    verdict = check_examiner(_phi4())

    assert verdict.reason == EXAMINER_PRODUCTION_UNKNOWN
    assert "not the same as matching it" in verdict.detail


# --- the pass, and the one difference it does NOT refuse ----------------------------------------


def test_a_pinned_production_model_passes(pinned) -> None:  # noqa: ANN001
    verdict = check_examiner(_phi4())

    assert verdict.ok
    assert verdict.reason is None
    assert verdict.village_tag == "phi4:latest"


def test_a_settings_difference_is_surfaced_and_never_refused(pinned) -> None:  # noqa: ANN001
    """The Village runs its agents at 0.7; the exam runs at 0.0, because an exam whose answers move
    between runs is not a certification. That tension is real and the ruling does not settle it, so
    it is reported and the battery proceeds. Refusing here would settle it by implication.
    """
    verdict = check_examiner(_phi4())

    assert verdict.ok
    assert verdict.settings_divergence == {
        "temperature": {"village": 0.7, "exam": 0.0},
        "max_tokens": {"village": 4000, "exam": 2048},
    }


def test_matching_settings_report_no_divergence(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    monkeypatch.setattr(settings, "exam_model_tag", "phi4:latest")
    monkeypatch.setattr(settings, "exam_model_digest", PHI4_DIGEST)
    monkeypatch.setattr(
        settings, "village_config_path", _village_config(tmp_path, temperature=0.0)
    )

    verdict = check_examiner(_phi4(settings={"temperature": 0.0, "max_tokens": 4000}))

    assert verdict.ok
    assert verdict.settings_divergence is None
