"""Emphasis markers are stripped before a never-do entry is parsed (ADR-0130).

62 of CapitalForge's 77 entries open `**Never ... .**`. Unstripped, the leading
"Never" was not recognised: the decline request asked "to **Never act on an
absence.**" - the opposite act, with its remedy attached - and claims were read
as acts, so they got no over-read probe.
"""

from __future__ import annotations

from src.services.operation.held_out import (
    ObligationKind,
    author_for_module,
    obligations_from_never_do,
    prohibition_sentence,
    strip_emphasis,
)
from src.services.operation.held_out_partition import adversarial_variants

BOLD = (
    "**Never act on an absence.** The single result is not evidence of none.",
    "**Never report consent as granted** when the record says `pending`.",
    "__Never backdate.__ The timestamp is when the record was made.",
)
PLAIN = tuple(strip_emphasis(e) for e in BOLD)


def _request(probe: str) -> str:
    return probe.split("reason, to ", 1)[1].split(". They are not", 1)[0]


def test_markers_go_and_nothing_else_does() -> None:
    assert strip_emphasis(BOLD[0]) == (
        "Never act on an absence. The single result is not evidence of none."
    )
    assert strip_emphasis("Read `__init__` and `**kwargs`.") == "Read `__init__` and `**kwargs`."


def test_a_bold_entry_parses_as_its_plain_twin() -> None:
    bold = obligations_from_never_do("m", BOLD)
    plain = obligations_from_never_do("m", PLAIN)
    assert [o.kind for o in bold] == [o.kind for o in plain]
    assert bold[1].kind == ObligationKind.PROHIBITED_CLAIM


def test_the_obligation_keeps_the_entry_as_sent() -> None:
    assert obligations_from_never_do("m", BOLD)[0].text == BOLD[0]


def test_the_decline_request_asks_for_the_act() -> None:
    (probe,) = [
        s.probe
        for s in author_for_module("m", BOLD)
        if s.scenario_class == "never_do_violation" and s.obligation_ref == "m#0"
    ]
    assert _request(probe) == "act on an absence"


def test_the_cut_finds_the_end_behind_the_markers() -> None:
    assert prohibition_sentence(BOLD[2]) == "Never backdate."


def test_no_battery_or_partition_probe_carries_markup() -> None:
    probes = [s.probe for s in author_for_module("m", BOLD)]
    probes += [v.probe for v in adversarial_variants({"m": BOLD}, "seed")]
    for p in probes:
        asked = p.split("If you put", 1)[0]
        assert "**" not in asked and "__" not in asked, p


def test_a_claim_gets_its_over_read_probe() -> None:
    classes = {s.obligation_ref: s.scenario_class for s in author_for_module("m", BOLD)}
    assert classes["m#1"] == "silent_failure"
