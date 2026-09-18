"""SimForge-internal agent runtime (blueprint §C.8).

Replicates the Village's layered system-prompt assembly so SimForge can exercise an agent
without touching the Village orchestrator. Village reads are best-effort: an agent missing
from the (dev) Village tree still runs with a minimal identity-based prompt.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.services.agent_runtime.llm_client import (
    LLMProvider,
    LLMResponse,
    get_agent_llm,
    get_exam_llm,
)
from src.services.agent_runtime.model_identity import ModelIdentity
from src.services.village.reader import VillageReader, VillageReaderError

#: The settings a turn runs under when the CALLER supplies none. Scenario runs, demos and the
#: scenario bank use these; **an exam does not** (ADR-0062).
#:
#: They were `EXAM_TEMPERATURE` / `EXAM_MAX_TOKENS` and were exactly wrong for an exam: 0.0 is
#: steadier than production, and an agent examined at a steadier setting than it works at is not
#: the agent doing the work. The battery now passes the Village's own declared values through
#: `AgentRuntime.generation`, and these stay as what a non-exam caller gets.
#:
#: `top_p` is deliberately NOT here. The runtime never sends one - `OllamaProvider` fixes it at 1.0
#: in its own options block - so listing it here would be this module asserting a value it does not
#: control, which is the shape of every drift this repo has recorded.
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_TOKENS = 2048


def build_agent_runtime(village_reader: VillageReader) -> AgentRuntime:
    """Construct an AgentRuntime with the configured agent-runtime LLM provider (ADR-0008)."""
    return AgentRuntime(village_reader=village_reader, provider=get_agent_llm())


def build_exam_runtime(village_reader: VillageReader) -> AgentRuntime:
    """A runtime pinned to the EXAMINER, which is not the same thing as the agent runtime.

    `get_agent_llm()` resolves `LLM_PROVIDER` and `OLLAMA_AGENT_MODEL` - settings that exist for
    scenario runs, demos and the scenario bank. The examiner is a different question with a
    different answer (ADR-0061): it is the model Village agents run on, pinned by digest, and it
    must not be changeable by a setting that was turned for something else.

    So the exam names its own model. `check_examiner` then decides whether that model may sit the
    exam at all - this function only makes sure the battery is asking for the right one rather
    than for whatever the last demo left configured.
    """
    return AgentRuntime(village_reader=village_reader, provider=get_exam_llm())


@dataclass
class AgentRuntime:
    village_reader: VillageReader
    provider: LLMProvider
    #: The generation settings every turn of THIS runtime is put under, or `None` for the module
    #: defaults. The battery sets it to the Village's declared production settings and nothing
    #: else does — which is why it is a field rather than an argument to `turn`: a setting that
    #: could differ between two turns of one exam would make the exam two exams.
    generation: dict | None = None

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
        extra_system: str = "",
    ) -> LLMResponse:
        """One agent turn.

        `extra_system` is appended to the assembled Village prompt as a final layer. It exists for
        the operation battery, which has to put the module's OPERATING CONTEXT to the agent — the
        module it is working and the standing prohibitions it is working under — without that
        context becoming part of the agent's Village identity. Appending rather than substituting
        matters: an agent examined under a prompt that had replaced its BREATH/FOT/SOUL layers
        would be a different agent from the one being certified.
        """
        sent = self.generation_settings(seed)
        system_prompt = self.assemble_system_prompt(agent_village_id, fallback_name, fallback_role)
        if extra_system:
            system_prompt = f"{system_prompt}\n\n{extra_system}"
        return await self.provider.complete(
            system=system_prompt,
            messages=conversation_history,
            # Passed explicitly rather than left to the provider's defaults, so the values
            # `generation_settings` records are the values this call sends. One source, not two
            # that agree today.
            temperature=sent["temperature"],
            max_tokens=sent["max_tokens"],
            seed=seed,
        )

    def generation_settings(self, seed: int) -> dict:
        """What `turn` sends, as the record ADR-0060 requires. One source, read twice.

        A caller-supplied `generation` wins over the module defaults, and a partial one is filled
        in rather than rejected: the Village declares `temperature` and `max_tokens` and says
        nothing about a seed, which is SimForge's to choose per attempt.
        """
        supplied = self.generation or {}
        return {
            "temperature": supplied.get("temperature", DEFAULT_TEMPERATURE),
            "max_tokens": supplied.get("max_tokens", DEFAULT_MAX_TOKENS),
            "seed": seed,
        }

    async def model_identity(self, seed: int) -> ModelIdentity | None:
        """The candidate that answered this runtime's turns, settings included.

        Asked of the provider rather than assembled here: only the provider can say what file it
        is serving, and only this runtime knows what it asked for. The two halves meet here and
        nowhere else.
        """
        return await self.provider.identity(self.generation_settings(seed))
