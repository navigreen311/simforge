"""SimForge-internal agent runtime (blueprint §C.8).

Replicates the Village's layered system-prompt assembly so SimForge can exercise an agent
without touching the Village orchestrator. Village reads are best-effort: an agent missing
from the (dev) Village tree still runs with a minimal identity-based prompt.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.services.agent_runtime.llm_client import LLMProvider, LLMResponse
from src.services.village.reader import VillageReader, VillageReaderError


@dataclass
class AgentRuntime:
    village_reader: VillageReader
    provider: LLMProvider

    def _safe(self, fn, *args, default: dict | list | None = None):
        try:
            return fn(*args)
        except VillageReaderError:
            return default if default is not None else {}

    def assemble_system_prompt(
        self, agent_village_id: str, fallback_name: str = "", fallback_role: str = ""
    ) -> str:
        parts: list[str] = []

        # Layer 1 — base identity
        identity = self._safe(self.village_reader.get_agent_identity, agent_village_id)
        name = identity.get("name") or fallback_name or agent_village_id
        role = identity.get("role") or fallback_role or "Village agent"
        parts.append(f"You are {name}, a {role}.")
        if identity.get("backstory"):
            parts.append(f"Backstory: {identity['backstory']}")
        if identity.get("personality_traits"):
            parts.append("Personality traits: " + ", ".join(identity["personality_traits"]))

        # Layer 2 — BREATH
        breath = self._safe(self.village_reader.get_agent_breath, agent_village_id)
        if breath:
            comps = [c for c, v in breath.items() if v]
            if comps:
                parts.append("Core character (BREATH): " + ", ".join(comps) + ".")

        # Layer 3 — FOT (fresh-on-top pressure)
        fot = self._safe(self.village_reader.get_agent_fot, agent_village_id)
        if fot:
            parts.append(f"Current pressure (FOT): tier={fot.get('tier', 'unknown')}.")

        # Layer 4 — SOUL (emotional state)
        soul = self._safe(self.village_reader.get_agent_soul, agent_village_id)
        ledger = (soul or {}).get("ledger", {})
        if ledger:
            current = ledger.get("current", {})
            if current:
                parts.append(
                    "Emotional state (SOUL): "
                    f"{current.get('dominant_emotion', 'steady')}, valence "
                    f"{current.get('valence', 0.5)}."
                )

        # Layers 5–8 (comm style / meta-cog / org context / Level-10) — placeholders in v1.

        # Layer 9 — recent memory
        episodes = self._safe(self.village_reader.get_agent_episodes, agent_village_id, default=[])
        if episodes:
            parts.append("Recent episode: " + episodes[0].get("summary", ""))

        parts.append("Respond in character, naturally and professionally.")
        return "\n\n".join(parts)

    async def turn(
        self,
        agent_village_id: str,
        conversation_history: list[dict],
        seed: int,
        fallback_name: str = "",
        fallback_role: str = "",
    ) -> LLMResponse:
        system_prompt = self.assemble_system_prompt(agent_village_id, fallback_name, fallback_role)
        return await self.provider.complete(
            system=system_prompt, messages=conversation_history, seed=seed
        )
