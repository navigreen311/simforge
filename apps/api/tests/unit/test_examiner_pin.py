"""The examiner pin (ADR-0061 ruling 1): the production model, by digest, never a moving tag.

Five refusals, five different fixes. They are tested one at a time because a single
`examiner_not_acceptable` would send an operator to the wrong file — an unpinned digest is a
config gap, an unreachable model is a deployment fact, and a moved tag is a real drift event.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.config import settings
from src.services.agent_runtime.examiner import (
    EXAMINER_NOT_PINNED,
    EXAMINER_NOT_PRODUCTION_MODEL,
    EXAMINER_PRODUCTION_SETTINGS_UNKNOWN,
    EXAMINER_PRODUCTION_UNKNOWN,
    EXAMINER_SETTINGS_NOT_PRODUCTION,
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
    declared = read_village_agent_model(_village_config(tmp_path), forge_id="cre-forge")

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

    declared = read_village_agent_model(path, forge_id="cre-forge")

    assert declared.tag == "phi4:latest"
    assert declared.route == "mate.ollama_model_routes.agent"
    assert declared.settings == {"temperature": 0.7, "max_tokens": 4000}


_LIVE_WITH_TASKS = (
    "agent_tasks:\n"
    "  default_temperature: 0.7\n"
    "  temperature_by_forge:\n"
    "    cre-forge: 0.0\n"
    "mate:\n"
    "  ollama_model_routes:\n"
    "    agent: phi4:latest\n"
    "  models:\n"
    "    default_llm:\n"
    "      model_id: phi4:latest\n"
    "      max_tokens: 4000\n"
    "      temperature: 0.7\n"
    "    reasoning_llm:\n"
    "      model_id: deepseek-r1:32b\n"
    "      temperature: 0.3\n"
)


def _tasks_config(tmp_path: Path, text: str = _LIVE_WITH_TASKS) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_a_cre_forge_exam_reads_cre_forges_task_temperature(tmp_path: Path) -> None:
    """B136 (Ivan Green, 18 and 19 October 2026): cre-forge at 0.0, max_tokens kept."""
    declared = read_village_agent_model(_tasks_config(tmp_path), forge_id="cre-forge")

    assert declared.settings == {"temperature": 0.0, "max_tokens": 4000}
    assert declared.temperature_from == "agent_tasks.temperature_by_forge.cre-forge"
    assert declared.forge_id == "cre-forge"


def test_a_forge_not_listed_reads_the_default_temperature(tmp_path: Path) -> None:
    """Every other Forge stays at 0.7 until it is re-certified on its own."""
    declared = read_village_agent_model(_tasks_config(tmp_path), forge_id="capitalforge")

    assert declared.settings == {"temperature": 0.7, "max_tokens": 4000}
    assert declared.temperature_from == "agent_tasks.default_temperature"
    assert declared.forge_id == "capitalforge"


def test_no_default_temperature_reads_the_mate_block_as_before(tmp_path: Path) -> None:
    """The fallback the operator shares: an unlisted Forge with no default reads 0.7."""
    path = _tasks_config(tmp_path, _LIVE_WITH_TASKS.replace("  default_temperature: 0.7\n", ""))

    declared = read_village_agent_model(path, forge_id="capitalforge")

    assert declared.settings == {"temperature": 0.7, "max_tokens": 4000}
    assert declared.temperature_from == "mate.models.default_llm.temperature"


def test_no_agent_tasks_block_reads_the_mate_block_for_every_forge(tmp_path: Path) -> None:
    text = _LIVE_WITH_TASKS[_LIVE_WITH_TASKS.index("mate:"):]
    for forge in ("cre-forge", "capitalforge"):
        declared = read_village_agent_model(_tasks_config(tmp_path, text), forge_id=forge)
        assert declared.settings == {"temperature": 0.7, "max_tokens": 4000}
        assert declared.temperature_from == "mate.models.default_llm.temperature"


def test_one_temperature_for_every_forge_is_refused(tmp_path: Path) -> None:
    """The first shape of B136, never deployed, would examine every Forge at one value."""
    path = _tasks_config(tmp_path, "agent_tasks:\n  temperature: 0.0\n" + _LIVE_WITH_TASKS[
        _LIVE_WITH_TASKS.index("mate:"):])

    with pytest.raises(VillageConfigError, match="per Forge"):
        read_village_agent_model(path, forge_id="cre-forge")


def test_a_read_that_names_no_forge_is_refused(tmp_path: Path) -> None:
    with pytest.raises(VillageConfigError, match="names no Forge"):
        read_village_agent_model(_tasks_config(tmp_path), forge_id="")


@pytest.mark.parametrize(
    ("old", "new", "key"),
    [
        ("cre-forge: 0.0", "cre-forge: '0.0'", "temperature_by_forge.cre-forge"),
        ("cre-forge: 0.0", "cre-forge: true", "temperature_by_forge.cre-forge"),
        ("default_temperature: 0.7", "default_temperature: [0.7]", "default_temperature"),
    ],
)
def test_a_task_temperature_that_is_not_a_number_raises(
    tmp_path: Path, old: str, new: str, key: str
) -> None:
    path = _tasks_config(tmp_path, _LIVE_WITH_TASKS.replace(old, new))
    forge = "cre-forge" if "cre-forge" in key else "capitalforge"

    with pytest.raises(VillageConfigError, match=re.escape(f"agent_tasks.{key}")):
        read_village_agent_model(path, forge_id=forge)


def test_the_examiner_is_at_production_for_its_own_forge_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An examiner at 0.0 sits cre-forge and is refused for a Forge declared at 0.7."""
    monkeypatch.setattr(settings, "exam_model_tag", "phi4:latest")
    monkeypatch.setattr(settings, "exam_model_digest", PHI4_DIGEST)
    monkeypatch.setattr(settings, "village_config_path", str(_tasks_config(tmp_path)))
    at_zero = _phi4(settings={"temperature": 0.0, "max_tokens": 4000, "seed": 0})
    at_seven = _phi4(settings={"temperature": 0.7, "max_tokens": 4000, "seed": 0})

    assert check_examiner(at_zero, forge_id="cre-forge").ok
    assert check_examiner(at_seven, forge_id="capitalforge").ok
    assert check_examiner(at_zero, forge_id="capitalforge").reason == (
        EXAMINER_SETTINGS_NOT_PRODUCTION
    )
    assert check_examiner(at_seven, forge_id="cre-forge").reason == (
        EXAMINER_SETTINGS_NOT_PRODUCTION
    )


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

    assert read_village_agent_model(path, forge_id="cre-forge").settings == {}


def test_a_route_that_names_a_tag_directly_is_accepted(tmp_path: Path) -> None:
    """Some deployments skip the indirection. Refusing a legal shape would be this reader
    asserting a convention rather than reading a value."""
    path = tmp_path / "config.yaml"
    path.write_text(
        "mate:\n  ollama_model_routes:\n    agent: phi4:latest\n", encoding="utf-8"
    )
    assert read_village_agent_model(path, forge_id="cre-forge").tag == "phi4:latest"


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
        read_village_agent_model(path, forge_id="cre-forge")


# --- the five refusals --------------------------------------------------------------------------


def test_an_unpinned_examiner_is_refused(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    monkeypatch.setattr(settings, "exam_model_digest", "")
    monkeypatch.setattr(settings, "village_config_path", _village_config(tmp_path))

    verdict = check_examiner(_phi4(), forge_id="cre-forge")

    assert verdict.reason == EXAMINER_NOT_PINNED
    assert "EXAM_MODEL_DIGEST" in verdict.detail


def test_a_model_that_cannot_describe_itself_is_refused(pinned) -> None:  # noqa: ANN001
    """`None` is what a provider returns when it has no file to name — a stub, or a tag that is
    not pulled on this host. A model that cannot be described cannot be pinned."""
    verdict = check_examiner(None, forge_id="cre-forge")

    assert verdict.reason == EXAMINER_UNREACHABLE


def test_a_tag_that_moved_under_its_pin_is_refused(pinned) -> None:  # noqa: ANN001
    """**The reason the pin is a digest and not a tag.** `phi4:latest` re-pulled over different
    weights is the same string and a different model; nothing in the name would change."""
    verdict = check_examiner(_phi4(file_digest="sha256:" + "ab" * 32), forge_id="cre-forge")

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
    , forge_id="cre-forge")

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

    verdict = check_examiner(_phi4(), forge_id="cre-forge")

    assert verdict.reason == EXAMINER_PRODUCTION_UNKNOWN
    assert "not the same as matching it" in verdict.detail


# --- the pass, and the one difference it does NOT refuse ----------------------------------------


def test_a_pinned_production_model_at_production_settings_passes(pinned) -> None:  # noqa: ANN001
    """The whole check, satisfied: right model, right file, right settings."""
    verdict = check_examiner(
        _phi4(settings={"temperature": 0.7, "max_tokens": 4000, "seed": 0}), forge_id="cre-forge"
    )

    assert verdict.ok
    assert verdict.reason is None
    assert verdict.village_tag == "phi4:latest"
    assert verdict.village_settings == {"temperature": 0.7, "max_tokens": 4000}
    assert verdict.settings_divergence is None


def test_an_exam_at_steadier_settings_than_production_is_refused(pinned) -> None:  # noqa: ANN001
    """**ADR-0062 turned this from a note into a refusal.**

    ADR-0061 surfaced the difference and let the battery proceed, on the grounds that an exam at
    0.7 does not repeat. Ivan settled it the other way: an exam at a steadier setting than
    production certifies an agent that is not the one doing the work, and the repeatability is
    bought by sitting the exam three times instead.
    """
    verdict = check_examiner(
        _phi4(settings={"temperature": 0.0, "max_tokens": 2048, "seed": 0}), forge_id="cre-forge"
    )

    assert verdict.reason == EXAMINER_SETTINGS_NOT_PRODUCTION
    assert verdict.settings_divergence == {
        "temperature": {"village": 0.7, "exam": 0.0},
        "max_tokens": {"village": 4000, "exam": 2048},
    }


def test_a_village_that_declares_no_settings_is_refused(monkeypatch, tmp_path) -> None:  # noqa: ANN001
    """Settings nobody stated cannot be matched. The live file reaches this whenever two
    `mate.models` blocks name one tag, which is reported as an absence rather than guessed at."""
    path = tmp_path / "config.yaml"
    path.write_text(
        "mate:\n  ollama_model_routes:\n    agent: phi4:latest\n", encoding="utf-8"
    )
    monkeypatch.setattr(settings, "exam_model_tag", "phi4:latest")
    monkeypatch.setattr(settings, "exam_model_digest", PHI4_DIGEST)
    monkeypatch.setattr(settings, "village_config_path", str(path))

    verdict = check_examiner(_phi4(), forge_id="cre-forge")

    assert verdict.reason == EXAMINER_PRODUCTION_SETTINGS_UNKNOWN
    assert "cannot be matched" in verdict.detail
