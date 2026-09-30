# SimForge backlog

Items ruled as needed and not yet built. Newest first. Each names who ruled it
and what it would take. Move an item to an ADR when it is built.

---

## Partition author and sealer are verified by typed name only

**Ruled by Ivan Green, 2026-09-30.** Needs real verification.

- `scripts/author_partition.py` takes `--by` and `--sealed-by` as free text.
  It refuses The Office's name, non-person strings, and a sealer whose name
  matches the author (ADR-0108 R1, ADR-0113).
- It verifies no identity. Anyone who can run the CLI with SimForge's
  credentials can type both names. The two-person rule is recorded, not
  enforced.
- **Direction:** tie author and sealer to The Office's MFA (The Office's
  decisions entry 215): each act carries a verified identity assertion, and
  seal refuses when the two identities are the same person or unverified.
- **Open:** where the assertion is minted, how SimForge verifies it offline,
  and whether existing sealed partitions are grandfathered.
