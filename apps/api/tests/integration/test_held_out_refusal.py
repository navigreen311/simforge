"""P-05b — the refusal, which is the one part of the isolation the engine CAN prove about itself.

`GATE_9_5_FLAG` says the engine cannot self-prove that whoever authors the held-out set is isolated
from whoever could leak it. That is true and P-05 said so. **But whether this service hands the
corpus to a caller is a question about this service**, and it is answerable — by being refused, with
a credential, against a running app, rather than asserted in a docstring.

ADR-0050's ruling: *no credential fetches the held-out set. Not `forge_owner`, not the founder.*
The reasoning is what constrains the design rather than merely permitting it:

    An endpoint returning the corpus makes isolation a function of who holds a token, and a strong
    enough role gets everything — ADR-0048's refusal undone one endpoint over.

WHY THE DEV PRINCIPAL MAKES THIS THE STRONGEST FORM OF THE TEST, NOT THE WEAKEST
===============================================================================

`src/auth/dev.py` gives the test principal **all eight roles**, and `Principal.has_role` answers
True to anything once `admin` is present. A reader could take that as "these tests run with auth
switched off, so a 403 proves nothing".

**It is the opposite.** The refusal being asserted is unconditional — it reads no role at all — so
the meaningful demonstration is that the *most privileged principal the system can construct* is
refused. A test that refused a `viewer` and stopped would have proved only that the weak are weak.
This one hands the route `admin`, `founder`, `forge_owner` and five more at once and gets the same
answer, which is exactly the property Ivan's ruling asks for and the one a role check could never
have.
"""

from __future__ import annotations

from httpx import AsyncClient

from src.auth.dev import ALL_ROLES
from src.services.operation.held_out import (
    HELD_OUT_CONTENT_REFUSED,
    author_for_module,
    inventory,
)
from tests.unit.test_held_out_authoring import PORTFOLIO_HEALTH_NEVER_DO

FORGE = "capitalforge"
MODULE = "portfolio_health"
SCENARIOS_URL = f"/api/operation/held-out/{FORGE}/{MODULE}/scenarios"
INVENTORY_URL = f"/api/operation/held-out/{FORGE}/{MODULE}"


# =================================================================================================
# THE REFUSAL — an actual request, an actual refusal, an actual assertion
# =================================================================================================


async def test_a_request_for_held_out_content_is_refused(client: AsyncClient) -> None:
    """The route exists in order to say no, and it says no with a reason and an ADR number.

    **A 404 here would have been the wrong answer**, and the difference is not pedantic: a 404 reads
    as "not built yet" and invites the next author to build it, which is the construction the ruling
    forbids. A 403 naming ADR-0050 is the decision, left where somebody looking for the corpus will
    find it instead of the corpus.
    """
    res = await client.get(SCENARIOS_URL)

    assert res.status_code == 403, res.text
    detail = res.json()["detail"]
    assert detail["error"] == HELD_OUT_CONTENT_REFUSED
    assert detail["adr"] == "ADR-0050"
    assert "never returned to any caller, at any role" in detail["message"]
    assert detail["inspectable_instead"] == INVENTORY_URL


async def test_the_most_privileged_principal_in_the_system_is_refused(
    client: AsyncClient,
) -> None:
    """*Not `forge_owner`, not the founder.* Asserted against the caller that holds BOTH, and six
    more besides.

    The response echoes the roles the refused caller actually held, so this test reads what the
    route saw rather than what the fixture intended — a principal that had somehow been narrowed
    would show up here as a weaker claim rather than pass as a strong one.
    """
    res = await client.get(SCENARIOS_URL)
    roles_held = set(res.json()["detail"]["roles_held"])

    assert res.status_code == 403
    assert roles_held == ALL_ROLES, (
        "the point of this assertion is that the caller was maximally privileged; if the fixture "
        "ever stops granting every role, this test would silently become the weak version of itself"
    )
    assert {"admin", "founder", "forge_owner", "compliance_analyst"} <= roles_held


async def test_the_refusal_body_carries_no_scenario_content(client: AsyncClient) -> None:
    """A refusal that leaked the thing it refused would be worse than no refusal, because it would
    read as a control. Checked by value against the set the pipeline really authors for this
    module."""
    res = await client.get(SCENARIOS_URL)
    body = res.text

    authored = author_for_module(MODULE, PORTFOLIO_HEALTH_NEVER_DO)
    assert authored, "a vacuous set would make every assertion below true and measure nothing"
    for scenario in authored:
        assert scenario.probe not in body
        assert scenario.expected_behavior not in body
        assert scenario.obligation_ref not in body


async def test_the_refusal_does_not_depend_on_the_module_existing(client: AsyncClient) -> None:
    """Refused before anything is looked up, for a module with no instruction set at all.

    This matters because the alternative implementation — look the module up, author its set, then
    decline to return it — would have had a window in which the corpus existed in the handler. It
    never does: the refusal is the whole handler, and it touches no session.
    """
    res = await client.get("/api/operation/held-out/nonexistent-forge/nonexistent-module/scenarios")

    assert res.status_code == 403
    assert res.json()["detail"]["error"] == HELD_OUT_CONTENT_REFUSED


# =================================================================================================
# THE INSPECTION SURFACE — counts and a digest, and nothing that could carry a probe
# =================================================================================================


async def _seed(client: AsyncClient, never_do: list[str]) -> None:
    """Put a real instruction set in the table the honest way: submit a curriculum, which is what
    persists `ForgeInstructionSet.neverDo`. Inserting the row directly would test the inventory
    against a fixture rather than against what the submission path actually stores."""
    body = {
        "instruction_set_ref": {
            "forge_id": FORGE,
            "module_id": MODULE,
            "instruction_version": "1.0.0",
            "forge_api_version": "1.0.0",
            "content_hash": "sha256:" + "h" * 8,
        },
        "certification_units_requested": [
            {
                "unit_type": "agent_operation",
                "forge_id": FORGE,
                "agent_id": "taylor_zhang",
                "module_id": MODULE,
            }
        ],
        "operation_scenarios": [
            {
                "scenario_class": c,
                "module_id": MODULE,
                "instruction_section": "correct_sequence",
                "expected_behavior": "reports what the response says and stops there",
                "expected_escalation": "none",
            }
            for c in ("happy_path", "permission_denied")
        ],
        "coverage_declaration": {
            "modules_in_forge": 11,
            "modules_covered": 1,
            "modules_uncovered": [],
            "functions_in_module": 0,
            "functions_covered": 0,
        },
        "module_never_do": {MODULE: never_do},
        "module_not_applicable": {
            MODULE: {
                c: (
                    "It takes no identifier and writes nothing, so this class has no honest "
                    "content at any level of effort."
                )
                for c in (
                    "escalation_required",
                    "malformed_input",
                    "partial_failure",
                    "rate_limited",
                    "recovery_after_failure",
                )
            }
        },
    }
    res = await client.post("/api/operation/curriculum", json=body)
    assert res.status_code == 200, res.text


async def test_the_inventory_reports_counts_that_match_what_was_authored(
    client: AsyncClient,
) -> None:
    """*"Eleven scenarios exist for this module" is inspectable.* Seven and five here, and the
    counts
    are checked against the pipeline rather than against a literal — a hardcoded 12 would keep
    passing if the authoring changed and the endpoint stopped describing it."""
    await _seed(client, list(PORTFOLIO_HEALTH_NEVER_DO))
    res = await client.get(INVENTORY_URL)

    assert res.status_code == 200, res.text
    body = res.json()
    expected = inventory(MODULE, PORTFOLIO_HEALTH_NEVER_DO)

    assert body["obligations_declared"] == 7
    assert body["by_class"] == {"never_do_violation": 7, "silent_failure": 5}
    assert body["scenarios_authored"] == expected.scenarios_authored == 12
    assert body["digest"] == expected.digest
    assert body["digest"].startswith("sha256:")
    assert "held_out_authoring_is_a_process_control" in body["gate_9_5_flag"]


async def test_the_inventory_carries_no_probe_and_no_key(client: AsyncClient) -> None:
    """*"Here they are" is the exam.* The inventory response is searched by value for every held-out
    field of every scenario it is counting."""
    await _seed(client, list(PORTFOLIO_HEALTH_NEVER_DO))
    body = (await client.get(INVENTORY_URL)).text

    authored = author_for_module(MODULE, PORTFOLIO_HEALTH_NEVER_DO)
    assert authored
    for scenario in authored:
        assert scenario.probe not in body
        assert scenario.expected_behavior not in body
        assert scenario.expected_escalation not in body
        assert scenario.obligation_ref not in body
        for reading in scenario.unsupported_readings:
            assert f'"{reading}"' not in body


async def test_the_inventory_response_has_no_field_that_could_hold_content(
    client: AsyncClient,
) -> None:
    """A schema-level claim, not a body-level one. The body of one response could be clean by
    accident; a response model with no content field cannot carry one on any input."""
    from src.schemas.operation_payloads import HeldOutInventoryResponse

    assert set(HeldOutInventoryResponse.model_fields) == {
        "forge_id",
        "module_id",
        "obligations_declared",
        "scenarios_authored",
        "by_class",
        "digest",
        "gate_9_5_flag",
    }
    assert HeldOutInventoryResponse.model_fields["by_class"].annotation == dict[str, int], (
        "counts, keyed by class. A dict[str, str] here would be a content field wearing a "
        "counts-shaped name"
    )


async def test_a_module_with_no_never_do_list_reports_zero_rather_than_an_error(
    client: AsyncClient,
) -> None:
    """Zero obligations is an answer. `never_do.STATUS_NONE` has meant "genuinely not applicable"
    since FIX 2, and an inventory that 404'd here would make a correct absence look like a missing
    module."""
    await _seed(client, [])
    body = (await client.get(INVENTORY_URL)).json()

    assert body["obligations_declared"] == 0
    assert body["scenarios_authored"] == 0
    assert body["by_class"] == {}
