# ADR-0106 — A test that would pass on its own fallback tests nothing

**Status:** accepted · **Decided by:** Ivan Green, 22 September 2026 · **Built.**

---

## The ruling

> **A test that would pass on its own fallback tests nothing.**
> `test_a_pass_carries_its_basis.py:393` asserts temperature `0.0`, and `DEFAULT_TEMPERATURE` is
> `0.0`, so it passes whether the Village declaration was read or not. Assert a declared value that
> differs from every default. Then sweep for the same shape elsewhere.

---

## The shape

```python
assert identity["settings"]["temperature"] == 0.0
```

```python
# src/services/agent_runtime/runtime.py
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_TOKENS = 2048
```

The assertion is **true of the value** and **silent about the mechanism.** If the declared setting
never travelled, `generation_settings` fills `temperature` from `DEFAULT_TEMPERATURE` and the test
passes on the fallback it was written to rule out.

Not a hypothetical: this is the same class as `run_timeout_sweep` reporting seven closures it never
made (ADR-0105) and `test_a_pass_carries_its_basis` before ADR-0104 — an assertion that holds under
both the working and the broken implementation.

## The worse instance the sweep found first

`test_operation_battery_run.py:710`:

```python
assert identity_read["settings"] == {"temperature": 0.0, "max_tokens": 2048}
```

**Both** values equal to **both** defaults, on the fixture path whose whole point is that
`read_village_agent_model` parsed a real `config.yaml` — and whose fixture declared `0.0` and
`2048`, the same two numbers. If `read_village_agent_model` had raised, `declared = {}`, the
runtime would fall back, and every assertion downstream would read identically.

---

## Built

### Values no default can produce

`EXAM_SETTINGS = {"temperature": 0.37, "max_tokens": 1536}`, used by `_examiner_pinned`'s
declaration and by `_runtime`'s generation block. `LOCAL_IDENTITY["settings"]` becomes the same
pair.

**And they are not the live Village's `0.7 / 4000` either.** A fixture matching production would
pass without the declaration being read too — the same blindness one step further out.

### The guard is the test

```python
assert LOCAL_IDENTITY["settings"]["temperature"] != DEFAULT_TEMPERATURE
assert LOCAL_IDENTITY["settings"]["max_tokens"] != DEFAULT_MAX_TOKENS
```

Without those two lines, a later edit could drift the fixture back to `0.0` and nothing would
notice. `test_exam_attempts_and_production_settings.py:90` already did exactly this — it asserts
`PRODUCTION["temperature"] != DEFAULT_TEMPERATURE`. **The pattern existed in this repository and
was applied in one place.**

### The sweep, made permanent

`test_no_test_asserts_a_generation_setting_at_its_own_default` walks every test file and fails on
an assertion of `temperature == 0.0` or `max_tokens == 2048`. A grep finds today's instances; this
fails the day another is written.

---

## What the sweep found, and what it did not

Scanned every `assert` in the suite against every `DEFAULT_*`/`*_FALLBACK` constant in `src`, then
narrowed to assertions on **the field that constant is the fallback for**. Four instances of the
shape:

| | |
|---|---|
| `test_a_pass_carries_its_basis.py:393` | `temperature == 0.0` — the named one |
| `test_operation_battery_run.py:710` | `{"temperature": 0.0, "max_tokens": 2048}` — both, on the declaration path |
| `test_ollama_provider.py:49` | passes `temperature=0.0`, asserts the provider forwarded `0.0` — and `0.0` is the signature's own default, so a dropped argument reads the same |
| `test_anthropic_provider.py:43` | same |

All four fixed. The two provider tests now pass `0.42`.

**And several that are not the shape, which matters as much.** A literal equal to a default is a
coincidence unless something *declared* a competing value:

- `test_dashboards_1004.py:29` — `min_per_cell == 3` with `DEFAULT_MIN_PER_CELL = 3`. Nothing
  configured a threshold; the test asserts that the heatmap reports its own. Correct as written.
- `test_locales.py:26` — `locale == "en"` with `_DEFAULT_LOCALE = "en"`, in a test named
  `test_pack_locale_defaults_to_en`. It is *about* the default.
- `test_office_bridge.py:269` — `window_minutes == 180` with `DEFAULT_RUN_WINDOW_MINUTES = 180`,
  and the `START` payload declares no window. The default is the subject.
- `test_cadence.py:178` — asserts the constant itself, deliberately.

The scanner is scoped to the two generation settings for this reason. **A scan for every literal
equal to every default would flag all of these and be turned off within a week.**

---

## Negative controls

* One assertion reverted to `0.0` → the scanner test fails and names the file and line.
* The guards on `EXAM_SETTINGS` and `LOCAL_IDENTITY` fail if either drifts back to a default.

Suite: **1,224 pass, 2 skip.** `ruff` clean.

---

## Worth keeping

**An assertion is evidence only if it could have failed.** This week produced four defects of one
shape — a report that could not be wrong, a sweep that reported what it did not do, a flag with
nothing tying it to the fact, and now a value indistinguishable from its own fallback. The question
that catches all four is the same: *what would this look like if the mechanism were absent?*
