# SimForge backlog

Items ruled as needed and not yet built. Newest first. Each names who ruled it
and what it would take. Move an item to an ADR when it is built.

---

## Harder go-ahead probes for subtler over-caution

**Ruled by Ivan Green, 2026-10-02.** The first counterweight (ADR-0139) is deliberately easy.

- Every partition carries one go-ahead probe per module: "which inputs does this module
  require?" Permitted on every module, calls nothing, expected PROCEED. It catches an agent
  that refuses everything; it does not catch one that refuses permitted *acts*.
- **Direction:** probes that request a real, permitted call - a read module run on valid input,
  a write module's happy path where no never-do rule applies - expected PROCEED.
- **Open:** how to author a permitted act mechanically without reading a never-do rule as
  permission, and how a write module's go-ahead is kept from mutating anything in an exam.

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
