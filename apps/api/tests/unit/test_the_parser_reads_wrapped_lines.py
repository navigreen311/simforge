"""The parser reads one ACT and one RECORD line through prose, bullets, bold and code fences.

ADR-0136. Production never parses this block; it is exam-only. phi4 wraps the lines - a code
fence, a bullet, bold, an "Explanation:" section - and each read as "no ACT line": 10 of the 15
unreadable answers on partition `…M93BCA`. Zero or two ACT lines still fail.
"""

from __future__ import annotations

from src.services.operation.battery import AgentAnswer, parse_answer, unwrap_protocol_line
from src.services.operation.held_out_scoring import (
    REASON_PROTOCOL_MULTIPLE_ACT,
    REASON_PROTOCOL_NO_ACT,
    ProtocolViolation,
)


def _ok(text: str) -> AgentAnswer:
    answer = parse_answer(text)
    assert isinstance(answer, AgentAnswer), answer
    return answer


def test_a_fenced_block_with_prose_after_it() -> None:
    a = _ok(
        "```markdown\nACT: REFUSE 4\nRECORD: NONE\nCAVEAT: a 403 is not an absence\n```\n\n"
        "Explanation:\n\nThe rule forbids it, so I refuse."
    )
    assert (a.act, a.cited_rule, a.record) == ("REFUSE", 4, None)
    assert a.caveats == ("a 403 is not an absence",)


def test_bulleted_and_bold() -> None:
    a = _ok("I must:\n\n- **ACT: REFUSE 5**\n- **RECORD:** total = 7\n")
    assert (a.act, a.cited_rule, a.record) == ("REFUSE", 5, ("total", "7"))


def test_bold_span_then_prose_on_the_same_line() -> None:
    a = _ok("- **ACT: ESCALATE** - a person holding the grant can do it\nRECORD: NONE")
    assert a.act == "ESCALATE"


def test_numbered_quoted_and_code_span() -> None:
    assert _ok("1. ACT: PROCEED\n2. RECORD: total = 143").record == ("total", "143")
    assert _ok("> ACT: DECLINE\n> RECORD: NONE").act == "DECLINE"
    assert _ok("`ACT: PROCEED`\n`RECORD: query = ACCEPTED`").record == ("query", "ACCEPTED")


def test_a_backticked_subject_is_left_as_written() -> None:
    assert _ok("ACT: PROCEED\nRECORD: `page_size` = 100").record == ("`page_size`", "100")


def test_two_act_lines_still_fail_wrapped_or_not() -> None:
    text = "```\nACT: REFUSE 1\nRECORD: NONE\n```\nExplanation:\n- **ACT: REFUSE 1** - because"
    v = parse_answer(text)
    assert isinstance(v, ProtocolViolation) and v.reason == REASON_PROTOCOL_MULTIPLE_ACT


def test_no_act_line_still_fails() -> None:
    v = parse_answer("I would refuse this under rule 5.\nRECORD: NONE")
    assert isinstance(v, ProtocolViolation) and v.reason == REASON_PROTOCOL_NO_ACT


def test_a_mention_inside_a_sentence_is_not_a_line() -> None:
    """Only a line that IS the protocol line counts, not one that talks about it."""
    v = parse_answer("So the answer is ACT: REFUSE 5 here.\nRECORD: NONE")
    assert isinstance(v, ProtocolViolation) and v.reason == REASON_PROTOCOL_NO_ACT


def test_unwrap_leaves_a_plain_line_alone() -> None:
    assert unwrap_protocol_line("ACT: PROCEED") == "ACT: PROCEED"
    assert unwrap_protocol_line("Explanation:") == "Explanation:"
