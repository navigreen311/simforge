"""No battery request ever carries a `role: assistant` message.

WHY THIS TEST EXISTS
====================

An assistant prefill - seeding the reply with `ACT:` so the model continues from it - would make
every answer parse. **The conformance number would go to 11/11 and it would be measuring a
constrained decode, not whether the agent holds the protocol.** It is the one instrument error in
this family that produces a *better-looking* result, so nothing about the output would invite a
second look: the number would be exactly the number a capable model produces honestly.

No prefill was ever sent - the battery's messages carry `role: "scenario"`, which
`to_chat_messages` maps to `user`. This test exists so that stays true, because the failure is
invisible in the result and the fix is a one-line temptation whenever a model answers badly.

Assistant prefill also returns a 400 on every current Claude model, so on Anthropic it would fail
loudly today. That is a property of the vendor's API, not of this repository, and it does not hold
for Ollama - which is where a prefill would silently work.
"""

from __future__ import annotations

import inspect

from src.services.agent_runtime.llm_client import to_chat_messages
from src.services.operation import battery


def test_the_battery_sends_only_scenario_turns() -> None:
    """The role the runner puts on the wire, read off the runner rather than assumed."""
    source = inspect.getsource(battery.run_module_battery)
    assert '"role": "scenario"' in source, "the battery's message role moved - re-check this test"
    assert '"role": "assistant"' not in source
    assert '"role": "agent"' not in source


def test_scenario_turns_never_become_assistant_turns() -> None:
    """`to_chat_messages` is the single mapping point, and `scenario` maps to `user`."""
    chat = to_chat_messages("sys", [{"role": "scenario", "content": "probe text"}])
    roles = [m["role"] for m in chat]
    assert roles == ["system", "user"]
    assert "assistant" not in roles


def test_no_message_the_battery_builds_carries_an_assistant_role() -> None:
    """The whole message list, end to end, for both providers' mapping.

    `agent` is the only role that becomes `assistant`, and the battery never emits one - it puts a
    single probe per call and reads a single answer. A multi-turn battery would be a different
    design and would have to revisit this (ADR-0051 keeps one graded response per scenario).
    """
    built = to_chat_messages(
        battery.battery_system_context("m", ("Never do the thing.",)),
        [{"role": "scenario", "content": "the probe"}],
    )
    assert not [m for m in built if m["role"] == "assistant"], (
        "an assistant turn reached the wire - a prefill would make every answer parse and the "
        "conformance number would measure a constrained decode"
    )


def test_the_protocol_block_is_never_used_as_a_seed() -> None:
    """The grammar is shown as instruction, never as the opening of the model's own reply.

    `RESPONSE_PROTOCOL` belongs in the system context. If it ever appears in a message the model is
    told it already wrote, the model is completing its own template rather than choosing a format.
    """
    context = battery.battery_system_context("m", ("Never do the thing.",))
    assert battery.RESPONSE_PROTOCOL in context
    chat = to_chat_messages(context, [{"role": "scenario", "content": "the probe"}])
    non_system = [m for m in chat if m["role"] != "system"]
    for message in non_system:
        assert battery.RESPONSE_PROTOCOL not in message["content"]
        assert not message["content"].lstrip().startswith("ACT:")
