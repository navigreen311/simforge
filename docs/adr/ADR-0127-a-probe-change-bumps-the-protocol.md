# ADR-0127 — A change to what a probe asks bumps the protocol version

**Status:** accepted · **Decided by:** Ivan Green, 2026-09-25 · **Built.**

---

## The ruling

> A change to what a probe asks bumps the protocol version. ADR-0126 changed
> the request a decline probe sends and left the version at 7.0.0.
>
> *Measured: all six Greenstone refs are unchanged, SimForge holds every one
> graded, so a fresh run would return the old verdicts and the identical
> scores would read as "the probe change made no difference". ADR-0119 bumped
> for a layout change; this is more than layout. ADR-0120's guard assumes the
> ref names the protocol a run was put under.*
>
> Bump to 8.0.0.

## 7.0.0 results are not comparable

**Nothing measured at 7.0.0 may be compared with anything measured at 8.0.0.**

That covers every decline-probe verdict, every `never_do_violation` class
verdict, every score and dimension a decline probe fed, and every Gate 9.5
sitting. It holds for probes whose verdict came out the same: at 7.0.0 the
five decline probes that carried a reason were handed their justification
for refusing, and at 8.0.0 they are not.

ADR-0126 said "no protocol change; no version bump". That was wrong, and this
ADR corrects it.

## Built

- `RESPONSE_PROTOCOL_VERSION` is `8.0.0`. The block text did not move, so
  its ADR-0103 pin is the same hash under the new version.
- **What a probe asks is now pinned too.**
  `test_a_probe_change_bumps_the_protocol` hashes every probe the three
  builders put on frozen fixtures: the battery's decline and over-read
  probes, the partition's framings, and a submitted key's probe. The hash is
  pinned to the version. Change a builder and the test fails until the
  version moves.
- ADR-0103 pinned how an agent is told to answer. This pins what it is asked.
  Between them, nothing an agent reads can move without a bump.

## What the bump does

- **Every 7.0.0 ref is refused** (ADR-0120). The Office must mint `:p8.0.0`
  refs for a fresh exam, and SimForge grades those anew.
- **Every 7.0.0 partition sitting is due** (ADR-0123).
- **Gate 9.5 reads 8.0.0 sittings only** (ADR-0122). Until one exists,
  Greenstone's verdict is `NOT_RUN`, not PASS.

## Still open

**A sealed partition does not record which protocol authored its probes.**
Partition bodies are stored at authoring. `…EWV64P` was authored before
ADR-0126 and still carries the old requests. Sat now, it would be recorded as
8.0.0 while asking 7.0.0 questions. A partition authored after this ADR asks
8.0.0 questions. Nothing enforces the difference: author a new partition
before sitting one.
