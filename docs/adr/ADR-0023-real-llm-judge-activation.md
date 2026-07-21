# ADR-0023 — Real LLM-judge activation (Ollama)

**Status:** Accepted (2026-07-21).

> Numbering note: the LLM-judge task originally reserved "ADR-0022", but that number was taken by
> the HSM signer providers ADR merged first (#26). This is ADR-0023.

## Context
The three LLM-judge dimensions — P7 (CX), C1 (breath coherence), C2 (soul stability) — were wired
for pluggable providers (ADR-0008) but ran on the **StubProvider** everywhere: a judge-aware stub
that returns a deterministic hash-derived score in [0.75, 0.95]. That keeps CI hermetic, but it is
**semantically blind** — it can't tell a strong interaction from a weak one. Before these scores are
used to tune Constitution thresholds we needed a first look at *real* judge signal, across all three
venture packs (greenstone, medlink-pro, caregrid), without giving up hermetic CI.

## Decision
1. **`auto` provider mode** — `LLM_JUDGE_PROVIDER=auto` (and `LLM_PROVIDER=auto`) resolves to the
   Ollama judge when `OLLAMA_BASE_URL` answers `GET /api/tags`, else the StubProvider. The
   reachability probe is cached per-process and only runs on the `auto` path, so the default (`stub`)
   never probes. **Defaults are unchanged** (`stub`), so CI stays hermetic and offline.
2. **Committed real-judge cache** — the canonical scenarios were scored once against a live
   `llama3.1:8b` in `record` mode; the resulting entries live in `tests/fixtures/llm_cache/` (keyed
   `sha256(canonicalize_json(request))`, provider+model-specific). CI replays them in
   `replay_strict` with **no live model**, so the real-judge path is exercised offline.
3. **First-signal report** — `docs/calibration/first-real-signal-2026-07-21.md`: a stub-vs-Ollama
   delta (identical inputs) + a temperature-0 calibration (3 runs/scenario, mean/stddev/min/max,
   stddev>0.1 flags), produced by `scripts/first-real-signal.py`.

## Findings (first signal)
- **The real judge discriminates where the stub can't.** The curt/weak-handling scenario scored
  **P7 = 0.20** on Ollama vs the stub's hash-derived **0.93** (Δ **−0.73**). Strong interactions
  score ~0.80–1.00 on both; the divergence is exactly on quality the stub can't see.
- **Stable at temperature 0.** Every dim had **stddev 0.000** across 3 runs — **0 flags**.
  `llama3.1:8b` is effectively deterministic for these judge prompts, so cached fixtures are a
  faithful stand-in and threshold tuning has a stable base.
- C1/C2 stay high on the canonical CCBs (pre==post, no fragmentation), as expected.

## Cost / latency
- One judge call (llama3.1:8b, local): **~0.9–1.6 s**, ~300–380 tokens. A full 15-dim eval adds 3
  such calls (~3–5 s of judge time) on top of the heuristic dims when the real judge is on.
- CI cost: **zero** — CI runs the stub (0 ms, no network); the committed cache replays the real
  judge offline. Real calls happen only when an operator sets `auto`/`ollama` locally.

## Rollback
- **Instant + config-only:** unset `LLM_JUDGE_PROVIDER` (or set `stub`) → back to the deterministic
  stub; no code change, no data migration. `auto` already self-heals: if Ollama is down, it falls
  back to stub.
- The committed cache and report are additive; deleting them affects nothing but the offline replay
  test and the calibration doc.

## Guardrails preserved
Sandbox-only, no Village writes, no integrated execution. No change to the Constitution, Pack
schema, or Jurisdiction engine. Only the judge *provider* changed — the P7/C1/C2 scorer logic and
rubric are untouched.

## Cross-references
ADR-0008 (pluggable providers + judge-aware stub + cache), ADR-0009 (canonicalization = cache keys),
`scripts/first-real-signal.py`, `docs/calibration/first-real-signal-2026-07-21.md`.
