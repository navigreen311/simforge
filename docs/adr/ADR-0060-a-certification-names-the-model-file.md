# ADR-0060 — Certification runs on the local model, and a result names the model file

**Status:** accepted · **Decided by:** Ivan Green, 17 September 2026 · **Built by:** the coordinator
**Extends:** ADR-0054 (the examiner is named) · **Implements:** part of ADR-0058 ruling 1.
**Companion:** The Office PR #168 — the manifest half, which must merge first.

---

## The rulings

**1. Village agents run on local models in production, so certification runs on the local model.**

**2. A certification counts only if it was earned on the exact model the agent runs in
production: model name, model file (including size and quantization), and generation settings such
as temperature.**

**3. SimForge records all of that on every result. An agent whose model, file or settings change
must be re-certified.**

**4. A cloud provider stays optional, for practice runs or future use. Exam scenarios use made-up
data only.**

## What was wrong with what we had

ADR-0054 closed the gap between the provider we *configured* and the provider that *answered*, and
`agent_model` records the result: `ollama/llama3.1:8b`.

**That string is a label, and three different candidates produce it.** The same tag re-pulled at a
different quantization is a different weights file. The same file served at temperature 0.7 instead
of 0.0 is a different exam. Neither moves `agent_model` by one character, so a certification earned
under one reads as current under the other — which is the exact failure ADR-0054 named one level up
and did not follow down.

## What is recorded

    provider          ollama
    model             what the SERVER said answered, never what was asked for
    file_digest       the model FILE — Ollama's blob sha256
    file_size_bytes   the file's size, recorded beside the digest rather than trusted from the tag
    parameter_size    "8.0B" — the scale, which the file size alone does not give
    quantization      "Q4_K_M"
    settings          temperature, token cap, seed — what was SENT, not what a default implies
    fingerprint       a sha256 over all of the above

Two calls produce it: `/api/show` carries the quantization and parameter size, `/api/tags` carries
the digest and the byte count. Ollama splits the facts; `OllamaProvider.identity` is the join.

**The settings come from the runtime, not the provider**, and they are named constants
(`EXAM_TEMPERATURE`, `EXAM_MAX_TOKENS`) that `turn` now passes explicitly. A recorded default that
is only implied is a second place for the two to disagree. `top_p` is deliberately absent: the
runtime never sends one — `OllamaProvider` fixes it at 1.0 in its own options — and listing it here
would be this module asserting a value it does not control.

**`fingerprint` is what re-certification compares.** Ruling 3 is a string comparison or it is an
argument about which of six fields counts as a change.

## The decisions

**A `certified` outcome whose model identity is absent or incomplete is refused — 422, naming each
missing fact.** This is ruling 2 made checkable and it is the test Ivan asked for: a result with no
model identity is never reported as a pass. Refused at the gate-result path, so the run never
reaches PASS at all and there is no window in which a verdict exists that nobody can attribute.

Each fact is named separately because the three come from three different places; a caller told
only "incomplete" has to go and find out which.

**A result carrying no model FILE is held at `provisional`, not refused.** Ruling 4 keeps a cloud
provider available for practice runs, and a practice run is a real run about a real candidate. What
the absent file costs is the certification, not the record. `provisional` has meant exactly this
since the Rev-2 audit: not certified, not a failure. It is the fourth withhold, independent of the
other three.

**And it is a PROXY for ruling 2, which is stated rather than hidden.** The real test is "the same
model as production". SimForge cannot read the Village's model configuration — it lives in another
repository behind no seam — so what is checkable here is narrower: whether anything with a model
file on this machine answered at all. The rest of the rule is recorded, computable from
`fingerprint`, and **not enforced**. Naming the gap is the difference between a proxy and a claim.

**The identity is recorded on EVERY result, not only a certified one.** A failed run's candidate is
what makes the failure reproducible; a provisional hold's is often the reason it was held.

**A provider that cannot describe its candidate returns `None`, and that is the base-class
default.** A provider added later that forgets to override it fails closed: its outcomes are
refused at `certified` rather than certifying something nobody can name. `StubProvider` inherits
it, which is the same rule its ugly `stub` label already carried.

## What this found when it was run for real

Two facts, measured on this machine rather than reasoned about, both in the report:

**The production model is not installed here.** Village routes its agents to `phi4:latest`;
this machine's Ollama serves `gemma2`, `mistral`, `qwen2.5` and `llama3.1:8b`. SimForge's
`OLLAMA_AGENT_MODEL` defaults to the last of those. So the exam model and the production model
already differ, and before this ADR nothing recorded enough to notice.

**The settings differ too.** Village's `default_llm` runs at temperature 0.7 with a 4000-token cap;
the battery runs at 0.0 and 2048. Under ruling 2 that is a different exam, and it was invisible.

## What this does not decide

Whether SimForge should read the Village's model configuration directly, or receive it through a
seam, or have it declared on the curriculum. That is the missing half of ruling 2 and it is sized
in the report, not settled here.
