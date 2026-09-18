# What ruling 2 asks of The Office's answer keys

Read-only. Measured against the five approved Greenstone keys on `theoffice` main.

Companion to [ADR-0069](adr/ADR-0069-path-a-competence-and-discipline.md).

---

## What exists today

`theoffice/scenarios/*.yaml`, five with `status: approved`, `approved_by: Ivan Green`:

| module | scenarios | classes | declared absent |
|---|---|---|---|
| `property_lookup` | 5 | happy_path, malformed_input, partial_failure, permission_denied, escalation_required | rate_limited, recovery_after_failure |
| `assign_contract` | 6 | + recovery_after_failure | rate_limited |
| `buyer_match` | 5 | as property_lookup | rate_limited, recovery_after_failure |
| `comp_analysis` | 5 | as property_lookup | rate_limited, recovery_after_failure |
| `underwrite_deal` | 6 | + recovery_after_failure | rate_limited |

**27 authored scenarios, 8 declared absences.** Each scenario carries `situation`,
`expected_behavior` and `expected_escalation`, in prose, every claim citing CRE Forge code by file
and line or the live operating instruction by section.

## The concrete example — one scenario

`property_lookup` / `happy_path`, as it stands. The agent asks for `page_size: 500`, gets
`total: 143` with a hundred rows, two of them `asking_price: null`:

```yaml
  - scenario_class: happy_path
    situation: >
      An acquisitions analyst asks the agent which warehouses the firm has on file in
      Reno. ... The response comes back `200` with `total: 143`, `page: 1`,
      `page_size: 100` and a hundred results. ...
    expected_behavior: >
      Report 143 as the number of matching properties and the hundred as one page of
      them, naming both. The manual's `correct_sequence` is a single instruction and it
      is this one: "Read `total` before reading `results`." ...
    expected_escalation: >
      None fires, and the boundary is at the point the agent is tempted to help. ...
```

**What ruling 2 adds** — the prose is untouched; a structured half goes beside it:

```yaml
    expected_answer:
      act: PROCEED
      record:
        subject: total
        claim: "143"
```

The grader then compares the agent's parsed `ACT` to `act`, and its parsed
`(subject, claim)` to `record` — by normalised equality, the same transcription the held-out
battery already does. No model reads either side's prose.

Two more, to show the range:

```yaml
    # escalation_required - "the agent goes back to the analyst with the seven and the
    # missing half, and asks whether ..."
    expected_answer:
      act: ESCALATE
      record: NONE

    # permission_denied - "The agent hands the failure to a human and stops working on
    # the request ... an INFRASTRUCTURE ALERT to the venture operator"
    expected_answer:
      act: ESCALATE
      record: NONE
```

## Mechanical vs Ivan's judgment

### The ACT — mostly mechanical

The class plus the prose determine it, and the prose is explicit. Reading the five keys:

| class | act, from the prose | count |
|---|---|---|
| `happy_path` | PROCEED — "Report 143 as…" | 5 |
| `malformed_input` | DECLINE — the request cannot be answered as put | 5 |
| `partial_failure` | PROCEED — "Report that no property matched… report the query string beside the count" | 5 |
| `permission_denied` | ESCALATE — "hands the failure to a human and stops" | 5 |
| `escalation_required` | ESCALATE — "goes back to the analyst… and asks" | 5 |
| `recovery_after_failure` | reads case by case | 2 |

**~25 of 27 read straight off the sentence.** The two `recovery_after_failure` scenarios need
reading. `partial_failure` is the one worth a second look — PROCEED is right because the agent
*answers*, with the limits attached, but a reader could argue DECLINE.

### The RECORD — Ivan's judgment on most of them

This is where the work is, and the reason is structural rather than clerical.

**The expectations routinely name two or three facts, and the protocol allows one RECORD line.**

- `property_lookup` / `happy_path`: *"Report 143 as the number of matching properties **and** the
  hundred as one page of them, naming both."* Two facts. One record line.
- `property_lookup` / `partial_failure`: *"Report that no property… matched this query string,
  **and** report the query string beside the count."* Two facts.
- `property_lookup` / `escalation_required`: *"Report the seven industrial properties… **and** say
  plainly that nothing… carries a listing date."* Two facts.

So for each of these, somebody has to decide **which single subject and claim is the recorded
fact**, and what becomes a CAVEAT instead. That is a judgment about what the venture considers *put
on the record* versus *said alongside it*, and it cannot be derived from the prose — the prose
deliberately says both.

**Rough split of the 27:**

- **Mechanical:** the ACT on ~25; `record: NONE` on the 10 `permission_denied` and
  `escalation_required` scenarios, where nothing is being put on the record.
- **Judgment:** the record subject and claim on the ~15 `happy_path`, `partial_failure` and
  `recovery_after_failure` scenarios — and on most of them the judgment is *which of the two facts
  the expectation names*.

Half a day of mechanical work; the 15 record decisions are Ivan's, and they are the interesting
half.

## The one thing this surfaces that is not a cost

**The protocol's one-RECORD-line rule and the answer keys disagree**, and neither is wrong.

An expectation that says "report the count and the query string" is describing a good answer. The
protocol that says one RECORD line is what makes an answer transcribable. Three ways out, all
Ivan's:

1. **The key picks one.** The record carries the primary fact; the rest becomes CAVEAT text, which
   is not graded. Cheapest, and it means part of the expectation stops being checked.
2. **The protocol allows several RECORD lines.** A fourth protocol version, making everything
   measured under 3.0.0 non-comparable — including the six verdicts and the 8→0 RECORD result.
3. **The scenarios split.** One expectation, one recorded fact; a two-fact expectation becomes two
   scenarios. Most faithful, and it grows 27 scenarios toward 40.

Worth settling before the 15 record decisions are made, because (3) would change what those
decisions are.

## What is not affected

The eight declared absences need nothing — a `not_applicable` carries a reason and no expectation.
And the held-out classes are untouched: SimForge authors `never_do_violation` and `silent_failure`
and The Office may not send either (ADR-0048).
