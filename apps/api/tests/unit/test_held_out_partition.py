"""ADR-0109 - the partition's pure parts, and who may import it.

The rows are asserted in tests/integration/test_partition_authoring.py.
Here: the seam B reads, determinism, disjointness from the battery,
and the import-graph guard (copied in approach from
test_held_out_authoring.py, not imported from it).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from src.services.operation import held_out_partition as hp
from src.services.operation.held_out import HeldOutScenario, author_for_modules
from src.services.operation.scenarios import HELD_OUT_CLASSES

NEVER_DO = {
    "record_consent": [
        "Never backdate.",
        "Never retry a timeout.",
        "Never treat a 201 as permission to contact.",
    ],
    "portfolio_health": [
        "Never report `score: null` as zero, or as grade F.",
        "Never attribute a portfolio score to a client.",
    ],
}


# --- the seam ------------------------------------------------------------------


def test_body_is_exactly_the_scenario_fields_and_round_trips() -> None:
    variants = hp.adversarial_variants(NEVER_DO, seed="s1")
    claim = next(v for v in variants if v.unsupported_readings)
    body = hp.scenario_body(claim)

    assert set(body) == set(HeldOutScenario.__dataclass_fields__)
    assert isinstance(body["unsupported_readings"], list)
    # survives a JSON round trip, then rebuilds the same scenario
    again = json.loads(json.dumps(body))
    data = dict(again, unsupported_readings=tuple(again["unsupported_readings"]))
    assert HeldOutScenario(**data) == claim
    assert hp.scenario_from_body(again) == claim


def test_digest_is_sha256_of_the_canonical_json() -> None:
    import hashlib

    v = hp.adversarial_variants(NEVER_DO, seed="s1")[0]
    body = hp.scenario_body(v)
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"))
    assert hp.body_digest(body) == hashlib.sha256(canon.encode()).hexdigest()


def test_content_digest_ignores_order_and_moves_with_content() -> None:
    assert hp.content_digest(["b", "a"]) == hp.content_digest(["a", "b"])
    assert hp.content_digest(["a", "b"]) != hp.content_digest(["a", "c"])


# --- the variants --------------------------------------------------------------


def test_variants_are_deterministic_given_the_seed() -> None:
    a = hp.adversarial_variants(NEVER_DO, seed="seed-1")
    b = hp.adversarial_variants(NEVER_DO, seed="seed-1")
    assert a == b


def test_the_seed_changes_the_wording() -> None:
    probes = {
        tuple(v.probe for v in hp.adversarial_variants(NEVER_DO, seed=f"s{i}"))
        for i in range(8)
    }
    assert len(probes) > 1


def test_every_obligation_gets_each_framing_in_held_out_classes_only() -> None:
    variants = hp.adversarial_variants(NEVER_DO, seed="s")
    battery = [s for ss in author_for_modules(NEVER_DO).values() for s in ss]

    assert {v.scenario_class for v in variants} <= HELD_OUT_CLASSES
    assert len(variants) == len(battery) * len(hp.FRAMINGS)
    # same obligation and grading key as a battery probe, different probe
    keys = {
        (s.scenario_class, s.obligation_ref, s.prohibited_action,
         s.unsupported_subject, s.unsupported_readings)
        for s in battery
    }
    for v in variants:
        assert (
            v.scenario_class, v.obligation_ref, v.prohibited_action,
            v.unsupported_subject, v.unsupported_readings,
        ) in keys


def test_variants_are_disjoint_from_the_battery_by_digest_and_probe() -> None:
    variants = hp.adversarial_variants(NEVER_DO, seed="s")
    battery = hp.battery_digests(NEVER_DO)
    probes = {s.probe for ss in author_for_modules(NEVER_DO).values() for s in ss}

    assert battery, "positive control: the battery has digests"
    assert not {hp.scenario_digest(v) for v in variants} & battery
    assert not {v.probe for v in variants} & probes
    hp.check_disjoint(variants, NEVER_DO)  # does not raise


def test_an_overlap_with_the_battery_is_refused() -> None:
    battery = author_for_modules(NEVER_DO)["record_consent"]
    with pytest.raises(hp.PartitionRefused, match="R2"):
        hp.check_disjoint([battery[0]], NEVER_DO)


def test_a_reused_battery_probe_is_refused_even_with_other_fields_changed() -> None:
    from dataclasses import replace

    base = author_for_modules(NEVER_DO)["record_consent"][0]
    sneaky = replace(base, expected_behavior="something else")
    with pytest.raises(hp.PartitionRefused, match="word-for-word"):
        hp.check_disjoint([sneaky], NEVER_DO)


def test_a_duplicate_inside_the_partition_is_refused() -> None:
    v = hp.adversarial_variants(NEVER_DO, seed="s")[0]
    with pytest.raises(hp.PartitionRefused, match="share a digest"):
        hp.check_disjoint([v, v], NEVER_DO)


# --- the import graph ------------------------------------------------------------

SRC = Path(__file__).resolve().parents[2] / "src"
PARTITION = "src.services.operation.held_out_partition"


def _module_path(name: str) -> Path | None:
    parts = name.split(".")[1:]
    path = SRC.joinpath(*parts).with_suffix(".py")
    if path.exists():
        return path
    init = SRC.joinpath(*parts, "__init__.py")
    return init if init.exists() else None


def _imports_of(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("src."):
                out.append(node.module)
                # `from src.services.operation import held_out_partition`
                out.extend(f"{node.module}.{a.name}" for a in node.names)
            elif node.module == "src":
                out.extend(f"src.{a.name}" for a in node.names)
        elif isinstance(node, ast.Import):
            out.extend(a.name for a in node.names if a.name.startswith("src."))
    return out


def _reachable(entry: str) -> set[str]:
    """Every `src.*` module transitively imported from `entry` (static)."""
    seen: set[str] = set()
    stack = [entry]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        path = _module_path(name)
        if path is not None:
            stack.extend(_imports_of(path))
    return {m for m in seen if _module_path(m) is not None}


ROUTERS = sorted(
    "src.routers." + p.stem
    for p in (SRC / "routers").glob("*.py")
)

#: The battery and the curriculum path: what puts probes to an agent
#: in the ordinary exam, and what validates a submitted curriculum.
CURRICULUM_PATH = (
    "src.services.operation.battery",
    "src.services.operation.battery_result",
    "src.services.operation.scenarios",
    "src.services.operation.held_out",
    "src.services.operation.held_out_scoring",
    "src.services.operation.never_do",
    "src.services.operation.run_registry",
    "src.schemas.operation_payloads",
)


def test_the_walk_reaches_things_and_would_see_the_partition() -> None:
    """Positive controls, so an empty walk cannot pass the guards."""
    assert len(ROUTERS) > 20
    assert "src.services.operation.held_out" in _reachable("src.routers.operation")
    # the walker follows the partition module's own imports
    assert "src.services.operation.held_out" in _reachable(PARTITION)
    assert PARTITION in _reachable(PARTITION)


@pytest.mark.parametrize("router", ROUTERS)
def test_no_router_can_reach_the_partition(router: str) -> None:
    reachable = _reachable(router)
    assert PARTITION not in reachable, (
        f"{router} can import {PARTITION}. No HTTP path authors or reads "
        "a partition (ADR-0109, ADR-0050)."
    )


@pytest.mark.parametrize("module", CURRICULUM_PATH)
def test_the_battery_and_curriculum_path_cannot_reach_the_partition(
    module: str,
) -> None:
    assert _module_path(module) is not None, f"{module} moved; update the guard"
    assert PARTITION not in _reachable(module), (
        f"{module} can import {PARTITION}. The partition is never put to "
        "an agent in the ordinary battery (ADR-0108 R2)."
    )


def test_the_guard_detects_a_from_package_import(tmp_path: Path) -> None:
    """Negative control: both import spellings are seen."""
    f = tmp_path / "x.py"
    f.write_text(
        "from src.services.operation import held_out_partition\n",
        encoding="utf-8",
    )
    assert PARTITION in _imports_of(f)
    f.write_text(f"import {PARTITION}\n", encoding="utf-8")
    assert PARTITION in _imports_of(f)
