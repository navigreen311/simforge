# ADR-0088 — A path is reported by whether it resolves

**Status:** accepted · **Decided by:** Ivan Green, 19 September 2026 · **Built.**
**Follows:** [ADR-0084](ADR-0084-a-live-process-is-not-an-up-to-date-one.md), whose endpoint hid one
of the settings this fixes.

---

## The ruling

**Set `EXAM_MODEL_DIGEST` to phi4's digest, `VILLAGE_CONFIG_PATH` and `VILLAGE_DB_PATH` to their real
locations. Put them where a restart keeps them, not only in one shell. `/api/version` reports
whether a path resolves, not just whether it has a value. Leave `SCHEDULER_ENABLED` off.**

---

## The settings, and the one that would have bitten

In `.env`, which pydantic reads on every start (`env_file=(".env", "../../.env")`) — not a shell
export, which is how `SCHEDULER_ENABLED` disappeared on 19 September.

```
VILLAGE_CONFIG_PATH=…/village1.0.2-recovered/village1.0.2/config.yaml
VILLAGE_DB_PATH=…/village1.0.2-recovered/village1.0.2/village.db
EXAM_MODEL_DIGEST=sha256:ac896e5b8b34a1f4efa7b14d7520725140d5512484457fab45d2a4ea14c69dba
SCHEDULER_ENABLED=false
```

**The `sha256:` prefix is load-bearing and nearly went in wrong.** Ollama's `/api/tags` returns
**bare hex**, and `llm_client.py:326` writes `file_digest=f"sha256:{digest}"`. A pin copied straight
off the API would compare unequal and report `EXAMINER_TAG_MOVED` — *"the tag moved… every
certification earned under the old pin is against a model that no longer exists here"* — a drift
event that never happened, in the most alarming words the module owns. Checked against the code
before writing it; `.env.example` now says so.

## The endpoint fix

`configured: true` answered *is there a string*. For a path the useful question is *is there a
file*, and the two differ exactly where it matters: **`village_db_path` read as configured for two
days while pointing at nothing**, because it has a default and a default is a value.

```json
"paths": {
  "village_db_path": {"value_set": true, "is_default": false, "resolves": true},
  "village_data_path": {"value_set": true, "is_default": true,  "resolves": true}
}
```

**`is_default` is compared against the field's default, not `os.environ` — and the first attempt got
that wrong.** A value set in `.env` is not in the process environment: pydantic reads the file into
the settings object. An environment check reported every configured path as unconfigured, which is
the same class of wrong answer pointing the other way. The version endpoint has now produced a
misleading green and a misleading red inside two days, which is a decent argument for the tests that
now pin both.

**No path value is reported.** An absolute path carries a username and this route is public;
`resolves` is what an operator needs and the value is not. A test asserts the response body contains
no path.

## What a battery would refuse on now — checked, not started

Both gates run clean against the live configuration:

```
pin   sha256:ac896e5b…c69dba
live  sha256:ac896e5b…c69dba
EXAMINER  : OK
identity source: village_db
  victor_serath OK · ronan_valek OK · seraphine_valek OK
```

`check_examiner` passes all six of its refusals, including the two that were blocking: the digest is
pinned and the Village declares `phi4:latest` at 0.7/4000 through
`mate.ollama_model_routes.agent`. Identity resolves from `village.db` for all three Greenstone
agents — the hand-corrected rows of September are no longer needed.

**What would still stop one, in order:**

1. **Nothing starts it.** `SCHEDULER_ENABLED=false`, and no endpoint may trigger a battery
   (ADR-0050). This is the ruling's own instruction and it is the top of the list.
2. **`underwrite_deal` would skip** — `SKIP_NO_MODULE`. `ForgeInstructionSet` holds four of the five
   CRE Forge modules.
3. **Any run would still reach `provisional`, not `certified`** — nothing submits a `situation`, so
   every submitted key is `NOT_RUN` and ADR-0072's breadth rule holds it. That is the design working:
   a discipline-only run says so.

So the environment is no longer what blocks a verdict. **The remaining three are a scheduler switch,
an instruction set The Office owns, and one field on its payload.**

## Read-only alongside

[Wiring the grader and P3](../wiring-the-grader-and-p3-2026-09-19.md) — the caller written out, and
where it belongs, since ADR-0086 left that a decision.
