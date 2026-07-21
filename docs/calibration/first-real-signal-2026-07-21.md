# First real LLM-judge signal — 2026-07-21

- **Judge model:** `llama3.1:8b` via Ollama (`http://localhost:11434`)
- **Agent provider:** StubProvider (deterministic) — only the *judge* dims (P7/C1/C2) use the real LLM
- **Scope:** the 9 canonical scenarios across all three venture packs (greenstone, medlink-pro, caregrid)
- **Guardrails:** sandbox-only, no Village writes, no integrated execution; Constitution/Pack-schema/jurisdiction untouched

## 1. Delta — StubProvider vs. real Ollama judge (identical inputs)

Same `EvalContext` scored by each provider; delta = ollama − stub. The Stub judge returns a
hash-derived score in [0.75, 0.95] (deterministic but semantically blind); the Ollama judge
reads the transcript, so a genuinely weak interaction scores low.

| Scenario | Dim | Stub | Ollama | Δ |
|---|---|---|---|---|
| gs_foundational_clean | P7 (CX) | 0.806 | 0.900 | 0.094 |
| gs_foundational_clean | C1 (Breath coherence) | 0.817 | 0.800 | -0.017 |
| gs_foundational_clean | C2 (Soul stability) | 0.811 | 0.900 | 0.089 |
| gs_intermediate_negotiation | P7 (CX) | 0.932 | 0.900 | -0.032 |
| gs_intermediate_negotiation | C1 (Breath coherence) | 0.918 | 0.900 | -0.018 |
| gs_intermediate_negotiation | C2 (Soul stability) | 0.892 | 0.950 | 0.058 |
| gs_crisis_title_defect | P7 (CX) | 0.814 | 0.900 | 0.086 |
| gs_crisis_title_defect | C1 (Breath coherence) | 0.806 | 1.000 | 0.194 |
| gs_crisis_title_defect | C2 (Soul stability) | 0.832 | 0.900 | 0.068 |
| ml_foundational_credential | P7 (CX) | 0.921 | 0.800 | -0.121 |
| ml_foundational_credential | C1 (Breath coherence) | 0.810 | 0.800 | -0.010 |
| ml_foundational_credential | C2 (Soul stability) | 0.947 | 0.950 | 0.003 |
| ml_crisis_audit | P7 (CX) | 0.874 | 0.800 | -0.074 |
| ml_crisis_audit | C1 (Breath coherence) | 0.893 | 0.900 | 0.007 |
| ml_crisis_audit | C2 (Soul stability) | 0.761 | 0.950 | 0.189 |
| gs_foundational_weak_cx | P7 (CX) | 0.931 | 0.200 | -0.731 |
| gs_foundational_weak_cx | C1 (Breath coherence) | 0.758 | 0.500 | -0.258 |
| gs_foundational_weak_cx | C2 (Soul stability) | 0.940 | 0.900 | -0.040 |
| cg_foundational_credential | P7 (CX) | 0.811 | 0.900 | 0.089 |
| cg_foundational_credential | C1 (Breath coherence) | 0.897 | 0.900 | 0.003 |
| cg_foundational_credential | C2 (Soul stability) | 0.784 | 0.900 | 0.116 |
| cg_intermediate_placement | P7 (CX) | 0.792 | 0.900 | 0.108 |
| cg_intermediate_placement | C1 (Breath coherence) | 0.859 | 0.800 | -0.059 |
| cg_intermediate_placement | C2 (Soul stability) | 0.842 | 0.950 | 0.108 |
| cg_crisis_cdph_audit | P7 (CX) | 0.895 | 0.900 | 0.005 |
| cg_crisis_cdph_audit | C1 (Breath coherence) | 0.847 | 0.900 | 0.053 |
| cg_crisis_cdph_audit | C2 (Soul stability) | 0.937 | 0.950 | 0.013 |

### Spotlight: CareGrid crisis (`cg_crisis_cdph_audit`) — the 3-P0-gap scenario

| Dim | Stub | Ollama | Δ |
|---|---|---|---|
| P7 (CX) | 0.895 | 0.900 | 0.005 |
| C1 (Breath coherence) | 0.847 | 0.900 | 0.053 |
| C2 (Soul stability) | 0.937 | 0.950 | 0.013 |

## 2. Calibration — real Ollama judge stability (temperature 0)

Each scenario scored **3×** with the live judge, cache off. Flag any dim with
**stddev > 0.1** (a noisy prompt to refine).

| Scenario | Dim | Mean | Stddev | Min | Max | n |
|---|---|---|---|---|---|---|
| gs_foundational_clean | P7 (CX) | 0.900 | 0.000 | 0.900 | 0.900 | 3 |
| gs_foundational_clean | C1 (Breath coherence) | 0.800 | 0.000 | 0.800 | 0.800 | 3 |
| gs_foundational_clean | C2 (Soul stability) | 0.900 | 0.000 | 0.900 | 0.900 | 3 |
| gs_intermediate_negotiation | P7 (CX) | 0.900 | 0.000 | 0.900 | 0.900 | 3 |
| gs_intermediate_negotiation | C1 (Breath coherence) | 0.900 | 0.000 | 0.900 | 0.900 | 3 |
| gs_intermediate_negotiation | C2 (Soul stability) | 0.950 | 0.000 | 0.950 | 0.950 | 3 |
| gs_crisis_title_defect | P7 (CX) | 0.900 | 0.000 | 0.900 | 0.900 | 3 |
| gs_crisis_title_defect | C1 (Breath coherence) | 1.000 | 0.000 | 1.000 | 1.000 | 3 |
| gs_crisis_title_defect | C2 (Soul stability) | 0.900 | 0.000 | 0.900 | 0.900 | 3 |
| ml_foundational_credential | P7 (CX) | 0.800 | 0.000 | 0.800 | 0.800 | 3 |
| ml_foundational_credential | C1 (Breath coherence) | 0.800 | 0.000 | 0.800 | 0.800 | 3 |
| ml_foundational_credential | C2 (Soul stability) | 0.950 | 0.000 | 0.950 | 0.950 | 3 |
| ml_crisis_audit | P7 (CX) | 0.800 | 0.000 | 0.800 | 0.800 | 3 |
| ml_crisis_audit | C1 (Breath coherence) | 0.900 | 0.000 | 0.900 | 0.900 | 3 |
| ml_crisis_audit | C2 (Soul stability) | 0.950 | 0.000 | 0.950 | 0.950 | 3 |
| gs_foundational_weak_cx | P7 (CX) | 0.200 | 0.000 | 0.200 | 0.200 | 3 |
| gs_foundational_weak_cx | C1 (Breath coherence) | 0.500 | 0.000 | 0.500 | 0.500 | 3 |
| gs_foundational_weak_cx | C2 (Soul stability) | 0.900 | 0.000 | 0.900 | 0.900 | 3 |
| cg_foundational_credential | P7 (CX) | 0.900 | 0.000 | 0.900 | 0.900 | 3 |
| cg_foundational_credential | C1 (Breath coherence) | 0.900 | 0.000 | 0.900 | 0.900 | 3 |
| cg_foundational_credential | C2 (Soul stability) | 0.900 | 0.000 | 0.900 | 0.900 | 3 |
| cg_intermediate_placement | P7 (CX) | 0.900 | 0.000 | 0.900 | 0.900 | 3 |
| cg_intermediate_placement | C1 (Breath coherence) | 0.800 | 0.000 | 0.800 | 0.800 | 3 |
| cg_intermediate_placement | C2 (Soul stability) | 0.950 | 0.000 | 0.950 | 0.950 | 3 |
| cg_crisis_cdph_audit | P7 (CX) | 0.900 | 0.000 | 0.900 | 0.900 | 3 |
| cg_crisis_cdph_audit | C1 (Breath coherence) | 0.900 | 0.000 | 0.900 | 0.900 | 3 |
| cg_crisis_cdph_audit | C2 (Soul stability) | 0.950 | 0.000 | 0.950 | 0.950 | 3 |

### Flags (stddev > 0.1 → prompt refinement candidate)
- none — all judge dims stable at temperature 0

## 3. Cost / latency (observed)

- Per judge call (llama3.1:8b, local): ~0.9–1.6 s, ~300–380 tokens. Each run scores 3 dims → ~3–5 s of judge time per scenario.
- Calibration cost this report: 9 scenarios × 3 runs × 3 dims ≈ 81 live calls.
- CI is unaffected: it runs the StubProvider (0 ms, no network); the committed cache replays the real judge offline in `replay_strict`.

## 4. Reading the signal

- The real judge **discriminates on CX quality** where the stub cannot: weak/curt handling drops P7 sharply while the stub stays flat in [0.75, 0.95].
- C1/C2 (coherence/stability) stay high on the canonical CCBs (pre==post, no fragmentation), matching expectations.
- Any flagged dim above is a prompt-refinement candidate before these scores gate Constitution thresholds.
