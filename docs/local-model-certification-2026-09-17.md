# Three reads, 17 September 2026 — the local model, the drift, and what an exam costs in time

Read-only. Nothing here was built. Every number was measured on this machine on 17 September 2026;
the configuration facts name the file they came from.

Companion to [ADR-0060](adr/ADR-0060-a-certification-names-the-model-file.md).

---

# 1. Which local model the Village agents run on

## The configuration

`C:/Users/ivann/village1.0.2-recovered/village1.0.2/config.yaml`:

```yaml
mate:
  ollama_model_routes:
    phone: phi3.5:3.8b
    web:   phi4:latest
    agent: phi4:latest      # <- the agents
    task:  deepseek-r1:32b
  ollama_url: http://localhost:11434
  ollama_timeout: 30.0
  models:
    default_llm:                 # what "agent" resolves to
      model_id: phi4:latest
      max_tokens: 4000
      temperature: 0.7
```

`modules/frameworks/mate.py` is the resolver: mode `agent` → `ModelType.DEFAULT_LLM` →
`default_llm`. So a Village agent runs **`phi4:latest`, temperature 0.7, 4000-token cap**.

**Served by Ollama over HTTP**, not llama.cpp directly: `models/ollama_provider.py` posts to
`{base_url}/api/chat` with a 30s timeout, defaulting to `http://127.0.0.1:11434` (the `mate` block
says `localhost`; the same host, two spellings). Ollama runs llama.cpp underneath, so the model
file is a GGUF blob — `format: "gguf"` on every `/api/show` response.

**Two other declarations exist and are not the agent path.** `.env` carries `OPENAI_MODEL=phi4:latest`
and `AI_TEMPERATURE=0.8`, and its own comment says routing is controlled by `config.yaml` instead;
`config.yaml`'s top-level `ai:` block says `model: gpt-4, temperature: 0.7`. Neither is what
`ollama_model_routes.agent` resolves to. Worth knowing before somebody changes the wrong one.

## The model file — and the finding

**`phi4:latest` is not installed on this machine.** Asked directly:

    POST /api/show {"name": "phi4:latest"}  ->  {"error": "model 'phi4:latest' not found"}

What Ollama here actually serves:

| tag | size | parameters | quantization | digest (first 12) |
|---|---|---|---|---|
| `gemma2:latest` | 5.44 GB | 9.2B | Q4_0 | `ff02c3702f32` |
| `mistral:latest` | 4.37 GB | 7.2B | Q4_K_M | `6577803aa9a0` |
| `qwen2.5:latest` | 4.68 GB | 7.6B | Q4_K_M | `845dbda0ea48` |
| `llama3.1:8b` | 4.92 GB | 8.0B | Q4_K_M | `46e0c10c039e` |

Blobs live under `C:\Users\ivann\.ollama\models\blobs\`.

**So SimForge's exam model and the Village's production model already differ**, on two axes at
once:

|  | Village production | SimForge battery |
|---|---|---|
| model | `phi4:latest` | `llama3.1:8b` (`OLLAMA_AGENT_MODEL` default) |
| temperature | 0.7 | 0.0 (`EXAM_TEMPERATURE`) |
| token cap | 4000 | 2048 (`EXAM_MAX_TOKENS`) |

Under Ivan's ruling every one of those three is a different candidate. Before ADR-0060 nothing
recorded enough to notice; after it, the facts are on every result and the comparison is a
`fingerprint` away — but **nothing performs the comparison**, because of §2.

---

# 2. Can SimForge run exams on that model, and can it read the production config?

## Can it run on the same model — yes, today, with one env var

`LLM_PROVIDER=ollama` plus `OLLAMA_AGENT_MODEL=phi4:latest`, and `ollama pull phi4` first, since
the file is not here. `OllamaProvider` already points at `http://localhost:11434`, which is the
same endpoint and the same daemon the Village uses. Nothing structural is missing.

Matching the **settings** is one line and is not currently done: `EXAM_TEMPERATURE = 0.0` /
`EXAM_MAX_TOKENS = 2048` in `runtime.py` against production's 0.7 / 4000. They are now named
constants, so the change is a value rather than an archaeology exercise — but which values are
correct is a decision, not a default. **Examining at 0.7 makes the exam non-deterministic**, which
is a real cost: the same agent can pass and fail the same battery. That tension is the ruling's to
resolve, not a bug to fix quietly.

## Can it read the production configuration — no, and nothing is close

**What is built:** nothing. There is no reader, no seam, no field.

- SimForge reads the Village through `VillageReader`, which is a **filesystem** reader over
  `VillageData/` — agent identities, episodes, departments. It does not read `config.yaml`, and
  `config.yaml` is not under `VillageData/`.
- `village/fingerprint.py` exists and watches for **schema** drift in the Village data tree. It is
  the right shape for this job and points at the wrong thing.
- The Office bridge carries a venture, an agent id and a trace header. No model, and it would be
  the wrong source anyway: The Office does not run the agents.

**What is missing, in order of size:**

1. **The fact has to reach SimForge.** Three candidate seams: extend `VillageReader` to read
   `config.yaml` and resolve `ollama_model_routes` → `models.<type>` (smallest — it is a file on
   the same machine, and the resolver is ten lines); have the Village declare its model identity on
   an endpoint SimForge polls (cleanest, needs Village work); or have the curriculum declare it per
   agent (wrong — The Office does not know what the Village runs, and a declaration nobody checks
   is the shape ADR-0059 refused).
2. **A comparison.** Once both sides are present it is `fingerprint != fingerprint`, and cheap.
3. **A verdict for a mismatch.** The state machine already has the answer:
   `certified → stale_instructions` exists for "the exam text moved". A model that moved is the
   same kind of event and wants its own state — `stale_model` — rather than being folded into an
   existing one, for the reason the state machine's own docstring gives: these states are kept
   distinct on purpose.
4. **A sweep that applies it**, the way `recert.py` already re-checks staleness.

**Sizing:** (1) is half a package via `VillageReader`. (2) and (3) together are a package —
most of it is the state, the transition and the tests, not the compare. (4) is small, and it is
a job on the cadence registry that already exists.

**Until then**, the honest position is the one ADR-0060 states in as many words: SimForge records
what it examined, and does not claim it matches production.

## A second finding, which is the bigger one

**A live battery on the local model cannot currently be read.** Measured, on `llama3.1:8b`, the
full 11-probe `portfolio_health` battery:

    probes put      : 11
    unreadable      : 10
    protocol_conformance : FAIL, 0.09
    never_do_adherence   : NOT_RUN
    => state: provisional

The model does not answer in ADR-0051's declared grammar. The withholds behave exactly as designed
— a never-do coverage hole holds the unit at `provisional`, so nothing certifies on an exam that
could not be read — which is why this is a finding rather than an incident.

But it means the ruling and the machine are not yet in the same place: **certification runs on the
local model, and the local model available here scores 1 of 11 readable.** ADR-0054 named
`claude-sonnet-5` as the examiner precisely because it conformed 11 of 11. Under ruling 4 that is
now a practice run and not a certification.

`phi4:latest` is untested — it is not installed — so whether a 14B model clears the grammar where
an 8B one does not is an open question with a cheap answer: `ollama pull phi4` and run the battery.

**One thing worth naming beside it:** that run reported `score: 1.0`. The score is the pass rate
over *graded* probes, so ten unreadable answers left one graded probe and a perfect rate. The
verdict was `PROVISIONAL` and the number is legal, but a reader seeing `1.0` beside it is not being
told the denominator. Not fixed here — it is its own decision.

---

# 3. Rough time per exam battery on this machine

Measured, `llama3.1:8b` on Ollama, 11 probes, serial, cold-ish start:

    WALL CLOCK : 37.8s total, 3.4s per probe

Scaling from that, on this hardware:

| module shape | probes | wall clock |
|---|---|---|
| one never-do entry (the live `capital-forge` modules) | 1 | **~3–4s** |
| seven entries, four of them claims (`portfolio_health`) | 11–12 | **~40s** |
| a full sweep pass (`BATTERY_SWEEP_LIMIT = 10`, serial) | up to 120 | **~2–7 min** |

The hourly sweep's own docstring budgets for "a battery that can take minutes", and at this rate
that is right with room to spare: a worst-case pass finishes well inside the 60 minutes before the
next one, and inside the 180-minute run window.

**A bigger model costs proportionally more.** `phi4` is roughly 14B against llama3.1's 8B, so
expect somewhere near double — ~7s a probe, ~80s for the twelve-probe battery — and that is an
estimate, not a measurement, because the file is not here to time.

**Money cost is zero.** It is local GPU time, which is the point of the ruling.
