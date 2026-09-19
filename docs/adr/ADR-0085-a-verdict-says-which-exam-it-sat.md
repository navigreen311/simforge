# ADR-0085 — A verdict says which exam it sat

**Status:** accepted · **Decided by:** Ivan Green, 19 September 2026 · **Built.**
**Follows:** [ADR-0084](ADR-0084-a-live-process-is-not-an-up-to-date-one.md), whose read-only found
the marker already stored.

---

## The ruling

**The six verdicts stay as they are. They were correct measurements and are not revoked. A verdict
is shown with the protocol version it was earned under, so a result from two majors ago describes
itself instead of reading as a current judgment.**

---

## Why nothing is revoked

`revoked` means **voided** — a content-hash mismatch, drift, a misoperation incident. The six
Greenstone verdicts of 18 September are none of those. phi4 genuinely failed those probes, and
ADR-0068's 8 → 0 RECORD result was measured on them.

Marking them revoked would make the record say the verdicts were invalid when they were correct,
which is the third time this repository has ruled against rewriting a recorded result's basis —
after the model-identity seed and the collapse measure.

## The fact was already there and nothing read it

Every attempt record carries `response_protocol_version`. The six carry **3.0.0**; the protocol is
at **4.0.0** and the naming design will make it 5.0.0. *"Earned under a protocol two majors ago"* has
been in the database since the day it happened.

`protocol_versions_of(exam_attempts)` reads it, and both of SimForge's own reads now carry
`response_protocol_versions` beside the verdict — `views.py`'s per-agent module view and
`battery_result_for`'s second read.

**A list, not a string.** Three attempts could in principle disagree, if a process were restarted
mid-exam across a protocol change. One entry is the normal case; two is a finding, and collapsing
to the first would hide it.

## Why this retires them better than a column would

ADR-0084's read-only sized three options: leave them, add a `supersededBy` column, or revoke. This
is none of them and costs less than all three.

A `supersededBy` column would have to be **written** for each retired verdict, by a script somebody
remembers to run. The protocol version is **already written**, by the run that earned it, and it
retires every future verdict automatically the moment the protocol moves. **A marker that has to be
applied is one that can be forgotten.**

## Not covered

The frontend does not show it yet — `OperationCertCard` renders the state, the spread and the
withhold reasons, and this is one more line of the same kind. The API carries it.
