# Three reads, 17 September 2026 (evening) — phi4, the missing agents, and Unit B in plain words

Read-only. Measured on this machine at the time of writing.

Companion to [ADR-0061](adr/ADR-0061-the-examiner-is-the-production-model.md).

---

# 1. Is phi4 reachable from where SimForge runs?

**Yes. It was pulled today** — 17 September, 10:28 PDT — and it was not there this morning.

    name          phi4:latest
    digest        sha256:ac896e5b8b34a1f4efa7b14d7520725140d5512484457fab45d2a4ea14c69dba
    size          9,053,116,391 bytes (9.05 GB)
    parameters    14.7B
    quantization  Q4_K_M
    format        gguf
    context       16384

That digest is the pin. It is now what `EXAM_MODEL_DIGEST` must hold, and `check_examiner` refuses
a battery whose `phi4:latest` serves anything else.

## Is it the same Ollama the Village uses?

**Yes — one instance, one port, verified two ways.**

- The Village points at `http://localhost:11434` (`mate.ollama_url`) and `http://127.0.0.1:11434`
  (`models/ollama_provider.py`'s default). SimForge points at `http://localhost:11434`
  (`OLLAMA_BASE_URL`).
- Only one process listens there: PID 24528 on `127.0.0.1:11434`. There is no second daemon and no
  container mapping that port.

So the model file SimForge would examine on is the same blob under
`C:\Users\ivann\.ollama\models\blobs\` that a Village agent call would load. The pin is not an
assertion about two machines agreeing; it is one file.

**Verified live, end to end**, with the real Ollama and the real Village config:

    village declares : phi4:latest  (mate.ollama_model_routes.agent)
    examiner         : phi4:latest @ sha256:ac896e5b8b34... Q4_K_M 14.7B
    check_examiner   : OK
    divergence       : temperature village 0.7 / exam 0.0 · max_tokens 4000 / 2048

---

# 2. Why `get_agent_identity` cannot find the three Office UUIDs

## Where SimForge looks

One place, and it is a directory name:

    VillageReader.agent_root(id)  ->  {VILLAGE_DATA_PATH}/agents/{id}
    get_agent_identity(id)        ->  that directory / identity.json

`VILLAGE_DATA_PATH` is `./village-data-local/VillageData`, a **synthetic dev fixture with eight
agents**: `david_kim`, `gardner`, `jennifer_adams`, `marcus_reed`, `nina_okafor`, `priya_patel`,
`sara_lopez`, `taylor_zhang`. Directory names are Village refs, in snake case.

The Office sends `office_agent_id`, a uuid — `provisioning.py:882` passes it as `agent_id` on
`run/start`, and the run rows carry it. So SimForge looks for a directory literally named
`e27fc174-01ac-4090-8127-f4f0cec91bf9`, and there is not one.

## The mapping exists — on the other side

The Office already records it, in `office_agent_identity`:

| office_agent_id | village_agent_ref | name | department |
|---|---|---|---|
| `e27fc174…` | `victor_serath` | Victor Serath | research |
| `c8afb0e6…` | `seraphine_valek` | Seraphine Valek | operations |
| `cc49a49c…` | `ronan_valek` | Ronan Valek | operations |

**It never crosses the boundary.** `OperationRunStartRequest` has no field for it.

## CORRECTION (same day, later): the ref would not be enough — but not for the reason below

**The three agents DO exist in the real Village.** They are in `village.db` with exactly these ids,
matching departments. What the section below actually checked was `VillageData/agents/` — the
per-agent framework directories — and reported "the agents do not exist" when the true statement was
"the directory tree does not have them".

The larger finding it hid: the tree and the database share **one agent out of 186 and 114**. They
are two different populations, and `VillageReader` has been reading a stale one.

Corrected in full in
[exam-timing-and-the-three-agents-2026-09-17.md](exam-timing-and-the-three-agents-2026-09-17.md)
§2, which also revises the three fixes below — fix 3 changes from "decide whether these agents
exist" to "make the tree describe the agents that do". The paragraph below is left standing, wrong,
so the correction has something to point at.

## And the ref would not be enough either

    real Village tree: C:/Users/ivann/village1.0.2-recovered/village1.0.2/VillageData/agents
    114 agents; victor_serath, seraphine_valek, ronan_valek: ABSENT

The Office's own `village_agent` roster holds 187 rows and **every one is `source='import'`** —
imported into The Office, not synced from a Village tree. So these three are Office identities that
no Village instance has an agent directory for.

## What connecting them takes

Three things, and they are three decisions, not one:

1. **Carry the ref.** Add `village_agent_ref` to `run/start` (an optional string; The Office already
   has the value). Small on both sides — a field, a column, a manifest line.
2. **Point SimForge at a real tree.** `VILLAGE_DATA_PATH` is the eight-agent fixture. The real tree
   is on this machine and has 114 agents. One env var — but see (3) before turning it.
3. **Decide whether these agents exist in the Village at all.** They are in none of the 114. Either
   the Village gains them, or they are a different population and the certification is not about
   Village OS agents. **That is the question, and (1) and (2) cannot answer it.**

Until then ADR-0061 ruling 2 does the honest thing: the battery refuses, loudly, by name.

---

# 3. Unit B in plain English

## What a department exam is meant to prove

Unit A asks: *can this agent drive this one tool?* Victor Serath, `property_lookup` — does he know
what it does, and does he know what he must never do with it.

Unit B asks a different question about the same work: **is the department around him a safe place
for that tool to be used?** Two things, concretely:

- **When something needs a person, does it actually reach one?** Every module has cases where the
  agent must stop and hand over. Unit B is the claim that the hand-over lands somewhere — that there
  is a named human, that they are reachable, and that the path is not a dead end.
- **Do the department's rules match the work?** Greenstone's research department operates a
  different set of tools than banking, under different obligations. Unit B says the department's
  compliance setup covers what its people actually do.

So Unit A certifies a person's competence. Unit B certifies their surroundings. The Office requires
**both** for every grant, which is why a perfect Unit A result alone does not open Gate 9.

Today nothing scores Unit B at all. The two things it is supposed to check — the hand-over path and
the compliance match — arrive as two boxes on the form, both default to *unchecked*, and nothing
reads them. A department is currently certified by nobody having said no.

## The three options, and what each costs

**Option A — make the two boxes count.**
Today a department passes with both boxes unticked. The smallest change is to require them: both
ticked, or the department is held short of certified.
*What it costs:* the boxes are still just claims. Whoever submits the exam ticks them; nobody
checks. It stops the silent pass and buys no actual evidence. **It is a stop-gap, and it should be
called one.**

**Option B — actually test the hand-over.**
Give the department the same kind of exam the agent gets: put it a situation that can only be
resolved by stopping and escalating, and see whether it reaches the named human.
*What it costs:* SimForge does not know who the humans are. Who a department escalates to is
Office data, and it would have to cross a boundary that does not exist yet. **This is the only
option that produces evidence, and it is the most work.**

**Option C — infer it from the agents.**
If every tool the department uses has a certified agent, call the department certified too. No new
exam.
*What it costs:* it stops being a second question. The Office asks for two certifications because
they check different things; if the second is computed from the first, the second gate is a
restatement of the first and the system has one check wearing two names. **Cheapest, and it quietly
removes a safeguard.**

**My recommendation, unchanged:** A now so departments stop passing on silence, B as the real
answer, and C rejected rather than deferred — a derived Unit B is worse than an honest gap, because
a gap is visible.
