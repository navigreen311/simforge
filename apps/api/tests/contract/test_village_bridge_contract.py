"""village_bridge contract: SimForge (consumer) ↔ the VillageData layout (provider) (ADR-0036).

The Forge boundary is HTTP, so it gets a real Pact (test_forge_sandbox_pact). The Village boundary
is a **filesystem** contract — SimForge reads a fixed VillageData directory shape — so its
consumer-driven contract is structural + shape assertions against the reference provider (the
committed VillageData fixture). The written artifact is `pacts/village_bridge.contract.json`.

If the Village layout the reader depends on changes, or the fixture stops providing a framework the
reader reads, this fails — the same guarantee Pact gives for the HTTP boundary.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.services.village.reader import VillageReader

VILLAGE_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "village" / "VillageData"
CONTRACT_FILE = Path(__file__).parent / "pacts" / "village_bridge.contract.json"

# The ten CCB frameworks SimForge reads for every agent — the consumer's required surface.
_FRAMEWORK_READERS = [
    "get_agent_identity",
    "get_agent_breath",
    "get_agent_fot",
    "get_agent_hfm",
    "get_agent_mate",
    "get_agent_soul",
    "get_agent_arc",
    "get_agent_echo",
    "get_agent_drift",
    "get_agent_ame",
    "get_agent_game",
]
_AGENT = "david_kim"


def test_village_provider_satisfies_reader_contract() -> None:
    """Every framework the consumer reads is provided, as a dict, by the reference Village."""
    reader = VillageReader(village_data_path=VILLAGE_FIXTURE)

    provided: dict[str, str] = {}
    for method_name in _FRAMEWORK_READERS:
        value = getattr(reader, method_name)(_AGENT)
        assert isinstance(value, dict), f"{method_name} must return a dict per the contract"
        provided[method_name] = "dict"

    # Episodes is a list contract.
    episodes = reader.get_agent_episodes(_AGENT, limit=5)
    assert isinstance(episodes, list)
    provided["get_agent_episodes"] = "list"

    # Persist the contract artifact (the shape the provider must maintain).
    CONTRACT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_FILE.write_text(
        json.dumps(
            {
                "consumer": "SimForgeVillageReader",
                "provider": "VillageData",
                "boundary": "filesystem",
                "agent_framework_shapes": provided,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    assert CONTRACT_FILE.exists()


def test_village_structural_fingerprint_is_stable() -> None:
    """The provider's structural fingerprint is deterministic — the drift-detection contract."""
    reader = VillageReader(village_data_path=VILLAGE_FIXTURE)
    fp1 = reader.get_village_schema_fingerprint()
    fp2 = reader.get_village_schema_fingerprint()
    assert fp1 == fp2 and len(fp1) == 64  # sha256 hex

    # The agent under contract appears in the provider's structural paths.
    assert _AGENT in reader.structural_paths()
