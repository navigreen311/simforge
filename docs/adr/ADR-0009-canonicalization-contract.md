# ADR-0009 — Canonicalization contract

**Status:** Accepted (2026-07-21).

## Context
ADR-0007 showed that Prisma `DateTime` → Postgres `timestamp(3)` coercion (tz-aware + microsecond
rounding) broke CertSnapshot **signature verification**, because the signed bytes differed from
the round-tripped bytes. The same class of "equal value → different bytes" bug threatens every
hash-dependent operation: **LLM cache keys** (dict order / float formatting), **CCB content
hashes**, **CertSnapshot signing**, and **lineage edge dedup**.

## Decision
Every hash-dependent operation applies **`src/utils/hashing.py::canonicalize_json()`** before
hashing. The canonical form is:
- **sorted keys** (order-independent),
- **no whitespace** (`separators=(",", ":")`),
- **stable float encoding** (`repr()` shortest round-trip — no `1e-5` vs `0.00001` variance),
- **naive-UTC datetimes truncated to milliseconds** (matches `timestamp(3)`; ADR-0007).

`sha256_hex(obj)` = `sha256(canonicalize_json(obj))`.

## Consequences
- The LLM cache (`LLMResponseCache.key_for`) uses `sha256_hex` — equal requests always hit the
  same entry regardless of dict order.
- New hash-consumers **must** route through the canonicalizer. Existing consumers
  (CertSnapshot canonical JSON, CCB content hash) already encode datetimes/floats stably and are
  compatible; migrating them to `canonicalize_json` is a low-risk follow-up.

## Cross-references
ADR-0007 (timestamp precision), ADR-0008 (LLM cache keys), blueprint §C.7, §F.2.
