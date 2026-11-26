"""The examiner the integration tests pin, as the record a held-out sitting carries.

The Office decisions entry 355: Gate 9.5 counts only sittings graded at the five facts
`examiner_settings.settings_now` states, and a row that records no examiner matches nothing. Tests
that seed `HeldOutPartitionVerdict` rows directly seed them AT the examiner
`test_operation_battery_run._examiner_pinned` pins - the scripted model, its fake digest, and the
Village declaration it writes - so they keep testing what they were written to test.

Built from the same pieces the grader uses (`ScriptedProvider.identity`, `exam_settings_from`),
not written out, so a change to either moves this with it.
"""

from __future__ import annotations

from src.services.agent_runtime.model_identity import ModelIdentity
from src.services.agent_runtime.runtime import exam_settings_from
from tests.integration.test_operation_battery_run import EXAM_SETTINGS

SCRIPTED_DIGEST = "sha256:" + "5c" * 32


def at_examiner(**settings_override: object) -> dict:
    """The record of a sitting graded by the pinned examiner, optionally at other settings."""
    return ModelIdentity(
        provider="scripted",
        model="scripted",
        file_digest=SCRIPTED_DIGEST,
        file_size_bytes=4_920_753_328,
        parameter_size="8.0B",
        quantization="Q4_K_M",
        settings={**exam_settings_from(EXAM_SETTINGS), **settings_override},
    ).as_record()


AT_EXAMINER = at_examiner()
