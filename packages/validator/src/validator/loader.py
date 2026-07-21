"""Load a Pack directory (pack.yml + scenarios/*.yml) into typed specs with content hashes."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from validator.pack_schema import PackSpec
from validator.scenario_schema import ScenarioSpec


class PackLoadError(Exception):
    """Raised when a Pack directory cannot be loaded or parsed."""


@dataclass
class LoadedScenario:
    spec: ScenarioSpec
    yaml_path: str
    yaml_hash: str
    raw_text: str


@dataclass
class LoadedPack:
    spec: PackSpec
    pack_yaml_path: str
    pack_yaml_hash: str
    scenarios: list[LoadedScenario] = field(default_factory=list)

    @property
    def all_raw_text(self) -> str:
        return "\n".join(s.raw_text for s in self.scenarios)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_pack(pack_dir: Path) -> LoadedPack:
    pack_dir = Path(pack_dir)
    pack_yml = pack_dir / "pack.yml"
    if not pack_yml.exists():
        raise PackLoadError(f"pack.yml not found in {pack_dir}")

    pack_text = pack_yml.read_text(encoding="utf-8")
    try:
        pack_data = yaml.safe_load(pack_text) or {}
    except yaml.YAMLError as exc:  # noqa: BLE001
        raise PackLoadError(f"invalid YAML in {pack_yml}: {exc}") from exc

    spec = PackSpec.model_validate(pack_data)

    loaded = LoadedPack(
        spec=spec,
        pack_yaml_path=str(pack_yml),
        pack_yaml_hash=_sha256(pack_text),
    )

    scen_dir = pack_dir / "scenarios"
    if scen_dir.exists():
        for scen_file in sorted(scen_dir.glob("*.yml")) + sorted(scen_dir.glob("*.yaml")):
            text = scen_file.read_text(encoding="utf-8")
            data = yaml.safe_load(text) or {}
            scen_spec = ScenarioSpec.model_validate(data)
            loaded.scenarios.append(
                LoadedScenario(
                    spec=scen_spec,
                    yaml_path=str(scen_file),
                    yaml_hash=_sha256(text),
                    raw_text=text,
                )
            )

    return loaded
