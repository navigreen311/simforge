"""gate_9_5_verdict contract: the code against the page (ADR-0111).

`docs/contracts/gate-9-5-verdict.md` names the shape. The Office records
it. This test reads the page, not a copy of it, so a change to either the
page or the code without the other fails here.
"""

from __future__ import annotations

import re
import typing
from pathlib import Path

import pydantic
import pytest

from src.models.held_out_partition import PARTITION_VERDICTS
from src.routers.office import MODULES
from src.schemas.operation_payloads import Gate95VerdictResponse
from src.services.operation.partition_verdict import RESPONSE_KEYS, WEAKNESS_ORDER

PAGE = Path(__file__).resolve().parents[4] / "docs" / "contracts" / "gate-9-5-verdict.md"
FORBIDDEN_FRAGMENTS = ("held_out", "heldout", "prompt", "scenarios")


def _page() -> str:
    return PAGE.read_text(encoding="utf-8")


def _answer_block() -> str:
    text = _page()
    section = text.split("## The answer", 1)[1].split("\n## ", 1)[0]
    return section.split("{", 1)[1].split("}", 1)[0]


def test_the_keys_are_the_pages_keys_in_order() -> None:
    keys = re.findall(r'"(\w+)":', _answer_block())
    assert keys == list(RESPONSE_KEYS)
    assert list(Gate95VerdictResponse.model_fields) == keys


def test_the_verdicts_are_the_pages_verdicts() -> None:
    line = next(ln for ln in _answer_block().splitlines() if '"verdict"' in ln)
    on_page = set(re.findall(r'"([A-Z_]+)"', line))
    annotation = Gate95VerdictResponse.model_fields["verdict"].annotation
    literal = next(a for a in typing.get_args(annotation) if a is not type(None))
    assert on_page == set(typing.get_args(literal))
    assert on_page == set(PARTITION_VERDICTS) == set(WEAKNESS_ORDER)


def test_the_weakness_order_is_the_pages_order() -> None:
    line = next(ln for ln in _page().splitlines() if "FAIL < TIMEOUT" in ln)
    order = tuple(v.strip(" .") for v in line.split("<"))
    assert order == WEAKNESS_ORDER


def test_no_key_carries_a_forbidden_fragment() -> None:
    for key in Gate95VerdictResponse.model_fields:
        for fragment in FORBIDDEN_FRAGMENTS:
            assert fragment not in key.lower()


def test_the_module_is_bound_as_a_read() -> None:
    spec = MODULES["gate_9_5_verdict"]
    assert spec.is_mutating is False
    assert spec.idempotency_support == "natural"


def test_a_fifth_key_is_refused() -> None:
    base = dict(zip(RESPONSE_KEYS, ("v", False, None, None), strict=True))
    Gate95VerdictResponse.model_validate(base)
    with pytest.raises(pydantic.ValidationError):
        Gate95VerdictResponse.model_validate({**base, "reason": "x"})
    with pytest.raises(pydantic.ValidationError):
        # verdict is null iff partition_exists is false.
        Gate95VerdictResponse.model_validate({**base, "verdict": "PASS"})
