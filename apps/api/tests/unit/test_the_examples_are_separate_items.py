"""The protocol's examples are separate items, not a sequence (ADR-0119).

Measured: all 9 unreadable answers in the 17:50 sitting were staged - 2 to 5
complete ACT·RECORD·CAVEAT blocks, never the same act twice. The examples
were five complete answers in a row, separated only by blank lines.

Layout only. What the protocol requires is pinned byte-for-byte below.
"""

from __future__ import annotations

import hashlib
import re

from src.services.operation.battery import (
    _ACT_RE,
    _CAVEAT_RE,
    _RECORD_RE,
    RESPONSE_EXAMPLE_CLAIM,
    RESPONSE_EXAMPLE_DECLINE_WITH_A_RECORD,
    RESPONSE_EXAMPLE_ESCALATE,
    RESPONSE_EXAMPLE_NONE,
    RESPONSE_EXAMPLE_REFUSE,
    RESPONSE_PROTOCOL,
    parse_answer,
)
from src.services.operation.rubric import RESPONSE_PROTOCOL_VERSION

INTRO = "Five separate examples follow."
EXAMPLES = (
    RESPONSE_EXAMPLE_NONE,
    RESPONSE_EXAMPLE_DECLINE_WITH_A_RECORD,
    RESPONSE_EXAMPLE_CLAIM,
    RESPONSE_EXAMPLE_REFUSE,
    RESPONSE_EXAMPLE_ESCALATE,
)
LABEL = re.compile(r"^--- Example (\d) of 5 ---$", re.M)
END = "--- End of examples ---"

#: sha256 of everything before the examples, at 6.0.0 on main (6de605e). The rules
#: an agent answers under did not move; only how the examples are laid out did.
RULES_SHA_UNCHANGED_SINCE_6 = "4ccf3268b71c6ef3fe18bfd29ce83ced4dd0c4f302f566b828b0d34f55d364ef"

#: ADR-0103's named enforcement: the rendered block is pinned to its version, so an
#: edit to the text without a bump fails here. Update both together, or neither.
PINNED = {
    "7.0.0": "2a48e56ef49c226be5b7152a1ee2d8f88811144ec8bb980df503eb6c8d6d4e49",
}


def _examples_region() -> str:
    return RESPONSE_PROTOCOL[RESPONSE_PROTOCOL.index(INTRO) :]


def test_each_example_is_labelled_in_order_and_the_run_is_closed() -> None:
    region = _examples_region()
    assert [int(n) for n in LABEL.findall(region)] == [1, 2, 3, 4, 5]
    for label_n, body in enumerate(EXAMPLES, start=1):
        label = f"--- Example {label_n} of 5 ---"
        assert region.index(label) < region.index(body), f"example {label_n} precedes its label"
    assert region.rstrip().endswith(END)


def test_no_two_example_acts_sit_without_a_divider_between_them() -> None:
    """The failure shape: two ACT lines with nothing but answers between them."""
    lines = _examples_region().splitlines()
    kinds = [
        "ACT" if _ACT_RE.match(x) else "DIV" if x.startswith("---") else None for x in lines
    ]
    marks = [k for k in kinds if k]
    for a, b in zip(marks, marks[1:], strict=False):
        assert not (a == "ACT" and b == "ACT"), "two example ACT lines with no divider between"


def test_a_divider_is_not_a_protocol_line() -> None:
    """A model that copies a divider writes OTHER, never a second ACT or RECORD."""
    for line in LABEL.findall(_examples_region()):
        divider = f"--- Example {line} of 5 ---"
        for pattern in (_ACT_RE, _RECORD_RE, _CAVEAT_RE):
            assert not pattern.match(divider)


def test_every_example_is_still_one_readable_answer() -> None:
    for body in EXAMPLES:
        assert not type(parse_answer(body)).__name__ == "ProtocolViolation"


def test_what_the_protocol_requires_did_not_move() -> None:
    rules = RESPONSE_PROTOCOL[: RESPONSE_PROTOCOL.index(INTRO)]
    assert hashlib.sha256(rules.encode()).hexdigest() == RULES_SHA_UNCHANGED_SINCE_6


def test_the_rendered_block_is_pinned_to_its_version() -> None:
    """ADR-0103: any change to what the agent reads bumps RESPONSE_PROTOCOL_VERSION."""
    assert RESPONSE_PROTOCOL_VERSION in PINNED, "a new version needs its text pinned here"
    digest = hashlib.sha256(RESPONSE_PROTOCOL.encode()).hexdigest()
    assert digest == PINNED[RESPONSE_PROTOCOL_VERSION], (
        "RESPONSE_PROTOCOL changed without a version bump (ADR-0103)"
    )
